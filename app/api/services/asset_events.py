"""Asset event sourcing service for tracking asset history."""
import hashlib
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from ulid import ULID

from app.api.db.database import get_db

logger = logging.getLogger(__name__)


class AssetEventService:
    """Service for managing asset events (event sourcing)."""
    
    @staticmethod
    def generate_event_id(asset_id: str, event_type: str, job_id: Optional[str] = None) -> str:
        """Generate deterministic event ID for idempotency."""
        components = [asset_id, event_type]
        if job_id:
            components.append(job_id)
        hash_input = ":".join(components)
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]
    
    @classmethod
    async def emit_event(
        cls,
        asset_id: str,
        event_type: str,
        payload: Dict[str, Any],
        job_id: Optional[str] = None
    ) -> bool:
        """Emit an asset event (idempotent)."""
        try:
            db = await get_db()
            event_id = cls.generate_event_id(asset_id, event_type, job_id)
            
            # Check if event already exists (idempotency)
            cursor = await db.execute(
                "SELECT id FROM so_asset_events WHERE id = ?",
                (event_id,)
            )
            if await cursor.fetchone():
                logger.debug(f"Event {event_id} already exists, skipping")
                return True
            
            # Insert new event
            await db.execute(
                """
                INSERT INTO so_asset_events (id, asset_id, event_type, payload_json, job_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    asset_id,
                    event_type,
                    json.dumps(payload),
                    job_id,
                    datetime.utcnow().isoformat()
                )
            )
            await db.commit()
            
            logger.info(f"Emitted {event_type} event for asset {asset_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to emit event: {e}")
            return False
    
    @classmethod
    async def get_asset_timeline(cls, asset_id: str) -> List[Dict[str, Any]]:
        """Get timeline of events for an asset."""
        try:
            db = await get_db()
            cursor = await db.execute(
                """
                SELECT event_type, payload_json, job_id, created_at
                FROM so_asset_events
                WHERE asset_id = ?
                ORDER BY created_at ASC
                """,
                (asset_id,)
            )
            
            events = []
            rows = await cursor.fetchall()
            for row in rows:
                events.append({
                    "event_type": row[0],
                    "payload": json.loads(row[1]),
                    "job_id": row[2],
                    "created_at": row[3]
                })
            
            return events
            
        except Exception as e:
            logger.error(f"Failed to get timeline for asset {asset_id}: {e}")
            return []
    
    @classmethod
    async def emit_recorded_event(cls, asset_id: str, file_path: str, metadata: Dict[str, Any]) -> bool:
        """Emit a 'recorded' event when file is indexed."""
        payload = {
            "path": file_path,
            "duration": metadata.get("duration_sec", 0),
            "size": metadata.get("size", 0),
            "container": metadata.get("container", ""),
            "video_codec": metadata.get("video_codec", ""),
            "audio_codec": metadata.get("audio_codec", "")
        }
        return await cls.emit_event(asset_id, "recorded", payload)
    
    @classmethod
    async def emit_remux_completed(cls, asset_id: str, job_id: str, from_path: str, to_path: str, output_size: int) -> bool:
        """Emit a 'remux_completed' event."""
        payload = {
            "from": from_path,
            "to": to_path,
            "size": output_size
        }
        return await cls.emit_event(asset_id, "remux_completed", payload, job_id)
    
    @classmethod
    async def emit_move_completed(cls, asset_id: str, from_path: str, to_path: str) -> bool:
        """Emit a 'move_completed' event."""
        payload = {
            "from": from_path,
            "to": to_path
        }
        return await cls.emit_event(asset_id, "move_completed", payload)
    
    @classmethod
    async def emit_proxy_completed(cls, asset_id: str, job_id: str, output_path: str, profile: str, resolution: str, size: int) -> bool:
        """Emit a 'proxy_completed' event."""
        payload = {
            "output": output_path,
            "profile": profile,
            "resolution": resolution,
            "size": size
        }
        return await cls.emit_event(asset_id, "proxy_completed", payload, job_id)
    
    @classmethod
    async def emit_error_event(cls, asset_id: str, job_id: str, action: str, error_message: str, stage: str = "unknown") -> bool:
        """Emit an 'error' event."""
        payload = {
            "action": action,
            "message": error_message,
            "stage": stage
        }
        return await cls.emit_event(asset_id, "error", payload, job_id)