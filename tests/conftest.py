import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, AsyncMock
import aiosqlite

from app.api.db.database import init_db, close_db, get_db
from app.api.services.nats_service import NATSService
from app.api.services.config_service import ConfigService


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def test_db():
    """Create a test database."""
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    
    # Initialize database
    import os
    os.environ["DB_PATH"] = db_path
    
    await init_db()
    db = await get_db()
    
    yield db
    
    # Cleanup
    await close_db()
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def mock_nats():
    """Create a mock NATS service."""
    nats = Mock(spec=NATSService)
    nats.connect = AsyncMock()
    nats.disconnect = AsyncMock()
    nats.publish_job = AsyncMock()
    nats.publish_event = AsyncMock()
    nats.publish_metric = AsyncMock()
    nats.subscribe_jobs = AsyncMock()
    nats.is_connected = True
    
    return nats


@pytest.fixture
def mock_config():
    """Create a mock configuration service."""
    config = Mock(spec=ConfigService)
    config.load_config = AsyncMock()
    config.save_config = AsyncMock()
    config.update_config = AsyncMock()
    config.get = Mock(return_value=None)
    config.get_all = Mock(return_value={})
    
    return config


@pytest.fixture
def temp_media_dir():
    """Create a temporary directory with test media files."""
    temp_dir = tempfile.mkdtemp()
    media_dir = Path(temp_dir) / "media"
    media_dir.mkdir()
    
    # Create test files
    (media_dir / "test.mp4").write_text("fake video content")
    (media_dir / "test.mkv").write_text("fake video content")
    (media_dir / "test.jpg").write_text("fake image content")
    
    yield media_dir
    
    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_job_data():
    """Sample job data for testing."""
    return {
        "id": "test_job_123",
        "type": "remux",
        "data": {
            "input_path": "/test/input.mkv",
            "output_format": "mov",
            "faststart": True
        }
    }


@pytest.fixture
def sample_asset_data():
    """Sample asset data for testing."""
    return {
        "id": "asset_123",
        "abs_path": "/test/media/video.mp4",
        "drive_hint": "drive_d",
        "size": 1024000,
        "duration_sec": 120.5,
        "video_codec": "h264",
        "audio_codec": "aac",
        "width": 1920,
        "height": 1080,
        "fps": 30.0,
        "container": "mp4"
    }


@pytest.fixture
def sample_rule_data():
    """Sample rule data for testing."""
    return {
        "id": "rule_123",
        "name": "Test Rule",
        "enabled": True,
        "priority": 100,
        "when_json": {
            "event": "file.closed",
            "path_glob": "*.mkv",
            "min_quiet_seconds": 45
        },
        "do_json": [
            {"type": "ffmpeg_remux", "params": {"container": "mov"}},
            {"type": "index_asset", "params": {}}
        ]
    }