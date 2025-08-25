from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum


class RuleStatus(str, Enum):
    """Rule status enumeration"""
    active = "active"
    inactive = "inactive"
    paused = "paused"
    error = "error"


class RuleConditionOperator(str, Enum):
    """Rule condition operators"""
    equals = "equals"
    not_equals = "not_equals"
    contains = "contains"
    not_contains = "not_contains"
    starts_with = "starts_with"
    ends_with = "ends_with"
    greater_than = "greater_than"
    less_than = "less_than"
    regex_match = "regex_match"
    file_exists = "file_exists"
    has_tag = "has_tag"


class RuleCondition(BaseModel):
    """Rule condition definition"""
    field: str = Field(..., description="Field to check")
    operator: RuleConditionOperator = Field(..., description="Comparison operator")
    value: Union[str, int, float, bool] = Field(..., description="Value to compare against")


class RuleAction(BaseModel):
    """Rule action definition"""
    action_type: str = Field(..., description="Type of action to perform")
    params: Dict[str, Any] = Field(default_factory=dict, description="Action parameters")
    
    @validator('action_type')
    def validate_action_type(cls, v):
        allowed_actions = [
            'ffmpeg_remux', 'move', 'copy', 'index_asset', 'thumbs', 
            'proxy', 'transcode_preset', 'tag', 'overlay_update'
        ]
        if v not in allowed_actions:
            raise ValueError(f"Invalid action type. Must be one of: {allowed_actions}")
        return v


class RuleGuardrail(BaseModel):
    """Rule guardrail definition"""
    guardrail_type: str = Field(..., description="Type of guardrail")
    threshold: Union[int, float] = Field(..., description="Threshold value")
    
    @validator('guardrail_type')
    def validate_guardrail_type(cls, v):
        allowed_guardrails = [
            'pause_if_recording', 'pause_if_gpu_pct_above', 'pause_if_cpu_pct_above'
        ]
        if v not in allowed_guardrails:
            raise ValueError(f"Invalid guardrail type. Must be one of: {allowed_guardrails}")
        return v


class RuleCreate(BaseModel):
    """Create rule request"""
    name: str = Field(..., description="Rule name")
    description: Optional[str] = Field(None, description="Rule description")
    priority: int = Field(100, description="Rule priority (lower number = higher priority)")
    conditions: List[RuleCondition] = Field(..., description="Rule conditions (AND logic)")
    actions: List[RuleAction] = Field(..., description="Actions to perform")
    guardrails: Optional[List[RuleGuardrail]] = Field(default_factory=list, description="Safety guardrails")
    enabled: bool = Field(True, description="Whether rule is enabled")
    tags: Optional[List[str]] = Field(default_factory=list, description="Rule tags")


class RuleUpdate(BaseModel):
    """Update rule request"""
    name: Optional[str] = Field(None, description="Rule name")
    description: Optional[str] = Field(None, description="Rule description")
    priority: Optional[int] = Field(None, description="Rule priority")
    conditions: Optional[List[RuleCondition]] = Field(None, description="Rule conditions")
    actions: Optional[List[RuleAction]] = Field(None, description="Actions to perform")
    guardrails: Optional[List[RuleGuardrail]] = Field(None, description="Safety guardrails")
    enabled: Optional[bool] = Field(None, description="Whether rule is enabled")
    tags: Optional[List[str]] = Field(None, description="Rule tags")


class RuleResponse(BaseModel):
    """Rule response"""
    id: str
    name: str
    description: Optional[str] = None
    priority: int
    conditions: List[RuleCondition]
    actions: List[RuleAction]
    guardrails: List[RuleGuardrail]
    enabled: bool
    status: RuleStatus
    tags: List[str]
    executions: int = 0
    last_executed: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class RuleListResponse(BaseModel):
    """Rule list response"""
    rules: List[RuleResponse]
    total: int
    page: int
    per_page: int


class RuleSearchQuery(BaseModel):
    """Rule search query"""
    name: Optional[str] = Field(None, description="Filter by name (partial match)")
    status: Optional[RuleStatus] = Field(None, description="Filter by status")
    enabled: Optional[bool] = Field(None, description="Filter by enabled status")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    created_after: Optional[datetime] = Field(None, description="Created after timestamp")
    created_before: Optional[datetime] = Field(None, description="Created before timestamp")


class RuleExecution(BaseModel):
    """Rule execution result"""
    rule_id: str
    asset_id: Optional[str] = None
    session_id: Optional[str] = None
    success: bool
    actions_performed: List[str]
    error_message: Optional[str] = None
    execution_time: float
    executed_at: datetime


class RuleExecutionHistory(BaseModel):
    """Rule execution history"""
    executions: List[RuleExecution]
    total: int
    page: int
    per_page: int


class RuleTestRequest(BaseModel):
    """Test rule request"""
    asset_id: Optional[str] = Field(None, description="Asset ID to test against")
    test_data: Optional[Dict[str, Any]] = Field(None, description="Mock data for testing")
    dry_run: bool = Field(True, description="Whether to perform a dry run")