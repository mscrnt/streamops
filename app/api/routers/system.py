"""System monitoring and stats endpoints"""
import os
import json
import psutil
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Query, Depends, Body
from pydantic import BaseModel, Field
import logging
import aiofiles
import asyncio

from app.api.schemas.system import SystemStats, SystemHealth, DiskUsage, MemoryUsage, CPUUsage
from app.api.db.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


class MountInfo(BaseModel):
    """Mount point information"""
    id: str = Field(..., description="Unique identifier for the mount")
    label: str = Field(..., description="User-friendly label")
    path: str = Field(..., description="Mount path")
    type: str = Field("local", description="Mount type (local, network, etc)")
    total: int = Field(..., description="Total space in bytes")
    free: int = Field(..., description="Free space in bytes")
    used: int = Field(..., description="Used space in bytes")
    percent: float = Field(..., description="Usage percentage")
    rw: bool = Field(..., description="Whether mount is read-write")
    is_container_mount: bool = Field(..., description="Whether this is a container mount")
    env_hint: Optional[str] = Field(None, description="Environment variable hint")


class OBSProbeRequest(BaseModel):
    """OBS connection probe request"""
    url: str = Field(..., description="OBS WebSocket URL")
    password: str = Field(..., description="OBS WebSocket password")


@router.get("/stats", response_model=SystemStats)
async def get_system_stats() -> SystemStats:
    """Get current system statistics"""
    try:
        # Get CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        
        # Get memory usage
        memory = psutil.virtual_memory()
        
        # Get disk usage
        disk = psutil.disk_usage('/')
        
        # Get network stats
        net_io = psutil.net_io_counters()
        
        # Get process info
        process = psutil.Process()
        
        return SystemStats(
            cpu=CPUUsage(
                percent=cpu_percent,
                count=cpu_count,
                load_avg=os.getloadavg() if hasattr(os, 'getloadavg') else [0, 0, 0]
            ),
            memory=MemoryUsage(
                total=memory.total,
                available=memory.available,
                percent=memory.percent,
                used=memory.used,
                free=memory.free
            ),
            disk=DiskUsage(
                total=disk.total,
                used=disk.used,
                free=disk.free,
                percent=disk.percent
            ),
            network={
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_sent": net_io.packets_sent,
                "packets_recv": net_io.packets_recv
            },
            process={
                "cpu_percent": process.cpu_percent(),
                "memory_percent": process.memory_percent(),
                "num_threads": process.num_threads(),
                "uptime": (datetime.now() - datetime.fromtimestamp(process.create_time())).total_seconds()
            },
            timestamp=datetime.utcnow()
        )
    except Exception as e:
        logger.error(f"Failed to get system stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get system stats: {str(e)}")


@router.get("/health", response_model=SystemHealth)
async def get_system_health(db=Depends(get_db)) -> SystemHealth:
    """Get system health status"""
    try:
        # Check various health indicators
        checks = {}
        
        # Database check
        try:
            cursor = await db.execute("SELECT 1")
            await cursor.fetchone()
            checks["database"] = "healthy"
        except:
            checks["database"] = "unhealthy"
        
        # Disk space check
        disk = psutil.disk_usage('/')
        if disk.percent > 90:
            checks["disk"] = "warning"
        elif disk.percent > 95:
            checks["disk"] = "critical"
        else:
            checks["disk"] = "healthy"
        
        # Memory check
        memory = psutil.virtual_memory()
        if memory.percent > 85:
            checks["memory"] = "warning"
        elif memory.percent > 95:
            checks["memory"] = "critical"
        else:
            checks["memory"] = "healthy"
        
        # CPU check
        cpu_percent = psutil.cpu_percent(interval=1)
        if cpu_percent > 80:
            checks["cpu"] = "warning"
        elif cpu_percent > 95:
            checks["cpu"] = "critical"
        else:
            checks["cpu"] = "healthy"
        
        # Overall status
        if any(v == "critical" for v in checks.values()):
            status = "critical"
        elif any(v == "unhealthy" for v in checks.values()):
            status = "unhealthy"
        elif any(v == "warning" for v in checks.values()):
            status = "warning"
        else:
            status = "healthy"
        
        return SystemHealth(
            status=status,
            checks=checks,
            timestamp=datetime.utcnow()
        )
    except Exception as e:
        logger.error(f"Failed to get system health: {e}")
        return SystemHealth(
            status="unhealthy",
            checks={"error": str(e)},
            timestamp=datetime.utcnow()
        )


