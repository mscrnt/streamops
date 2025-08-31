"""OBS Manager for handling multiple OBS connections"""
import os
import json
import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import obsws_python as obs
from ulid import ULID

from app.api.db.database import get_db

logger = logging.getLogger(__name__)

class OBSClient:
    """Single OBS WebSocket client instance"""
    
    def __init__(self, connection_id: str, name: str, ws_url: str, password: Optional[str] = None):
        self.connection_id = connection_id
        self.name = name
        self.ws_url = ws_url
        self.password = password
        self.client: Optional[obs.ReqClient] = None
        self.event_client: Optional[obs.EventClient] = None
        self.connected = False
        self.last_error: Optional[str] = None
        self.last_seen: Optional[datetime] = None
        self.recording = False
        self.streaming = False
        self.current_scene: Optional[str] = None
        
    async def connect(self) -> bool:
        """Connect to OBS WebSocket"""
        try:
            # Parse URL to get host and port
            import re
            match = re.match(r'wss?://([^:]+):(\d+)', self.ws_url)
            if not match:
                self.last_error = f"Invalid WebSocket URL: {self.ws_url}"
                logger.error(f"[{self.name}] {self.last_error}")
                return False
            
            host = match.group(1)
            port = int(match.group(2))
            
            # Run blocking connection in executor
            loop = asyncio.get_event_loop()
            
            def _connect_sync():
                # Connect request client
                self.client = obs.ReqClient(
                    host=host,
                    port=port,
                    password=self.password,
                    timeout=5
                )
                
                # Connect event client
                self.event_client = obs.EventClient(
                    host=host,
                    port=port,
                    password=self.password
                )
                
                # Get initial status
                status = self.client.get_record_status()
                self.recording = status.output_active
                
                stream_status = self.client.get_stream_status()
                self.streaming = stream_status.output_active
                
                scene = self.client.get_current_program_scene()
                self.current_scene = scene.scene_name
            
            await loop.run_in_executor(None, _connect_sync)
            
            self.connected = True
            self.last_seen = datetime.utcnow()
            self.last_error = None
            logger.info(f"[{self.name}] Connected to OBS at {self.ws_url}")
            return True
            
        except Exception as e:
            self.connected = False
            self.last_error = str(e)
            logger.error(f"[{self.name}] Failed to connect: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from OBS"""
        try:
            if self.event_client:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self.event_client.disconnect)
                self.event_client = None
            
            if self.client:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self.client.disconnect)
                self.client = None
            
            self.connected = False
            logger.info(f"[{self.name}] Disconnected from OBS")
            
        except Exception as e:
            logger.error(f"[{self.name}] Error during disconnect: {e}")
    
    async def start_recording(self):
        """Start recording in OBS"""
        if not self.client:
            raise Exception("Not connected to OBS")
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.client.start_record)
            logger.info(f"[{self.name}] Started recording")
        except Exception as e:
            logger.error(f"[{self.name}] Failed to start recording: {e}")
            raise
    
    async def stop_recording(self):
        """Stop recording in OBS"""
        if not self.client:
            raise Exception("Not connected to OBS")
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.client.stop_record)
            logger.info(f"[{self.name}] Stopped recording")
        except Exception as e:
            logger.error(f"[{self.name}] Failed to stop recording: {e}")
            raise
    
    async def start_streaming(self):
        """Start streaming in OBS"""
        if not self.client:
            raise Exception("Not connected to OBS")
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.client.start_stream)
            logger.info(f"[{self.name}] Started streaming")
        except Exception as e:
            logger.error(f"[{self.name}] Failed to start streaming: {e}")
            raise
    
    async def stop_streaming(self):
        """Stop streaming in OBS"""
        if not self.client:
            raise Exception("Not connected to OBS")
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.client.stop_stream)
            logger.info(f"[{self.name}] Stopped streaming")
        except Exception as e:
            logger.error(f"[{self.name}] Failed to stop streaming: {e}")
            raise
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test connection and return capabilities"""
        try:
            if not self.connected:
                connected = await self.connect()
                if not connected:
                    return {
                        "ok": False,
                        "error": self.last_error or "Connection failed"
                    }
            
            # Get OBS info
            loop = asyncio.get_event_loop()
            
            def _get_info():
                version = self.client.get_version()
                scenes = self.client.get_scene_list()
                profiles = self.client.get_profile_list()
                collections = self.client.get_scene_collection_list()
                
                return {
                    "ok": True,
                    "obs_version": version.obs_version,
                    "websocket_version": version.obs_web_socket_version,
                    "scenes_count": len(scenes.scenes),
                    "profiles_count": len(profiles.profiles),
                    "collections_count": len(collections.scene_collections),
                    "current_scene": scenes.current_program_scene_name,
                    "current_profile": profiles.current_profile_name,
                    "current_collection": collections.current_scene_collection_name
                }
            
            info = await loop.run_in_executor(None, _get_info)
            return info
            
        except Exception as e:
            return {
                "ok": False,
                "error": str(e)
            }
    
    async def refresh_status(self) -> bool:
        """Refresh current recording/streaming status from OBS"""
        if not self.connected or not self.client:
            return False
        
        try:
            loop = asyncio.get_event_loop()
            
            def _get_status():
                record_status = self.client.get_record_status()
                stream_status = self.client.get_stream_status()
                scene = self.client.get_current_program_scene()
                return record_status.output_active, stream_status.output_active, scene.scene_name
            
            self.recording, self.streaming, self.current_scene = await loop.run_in_executor(None, _get_status)
            self.last_seen = datetime.utcnow()
            logger.debug(f"[{self.name}] Status refreshed - Recording: {self.recording}, Streaming: {self.streaming}")
            return True
        except Exception as e:
            logger.error(f"[{self.name}] Failed to refresh status: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get current client status"""
        return {
            "connection_id": self.connection_id,
            "name": self.name,
            "connected": self.connected,
            "recording": self.recording,
            "streaming": self.streaming,
            "current_scene": self.current_scene,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "last_error": self.last_error
        }


