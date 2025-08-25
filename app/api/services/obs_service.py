import os
import json
import logging
import asyncio
from typing import Dict, Any, Optional, Callable
from datetime import datetime
import obsws_python as obs

logger = logging.getLogger(__name__)

class OBSService:
    """Service for OBS WebSocket integration"""
    
    def __init__(self, nats_service=None):
        self.nats = nats_service
        self.ws_url = os.getenv("OBS_WS_URL")
        self.ws_password = os.getenv("OBS_WS_PASSWORD")
        self.client: Optional[obs.ReqClient] = None
        self.event_client: Optional[obs.EventClient] = None
        self.connected = False
        self.current_session: Optional[Dict[str, Any]] = None
        self.auto_reconnect = True
        self._callbacks: Dict[str, list] = {}
        
    async def connect(self):
        """Connect to OBS WebSocket"""
        if not self.ws_url:
            logger.info("OBS WebSocket URL not configured")
            return
        
        try:
            # Parse URL to get host and port
            import re
            match = re.match(r'ws://([^:]+):(\d+)', self.ws_url)
            if not match:
                logger.error(f"Invalid OBS WebSocket URL: {self.ws_url}")
                return
            
            host = match.group(1)
            port = int(match.group(2))
            
            # Run blocking connection in executor
            loop = asyncio.get_event_loop()
            
            def _connect_sync():
                # Connect request client
                self.client = obs.ReqClient(
                    host=host,
                    port=port,
                    password=self.ws_password
                )
                
                # Connect event client
                self.event_client = obs.EventClient(
                    host=host,
                    port=port,
                    password=self.ws_password
                )
                
                # Register event handlers
                self._register_event_handlers()
                return True
            
            await loop.run_in_executor(None, _connect_sync)
            
            self.connected = True
            logger.info(f"Connected to OBS WebSocket at {self.ws_url}")
            
            # Start status update task in background
            asyncio.create_task(self._update_status())
            
        except Exception as e:
            logger.error(f"Failed to connect to OBS: {e}")
            self.connected = False
            
            # Schedule reconnect
            if self.auto_reconnect:
                asyncio.create_task(self._reconnect())
    
    async def disconnect(self):
        """Disconnect from OBS WebSocket"""
        self.auto_reconnect = False
        
        if self.event_client:
            self.event_client.disconnect()
        
        self.connected = False
        logger.info("Disconnected from OBS WebSocket")
    
    async def _reconnect(self):
        """Attempt to reconnect to OBS"""
        await asyncio.sleep(10)
        
        if self.auto_reconnect and not self.connected:
            logger.info("Attempting to reconnect to OBS...")
            await self.connect()
    
    def _register_event_handlers(self):
        """Register OBS event handlers"""
        if not self.event_client:
            return
        
        # Recording events
        self.event_client.callback.register(self._on_recording_started)
        self.event_client.callback.register(self._on_recording_stopped)
        self.event_client.callback.register(self._on_recording_paused)
        self.event_client.callback.register(self._on_recording_resumed)
        
        # Scene events
        self.event_client.callback.register(self._on_scene_changed)
        
        # Stream events
        self.event_client.callback.register(self._on_stream_started)
        self.event_client.callback.register(self._on_stream_stopped)
    
    async def _on_recording_started(self, data):
        """Handle recording started event"""
        logger.info("OBS Recording started")
        
        # Create session
        self.current_session = {
            "id": self._generate_session_id(),
            "start_ts": datetime.utcnow().isoformat(),
            "scene_at_start": await self.get_current_scene(),
            "obs_profile": await self.get_current_profile(),
            "obs_collection": await self.get_current_collection(),
            "markers": []
        }
        
        # Save session to database
        await self._save_session()
        
        # Publish event
        if self.nats:
            await self.nats.publish_event(
                "obs.recording.started",
                self.current_session
            )
        
        # Trigger callbacks
        await self._trigger_callbacks("recording_started", self.current_session)
    
    async def _on_recording_stopped(self, data):
        """Handle recording stopped event"""
        logger.info("OBS Recording stopped")
        
        if self.current_session:
            # Update session
            self.current_session["end_ts"] = datetime.utcnow().isoformat()
            
            # Calculate duration
            start = datetime.fromisoformat(self.current_session["start_ts"])
            end = datetime.fromisoformat(self.current_session["end_ts"])
            duration = (end - start).total_seconds()
            
            self.current_session["duration_sec"] = duration
            
            # Update session in database
            await self._update_session()
            
            # Publish event
            if self.nats:
                await self.nats.publish_event(
                    "obs.recording.stopped",
                    self.current_session
                )
                
                # Trigger file processing rule
                await self.nats.publish_event(
                    "session.ended",
                    {
                        "session_id": self.current_session["id"],
                        "duration_sec": duration,
                        "has_markers": len(self.current_session.get("markers", [])) > 0
                    }
                )
            
            # Trigger callbacks
            await self._trigger_callbacks("recording_stopped", self.current_session)
            
            # Clear current session
            self.current_session = None
    
    async def _on_recording_paused(self, data):
        """Handle recording paused event"""
        logger.info("OBS Recording paused")
        
        if self.nats:
            await self.nats.publish_event("obs.recording.paused", {})
    
    async def _on_recording_resumed(self, data):
        """Handle recording resumed event"""
        logger.info("OBS Recording resumed")
        
        if self.nats:
            await self.nats.publish_event("obs.recording.resumed", {})
    
    async def _on_scene_changed(self, data):
        """Handle scene changed event"""
        scene_name = data.sceneName
        logger.info(f"OBS Scene changed to: {scene_name}")
        
        # Add scene change marker if recording
        if self.current_session:
            marker = {
                "type": "scene_change",
                "scene": scene_name,
                "timestamp": datetime.utcnow().isoformat()
            }
            self.current_session["markers"].append(marker)
        
        if self.nats:
            await self.nats.publish_event(
                "obs.scene.changed",
                {"scene": scene_name}
            )
    
    async def _on_stream_started(self, data):
        """Handle stream started event"""
        logger.info("OBS Stream started")
        
        if self.nats:
            await self.nats.publish_event("obs.stream.started", {})
    
    async def _on_stream_stopped(self, data):
        """Handle stream stopped event"""
        logger.info("OBS Stream stopped")
        
        if self.nats:
            await self.nats.publish_event("obs.stream.stopped", {})
    
    async def get_status(self) -> Dict[str, Any]:
        """Get OBS status"""
        if not self.connected or not self.client:
            return {
                "connected": False,
                "recording": False,
                "streaming": False
            }
        
        try:
            record_status = self.client.get_record_status()
            stream_status = self.client.get_stream_status()
            
            return {
                "connected": True,
                "recording": record_status.output_active,
                "recording_paused": record_status.output_paused if hasattr(record_status, 'output_paused') else False,
                "recording_duration": record_status.output_duration if hasattr(record_status, 'output_duration') else 0,
                "streaming": stream_status.output_active,
                "streaming_duration": stream_status.output_duration if hasattr(stream_status, 'output_duration') else 0
            }
        except Exception as e:
            logger.error(f"Failed to get OBS status: {e}")
            return {
                "connected": False,
                "recording": False,
                "streaming": False
            }
    
    async def get_current_scene(self) -> Optional[str]:
        """Get current OBS scene"""
        if not self.connected or not self.client:
            return None
        
        try:
            response = self.client.get_current_program_scene()
            return response.current_program_scene_name
        except Exception as e:
            logger.error(f"Failed to get current scene: {e}")
            return None
    
    async def get_current_profile(self) -> Optional[str]:
        """Get current OBS profile"""
        if not self.connected or not self.client:
            return None
        
        try:
            response = self.client.get_current_profile()
            return response.current_profile_name
        except Exception as e:
            logger.error(f"Failed to get current profile: {e}")
            return None
    
    async def get_current_collection(self) -> Optional[str]:
        """Get current OBS scene collection"""
        if not self.connected or not self.client:
            return None
        
        try:
            response = self.client.get_current_scene_collection()
            return response.current_scene_collection_name
        except Exception as e:
            logger.error(f"Failed to get current collection: {e}")
            return None
    
    async def add_marker(self, marker_type: str, data: Dict[str, Any] = None):
        """Add a marker to the current recording session"""
        if not self.current_session:
            logger.warning("No active recording session for marker")
            return
        
        marker = {
            "type": marker_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data or {}
        }
        
        self.current_session["markers"].append(marker)
        logger.info(f"Added marker: {marker_type}")
        
        # Publish marker event
        if self.nats:
            await self.nats.publish_event(
                "obs.marker.added",
                marker
            )
    
    async def _update_status(self):
        """Update OBS status periodically"""
        while self.connected:
            try:
                status = await self.get_status()
                
                # Publish status update
                if self.nats:
                    await self.nats.publish_metric(
                        "obs.status",
                        status,
                        {"source": "obs_service"}
                    )
                
                await asyncio.sleep(30)  # Update every 30 seconds
                
            except Exception as e:
                logger.error(f"Error updating OBS status: {e}")
                await asyncio.sleep(60)
    
    async def _save_session(self):
        """Save session to database"""
        if not self.current_session:
            return
        
        from app.api.db.database import get_db
        
        try:
            db = await get_db()
            await db.execute(
                """
                INSERT INTO so_sessions (
                    id, start_ts, scene_at_start, obs_profile, 
                    obs_collection, markers_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    self.current_session["id"],
                    self.current_session["start_ts"],
                    self.current_session.get("scene_at_start"),
                    self.current_session.get("obs_profile"),
                    self.current_session.get("obs_collection"),
                    json.dumps(self.current_session.get("markers", []))
                )
            )
            await db.commit()
            
        except Exception as e:
            logger.error(f"Failed to save session: {e}")
    
    async def _update_session(self):
        """Update session in database"""
        if not self.current_session:
            return
        
        from app.api.db.database import get_db
        
        try:
            db = await get_db()
            await db.execute(
                """
                UPDATE so_sessions 
                SET end_ts = ?, markers_json = ?, metrics_json = ?
                WHERE id = ?
                """,
                (
                    self.current_session.get("end_ts"),
                    json.dumps(self.current_session.get("markers", [])),
                    json.dumps({
                        "duration_sec": self.current_session.get("duration_sec", 0)
                    }),
                    self.current_session["id"]
                )
            )
            await db.commit()
            
        except Exception as e:
            logger.error(f"Failed to update session: {e}")
    
    def _generate_session_id(self) -> str:
        """Generate unique session ID"""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        return f"session_{timestamp}"
    
    def register_callback(self, event: str, callback: Callable):
        """Register a callback for an event"""
        if event not in self._callbacks:
            self._callbacks[event] = []
        self._callbacks[event].append(callback)
    
    async def _trigger_callbacks(self, event: str, data: Any):
        """Trigger callbacks for an event"""
        if event in self._callbacks:
            for callback in self._callbacks[event]:
                try:
                    await callback(data)
                except Exception as e:
                    logger.error(f"Error in callback for {event}: {e}")
    
    async def test_connection(self, url: str, password: str) -> bool:
        """Test OBS WebSocket connection with provided credentials"""
        try:
            # Parse URL to get host and port
            import re
            match = re.match(r'ws://([^:]+):(\d+)', url)
            if not match:
                logger.error(f"Invalid OBS WebSocket URL: {url}")
                return False
            
            host = match.group(1)
            port = int(match.group(2))
            
            # Try to connect with provided credentials
            test_client = obs.ReqClient(
                host=host,
                port=port,
                password=password,
                timeout=5
            )
            
            # If connection succeeds, disconnect and return True
            test_client.disconnect()
            return True
            
        except Exception as e:
            logger.error(f"Failed to test OBS connection: {e}")
            return False