@router.get("/metrics")
async def get_system_metrics(
    period: str = Query("1h", description="Time period for metrics (1h, 6h, 24h, 7d)"),
    db=Depends(get_db)
) -> Dict[str, Any]:
    """Get system metrics over time"""
    try:
        # This would typically query a time-series database
        # For now, return current snapshot with metadata
        
        # Parse period
        period_map = {
            "1h": timedelta(hours=1),
            "6h": timedelta(hours=6),
            "24h": timedelta(hours=24),
            "7d": timedelta(days=7)
        }
        delta = period_map.get(period, timedelta(hours=1))
        start_time = datetime.utcnow() - delta
        
        # Get job metrics for the period
        cursor = await db.execute(
            """SELECT 
                COUNT(*) as total_jobs,
                SUM(CASE WHEN state = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN state = 'failed' THEN 1 ELSE 0 END) as failed,
                AVG(CASE WHEN state = 'completed' THEN progress ELSE NULL END) as avg_progress
               FROM so_jobs
               WHERE created_at >= ?""",
            (start_time.isoformat(),)
        )
        job_metrics = await cursor.fetchone()
        
        # Get asset metrics
        cursor = await db.execute(
            """SELECT 
                COUNT(*) as new_assets,
                SUM(size) as total_size
               FROM so_assets
               WHERE created_at >= ?""",
            (start_time.isoformat(),)
        )
        asset_metrics = await cursor.fetchone()
        
        return {
            "period": period,
            "start_time": start_time.isoformat(),
            "end_time": datetime.utcnow().isoformat(),
            "jobs": {
                "total": job_metrics[0] or 0,
                "completed": job_metrics[1] or 0,
                "failed": job_metrics[2] or 0,
                "success_rate": ((job_metrics[1] or 0) / job_metrics[0] * 100) if job_metrics[0] else 0
            },
            "assets": {
                "new_count": asset_metrics[0] or 0,
                "total_size_bytes": asset_metrics[1] or 0
            },
            "system": {
                "cpu_current": psutil.cpu_percent(interval=1),
                "memory_current": psutil.virtual_memory().percent,
                "disk_current": psutil.disk_usage('/').percent
            }
        }
    except Exception as e:
        logger.error(f"Failed to get system metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get system metrics: {str(e)}")


