from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks, Body
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime, timedelta, time
from pydantic import BaseModel, Field, validator
import uuid
import json
import os
import re
import logging
import aiosqlite
from pathlib import Path

from app.api.db.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()

# Pydantic models for rules API
class ActiveHours(BaseModel):
    enabled: bool = True
    start: str = "00:00"  # HH:MM format
    end: str = "23:59"    # HH:MM format
    days: List[int] = [1, 2, 3, 4, 5, 6, 7]  # 1=Mon, 7=Sun
    
    @validator('start', 'end')
    def validate_time_format(cls, v):
        if not re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', v):
            raise ValueError('Time must be in HH:MM format')
        return v

class RuleTrigger(BaseModel):
    type: Literal["file_closed", "schedule", "tagged", "manual", "api"]
    params: Dict[str, Any] = {}

class RuleCondition(BaseModel):
    field: str
    op: str  # equals, contains, regex, lt, lte, gte, gt, in, matches
    value: Any

class RuleAction(BaseModel):
    type: str
    params: Dict[str, Any]

class RuleGuardrails(BaseModel):
    pause_if_recording: bool = True
    pause_if_gpu_pct_above: Optional[int] = 40
    pause_if_cpu_pct_above: Optional[int] = 70
    require_disk_space_gb: Optional[int] = 5

class RuleCreate(BaseModel):
    name: str
    enabled: bool = True
    priority: int = Field(50, ge=1, le=100)
    trigger: RuleTrigger
    when: List[RuleCondition] = []
    quiet_period_sec: int = 45
    active_hours: Optional[ActiveHours] = None
    guardrails: Optional[RuleGuardrails] = None
    do: List[Dict[str, Any]]
    meta: Dict[str, Any] = {}

class RuleUpdate(BaseModel):
    name: Optional[str] = None
    enabled: Optional[bool] = None
    priority: Optional[int] = None
    trigger: Optional[RuleTrigger] = None
    when: Optional[List[RuleCondition]] = None
    quiet_period_sec: Optional[int] = None
    active_hours: Optional[ActiveHours] = None
    guardrails: Optional[RuleGuardrails] = None
    do: Optional[List[Dict[str, Any]]] = None
    meta: Optional[Dict[str, Any]] = None

class RuleResponse(BaseModel):
    id: str
    name: str
    enabled: bool
    priority: int
    trigger: Dict[str, Any]
    when: List[Dict[str, Any]]
    quiet_period_sec: int
    active_hours: Optional[Dict[str, Any]]
    guardrails: Dict[str, Any]
    do: List[Dict[str, Any]]
    meta: Dict[str, Any]
    last_triggered: Optional[str]
    last_error: Optional[str]
    created_at: str
    updated_at: str

class RuleListResponse(BaseModel):
    rules: List[RuleResponse]
    total: int

class RuleTestRequest(BaseModel):
    filepath: str

class RuleTestResponse(BaseModel):
    matched: bool
    conditions_met: List[str]
    actions: List[Dict[str, Any]]
    deferred_until: Optional[str] = None
    deferred_reason: Optional[str] = None

class PresetResponse(BaseModel):
    id: str
    label: str
    description: str
    category: str
    parameters_schema: Dict[str, Any]
    defaults: Dict[str, Any]
    enabled: bool = False

