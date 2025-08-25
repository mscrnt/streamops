from typing import Dict, Any
import os
import logging
import json
from pathlib import Path
from math import ceil

from app.worker.jobs.base import BaseJob

logger = logging.getLogger(__name__)

class ThumbnailJob(BaseJob):
    """Job processor for generating thumbnails, sprites, and hover previews"""
    
    async def process(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate thumbnails, sprite sheet, and hover preview for media file"""
        job_id = job_data.get("id")
        data = job_data.get("data", {})
        
        input_path = data.get("input_path")
        asset_id = data.get("asset_id")
        poster_time = data.get("poster_time", "00:00:05")  # Default 5 seconds in
        sprite_count = data.get("sprite_count", 10)  # Number of thumbnails in sprite
        hover_duration = data.get("hover_duration", 3)  # Hover preview duration
        
        if not input_path or not os.path.exists(input_path):
            raise ValueError(f"Input file not found: {input_path}")
        
        if not asset_id:
            raise ValueError("asset_id is required")
        
        # Create thumbnail directory
        thumbs_dir = os.getenv("THUMBS_DIR", "/data/thumbs")
        asset_thumbs_dir = os.path.join(thumbs_dir, str(asset_id))
        os.makedirs(asset_thumbs_dir, exist_ok=True)
        
        poster_path = os.path.join(asset_thumbs_dir, "poster.jpg")
        sprite_path = os.path.join(asset_thumbs_dir, "sprite.jpg")
        hover_path = os.path.join(asset_thumbs_dir, "hover.mp4")
        
        await self.update_progress(job_id, 10, "running")
        
        # Get video duration first
        duration_cmd = [
            "ffprobe",
            "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            input_path
        ]
        
        returncode, stdout, stderr = await self.run_command(duration_cmd)
        if returncode != 0:
            raise RuntimeError(f"Failed to get video duration: {stderr}")
        
        try:
            duration = float(stdout.strip())
        except ValueError:
            raise RuntimeError(f"Invalid duration: {stdout.strip()}")
        
        await self.update_progress(job_id, 20, "running")
        
        # Generate poster thumbnail
        logger.info(f"Generating poster thumbnail at {poster_time}")
        poster_cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-ss", poster_time,
            "-i", input_path,
            "-vframes", "1",
            "-vf", "scale=320:180:force_original_aspect_ratio=decrease,pad=320:180:(ow-iw)/2:(oh-ih)/2",
            "-q:v", "3",
            "-y", poster_path
        ]
        
        returncode, stdout, stderr = await self.run_command(poster_cmd)
        if returncode != 0:
            logger.error(f"Failed to generate poster: {stderr}")
            raise RuntimeError(f"Failed to generate poster: {stderr}")
        
        await self.update_progress(job_id, 40, "running")
        
        # Generate sprite sheet
        logger.info(f"Generating sprite sheet with {sprite_count} thumbnails")
        
        # Calculate time intervals for sprite thumbnails
        interval = duration / (sprite_count + 1)  # +1 to avoid the very end
        
        # Create individual thumbnails first
        temp_thumbs = []
        for i in range(sprite_count):
            time_offset = (i + 1) * interval
            temp_thumb = self.get_temp_path(job_id, f"_thumb_{i}.jpg")
            temp_thumbs.append(temp_thumb)
            
            thumb_cmd = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel", "error",
                "-ss", str(time_offset),
                "-i", input_path,
                "-vframes", "1",
                "-vf", "scale=160:90:force_original_aspect_ratio=decrease,pad=160:90:(ow-iw)/2:(oh-ih)/2",
                "-q:v", "3",
                "-y", temp_thumb
            ]
            
            returncode, stdout, stderr = await self.run_command(thumb_cmd)
            if returncode != 0:
                logger.warning(f"Failed to generate thumbnail {i}: {stderr}")
        
        # Create sprite sheet by tiling thumbnails
        valid_thumbs = [t for t in temp_thumbs if os.path.exists(t)]
        if valid_thumbs:
            # Calculate grid dimensions (try to make it roughly square)
            cols = ceil(len(valid_thumbs) ** 0.5)
            rows = ceil(len(valid_thumbs) / cols)
            
            # Create filter for tiling
            filter_inputs = []
            for i, thumb in enumerate(valid_thumbs):
                filter_inputs.extend(["-i", thumb])
            
            # Build tile filter
            tile_filter = f"tile={cols}x{rows}:margin=2:padding=2"
            
            sprite_cmd = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel", "error"
            ] + filter_inputs + [
                "-filter_complex", tile_filter,
                "-q:v", "3",
                "-y", sprite_path
            ]
            
            returncode, stdout, stderr = await self.run_command(sprite_cmd)
            if returncode != 0:
                logger.warning(f"Failed to generate sprite sheet: {stderr}")
        
        await self.update_progress(job_id, 70, "running")
        
        # Generate hover preview (short clip from middle)
        hover_start = max(0, duration / 2 - hover_duration / 2)
        logger.info(f"Generating hover preview ({hover_duration}s from {hover_start}s)")
        
        hover_cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-ss", str(hover_start),
            "-t", str(hover_duration),
            "-i", input_path,
            "-vf", "scale=320:180:force_original_aspect_ratio=decrease,pad=320:180:(ow-iw)/2:(oh-ih)/2",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "28",
            "-an",  # No audio for hover preview
            "-movflags", "+faststart",
            "-y", hover_path
        ]
        
        returncode, stdout, stderr = await self.run_command(hover_cmd)
        if returncode != 0:
            logger.warning(f"Failed to generate hover preview: {stderr}")
        
        # Clean up temporary files
        self.cleanup_temp_files(job_id)
        
        await self.update_progress(job_id, 100, "completed")
        
        # Check what was actually created
        results = {
            "success": True,
            "asset_id": asset_id,
            "poster_path": poster_path if os.path.exists(poster_path) else None,
            "sprite_path": sprite_path if os.path.exists(sprite_path) else None,
            "hover_path": hover_path if os.path.exists(hover_path) else None,
            "duration": duration
        }
        
        created_files = [f for f in [results["poster_path"], results["sprite_path"], results["hover_path"]] if f]
        logger.info(f"Generated {len(created_files)} thumbnail files for asset {asset_id}")
        
        return results