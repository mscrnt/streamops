from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from contextlib import asynccontextmanager
import os
import logging
from pathlib import Path

from app.api.routers import health, config, assets, jobs, rules, overlays, reports, drives, system, wizard, websocket, settings, guardrails, filesystem, obs, events
from app.api.db.database import init_db, close_db, get_db
from app.api.services.nats_service import NATSService
from app.api.services.config_service import ConfigService
from app.api.services.gpu_service import gpu_service
from app.overlay.server import overlay_handler, overlay_manager, sponsor_rotation
from app.overlay.renderer import overlay_renderer

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Set uvicorn access logger to WARNING to reduce noise
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting StreamOps API...")
    
    # Initialize configuration
    logger.info("Initializing configuration...")
    config_service = ConfigService()
    await config_service.load_config()
    app.state.config = config_service
    logger.info("Configuration initialized")
    
    # Initialize database
    logger.info("Initializing database...")
    await init_db()
    logger.info("Database initialized")
    
    # Initialize GPU service
    logger.info("Detecting GPU capabilities...")
    gpu_info = await gpu_service.get_gpu_info()
    app.state.gpu = gpu_service
    if gpu_info["available"]:
        vendor = gpu_info.get('vendor', 'unknown')
        name = gpu_info.get('name', 'Unknown GPU')
        hw_encode = gpu_info.get('hw_encode_available', False)
        hw_decode = gpu_info.get('hw_decode_available', False)
        logger.info(f"GPU detected: {name} ({vendor}) - HW Encode: {hw_encode}, HW Decode: {hw_decode}")
    else:
        logger.info("No GPU detected, using CPU for all processing")
    logger.info("GPU service initialized")
    
    # Initialize NATS
    logger.info("Initializing NATS...")
    nats_service = NATSService()
    await nats_service.connect()
    app.state.nats = nats_service
    logger.info("NATS initialized")
    
    # Seed OBS connections from environment if needed
    logger.info("Checking for OBS environment configuration...")
    from app.api.services.obs_seeder import seed_obs_connections_from_env
    db = await get_db()
    await seed_obs_connections_from_env(db)
    
    # Initialize OBS Manager for multi-instance support
    logger.info("Initializing OBS Manager...")
    from app.api.services.obs_manager import get_obs_manager
    obs_manager = get_obs_manager()
    obs_manager.nats = nats_service if 'nats_service' in locals() else None
    await obs_manager.connect_all_autostart()
    app.state.obs_manager = obs_manager
    logger.info(f"OBS Manager initialized with {len(obs_manager.clients)} connections")
    
    # Use manager for legacy API compatibility
    app.state.obs = obs_manager
    
    # Initialize guardrails with OBS service
    logger.info("Initializing guardrails system...")
    from app.api.routers.guardrails import init_guardrails
    db = await init_db()  # Get DB connection
    await init_guardrails(db, app.state.obs if hasattr(app.state, 'obs') else None)
    logger.info("Guardrails system initialized")
    
    # Initialize deferred job scheduler
    logger.info("Starting deferred job scheduler...")
    from app.worker.deferred_scheduler import init_scheduler
    scheduler = await init_scheduler(app.state.nats if hasattr(app.state, 'nats') else None)
    app.state.scheduler = scheduler
    logger.info("Deferred job scheduler started")
    
    logger.info("StreamOps API started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down StreamOps API...")
    
    # Stop deferred job scheduler
    if hasattr(app.state, 'scheduler') and app.state.scheduler:
        await app.state.scheduler.stop()
        logger.info("Deferred job scheduler stopped")
    
    # Close OBS connections
    if hasattr(app.state, 'obs') and app.state.obs:
        await app.state.obs.disconnect_all()
        logger.info("OBS connections disconnected")
    
    # Close NATS connection
    if hasattr(app.state, 'nats'):
        await app.state.nats.disconnect()
    
    # Close database
    await close_db()
    
    logger.info("StreamOps API shutdown complete")

# Create FastAPI app
app = FastAPI(
    title="StreamOps API",
    description="Media pipeline automation for streamers",
    version="1.0.0",
    lifespan=lifespan
)

