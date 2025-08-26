from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field
import uuid
import os
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

from app.api.schemas.drives import (
    DriveResponse, DriveCreate, DriveUpdate, DriveListResponse, DriveSearchQuery,
    DriveStats, DriveActivity, DriveActivityResponse, DriveTest, DriveTestResult,
    DriveStatus, WatcherStatus, DriveType
)
from app.api.db.database import get_db
import aiofiles
import psutil

router = APIRouter()

# Role types
RoleType = Literal["recording", "editing", "archive", "backlog", "assets"]

class AssignRoleRequest(BaseModel):
    role: RoleType
    root_id: str  # Drive ID
    subpath: str = ""  # Relative path within drive
    watch: bool = True

class RoleAssignment(BaseModel):
    role: RoleType
    drive_id: str
    drive_label: str
    subpath: str
    abs_path: str
    watch: bool
    exists: bool
    writable: bool

class RolesResponse(BaseModel):
    roles: Dict[str, Optional[RoleAssignment]]


@router.get("/", response_model=DriveListResponse)
async def list_drives(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    status: Optional[DriveStatus] = Query(None, description="Filter by drive status"),
    drive_type: Optional[DriveType] = Query(None, description="Filter by drive type"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    watcher_status: Optional[WatcherStatus] = Query(None, description="Filter by watcher status"),
    db=Depends(get_db)
) -> DriveListResponse:
    """List watched drives with filtering and pagination"""
    try:
        # Build query with filters
        query = "SELECT * FROM so_drives WHERE 1=1"
        params = []
        
        if status:
            query += " AND json_extract(stats_json, '$.status') = ?"
            params.append(status.value)
        if drive_type:
            query += " AND type = ?"
            params.append(drive_type.value)
        if enabled is not None:
            query += " AND enabled = ?"
            params.append(1 if enabled else 0)
        if watcher_status:
            query += " AND json_extract(stats_json, '$.watcher_status') = ?"
            params.append(watcher_status.value)
        
        query += " ORDER BY created_at DESC"
        
        # Get total count
        count_query = query.replace("SELECT *", "SELECT COUNT(*)", 1)
        cursor = await db.execute(count_query, params)
        total = (await cursor.fetchone())[0]
        
        # Apply pagination
        query += " LIMIT ? OFFSET ?"
        params.extend([per_page, (page - 1) * per_page])
        
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        
        drives = []
        for row in rows:
            config = json.loads(row[4]) if row[4] else {}
            stats = json.loads(row[5]) if row[5] else {}
            tags = json.loads(row[6]) if row[6] else []
            
            # Get drive space info if path exists
            info = {}
            if os.path.exists(row[1]):
                try:
                    import shutil
                    import platform
                    total, used, free = shutil.disk_usage(row[1])
                    
                    # Detect filesystem type
                    filesystem = "unknown"
                    if platform.system() == "Windows" and len(row[1]) >= 3:
                        try:
                            import subprocess
                            result = subprocess.run(["fsutil", "fsinfo", "volumeinfo", row[1][:3]], 
                                                  capture_output=True, text=True, timeout=2)
                            if result.returncode == 0:
                                for line in result.stdout.split('\n'):
                                    if "File System Name" in line:
                                        filesystem = line.split(":")[1].strip()
                                        break
                        except:
                            pass
                    elif platform.system() in ["Linux", "Darwin"]:
                        try:
                            import subprocess
                            result = subprocess.run(["df", "-T", row[1]], 
                                                  capture_output=True, text=True, timeout=2)
                            if result.returncode == 0:
                                lines = result.stdout.strip().split('\n')
                                if len(lines) > 1:
                                    parts = lines[1].split()
                                    if len(parts) > 1:
                                        filesystem = parts[1]
                        except:
                            pass
                    
                    info = {
                        "path": row[1],
                        "drive_type": row[3],
                        "total_space": total,
                        "free_space": free,
                        "used_space": used,
                        "filesystem": filesystem
                    }
                except:
                    pass
            
            drives.append(DriveResponse(
                id=row[0],
                path=row[1],
                label=row[2],
                drive_type=DriveType(row[3]),
                status=DriveStatus(stats.get('status', 'unknown')),
                enabled=row[7] == 1,
                config=config,
                tags=tags,
                info=info if info else None,
                watcher_status=WatcherStatus(stats.get('watcher_status', 'stopped')),
                files_watched=stats.get('files_watched', 0),
                files_processed=stats.get('files_processed', 0),
                last_activity=datetime.fromisoformat(stats['last_activity']) if stats.get('last_activity') else None,
                created_at=datetime.fromisoformat(row[8]),
                updated_at=datetime.fromisoformat(row[9])
            ))
        
        return DriveListResponse(
            drives=drives,
            total=len(drives),
            page=page,
            per_page=per_page
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch drives: {str(e)}")


@router.post("/", response_model=DriveResponse)
async def create_drive_watch(
    drive: DriveCreate,
    background_tasks: BackgroundTasks,
    db=Depends(get_db)
) -> DriveResponse:
    """Create a new drive watch configuration"""
    try:
        drive_id = str(uuid.uuid4())
        
        # Validate drive path exists and is accessible
        if not os.path.exists(drive.path):
            raise HTTPException(status_code=400, detail=f"Path {drive.path} does not exist")
        if not os.path.isdir(drive.path):
            raise HTTPException(status_code=400, detail=f"Path {drive.path} is not a directory")
        if not os.access(drive.path, os.R_OK):
            raise HTTPException(status_code=400, detail=f"Path {drive.path} is not readable")
        
        # Default config if not provided
        if drive.config:
            # Convert WatcherConfig object to dict
            config = drive.config.dict() if hasattr(drive.config, 'dict') else drive.config
        else:
            config = {
                "recursive": True,
                "file_patterns": ["*.mp4", "*.mov", "*.mkv", "*.avi"],
                "ignore_patterns": ["*.tmp", "*.part"],
                "min_file_size": 1024,
                "stable_time": 5,
                "batch_size": 10,
                "poll_interval": 5
            }
        
        # Initial stats
        stats = {
            "status": DriveStatus.active.value,
            "watcher_status": WatcherStatus.running.value if drive.enabled else WatcherStatus.stopped.value,
            "files_watched": 0,
            "files_processed": 0,
            "last_activity": None
        }
        
        # Insert into database
        now = datetime.utcnow()
        await db.execute(
            """INSERT INTO so_drives (id, path, label, type, config_json, stats_json, tags_json, enabled, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (drive_id, drive.path, drive.label, drive.drive_type.value,
             json.dumps(config), json.dumps(stats), json.dumps(drive.tags or []),
             1 if drive.enabled else 0, now.isoformat(), now.isoformat())
        )
        await db.commit()
        
        new_drive = DriveResponse(
            id=drive_id,
            path=drive.path,
            label=drive.label,
            drive_type=drive.drive_type,
            status=DriveStatus.active,
            enabled=drive.enabled,
            config=config,
            tags=drive.tags or [],
            watcher_status=WatcherStatus.running if drive.enabled else WatcherStatus.stopped,
            created_at=now,
            updated_at=now
        )
        
        # Start watcher if enabled
        if drive.enabled:
            background_tasks.add_task(_start_watcher, drive_id, drive.path)
        
        return new_drive
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create drive watch: {str(e)}")


@router.get("/status")
async def get_drives_status(db=Depends(get_db)) -> List[Dict[str, Any]]:
    """Get status of all drives for dashboard"""
    try:
        cursor = await db.execute(
            """SELECT id, path, label, type, config_json, stats_json, enabled 
               FROM so_drives 
               ORDER BY label"""
        )
        rows = await cursor.fetchall()
        
        drives_status = []
        for row in rows:
            drive_id, path, label, drive_type, config_json, stats_json, enabled = row
            config = json.loads(config_json) if config_json else {}
            stats = json.loads(stats_json) if stats_json else {}
            
            # Get current disk usage
            total = 0
            free = 0
            rw = False
            health = "unknown"
            
            if os.path.exists(path):
                try:
                    usage = psutil.disk_usage(path)
                    total = usage.total
                    free = usage.free
                    
                    # Test write permission
                    test_file = os.path.join(path, f".streamops_test_{os.getpid()}")
                    try:
                        with open(test_file, 'w') as f:
                            f.write("test")
                        os.remove(test_file)
                        rw = True
                    except:
                        rw = False
                    
                    # Determine health
                    if not rw:
                        health = "read_only"
                    elif usage.percent > 95:
                        health = "critical"
                    elif usage.percent > 90:
                        health = "warning"
                    else:
                        health = "ok"
                        
                except Exception as e:
                    logger.warning(f"Failed to get usage for {path}: {e}")
                    health = "error"
            else:
                health = "missing"
            
            # Get watcher status
            watcher_status = stats.get("watcher_status", "stopped" if not enabled else "listening")
            
            drives_status.append({
                "id": drive_id,
                "label": label or drive_id,
                "path": path,
                "role": config.get("role", drive_type),
                "total": total,
                "free": free,
                "rw": rw,
                "watcher": watcher_status,
                "last_event_at": stats.get("last_event_at"),
                "health": health
            })
        
        return drives_status
        
    except Exception as e:
        logger.error(f"Failed to get drives status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get drives status: {str(e)}")


@router.get("/discovered")
async def get_discovered_drives(db=Depends(get_db)) -> List[Dict[str, Any]]:
    """Get all mounted drives from environment and database"""
    try:
        drives = []
        
        # Get drives from database
        cursor = await db.execute("""
            SELECT id, path, label, enabled, config_json, stats_json
            FROM so_drives
            ORDER BY label
        """)
        rows = await cursor.fetchall()
        
        for row in rows:
            drive_id, path, label, enabled, config, stats = row
            
            # Check drive status
            online = os.path.exists(path)
            access = "read-write"
            free = 0
            total = 0
            
            if online:
                try:
                    # Check access
                    if not os.access(path, os.W_OK):
                        access = "read-only"
                    
                    # Get disk usage
                    import shutil
                    total, used, free = shutil.disk_usage(path)
                except:
                    access = "error"
            
            drives.append({
                "id": drive_id,
                "path": path,
                "label": label or path,
                "enabled": bool(enabled),
                "online": online,
                "access": access,
                "free": free,
                "total": total,
                "config": json.loads(config) if config else {},
                "stats": json.loads(stats) if stats else {}
            })
        
        # Add drives from environment that aren't in DB
        env_drives = discover_env_drives()
        for env_drive in env_drives:
            if not any(d["path"] == env_drive["path"] for d in drives):
                drives.append(env_drive)
        
        return drives
        
    except Exception as e:
        logger.error(f"Failed to get discovered drives: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def discover_env_drives() -> List[Dict[str, Any]]:
    """Discover drives from environment variables"""
    drives = []
    
    # Check for SO_MOUNT_N environment variables
    for i in range(1, 10):  # Check up to 10 mount points
        host_path = os.getenv(f"SO_MOUNT_{i}_HOST")
        container_path = os.getenv(f"SO_MOUNT_{i}_PATH")
        label = os.getenv(f"SO_MOUNT_{i}_LABEL", f"Mount {i}")
        watch = os.getenv(f"SO_MOUNT_{i}_WATCH", "false").lower() == "true"
        
        if container_path and os.path.exists(container_path):
            # Check drive status
            online = True
            access = "read-write"
            free = 0
            total = 0
            
            try:
                if not os.access(container_path, os.W_OK):
                    access = "read-only"
                
                import shutil
                total, used, free = shutil.disk_usage(container_path)
            except:
                access = "error"
            
            drives.append({
                "id": f"env_mount_{i}",
                "path": container_path,
                "label": label,
                "enabled": True,
                "online": online,
                "access": access,
                "free": free,
                "total": total,
                "config": {"watch": watch, "from_env": True},
                "stats": {}
            })
    
    # Check for convenience role roots
    role_paths = {
        "recording": os.getenv("SO_REC_PATH"),
        "editing": os.getenv("SO_EDIT_PATH"),
        "archive": os.getenv("SO_ARCHIVE_PATH")
    }
    
    for role, path in role_paths.items():
        if path and os.path.exists(path):
            online = True
            access = "read-write"
            free = 0
            total = 0
            
            try:
                if not os.access(path, os.W_OK):
                    access = "read-only"
                
                import shutil
                total, used, free = shutil.disk_usage(path)
            except:
                access = "error"
            
            drives.append({
                "id": f"role_{role}",
                "path": path,
                "label": f"{role.title()} Folder",
                "enabled": True,
                "online": online,
                "access": access,
                "free": free,
                "total": total,
                "config": {"role": role, "from_env": True},
                "stats": {}
            })
    
    return drives


@router.post("/assign-role", response_model=RoleAssignment)
async def assign_role(
    request: AssignRoleRequest,
    db=Depends(get_db)
) -> RoleAssignment:
    """Assign a role to a specific subfolder within a mounted drive"""
    try:
        # First try to get drive from database
        cursor = await db.execute(
            "SELECT id, path, label FROM so_drives WHERE id = ? AND enabled = 1",
            (request.root_id,)
        )
        row = await cursor.fetchone()
        
        if row:
            drive_id, drive_path, drive_label = row
        else:
            # Check if it's an environment drive
            env_drives = discover_env_drives()
            env_drive = next((d for d in env_drives if d["id"] == request.root_id), None)
            
            if not env_drive:
                raise HTTPException(status_code=404, detail=f"Drive '{request.root_id}' not found or disabled")
            
            drive_id = env_drive["id"]
            drive_path = env_drive["path"]
            drive_label = env_drive["label"]
        
        # Safely join paths
        abs_path = safe_join(drive_path, request.subpath)
        if abs_path is None:
            raise HTTPException(status_code=400, detail="Invalid path (traversal detected)")
        
        # Check if path exists
        exists = os.path.exists(abs_path)
        is_dir = os.path.isdir(abs_path) if exists else False
        writable = False
        
        # Create directory if it doesn't exist
        if not exists:
            try:
                os.makedirs(abs_path, exist_ok=True)
                exists = True
                is_dir = True
                logger.info(f"Created directory for role {request.role}: {abs_path}")
            except Exception as e:
                logger.error(f"Failed to create directory {abs_path}: {e}")
                raise HTTPException(status_code=500, detail=f"Cannot create directory: {e}")
        
        if not is_dir:
            raise HTTPException(status_code=400, detail="Path exists but is not a directory")
        
        # Check writability
        writable = check_directory_writable(abs_path)
        
        # Validate write requirements for certain roles
        write_required_roles = ["recording", "editing", "archive"]
        if request.role in write_required_roles and not writable:
            raise HTTPException(
                status_code=400,
                detail=f"Role '{request.role}' requires write access but directory is not writable"
            )
        
        # Update or insert role assignment
        now = datetime.utcnow().isoformat()
        
        # For environment drives, store with a special prefix to avoid FK issues
        stored_drive_id = drive_id if not drive_id.startswith("env_") else None
        
        await db.execute("""
            INSERT OR REPLACE INTO so_roles 
            (role, drive_id, subpath, abs_path, watch, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            request.role,
            stored_drive_id,  # Will be NULL for env drives, avoiding FK constraint
            request.subpath,
            abs_path,
            1 if request.watch else 0,
            now,
            now
        ))
        await db.commit()
        
        logger.info(f"Assigned role {request.role} to {abs_path}")
        
        # TODO: Restart watcher if watch is enabled
        
        return RoleAssignment(
            role=request.role,
            drive_id=drive_id,
            drive_label=drive_label or drive_path,
            subpath=request.subpath,
            abs_path=abs_path,
            watch=request.watch,
            exists=exists,
            writable=writable
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to assign role: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/roles", response_model=RolesResponse)
async def get_role_assignments(db=Depends(get_db)) -> RolesResponse:
    """Get all role assignments"""
    try:
        # Define all possible roles
        all_roles = ["recording", "editing", "archive", "backlog", "assets"]
        roles_dict = {role: None for role in all_roles}
        
        # Get current assignments
        cursor = await db.execute("""
            SELECT r.role, r.drive_id, r.subpath, r.abs_path, r.watch,
                   d.label, d.path
            FROM so_roles r
            LEFT JOIN so_drives d ON r.drive_id = d.id
        """)
        rows = await cursor.fetchall()
        
        for row in rows:
            role, drive_id, subpath, abs_path, watch, drive_label, drive_path = row
            
            # For roles without drive_id (env drives), extract info from path
            if not drive_id and abs_path:
                # Try to match with env drives
                env_drives = discover_env_drives()
                for env_drive in env_drives:
                    if abs_path.startswith(env_drive["path"]):
                        drive_id = env_drive["id"]
                        drive_label = env_drive["label"]
                        break
            
            # Check current status
            exists = os.path.exists(abs_path) if abs_path else False
            writable = check_directory_writable(abs_path) if exists else False
            
            roles_dict[role] = RoleAssignment(
                role=role,
                drive_id=drive_id or "unknown",
                drive_label=drive_label or drive_path or "Unknown Drive",
                subpath=subpath,
                abs_path=abs_path,
                watch=bool(watch),
                exists=exists,
                writable=writable
            )
        
        return RolesResponse(roles=roles_dict)
        
    except Exception as e:
        logger.error(f"Failed to get role assignments: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/roles/{role}")
async def remove_role_assignment(
    role: RoleType,
    db=Depends(get_db)
) -> Dict[str, str]:
    """Remove a role assignment"""
    try:
        await db.execute("DELETE FROM so_roles WHERE role = ?", (role,))
        await db.commit()
        
        logger.info(f"Removed role assignment for {role}")
        
        return {"message": f"Role '{role}' assignment removed"}
        
    except Exception as e:
        logger.error(f"Failed to remove role assignment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{drive_id}", response_model=DriveResponse)
async def get_drive(drive_id: str, db=Depends(get_db)) -> DriveResponse:
    """Get a specific drive watch by ID"""
    try:
        # Get drive from database
        cursor = await db.execute(
            "SELECT * FROM so_drives WHERE id = ?",
            (drive_id,)
        )
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail=f"Drive {drive_id} not found")
        
        config = json.loads(row[4]) if row[4] else {}
        stats = json.loads(row[5]) if row[5] else {}
        tags = json.loads(row[6]) if row[6] else []
        
        # Get drive space info if path exists
        info = {}
        if os.path.exists(row[1]):
            try:
                import shutil
                total, used, free = shutil.disk_usage(row[1])
                info = {
                    "path": row[1],
                    "drive_type": row[3],
                    "total_space": total,
                    "free_space": free,
                    "used_space": used,
                    "filesystem": "unknown"
                }
            except:
                pass
        
        return DriveResponse(
            id=row[0],
            path=row[1],
            label=row[2],
            drive_type=DriveType(row[3]),
            status=DriveStatus(stats.get('status', 'unknown')),
            enabled=row[7] == 1,
            config=config,
            tags=tags,
            info=info if info else None,
            watcher_status=WatcherStatus(stats.get('watcher_status', 'stopped')),
            files_watched=stats.get('files_watched', 0),
            files_processed=stats.get('files_processed', 0),
            last_activity=datetime.fromisoformat(stats['last_activity']) if stats.get('last_activity') else None,
            created_at=datetime.fromisoformat(row[8]),
            updated_at=datetime.fromisoformat(row[9])
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch drive: {str(e)}")


@router.put("/{drive_id}", response_model=DriveResponse)
async def update_drive(
    drive_id: str,
    drive_update: DriveUpdate,
    background_tasks: BackgroundTasks,
    db=Depends(get_db)
) -> DriveResponse:
    """Update a drive watch configuration"""
    try:
        # Get existing drive from database
        cursor = await db.execute(
            "SELECT * FROM so_drives WHERE id = ?",
            (drive_id,)
        )
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail=f"Drive {drive_id} not found")
        
        # Parse existing config
        existing_config = json.loads(row[4]) if row[4] else {}
        existing_stats = json.loads(row[5]) if row[5] else {}
        
        # Update fields
        updates = []
        params = []
        
        if drive_update.label is not None:
            updates.append("label = ?")
            params.append(drive_update.label)
        
        if drive_update.enabled is not None:
            updates.append("enabled = ?")
            params.append(1 if drive_update.enabled else 0)
        
        if drive_update.config:
            existing_config.update(drive_update.config)
            updates.append("config_json = ?")
            params.append(json.dumps(existing_config))
        
        if drive_update.tags is not None:
            updates.append("tags_json = ?")
            params.append(json.dumps(drive_update.tags))
        
        # Update timestamp
        updates.append("updated_at = ?")
        params.append(datetime.utcnow().isoformat())
        
        # Add drive_id to params
        params.append(drive_id)
        
        # Execute update
        await db.execute(
            f"UPDATE so_drives SET {', '.join(updates)} WHERE id = ?",
            params
        )
        await db.commit()
        
        # Get updated drive
        cursor = await db.execute(
            "SELECT * FROM so_drives WHERE id = ?",
            (drive_id,)
        )
        row = await cursor.fetchone()
        
        config = json.loads(row[4]) if row[4] else {}
        stats = json.loads(row[5]) if row[5] else {}
        tags = json.loads(row[6]) if row[6] else []
        
        updated_drive = DriveResponse(
            id=row[0],
            path=row[1],
            label=row[2],
            drive_type=DriveType(row[3]),
            status=DriveStatus(stats.get('status', 'unknown')),
            enabled=row[7] == 1,
            config=config,
            tags=tags,
            watcher_status=WatcherStatus(stats.get('watcher_status', 'stopped')),
            created_at=datetime.fromisoformat(row[8]),
            updated_at=datetime.fromisoformat(row[9])
        )
        
        # Restart watcher with new configuration
        if drive_update.enabled is not None:
            if drive_update.enabled:
                background_tasks.add_task(_start_watcher, drive_id, "/mnt/sample_drive")
            else:
                background_tasks.add_task(_stop_watcher, drive_id)
        
        return updated_drive
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update drive: {str(e)}")


@router.delete("/{drive_id}")
async def delete_drive(
    drive_id: str,
    stop_watcher: bool = Query(True, description="Stop the watcher before deletion"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db=Depends(get_db)
) -> Dict[str, str]:
    """Delete a drive watch configuration"""
    try:
        # Check if drive exists
        cursor = await db.execute(
            "SELECT path FROM so_drives WHERE id = ?",
            (drive_id,)
        )
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail=f"Drive {drive_id} not found")
        
        if stop_watcher:
            background_tasks.add_task(_stop_watcher, drive_id)
        
        # Delete from database
        await db.execute("DELETE FROM so_drives WHERE id = ?", (drive_id,))
        await db.commit()
        
        return {"message": f"Drive watch {drive_id} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete drive: {str(e)}")


@router.post("/{drive_id}/start")
async def start_watcher(
    drive_id: str,
    background_tasks: BackgroundTasks,
    db=Depends(get_db)
) -> Dict[str, str]:
    """Start the file watcher for a drive"""
    try:
        # Get drive path from database
        cursor = await db.execute(
            "SELECT path FROM so_drives WHERE id = ?",
            (drive_id,)
        )
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail=f"Drive {drive_id} not found")
        
        drive_path = row[0]
        background_tasks.add_task(_start_watcher, drive_id, drive_path)
        
        return {"message": f"Watcher for drive {drive_id} started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start watcher: {str(e)}")


@router.post("/{drive_id}/stop")
async def stop_watcher(
    drive_id: str,
    background_tasks: BackgroundTasks,
    db=Depends(get_db)
) -> Dict[str, str]:
    """Stop the file watcher for a drive"""
    try:
        background_tasks.add_task(_stop_watcher, drive_id)
        
        return {"message": f"Watcher for drive {drive_id} stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop watcher: {str(e)}")


@router.post("/{drive_id}/restart")
async def restart_watcher(
    drive_id: str,
    background_tasks: BackgroundTasks,
    db=Depends(get_db)
) -> Dict[str, str]:
    """Restart the file watcher for a drive"""
    try:
        # Get drive path from database
        cursor = await db.execute(
            "SELECT path FROM so_drives WHERE id = ?",
            (drive_id,)
        )
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail=f"Drive {drive_id} not found")
        
        drive_path = row[0]
        
        # Stop then start the watcher
        background_tasks.add_task(_stop_watcher, drive_id)
        background_tasks.add_task(_start_watcher, drive_id, drive_path)
        
        return {"message": f"Watcher for drive {drive_id} restarted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to restart watcher: {str(e)}")




