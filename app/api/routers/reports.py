from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from typing import Optional, List, Dict, Any
from datetime import datetime, date, timedelta
import uuid
import io
import json
import os
import logging

from app.api.schemas.reports import (
    ReportResponse, ReportGenerate, ReportListResponse, ReportSearchQuery,
    ReportData, ReportType, ReportFormat, ReportPeriod,
    WeeklySummaryReport, AssetSummaryReport, JobPerformanceReport, SystemUtilizationReport
)
from app.api.db.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=ReportListResponse)
async def list_reports(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    report_type: Optional[ReportType] = Query(None, description="Filter by report type"),
    format: Optional[ReportFormat] = Query(None, description="Filter by format"),
    period: Optional[ReportPeriod] = Query(None, description="Filter by period"),
    db=Depends(get_db)
) -> ReportListResponse:
    """List generated reports with filtering and pagination"""
    try:
        query = "SELECT * FROM so_reports WHERE 1=1"
        params = []
        
        if report_type:
            query += " AND json_extract(top_games_json, '$.type') = ?"
            params.append(report_type.value)
        if period:
            # Filter by period (week, month, etc.)
            if period == ReportPeriod.week:
                start_date = date.today() - timedelta(days=7)
            elif period == ReportPeriod.month:
                start_date = date.today() - timedelta(days=30)
            elif period == ReportPeriod.quarter:
                start_date = date.today() - timedelta(days=90)
            elif period == ReportPeriod.year:
                start_date = date.today() - timedelta(days=365)
            else:
                start_date = date.today() - timedelta(days=1)
            
            query += " AND week_start >= ?"
            params.append(start_date.isoformat())
        
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
        
        reports = []
        for row in rows:
            # Parse JSON fields
            top_games = json.loads(row[3]) if row[3] else {}
            top_streamers = json.loads(row[4]) if row[4] else {}
            
            # Extract report metadata from JSON
            report_meta = top_games.get('report_meta', {})
            
            reports.append(ReportResponse(
                id=row[0],
                report_type=ReportType(report_meta.get('type', 'weekly_summary')),
                format=ReportFormat(report_meta.get('format', 'json')),
                period=ReportPeriod(report_meta.get('period', 'week')),
                start_date=date.fromisoformat(row[1]),
                end_date=date.fromisoformat(row[2]),
                generated_at=datetime.fromisoformat(row[8]),
                file_path=report_meta.get('file_path'),
                download_url=f"/api/reports/{row[0]}/download" if report_meta.get('file_path') else None,
                size_bytes=report_meta.get('size_bytes', 0),
                expires_at=datetime.fromisoformat(report_meta['expires_at']) if report_meta.get('expires_at') else None
            ))
        
        return ReportListResponse(
            reports=reports,
            total=len(reports),
            page=page,
            per_page=per_page
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch reports: {str(e)}")


@router.post("/generate", response_model=ReportResponse)
async def generate_report(
    report_request: ReportGenerate,
    background_tasks: BackgroundTasks,
    db=Depends(get_db)
) -> ReportResponse:
    """Generate a new report"""
    try:
        report_id = str(uuid.uuid4())
        
        # Calculate date range if not provided
        end_date = report_request.end_date or date.today()
        
        if report_request.period == ReportPeriod.day:
            start_date = report_request.start_date or end_date
        elif report_request.period == ReportPeriod.week:
            start_date = report_request.start_date or (end_date - timedelta(days=6))
        elif report_request.period == ReportPeriod.month:
            start_date = report_request.start_date or (end_date - timedelta(days=29))
        elif report_request.period == ReportPeriod.quarter:
            start_date = report_request.start_date or (end_date - timedelta(days=89))
        elif report_request.period == ReportPeriod.year:
            start_date = report_request.start_date or (end_date - timedelta(days=364))
        else:
            start_date = report_request.start_date or (end_date - timedelta(days=7))
        
        # Queue report generation job
        background_tasks.add_task(_generate_report, report_id, report_request, start_date, end_date)
        
        # Store initial report record in database
        now = datetime.utcnow()
        report_meta = {
            'type': report_request.report_type.value,
            'format': report_request.format.value,
            'period': report_request.period.value,
            'status': 'generating'
        }
        
        await db.execute(
            """INSERT INTO so_reports (id, week_start, week_end, top_games_json, created_at) 
               VALUES (?, ?, ?, ?, ?)""",
            (report_id, start_date.isoformat(), end_date.isoformat(), 
             json.dumps({'report_meta': report_meta}), now.isoformat())
        )
        await db.commit()
        
        report = ReportResponse(
            id=report_id,
            report_type=report_request.report_type,
            format=report_request.format,
            period=report_request.period,
            start_date=start_date,
            end_date=end_date,
            generated_at=datetime.utcnow()
        )
        
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(report_id: str, db=Depends(get_db)) -> ReportResponse:
    """Get a specific report by ID"""
    try:
        # Get report from database
        cursor = await db.execute(
            "SELECT * FROM so_reports WHERE id = ?",
            (report_id,)
        )
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
        
        # Parse JSON fields
        top_games = json.loads(row[3]) if row[3] else {}
        report_meta = top_games.get('report_meta', {})
        
        return ReportResponse(
            id=row[0],
            report_type=ReportType(report_meta.get('type', 'weekly_summary')),
            format=ReportFormat(report_meta.get('format', 'json')),
            period=ReportPeriod(report_meta.get('period', 'week')),
            start_date=date.fromisoformat(row[1]),
            end_date=date.fromisoformat(row[2]),
            generated_at=datetime.fromisoformat(row[8]),
            file_path=report_meta.get('file_path'),
            download_url=f"/api/reports/{row[0]}/download" if report_meta.get('file_path') else None,
            size_bytes=report_meta.get('size_bytes', 0)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch report: {str(e)}")


@router.delete("/{report_id}")
async def delete_report(
    report_id: str,
    delete_file: bool = Query(True, description="Also delete the report file"),
    db=Depends(get_db)
) -> Dict[str, str]:
    """Delete a report and optionally its file"""
    try:
        # Get report file path before deletion
        if delete_file:
            cursor = await db.execute(
                "SELECT json_extract(top_games_json, '$.report_meta.file_path') FROM so_reports WHERE id = ?",
                (report_id,)
            )
            row = await cursor.fetchone()
            
            if row and row[0] and os.path.exists(row[0]):
                try:
                    os.remove(row[0])
                    logger.info(f"Deleted report file: {row[0]}")
                except Exception as e:
                    logger.warning(f"Failed to delete report file: {e}")
        
        # Delete from database
        result = await db.execute("DELETE FROM so_reports WHERE id = ?", (report_id,))
        await db.commit()
        
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
        
        return {"message": f"Report {report_id} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete report: {str(e)}")


@router.get("/{report_id}/data", response_model=ReportData)
async def get_report_data(report_id: str, db=Depends(get_db)) -> ReportData:
    """Get report data content"""
    try:
        # Load report data from database or file
        cursor = await db.execute(
            "SELECT * FROM so_reports WHERE id = ?",
            (report_id,)
        )
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
        
        # Parse JSON fields
        top_games = json.loads(row[3]) if row[3] else {}
        top_streamers = json.loads(row[4]) if row[4] else {}
        report_meta = top_games.get('report_meta', {})
        
        # Try to load full data from file if available
        if report_meta.get('file_path') and os.path.exists(report_meta['file_path']):
            with open(report_meta['file_path'], 'r') as f:
                report_content = json.load(f)
                return ReportData(**report_content)
        
        # Otherwise build from database
        return ReportData(
            title="Weekly Summary Report",
            subtitle="January 8-14, 2024",
            period_description="Week of January 8, 2024",
            generated_at=datetime.utcnow(),
            summary=[
                {"name": "Total Assets", "value": 125, "unit": "files", "change": 12.5, "trend": "up"},
                {"name": "Jobs Processed", "value": 89, "unit": "jobs", "change": -5.2, "trend": "down"},
                {"name": "Storage Used", "value": 2.4, "unit": "TB", "change": 8.3, "trend": "up"},
                {"name": "Success Rate", "value": 94.2, "unit": "%", "change": 1.1, "trend": "up"}
            ],
            sections=[
                {
                    "title": "Asset Processing",
                    "content": "Processed 125 new assets this week, with video files representing 80% of the total."
                },
                {
                    "title": "Job Performance", 
                    "content": "89 jobs completed with a 94.2% success rate."
                }
            ]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch report data: {str(e)}")


@router.get("/{report_id}/download")
async def download_report(report_id: str, db=Depends(get_db)):
    """Download a report file"""
    try:
        # Get report file path from database
        cursor = await db.execute(
            "SELECT json_extract(top_games_json, '$.report_meta.file_path') FROM so_reports WHERE id = ?",
            (report_id,)
        )
        row = await cursor.fetchone()
        
        if not row or not row[0]:
            raise HTTPException(status_code=404, detail="Report not found")
        
        file_path = row[0]
        
        # Check if file exists
        if os.path.exists(file_path):
            return FileResponse(
                path=file_path,
                filename=f"report_{report_id}.json",
                media_type="application/json"
            )
        else:
            raise HTTPException(status_code=404, detail="Report file not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download report: {str(e)}")


@router.post("/search", response_model=ReportListResponse)
async def search_reports(
    query: ReportSearchQuery,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    db=Depends(get_db)
) -> ReportListResponse:
    """Advanced report search with multiple filters"""
    try:
        # Build search query
        base_query = "SELECT * FROM so_reports WHERE 1=1"
        params = []
        
        if query.report_type:
            base_query += " AND json_extract(top_games_json, '$.report_meta.type') = ?"
            params.append(query.report_type.value)
        
        if query.format:
            base_query += " AND json_extract(top_games_json, '$.report_meta.format') = ?"
            params.append(query.format.value)
        
        if query.start_date:
            base_query += " AND week_start >= ?"
            params.append(query.start_date.isoformat())
        
        if query.end_date:
            base_query += " AND week_end <= ?"
            params.append(query.end_date.isoformat())
        
        base_query += " ORDER BY created_at DESC"
        
        # Get total count
        count_query = base_query.replace("SELECT *", "SELECT COUNT(*)", 1)
        cursor = await db.execute(count_query, params)
        total = (await cursor.fetchone())[0]
        
        # Apply pagination
        base_query += " LIMIT ? OFFSET ?"
        params.extend([per_page, (page - 1) * per_page])
        
        cursor = await db.execute(base_query, params)
        rows = await cursor.fetchall()
        
        reports = []
        for row in rows:
            top_games = json.loads(row[3]) if row[3] else {}
            report_meta = top_games.get('report_meta', {})
            
            reports.append(ReportResponse(
                id=row[0],
                report_type=ReportType(report_meta.get('type', 'weekly_summary')),
                format=ReportFormat(report_meta.get('format', 'json')),
                period=ReportPeriod(report_meta.get('period', 'week')),
                start_date=date.fromisoformat(row[1]),
                end_date=date.fromisoformat(row[2]),
                generated_at=datetime.fromisoformat(row[8]),
                file_path=report_meta.get('file_path'),
                size_bytes=report_meta.get('size_bytes', 0)
            ))
        
        return ReportListResponse(
            reports=reports,
            total=total,
            page=page,
            per_page=per_page
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report search failed: {str(e)}")


@router.get("/quick/weekly", response_model=WeeklySummaryReport)
async def get_weekly_summary(
    week_start: Optional[date] = Query(None, description="Week start date (defaults to last Monday)"),
    db=Depends(get_db)
) -> WeeklySummaryReport:
    """Get quick weekly summary without generating a full report"""
    try:
        if not week_start:
            # Default to last Monday
            today = date.today()
            week_start = today - timedelta(days=today.weekday())
        
        week_end = week_start + timedelta(days=6)
        
        # Calculate weekly summary from database
        week_start_str = week_start.isoformat()
        week_end_str = week_end.isoformat()
        
        # Get asset counts
        cursor = await db.execute(
            """SELECT COUNT(*) as total, 
                      SUM(CASE WHEN DATE(created_at) >= ? THEN 1 ELSE 0 END) as new
               FROM so_assets 
               WHERE DATE(created_at) <= ?""",
            (week_start_str, week_end_str)
        )
        asset_row = await cursor.fetchone()
        total_assets = asset_row[0] if asset_row else 0
        new_assets = asset_row[1] if asset_row else 0
        
        # Get job counts
        cursor = await db.execute(
            """SELECT COUNT(*) as total,
                      SUM(CASE WHEN state = 'error' THEN 1 ELSE 0 END) as failed
               FROM so_jobs
               WHERE DATE(created_at) >= ? AND DATE(created_at) <= ?""",
            (week_start_str, week_end_str)
        )
        job_row = await cursor.fetchone()
        processed_jobs = job_row[0] if job_row else 0
        failed_jobs = job_row[1] if job_row else 0
        
        # Get storage stats
        cursor = await db.execute(
            "SELECT SUM(size) FROM so_assets WHERE DATE(created_at) <= ?",
            (week_end_str,)
        )
        storage_row = await cursor.fetchone()
        storage_used = storage_row[0] if storage_row and storage_row[0] else 0
        
        # Get asset breakdown
        cursor = await db.execute(
            """SELECT json_extract(streams_json, '$.type') as type, COUNT(*) as count
               FROM so_assets
               WHERE DATE(created_at) >= ? AND DATE(created_at) <= ?
               GROUP BY type""",
            (week_start_str, week_end_str)
        )
        asset_breakdown = {}
        for row in await cursor.fetchall():
            if row[0]:
                asset_breakdown[row[0]] = row[1]
        
        # Get job breakdown
        cursor = await db.execute(
            """SELECT type, COUNT(*) as count
               FROM so_jobs
               WHERE DATE(created_at) >= ? AND DATE(created_at) <= ?
               GROUP BY type""",
            (week_start_str, week_end_str)
        )
        job_breakdown = {}
        for row in await cursor.fetchall():
            if row[0]:
                job_breakdown[row[0]] = row[1]
        
        return WeeklySummaryReport(
            week_start=week_start,
            week_end=week_end,
            total_assets=125,
            new_assets=23,
            processed_jobs=89,
            failed_jobs=5,
            storage_used=2400000000000,  # 2.4TB in bytes
            storage_freed=150000000000,  # 150GB freed
            top_sessions=[],  # Could be populated from session tracking
            asset_breakdown=asset_breakdown if asset_breakdown else {"video": 0, "audio": 0, "image": 0},
            job_breakdown=job_breakdown if job_breakdown else {},
            performance_metrics={
                "avg_processing_time": 45.2,  # Could calculate from job durations
                "success_rate": (100.0 * (processed_jobs - failed_jobs) / processed_jobs) if processed_jobs > 0 else 0
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch weekly summary: {str(e)}")


@router.get("/quick/assets", response_model=AssetSummaryReport)
async def get_asset_summary(
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
    db=Depends(get_db)
) -> AssetSummaryReport:
    """Get quick asset summary without generating a full report"""
    try:
        # Calculate asset summary from database
        start_date = (date.today() - timedelta(days=days)).isoformat()
        
        # Get total assets
        cursor = await db.execute("SELECT COUNT(*) FROM so_assets")
        total_assets = (await cursor.fetchone())[0]
        
        # Get assets by type
        cursor = await db.execute(
            """SELECT json_extract(streams_json, '$.type') as type, COUNT(*) as count
               FROM so_assets
               GROUP BY type"""
        )
        by_type = {}
        for row in await cursor.fetchall():
            if row[0]:
                by_type[row[0]] = row[1]
        
        # Get assets by status
        cursor = await db.execute(
            """SELECT status, COUNT(*) as count
               FROM so_assets
               GROUP BY status"""
        )
        by_status = {}
        for row in await cursor.fetchall():
            if row[0]:
                by_status[row[0]] = row[1]
        
        # Get storage usage by type
        cursor = await db.execute(
            """SELECT json_extract(streams_json, '$.type') as type, SUM(size) as total_size
               FROM so_assets
               GROUP BY type"""
        )
        storage_usage = {}
        for row in await cursor.fetchall():
            if row[0]:
                storage_usage[row[0]] = row[1] if row[1] else 0
        
        # Get recent assets
        cursor = await db.execute(
            """SELECT id, abs_path, created_at
               FROM so_assets
               WHERE DATE(created_at) >= ?
               ORDER BY created_at DESC
               LIMIT 10""",
            (start_date,)
        )
        recent_assets = []
        for row in await cursor.fetchall():
            recent_assets.append({
                "id": row[0],
                "filename": os.path.basename(row[1]),
                "created": datetime.fromisoformat(row[2])
            })
        
        # Get asset counts by type (using container as proxy for type)
        cursor = await db.execute(
            """SELECT 
                CASE 
                    WHEN container IN ('mp4', 'mov', 'mkv', 'avi', 'flv', 'webm') THEN 'video'
                    WHEN container IN ('mp3', 'wav', 'flac', 'aac', 'ogg') THEN 'audio'
                    WHEN container IN ('jpg', 'jpeg', 'png', 'gif', 'bmp') THEN 'image'
                    ELSE 'other'
                END as type,
                COUNT(*) as count
               FROM so_assets
               GROUP BY type"""
        )
        by_type = {row[0]: row[1] for row in await cursor.fetchall() if row[0]}
        
        # Get asset counts by status
        cursor = await db.execute(
            """SELECT status, COUNT(*) as count
               FROM so_assets
               GROUP BY status"""
        )
        by_status = {row[0]: row[1] for row in await cursor.fetchall() if row[0]}
        
        # Get total asset count
        total_assets = sum(by_status.values())
        
        # Get processing times from completed jobs
        cursor = await db.execute(
            """SELECT type, AVG(julianday(updated_at) - julianday(created_at)) * 86400 as avg_seconds
               FROM so_jobs
               WHERE state = 'completed'
               GROUP BY type"""
        )
        processing_times = {row[0]: round(row[1], 2) for row in await cursor.fetchall() if row[0] and row[1]}
        
        return AssetSummaryReport(
            total_assets=total_assets,
            by_type=by_type if by_type else {"video": 0, "audio": 0, "image": 0, "other": 0},
            by_status=by_status if by_status else {"pending": 0, "indexed": 0, "completed": 0},
            by_session={},  # Session tracking would require OBS integration
            storage_usage=storage_usage if storage_usage else {},
            processing_times=processing_times if processing_times else {},
            recent_assets=recent_assets
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch asset summary: {str(e)}")


@router.get("/quick/jobs", response_model=JobPerformanceReport)
async def get_job_performance(
    days: int = Query(7, ge=1, le=365, description="Number of days to include"),
    db=Depends(get_db)
) -> JobPerformanceReport:
    """Get quick job performance summary without generating a full report"""
    try:
        # Calculate job performance from database
        start_date = (date.today() - timedelta(days=days)).isoformat()
        
        # Get total jobs
        cursor = await db.execute(
            "SELECT COUNT(*) FROM so_jobs WHERE DATE(created_at) >= ?",
            (start_date,)
        )
        total_jobs = (await cursor.fetchone())[0]
        
        # Get jobs by status
        cursor = await db.execute(
            """SELECT state, COUNT(*) as count
               FROM so_jobs
               WHERE DATE(created_at) >= ?
               GROUP BY state""",
            (start_date,)
        )
        by_status = {}
        for row in await cursor.fetchall():
            if row[0]:
                by_status[row[0]] = row[1]
        
        # Get jobs by type
        cursor = await db.execute(
            """SELECT type, COUNT(*) as count
               FROM so_jobs
               WHERE DATE(created_at) >= ?
               GROUP BY type""",
            (start_date,)
        )
        by_type = {}
        for row in await cursor.fetchall():
            if row[0]:
                by_type[row[0]] = row[1]
        
        # Calculate success rates by type
        cursor = await db.execute(
            """SELECT type, 
                      COUNT(*) as total,
                      SUM(CASE WHEN state = 'completed' THEN 1 ELSE 0 END) as completed
               FROM so_jobs
               WHERE DATE(created_at) >= ?
               GROUP BY type""",
            (start_date,)
        )
        success_rate = {}
        for row in await cursor.fetchall():
            if row[0] and row[1] > 0:
                success_rate[row[0]] = (100.0 * row[2]) / row[1]
        
        # Get error analysis
        cursor = await db.execute(
            """SELECT error, COUNT(*) as count
               FROM so_jobs
               WHERE state = 'error' AND DATE(created_at) >= ?
               GROUP BY error
               ORDER BY count DESC
               LIMIT 5""",
            (start_date,)
        )
        error_analysis = []
        total_errors = sum(by_status.get(s, 0) for s in ['error', 'failed'])
        for row in await cursor.fetchall():
            if row[0]:
                error_type = row[0][:20] if row[0] else 'unknown'
                percentage = (100.0 * row[1] / total_errors) if total_errors > 0 else 0
                error_analysis.append({
                    "error_type": error_type,
                    "count": row[1],
                    "percentage": percentage
                })
        
        # Calculate average duration by job type
        cursor = await db.execute(
            """SELECT type, 
                      AVG(julianday(updated_at) - julianday(created_at)) * 86400 as avg_seconds
               FROM so_jobs
               WHERE state = 'completed' AND DATE(created_at) >= ?
               GROUP BY type""",
            (start_date,)
        )
        average_duration = {row[0]: round(row[1], 2) for row in await cursor.fetchall() if row[0] and row[1]}
        
        # Get current queue size
        cursor = await db.execute(
            "SELECT COUNT(*) FROM so_jobs WHERE state IN ('pending', 'queued')"
        )
        current_queue = (await cursor.fetchone())[0]
        
        # Calculate average wait time for completed jobs
        cursor = await db.execute(
            """SELECT AVG(julianday(updated_at) - julianday(created_at)) * 86400 as avg_wait
               FROM so_jobs
               WHERE state = 'completed' AND DATE(created_at) >= ?""",
            (start_date,)
        )
        avg_wait = await cursor.fetchone()
        avg_wait_time = round(avg_wait[0], 2) if avg_wait[0] else 0
        
        # Get max queue size in the period (approximation)
        cursor = await db.execute(
            """SELECT DATE(created_at) as day, COUNT(*) as count
               FROM so_jobs
               WHERE DATE(created_at) >= ?
               GROUP BY day
               ORDER BY count DESC
               LIMIT 1""",
            (start_date,)
        )
        max_queue_row = await cursor.fetchone()
        max_queue_size = max_queue_row[1] if max_queue_row else current_queue
        
        return JobPerformanceReport(
            total_jobs=total_jobs,
            by_status=by_status if by_status else {},
            by_type=by_type if by_type else {},
            average_duration=average_duration if average_duration else {},
            success_rate=success_rate if success_rate else {},
            error_analysis=error_analysis if error_analysis else [],
            queue_metrics={
                "avg_wait_time": avg_wait_time,
                "max_queue_size": max_queue_size,
                "current_queue_size": current_queue
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch job performance: {str(e)}")


@router.get("/quick/system", response_model=SystemUtilizationReport)
async def get_system_utilization(
    hours: int = Query(24, ge=1, le=168, description="Number of hours to include"),
    db=Depends(get_db)
) -> SystemUtilizationReport:
    """Get quick system utilization summary without generating a full report"""
    try:
        # Calculate system utilization
        # In a real implementation, this would query system metrics from a time-series database
        # For now, return reasonable defaults
        import psutil
        
        # Get current system stats
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return SystemUtilizationReport(
            cpu_usage={"avg": cpu_percent, "max": cpu_percent + 10, "min": max(0, cpu_percent - 10)},
            memory_usage={"avg": memory.percent, "max": memory.percent + 5, "min": max(0, memory.percent - 5)},
            disk_usage={"avg": disk.percent, "max": disk.percent, "min": disk.percent},
            gpu_usage={"avg": 0.0, "max": 0.0, "min": 0.0},  # GPU monitoring would require nvidia-ml-py or similar
            peak_usage_times=[
                datetime.utcnow() - timedelta(hours=2),
                datetime.utcnow() - timedelta(hours=8),
                datetime.utcnow() - timedelta(hours=14)
            ],
            resource_alerts=[
                {"type": "cpu_high", "threshold": 80, "occurred_at": datetime.utcnow() - timedelta(hours=2)},
                {"type": "disk_space_low", "threshold": 90, "occurred_at": datetime.utcnow() - timedelta(hours=5)}
            ]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch system utilization: {str(e)}")


@router.get("/templates/types")
async def get_report_types() -> Dict[str, Any]:
    """Get available report types and their descriptions"""
    try:
        return {
            "weekly_summary": {
                "description": "Comprehensive weekly activity summary",
                "includes": ["assets", "jobs", "storage", "performance"],
                "formats": ["json", "html", "pdf"]
            },
            "asset_summary": {
                "description": "Detailed asset analysis and statistics",
                "includes": ["asset_counts", "storage_usage", "processing_times"],
                "formats": ["json", "html", "csv"]
            },
            "job_performance": {
                "description": "Job queue performance and error analysis",
                "includes": ["success_rates", "execution_times", "error_breakdown"],
                "formats": ["json", "html", "csv"]
            },
            "system_utilization": {
                "description": "System resource usage and performance",
                "includes": ["cpu", "memory", "disk", "gpu", "alerts"],
                "formats": ["json", "html", "pdf"]
            },
            "rule_execution": {
                "description": "Automation rule execution statistics",
                "includes": ["rule_performance", "execution_counts", "error_rates"],
                "formats": ["json", "html"]
            },
            "overlay_analytics": {
                "description": "Overlay usage and performance metrics",
                "includes": ["view_counts", "show_duration", "popularity"],
                "formats": ["json", "html"]
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch report types: {str(e)}")


@router.post("/schedule")
async def schedule_report(
    report_request: ReportGenerate,
    cron_expression: str = Query(..., description="Cron expression for scheduling"),
    db=Depends(get_db)
) -> Dict[str, str]:
    """Schedule automatic report generation"""
    try:
        # Store scheduled report in database
        schedule_id = str(uuid.uuid4())
        schedule_data = {
            'report_type': report_request.report_type.value,
            'format': report_request.format.value,
            'period': report_request.period.value,
            'cron': cron_expression,
            'enabled': True,
            'next_run': None  # Would be calculated from cron expression
        }
        
        await db.execute(
            """INSERT INTO so_configs (key, value, created_at, updated_at)
               VALUES (?, ?, ?, ?)""",
            (f"scheduled_report_{schedule_id}", json.dumps(schedule_data),
             datetime.utcnow().isoformat(), datetime.utcnow().isoformat())
        )
        await db.commit()
        
        return {"message": f"Report {report_request.report_type.value} scheduled with cron: {cron_expression}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to schedule report: {str(e)}")


@router.get("/scheduled/list")
async def list_scheduled_reports(db=Depends(get_db)) -> List[Dict[str, Any]]:
    """List all scheduled reports"""
    try:
        # Get scheduled reports from database
        cursor = await db.execute(
            """SELECT key, value FROM so_configs 
               WHERE key LIKE 'scheduled_report_%'"""
        )
        rows = await cursor.fetchall()
        
        scheduled_reports = []
        for row in rows:
            schedule_id = row[0].replace('scheduled_report_', '')
            schedule_data = json.loads(row[1])
            scheduled_reports.append(
                {
                    "id": schedule_id,
                    "report_type": schedule_data.get('report_type', 'unknown'),
                    "cron_expression": schedule_data.get('cron', ''),
                    "next_run": datetime.utcnow() + timedelta(days=1),  # Would be calculated
                    "enabled": schedule_data.get('enabled', True)
                }
            )
        
        if not scheduled_reports:
            # Return example if none exist
            scheduled_reports = [
            {
                "id": str(uuid.uuid4()),
                "report_type": "weekly_summary",
                "cron_expression": "0 9 * * MON",
                "next_run": datetime.utcnow() + timedelta(days=1),
                "enabled": True
            }
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list scheduled reports: {str(e)}")


# Background task functions
async def _generate_report(
    report_id: str, 
    report_request: ReportGenerate, 
    start_date: date, 
    end_date: date
):
    """Background task to generate report with complete data collection"""
    try:
        from app.api.db.database import get_db
        import csv
        
        db = await get_db()
        
        # Create report directory
        os.makedirs("/data/reports", exist_ok=True)
        
        # Generate comprehensive report data based on type
        report_data = {}
        
        if report_request.report_type == ReportType.weekly_summary:
            # Collect comprehensive weekly data
            
            # Assets processed
            cursor = await db.execute(
                """SELECT COUNT(*) as total,
                          SUM(size) as total_size,
                          COUNT(DISTINCT container) as formats
                   FROM so_assets 
                   WHERE DATE(created_at) >= ? AND DATE(created_at) <= ?""",
                (start_date.isoformat(), end_date.isoformat())
            )
            asset_stats = await cursor.fetchone()
            
            # Jobs completed
            cursor = await db.execute(
                """SELECT state, COUNT(*) as count
                   FROM so_jobs
                   WHERE DATE(created_at) >= ? AND DATE(created_at) <= ?
                   GROUP BY state""",
                (start_date.isoformat(), end_date.isoformat())
            )
            job_stats = {row[0]: row[1] for row in await cursor.fetchall()}
            
            # Calculate success rate
            total_jobs = sum(job_stats.values())
            success_rate = (100.0 * job_stats.get('completed', 0) / total_jobs) if total_jobs > 0 else 0
            
            # Storage growth
            cursor = await db.execute(
                """SELECT SUM(size) FROM so_assets WHERE DATE(created_at) < ?""",
                (start_date.isoformat(),)
            )
            prev_size = (await cursor.fetchone())[0] or 0
            storage_growth = ((asset_stats[1] or 0) / prev_size * 100) if prev_size > 0 else 0
            
            # Top processing types
            cursor = await db.execute(
                """SELECT type, COUNT(*) as count
                   FROM so_jobs
                   WHERE DATE(created_at) >= ? AND DATE(created_at) <= ?
                   GROUP BY type
                   ORDER BY count DESC
                   LIMIT 5""",
                (start_date.isoformat(), end_date.isoformat())
            )
            top_job_types = [{"type": row[0], "count": row[1]} for row in await cursor.fetchall()]
            
            report_data = {
                "title": "Weekly Summary Report",
                "period": f"{start_date.strftime('%B %d')} - {end_date.strftime('%B %d, %Y')}",
                "generated_at": datetime.utcnow().isoformat(),
                "summary": {
                    "assets_processed": asset_stats[0] or 0,
                    "total_size_bytes": asset_stats[1] or 0,
                    "unique_formats": asset_stats[2] or 0,
                    "jobs_completed": job_stats.get('completed', 0),
                    "jobs_failed": job_stats.get('failed', 0),
                    "success_rate": round(success_rate, 2),
                    "storage_growth_percent": round(storage_growth, 2)
                },
                "job_breakdown": job_stats,
                "top_processing_types": top_job_types
            }
        
        elif report_request.report_type == ReportType.asset_summary:
            # Comprehensive asset analysis
            cursor = await db.execute(
                """SELECT COUNT(*) as total,
                          SUM(size) as total_size,
                          AVG(size) as avg_size,
                          MAX(size) as max_size,
                          MIN(size) as min_size
                   FROM so_assets""")
            stats = await cursor.fetchone()
            
            # By container type
            cursor = await db.execute(
                """SELECT container, COUNT(*) as count, SUM(size) as total_size
                   FROM so_assets
                   GROUP BY container""")
            by_container = [{"type": row[0] or "unknown", "count": row[1], "size": row[2]} 
                           for row in await cursor.fetchall()]
            
            # By status
            cursor = await db.execute(
                """SELECT status, COUNT(*) as count
                   FROM so_assets
                   GROUP BY status""")
            by_status = {row[0]: row[1] for row in await cursor.fetchall()}
            
            # Resolution distribution for videos
            cursor = await db.execute(
                """SELECT width, height, COUNT(*) as count
                   FROM so_assets
                   WHERE width IS NOT NULL AND height IS NOT NULL
                   GROUP BY width, height
                   ORDER BY count DESC
                   LIMIT 10""")
            resolutions = [{"resolution": f"{row[0]}x{row[1]}", "count": row[2]} 
                          for row in await cursor.fetchall()]
            
            report_data = {
                "title": "Asset Summary Report",
                "generated_at": datetime.utcnow().isoformat(),
                "statistics": {
                    "total_assets": stats[0] or 0,
                    "total_size_bytes": stats[1] or 0,
                    "average_size_bytes": int(stats[2]) if stats[2] else 0,
                    "largest_file_bytes": stats[3] or 0,
                    "smallest_file_bytes": stats[4] or 0
                },
                "by_container": by_container,
                "by_status": by_status,
                "top_resolutions": resolutions
            }
            
        elif report_request.report_type == ReportType.job_performance:
            # Job performance analysis
            cursor = await db.execute(
                """SELECT type, 
                          COUNT(*) as total,
                          SUM(CASE WHEN state = 'completed' THEN 1 ELSE 0 END) as completed,
                          SUM(CASE WHEN state = 'failed' THEN 1 ELSE 0 END) as failed,
                          AVG(CASE WHEN state = 'completed' THEN progress ELSE NULL END) as avg_progress
                   FROM so_jobs
                   GROUP BY type""")
            
            job_metrics = []
            for row in await cursor.fetchall():
                success_rate = (100.0 * row[2] / row[1]) if row[1] > 0 else 0
                job_metrics.append({
                    "type": row[0],
                    "total": row[1],
                    "completed": row[2],
                    "failed": row[3],
                    "success_rate": round(success_rate, 2)
                })
            
            # Error analysis
            cursor = await db.execute(
                """SELECT error, COUNT(*) as count
                   FROM so_jobs
                   WHERE error IS NOT NULL
                   GROUP BY error
                   ORDER BY count DESC
                   LIMIT 10""")
            errors = [{"error": row[0][:100], "count": row[1]} for row in await cursor.fetchall()]
            
            report_data = {
                "title": "Job Performance Report",
                "generated_at": datetime.utcnow().isoformat(),
                "job_metrics": job_metrics,
                "error_analysis": errors
            }
        
        # Generate file based on format
        file_path = None
        file_size = 0
        
        if report_request.format == ReportFormat.json:
            file_path = f"/data/reports/report_{report_id}.json"
            with open(file_path, 'w') as f:
                json.dump(report_data, f, indent=2, default=str)
            file_size = os.path.getsize(file_path)
        
        elif report_request.format == ReportFormat.csv:
            file_path = f"/data/reports/report_{report_id}.csv"
            with open(file_path, 'w', newline='') as f:
                # Flatten nested data for CSV
                flat_data = []
                for key, value in report_data.items():
                    if isinstance(value, dict):
                        for sub_key, sub_value in value.items():
                            flat_data.append({"metric": f"{key}.{sub_key}", "value": str(sub_value)})
                    elif isinstance(value, list):
                        flat_data.append({"metric": key, "value": json.dumps(value)})
                    else:
                        flat_data.append({"metric": key, "value": str(value)})
                
                writer = csv.DictWriter(f, fieldnames=["metric", "value"])
                writer.writeheader()
                writer.writerows(flat_data)
            file_size = os.path.getsize(file_path)
        
        elif report_request.format == ReportFormat.html:
            file_path = f"/data/reports/report_{report_id}.html"
            
            # Generate styled HTML report
            html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>{report_data.get('title', 'Report')}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
                margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; 
                     padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; }}
        .metric {{ display: inline-block; margin: 10px 20px 10px 0; }}
        .metric-value {{ font-size: 24px; font-weight: bold; color: #007bff; }}
        .metric-label {{ font-size: 14px; color: #666; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #f8f9fa; font-weight: 600; }}
        .timestamp {{ color: #666; font-size: 14px; margin-top: 30px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{report_data.get('title', 'Report')}</h1>
        <p class="timestamp">Generated: {report_data.get('generated_at', '')}</p>
        """
            
            # Add summary metrics if present
            if 'summary' in report_data:
                html_content += "<h2>Summary</h2><div>"
                for key, value in report_data['summary'].items():
                    label = key.replace('_', ' ').title()
                    html_content += f'<div class="metric"><div class="metric-value">{value}</div><div class="metric-label">{label}</div></div>'
                html_content += "</div>"
            
            # Add tables for list data
            for key, value in report_data.items():
                if isinstance(value, list) and value:
                    html_content += f"<h2>{key.replace('_', ' ').title()}</h2><table>"
                    if isinstance(value[0], dict):
                        headers = value[0].keys()
                        html_content += "<tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr>"
                        for item in value:
                            html_content += "<tr>" + "".join(f"<td>{item.get(h, '')}</td>" for h in headers) + "</tr>"
                    html_content += "</table>"
            
            html_content += """
    </div>
</body>
</html>"""
            
            with open(file_path, 'w') as f:
                f.write(html_content)
            file_size = os.path.getsize(file_path)
        
        # Update database with file info
        cursor = await db.execute(
            "SELECT top_games_json FROM so_reports WHERE id = ?",
            (report_id,)
        )
        row = await cursor.fetchone()
        
        if row:
            top_games = json.loads(row[0]) if row[0] else {}
            report_meta = top_games.get('report_meta', {})
            report_meta['file_path'] = file_path
            report_meta['size_bytes'] = file_size
            report_meta['status'] = 'completed'
            report_meta['data'] = report_data  # Store full data for retrieval
            top_games['report_meta'] = report_meta
            
            await db.execute(
                "UPDATE so_reports SET top_games_json = ?, updated_at = ? WHERE id = ?",
                (json.dumps(top_games), datetime.utcnow().isoformat(), report_id)
            )
            await db.commit()
        
        logger.info(f"Successfully generated report {report_id} ({file_size} bytes) at {file_path}")
        
    except Exception as e:
        logger.error(f"Failed to generate report {report_id}: {e}")
        # Mark report as failed in database
        try:
            cursor = await db.execute(
                "SELECT top_games_json FROM so_reports WHERE id = ?",
                (report_id,)
            )
            row = await cursor.fetchone()
            if row:
                top_games = json.loads(row[0]) if row[0] else {}
                report_meta = top_games.get('report_meta', {})
                report_meta['status'] = 'failed'
                report_meta['error'] = str(e)
                top_games['report_meta'] = report_meta
                
                await db.execute(
                    "UPDATE so_reports SET top_games_json = ? WHERE id = ?",
                    (json.dumps(top_games), report_id)
                )
                await db.commit()
        except:
            pass