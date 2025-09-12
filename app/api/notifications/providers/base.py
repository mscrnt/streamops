"""Base provider interface for notification system"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from enum import Enum
from pydantic import BaseModel
from datetime import datetime
import hashlib
import json


class NotificationChannel(str, Enum):
    """Supported notification channels"""
    DISCORD = "discord"
    TWITTER = "twitter"
    EMAIL = "email"
    WEBHOOK = "webhook"


class NotificationPriority(str, Enum):
    """Notification priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationEvent(str, Enum):
    """Notification event types"""
    # Job events
    JOB_STARTED = "job.started"
    JOB_COMPLETED = "job.completed"
    JOB_FAILED = "job.failed"
    
    # Recording events
    RECORDING_CREATED = "recording.created"
    RECORDING_STARTED = "recording.started"
    RECORDING_STOPPED = "recording.stopped"
    RECORDING_PROCESSED = "recording.processed"
    RECORDING_FAILED = "recording.failed"
    
    # Streaming events
    STREAM_STARTED = "stream.started"
    STREAM_STOPPED = "stream.stopped"
    STREAM_HEALTH_WARNING = "stream.health_warning"
    STREAM_HEALTH_CRITICAL = "stream.health_critical"
    STREAM_DISCONNECTED = "stream.disconnected"
    STREAM_RECONNECTED = "stream.reconnected"
    
    # OBS events
    OBS_CONNECTED = "obs.connected"
    OBS_DISCONNECTED = "obs.disconnected"
    OBS_SCENE_CHANGED = "obs.scene_changed"
    OBS_RECORDING_STARTED = "obs.recording_started"
    OBS_RECORDING_STOPPED = "obs.recording_stopped"
    OBS_STREAMING_STARTED = "obs.streaming_started"
    OBS_STREAMING_STOPPED = "obs.streaming_stopped"
    
    # System events
    SYSTEM_ALERT = "system.alert"
    STORAGE_THRESHOLD = "storage.threshold"
    DRIVE_OFFLINE = "drive.offline"
    
    # Custom events
    CUSTOM = "custom"


class SendResult(BaseModel):
    """Result of a send operation"""
    success: bool
    channel: NotificationChannel
    provider_message_id: Optional[str] = None
    error: Optional[str] = None
    timestamp: datetime = None
    
    def __init__(self, **data):
        if 'timestamp' not in data:
            data['timestamp'] = datetime.utcnow()
        super().__init__(**data)


class NotificationMessage(BaseModel):
    """Unified notification message"""
    event_type: str
    title: Optional[str] = None
    content: str
    priority: NotificationPriority = NotificationPriority.NORMAL
    metadata: Dict[str, Any] = {}
    attachments: List[Dict[str, Any]] = []
    
    def get_idempotency_key(self) -> str:
        """Generate idempotency key for deduplication"""
        data = f"{self.event_type}:{self.content}:{json.dumps(self.metadata, sort_keys=True)}"
        return hashlib.sha256(data.encode()).hexdigest()


class BaseProvider(ABC):
    """Base class for notification providers"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get('enabled', False)
        self.rate_limit = config.get('rate_per_min', 60)
    
    @abstractmethod
    def validate_config(self) -> tuple[bool, Optional[str]]:
        """
        Validate provider configuration
        Returns (is_valid, error_message)
        """
        pass
    
    @abstractmethod
    async def send(self, message: NotificationMessage) -> SendResult:
        """Send a notification through this provider"""
        pass
    
    @abstractmethod
    def format_message(self, message: NotificationMessage) -> Dict[str, Any]:
        """Format message for this provider's API"""
        pass
    
    def get_rate_limit_key(self) -> str:
        """Get rate limiting key for this provider"""
        return f"notif:{self.__class__.__name__.lower()}:{datetime.utcnow().minute}"
    
    def is_enabled(self) -> bool:
        """Check if provider is enabled"""
        return self.enabled