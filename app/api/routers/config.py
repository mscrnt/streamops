from fastapi import APIRouter, HTTPException, Depends, Query, File, UploadFile
from typing import Optional, List, Dict, Any
from datetime import datetime
import json

from app.api.schemas.config import (
    ConfigResponse, ConfigUpdate, ConfigKeyValue,
    ConfigListResponse, ConfigBulkUpdate
)
from app.api.db.database import get_db
from app.api.services.config_service import ConfigService

router = APIRouter()

@router.get("/", response_model=ConfigListResponse)
async def list_configs(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search in keys and values"),
    db=Depends(get_db)
) -> ConfigListResponse:
    """List all configuration settings with pagination and search"""
    try:
        query = "SELECT * FROM so_configs WHERE 1=1"
        params = []
        
        if search:
            query += " AND (key LIKE ? OR value LIKE ?)"
            search_term = f"%{search}%"
            params.extend([search_term, search_term])
        
        query += " ORDER BY key ASC"
        
        # Get total count
        count_query = query.replace("SELECT *", "SELECT COUNT(*)", 1)
        cursor = await db.execute(count_query, params)
        total = (await cursor.fetchone())[0]
        
        # Apply pagination
        query += " LIMIT ? OFFSET ?"
        params.extend([per_page, (page - 1) * per_page])
        
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        
        configs = []
        for row in rows:
            configs.append(ConfigResponse(
                key=row[0],
                value=json.loads(row[1]) if row[1].startswith('{') or row[1].startswith('[') else row[1],
                description=f"Configuration for {row[0].replace('_', ' ').title()}",
                data_type="string" if isinstance(row[1], str) and not (row[1].startswith('{') or row[1].startswith('[')) else "json",
                default_value=None,
                updated_at=datetime.fromisoformat(row[2]) if row[2] else None
            ))
        
        return ConfigListResponse(
            configs=configs,
            total=total,
            page=page,
            per_page=per_page
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch configurations: {str(e)}")


@router.get("/{key}", response_model=ConfigResponse)
async def get_config(key: str, db=Depends(get_db)) -> ConfigResponse:
    """Get a specific configuration by key"""
    try:
        cursor = await db.execute(
            "SELECT * FROM so_configs WHERE key = ?",
            (key,)
        )
        row = await cursor.fetchone()
        
        if not row:
            # Return default values for known keys
            defaults = {
                "gpu_guard_pct": {"value": 40, "description": "GPU usage threshold percentage"},
                "cpu_guard_pct": {"value": 70, "description": "CPU usage threshold percentage"},
                "pause_when_recording": {"value": True, "description": "Pause processing when OBS is recording"},
                "watch_poll_interval": {"value": 5, "description": "File watcher polling interval in seconds"},
                "file_quiet_seconds": {"value": 45, "description": "Seconds to wait before processing a file"},
                "default_remux_format": {"value": "mov", "description": "Default format for remuxing"},
                "enable_auto_proxy": {"value": True, "description": "Automatically create proxy files"},
                "proxy_min_duration_sec": {"value": 900, "description": "Minimum duration for proxy creation"},
                "proxy_codec": {"value": "dnxhr_lb", "description": "Codec for proxy files"},
                "queue_paused": {"value": False, "description": "Whether the job queue is paused"}
            }
            
            if key in defaults:
                return ConfigResponse(
                    key=key,
                    value=defaults[key]["value"],
                    description=defaults[key]["description"],
                    data_type="number" if isinstance(defaults[key]["value"], (int, float)) else 
                              "boolean" if isinstance(defaults[key]["value"], bool) else "string",
                    default_value=defaults[key]["value"],
                    updated_at=None
                )
            else:
                raise HTTPException(status_code=404, detail=f"Configuration '{key}' not found")
        
        value = json.loads(row[1]) if row[1].startswith('{') or row[1].startswith('[') else row[1]
        
        # Try to convert to appropriate type
        if row[1].lower() in ['true', 'false']:
            value = row[1].lower() == 'true'
        elif row[1].isdigit():
            value = int(row[1])
        elif row[1].replace('.', '', 1).isdigit():
            value = float(row[1])
        
        return ConfigResponse(
            key=row[0],
            value=value,
            description=f"Configuration for {row[0].replace('_', ' ').title()}",
            data_type="number" if isinstance(value, (int, float)) else 
                      "boolean" if isinstance(value, bool) else 
                      "json" if isinstance(value, (dict, list)) else "string",
            default_value=None,
            updated_at=datetime.fromisoformat(row[2]) if row[2] else None
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch configuration: {str(e)}")


@router.put("/{key}", response_model=ConfigResponse)
async def update_config(
    key: str,
    config_update: ConfigUpdate,
    db=Depends(get_db)
) -> ConfigResponse:
    """Update a specific configuration"""
    try:
        # Convert value to string for storage
        if isinstance(config_update.value, (dict, list)):
            value_str = json.dumps(config_update.value)
        else:
            value_str = str(config_update.value)
        
        now = datetime.utcnow()
        
        # Upsert configuration
        await db.execute(
            """INSERT OR REPLACE INTO so_configs (key, value, updated_at)
               VALUES (?, ?, ?)""",
            (key, value_str, now.isoformat())
        )
        await db.commit()
        
        return ConfigResponse(
            key=key,
            value=config_update.value,
            description=config_update.description or f"Configuration for {key.replace('_', ' ').title()}",
            data_type="number" if isinstance(config_update.value, (int, float)) else 
                      "boolean" if isinstance(config_update.value, bool) else 
                      "json" if isinstance(config_update.value, (dict, list)) else "string",
            default_value=None,
            updated_at=now
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update configuration: {str(e)}")


@router.post("/", response_model=ConfigResponse)
async def create_config(config: ConfigKeyValue, db=Depends(get_db)) -> ConfigResponse:
    """Create a new configuration setting"""
    try:
        # Check if config already exists
        cursor = await db.execute(
            "SELECT key FROM so_configs WHERE key = ?",
            (config.key,)
        )
        if await cursor.fetchone():
            raise HTTPException(status_code=409, detail=f"Configuration '{config.key}' already exists")
        
        # Convert value to string for storage
        if isinstance(config.value, (dict, list)):
            value_str = json.dumps(config.value)
        else:
            value_str = str(config.value)
        
        now = datetime.utcnow()
        
        # Insert configuration
        await db.execute(
            """INSERT INTO so_configs (key, value, updated_at)
               VALUES (?, ?, ?)""",
            (config.key, value_str, now.isoformat())
        )
        await db.commit()
        
        return ConfigResponse(
            key=config.key,
            value=config.value,
            description=config.description or f"Configuration for {config.key.replace('_', ' ').title()}",
            data_type=config.data_type or ("number" if isinstance(config.value, (int, float)) else 
                                          "boolean" if isinstance(config.value, bool) else 
                                          "json" if isinstance(config.value, (dict, list)) else "string"),
            default_value=config.default_value,
            updated_at=now
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create configuration: {str(e)}")


@router.delete("/{key}")
async def delete_config(key: str, db=Depends(get_db)) -> Dict[str, str]:
    """Delete a configuration setting"""
    try:
        # Check if config exists
        cursor = await db.execute(
            "SELECT key FROM so_configs WHERE key = ?",
            (key,)
        )
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail=f"Configuration '{key}' not found")
        
        # Delete configuration
        await db.execute("DELETE FROM so_configs WHERE key = ?", (key,))
        await db.commit()
        
        return {"message": f"Configuration '{key}' deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete configuration: {str(e)}")


@router.post("/bulk-update", response_model=List[ConfigResponse])
async def bulk_update_configs(
    bulk_update: ConfigBulkUpdate,
    db=Depends(get_db)
) -> List[ConfigResponse]:
    """Update multiple configurations at once"""
    try:
        results = []
        now = datetime.utcnow()
        
        for config_update in bulk_update.configs:
            # Convert value to string for storage
            if isinstance(config_update.value, (dict, list)):
                value_str = json.dumps(config_update.value)
            else:
                value_str = str(config_update.value)
            
            # Upsert configuration
            await db.execute(
                """INSERT OR REPLACE INTO so_configs (key, value, updated_at)
                   VALUES (?, ?, ?)""",
                (config_update.key, value_str, now.isoformat())
            )
            
            results.append(ConfigResponse(
                key=config_update.key,
                value=config_update.value,
                description=config_update.description or f"Configuration for {config_update.key.replace('_', ' ').title()}",
                data_type="number" if isinstance(config_update.value, (int, float)) else 
                          "boolean" if isinstance(config_update.value, bool) else 
                          "json" if isinstance(config_update.value, (dict, list)) else "string",
                default_value=None,
                updated_at=now
            ))
        
        await db.commit()
        return results
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to bulk update configurations: {str(e)}")


@router.post("/reset")
async def reset_configs(
    keys: Optional[List[str]] = Query(None, description="Specific keys to reset"),
    db=Depends(get_db)
) -> Dict[str, str]:
    """Reset configurations to default values"""
    try:
        # Default values
        defaults = {
            "gpu_guard_pct": "40",
            "cpu_guard_pct": "70",
            "pause_when_recording": "true",
            "watch_poll_interval": "5",
            "file_quiet_seconds": "45",
            "default_remux_format": "mov",
            "enable_auto_proxy": "true",
            "proxy_min_duration_sec": "900",
            "proxy_codec": "dnxhr_lb",
            "enable_scene_detect": "true",
            "enable_waveform": "true",
            "enable_hover_scrub": "true",
            "thumbnail_interval_sec": "20",
            "sprite_columns": "5",
            "enable_social_exports": "false",
            "enable_remote_workers": "false",
            "worker_heartbeat_sec": "30",
            "metrics_retention_days": "90"
        }
        
        now = datetime.utcnow().isoformat()
        
        if keys:
            # Reset specific keys
            for key in keys:
                if key in defaults:
                    await db.execute(
                        """INSERT OR REPLACE INTO so_configs (key, value, updated_at)
                           VALUES (?, ?, ?)""",
                        (key, defaults[key], now)
                    )
            await db.commit()
            return {"message": f"Reset {len(keys)} configurations to defaults"}
        else:
            # Reset all configurations
            for key, value in defaults.items():
                await db.execute(
                    """INSERT OR REPLACE INTO so_configs (key, value, updated_at)
                       VALUES (?, ?, ?)""",
                    (key, value, now)
                )
            await db.commit()
            return {"message": "All configurations reset to defaults"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset configurations: {str(e)}")


@router.get("/export/json")
async def export_configs(db=Depends(get_db)) -> Dict[str, Any]:
    """Export all configurations as JSON"""
    try:
        cursor = await db.execute("SELECT key, value FROM so_configs ORDER BY key")
        rows = await cursor.fetchall()
        
        configs = {}
        for row in rows:
            key = row[0]
            value = row[1]
            
            # Try to parse JSON
            if value.startswith('{') or value.startswith('['):
                configs[key] = json.loads(value)
            # Try to convert to appropriate type
            elif value.lower() in ['true', 'false']:
                configs[key] = value.lower() == 'true'
            elif value.isdigit():
                configs[key] = int(value)
            elif value.replace('.', '', 1).isdigit():
                configs[key] = float(value)
            else:
                configs[key] = value
        
        return configs
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export configurations: {str(e)}")


@router.post("/import")
async def import_configs(
    file: UploadFile = File(...),
    overwrite: bool = Query(False, description="Overwrite existing configurations"),
    db=Depends(get_db)
) -> Dict[str, Any]:
    """Import configurations from a JSON file"""
    try:
        # Read and parse the uploaded file
        content = await file.read()
        configs = json.loads(content)
        
        if not isinstance(configs, dict):
            raise HTTPException(status_code=400, detail="Invalid configuration format")
        
        imported = 0
        skipped = 0
        now = datetime.utcnow().isoformat()
        
        for key, value in configs.items():
            # Check if config exists
            cursor = await db.execute(
                "SELECT key FROM so_configs WHERE key = ?",
                (key,)
            )
            exists = await cursor.fetchone() is not None
            
            if exists and not overwrite:
                skipped += 1
                continue
            
            # Convert value to string for storage
            if isinstance(value, (dict, list)):
                value_str = json.dumps(value)
            else:
                value_str = str(value)
            
            # Insert or replace configuration
            await db.execute(
                """INSERT OR REPLACE INTO so_configs (key, value, updated_at)
                   VALUES (?, ?, ?)""",
                (key, value_str, now)
            )
            imported += 1
        
        await db.commit()
        
        return {
            "message": f"Import completed",
            "imported": imported,
            "skipped": skipped,
            "total": len(configs)
        }
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to import configurations: {str(e)}")