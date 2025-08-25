from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class JobStatus(str, Enum):
    """Job status enumeration"""
    pending = "pending"
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"
    retrying = "retrying"


class JobPriority(str, Enum):
    """Job priority levels"""
    low = "low"
    normal = "normal"
    high = "high"
    critical = "critical"


class JobType(str, Enum):
    """Job type enumeration"""
    ffmpeg_remux = "ffmpeg_remux"
    ffmpeg_transcode = "ffmpeg_transcode"
    thumbnail_generation = "thumbnail_generation"
    scene_detection = "scene_detection"
    asset_indexing = "asset_indexing"
    file_move = "file_move"
    file_copy = "file_copy"
    overlay_update = "overlay_update"
    proxy_creation = "proxy_creation"
    cleanup = "cleanup"


class JobCreate(BaseModel):
    """Create job request"""
    job_type: JobType = Field(..., description="Type of job to create")
    priority: JobPriority = Field(JobPriority.normal, description="Job priority")
    params: Dict[str, Any] = Field(..., description="Job parameters")
    asset_id: Optional[str] = Field(None, description="Associated asset ID")
    session_id: Optional[str] = Field(None, description="Associated session ID")
    max_retries: int = Field(3, description="Maximum retry attempts")
    timeout_seconds: Optional[int] = Field(None, description="Job timeout in seconds")


class JobUpdate(BaseModel):
    """Update job request"""
    status: Optional[JobStatus] = Field(None, description="Update job status")
    priority: Optional[JobPriority] = Field(None, description="Update job priority")
    progress: Optional[float] = Field(None, ge=0, le=100, description="Progress percentage")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    result: Optional[Dict[str, Any]] = Field(None, description="Job result data")


class JobResponse(BaseModel):
    """Job response"""
    id: str
    job_type: JobType
    status: JobStatus
    priority: JobPriority
    params: Dict[str, Any]
    asset_id: Optional[str] = None
    session_id: Optional[str] = None
    progress: float = 0.0
    error_message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: Optional[int] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class JobListResponse(BaseModel):
    """Job list response"""
    jobs: List[JobResponse]
    total: int
    page: int
    per_page: int


class JobSearchQuery(BaseModel):
    """Job search query"""
    status: Optional[JobStatus] = Field(None, description="Filter by status")
    job_type: Optional[JobType] = Field(None, description="Filter by job type")
    priority: Optional[JobPriority] = Field(None, description="Filter by priority")
    asset_id: Optional[str] = Field(None, description="Filter by asset ID")
    session_id: Optional[str] = Field(None, description="Filter by session ID")
    created_after: Optional[datetime] = Field(None, description="Created after timestamp")
    created_before: Optional[datetime] = Field(None, description="Created before timestamp")


class JobStats(BaseModel):
    """Job queue statistics"""
    total_jobs: int
    pending: int
    queued: int
    running: int
    completed: int
    failed: int
    cancelled: int
    retrying: int
    
    
class JobCancel(BaseModel):
    """Cancel job request"""
    reason: Optional[str] = Field(None, description="Cancellation reason")