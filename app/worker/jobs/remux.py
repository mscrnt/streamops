from typing import Dict, Any
import os
import logging
from pathlib import Path
import subprocess

from app.worker.jobs.base import BaseJob

logger = logging.getLogger(__name__)

class RemuxJob(BaseJob):
    """Job processor for remuxing media files"""
    
    async def process(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Remux media file to new container format"""
        logger.info(f"RemuxJob received job_data: {job_data}")
        job_id = job_data.get("id")
        data = job_data.get("data", {})
        logger.info(f"RemuxJob extracted data: {data}")
        
        input_path = data.get("input_path")
        logger.info(f"RemuxJob input_path: {input_path}")
        output_format = data.get("output_format", "mov")
        output_path = data.get("output_path")
        faststart = data.get("faststart", True)
        use_gpu = data.get("use_gpu", True)  # Enable GPU by default
        
        if not input_path or not os.path.exists(input_path):
            raise ValueError(f"Input file not found: {input_path}")
        
        # Check for GPU availability (for potential future GPU-based remuxing)
        gpu_available = await self.check_gpu_available()
        use_hardware = use_gpu and gpu_available
        
        # Generate output path if not provided - ALWAYS in the same directory as input
        if not output_path:
            input_file = Path(input_path)
            # Remux in the same directory as the input file
            output_path = str(input_file.with_suffix(f".{output_format}"))
        
        # Update progress
        await self.update_progress(job_id, 10, "running")
        
        # Build FFmpeg command
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-fflags", "+genpts",
            "-i", input_path,
            "-map", "0",  # Copy all streams
            "-c", "copy",  # Stream copy (no re-encoding)
        ]
        
        # Add format-specific options
        if output_format == "mov" and faststart:
            cmd.extend(["-movflags", "+faststart"])
        elif output_format == "mp4" and faststart:
            cmd.extend(["-movflags", "+faststart"])
        
        cmd.append(output_path)
        
        logger.info(f"Remuxing {input_path} to {output_path}")
        
        # Run FFmpeg
        await self.update_progress(job_id, 20, "running")
        returncode, stdout, stderr = await self.run_command(cmd)
        
        if returncode != 0:
            error_msg = f"FFmpeg failed: {stderr}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        # Verify output file
        if not os.path.exists(output_path):
            raise RuntimeError(f"Output file not created: {output_path}")
        
        output_size = os.path.getsize(output_path)
        
        # Remove original file after successful remux (unless it's the same file)
        remove_original = data.get("remove_original", True)  # Default to True
        
        if remove_original and input_path != output_path:
            try:
                os.remove(input_path)
                logger.info(f"Removed original file: {input_path}")
            except Exception as e:
                logger.warning(f"Could not remove original file {input_path}: {e}")
        
        # Update progress and store result in database
        await self.update_progress(job_id, 100, "completed")
        
        # Store result in database for rule engine to retrieve
        result = {
            "success": True,
            "output_path": output_path,
            "output_size": output_size,
            "output_format": output_format,
            "gpu_used": use_hardware,
            "original_removed": remove_original and input_path != output_path,
            "input_path": input_path
        }
        
        # Update job with result and update asset's current_path
        try:
            import aiosqlite
            import json
            from datetime import datetime
            
            conn = await aiosqlite.connect("/data/db/streamops.db")
            
            # Update job result
            await conn.execute("""
                UPDATE so_jobs 
                SET result_json = ?, state = 'completed', updated_at = ?
                WHERE id = ?
            """, (
                json.dumps(result),
                datetime.utcnow().isoformat(),
                job_id
            ))
            
            # Update asset's current_path if we have an asset_id
            asset_id = job_data.get("asset_id") or data.get("asset_id")
            if asset_id:
                await conn.execute("""
                    UPDATE so_assets 
                    SET current_path = ?, updated_at = datetime('now')
                    WHERE id = ?
                """, (output_path, asset_id))
                logger.info(f"Updated asset {asset_id} current_path to {output_path}")
            
            await conn.commit()
            await conn.close()
            logger.info(f"Updated job {job_id} with result in database")
        except Exception as e:
            logger.error(f"Failed to update job result in database: {e}")
        
        logger.info(f"Successfully remuxed to {output_path} ({output_size} bytes)")
        
        # Emit remux completed event
        try:
            # Get asset_id from database
            conn = await aiosqlite.connect("/data/db/streamops.db")
            cursor = await conn.execute(
                "SELECT asset_id FROM so_jobs WHERE id = ?",
                (job_id,)
            )
            row = await cursor.fetchone()
            if row and row[0]:
                from app.api.services.asset_events import AssetEventService
                await AssetEventService.emit_remux_completed(
                    row[0], job_id, input_path, output_path, output_size
                )
            await conn.close()
        except Exception as e:
            logger.debug(f"Could not emit remux event: {e}")
        
        return result
    
    async def check_gpu_available(self) -> bool:
        """Check if NVIDIA GPU is available"""
        try:
            # Check for nvidia-smi
            result = await self.run_command(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"])
            if result[0] == 0 and result[1].strip():
                logger.debug(f"GPU detected for remux: {result[1].strip()}")
                # Note: Remuxing doesn't benefit from GPU acceleration since it's just stream copying
                # But we check anyway for consistency and future enhancements
                return True
            return False
        except Exception as e:
            logger.debug(f"GPU check failed: {e}")
            return False