# Rule presets
RULE_PRESETS = [
    {
        "id": "remux_move_proxy",
        "label": "Remux to MOV, Move to Editing, Create Proxies",
        "description": "Remux MKV files to MOV with faststart, move to editing drive, and create proxy files for clips longer than 15 minutes",
        "category": "processing",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "container": {
                    "type": "string",
                    "enum": ["mov", "mp4"],
                    "default": "mov",
                    "title": "Output Container"
                },
                "faststart": {
                    "type": "boolean",
                    "default": True,
                    "title": "Fast Start"
                },
                "editing_folder": {
                    "type": "string",
                    "format": "path",
                    "title": "Editing Folder",
                    "default": "/mnt/drive_f/Editing/{YYYY}/{MM}/{DD}"
                },
                "proxy_min_duration_sec": {
                    "type": "integer",
                    "default": 900,
                    "title": "Min Duration for Proxy (seconds)"
                }
            }
        },
        "defaults": {
            "container": "mov",
            "faststart": True,
            "editing_folder": "/mnt/drive_f/Editing/{YYYY}/{MM}/{DD}",
            "proxy_min_duration_sec": 900
        }
    },
    {
        "id": "archive_old",
        "label": "Archive Old Recordings",
        "description": "Move recordings older than 30 days to archive storage",
        "category": "maintenance",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "older_than_days": {
                    "type": "integer",
                    "default": 30,
                    "title": "Archive files older than (days)"
                },
                "archive_path": {
                    "type": "string",
                    "format": "path",
                    "default": "/mnt/archive",
                    "title": "Archive Location"
                },
                "delete_after_days": {
                    "type": "integer",
                    "default": 90,
                    "title": "Delete from archive after (days)"
                }
            }
        },
        "defaults": {
            "older_than_days": 30,
            "archive_path": "/mnt/archive",
            "delete_after_days": 90
        }
    },
    {
        "id": "transcode_youtube",
        "label": "Transcode for YouTube",
        "description": "Create YouTube-optimized versions with H.264 codec at 1080p",
        "category": "publishing",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "preset": {
                    "type": "string",
                    "enum": ["youtube_1080p", "youtube_1440p", "youtube_4k"],
                    "default": "youtube_1080p",
                    "title": "YouTube Preset"
                },
                "output_folder": {
                    "type": "string",
                    "format": "path",
                    "default": "/mnt/drive_f/YouTube/{YYYY}/{MM}",
                    "title": "Output Folder"
                }
            }
        },
        "defaults": {
            "preset": "youtube_1080p",
            "output_folder": "/mnt/drive_f/YouTube/{YYYY}/{MM}"
        }
    }
]

