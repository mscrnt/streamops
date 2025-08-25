from typing import Dict, Any
import os
import logging
import json
import hashlib
from pathlib import Path
from datetime import datetime

from app.worker.jobs.base import BaseJob

logger = logging.getLogger(__name__)

class IndexJob(BaseJob):
    """Job processor for indexing assets in database"""
    
    async def process(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Index media asset with metadata in database"""
        job_id = job_data.get("id")
        data = job_data.get("data", {})
        
        file_path = data.get("file_path")
        force_reindex = data.get("force_reindex", False)
        extract_scenes = data.get("extract_scenes", False)
        
        if not file_path or not os.path.exists(file_path):
            raise ValueError(f"File not found: {file_path}")
        
        await self.update_progress(job_id, 10, "running")
        
        # Get file basic info
        file_stat = os.stat(file_path)
        file_size = file_stat.st_size
        file_mtime = datetime.fromtimestamp(file_stat.st_mtime)
        
        # Calculate file hash for deduplication
        file_hash = await self.calculate_file_hash(file_path)
        
        await self.update_progress(job_id, 20, "running")
        
        # Check if asset already exists
        from app.api.db.database import get_db
        db = await get_db()
        
        existing_query = """
            SELECT id, file_hash, file_mtime, metadata 
            FROM so_assets 
            WHERE file_path = ? OR file_hash = ?
        """
        
        cursor = await db.execute(existing_query, [file_path, file_hash])
        existing_asset = await cursor.fetchone()
        
        if existing_asset and not force_reindex:
            # Check if file has been modified
            existing_mtime = datetime.fromisoformat(existing_asset["file_mtime"]) if existing_asset["file_mtime"] else None
            
            if existing_mtime and existing_mtime >= file_mtime:
                logger.info(f"Asset already indexed and up to date: {file_path}")
                await self.update_progress(job_id, 100, "completed")
                return {
                    "success": True,
                    "asset_id": existing_asset["id"],
                    "action": "skipped",
                    "reason": "already_indexed"
                }
        
        await self.update_progress(job_id, 30, "running")
        
        # Extract media metadata using FFprobe
        metadata = await self.extract_media_metadata(file_path)
        
        await self.update_progress(job_id, 50, "running")
        
        # Extract additional metadata
        additional_metadata = await self.extract_additional_metadata(file_path, metadata)
        metadata.update(additional_metadata)
        
        await self.update_progress(job_id, 70, "running")
        
        # Extract scenes if requested
        scenes = []
        if extract_scenes and self.is_video_file(file_path):
            try:
                scenes = await self.extract_scene_data(file_path)
            except Exception as e:
                logger.warning(f"Failed to extract scenes: {e}")
        
        await self.update_progress(job_id, 80, "running")
        
        # Prepare asset data
        asset_data = {
            "file_path": file_path,
            "file_name": os.path.basename(file_path),
            "file_size": file_size,
            "file_hash": file_hash,
            "file_mtime": file_mtime.isoformat(),
            "duration": metadata.get("duration"),
            "width": metadata.get("width"),
            "height": metadata.get("height"),
            "fps": metadata.get("fps"),
            "video_codec": metadata.get("video_codec"),
            "audio_codec": metadata.get("audio_codec"),
            "bitrate": metadata.get("bitrate"),
            "metadata": json.dumps(metadata),
            "scenes_data": json.dumps(scenes) if scenes else None,
            "indexed_at": datetime.utcnow().isoformat()
        }
        
        # Insert or update asset
        if existing_asset:
            # Update existing asset
            update_query = """
                UPDATE so_assets SET
                    file_size = ?, file_hash = ?, file_mtime = ?,
                    duration = ?, width = ?, height = ?, fps = ?,
                    video_codec = ?, audio_codec = ?, bitrate = ?,
                    metadata = ?, scenes_data = ?, indexed_at = ?
                WHERE id = ?
            """
            
            update_params = [
                asset_data["file_size"], asset_data["file_hash"], asset_data["file_mtime"],
                asset_data["duration"], asset_data["width"], asset_data["height"], asset_data["fps"],
                asset_data["video_codec"], asset_data["audio_codec"], asset_data["bitrate"],
                asset_data["metadata"], asset_data["scenes_data"], asset_data["indexed_at"],
                existing_asset["id"]
            ]
            
            await db.execute(update_query, update_params)
            asset_id = existing_asset["id"]
            action = "updated"
            
        else:
            # Insert new asset
            insert_query = """
                INSERT INTO so_assets (
                    file_path, file_name, file_size, file_hash, file_mtime,
                    duration, width, height, fps, video_codec, audio_codec,
                    bitrate, metadata, scenes_data, indexed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            insert_params = [
                asset_data["file_path"], asset_data["file_name"], asset_data["file_size"],
                asset_data["file_hash"], asset_data["file_mtime"], asset_data["duration"],
                asset_data["width"], asset_data["height"], asset_data["fps"],
                asset_data["video_codec"], asset_data["audio_codec"], asset_data["bitrate"],
                asset_data["metadata"], asset_data["scenes_data"], asset_data["indexed_at"]
            ]
            
            cursor = await db.execute(insert_query, insert_params)
            asset_id = cursor.lastrowid
            action = "created"
        
        await db.commit()
        
        # Update full-text search index
        try:
            fts_query = """
                INSERT OR REPLACE INTO so_assets_fts (
                    rowid, file_name, file_path, metadata_text
                ) VALUES (?, ?, ?, ?)
            """
            
            # Create searchable text from metadata
            searchable_text = " ".join([
                asset_data["file_name"],
                str(metadata.get("title", "")),
                str(metadata.get("comment", "")),
                str(metadata.get("creation_time", ""))
            ])
            
            await db.execute(fts_query, [asset_id, asset_data["file_name"], asset_data["file_path"], searchable_text])
            await db.commit()
            
        except Exception as e:
            logger.warning(f"Failed to update FTS index: {e}")
        
        await self.update_progress(job_id, 100, "completed")
        
        logger.info(f"Successfully indexed asset {asset_id}: {file_path}")
        
        return {
            "success": True,
            "asset_id": asset_id,
            "action": action,
            "file_path": file_path,
            "file_size": file_size,
            "duration": metadata.get("duration"),
            "resolution": f"{metadata.get('width', 0)}x{metadata.get('height', 0)}" if metadata.get('width') else None,
            "video_codec": metadata.get("video_codec"),
            "audio_codec": metadata.get("audio_codec"),
            "scenes_count": len(scenes) if scenes else 0
        }
    
    async def calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA-256 hash of file"""
        hash_sha256 = hashlib.sha256()
        
        # For large files, only hash first and last chunks for performance
        file_size = os.path.getsize(file_path)
        chunk_size = 64 * 1024  # 64KB chunks
        
        with open(file_path, "rb") as f:
            if file_size > 100 * 1024 * 1024:  # Files larger than 100MB
                # Hash first chunk
                chunk = f.read(chunk_size)
                hash_sha256.update(chunk)
                
                # Hash middle chunk
                f.seek(file_size // 2)
                chunk = f.read(chunk_size)
                hash_sha256.update(chunk)
                
                # Hash last chunk
                f.seek(-chunk_size, 2)
                chunk = f.read(chunk_size)
                hash_sha256.update(chunk)
                
            else:
                # Hash entire file for smaller files
                while chunk := f.read(chunk_size):
                    hash_sha256.update(chunk)
        
        return hash_sha256.hexdigest()
    
    async def extract_media_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extract media metadata using FFprobe"""
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            file_path
        ]
        
        returncode, stdout, stderr = await self.run_command(cmd)
        if returncode != 0:
            logger.warning(f"FFprobe failed for {file_path}: {stderr}")
            return {}
        
        try:
            probe_data = json.loads(stdout)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse FFprobe output for {file_path}")
            return {}
        
        metadata = {}
        
        # Extract format information
        format_info = probe_data.get("format", {})
        metadata.update({
            "duration": float(format_info.get("duration", 0)) if format_info.get("duration") else None,
            "bitrate": int(format_info.get("bit_rate", 0)) if format_info.get("bit_rate") else None,
            "format_name": format_info.get("format_name"),
            "format_long_name": format_info.get("format_long_name")
        })
        
        # Extract format tags
        format_tags = format_info.get("tags", {})
        for key, value in format_tags.items():
            metadata[f"tag_{key.lower()}"] = value
        
        # Extract stream information
        streams = probe_data.get("streams", [])
        video_stream = None
        audio_streams = []
        
        for stream in streams:
            if stream.get("codec_type") == "video":
                video_stream = stream
            elif stream.get("codec_type") == "audio":
                audio_streams.append(stream)
        
        # Video stream metadata
        if video_stream:
            metadata.update({
                "width": video_stream.get("width"),
                "height": video_stream.get("height"),
                "fps": self.parse_fps(video_stream.get("r_frame_rate")),
                "video_codec": video_stream.get("codec_name"),
                "video_profile": video_stream.get("profile"),
                "pixel_format": video_stream.get("pix_fmt"),
                "aspect_ratio": video_stream.get("display_aspect_ratio")
            })
        
        # Audio stream metadata (first stream)
        if audio_streams:
            audio_stream = audio_streams[0]
            metadata.update({
                "audio_codec": audio_stream.get("codec_name"),
                "sample_rate": audio_stream.get("sample_rate"),
                "channels": audio_stream.get("channels"),
                "channel_layout": audio_stream.get("channel_layout")
            })
            
            # Include info about all audio streams
            metadata["audio_streams_count"] = len(audio_streams)
        
        return metadata
    
    async def extract_additional_metadata(self, file_path: str, existing_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Extract additional metadata like file type classification"""
        path = Path(file_path)
        
        additional = {
            "file_extension": path.suffix.lower(),
            "is_video": self.is_video_file(file_path),
            "is_audio": self.is_audio_file(file_path),
            "is_image": self.is_image_file(file_path)
        }
        
        # Classify content type
        if additional["is_video"]:
            additional["content_type"] = "video"
        elif additional["is_audio"]:
            additional["content_type"] = "audio"
        elif additional["is_image"]:
            additional["content_type"] = "image"
        else:
            additional["content_type"] = "unknown"
        
        # Estimate quality category based on resolution
        if existing_metadata.get("width") and existing_metadata.get("height"):
            width = existing_metadata["width"]
            height = existing_metadata["height"]
            
            if height >= 2160:
                additional["quality_category"] = "4k"
            elif height >= 1080:
                additional["quality_category"] = "hd"
            elif height >= 720:
                additional["quality_category"] = "hd"
            else:
                additional["quality_category"] = "sd"
        
        return additional
    
    async def extract_scene_data(self, file_path: str) -> list:
        """Extract scene detection data (simplified version)"""
        # This is a simplified scene detection - in production you'd use PySceneDetect
        cmd = [
            "ffprobe",
            "-f", "lavfi",
            "-i", f"movie={file_path},select=gt(scene\\,0.3)",
            "-show_entries", "frame=pkt_pts_time",
            "-of", "csv=p=0",
            "-v", "quiet"
        ]
        
        returncode, stdout, stderr = await self.run_command(cmd)
        if returncode != 0:
            return []
        
        scene_times = []
        for line in stdout.strip().split('\n'):
            if line:
                try:
                    time_val = float(line)
                    scene_times.append({"time": time_val, "type": "cut"})
                except ValueError:
                    continue
        
        return scene_times[:50]  # Limit to 50 scenes
    
    def is_video_file(self, file_path: str) -> bool:
        """Check if file is a video file"""
        video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg'}
        return Path(file_path).suffix.lower() in video_extensions
    
    def is_audio_file(self, file_path: str) -> bool:
        """Check if file is an audio file"""
        audio_extensions = {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma'}
        return Path(file_path).suffix.lower() in audio_extensions
    
    def is_image_file(self, file_path: str) -> bool:
        """Check if file is an image file"""
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
        return Path(file_path).suffix.lower() in image_extensions
    
    def parse_fps(self, fps_str) -> float:
        """Parse FPS from fraction string"""
        if not fps_str:
            return None
        
        try:
            if '/' in fps_str:
                num, den = fps_str.split('/')
                return round(float(num) / float(den), 2)
            return float(fps_str)
        except:
            return None