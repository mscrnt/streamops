from fastapi import APIRouter, HTTPException, Depends, Query, WebSocket, WebSocketDisconnect
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import uuid
import json
import os

from app.api.schemas.jobs import (
    JobResponse, JobCreate, JobUpdate, JobListResponse,
    JobSearchQuery, JobStats, JobCancel, JobStatus, JobType, JobPriority
)
from app.api.db.database import get_db

router = APIRouter()

# WebSocket connections for real-time job updates
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                pass

manager = ConnectionManager()


@router.get("/", response_model=JobListResponse)
async def list_jobs(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    status: Optional[JobStatus] = Query(None, description="Filter by status"),
    job_type: Optional[JobType] = Query(None, description="Filter by job type"),
    priority: Optional[JobPriority] = Query(None, description="Filter by priority"),
    asset_id: Optional[str] = Query(None, description="Filter by asset ID"),
    session_id: Optional[str] = Query(None, description="Filter by session ID"),
    db=Depends(get_db)
) -> JobListResponse:
    """List jobs with filtering and pagination"""
    try:
        query = "SELECT * FROM so_jobs WHERE 1=1"
        params = []
        
        if status:
            query += " AND state = ?"
            params.append(status.value)
        if job_type:
            query += " AND type = ?"
            params.append(job_type.value)
        if priority:
            query += " AND json_extract(payload_json, '$.priority') = ?"
            params.append(priority.value)
        if asset_id:
            query += " AND asset_id = ?"
            params.append(asset_id)
        if session_id:
            query += " AND json_extract(payload_json, '$.session_id') = ?"
            params.append(session_id)
        
        query += " ORDER BY created_at DESC"
        
        # Get total count
        count_query = query.replace("SELECT *", "SELECT COUNT(*)", 1)
        cursor = await db.execute(count_query, params)
        total = (await cursor.fetchone())[0]
        
        # Apply pagination
        query += " LIMIT ? OFFSET ?"
        params.extend([per_page, (page - 1) * per_page])
        
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        
        jobs = []
        for row in rows:
            payload = json.loads(row[3]) if row[3] else {}
            jobs.append(JobResponse(
                id=row[0],
                job_type=JobType(row[1]),
                status=JobStatus(row[4]),
                priority=JobPriority(payload.get('priority', 'normal')),
                params=payload.get('params', {}),
                asset_id=row[2],
                session_id=payload.get('session_id'),
                progress=row[5] or 0.0,
                error_message=row[6],
                result=json.loads(payload.get('result', '{}')) if payload.get('result') else None,
                retry_count=payload.get('retry_count', 0),
                max_retries=payload.get('max_retries', 3),
                timeout_seconds=payload.get('timeout_seconds'),
                created_at=datetime.fromisoformat(row[7]),
                started_at=datetime.fromisoformat(payload.get('started_at')) if payload.get('started_at') else None,
                completed_at=datetime.fromisoformat(payload.get('completed_at')) if payload.get('completed_at') else None
            ))
        
        return JobListResponse(
            jobs=jobs,
            total=total,
            page=page,
            per_page=per_page
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch jobs: {str(e)}")


@router.post("/", response_model=JobResponse)
async def create_job(job: JobCreate, db=Depends(get_db)) -> JobResponse:
    """Create a new job and queue it for processing"""
    try:
        job_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        # Prepare payload
        payload = {
            'priority': job.priority.value,
            'params': job.params,
            'session_id': job.session_id,
            'max_retries': job.max_retries,
            'timeout_seconds': job.timeout_seconds,
            'retry_count': 0
        }
        
        # Insert into database
        await db.execute(
            """INSERT INTO so_jobs (id, type, asset_id, payload_json, state, progress, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (job_id, job.job_type.value, job.asset_id, json.dumps(payload), 
             JobStatus.pending.value, 0.0, now.isoformat(), now.isoformat())
        )
        await db.commit()
        
        # Queue the job in NATS if enabled
        if os.getenv("NATS_ENABLE", "true").lower() == "true":
            try:
                from app.api.main import app
                if hasattr(app.state, 'nats'):
                    await app.state.nats.publish_job(job.job_type.value, {
                        'id': job_id,
                        'type': job.job_type.value,
                        'params': job.params,
                        'asset_id': job.asset_id,
                        'priority': job.priority.value
                    })
            except Exception as e:
                # Log but don't fail if NATS publish fails
                pass
        
        new_job = JobResponse(
            id=job_id,
            job_type=job.job_type,
            status=JobStatus.pending,
            priority=job.priority,
            params=job.params,
            asset_id=job.asset_id,
            session_id=job.session_id,
            max_retries=job.max_retries,
            timeout_seconds=job.timeout_seconds,
            created_at=now
        )
        
        # Broadcast job creation
        await manager.broadcast(json.dumps({
            "type": "job_created",
            "job": new_job.dict()
        }))
        
        return new_job
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create job: {str(e)}")



@router.get("/active")
async def get_active_jobs(
    limit: int = Query(10, description="Maximum number of jobs to return"),
    db=Depends(get_db)
) -> List[Dict[str, Any]]:
    """Get active jobs for dashboard"""
    try:
        cursor = await db.execute(
            """SELECT j.id, j.type, j.asset_id, j.state, j.progress, j.created_at, j.updated_at,
                      a.abs_path
               FROM so_jobs j
               LEFT JOIN so_assets a ON j.asset_id = a.id
               WHERE j.state IN ('running', 'pending')
               ORDER BY j.updated_at DESC
               LIMIT ?""",
            (limit,)
        )
        rows = await cursor.fetchall()
        
        jobs = []
        for row in rows:
            # Extract filename from path if it exists
            asset_path = row[7]
            asset_name = "Unknown"
            if asset_path:
                asset_name = asset_path.split('/')[-1] if '/' in asset_path else asset_path
            
            jobs.append({
                "id": row[0],
                "type": row[1],
                "asset_id": row[2],
                "asset_name": asset_name,
                "asset_path": asset_path,
                "status": row[3],
                "progress": row[4],
                "started_at": row[5],
                "updated_at": row[6]
            })
        
        return jobs
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to get active jobs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get active jobs: {str(e)}")


@router.get("/stats")
async def get_job_stats(
    time_range: str = Query("24h", description="Time range for stats (1h, 24h, 7d, 30d)"),
    db=Depends(get_db)
) -> Dict[str, Any]:
    """Get job statistics for the specified time range"""
    try:
        # Calculate time offset based on range
        now = datetime.utcnow()
        if time_range == "1h":
            time_offset = now - timedelta(hours=1)
        elif time_range == "24h":
            time_offset = now - timedelta(days=1)
        elif time_range == "7d":
            time_offset = now - timedelta(days=7)
        elif time_range == "30d":
            time_offset = now - timedelta(days=30)
        else:
            time_offset = now - timedelta(days=1)
        
        # Get job counts by status
        cursor = await db.execute(
            """SELECT state, COUNT(*) FROM so_jobs 
               WHERE created_at >= ? 
               GROUP BY state""",
            (time_offset.isoformat(),)
        )
        status_counts = {row[0]: row[1] for row in await cursor.fetchall()}
        
        # Get job counts by type
        cursor = await db.execute(
            """SELECT type, COUNT(*) FROM so_jobs 
               WHERE created_at >= ? 
               GROUP BY type""",
            (time_offset.isoformat(),)
        )
        type_counts = {row[0]: row[1] for row in await cursor.fetchall()}
        
        # Calculate success rate
        total = sum(status_counts.values())
        completed = status_counts.get('completed', 0)
        failed = status_counts.get('failed', 0)
        success_rate = (completed / (completed + failed) * 100) if (completed + failed) > 0 else 0
        
        return {
            "time_range": time_range,
            "total_jobs": total,
            "status_breakdown": status_counts,
            "type_breakdown": type_counts,
            "success_rate": round(success_rate, 2),
            "pending": status_counts.get('pending', 0),
            "running": status_counts.get('running', 0),
            "completed": completed,
            "failed": failed
        }
    except Exception as e:
        logger.error(f"Failed to get job stats: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get job stats: {str(e)}")




@router.get("/history")
async def get_job_history(
    limit: int = Query(50, description="Number of jobs to return"),
    offset: int = Query(0, description="Offset for pagination"),
    db=Depends(get_db)
) -> List[JobResponse]:
    """Get recent job history"""
    try:
        cursor = await db.execute(
            """SELECT * FROM so_jobs 
               WHERE state IN ('completed', 'failed', 'cancelled')
               ORDER BY updated_at DESC
               LIMIT ? OFFSET ?""",
            (limit, offset)
        )
        rows = await cursor.fetchall()
        
        jobs = []
        for row in rows:
            payload = json.loads(row[3]) if row[3] else {}
            jobs.append(JobResponse(
                id=row[0],
                type=row[1],
                asset_id=row[2],
                payload=payload,
                state=row[4],
                progress=row[5],
                error=row[6],
                created_at=datetime.fromisoformat(row[7]),
                updated_at=datetime.fromisoformat(row[8])
            ))
        
        return jobs
    except Exception as e:
        logger.error(f"Failed to get job history: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get job history: {str(e)}")


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, db=Depends(get_db)) -> JobResponse:
    """Get a specific job by ID"""
    try:
        cursor = await db.execute(
            "SELECT * FROM so_jobs WHERE id = ?",
            (job_id,)
        )
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        payload = json.loads(row[3]) if row[3] else {}
        return JobResponse(
            id=row[0],
            job_type=JobType(row[1]),
            status=JobStatus(row[4]),
            priority=JobPriority(payload.get('priority', 'normal')),
            params=payload.get('params', {}),
            asset_id=row[2],
            session_id=payload.get('session_id'),
            progress=row[5] or 0.0,
            error_message=row[6],
            result=json.loads(payload.get('result', '{}')) if payload.get('result') else None,
            retry_count=payload.get('retry_count', 0),
            max_retries=payload.get('max_retries', 3),
            timeout_seconds=payload.get('timeout_seconds'),
            created_at=datetime.fromisoformat(row[7]),
            started_at=datetime.fromisoformat(payload.get('started_at')) if payload.get('started_at') else None,
            completed_at=datetime.fromisoformat(payload.get('completed_at')) if payload.get('completed_at') else None
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch job: {str(e)}")


@router.put("/{job_id}", response_model=JobResponse)
async def update_job(
    job_id: str,
    job_update: JobUpdate,
    db=Depends(get_db)
) -> JobResponse:
    """Update a job (typically used by workers)"""
    try:
        # Get existing job first
        cursor = await db.execute("SELECT * FROM so_jobs WHERE id = ?", (job_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        existing_payload = json.loads(row[3]) if row[3] else {}
        now = datetime.utcnow()
        
        # Update fields
        updates = []
        params = []
        
        if job_update.status:
            updates.append("state = ?")
            params.append(job_update.status.value)
            
            if job_update.status == JobStatus.running and not existing_payload.get('started_at'):
                existing_payload['started_at'] = now.isoformat()
            elif job_update.status in [JobStatus.completed, JobStatus.failed]:
                existing_payload['completed_at'] = now.isoformat()
        
        if job_update.progress is not None:
            updates.append("progress = ?")
            params.append(job_update.progress)
        
        if job_update.error_message:
            updates.append("error = ?")
            params.append(job_update.error_message)
        
        if job_update.priority:
            existing_payload['priority'] = job_update.priority.value
        
        if job_update.result:
            existing_payload['result'] = json.dumps(job_update.result)
        
        updates.append("payload_json = ?")
        params.append(json.dumps(existing_payload))
        
        updates.append("updated_at = ?")
        params.append(now.isoformat())
        
        params.append(job_id)
        
        await db.execute(
            f"UPDATE so_jobs SET {', '.join(updates)} WHERE id = ?",
            params
        )
        await db.commit()
        
        # Get updated job
        updated_job = await get_job(job_id, db)
        
        # Broadcast job update
        await manager.broadcast(json.dumps({
            "type": "job_updated",
            "job": updated_job.dict()
        }))
        
        return updated_job
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update job: {str(e)}")


@router.delete("/{job_id}")
async def delete_job(job_id: str, db=Depends(get_db)) -> Dict[str, str]:
    """Delete a job (only if not running)"""
    try:
        # Check job status
        cursor = await db.execute(
            "SELECT state FROM so_jobs WHERE id = ?",
            (job_id,)
        )
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        if row[0] == JobStatus.running.value:
            raise HTTPException(status_code=400, detail="Cannot delete a running job")
        
        # Delete the job
        await db.execute("DELETE FROM so_jobs WHERE id = ?", (job_id,))
        await db.commit()
        
        return {"message": f"Job {job_id} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete job: {str(e)}")


@router.post("/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    cancel_request: Optional[JobCancel] = None,
    db=Depends(get_db)
) -> Dict[str, str]:
    """Cancel a running or queued job"""
    try:
        # Update job status to cancelled
        await db.execute(
            """UPDATE so_jobs 
               SET state = ?, error = ?, updated_at = ?
               WHERE id = ? AND state IN ('pending', 'running', 'queued')""",
            (JobStatus.failed.value, 'Job cancelled by user', datetime.utcnow().isoformat(), job_id)
        )
        await db.commit()
        
        # Check if update affected any rows
        if db.total_changes == 0:
            raise HTTPException(status_code=400, detail="Job cannot be cancelled or not found")
        
        # Broadcast job cancellation
        await manager.broadcast(json.dumps({
            "type": "job_cancelled",
            "job_id": job_id
        }))
        
        return {"message": f"Job {job_id} cancelled successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cancel job: {str(e)}")


@router.post("/{job_id}/retry", response_model=JobResponse)
async def retry_job(job_id: str, db=Depends(get_db)) -> JobResponse:
    """Retry a failed job"""
    try:
        # Get the failed job
        cursor = await db.execute(
            "SELECT * FROM so_jobs WHERE id = ? AND state = ?",
            (job_id, JobStatus.failed.value)
        )
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Job not found or not in failed state")
        
        payload = json.loads(row[3]) if row[3] else {}
        retry_count = payload.get('retry_count', 0) + 1
        max_retries = payload.get('max_retries', 3)
        
        if retry_count > max_retries:
            raise HTTPException(status_code=400, detail="Maximum retry attempts exceeded")
        
        # Update retry count and reset status
        payload['retry_count'] = retry_count
        payload.pop('started_at', None)
        payload.pop('completed_at', None)
        now = datetime.utcnow()
        
        await db.execute(
            """UPDATE so_jobs 
               SET state = ?, progress = ?, error = NULL, 
                   payload_json = ?, updated_at = ?
               WHERE id = ?""",
            (JobStatus.pending.value, 0.0, json.dumps(payload), now.isoformat(), job_id)
        )
        await db.commit()
        
        # Re-queue the job if NATS is enabled
        if os.getenv("NATS_ENABLE", "true").lower() == "true":
            try:
                from app.api.main import app
                if hasattr(app.state, 'nats'):
                    await app.state.nats.publish_job(row[1], {
                        'id': job_id,
                        'type': row[1],
                        'params': payload.get('params', {}),
                        'asset_id': row[2],
                        'priority': payload.get('priority', 'normal'),
                        'retry_count': retry_count
                    })
            except Exception as e:
                pass
        
        retried_job = await get_job(job_id, db)
        
        # Broadcast job retry
        await manager.broadcast(json.dumps({
            "type": "job_retried",
            "job": retried_job.dict()
        }))
        
        return retried_job
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retry job: {str(e)}")


@router.post("/search", response_model=JobListResponse)
async def search_jobs(
    search_query: JobSearchQuery,
    db=Depends(get_db)
) -> JobListResponse:
    """Advanced job search with multiple filters"""
    try:
        query = "SELECT * FROM so_jobs WHERE 1=1"
        params = []
        
        if search_query.job_types:
            placeholders = ','.join('?' * len(search_query.job_types))
            query += f" AND type IN ({placeholders})"
            params.extend([jt.value for jt in search_query.job_types])
        
        if search_query.statuses:
            placeholders = ','.join('?' * len(search_query.statuses))
            query += f" AND state IN ({placeholders})"
            params.extend([s.value for s in search_query.statuses])
        
        if search_query.priorities:
            priority_conditions = []
            for p in search_query.priorities:
                priority_conditions.append("json_extract(payload_json, '$.priority') = ?")
                params.append(p.value)
            query += f" AND ({' OR '.join(priority_conditions)})"
        
        if search_query.asset_id:
            query += " AND asset_id = ?"
            params.append(search_query.asset_id)
        
        if search_query.session_id:
            query += " AND json_extract(payload_json, '$.session_id') = ?"
            params.append(search_query.session_id)
        
        if search_query.created_after:
            query += " AND created_at >= ?"
            params.append(search_query.created_after.isoformat())
        
        if search_query.created_before:
            query += " AND created_at <= ?"
            params.append(search_query.created_before.isoformat())
        
        # Apply sorting
        sort_field = search_query.sort_by or 'created_at'
        sort_order = search_query.sort_order or 'desc'
        query += f" ORDER BY {sort_field} {sort_order.upper()}"
        
        # Get total count
        count_query = query.replace("SELECT *", "SELECT COUNT(*)", 1)
        cursor = await db.execute(count_query, params)
        total = (await cursor.fetchone())[0]
        
        # Apply pagination
        page = search_query.page or 1
        per_page = search_query.per_page or 50
        query += " LIMIT ? OFFSET ?"
        params.extend([per_page, (page - 1) * per_page])
        
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        
        jobs = []
        for row in rows:
            payload = json.loads(row[3]) if row[3] else {}
            jobs.append(JobResponse(
                id=row[0],
                job_type=JobType(row[1]),
                status=JobStatus(row[4]),
                priority=JobPriority(payload.get('priority', 'normal')),
                params=payload.get('params', {}),
                asset_id=row[2],
                session_id=payload.get('session_id'),
                progress=row[5] or 0.0,
                error_message=row[6],
                created_at=datetime.fromisoformat(row[7])
            ))
        
        return JobListResponse(
            jobs=jobs,
            total=total,
            page=page,
            per_page=per_page
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to search jobs: {str(e)}")


@router.get("/stats/summary", response_model=JobStats)
async def get_job_stats(
    time_range: Optional[str] = Query("24h", description="Time range for stats"),
    db=Depends(get_db)
) -> JobStats:
    """Get job queue statistics"""
    try:
        # Get counts by status
        cursor = await db.execute(
            """SELECT state, COUNT(*) FROM so_jobs GROUP BY state"""
        )
        status_counts = {row[0]: row[1] for row in await cursor.fetchall()}
        
        total_jobs = sum(status_counts.values())
        pending_jobs = status_counts.get(JobStatus.pending.value, 0) + status_counts.get('queued', 0)
        running_jobs = status_counts.get(JobStatus.running.value, 0)
        completed_jobs = status_counts.get(JobStatus.completed.value, 0)
        failed_jobs = status_counts.get(JobStatus.failed.value, 0)
        
        # Calculate average processing time for completed jobs
        cursor = await db.execute(
            """SELECT AVG(
                   julianday(json_extract(payload_json, '$.completed_at')) - 
                   julianday(json_extract(payload_json, '$.started_at'))
               ) * 86400 as avg_seconds
               FROM so_jobs 
               WHERE state = ? 
               AND json_extract(payload_json, '$.started_at') IS NOT NULL
               AND json_extract(payload_json, '$.completed_at') IS NOT NULL""",
            (JobStatus.completed.value,)
        )
        avg_time_row = await cursor.fetchone()
        average_processing_time = avg_time_row[0] if avg_time_row[0] else 0.0
        
        # Calculate jobs per hour (last 24 hours)
        one_day_ago = (datetime.utcnow() - timedelta(days=1)).isoformat()
        cursor = await db.execute(
            """SELECT COUNT(*) FROM so_jobs 
               WHERE created_at >= ?""",
            (one_day_ago,)
        )
        recent_jobs = (await cursor.fetchone())[0]
        jobs_per_hour = recent_jobs / 24.0 if recent_jobs > 0 else 0.0
        
        # Calculate success rate
        total_finished = completed_jobs + failed_jobs
        success_rate = (completed_jobs / total_finished * 100) if total_finished > 0 else 0.0
        
        return JobStats(
            total_jobs=total_jobs,
            pending_jobs=pending_jobs,
            running_jobs=running_jobs,
            completed_jobs=completed_jobs,
            failed_jobs=failed_jobs,
            average_processing_time=round(average_processing_time, 1),
            jobs_per_hour=round(jobs_per_hour, 1),
            success_rate=round(success_rate, 1)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get job stats: {str(e)}")


@router.post("/queue/pause")
async def pause_queue(db=Depends(get_db)) -> Dict[str, str]:
    """Pause the job queue (stop processing new jobs)"""
    try:
        # Store pause state in config
        await db.execute(
            """INSERT OR REPLACE INTO so_configs (key, value, updated_at)
               VALUES ('queue_paused', 'true', ?)""",
            (datetime.utcnow().isoformat(),)
        )
        await db.commit()
        
        await manager.broadcast(json.dumps({
            "type": "queue_paused",
            "timestamp": datetime.utcnow().isoformat()
        }))
        return {"message": "Job queue paused"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to pause queue: {str(e)}")


@router.post("/queue/resume")
async def resume_queue(db=Depends(get_db)) -> Dict[str, str]:
    """Resume the job queue"""
    try:
        # Update pause state in config
        await db.execute(
            """INSERT OR REPLACE INTO so_configs (key, value, updated_at)
               VALUES ('queue_paused', 'false', ?)""",
            (datetime.utcnow().isoformat(),)
        )
        await db.commit()
        
        await manager.broadcast(json.dumps({
            "type": "queue_resumed",
            "timestamp": datetime.utcnow().isoformat()
        }))
        return {"message": "Job queue resumed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resume queue: {str(e)}")


@router.delete("/queue/clear")
async def clear_queue(
    clear_failed_only: bool = Query(False, description="Only clear failed jobs"),
    db=Depends(get_db)
) -> Dict[str, Any]:
    """Clear completed/failed jobs from the queue"""
    try:
        # Count jobs to be cleared
        statuses_to_clear = [JobStatus.completed.value, JobStatus.failed.value]
        if clear_failed_only:
            statuses_to_clear = [JobStatus.failed.value]
        
        placeholders = ','.join('?' * len(statuses_to_clear))
        cursor = await db.execute(
            f"SELECT COUNT(*) FROM so_jobs WHERE state IN ({placeholders})",
            statuses_to_clear
        )
        cleared_count = (await cursor.fetchone())[0]
        
        # Delete the jobs
        await db.execute(
            f"DELETE FROM so_jobs WHERE state IN ({placeholders})",
            statuses_to_clear
        )
        await db.commit()
        
        await manager.broadcast(json.dumps({
            "type": "queue_cleared",
            "cleared_count": cleared_count,
            "timestamp": datetime.utcnow().isoformat()
        }))
        
        return {
            "message": f"Cleared {cleared_count} jobs from the queue",
            "cleared_count": cleared_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear queue: {str(e)}")


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time job updates"""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Handle incoming messages if needed
    except WebSocketDisconnect:
        manager.disconnect(websocket)