import os
import asyncio
import logging
from pathlib import Path
from typing import Optional, Set, Dict, Any
from datetime import datetime, timedelta
import hashlib
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent, FileMovedEvent

logger = logging.getLogger(__name__)

class FileEventHandler(FileSystemEventHandler):
    """Handle file system events"""
    
    def __init__(self, watcher):
        self.watcher = watcher
        
    def on_created(self, event):
        if not event.is_directory:
            asyncio.create_task(self.watcher.handle_file_event(event.src_path, "created"))
    
    def on_modified(self, event):
        if not event.is_directory:
            asyncio.create_task(self.watcher.handle_file_event(event.src_path, "modified"))
    
    def on_moved(self, event):
        if not event.is_directory:
            asyncio.create_task(self.watcher.handle_file_event(event.dest_path, "moved"))

class DriveWatcher:
    """Watch drive for media files and trigger processing"""
    
    def __init__(self, path: str, nats_service=None):
        self.path = Path(path)
        self.nats = nats_service
        self.observer: Optional[Observer] = None
        self.running = False
        self.file_tracker: Dict[str, Dict[str, Any]] = {}
        self.quiet_seconds = int(os.getenv("FILE_QUIET_SECONDS", "45"))
        self.poll_interval = int(os.getenv("WATCH_POLL_INTERVAL", "5"))
        
        # Media file extensions to watch
        self.media_extensions = {
            ".mp4", ".mov", ".mkv", ".avi", ".webm", ".flv",
            ".mp3", ".wav", ".aac", ".flac", ".ogg",
            ".jpg", ".jpeg", ".png", ".gif", ".webp"
        }
        
    async def start(self):
        """Start watching the drive"""
        if not self.path.exists():
            logger.error(f"Path does not exist: {self.path}")
            return
        
        logger.info(f"Starting drive watcher for {self.path}")
        
        # Start watchdog observer
        self.observer = Observer()
        event_handler = FileEventHandler(self)
        self.observer.schedule(event_handler, str(self.path), recursive=True)
        self.observer.start()
        
        self.running = True
        
        # Scan existing files on startup
        await self.scan_existing()
        
        # Start file stability checker
        asyncio.create_task(self._check_file_stability())
        
        logger.info(f"Drive watcher started for {self.path}")
    
    async def stop(self):
        """Stop watching the drive"""
        logger.info(f"Stopping drive watcher for {self.path}")
        self.running = False
        
        if self.observer:
            self.observer.stop()
            self.observer.join()
        
        logger.info(f"Drive watcher stopped for {self.path}")
    
    async def handle_file_event(self, file_path: str, event_type: str):
        """Handle a file system event"""
        file_path = Path(file_path)
        
        # Check if file has media extension
        if file_path.suffix.lower() not in self.media_extensions:
            return
        
        # Track file for stability checking
        now = datetime.utcnow()
        
        if str(file_path) not in self.file_tracker:
            logger.info(f"Tracking new file: {file_path}")
            self.file_tracker[str(file_path)] = {
                "path": str(file_path),
                "first_seen": now,
                "last_modified": now,
                "size": self._get_file_size(file_path),
                "event_type": event_type
            }
        else:
            # Update last modified time and size
            self.file_tracker[str(file_path)].update({
                "last_modified": now,
                "size": self._get_file_size(file_path)
            })
    
    async def _check_file_stability(self):
        """Periodically check if files are stable (not being written)"""
        while self.running:
            try:
                now = datetime.utcnow()
                stable_files = []
                
                for file_path, info in list(self.file_tracker.items()):
                    # Check if file has been quiet for configured seconds
                    quiet_time = (now - info["last_modified"]).total_seconds()
                    
                    if quiet_time >= self.quiet_seconds:
                        # File is stable, check if it still exists and size hasn't changed
                        path = Path(file_path)
                        if path.exists():
                            current_size = self._get_file_size(path)
                            
                            if current_size == info["size"] and current_size > 0:
                                # File is stable and complete
                                stable_files.append(file_path)
                        else:
                            # File was deleted
                            del self.file_tracker[file_path]
                
                # Process stable files
                for file_path in stable_files:
                    await self._process_stable_file(file_path)
                    del self.file_tracker[file_path]
                
            except Exception as e:
                logger.error(f"Error in file stability checker: {e}")
            
            await asyncio.sleep(self.poll_interval)
    
    async def _process_stable_file(self, file_path: str):
        """Process a file that has become stable"""
        logger.info(f"File is stable, processing: {file_path}")
        
        # Publish file closed event
        if self.nats:
            await self.nats.publish_event(
                "file.closed",
                {
                    "path": file_path,
                    "drive": str(self.path),
                    "size": self._get_file_size(Path(file_path)),
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        
        # Trigger index job
        await self._trigger_index_job(file_path)
    
    async def _trigger_index_job(self, file_path: str):
        """Trigger an index job for the file"""
        if not self.nats:
            return
        
        # Generate job ID
        job_id = self._generate_job_id(file_path)
        
        # Create job data in the format expected by IndexJob
        job_data = {
            "id": job_id,
            "type": "index",
            "data": {
                "file_path": file_path,
                "drive": str(self.path),
                "force_reindex": False,
                "extract_scenes": False
            }
        }
        
        # Publish job
        try:
            await self.nats.publish_job("index", job_data)
            logger.info(f"Published index job for {file_path}")
        except Exception as e:
            logger.error(f"Failed to publish index job: {e}")
    
    def _get_file_size(self, path: Path) -> int:
        """Get file size safely"""
        try:
            return path.stat().st_size if path.exists() else 0
        except Exception:
            return 0
    
    def _generate_job_id(self, file_path: str) -> str:
        """Generate unique job ID"""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        hash_part = hashlib.md5(file_path.encode()).hexdigest()[:8]
        return f"idx_{timestamp}_{hash_part}"
    
    async def scan_existing(self):
        """Scan for existing files in the watched directory"""
        logger.info(f"Scanning existing files in {self.path}")
        
        count = 0
        for root, dirs, files in os.walk(self.path):
            for file in files:
                file_path = Path(root) / file
                
                # Check if media file
                if file_path.suffix.lower() in self.media_extensions:
                    # Check if file is already indexed
                    if not await self._is_indexed(str(file_path)):
                        await self._trigger_index_job(str(file_path))
                        count += 1
        
        logger.info(f"Queued {count} existing files for indexing")
    
    async def _is_indexed(self, file_path: str) -> bool:
        """Check if file is already indexed in database"""
        from app.api.db.database import get_db
        
        try:
            db = await get_db()
            async with db.execute(
                "SELECT id FROM so_assets WHERE abs_path = ?",
                (file_path,)
            ) as cursor:
                result = await cursor.fetchone()
                return result is not None
        except Exception:
            return False