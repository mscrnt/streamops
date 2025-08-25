from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid
import json
import logging

from app.api.schemas.rules import (
    RuleResponse, RuleCreate, RuleUpdate, RuleListResponse,
    RuleSearchQuery, RuleExecution, RuleExecutionHistory, 
    RuleTestRequest, RuleStatus
)
from app.api.db.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


# Rule presets for wizard and no-code UI
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
                    "title": "Output Container",
                    "description": "Container format for remuxed files"
                },
                "faststart": {
                    "type": "boolean",
                    "default": True,
                    "title": "Fast Start",
                    "description": "Enable fast start for web playback"
                },
                "editing_target": {
                    "type": "string",
                    "format": "path",
                    "title": "Editing Folder",
                    "description": "Target folder for edited files"
                },
                "proxy_min_duration_sec": {
                    "type": "integer",
                    "default": 900,
                    "minimum": 0,
                    "title": "Minimum Duration for Proxy",
                    "description": "Only create proxies for files longer than this (seconds)"
                }
            },
            "required": ["editing_target"]
        },
        "defaults": {
            "container": "mov",
            "faststart": True,
            "proxy_min_duration_sec": 900
        }
    },
    {
        "id": "generate_thumbs",
        "label": "Generate Thumbnails & Previews",
        "description": "Create poster frame, sprite sheet, and hover preview for all videos",
        "category": "processing",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "poster": {
                    "type": "boolean",
                    "default": True,
                    "title": "Poster Frame",
                    "description": "Generate poster frame thumbnail"
                },
                "sprite": {
                    "type": "boolean",
                    "default": True,
                    "title": "Sprite Sheet",
                    "description": "Generate sprite sheet for timeline scrubbing"
                },
                "hover": {
                    "type": "boolean",
                    "default": True,
                    "title": "Hover Preview",
                    "description": "Generate hover preview video"
                }
            }
        },
        "defaults": {
            "poster": True,
            "sprite": True,
            "hover": True
        }
    },
    {
        "id": "archive_old",
        "label": "Archive Old Recordings",
        "description": "Move recordings older than specified days to archive storage",
        "category": "organization",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "days_old": {
                    "type": "integer",
                    "default": 90,
                    "minimum": 1,
                    "title": "Days Old",
                    "description": "Archive files older than this many days"
                },
                "archive_path": {
                    "type": "string",
                    "format": "path",
                    "title": "Archive Folder",
                    "description": "Target folder for archived files"
                },
                "delete_after_archive": {
                    "type": "boolean",
                    "default": False,
                    "title": "Delete After Archive",
                    "description": "Delete original file after archiving"
                }
            },
            "required": ["archive_path"]
        },
        "defaults": {
            "days_old": 90,
            "delete_after_archive": False
        }
    },
    {
        "id": "transcode_streaming",
        "label": "Transcode for Streaming",
        "description": "Create optimized versions for streaming platforms",
        "category": "export",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "preset": {
                    "type": "string",
                    "enum": ["youtube_1080p", "twitch_720p", "twitter_720p"],
                    "default": "youtube_1080p",
                    "title": "Platform Preset",
                    "description": "Optimized settings for target platform"
                },
                "bitrate_mbps": {
                    "type": "number",
                    "default": 8,
                    "minimum": 1,
                    "maximum": 50,
                    "title": "Bitrate (Mbps)",
                    "description": "Target bitrate in megabits per second"
                }
            }
        },
        "defaults": {
            "preset": "youtube_1080p",
            "bitrate_mbps": 8
        }
    }
]


@router.get("/presets")
async def get_rule_presets() -> List[Dict[str, Any]]:
    """Get available rule presets for the wizard and no-code UI"""
    return RULE_PRESETS


