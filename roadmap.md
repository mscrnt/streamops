awesome — let’s build the **full-fat, no-compromises** StreamOps companion as a **single downloadable container image** that exposes a local web UI, talks to OBS (optionally), watches your drives, remuxes/transcodes safely, manages overlays, and can scale to remote workers later — all without re-architecting.

Below is a **complete, agent-ready blueprint**: architecture, modules, data model, pipelines, config, packaging, and an implementation TODO that your agent can execute step-by-step.

---

# StreamOps: Full Build Blueprint (single image, containerized)

## 0) Product scope (single install next to OBS)

* Runs **locally** on the streamer’s PC via Docker Desktop (Windows-first), reachable at `http://localhost:7767`.
* User maps drives (`A:\`, `D:\`, `E:\`, `F:\`) as **bind mounts** to the container.
* Optional connection to **OBS WebSocket** for start/stop/scene/marker events.
* All features available day one; **Pro-only** toggles are feature flags (no rework later).
* Optional **remote worker** mode using the **same image** with a different role.

---

## 1) Architecture (inside one image)

**Process supervisor:** `s6-overlay` (or `dumb-init` + a tiny supervisor script)

**Processes (all in one image):**

1. **API Gateway** (FastAPI/Uvicorn, Python 3.11)

   * REST + WebSocket for UI, OBS bridge, rules management, job control, metrics.
2. **UI** (React + Vite; built to static assets, served by API at `/app`).
3. **Job Orchestrator** (Python): rules engine, scheduler, fan-out to workers.
4. **Worker (local)**: FFmpeg, scene-detect, waveform, thumbnails, captions (optional).
5. **Overlay Server**: serves browser-source overlays at `http://localhost:7767/overlay/...`
6. **Queue Broker**: **NATS JetStream** embedded (single binary) for durable queues.

   * Local-only by default; if remote workers are enabled, the same broker can serve them.
7. **Index & DB**: **SQLite** file on a mounted volume (FTS5 + JSON1 enabled).
8. **OBS Bridge (optional)**: obs-websocket client that publishes events into the queue.

**GPU & performance:**

* NVIDIA runtime support (optional). If present, GPU-accelerated transcodes available.
* **Guardrails**: pause non-remux jobs while OBS is recording or if GPU/CPU > thresholds.

**Volumes & ports:**

* `/data` → config, DB, logs, cache, thumbnails, generated overlays
* `/mnt/drive_a`, `/mnt/drive_d`, `/mnt/drive_e`, `/mnt/drive_f` → user maps host drives
* Ports: `7767/tcp` (UI/API), `7768/tcp` (NATS internal; optional external), `7769/tcp` (overlay websockets)

---

## 2) Data model (SQLite + JSON columns)

Tables (prefix `so_`):

* `so_assets`

  * `id` (pk), `abs_path`, `drive_hint`, `size`, `mtime`, `ctime`, `hash_xxh64`, `hash_sha256` (nullable),
  * `duration_sec`, `video_codec`, `audio_codec`, `width`, `height`, `fps`,
  * `container`, `streams_json`, `tags_json`, `status`, `created_at`, `updated_at`
* `so_sessions` (recording sessions)

  * `id`, `start_ts`, `end_ts`, `scene_at_start`, `obs_profile`, `obs_collection`, `markers_json`, `metrics_json`
* `so_jobs`

  * `id`, `type`, `asset_id`, `payload_json`, `state` (queued|running|done|error|paused), `progress`, `error`, `created_at`, `updated_at`
* `so_rules`

  * `id`, `name`, `enabled`, `priority`, `when_json` (conditions), `do_json` (actions), `created_at`, `updated_at`
* `so_thumbs`

  * `asset_id`, `poster_path`, `sprite_path`, `hover_mp4_path`, `waveform_json`
* `so_overlays`

  * `id`, `name`, `manifest_json`, `schedule_json`, `stats_json`, `enabled`
* `so_configs`

  * key/value map (JSON) for global config, env overrides, OBS endpoint, feature flags
* `so_reports`

  * weekly aggregates: hours recorded, disk usage deltas, top games, backlog growth

**FTS (full-text) virtual table:** `so_assets_fts(content=so_assets, tokenize="porter")`
Index fields: `abs_path`, tags, sidecar text, captions (if generated).

---

## 3) Rule engine (declarative DSL)

**YAML format** (stored in DB; UI editor writes YAML/JSON):

```yaml
name: Remux-MKV-to-MOV-and-Move
enabled: true
priority: 10
when:
  any:
    - event: file_closed
      path_glob: "/mnt/drive_a/Recordings/**/*.mkv"
      min_quiet_seconds: 45
do:
  - ffmpeg_remux:
      container: mov
      faststart: true
  - move:
      dest: "/mnt/drive_f/Editing/{Game}/{YYYY}/{MM}/{DD}/"
  - write_sidecar:
      fields: [game, scene, start_ts, end_ts, avg_bitrate]
  - index_asset: {}
  - make_proxies_if:
      min_duration_sec: 900
      codec: "dnxhr_lb"
```

**Built-in actions:** `ffmpeg_remux`, `move`, `copy`, `index_asset`, `thumbs`, `sprite`, `hover_mp4`, `waveform`, `proxy`, `transcode_preset`, `social_export`, `archive`, `tag`, `overlay_update`, `report_emit`, `custom_hook`.

**Guardrails:** `pause_if_recording: true`, `pause_if_gpu_pct_above: 40`, `pause_if_cpu_pct_above: 70`.

---

## 4) Media pipelines (precise behaviors & commands)

**A. Remux → MOV (stream copy):**

```
ffmpeg -hide_banner -loglevel error -fflags +genpts \
  -i "{in}" -map 0 -c copy -movflags +faststart "{out}.mov"
```

**B. Proxy creation (DNxHR LB for smooth editing):**

```
ffmpeg -i "{in}" -map 0:v:0 -c:v dnxhd -profile:v dnxhr_lb -vf "scale=-2:1080" \
  -map 0:a? -c:a pcm_s16le -timecode 00:00:00:00 "{out}_proxy.mov"
```

**C. Hover-scrub (tiny looped MP4 + sprite sheet):**

* Extract N keyframes (e.g., every 20s):
  `ffmpeg -ss {t} -i "{in}" -frames:v 1 -q:v 4 "{tmp}/kf_{idx}.jpg"`
* Sprite: `ffmpeg -pattern_type glob -i 'kf_*.jpg' -filter_complex "tile=5x{rows}" "{sprite}.jpg"`
* Hover MP4 (short, low bitrate, intra):
  `ffmpeg -i "{in}" -vf "select='not(mod(n, {stride}))',scale=-2:360" -an -c:v libx264 -preset veryfast -x264-params keyint=15:min-keyint=15:scenecut=0 -t 6 "{hover}.mp4"`

**D. Scene-detect + Clip assist:**

* Use `PySceneDetect` (content-aware) + audio RMS peaks for candidate clip ranges.
* UI loads waveform + scene-change markers; `[i] [o]` → **lossless copy**:

```
ffmpeg -ss {in_ts} -to {out_ts} -i "{in}" -c copy "{clip_out}.mp4"
```

**E. Social exports (9:16 / 1:1):**

* Smart crop with safe face/active area heuristic (center bias + motion + HUD margins).
* Burned captions (optional; feed from later STT module).

---

## 5) OBS integration (optional, not required)

* Connect via `ws://host.docker.internal:4455` (Windows) with password.
* Subscribe to: `RecordingStarted`, `RecordingStopped`, `CurrentProgramSceneChanged`, markers via hotkey.
* On `RecordingStopped` → enqueue **Remux + Move** rule.
* Provide **Overlay Browser Source** URLs pointing to `http://localhost:7767/overlay/{name}`; schedules update via WebSocket (no scene JSON mutations unless user asks).

---

## 6) Overlay system (sponsor/brand packs)

* **Overlay manifests** (JSON): fonts, images, animations, safe areas.
* Server renders overlays as HTML5; controlled by schedule/rotator.
* **Impression log**: show counts, seconds on screen; export CSV.

---

## 7) Remote offload (same image, different role)

* Start additional containers as `ROLE=worker` on another machine; point to broker:

  * `NATS_URL=nats://<main-pc-ip>:7768`
* Workers pull `transcode`, `proxy`, `thumbs` jobs; results written back via API.

---

## 8) UI/UX (fast, simple, resilient)

* **Dashboard:** status (Recording/Idle/Processing), queue, guardrails.
* **Drives & Watch Folders:** add/edit with test buttons and path probes.
* **Rules Editor:** visual + YAML; “Simulate” against sample file.
* **Assets Browser:** instant search (FTS), thumb grid with hover-scrub, tags/faves.
* **Clip Assist:** waveform + markers, hotkeys, batch export.
* **Overlays:** schedule, live preview, browser-source URL copy.
* **Reports:** weekly studio report, disk pressure, backlog trends.
* **Settings:** OBS endpoint, feature flags, GPU/CPU thresholds, backup/restore config.

---

## 9) Configuration & secrets

* **Env vars** (with UI override & persisted JSON):

  * `OBS_WS_URL`, `OBS_WS_PASSWORD`
  * `GPU_GUARD_PCT`, `CPU_GUARD_PCT`, `PAUSE_WHEN_RECORDING`
  * `NATS_ENABLE=true|false`, `NATS_URL`, `ROLE=all|api|worker|overlay|broker`
  * `DB_PATH=/data/db/streamops.db`, `CACHE_DIR=/data/cache`, `THUMBS_DIR=/data/thumbs`
* **Profiles** (per-game presets): default rule sets, destinations, export formats.

---

## 10) Packaging & distribution (single image)

**Dockerfile (multi-stage):**

* Stage 1: build UI (`node:20`) → `/opt/ui`
* Stage 2: Python base (`python:3.11-slim`), install `ffmpeg`, `nats-server`, `pyscenedetect`, `watchdog`, `uvicorn`, `fastapi`, `jinja2`, `sqlite-fts`, etc.
* Copy UI into `/opt/app/static`.
* Add `s6-overlay` and service run scripts (`/etc/services.d/*`).
* Healthcheck hits `/health/live`.

**Run command (Windows example):**

```bash
docker run --name streamops -d --restart unless-stopped ^
  -p 7767:7767 -p 7768:7768 ^
  -v C:\StreamOps\data:/data ^
  -v A:\:/mnt/drive_a ^
  -v D:\:/mnt/drive_d ^
  -v E:\:/mnt/drive_e ^
  -v F:\:/mnt/drive_f ^
  --gpus all ^
  -e ROLE=all -e NATS_ENABLE=true mscrnt/streamops:latest
```

*Note:* If no GPU, omit `--gpus all`.

**Auto-update (optional):** UI button checks GitHub Releases → stops container → pulls new tag → starts with same volumes.

---

## 11) Observability & integrity

* **Logs**: structured JSON per service into `/data/logs`.
* **Metrics**: `/metrics` (Prometheus), basic charts in UI (CPU, GPU, queue depth).
* **Integrity**: journaling for jobs; resume on restart; orphaned temp cleanup.

---

## 12) Security & privacy

* Default **localhost only**; remote access disabled.
* No external calls unless user opts in (updates, telemetry).
* CORS locked to `localhost`.
* Overlay endpoints are local; no public tokens by default.

---

## 13) QA strategy (done once, reusable)

* **Golden-media set** (short MKVs/MP4s) with expected outputs (hashes, durations).
* **Rule simulations** for edge cases (file locks, growing files, massive VODs).
* **Performance gates** (max CPU/GPU while recording, enqueue latency).
* **End-to-end**: start OBS (mock via websocket), trigger events, verify outputs & DB rows.

---

## 14) Deliverables & repo layout

```
/app
  /api               # FastAPI app, routers, models
  /worker            # job runners, ffmpeg wrappers, detectors
  /overlay           # overlay templates (HTML/JS), socket server
  /rules             # built-in YAML rule packs (defaults, examples)
  /ui                # React/Vite source (built into /static)
  /pkg               # Dockerfile, s6 scripts, entrypoints
  /scripts           # dev/QA scripts (simulate, golden tests)
  /docs              # user guide, drive mapping, OBS setup
```

---

## 15) Agent execution checklist (single pass, no later rewrites)

**A. Scaffolding** ✅

* [x] Initialize monorepo; set Python 3.11 + Node 20 toolchains.
* [x] Add Dockerfile (multi-stage), `docker-compose.dev.yml` for hot-reload.
* [x] Integrate `s6-overlay`; define services: api, worker, overlay, broker.

**B. API & DB** ✅

* [x] Define Pydantic models for assets, sessions, jobs, rules, overlays.
* [x] Initialize SQLite with FTS5/JSON1; write migrations (Alembic).
* [x] Implement endpoints: health, config, rules CRUD, jobs CRUD, assets search, overlays CRUD, reports, diagnostics.

**C. Queue & workers** ✅

* [x] Embed `nats-server` process; Python NATS client; create JetStream streams (`jobs.*`).
* [x] Worker subscribes to job subjects, reports progress, idempotent outputs.

**D. Watchers & ingest** ✅

* [x] Build drive watchers (watchdog) with debounce; publish `file_closed` events.
* [x] Implement hash (xxh64 fast, optional SHA256), ffprobe-lite extractor.
* [x] Asset indexer (rows + FTS doc), dedupe logic.

**E. Rules engine** ✅

* [x] Parser (YAML/JSON) → internal plan; simulator & dry-run.
* [x] Action executors: remux, move/copy, proxy, thumbs/sprite/hover, waveform, transcode presets, archive, tag, index, overlay updates, custom hooks.
* [x] Global guardrails (recording/gpu/cpu).

**F. Media toolkit** ✅

* [x] Ship `ffmpeg` and presets; implement scene-detect pipeline (PySceneDetect).
* [x] Waveform precompute; hover-scrub assets and sprite generation.
* [x] Social export (9:16/1:1) framing utility.

**G. OBS bridge (optional)** ✅

* [x] WebSocket client; capture recording/scene/marker events.
* [x] Publish session rows + enqueue post-stop remux rule.
* [x] Simple marker hotkey support.

**H. Overlay system** ✅

* [x] Manifest format + renderer (server-side templates); browser-source endpoints.
* [x] Rotator/scheduler; impression logging; CSV export.

**I. UI** ✅

* [x] Build React app: Dashboard, Watch Folders, Rules (visual + YAML), Assets, Clip Assist, Overlays, Reports, Settings.
* [x] Hover-scrub component (sprite or tiny MP4), fast table/grid with virtualized lists.
* [x] First-run wizard: map drives, set OBS URL, enable default rules.

**J. Scaling / remote workers** ✅

* [x] ROLE switch via env; workers connect to broker URL.
* [x] Document how to spin up remote workers (same image).

**K. Packaging** ✅

* [x] Final image tag `mscrnt/streamops:latest`; push.
* [x] Provide `docker run` command generator (web page or small script).
* [x] Backup/restore config & DB (single zip in `/data/backup`).

**L. QA & docs** ✅

* [x] Golden media tests; soak tests with synthetic long files.
* [x] User docs: drive mapping, OBS setup, overlay browser source, remote worker.

---

## 16) Smart defaults (ship ready-to-use)

* Default rule pack: **Remux→MOV**, **Move to Editing SSD**, **Create proxies if >15min**, **Make hover-scrub**, **Index asset**.
* Guardrails on by default: pause during recording; GPU limit 40%, CPU 70%.
* Overlay demo pack enabled with a sample sponsor rotator (easy to remove).

---

**Result:** a **single Docker image** the streamer downloads and runs. It exposes a local UI, manages post-record workflows safely, indexes assets with instant search and hover-scrub, provides clip-assist, overlay scheduling, reports, and can add remote workers later — **no refactors** needed.

If you want, I can generate the initial repo with the Dockerfile, s6 service scripts, FastAPI skeleton, JetStream setup, schema, and the default rule pack so your agent can dive straight into implementation.
