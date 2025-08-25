from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from typing import Set, Dict, Any
import json
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter()

# Store active WebSocket connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.subscriptions: Dict[WebSocket, Set[str]] = {}
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        self.subscriptions[websocket] = set()
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        self.subscriptions.pop(websocket, None)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    def subscribe(self, websocket: WebSocket, channels: list):
        """Subscribe a websocket to specific channels"""
        if websocket in self.subscriptions:
            self.subscriptions[websocket].update(channels)
            logger.debug(f"WebSocket subscribed to channels: {channels}")
    
    def unsubscribe(self, websocket: WebSocket, channels: list):
        """Unsubscribe a websocket from specific channels"""
        if websocket in self.subscriptions:
            self.subscriptions[websocket].difference_update(channels)
            logger.debug(f"WebSocket unsubscribed from channels: {channels}")
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send a message to a specific client"""
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending message to client: {e}")
            self.disconnect(websocket)
    
    async def broadcast(self, message: str, channel: str = None):
        """Broadcast a message to all connected clients or those subscribed to a channel"""
        disconnected = []
        for connection in self.active_connections:
            # If channel specified, only send to subscribed clients
            if channel and channel not in self.subscriptions.get(connection, set()):
                continue
            
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error broadcasting to client: {e}")
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)
    
    async def broadcast_event(self, event_type: str, payload: Dict[str, Any], channel: str = None):
        """Broadcast an event with payload"""
        message = json.dumps({
            "type": event_type,
            "payload": payload,
            "timestamp": datetime.utcnow().isoformat()
        })
        await self.broadcast(message, channel)

# Global connection manager
manager = ConnectionManager()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    
    try:
        # Send initial connection confirmation
        await manager.send_personal_message(
            json.dumps({
                "type": "connection.established",
                "payload": {"status": "connected"},
                "timestamp": datetime.utcnow().isoformat()
            }),
            websocket
        )
        
        while True:
            # Receive messages from client
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                msg_type = message.get("type")
                payload = message.get("payload", {})
                
                # Handle different message types
                if msg_type == "subscribe":
                    channels = payload.get("channels", [])
                    manager.subscribe(websocket, channels)
                    await manager.send_personal_message(
                        json.dumps({
                            "type": "subscription.confirmed",
                            "payload": {"channels": channels},
                            "timestamp": datetime.utcnow().isoformat()
                        }),
                        websocket
                    )
                
                elif msg_type == "unsubscribe":
                    channels = payload.get("channels", [])
                    manager.unsubscribe(websocket, channels)
                    await manager.send_personal_message(
                        json.dumps({
                            "type": "unsubscription.confirmed",
                            "payload": {"channels": channels},
                            "timestamp": datetime.utcnow().isoformat()
                        }),
                        websocket
                    )
                
                elif msg_type == "ping":
                    # Respond to ping with pong
                    await manager.send_personal_message(
                        json.dumps({
                            "type": "pong",
                            "timestamp": datetime.utcnow().isoformat()
                        }),
                        websocket
                    )
                
                else:
                    logger.warning(f"Unknown message type: {msg_type}")
                    
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON received: {data}")
                await manager.send_personal_message(
                    json.dumps({
                        "type": "error",
                        "payload": {"message": "Invalid JSON format"},
                        "timestamp": datetime.utcnow().isoformat()
                    }),
                    websocket
                )
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)

# Export the manager so other parts of the app can broadcast events
def get_ws_manager():
    return manager