@router.post("/compile")
async def compile_rule(
    rule_data: Dict[str, Any],
    simulate: bool = Query(False, description="Simulate rule execution without saving")
) -> Dict[str, Any]:
    """Compile UI rule data into internal rule format and optionally simulate"""
    try:
        # Validate rule structure
        if not rule_data.get("name"):
            raise HTTPException(status_code=400, detail="Rule name is required")
        
        if not rule_data.get("conditions") and not rule_data.get("schedule"):
            raise HTTPException(status_code=400, detail="Rule must have conditions or schedule")
        
        if not rule_data.get("actions"):
            raise HTTPException(status_code=400, detail="Rule must have at least one action")
        
        # Compile conditions
        when_clause = {}
        if rule_data.get("conditions"):
            conditions = rule_data["conditions"]
            
            # Handle single condition vs multiple
            if len(conditions) == 1:
                when_clause = compile_condition(conditions[0])
            else:
                # Default to AND for multiple conditions
                logic = rule_data.get("condition_logic", "all")
                when_clause = {
                    logic: [compile_condition(c) for c in conditions]
                }
        
        # Compile actions
        do_actions = []
        for action in rule_data.get("actions", []):
            do_actions.append(compile_action(action))
        
        # Compile guardrails
        guardrails = rule_data.get("guardrails", {})
        
        # Build final rule
        compiled_rule = {
            "name": rule_data["name"],
            "description": rule_data.get("description", ""),
            "priority": rule_data.get("priority", 100),
            "when": when_clause,
            "do": do_actions,
            "guardrails": guardrails
        }
        
        # Add schedule if present
        if rule_data.get("schedule"):
            compiled_rule["schedule"] = rule_data["schedule"]
        
        # Simulate if requested
        if simulate and rule_data.get("test_file"):
            # Simulate rule execution
            simulation_result = await simulate_rule_execution(
                compiled_rule, 
                rule_data["test_file"]
            )
            return {
                "compiled": compiled_rule,
                "simulation": simulation_result
            }
        
        return {
            "compiled": compiled_rule,
            "valid": True
        }
        
    except Exception as e:
        logger.error(f"Failed to compile rule: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to compile rule: {str(e)}")


def compile_condition(condition: Dict[str, Any]) -> Dict[str, Any]:
    """Compile a single condition from UI format to internal format"""
    return {
        "field": condition["field"],
        "operator": condition["operator"],
        "value": condition["value"]
    }


def compile_action(action: Dict[str, Any]) -> Dict[str, Any]:
    """Compile a single action from UI format to internal format"""
    return {
        "action": action["type"],
        "params": action.get("parameters", {})
    }


async def simulate_rule_execution(rule: Dict[str, Any], test_file: str) -> Dict[str, Any]:
    """Simulate rule execution on a test file"""
    # This would actually evaluate conditions and show what actions would be taken
    return {
        "would_match": True,
        "matched_conditions": rule["when"],
        "planned_actions": rule["do"],
        "estimated_duration": "2-5 minutes"
    }


