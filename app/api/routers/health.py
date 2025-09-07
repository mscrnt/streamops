from fastapi import APIRouter, Depends
from typing import Dict, Any
import psutil
import os
from datetime import datetime

from app.api.db.database import get_db

router = APIRouter()

@router.get("/")
async def health_check() -> Dict[str, Any]:
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "StreamOps API",
        "version": "1.0.0"
    }

@router.get("/live")
async def liveness_check() -> Dict[str, str]:
    """Kubernetes liveness probe endpoint"""
    return {"status": "alive"}

@router.get("/ready")
async def readiness_check() -> Dict[str, Any]:
    """Kubernetes readiness probe endpoint"""
    checks = {
        "database": False,
        "nats": False,
        "filesystem": False,
    }
    
    # Check database
    try:
        db = await get_db()
        async with db.execute("SELECT 1") as cursor:
            await cursor.fetchone()
        checks["database"] = True
    except Exception:
        pass
    
    # Check filesystem
    try:
        data_path = os.getenv("DB_PATH", "/data/db/streamops.db")
        if os.path.exists(os.path.dirname(data_path)):
            checks["filesystem"] = True
    except Exception:
        pass
    
    # Check NATS
    try:
        from app.api.main import app
        if hasattr(app.state, 'nats') and app.state.nats.is_connected:
            checks["nats"] = True
        else:
            checks["nats"] = False
    except Exception:
        checks["nats"] = False
    
    all_ready = all(v for v in checks.values() if v is not None)
    
    return {
        "ready": all_ready,
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/system/info")
async def get_system_info() -> Dict[str, Any]:
    """Get system information"""
    import platform
    
    return {
        "platform": platform.system(),
        "python_version": platform.python_version(),
        "cpu_count": psutil.cpu_count(),
        "memory_total": psutil.virtual_memory().total,
        "memory_available": psutil.virtual_memory().available,
        "memory_percent": psutil.virtual_memory().percent,
        "disk_usage": {
            "total": psutil.disk_usage('/').total,
            "used": psutil.disk_usage('/').used,
            "free": psutil.disk_usage('/').free,
            "percent": psutil.disk_usage('/').percent
        },
        "uptime": datetime.utcnow().isoformat(),
        "streamops_version": "1.0.0"
    }

@router.get("/stats")
async def system_stats() -> Dict[str, Any]:
    """Get system statistics"""
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/data") if os.path.exists("/data") else psutil.disk_usage("/")
    
    # Get GPU stats if available
    gpu_stats = None
    try:
        import pynvml
        pynvml.nvmlInit()
        device_count = pynvml.nvmlDeviceGetCount()
        if device_count > 0:
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            gpu_util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            gpu_memory = pynvml.nvmlDeviceGetMemoryInfo(handle)
            gpu_stats = {
                "utilization": gpu_util.gpu,
                "memory_used": gpu_memory.used,
                "memory_total": gpu_memory.total,
                "memory_percent": (gpu_memory.used / gpu_memory.total) * 100
            }
    except Exception:
        pass
    
    return {
        "cpu": {
            "percent": cpu_percent,
            "count": psutil.cpu_count()
        },
        "memory": {
            "total": memory.total,
            "available": memory.available,
            "percent": memory.percent,
            "used": memory.used
        },
        "disk": {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": disk.percent
        },
        "gpu": gpu_stats,
        "timestamp": datetime.utcnow().isoformat()
    }