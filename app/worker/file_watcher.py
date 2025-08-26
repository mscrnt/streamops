"""File watcher that monitors role-based paths for new recordings"""

import os
import asyncio
import logging
from pathlib import Path
from typing import Optional, Set, Dict, Any
from datetime import datetime, timedelta
import hashlib
import json

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent
import aiosqlite

logger = logging.getLogger(__name__)

class RecordingHandler(FileSystemEventHandler):
    """Handles file system events for recording folders"""
    
    def __init__(self, watcher):
        self.watcher = watcher
        self.pending_files = {}
        
    def on_created(self, event):
        if not event.is_directory:
            self.handle_file(event.src_path)
    
    def on_modified(self, event):
        if not event.is_directory:
            self.handle_file(event.src_path)
    
    def handle_file(self, file_path):
        """Track file for processing after quiet period"""
        # Filter by extension
        ext = Path(file_path).suffix.lower()
        if ext not in ['.mp4', '.mov', '.mkv', '.avi', '.flv', '.ts', '.m2ts']:
            return
        
        # Track file with timestamp
        self.pending_files[file_path] = datetime.utcnow()
        logger.info(f"Detected new file: {file_path}")


class FileWatcher:
    """Main file watcher that monitors role-based paths"""
    
    def __init__(self, db_path: str = "/data/db/streamops.db"):
        self.db_path = db_path
        self.observers = {}
        self.handlers = {}
        self.running = False
        self.quiet_period_sec = 45  # Default quiet period
        
    async def get_db(self):
        """Get database connection"""
        return await aiosqlite.connect(self.db_path)
    
    async def resolve_role_path(self, role: str) -> Optional[str]:
        """Resolve a role to its absolute path"""
        try:
            async with await self.get_db() as db:
                cursor = await db.execute(
                    "SELECT abs_path FROM so_roles WHERE role = ? AND watch = 1",
                    (role,)
                )
                row = await cursor.fetchone()
                return row[0] if row else None
        except Exception as e:
            logger.error(f"Failed to resolve role path for {role}: {e}")
            return None
    
    async def get_all_watched_roles(self) -> Dict[str, str]:
        """Get all roles that have watch enabled"""
        roles = {}
        try:
            async with await self.get_db() as db:
                cursor = await db.execute(
                    "SELECT role, abs_path FROM so_roles WHERE watch = 1"
                )
                rows = await cursor.fetchall()
                for role, path in rows:
                    if path and os.path.exists(path):
                        roles[role] = path
        except Exception as e:
            logger.error(f"Failed to get watched roles: {e}")
        return roles
    
    async def start_watching(self):
        """Start watching all configured role paths"""
        self.running = True
        
        while self.running:
            try:
                # Get current watched roles
                roles = await self.get_all_watched_roles()
                
                # Stop watchers for roles that are no longer watched
                for role in list(self.observers.keys()):
                    if role not in roles:
                        logger.info(f"Stopping watcher for role: {role}")
                        self.observers[role].stop()
                        del self.observers[role]
                        del self.handlers[role]
                
                # Start watchers for new roles
                for role, path in roles.items():
                    if role not in self.observers:
                        logger.info(f"Starting watcher for role {role}: {path}")
                        
                        handler = RecordingHandler(self)
                        observer = Observer()
                        observer.schedule(handler, path, recursive=True)
                        observer.start()
                        
                        self.observers[role] = observer
                        self.handlers[role] = handler
                
                # Process pending files
                await self.process_pending_files()
                
                # Sleep before next check
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"Error in watcher loop: {e}")
                await asyncio.sleep(10)
    
    async def process_pending_files(self):
        """Process files that have passed the quiet period"""
        now = datetime.utcnow()
        
        for handler in self.handlers.values():
            files_to_process = []
            
            for file_path, detected_time in list(handler.pending_files.items()):
                # Check if file has been quiet for the configured period
                if (now - detected_time).total_seconds() >= self.quiet_period_sec:
                    # Verify file still exists and is not being written
                    if os.path.exists(file_path):
                        try:
                            # Check if file size is stable
                            size1 = os.path.getsize(file_path)
                            await asyncio.sleep(1)
                            size2 = os.path.getsize(file_path)
                            
                            if size1 == size2:
                                files_to_process.append(file_path)
                                del handler.pending_files[file_path]
                            else:
                                # File still growing, update timestamp
                                handler.pending_files[file_path] = now
                        except Exception as e:
                            logger.warning(f"Error checking file {file_path}: {e}")
                            del handler.pending_files[file_path]
                    else:
                        # File no longer exists
                        del handler.pending_files[file_path]
            
            # Queue files for processing
            for file_path in files_to_process:
                await self.queue_file_for_processing(file_path)
    
    async def queue_file_for_processing(self, file_path: str):
        """Queue a file for processing"""
        try:
            async with await self.get_db() as db:
                # Check if file already indexed
                cursor = await db.execute(
                    "SELECT id FROM so_assets WHERE abs_path = ?",
                    (file_path,)
                )
                existing = await cursor.fetchone()
                
                if not existing:
                    # Get file stats
                    stat = os.stat(file_path)
                    file_id = hashlib.sha256(file_path.encode()).hexdigest()[:16]
                    
                    # Insert new asset
                    await db.execute("""
                        INSERT INTO so_assets 
                        (id, abs_path, size, mtime, ctime, status, created_at)
                        VALUES (?, ?, ?, ?, ?, 'pending', ?)
                    """, (
                        file_id,
                        file_path,
                        stat.st_size,
                        stat.st_mtime,
                        stat.st_ctime,
                        datetime.utcnow().isoformat()
                    ))
                    
                    # Create indexing job
                    job_id = hashlib.sha256(f"index_{file_path}".encode()).hexdigest()[:16]
                    await db.execute("""
                        INSERT INTO so_jobs
                        (id, type, asset_id, payload_json, state, created_at)
                        VALUES (?, 'index', ?, ?, 'queued', ?)
                    """, (
                        job_id,
                        file_id,
                        json.dumps({"path": file_path}),
                        datetime.utcnow().isoformat()
                    ))
                    
                    await db.commit()
                    logger.info(f"Queued file for processing: {file_path}")
                    
        except Exception as e:
            logger.error(f"Failed to queue file {file_path}: {e}")
    
    async def stop_watching(self):
        """Stop all watchers"""
        self.running = False
        
        for role, observer in self.observers.items():
            logger.info(f"Stopping watcher for role: {role}")
            observer.stop()
            observer.join()
        
        self.observers.clear()
        self.handlers.clear()


async def main():
    """Main entry point for file watcher"""
    watcher = FileWatcher()
    
    try:
        logger.info("Starting file watcher service...")
        await watcher.start_watching()
    except KeyboardInterrupt:
        logger.info("Shutting down file watcher...")
    finally:
        await watcher.stop_watching()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    asyncio.run(main())