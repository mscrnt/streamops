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