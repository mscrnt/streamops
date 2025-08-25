# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

StreamOps is a containerized media pipeline automation tool for streamers. It runs as a single Docker container that watches recording folders, automatically remuxes files, creates proxies, generates thumbnails, manages overlays, and integrates with OBS.

## Architecture

Single Docker image containing:
- **API Gateway**: FastAPI/Uvicorn (Python 3.11) - REST + WebSocket
- **UI**: React + Vite built to static assets, served at `/app`
- **Job Orchestrator**: Python rules engine and scheduler
- **Workers**: FFmpeg, PySceneDetect, waveform, thumbnails processing
- **Overlay Server**: Browser-source overlays at `http://localhost:7767/overlay/`
- **Queue**: NATS JetStream embedded for durable job queues
- **Database**: SQLite with FTS5 + JSON1 extensions
- **Process Supervisor**: s6-overlay for managing all services

## Project Structure

```
/app
  /api            # FastAPI app, routers, schemas, services
  /worker         # Job runners, ffmpeg wrappers, scene detect, watchers
  /overlay        # Overlay templates, renderer, WS control
  /rules          # Default rule packs (YAML) and examples
  /ui             # React/Vite source (built into /static)
  /pkg            # Dockerfile, s6 services, entrypoints
  /scripts        # Dev & QA scripts (simulate, golden media tests)
  /docs           # User guide assets
```

Runtime data structure:
```
/data
  /db/streamops.db   # SQLite database
  /logs/*.json       # Structured JSON logs
  /thumbs/{id}/      # poster.jpg, sprite.jpg, hover.mp4
  /cache/            # Temporary files
  config.json        # Configuration
```

## Development Commands

### Building the Container
```bash
# Build the full image
docker build -t mscrnt/streamops:latest .

# Development build with hot-reload
docker-compose -f docker-compose.dev.yml up
```

### Running Tests
```bash
# Run Python tests
pytest app/tests/

# Run UI tests
cd app/ui && npm test

# Golden media tests
python scripts/golden_tests.py
```

### Local Development
```bash
# API development (with hot reload)
cd app && uvicorn api.main:app --reload --port 7767

# UI development
cd app/ui && npm run dev

# Worker development
python -m app.worker.main
```

## Database Schema

Key tables (prefix `so_`):
- `so_assets`: Media files with metadata, codecs, dimensions
- `so_sessions`: OBS recording sessions with markers
- `so_jobs`: Job queue and status tracking
- `so_rules`: Automation rules (YAML-based DSL)
- `so_thumbs`: Thumbnail and preview paths
- `so_overlays`: Overlay manifests and schedules
- `so_configs`: Key-value configuration store
- `so_reports`: Weekly aggregated metrics

Full-text search: `so_assets_fts` virtual table

## Rules DSL

Rules are YAML-based with conditions (`when`) and actions (`do`):
- **Actions**: `ffmpeg_remux`, `move`, `copy`, `index_asset`, `thumbs`, `proxy`, `transcode_preset`, `tag`, `overlay_update`
- **Guardrails**: `pause_if_recording`, `pause_if_gpu_pct_above`, `pause_if_cpu_pct_above`

## FFmpeg Command Patterns

### Remux (stream copy)
```bash
ffmpeg -hide_banner -loglevel error -fflags +genpts \
  -i "{in}" -map 0 -c copy -movflags +faststart "{out}.mov"
```

### Proxy Creation (DNxHR LB)
```bash
ffmpeg -i "{in}" -map 0:v:0 -c:v dnxhd -profile:v dnxhr_lb -vf "scale=-2:1080" \
  -map 0:a? -c:a pcm_s16le -timecode 00:00:00:00 "{out}_proxy.mov"
```

### Lossless Clip Export
```bash
ffmpeg -ss {in_ts} -to {out_ts} -i "{in}" -c copy "{clip_out}.mp4"
```

## Environment Variables

Key configuration:
- `ROLE`: `all` | `api` | `worker` | `overlay` | `broker`
- `NATS_ENABLE`: Enable internal queue (default: true)
- `GPU_GUARD_PCT`: GPU usage threshold (default: 40)
- `CPU_GUARD_PCT`: CPU usage threshold (default: 70)
- `OBS_WS_URL`: OBS WebSocket URL (e.g., `ws://host.docker.internal:4455`)
- `OBS_WS_PASSWORD`: OBS WebSocket password

## Ports and Volumes

Ports:
- `7767/tcp`: UI/API
- `7768/tcp`: NATS (optional external)
- `7769/tcp`: Overlay WebSocket

Volumes:
- `/data`: Config, DB, logs, cache, thumbnails
- `/mnt/drive_*`: Bind mounts to host drives

## Testing Patterns

- Use golden media set for pipeline verification
- Test with file locks and growing files
- Verify GPU/CPU guardrails work correctly
- Test OBS WebSocket events with mock server
- Ensure idempotent job processing