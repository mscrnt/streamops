from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime


class ConfigKeyValue(BaseModel):
    """Configuration key-value pair"""
    key: str = Field(..., description="Configuration key")
    value: Any = Field(..., description="Configuration value")
    description: Optional[str] = Field(None, description="Description of the configuration")


class ConfigUpdate(BaseModel):
    """Configuration update request"""
    key: str = Field(..., description="Configuration key")
    value: Any = Field(..., description="New configuration value")


class ConfigResponse(BaseModel):
    """Configuration response"""
    key: str
    value: Any
    description: Optional[str] = None
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ConfigBulkUpdate(BaseModel):
    """Bulk configuration update"""
    configs: List[ConfigUpdate] = Field(..., description="List of configuration updates")


class ConfigListResponse(BaseModel):
    """Configuration list response"""
    configs: List[ConfigResponse]
    total: int