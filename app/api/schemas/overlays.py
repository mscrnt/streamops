from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum


class OverlayStatus(str, Enum):
    """Overlay status enumeration"""
    active = "active"
    inactive = "inactive"
    scheduled = "scheduled"
    expired = "expired"
    error = "error"


class OverlayType(str, Enum):
    """Overlay type enumeration"""
    text = "text"
    image = "image"
    video = "video"
    html = "html"
    countdown = "countdown"
    progress_bar = "progress_bar"
    recent_follower = "recent_follower"
    scene_info = "scene_info"
    chat_display = "chat_display"


class OverlayPosition(BaseModel):
    """Overlay position and size"""
    x: int = Field(..., description="X coordinate (pixels)")
    y: int = Field(..., description="Y coordinate (pixels)")
    width: Optional[int] = Field(None, description="Width (pixels)")
    height: Optional[int] = Field(None, description="Height (pixels)")
    z_index: int = Field(1, description="Z-index for layering")


class OverlayStyle(BaseModel):
    """Overlay styling options"""
    background_color: Optional[str] = Field(None, description="Background color (CSS)")
    text_color: Optional[str] = Field(None, description="Text color (CSS)")
    font_family: Optional[str] = Field(None, description="Font family")
    font_size: Optional[str] = Field(None, description="Font size")
    opacity: Optional[float] = Field(1.0, ge=0, le=1, description="Opacity (0-1)")
    border_radius: Optional[str] = Field(None, description="Border radius")
    padding: Optional[str] = Field(None, description="Padding")
    margin: Optional[str] = Field(None, description="Margin")
    animation: Optional[str] = Field(None, description="CSS animation")


class OverlayContent(BaseModel):
    """Overlay content configuration"""
    text: Optional[str] = Field(None, description="Text content")
    image_url: Optional[str] = Field(None, description="Image URL")
    video_url: Optional[str] = Field(None, description="Video URL")
    html: Optional[str] = Field(None, description="HTML content")
    template_variables: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Template variables")


class OverlaySchedule(BaseModel):
    """Overlay scheduling configuration"""
    start_time: Optional[datetime] = Field(None, description="Start time (UTC)")
    end_time: Optional[datetime] = Field(None, description="End time (UTC)")
    duration_seconds: Optional[int] = Field(None, description="Duration in seconds")
    repeat_interval: Optional[int] = Field(None, description="Repeat interval in seconds")
    max_repeats: Optional[int] = Field(None, description="Maximum number of repeats")


class OverlayCreate(BaseModel):
    """Create overlay request"""
    name: str = Field(..., description="Overlay name")
    overlay_type: OverlayType = Field(..., description="Type of overlay")
    description: Optional[str] = Field(None, description="Overlay description")
    position: OverlayPosition = Field(..., description="Position and size")
    style: Optional[OverlayStyle] = Field(None, description="Styling options")
    content: OverlayContent = Field(..., description="Content configuration")
    schedule: Optional[OverlaySchedule] = Field(None, description="Scheduling configuration")
    enabled: bool = Field(True, description="Whether overlay is enabled")
    tags: Optional[List[str]] = Field(default_factory=list, description="Overlay tags")
    scene_filter: Optional[List[str]] = Field(None, description="OBS scenes to show on")


class OverlayUpdate(BaseModel):
    """Update overlay request"""
    name: Optional[str] = Field(None, description="Overlay name")
    description: Optional[str] = Field(None, description="Overlay description")
    position: Optional[OverlayPosition] = Field(None, description="Position and size")
    style: Optional[OverlayStyle] = Field(None, description="Styling options")
    content: Optional[OverlayContent] = Field(None, description="Content configuration")
    schedule: Optional[OverlaySchedule] = Field(None, description="Scheduling configuration")
    enabled: Optional[bool] = Field(None, description="Whether overlay is enabled")
    tags: Optional[List[str]] = Field(None, description="Overlay tags")
    scene_filter: Optional[List[str]] = Field(None, description="OBS scenes to show on")


class OverlayResponse(BaseModel):
    """Overlay response"""
    id: str
    name: str
    overlay_type: OverlayType
    description: Optional[str] = None
    position: OverlayPosition
    style: OverlayStyle
    content: OverlayContent
    schedule: Optional[OverlaySchedule] = None
    enabled: bool
    status: OverlayStatus
    tags: List[str]
    scene_filter: Optional[List[str]] = None
    views: int = 0
    last_shown: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class OverlayListResponse(BaseModel):
    """Overlay list response"""
    overlays: List[OverlayResponse]
    total: int
    page: int
    per_page: int


class OverlaySearchQuery(BaseModel):
    """Overlay search query"""
    name: Optional[str] = Field(None, description="Filter by name (partial match)")
    overlay_type: Optional[OverlayType] = Field(None, description="Filter by overlay type")
    status: Optional[OverlayStatus] = Field(None, description="Filter by status")
    enabled: Optional[bool] = Field(None, description="Filter by enabled status")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    scene: Optional[str] = Field(None, description="Filter by scene")
    created_after: Optional[datetime] = Field(None, description="Created after timestamp")
    created_before: Optional[datetime] = Field(None, description="Created before timestamp")


class OverlayPreview(BaseModel):
    """Overlay preview response"""
    html: str = Field(..., description="Rendered HTML for preview")
    css: str = Field(..., description="Compiled CSS styles")
    js: Optional[str] = Field(None, description="JavaScript for interactivity")


class OverlayManifest(BaseModel):
    """Overlay manifest for browser source"""
    overlays: List[OverlayResponse]
    scene: Optional[str] = None
    last_updated: datetime
    websocket_url: str