class OBSManager:
    """Manager for multiple OBS connections"""
    
    def __init__(self, nats_service=None):
        self.nats = nats_service
        self.clients: Dict[str, OBSClient] = {}
        self._running = False
        self._event_task = None
        self._polling_task = None
        
    async def load_all(self):
        """Load all enabled OBS connections from database"""
        try:
            db = await get_db()
            cursor = await db.execute("""
                SELECT id, name, ws_url, password, auto_connect, roles_json
                FROM so_obs_connections
                WHERE enabled = 1
            """)
            rows = await cursor.fetchall()
            
            for row in rows:
                conn_id, name, ws_url, password, auto_connect, roles_json = row
                
                # Create client instance
                client = OBSClient(conn_id, name, ws_url, password)
                self.clients[conn_id] = client
                
                # Auto-connect if configured
                if auto_connect:
                    asyncio.create_task(self._auto_connect(client))
                    
            logger.info(f"Loaded {len(self.clients)} OBS connections")
            
        except Exception as e:
            logger.error(f"Failed to load OBS connections: {e}")
    
    async def _auto_connect(self, client: OBSClient):
        """Auto-connect with retry logic"""
        for attempt in range(3):
            if await client.connect():
                await self._update_status(client)
                await self._setup_event_handlers(client)
                # Start polling for this client
                asyncio.create_task(self._start_polling(client))
                return
            await asyncio.sleep(5 * (attempt + 1))  # Exponential backoff
        
        logger.warning(f"Failed to auto-connect to {client.name} after 3 attempts")
        await self._update_status(client)
    
    async def _setup_event_handlers(self, client: OBSClient):
        """Setup event handlers for a client"""
        if not client.event_client:
            return
            
        try:
            loop = asyncio.get_event_loop()
            
            def register_handlers():
                # Recording events
                client.event_client.callback.register(
                    lambda data: asyncio.create_task(self._on_recording_started(client, data)),
                    "RecordStateChanged"
                )
                
                # Streaming events
                client.event_client.callback.register(
                    lambda data: asyncio.create_task(self._on_streaming_started(client, data)),
                    "StreamStateChanged"
                )
                
                # Scene changes
                client.event_client.callback.register(
                    lambda data: asyncio.create_task(self._on_scene_changed(client, data)),
                    "CurrentProgramSceneChanged"
                )
            
            await loop.run_in_executor(None, register_handlers)
            logger.info(f"Event handlers registered for {client.name}")
            
        except Exception as e:
            logger.error(f"Failed to setup event handlers for {client.name}: {e}")
    
    async def _on_recording_started(self, client: OBSClient, data):
        """Handle recording state change"""
        try:
            client.recording = data.output_active
            client.last_seen = datetime.utcnow()
            
            if data.output_active:
                # Recording started
                logger.info(f"[{client.name}] Recording started (via event)")
                await self._handle_recording_started(client)
            else:
                # Recording stopped
                logger.info(f"[{client.name}] Recording stopped (via event)")
                await self._handle_recording_stopped(client)
            
            await self._update_status(client)
            
        except Exception as e:
            logger.error(f"Error handling recording event for {client.name}: {e}")
    
    async def _on_streaming_started(self, client: OBSClient, data):
        """Handle streaming state change"""
        try:
            client.streaming = data.output_active
            client.last_seen = datetime.utcnow()
            
            if data.output_active:
                logger.info(f"[{client.name}] Streaming started (via event)")
                await self._handle_streaming_started(client)
            else:
                logger.info(f"[{client.name}] Streaming stopped (via event)")
                await self._handle_streaming_stopped(client)
            
            await self._update_status(client)
            
        except Exception as e:
            logger.error(f"Error handling streaming event for {client.name}: {e}")
    
    async def _on_scene_changed(self, client: OBSClient, data):
        """Handle scene change"""
        try:
            client.current_scene = data.scene_name
            client.last_seen = datetime.utcnow()
            
            # Emit event
            event_data = {
                "connection_id": client.connection_id,
                "connection_name": client.name,
                "timestamp": datetime.utcnow().isoformat(),
                "scene": data.scene_name
            }
            
            if self.nats:
                await self.nats.publish("events.obs.scene_changed", json.dumps(event_data))
            
            logger.info(f"[{client.name}] Scene changed to {data.scene_name}")
            await self._update_status(client)
            
        except Exception as e:
            logger.error(f"Error handling scene change for {client.name}: {e}")
    
    
    async def _start_polling(self, client: OBSClient):
        """Start polling for a specific client's status"""
        logger.info(f"Starting status polling for {client.name}")
        
        # Track previous states to detect changes
        prev_recording = client.recording
        prev_streaming = client.streaming
        
        while client.connected:
            try:
                await asyncio.sleep(5)  # Poll every 5 seconds
                if client.connected:
                    # Store previous states before refresh
                    prev_recording = client.recording
                    prev_streaming = client.streaming
                    
                    # Refresh status from OBS
                    await client.refresh_status()
                    
                    # Check if recording state changed
                    if prev_recording and not client.recording:
                        logger.info(f"[{client.name}] Recording stopped (detected via polling)")
                        await self._handle_recording_stopped(client)
                    elif not prev_recording and client.recording:
                        logger.info(f"[{client.name}] Recording started (detected via polling)")
                        await self._handle_recording_started(client)
                    
                    # Check if streaming state changed
                    if prev_streaming and not client.streaming:
                        logger.info(f"[{client.name}] Streaming stopped (detected via polling)")
                        await self._handle_streaming_stopped(client)
                    elif not prev_streaming and client.streaming:
                        logger.info(f"[{client.name}] Streaming started (detected via polling)")
                        await self._handle_streaming_started(client)
                    
                    # Update database with current status
                    await self._update_status(client)
            except Exception as e:
                logger.error(f"Error polling status for {client.name}: {e}")
                # Continue polling even on error
        logger.info(f"Stopped polling for {client.name}")
    
    async def _handle_recording_started(self, client: OBSClient):
        """Handle when recording starts - common logic for events and polling"""
        try:
            # Emit event if NATS is available
            event_data = {
                "connection_id": client.connection_id,
                "connection_name": client.name,
                "timestamp": datetime.utcnow().isoformat(),
                "scene": client.current_scene,
                "state": "recording"
            }
            
            if self.nats:
                await self.nats.publish_event("obs.recording_started", event_data)
            
            # Broadcast SSE event for immediate UI update
            try:
                from app.api.routers.events import notify_recording_state
                await notify_recording_state(True, client.name)
                logger.info(f"Sent recording started notification for {client.name}")
            except Exception as e:
                logger.error(f"Failed to send recording started notification: {e}")
            
            logger.info(f"Recording started for {client.name}")
            
        except Exception as e:
            logger.error(f"Failed to handle recording started: {e}")
    
    async def _handle_streaming_started(self, client: OBSClient):
        """Handle when streaming starts - common logic for events and polling"""
        try:
            # Emit event if NATS is available
            event_data = {
                "connection_id": client.connection_id,
                "connection_name": client.name,
                "timestamp": datetime.utcnow().isoformat(),
                "scene": client.current_scene,
                "state": "streaming"
            }
            
            if self.nats:
                await self.nats.publish_event("obs.streaming_started", event_data)
            
            # Broadcast SSE event for immediate UI update
            from app.api.routers.events import notify_recording_state
            asyncio.create_task(notify_recording_state(True, client.name))
            
            logger.info(f"Streaming started for {client.name}")
            
        except Exception as e:
            logger.error(f"Failed to handle streaming started: {e}")
    
    async def _handle_streaming_stopped(self, client: OBSClient):
        """Handle when streaming stops - common logic for events and polling"""
        try:
            # Emit event if NATS is available
            event_data = {
                "connection_id": client.connection_id,
                "connection_name": client.name,
                "timestamp": datetime.utcnow().isoformat(),
                "scene": client.current_scene,
                "state": "idle"
            }
            
            if self.nats:
                await self.nats.publish_event("obs.streaming_stopped", event_data)
            
            # Broadcast SSE event for immediate UI update
            from app.api.routers.events import notify_recording_state
            asyncio.create_task(notify_recording_state(False, client.name))
            
            logger.info(f"Streaming stopped for {client.name}")
            
        except Exception as e:
            logger.error(f"Failed to handle streaming stopped: {e}")
    
    async def _handle_recording_stopped(self, client: OBSClient):
        """Handle when recording stops - common logic for events and polling"""
        try:
            # Emit event if NATS is available
            event_data = {
                "connection_id": client.connection_id,
                "connection_name": client.name,
                "timestamp": datetime.utcnow().isoformat(),
                "scene": client.current_scene,
                "state": "idle"
            }
            
            if self.nats:
                await self.nats.publish_event("obs.recording_stopped", event_data)
            
            # Broadcast SSE event for immediate UI update
            try:
                from app.api.routers.events import notify_recording_state
                await notify_recording_state(False, client.name)
                logger.info(f"Sent recording stopped notification for {client.name}")
            except Exception as e:
                logger.error(f"Failed to send recording stopped notification: {e}")
            
            # Scan immediately - OBS recordings are complete when stopped
            logger.info(f"Recording stopped for {client.name}, scanning for new files immediately")
            asyncio.create_task(self._trigger_recording_scan())
            
        except Exception as e:
            logger.error(f"Failed to handle recording stopped: {e}")
    
    
    async def _trigger_recording_scan(self):
        """Trigger scan of recording folders after recording stops"""
        try:
            db = await get_db()
            # Get recording folder paths
            cursor = await db.execute(
                "SELECT abs_path FROM so_roles WHERE role = 'recording'"
            )
            rows = await cursor.fetchall()
            
            for row in rows:
                recording_path = row[0]
                logger.info(f"Triggering scan of recording folder: {recording_path}")
                
                # Import and use DriveWatcher to scan
                from app.worker.watchers.drive_watcher import DriveWatcher
                watcher = DriveWatcher(recording_path, self.nats)
                await watcher.scan_existing()
                
        except Exception as e:
            logger.error(f"Failed to trigger recording scan: {e}")
    
    async def _update_status(self, client: OBSClient):
        """Update client status in database"""
        try:
            db = await get_db()
            status = "connected" if client.connected else "disconnected"
            if client.last_error and not client.connected:
                status = f"error:{client.last_error[:100]}"
            
            await db.execute("""
                UPDATE so_obs_connections
                SET last_status = ?, last_error = ?, last_seen_ts = ?, updated_at = ?
                WHERE id = ?
            """, (
                status,
                client.last_error,
                client.last_seen.isoformat() if client.last_seen else None,
                datetime.utcnow().isoformat(),
                client.connection_id
            ))
            await db.commit()
            
        except Exception as e:
            logger.error(f"Failed to update status for {client.name}: {e}")
    
    async def connect(self, connection_id: str) -> bool:
        """Connect a specific OBS instance"""
        if connection_id not in self.clients:
            # Load from database
            db = await get_db()
            cursor = await db.execute("""
                SELECT name, ws_url, password
                FROM so_obs_connections
                WHERE id = ? AND enabled = 1
            """, (connection_id,))
            row = await cursor.fetchone()
            
            if not row:
                logger.error(f"Connection {connection_id} not found or disabled")
                return False
            
            name, ws_url, password = row
            client = OBSClient(connection_id, name, ws_url, password)
            self.clients[connection_id] = client
        else:
            client = self.clients[connection_id]
        
        success = await client.connect()
        if success:
            await self._setup_event_handlers(client)
            # Start polling for this client
            asyncio.create_task(self._start_polling(client))
        await self._update_status(client)
        return success
    
    async def disconnect(self, connection_id: str) -> bool:
        """Disconnect a specific OBS instance"""
        if connection_id not in self.clients:
            return False
        
        client = self.clients[connection_id]
        await client.disconnect()
        await self._update_status(client)
        return True
    
    async def disconnect_all(self):
        """Disconnect all OBS instances"""
        for connection_id in list(self.clients.keys()):
            await self.disconnect(connection_id)
        logger.info("Disconnected all OBS connections")
    
    async def test(self, connection_id: str) -> Dict[str, Any]:
        """Test a specific OBS connection"""
        if connection_id not in self.clients:
            # Load from database for testing
            db = await get_db()
            cursor = await db.execute("""
                SELECT name, ws_url, password
                FROM so_obs_connections
                WHERE id = ?
            """, (connection_id,))
            row = await cursor.fetchone()
            
            if not row:
                return {"ok": False, "error": "Connection not found"}
            
            name, ws_url, password = row
            client = OBSClient(connection_id, name, ws_url, password)
        else:
            client = self.clients[connection_id]
        
        result = await client.test_connection()
        
        # Disconnect if we created a temporary client
        if connection_id not in self.clients and client.connected:
            await client.disconnect()
        
        return result
    
    def get_state(self, scope: Optional[str] = None) -> Dict[str, Any]:
        """Get current state of all connections"""
        state = {
            "connected_count": 0,
            "recording_count": 0,
            "streaming_count": 0,
            "any_active": False,
            "connections": []
        }
        
        for client in self.clients.values():
            if client.connected:
                state["connected_count"] += 1
            if client.recording:
                state["recording_count"] += 1
            if client.streaming:
                state["streaming_count"] += 1
            
            state["connections"].append(client.get_status())
        
        state["any_active"] = state["recording_count"] > 0 or state["streaming_count"] > 0
        
        return state
    
    def is_any_active(self, scope: Optional[str] = None) -> bool:
        """Check if any OBS instance is actively recording/streaming"""
        for client in self.clients.values():
            if client.connected and (client.recording or client.streaming):
                return True
        return False
    
    async def get_all_statuses(self) -> Dict[str, Dict[str, Any]]:
        """Get status for all connections"""
        statuses = {}
        for connection_id, client in self.clients.items():
            statuses[connection_id] = client.get_status()
        return statuses
    
    async def connect_all_autostart(self):
        """Connect all auto-start enabled connections"""
        await self.load_all()
        logger.info(f"OBS Manager initialized with {len(self.clients)} connections")

# Global instance
obs_manager: Optional[OBSManager] = None

def get_obs_manager() -> OBSManager:
    """Get OBS manager singleton"""
    global obs_manager
    if obs_manager is None:
        obs_manager = OBSManager()
    return obs_manager