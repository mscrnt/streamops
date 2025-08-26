"""
Deferred job scheduler service.

Monitors deferred jobs and promotes them to active queue when:
1. Quiet Period has elapsed
2. Active Hours window is reached
3. Guardrails are clear

This is the Queue Admission Layer that ensures no heavy processing
runs while blocked conditions are active.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import json
import aiohttp

from app.api.db.database import get_db
from app.api.services.nats_service import NATSService

logger = logging.getLogger(__name__)


class DeferredJobScheduler:
    """
    Scheduler that monitors deferred jobs and promotes them when ready.
    
    This implements the Queue Admission Layer, ensuring jobs only move
    from deferred to active queues when all blocking conditions clear.
    """
    
    def __init__(self, nats_service: Optional[NATSService] = None, 
                 check_interval: int = 10):
        """
        Initialize the scheduler.
        
        Args:
            nats_service: NATS service for publishing jobs to queues
            check_interval: How often to check for ready jobs (seconds)
        """
        self.nats = nats_service
        self.check_interval = check_interval
        self.running = False
        self._task = None
        self.api_base_url = "http://localhost:7767"
        
    async def start(self):
        """Start the scheduler"""
        if self.running:
            logger.warning("Scheduler already running")
            return
        
        self.running = True
        self._task = asyncio.create_task(self._run_scheduler())
        logger.info(f"Deferred job scheduler started (check interval: {self.check_interval}s)")
    
    async def stop(self):
        """Stop the scheduler"""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Deferred job scheduler stopped")
    
    async def _run_scheduler(self):
        """Main scheduler loop"""
        while self.running:
            try:
                await self._check_deferred_jobs()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                await asyncio.sleep(self.check_interval)
    
    async def _check_deferred_jobs(self):
        """Check for deferred jobs ready to run"""
        try:
            db = await get_db()
            now = datetime.utcnow()
            
            # Find deferred jobs where next_run_at has passed
            cursor = await db.execute("""
                SELECT id, type, asset_id, payload_json, blocked_reason, 
                       attempts, next_run_at
                FROM so_jobs 
                WHERE deferred = 1 
                  AND (next_run_at IS NULL OR next_run_at <= ?)
                ORDER BY next_run_at ASC, created_at ASC
                LIMIT 10
            """, (now.isoformat(),))
            
            rows = await cursor.fetchall()
            
            for row in rows:
                job_id = row[0]
                job_type = row[1]
                asset_id = row[2]
                payload = json.loads(row[3]) if row[3] else {}
                blocked_reason = row[4]
                attempts = row[5]
                
                # Check if job can be promoted
                can_run, new_block_reason = await self._can_job_run(
                    job_id, job_type, blocked_reason, payload
                )
                
                if can_run:
                    # Promote to active queue
                    await self._promote_job(job_id, job_type, asset_id, payload)
                else:
                    # Still blocked, update with new reason and next run time
                    await self._defer_job_again(job_id, new_block_reason, attempts)
            
        except Exception as e:
            logger.error(f"Failed to check deferred jobs: {e}")
    
    async def _can_job_run(self, job_id: str, job_type: str, 
                          blocked_reason: str, payload: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Check if a deferred job can now run.
        
        Returns:
            Tuple of (can_run, new_block_reason)
        """
        # Check different blocking conditions
        
        # 1. Check Quiet Period
        if blocked_reason and blocked_reason.startswith('quiet_period'):
            # Quiet period is time-based, if we're here it should be elapsed
            # Double-check file modification time if needed
            filepath = payload.get('context', {}).get('filepath')
            if filepath:
                from pathlib import Path
                try:
                    path = Path(filepath)
                    if path.exists():
                        mtime = path.stat().st_mtime
                        quiet_period = payload.get('quiet_period_sec', 45)
                        elapsed = datetime.utcnow().timestamp() - mtime
                        if elapsed < quiet_period:
                            return False, f"quiet_period:{int(quiet_period - elapsed)}s_remaining"
                except Exception as e:
                    logger.warning(f"Could not check file mtime: {e}")
        
        # 2. Check Active Hours
        if blocked_reason and blocked_reason.startswith('active_hours'):
            # Check if we're now within active hours
            active_hours = payload.get('context', {}).get('active_hours')
            if active_hours and active_hours.get('enabled'):
                if not self._is_within_active_hours(active_hours):
                    return False, "active_hours"
        
        # 3. Check Guardrails (always check for CPU/GPU intensive jobs)
        if job_type in ['ffmpeg_remux', 'ffmpeg_transcode', 'proxy', 'thumbnail']:
            is_blocked, reason = await self._check_guardrails()
            if is_blocked:
                return False, f"guardrails:{reason}"
        
        # All checks passed
        return True, None
    
    async def _check_guardrails(self) -> tuple[bool, Optional[str]]:
        """Check if guardrails would block execution"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.api_base_url}/api/guardrails/check") as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('blocked'):
                            reasons = data.get('reasons', [])
                            return True, ','.join(reasons) if reasons else 'unknown'
                        return False, None
                    else:
                        # API error, allow execution
                        return False, None
                        
        except Exception as e:
            logger.warning(f"Failed to check guardrails: {e}")
            # On error, allow execution (fail open)
            return False, None
    
    def _is_within_active_hours(self, active_hours: Dict[str, Any]) -> bool:
        """Check if current time is within active hours"""
        try:
            now = datetime.now()
            current_day = now.isoweekday()  # 1=Monday, 7=Sunday
            current_time = now.strftime("%H:%M")
            
            # Check day
            active_days = active_hours.get('days', [1, 2, 3, 4, 5, 6, 7])
            if current_day not in active_days:
                return False
            
            # Check time
            start_time = active_hours.get('start', '00:00')
            end_time = active_hours.get('end', '23:59')
            
            # Handle overnight windows
            if end_time < start_time:
                # Active hours span midnight
                return current_time >= start_time or current_time <= end_time
            else:
                return start_time <= current_time <= end_time
                
        except Exception as e:
            logger.error(f"Error checking active hours: {e}")
            return True  # Default to allowing on error
    
    async def _promote_job(self, job_id: str, job_type: str, 
                          asset_id: Optional[str], payload: Dict[str, Any]):
        """Promote a deferred job to active queue"""
        try:
            db = await get_db()
            
            # Update job to no longer be deferred
            await db.execute("""
                UPDATE so_jobs 
                SET deferred = 0,
                    blocked_reason = NULL,
                    next_run_at = NULL,
                    state = 'queued',
                    last_check_at = datetime('now'),
                    updated_at = datetime('now')
                WHERE id = ?
            """, (job_id,))
            await db.commit()
            
            # Publish to appropriate queue
            if self.nats:
                queue_name = f"jobs.{job_type}"
                message = {
                    'id': job_id,
                    'type': job_type,
                    'asset_id': asset_id,
                    'payload': payload
                }
                await self.nats.publish(queue_name, message)
                logger.info(f"Promoted deferred job {job_id} to queue {queue_name}")
            else:
                logger.warning(f"No NATS service, job {job_id} updated but not queued")
                
        except Exception as e:
            logger.error(f"Failed to promote job {job_id}: {e}")
    
    async def _defer_job_again(self, job_id: str, reason: str, attempts: int):
        """Update a deferred job with new block reason and retry time"""
        try:
            db = await get_db()
            
            # Calculate backoff with exponential increase
            base_delay = 60  # Start with 60 seconds
            max_delay = 300  # Max 5 minutes
            delay = min(base_delay * (2 ** min(attempts, 4)), max_delay)
            
            # Add jitter
            import random
            jitter = delay * 0.1 * (0.5 - random.random())
            next_run_at = datetime.utcnow() + timedelta(seconds=delay + jitter)
            
            # Update job
            await db.execute("""
                UPDATE so_jobs 
                SET blocked_reason = ?,
                    next_run_at = ?,
                    attempts = ?,
                    last_check_at = datetime('now'),
                    updated_at = datetime('now')
                WHERE id = ?
            """, (reason, next_run_at.isoformat(), attempts + 1, job_id))
            await db.commit()
            
            logger.debug(f"Re-deferred job {job_id}: {reason}, retry at {next_run_at}")
            
        except Exception as e:
            logger.error(f"Failed to re-defer job {job_id}: {e}")


# Singleton instance
_scheduler: Optional[DeferredJobScheduler] = None


def get_scheduler() -> DeferredJobScheduler:
    """Get the singleton scheduler instance"""
    global _scheduler
    if _scheduler is None:
        _scheduler = DeferredJobScheduler()
    return _scheduler


async def init_scheduler(nats_service: Optional[NATSService] = None):
    """Initialize and start the scheduler"""
    scheduler = get_scheduler()
    scheduler.nats = nats_service
    await scheduler.start()
    return scheduler