"""Sandboxed filesystem API for browsing mounted drives"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional, Dict, Any
from pathlib import Path
from pydantic import BaseModel, Field
import os
import logging
from datetime import datetime

from app.api.db.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()

class FileEntry(BaseModel):
    name: str
    type: str  # 'dir' or 'file'
    size: int
    mtime: float
    writable: bool = False

class DirectoryListResponse(BaseModel):
    root_id: str
    cwd: str
    entries: List[FileEntry]
    can_navigate_up: bool
    absolute_path: str
    is_writable: bool

class EnsureDirectoryRequest(BaseModel):
    root_id: str
    path: str = ""

class EnsureDirectoryResponse(BaseModel):
    absolute_path: str
    created: bool
    writable: bool
    exists: bool


def safe_join(base: str, relative: str) -> Optional[str]:
    """
    Safely join a base path with a relative path, preventing directory traversal.
    Returns None if the result would escape the base directory.
    """
    # Normalize the base path
    base = os.path.abspath(base)
    
    # Handle empty relative path
    if not relative or relative == ".":
        return base
    
    # Clean the relative path
    # Remove leading slashes to ensure it's relative
    relative = relative.lstrip("/\\")
    
    # Join and normalize
    joined = os.path.abspath(os.path.join(base, relative))
    
    # Check if the result is within the base directory
    if not joined.startswith(base):
        return None
    
    return joined


async def get_mounted_roots(db) -> Dict[str, Dict[str, Any]]:
    """Get all mounted drive roots from database and environment"""
    roots = {}
    
    # Get drives from database
    cursor = await db.execute("""
        SELECT id, path, label, enabled, config_json, stats_json
        FROM so_drives
        WHERE enabled = 1
        ORDER BY label
    """)
    rows = await cursor.fetchall()
    
    for row in rows:
        roots[row[0]] = {
            "id": row[0],
            "path": row[1],
            "label": row[2],
            "enabled": row[3],
            "config": row[4],
            "stats": row[5]
        }
    
    # Add environment drives
    for i in range(1, 10):  # Check up to 10 mount points
        container_path = os.getenv(f"SO_MOUNT_{i}_PATH")
        label = os.getenv(f"SO_MOUNT_{i}_LABEL", f"Mount {i}")
        
        if container_path and os.path.exists(container_path):
            mount_id = f"env_mount_{i}"
            if mount_id not in roots:  # Don't override if already in DB
                roots[mount_id] = {
                    "id": mount_id,
                    "path": container_path,
                    "label": label,
                    "enabled": True,
                    "config": {},
                    "stats": {}
                }
    
    return roots


def check_directory_writable(path: str) -> bool:
    """Check if a directory is writable by attempting to create a temp file"""
    try:
        # Try to create a temporary file
        test_file = os.path.join(path, f".streamops_write_test_{os.getpid()}")
        
        # Attempt to create and immediately delete
        try:
            with open(test_file, 'w') as f:
                f.write("test")
            os.unlink(test_file)
            return True
        except:
            return False
    except:
        return False


@router.get("/list", response_model=DirectoryListResponse)
async def list_directory(
    root_id: str,
    path: str = Query(default="", description="Relative path within root"),
    show_hidden: bool = Query(default=False, description="Show hidden files"),
    db=Depends(get_db)
) -> DirectoryListResponse:
    """List directory contents within a sandboxed root"""
    try:
        # Get mounted roots
        roots = await get_mounted_roots(db)
        
        if root_id not in roots:
            raise HTTPException(status_code=404, detail=f"Root '{root_id}' not found")
        
        root = roots[root_id]
        root_path = root["path"]
        
        # Safely join paths
        abs_path = safe_join(root_path, path)
        if abs_path is None:
            raise HTTPException(status_code=400, detail="Path traversal detected")
        
        # Check if path exists and is a directory
        if not os.path.exists(abs_path):
            raise HTTPException(status_code=404, detail="Path not found")
        
        if not os.path.isdir(abs_path):
            raise HTTPException(status_code=400, detail="Path is not a directory")
        
        # List directory contents
        entries = []
        try:
            items = os.listdir(abs_path)
            
            # Filter hidden files if requested
            if not show_hidden:
                items = [i for i in items if not i.startswith('.')]
            
            for item in sorted(items):
                item_path = os.path.join(abs_path, item)
                
                try:
                    stat = os.stat(item_path)
                    is_dir = os.path.isdir(item_path)
                    
                    # Check if writable (for directories)
                    writable = False
                    if is_dir:
                        writable = check_directory_writable(item_path)
                    else:
                        writable = os.access(item_path, os.W_OK)
                    
                    entries.append(FileEntry(
                        name=item,
                        type="dir" if is_dir else "file",
                        size=stat.st_size if not is_dir else 0,
                        mtime=stat.st_mtime,
                        writable=writable
                    ))
                except OSError as e:
                    # Skip items we can't stat
                    logger.warning(f"Cannot stat {item_path}: {e}")
                    continue
            
            # Sort: directories first, then by name
            entries.sort(key=lambda x: (x.type != "dir", x.name.lower()))
            
        except PermissionError:
            raise HTTPException(status_code=403, detail="Permission denied")
        
        # Check if current directory is writable
        is_writable = check_directory_writable(abs_path)
        
        # Can navigate up if we're not at the root
        can_navigate_up = abs_path != root_path
        
        return DirectoryListResponse(
            root_id=root_id,
            cwd=path,
            entries=entries,
            can_navigate_up=can_navigate_up,
            absolute_path=abs_path,
            is_writable=is_writable
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list directory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ensure-dir", response_model=EnsureDirectoryResponse)
async def ensure_directory(
    request: EnsureDirectoryRequest,
    db=Depends(get_db)
) -> EnsureDirectoryResponse:
    """Create a directory if it doesn't exist (sandboxed)"""
    try:
        # Get mounted roots
        roots = await get_mounted_roots(db)
        
        if request.root_id not in roots:
            raise HTTPException(status_code=404, detail=f"Root '{request.root_id}' not found")
        
        root = roots[request.root_id]
        root_path = root["path"]
        
        # Safely join paths
        abs_path = safe_join(root_path, request.path)
        if abs_path is None:
            raise HTTPException(status_code=400, detail="Path traversal detected")
        
        # Check if it already exists
        exists = os.path.exists(abs_path)
        created = False
        
        if not exists:
            try:
                # Create directory with parents
                os.makedirs(abs_path, exist_ok=True)
                created = True
                logger.info(f"Created directory: {abs_path}")
            except PermissionError:
                raise HTTPException(status_code=403, detail="Permission denied to create directory")
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to create directory: {e}")
        
        # Check if writable
        writable = check_directory_writable(abs_path) if os.path.isdir(abs_path) else False
        
        return EnsureDirectoryResponse(
            absolute_path=abs_path,
            created=created,
            writable=writable,
            exists=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to ensure directory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/validate-path")
async def validate_path(
    root_id: str,
    path: str = Query(default="", description="Path to validate"),
    require_write: bool = Query(default=False, description="Check if path is writable"),
    db=Depends(get_db)
) -> Dict[str, Any]:
    """Validate if a path exists and meets requirements"""
    try:
        # Get mounted roots
        roots = await get_mounted_roots(db)
        
        if root_id not in roots:
            return {
                "valid": False,
                "exists": False,
                "reason": f"Root '{root_id}' not found"
            }
        
        root = roots[root_id]
        root_path = root["path"]
        
        # Safely join paths
        abs_path = safe_join(root_path, path)
        if abs_path is None:
            return {
                "valid": False,
                "exists": False,
                "reason": "Invalid path (traversal detected)"
            }
        
        # Check existence
        exists = os.path.exists(abs_path)
        if not exists:
            return {
                "valid": False,
                "exists": False,
                "absolute_path": abs_path,
                "reason": "Path does not exist"
            }
        
        # Check if it's a directory
        is_dir = os.path.isdir(abs_path)
        if not is_dir:
            return {
                "valid": False,
                "exists": True,
                "absolute_path": abs_path,
                "reason": "Path is not a directory"
            }
        
        # Check writability if required
        writable = check_directory_writable(abs_path)
        if require_write and not writable:
            return {
                "valid": False,
                "exists": True,
                "is_directory": True,
                "writable": False,
                "absolute_path": abs_path,
                "reason": "Directory is not writable"
            }
        
        return {
            "valid": True,
            "exists": True,
            "is_directory": True,
            "writable": writable,
            "absolute_path": abs_path
        }
        
    except Exception as e:
        logger.error(f"Failed to validate path: {e}")
        return {
            "valid": False,
            "exists": False,
            "reason": str(e)
        }