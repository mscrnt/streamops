from typing import Dict, Any
import os
import logging
from pathlib import Path

from app.worker.jobs.base import BaseJob

logger = logging.getLogger(__name__)

class ProxyJob(BaseJob):
    """Job processor for creating proxy files for editing (DNxHR)"""
    
    async def process(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create DNxHR proxy file for editing workflows"""
        job_id = job_data.get("id")
        data = job_data.get("data", {})
        
        input_path = data.get("input_path")
        output_path = data.get("output_path")
        profile = data.get("profile", "dnxhr_lb")  # Low Bandwidth by default
        resolution = data.get("resolution", "1080")  # Target height
        timecode_start = data.get("timecode_start", "00:00:00:00")
        audio_channels = data.get("audio_channels", None)  # Auto-detect if None
        use_gpu = data.get("use_gpu", True)  # Enable GPU by default
        
        if not input_path or not os.path.exists(input_path):
            raise ValueError(f"Input file not found: {input_path}")
        
        # Check for GPU availability
        gpu_available = await self.check_gpu_available()
        use_hardware = use_gpu and gpu_available
        
        # Generate output path if not provided
        if not output_path:
            input_file = Path(input_path)
            suffix = f"_proxy_{profile}_{resolution}p"
            output_path = str(input_file.with_suffix("").with_suffix(f"{suffix}.mov"))
        
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
        
        # Video codec settings for DNxHR
        cmd.extend([
            "-c:v", "dnxhd",
            "-profile:v", profile,
        ])
        
        # Scale video to target resolution
        target_height = int(resolution)
        
        # Use GPU scaling if hardware acceleration is enabled
        if use_hardware:
            # Use CUDA scale filter
            scale_filter = f"scale_cuda=-2:{target_height}:format=yuv422p10le"
            # Transfer from GPU back to CPU for DNxHR encoding
            video_filters = [scale_filter, "hwdownload", "format=yuv422p10le"]
        else:
            scale_filter = f"scale=-2:{target_height}"
            video_filters = [scale_filter]
        
        # Apply video filters
        cmd.extend(["-vf", ",".join(video_filters)])
        
        # Handle audio streams
        if audio_streams:
            if audio_channels:
                # Use specified channel layout
                cmd.extend(["-map", "0:a?", "-c:a", "pcm_s16le", "-ac", str(audio_channels)])
            else:
                # Keep original audio layout
                cmd.extend(["-map", "0:a?", "-c:a", "pcm_s16le"])
        
        # Add timecode
        cmd.extend(["-timecode", timecode_start])
        
        # DNxHR specific settings
        cmd.extend([
            "-vendor", "avc1",  # Vendor code for compatibility
            "-pix_fmt", "yuv422p10le",  # Pixel format for DNxHR
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
        
        return {
            "success": True,
            "input_path": input_path,
            "output_path": output_path,
            "output_size": output_size,
            "profile": profile,
            "resolution": f"{target_height}p",
            "codec": "DNxHR",
            "audio_codec": "PCM 16-bit" if audio_streams else None
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
        
        # Start reading stderr
        stderr_task = asyncio.create_task(read_stderr())
        
        # Wait for process completion
        stdout, _ = await process.communicate()
        
        # Wait for stderr reading to complete
        await stderr_task
        
        stderr_output = ''.join(stderr_data)
        
        return process.returncode, stdout.decode(), stderr_output
    
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