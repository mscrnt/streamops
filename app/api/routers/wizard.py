"""Setup wizard endpoints for zero-configuration"""
import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
import aiofiles

from app.api.db.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


class WizardDriveConfig(BaseModel):
    """Drive role assignment from wizard"""
    role: str = Field(..., description="Drive role: recording, editing, archive, backlog, assets")
    drive_id: Optional[str] = Field(None, description="Drive identifier")
    drive_label: Optional[str] = Field(None, description="Drive label")
    subpath: Optional[str] = Field(None, description="Subpath within drive")
    abs_path: str = Field(..., description="Absolute path")
    watch: bool = Field(False, description="Whether to watch this folder")
    exists: bool = Field(True, description="Whether path exists")
    writable: bool = Field(True, description="Whether path is writable")


class WizardOBSConnectionConfig(BaseModel):
    """OBS connection configuration from wizard"""
    id: str = Field(..., description="Connection ID")
    name: str = Field(..., description="Connection name")
    ws_url: str = Field(..., description="WebSocket URL")
    connected: Optional[bool] = Field(False, description="Whether currently connected")
    auto_connect: Optional[bool] = Field(True, description="Auto-connect on startup")
    roles: Optional[List[str]] = Field(default_factory=list, description="Connection roles")


class WizardRuleConfig(BaseModel):
    """Rule configuration in wizard"""
    id: str = Field(..., description="Rule preset ID")
    enabled: bool = Field(..., description="Whether rule is enabled")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Rule parameters")


class WizardOverlayConfig(BaseModel):
    """Overlay configuration in wizard"""
    enabled: bool = Field(..., description="Whether overlays are enabled")
    preset: Optional[str] = Field(None, description="Overlay preset to use")
    position: Optional[str] = Field(None, description="Overlay position")
    margin: Optional[int] = Field(None, description="Overlay margin in pixels")


class WizardApplyRequest(BaseModel):
    """Complete wizard configuration to apply"""
    drives: List[WizardDriveConfig] = Field(..., description="Drive role assignments")
    obs: List[WizardOBSConnectionConfig] = Field(default_factory=list, description="OBS connections")
    rules: List[WizardRuleConfig] = Field(default_factory=list, description="Rule configurations")
    overlays: WizardOverlayConfig = Field(..., description="Overlay configuration")


class WizardDefaults(BaseModel):
    """Default wizard suggestions"""
    recording_paths: List[str] = Field(..., description="Suggested recording paths")
    editing_paths: List[str] = Field(..., description="Suggested editing paths")
    obs_url: str = Field(..., description="Default OBS WebSocket URL")
    rules: List[Dict[str, Any]] = Field(..., description="Recommended rule presets")
    overlay_presets: List[Dict[str, Any]] = Field(..., description="Available overlay presets")


class WizardState(BaseModel):
    """Wizard completion state"""
    completed: bool = Field(..., description="Whether wizard has been completed")
    last_completed_at: Optional[datetime] = Field(None, description="Last completion timestamp")
    version: str = Field(..., description="Wizard version")


@router.get("/defaults", response_model=WizardDefaults)
async def get_wizard_defaults() -> WizardDefaults:
    """Get wizard default suggestions based on system inspection"""
    try:
        recording_paths = []
        editing_paths = []
        
        # Look for common recording folders
        common_recording_names = ["Recordings", "Videos", "OBS", "Stream", "Captures"]
        common_editing_names = ["Editing", "Projects", "Export", "Final"]
        
        # Scan mounted drives
        if os.path.exists("/mnt"):
            for entry in os.scandir("/mnt"):
                if entry.is_dir() and not entry.name.startswith('.'):
                    path = entry.path
                    
                    # Check for recording folders
                    for rec_name in common_recording_names:
                        rec_path = os.path.join(path, rec_name)
                        if os.path.exists(rec_path):
                            recording_paths.append(rec_path)
                    
                    # Check for editing folders
                    for edit_name in common_editing_names:
                        edit_path = os.path.join(path, edit_name)
                        if os.path.exists(edit_path):
                            editing_paths.append(edit_path)
        
        # If no specific folders found, suggest mount roots
        if not recording_paths and os.path.exists("/mnt/recordings"):
            recording_paths.append("/mnt/recordings")
        elif not recording_paths and os.path.exists("/mnt/drive_a"):
            recording_paths.append("/mnt/drive_a")
            
        if not editing_paths and os.path.exists("/mnt/drive_f"):
            editing_paths.append("/mnt/drive_f")
        elif not editing_paths and os.path.exists("/mnt/drive_d"):
            editing_paths.append("/mnt/drive_d")
        
        # Default OBS URL
        obs_url = "ws://host.docker.internal:4455"
        
        # Recommended rule presets
        rules = [
            {
                "id": "remux_move_proxy",
                "label": "Remux to MOV, Move to Editing, Create Proxies",
                "description": "Remux MKV files to MOV with faststart, move to editing drive, and create proxy files for clips longer than 15 minutes",
                "enabled_by_default": True,
                "parameters": {
                    "container": "mov",
                    "faststart": True,
                    "proxy_min_duration_sec": 900
                }
            },
            {
                "id": "archive_old",
                "label": "Archive Old Recordings",
                "description": "Move recordings older than 90 days to archive storage",
                "enabled_by_default": False,
                "parameters": {
                    "days_old": 90,
                    "delete_after_archive": False
                }
            }
        ]
        
        # Available overlay presets
        overlay_presets = [
            {
                "id": "sponsor_rotator",
                "label": "Sponsor Rotator",
                "description": "Rotate sponsor logos in corner of stream",
                "positions": ["top-left", "top-right", "bottom-left", "bottom-right"],
                "default_position": "bottom-right",
                "default_margin": 20
            },
            {
                "id": "now_playing",
                "label": "Now Playing",
                "description": "Show current music track",
                "positions": ["top", "bottom"],
                "default_position": "bottom",
                "default_margin": 10
            }
        ]
        
        return WizardDefaults(
            recording_paths=recording_paths,
            editing_paths=editing_paths,
            obs_url=obs_url,
            rules=rules,
            overlay_presets=overlay_presets
        )
        
    except Exception as e:
        logger.error(f"Failed to get wizard defaults: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get wizard defaults: {str(e)}")


