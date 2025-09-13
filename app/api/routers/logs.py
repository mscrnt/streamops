"""Log viewing endpoints"""
import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


class LogEntry(BaseModel):
    """Parsed log entry"""
    timestamp: Optional[str]
    level: str
    module: Optional[str]
    message: str
    raw: str


class LogFile(BaseModel):
    """Log file information"""
    name: str
    path: str
    size: int
    modified: datetime
    lines: int


class LogsResponse(BaseModel):
    """Response for log queries"""
    files: List[LogFile]
    entries: List[LogEntry]
    total: int
    filtered: int


@router.get("/files", response_model=List[LogFile])
async def list_log_files() -> List[LogFile]:
    """List all available log files"""
    try:
        log_dir = Path("/data/logs")
        if not log_dir.exists():
            return []
        
        files = []
        for file_path in log_dir.glob("*.log*"):
            if file_path.is_file():
                stat = file_path.stat()
                
                # Count lines (efficient for reasonable file sizes)
                line_count = 0
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        line_count = sum(1 for _ in f)
                except:
                    line_count = 0
                
                files.append(LogFile(
                    name=file_path.name,
                    path=str(file_path),
                    size=stat.st_size,
                    modified=datetime.fromtimestamp(stat.st_mtime),
                    lines=line_count
                ))
        
        # Sort by modified time, newest first
        files.sort(key=lambda x: x.modified, reverse=True)
        return files
        
    except Exception as e:
        logger.error(f"Failed to list log files: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/read", response_model=LogsResponse)
async def read_log_file(
    file: str = Query(..., description="Log file name"),
    level: Optional[str] = Query(None, description="Filter by log level"),
    search: Optional[str] = Query(None, description="Search text"),
    limit: int = Query(1000, description="Maximum entries to return"),
    offset: int = Query(0, description="Offset for pagination")
) -> LogsResponse:
    """Read and parse a log file with filtering"""
    try:
        log_path = Path("/data/logs") / file
        
        # Security check - ensure we're only reading from logs directory
        if not log_path.exists() or not str(log_path).startswith("/data/logs"):
            raise HTTPException(status_code=404, detail="Log file not found")
        
        entries = []
        total_lines = 0
        
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f):
                total_lines += 1
                line = line.strip()
                if not line:
                    continue
                
                # Try to parse JSON log format
                entry = None
                try:
                    log_data = json.loads(line)
                    entry = LogEntry(
                        timestamp=log_data.get('timestamp', log_data.get('time')),
                        level=log_data.get('level', 'INFO').upper(),
                        module=log_data.get('module', log_data.get('name')),
                        message=log_data.get('message', log_data.get('msg', '')),
                        raw=line
                    )
                except json.JSONDecodeError:
                    # Fall back to text parsing
                    entry = parse_text_log(line)
                
                if entry:
                    # Apply filters
                    if level and entry.level.upper() != level.upper():
                        continue
                    if search and search.lower() not in entry.message.lower():
                        continue
                    
                    entries.append(entry)
        
        # Reverse entries to show newest first
        entries.reverse()
        
        # Apply pagination
        filtered_count = len(entries)
        entries = entries[offset:offset + limit]
        
        # Get file list for response
        files = await list_log_files()
        
        return LogsResponse(
            files=files,
            entries=entries,
            total=total_lines,
            filtered=filtered_count
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to read log file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def parse_text_log(line: str) -> LogEntry:
    """Parse a text log line"""
    # Common log patterns
    # Pattern: 2024-01-15 10:30:45,330 - module - INFO - function:line - message
    # Pattern: 2024-01-15 10:30:45 - INFO - module - message
    # Pattern: [INFO] message
    # Pattern: ERROR: message
    
    level = "INFO"
    message = line
    timestamp = None
    module = None
    
    # Try to extract timestamp (ISO format with optional milliseconds)
    if line.startswith("20"):  # Likely a timestamp
        parts = line.split(" - ", 4)
        if len(parts) >= 3:
            # Extract timestamp (replace comma with dot for ISO format)
            timestamp = parts[0].replace(',', '.')
            # Try to identify the level and module
            # Format could be: timestamp - module - LEVEL - location - message
            # or: timestamp - LEVEL - module - message
            if len(parts) >= 4:
                # Check if second part is a module name or level
                if parts[1].upper() in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
                    level = parts[1].upper()
                    module = parts[2] if len(parts) > 2 else None
                    message = parts[3] if len(parts) > 3 else parts[-1]
                else:
                    module = parts[1]
                    level = parts[2].upper() if len(parts) > 2 else "INFO"
                    # Skip the function:line part if present
                    message = parts[4] if len(parts) > 4 else parts[3] if len(parts) > 3 else parts[-1]
    
    # Try to extract level from brackets [LEVEL]
    elif line.startswith("["):
        end_bracket = line.find("]")
        if end_bracket > 0:
            level = line[1:end_bracket].upper()
            message = line[end_bracket + 1:].strip()
    
    # Try to extract level from prefix LEVEL:
    else:
        for log_level in ["ERROR", "WARNING", "WARN", "INFO", "DEBUG", "CRITICAL"]:
            if line.upper().startswith(log_level + ":"):
                level = log_level if log_level != "WARN" else "WARNING"
                message = line[len(log_level) + 1:].strip()
                break
    
    return LogEntry(
        timestamp=timestamp,
        level=level,
        module=module,
        message=message,
        raw=line
    )


@router.delete("/clear")
async def clear_log_file(file: str = Query(..., description="Log file name")) -> Dict[str, Any]:
    """Clear a log file"""
    try:
        log_path = Path("/data/logs") / file
        
        # Security check
        if not str(log_path).startswith("/data/logs"):
            raise HTTPException(status_code=403, detail="Invalid log file path")
        
        if not log_path.exists():
            raise HTTPException(status_code=404, detail="Log file not found")
        
        # Don't delete, just truncate
        with open(log_path, 'w') as f:
            f.write("")
        
        return {"success": True, "message": f"Cleared {file}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to clear log file: {e}")
        raise HTTPException(status_code=500, detail=str(e))