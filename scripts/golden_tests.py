#!/usr/bin/env python3
"""
Golden media tests for StreamOps pipelines.
Tests media processing with known inputs and expected outputs.
"""

import os
import sys
import json
import hashlib
import asyncio
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Tuple
import subprocess

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.worker.jobs.remux import RemuxJob
from app.worker.jobs.thumbnail import ThumbnailJob
from app.worker.jobs.proxy import ProxyJob
from app.worker.jobs.transcode import TranscodeJob


class GoldenMediaTest:
    """Golden media test runner."""
    
    def __init__(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="streamops_golden_"))
        self.results: List[Dict[str, Any]] = []
        
    def cleanup(self):
        """Clean up test directory."""
        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
    
    async def run_all_tests(self) -> bool:
        """Run all golden media tests."""
        print("🎬 StreamOps Golden Media Tests")
        print("=" * 50)
        
        # Create test media files
        await self.create_test_media()
        
        # Run tests
        tests = [
            self.test_remux_mkv_to_mov(),
            self.test_thumbnail_generation(),
            self.test_proxy_creation(),
            self.test_web_transcode(),
        ]
        
        results = await asyncio.gather(*tests, return_exceptions=True)
        
        # Print results
        print("\n" + "=" * 50)
        print("Test Results:")
        print("-" * 50)
        
        passed = 0
        failed = 0
        
        for i, result in enumerate(results):
            test_name = tests[i].__name__ if hasattr(tests[i], '__name__') else f"Test {i+1}"
            
            if isinstance(result, Exception):
                print(f"❌ {test_name}: FAILED - {result}")
                failed += 1
            elif result:
                print(f"✅ {test_name}: PASSED")
                passed += 1
            else:
                print(f"❌ {test_name}: FAILED")
                failed += 1
        
        print("-" * 50)
        print(f"Total: {passed} passed, {failed} failed")
        
        # Cleanup
        self.cleanup()
        
        return failed == 0
    
    async def create_test_media(self):
        """Create test media files using FFmpeg."""
        print("Creating test media files...")
        
        # Create a 5-second test video (1920x1080, 30fps)
        test_mkv = self.test_dir / "test.mkv"
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc=duration=5:size=1920x1080:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=1000:duration=5",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac",
            str(test_mkv)
        ]
        
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            print(f"Failed to create test media: {result.stderr.decode()}")
            return False
        
        print(f"✓ Created test video: {test_mkv}")
        
        # Create MP4 version
        test_mp4 = self.test_dir / "test.mp4"
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-i", str(test_mkv),
            "-c", "copy",
            str(test_mp4)
        ])
        print(f"✓ Created test video: {test_mp4}")
        
        return True
    
    async def test_remux_mkv_to_mov(self) -> bool:
        """Test remuxing MKV to MOV."""
        print("\nTest: Remux MKV to MOV")
        
        job = RemuxJob()
        input_file = self.test_dir / "test.mkv"
        output_file = self.test_dir / "test_remuxed.mov"
        
        job_data = {
            "id": "golden_remux_001",
            "data": {
                "input_path": str(input_file),
                "output_format": "mov",
                "output_path": str(output_file),
                "faststart": True
            }
        }
        
        # Mock update_progress
        job.update_progress = lambda *args: None
        
        try:
            result = await job.process(job_data)
            
            # Verify output
            if not output_file.exists():
                raise Exception("Output file not created")
            
            if output_file.stat().st_size == 0:
                raise Exception("Output file is empty")
            
            # Verify it's a valid MOV file
            probe_result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_format", "-of", "json", str(output_file)],
                capture_output=True
            )
            
            if probe_result.returncode != 0:
                raise Exception("Output file is not a valid media file")
            
            format_info = json.loads(probe_result.stdout)
            if "mov" not in format_info["format"]["format_name"]:
                raise Exception(f"Output format is {format_info['format']['format_name']}, expected mov")
            
            print(f"  ✓ Successfully remuxed to MOV ({output_file.stat().st_size} bytes)")
            return True
            
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            return False
    
    async def test_thumbnail_generation(self) -> bool:
        """Test thumbnail generation."""
        print("\nTest: Thumbnail Generation")
        
        job = ThumbnailJob()
        input_file = self.test_dir / "test.mp4"
        
        job_data = {
            "id": "golden_thumb_001",
            "data": {
                "input_path": str(input_file),
                "asset_id": "test_asset_001"
            }
        }
        
        # Mock update_progress
        job.update_progress = lambda *args: None
        
        # Override output directory
        import os
        os.environ["THUMBS_DIR"] = str(self.test_dir / "thumbs")
        
        try:
            result = await job.process(job_data)
            
            # Verify outputs
            if not result.get("success"):
                raise Exception("Job failed")
            
            poster_path = Path(result.get("poster_path", ""))
            if not poster_path.exists():
                raise Exception("Poster thumbnail not created")
            
            # Verify it's a valid image
            probe_result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(poster_path)],
                capture_output=True
            )
            
            if probe_result.returncode != 0:
                raise Exception("Poster is not a valid image")
            
            print(f"  ✓ Generated poster thumbnail ({poster_path.stat().st_size} bytes)")
            return True
            
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            return False
    
    async def test_proxy_creation(self) -> bool:
        """Test proxy file creation."""
        print("\nTest: Proxy Creation (DNxHR)")
        
        job = ProxyJob()
        input_file = self.test_dir / "test.mp4"
        output_file = self.test_dir / "test_proxy.mov"
        
        job_data = {
            "id": "golden_proxy_001",
            "data": {
                "input_path": str(input_file),
                "output_path": str(output_file),
                "codec": "dnxhr_lb"
            }
        }
        
        # Mock update_progress
        job.update_progress = lambda *args: None
        
        try:
            result = await job.process(job_data)
            
            # Verify output
            if not output_file.exists():
                raise Exception("Proxy file not created")
            
            # Verify codec
            probe_result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(output_file)],
                capture_output=True
            )
            
            if probe_result.returncode != 0:
                raise Exception("Proxy is not a valid media file")
            
            streams = json.loads(probe_result.stdout)
            video_stream = next((s for s in streams["streams"] if s["codec_type"] == "video"), None)
            
            if not video_stream:
                raise Exception("No video stream in proxy")
            
            if "dnxhd" not in video_stream.get("codec_name", ""):
                raise Exception(f"Wrong codec: {video_stream.get('codec_name')}")
            
            print(f"  ✓ Created DNxHR proxy ({output_file.stat().st_size} bytes)")
            return True
            
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            return False
    
    async def test_web_transcode(self) -> bool:
        """Test web transcode preset."""
        print("\nTest: Web Transcode (1080p)")
        
        job = TranscodeJob()
        input_file = self.test_dir / "test.mkv"
        output_file = self.test_dir / "test_web.mp4"
        
        job_data = {
            "id": "golden_transcode_001",
            "data": {
                "input_path": str(input_file),
                "output_path": str(output_file),
                "preset": "web_1080p"
            }
        }
        
        # Mock update_progress
        job.update_progress = lambda *args: None
        
        try:
            result = await job.process(job_data)
            
            # Verify output
            if not output_file.exists():
                raise Exception("Transcoded file not created")
            
            # Verify format and codec
            probe_result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(output_file)],
                capture_output=True
            )
            
            if probe_result.returncode != 0:
                raise Exception("Transcoded file is not valid")
            
            info = json.loads(probe_result.stdout)
            video_stream = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
            
            if not video_stream:
                raise Exception("No video stream in output")
            
            if video_stream.get("codec_name") != "h264":
                raise Exception(f"Wrong codec: {video_stream.get('codec_name')}")
            
            if video_stream.get("height") != 1080:
                raise Exception(f"Wrong resolution: {video_stream.get('height')}p")
            
            print(f"  ✓ Transcoded to web format ({output_file.stat().st_size} bytes)")
            print(f"    - Codec: {video_stream.get('codec_name')}")
            print(f"    - Resolution: {video_stream.get('width')}x{video_stream.get('height')}")
            print(f"    - Bitrate: {info['format'].get('bit_rate', 'N/A')} bps")
            
            return True
            
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            return False


async def main():
    """Run golden media tests."""
    tester = GoldenMediaTest()
    success = await tester.run_all_tests()
    
    if not success:
        sys.exit(1)
    
    print("\n✨ All golden media tests passed!")


if __name__ == "__main__":
    asyncio.run(main())