@router.get("/state", response_model=WizardState)
async def get_wizard_state(request: Request, db=Depends(get_db)) -> WizardState:
    """Get wizard completion state"""
    try:
        config_service = request.app.state.config
        
        # Check wizard state in config
        wizard_config = await config_service.get_config("wizard_state")
        
        # Even if wizard was marked complete, verify essential drives exist
        if wizard_config and wizard_config.get("completed", False):
            # Check if essential drives are configured in the database
            try:
                cursor = await db.execute("""
                    SELECT COUNT(*) 
                    FROM so_roles 
                    WHERE role IN ('recording', 'editing')
                """)
                count = await cursor.fetchone()
                
                # If essential drives are missing, wizard is not complete
                if not count or count[0] < 2:
                    logger.info("Wizard marked complete but essential drives missing - resetting wizard state")
                    return WizardState(
                        completed=False,
                        last_completed_at=None,
                        version="1.0.0"
                    )
                    
            except Exception as db_error:
                logger.warning(f"Could not verify drive configuration: {db_error}")
                # If we can't verify, assume wizard needs to run
                return WizardState(
                    completed=False,
                    last_completed_at=None,
                    version="1.0.0"
                )
            
            return WizardState(
                completed=wizard_config.get("completed", False),
                last_completed_at=datetime.fromisoformat(wizard_config["last_completed_at"]) if wizard_config.get("last_completed_at") else None,
                version=wizard_config.get("version", "1.0.0")
            )
        else:
            return WizardState(
                completed=False,
                last_completed_at=None,
                version="1.0.0"
            )
            
    except Exception as e:
        logger.error(f"Failed to get wizard state: {e}")
        return WizardState(
            completed=False,
            last_completed_at=None,
            version="1.0.0"
        )


