"""Index job for cataloging media assets"""
import os
import json
import logging
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import asyncio
import aiosqlite
from ulid import ULID

logger = logging.getLogger(__name__)

class IndexJob:
    """Job processor for indexing media assets"""
    
    async def process(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Index a media file into the database"""
        logger.info(f"IndexJob received job_data: {job_data}")
        
        job_id = job_data.get("id")
        data = job_data.get("data", {})
        
        # Handle double-nested data structure
        if "data" in data and isinstance(data.get("data"), dict):
            logger.info("Detected nested data structure, extracting inner data")
            data = data["data"]
        
        logger.info(f"Extracted data: {data}")
        
        file_path = data.get("file_path")
        if not file_path:
            logger.error(f"No file_path in data. Full job_data: {job_data}")
            raise ValueError(f"No file_path provided in job data")
        
        if not os.path.exists(file_path):
            logger.error(f"File does not exist: {file_path}")
            raise ValueError(f"File not found: {file_path}")
        
        logger.info(f"Indexing file: {file_path}")
        
        # Get basic file info
        file_stat = os.stat(file_path)
        file_size = file_stat.st_size
        file_mtime = file_stat.st_mtime
        file_ctime = file_stat.st_ctime
        
        # Get database connection
        from app.api.db.database import get_db
        db = await get_db()
        
        # Check if already indexed
        cursor = await db.execute(
            "SELECT id, mtime FROM so_assets WHERE abs_path = ?",
            (file_path,)
        )
        existing = await cursor.fetchone()
        
        if existing:
            # Check if file has been modified
            if existing[1] and existing[1] >= file_mtime:
                logger.info(f"Asset already indexed and up to date: {file_path}")
                return {"success": True, "asset_id": existing[0], "action": "skipped"}
        
        # Extract basic media info with ffprobe
        media_info = await self._get_media_info(file_path)
        
        # Classify asset type based on extension and MIME type
        ext = (Path(file_path).suffix or "").lower()
        mime, _ = mimetypes.guess_type(file_path)
        
        def classify(ext: str, mime: str | None) -> str:
            if mime:
                if mime.startswith("video/"): return "video"
                if mime.startswith("audio/"): return "audio"
                if mime.startswith("image/"): return "image"
                if mime in ("application/pdf",): return "document"
            # fallback by extension
            if ext in [".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".mpg", ".mpeg", ".wmv", ".flv"]: return "video"
            if ext in [".wav", ".mp3", ".flac", ".aac", ".ogg", ".m4a", ".wma"]: return "audio"
            if ext in [".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff"]: return "image"
            if ext in [".pdf", ".doc", ".docx", ".txt", ".md", ".rtf"]: return "document"
            return "unknown"
        
        asset_type = classify(ext, mime)
        
        # Calculate quick hash if enabled (for deduplication)
        file_hash = None
        if data.get("calculate_hash", False):
            file_hash = await self._calculate_quick_hash(file_path)
        
        # Generate asset ID or use existing
        asset_id = existing[0] if existing else str(ULID())
        
        # Check if this is a proxy file by filename pattern
        parent_asset_id = None
        filename = os.path.basename(file_path)
        if '_proxy_' in filename:
            # Try to find parent asset by matching the base filename
            base_name = filename.split('_proxy_')[0]
            # Look for parent asset with similar path
            parent_dir = os.path.dirname(file_path)
            cursor = await db.execute("""
                SELECT id FROM so_assets 
                WHERE dir_path = ? 
                AND filename LIKE ?
                AND parent_asset_id IS NULL
                ORDER BY created_at DESC
                LIMIT 1
            """, (parent_dir, f"{base_name}%"))
            parent_row = await cursor.fetchone()
            if parent_row:
                parent_asset_id = parent_row[0]
                logger.info(f"Detected proxy file, linking to parent asset {parent_asset_id}")
        
        # Prepare the data
        now = datetime.utcnow().isoformat()
        
        if existing:
            # Update existing asset - also set current_path if it's null
            await db.execute("""
                UPDATE so_assets SET
                    size_bytes = ?, mtime = ?, ctime = ?,
                    hash = ?,
                    duration_s = ?, video_codec = ?, audio_codec = ?, 
                    width = ?, height = ?, fps = ?, has_audio = ?, container = ?,
                    streams_json = ?, indexed_at = ?, updated_at = ?,
                    current_path = COALESCE(current_path, ?)
                WHERE id = ?
            """, (
                file_size, file_mtime, file_ctime,
                file_hash,
                media_info.get("duration"),
                media_info.get("video_codec"),
                media_info.get("audio_codec"),
                media_info.get("width"),
                media_info.get("height"),
                media_info.get("fps"),
                1 if media_info.get("audio_codec") else 0,
                media_info.get("container"),
                json.dumps({**media_info.get("streams_data", {}), "type": asset_type, "streams": media_info.get("streams", [])}),
                now,
                now,
                file_path,  # Set current_path to file_path if it's null
                asset_id
            ))
            action = "updated"
        else:
            # Insert new asset - set current_path to abs_path initially
            await db.execute("""
                INSERT INTO so_assets (
                    id, abs_path, current_path, parent_asset_id, dir_path, filename, size_bytes, mtime, ctime,
                    hash, duration_s, video_codec, audio_codec, 
                    width, height, fps, has_audio, container,
                    streams_json, tags_json, status, indexed_at,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                asset_id, 
                file_path,
                file_path,  # Set current_path to the same as abs_path initially
                parent_asset_id,  # Link to parent if this is a proxy
                os.path.dirname(file_path),
                os.path.basename(file_path),
                file_size, file_mtime, file_ctime,
                file_hash,
                media_info.get("duration"),
                media_info.get("video_codec"),
                media_info.get("audio_codec"),
                media_info.get("width"),
                media_info.get("height"),
                media_info.get("fps"),
                1 if media_info.get("audio_codec") else 0,
                media_info.get("container"),
                json.dumps({**media_info.get("streams_data", {}), "type": "proxy" if parent_asset_id else asset_type, "streams": media_info.get("streams", [])}),
                json.dumps(["proxy"] if parent_asset_id else []),  # Add proxy tag if it's a proxy
                'ready',  # status
                now,
                now, now
            ))
            action = "created"
        
        await db.commit()
        
        # Emit asset event for recording (skip for proxy files)
        if action == "created" and not parent_asset_id:
            try:
                from app.api.services.asset_events import AssetEventService
                await AssetEventService.emit_recorded_event(
                    asset_id,
                    file_path,
                    {
                        "duration_sec": media_info.get("duration"),
                        "size": file_size,
                        "container": media_info.get("container"),
                        "video_codec": media_info.get("video_codec"),
                        "audio_codec": media_info.get("audio_codec")
                    }
                )
            except Exception as e:
                logger.debug(f"Could not emit recorded event: {e}")
        
        # Notify about new asset via SSE (skip for proxy files)
        if action == "created" and not parent_asset_id:
            try:
                # Import the broadcast function from events router
                from app.api.routers.events import notify_new_asset
                # Fire and forget the notification
                asyncio.create_task(notify_new_asset(asset_id, file_path))
                logger.info(f"Notified clients about new asset: {asset_id}")
            except Exception as e:
                logger.debug(f"Could not notify about new asset: {e}")
                
            try:
                # Trigger automation rules for new assets
                from app.worker.rules.engine import RulesEngine
                
                # Get full asset data for rule evaluation
                conn = await aiosqlite.connect("/data/db/streamops.db")
                cursor = await conn.execute(
                    "SELECT * FROM so_assets WHERE id = ?", (asset_id,)
                )
                row = await cursor.fetchone()
                await conn.close()
                
                if row:
                    # Convert row to dict
                    columns = [col[0] for col in cursor.description]
                    asset_data = dict(zip(columns, row))
                    
                    # Initialize rule engine
                    from app.api.services.nats_service import NATSService
                    nats = NATSService()
                    await nats.connect()
                    
                    rule_engine = RulesEngine(nats_service=nats)
                    await rule_engine.load_rules()
                    
                    # Create event data for rule evaluation
                    event_data = {
                        'asset_id': asset_id,
                        'file_path': file_path,
                        'path': file_path,  # Add path for rule engine compatibility
                        'file': {
                            'path': file_path,
                            'name': Path(file_path).name,
                            'extension': Path(file_path).suffix,
                            'container': asset_data.get('container', ''),
                            'size': asset_data.get('size', 0),
                            'duration': asset_data.get('duration', 0),
                        },
                        **asset_data
                    }
                    
                    # Evaluate rules with file_closed event
                    await rule_engine.evaluate_event('file_closed', event_data)
                    logger.info(f"Triggered rule evaluation for asset {asset_id}")
                        
            except Exception as e:
                logger.error(f"Error triggering rules for asset {asset_id}: {e}")
        
        logger.info(f"Successfully {action} asset: {file_path} as {asset_id}")
        return {"success": True, "asset_id": asset_id, "action": action}
    
    async def _get_media_info(self, file_path: str) -> Dict[str, Any]:
        """Extract media info using ffprobe"""
        try:
            cmd = [
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_format", "-show_streams", file_path
            ]
            
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                logger.warning(f"ffprobe failed for {file_path}: {stderr.decode()}")
                return {}
            
            data = json.loads(stdout)
            
            # Extract key info
            info = {}
            
            # Get format info
            if "format" in data:
                fmt = data["format"]
                info["duration"] = float(fmt.get("duration", 0))
                info["container"] = fmt.get("format_name", "").split(",")[0]
                info["size"] = int(fmt.get("size", 0))
            
            # Get stream info
            info["streams"] = []
            info["streams_data"] = {}  # Additional data to merge into streams_json
            for stream in data.get("streams", []):
                stream_info = {
                    "index": stream.get("index"),
                    "codec_type": stream.get("codec_type"),
                    "codec_name": stream.get("codec_name")
                }
                
                if stream.get("codec_type") == "video" and not info.get("video_codec"):
                    info["video_codec"] = stream.get("codec_name")
                    info["width"] = stream.get("width")
                    info["height"] = stream.get("height")
                    
                    # Calculate FPS
                    if stream.get("r_frame_rate"):
                        try:
                            num, den = stream["r_frame_rate"].split("/")
                            info["fps"] = float(num) / float(den) if float(den) != 0 else 0
                        except:
                            pass
                
                elif stream.get("codec_type") == "audio" and not info.get("audio_codec"):
                    info["audio_codec"] = stream.get("codec_name")
                
                info["streams"].append(stream_info)
            
            return info
            
        except Exception as e:
            logger.error(f"Failed to get media info for {file_path}: {e}")
            return {}
    
    async def _calculate_quick_hash(self, file_path: str, sample_size: int = 65536) -> Optional[str]:
        """Calculate a quick xxhash of the file (first 64KB by default)"""
        try:
            import xxhash
            
            x = xxhash.xxh64()
            with open(file_path, 'rb') as f:
                # Read first chunk for quick hash
                chunk = f.read(sample_size)
                if chunk:
                    x.update(chunk)
            
            return x.hexdigest()
            
        except ImportError:
            logger.warning("xxhash not available, skipping quick hash")
            return None
        except Exception as e:
            logger.error(f"Failed to calculate hash for {file_path}: {e}")
            return None
    
    async def _calculate_full_hash(self, file_path: str) -> Optional[str]:
        """Calculate full SHA256 hash of the file (for future use)"""
        try:
            import hashlib
            
            sha256 = hashlib.sha256()
            with open(file_path, 'rb') as f:
                # Read in chunks to handle large files
                while chunk := f.read(8192):
                    sha256.update(chunk)
            
            return sha256.hexdigest()
            
        except Exception as e:
            logger.error(f"Failed to calculate SHA256 for {file_path}: {e}")
            return None