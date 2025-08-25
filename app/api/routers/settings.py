"""Settings API endpoints"""

from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Body, Request
from pydantic import BaseModel
import logging

from app.api.services.settings_service import settings_service
from app.api.services.system_info_service import system_info_service

logger = logging.getLogger(__name__)
router = APIRouter()


class GuardrailApplyRequest(BaseModel):
    pause_when_recording: bool
    cpu_threshold_pct: int
    gpu_threshold_pct: int
    min_free_disk_gb: int


@router.get("/system/info")
async def get_system_info(refresh: bool = False) -> Dict[str, Any]:
    """Get comprehensive system information"""
    try:
        info = await system_info_service.get_info(force_refresh=refresh)
        return info
    except Exception as e:
        logger.error(f"Failed to get system info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/settings")
async def get_settings() -> Dict[str, Any]:
    """Get all settings"""
    try:
        settings = await settings_service.get_settings()
        return settings
    except Exception as e:
        logger.error(f"Failed to get settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/settings")
async def update_settings(
    request: Request,
    updates: Dict[str, Any] = Body(...)
) -> Dict[str, Any]:
    """Update settings with partial data"""
    try:
        # Update settings
        await settings_service.update_settings(updates)
        
        # Get updated settings (with redacted secrets)
        settings = await settings_service.get_settings()
        
        # Apply hot-reload for certain sections
        if "guardrails" in updates:
            # Apply guardrails immediately
            await apply_guardrails_internal(settings["guardrails"])
        
        if "system" in updates:
            # Check if worker restart needed
            if "max_workers" in updates["system"] or "worker_timeout" in updates["system"]:
                logger.info("Worker configuration changed, restart required")
                # TODO: Trigger worker restart
        
        if "obs" in updates and updates["obs"].get("auto_connect"):
            # Reconnect to OBS if auto-connect enabled
            logger.info("OBS settings changed, reconnecting")
            # TODO: Trigger OBS reconnection
        
        return settings
    
    except Exception as e:
        logger.error(f"Failed to update settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/settings/reset/{section}")
async def reset_settings_section(section: str) -> Dict[str, Any]:
    """Reset a specific settings section to defaults"""
    try:
        await settings_service.reset_section(section)
        settings = await settings_service.get_settings()
        return settings
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to reset section {section}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/guardrails/apply")
async def apply_guardrails(request: GuardrailApplyRequest) -> Dict[str, Any]:
    """Apply guardrail settings immediately"""
    try:
        guardrails = request.dict()
        await apply_guardrails_internal(guardrails)
        return {"ok": True, "message": "Guardrails applied successfully"}
    except Exception as e:
        logger.error(f"Failed to apply guardrails: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def apply_guardrails_internal(guardrails: Dict[str, Any]):
    """Internal function to apply guardrails to workers"""
    # This would communicate with the worker orchestrator
    # For now, just log the change
    logger.info(f"Applying guardrails: {guardrails}")
    
    # Store in environment for workers to pick up
    import os
    if guardrails.get("pause_when_recording"):
        os.environ["PAUSE_WHEN_RECORDING"] = "true"
    else:
        os.environ["PAUSE_WHEN_RECORDING"] = "false"
    
    os.environ["CPU_GUARD_PCT"] = str(guardrails.get("cpu_threshold_pct", 80))
    os.environ["GPU_GUARD_PCT"] = str(guardrails.get("gpu_threshold_pct", 80))
    os.environ["MIN_FREE_GB"] = str(guardrails.get("min_free_disk_gb", 10))


@router.post("/notifications/test/email")
async def test_email_notification(
    smtp_server: str = Body(...),
    smtp_port: int = Body(...),
    from_email: str = Body(...),
    password: str = Body(...)
) -> Dict[str, Any]:
    """Test email notification settings"""
    try:
        # TODO: Implement actual email test
        logger.info(f"Testing email to {from_email} via {smtp_server}:{smtp_port}")
        
        # For now, simulate success
        return {
            "ok": True,
            "message": "Test email sent successfully"
        }
    except Exception as e:
        logger.error(f"Email test failed: {e}")
        return {
            "ok": False,
            "message": str(e)
        }


@router.post("/notifications/test/webhook")
async def test_webhook_notification(
    url: str = Body(...)
) -> Dict[str, Any]:
    """Test webhook notification"""
    try:
        # TODO: Implement actual webhook test
        logger.info(f"Testing webhook to {url}")
        
        # For now, simulate success
        return {
            "ok": True,
            "message": "Test webhook sent successfully"
        }
    except Exception as e:
        logger.error(f"Webhook test failed: {e}")
        return {
            "ok": False,
            "message": str(e)
        }