# Ensure "no slash" and "slash" both resolve cleanly
app.router.redirect_slashes = True

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:7767"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cache headers middleware for proper caching policy
@app.middleware("http")
async def cache_headers(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    
    # No cache for HTML and root
    if path == "/" or path.endswith(".html"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    # Long cache for hashed assets
    elif path.startswith("/assets/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    # Default moderate cache for API responses
    elif path.startswith("/api/"):
        response.headers["Cache-Control"] = "private, max-age=0, must-revalidate"
    
    return response

# Add exception handler middleware
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler to log all unhandled errors"""
    import traceback
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {str(exc)}")
    logger.error(f"Traceback: {traceback.format_exc()}")
    
    # Return a proper error response
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"}
    )

# Include API routers
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(config.router, prefix="/api/config", tags=["config"])
app.include_router(assets.router, prefix="/api/assets", tags=["assets"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(rules.router, prefix="/api/rules", tags=["rules"])
app.include_router(guardrails.router, prefix="/api/guardrails", tags=["guardrails"])
app.include_router(overlays.router, prefix="/api/overlays", tags=["overlays"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
app.include_router(drives.router, prefix="/api/drives", tags=["drives"])
app.include_router(filesystem.router, prefix="/api/fs", tags=["filesystem"])
app.include_router(system.router, prefix="/api/system", tags=["system"])
app.include_router(wizard.router, prefix="/api/wizard", tags=["wizard"])
app.include_router(settings.router, prefix="/api", tags=["settings"])
app.include_router(obs.router, tags=["obs"])  # No prefix, it's already in the router
app.include_router(events.router, tags=["events"])

# Main WebSocket endpoint for UI updates
import asyncio
from typing import Set
import psutil
from datetime import datetime

# Store active WebSocket connections
active_websockets: Set[WebSocket] = set()

async def broadcast_to_websockets(message: dict):
    """Broadcast message to all connected WebSocket clients"""
    disconnected = set()
    for ws in active_websockets:
        try:
            await ws.send_json(message)
        except:
            disconnected.add(ws)
    # Remove disconnected websockets
    active_websockets.difference_update(disconnected)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint for real-time UI updates."""
    await websocket.accept()
    active_websockets.add(websocket)
    
    # Create background tasks for this connection
    system_task = None
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            
            # Handle subscription requests
            if data.get("type") == "subscribe":
                # Acknowledge subscription
                await websocket.send_json({
                    "type": "subscription_confirmed",
                    "topics": data.get("topics", [])
                })
                
                # Send initial data for subscribed topics
                if "jobs" in data.get("topics", []):
                    # Send current active jobs
                    try:
                        from app.api.db.database import get_db
                        db = await get_db()
                        cursor = await db.execute(
                            "SELECT * FROM so_jobs WHERE state IN ('running', 'pending') LIMIT 10"
                        )
                        jobs = await cursor.fetchall()
                        await websocket.send_json({
                            "type": "jobs_update",
                            "jobs": [{"id": row[0], "type": row[1], "state": row[4], "progress": row[5]} for row in jobs]
                        })
                    except Exception as e:
                        logger.warning(f"Failed to fetch initial jobs data: {e}")
                    
            elif data.get("type") == "subscribe_system":
                # Start sending system stats periodically
                interval = data.get("interval", 5000) / 1000  # Convert to seconds
                
                async def send_system_stats():
                    while websocket in active_websockets:
                        try:
                            # Get real system stats
                            cpu_percent = psutil.cpu_percent(interval=1)
                            memory = psutil.virtual_memory()
                            disk = psutil.disk_usage('/')
                            
                            await websocket.send_json({
                                "type": "system_stats",
                                "stats": {
                                    "cpu_percent": cpu_percent,
                                    "memory_percent": memory.percent,
                                    "memory_used": memory.used,
                                    "memory_total": memory.total,
                                    "disk_percent": disk.percent,
                                    "disk_used": disk.used,
                                    "disk_total": disk.total,
                                    "timestamp": datetime.utcnow().isoformat()
                                }
                            })
                            await asyncio.sleep(interval)
                        except asyncio.CancelledError:
                            # Task was cancelled, exit gracefully
                            break
                        except Exception as e:
                            logger.debug(f"Error sending system stats: {e}")
                            break
                
                # Cancel previous task if exists
                if system_task:
                    system_task.cancel()
                
                # Start new task
                system_task = asyncio.create_task(send_system_stats())
                
                await websocket.send_json({
                    "type": "system_subscription_confirmed",
                    "interval": data.get("interval", 5000)
                })
                
            elif data.get("type") == "ping":
                # Handle ping/pong for keepalive
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": data.get("timestamp")
                })
            
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Clean up
        active_websockets.discard(websocket)
        if system_task:
            system_task.cancel()
        # Don't try to close the websocket here - it's already closed or closing

# WebSocket endpoints for overlay communication
@app.websocket("/overlay/ws")
async def overlay_websocket(websocket: WebSocket, overlay_id: str = None):
    """WebSocket endpoint for overlay browser sources."""
    try:
        await overlay_handler.handle_overlay_connection(websocket, overlay_id)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Error in overlay WebSocket: {e}")

@app.websocket("/overlay/control")
async def overlay_control_websocket(websocket: WebSocket):
    """WebSocket endpoint for overlay control interfaces."""
    try:
        await overlay_handler.handle_control_connection(websocket)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Error in overlay control WebSocket: {e}")

# Overlay rendering endpoints
@app.get("/overlay/{overlay_id}", response_class=HTMLResponse)
async def render_overlay_page(overlay_id: str):
    """Render a complete overlay page for browser source."""
    try:
        from app.api.schemas.overlays import OverlayResponse, OverlayType, OverlayPosition, OverlayStyle, OverlayContent, OverlayStatus
        from app.api.db.database import get_db
        from datetime import datetime
        import json
        
        # Get overlay from database
        db = await get_db()
        cursor = await db.execute(
            "SELECT * FROM so_overlays WHERE id = ?",
            (overlay_id,)
        )
        row = await cursor.fetchone()
        
        if row:
            manifest = json.loads(row[2]) if row[2] else {}
            schedule = json.loads(row[3]) if row[3] else None
            stats = json.loads(row[4]) if row[4] else None
            
            overlay = OverlayResponse(
                id=row[0],
                name=row[1],
                overlay_type=OverlayType(manifest.get('type', 'text')),
                position=OverlayPosition(
                    x=manifest.get('position', {}).get('x', 100),
                    y=manifest.get('position', {}).get('y', 100),
                    z_index=manifest.get('position', {}).get('z_index', 10)
                ),
                style=OverlayStyle(
                    background_color=manifest.get('style', {}).get('background_color', 'rgba(0, 0, 0, 0.8)'),
                    text_color=manifest.get('style', {}).get('text_color', '#ffffff'),
                    font_family=manifest.get('style', {}).get('font_family', 'Arial, sans-serif'),
                    font_size=manifest.get('style', {}).get('font_size', '24px'),
                    border_radius=manifest.get('style', {}).get('border_radius', '10px'),
                    padding=manifest.get('style', {}).get('padding', '20px')
                ),
                content=OverlayContent(
                    text=manifest.get('content', {}).get('text', ''),
                    template_variables=manifest.get('content', {}).get('template_variables', {})
                ),
                enabled=row[5] == 1,
                status=OverlayStatus(stats.get('status', 'inactive') if stats else 'inactive'),
                tags=manifest.get('tags', []),
                created_at=datetime.fromisoformat(row[6]),
                updated_at=datetime.fromisoformat(row[7])
            )
        else:
            # Create default overlay if not found
            overlay = OverlayResponse(
                id=overlay_id,
                name=f"Overlay {overlay_id}",
                overlay_type=OverlayType.text,
                position=OverlayPosition(x=100, y=100, z_index=10),
                style=OverlayStyle(
                    background_color="rgba(0, 0, 0, 0.8)",
                    text_color="#ffffff",
                    font_family="Arial, sans-serif",
                    font_size="24px",
                    border_radius="10px",
                    padding="20px"
                ),
                content=OverlayContent(
                    text="Overlay Not Found",
                    template_variables={}
                ),
                enabled=False,
                status=OverlayStatus.inactive,
                tags=[],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
        
        websocket_url = f"ws://localhost:7769/overlay/ws?overlay_id={overlay_id}"
        html = overlay_renderer.render_overlay_page(overlay, websocket_url)
        return HTMLResponse(html)
        
    except Exception as e:
        logger.error(f"Failed to render overlay {overlay_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to render overlay: {str(e)}")

@app.get("/overlay/{overlay_id}/sponsor", response_class=HTMLResponse)
async def render_sponsor_overlay(overlay_id: str):
    """Render sponsor overlay template."""
    try:
        from app.api.schemas.overlays import OverlayResponse, OverlayType, OverlayPosition, OverlayStyle, OverlayContent, OverlayStatus
        from datetime import datetime
        
        # Create sponsor overlay configuration
        overlay = OverlayResponse(
            id=overlay_id,
            name=f"Sponsor Overlay {overlay_id}",
            overlay_type=OverlayType.html,
            position=OverlayPosition(x=50, y=50, z_index=10),
            style=OverlayStyle(),
            content=OverlayContent(
                template_variables={
                    "sponsor_name": "Our Sponsor",
                    "sponsor_logo": "",
                    "sponsor_message": "Thanks for supporting the stream!",
                    "sponsor_url": "https://example.com"
                }
            ),
            enabled=True,
            status=OverlayStatus.active,
            tags=["sponsor"],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        # Use sponsor template specifically
        template = overlay_renderer.get_template('sponsor.html')
        overlay_html = template.render(overlay=overlay, overlay_id=overlay_id, content=overlay.content)
        
        # Render in base template
        base_template = overlay_renderer.get_template('base.html')
        websocket_url = f"ws://localhost:7769/overlay/ws?overlay_id={overlay_id}"
        
        html = base_template.render(
            overlay=overlay,
            overlay_id=overlay_id,
            overlay_html=overlay_html,
            overlay_css="/* Sponsor overlay styles loaded via template */",
            overlay_js="/* Sponsor overlay JS loaded via template */",
            websocket_url=websocket_url,
            page_title=f"StreamOps Sponsor Overlay - {overlay.name}"
        )
        
        return HTMLResponse(html)
        
    except Exception as e:
        logger.error(f"Failed to render sponsor overlay {overlay_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to render sponsor overlay: {str(e)}")

@app.get("/overlay/{overlay_id}/alert", response_class=HTMLResponse)
async def render_alert_overlay(overlay_id: str):
    """Render alert overlay template."""
    try:
        from app.api.schemas.overlays import OverlayResponse, OverlayType, OverlayPosition, OverlayStyle, OverlayContent, OverlayStatus
        from datetime import datetime
        
        # Create alert overlay configuration
        overlay = OverlayResponse(
            id=overlay_id,
            name=f"Alert Overlay {overlay_id}",
            overlay_type=OverlayType.html,
            position=OverlayPosition(x=100, y=100, z_index=20),
            style=OverlayStyle(),
            content=OverlayContent(
                template_variables={
                    "alert_text": "Alert message",
                    "alert_type": "info",
                    "alert_subtitle": "",
                    "duration": 10
                }
            ),
            enabled=True,
            status=OverlayStatus.active,
            tags=["alert"],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        # Use alert template specifically
        template = overlay_renderer.get_template('alert.html')
        overlay_html = template.render(overlay=overlay, overlay_id=overlay_id, content=overlay.content)
        
        # Render in base template
        base_template = overlay_renderer.get_template('base.html')
        websocket_url = f"ws://localhost:7769/overlay/ws?overlay_id={overlay_id}"
        
        html = base_template.render(
            overlay=overlay,
            overlay_id=overlay_id,
            overlay_html=overlay_html,
            overlay_css="/* Alert overlay styles loaded via template */",
            overlay_js="/* Alert overlay JS loaded via template */",
            websocket_url=websocket_url,
            page_title=f"StreamOps Alert Overlay - {overlay.name}"
        )
        
        return HTMLResponse(html)
        
    except Exception as e:
        logger.error(f"Failed to render alert overlay {overlay_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to render alert overlay: {str(e)}")

# Overlay control endpoints
@app.post("/overlay/{overlay_id}/show")
async def show_overlay_endpoint(overlay_id: str, content: dict = None, duration: int = None, animation: str = None):
    """Show an overlay via HTTP endpoint."""
    try:
        await overlay_manager.show_overlay(overlay_id, content or {}, duration, animation)
        return {"message": f"Overlay {overlay_id} shown successfully"}
    except Exception as e:
        logger.error(f"Failed to show overlay {overlay_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to show overlay: {str(e)}")

@app.post("/overlay/{overlay_id}/hide")
async def hide_overlay_endpoint(overlay_id: str, animation: str = None):
    """Hide an overlay via HTTP endpoint."""
    try:
        await overlay_manager.hide_overlay(overlay_id, animation)
        return {"message": f"Overlay {overlay_id} hidden successfully"}
    except Exception as e:
        logger.error(f"Failed to hide overlay {overlay_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to hide overlay: {str(e)}")

@app.post("/overlay/{overlay_id}/update")
async def update_overlay_endpoint(overlay_id: str, content: dict, animation: str = None):
    """Update overlay content via HTTP endpoint."""
    try:
        await overlay_manager.update_overlay(overlay_id, content, animation)
        return {"message": f"Overlay {overlay_id} updated successfully"}
    except Exception as e:
        logger.error(f"Failed to update overlay {overlay_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update overlay: {str(e)}")

@app.get("/overlay/status")
async def get_overlay_status():
    """Get status of all overlays."""
    try:
        status = await overlay_manager.get_overlay_status()
        return status
    except Exception as e:
        logger.error(f"Failed to get overlay status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get overlay status: {str(e)}")

# Sponsor rotation endpoints
@app.post("/overlay/sponsor/start")
async def start_sponsor_rotation(
    rotation_id: str, 
    sponsors: list, 
    interval_seconds: int = 30, 
    overlay_id: str = "sponsor"
):
    """Start sponsor rotation."""
    try:
        await sponsor_rotation.start_sponsor_rotation(rotation_id, sponsors, interval_seconds, overlay_id)
        return {"message": f"Sponsor rotation {rotation_id} started successfully"}
    except Exception as e:
        logger.error(f"Failed to start sponsor rotation {rotation_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start sponsor rotation: {str(e)}")

@app.post("/overlay/sponsor/{rotation_id}/stop")
async def stop_sponsor_rotation(rotation_id: str):
    """Stop sponsor rotation."""
    try:
        await sponsor_rotation.stop_sponsor_rotation(rotation_id)
        return {"message": f"Sponsor rotation {rotation_id} stopped successfully"}
    except Exception as e:
        logger.error(f"Failed to stop sponsor rotation {rotation_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop sponsor rotation: {str(e)}")

@app.get("/overlay/sponsor/rotations")
async def get_sponsor_rotations():
    """Get active sponsor rotations."""
    try:
        rotations = sponsor_rotation.get_active_rotations()
        return rotations
    except Exception as e:
        logger.error(f"Failed to get sponsor rotations: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get sponsor rotations: {str(e)}")

# Serve overlay static files
overlay_static_path = Path(__file__).parent.parent / "overlay" / "static"
if overlay_static_path.exists():
    app.mount("/overlay/static", StaticFiles(directory=str(overlay_static_path)), name="overlay_static")

# Serve static files (UI)
static_path = Path("/opt/streamops/app/static")
if static_path.exists():
    app.mount("/assets", StaticFiles(directory=str(static_path / "assets")), name="assets")
    
    # Catch-all route for SPA
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # API routes are handled above, everything else serves the SPA
        if not full_path.startswith("api/") and not full_path.startswith("health/"):
            index_path = static_path / "index.html"
            if index_path.exists():
                return FileResponse(str(index_path))
        return {"error": "Not found"}, 404

# Root endpoint - serve the UI
@app.get("/")
async def root():
    index_path = static_path / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {
        "name": "StreamOps",
        "version": "1.0.0",
        "status": "running",
        "message": "UI not found - build the UI first"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.api.main:app",
        host="0.0.0.0",
        port=7767,
        reload=os.getenv("ENV", "production") == "development"
    )