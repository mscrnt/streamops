"""
Base worker class that enforces guardrails checks before CPU/GPU intensive operations.
All workers MUST inherit from this class to ensure no heavy processing runs while blocked.
"""

import asyncio
import logging
import json
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import aiohttp
import random

from app.api.db.database import get_db

logger = logging.getLogger(__name__)


class GuardrailsBlocked(Exception):
    """Raised when guardrails prevent job execution"""
    def __init__(self, reason: str, retry_after_sec: int = 60):
        self.reason = reason
        self.retry_after_sec = retry_after_sec
        super().__init__(f"Guardrails blocked: {reason}")


class BaseWorker:
    """
    Base worker class with guardrails enforcement.
    
    All workers processing CPU/GPU intensive tasks MUST inherit from this class
    and call check_guardrails() before starting heavy operations.
    """
    
    def __init__(self, worker_type: str, api_base_url: str = "http://localhost:7767"):
        self.worker_type = worker_type
        self.api_base_url = api_base_url
        self.logger = logging.getLogger(f"{__name__}.{worker_type}")
        
    async def check_guardrails(self) -> Tuple[bool, Optional[str], int]:
        """
        Check if guardrails would block execution.
        
        Returns:
            Tuple of (is_blocked, reason, retry_after_sec)
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.api_base_url}/api/guardrails/check") as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('blocked'):
                            reasons = data.get('reasons', [])
                            reason = ', '.join(reasons) if reasons else 'Unknown'
                            retry_after = data.get('retry_after_sec', 60)
                            return True, reason, retry_after
                        return False, None, 0
                    else:
                        # If API is down, allow execution (fail open)
                        self.logger.warning(f"Guardrails API returned {response.status}, allowing execution")
                        return False, None, 0
                        
        except Exception as e:
            # On error, allow execution (fail open) but log warning
            self.logger.warning(f"Failed to check guardrails: {e}, allowing execution")
            return False, None, 0
    
    async def ensure_guardrails_clear(self):
        """
        Ensure guardrails are clear before proceeding.
        Raises GuardrailsBlocked if blocked.
        """
        is_blocked, reason, retry_after = await self.check_guardrails()
        if is_blocked:
            raise GuardrailsBlocked(reason, retry_after)
    
    async def defer_job(self, job_id: str, blocked_reason: str, retry_after_sec: int):
        """
        Mark job as deferred and set next run time.
        """
        try:
            db = await get_db()
            
            # Calculate next run time with jitter
            jitter = retry_after_sec * 0.1 * (0.5 - random.random())  # ±10% jitter
            next_run_at = datetime.utcnow() + timedelta(seconds=retry_after_sec + jitter)
            
            # Update job to deferred state
            await db.execute("""
                UPDATE so_jobs 
                SET deferred = 1,
                    blocked_reason = ?,
                    next_run_at = ?,
                    attempts = attempts + 1,
                    last_check_at = datetime('now'),
                    updated_at = datetime('now')
                WHERE id = ?
            """, (blocked_reason, next_run_at.isoformat(), job_id))
            await db.commit()
            
            self.logger.info(f"Deferred job {job_id}: {blocked_reason}, retry at {next_run_at}")
            
        except Exception as e:
            self.logger.error(f"Failed to defer job {job_id}: {e}")
    
    async def process_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a job with guardrails enforcement.
        
        This is the main entry point for workers. It ensures guardrails
        are checked before calling the actual processing logic.
        
        Args:
            job_data: Job data including id, type, payload, etc.
            
        Returns:
            Processing result dict
        """
        job_id = job_data.get('id')
        job_type = job_data.get('type')
        
        try:
            # CRITICAL: Check guardrails before any heavy processing
            await self.ensure_guardrails_clear()
            
            self.logger.info(f"Processing job {job_id} (type: {job_type})")
            
            # Mark job as running
            await self.update_job_state(job_id, 'running')
            
            # Call the actual worker implementation
            result = await self.execute(job_data)
            
            # Mark job as completed
            await self.update_job_state(job_id, 'completed', result=result)
            
            return result
            
        except GuardrailsBlocked as e:
            # Defer the job - it will be retried when guardrails clear
            self.logger.warning(f"Job {job_id} blocked by guardrails: {e.reason}")
            await self.defer_job(job_id, f"guardrails:{e.reason}", e.retry_after_sec)
            
            # Return deferred status (don't mark as failed)
            return {
                'status': 'deferred',
                'reason': e.reason,
                'retry_after_sec': e.retry_after_sec
            }
            
        except Exception as e:
            # Mark job as failed
            self.logger.error(f"Job {job_id} failed: {e}")
            await self.update_job_state(job_id, 'failed', error=str(e))
            raise
    
    async def execute(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the actual job processing logic.
        
        This method MUST be implemented by subclasses.
        It will only be called if guardrails checks pass.
        
        Args:
            job_data: Job data including payload
            
        Returns:
            Processing result dict
        """
        raise NotImplementedError("Subclasses must implement execute()")
    
    async def update_job_state(self, job_id: str, state: str, 
                              result: Optional[Dict] = None, 
                              error: Optional[str] = None,
                              progress: Optional[float] = None):
        """Update job state in database"""
        try:
            db = await get_db()
            
            # Base update query
            updates = ["state = ?", "updated_at = datetime('now')"]
            params = [state]
            
            # Add optional fields
            if state == 'running':
                updates.append("started_at = datetime('now')")
                updates.append("deferred = 0")
                updates.append("blocked_reason = NULL")
            elif state in ['completed', 'failed', 'canceled']:
                updates.append("ended_at = datetime('now')")
            
            if progress is not None:
                updates.append("progress = ?")
                params.append(progress)
            
            if error:
                updates.append("error = ?")
                params.append(error)
            
            if result:
                # Store result in payload_json
                updates.append("payload_json = json_patch(payload_json, '$.result', json(?))")
                params.append(json.dumps(result))
            
            # Execute update
            params.append(job_id)
            query = f"UPDATE so_jobs SET {', '.join(updates)} WHERE id = ?"
            await db.execute(query, params)
            await db.commit()
            
        except Exception as e:
            self.logger.error(f"Failed to update job {job_id} state: {e}")
    
    async def report_progress(self, job_id: str, progress: float, eta_sec: Optional[int] = None):
        """Report job progress"""
        await self.update_job_state(job_id, 'running', progress=progress)
        
        # Also broadcast via WebSocket if available
        # This would integrate with your WebSocket manager
        self.logger.debug(f"Job {job_id} progress: {progress:.1f}%")