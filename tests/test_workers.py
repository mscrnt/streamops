import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path

from app.worker.jobs.base import BaseJob
from app.worker.jobs.remux import RemuxJob
from app.worker.jobs.thumbnail import ThumbnailJob
from app.worker.jobs.proxy import ProxyJob
from app.worker.jobs.index import IndexJob
from app.worker.watchers.drive_watcher import DriveWatcher


class TestBaseJob:
    
    @pytest.mark.unit
    async def test_update_progress(self, test_db):
        """Test job progress update."""
        job = BaseJob()
        
        # Insert test job
        await test_db.execute(
            "INSERT INTO so_jobs (id, type, payload_json, state) VALUES (?, ?, ?, ?)",
            ("test_job", "test", "{}", "running")
        )
        await test_db.commit()
        
        # Update progress
        await job.update_progress("test_job", 50.0)
        
        # Verify update
        async with test_db.execute(
            "SELECT progress FROM so_jobs WHERE id = ?",
            ("test_job",)
        ) as cursor:
            row = await cursor.fetchone()
            assert row[0] == 50.0
    
    @pytest.mark.unit
    async def test_run_command(self):
        """Test running shell command."""
        job = BaseJob()
        
        # Run echo command
        returncode, stdout, stderr = await job.run_command(["echo", "test"])
        
        assert returncode == 0
        assert stdout.strip() == "test"
        assert stderr == ""
    
    @pytest.mark.unit
    def test_get_temp_path(self):
        """Test getting temporary file path."""
        job = BaseJob()
        
        path = job.get_temp_path("test_job", ".mp4")
        assert "test_job.mp4" in path
        assert "/cache/" in path or "\\cache\\" in path


class TestRemuxJob:
    
    @pytest.mark.worker
    @patch("app.worker.jobs.remux.RemuxJob.run_command")
    async def test_process_remux(self, mock_run_command, temp_media_dir):
        """Test remux job processing."""
        mock_run_command.return_value = (0, "", "")
        
        job = RemuxJob()
        
        # Create test input file
        input_file = temp_media_dir / "input.mkv"
        input_file.write_text("fake content")
        
        job_data = {
            "id": "remux_123",
            "data": {
                "input_path": str(input_file),
                "output_format": "mov"
            }
        }
        
        # Mock update_progress
        job.update_progress = AsyncMock()
        
        # Process job
        result = await job.process(job_data)
        
        assert result["success"] is True
        assert result["output_format"] == "mov"
        assert mock_run_command.called
        
        # Verify FFmpeg command
        call_args = mock_run_command.call_args[0][0]
        assert "ffmpeg" in call_args
        assert str(input_file) in call_args
        assert "-c" in call_args
        assert "copy" in call_args


class TestThumbnailJob:
    
    @pytest.mark.worker
    @patch("app.worker.jobs.thumbnail.ThumbnailJob.run_command")
    async def test_process_thumbnail(self, mock_run_command, temp_media_dir):
        """Test thumbnail job processing."""
        mock_run_command.return_value = (0, "", "")
        
        job = ThumbnailJob()
        
        input_file = temp_media_dir / "video.mp4"
        input_file.write_text("fake content")
        
        job_data = {
            "id": "thumb_123",
            "data": {
                "input_path": str(input_file),
                "asset_id": "asset_123"
            }
        }
        
        # Mock update_progress
        job.update_progress = AsyncMock()
        
        # Process job
        result = await job.process(job_data)
        
        assert result["success"] is True
        assert "poster_path" in result
        assert mock_run_command.called


class TestIndexJob:
    
    @pytest.mark.worker
    @patch("app.worker.jobs.index.IndexJob._get_file_hash")
    @patch("app.worker.jobs.index.IndexJob._get_media_info")
    async def test_process_index(self, mock_media_info, mock_hash, test_db, temp_media_dir):
        """Test index job processing."""
        mock_hash.return_value = "test_hash"
        mock_media_info.return_value = {
            "duration": 120.5,
            "width": 1920,
            "height": 1080,
            "video_codec": "h264",
            "audio_codec": "aac",
            "fps": 30.0,
            "container": "mp4"
        }
        
        job = IndexJob()
        
        input_file = temp_media_dir / "video.mp4"
        input_file.write_text("fake content")
        
        job_data = {
            "id": "index_123",
            "data": {
                "input_path": str(input_file)
            }
        }
        
        # Mock update_progress
        job.update_progress = AsyncMock()
        
        # Process job
        result = await job.process(job_data)
        
        assert result["success"] is True
        assert result["asset_id"] is not None
        
        # Verify asset was indexed
        async with test_db.execute(
            "SELECT * FROM so_assets WHERE abs_path = ?",
            (str(input_file),)
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None


class TestDriveWatcher:
    
    @pytest.mark.worker
    async def test_start_watcher(self, temp_media_dir, mock_nats):
        """Test starting drive watcher."""
        watcher = DriveWatcher(str(temp_media_dir), mock_nats)
        
        await watcher.start()
        assert watcher.running is True
        
        await watcher.stop()
        assert watcher.running is False
    
    @pytest.mark.worker
    async def test_handle_file_event(self, temp_media_dir, mock_nats):
        """Test handling file events."""
        watcher = DriveWatcher(str(temp_media_dir), mock_nats)
        
        test_file = temp_media_dir / "test.mp4"
        
        await watcher.handle_file_event(str(test_file), "created")
        
        # File should be tracked
        assert str(test_file) in watcher.file_tracker
        assert watcher.file_tracker[str(test_file)]["event_type"] == "created"
    
    @pytest.mark.worker
    async def test_file_stability_check(self, temp_media_dir, mock_nats):
        """Test file stability checking."""
        watcher = DriveWatcher(str(temp_media_dir), mock_nats)
        watcher.quiet_seconds = 0  # Immediate stability
        
        test_file = temp_media_dir / "test.mp4"
        test_file.write_text("content")
        
        # Add file to tracker
        await watcher.handle_file_event(str(test_file), "created")
        
        # Process stable file
        await watcher._process_stable_file(str(test_file))
        
        # Verify events were published
        mock_nats.publish_event.assert_called()
        mock_nats.publish_job.assert_called()