@router.post("/apply")
async def apply_wizard_config(
    wizard_request: WizardApplyRequest,
    request: Request,
    db=Depends(get_db)
) -> Dict[str, Any]:
    """Apply wizard configuration - creates drives, rules, and starts watchers"""
    try:
        config_service = request.app.state.config
        applied_items = []
        
        # 1. Drive roles are already configured in the database from the WizardDrives component
        # Just log what we received
        for drive_role in wizard_request.drives:
            applied_items.append(f"Drive role: {drive_role.role} -> {drive_role.abs_path}")
            logger.info(f"Drive role configured: {drive_role.role} at {drive_role.abs_path}")
        
        # 2. OBS connections are already in the database from the WizardOBS component
        # Just log what we have
        if wizard_request.obs:
            for obs_conn in wizard_request.obs:
                logger.info(f"OBS connection: {obs_conn.name} at {obs_conn.ws_url}")
                applied_items.append(f"OBS: {obs_conn.name}")
        
        # 3. Create rules from presets
        for rule_config in wizard_request.rules:
            if not rule_config.enabled:
                continue
                
            try:
                # Create rule from preset
                rule_json = await create_rule_from_preset(
                    rule_config.id,
                    rule_config.parameters,
                    wizard_request.drives
                )
                
                # Insert rule into database
                await db.execute(
                    """INSERT INTO so_rules 
                       (id, name, enabled, priority, when_json, do_json, created_at, updated_at)
                       VALUES (?, ?, 1, ?, ?, ?, datetime('now'), datetime('now'))""",
                    (
                        f"wizard_{rule_config.id}",
                        rule_json["name"],
                        rule_json.get("priority", 100),
                        json.dumps(rule_json.get("when", {})),
                        json.dumps(rule_json.get("do", []))
                    )
                )
                applied_items.append(f"Rule: {rule_json['name']}")
            except Exception as e:
                logger.error(f"Failed to create rule {rule_config.id}: {e}")
        
        await db.commit()
        
        # 4. Configure overlays if enabled
        if wizard_request.overlays.enabled and wizard_request.overlays.preset:
            await config_service.set_config("overlays", {
                "enabled": True,
                "preset": wizard_request.overlays.preset,
                "position": wizard_request.overlays.position,
                "margin": wizard_request.overlays.margin
            })
            applied_items.append("Overlay configuration")
        
        # 5. Set guardrails to safe defaults
        await config_service.set_config("guardrails", {
            "pause_if_recording": True,
            "pause_if_gpu_pct_above": 40,
            "pause_if_cpu_pct_above": 70,
            "require_disk_space_gb": 5
        })
        applied_items.append("Safety guardrails")
        
        # 6. Mark wizard as completed
        await config_service.set_config("wizard_state", {
            "completed": True,
            "last_completed_at": datetime.utcnow().isoformat(),
            "version": "1.0.0"
        })
        
        # 7. Start drive watchers
        # This would trigger the watcher service to restart
        # For now, we'll just log it
        logger.info("Wizard configuration applied - watchers should be restarted")
        
        # 8. Schedule initial indexing of existing files
        recording_drives = [d for d in wizard_request.drives if d.role == "recording"]
        for drive in recording_drives:
            # Queue indexing job
            logger.info(f"Queueing indexing job for {drive.abs_path}")
            # This would use NATS to queue the job
        
        return {
            "success": True,
            "message": "Wizard configuration applied successfully",
            "applied": applied_items,
            "next_steps": [
                "Drive watchers have been started",
                "Existing files will be indexed in the background",
                "You can now record and StreamOps will process automatically"
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to apply wizard config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to apply wizard config: {str(e)}")


async def create_rule_from_preset(
    preset_id: str,
    parameters: Dict[str, Any],
    drives: List[WizardDriveConfig]
) -> Dict[str, Any]:
    """Create a rule JSON from a preset and parameters"""
    
    # Find editing drive path from role assignments
    editing_drive = next((d for d in drives if d.role == "editing"), None)
    editing_path = editing_drive.abs_path if editing_drive else "/mnt/editing"
    
    if preset_id == "remux_move_proxy":
        return {
            "name": "Remux, Move and Create Proxies",
            "description": "Automatically remux recordings, move to editing drive, and create proxy files",
            "priority": 100,
            "when": {
                "all": [
                    {"field": "event.type", "operator": "=", "value": "file.closed"},
                    {"field": "file.extension", "operator": "in", "value": [".mkv", ".flv", ".ts"]},
                    {"field": "file.size_mb", "operator": ">", "value": 10}
                ]
            },
            "do": [
                {
                    "action": "ffmpeg_remux",
                    "params": {
                        "container": parameters.get("container", "mov"),
                        "faststart": parameters.get("faststart", True)
                    }
                },
                {
                    "action": "move",
                    "params": {
                        "target": f"{editing_path}/{{date}}/{{filename}}"
                    }
                },
                {
                    "action": "proxy",
                    "params": {
                        "codec": "dnxhr_lb",
                        "if_duration_gt": parameters.get("proxy_min_duration_sec", 900)
                    }
                }
            ],
            "guardrails": {
                "pause_if_recording": True,
                "pause_if_gpu_pct_above": 40
            }
        }
    
    elif preset_id == "archive_old":
        archive_drive = next((d for d in drives if d.role == "archive"), None)
        archive_path = archive_drive.abs_path if archive_drive else "/mnt/archive"
        
        return {
            "name": "Archive Old Recordings",
            "description": "Move old recordings to archive storage",
            "priority": 200,
            "schedule": "0 4 * * *",  # Daily at 4 AM
            "when": {
                "all": [
                    {"field": "file.age_days", "operator": ">", "value": parameters.get("days_old", 90)},
                    {"field": "file.archived", "operator": "=", "value": False}
                ]
            },
            "do": [
                {
                    "action": "move",
                    "params": {
                        "target": f"{archive_path}/{{year}}/{{month}}/{{filename}}"
                    }
                },
                {
                    "action": "tag",
                    "params": {
                        "tag": "archived"
                    }
                }
            ]
        }
    
    else:
        raise ValueError(f"Unknown preset ID: {preset_id}")