@router.post("/watchers/restart")
async def restart_all_watchers(
    background_tasks: BackgroundTasks,
    db=Depends(get_db)
) -> Dict[str, Any]:
    """Restart all drive watchers - useful after configuration changes"""
    try:
        # Get all enabled drives
        cursor = await db.execute(
            "SELECT id, path FROM so_drives WHERE enabled = 1"
        )
        rows = await cursor.fetchall()
        
        restarted = []
        for row in rows:
            drive_id, drive_path = row
            background_tasks.add_task(_stop_watcher, drive_id)
            background_tasks.add_task(_start_watcher, drive_id, drive_path)
            restarted.append(drive_id)
        
        return {
            "message": "All watchers scheduled for restart",
            "drives": restarted,
            "count": len(restarted)
        }
    except Exception as e:
        logger.error(f"Failed to restart all watchers: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to restart watchers: {str(e)}")


@router.get("/{drive_id}/activity", response_model=DriveActivityResponse)
async def get_drive_activity(
    drive_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    processed_only: Optional[bool] = Query(None, description="Show only processed files"),
    db=Depends(get_db)
) -> DriveActivityResponse:
    """Get activity history for a drive"""
    try:
        # Build query for drive activity
        query = """SELECT * FROM so_drive_activity WHERE drive_id = ?"""
        params = [drive_id]
        
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        if processed_only is not None:
            query += " AND processed = ?"
            params.append(1 if processed_only else 0)
        
        query += " ORDER BY timestamp DESC"
        
        # Get total count
        count_query = query.replace("SELECT *", "SELECT COUNT(*)", 1)
        cursor = await db.execute(count_query, params)
        result = await cursor.fetchone()
        total = result[0] if result else 0
        
        # Apply pagination
        query += " LIMIT ? OFFSET ?"
        params.extend([per_page, (page - 1) * per_page])
        
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        
        activities = []
        for row in rows:
            activities.append(DriveActivity(
                drive_id=row[1],
                event_type=row[2],
                file_path=row[3],
                file_size=row[4],
                timestamp=datetime.fromisoformat(row[5]),
                processed=row[6] == 1
            ))
        
        return DriveActivityResponse(
            activities=activities,
            total=len(activities),
            page=page,
            per_page=per_page
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch drive activity: {str(e)}")


@router.post("/{drive_id}/scan")
async def scan_drive(
    drive_id: str,
    background_tasks: BackgroundTasks,
    force_rescan: bool = Query(False, description="Force rescan of all files"),
    db=Depends(get_db)
) -> Dict[str, str]:
    """Manually scan a drive for new files"""
    try:
        background_tasks.add_task(_scan_drive, drive_id, force_rescan)
        
        return {"message": f"Drive {drive_id} scan queued"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to queue drive scan: {str(e)}")


@router.post("/search", response_model=DriveListResponse)
async def search_drives(
    query: DriveSearchQuery,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    db=Depends(get_db)
) -> DriveListResponse:
    """Advanced drive search with multiple filters"""
    try:
        # Build search query
        base_query = "SELECT * FROM so_drives WHERE 1=1"
        params = []
        
        if query.query:
            base_query += " AND (path LIKE ? OR label LIKE ?)"
            search_term = f"%{query.query}%"
            params.extend([search_term, search_term])
        
        if query.drive_type:
            base_query += " AND type = ?"
            params.append(query.drive_type.value)
        
        if query.enabled is not None:
            base_query += " AND enabled = ?"
            params.append(1 if query.enabled else 0)
        
        if query.tags:
            for tag in query.tags:
                base_query += " AND json_extract(tags_json, '$') LIKE ?"
                params.append(f'%"{tag}"%')
        
        base_query += " ORDER BY created_at DESC"
        
        # Get total count
        count_query = base_query.replace("SELECT *", "SELECT COUNT(*)", 1)
        cursor = await db.execute(count_query, params)
        total = (await cursor.fetchone())[0]
        
        # Apply pagination
        base_query += " LIMIT ? OFFSET ?"
        params.extend([per_page, (page - 1) * per_page])
        
        cursor = await db.execute(base_query, params)
        rows = await cursor.fetchall()
        
        drives = []
        for row in rows:
            config = json.loads(row[4]) if row[4] else {}
            stats = json.loads(row[5]) if row[5] else {}
            tags = json.loads(row[6]) if row[6] else []
            
            drives.append(DriveResponse(
                id=row[0],
                path=row[1],
                label=row[2],
                drive_type=DriveType(row[3]),
                status=DriveStatus(stats.get('status', 'unknown')),
                enabled=row[7] == 1,
                config=config,
                tags=tags,
                watcher_status=WatcherStatus(stats.get('watcher_status', 'stopped')),
                files_watched=stats.get('files_watched', 0),
                files_processed=stats.get('files_processed', 0),
                last_activity=datetime.fromisoformat(stats['last_activity']) if stats.get('last_activity') else None,
                created_at=datetime.fromisoformat(row[8]),
                updated_at=datetime.fromisoformat(row[9])
            ))
        
        return DriveListResponse(
            drives=drives,
            total=total,
            page=page,
            per_page=per_page
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Drive search failed: {str(e)}")


@router.get("/stats/summary", response_model=DriveStats)
async def get_drive_stats(db=Depends(get_db)) -> DriveStats:
    """Get drive and watcher statistics"""
    try:
        # Get drive statistics
        cursor = await db.execute("SELECT COUNT(*) FROM so_drives")
        total_drives = (await cursor.fetchone())[0]
        
        cursor = await db.execute("SELECT COUNT(*) FROM so_drives WHERE enabled = 1")
        active_drives = (await cursor.fetchone())[0]
        
        # Calculate space across all drives
        cursor = await db.execute("SELECT path FROM so_drives WHERE enabled = 1")
        rows = await cursor.fetchall()
        
        total_space = 0
        free_space = 0
        used_space = 0
        
        for row in rows:
            if os.path.exists(row[0]):
                try:
                    import shutil
                    total, used, free = shutil.disk_usage(row[0])
                    total_space += total
                    used_space += used
                    free_space += free
                except:
                    pass
        
        # Get file statistics
        cursor = await db.execute(
            "SELECT SUM(json_extract(stats_json, '$.files_watched')) FROM so_drives"
        )
        result = await cursor.fetchone()
        files_watched = result[0] if result and result[0] else 0
        
        # Get today's processed files
        today = datetime.utcnow().date().isoformat()
        cursor = await db.execute(
            """SELECT COUNT(*) FROM so_assets 
               WHERE DATE(created_at) = DATE(?)""",
            (today,)
        )
        files_processed_today = (await cursor.fetchone())[0]
        
        # Count running watchers
        cursor = await db.execute(
            """SELECT COUNT(*) FROM so_drives 
               WHERE json_extract(stats_json, '$.watcher_status') = 'running'"""
        )
        watchers_running = (await cursor.fetchone())[0]
        
        return DriveStats(
            total_drives=total_drives,
            active_drives=active_drives,
            total_space=total_space,
            free_space=free_space,
            used_space=used_space,
            files_watched=files_watched,
            files_processed_today=files_processed_today,
            watchers_running=watchers_running
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch drive stats: {str(e)}")


@router.post("/test", response_model=DriveTestResult)
async def test_drive_access(test: DriveTest, db=Depends(get_db)) -> DriveTestResult:
    """Test drive accessibility and permissions"""
    try:
        path = Path(test.path)
        
        # Test basic access
        exists = path.exists()
        is_directory = path.is_dir() if exists else False
        readable = os.access(test.path, os.R_OK) if exists else False
        writable = os.access(test.path, os.W_OK) if exists and test.test_write else False
        
        # Get space information if accessible
        space_info = None
        if exists and is_directory:
            try:
                import shutil
                total, used, free = shutil.disk_usage(test.path)
                # Detect drive type and filesystem
                import platform
                drive_type = DriveType.local
                filesystem = "unknown"
                
                if platform.system() == "Windows":
                    import ctypes
                    # Check if network drive on Windows
                    if test.path.startswith("\\\\"):
                        drive_type = DriveType.network
                    elif len(test.path) >= 2 and test.path[1] == ":":
                        try:
                            drive_letter = test.path[0].upper() + ":\\"
                            drive_type_code = ctypes.windll.kernel32.GetDriveTypeW(drive_letter)
                            # 3 = Fixed, 2 = Removable, 4 = Network, 5 = CD-ROM
                            if drive_type_code == 4:
                                drive_type = DriveType.network
                            elif drive_type_code == 2:
                                drive_type = DriveType.external
                        except:
                            pass
                    
                    # Get filesystem type on Windows
                    try:
                        import subprocess
                        result = subprocess.run(["fsutil", "fsinfo", "volumeinfo", test.path[:3]], 
                                              capture_output=True, text=True, timeout=5)
                        if result.returncode == 0:
                            for line in result.stdout.split('\n'):
                                if "File System Name" in line:
                                    filesystem = line.split(":")[1].strip()
                                    break
                    except:
                        pass
                        
                elif platform.system() == "Linux":
                    # Check mount points on Linux
                    try:
                        import subprocess
                        result = subprocess.run(["df", "-T", test.path], 
                                              capture_output=True, text=True, timeout=5)
                        if result.returncode == 0:
                            lines = result.stdout.strip().split('\n')
                            if len(lines) > 1:
                                parts = lines[1].split()
                                if len(parts) > 1:
                                    filesystem = parts[1]
                                    # Check if network mount
                                    if filesystem in ["nfs", "cifs", "smbfs"]:
                                        drive_type = DriveType.network
                                    # Check if external drive (USB)
                                    elif "/media/" in test.path or "/mnt/" in test.path:
                                        drive_type = DriveType.external
                    except:
                        pass
                        
                elif platform.system() == "Darwin":
                    # macOS detection
                    try:
                        import subprocess
                        result = subprocess.run(["diskutil", "info", test.path], 
                                              capture_output=True, text=True, timeout=5)
                        if result.returncode == 0:
                            for line in result.stdout.split('\n'):
                                if "File System" in line:
                                    filesystem = line.split(":")[1].strip().split()[0]
                                elif "Protocol" in line:
                                    protocol = line.split(":")[1].strip()
                                    if "USB" in protocol:
                                        drive_type = DriveType.external
                                    elif "Network" in protocol:
                                        drive_type = DriveType.network
                    except:
                        pass
                
                space_info = {
                    "path": test.path,
                    "drive_type": drive_type,
                    "total_space": total,
                    "used_space": used,
                    "free_space": free,
                    "filesystem": filesystem
                }
            except:
                pass
        
        # Get permissions string
        permissions = None
        if exists:
            import stat
            st = os.stat(test.path)
            permissions = stat.filemode(st.st_mode)
        
        error_message = None
        if not exists:
            error_message = "Path does not exist"
        elif not is_directory:
            error_message = "Path is not a directory"
        elif not readable:
            error_message = "Directory is not readable"
        elif test.test_write and not writable:
            error_message = "Directory is not writable"
        
        return DriveTestResult(
            path=test.path,
            accessible=exists and readable,
            readable=readable,
            writable=writable,
            exists=exists,
            is_directory=is_directory,
            permissions=permissions,
            error_message=error_message,
            space_info=space_info
        )
    except Exception as e:
        return DriveTestResult(
            path=test.path,
            accessible=False,
            readable=False,
            writable=False,
            exists=False,
            is_directory=False,
            error_message=f"Test failed: {str(e)}"
        )


@router.get("/discover")
async def discover_drives() -> List[Dict[str, Any]]:
    """Discover available drives on the system"""
    try:
        drives = []
        
        # Cross-platform drive discovery
        import platform
        
        if platform.system() == "Windows":
            import string
            common_paths = [f"{letter}:\\" for letter in string.ascii_uppercase if os.path.exists(f"{letter}:\\")]
        elif platform.system() == "Darwin":  # macOS
            common_paths = ["/Volumes/" + d for d in os.listdir("/Volumes") if os.path.isdir("/Volumes/" + d)]
        else:  # Linux/Unix
            common_paths = []
            # Check /mnt
            if os.path.exists("/mnt"):
                common_paths.extend(["/mnt/" + d for d in os.listdir("/mnt") if os.path.isdir("/mnt/" + d)])
            # Check /media
            if os.path.exists("/media"):
                common_paths.extend(["/media/" + d for d in os.listdir("/media") if os.path.isdir("/media/" + d)])
            # Add root if nothing found
            if not common_paths:
                common_paths = ["/"]
        
        for path in common_paths:
            if os.path.exists(path):
                try:
                    import shutil
                    total, used, free = shutil.disk_usage(path)
                    
                    drives.append({
                        "path": path,
                        "label": path.split("/")[-1] or path,
                        "total_space": total,
                        "free_space": free,
                        "used_space": used,
                        "available": True
                    })
                except:
                    drives.append({
                        "path": path,
                        "label": path.split("/")[-1] or path,
                        "available": False
                    })
        
        return drives
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to discover drives: {str(e)}")


@router.post("/bulk/start")
async def bulk_start_watchers(
    drive_ids: List[str],
    background_tasks: BackgroundTasks,
    db=Depends(get_db)
) -> Dict[str, Any]:
    """Start watchers for multiple drives"""
    try:
        # Get drive paths from database
        started = 0
        failed = 0
        
        for drive_id in drive_ids:
            cursor = await db.execute(
                "SELECT path FROM so_drives WHERE id = ?",
                (drive_id,)
            )
            row = await cursor.fetchone()
            
            if row:
                background_tasks.add_task(_start_watcher, drive_id, row[0])
                started += 1
            else:
                failed += 1
        
        return {
            "started": started,
            "failed": failed,
            "drive_ids": drive_ids
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to bulk start watchers: {str(e)}")


@router.post("/bulk/stop")
async def bulk_stop_watchers(
    drive_ids: List[str],
    background_tasks: BackgroundTasks,
    db=Depends(get_db)
) -> Dict[str, Any]:
    """Stop watchers for multiple drives"""
    try:
        for drive_id in drive_ids:
            background_tasks.add_task(_stop_watcher, drive_id)
        
        return {
            "stopped": len(drive_ids),
            "failed": 0,
            "drive_ids": drive_ids
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to bulk stop watchers: {str(e)}")


# Background task functions
async def _start_watcher(drive_id: str, drive_path: str):
    """Background task to start file watcher"""
    try:
        # Update watcher status in database
        from app.api.db.database import get_db
        db = await get_db()
        
        # Get current stats
        cursor = await db.execute(
            "SELECT stats_json FROM so_drives WHERE id = ?",
            (drive_id,)
        )
        row = await cursor.fetchone()
        
        if row:
            stats = json.loads(row[0]) if row[0] else {}
            stats['watcher_status'] = WatcherStatus.running.value
            stats['last_activity'] = datetime.utcnow().isoformat()
            
            await db.execute(
                "UPDATE so_drives SET stats_json = ?, updated_at = ? WHERE id = ?",
                (json.dumps(stats), datetime.utcnow().isoformat(), drive_id)
            )
            await db.commit()
            
            logger.info(f"Started watcher for drive {drive_id} at {drive_path}")
            
            # In production, would start actual file watching process here
            # For now, just update the status
    except Exception as e:
        logger.error(f"Failed to start watcher for drive {drive_id}: {e}")


async def _stop_watcher(drive_id: str):
    """Background task to stop file watcher"""
    try:
        # Update watcher status in database
        from app.api.db.database import get_db
        db = await get_db()
        
        # Get current stats
        cursor = await db.execute(
            "SELECT stats_json FROM so_drives WHERE id = ?",
            (drive_id,)
        )
        row = await cursor.fetchone()
        
        if row:
            stats = json.loads(row[0]) if row[0] else {}
            stats['watcher_status'] = WatcherStatus.stopped.value
            
            await db.execute(
                "UPDATE so_drives SET stats_json = ?, updated_at = ? WHERE id = ?",
                (json.dumps(stats), datetime.utcnow().isoformat(), drive_id)
            )
            await db.commit()
            
            logger.info(f"Stopped watcher for drive {drive_id}")
            
            # In production, would stop actual file watching process here
    except Exception as e:
        logger.error(f"Failed to stop watcher for drive {drive_id}: {e}")


async def _scan_drive(drive_id: str, force_rescan: bool):
    """Background task to scan drive for files"""
    try:
        from app.api.db.database import get_db
        db = await get_db()
        
        # Get drive path
        cursor = await db.execute(
            "SELECT path, config_json FROM so_drives WHERE id = ?",
            (drive_id,)
        )
        row = await cursor.fetchone()
        
        if not row:
            logger.error(f"Drive {drive_id} not found")
            return
        
        drive_path = row[0]
        config = json.loads(row[1]) if row[1] else {}
        
        # Get file patterns
        file_patterns = config.get('file_patterns', ['*.mp4', '*.mov', '*.mkv'])
        ignore_patterns = config.get('ignore_patterns', ['*.tmp', '*.part'])
        min_file_size = config.get('min_file_size', 1024)
        recursive = config.get('recursive', True)
        
        # Scan for files
        import glob
        import fnmatch
        
        files_found = 0
        files_added = 0
        
        if recursive:
            for root, dirs, files in os.walk(drive_path):
                for file in files:
                    filepath = os.path.join(root, file)
                    
                    # Check if file matches patterns
                    matches_pattern = any(fnmatch.fnmatch(file, pattern) for pattern in file_patterns)
                    matches_ignore = any(fnmatch.fnmatch(file, pattern) for pattern in ignore_patterns)
                    
                    if matches_pattern and not matches_ignore:
                        try:
                            file_size = os.path.getsize(filepath)
                            if file_size >= min_file_size:
                                files_found += 1
                                
                                # Check if already in database
                                if force_rescan:
                                    # Add or update asset in database
                                    asset_id = str(uuid.uuid4())
                                    now = datetime.utcnow()
                                    
                                    await db.execute(
                                        """INSERT OR IGNORE INTO so_assets 
                                           (id, abs_path, drive_hint, size, status, created_at, updated_at)
                                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                                        (asset_id, filepath, drive_id, file_size, 
                                         'pending', now.isoformat(), now.isoformat())
                                    )
                                    files_added += 1
                        except Exception as e:
                            logger.warning(f"Error processing file {filepath}: {e}")
        
        await db.commit()
        
        # Update drive stats
        cursor = await db.execute(
            "SELECT stats_json FROM so_drives WHERE id = ?",
            (drive_id,)
        )
        row = await cursor.fetchone()
        
        if row:
            stats = json.loads(row[0]) if row[0] else {}
            stats['files_watched'] = stats.get('files_watched', 0) + files_found
            stats['last_scan'] = datetime.utcnow().isoformat()
            
            await db.execute(
                "UPDATE so_drives SET stats_json = ?, updated_at = ? WHERE id = ?",
                (json.dumps(stats), datetime.utcnow().isoformat(), drive_id)
            )
            await db.commit()
        
        logger.info(f"Scanned drive {drive_id}: found {files_found} files, added {files_added} new assets")
    except Exception as e:
        logger.error(f"Failed to scan drive {drive_id}: {e}")


# Role assignment endpoints

def safe_join(base: str, relative: str) -> Optional[str]:
    """Safely join paths, preventing directory traversal"""
    base = os.path.abspath(base)
    if not relative or relative == ".":
        return base
    relative = relative.lstrip("/\\")
    joined = os.path.abspath(os.path.join(base, relative))
    if not joined.startswith(base):
        return None
    return joined


def check_directory_writable(path: str) -> bool:
    """Check if directory is writable"""
    try:
        test_file = os.path.join(path, f".streamops_test_{os.getpid()}")
        with open(test_file, 'w') as f:
            f.write("test")
        os.unlink(test_file)
        return True
    except:
        return False


async def resolve_role_path(role: RoleType, db) -> Optional[str]:
    """Resolve a role to its absolute path"""
    cursor = await db.execute(
        "SELECT abs_path FROM so_roles WHERE role = ?",
        (role,)
    )
    row = await cursor.fetchone()
    return row[0] if row else None