from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from fastapi.responses import HTMLResponse
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid
import json
import logging

from app.api.schemas.overlays import (
    OverlayResponse, OverlayCreate, OverlayUpdate, OverlayListResponse,
    OverlaySearchQuery, OverlayPreview, OverlayManifest, OverlayStatus, OverlayType
)
from app.api.db.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=OverlayListResponse)
async def list_overlays(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    overlay_type: Optional[OverlayType] = Query(None, description="Filter by overlay type"),
    status: Optional[OverlayStatus] = Query(None, description="Filter by status"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    scene: Optional[str] = Query(None, description="Filter by scene"),
    tags: Optional[List[str]] = Query(None, description="Filter by tags"),
    search: Optional[str] = Query(None, description="Search query"),
    db=Depends(get_db)
) -> OverlayListResponse:
    """List overlays with filtering and pagination"""
    try:
        query = "SELECT * FROM so_overlays WHERE 1=1"
        params = []
        
        if overlay_type:
            query += " AND json_extract(manifest_json, '$.type') = ?"
            params.append(overlay_type.value)
        if enabled is not None:
            query += " AND enabled = ?"
            params.append(1 if enabled else 0)
        if search:
            query += " AND (name LIKE ? OR json_extract(manifest_json, '$.description') LIKE ?)"
            search_term = f"%{search}%"
            params.extend([search_term, search_term])
        
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
        
        overlays = []
        for row in rows:
            manifest = json.loads(row[2]) if row[2] else {}
            
            overlays.append(OverlayResponse(
                id=row[0],
                name=row[1],
                overlay_type=OverlayType(manifest.get('type', 'text')),
                description=manifest.get('description', ''),
                position=manifest.get('position', {"x": 0, "y": 0, "z_index": 1}),
                style=manifest.get('style', {}),
                content=manifest.get('content', {}),
                schedule=manifest.get('schedule'),
                enabled=row[3] == 1,
                status=OverlayStatus(row[4]) if row[4] else OverlayStatus.inactive,
                tags=json.loads(manifest.get('tags', '[]')) if manifest.get('tags') else [],
                scene_filter=manifest.get('scene_filter'),
                views=manifest.get('views', 0),
                last_shown=datetime.fromisoformat(manifest['last_shown']) if manifest.get('last_shown') else None,
                created_at=datetime.fromisoformat(row[5]),
                updated_at=datetime.fromisoformat(row[6])
            ))
        
        return OverlayListResponse(
            overlays=overlays,
            total=total,
            page=page,
            per_page=per_page
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch overlays: {str(e)}")


@router.post("/", response_model=OverlayResponse)
async def create_overlay(overlay: OverlayCreate, db=Depends(get_db)) -> OverlayResponse:
    """Create a new overlay"""
    try:
        overlay_id = str(uuid.uuid4())
        
        # Validate overlay configuration
        if not overlay.position:
            overlay.position = {"x": 0, "y": 0, "z_index": 1}
        if not overlay.style:
            overlay.style = {}
        if not overlay.content:
            raise HTTPException(status_code=400, detail="Overlay content is required")
        
        # Build manifest
        manifest = {
            "type": overlay.overlay_type.value,
            "description": overlay.description,
            "position": overlay.position,
            "style": overlay.style,
            "content": overlay.content,
            "schedule": overlay.schedule,
            "tags": json.dumps(overlay.tags or []),
            "scene_filter": overlay.scene_filter,
            "views": 0,
            "last_shown": None
        }
        
        # Insert into database
        now = datetime.utcnow()
        status = OverlayStatus.active.value if overlay.enabled else OverlayStatus.inactive.value
        
        await db.execute(
            """INSERT INTO so_overlays (id, name, manifest_json, enabled, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (overlay_id, overlay.name, json.dumps(manifest), 
             1 if overlay.enabled else 0, status, now.isoformat(), now.isoformat())
        )
        await db.commit()
        
        new_overlay = OverlayResponse(
            id=overlay_id,
            name=overlay.name,
            overlay_type=overlay.overlay_type,
            description=overlay.description,
            position=overlay.position,
            style=overlay.style,
            content=overlay.content,
            schedule=overlay.schedule,
            enabled=overlay.enabled,
            status=OverlayStatus(status),
            tags=overlay.tags or [],
            scene_filter=overlay.scene_filter,
            created_at=now,
            updated_at=now
        )
        
        return new_overlay
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create overlay: {str(e)}")


@router.get("/{overlay_id}", response_model=OverlayResponse)
async def get_overlay(overlay_id: str, db=Depends(get_db)) -> OverlayResponse:
    """Get a specific overlay by ID"""
    try:
        # Get overlay from database
        cursor = await db.execute(
            "SELECT * FROM so_overlays WHERE id = ?",
            (overlay_id,)
        )
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail=f"Overlay {overlay_id} not found")
        
        manifest = json.loads(row[2]) if row[2] else {}
        
        return OverlayResponse(
            id=row[0],
            name=row[1],
            overlay_type=OverlayType(manifest.get('type', 'text')),
            description=manifest.get('description', ''),
            position=manifest.get('position', {"x": 0, "y": 0, "z_index": 1}),
            style=manifest.get('style', {}),
            content=manifest.get('content', {}),
            schedule=manifest.get('schedule'),
            enabled=row[3] == 1,
            status=OverlayStatus(row[4]) if row[4] else OverlayStatus.inactive,
            tags=json.loads(manifest.get('tags', '[]')) if manifest.get('tags') else [],
            scene_filter=manifest.get('scene_filter'),
            views=manifest.get('views', 0),
            last_shown=datetime.fromisoformat(manifest['last_shown']) if manifest.get('last_shown') else None,
            created_at=datetime.fromisoformat(row[5]),
            updated_at=datetime.fromisoformat(row[6])
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch overlay: {str(e)}")


@router.put("/{overlay_id}", response_model=OverlayResponse)
async def update_overlay(
    overlay_id: str,
    overlay_update: OverlayUpdate,
    db=Depends(get_db)
) -> OverlayResponse:
    """Update an overlay"""
    try:
        # Get existing overlay
        cursor = await db.execute(
            "SELECT * FROM so_overlays WHERE id = ?",
            (overlay_id,)
        )
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail=f"Overlay {overlay_id} not found")
        
        # Parse existing manifest
        existing_manifest = json.loads(row[2]) if row[2] else {}
        
        # Update manifest fields
        if overlay_update.name is not None:
            name = overlay_update.name
        else:
            name = row[1]
            
        if overlay_update.description is not None:
            existing_manifest['description'] = overlay_update.description
        if overlay_update.position is not None:
            existing_manifest['position'] = overlay_update.position
        if overlay_update.style is not None:
            existing_manifest['style'] = overlay_update.style
        if overlay_update.content is not None:
            existing_manifest['content'] = overlay_update.content
        if overlay_update.schedule is not None:
            existing_manifest['schedule'] = overlay_update.schedule
        if overlay_update.tags is not None:
            existing_manifest['tags'] = json.dumps(overlay_update.tags)
        if overlay_update.scene_filter is not None:
            existing_manifest['scene_filter'] = overlay_update.scene_filter
        
        # Update enabled and status
        if overlay_update.enabled is not None:
            enabled = overlay_update.enabled
            status = OverlayStatus.active.value if enabled else OverlayStatus.inactive.value
        else:
            enabled = row[3] == 1
            status = row[4]
        
        # Update database
        now = datetime.utcnow()
        await db.execute(
            """UPDATE so_overlays 
               SET name = ?, manifest_json = ?, enabled = ?, status = ?, updated_at = ?
               WHERE id = ?""",
            (name, json.dumps(existing_manifest), 1 if enabled else 0, 
             status, now.isoformat(), overlay_id)
        )
        await db.commit()
        
        # Return updated overlay
        return OverlayResponse(
            id=overlay_id,
            name=name,
            overlay_type=OverlayType(existing_manifest.get('type', 'text')),
            description=existing_manifest.get('description', ''),
            position=existing_manifest.get('position', {"x": 0, "y": 0, "z_index": 1}),
            style=existing_manifest.get('style', {}),
            content=existing_manifest.get('content', {}),
            schedule=existing_manifest.get('schedule'),
            enabled=enabled,
            status=OverlayStatus(status),
            tags=json.loads(existing_manifest.get('tags', '[]')) if existing_manifest.get('tags') else [],
            scene_filter=existing_manifest.get('scene_filter'),
            created_at=datetime.fromisoformat(row[5]),
            updated_at=now
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update overlay: {str(e)}")


@router.delete("/{overlay_id}")
async def delete_overlay(overlay_id: str, db=Depends(get_db)) -> Dict[str, str]:
    """Delete an overlay"""
    try:
        # Check if overlay exists
        cursor = await db.execute(
            "SELECT id FROM so_overlays WHERE id = ?",
            (overlay_id,)
        )
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail=f"Overlay {overlay_id} not found")
        
        # Delete from database
        await db.execute("DELETE FROM so_overlays WHERE id = ?", (overlay_id,))
        await db.commit()
        
        return {"message": f"Overlay {overlay_id} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete overlay: {str(e)}")


@router.post("/{overlay_id}/enable")
async def enable_overlay(overlay_id: str, db=Depends(get_db)) -> Dict[str, str]:
    """Enable an overlay"""
    try:
        # Check if overlay exists
        cursor = await db.execute(
            "SELECT id FROM so_overlays WHERE id = ?",
            (overlay_id,)
        )
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail=f"Overlay {overlay_id} not found")
        
        # Enable overlay
        await db.execute(
            "UPDATE so_overlays SET enabled = 1, status = ?, updated_at = ? WHERE id = ?",
            (OverlayStatus.active.value, datetime.utcnow().isoformat(), overlay_id)
        )
        await db.commit()
        
        return {"message": f"Overlay {overlay_id} enabled"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to enable overlay: {str(e)}")


@router.post("/{overlay_id}/disable")
async def disable_overlay(overlay_id: str, db=Depends(get_db)) -> Dict[str, str]:
    """Disable an overlay"""
    try:
        # Check if overlay exists
        cursor = await db.execute(
            "SELECT id FROM so_overlays WHERE id = ?",
            (overlay_id,)
        )
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail=f"Overlay {overlay_id} not found")
        
        # Disable overlay
        await db.execute(
            "UPDATE so_overlays SET enabled = 0, status = ?, updated_at = ? WHERE id = ?",
            (OverlayStatus.inactive.value, datetime.utcnow().isoformat(), overlay_id)
        )
        await db.commit()
        
        return {"message": f"Overlay {overlay_id} disabled"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to disable overlay: {str(e)}")


@router.get("/{overlay_id}/preview", response_model=OverlayPreview)
async def preview_overlay(overlay_id: str, db=Depends(get_db)) -> OverlayPreview:
    """Generate a preview of the overlay"""
    try:
        # Get overlay from database
        cursor = await db.execute(
            "SELECT name, manifest_json FROM so_overlays WHERE id = ?",
            (overlay_id,)
        )
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail=f"Overlay {overlay_id} not found")
        
        manifest = json.loads(row[1]) if row[1] else {}
        position = manifest.get('position', {"x": 0, "y": 0, "z_index": 1})
        style = manifest.get('style', {})
        content = manifest.get('content', {})
        overlay_type = manifest.get('type', 'text')
        
        # Generate CSS from style
        css_rules = []
        if style.get('background_color'):
            css_rules.append(f"background: {style['background_color']}")
        if style.get('text_color'):
            css_rules.append(f"color: {style['text_color']}")
        if style.get('font_family'):
            css_rules.append(f"font-family: {style['font_family']}")
        if style.get('font_size'):
            css_rules.append(f"font-size: {style['font_size']}")
        if style.get('opacity'):
            css_rules.append(f"opacity: {style['opacity']}")
        if style.get('border_radius'):
            css_rules.append(f"border-radius: {style['border_radius']}")
        if style.get('padding'):
            css_rules.append(f"padding: {style['padding']}")
            
        css_string = "; ".join(css_rules)
        
        # Generate HTML based on overlay type
        if overlay_type == 'text':
            html_content = content.get('text', 'Preview Text')
        elif overlay_type == 'image':
            image_url = content.get('image_url', '')
            html_content = f'<img src="{image_url}" alt="Overlay Image" style="max-width: 100%; height: auto;">'
        elif overlay_type == 'countdown':
            html_content = content.get('text', 'Starting in') + ' <span id="countdown">00:05:00</span>'
        else:
            html_content = 'Overlay Preview'
        
        html = f"""
        <div class="overlay" style="position: absolute; 
                                  left: {position.get('x', 0)}px; 
                                  top: {position.get('y', 0)}px;
                                  z-index: {position.get('z_index', 1)};
                                  {css_string}">
            {html_content}
        </div>
        """
        
        css = """
        .overlay {
            font-family: Arial, sans-serif;
            font-weight: bold;
            text-align: center;
        }
        """
        
        return OverlayPreview(html=html, css=css)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate overlay preview: {str(e)}")


@router.post("/{overlay_id}/show")
async def show_overlay(
    overlay_id: str,
    duration: Optional[int] = Query(None, description="Show duration in seconds"),
    scene: Optional[str] = Query(None, description="Show only on specific scene"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db=Depends(get_db)
) -> Dict[str, str]:
    """Manually show an overlay"""
    try:
        # Check if overlay exists
        cursor = await db.execute(
            "SELECT id FROM so_overlays WHERE id = ?",
            (overlay_id,)
        )
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail=f"Overlay {overlay_id} not found")
        
        # Queue overlay show command
        background_tasks.add_task(_show_overlay, overlay_id, duration, scene)
        
        return {"message": f"Overlay {overlay_id} show command queued"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to show overlay: {str(e)}")


@router.post("/{overlay_id}/hide")
async def hide_overlay(overlay_id: str, db=Depends(get_db)) -> Dict[str, str]:
    """Manually hide an overlay"""
    try:
        # Check if overlay exists and update its visibility status
        cursor = await db.execute(
            "SELECT manifest_json FROM so_overlays WHERE id = ?",
            (overlay_id,)
        )
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail=f"Overlay {overlay_id} not found")
        
        # Update manifest to mark as hidden
        manifest = json.loads(row[0]) if row[0] else {}
        manifest['visible'] = False
        manifest['last_hidden'] = datetime.utcnow().isoformat()
        
        await db.execute(
            "UPDATE so_overlays SET manifest_json = ?, updated_at = ? WHERE id = ?",
            (json.dumps(manifest), datetime.utcnow().isoformat(), overlay_id)
        )
        await db.commit()
        
        return {"message": f"Overlay {overlay_id} hidden"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to hide overlay: {str(e)}")


@router.post("/search", response_model=OverlayListResponse)
async def search_overlays(
    query: OverlaySearchQuery,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    db=Depends(get_db)
) -> OverlayListResponse:
    """Advanced overlay search with multiple filters"""
    try:
        # Build search query
        base_query = "SELECT * FROM so_overlays WHERE 1=1"
        params = []
        
        if query.query:
            base_query += " AND (name LIKE ? OR json_extract(manifest_json, '$.description') LIKE ?)"
            search_term = f"%{query.query}%"
            params.extend([search_term, search_term])
        
        if query.overlay_type:
            base_query += " AND json_extract(manifest_json, '$.type') = ?"
            params.append(query.overlay_type.value)
        
        if query.enabled is not None:
            base_query += " AND enabled = ?"
            params.append(1 if query.enabled else 0)
        
        if query.tags:
            for tag in query.tags:
                base_query += " AND json_extract(manifest_json, '$.tags') LIKE ?"
                params.append(f'%"{tag}"%')
        
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
        
        overlays = []
        for row in rows:
            manifest = json.loads(row[2]) if row[2] else {}
            
            overlays.append(OverlayResponse(
                id=row[0],
                name=row[1],
                overlay_type=OverlayType(manifest.get('type', 'text')),
                description=manifest.get('description', ''),
                position=manifest.get('position', {"x": 0, "y": 0, "z_index": 1}),
                style=manifest.get('style', {}),
                content=manifest.get('content', {}),
                schedule=manifest.get('schedule'),
                enabled=row[3] == 1,
                status=OverlayStatus(row[4]) if row[4] else OverlayStatus.inactive,
                tags=json.loads(manifest.get('tags', '[]')) if manifest.get('tags') else [],
                scene_filter=manifest.get('scene_filter'),
                views=manifest.get('views', 0),
                last_shown=datetime.fromisoformat(manifest['last_shown']) if manifest.get('last_shown') else None,
                created_at=datetime.fromisoformat(row[5]),
                updated_at=datetime.fromisoformat(row[6])
            ))
        
        return OverlayListResponse(
            overlays=overlays,
            total=total,
            page=page,
            per_page=per_page
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Overlay search failed: {str(e)}")


@router.get("/manifest/{scene}", response_model=OverlayManifest)
async def get_overlay_manifest(
    scene: Optional[str] = None,
    db=Depends(get_db)
) -> OverlayManifest:
    """Get overlay manifest for browser source"""
    try:
        # Get active overlays for the scene
        if scene:
            query = """SELECT * FROM so_overlays 
                      WHERE enabled = 1 
                      AND (json_extract(manifest_json, '$.scene_filter') IS NULL 
                           OR json_extract(manifest_json, '$.scene_filter') LIKE ?)"""
            params = [f'%"{scene}"%']
        else:
            query = "SELECT * FROM so_overlays WHERE enabled = 1"
            params = []
        
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        
        active_overlays = []
        for row in rows:
            manifest = json.loads(row[2]) if row[2] else {}
            
            active_overlays.append({
                "id": row[0],
                "name": row[1],
                "type": manifest.get('type', 'text'),
                "position": manifest.get('position', {"x": 0, "y": 0, "z_index": 1}),
                "style": manifest.get('style', {}),
                "content": manifest.get('content', {}),
                "visible": manifest.get('visible', True)
            })
        
        return OverlayManifest(
            overlays=active_overlays,
            scene=scene,
            last_updated=datetime.utcnow(),
            websocket_url="ws://localhost:7769/overlay/ws"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate overlay manifest: {str(e)}")


@router.get("/render/{overlay_id}", response_class=HTMLResponse)
async def render_overlay(overlay_id: str, db=Depends(get_db)) -> str:
    """Render overlay as HTML for browser source"""
    try:
        # Get overlay from database
        cursor = await db.execute(
            "SELECT name, manifest_json FROM so_overlays WHERE id = ?",
            (overlay_id,)
        )
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail=f"Overlay {overlay_id} not found")
        
        name = row[0]
        manifest = json.loads(row[1]) if row[1] else {}
        position = manifest.get('position', {"x": 0, "y": 0, "z_index": 1})
        style = manifest.get('style', {})
        content = manifest.get('content', {})
        overlay_type = manifest.get('type', 'text')
        
        # Generate inline styles
        styles = []
        styles.append(f"position: absolute")
        styles.append(f"left: {position.get('x', 0)}px")
        styles.append(f"top: {position.get('y', 0)}px")
        styles.append(f"z-index: {position.get('z_index', 1)}")
        
        if style.get('background_color'):
            styles.append(f"background: {style['background_color']}")
        if style.get('text_color'):
            styles.append(f"color: {style['text_color']}")
        if style.get('font_family'):
            styles.append(f"font-family: {style['font_family']}")
        if style.get('font_size'):
            styles.append(f"font-size: {style['font_size']}")
        if style.get('padding'):
            styles.append(f"padding: {style['padding']}")
        if style.get('border_radius'):
            styles.append(f"border-radius: {style['border_radius']}")
        
        style_string = "; ".join(styles)
        
        # Generate content based on type
        if overlay_type == 'text':
            overlay_content = content.get('text', name)
        elif overlay_type == 'image':
            image_url = content.get('image_url', '')
            overlay_content = f'<img src="{image_url}" alt="{name}" style="max-width: 100%; height: auto;">'
        elif overlay_type == 'countdown':
            overlay_content = f'{content.get("text", "Starting in")} <span id="countdown">00:00:00</span>'
        else:
            overlay_content = name
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>StreamOps Overlay</title>
            <style>
                body {{ margin: 0; padding: 0; background: transparent; }}
                .overlay {{
                    {style_string}
                }}
            </style>
        </head>
        <body>
            <div id="overlay-{overlay_id}" class="overlay">
                {overlay_content}
            </div>
            <script>
                // WebSocket connection for real-time updates
                const ws = new WebSocket('ws://localhost:7769/overlay/ws');
                ws.onmessage = function(event) {{
                    const data = JSON.parse(event.data);
                    if (data.overlay_id === '{overlay_id}') {{
                        // Update overlay content
                    }}
                }};
            </script>
        </body>
        </html>
        """
        
        return html
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to render overlay: {str(e)}")


@router.get("/templates/types")
async def get_overlay_types() -> Dict[str, Any]:
    """Get available overlay types and their configurations"""
    try:
        return {
            "text": {
                "description": "Simple text overlay",
                "content_fields": ["text"],
                "supports_variables": True
            },
            "image": {
                "description": "Static image overlay",
                "content_fields": ["image_url"],
                "supports_variables": False
            },
            "countdown": {
                "description": "Countdown timer overlay",
                "content_fields": ["text", "target_time"],
                "supports_variables": True
            },
            "progress_bar": {
                "description": "Progress bar overlay",
                "content_fields": ["progress_value", "max_value", "label"],
                "supports_variables": True
            },
            "recent_follower": {
                "description": "Recent follower display",
                "content_fields": ["template"],
                "supports_variables": True
            },
            "scene_info": {
                "description": "Current scene information",
                "content_fields": ["template"],
                "supports_variables": True
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch overlay types: {str(e)}")


@router.post("/bulk/enable")
async def bulk_enable_overlays(
    overlay_ids: List[str],
    db=Depends(get_db)
) -> Dict[str, Any]:
    """Enable multiple overlays"""
    try:
        enabled = 0
        failed = 0
        
        for overlay_id in overlay_ids:
            try:
                await db.execute(
                    "UPDATE so_overlays SET enabled = 1, status = ?, updated_at = ? WHERE id = ?",
                    (OverlayStatus.active.value, datetime.utcnow().isoformat(), overlay_id)
                )
                enabled += 1
            except:
                failed += 1
        
        await db.commit()
        
        return {
            "enabled": enabled,
            "failed": failed,
            "overlay_ids": overlay_ids
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to bulk enable overlays: {str(e)}")


@router.post("/bulk/disable")
async def bulk_disable_overlays(
    overlay_ids: List[str],
    db=Depends(get_db)
) -> Dict[str, Any]:
    """Disable multiple overlays"""
    try:
        disabled = 0
        failed = 0
        
        for overlay_id in overlay_ids:
            try:
                await db.execute(
                    "UPDATE so_overlays SET enabled = 0, status = ?, updated_at = ? WHERE id = ?",
                    (OverlayStatus.inactive.value, datetime.utcnow().isoformat(), overlay_id)
                )
                disabled += 1
            except:
                failed += 1
        
        await db.commit()
        
        return {
            "disabled": disabled,
            "failed": failed,
            "overlay_ids": overlay_ids
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to bulk disable overlays: {str(e)}")


# Background task functions
async def _show_overlay(overlay_id: str, duration: Optional[int], scene: Optional[str]):
    """Background task to show overlay"""
    try:
        from app.api.db.database import get_db
        db = await get_db()
        
        # Get overlay manifest
        cursor = await db.execute(
            "SELECT manifest_json FROM so_overlays WHERE id = ?",
            (overlay_id,)
        )
        row = await cursor.fetchone()
        
        if row:
            manifest = json.loads(row[0]) if row[0] else {}
            manifest['visible'] = True
            manifest['last_shown'] = datetime.utcnow().isoformat()
            manifest['views'] = manifest.get('views', 0) + 1
            
            # If scene is specified, add to scene filter
            if scene and manifest.get('scene_filter'):
                scene_filter = manifest['scene_filter']
                if isinstance(scene_filter, list) and scene not in scene_filter:
                    scene_filter.append(scene)
            
            await db.execute(
                "UPDATE so_overlays SET manifest_json = ?, updated_at = ? WHERE id = ?",
                (json.dumps(manifest), datetime.utcnow().isoformat(), overlay_id)
            )
            await db.commit()
            
            logger.info(f"Showing overlay {overlay_id} for {duration} seconds on scene {scene}")
            
            # If duration is specified, hide after duration
            if duration:
                import asyncio
                await asyncio.sleep(duration)
                
                # Hide the overlay
                manifest['visible'] = False
                manifest['last_hidden'] = datetime.utcnow().isoformat()
                
                await db.execute(
                    "UPDATE so_overlays SET manifest_json = ?, updated_at = ? WHERE id = ?",
                    (json.dumps(manifest), datetime.utcnow().isoformat(), overlay_id)
                )
                await db.commit()
                
                logger.info(f"Auto-hiding overlay {overlay_id} after {duration} seconds")
    except Exception as e:
        logger.error(f"Failed to show overlay {overlay_id}: {e}")