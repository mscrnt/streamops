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
        job_id = job_data.get("id")
        data = job_data.get("data", {})
        
        input_path = data.get("input_path")
        output_format = data.get("output_format", "mov")
        output_path = data.get("output_path")
        faststart = data.get("faststart", True)
        use_gpu = data.get("use_gpu", True)  # Enable GPU by default
        
        if not input_path or not os.path.exists(input_path):
            raise ValueError(f"Input file not found: {input_path}")
        
        # Check for GPU availability (for potential future GPU-based remuxing)
        gpu_available = await self.check_gpu_available()
        use_hardware = use_gpu and gpu_available
        
        # Generate output path if not provided
        if not output_path:
            input_file = Path(input_path)
            
            # Check if we're remuxing from Recording folder to Editing folder
            try:
                import aiosqlite
                conn = await aiosqlite.connect("/data/db/streamops.db")
                
                # Get Recording and Editing paths from roles
                cursor = await conn.execute("""
                    SELECT role, abs_path FROM so_roles 
                    WHERE role IN ('recording', 'editing')
                """)
                roles = {}
                async for row in cursor:
                    roles[row[0]] = row[1]
                await conn.close()
                
                # If input is in Recording folder and Editing folder exists, put output there
                if roles.get('recording') and roles.get('editing'):
                    recording_path = Path(roles['recording'])
                    editing_path = Path(roles['editing'])
                    
                    # Check if input file is in Recording folder or its subdirectories
                    try:
                        input_file.relative_to(recording_path)
                        # File is in recording folder, put output in editing folder with same structure
                        relative_path = input_file.relative_to(recording_path)
                        output_dir = editing_path / relative_path.parent
                        
                        # Create output directory if it doesn't exist
                        output_dir.mkdir(parents=True, exist_ok=True)
                        
                        # Set output path in editing folder
                        output_path = str(output_dir / input_file.with_suffix(f".{output_format}").name)
                        logger.info(f"Remuxing from Recording to Editing folder: {output_path}")
                    except ValueError:
                        # Not in recording folder, use same directory
                        output_path = str(input_file.with_suffix(f".{output_format}"))
                else:
                    # No roles configured, use same directory
                    output_path = str(input_file.with_suffix(f".{output_format}"))
            except Exception as e:
                logger.warning(f"Could not check roles for output path: {e}")
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
        
        # Remove original file if we remuxed to a different location
        # (e.g., from Recording to Editing folder)
        remove_original = data.get("remove_original", None)
        if remove_original is None:
            # Auto-determine: remove if output is in different directory
            remove_original = Path(input_path).parent != Path(output_path).parent
        
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
        
        # Update job with result
        try:
            import aiosqlite
            import json
            from datetime import datetime
            
            conn = await aiosqlite.connect("/data/db/streamops.db")
            await conn.execute("""
                UPDATE so_jobs 
                SET result_json = ?, state = 'completed', updated_at = ?
                WHERE id = ?
            """, (
                json.dumps(result),
                datetime.utcnow().isoformat(),
                job_id
            ))
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