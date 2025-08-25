# StreamOps

> **Automated media pipeline for content creators** — A containerized solution that handles post-recording workflows including smart remuxing, file organization, proxy generation, thumbnail creation, and asset management. Designed for streamers and content creators with multi-drive setups.

---

## Table of Contents

- [Features](#features)
- [System Requirements](#system-requirements)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Configuration](#configuration)
- [Automation Rules](#automation-rules)
- [API Documentation](#api-documentation)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## Features

### 🎬 **Media Processing**
- **Lossless Remuxing** - Convert between containers (MKV→MOV/MP4) without re-encoding
- **Smart File Detection** - Waits for files to finish writing before processing
- **Proxy Generation** - Create editing proxies (DNxHR, ProRes, CineForm)
- **Thumbnail Generation** - Poster frames, sprite sheets, and hover previews
- **Scene Detection** - Automatic scene change detection for clip creation
- **Batch Processing** - Handle multiple files with queue management

### 📁 **File Management**
- **Automated Organization** - Move files to structured folders by date/game/project
- **Multi-Drive Support** - Monitor and manage files across multiple storage drives
- **Watch Folders** - Automatic detection and processing of new recordings
- **Full-Text Search** - Instant search across all indexed media assets
- **Metadata Extraction** - Comprehensive media information (codec, resolution, duration)

### 🤖 **Automation**
- **Rules Engine** - YAML-based automation workflows with conditions and actions
- **Performance Guardrails** - Pause processing during recording or high system load
- **Scheduled Tasks** - Time-based automation for maintenance and archival
- **Event-Driven Processing** - React to file events, OBS events, or manual triggers
- **Custom Hooks** - Execute custom scripts as part of workflows

### 🎨 **Streaming Features**
- **OBS Integration** - WebSocket connection for recording awareness and session tracking
- **Overlay System** - Browser source overlays with rotation and scheduling
- **Impression Tracking** - Analytics for overlay views and engagement
- **Clip Assistant** - Waveform visualization and lossless clip extraction
- **Session Management** - Track recording sessions with markers and metadata

### 📊 **Monitoring & Reporting**
- **Real-time Dashboard** - System status, active jobs, and performance metrics
- **Weekly Reports** - Recording statistics, storage usage, and productivity metrics
- **Job Queue Visualization** - Monitor processing progress and queue depth
- **System Health Checks** - CPU, GPU, memory, and disk usage monitoring

### 🔧 **Technical Features**
- **Single Container Deployment** - Everything in one Docker image
- **RESTful API** - Complete API for integration and automation
- **WebSocket Support** - Real-time updates and control
- **Remote Workers** - Distribute processing across multiple machines
- **GPU Acceleration** - NVIDIA GPU support for transcoding

---

## System Requirements

### Minimum Requirements
- **Operating System**: 
  - Windows 10/11 with WSL2
  - macOS 12+ (Monterey or later)
  - Linux (Ubuntu 20.04+, Debian 11+, RHEL 8+)
- **Docker**: 
  - Docker Desktop 4.0+ (Windows/macOS)
  - Docker Engine 20.10+ (Linux)
- **Hardware**:
  - CPU: 4 cores (8 threads recommended)
  - RAM: 8GB minimum (16GB recommended)
  - Storage: 10GB for application + space for media files
- **Network**: 
  - Ports 7767-7769 available
  - Local network access for remote workers (optional)

### Recommended Setup
- **CPU**: 8+ cores for parallel processing
- **RAM**: 16GB+ for large file operations
- **GPU**: NVIDIA GPU with CUDA support for accelerated transcoding
- **Storage**: 
  - Fast NVMe SSD for active recordings
  - Large HDD for archive storage
  - Separate SSD for editing proxies
- **Network**: Gigabit Ethernet for remote workers

---

## Installation

### Prerequisites
1. Install Docker Desktop (Windows/macOS) or Docker Engine (Linux)
2. Ensure Docker is running and configured
3. For GPU support, install NVIDIA Container Toolkit

### Quick Start

#### Basic Installation
```bash
# Pull the StreamOps image
docker pull mscrnt/streamops:latest

# Create data directory
mkdir -p /opt/streamops/data

# Run StreamOps
docker run --name streamops -d \
  --restart unless-stopped \
  -p 7767:7767 \
  -v /opt/streamops/data:/data \
  -v /path/to/media:/mnt/media \
  mscrnt/streamops:latest
```

#### Windows Installation with Multiple Drives
```powershell
# Create data directory
mkdir C:\StreamOps\data

# Run with multiple drives mapped
docker run --name streamops -d --restart unless-stopped `
  -p 7767:7767 -p 7768:7768 `
  -v C:\StreamOps\data:/data `
  -v D:\Recordings:/mnt/recordings `
  -v E:\Archive:/mnt/archive `
  -v F:\Editing:/mnt/editing `
  mscrnt/streamops:latest
```

#### GPU-Accelerated Setup
```bash
docker run --name streamops -d \
  --restart unless-stopped \
  --gpus all \
  -p 7767:7767 \
  -v /opt/streamops/data:/data \
  -v /media:/mnt/media \
  -e GPU_GUARD_PCT=40 \
  mscrnt/streamops:latest
```

### Access the Application
Open your browser and navigate to: **http://localhost:7767**

The first-run wizard will guide you through:
1. Setting up watch folders
2. Configuring automation rules
3. Connecting to OBS (optional)
4. Setting performance limits

---

## Architecture

StreamOps uses a microservices architecture within a single container, managed by s6-overlay:

```
┌─────────────────────────────────────────────────┐
│                 StreamOps Container              │
├─────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │   API    │  │    UI    │  │  Overlay │      │
│  │ (FastAPI)│  │  (React) │  │  Server  │      │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘      │
│       │             │              │            │
│  ┌────┴─────────────┴──────────────┴────┐      │
│  │         NATS JetStream Queue         │      │
│  └────┬─────────────┬──────────────┬────┘      │
│       │             │              │            │
│  ┌────┴────┐  ┌────┴────┐  ┌─────┴────┐       │
│  │ Worker 1│  │ Worker 2│  │ Watcher  │       │
│  │ (FFmpeg)│  │ (Thumb) │  │ (Files)  │       │
│  └─────────┘  └─────────┘  └──────────┘       │
│                                                 │
│  ┌──────────────────────────────────────┐      │
│  │     SQLite Database (FTS5+JSON1)     │      │
│  └──────────────────────────────────────┘      │
└─────────────────────────────────────────────────┘
```

### Components
- **API Gateway**: FastAPI application serving REST endpoints and WebSocket connections
- **Web UI**: React SPA with real-time updates via WebSocket
- **Job Queue**: NATS JetStream for reliable, distributed job processing
- **Workers**: Python-based processors for media operations
- **File Watcher**: Monitors directories for new files with stability detection
- **Database**: SQLite with full-text search and JSON support
- **Overlay Server**: Serves browser source overlays with WebSocket control

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ROLE` | `all` | Service role: `all`, `api`, `worker`, `overlay`, `broker` |
| `NATS_ENABLE` | `true` | Enable internal message queue |
| `DB_PATH` | `/data/db/streamops.db` | Database file location |
| `CACHE_DIR` | `/data/cache` | Temporary file storage |
| `THUMBS_DIR` | `/data/thumbs` | Thumbnail storage location |
| `LOG_LEVEL` | `INFO` | Logging verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

### Performance Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `GPU_GUARD_PCT` | `40` | GPU usage threshold to pause processing |
| `CPU_GUARD_PCT` | `70` | CPU usage threshold to pause processing |
| `PAUSE_WHEN_RECORDING` | `true` | Pause processing during active recording |
| `MAX_CONCURRENT_JOBS` | `2` | Maximum parallel processing jobs |
| `FILE_QUIET_SECONDS` | `45` | Seconds to wait before processing files |

### OBS Integration (Optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `OBS_WS_URL` | - | OBS WebSocket URL (e.g., `ws://host.docker.internal:4455`) |
| `OBS_WS_PASSWORD` | - | OBS WebSocket password |
| `OBS_AUTO_CONNECT` | `true` | Automatically connect to OBS on startup |

### Configuration File
Settings are stored in `/data/config.json` and can be modified through the UI or API.

---

## Automation Rules

StreamOps uses a YAML-based rules engine for automation. Rules define conditions and actions for processing media files.

### Rule Structure
```yaml
name: Rule Name
enabled: true
priority: 100  # Higher priority runs first
when:          # Conditions that trigger the rule
  event: file.closed
  path_glob: "*.mkv"
do:            # Actions to perform
  - action_name:
      parameter: value
```

### Example Rules

#### Automatic Remux and Organization
```yaml
name: Process Recordings
when:
  event: file.closed
  path_glob: "/mnt/recordings/**/*.mkv"
  min_quiet_seconds: 45
do:
  - ffmpeg_remux:
      container: mov
      faststart: true
  - move:
      dest: "/mnt/editing/{YYYY}/{MM}/{DD}/"
  - index_asset: {}
  - make_proxies_if:
      min_duration_sec: 900
```

#### Archive Old Content
```yaml
name: Monthly Archive
when:
  schedule: "0 2 * * 0"  # Weekly at 2 AM Sunday
  conditions:
    age_days: {"$gte": 30}
do:
  - transcode_preset:
      preset: archive_h265
  - move:
      dest: "/mnt/archive/{YYYY}-{MM}/"
```

### Available Actions
- `ffmpeg_remux` - Convert container format without re-encoding
- `transcode_preset` - Transcode with predefined settings
- `proxy` - Generate editing proxies
- `thumbnail` - Create thumbnails and previews
- `move` / `copy` - File operations
- `index_asset` - Add to media database
- `tag` - Apply metadata tags
- `custom_hook` - Execute custom scripts

---

## API Documentation

StreamOps provides a comprehensive REST API for integration and automation.

### Base URL
```
http://localhost:7767/api
```

### Authentication
Currently uses local-only access. Token authentication planned for future releases.

### Main Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health/live` | GET | Liveness check |
| `/health/ready` | GET | Readiness check with component status |
| `/assets` | GET | List media assets |
| `/assets/{id}` | GET | Get specific asset |
| `/assets/search` | POST | Search assets with filters |
| `/jobs` | GET | List processing jobs |
| `/jobs/{id}` | GET | Get job status |
| `/rules` | GET/POST | Manage automation rules |
| `/config` | GET/PUT | System configuration |

### WebSocket Endpoints
- `/ws` - Real-time job updates
- `/overlay/ws` - Overlay control channel

### Example: Create Processing Job
```bash
curl -X POST http://localhost:7767/api/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "type": "remux",
    "input_path": "/mnt/recordings/video.mkv",
    "output_format": "mov"
  }'
```

Full API documentation available at `http://localhost:7767/docs` when running.

---

## Development

### Building from Source

```bash
# Clone repository
git clone https://github.com/mscrnt/streamops.git
cd streamops

# Build Docker image
docker build -t streamops:dev .

# Run development environment
docker-compose -f docker-compose.dev.yml up
```

### Project Structure
```
streamops/
├── app/
│   ├── api/          # FastAPI backend
│   ├── worker/       # Job processors
│   ├── overlay/      # Overlay system
│   ├── ui/           # React frontend
│   └── rules/        # Default rule packs
├── tests/            # Test suite
├── scripts/          # Utility scripts
└── Dockerfile        # Container definition
```

### Testing
```bash
# Run Python tests
pytest tests/

# Run golden media tests
python scripts/golden_tests.py

# Run UI tests
cd app/ui && npm test
```

---

## Troubleshooting

### Common Issues

#### Container Won't Start
```bash
# Check container status
docker ps -a

# View logs
docker logs streamops

# Verify port availability
netstat -an | grep 7767
```

#### Files Not Being Processed
1. Verify watch folder paths in the UI
2. Check file has been quiet for configured time (default 45s)
3. Ensure file extension matches rule patterns
4. Check job queue for errors: `http://localhost:7767/jobs`

#### High Resource Usage
- Adjust `GPU_GUARD_PCT` and `CPU_GUARD_PCT` environment variables
- Reduce `MAX_CONCURRENT_JOBS`
- Enable `PAUSE_WHEN_RECORDING` if using OBS

#### Permission Errors
- Ensure Docker has access to mapped drives
- On Windows, check Docker Desktop file sharing settings
- Verify container user has read/write permissions

### Getting Help
- Check logs: `docker logs streamops`
- View system status: `http://localhost:7767/health/ready`
- Enable debug logging: `-e LOG_LEVEL=DEBUG`

---

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Areas for Contribution
- Additional media processing actions
- UI/UX improvements
- Documentation and tutorials
- Bug fixes and performance optimizations
- Integration with other streaming tools

### Development Setup
1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request

---

## License

MIT License - See [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- FFmpeg team for media processing capabilities
- NATS.io for reliable message queuing
- FastAPI and React communities
- All contributors and testers

---

## Quick Links

- 📚 [Full Documentation](app/docs/QUICKSTART.md)
- 🐛 [Report Issues](https://github.com/mscrnt/streamops/issues)
- 💬 [Discussions](https://github.com/mscrnt/streamops/discussions)
- 🚀 [Releases](https://github.com/mscrnt/streamops/releases)

---

*StreamOps - Automate your media pipeline so you can focus on creating content.*
