"""
FFmpeg worker that processes video remux, transcode, and proxy jobs.
Inherits from BaseWorker to ensure guardrails are checked before processing.
"""

import asyncio
import subprocess
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
import shlex

from app.worker.base_worker import BaseWorker, GuardrailsBlocked

class FFmpegWorker(BaseWorker):
    """
    FFmpeg worker for CPU/GPU intensive video processing.
    
    Automatically checks guardrails before starting any FFmpeg process.
    """
    
    def __init__(self):
        super().__init__("ffmpeg")
        self.ffmpeg_path = "ffmpeg"  # Assumes ffmpeg is in PATH
        
    async def execute(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute FFmpeg job. This is only called if guardrails checks pass.
        """
        job_type = job_data.get('type')
        job_id = job_data.get('id')
        payload = job_data.get('payload', {})
        
        # Dispatch to specific handler based on job type
        if job_type == 'ffmpeg_remux':
            return await self.handle_remux(job_id, payload)
        elif job_type == 'ffmpeg_transcode':
            return await self.handle_transcode(job_id, payload)
        elif job_type == 'proxy':
            return await self.handle_proxy(job_id, payload)
        else:
            raise ValueError(f"Unknown FFmpeg job type: {job_type}")
    
    async def handle_remux(self, job_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle remux job (stream copy, no transcoding).
        Even remux can be I/O intensive, so guardrails still apply.
        """
        input_path = payload.get('input_path')
        output_format = payload.get('output_format', 'mov')
        faststart = payload.get('faststart', True)
        
        if not input_path or not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        # Generate output path
        input_file = Path(input_path)
        output_path = input_file.with_suffix(f'.{output_format}')
        
        # Build FFmpeg command
        cmd = [
            self.ffmpeg_path,
            '-hide_banner',
            '-loglevel', 'error',
            '-fflags', '+genpts',
            '-i', input_path,
            '-map', '0',  # Map all streams
            '-c', 'copy',  # Stream copy (no re-encoding)
        ]
        
        if faststart and output_format in ['mp4', 'mov']:
            cmd.extend(['-movflags', '+faststart'])
        
        cmd.append(str(output_path))
        
        # Check guardrails one more time before starting FFmpeg
        await self.ensure_guardrails_clear()
        
        # Execute FFmpeg
        self.logger.info(f"Starting remux: {input_path} -> {output_path}")
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Monitor process and check guardrails periodically
            while process.returncode is None:
                # Check if guardrails have activated while running
                is_blocked, reason, _ = await self.check_guardrails()
                if is_blocked:
                    # Kill the process if guardrails activate
                    self.logger.warning(f"Guardrails activated during remux: {reason}, terminating FFmpeg")
                    process.terminate()
                    await process.wait()
                    raise GuardrailsBlocked(reason, 60)
                
                # Wait a bit before checking again
                try:
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    # Still running, continue monitoring
                    continue
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='ignore')
                raise RuntimeError(f"FFmpeg failed: {error_msg}")
            
            # Get output file info
            output_stat = output_path.stat()
            
            return {
                'output_path': str(output_path),
                'output_size': output_stat.st_size,
                'success': True
            }
            
        except GuardrailsBlocked:
            # Clean up partial output if exists
            if output_path.exists():
                output_path.unlink()
            raise
            
        except Exception as e:
            # Clean up on error
            if output_path.exists():
                output_path.unlink()
            raise
    
    async def handle_transcode(self, job_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle transcode job (re-encoding, very CPU/GPU intensive).
        """
        input_path = payload.get('input_path')
        preset = payload.get('preset', 'web_1080p')
        
        if not input_path or not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        # Get preset settings
        preset_config = self.get_transcode_preset(preset)
        
        # Generate output path
        input_file = Path(input_path)
        output_path = input_file.parent / f"{input_file.stem}_{preset}.mp4"
        
        # Build FFmpeg command based on preset
        cmd = [
            self.ffmpeg_path,
            '-hide_banner',
            '-loglevel', 'info',
            '-progress', 'pipe:1',  # Output progress to stdout
            '-i', input_path
        ]
        
        # Add preset parameters
        cmd.extend(preset_config['ffmpeg_args'])
        cmd.append(str(output_path))
        
        # Check guardrails before starting this CPU/GPU intensive operation
        await self.ensure_guardrails_clear()
        
        self.logger.info(f"Starting transcode ({preset}): {input_path} -> {output_path}")
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Monitor progress and guardrails
            last_progress = 0
            while process.returncode is None:
                # Check guardrails
                is_blocked, reason, _ = await self.check_guardrails()
                if is_blocked:
                    self.logger.warning(f"Guardrails activated during transcode: {reason}, terminating FFmpeg")
                    process.terminate()
                    await process.wait()
                    raise GuardrailsBlocked(reason, 60)
                
                # Read progress from FFmpeg
                try:
                    line = await asyncio.wait_for(process.stdout.readline(), timeout=1.0)
                    if line:
                        line = line.decode('utf-8', errors='ignore').strip()
                        # Parse progress from FFmpeg output
                        if 'out_time_ms=' in line:
                            # Extract progress percentage
                            # This is simplified - real implementation would parse properly
                            progress = self.parse_ffmpeg_progress(line)
                            if progress > last_progress:
                                await self.report_progress(job_id, progress)
                                last_progress = progress
                except asyncio.TimeoutError:
                    continue
                
                # Check if process has ended
                if process.returncode is not None:
                    break
            
            _, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='ignore')
                raise RuntimeError(f"FFmpeg transcode failed: {error_msg}")
            
            return {
                'output_path': str(output_path),
                'output_size': output_path.stat().st_size,
                'preset': preset,
                'success': True
            }
            
        except GuardrailsBlocked:
            if output_path.exists():
                output_path.unlink()
            raise
            
        except Exception as e:
            if output_path.exists():
                output_path.unlink()
            raise
    
    async def handle_proxy(self, job_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle proxy creation (DNxHR, very CPU intensive).
        """
        input_path = payload.get('input_path')
        codec = payload.get('codec', 'dnxhr_lb')
        
        if not input_path or not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        # Generate output path
        input_file = Path(input_path)
        output_path = input_file.parent / f"{input_file.stem}_proxy.mov"
        
        # Build FFmpeg command for proxy
        cmd = [
            self.ffmpeg_path,
            '-hide_banner',
            '-loglevel', 'error',
            '-i', input_path,
            '-map', '0:v:0',  # First video stream
            '-c:v', 'dnxhd',
            '-profile:v', codec,
            '-vf', 'scale=-2:1080',  # Scale to 1080p maintaining aspect ratio
            '-map', '0:a?',  # Optional audio
            '-c:a', 'pcm_s16le',  # Uncompressed audio for editing
            '-timecode', '00:00:00:00',
            str(output_path)
        ]
        
        # Check guardrails - proxy creation is VERY CPU intensive
        await self.ensure_guardrails_clear()
        
        self.logger.info(f"Starting proxy creation ({codec}): {input_path} -> {output_path}")
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Monitor with more frequent guardrail checks for CPU intensive work
            check_interval = 2.0  # Check every 2 seconds for proxy jobs
            while process.returncode is None:
                is_blocked, reason, _ = await self.check_guardrails()
                if is_blocked:
                    self.logger.warning(f"Guardrails activated during proxy creation: {reason}")
                    process.terminate()
                    await process.wait()
                    raise GuardrailsBlocked(reason, 120)  # Longer retry for proxy jobs
                
                try:
                    await asyncio.wait_for(process.wait(), timeout=check_interval)
                except asyncio.TimeoutError:
                    continue
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='ignore')
                raise RuntimeError(f"Proxy creation failed: {error_msg}")
            
            return {
                'output_path': str(output_path),
                'output_size': output_path.stat().st_size,
                'codec': codec,
                'success': True
            }
            
        except GuardrailsBlocked:
            if output_path.exists():
                output_path.unlink()
            raise
            
        except Exception as e:
            if output_path.exists():
                output_path.unlink()
            raise
    
    def get_transcode_preset(self, preset: str) -> Dict[str, Any]:
        """Get FFmpeg arguments for a transcode preset"""
        presets = {
            'web_1080p': {
                'ffmpeg_args': [
                    '-c:v', 'libx264',
                    '-preset', 'medium',
                    '-crf', '23',
                    '-vf', 'scale=-2:1080',
                    '-c:a', 'aac',
                    '-b:a', '128k',
                    '-movflags', '+faststart'
                ]
            },
            'web_720p': {
                'ffmpeg_args': [
                    '-c:v', 'libx264',
                    '-preset', 'fast',
                    '-crf', '25',
                    '-vf', 'scale=-2:720',
                    '-c:a', 'aac',
                    '-b:a', '96k',
                    '-movflags', '+faststart'
                ]
            },
            'archive': {
                'ffmpeg_args': [
                    '-c:v', 'libx265',
                    '-preset', 'slow',
                    '-crf', '20',
                    '-c:a', 'aac',
                    '-b:a', '192k',
                    '-movflags', '+faststart'
                ]
            }
        }
        
        return presets.get(preset, presets['web_1080p'])
    
    def parse_ffmpeg_progress(self, line: str) -> float:
        """Parse progress from FFmpeg output line"""
        # Simplified progress parsing
        # Real implementation would properly parse FFmpeg's progress output
        return 0.0