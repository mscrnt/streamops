"""
WebSocket server for real-time overlay control and communication.
"""

import asyncio
import json
import logging
from typing import Dict, List, Set, Optional, Any
from datetime import datetime, timedelta
from fastapi import WebSocket, WebSocketDisconnect
from contextlib import asynccontextmanager
import uuid

from app.api.services.config_service import ConfigService

logger = logging.getLogger(__name__)


class OverlayConnectionManager:
    """Manages WebSocket connections for overlay clients and control interfaces."""
    
    def __init__(self):
        # Active overlay connections (browser sources)
        self.overlay_connections: Dict[str, WebSocket] = {}
        # Control connections (admin interface)
        self.control_connections: Set[WebSocket] = set()
        # Overlay states and schedules
        self.overlay_states: Dict[str, Dict[str, Any]] = {}
        # Scheduled tasks
        self.scheduled_tasks: Dict[str, asyncio.Task] = {}
        # Impression tracking
        self.impressions: Dict[str, List[datetime]] = {}
        
    async def connect_overlay(self, websocket: WebSocket, overlay_id: str):
        """Connect an overlay browser source."""
        await websocket.accept()
        self.overlay_connections[overlay_id] = websocket
        logger.info(f"Overlay {overlay_id} connected")
        
        # Send current state if available
        if overlay_id in self.overlay_states:
            await self.send_to_overlay(overlay_id, self.overlay_states[overlay_id])
    
    async def connect_control(self, websocket: WebSocket):
        """Connect a control interface."""
        await websocket.accept()
        self.control_connections.add(websocket)
        logger.info("Control interface connected")
        
        # Send current status
        await self.send_to_control(websocket, {
            "type": "status",
            "active_overlays": list(self.overlay_connections.keys()),
            "overlay_states": self.overlay_states,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def disconnect_overlay(self, overlay_id: str):
        """Disconnect an overlay browser source."""
        if overlay_id in self.overlay_connections:
            del self.overlay_connections[overlay_id]
            logger.info(f"Overlay {overlay_id} disconnected")
    
    def disconnect_control(self, websocket: WebSocket):
        """Disconnect a control interface."""
        self.control_connections.discard(websocket)
        logger.info("Control interface disconnected")
    
    async def send_to_overlay(self, overlay_id: str, data: Dict[str, Any]):
        """Send data to a specific overlay."""
        if overlay_id not in self.overlay_connections:
            return
            
        try:
            websocket = self.overlay_connections[overlay_id]
            await websocket.send_text(json.dumps({
                **data,
                "timestamp": datetime.utcnow().isoformat()
            }))
            
            # Track impression if this is a show command
            if data.get("type") == "show":
                self.track_impression(overlay_id)
                
        except Exception as e:
            logger.error(f"Failed to send to overlay {overlay_id}: {e}")
            self.disconnect_overlay(overlay_id)
    
    async def broadcast_to_overlays(self, data: Dict[str, Any]):
        """Broadcast data to all connected overlays."""
        if not self.overlay_connections:
            return
            
        message = json.dumps({
            **data,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        disconnected = []
        for overlay_id, websocket in self.overlay_connections.items():
            try:
                await websocket.send_text(message)
            except Exception as e:
                logger.error(f"Failed to broadcast to overlay {overlay_id}: {e}")
                disconnected.append(overlay_id)
        
        # Clean up disconnected overlays
        for overlay_id in disconnected:
            self.disconnect_overlay(overlay_id)
    
    async def send_to_control(self, websocket: WebSocket, data: Dict[str, Any]):
        """Send data to a specific control interface."""
        try:
            await websocket.send_text(json.dumps({
                **data,
                "timestamp": datetime.utcnow().isoformat()
            }))
        except Exception as e:
            logger.error(f"Failed to send to control interface: {e}")
            self.disconnect_control(websocket)
    
    async def broadcast_to_controls(self, data: Dict[str, Any]):
        """Broadcast data to all control interfaces."""
        if not self.control_connections:
            return
            
        message = json.dumps({
            **data,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        disconnected = []
        for websocket in self.control_connections:
            try:
                await websocket.send_text(message)
            except Exception as e:
                logger.error(f"Failed to broadcast to control interface: {e}")
                disconnected.append(websocket)
        
        # Clean up disconnected controls
        for websocket in disconnected:
            self.disconnect_control(websocket)
    
    def track_impression(self, overlay_id: str):
        """Track overlay impression for analytics."""
        now = datetime.utcnow()
        if overlay_id not in self.impressions:
            self.impressions[overlay_id] = []
        
        self.impressions[overlay_id].append(now)
        
        # Clean up old impressions (keep last 24 hours)
        cutoff = now - timedelta(hours=24)
        self.impressions[overlay_id] = [
            imp for imp in self.impressions[overlay_id] 
            if imp > cutoff
        ]
    
    def get_impression_stats(self, overlay_id: str) -> Dict[str, Any]:
        """Get impression statistics for an overlay."""
        if overlay_id not in self.impressions:
            return {
                "total_24h": 0,
                "last_hour": 0,
                "last_shown": None
            }
        
        impressions = self.impressions[overlay_id]
        now = datetime.utcnow()
        
        last_hour = len([
            imp for imp in impressions 
            if imp > now - timedelta(hours=1)
        ])
        
        return {
            "total_24h": len(impressions),
            "last_hour": last_hour,
            "last_shown": max(impressions).isoformat() if impressions else None
        }
    
    async def show_overlay(
        self, 
        overlay_id: str, 
        content: Dict[str, Any],
        duration: Optional[int] = None,
        animation: Optional[str] = None
    ):
        """Show an overlay with specified content."""
        data = {
            "type": "show",
            "overlay_id": overlay_id,
            "content": content,
            "animation": animation or "fadeIn",
            "duration": duration
        }
        
        # Update state
        self.overlay_states[overlay_id] = {
            **data,
            "visible": True,
            "shown_at": datetime.utcnow().isoformat()
        }
        
        # Send to overlay
        await self.send_to_overlay(overlay_id, data)
        
        # Notify control interfaces
        await self.broadcast_to_controls({
            "type": "overlay_shown",
            "overlay_id": overlay_id,
            "content": content,
            "duration": duration
        })
        
        # Schedule auto-hide if duration specified
        if duration:
            await self.schedule_hide(overlay_id, duration)
    
    async def hide_overlay(
        self, 
        overlay_id: str, 
        animation: Optional[str] = None
    ):
        """Hide an overlay."""
        data = {
            "type": "hide",
            "overlay_id": overlay_id,
            "animation": animation or "fadeOut"
        }
        
        # Update state
        if overlay_id in self.overlay_states:
            self.overlay_states[overlay_id]["visible"] = False
            self.overlay_states[overlay_id]["hidden_at"] = datetime.utcnow().isoformat()
        
        # Send to overlay
        await self.send_to_overlay(overlay_id, data)
        
        # Notify control interfaces
        await self.broadcast_to_controls({
            "type": "overlay_hidden",
            "overlay_id": overlay_id
        })
        
        # Cancel any scheduled hide task
        if overlay_id in self.scheduled_tasks:
            self.scheduled_tasks[overlay_id].cancel()
            del self.scheduled_tasks[overlay_id]
    
    async def update_overlay(
        self, 
        overlay_id: str, 
        content: Dict[str, Any],
        animation: Optional[str] = None
    ):
        """Update overlay content without hiding/showing."""
        data = {
            "type": "update",
            "overlay_id": overlay_id,
            "content": content,
            "animation": animation or "slideIn"
        }
        
        # Update state
        if overlay_id in self.overlay_states:
            self.overlay_states[overlay_id]["content"] = content
            self.overlay_states[overlay_id]["updated_at"] = datetime.utcnow().isoformat()
        
        # Send to overlay
        await self.send_to_overlay(overlay_id, data)
        
        # Notify control interfaces
        await self.broadcast_to_controls({
            "type": "overlay_updated",
            "overlay_id": overlay_id,
            "content": content
        })
    
    async def schedule_hide(self, overlay_id: str, delay_seconds: int):
        """Schedule an overlay to be hidden after a delay."""
        async def hide_task():
            try:
                await asyncio.sleep(delay_seconds)
                await self.hide_overlay(overlay_id)
            except asyncio.CancelledError:
                pass
        
        # Cancel existing task if any
        if overlay_id in self.scheduled_tasks:
            self.scheduled_tasks[overlay_id].cancel()
        
        # Create new task
        task = asyncio.create_task(hide_task())
        self.scheduled_tasks[overlay_id] = task
    
    async def set_overlay_schedule(
        self, 
        overlay_id: str, 
        schedule: Dict[str, Any]
    ):
        """Set up recurring overlay schedule."""
        # This would integrate with a job scheduler
        # For now, just store the schedule configuration
        if overlay_id not in self.overlay_states:
            self.overlay_states[overlay_id] = {}
        
        self.overlay_states[overlay_id]["schedule"] = schedule
        
        # Notify control interfaces
        await self.broadcast_to_controls({
            "type": "schedule_set",
            "overlay_id": overlay_id,
            "schedule": schedule
        })
    
    async def get_overlay_status(self) -> Dict[str, Any]:
        """Get current status of all overlays."""
        return {
            "connected_overlays": list(self.overlay_connections.keys()),
            "control_connections": len(self.control_connections),
            "overlay_states": self.overlay_states,
            "impression_stats": {
                overlay_id: self.get_impression_stats(overlay_id)
                for overlay_id in self.overlay_states.keys()
            }
        }


# Global connection manager instance
overlay_manager = OverlayConnectionManager()


class OverlayWebSocketHandler:
    """Handles WebSocket connections for overlays."""
    
    def __init__(self, manager: OverlayConnectionManager):
        self.manager = manager
    
    async def handle_overlay_connection(self, websocket: WebSocket, overlay_id: str):
        """Handle overlay browser source WebSocket connection."""
        await self.manager.connect_overlay(websocket, overlay_id)
        
        try:
            while True:
                # Listen for messages from overlay (status updates, etc.)
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Handle overlay status messages
                if message.get("type") == "status":
                    await self.handle_overlay_status(overlay_id, message)
                elif message.get("type") == "error":
                    await self.handle_overlay_error(overlay_id, message)
                elif message.get("type") == "impression":
                    self.manager.track_impression(overlay_id)
                
        except WebSocketDisconnect:
            self.manager.disconnect_overlay(overlay_id)
        except Exception as e:
            logger.error(f"Error in overlay connection {overlay_id}: {e}")
            self.manager.disconnect_overlay(overlay_id)
    
    async def handle_control_connection(self, websocket: WebSocket):
        """Handle control interface WebSocket connection."""
        await self.manager.connect_control(websocket)
        
        try:
            while True:
                # Listen for control commands
                data = await websocket.receive_text()
                message = json.loads(data)
                
                await self.handle_control_command(message)
                
        except WebSocketDisconnect:
            self.manager.disconnect_control(websocket)
        except Exception as e:
            logger.error(f"Error in control connection: {e}")
            self.manager.disconnect_control(websocket)
    
    async def handle_overlay_status(self, overlay_id: str, message: Dict[str, Any]):
        """Handle status update from overlay."""
        logger.debug(f"Overlay {overlay_id} status: {message}")
        
        # Broadcast status to control interfaces
        await self.manager.broadcast_to_controls({
            "type": "overlay_status",
            "overlay_id": overlay_id,
            "status": message
        })
    
    async def handle_overlay_error(self, overlay_id: str, message: Dict[str, Any]):
        """Handle error from overlay."""
        logger.error(f"Overlay {overlay_id} error: {message}")
        
        # Broadcast error to control interfaces
        await self.manager.broadcast_to_controls({
            "type": "overlay_error",
            "overlay_id": overlay_id,
            "error": message
        })
    
    async def handle_control_command(self, message: Dict[str, Any]):
        """Handle command from control interface."""
        command = message.get("command")
        overlay_id = message.get("overlay_id")
        
        if command == "show":
            await self.manager.show_overlay(
                overlay_id,
                message.get("content", {}),
                message.get("duration"),
                message.get("animation")
            )
        
        elif command == "hide":
            await self.manager.hide_overlay(
                overlay_id,
                message.get("animation")
            )
        
        elif command == "update":
            await self.manager.update_overlay(
                overlay_id,
                message.get("content", {}),
                message.get("animation")
            )
        
        elif command == "get_status":
            status = await self.manager.get_overlay_status()
            # Send status back to requesting control
            # (In practice, you'd need to track which control sent this)
            await self.manager.broadcast_to_controls({
                "type": "status_response",
                "status": status
            })
        
        elif command == "set_schedule":
            await self.manager.set_overlay_schedule(
                overlay_id,
                message.get("schedule", {})
            )
        
        else:
            logger.warning(f"Unknown control command: {command}")


# Create handler instance
overlay_handler = OverlayWebSocketHandler(overlay_manager)


# Sponsor rotation functionality
class SponsorRotation:
    """Manages sponsor overlay rotations and scheduling."""
    
    def __init__(self, manager: OverlayConnectionManager):
        self.manager = manager
        self.rotation_tasks: Dict[str, asyncio.Task] = {}
        self.sponsor_configs: Dict[str, Dict[str, Any]] = {}
    
    async def start_sponsor_rotation(
        self, 
        rotation_id: str, 
        sponsors: List[Dict[str, Any]], 
        interval_seconds: int = 30,
        overlay_id: str = "sponsor"
    ):
        """Start sponsor rotation for an overlay."""
        
        async def rotation_task():
            sponsor_index = 0
            try:
                while True:
                    if not sponsors:
                        await asyncio.sleep(interval_seconds)
                        continue
                    
                    sponsor = sponsors[sponsor_index % len(sponsors)]
                    
                    # Show sponsor overlay
                    await self.manager.show_overlay(
                        overlay_id,
                        {
                            "type": "sponsor",
                            "sponsor_name": sponsor.get("name", ""),
                            "sponsor_logo": sponsor.get("logo_url", ""),
                            "sponsor_message": sponsor.get("message", ""),
                            "sponsor_url": sponsor.get("url", "")
                        },
                        duration=interval_seconds - 2,  # Hide 2 seconds before next
                        animation="slideInRight"
                    )
                    
                    sponsor_index += 1
                    await asyncio.sleep(interval_seconds)
                    
            except asyncio.CancelledError:
                await self.manager.hide_overlay(overlay_id)
                raise
        
        # Cancel existing rotation if any
        if rotation_id in self.rotation_tasks:
            self.rotation_tasks[rotation_id].cancel()
        
        # Store configuration
        self.sponsor_configs[rotation_id] = {
            "sponsors": sponsors,
            "interval": interval_seconds,
            "overlay_id": overlay_id
        }
        
        # Start new rotation
        task = asyncio.create_task(rotation_task())
        self.rotation_tasks[rotation_id] = task
        
        logger.info(f"Started sponsor rotation {rotation_id} with {len(sponsors)} sponsors")
    
    async def stop_sponsor_rotation(self, rotation_id: str):
        """Stop sponsor rotation."""
        if rotation_id in self.rotation_tasks:
            self.rotation_tasks[rotation_id].cancel()
            del self.rotation_tasks[rotation_id]
            
        if rotation_id in self.sponsor_configs:
            del self.sponsor_configs[rotation_id]
        
        logger.info(f"Stopped sponsor rotation {rotation_id}")
    
    def get_active_rotations(self) -> Dict[str, Dict[str, Any]]:
        """Get information about active sponsor rotations."""
        return {
            rotation_id: {
                **config,
                "active": rotation_id in self.rotation_tasks and not self.rotation_tasks[rotation_id].done()
            }
            for rotation_id, config in self.sponsor_configs.items()
        }


# Create sponsor rotation manager
sponsor_rotation = SponsorRotation(overlay_manager)


# Export the main components for use in FastAPI routes
__all__ = [
    "overlay_manager",
    "overlay_handler", 
    "sponsor_rotation",
    "OverlayConnectionManager",
    "OverlayWebSocketHandler",
    "SponsorRotation"
]