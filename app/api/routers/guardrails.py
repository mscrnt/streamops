from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime
import psutil
import logging
import json
import os

from app.api.db.database import get_db
from app.api.services.obs_service import OBSService

logger = logging.getLogger(__name__)

router = APIRouter()

class GuardrailStatus(BaseModel):
    active: bool
    reasons: List[str] = Field(default_factory=list)
    cpu_percent: float
    gpu_percent: float
    memory_available_gb: float
    disk_free_gb: float
    is_recording: bool
    is_streaming: bool
    thresholds: Dict[str, Any]

class GuardrailConfig(BaseModel):
    cpu_threshold_pct: float = Field(default=70, ge=0, le=100)
    gpu_threshold_pct: float = Field(default=40, ge=0, le=100)
    min_disk_gb: float = Field(default=10, ge=0)
    min_memory_gb: float = Field(default=2, ge=0)
    pause_if_recording: bool = True
    pause_if_streaming: bool = True

# Global guardrails state
_guardrails_config = GuardrailConfig()
_obs_service: Optional[OBSService] = None

def set_obs_service(obs_service: OBSService):
    """Set the OBS service for recording checks"""
    global _obs_service
    _obs_service = obs_service

@router.get("/", response_model=GuardrailStatus)
async def get_guardrails_status(db=Depends(get_db)) -> GuardrailStatus:
    """Get current guardrails status and system metrics"""
    try:
        reasons = []
        
        # Get current system metrics
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        memory_available_gb = memory.available / (1024**3)
        disk_free_gb = disk.free / (1024**3)
        
        # Check CPU
        if cpu_percent > _guardrails_config.cpu_threshold_pct:
            reasons.append(f"CPU usage {cpu_percent:.1f}% > {_guardrails_config.cpu_threshold_pct}%")
        
        # Check memory
        if memory_available_gb < _guardrails_config.min_memory_gb:
            reasons.append(f"Memory {memory_available_gb:.1f}GB < {_guardrails_config.min_memory_gb}GB")
        
        # Check disk
        if disk_free_gb < _guardrails_config.min_disk_gb:
            reasons.append(f"Disk free {disk_free_gb:.1f}GB < {_guardrails_config.min_disk_gb}GB")
        
        # Check recording and streaming status
        is_recording = False
        is_streaming = False
        if _obs_service:
            try:
                if _guardrails_config.pause_if_recording:
                    is_recording = await _obs_service.is_recording()
                    if is_recording:
                        reasons.append("OBS is recording")
                
                if _guardrails_config.pause_if_streaming:
                    is_streaming = await _obs_service.is_streaming()
                    if is_streaming:
                        reasons.append("OBS is streaming")
            except Exception as e:
                logger.warning(f"Failed to check OBS status: {e}")
        
        # Check GPU (placeholder - would need nvidia-ml-py or similar)
        gpu_percent = 0.0
        try:
            # This would require proper GPU monitoring library
            # For now, return 0 as placeholder
            pass
        except Exception:
            pass
        
        return GuardrailStatus(
            active=len(reasons) > 0,
            reasons=reasons,
            cpu_percent=cpu_percent,
            gpu_percent=gpu_percent,
            memory_available_gb=memory_available_gb,
            disk_free_gb=disk_free_gb,
            is_recording=is_recording,
            is_streaming=is_streaming,
            thresholds={
                "cpu_threshold_pct": _guardrails_config.cpu_threshold_pct,
                "gpu_threshold_pct": _guardrails_config.gpu_threshold_pct,
                "min_memory_gb": _guardrails_config.min_memory_gb,
                "min_disk_gb": _guardrails_config.min_disk_gb,
                "pause_if_recording": _guardrails_config.pause_if_recording,
                "pause_if_streaming": _guardrails_config.pause_if_streaming
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to get guardrails status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/apply")
async def apply_guardrails(
    config: GuardrailConfig,
    db=Depends(get_db)
) -> Dict[str, str]:
    """Update guardrails configuration"""
    global _guardrails_config
    
    try:
        _guardrails_config = config
        
        # Save to database
        await db.execute("""
            INSERT OR REPLACE INTO so_configs (key, value, updated_at)
            VALUES ('guardrails.config', ?, datetime('now'))
        """, (json.dumps(config.dict()),))
        await db.commit()
        
        logger.info(f"Updated guardrails config: {config.dict()}")
        
        return {"status": "ok", "message": "Guardrails configuration updated"}
        
    except Exception as e:
        logger.error(f"Failed to apply guardrails: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/check")
async def check_guardrails_preflight(db=Depends(get_db)) -> Dict[str, Any]:
    """
    Check if guardrails would currently block execution.
    Used by workers before starting heavy processing.
    """
    try:
        status = await get_guardrails_status(db)
        
        if status.active:
            return {
                "blocked": True,
                "reasons": status.reasons,
                "retry_after_sec": 60  # Suggest retry after 60 seconds
            }
        else:
            return {
                "blocked": False,
                "reasons": [],
                "retry_after_sec": 0
            }
            
    except Exception as e:
        logger.error(f"Guardrails preflight check failed: {e}")
        # On error, allow execution (fail open)
        return {
            "blocked": False,
            "reasons": [],
            "retry_after_sec": 0,
            "error": str(e)
        }

# Load config from database on startup
async def load_guardrails_config(db):
    """Load guardrails config from database"""
    global _guardrails_config
    
    # Use defaults if no db connection
    if not db:
        logger.debug("No database connection, using default guardrails config")
        return
    
    try:
        cursor = await db.execute(
            "SELECT value FROM so_configs WHERE key = 'guardrails.config'"
        )
        row = await cursor.fetchone()
        
        if row and row[0]:
            config_dict = json.loads(row[0])
            _guardrails_config = GuardrailConfig(**config_dict)
            logger.info(f"Loaded guardrails config: {config_dict}")
        else:
            logger.debug("No guardrails config in database, using defaults")
    except Exception as e:
        # This is expected on first run when config doesn't exist yet
        logger.debug(f"Guardrails config not found in database, using defaults: {e}")

# This would be called during app startup
async def init_guardrails(db, obs_service=None):
    """Initialize guardrails system"""
    await load_guardrails_config(db)
    if obs_service:
        set_obs_service(obs_service)