from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class AssetStatus(str, Enum):
    """Asset processing status"""
    pending = "pending"
    processing = "processing"
    ready = "ready"
    completed = "completed"
    error = "error"
    archived = "archived"


class AssetType(str, Enum):
    """Media asset type"""
    video = "video"
    audio = "audio"
    image = "image"
    other = "other"


class AssetMetadata(BaseModel):
    """Media asset metadata"""
    duration: Optional[float] = Field(None, description="Duration in seconds")
    width: Optional[int] = Field(None, description="Video width")
    height: Optional[int] = Field(None, description="Video height")
    fps: Optional[float] = Field(None, description="Frames per second")
    bitrate: Optional[int] = Field(None, description="Bitrate in bits per second")
    codec: Optional[str] = Field(None, description="Video/audio codec")
    container: Optional[str] = Field(None, description="Container format")
    size_bytes: Optional[int] = Field(None, description="File size in bytes")


class AssetCreate(BaseModel):
    """Create asset request"""
    filepath: str = Field(..., description="Full path to the media file")
    session_id: Optional[str] = Field(None, description="Associated session ID")
    tags: Optional[List[str]] = Field(default_factory=list, description="Asset tags")


class AssetUpdate(BaseModel):
    """Update asset request"""
    tags: Optional[List[str]] = Field(None, description="Asset tags")
    status: Optional[AssetStatus] = Field(None, description="Asset status")
    metadata: Optional[AssetMetadata] = Field(None, description="Asset metadata")


class AssetResponse(BaseModel):
    """Asset response"""
    id: str
    filepath: str  # Kept for backward compatibility
    abs_path: Optional[str] = None  # Original path where file was indexed
    current_path: Optional[str] = None  # Current location of file
    filename: str
    asset_type: AssetType
    status: AssetStatus
    session_id: Optional[str] = None
    tags: List[str]
    metadata: AssetMetadata
    indexed_at: Optional[datetime] = None  # When file was first indexed
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class AssetListResponse(BaseModel):
    """Asset list response"""
    assets: List[AssetResponse]
    total: int
    page: int
    per_page: int


class AssetSearchQuery(BaseModel):
    """Asset search query"""
    query: Optional[str] = Field(None, description="Full-text search query")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    status: Optional[AssetStatus] = Field(None, description="Filter by status")
    asset_type: Optional[AssetType] = Field(None, description="Filter by asset type")
    session_id: Optional[str] = Field(None, description="Filter by session")
    created_after: Optional[datetime] = Field(None, description="Created after timestamp")
    created_before: Optional[datetime] = Field(None, description="Created before timestamp")


