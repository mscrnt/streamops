"""Server-Sent Events for real-time updates"""
import asyncio
import json
import logging
from typing import AsyncGenerator
from datetime import datetime
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/events", tags=["events"])

# Global event queue for broadcasting
event_queues = []

async def broadcast_event(event_type: str, data: dict):
    """Broadcast an event to all connected clients"""
    event = {
        "type": event_type,
        "data": data,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Send to all connected clients
    for queue in event_queues:
        try:
            await queue.put(event)
        except:
            # Queue might be closed, ignore
            pass

@router.get("/stream")
async def event_stream(request: Request):
    """SSE endpoint for real-time updates"""
    async def event_generator():
        queue = asyncio.Queue()
        event_queues.append(queue)
        
        try:
            # Send initial connection event
            yield f"event: connected\ndata: {json.dumps({'message': 'Connected to event stream'})}\n\n"
            
            # Send events as they come
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break
                
                try:
                    # Wait for events with timeout to check disconnection
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"event: {event['type']}\ndata: {json.dumps(event['data'])}\n\n"
                except asyncio.TimeoutError:
                    # Send heartbeat
                    yield f"event: heartbeat\ndata: {json.dumps({'timestamp': datetime.utcnow().isoformat()})}\n\n"
                    
        except asyncio.CancelledError:
            logger.info("Client disconnected from event stream")
        finally:
            # Remove queue from list
            if queue in event_queues:
                event_queues.remove(queue)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )

# Helper function to notify about new assets
async def notify_new_asset(asset_id: str, filepath: str):
    """Notify clients about a new asset"""
    await broadcast_event("asset.created", {
        "asset_id": asset_id,
        "filepath": filepath,
        "message": f"New asset indexed: {filepath.split('/')[-1]}"
    })

# Helper function to notify about recording state changes
async def notify_recording_state(is_recording: bool, connection_name: str = None):
    """Notify clients about recording state changes"""
    await broadcast_event("recording.state", {
        "is_recording": is_recording,
        "connection_name": connection_name,
        "message": f"Recording {'started' if is_recording else 'stopped'}"
    })