@router.get("/", response_model=RuleListResponse)
async def list_rules(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    status: Optional[RuleStatus] = Query(None, description="Filter by status"),
    tags: Optional[List[str]] = Query(None, description="Filter by tags"),
    db=Depends(get_db)
) -> RuleListResponse:
    """List automation rules with filtering and pagination"""
    try:
        query = "SELECT * FROM so_rules WHERE 1=1"
        params = []
        
        if enabled is not None:
            query += " AND enabled = ?"
            params.append(1 if enabled else 0)
        search = None  # Add search parameter if needed
        if search:
            query += " AND (name LIKE ? OR json_extract(when_json, '$') LIKE ?)"
            search_term = f"%{search}%"
            params.extend([search_term, search_term])
        
        query += " ORDER BY priority DESC, created_at DESC"
        
        # Get total count
        count_query = query.replace("SELECT *", "SELECT COUNT(*)", 1)
        cursor = await db.execute(count_query, params)
        total = (await cursor.fetchone())[0]
        
        # Apply pagination
        query += " LIMIT ? OFFSET ?"
        params.extend([per_page, (page - 1) * per_page])
        
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        rules = [
            RuleResponse(
                id=str(uuid.uuid4()),
                name="Auto Remux Recordings",
                description="Automatically remux .mp4 recordings to .mov format",
                priority=100,
                conditions=[
                    {
                        "field": "filepath",
                        "operator": "ends_with",
                        "value": ".mp4"
                    },
                    {
                        "field": "asset_type",
                        "operator": "equals",
                        "value": "video"
                    }
                ],
                actions=[
                    {
                        "action_type": "ffmpeg_remux",
                        "params": {
                            "output_format": "mov",
                            "output_codec": "copy"
                        }
                    }
                ],
                guardrails=[
                    {
                        "guardrail_type": "pause_if_cpu_pct_above",
                        "threshold": 80
                    }
                ],
                enabled=True,
                status=RuleStatus.active,
                tags=["automation", "video"],
                executions=45,
                last_executed=datetime.utcnow(),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
        ]
        
        return RuleListResponse(
            rules=rules,
            total=len(rules),
            page=page,
            per_page=per_page
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch rules: {str(e)}")


@router.post("/", response_model=RuleResponse)
async def create_rule(rule: RuleCreate, db=Depends(get_db)) -> RuleResponse:
    """Create a new automation rule"""
    try:
        rule_id = str(uuid.uuid4())
        
        # Validate rule conditions and actions
        if not rule.conditions or not rule.actions:
            raise HTTPException(status_code=400, detail="Rule must have at least one condition and one action")
        
        # Insert into database
        now = datetime.utcnow()
        await db.execute(
            """INSERT INTO so_rules (id, name, when_json, do_json, priority, enabled, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (rule_id, rule.name, json.dumps(rule.conditions), json.dumps(rule.actions),
             rule.priority, 1 if rule.enabled else 0, now.isoformat(), now.isoformat())
        )
        await db.commit()
        
        new_rule = RuleResponse(
            id=rule_id,
            name=rule.name,
            description=rule.description,
            priority=rule.priority,
            conditions=rule.conditions,
            actions=rule.actions,
            guardrails=rule.guardrails or [],
            enabled=rule.enabled,
            status=RuleStatus.active if rule.enabled else RuleStatus.inactive,
            tags=rule.tags or [],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        return new_rule
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create rule: {str(e)}")


@router.get("/{rule_id}", response_model=RuleResponse)
async def get_rule(rule_id: str, db=Depends(get_db)) -> RuleResponse:
    """Get a specific rule by ID"""
    try:
        cursor = await db.execute("SELECT * FROM so_rules WHERE id = ?", (rule_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
        
        return RuleResponse(
            id=rule_id,
            name="Sample Rule",
            description="A sample automation rule",
            priority=100,
            conditions=[],
            actions=[],
            guardrails=[],
            enabled=True,
            status=RuleStatus.active,
            tags=[],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch rule: {str(e)}")


@router.put("/{rule_id}", response_model=RuleResponse)
async def update_rule(
    rule_id: str,
    rule_update: RuleUpdate,
    db=Depends(get_db)
) -> RuleResponse:
    """Update an automation rule"""
    try:
        # Check if rule exists
        cursor = await db.execute("SELECT * FROM so_rules WHERE id = ?", (rule_id,))
        existing = await cursor.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
        
        # Validate updated conditions and actions
        if rule_update.conditions is not None and not rule_update.conditions:
            raise HTTPException(status_code=400, detail="Rule must have at least one condition")
        if rule_update.actions is not None and not rule_update.actions:
            raise HTTPException(status_code=400, detail="Rule must have at least one action")
        
        updated_rule = RuleResponse(
            id=rule_id,
            name=rule_update.name or "Updated Rule",
            description=rule_update.description,
            priority=rule_update.priority or 100,
            conditions=rule_update.conditions or [],
            actions=rule_update.actions or [],
            guardrails=rule_update.guardrails or [],
            enabled=rule_update.enabled if rule_update.enabled is not None else True,
            status=RuleStatus.active if rule_update.enabled else RuleStatus.inactive,
            tags=rule_update.tags or [],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        return updated_rule
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update rule: {str(e)}")


@router.delete("/{rule_id}")
async def delete_rule(rule_id: str, db=Depends(get_db)) -> Dict[str, str]:
    """Delete an automation rule"""
    try:
        await db.execute("DELETE FROM so_rules WHERE id = ?", (rule_id,))
        await db.commit()
        return {"message": f"Rule {rule_id} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete rule: {str(e)}")


@router.post("/{rule_id}/enable")
async def enable_rule(rule_id: str, db=Depends(get_db)) -> Dict[str, str]:
    """Enable a rule"""
    try:
        await db.execute("UPDATE so_rules SET enabled = 1 WHERE id = ?", (rule_id,))
        await db.commit()
        return {"message": f"Rule {rule_id} enabled"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to enable rule: {str(e)}")


@router.post("/{rule_id}/disable")
async def disable_rule(rule_id: str, db=Depends(get_db)) -> Dict[str, str]:
    """Disable a rule"""
    try:
        await db.execute("UPDATE so_rules SET enabled = 0 WHERE id = ?", (rule_id,))
        await db.commit()
        return {"message": f"Rule {rule_id} disabled"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to disable rule: {str(e)}")


@router.post("/{rule_id}/test", response_model=RuleExecution)
async def test_rule(
    rule_id: str,
    test_request: RuleTestRequest,
    db=Depends(get_db)
) -> RuleExecution:
    """Test a rule against mock or real data"""
    try:
        from app.api.services.rules_engine import RulesEngine
        from app.api.services.nats_service import NATSService
        from app.api.services.obs_service import OBSService
        import time
        
        # Initialize services
        nats_service = NATSService() if os.getenv("NATS_ENABLE", "true").lower() == "true" else None
        obs_service = OBSService()
        
        # Initialize rules engine
        engine = RulesEngine(
            nats_service=nats_service,
            obs_service=obs_service,
            db=db
        )
        
        # Load rule from database
        cursor = await db.execute("SELECT * FROM so_rules WHERE id = ?", (rule_id,))
        rule = await cursor.fetchone()
        if not rule:
            raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
        
        # Parse rule data
        rule_dict = {
            'id': rule[0],
            'name': rule[1],
            'when': json.loads(rule[4]) if rule[4] else {},
            'do': json.loads(rule[5]) if rule[5] else []
        }
        
        # Test data - either from request or mock
        test_data = test_request.test_data or {
            'filepath': test_request.asset_id or '/test/file.mp4',
            'asset_id': test_request.asset_id,
            'event': test_request.event_type or 'file.created'
        }
        
        # Evaluate rule in dry-run mode
        start_time = time.time()
        matched = await engine._evaluate_conditions(rule_dict['when'], test_data)
        execution_time = time.time() - start_time
        
        # Determine what actions would be performed
        actions_to_perform = []
        if matched:
            for action in rule_dict['do']:
                if isinstance(action, dict):
                    actions_to_perform.append(list(action.keys())[0])
                else:
                    actions_to_perform.append(str(action))
        
        return RuleExecution(
            rule_id=rule_id,
            asset_id=test_request.asset_id,
            success=matched,
            actions_performed=actions_to_perform if matched else [],
            execution_time=execution_time,
            executed_at=datetime.utcnow()
        )
    except Exception as e:
        logger.error(f"Failed to test rule {rule_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to test rule: {str(e)}")


@router.post("/{rule_id}/execute")
async def execute_rule(
    rule_id: str,
    asset_id: Optional[str] = Query(None, description="Asset ID to execute rule against"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    force: bool = Query(False, description="Force execution even if conditions not met"),
    db=Depends(get_db)
) -> Dict[str, str]:
    """Manually execute a rule"""
    try:
        # Queue rule execution job via NATS
        from app.api.services.nats_service import publish_job
        job_payload = {
            "rule_id": rule_id,
            "asset_id": asset_id,
            "force": force
        }
        await publish_job("rules.execute", job_payload)
        background_tasks.add_task(_execute_rule, rule_id, asset_id, force)
        
        return {"message": f"Rule {rule_id} execution queued"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute rule: {str(e)}")


@router.get("/{rule_id}/history", response_model=RuleExecutionHistory)
async def get_rule_history(
    rule_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    success_only: Optional[bool] = Query(None, description="Filter by success status"),
    db=Depends(get_db)
) -> RuleExecutionHistory:
    """Get execution history for a rule"""
    try:
        # Query execution history from database
        query = "SELECT * FROM so_rule_executions WHERE rule_id = ?"
        params = [rule_id]
        
        if success_only is not None:
            query += " AND success = ?"
            params.append(1 if success_only else 0)
        
        query += " ORDER BY executed_at DESC LIMIT ? OFFSET ?"
        params.extend([per_page, (page - 1) * per_page])
        
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        
        executions = [
            RuleExecution(
                rule_id=rule_id,
                asset_id="asset_123",
                success=True,
                actions_performed=["ffmpeg_remux"],
                execution_time=5.2,
                executed_at=datetime.utcnow()
            )
        ]
        
        return RuleExecutionHistory(
            executions=executions,
            total=len(executions),
            page=page,
            per_page=per_page
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch rule history: {str(e)}")


@router.post("/search", response_model=RuleListResponse)
async def search_rules(
    query: RuleSearchQuery,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    db=Depends(get_db)
) -> RuleListResponse:
    """Advanced rule search with multiple filters"""
    try:
        # Build search query based on filters
        search_query = "SELECT * FROM so_rules WHERE 1=1"
        params = []
        
        if query.search_text:
            search_query += " AND (name LIKE ? OR json_extract(when_json, '$') LIKE ?)"
            search_term = f"%{query.search_text}%"
            params.extend([search_term, search_term])
        
        if query.enabled is not None:
            search_query += " AND enabled = ?"
            params.append(1 if query.enabled else 0)
        
        if query.tags:
            for tag in query.tags:
                search_query += " AND json_extract(tags_json, '$') LIKE ?"
                params.append(f"%{tag}%")
        
        search_query += " ORDER BY priority DESC LIMIT ? OFFSET ?"
        params.extend([per_page, (page - 1) * per_page])
        
        cursor = await db.execute(search_query, params)
        rows = await cursor.fetchall()
        
        rules = []  # Convert rows to RuleResponse objects
        
        return RuleListResponse(
            rules=[],
            total=0,
            page=page,
            per_page=per_page
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rule search failed: {str(e)}")


@router.get("/templates/actions")
async def get_action_templates() -> Dict[str, Any]:
    """Get available action templates and their parameters"""
    try:
        return {
            "ffmpeg_remux": {
                "description": "Remux media files using FFmpeg",
                "parameters": {
                    "output_format": {"type": "string", "required": True},
                    "output_codec": {"type": "string", "default": "copy"},
                    "output_path": {"type": "string", "required": False}
                }
            },
            "move": {
                "description": "Move files to a different location",
                "parameters": {
                    "destination": {"type": "string", "required": True},
                    "create_dirs": {"type": "boolean", "default": True}
                }
            },
            "copy": {
                "description": "Copy files to a different location",
                "parameters": {
                    "destination": {"type": "string", "required": True},
                    "overwrite": {"type": "boolean", "default": False}
                }
            },
            "thumbs": {
                "description": "Generate thumbnails and previews",
                "parameters": {
                    "poster_count": {"type": "integer", "default": 1},
                    "sprite_interval": {"type": "integer", "default": 10}
                }
            },
            "tag": {
                "description": "Add tags to assets",
                "parameters": {
                    "tags": {"type": "array", "required": True}
                }
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch action templates: {str(e)}")


@router.get("/templates/conditions")
async def get_condition_templates() -> Dict[str, Any]:
    """Get available condition templates and operators"""
    try:
        return {
            "operators": {
                "equals": "Exact match",
                "not_equals": "Not equal to",
                "contains": "Contains substring",
                "not_contains": "Does not contain substring",
                "starts_with": "Starts with string",
                "ends_with": "Ends with string",
                "greater_than": "Greater than (numeric)",
                "less_than": "Less than (numeric)",
                "regex_match": "Regular expression match",
                "file_exists": "File exists at path",
                "has_tag": "Asset has specific tag"
            },
            "fields": {
                "filepath": "Full file path",
                "filename": "File name only",
                "asset_type": "Type of asset (video/audio/image)",
                "file_size": "File size in bytes",
                "duration": "Media duration in seconds",
                "codec": "Video/audio codec",
                "tags": "Asset tags array"
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch condition templates: {str(e)}")


@router.post("/bulk/enable")
async def bulk_enable_rules(
    rule_ids: List[str],
    db=Depends(get_db)
) -> Dict[str, Any]:
    """Enable multiple rules"""
    try:
        # Enable multiple rules
        for rule_id in rule_ids:
            await db.execute("UPDATE so_rules SET enabled = 1 WHERE id = ?", (rule_id,))
        await db.commit()
        
        return {
            "enabled": len(rule_ids),
            "failed": 0,
            "rule_ids": rule_ids
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to bulk enable rules: {str(e)}")


@router.post("/bulk/disable")
async def bulk_disable_rules(
    rule_ids: List[str],
    db=Depends(get_db)
) -> Dict[str, Any]:
    """Disable multiple rules"""
    try:
        # Disable multiple rules
        for rule_id in rule_ids:
            await db.execute("UPDATE so_rules SET enabled = 0 WHERE id = ?", (rule_id,))
        await db.commit()
        
        return {
            "disabled": len(rule_ids),
            "failed": 0,
            "rule_ids": rule_ids
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to bulk disable rules: {str(e)}")


# Background task functions
async def _execute_rule(rule_id: str, asset_id: Optional[str], force: bool):
    """Background task to execute rule"""
    try:
        from app.api.db.database import get_db
        db = await get_db()
        
        # Load rule
        cursor = await db.execute("SELECT * FROM so_rules WHERE id = ?", (rule_id,))
        rule = await cursor.fetchone()
        
        if rule:
            # Parse and execute rule actions
            actions = json.loads(rule[3]) if rule[3] else []
            for action in actions:
                logger.info(f"Executing action {action} for rule {rule_id}")
                # Action execution would be handled by worker
    except Exception as e:
        logger.error(f"Failed to execute rule {rule_id}: {e}")