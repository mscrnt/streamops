from typing import Dict, Any
import os
import logging
from pathlib import Path

from app.worker.jobs.base import BaseJob

logger = logging.getLogger(__name__)

# DNxHR profile format mappings
DNXHR_8BIT = {"dnxhr_lb", "dnxhr_sq", "dnxhr_hq"}
DNXHR_10BIT = {"dnxhr_hqx", "dnxhr_444"}

def pick_formats(profile: str) -> Dict[str, str]:
    """Map DNxHR profile to required pixel formats.
    
    Args:
        profile: DNxHR profile name (e.g., dnxhr_lb, dnxhr_hqx)
        
    Returns:
        Dict with cpu_pix_fmt and gpu_surface format
    """
    profile = (profile or "dnxhr_lb").lower()
    if profile in DNXHR_8BIT:
        return {
            "cpu_pix_fmt": "yuv422p",   # DNxHR LB/SQ/HQ use 8-bit
            "gpu_surface": "nv12",      # 8-bit CUDA/NPP surface
        }
    elif profile in DNXHR_10BIT:
        return {
            "cpu_pix_fmt": "yuv422p10le",  # DNxHR HQX/444 use 10-bit
            "gpu_surface": "p010le",       # 10-bit CUDA/NPP surface
        }
    # Default to safe 8-bit formats
    return {"cpu_pix_fmt": "yuv422p", "gpu_surface": "nv12"}

