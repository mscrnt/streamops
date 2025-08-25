from fastapi import APIRouter, HTTPException, Depends, Query, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
import uuid
import json
import os
import asyncio
import logging
import aiosqlite

from app.api.db.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()

# Pydantic models for the Jobs API
class JobStatus(str):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    canceled = "canceled"

class JobType(str):
    ffmpeg_remux = "ffmpeg_remux"
    ffmpeg_transcode = "ffmpeg_transcode"
    proxy = "proxy"
    thumbnail = "thumbnail"
    index = "index"
    move = "move"
    copy = "copy"
    archive = "archive"
    custom = "custom"

class JobItem(BaseModel):
    id: str
    type: str
    asset_id: Optional[str] = None
    asset_name: Optional[str] = None
    status: str
    progress: float = 0.0
    eta_sec: Optional[int] = None
    created_at: str
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    duration_sec: Optional[float] = None
    error: Optional[str] = None

class JobListResponse(BaseModel):
    items: List[JobItem]
    page: int
    per_page: int
    total: int

class JobDetailResponse(BaseModel):
    job: Dict[str, Any]
    logs_tail: Optional[str] = None

class JobSummaryResponse(BaseModel):
    running: int
    queued: int
    completed_24h: int
    failed_24h: int

class BulkActionRequest(BaseModel):
    action: Literal["retry", "cancel", "delete"]
    ids: List[str]

class BulkActionResponse(BaseModel):
    ok: bool
    results: List[Dict[str, Any]]

# WebSocket connection manager for real-time updates
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_message(self, message: dict, websocket: WebSocket):
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send message: {e}")

    async def broadcast(self, message: dict):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)

manager = ConnectionManager()

