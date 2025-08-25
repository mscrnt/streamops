from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from pathlib import Path


class DriveStatus(str, Enum):
    """Drive status enumeration"""
    active = "active"
    inactive = "inactive"
    error = "error"
    full = "full"
    disconnected = "disconnected"


class WatcherStatus(str, Enum):
    """Watcher status enumeration"""
    running = "running"
    stopped = "stopped"
    error = "error"
    paused = "paused"


class DriveType(str, Enum):
    """Drive type enumeration"""
    local = "local"
    network = "network"
    cloud = "cloud"
    removable = "removable"


class DriveInfo(BaseModel):
    """Drive information"""
    path: str = Field(..., description="Drive mount path")
    label: Optional[str] = Field(None, description="Drive label")
    drive_type: DriveType = Field(..., description="Type of drive")
    total_space: Optional[int] = Field(None, description="Total space in bytes")
    free_space: Optional[int] = Field(None, description="Free space in bytes")
    used_space: Optional[int] = Field(None, description="Used space in bytes")
    filesystem: Optional[str] = Field(None, description="Filesystem type")
    
    @validator('path')
    def validate_path(cls, v):
        if not Path(v).is_absolute():
            raise ValueError('Drive path must be absolute')
        return v


class WatcherConfig(BaseModel):
    """Watcher configuration"""
    recursive: bool = Field(True, description="Watch subdirectories recursively")
    file_patterns: List[str] = Field(default_factory=lambda: ["*.mp4", "*.mov", "*.mkv", "*.avi"], description="File patterns to watch")
    ignore_patterns: Optional[List[str]] = Field(default_factory=lambda: ["*.tmp", "*.part"], description="Patterns to ignore")
    min_file_size: int = Field(1024, description="Minimum file size in bytes")
    stable_time: int = Field(5, description="Seconds to wait for file stability")
    batch_size: int = Field(10, description="Maximum files to process in batch")
    poll_interval: int = Field(5, description="Polling interval in seconds")


class DriveCreate(BaseModel):
    """Create drive watch request"""
    path: str = Field(..., description="Path to watch")
    label: Optional[str] = Field(None, description="Drive label")
    drive_type: DriveType = Field(DriveType.local, description="Type of drive")
    enabled: bool = Field(True, description="Whether watching is enabled")
    config: Optional[WatcherConfig] = Field(None, description="Watcher configuration")
    tags: Optional[List[str]] = Field(default_factory=list, description="Drive tags")


class DriveUpdate(BaseModel):
    """Update drive watch request"""
    label: Optional[str] = Field(None, description="Drive label")
    enabled: Optional[bool] = Field(None, description="Whether watching is enabled")
    config: Optional[WatcherConfig] = Field(None, description="Watcher configuration")
    tags: Optional[List[str]] = Field(None, description="Drive tags")


class DriveResponse(BaseModel):
    """Drive response"""
    id: str
    path: str
    label: Optional[str] = None
    drive_type: DriveType
    status: DriveStatus
    enabled: bool
    config: WatcherConfig
    tags: List[str]
    info: Optional[DriveInfo] = None
    watcher_status: WatcherStatus
    files_watched: int = 0
    files_processed: int = 0
    last_activity: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class DriveListResponse(BaseModel):
    """Drive list response"""
    drives: List[DriveResponse]
    total: int
    page: int
    per_page: int


class DriveSearchQuery(BaseModel):
    """Drive search query"""
    path: Optional[str] = Field(None, description="Filter by path (partial match)")
    status: Optional[DriveStatus] = Field(None, description="Filter by status")
    drive_type: Optional[DriveType] = Field(None, description="Filter by drive type")
    enabled: Optional[bool] = Field(None, description="Filter by enabled status")
    watcher_status: Optional[WatcherStatus] = Field(None, description="Filter by watcher status")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")


class DriveStats(BaseModel):
    """Drive statistics"""
    total_drives: int
    active_drives: int
    total_space: int
    free_space: int
    used_space: int
    files_watched: int
    files_processed_today: int
    watchers_running: int


class DriveActivity(BaseModel):
    """Drive activity log entry"""
    drive_id: str
    event_type: str
    file_path: str
    file_size: Optional[int] = None
    timestamp: datetime
    processed: bool = False
    error_message: Optional[str] = None


class DriveActivityResponse(BaseModel):
    """Drive activity response"""
    activities: List[DriveActivity]
    total: int
    page: int
    per_page: int


class DriveTest(BaseModel):
    """Test drive access request"""
    path: str = Field(..., description="Path to test")
    test_write: bool = Field(False, description="Test write permissions")


class DriveTestResult(BaseModel):
    """Drive test result"""
    path: str
    accessible: bool
    readable: bool
    writable: bool
    exists: bool
    is_directory: bool
    permissions: Optional[str] = None
    error_message: Optional[str] = None
    space_info: Optional[DriveInfo] = None