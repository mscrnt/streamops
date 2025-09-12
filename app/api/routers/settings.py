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
async def apply_guardrails_settings(request: GuardrailApplyRequest) -> Dict[str, Any]:
    """Apply guardrail settings immediately from settings page"""
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


@router.post("/notifications/test/{channel}")
async def test_notification_channel(
    channel: str,
    request: Request
) -> Dict[str, Any]:
    """Test a specific notification channel"""
    try:
        import asyncio
        from app.api.notifications import NotificationService, NotificationChannel
        from app.api.notifications.service import notification_service
        
        # Force reload settings from disk to get latest config
        await settings_service.load_settings()
        
        # Get current settings (unredacted for internal use)
        settings = await settings_service.get_settings_internal()
        notif_config = settings.get("notifications", {})
        
        # Initialize notification service with current config
        config = {
            "enabled": True
        }
        
        if channel == "discord":
            config["discord"] = {
                "enabled": True,
                "webhook_url": notif_config.get("discord_webhook_url"),
                "username": notif_config.get("discord_username", "StreamOps"),
                "avatar_url": notif_config.get("discord_avatar_url")
            }
            channel_enum = NotificationChannel.DISCORD
        elif channel == "email":
            config["email"] = {
                "enabled": True,
                "smtp_host": notif_config.get("email_smtp_host"),
                "smtp_port": notif_config.get("email_smtp_port"),
                "smtp_user": notif_config.get("email_smtp_user"),
                "smtp_pass": notif_config.get("email_smtp_pass"),
                "from_email": notif_config.get("email_from"),
                "to_emails": notif_config.get("email_to", []),
                "use_tls": notif_config.get("email_use_tls", True),
                "use_ssl": notif_config.get("email_use_ssl", False)
            }
            channel_enum = NotificationChannel.EMAIL
        elif channel == "twitter":
            config["twitter"] = {
                "enabled": True,
                "auth_type": notif_config.get("twitter_auth_type", "bearer"),
                "bearer_token": notif_config.get("twitter_bearer_token"),
                "api_key": notif_config.get("twitter_api_key"),
                "api_secret": notif_config.get("twitter_api_secret"),
                "access_token": notif_config.get("twitter_access_token"),
                "access_secret": notif_config.get("twitter_access_secret")
            }
            channel_enum = NotificationChannel.TWITTER
        elif channel == "webhook":
            config["webhook"] = {
                "enabled": True,
                "endpoints": notif_config.get("webhook_endpoints", [])
            }
            channel_enum = NotificationChannel.WEBHOOK
        else:
            return {
                "ok": False,
                "message": f"Unknown channel: {channel}"
            }
        
        # Create a fresh notification service instance for testing
        # This ensures we use the latest config without caching issues
        test_service = NotificationService()
        await test_service.initialize(config)
        
        # Add timeout to prevent hanging
        try:
            result = await asyncio.wait_for(
                test_service.test_channel(channel_enum),
                timeout=10.0  # 10 second timeout
            )
        except asyncio.TimeoutError:
            return {
                "ok": False,
                "message": "Test timed out after 10 seconds"
            }
        
        return {
            "ok": result.success,
            "message": "Test notification sent successfully" if result.success else result.error,
            "details": {
                "channel": channel,
                "timestamp": result.timestamp.isoformat() if result.timestamp else None,
                "provider_message_id": result.provider_message_id
            }
        }
        
    except Exception as e:
        logger.error(f"Notification test failed for {channel}: {e}")
        return {
            "ok": False,
            "message": str(e)
        }


@router.get("/notifications/events")
async def get_notification_events() -> Dict[str, Any]:
    """Get available notification events and their descriptions"""
    from app.api.notifications.providers.base import NotificationEvent
    
    events = {}
    for event in NotificationEvent:
        events[event.value] = {
            "name": event.value,
            "description": event.value.replace('.', ' ').replace('_', ' ').title(),
            "category": event.value.split('.')[0]
        }
    
    return {
        "events": events,
        "categories": list(set(e["category"] for e in events.values()))
    }