class ProxyJob(BaseJob):
    """Job processor for creating proxy files for editing (DNxHR)"""
    
    async def process(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create DNxHR proxy file for editing workflows"""
        job_id = job_data.get("id")
        data = job_data.get("data", {})
        
        # Get the asset's current path from database
        asset_id = job_data.get("asset_id") or data.get("asset_id")
        input_path = data.get("input_path")
        
        if asset_id:
            # Look up the asset's current path
            import aiosqlite
            try:
                conn = await aiosqlite.connect("/data/db/streamops.db")
                cursor = await conn.execute("""
                    SELECT current_path 
                    FROM so_assets 
                    WHERE id = ?
                """, (asset_id,))
                row = await cursor.fetchone()
                await conn.close()
                
                if row and row[0]:
                    actual_path = row[0]
                    logger.info(f"Asset {asset_id} current_path from DB: {actual_path}")
                    # Use the current_path from database as the input
                    input_path = actual_path
            except Exception as e:
                logger.warning(f"Failed to get asset current_path: {e}")
        
        input_path = input_path or data.get("input_path")
        output_path = data.get("output_path")
        
        # Use values from rule, with sensible defaults only if not specified
        profile = data.get("profile") or data.get("codec")
        if not profile:
            profile = "h264_proxy"  # Default to H.264 for smaller files
            
        resolution = data.get("resolution", "720")  # Default 720p for proxies
        timecode_start = data.get("timecode_start", "00:00:00:00")
        audio_channels = data.get("audio_channels", None)  # Auto-detect if None
        use_gpu = data.get("use_gpu", True)  # Enable GPU by default
        
        # Default bitrate based on codec if not specified
        bitrate = data.get("bitrate")
        if not bitrate:
            if profile.startswith("h264"):
                bitrate = "2M"  # 2 Mbps for H.264
            else:
                bitrate = None  # DNxHR doesn't use bitrate parameter
        
        if not input_path or not os.path.exists(input_path):
            raise ValueError(f"Input file not found: {input_path}")
        
        # Check for GPU availability
        gpu_available = await self.check_gpu_available()
        use_hardware = use_gpu and gpu_available
        
        # Check for specific CUDA filter availability if GPU is enabled
        if use_hardware:
            logger.info("GPU detected, checking for CUDA filter support...")
            code, out, _ = await self.run_command(["ffmpeg", "-hide_banner", "-filters"])
            if code == 0:
                has_scale_npp = "scale_npp" in out
                has_scale_cuda = "scale_cuda" in out
                
                if not has_scale_npp and not has_scale_cuda:
                    logger.warning("CUDA scaling filters not available; falling back to CPU path")
                    use_hardware = False
                elif has_scale_npp:
                    logger.info("Using scale_npp for GPU acceleration")
                elif has_scale_cuda:
                    logger.info("scale_npp not found, using scale_cuda for GPU acceleration")
            else:
                logger.warning("Failed to query FFmpeg filters; falling back to CPU path")
                use_hardware = False
        
        # Generate output path if not provided - will be updated later with actual height
        if not output_path:
            input_file = Path(input_path)
            # Build the new filename with proxy suffix
            base_name = input_file.stem  # Get filename without extension
            
            # Choose extension based on codec
            if profile.startswith("h264"):
                extension = ".mp4"
                codec_label = "h264"
            else:
                extension = ".mov"
                codec_label = profile
            
            # Temporarily use requested resolution - will update later with actual
            proxy_suffix = f"_proxy_{codec_label}_{resolution}p"
            output_path = str(input_file.parent / f"{base_name}{proxy_suffix}{extension}")
        
        await self.update_progress(job_id, 10, "running")
        
        # Get input video info
        probe_cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            "-show_format",
            input_path
        ]
        
        returncode, stdout, stderr = await self.run_command(probe_cmd)
        if returncode != 0:
            raise RuntimeError(f"Failed to probe input file: {stderr}")
        
        try:
            import json
            probe_data = json.loads(stdout)
        except json.JSONDecodeError:
            raise RuntimeError(f"Failed to parse probe data: {stdout}")
        
        # Find video and audio streams
        video_stream = None
        audio_streams = []
        
        for stream in probe_data.get("streams", []):
            if stream.get("codec_type") == "video":
                video_stream = stream
            elif stream.get("codec_type") == "audio":
                audio_streams.append(stream)
        
        if not video_stream:
            raise RuntimeError("No video stream found in input file")
        
        await self.update_progress(job_id, 20, "running")
        
        # Build FFmpeg command
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error"
        ]
        
        # Add hardware acceleration for decoding if available
        if use_hardware:
            cmd.extend(["-hwaccel", "cuda"])
            cmd.extend(["-hwaccel_output_format", "cuda"])
        
        cmd.extend(["-i", input_path])
        
        # Map video stream
        cmd.extend(["-map", "0:v:0"])
        
        # Scale video to target resolution (but don't upscale)
        # Get original height from video stream
        original_height = video_stream.get("height", 0)
        
        # Parse resolution - default to 720 if not specified or invalid
        try:
            target_height = int(resolution) if resolution else 720
        except (ValueError, TypeError):
            logger.warning(f"Invalid resolution '{resolution}', defaulting to 720")
            target_height = 720
        
        # Don't upscale - use the smaller of target or original
        if original_height > 0 and original_height < target_height:
            logger.info(f"Not upscaling: keeping original height {original_height} instead of {target_height}")
            target_height = original_height
        
        # Determine formats from DNxHR profile
        fmt = pick_formats(profile)
        cpu_pix_fmt = fmt["cpu_pix_fmt"]
        gpu_surface = fmt["gpu_surface"]
        
        # Build filter chain deterministically
        if use_hardware:
            # GPU path: CUDA decode + GPU scale + hwdownload → software format convert
            # Check which GPU filter is available (prefer scale_npp over scale_cuda)
            code, out, _ = await self.run_command(["ffmpeg", "-hide_banner", "-filters"])
            use_scale_npp = code == 0 and "scale_npp" in out
            
            if use_scale_npp:
                # scale_npp supports explicit format specification
                scale_gpu = f"scale_npp=-2:{target_height}:format={gpu_surface}"
                scale_name = "scale_npp"
            else:
                # scale_cuda doesn't support format parameter, relies on auto-detection
                scale_gpu = f"scale_cuda=-2:{target_height}"
                scale_name = "scale_cuda"
                logger.info(f"Using scale_cuda (will auto-detect surface format)")
            
            # CRITICAL: Build filter chain as a single string
            # hwdownload can only output to nv12 or yuv420p, not yuv422p directly
            # We need an intermediate format conversion
            # First download to nv12/yuv420p, then convert to yuv422p for DNxHR
            video_filters = f"{scale_gpu},hwdownload,format=nv12,format={cpu_pix_fmt}"
            
            logger.info(f"GPU proxy pipeline: {scale_name} -> hwdownload -> format={cpu_pix_fmt}")
        else:
            # CPU path: scale then convert to DNxHR-required pix_fmt
            video_filters = f"scale=-2:{target_height},format={cpu_pix_fmt}"
            logger.info(f"CPU proxy pipeline: scale -> format={cpu_pix_fmt}")
        
        # Log the exact filter chain for debugging
        logger.info(f"Proxy: GPU={'on' if use_hardware else 'off'} profile={profile} vf='{video_filters}' pix_fmt={cpu_pix_fmt}")
        
        # Apply video filters as ONE argument
        cmd.extend(["-vf", video_filters])
        
        # Handle audio streams
        if audio_streams:
            # Choose audio codec based on output format
            if profile.startswith("h264"):
                # MP4 container requires compressed audio (AAC)
                audio_codec = "aac"
                audio_bitrate = ["-b:a", "128k"]  # 128kbps for proxy audio
            else:
                # MOV container supports PCM for DNxHR
                audio_codec = "pcm_s16le"
                audio_bitrate = []
            
            if audio_channels:
                # Use specified channel layout
                cmd.extend(["-map", "0:a?", "-c:a", audio_codec] + audio_bitrate + ["-ac", str(audio_channels)])
            else:
                # Keep original audio layout
                cmd.extend(["-map", "0:a?", "-c:a", audio_codec] + audio_bitrate)
        
        # Add timecode
        cmd.extend(["-timecode", timecode_start])
        
        # Choose encoder based on profile
        if profile.startswith("h264"):
            # H.264 proxy settings for smaller files
            if use_hardware:
                # Use NVIDIA encoder if available
                cmd.extend([
                    "-c:v", "h264_nvenc",
                    "-preset", "fast",
                    "-b:v", bitrate,
                    "-maxrate", bitrate,
                    "-bufsize", f"{int(bitrate[:-1])*2}M",
                    "-pix_fmt", "yuv420p",  # Standard format for H.264
                ])
            else:
                # Software H.264 encoding
                cmd.extend([
                    "-c:v", "libx264",
                    "-preset", "fast",
                    "-crf", "23",  # Quality-based encoding
                    "-b:v", bitrate,
                    "-maxrate", bitrate,
                    "-bufsize", f"{int(bitrate[:-1])*2}M" if bitrate.endswith('M') else bitrate,
                    "-pix_fmt", "yuv420p",
                ])
        elif profile.startswith("dnx"):
            # DNxHR encoder settings - MUST come after filters
            # Determine pixel format from profile (already done above)
            cmd.extend([
                "-c:v", "dnxhd",
                "-profile:v", profile,
                "-vendor", "avc1",  # Vendor code for compatibility
                "-pix_fmt", cpu_pix_fmt,  # Explicitly set pixel format for encoder
            ])
        else:
            # Default to H.264 for unrecognized profiles
            cmd.extend([
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "23",
                "-pix_fmt", "yuv420p",
            ])
        
        # Output file
        cmd.append(output_path)
        
        logger.info(f"Creating {profile} proxy: {input_path} -> {output_path}")
        
        await self.update_progress(job_id, 30, "running")
        
        # Run FFmpeg with progress tracking
        process = await self.create_ffmpeg_process(cmd)
        
        # Monitor FFmpeg progress if possible
        total_frames = video_stream.get("nb_frames")
        if not total_frames or total_frames == "N/A":
            # Estimate from duration and fps
            duration = float(probe_data.get("format", {}).get("duration", 0))
            fps = self.parse_fps(video_stream.get("r_frame_rate", "25/1"))
            total_frames = int(duration * fps) if duration > 0 else None
        else:
            total_frames = int(total_frames)
        
        # Wait for process completion
        returncode, stdout, stderr = await self.wait_for_process(process, job_id, total_frames)
        
        if returncode != 0:
            error_msg = f"FFmpeg failed: {stderr}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        # Verify output file
        if not os.path.exists(output_path):
            raise RuntimeError(f"Output file not created: {output_path}")
        
        output_size = os.path.getsize(output_path)
        
        await self.update_progress(job_id, 100, "completed")
        
        logger.info(f"Successfully created proxy: {output_path} ({output_size} bytes)")
        
        # Emit proxy completed event
        try:
            # Get asset_id from job data or database
            asset_id = None
            if 'asset_id' in data:
                asset_id = data['asset_id']
            else:
                # Try to get from database
                import aiosqlite
                conn = await aiosqlite.connect("/data/db/streamops.db")
                cursor = await conn.execute(
                    "SELECT asset_id FROM so_jobs WHERE id = ?",
                    (job_id,)
                )
                row = await cursor.fetchone()
                if row and row[0]:
                    asset_id = row[0]
                await conn.close()
            
            if asset_id:
                from app.api.services.asset_events import AssetEventService
                await AssetEventService.emit_proxy_completed(
                    asset_id, job_id, output_path, profile, f"{target_height}p", output_size
                )
        except Exception as e:
            logger.debug(f"Could not emit proxy event: {e}")
        
        # Determine output codec info for response
        if profile.startswith("h264"):
            video_codec_name = "H.264"
            audio_codec_name = "AAC" if audio_streams else None
        else:
            video_codec_name = "DNxHR"
            audio_codec_name = "PCM 16-bit" if audio_streams else None
        
        return {
            "success": True,
            "input_path": input_path,
            "output_path": output_path,
            "output_size": output_size,
            "profile": profile,
            "resolution": f"{target_height}p",
            "codec": video_codec_name,
            "audio_codec": audio_codec_name
        }
    
    async def create_ffmpeg_process(self, cmd):
        """Create FFmpeg subprocess for monitoring"""
        import asyncio
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        return process
    
    async def wait_for_process(self, process, job_id, total_frames=None):
        """Wait for FFmpeg process and track progress"""
        import asyncio
        import re
        
        stderr_data = []
        stdout_data = []
        
        async def read_stderr():
            """Read stderr for progress info"""
            if not process.stderr:
                return
                
            while True:
                line = await process.stderr.readline()
                if not line:
                    break
                    
                line_str = line.decode('utf-8', errors='ignore')
                stderr_data.append(line_str)
                
                # Parse progress from FFmpeg output
                if total_frames and 'frame=' in line_str:
                    frame_match = re.search(r'frame=\s*(\d+)', line_str)
                    if frame_match:
                        current_frame = int(frame_match.group(1))
                        progress = min(90, 30 + (current_frame / total_frames) * 60)
                        await self.update_progress(job_id, progress, "running")
        
        async def read_stdout():
            """Read stdout"""
            if not process.stdout:
                return
                
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                stdout_data.append(line.decode('utf-8', errors='ignore'))
        
        # Start reading both streams concurrently
        stderr_task = asyncio.create_task(read_stderr())
        stdout_task = asyncio.create_task(read_stdout())
        
        # Wait for process to complete
        await process.wait()
        
        # Wait for both reading tasks to complete
        await stderr_task
        await stdout_task
        
        stderr_output = ''.join(stderr_data)
        stdout_output = ''.join(stdout_data)
        
        return process.returncode, stdout_output, stderr_output
    
    def parse_fps(self, fps_str):
        """Parse fps from fraction string like '30000/1001'"""
        try:
            if '/' in fps_str:
                num, den = fps_str.split('/')
                return float(num) / float(den)
            return float(fps_str)
        except:
            return 25.0  # Default fallback
    
    async def check_gpu_available(self) -> bool:
        """Check if NVIDIA GPU is available for acceleration"""
        try:
            # Check for nvidia-smi
            result = await self.run_command(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"])
            if result[0] == 0 and result[1].strip():
                logger.info(f"GPU detected for proxy: {result[1].strip()}")
                
                # Check if FFmpeg has CUDA support
                ffmpeg_result = await self.run_command(["ffmpeg", "-filters"])
                if ffmpeg_result[0] == 0:
                    filters = ffmpeg_result[1]
                    if "scale_cuda" in filters:
                        logger.info("CUDA scaling available for proxy generation")
                        return True
                    else:
                        logger.warning("GPU detected but CUDA filters not available in FFmpeg")
            return False
        except Exception as e:
            logger.debug(f"GPU check failed: {e}")
            return False