# Rule metadata for dropdowns
RULE_METADATA = {
    "guardrails": [
        {
            "name": "pause_if_recording",
            "display_name": "Pause if Recording",
            "params": {}
        },
        {
            "name": "pause_if_streaming", 
            "display_name": "Pause if Streaming",
            "params": {}
        },
        {
            "name": "pause_if_cpu_pct_above",
            "display_name": "Pause if CPU Above %",
            "params": {
                "threshold": {
                    "type": "number",
                    "default": 70,
                    "display_name": "CPU Threshold %",
                    "description": "Pause if CPU usage exceeds this percentage"
                }
            }
        },
        {
            "name": "pause_if_gpu_pct_above",
            "display_name": "Pause if GPU Above %",
            "params": {
                "threshold": {
                    "type": "number",
                    "default": 40,
                    "display_name": "GPU Threshold %",
                    "description": "Pause if GPU usage exceeds this percentage"
                }
            }
        }
    ],
    "fields": [
        {"key": "file.extension", "label": "File Extension", "type": "string"},
        {"key": "file.size", "label": "File Size", "type": "number"},
        {"key": "file.duration_sec", "label": "Duration (seconds)", "type": "number"},
        {"key": "file.container", "label": "Container Format", "type": "string"},
        {"key": "file.video_codec", "label": "Video Codec", "type": "string"},
        {"key": "file.audio_codec", "label": "Audio Codec", "type": "string"},
        {"key": "file.width", "label": "Video Width", "type": "number"},
        {"key": "file.height", "label": "Video Height", "type": "number"},
        {"key": "file.fps", "label": "Frame Rate", "type": "number"},
        {"key": "path.abs", "label": "File Path", "type": "string"},
        {"key": "path.glob", "label": "Path Pattern", "type": "string"},
        {"key": "tags.contains", "label": "Has Tag", "type": "string"},
        {"key": "older_than_days", "label": "Age (days)", "type": "number"}
    ],
    "operators": [
        {"key": "equals", "label": "Equals", "types": ["string", "number"]},
        {"key": "contains", "label": "Contains", "types": ["string"]},
        {"key": "regex", "label": "Matches Regex", "types": ["string"]},
        {"key": "lt", "label": "Less Than", "types": ["number"]},
        {"key": "lte", "label": "Less Than or Equal", "types": ["number"]},
        {"key": "gte", "label": "Greater Than or Equal", "types": ["number"]},
        {"key": "gt", "label": "Greater Than", "types": ["number"]},
        {"key": "in", "label": "In List", "types": ["string", "number"]},
        {"key": "matches", "label": "Matches Pattern", "types": ["string"]}
    ],
    "actions": [
        {
            "key": "ffmpeg_remux",
            "label": "Remux",
            "description": "Change container without re-encoding",
            "schema": {
                "type": "object",
                "properties": {
                    "container": {
                        "type": "string",
                        "enum": ["mp4", "mov", "mkv", "webm"],
                        "default": "mov",
                        "title": "Container"
                    },
                    "faststart": {
                        "type": "boolean",
                        "default": True,
                        "title": "Fast Start (for web)"
                    }
                }
            }
        },
        {
            "key": "move",
            "label": "Move",
            "description": "Move file to another location",
            "schema": {
                "type": "object",
                "properties": {
                    "dest": {
                        "type": "string",
                        "format": "path",
                        "title": "Destination",
                        "description": "Use {YYYY}, {MM}, {DD}, {Game} variables"
                    }
                },
                "required": ["dest"]
            }
        },
        {
            "key": "copy",
            "label": "Copy",
            "description": "Copy file to another location",
            "schema": {
                "type": "object",
                "properties": {
                    "dest": {
                        "type": "string",
                        "format": "path",
                        "title": "Destination",
                        "description": "Use {YYYY}, {MM}, {DD}, {Game} variables"
                    }
                },
                "required": ["dest"]
            }
        },
        {
            "key": "proxy",
            "label": "Create Proxy",
            "description": "Generate lightweight proxy for editing",
            "schema": {
                "type": "object",
                "properties": {
                    "resolution": {
                        "type": "string",
                        "enum": ["720p", "1080p", "1440p"],
                        "default": "1080p",
                        "title": "Resolution"
                    },
                    "min_duration_sec": {
                        "type": "integer",
                        "default": 0,
                        "title": "Min Duration (seconds)",
                        "description": "Only create proxy for files longer than this"
                    }
                }
            }
},
        {
            "key": "transcode_preset",
            "label": "Transcode",
            "description": "Transcode to optimized preset",
            "schema": {
                "type": "object",
                "properties": {
                    "preset": {
                        "type": "string",
                        "enum": ["youtube_1080p", "youtube_1440p", "youtube_4k", "tiktok_1080x1920", "twitter_720p"],
                        "title": "Preset"
                    }
                },
                "required": ["preset"]
            }
        },
        {
            "key": "tag",
            "label": "Tag",
            "description": "Add or remove tags",
            "schema": {
                "type": "object",
                "properties": {
                    "add": {
                        "type": "array",
                        "items": {"type": "string"},
                        "title": "Add Tags"
                    },
                    "remove": {
                        "type": "array",
                        "items": {"type": "string"},
                        "title": "Remove Tags"
                    }
                }
            }
        },
        {
            "key": "archive",
            "label": "Archive",
            "description": "Move to archive storage",
            "schema": {
                "type": "object",
                "properties": {
                    "policy": {
                        "type": "string",
                        "enum": ["default", "compress", "cold"],
                        "default": "default",
                        "title": "Archive Policy"
                    },
                    "delete_after_days": {
                        "type": "integer",
                        "title": "Delete After (days)",
                        "description": "Auto-delete from archive after this many days"
                    }
                }
            }
        },
        {
            "key": "index_asset",
            "label": "Reindex",
            "description": "Re-scan and update metadata",
            "schema": {
                "type": "object",
                "properties": {}
            }
        }
    ]
}

@router.get("/meta")
async def get_rule_metadata() -> Dict[str, Any]:
    """Get metadata for rule builder dropdowns"""
    return RULE_METADATA

