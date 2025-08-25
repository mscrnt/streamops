import os
import asyncio
import logging
import signal
from typing import Dict, Any
from datetime import datetime

from app.api.services.nats_service import NATSService
from app.api.db.database import init_db, close_db
from app.worker.jobs.remux import RemuxJob
from app.worker.jobs.thumbnail import ThumbnailJob
from app.worker.jobs.proxy import ProxyJob
from app.worker.jobs.transcode import TranscodeJob
from app.worker.jobs.index import IndexJob
from app.worker.watchers.drive_watcher import DriveWatcher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Worker:
    def __init__(self):
        self.nats: NATSService = None
        self.running = False
        self.watchers = []
        self.job_handlers = {
            "remux": RemuxJob(),
            "thumbnail": ThumbnailJob(),
            "proxy": ProxyJob(),
            "transcode": TranscodeJob(),
            "index": IndexJob(),
        }
        
    async def start(self):
        """Start the worker process"""
        logger.info("Starting StreamOps Worker...")
        
        # Initialize database
        await init_db()
        
        # Connect to NATS
        if os.getenv("NATS_ENABLE", "true").lower() == "true":
            self.nats = NATSService()
            await self.nats.connect()
            
            # Subscribe to job queues
            await self._subscribe_to_jobs()
        
        # Start drive watchers
        await self._start_watchers()
        
        self.running = True
        logger.info("StreamOps Worker started successfully")
        
        # Keep running
        try:
            while self.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop the worker process"""
        logger.info("Stopping StreamOps Worker...")
        self.running = False
        
        # Stop watchers
        for watcher in self.watchers:
            await watcher.stop()
        
        # Disconnect from NATS
        if self.nats:
            await self.nats.disconnect()
        
        # Close database
        await close_db()
        
        logger.info("StreamOps Worker stopped")
    
    async def _subscribe_to_jobs(self):
        """Subscribe to job queues"""
        for job_type, handler in self.job_handlers.items():
            await self.nats.subscribe_jobs(
                job_type,
                self._create_job_handler(handler),
                queue_group="workers"
            )
            logger.info(f"Subscribed to {job_type} jobs")
    
    def _create_job_handler(self, handler):
        """Create a job handler function"""
        async def handle_job(job_data: Dict[str, Any]):
            job_id = job_data.get("id")
            logger.info(f"Processing job {job_id} of type {job_data.get('type')}")
            
            try:
                # Check guardrails before processing
                if await self._check_guardrails():
                    # Process the job
                    result = await handler.process(job_data)
                    
                    # Update job status
                    await self._update_job_status(job_id, "completed", result)
                    
                    # Publish completion event
                    if self.nats:
                        await self.nats.publish_event(
                            "job.completed",
                            {"job_id": job_id, "result": result}
                        )
                else:
                    # Pause job due to guardrails
                    await self._update_job_status(job_id, "paused", None)
                    logger.info(f"Job {job_id} paused due to guardrails")
                    
            except Exception as e:
                logger.error(f"Error processing job {job_id}: {e}")
                await self._update_job_status(job_id, "error", str(e))
                
                # Publish error event
                if self.nats:
                    await self.nats.publish_event(
                        "job.error",
                        {"job_id": job_id, "error": str(e)}
                    )
        
        return handle_job
    
    async def _check_guardrails(self) -> bool:
        """Check if processing should proceed based on guardrails"""
        import psutil
        
        # Check CPU usage
        cpu_limit = int(os.getenv("CPU_GUARD_PCT", "70"))
        cpu_percent = psutil.cpu_percent(interval=1)
        if cpu_percent > cpu_limit:
            logger.warning(f"CPU usage {cpu_percent}% exceeds limit {cpu_limit}%")
            return False
        
        # Check GPU usage (if available)
        gpu_limit = int(os.getenv("GPU_GUARD_PCT", "40"))
        try:
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            gpu_util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            if gpu_util.gpu > gpu_limit:
                logger.warning(f"GPU usage {gpu_util.gpu}% exceeds limit {gpu_limit}%")
                return False
        except Exception:
            pass
        
        # Check if OBS is recording (if configured)
        if os.getenv("PAUSE_WHEN_RECORDING", "true").lower() == "true":
            # Check OBS recording status via WebSocket if configured
            obs_url = os.getenv("OBS_WS_URL")
            if obs_url:
                try:
                    from app.api.services.obs_service import OBSService
                    obs = OBSService()
                    if await obs.is_recording():
                        logger.info("OBS is recording, pausing job processing")
                        return False
                except Exception as e:
                    logger.warning(f"Failed to check OBS status: {e}")
                    # Continue processing if we can't check OBS status
        
        return True
    
    async def _update_job_status(self, job_id: str, status: str, result: Any):
        """Update job status in database"""
        from app.api.db.database import get_db
        
        try:
            db = await get_db()
            await db.execute(
                """
                UPDATE so_jobs 
                SET state = ?, error = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, result if status == "error" else None, job_id)
            )
            await db.commit()
        except Exception as e:
            logger.error(f"Failed to update job status: {e}")
    
    async def _start_watchers(self):
        """Start drive watchers"""
        # Get configured drives from environment or config
        drives = os.getenv("WATCH_DRIVES", "").split(",")
        
        for drive in drives:
            if drive:
                try:
                    watcher = DriveWatcher(drive, self.nats)
                    await watcher.start()
                    self.watchers.append(watcher)
                    logger.info(f"Started watcher for {drive}")
                except Exception as e:
                    logger.error(f"Failed to start watcher for {drive}: {e}")

async def main():
    """Main entry point for worker"""
    worker = Worker()
    
    # Handle signals
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}")
        asyncio.create_task(worker.stop())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    await worker.start()

if __name__ == "__main__":
    asyncio.run(main())