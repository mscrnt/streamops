from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks, Response
from fastapi.responses import StreamingResponse, FileResponse
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path
from pydantic import BaseModel, Field
import uuid
import os
import json
import logging
import aiosqlite

from app.api.schemas.assets import (
    AssetResponse, AssetCreate, AssetUpdate, AssetListResponse,
    AssetSearchQuery, AssetThumbnailResponse, AssetStatus, AssetType
)
from app.api.db.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()

# Additional Pydantic models for new endpoints
class AssetDetailResponse(BaseModel):
    asset: Dict[str, Any]
    thumbs: Dict[str, str]
    jobs_recent: List[Dict[str, Any]]

class AssetAction(BaseModel):
    action: str
    params: Dict[str, Any] = {}

class BulkAssetAction(BaseModel):
    ids: List[str]
    action: str
    params: Dict[str, Any] = {}

class ActionResponse(BaseModel):
    ok: bool
    job_ids: List[str] = []
    message: Optional[str] = None

class PathResponse(BaseModel):
    container_path: str
    host_hint: Optional[str] = None
    can_open_on_host: bool = False


@router.get("/", response_model=AssetListResponse)
async def list_assets(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    status: Optional[AssetStatus] = Query(None, description="Filter by status"),
    asset_type: Optional[AssetType] = Query(None, description="Filter by asset type"),
    types: Optional[str] = Query(None, description="Alternative parameter for asset_type"),
    session_id: Optional[str] = Query(None, description="Filter by session ID"),
    tags: Optional[List[str]] = Query(None, description="Filter by tags"),
    search: Optional[str] = Query(None, description="Full-text search query"),
    sort: str = Query("created_at:desc", description="Sort field and direction"),
    db=Depends(get_db)
) -> AssetListResponse:
    """List assets with filtering, search, and pagination"""
    try:
        query = "SELECT * FROM so_assets WHERE 1=1"
        params = []
        
        if status:
            query += " AND status = ?"
            params.append(status.value)
        
        # Handle both asset_type and types parameters
        type_filter = asset_type or (AssetType(types) if types else None)
        if type_filter:
            query += " AND json_extract(streams_json, '$.type') = ?"
            params.append(type_filter.value)
        
        if session_id:
            query += " AND json_extract(tags_json, '$.session_id') = ?"
            params.append(session_id)
        if search:
            query += " AND (abs_path LIKE ? OR json_extract(tags_json, '$') LIKE ?)"
            search_term = f"%{search}%"
            params.extend([search_term, search_term])
        
        # Apply sorting
        sort_field, sort_dir = sort.split(':') if ':' in sort else (sort, 'desc')
        valid_sort_fields = ['created_at', 'updated_at', 'size', 'abs_path']
        if sort_field in valid_sort_fields:
            query += f" ORDER BY {sort_field} {sort_dir.upper()}"
        else:
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
        
        assets = []
        for row in rows:
            streams = json.loads(row[15]) if row[15] else {}
            tags = json.loads(row[16]) if row[16] else []
            
            # Build metadata from row data
            metadata = {
                "size_bytes": row[3],
                "duration": row[8],
                "width": row[11],
                "height": row[12],
                "fps": row[13],
                "codec": row[9],
                "container": row[14]
            }
            
            assets.append(AssetResponse(
                id=row[0],
                filepath=row[1],
                filename=os.path.basename(row[1]),
                asset_type=AssetType(streams.get('type', 'video')),
                status=AssetStatus(row[17]),
                session_id=tags.get('session_id') if isinstance(tags, dict) else None,
                tags=tags if isinstance(tags, list) else [],
                metadata=metadata,
                created_at=datetime.fromisoformat(row[18]),
                updated_at=datetime.fromisoformat(row[19])
            ))
        
        return AssetListResponse(
            assets=assets,
            total=total,
            page=page,
            per_page=per_page
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch assets: {str(e)}")


@router.post("/", response_model=AssetResponse)
async def create_asset(
    asset: AssetCreate,
    background_tasks: BackgroundTasks,
    db=Depends(get_db)
) -> AssetResponse:
    """Create a new asset and trigger processing"""
    try:
        asset_id = str(uuid.uuid4())
        
        # Detect asset type from file extension
        ext = os.path.splitext(asset.filepath)[1].lower()
        if ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv']:
            asset_type = AssetType.video
        elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
            asset_type = AssetType.image
        elif ext in ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a']:
            asset_type = AssetType.audio
        else:
            asset_type = AssetType.other
        
        # Get file stats
        file_stats = os.stat(asset.filepath) if os.path.exists(asset.filepath) else None
        
        # Insert into database
        now = datetime.utcnow()
        await db.execute(
            """INSERT INTO so_assets (id, abs_path, drive_hint, size, mtime, ctime, status, 
                                      tags_json, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (asset_id, asset.filepath, asset.drive_id, 
             file_stats.st_size if file_stats else 0,
             file_stats.st_mtime if file_stats else 0,
             file_stats.st_ctime if file_stats else 0,
             AssetStatus.pending.value,
             json.dumps(asset.tags or []),
             now.isoformat(), now.isoformat())
        )
        await db.commit()
        
        # Queue asset processing job if NATS is enabled
        if os.getenv("NATS_ENABLE", "true").lower() == "true":
            try:
                from app.api.main import app
                if hasattr(app.state, 'nats'):
                    await app.state.nats.publish_job('index', {
                        'id': str(uuid.uuid4()),
                        'asset_id': asset_id,
                        'filepath': asset.filepath,
                        'type': asset_type.value
                    })
            except Exception as e:
                logger.warning(f"Failed to queue asset processing: {e}")
        
        # Add background task for initial processing
        background_tasks.add_task(_process_asset, asset_id, asset.filepath)
        
        return AssetResponse(
            id=asset_id,
            filepath=asset.filepath,
            filename=os.path.basename(asset.filepath),
            asset_type=asset_type,
            status=AssetStatus.pending,
            session_id=asset.session_id,
            tags=asset.tags or [],
            metadata={
                'size_bytes': file_stats.st_size if file_stats else 0,
                'created': file_stats.st_ctime if file_stats else 0,
                'modified': file_stats.st_mtime if file_stats else 0
            },
            created_at=now,
            updated_at=now
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create asset: {str(e)}")


@router.post("/search", response_model=AssetListResponse)
async def search_assets(
    query: AssetSearchQuery,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    db=Depends(get_db)
) -> AssetListResponse:
    """Advanced asset search with multiple filters"""
    try:
        # Build the search query
        base_query = "SELECT * FROM so_assets WHERE 1=1"
        params = []
        
        # Add search filter using FTS if query text is provided
        if query.query:
            # Use FTS table for text search
            base_query = """
                SELECT a.* FROM so_assets a
                JOIN so_assets_fts f ON a.id = f.rowid
                WHERE so_assets_fts MATCH ?
            """
            params.append(query.query)
            
            # Add other filters
            if query.asset_type:
                base_query += " AND a.status = ?"
                params.append(query.asset_type.value)
            if query.tags:
                for tag in query.tags:
                    base_query += " AND json_extract(a.tags_json, '$') LIKE ?"
                    params.append(f'%"{tag}"%')
            if query.min_duration:
                base_query += " AND a.duration >= ?"
                params.append(query.min_duration)
            if query.max_duration:
                base_query += " AND a.duration <= ?"
                params.append(query.max_duration)
        else:
            # No search query, apply filters only
            if query.asset_type:
                base_query += " AND json_extract(streams_json, '$.type') = ?"
                params.append(query.asset_type.value)
            if query.tags:
                for tag in query.tags:
                    base_query += " AND json_extract(tags_json, '$') LIKE ?"
                    params.append(f'%"{tag}"%')
            if query.min_duration:
                base_query += " AND duration >= ?"
                params.append(query.min_duration)
            if query.max_duration:
                base_query += " AND duration <= ?"
                params.append(query.max_duration)
        
        # Get total count
        if "SELECT a.*" in base_query:
            count_query = base_query.replace("SELECT a.*", "SELECT COUNT(a.id)", 1)
        else:
            count_query = base_query.replace("SELECT *", "SELECT COUNT(*)", 1)
        cursor = await db.execute(count_query, params)
        total = (await cursor.fetchone())[0]
        
        # Add ordering and pagination
        base_query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([per_page, (page - 1) * per_page])
        
        # Execute the query
        cursor = await db.execute(base_query, params)
        rows = await cursor.fetchall()
        
        assets = []
        for row in rows:
            streams = json.loads(row[15]) if row[15] else {}
            tags = json.loads(row[16]) if row[16] else []
            
            # Detect asset type
            ext = os.path.splitext(row[1])[1].lower()
            if streams.get('type'):
                asset_type = AssetType(streams['type'])
            elif ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv']:
                asset_type = AssetType.video
            elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
                asset_type = AssetType.image
            elif ext in ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a']:
                asset_type = AssetType.audio
            else:
                asset_type = AssetType.other
            
            # Build metadata
            metadata = {
                "size_bytes": row[3],
                "duration": row[8],
                "width": row[11],
                "height": row[12],
                "fps": row[13],
                "video_codec": row[9],
                "audio_codec": row[10],
                "container": row[14]
            }
            metadata = {k: v for k, v in metadata.items() if v is not None}
            
            assets.append(AssetResponse(
                id=row[0],
                filepath=row[1],
                filename=os.path.basename(row[1]),
                asset_type=asset_type,
                status=AssetStatus(row[17]),
                session_id=tags.get('session_id') if isinstance(tags, dict) else None,
                tags=tags if isinstance(tags, list) else [],
                metadata=metadata,
                created_at=datetime.fromisoformat(row[18]),
                updated_at=datetime.fromisoformat(row[19])
            ))
        
        return AssetListResponse(
            assets=assets,
            total=total,
            page=page,
            per_page=per_page
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Asset search failed: {str(e)}")


@router.get("/stats")
async def get_asset_stats(
    time_range: str = Query("24h", description="Time range for stats (1h, 24h, 7d, 30d)"),
    db=Depends(get_db)
) -> Dict[str, Any]:
    """Get asset statistics for the specified time range"""
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
        
        # Get total asset count
        cursor = await db.execute(
            "SELECT COUNT(*) FROM so_assets WHERE created_at >= ?",
            (time_offset.isoformat(),)
        )
        total_assets = (await cursor.fetchone())[0]
        
        # Get asset counts by type
        cursor = await db.execute(
            """SELECT container, COUNT(*) FROM so_assets 
               WHERE created_at >= ? 
               GROUP BY container""",
            (time_offset.isoformat(),)
        )
        type_counts = {row[0]: row[1] for row in await cursor.fetchall() if row[0]}
        
        # Get total size
        cursor = await db.execute(
            "SELECT SUM(size) FROM so_assets WHERE created_at >= ?",
            (time_offset.isoformat(),)
        )
        total_size = (await cursor.fetchone())[0] or 0
        
        # Get assets with thumbnails
        cursor = await db.execute(
            "SELECT COUNT(*) FROM so_thumbs WHERE asset_id IN (SELECT id FROM so_assets WHERE created_at >= ?)",
            (time_offset.isoformat(),)
        )
        with_thumbnails = (await cursor.fetchone())[0]
        
        return {
            "time_range": time_range,
            "total_assets": total_assets,
            "total_size_bytes": total_size,
            "total_size_gb": round(total_size / (1024**3), 2) if total_size else 0,
            "type_breakdown": type_counts,
            "with_thumbnails": with_thumbnails,
            "thumbnail_percentage": round((with_thumbnails / total_assets * 100) if total_assets > 0 else 0, 2)
        }
    except Exception as e:
        logger.error(f"Failed to get asset stats: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get asset stats: {str(e)}")


@router.post("/scan/recording")
async def scan_recording_folders(
    db=Depends(get_db)
) -> Dict[str, Any]:
    """Manually trigger scan of recording folders for new assets"""
    try:
        # Get recording folder paths
        cursor = await db.execute(
            "SELECT abs_path FROM so_roles WHERE role = 'recording'"
        )
        rows = await cursor.fetchall()
        
        if not rows:
            return {"status": "error", "message": "No recording folders configured"}
        
        scanned_count = 0
        indexed_count = 0
        
        for row in rows:
            recording_path = row[0]
            logger.info(f"Scanning recording folder: {recording_path}")
            
            # Import and use DriveWatcher to scan
            from app.worker.watchers.drive_watcher import DriveWatcher
            
            # Try to get NATS service from app state
            nats = None
            try:
                from app.api.main import app
                if hasattr(app.state, 'nats'):
                    nats = app.state.nats
                    logger.info("Using NATS service from app state")
            except Exception as e:
                logger.warning(f"NATS not available, will index directly: {e}")
            
            watcher = DriveWatcher(recording_path, nats)
            # Note: scan_existing will queue index jobs for unindexed files
            await watcher.scan_existing()
            scanned_count += 1
        
        return {
            "status": "success",
            "message": f"Scanned {scanned_count} recording folder(s)",
            "folders_scanned": scanned_count
        }
        
    except Exception as e:
        logger.error(f"Failed to scan recording folders: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to scan: {str(e)}")


@router.get("/recent")
async def get_recent_assets(
    limit: int = Query(10, ge=1, le=100, description="Number of recent assets to return"),
    db=Depends(get_db)
) -> List[AssetResponse]:
    """Get recently added video assets from recording folders only"""
    try:
        # First get recording folder path
        recording_cursor = await db.execute(
            "SELECT abs_path FROM so_roles WHERE role = 'recording'"
        )
        recording_row = await recording_cursor.fetchone()
        
        if not recording_row:
            # No recording folder configured
            return []
            
        recording_path = recording_row[0]
        
        # Filter for video files in recording folder by extension
        cursor = await db.execute(
            """SELECT * FROM so_assets 
               WHERE abs_path LIKE ? AND (
                   abs_path LIKE '%.mp4' OR 
                   abs_path LIKE '%.mov' OR 
                   abs_path LIKE '%.mkv' OR 
                   abs_path LIKE '%.avi' OR 
                   abs_path LIKE '%.flv' OR 
                   abs_path LIKE '%.webm' OR
                   abs_path LIKE '%.ts' OR
                   abs_path LIKE '%.m2ts' OR
                   abs_path LIKE '%.mts' OR
                   abs_path LIKE '%.wmv' OR
                   abs_path LIKE '%.mpg' OR
                   abs_path LIKE '%.mpeg'
               )
               ORDER BY created_at DESC 
               LIMIT ?""",
            (f"{recording_path}%", limit,)
        )
        rows = await cursor.fetchall()
        
        assets = []
        for row in rows:
            # Parse JSON fields
            streams = json.loads(row[15]) if row[15] else []
            tags = json.loads(row[16]) if row[16] else []
            
            # Build metadata from available fields
            metadata = {
                "duration": row[8],
                "width": row[11],
                "height": row[12],
                "fps": row[13],
                "codec": row[9],
                "container": row[14],
                "size_bytes": row[3]
            }
            
            # All results are videos since we filtered in the query
            asset_type = "video"
            
            assets.append(AssetResponse(
                id=row[0],
                filepath=row[1],  # Using abs_path as filepath
                filename=os.path.basename(row[1]) if row[1] else "",
                asset_type=asset_type,
                status=row[17],
                session_id=None,  # Not in current schema
                tags=tags,
                metadata=metadata,
                created_at=datetime.fromisoformat(row[18]),
                updated_at=datetime.fromisoformat(row[19])
            ))
        
        return assets
    except Exception as e:
        logger.error(f"Failed to get recent assets: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get recent assets: {str(e)}")
@router.get("/{asset_id}", response_model=AssetResponse)
async def get_asset(asset_id: str, db=Depends(get_db)) -> AssetResponse:
    """Get a specific asset by ID"""
    try:
        cursor = await db.execute(
            "SELECT * FROM so_assets WHERE id = ?",
            (asset_id,)
        )
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail=f"Asset {asset_id} not found")
        
        streams = json.loads(row[15]) if row[15] else {}
        tags = json.loads(row[16]) if row[16] else []
        
        # Detect asset type from streams or file extension
        ext = os.path.splitext(row[1])[1].lower()
        if streams.get('type'):
            asset_type = AssetType(streams['type'])
        elif ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv']:
            asset_type = AssetType.video
        elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
            asset_type = AssetType.image
        elif ext in ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a']:
            asset_type = AssetType.audio
        else:
            asset_type = AssetType.other
        
        # Build metadata from row data
        metadata = {
            "size_bytes": row[3],
            "duration": row[8],
            "width": row[11],
            "height": row[12],
            "fps": row[13],
            "video_codec": row[9],
            "audio_codec": row[10],
            "container": row[14]
        }
        
        # Remove None values from metadata
        metadata = {k: v for k, v in metadata.items() if v is not None}
        
        return AssetResponse(
            id=row[0],
            filepath=row[1],
            filename=os.path.basename(row[1]),
            asset_type=asset_type,
            status=AssetStatus(row[17]),
            session_id=tags.get('session_id') if isinstance(tags, dict) else None,
            tags=tags if isinstance(tags, list) else [],
            metadata=metadata,
            created_at=datetime.fromisoformat(row[18]),
            updated_at=datetime.fromisoformat(row[19])
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch asset: {str(e)}")


@router.put("/{asset_id}", response_model=AssetResponse)
async def update_asset(
    asset_id: str,
    asset_update: AssetUpdate,
    db=Depends(get_db)
) -> AssetResponse:
    """Update an asset"""
    try:
        # Check if asset exists
        cursor = await db.execute(
            "SELECT * FROM so_assets WHERE id = ?",
            (asset_id,)
        )
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail=f"Asset {asset_id} not found")
        
        # Build update query
        updates = []
        params = []
        
        if asset_update.status:
            updates.append("status = ?")
            params.append(asset_update.status.value)
        
        if asset_update.tags is not None:
            updates.append("tags_json = ?")
            params.append(json.dumps(asset_update.tags))
        
        if asset_update.metadata:
            # Merge with existing metadata
            existing_streams = json.loads(row[15]) if row[15] else {}
            existing_streams.update(asset_update.metadata)
            updates.append("streams_json = ?")
            params.append(json.dumps(existing_streams))
        
        if asset_update.session_id is not None:
            # Store session_id in tags_json
            tags = json.loads(row[16]) if row[16] else {}
            if not isinstance(tags, dict):
                tags = {'tags': tags, 'session_id': asset_update.session_id}
            else:
                tags['session_id'] = asset_update.session_id
            updates.append("tags_json = ?")
            params.append(json.dumps(tags))
        
        # Update timestamp
        updates.append("updated_at = ?")
        params.append(datetime.utcnow().isoformat())
        
        # Execute update
        params.append(asset_id)
        await db.execute(
            f"UPDATE so_assets SET {', '.join(updates)} WHERE id = ?",
            params
        )
        await db.commit()
        
        # Return updated asset
        return await get_asset(asset_id, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update asset: {str(e)}")


@router.delete("/{asset_id}")
async def delete_asset(
    asset_id: str,
    delete_files: bool = Query(False, description="Also delete physical files"),
    db=Depends(get_db)
) -> dict:
    """Delete an asset and optionally its files"""
    try:
        # Get asset info before deletion
        cursor = await db.execute(
            "SELECT abs_path FROM so_assets WHERE id = ?",
            (asset_id,)
        )
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail=f"Asset {asset_id} not found")
        
        filepath = row[0]
        
        # Delete from database
        await db.execute("DELETE FROM so_assets WHERE id = ?", (asset_id,))
        
        # Also delete related thumbnails
        await db.execute("DELETE FROM so_thumbs WHERE asset_id = ?", (asset_id,))
        
        await db.commit()
        
        # Optionally delete physical files
        if delete_files and filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
                # Also try to delete thumbnail files
                thumb_dir = f"/data/thumbs/{asset_id}"
                if os.path.exists(thumb_dir):
                    import shutil
                    shutil.rmtree(thumb_dir)
            except Exception as e:
                logger.warning(f"Failed to delete physical files for asset {asset_id}: {e}")
        
        return {"message": f"Asset {asset_id} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete asset: {str(e)}")


@router.get("/{asset_id}/thumbnails", response_model=AssetThumbnailResponse)
async def get_asset_thumbnails(asset_id: str, db=Depends(get_db)) -> AssetThumbnailResponse:
    """Get thumbnail URLs for an asset"""
    try:
        # Check if thumbnails exist in database
        cursor = await db.execute(
            "SELECT * FROM so_thumbs WHERE asset_id = ?",
            (asset_id,)
        )
        row = await cursor.fetchone()
        
        if row:
            # Thumbnails exist, return actual URLs
            return AssetThumbnailResponse(
                poster_url=f"/api/assets/{asset_id}/thumbnail/poster.jpg",
                sprite_url=f"/api/assets/{asset_id}/thumbnail/sprite.jpg",
                hover_url=f"/api/assets/{asset_id}/thumbnail/hover.mp4",
                generated_at=datetime.fromisoformat(row[5]) if row[5] else datetime.utcnow()
            )
        else:
            # Check if thumbnail files exist on disk
            thumb_dir = f"/data/thumbs/{asset_id}"
            poster_exists = os.path.exists(f"{thumb_dir}/poster.jpg")
            sprite_exists = os.path.exists(f"{thumb_dir}/sprite.jpg")
            hover_exists = os.path.exists(f"{thumb_dir}/hover.mp4")
            
            if poster_exists or sprite_exists or hover_exists:
                # Files exist but not in database, add to database
                now = datetime.utcnow()
                await db.execute(
                    """INSERT INTO so_thumbs (id, asset_id, poster_path, sprite_path, hover_path, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (str(uuid.uuid4()), asset_id,
                     f"{thumb_dir}/poster.jpg" if poster_exists else None,
                     f"{thumb_dir}/sprite.jpg" if sprite_exists else None,
                     f"{thumb_dir}/hover.mp4" if hover_exists else None,
                     now.isoformat())
                )
                await db.commit()
                
                return AssetThumbnailResponse(
                    poster_url=f"/api/assets/{asset_id}/thumbnail/poster.jpg" if poster_exists else None,
                    sprite_url=f"/api/assets/{asset_id}/thumbnail/sprite.jpg" if sprite_exists else None,
                    hover_url=f"/api/assets/{asset_id}/thumbnail/hover.mp4" if hover_exists else None,
                    generated_at=now
                )
            else:
                # No thumbnails exist
                raise HTTPException(status_code=404, detail=f"No thumbnails found for asset {asset_id}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch thumbnails: {str(e)}")


@router.post("/{asset_id}/thumbnails")
async def generate_thumbnails(
    asset_id: str,
    background_tasks: BackgroundTasks,
    force_regenerate: bool = Query(False, description="Force regeneration of existing thumbnails"),
    db=Depends(get_db)
) -> dict:
    """Generate thumbnails for an asset"""
    try:
        # Check if asset exists
        cursor = await db.execute(
            "SELECT abs_path FROM so_assets WHERE id = ?",
            (asset_id,)
        )
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail=f"Asset {asset_id} not found")
        
        # Check if thumbnails already exist
        if not force_regenerate:
            cursor = await db.execute(
                "SELECT id FROM so_thumbs WHERE asset_id = ?",
                (asset_id,)
            )
            if await cursor.fetchone():
                return {"message": f"Thumbnails already exist for asset {asset_id}. Use force_regenerate=true to regenerate."}
        
        # Queue thumbnail generation job if NATS is enabled
        if os.getenv("NATS_ENABLE", "true").lower() == "true":
            try:
                from app.api.main import app
                if hasattr(app.state, 'nats'):
                    job_id = str(uuid.uuid4())
                    await app.state.nats.publish_job('thumbnail', {
                        'id': job_id,
                        'asset_id': asset_id,
                        'filepath': row[0],
                        'force': force_regenerate
                    })
                    
                    # Add job to database
                    now = datetime.utcnow()
                    await db.execute(
                        """INSERT INTO so_jobs (id, type, state, asset_id, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (job_id, 'thumbnail', 'queued', asset_id, now.isoformat(), now.isoformat())
                    )
                    await db.commit()
                    
                    return {"message": f"Thumbnail generation job {job_id} queued for asset {asset_id}"}
            except Exception as e:
                logger.warning(f"Failed to queue thumbnail generation via NATS: {e}")
        
        # Fallback to background task
        background_tasks.add_task(_generate_thumbnails, asset_id, row[0], force_regenerate)
        
        return {"message": f"Thumbnail generation queued for asset {asset_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to queue thumbnail generation: {str(e)}")


@router.post("/{asset_id}/process")
async def reprocess_asset(
    asset_id: str,
    background_tasks: BackgroundTasks,
    force: bool = Query(False, description="Force reprocessing even if completed"),
    db=Depends(get_db)
) -> dict:
    """Reprocess an asset (metadata extraction, thumbnails, etc.)"""
    try:
        # Check if asset exists
        cursor = await db.execute(
            "SELECT abs_path, status FROM so_assets WHERE id = ?",
            (asset_id,)
        )
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail=f"Asset {asset_id} not found")
        
        # Check if already processed
        if not force and row[1] == AssetStatus.ready.value:
            return {"message": f"Asset {asset_id} is already processed. Use force=true to reprocess."}
        
        # Queue reprocessing job if NATS is enabled
        if os.getenv("NATS_ENABLE", "true").lower() == "true":
            try:
                from app.api.main import app
                if hasattr(app.state, 'nats'):
                    job_id = str(uuid.uuid4())
                    await app.state.nats.publish_job('index', {
                        'id': job_id,
                        'asset_id': asset_id,
                        'filepath': row[0],
                        'reprocess': True,
                        'force': force
                    })
                    
                    # Add job to database
                    now = datetime.utcnow()
                    await db.execute(
                        """INSERT INTO so_jobs (id, type, state, asset_id, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (job_id, 'index', 'queued', asset_id, now.isoformat(), now.isoformat())
                    )
                    
                    # Update asset status to processing
                    await db.execute(
                        "UPDATE so_assets SET status = ?, updated_at = ? WHERE id = ?",
                        (AssetStatus.processing.value, now.isoformat(), asset_id)
                    )
                    await db.commit()
                    
                    return {"message": f"Reprocessing job {job_id} queued for asset {asset_id}"}
            except Exception as e:
                logger.warning(f"Failed to queue reprocessing via NATS: {e}")
        
        # Fallback to background task
        background_tasks.add_task(_reprocess_asset, asset_id, row[0], force)
        
        return {"message": f"Asset {asset_id} queued for reprocessing"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to queue asset reprocessing: {str(e)}")


@router.get("/{asset_id}/proxy")
async def get_proxy_info(asset_id: str, db=Depends(get_db)) -> dict:
    """Get proxy file information for an asset"""
    try:
        # Check if asset exists and has proxy
        cursor = await db.execute(
            "SELECT proxy_path FROM so_assets WHERE id = ?",
            (asset_id,)
        )
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail=f"Asset {asset_id} not found")
        
        proxy_path = row[0]
        
        if proxy_path and os.path.exists(proxy_path):
            # Get file stats
            file_stats = os.stat(proxy_path)
            return {
                "has_proxy": True,
                "proxy_path": proxy_path,
                "proxy_url": f"/api/assets/{asset_id}/proxy/download",
                "size_bytes": file_stats.st_size,
                "created_at": datetime.fromtimestamp(file_stats.st_ctime).isoformat()
            }
        else:
            # Check default proxy location
            default_proxy = f"/data/proxies/{asset_id}_proxy.mov"
            if os.path.exists(default_proxy):
                # Update database with proxy path
                await db.execute(
                    "UPDATE so_assets SET proxy_path = ? WHERE id = ?",
                    (default_proxy, asset_id)
                )
                await db.commit()
                
                file_stats = os.stat(default_proxy)
                return {
                    "has_proxy": True,
                    "proxy_path": default_proxy,
                    "proxy_url": f"/api/assets/{asset_id}/proxy/download",
                    "size_bytes": file_stats.st_size,
                    "created_at": datetime.fromtimestamp(file_stats.st_ctime).isoformat()
                }
            else:
                return {
                    "has_proxy": False,
                    "proxy_path": None,
                    "proxy_url": None,
                    "created_at": None
                }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch proxy info: {str(e)}")


@router.post("/{asset_id}/proxy")
async def create_proxy(
    asset_id: str,
    background_tasks: BackgroundTasks,
    force_regenerate: bool = Query(False, description="Force regeneration of existing proxy"),
    db=Depends(get_db)
) -> dict:
    """Create a proxy file for an asset"""
    try:
        # Check if asset exists
        cursor = await db.execute(
            "SELECT abs_path, proxy_path FROM so_assets WHERE id = ?",
            (asset_id,)
        )
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail=f"Asset {asset_id} not found")
        
        # Check if proxy already exists
        if not force_regenerate and row[1]:
            if os.path.exists(row[1]):
                return {"message": f"Proxy already exists for asset {asset_id}. Use force_regenerate=true to regenerate."}
        
        # Queue proxy creation job if NATS is enabled
        if os.getenv("NATS_ENABLE", "true").lower() == "true":
            try:
                from app.api.main import app
                if hasattr(app.state, 'nats'):
                    job_id = str(uuid.uuid4())
                    await app.state.nats.publish_job('proxy', {
                        'id': job_id,
                        'asset_id': asset_id,
                        'filepath': row[0],
                        'output_path': f"/data/proxies/{asset_id}_proxy.mov",
                        'force': force_regenerate
                    })
                    
                    # Add job to database
                    now = datetime.utcnow()
                    await db.execute(
                        """INSERT INTO so_jobs (id, type, state, asset_id, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (job_id, 'proxy', 'queued', asset_id, now.isoformat(), now.isoformat())
                    )
                    await db.commit()
                    
                    return {"message": f"Proxy creation job {job_id} queued for asset {asset_id}"}
            except Exception as e:
                logger.warning(f"Failed to queue proxy creation via NATS: {e}")
        
        # Fallback to background task
        background_tasks.add_task(_create_proxy, asset_id, row[0], force_regenerate)
        
        return {"message": f"Proxy creation queued for asset {asset_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to queue proxy creation: {str(e)}")


@router.post("/{asset_id}/tags/{tag}")
async def add_tag(asset_id: str, tag: str, db=Depends(get_db)) -> dict:
    """Add a tag to an asset"""
    try:
        # Get current tags
        cursor = await db.execute(
            "SELECT tags_json FROM so_assets WHERE id = ?",
            (asset_id,)
        )
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail=f"Asset {asset_id} not found")
        
        # Parse existing tags
        tags = json.loads(row[0]) if row[0] else []
        if not isinstance(tags, list):
            tags = []
        
        # Add new tag if not already present
        if tag not in tags:
            tags.append(tag)
            
            # Update database
            await db.execute(
                "UPDATE so_assets SET tags_json = ?, updated_at = ? WHERE id = ?",
                (json.dumps(tags), datetime.utcnow().isoformat(), asset_id)
            )
            await db.commit()
            
            return {"message": f"Tag '{tag}' added to asset {asset_id}"}
        else:
            return {"message": f"Tag '{tag}' already exists for asset {asset_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add tag: {str(e)}")


@router.delete("/{asset_id}/tags/{tag}")
async def remove_tag(asset_id: str, tag: str, db=Depends(get_db)) -> dict:
    """Remove a tag from an asset"""
    try:
        # Get current tags
        cursor = await db.execute(
            "SELECT tags_json FROM so_assets WHERE id = ?",
            (asset_id,)
        )
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail=f"Asset {asset_id} not found")
        
        # Parse existing tags
        tags = json.loads(row[0]) if row[0] else []
        if not isinstance(tags, list):
            tags = []
        
        # Remove tag if present
        if tag in tags:
            tags.remove(tag)
            
            # Update database
            await db.execute(
                "UPDATE so_assets SET tags_json = ?, updated_at = ? WHERE id = ?",
                (json.dumps(tags), datetime.utcnow().isoformat(), asset_id)
            )
            await db.commit()
            
            return {"message": f"Tag '{tag}' removed from asset {asset_id}"}
        else:
            return {"message": f"Tag '{tag}' not found for asset {asset_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to remove tag: {str(e)}")


# Background task functions
async def _process_asset(asset_id: str, filepath: str):
    """Background task to process asset"""
    try:
        # Check if file exists
        if not os.path.exists(filepath):
            logger.error(f"File not found for asset {asset_id}: {filepath}")
            return
        
        # Get file extension
        ext = os.path.splitext(filepath)[1].lower()
        
        # Process based on file type
        if ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv']:
            # Video file - extract metadata using ffprobe
            import subprocess
            try:
                result = subprocess.run(
                    ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', filepath],
                    capture_output=True, text=True, timeout=30
                )
                if result.returncode == 0:
                    import json
                    probe_data = json.loads(result.stdout)
                    
                    # Extract video stream info
                    video_stream = next((s for s in probe_data.get('streams', []) if s['codec_type'] == 'video'), {})
                    audio_stream = next((s for s in probe_data.get('streams', []) if s['codec_type'] == 'audio'), {})
                    format_info = probe_data.get('format', {})
                    
                    # Update database with metadata
                    from app.api.db.database import get_db
                    db = await get_db()
                    
                    await db.execute(
                        """UPDATE so_assets SET 
                           duration = ?, width = ?, height = ?, fps = ?,
                           video_codec = ?, audio_codec = ?, container = ?,
                           streams_json = ?, status = ?, updated_at = ?
                           WHERE id = ?""",
                        (float(format_info.get('duration', 0)),
                         video_stream.get('width'),
                         video_stream.get('height'),
                         eval(video_stream.get('r_frame_rate', '0/1')) if '/' in video_stream.get('r_frame_rate', '0/1') else 0,
                         video_stream.get('codec_name'),
                         audio_stream.get('codec_name'),
                         format_info.get('format_name'),
                         json.dumps({'video': video_stream, 'audio': audio_stream, 'format': format_info}),
                         AssetStatus.ready.value,
                         datetime.utcnow().isoformat(),
                         asset_id)
                    )
                    await db.commit()
                    logger.info(f"Processed video asset {asset_id}")
            except subprocess.TimeoutExpired:
                logger.error(f"Timeout processing asset {asset_id}")
            except Exception as e:
                logger.error(f"Error processing asset {asset_id}: {e}")
        else:
            # Non-video file - just mark as ready
            from app.api.db.database import get_db
            db = await get_db()
            
            await db.execute(
                "UPDATE so_assets SET status = ?, updated_at = ? WHERE id = ?",
                (AssetStatus.ready.value, datetime.utcnow().isoformat(), asset_id)
            )
            await db.commit()
            logger.info(f"Marked non-video asset {asset_id} as ready")
    except Exception as e:
        logger.error(f"Failed to process asset {asset_id}: {e}")


async def _generate_thumbnails(asset_id: str, filepath: str, force_regenerate: bool):
    """Background task to generate thumbnails"""
    try:
        import subprocess
        
        # Create thumbnail directory
        thumb_dir = f"/data/thumbs/{asset_id}"
        os.makedirs(thumb_dir, exist_ok=True)
        
        # Generate poster frame (middle of video)
        poster_path = f"{thumb_dir}/poster.jpg"
        if force_regenerate or not os.path.exists(poster_path):
            try:
                # Get video duration
                result = subprocess.run(
                    ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', filepath],
                    capture_output=True, text=True, timeout=10
                )
                duration = float(result.stdout.strip()) if result.returncode == 0 else 0
                
                # Extract frame from middle of video
                middle_time = duration / 2 if duration > 0 else 0
                subprocess.run(
                    ['ffmpeg', '-ss', str(middle_time), '-i', filepath, '-vf', 'scale=1920:-1', '-frames:v', '1', '-y', poster_path],
                    capture_output=True, timeout=30
                )
                logger.info(f"Generated poster for asset {asset_id}")
            except Exception as e:
                logger.error(f"Failed to generate poster for asset {asset_id}: {e}")
        
        # Generate sprite sheet (10 frames)
        sprite_path = f"{thumb_dir}/sprite.jpg"
        if force_regenerate or not os.path.exists(sprite_path):
            try:
                # Create sprite sheet with 10 frames
                subprocess.run(
                    ['ffmpeg', '-i', filepath, '-vf', 'fps=1/10,scale=320:-1,tile=10x1', '-frames:v', '1', '-y', sprite_path],
                    capture_output=True, timeout=60
                )
                logger.info(f"Generated sprite sheet for asset {asset_id}")
            except Exception as e:
                logger.error(f"Failed to generate sprite sheet for asset {asset_id}: {e}")
        
        # Generate hover preview video (10 second clip)
        hover_path = f"{thumb_dir}/hover.mp4"
        if force_regenerate or not os.path.exists(hover_path):
            try:
                subprocess.run(
                    ['ffmpeg', '-i', filepath, '-t', '10', '-vf', 'scale=640:-1', '-c:v', 'libx264', '-preset', 'fast', '-an', '-y', hover_path],
                    capture_output=True, timeout=60
                )
                logger.info(f"Generated hover preview for asset {asset_id}")
            except Exception as e:
                logger.error(f"Failed to generate hover preview for asset {asset_id}: {e}")
        
        # Update database
        from app.api.db.database import get_db
        db = await get_db()
        
        # Check if thumbs record exists
        cursor = await db.execute(
            "SELECT id FROM so_thumbs WHERE asset_id = ?",
            (asset_id,)
        )
        row = await cursor.fetchone()
        
        now = datetime.utcnow().isoformat()
        if row:
            # Update existing record
            await db.execute(
                """UPDATE so_thumbs SET poster_path = ?, sprite_path = ?, hover_path = ?, created_at = ?
                   WHERE asset_id = ?""",
                (poster_path, sprite_path, hover_path, now, asset_id)
            )
        else:
            # Create new record
            await db.execute(
                """INSERT INTO so_thumbs (id, asset_id, poster_path, sprite_path, hover_path, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (str(uuid.uuid4()), asset_id, poster_path, sprite_path, hover_path, now)
            )
        
        # Update asset to indicate it has thumbnails
        await db.execute(
            "UPDATE so_assets SET has_thumbnail = 1, updated_at = ? WHERE id = ?",
            (now, asset_id)
        )
        await db.commit()
        
        logger.info(f"Completed thumbnail generation for asset {asset_id}")
    except Exception as e:
        logger.error(f"Failed to generate thumbnails for asset {asset_id}: {e}")


async def _reprocess_asset(asset_id: str, filepath: str, force: bool):
    """Background task to reprocess asset"""
    try:
        # Process the asset (extract metadata)
        await _process_asset(asset_id, filepath)
        
        # Generate thumbnails
        await _generate_thumbnails(asset_id, filepath, force)
        
        # Update asset status
        from app.api.db.database import get_db
        db = await get_db()
        
        await db.execute(
            "UPDATE so_assets SET status = ?, updated_at = ? WHERE id = ?",
            (AssetStatus.ready.value, datetime.utcnow().isoformat(), asset_id)
        )
        await db.commit()
        
        logger.info(f"Completed reprocessing of asset {asset_id}")
    except Exception as e:
        logger.error(f"Failed to reprocess asset {asset_id}: {e}")


async def _create_proxy(asset_id: str, filepath: str, force_regenerate: bool):
    """Background task to create proxy"""
    try:
        import subprocess
        
        # Create proxy directory
        os.makedirs("/data/proxies", exist_ok=True)
        
        # Define proxy path
        proxy_path = f"/data/proxies/{asset_id}_proxy.mov"
        
        # Check if proxy exists
        if not force_regenerate and os.path.exists(proxy_path):
            logger.info(f"Proxy already exists for asset {asset_id}")
            return
        
        # Create DNxHR LB proxy (as per CLAUDE.md specs)
        try:
            subprocess.run(
                ['ffmpeg', '-i', filepath,
                 '-map', '0:v:0', '-c:v', 'dnxhd', '-profile:v', 'dnxhr_lb', '-vf', 'scale=-2:1080',
                 '-map', '0:a?', '-c:a', 'pcm_s16le', '-timecode', '00:00:00:00',
                 '-y', proxy_path],
                capture_output=True, timeout=300
            )
            logger.info(f"Created proxy for asset {asset_id}")
            
            # Update database with proxy path
            from app.api.db.database import get_db
            db = await get_db()
            
            await db.execute(
                "UPDATE so_assets SET proxy_path = ?, has_proxy = 1, updated_at = ? WHERE id = ?",
                (proxy_path, datetime.utcnow().isoformat(), asset_id)
            )
            await db.commit()
            
            logger.info(f"Updated database with proxy info for asset {asset_id}")
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout creating proxy for asset {asset_id}")
        except Exception as e:
            logger.error(f"Failed to create proxy for asset {asset_id}: {e}")
    except Exception as e:
        logger.error(f"Failed to create proxy for asset {asset_id}: {e}")


@router.get("/{asset_id}/detail", response_model=AssetDetailResponse)
async def get_asset_detail(
    asset_id: str,
    db=Depends(get_db)
) -> AssetDetailResponse:
    """Get detailed asset information including thumbnails and recent jobs."""
    
    try:
        # Get asset details
        cursor = await db.execute("""
            SELECT 
                id, name, abs_path, size_bytes, status, 
                duration_sec, container, video_codec, audio_codec,
                width, height, fps, created_at, updated_at, tags_json,
                streams_json
            FROM so_assets
            WHERE id = ?
        """, (asset_id,))
        
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Asset not found")
        
        asset = {
            "id": row[0],
            "name": row[1],
            "abs_path": row[2],
            "size": row[3],
            "status": row[4],
            "duration_sec": row[5],
            "container": row[6],
            "video_codec": row[7],
            "audio_codec": row[8],
            "width": row[9],
            "height": row[10],
            "fps": row[11],
            "created_at": row[12],
            "updated_at": row[13],
            "tags": json.loads(row[14]) if row[14] else [],
            "streams": json.loads(row[15]) if row[15] else []
        }
        
        # Get thumbnails
        thumbs = {
            "poster": f"/api/assets/{asset_id}/poster.jpg",
            "sprite": f"/api/assets/{asset_id}/sprite.jpg",
            "hover_mp4": f"/api/assets/{asset_id}/hover.mp4"
        }
        
        # Get recent jobs for this asset
        cursor = await db.execute("""
            SELECT id, type, state, started_at, ended_at,
                   json_extract(metadata, '$.duration_sec') as duration_sec
            FROM so_jobs
            WHERE json_extract(metadata, '$.asset_id') = ?
            ORDER BY created_at DESC
            LIMIT 10
        """, (asset_id,))
        
        jobs = []
        async for job_row in cursor:
            job = {
                "id": job_row[0],
                "type": job_row[1],
                "state": job_row[2],
                "started_at": job_row[3],
                "ended_at": job_row[4],
                "duration_sec": job_row[5]
            }
            jobs.append(job)
        
        return AssetDetailResponse(
            asset=asset,
            thumbs=thumbs,
            jobs_recent=jobs
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get asset details: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get asset details: {str(e)}")


async def create_job(db, job_type: str, asset_id: str, metadata: dict) -> str:
    """Helper function to create a job in the database."""
    job_id = str(uuid.uuid4())
    await db.execute("""
        INSERT INTO so_jobs (id, type, asset_id, payload_json, state, created_at, updated_at)
        VALUES (?, ?, ?, ?, 'pending', datetime('now'), datetime('now'))
    """, (job_id, job_type, asset_id, json.dumps(metadata)))
    await db.commit()
    return job_id


@router.post("/{asset_id}/actions", response_model=ActionResponse)
async def execute_asset_action(
    asset_id: str,
    action: AssetAction,
    db=Depends(get_db)
) -> ActionResponse:
    """Execute an action on a single asset."""
    
    try:
        # Verify asset exists
        cursor = await db.execute("SELECT abs_path, status FROM so_assets WHERE id = ?", (asset_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Asset not found")
        
        asset_path, asset_status = row
        
        # Check if asset is missing
        if asset_status == "missing" and action.action != "reindex":
            raise HTTPException(status_code=400, detail="Asset is missing on disk. Please reindex first.")
        
        # Create job based on action
        job_ids = []
        
        if action.action == "remux":
            metadata = {
                "asset_id": asset_id,
                "input_path": asset_path,
                "container": action.params.get("container", "mov"),
                "faststart": action.params.get("faststart", True)
            }
            job_id = await create_job(db, "ffmpeg_remux", asset_id, metadata)
            job_ids.append(job_id)
            
        elif action.action == "proxy":
            metadata = {
                "asset_id": asset_id,
                "input_path": asset_path,
                "resolution": action.params.get("resolution", "1080p")
            }
            job_id = await create_job(db, "proxy_create", asset_id, metadata)
            job_ids.append(job_id)
            
        elif action.action == "thumbnails":
            metadata = {
                "asset_id": asset_id,
                "input_path": asset_path
            }
            job_id = await create_job(db, "thumbs_generate", asset_id, metadata)
            job_ids.append(job_id)
            
        elif action.action == "move":
            metadata = {
                "asset_id": asset_id,
                "source_path": asset_path,
                "dest_path": action.params.get("dest")
            }
            job_id = await create_job(db, "file_move", asset_id, metadata)
            job_ids.append(job_id)
            
        elif action.action == "archive":
            metadata = {
                "asset_id": asset_id,
                "source_path": asset_path,
                "policy": action.params.get("policy", "default")
            }
            job_id = await create_job(db, "asset_archive", asset_id, metadata)
            job_ids.append(job_id)
            
        elif action.action == "delete":
            metadata = {
                "asset_id": asset_id,
                "path": asset_path,
                "to_trash": action.params.get("to_trash", True)
            }
            job_id = await create_job(db, "asset_delete", asset_id, metadata)
            job_ids.append(job_id)
            
        elif action.action == "reindex":
            metadata = {
                "asset_id": asset_id,
                "path": asset_path
            }
            job_id = await create_job(db, "asset_reindex", asset_id, metadata)
            job_ids.append(job_id)
            
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {action.action}")
        
        return ActionResponse(ok=True, job_ids=job_ids)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to execute action: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to execute action: {str(e)}")


@router.post("/bulk", response_model=ActionResponse)
async def execute_bulk_action(
    bulk_action: BulkAssetAction,
    db=Depends(get_db)
) -> ActionResponse:
    """Execute an action on multiple assets."""
    
    job_ids = []
    
    try:
        # Process each asset
        for asset_id in bulk_action.ids:
            # Verify asset exists
            cursor = await db.execute("SELECT abs_path, status FROM so_assets WHERE id = ?", (asset_id,))
            row = await cursor.fetchone()
            if not row:
                continue  # Skip missing assets
            
            asset_path, asset_status = row
            
            # Skip missing assets for non-reindex actions
            if asset_status == "missing" and bulk_action.action != "reindex":
                continue
            
            # Create job for this asset
            if bulk_action.action == "archive":
                metadata = {
                    "asset_id": asset_id,
                    "source_path": asset_path,
                    "policy": bulk_action.params.get("policy", "default")
                }
                job_id = await create_job(db, "asset_archive", asset_id, metadata)
                job_ids.append(job_id)
            
            elif bulk_action.action == "delete":
                metadata = {
                    "asset_id": asset_id,
                    "path": asset_path,
                    "to_trash": bulk_action.params.get("to_trash", True)
                }
                job_id = await create_job(db, "asset_delete", asset_id, metadata)
                job_ids.append(job_id)
            
            elif bulk_action.action == "thumbnails":
                metadata = {
                    "asset_id": asset_id,
                    "input_path": asset_path
                }
                job_id = await create_job(db, "thumbs_generate", asset_id, metadata)
                job_ids.append(job_id)
            
            elif bulk_action.action == "proxy":
                metadata = {
                    "asset_id": asset_id,
                    "input_path": asset_path,
                    "resolution": bulk_action.params.get("resolution", "1080p")
                }
                job_id = await create_job(db, "proxy_create", asset_id, metadata)
                job_ids.append(job_id)
            
            elif bulk_action.action == "remux":
                metadata = {
                    "asset_id": asset_id,
                    "input_path": asset_path,
                    "container": bulk_action.params.get("container", "mov"),
                    "faststart": bulk_action.params.get("faststart", True)
                }
                job_id = await create_job(db, "ffmpeg_remux", asset_id, metadata)
                job_ids.append(job_id)
        
        return ActionResponse(
            ok=True, 
            job_ids=job_ids,
            message=f"Queued {len(job_ids)} jobs for {len(bulk_action.ids)} assets"
        )
        
    except Exception as e:
        logger.error(f"Failed to execute bulk action: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to execute bulk action: {str(e)}")


@router.get("/{asset_id}/download")
async def download_asset(
    asset_id: str,
    db=Depends(get_db)
):
    """Download an asset file."""
    
    try:
        # TODO: Check if downloads are allowed from settings
        
        # Get asset path
        cursor = await db.execute("SELECT abs_path, name FROM so_assets WHERE id = ?", (asset_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Asset not found")
        
        file_path, file_name = row
        
        # Check if file exists
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found on disk")
        
        # Return file response
        return FileResponse(
            path=file_path,
            filename=file_name,
            media_type="application/octet-stream"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download asset: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to download asset: {str(e)}")


@router.get("/{asset_id}/path", response_model=PathResponse)
async def get_asset_path(
    asset_id: str,
    db=Depends(get_db)
) -> PathResponse:
    """Get asset path information including host-mapped path."""
    
    try:
        # Get asset path
        cursor = await db.execute("SELECT abs_path FROM so_assets WHERE id = ?", (asset_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Asset not found")
        
        container_path = row[0]
        
        # Get drive mapping to determine host path
        # For now, we'll provide a simple mapping
        host_hint = None
        
        # Simple mapping for common mount points
        drive_mappings = {
            "/mnt/drive_a": "A:\\Recordings",
            "/mnt/drive_b": "B:\\",
            "/mnt/drive_c": "C:\\",
            "/mnt/drive_d": "D:\\",
            "/mnt/drive_e": "E:\\",
            "/mnt/drive_f": "F:\\Editing"
        }
        
        for mount_point, host_path in drive_mappings.items():
            if container_path.startswith(mount_point):
                relative_path = container_path[len(mount_point):]
                host_hint = host_path + relative_path.replace('/', '\\')
                break
        
        return PathResponse(
            container_path=container_path,
            host_hint=host_hint,
            can_open_on_host=False  # Always false for now
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get asset path: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get asset path: {str(e)}")


@router.get("/{asset_id}/poster.jpg")
async def get_asset_poster(
    asset_id: str,
    db=Depends(get_db)
):
    """Get asset poster thumbnail."""
    thumb_path = f"/data/thumbs/{asset_id}/poster.jpg"
    if os.path.exists(thumb_path):
        return FileResponse(thumb_path, media_type="image/jpeg")
    else:
        # Return placeholder
        return Response(content=b"", media_type="image/jpeg", status_code=404)


@router.get("/{asset_id}/sprite.jpg")
async def get_asset_sprite(
    asset_id: str,
    db=Depends(get_db)
):
    """Get asset sprite sheet."""
    sprite_path = f"/data/thumbs/{asset_id}/sprite.jpg"
    if os.path.exists(sprite_path):
        return FileResponse(sprite_path, media_type="image/jpeg")
    else:
        return Response(content=b"", media_type="image/jpeg", status_code=404)


@router.get("/{asset_id}/hover.mp4")
async def get_asset_hover_video(
    asset_id: str,
    db=Depends(get_db)
):
    """Get asset hover preview video."""
    hover_path = f"/data/thumbs/{asset_id}/hover.mp4"
    if os.path.exists(hover_path):
        return FileResponse(hover_path, media_type="video/mp4")
    else:
        return Response(content=b"", media_type="video/mp4", status_code=404)