@router.get("/presets", response_model=List[PresetResponse])
async def get_rule_presets(db=Depends(get_db)) -> List[PresetResponse]:
    """Get available rule presets with their enabled status"""
    try:
        # Get all rules to check which presets are enabled
        cursor = await db.execute("""
            SELECT meta_json 
            FROM so_rules 
            WHERE is_active = 1 AND meta_json IS NOT NULL
        """)
        rows = await cursor.fetchall()
        
        enabled_presets = set()
        for row in rows:
            if row[0]:
                meta = json.loads(row[0])
                if 'preset_id' in meta:
                    enabled_presets.add(meta['preset_id'])
        
        # Return presets with enabled status
        presets = []
        for preset in RULE_PRESETS:
            presets.append(PresetResponse(
                **preset,
                enabled=preset['id'] in enabled_presets
            ))
        
        return presets
    except Exception as e:
        logger.error(f"Failed to get rule presets: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=RuleListResponse)
async def list_rules(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    db=Depends(get_db)
) -> RuleListResponse:
    """List all rules with pagination"""
    try:
        query = """SELECT 
            id, name, is_active, priority, trigger_json, conditions_json,
            actions_json, quiet_period_sec, active_hours_json, guardrails_json,
            meta_json, last_triggered, last_error, created_at, updated_at
            FROM so_rules WHERE 1=1"""
        params = []
        
        if enabled is not None:
            query += " AND is_active = ?"
            params.append(1 if enabled else 0)
        
        # Count total
        count_query = "SELECT COUNT(*) FROM so_rules WHERE 1=1"
        count_params = []  
        if enabled is not None:
            count_query += " AND is_active = ?"
            count_params.append(1 if enabled else 0)
        cursor = await db.execute(count_query, count_params)
        total = (await cursor.fetchone())[0]
        
        # Get paginated results
        query += " ORDER BY priority ASC, created_at DESC LIMIT ? OFFSET ?"
        params.extend([per_page, (page - 1) * per_page])
        
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        
        rules = []
        for row in rows:
            rule = {
                "id": row[0],
                "name": row[1],
                "enabled": bool(row[2]),
                "priority": row[3] or 50,
                "trigger": json.loads(row[4]) if row[4] else {"type": "manual"},
                "when": json.loads(row[5]) if row[5] else [],
                "do": json.loads(row[6]) if row[6] else [],
                "quiet_period_sec": row[7] if row[7] is not None else 45,
                "active_hours": json.loads(row[8]) if row[8] else None,
                "guardrails": json.loads(row[9]) if row[9] else {},
                "meta": json.loads(row[10]) if row[10] else {},
                "last_triggered": row[11],
                "last_error": row[12],
                "created_at": row[13] if row[13] else datetime.utcnow().isoformat(),
                "updated_at": row[14] if row[14] else datetime.utcnow().isoformat()
            }
            rules.append(RuleResponse(**rule))
        
        return RuleListResponse(rules=rules, total=total)
    except Exception as e:
        logger.error(f"Failed to list rules: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{rule_id}", response_model=RuleResponse)
async def get_rule(rule_id: str, db=Depends(get_db)) -> RuleResponse:
    """Get a specific rule by ID"""
    try:
        cursor = await db.execute("""SELECT 
            id, name, is_active, priority, trigger_json, conditions_json,
            actions_json, quiet_period_sec, active_hours_json, guardrails_json,
            meta_json, last_triggered, last_error, created_at, updated_at
            FROM so_rules WHERE id = ?""", (rule_id,))
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Rule not found")
        
        rule = {
            "id": row[0],
            "name": row[1],
            "enabled": bool(row[2]),
            "priority": row[3] or 50,
            "trigger": json.loads(row[4]) if row[4] else {"type": "manual"},
            "when": json.loads(row[5]) if row[5] else [],
            "do": json.loads(row[6]) if row[6] else [],
            "quiet_period_sec": row[7] if row[7] is not None else 45,
            "active_hours": json.loads(row[8]) if row[8] else None,
            "guardrails": json.loads(row[9]) if row[9] else {},
            "meta": json.loads(row[10]) if row[10] else {},
            "last_triggered": row[11],
            "last_error": row[12],
            "created_at": row[13] if row[13] else datetime.utcnow().isoformat(),
            "updated_at": row[14] if row[14] else datetime.utcnow().isoformat()
        }
        
        return RuleResponse(**rule)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get rule: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/", response_model=RuleResponse)
async def create_rule(rule: RuleCreate, db=Depends(get_db)) -> RuleResponse:
    """Create a new rule"""
    try:
        rule_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        
        # Columns are now part of the main schema in database.py
        
        # Insert rule
        await db.execute("""
            INSERT INTO so_rules (
                id, name, is_active, priority, trigger_json, conditions_json, 
                actions_json, quiet_period_sec, active_hours_json, guardrails_json,
                meta_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            rule_id,
            rule.name,
            1 if rule.enabled else 0,
            rule.priority,
            json.dumps(rule.trigger.dict()),
            json.dumps([c.dict() for c in rule.when]),
            json.dumps(rule.do),
            rule.quiet_period_sec,
            json.dumps(rule.active_hours.dict()) if rule.active_hours else None,
            json.dumps(rule.guardrails.dict()) if rule.guardrails else None,
            json.dumps(rule.meta),
            now,
            now
        ))
        await db.commit()
        
        return await get_rule(rule_id, db)
    except Exception as e:
        logger.error(f"Failed to create rule: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{rule_id}", response_model=RuleResponse)
async def update_rule(rule_id: str, rule: RuleUpdate, db=Depends(get_db)) -> RuleResponse:
    """Update an existing rule"""
    try:
        # Check if rule exists
        cursor = await db.execute("SELECT * FROM so_rules WHERE id = ?", (rule_id,))
        existing = await cursor.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Rule not found")
        
        # Build update query
        updates = []
        params = []
        
        if rule.name is not None:
            updates.append("name = ?")
            params.append(rule.name)
        if rule.enabled is not None:
            updates.append("is_active = ?")
            params.append(1 if rule.enabled else 0)
        if rule.priority is not None:
            updates.append("priority = ?")
            params.append(rule.priority)
        if rule.trigger is not None:
            updates.append("trigger_json = ?")
            params.append(json.dumps(rule.trigger.dict()))
        if rule.when is not None:
            updates.append("conditions_json = ?")
            params.append(json.dumps([c.dict() for c in rule.when]))
        if rule.do is not None:
            updates.append("actions_json = ?")
            params.append(json.dumps(rule.do))
        if rule.quiet_period_sec is not None:
            updates.append("quiet_period_sec = ?")
            params.append(rule.quiet_period_sec)
        if rule.active_hours is not None:
            updates.append("active_hours_json = ?")
            params.append(json.dumps(rule.active_hours.dict()) if rule.active_hours else None)
        if rule.guardrails is not None:
            updates.append("guardrails_json = ?")
            params.append(json.dumps(rule.guardrails.dict()) if rule.guardrails else None)
        if rule.meta is not None:
            updates.append("meta_json = ?")
            params.append(json.dumps(rule.meta))
        
        updates.append("updated_at = ?")
        params.append(datetime.utcnow().isoformat())
        
        params.append(rule_id)
        
        await db.execute(f"""
            UPDATE so_rules SET {', '.join(updates)} WHERE id = ?
        """, params)
        await db.commit()
        
        return await get_rule(rule_id, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update rule: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{rule_id}")
async def delete_rule(rule_id: str, db=Depends(get_db)):
    """Delete a rule"""
    try:
        result = await db.execute("DELETE FROM so_rules WHERE id = ?", (rule_id,))
        await db.commit()
        
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Rule not found")
        
        return {"ok": True, "message": "Rule deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete rule: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{rule_id}/duplicate", response_model=RuleResponse)
async def duplicate_rule(rule_id: str, db=Depends(get_db)) -> RuleResponse:
    """Duplicate an existing rule"""
    try:
        original = await get_rule(rule_id, db)
        
        # Create new rule with same settings but new ID
        new_rule = RuleCreate(
            name=f"{original.name} (Copy)",
            enabled=False,  # Start disabled
            priority=original.priority,
            trigger=RuleTrigger(**original.trigger),
            when=[RuleCondition(**c) for c in original.when],
            quiet_period_sec=original.quiet_period_sec,
            active_hours=ActiveHours(**original.active_hours) if original.active_hours else None,
            guardrails=RuleGuardrails(**original.guardrails) if original.guardrails else None,
            do=original.do,
            meta=original.meta
        )
        
        return await create_rule(new_rule, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to duplicate rule: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/compile")
async def compile_rule(rule: RuleCreate) -> Dict[str, Any]:
    """Validate and compile a rule configuration"""
    try:
        # Validate conditions
        for condition in rule.when:
            field_meta = next((f for f in RULE_METADATA['fields'] if f['key'] == condition.field), None)
            if not field_meta:
                raise HTTPException(status_code=400, detail=f"Unknown field: {condition.field}")
            
            operator_meta = next((o for o in RULE_METADATA['operators'] if o['key'] == condition.op), None)
            if not operator_meta:
                raise HTTPException(status_code=400, detail=f"Unknown operator: {condition.op}")
            
            if field_meta['type'] not in operator_meta['types']:
                raise HTTPException(status_code=400, detail=f"Operator {condition.op} not valid for field type {field_meta['type']}")
        
        # Validate actions
        if not rule.do:
            raise HTTPException(status_code=400, detail="Rule must have at least one action")
        
        for action in rule.do:
            if not action:
                continue
            action_type = list(action.keys())[0]
            action_meta = next((a for a in RULE_METADATA['actions'] if a['key'] == action_type), None)
            if not action_meta:
                raise HTTPException(status_code=400, detail=f"Unknown action: {action_type}")
        
        # Validate active hours
        if rule.active_hours and rule.active_hours.enabled:
            start_time = datetime.strptime(rule.active_hours.start, "%H:%M").time()
            end_time = datetime.strptime(rule.active_hours.end, "%H:%M").time()
            
            if start_time == end_time:
                raise HTTPException(status_code=400, detail="Active hours window has zero length")
            
            if not rule.active_hours.days:
                raise HTTPException(status_code=400, detail="Active hours must have at least one day selected")
        
        # Return normalized rule
        return {
            "valid": True,
            "rule": rule.dict(),
            "message": "Rule is valid and ready to save"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to compile rule: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{rule_id}/test", response_model=RuleTestResponse)
async def test_rule(
    rule_id: str,
    request: RuleTestRequest,
    db=Depends(get_db)
) -> RuleTestResponse:
    """Test a rule against a specific file"""
    try:
        rule = await get_rule(rule_id, db)
        
        # Get file metadata
        file_path = Path(request.filepath)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Test file not found")
        
        file_stats = file_path.stat()
        file_meta = {
            "file.extension": file_path.suffix,
            "file.size": file_stats.st_size,
            "path.abs": str(file_path),
            "path.glob": str(file_path),
            # Additional metadata would be extracted from FFmpeg probe in production
        }
        
        # Check conditions
        conditions_met = []
        matched = True
        
        for condition in rule.when:
            field_value = file_meta.get(condition['field'])
            if field_value is None:
                matched = False
                continue
            
            # Evaluate condition based on operator
            condition_matched = False
            if condition['op'] == 'equals':
                condition_matched = field_value == condition['value']
            elif condition['op'] == 'contains':
                condition_matched = condition['value'] in str(field_value)
            elif condition['op'] == 'gt':
                condition_matched = float(field_value) > float(condition['value'])
            elif condition['op'] == 'gte':
                condition_matched = float(field_value) >= float(condition['value'])
            elif condition['op'] == 'lt':
                condition_matched = float(field_value) < float(condition['value'])
            elif condition['op'] == 'lte':
                condition_matched = float(field_value) <= float(condition['value'])
            elif condition['op'] == 'matches':
                import fnmatch
                condition_matched = fnmatch.fnmatch(str(field_value), condition['value'])
            elif condition['op'] == 'regex':
                condition_matched = bool(re.match(condition['value'], str(field_value)))
            
            if condition_matched:
                conditions_met.append(f"{condition['field']} {condition['op']} {condition['value']}")
            else:
                matched = False
        
        if not matched:
            return RuleTestResponse(
                matched=False,
                conditions_met=conditions_met,
                actions=[],
                deferred_until=None,
                deferred_reason="Conditions not met"
            )
        
        # Check quiet period
        now = datetime.utcnow()
        file_mtime = datetime.fromtimestamp(file_stats.st_mtime)
        quiet_elapsed = (now - file_mtime).total_seconds()
        
        if quiet_elapsed < rule.quiet_period_sec:
            wait_until = file_mtime + timedelta(seconds=rule.quiet_period_sec)
            return RuleTestResponse(
                matched=True,
                conditions_met=conditions_met,
                actions=rule.do,
                deferred_until=wait_until.isoformat(),
                deferred_reason=f"Quiet period: waiting {rule.quiet_period_sec - quiet_elapsed:.0f} more seconds"
            )
        
        # Check active hours
        if rule.active_hours and rule.active_hours['enabled']:
            current_time = datetime.now().time()
            current_day = datetime.now().isoweekday()
            
            start_time = datetime.strptime(rule.active_hours['start'], "%H:%M").time()
            end_time = datetime.strptime(rule.active_hours['end'], "%H:%M").time()
            
            # Check if current day is allowed
            if current_day not in rule.active_hours['days']:
                # Find next allowed day
                next_day = None
                for i in range(1, 8):
                    check_day = ((current_day - 1 + i) % 7) + 1
                    if check_day in rule.active_hours['days']:
                        next_day = check_day
                        break
                
                if next_day:
                    days_until = (next_day - current_day) % 7
                    if days_until == 0:
                        days_until = 7
                    next_window = datetime.now() + timedelta(days=days_until)
                    next_window = next_window.replace(
                        hour=start_time.hour,
                        minute=start_time.minute,
                        second=0,
                        microsecond=0
                    )
                    
                    return RuleTestResponse(
                        matched=True,
                        conditions_met=conditions_met,
                        actions=rule.do,
                        deferred_until=next_window.isoformat(),
                        deferred_reason="Outside active days"
                    )
            
            # Check if current time is in window
            in_window = False
            if start_time <= end_time:
                # Same day window
                in_window = start_time <= current_time <= end_time
            else:
                # Overnight window (e.g., 23:00 to 06:00)
                in_window = current_time >= start_time or current_time <= end_time
            
            if not in_window:
                # Calculate next window opening
                if current_time < start_time:
                    next_window = datetime.now().replace(
                        hour=start_time.hour,
                        minute=start_time.minute,
                        second=0,
                        microsecond=0
                    )
                else:
                    next_window = (datetime.now() + timedelta(days=1)).replace(
                        hour=start_time.hour,
                        minute=start_time.minute,
                        second=0,
                        microsecond=0
                    )
                
                return RuleTestResponse(
                    matched=True,
                    conditions_met=conditions_met,
                    actions=rule.do,
                    deferred_until=next_window.isoformat(),
                    deferred_reason="Outside active hours"
                )
        
        # Rule would execute immediately
        return RuleTestResponse(
            matched=True,
            conditions_met=conditions_met,
            actions=rule.do,
            deferred_until=None,
            deferred_reason=None
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to test rule: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{rule_id}/enable")
async def enable_rule(rule_id: str, db=Depends(get_db)):
    """Enable a rule"""
    try:
        result = await db.execute(
            "UPDATE so_rules SET is_active = 1, updated_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), rule_id)
        )
        await db.commit()
        
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Rule not found")
        
        return {"ok": True, "message": "Rule enabled"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to enable rule: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{rule_id}/disable")
async def disable_rule(rule_id: str, db=Depends(get_db)):
    """Disable a rule"""
    try:
        result = await db.execute(
            "UPDATE so_rules SET is_active = 0, updated_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), rule_id)
        )
        await db.commit()
        
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Rule not found")
        
        return {"ok": True, "message": "Rule disabled"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to disable rule: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/from-preset", response_model=RuleResponse)
async def create_rule_from_preset(
    preset_id: str = Body(..., embed=True),
    parameters: Dict[str, Any] = Body({}),
    quiet_period_sec: int = Body(45),
    active_hours: Optional[ActiveHours] = Body(None),
    db=Depends(get_db)
) -> RuleResponse:
    """Create and enable a rule from a preset"""
    try:
        # Find preset
        preset = next((p for p in RULE_PRESETS if p['id'] == preset_id), None)
        if not preset:
            raise HTTPException(status_code=404, detail="Preset not found")
        
        # Merge parameters with defaults
        params = {**preset['defaults'], **parameters}
        
        # Build rule based on preset
        trigger = RuleTrigger(type="file_closed")
        conditions = []
        actions = []
        
        if preset_id == "remux_move_proxy":
            conditions = [
                RuleCondition(field="file.extension", op="in", value=[".mkv", ".ts", ".flv"]),
                RuleCondition(field="path.glob", op="matches", value="/mnt/*/Recordings/**")
            ]
            actions = [
                {"ffmpeg_remux": {"container": params["container"], "faststart": params["faststart"]}},
                {"move": {"dest": params["editing_folder"]}},
                {"proxy": {"resolution": "1080p", "min_duration_sec": params["proxy_min_duration_sec"]}}
            ]
        elif preset_id == "archive_old":
            conditions = [
                RuleCondition(field="older_than_days", op="gt", value=params["older_than_days"])
            ]
            actions = [
                {"archive": {
                    "policy": "default",
                    "delete_after_days": params.get("delete_after_days")
                }}
            ]
        elif preset_id == "transcode_youtube":
            conditions = [
                RuleCondition(field="file.extension", op="in", value=[".mp4", ".mov", ".mkv"])
            ]
            actions = [
                {"transcode_preset": {"preset": params["preset"]}},
                {"copy": {"dest": params["output_folder"]}}
            ]
        
        # Create rule
        rule = RuleCreate(
            name=preset['label'],
            enabled=True,
            priority=50,
            trigger=trigger,
            when=conditions,
            quiet_period_sec=quiet_period_sec,
            active_hours=active_hours,
            guardrails=RuleGuardrails(),
            do=actions,
            meta={"preset_id": preset_id, "parameters": params}
        )
        
        return await create_rule(rule, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create rule from preset: {e}")
        raise HTTPException(status_code=500, detail=str(e))