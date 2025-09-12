from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)

class BaseJob(ABC):
    """Base class for all job processors"""
    
    def __init__(self):
        self.job_type = self.__class__.__name__.replace("Job", "").lower()
        
    @abstractmethod
    async def process(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process the job and return result"""
        pass
    
    async def validate(self, job_data: Dict[str, Any]) -> bool:
        """Validate job data before processing"""
        return True
    
    async def update_progress(self, job_id: str, progress: float, status: str = None):
        """Update job progress in database"""
        from app.api.db.database import get_db
        
        try:
            db = await get_db()
            
            # Update progress in so_progress table
            await db.execute("""
                INSERT INTO so_progress (job_id, progress, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(job_id) DO UPDATE SET
                    progress = excluded.progress,
                    updated_at = CURRENT_TIMESTAMP
            """, (job_id, progress))
            
            # Update job status if provided
            if status:
                await db.execute(
                    "UPDATE so_jobs SET state = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (status, job_id)
                )
            
            await db.commit()
            
        except Exception as e:
            logger.error(f"Failed to update job progress: {e}")
    
    async def run_command(self, cmd: list, cwd: str = None) -> tuple[int, str, str]:
        """Run a shell command and return exit code, stdout, stderr"""
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd
        )
        
        stdout, stderr = await process.communicate()
        
        return process.returncode, stdout.decode(), stderr.decode()
    
    def get_temp_path(self, job_id: str, extension: str = "") -> str:
        """Get temporary file path for job"""
        import os
        cache_dir = os.getenv("CACHE_DIR", "/data/cache")
        os.makedirs(cache_dir, exist_ok=True)
        
        filename = f"{job_id}{extension}"
        return os.path.join(cache_dir, filename)
    
    def cleanup_temp_files(self, job_id: str):
        """Clean up temporary files for job"""
        import os
        import glob
        
        cache_dir = os.getenv("CACHE_DIR", "/data/cache")
        pattern = os.path.join(cache_dir, f"{job_id}*")
        
        for file in glob.glob(pattern):
            try:
                os.remove(file)
            except Exception as e:
                logger.warning(f"Failed to remove temp file {file}: {e}")
    
    async def reindex_folder_assets(self, folder_path: str):
        """Reindex assets count for a folder path - used after move/copy/delete operations"""
        from app.api.db.database import get_db
        import os
        
        try:
            # Normalize the folder path
            folder_path = os.path.normpath(folder_path)
            if os.path.isfile(folder_path):
                folder_path = os.path.dirname(folder_path)
            
            logger.info(f"Reindexing assets for folder: {folder_path}")
            
            db = await get_db()
            
            # Find all media files in the folder and ensure they're indexed with correct current_path
            if os.path.exists(folder_path) and os.path.isdir(folder_path):
                for entry in os.listdir(folder_path):
                    entry_path = os.path.join(folder_path, entry)
                    if os.path.isfile(entry_path):
                        # Check if it's a media file based on extension
                        ext = os.path.splitext(entry)[1].lower()
                        if ext in ['.mp4', '.mov', '.mkv', '.avi', '.webm', '.flv', '.wmv', '.m4v', '.mpg', '.mpeg']:
                            # Check if this file is in the database
                            cursor = await db.execute("""
                                SELECT id, current_path FROM so_assets 
                                WHERE abs_path = ? OR current_path = ?
                            """, (entry_path, entry_path))
                            
                            row = await cursor.fetchone()
                            if row:
                                # Asset exists - update current_path if needed
                                if row[1] != entry_path:
                                    await db.execute("""
                                        UPDATE so_assets 
                                        SET current_path = ?, updated_at = datetime('now')
                                        WHERE id = ?
                                    """, (entry_path, row[0]))
                                    logger.debug(f"Updated current_path for asset {row[0]} to {entry_path}")
                            else:
                                # Asset not in database - this file needs to be indexed
                                # We can't fully index it here without media info, so just log it
                                logger.info(f"Found unindexed media file: {entry_path}")
                
                await db.commit()
            
            # Now count the assets properly
            cursor = await db.execute("""
                SELECT COUNT(*) FROM so_assets 
                WHERE current_path LIKE ? || '/%' 
                   AND current_path NOT LIKE ? || '/%/%'
            """, (folder_path, folder_path))
            
            db_count = (await cursor.fetchone())[0]
            logger.debug(f"Folder {folder_path} has {db_count} indexed assets")
            
        except Exception as e:
            logger.error(f"Failed to reindex folder {folder_path}: {e}")
    
    async def send_notification(self, event_type: str, data: Dict[str, Any]):
        """Send notification for job event"""
        try:
            # Check if notifications are enabled
            from app.api.services.settings_service import settings_service
            settings = await settings_service.get_settings()
            notif_settings = settings.get("notifications", {})
            
            if not notif_settings.get("enabled", False):
                return
            
            # Check if this event type is enabled
            event_key = f"events_{event_type.replace('.', '_')}"
            if not notif_settings.get(event_key, False):
                return
            
            # Initialize notification service
            from app.api.notifications.service import notification_service
            from app.api.notifications.providers.base import NotificationPriority
            
            # Build notification config from settings
            config = {
                "enabled": True,
                "rules": {},
                "templates": {}
            }
            
            # Add enabled channels
            channels = []
            if notif_settings.get("discord_enabled") and notif_settings.get("discord_webhook_url"):
                config["discord"] = {
                    "enabled": True,
                    "webhook_url": notif_settings["discord_webhook_url"],
                    "username": notif_settings.get("discord_username", "StreamOps")
                }
                channels.append("discord")
            
            if notif_settings.get("email_enabled") and notif_settings.get("email_smtp_host"):
                config["email"] = {
                    "enabled": True,
                    "smtp_host": notif_settings["email_smtp_host"],
                    "smtp_port": notif_settings.get("email_smtp_port", 587),
                    "smtp_user": notif_settings.get("email_smtp_user"),
                    "smtp_pass": notif_settings.get("email_smtp_pass"),
                    "from_email": notif_settings.get("email_from"),
                    "to_emails": notif_settings.get("email_to", [])
                }
                channels.append("email")
            
            if notif_settings.get("twitter_enabled"):
                config["twitter"] = {
                    "enabled": True,
                    "auth_type": notif_settings.get("twitter_auth_type", "bearer"),
                    "bearer_token": notif_settings.get("twitter_bearer_token"),
                    "api_key": notif_settings.get("twitter_api_key"),
                    "api_secret": notif_settings.get("twitter_api_secret"),
                    "access_token": notif_settings.get("twitter_access_token"),
                    "access_secret": notif_settings.get("twitter_access_secret")
                }
                channels.append("twitter")
            
            if notif_settings.get("webhook_enabled") and notif_settings.get("webhook_endpoints"):
                config["webhook"] = {
                    "enabled": True,
                    "endpoints": notif_settings["webhook_endpoints"]
                }
                channels.append("webhook")
            
            if not channels:
                logger.debug("No notification channels enabled")
                return
            
            # Set up rules for this event
            config["rules"][event_type] = {
                "channels": channels
            }
            
            # Initialize and send
            await notification_service.initialize(config)
            
            # Determine priority based on event type
            priority = NotificationPriority.NORMAL
            if "failed" in event_type:
                priority = NotificationPriority.HIGH
            elif "completed" in event_type:
                priority = NotificationPriority.LOW
            
            results = await notification_service.send_event(
                event_type=event_type,
                data=data,
                priority=priority
            )
            
            for result in results:
                if not result.success:
                    logger.warning(f"Failed to send {event_type} notification via {result.channel}: {result.error}")
                    
        except Exception as e:
            logger.error(f"Failed to send notification for {event_type}: {e}")