@router.get("/", response_model=JobListResponse)
async def list_jobs(
    status: Optional[str] = Query(None, description="Filter by status (all|queued|running|completed|failed|canceled)"),
    type: Optional[str] = Query(None, description="Filter by job type"),
    date_field: str = Query("created_at", description="Date field to filter on"),
    start: Optional[str] = Query(None, description="Start date (ISO8601)"),
    end: Optional[str] = Query(None, description="End date (ISO8601)"),
    sort: str = Query("created_at", description="Sort field"),
    order: str = Query("desc", description="Sort order (asc|desc)"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    db=Depends(get_db)
) -> JobListResponse:
    """List all jobs with filtering, sorting, and pagination"""
    try:
        # Build query
        query = """
            SELECT j.*, a.abs_path as asset_name
            FROM so_jobs j
            LEFT JOIN so_assets a ON j.asset_id = a.id
            WHERE 1=1
        """
        params = []
        
        # Apply filters
        if status and status != "all":
            query += " AND j.state = ?"
            params.append(status)
        
        if type and type != "all":
            query += " AND j.type = ?"
            params.append(type)
        
        # Date range filter
        if start:
            query += f" AND j.{date_field} >= ?"
            params.append(start)
        if end:
            query += f" AND j.{date_field} <= ?"
            params.append(end)
        
        # Count total before pagination
        count_query = query.replace("SELECT j.*, a.abs_path as asset_name", "SELECT COUNT(*)", 1)
        cursor = await db.execute(count_query, params)
        total = (await cursor.fetchone())[0]
        
        # Apply sorting
        valid_sort_fields = ['created_at', 'updated_at', 'type', 'state']
        if sort in valid_sort_fields:
            query += f" ORDER BY j.{sort} {order.upper()}"
        else:
            query += " ORDER BY j.created_at DESC"
        
        # Apply pagination
        query += " LIMIT ? OFFSET ?"
        params.extend([per_page, (page - 1) * per_page])
        
        # Execute query
        cursor = await db.execute(query, params)
        
        # Get column names
        column_names = [description[0] for description in cursor.description]
        rows = await cursor.fetchall()
        
        # Build response
        items = []
        for row in rows:
            # Convert row to dict for easier access
            row_dict = dict(zip(column_names, row))
            
            # Calculate duration if both timestamps exist
            duration_sec = None
            if row_dict.get('started_at') and row_dict.get('ended_at'):
                try:
                    started = datetime.fromisoformat(row_dict['started_at'])
                    ended = datetime.fromisoformat(row_dict['ended_at'])
                    duration_sec = (ended - started).total_seconds()
                except:
                    pass
            
            # Parse payload for progress and eta if available
            payload = json.loads(row_dict.get('payload_json', '{}')) if row_dict.get('payload_json') else {}
            progress = payload.get('progress', row_dict.get('progress', 0.0) or 0.0)
            eta_sec = payload.get('eta_sec', None)
            
            items.append(JobItem(
                id=row_dict.get('id', ''),
                type=row_dict.get('type', ''),
                asset_id=row_dict.get('asset_id'),
                asset_name=os.path.basename(row_dict.get('asset_name', '')) if row_dict.get('asset_name') else None,
                status=row_dict.get('state', row_dict.get('status', 'unknown')),
                progress=progress * 100 if progress <= 1 else progress,
                eta_sec=eta_sec,
                created_at=row_dict.get('created_at', datetime.utcnow().isoformat()),
                started_at=row_dict.get('started_at'),
                ended_at=row_dict.get('ended_at'),
                duration_sec=duration_sec,
                error=row_dict.get('error')
            ))
        
        return JobListResponse(
            items=items,
            page=page,
            per_page=per_page,
            total=total
        )
    except Exception as e:
        logger.error(f"Failed to list jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/summary", response_model=JobSummaryResponse)
async def get_job_summary(
    window: str = Query("24h", description="Time window for completed/failed stats"),
    db=Depends(get_db)
) -> JobSummaryResponse:
    """Get summary statistics for the job queue"""
    try:
        # Parse window
        if window == "24h":
            cutoff = datetime.utcnow() - timedelta(hours=24)
        elif window == "7d":
            cutoff = datetime.utcnow() - timedelta(days=7)
        else:
            cutoff = datetime.utcnow() - timedelta(hours=24)
        
        cutoff_str = cutoff.isoformat()
        
        # Get counts
        cursor = await db.execute("""
            SELECT 
                SUM(CASE WHEN state = 'running' THEN 1 ELSE 0 END) as running,
                SUM(CASE WHEN state = 'queued' OR state = 'pending' THEN 1 ELSE 0 END) as queued,
                SUM(CASE WHEN state = 'completed' AND updated_at >= ? THEN 1 ELSE 0 END) as completed_24h,
                SUM(CASE WHEN state = 'failed' AND updated_at >= ? THEN 1 ELSE 0 END) as failed_24h
            FROM so_jobs
        """, (cutoff_str, cutoff_str))
        
        row = await cursor.fetchone()
        
        return JobSummaryResponse(
            running=row[0] or 0,
            queued=row[1] or 0,
            completed_24h=row[2] or 0,
            failed_24h=row[3] or 0
        )
    except Exception as e:
        logger.error(f"Failed to get job summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{job_id}", response_model=JobDetailResponse)
async def get_job_details(
    job_id: str,
    db=Depends(get_db)
) -> JobDetailResponse:
    """Get detailed information about a specific job"""
    try:
        cursor = await db.execute("""
            SELECT j.*, a.abs_path as asset_name
            FROM so_jobs j
            LEFT JOIN so_assets a ON j.asset_id = a.id
            WHERE j.id = ?
        """, (job_id,))
        
        # Get column names
        column_names = [description[0] for description in cursor.description]
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Convert row to dict
        row_dict = dict(zip(column_names, row))
        
        # Build job object
        job = {
            "id": row_dict.get('id', ''),
            "type": row_dict.get('type', ''),
            "asset_id": row_dict.get('asset_id'),
            "asset_name": os.path.basename(row_dict.get('asset_name', '')) if row_dict.get('asset_name') else None,
            "status": row_dict.get('state', row_dict.get('status', 'unknown')),
            "progress": (row_dict.get('progress', 0) or 0) * 100 if row_dict.get('progress', 0) <= 1 else (row_dict.get('progress', 0) or 0),
            "error": row_dict.get('error'),
            "created_at": row_dict.get('created_at'),
            "started_at": row_dict.get('started_at'),
            "ended_at": row_dict.get('ended_at'),
            "updated_at": row_dict.get('updated_at')
        }
        
        # Parse and add payload (with secrets redacted)
        if row_dict.get('payload_json'):
            payload = json.loads(row_dict['payload_json'])
            # Redact sensitive fields
            for key in ['password', 'token', 'secret', 'api_key']:
                if key in payload:
                    payload[key] = "***REDACTED***"
            job["payload_json"] = payload
        
        # Get last N lines of logs if available
        logs_tail = None
        log_file = f"/data/logs/jobs/{job_id}.log"
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    logs_tail = ''.join(lines[-100:])  # Last 100 lines
            except:
                pass
        
        return JobDetailResponse(
            job=job,
            logs_tail=logs_tail
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job details: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    db=Depends(get_db)
):
    """Cancel a running or queued job"""
    try:
        # Check current status
        cursor = await db.execute("SELECT state FROM so_jobs WHERE id = ?", (job_id,))
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Job not found")
        
        current_status = row[0]
        if current_status not in ['queued', 'pending', 'running']:
            raise HTTPException(status_code=400, detail=f"Cannot cancel job in {current_status} state")
        
        # Update job status
        await db.execute("""
            UPDATE so_jobs 
            SET state = 'canceled', 
                ended_at = datetime('now'),
                updated_at = datetime('now')
            WHERE id = ?
        """, (job_id,))
        await db.commit()
        
        # Broadcast cancellation
        await manager.broadcast({
            "type": "job_state",
            "id": job_id,
            "status": "canceled",
            "ended_at": datetime.utcnow().isoformat()
        })
        
        # TODO: Send actual cancel signal to worker via NATS
        
        return {"ok": True, "message": "Job canceled"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel job: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{job_id}/retry")
async def retry_job(
    job_id: str,
    db=Depends(get_db)
):
    """Retry a failed or canceled job"""
    try:
        # Get original job
        cursor = await db.execute("""
            SELECT type, asset_id, payload_json 
            FROM so_jobs 
            WHERE id = ? AND state IN ('failed', 'canceled')
        """, (job_id,))
        
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Job not found or not retryable")
        
        # Create new job with same parameters
        new_job_id = str(uuid.uuid4())
        payload = json.loads(row[2]) if row[2] else {}
        payload['retry_of'] = job_id
        payload['retries'] = payload.get('retries', 0) + 1
        
        await db.execute("""
            INSERT INTO so_jobs (id, type, asset_id, payload_json, state, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'queued', datetime('now'), datetime('now'))
        """, (new_job_id, row[0], row[1], json.dumps(payload)))
        await db.commit()
        
        # Broadcast new job
        await manager.broadcast({
            "type": "job_state",
            "id": new_job_id,
            "status": "queued",
            "created_at": datetime.utcnow().isoformat()
        })
        
        return {"ok": True, "new_job_id": new_job_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retry job: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/bulk", response_model=BulkActionResponse)
async def bulk_job_action(
    request: BulkActionRequest,
    db=Depends(get_db)
) -> BulkActionResponse:
    """Perform bulk actions on multiple jobs"""
    results = []
    
    for job_id in request.ids:
        try:
            if request.action == "retry":
                # Get job and check if retryable
                cursor = await db.execute("""
                    SELECT type, asset_id, payload_json, state
                    FROM so_jobs 
                    WHERE id = ?
                """, (job_id,))
                row = await cursor.fetchone()
                
                if row and row[3] in ['failed', 'canceled']:
                    # Create new job
                    new_job_id = str(uuid.uuid4())
                    payload = json.loads(row[2]) if row[2] else {}
                    payload['retry_of'] = job_id
                    
                    await db.execute("""
                        INSERT INTO so_jobs (id, type, asset_id, payload_json, state, created_at, updated_at)
                        VALUES (?, ?, ?, ?, 'queued', datetime('now'), datetime('now'))
                    """, (new_job_id, row[0], row[1], json.dumps(payload)))
                    
                    results.append({"id": job_id, "ok": True, "new_job_id": new_job_id})
                else:
                    results.append({"id": job_id, "ok": False, "error": "Not retryable"})
                    
            elif request.action == "cancel":
                # Cancel if running or queued
                cursor = await db.execute("SELECT state FROM so_jobs WHERE id = ?", (job_id,))
                row = await cursor.fetchone()
                
                if row and row[0] in ['queued', 'pending', 'running']:
                    await db.execute("""
                        UPDATE so_jobs 
                        SET state = 'canceled', ended_at = datetime('now'), updated_at = datetime('now')
                        WHERE id = ?
                    """, (job_id,))
                    results.append({"id": job_id, "ok": True})
                else:
                    results.append({"id": job_id, "ok": False, "error": "Not cancelable"})
                    
            elif request.action == "delete":
                # Delete if in terminal state
                cursor = await db.execute("SELECT state FROM so_jobs WHERE id = ?", (job_id,))
                row = await cursor.fetchone()
                
                if row and row[0] in ['completed', 'failed', 'canceled']:
                    await db.execute("DELETE FROM so_jobs WHERE id = ?", (job_id,))
                    results.append({"id": job_id, "ok": True})
                else:
                    results.append({"id": job_id, "ok": False, "error": "Cannot delete active job"})
                    
        except Exception as e:
            results.append({"id": job_id, "ok": False, "error": str(e)})
    
    await db.commit()
    
    # Broadcast updates
    for result in results:
        if result["ok"]:
            if request.action == "cancel":
                await manager.broadcast({
                    "type": "job_state",
                    "id": result["id"],
                    "status": "canceled"
                })
            elif request.action == "retry" and "new_job_id" in result:
                await manager.broadcast({
                    "type": "job_state",
                    "id": result["new_job_id"],
                    "status": "queued"
                })
    
    return BulkActionResponse(
        ok=all(r["ok"] for r in results),
        results=results
    )

@router.post("/queue/pause")
async def pause_queue(db=Depends(get_db)):
    """Pause the job processing queue"""
    try:
        # Set queue state in config
        await db.execute("""
            INSERT OR REPLACE INTO so_configs (key, value, updated_at)
            VALUES ('queue.paused', 'true', datetime('now'))
        """)
        await db.commit()
        
        # Broadcast queue state
        await manager.broadcast({
            "type": "queue_state",
            "paused": True
        })
        
        return {"ok": True, "message": "Queue paused"}
    except Exception as e:
        logger.error(f"Failed to pause queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/queue/resume")
async def resume_queue(db=Depends(get_db)):
    """Resume the job processing queue"""
    try:
        # Set queue state in config
        await db.execute("""
            INSERT OR REPLACE INTO so_configs (key, value, updated_at)
            VALUES ('queue.paused', 'false', datetime('now'))
        """)
        await db.commit()
        
        # Broadcast queue state
        await manager.broadcast({
            "type": "queue_state",
            "paused": False
        })
        
        return {"ok": True, "message": "Queue resumed"}
    except Exception as e:
        logger.error(f"Failed to resume queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/queue/clear")
async def clear_queue(db=Depends(get_db)):
    """Clear all queued jobs (requires confirmation)"""
    try:
        # Delete only queued/pending jobs
        result = await db.execute("""
            DELETE FROM so_jobs 
            WHERE state IN ('queued', 'pending')
        """)
        await db.commit()
        
        deleted_count = result.rowcount
        
        # Broadcast queue cleared
        await manager.broadcast({
            "type": "queue_cleared",
            "deleted_count": deleted_count
        })
        
        return {"ok": True, "deleted_count": deleted_count}
    except Exception as e:
        logger.error(f"Failed to clear queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time job updates"""
    await manager.connect(websocket)
    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connected",
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Keep connection alive
        while True:
            # Wait for any message from client (ping/pong)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)

@router.get("/active", response_model=List[JobItem])
async def get_active_jobs(
    limit: int = Query(10, ge=1, le=100, description="Maximum number of jobs to return"),
    db=Depends(get_db)
) -> List[JobItem]:
    """Get currently active (running or queued) jobs"""
    try:
        cursor = await db.execute("""
            SELECT j.*, a.abs_path as asset_name
            FROM so_jobs j
            LEFT JOIN so_assets a ON j.asset_id = a.id
            WHERE j.state IN ('running', 'queued', 'pending')
            ORDER BY 
                CASE j.state 
                    WHEN 'running' THEN 1 
                    WHEN 'queued' THEN 2 
                    WHEN 'pending' THEN 3 
                END,
                j.updated_at DESC
            LIMIT ?
        """, (limit,))
        
        # Get column names
        column_names = [description[0] for description in cursor.description]
        rows = await cursor.fetchall()
        
        items = []
        for row in rows:
            # Convert row to dict
            row_dict = dict(zip(column_names, row))
            
            # Parse payload for progress
            payload = json.loads(row_dict.get('payload_json', '{}')) if row_dict.get('payload_json') else {}
            progress = payload.get('progress', row_dict.get('progress', 0.0) or 0.0)
            eta_sec = payload.get('eta_sec', None)
            
            items.append(JobItem(
                id=row_dict.get('id', ''),
                type=row_dict.get('type', ''),
                asset_id=row_dict.get('asset_id'),
                asset_name=os.path.basename(row_dict.get('asset_name', '')) if row_dict.get('asset_name') else None,
                status=row_dict.get('state', row_dict.get('status', 'unknown')),
                progress=progress * 100 if progress <= 1 else progress,
                eta_sec=eta_sec,
                created_at=row_dict.get('created_at', datetime.utcnow().isoformat()),
                started_at=row_dict.get('started_at'),
                ended_at=row_dict.get('ended_at'),
                duration_sec=None,
                error=row_dict.get('error')
            ))
        
        return items
    except Exception as e:
        logger.error(f"Failed to get active jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))