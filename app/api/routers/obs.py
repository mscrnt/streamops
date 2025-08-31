"""OBS connections management API"""
import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel, Field, validator
from ulid import ULID

from app.api.db.database import get_db
from app.api.services.obs_manager import get_obs_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/obs", tags=["obs"])

class OBSConnection(BaseModel):
    """OBS connection configuration"""
    name: str = Field(..., min_length=1, max_length=100, description="Friendly name for the connection")
    ws_url: str = Field(..., description="WebSocket URL (ws://host:port)")
    password: Optional[str] = Field(None, description="OBS WebSocket password")
    auto_connect: bool = Field(True, description="Auto-connect on startup")
    roles: List[str] = Field(default_factory=list, description="Connection roles (recording, streaming, backup)")
    
    @validator('ws_url')
    def validate_ws_url(cls, v):
        if not v.startswith(('ws://', 'wss://')):
            raise ValueError('WebSocket URL must start with ws:// or wss://')
        return v
    
    @validator('roles')
    def validate_roles(cls, v):
        valid_roles = {'recording', 'streaming', 'backup'}
        for role in v:
            if role not in valid_roles:
                raise ValueError(f'Invalid role: {role}. Must be one of: {", ".join(valid_roles)}')
        return v

class OBSConnectionUpdate(BaseModel):
    """OBS connection update"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    ws_url: Optional[str] = None
    password: Optional[str] = None
    auto_connect: Optional[bool] = None
    roles: Optional[List[str]] = None
    enabled: Optional[bool] = None

class OBSConnectionResponse(BaseModel):
    """OBS connection with status"""
    id: str
    name: str
    ws_url: str
    password: str = Field(default="***", description="Password is masked")
    auto_connect: bool
    enabled: bool
    roles: List[str]
    last_status: Optional[str]
    last_error: Optional[str]
    last_seen_ts: Optional[str]
    created_at: str
    updated_at: str
    
    # Live status (added when queried)
    connected: Optional[bool] = None
    recording: Optional[bool] = None
    streaming: Optional[bool] = None
    current_scene: Optional[str] = None

@router.get("", response_model=List[OBSConnectionResponse])
async def list_connections(db=Depends(get_db)):
    """List all OBS connections with live status"""
    try:
        cursor = await db.execute("""
            SELECT id, name, ws_url, auto_connect, enabled, roles_json,
                   last_status, last_error, last_seen_ts, created_at, updated_at
            FROM so_obs_connections
            ORDER BY created_at DESC
        """)
        rows = await cursor.fetchall()
        
        # Get live status from manager
        manager = get_obs_manager()
        live_state = manager.get_state()
        live_status_map = {s['connection_id']: s for s in live_state['connections']}
        
        connections = []
        for row in rows:
            conn_id, name, ws_url, auto_connect, enabled, roles_json, \
            last_status, last_error, last_seen_ts, created_at, updated_at = row
            
            conn = OBSConnectionResponse(
                id=conn_id,
                name=name,
                ws_url=ws_url,
                auto_connect=bool(auto_connect),
                enabled=bool(enabled),
                roles=json.loads(roles_json) if roles_json else [],
                last_status=last_status,
                last_error=last_error,
                last_seen_ts=last_seen_ts,
                created_at=created_at,
                updated_at=updated_at
            )
            
            # Add live status if available
            if conn_id in live_status_map:
                live = live_status_map[conn_id]
                conn.connected = live['connected']
                conn.recording = live['recording']
                conn.streaming = live['streaming']
                conn.current_scene = live['current_scene']
            
            connections.append(conn)
        
        return connections
        
    except Exception as e:
        logger.error(f"Failed to list OBS connections: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("", response_model=OBSConnectionResponse)
async def create_connection(
    connection: OBSConnection,
    db=Depends(get_db)
):
    """Create a new OBS connection"""
    try:
        # Check for duplicate URLs
        cursor = await db.execute(
            "SELECT id FROM so_obs_connections WHERE ws_url = ?",
            (connection.ws_url,)
        )
        existing = await cursor.fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Connection with this URL already exists")
        
        # Create connection
        conn_id = str(ULID())
        now = datetime.utcnow().isoformat()
        
        await db.execute("""
            INSERT INTO so_obs_connections
            (id, name, ws_url, password, auto_connect, enabled, roles_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            conn_id,
            connection.name,
            connection.ws_url,
            connection.password,
            1 if connection.auto_connect else 0,
            1,  # Enabled by default
            json.dumps(connection.roles),
            now,
            now
        ))
        await db.commit()
        
        logger.info(f"Created OBS connection: {connection.name} ({conn_id})")
        
        # Return created connection
        return OBSConnectionResponse(
            id=conn_id,
            name=connection.name,
            ws_url=connection.ws_url,
            auto_connect=connection.auto_connect,
            enabled=True,
            roles=connection.roles,
            last_status=None,
            last_error=None,
            last_seen_ts=None,
            created_at=now,
            updated_at=now
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create OBS connection: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{connection_id}", response_model=OBSConnectionResponse)
async def update_connection(
    connection_id: str,
    update: OBSConnectionUpdate,
    db=Depends(get_db)
):
    """Update an OBS connection"""
    try:
        # Get existing connection
        cursor = await db.execute(
            "SELECT * FROM so_obs_connections WHERE id = ?",
            (connection_id,)
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Connection not found")
        
        # Build update query
        updates = []
        params = []
        
        if update.name is not None:
            updates.append("name = ?")
            params.append(update.name)
        
        if update.ws_url is not None:
            # Check for duplicate URLs
            cursor = await db.execute(
                "SELECT id FROM so_obs_connections WHERE ws_url = ? AND id != ?",
                (update.ws_url, connection_id)
            )
            existing = await cursor.fetchone()
            if existing:
                raise HTTPException(status_code=400, detail="Connection with this URL already exists")
            
            updates.append("ws_url = ?")
            params.append(update.ws_url)
        
        if update.password is not None:
            updates.append("password = ?")
            params.append(update.password)
        
        if update.auto_connect is not None:
            updates.append("auto_connect = ?")
            params.append(1 if update.auto_connect else 0)
        
        if update.enabled is not None:
            updates.append("enabled = ?")
            params.append(1 if update.enabled else 0)
        
        if update.roles is not None:
            updates.append("roles_json = ?")
            params.append(json.dumps(update.roles))
        
        if not updates:
            raise HTTPException(status_code=400, detail="No updates provided")
        
        # Add updated_at
        updates.append("updated_at = ?")
        params.append(datetime.utcnow().isoformat())
        
        # Add connection_id for WHERE clause
        params.append(connection_id)
        
        # Execute update
        query = f"UPDATE so_obs_connections SET {', '.join(updates)} WHERE id = ?"
        await db.execute(query, params)
        await db.commit()
        
        # Get updated connection
        cursor = await db.execute("""
            SELECT id, name, ws_url, auto_connect, enabled, roles_json,
                   last_status, last_error, last_seen_ts, created_at, updated_at
            FROM so_obs_connections
            WHERE id = ?
        """, (connection_id,))
        row = await cursor.fetchone()
        
        conn_id, name, ws_url, auto_connect, enabled, roles_json, \
        last_status, last_error, last_seen_ts, created_at, updated_at = row
        
        return OBSConnectionResponse(
            id=conn_id,
            name=name,
            ws_url=ws_url,
            auto_connect=bool(auto_connect),
            enabled=bool(enabled),
            roles=json.loads(roles_json) if roles_json else [],
            last_status=last_status,
            last_error=last_error,
            last_seen_ts=last_seen_ts,
            created_at=created_at,
            updated_at=updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update OBS connection: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{connection_id}")
async def delete_connection(
    connection_id: str,
    db=Depends(get_db)
):
    """Delete an OBS connection"""
    try:
        # Disconnect if connected
        manager = get_obs_manager()
        await manager.disconnect(connection_id)
        
        # Delete from database
        result = await db.execute(
            "DELETE FROM so_obs_connections WHERE id = ?",
            (connection_id,)
        )
        await db.commit()
        
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Connection not found")
        
        logger.info(f"Deleted OBS connection: {connection_id}")
        
        return {"message": "Connection deleted"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete OBS connection: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{connection_id}/test")
async def test_connection(
    connection_id: str,
    db=Depends(get_db)
):
    """Test an OBS connection"""
    try:
        manager = get_obs_manager()
        result = await manager.test(connection_id)
        
        if result["ok"]:
            return {
                "ok": True,
                "obs_version": result.get("obs_version"),
                "websocket_version": result.get("websocket_version"),
                "scenes_count": result.get("scenes_count"),
                "profiles_count": result.get("profiles_count"),
                "collections_count": result.get("collections_count"),
                "current_scene": result.get("current_scene"),
                "message": f"Connected to OBS {result.get('obs_version', 'Unknown')} · Scenes {result.get('scenes_count', 0)} · Profiles {result.get('profiles_count', 0)}"
            }
        else:
            # Parse error for user-friendly message
            error = result.get("error", "Connection failed")
            
            if "auth" in error.lower() or "password" in error.lower():
                friendly_error = "Authentication failed - check password"
            elif "connection" in error.lower() or "refused" in error.lower():
                friendly_error = "Connection refused - check URL and ensure OBS WebSocket is enabled"
            elif "timeout" in error.lower():
                friendly_error = "Connection timeout - check network and firewall"
            else:
                friendly_error = error
            
            return {
                "ok": False,
                "error": friendly_error,
                "details": error
            }
        
    except Exception as e:
        logger.error(f"Failed to test OBS connection: {e}")
        return {
            "ok": False,
            "error": "Internal error",
            "details": str(e)
        }

@router.post("/{connection_id}/connect")
async def connect(
    connection_id: str,
    db=Depends(get_db)
):
    """Connect to an OBS instance"""
    try:
        manager = get_obs_manager()
        success = await manager.connect(connection_id)
        
        if success:
            return {"message": "Connected successfully"}
        else:
            client = manager.clients.get(connection_id)
            error = client.last_error if client else "Connection failed"
            raise HTTPException(status_code=400, detail=error)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to connect OBS: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{connection_id}/disconnect")
async def disconnect(
    connection_id: str
):
    """Disconnect from an OBS instance"""
    try:
        manager = get_obs_manager()
        success = await manager.disconnect(connection_id)
        
        if success:
            return {"message": "Disconnected successfully"}
        else:
            raise HTTPException(status_code=404, detail="Connection not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to disconnect OBS: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/clients/{client_name}/recording/start")
async def start_recording(client_name: str):
    """Start recording on an OBS instance"""
    try:
        manager = get_obs_manager()
        # Find the connection by name
        state = manager.get_state()
        connection = None
        for conn in state['connections']:
            if conn['name'] == client_name:
                connection = conn
                break
        
        if not connection:
            raise HTTPException(status_code=404, detail=f"OBS client '{client_name}' not found")
        
        if not connection.get('connected'):
            raise HTTPException(status_code=400, detail=f"OBS client '{client_name}' is not connected")
        
        # Get the actual client from manager
        if connection['connection_id'] not in manager.clients:
            raise HTTPException(status_code=404, detail="Client connection not found")
        
        client = manager.clients[connection['connection_id']]
        
        # Start recording
        await client.start_recording()
        return {"success": True, "message": f"Recording started on {client_name}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/clients/{client_name}/recording/stop")
async def stop_recording(client_name: str):
    """Stop recording on an OBS instance"""
    try:
        manager = get_obs_manager()
        # Find the connection by name
        state = manager.get_state()
        connection = None
        for conn in state['connections']:
            if conn['name'] == client_name:
                connection = conn
                break
        
        if not connection:
            raise HTTPException(status_code=404, detail=f"OBS client '{client_name}' not found")
        
        if not connection.get('connected'):
            raise HTTPException(status_code=400, detail=f"OBS client '{client_name}' is not connected")
        
        # Get the actual client from manager
        if connection['connection_id'] not in manager.clients:
            raise HTTPException(status_code=404, detail="Client connection not found")
        
        client = manager.clients[connection['connection_id']]
        
        # Stop recording
        await client.stop_recording()
        return {"success": True, "message": f"Recording stopped on {client_name}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stop recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/clients/{client_name}/streaming/start")
async def start_streaming(client_name: str):
    """Start streaming on an OBS instance"""
    try:
        manager = get_obs_manager()
        # Find the connection by name
        state = manager.get_state()
        connection = None
        for conn in state['connections']:
            if conn['name'] == client_name:
                connection = conn
                break
        
        if not connection:
            raise HTTPException(status_code=404, detail=f"OBS client '{client_name}' not found")
        
        if not connection.get('connected'):
            raise HTTPException(status_code=400, detail=f"OBS client '{client_name}' is not connected")
        
        # Get the actual client from manager
        if connection['connection_id'] not in manager.clients:
            raise HTTPException(status_code=404, detail="Client connection not found")
        
        client = manager.clients[connection['connection_id']]
        
        # Start streaming
        await client.start_streaming()
        return {"success": True, "message": f"Streaming started on {client_name}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start streaming: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/clients/{client_name}/streaming/stop")
async def stop_streaming(client_name: str):
    """Stop streaming on an OBS instance"""
    try:
        manager = get_obs_manager()
        # Find the connection by name
        state = manager.get_state()
        connection = None
        for conn in state['connections']:
            if conn['name'] == client_name:
                connection = conn
                break
        
        if not connection:
            raise HTTPException(status_code=404, detail=f"OBS client '{client_name}' not found")
        
        if not connection.get('connected'):
            raise HTTPException(status_code=400, detail=f"OBS client '{client_name}' is not connected")
        
        # Get the actual client from manager
        if connection['connection_id'] not in manager.clients:
            raise HTTPException(status_code=404, detail="Client connection not found")
        
        client = manager.clients[connection['connection_id']]
        
        # Stop streaming
        await client.stop_streaming()
        return {"success": True, "message": f"Streaming stopped on {client_name}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stop streaming: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_status():
    """Get overall OBS status"""
    try:
        manager = get_obs_manager()
        state = manager.get_state()
        
        # Build summary
        errors = []
        for conn in state['connections']:
            if conn.get('last_error'):
                errors.append({
                    'name': conn['name'],
                    'error': conn['last_error']
                })
        
        return {
            "connected": state['connected_count'],
            "disconnected": len(state['connections']) - state['connected_count'],
            "recording": state['recording_count'],
            "streaming": state['streaming_count'],
            "any_active": state['any_active'],
            "errors": errors,
            "connections": state['connections']
        }
        
    except Exception as e:
        logger.error(f"Failed to get OBS status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/capabilities/{connection_id}")
async def get_capabilities(
    connection_id: str,
    db=Depends(get_db)
):
    """Get detailed capabilities of an OBS instance"""
    try:
        # First ensure we have the connection
        cursor = await db.execute(
            "SELECT name FROM so_obs_connections WHERE id = ?",
            (connection_id,)
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Connection not found")
        
        manager = get_obs_manager()
        
        # Test connection to get capabilities
        result = await manager.test(connection_id)
        
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to connect"))
        
        # TODO: Add more detailed capabilities like recording folder path
        # This would require additional OBS API calls
        
        return {
            "obs_version": result.get("obs_version"),
            "websocket_version": result.get("websocket_version"),
            "scenes": {
                "count": result.get("scenes_count"),
                "current": result.get("current_scene")
            },
            "profiles": {
                "count": result.get("profiles_count"),
                "current": result.get("current_profile")
            },
            "collections": {
                "count": result.get("collections_count"),
                "current": result.get("current_collection")
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get OBS capabilities: {e}")
        raise HTTPException(status_code=500, detail=str(e))