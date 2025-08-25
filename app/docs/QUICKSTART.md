# StreamOps Quick Start Guide

## 🎮 Streamer Use Case: Multi-Drive Recording Workflow

This guide walks through setting up StreamOps for a real streamer's workflow with multiple drives and automatic post-recording processing.

### Example Setup (Your Setup May Vary)
- **A: Drive** (2TB NVMe) - Recording & Active Projects
- **D: Drive** (6TB HDD) - OBS & Stream Assets  
- **E: Drive** (4TB HDD) - Backlog/Archive
- **F: Drive** (4TB SSD) - Editing & Encoding Targets

**Current Pain Points:**
- OBS records to MKV but can't remux to MOV (only MP4)
- Don't want remuxing during recording (quick restart between sessions)
- Need automatic organization and proxy generation for editing

---

## 🚀 Quick Start in 5 Minutes

### 1. Install Docker Desktop
- **Windows**: Download from [docker.com](https://www.docker.com/products/docker-desktop/)
- **Enable WSL2 backend** during installation
- Restart your computer after installation

### 2. Download and Run StreamOps

Open PowerShell as Administrator and run:

```powershell
# Pull the StreamOps image
docker pull mscrnt/streamops:latest

# Create data directory
mkdir C:\StreamOps\data

# Run StreamOps with your drives mapped
docker run --name streamops -d --restart unless-stopped `
  -p 7767:7767 `
  -v C:\StreamOps\data:/data `
  -v A:\:/mnt/drive_a `
  -v D:\:/mnt/drive_d `
  -v E:\:/mnt/drive_e `
  -v F:\:/mnt/drive_f `
  -e OBS_WS_URL=ws://host.docker.internal:4455 `
  -e OBS_WS_PASSWORD=your_obs_password `
  mscrnt/streamops:latest
```

### 3. Access StreamOps UI
Open your browser and go to: **http://localhost:7767**

---

## ⚙️ Configuration for Your Workflow

### Step 1: Configure Drive Watching

1. Go to **Drives** in the UI
2. Add your recording drive:
   - **Path**: `/mnt/drive_a/Recordings`
   - **Name**: "NVMe Recording Drive"
   - **Poll Interval**: 5 seconds
   - **File Quiet Time**: 45 seconds (ensures recording is complete)
3. Click **Start Watching**

### Step 2: Set Up Automatic Rules

StreamOps comes with pre-configured rules perfect for your workflow. Go to **Rules** and enable:

#### Rule 1: "Remux MKV to MOV and Organize"
```yaml
name: "Remux OBS Recordings to MOV"
when:
  event: file.closed
  path_glob: "/mnt/drive_a/Recordings/**/*.mkv"
  min_quiet_seconds: 45  # Wait until OBS is done writing
do:
  - ffmpeg_remux:
      container: mov
      faststart: true
  - move:
      dest: "/mnt/drive_f/Editing/{Game}/{YYYY}/{MM}/{DD}/"
  - index_asset: {}
  - make_proxies_if:
      min_duration_sec: 900  # Only for videos > 15 minutes
      codec: dnxhr_lb
```

This rule:
- ✅ Waits for OBS to finish writing the file
- ✅ Remuxes MKV to MOV (what OBS can't do)
- ✅ Moves to your editing SSD organized by game/date
- ✅ Creates DNxHR proxies for smooth editing
- ✅ Indexes for quick searching

#### Rule 2: "Archive Old Projects"
```yaml
name: "Move Inactive Projects to Backlog"
when:
  event: asset.aged
  conditions:
    age_days: 30
    status: "completed"
do:
  - move:
      dest: "/mnt/drive_e/Backlog/{Game}/{YYYY}-{MM}/"
  - tag:
      tags: ["archived", "backlog"]
```

### Step 3: Connect OBS (Optional but Recommended)

1. In OBS, install the **obs-websocket** plugin (v5.0+)
2. Go to **Tools → WebSocket Server Settings**
3. Enable WebSocket server
4. Set a password
5. Note the port (usually 4455)

StreamOps will now:
- Know when you're recording (won't process files during recording)
- Track recording sessions with markers
- Automatically trigger processing when recording stops

### Step 4: Configure Performance Guardrails

In **Settings → Performance**:
- **Pause When Recording**: ✅ Enabled
- **GPU Usage Limit**: 40% (prevents lag during streaming)
- **CPU Usage Limit**: 70%
- **Max Concurrent Jobs**: 2

---

## 🎯 Your Optimized Workflow

### What Happens Automatically:

1. **You Record in OBS** → MKV files saved to A:\Recordings
2. **You Stop Recording** → StreamOps detects recording ended
3. **After 45 seconds** → File is considered stable
4. **Automatic Processing**:
   - Remuxes MKV → MOV (lossless, with faststart)
   - Moves to F:\Editing\{Game}\2024\08\18\
   - Creates DNxHR proxy for Premiere/Resolve
   - Generates thumbnails and preview
   - Indexes with full-text search

### Manual Controls:

- **Quick Clip Export**: Select in/out points, export lossless clips
- **Bulk Operations**: Select multiple files, apply rules
- **Search**: Find any recording instantly by game, date, or content
- **Reports**: Weekly summaries of recording time, storage usage

---

## 📊 Dashboard Overview

When you open StreamOps, you'll see:

- **Recording Status**: Live indicator if OBS is recording
- **Active Jobs**: Real-time progress of remuxing/processing
- **Storage Health**: Usage across all drives
- **Recent Assets**: Latest processed recordings with previews
- **Queue Depth**: Number of files waiting to process

---

## 🔧 Advanced Tweaks

### Customize Folder Structure
Edit the rule's destination pattern:
- `{Game}` - Detected game name or OBS scene
- `{YYYY}` - Year (2024)
- `{MM}` - Month (08)
- `{DD}` - Day (18)
- `{Scene}` - OBS scene name
- `{Profile}` - OBS profile name

Example: `/mnt/drive_f/{Profile}/{Game}/{YYYY}-{MM}-{DD}/`

### Different Proxy Codecs
In the proxy rule, change codec to:
- `dnxhr_lb` - DNxHR Low Bandwidth (default, good quality/size)
- `dnxhr_sq` - Standard Quality (better quality)
- `dnxhr_hq` - High Quality (best for color grading)
- `prores_proxy` - Apple ProRes Proxy
- `cineform` - GoPro CineForm

### Social Media Clips
Enable the "Generate Social Clips" rule to auto-create:
- Vertical 9:16 for TikTok/Shorts
- Square 1:1 for Instagram
- Optimized file sizes with smart cropping

---

## 🚨 Troubleshooting

### Container Won't Start
```powershell
# Check logs
docker logs streamops

# Restart container
docker restart streamops
```

### Files Not Being Detected
1. Check drive mapping is correct
2. Verify path in Drives section shows files
3. Check file extensions match rules (.mkv)
4. Ensure "quiet time" has passed (45 seconds)

### Remux Failing
```powershell
# Check FFmpeg is working
docker exec streamops ffmpeg -version

# Check file permissions
docker exec streamops ls -la /mnt/drive_a/Recordings
```

### OBS Connection Issues
1. Ensure obs-websocket is v5.0 or newer
2. Check firewall isn't blocking port 4455
3. Try `localhost` instead of `host.docker.internal`
4. Verify password is correct

---

## 💡 Pro Tips

1. **Start Small**: Test with one recording first before enabling all rules
2. **Monitor First Run**: Watch the Jobs page to ensure processing works
3. **Adjust Quiet Time**: If files process too early/late, adjust the quiet seconds
4. **Use Tags**: Tag your best clips for easy finding later
5. **Set Up Schedules**: Schedule heavy processing for off-stream hours
6. **Export Settings**: Backup your rules and config regularly

---

## 📚 Next Steps

- [Full Documentation](../README.md)
- [Creating Custom Rules](./RULES.md)
- [API Documentation](./API.md)
- [Overlay System Guide](./OVERLAYS.md)

## 🆘 Getting Help

- **GitHub Issues**: [github.com/mscrnt/streamops/issues](https://github.com/mscrnt/streamops/issues)
- **Discord**: [Join our Discord](https://discord.gg/streamops)
- **Email**: support@streamops.io

---

*StreamOps - Automate your streaming workflow so you can focus on creating content!* 🎮🎬✨