@router.get("/processes")
async def get_running_processes() -> Dict[str, Any]:
    """Get information about running StreamOps processes"""
    try:
        processes = []
        
        # Get all Python processes that might be StreamOps related
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'create_time', 'cmdline']):
            try:
                info = proc.info
                cmdline = ' '.join(info.get('cmdline', []))
                
                # Check if it's a StreamOps process
                if 'streamops' in cmdline.lower() or 'uvicorn' in cmdline.lower() or 'worker' in cmdline.lower():
                    processes.append({
                        "pid": info['pid'],
                        "name": info['name'],
                        "cpu_percent": proc.cpu_percent(interval=0.1),
                        "memory_percent": info['memory_percent'],
                        "uptime": (datetime.now() - datetime.fromtimestamp(info['create_time'])).total_seconds(),
                        "type": "api" if 'uvicorn' in cmdline else "worker" if 'worker' in cmdline else "other"
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        return {
            "processes": processes,
            "total": len(processes),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get process list: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get process list: {str(e)}")


@router.get("/resource-usage")
async def get_resource_usage(
    resource: str = Query("all", description="Resource type (cpu, memory, disk, gpu, all)"),
) -> Dict[str, Any]:
    """Get detailed resource usage information"""
    try:
        result = {}
        
        if resource in ["cpu", "all"]:
            cpu_freq = psutil.cpu_freq()
            result["cpu"] = {
                "percent": psutil.cpu_percent(interval=1),
                "per_core": psutil.cpu_percent(interval=1, percpu=True),
                "count_physical": psutil.cpu_count(logical=False),
                "count_logical": psutil.cpu_count(logical=True),
                "frequency": {
                    "current": cpu_freq.current if cpu_freq else 0,
                    "min": cpu_freq.min if cpu_freq else 0,
                    "max": cpu_freq.max if cpu_freq else 0
                },
                "load_average": os.getloadavg() if hasattr(os, 'getloadavg') else [0, 0, 0]
            }
        
        if resource in ["memory", "all"]:
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()
            result["memory"] = {
                "virtual": {
                    "total": mem.total,
                    "available": mem.available,
                    "used": mem.used,
                    "free": mem.free,
                    "percent": mem.percent
                },
                "swap": {
                    "total": swap.total,
                    "used": swap.used,
                    "free": swap.free,
                    "percent": swap.percent
                }
            }
        
        if resource in ["disk", "all"]:
            result["disk"] = {}
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    result["disk"][partition.mountpoint] = {
                        "device": partition.device,
                        "fstype": partition.fstype,
                        "total": usage.total,
                        "used": usage.used,
                        "free": usage.free,
                        "percent": usage.percent
                    }
                except:
                    continue
        
        if resource in ["gpu", "all"]:
            # Check for GPU if nvidia-ml-py is available
            try:
                import pynvml
                pynvml.nvmlInit()
                device_count = pynvml.nvmlDeviceGetCount()
                result["gpu"] = []
                
                for i in range(device_count):
                    handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                    result["gpu"].append({
                        "index": i,
                        "name": pynvml.nvmlDeviceGetName(handle).decode('utf-8'),
                        "memory": {
                            "total": pynvml.nvmlDeviceGetMemoryInfo(handle).total,
                            "used": pynvml.nvmlDeviceGetMemoryInfo(handle).used,
                            "free": pynvml.nvmlDeviceGetMemoryInfo(handle).free
                        },
                        "utilization": pynvml.nvmlDeviceGetUtilizationRates(handle).gpu,
                        "temperature": pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                    })
            except:
                result["gpu"] = None
        
        result["timestamp"] = datetime.utcnow().isoformat()
        return result
        
    except Exception as e:
        logger.error(f"Failed to get resource usage: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get resource usage: {str(e)}")


@router.get("/mounts", response_model=List[MountInfo])
async def get_system_mounts() -> List[MountInfo]:
    """Get available mount points with storage information and write permissions"""
    try:
        mounts = []
        seen_devices = set()
        
        # Check for environment hints
        env_mounts = os.environ.get("STREAMOPS_MOUNTS_JSON", "")
        mount_hints = {}
        if env_mounts:
            try:
                hints = json.loads(env_mounts)
                mount_hints = {h.get("path"): h for h in hints if isinstance(h, dict)}
            except json.JSONDecodeError:
                logger.warning(f"Invalid STREAMOPS_MOUNTS_JSON: {env_mounts}")
        
        # Scan /mnt/* directories
        mnt_paths = []
        if os.path.exists("/mnt"):
            for entry in os.scandir("/mnt"):
                if entry.is_dir() and not entry.name.startswith('.'):
                    mnt_paths.append(entry.path)
        
        # Also check common paths
        common_paths = ["/", "/data", "/opt/streamops"]
        all_paths = mnt_paths + common_paths
        
        for path in all_paths:
            try:
                if not os.path.exists(path):
                    continue
                    
                # Get disk usage
                usage = psutil.disk_usage(path)
                
                # Skip if we've seen this device (same filesystem)
                device_key = f"{usage.total}_{usage.free}"
                if device_key in seen_devices and path not in mount_hints:
                    continue
                seen_devices.add(device_key)
                
                # Test write permissions
                is_writable = await test_write_permission(path)
                
                # Determine mount properties
                path_obj = Path(path)
                mount_id = path_obj.name or "root"
                if path.startswith("/mnt/drive_"):
                    mount_id = path.replace("/mnt/", "")
                elif path.startswith("/mnt/"):
                    mount_id = f"mount_{path_obj.name}"
                
                # Get hint data if available
                hint = mount_hints.get(path, {})
                
                # Determine label
                label = hint.get("label")
                if not label:
                    if path.startswith("/mnt/drive_"):
                        # Extract drive letter if present
                        drive_part = path.replace("/mnt/drive_", "")
                        if drive_part:
                            label = f"{drive_part.upper()}:"
                    elif path == "/":
                        label = "Root"
                    elif path == "/data":
                        label = "Data Volume"
                    else:
                        label = path_obj.name.title()
                
                mount_info = MountInfo(
                    id=mount_id,
                    label=label,
                    path=path,
                    type=hint.get("type", "local"),
                    total=usage.total,
                    free=usage.free,
                    used=usage.used,
                    percent=usage.percent,
                    rw=is_writable,
                    is_container_mount=path.startswith("/mnt/"),
                    env_hint=hint.get("id") if hint else None
                )
                mounts.append(mount_info)
                
            except Exception as e:
                logger.warning(f"Failed to get mount info for {path}: {e}")
                continue
        
        # Sort by path for consistency
        mounts.sort(key=lambda m: m.path)
        return mounts
        
    except Exception as e:
        logger.error(f"Failed to get system mounts: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get system mounts: {str(e)}")


async def test_write_permission(path: str) -> bool:
    """Test if a path is writable"""
    try:
        test_file = os.path.join(path, f".streamops_write_test_{os.getpid()}")
        
        # Try to create and write to a test file
        async with aiofiles.open(test_file, 'w') as f:
            await f.write("test")
        
        # Clean up
        try:
            os.remove(test_file)
        except:
            pass
            
        return True
    except:
        return False


@router.post("/probe-obs")
async def probe_obs_connection(request: OBSProbeRequest) -> Dict[str, Any]:
    """Test OBS WebSocket connection"""
    try:
        # Import OBS service to test connection
        from app.api.services.obs_service import OBSService
        
        # Create temporary OBS service instance
        obs = OBSService()
        
        # Try to connect with provided credentials
        connected = await obs.test_connection(request.url, request.password)
        
        if connected:
            # Try to get version info
            version = None
            try:
                # This would require actual OBS websocket implementation
                version = "28.0.0"  # Placeholder
            except:
                pass
                
            return {
                "ok": True,
                "version": version,
                "reason": "Successfully connected to OBS"
            }
        else:
            return {
                "ok": False,
                "version": None,
                "reason": "Failed to connect - check URL and password"
            }
            
    except Exception as e:
        logger.error(f"Failed to probe OBS: {e}")
        return {
            "ok": False,
            "version": None,
            "reason": str(e)
        }