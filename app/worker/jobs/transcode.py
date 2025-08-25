from typing import Dict, Any
import os
import logging
import json
from pathlib import Path

from app.worker.jobs.base import BaseJob

logger = logging.getLogger(__name__)

class TranscodeJob(BaseJob):
    """Job processor for transcoding with presets"""
    
    PRESETS = {
        "web_720p": {
            "video_codec": "libx264",
            "audio_codec": "aac",
            "video_bitrate": "2500k",
            "audio_bitrate": "128k",
            "video_filters": "scale=-2:720",
            "pixel_format": "yuv420p",
            "preset": "medium",
            "crf": None,
            "container": "mp4"
        },
        "web_1080p": {
            "video_codec": "libx264",
            "audio_codec": "aac",
            "video_bitrate": "5000k",
            "audio_bitrate": "192k",
            "video_filters": "scale=-2:1080",
            "pixel_format": "yuv420p",
            "preset": "medium",
            "crf": None,
            "container": "mp4"
        },
        "archive_h265": {
            "video_codec": "libx265",
            "audio_codec": "aac",
            "video_bitrate": None,
            "audio_bitrate": "128k",
            "video_filters": None,
            "pixel_format": "yuv420p10le",
            "preset": "medium",
            "crf": "23",
            "container": "mp4"
        },
        "streaming_twitch": {
            "video_codec": "libx264",
            "audio_codec": "aac",
            "video_bitrate": "6000k",
            "audio_bitrate": "160k",
            "video_filters": "scale=-2:1080",
            "pixel_format": "yuv420p",
            "preset": "veryfast",
            "crf": None,
            "container": "mp4"
        },
        "mobile_480p": {
            "video_codec": "libx264",
            "audio_codec": "aac",
            "video_bitrate": "1000k",
            "audio_bitrate": "96k",
            "video_filters": "scale=-2:480",
            "pixel_format": "yuv420p",
            "preset": "medium",
            "crf": None,
            "container": "mp4"
        }
    }
    
    async def process(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Transcode media file using specified preset"""
        job_id = job_data.get("id")
        data = job_data.get("data", {})
        
        input_path = data.get("input_path")
        preset_name = data.get("preset", "web_1080p")
        output_path = data.get("output_path")
        custom_preset = data.get("custom_preset", {})
        start_time = data.get("start_time")  # Optional clip start
        end_time = data.get("end_time")      # Optional clip end
        use_gpu = data.get("use_gpu", True)  # Enable GPU by default
        
        if not input_path or not os.path.exists(input_path):
            raise ValueError(f"Input file not found: {input_path}")
        
        # Check for GPU availability
        gpu_available = await self.check_gpu_available()
        use_hardware = use_gpu and gpu_available
        
        # Get preset settings
        if preset_name in self.PRESETS:
            preset = self.PRESETS[preset_name].copy()
        else:
            raise ValueError(f"Unknown preset: {preset_name}")
        
        # Override with custom settings
        preset.update(custom_preset)
        
        # Generate output path if not provided
        if not output_path:
            input_file = Path(input_path)
            suffix = f"_{preset_name}"
            if start_time and end_time:
                suffix += "_clip"
            container = preset.get("container", "mp4")
            output_path = str(input_file.with_suffix("").with_suffix(f"{suffix}.{container}"))
        
        await self.update_progress(job_id, 10, "running")
        
        # Get input file info for progress tracking
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
            probe_data = json.loads(stdout)
        except json.JSONDecodeError:
            raise RuntimeError(f"Failed to parse probe data: {stdout}")
        
        # Calculate duration for progress tracking
        duration = None
        if start_time and end_time:
            duration = self.parse_time(end_time) - self.parse_time(start_time)
        else:
            format_info = probe_data.get("format", {})
            if "duration" in format_info:
                duration = float(format_info["duration"])
        
        await self.update_progress(job_id, 20, "running")
        
        # Build FFmpeg command
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-stats"  # Enable progress stats
        ]
        
        # Add hardware acceleration if available
        if use_hardware:
            # Use NVIDIA GPU decoding
            cmd.extend(["-hwaccel", "cuda"])
            cmd.extend(["-hwaccel_output_format", "cuda"])
        
        # Add input options
        if start_time:
            cmd.extend(["-ss", str(start_time)])
        
        cmd.extend(["-i", input_path])
        
        # Add output options
        if end_time:
            cmd.extend(["-to", str(end_time)])
        elif start_time and duration:
            cmd.extend(["-t", str(duration)])
        
        # Video codec settings
        video_codec = preset.get("video_codec")
        if video_codec:
            # Use hardware encoder if available and codec is h264/h265
            if use_hardware and video_codec == "libx264":
                cmd.extend(["-c:v", "h264_nvenc"])
            elif use_hardware and video_codec == "libx265":
                cmd.extend(["-c:v", "hevc_nvenc"])
            else:
                cmd.extend(["-c:v", video_codec])
            
            # Video quality settings
            if preset.get("crf"):
                cmd.extend(["-crf", preset["crf"]])
            elif preset.get("video_bitrate"):
                cmd.extend(["-b:v", preset["video_bitrate"]])
            
            # Encoder preset
            if preset.get("preset"):
                cmd.extend(["-preset", preset["preset"]])
            
            # Pixel format
            if preset.get("pixel_format"):
                cmd.extend(["-pix_fmt", preset["pixel_format"]])
            
            # Video filters
            video_filters = preset.get("video_filters")
            if video_filters:
                cmd.extend(["-vf", video_filters])
        
        # Audio codec settings
        audio_codec = preset.get("audio_codec")
        if audio_codec:
            cmd.extend(["-c:a", audio_codec])
            
            if preset.get("audio_bitrate"):
                cmd.extend(["-b:a", preset["audio_bitrate"]])
        
        # Container-specific options
        container = preset.get("container", "mp4")
        if container == "mp4":
            cmd.extend(["-movflags", "+faststart"])
        
        # Map all streams by default
        cmd.extend(["-map", "0"])
        
        # Output file
        cmd.append(output_path)
        
        logger.info(f"Transcoding with preset '{preset_name}': {input_path} -> {output_path}")
        
        await self.update_progress(job_id, 30, "running")
        
        # Run FFmpeg with progress monitoring
        process = await self.create_ffmpeg_process(cmd)
        returncode, stdout, stderr = await self.monitor_transcode_progress(
            process, job_id, duration
        )
        
        if returncode != 0:
            error_msg = f"FFmpeg transcoding failed: {stderr}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        # Verify output file
        if not os.path.exists(output_path):
            raise RuntimeError(f"Output file not created: {output_path}")
        
        output_size = os.path.getsize(output_path)
        input_size = os.path.getsize(input_path)
        compression_ratio = (1 - output_size / input_size) * 100 if input_size > 0 else 0
        
        await self.update_progress(job_id, 100, "completed")
        
        logger.info(f"Successfully transcoded: {output_path} ({output_size} bytes, {compression_ratio:.1f}% compression)")
        
        return {
            "success": True,
            "input_path": input_path,
            "output_path": output_path,
            "preset": preset_name,
            "input_size": input_size,
            "output_size": output_size,
            "compression_ratio": compression_ratio,
            "video_codec": preset.get("video_codec"),
            "audio_codec": preset.get("audio_codec"),
            "container": container
        }
    
    async def create_ffmpeg_process(self, cmd):
        """Create FFmpeg subprocess"""
        import asyncio
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        return process
    
    async def monitor_transcode_progress(self, process, job_id, total_duration=None):
        """Monitor FFmpeg transcoding progress"""
        import asyncio
        import re
        
        stderr_lines = []
        
        async def read_stderr():
            if not process.stderr:
                return
                
            while True:
                line = await process.stderr.readline()
                if not line:
                    break
                    
                line_str = line.decode('utf-8', errors='ignore')
                stderr_lines.append(line_str)
                
                # Parse time progress from FFmpeg output
                if total_duration and 'time=' in line_str:
                    time_match = re.search(r'time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})', line_str)
                    if time_match:
                        h, m, s, cs = time_match.groups()
                        current_time = int(h) * 3600 + int(m) * 60 + int(s) + int(cs) / 100
                        progress = min(90, 30 + (current_time / total_duration) * 60)
                        await self.update_progress(job_id, progress, "running")
        
        # Start monitoring stderr
        stderr_task = asyncio.create_task(read_stderr())
        
        # Wait for completion
        stdout, _ = await process.communicate()
        
        # Wait for stderr monitoring to finish
        await stderr_task
        
        stderr_output = ''.join(stderr_lines)
        
        return process.returncode, stdout.decode(), stderr_output
    
    def parse_time(self, time_str):
        """Parse time string to seconds"""
        try:
            if ':' in time_str:
                parts = time_str.split(':')
                if len(parts) == 3:
                    h, m, s = parts
                    return int(h) * 3600 + int(m) * 60 + float(s)
                elif len(parts) == 2:
                    m, s = parts
                    return int(m) * 60 + float(s)
            return float(time_str)
        except:
            return 0.0
    
    async def check_gpu_available(self) -> bool:
        """Check if NVIDIA GPU is available for encoding"""
        try:
            # Check for nvidia-smi
            result = await self.run_command(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"])
            if result[0] == 0 and result[1].strip():
                logger.info(f"GPU detected: {result[1].strip()}")
                
                # Check if FFmpeg has NVENC support
                ffmpeg_result = await self.run_command(["ffmpeg", "-encoders"])
                if ffmpeg_result[0] == 0:
                    encoders = ffmpeg_result[1]
                    if "h264_nvenc" in encoders or "hevc_nvenc" in encoders:
                        logger.info("NVENC hardware encoding available")
                        return True
                    else:
                        logger.warning("GPU detected but NVENC not available in FFmpeg")
            return False
        except Exception as e:
            logger.debug(f"GPU check failed: {e}")
            return False