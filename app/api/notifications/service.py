"""Main notification service orchestrator"""

import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import asyncio

from .providers.base import (
    NotificationMessage, NotificationChannel, NotificationEvent,
    NotificationPriority, SendResult
)
from .providers.discord import DiscordProvider
from .providers.email import EmailProvider
from .providers.twitter import TwitterProvider
from .providers.webhook import WebhookProvider

logger = logging.getLogger(__name__)


class NotificationService:
    """Central notification service for orchestrating notifications"""
    
    def __init__(self):
        self.providers: Dict[NotificationChannel, Any] = {}
        self.enabled = False
        self.rules = {}
        self.templates = {}
        self._rate_limiters = {}
        
    async def initialize(self, config: Dict[str, Any]):
        """Initialize notification service with configuration"""
        self.enabled = config.get('enabled', False)
        
        if not self.enabled:
            logger.info("Notification service is disabled")
            return
        
        # Initialize providers
        if 'discord' in config:
            self.providers[NotificationChannel.DISCORD] = DiscordProvider(config['discord'])
        
        if 'email' in config:
            self.providers[NotificationChannel.EMAIL] = EmailProvider(config['email'])
        
        if 'twitter' in config:
            self.providers[NotificationChannel.TWITTER] = TwitterProvider(config['twitter'])
        
        if 'webhook' in config:
            self.providers[NotificationChannel.WEBHOOK] = WebhookProvider(config['webhook'])
        
        # Load rules
        self.rules = config.get('rules', {})
        
        # Load templates
        self.templates = config.get('templates', {})
        
        # Validate all providers
        for channel, provider in self.providers.items():
            is_valid, error = provider.validate_config()
            if not is_valid:
                logger.error(f"Invalid config for {channel}: {error}")
                provider.enabled = False
        
        logger.info(f"Notification service initialized with {len(self.providers)} providers")
    
    async def send_event(
        self,
        event_type: str,
        data: Dict[str, Any],
        priority: NotificationPriority = NotificationPriority.NORMAL,
        channels: Optional[List[NotificationChannel]] = None
    ) -> List[SendResult]:
        """Send notification for an event"""
        if not self.enabled:
            return []
        
        # Determine channels from rules if not specified
        if channels is None:
            channels = self._get_channels_for_event(event_type)
        
        if not channels:
            logger.debug(f"No channels configured for event {event_type}")
            return []
        
        # Create notification message
        message = self._create_message(event_type, data, priority)
        
        # Check for duplicate (idempotency)
        if await self._is_duplicate(message):
            logger.debug(f"Skipping duplicate notification for {event_type}")
            return []
        
        # Send to all channels
        results = []
        for channel in channels:
            if channel in self.providers:
                provider = self.providers[channel]
                if provider.is_enabled():
                    # Check rate limit
                    if await self._check_rate_limit(channel):
                        result = await provider.send(message)
                        results.append(result)
                        await self._record_send(channel, message, result)
                    else:
                        logger.warning(f"Rate limit exceeded for {channel}")
                        results.append(SendResult(
                            success=False,
                            channel=channel,
                            error="Rate limit exceeded"
                        ))
        
        return results
    
    async def send_custom(
        self,
        title: str,
        content: str,
        channels: List[NotificationChannel],
        priority: NotificationPriority = NotificationPriority.NORMAL,
        metadata: Dict[str, Any] = None
    ) -> List[SendResult]:
        """Send custom notification"""
        if not self.enabled:
            return []
        
        message = NotificationMessage(
            event_type="custom",
            title=title,
            content=content,
            priority=priority,
            metadata=metadata or {}
        )
        
        results = []
        for channel in channels:
            if channel in self.providers:
                provider = self.providers[channel]
                if provider.is_enabled():
                    result = await provider.send(message)
                    results.append(result)
                    await self._record_send(channel, message, result)
        
        return results
    
    async def test_channel(self, channel: NotificationChannel) -> SendResult:
        """Test a specific notification channel"""
        if channel not in self.providers:
            return SendResult(
                success=False,
                channel=channel,
                error=f"Provider {channel} not configured"
            )
        
        provider = self.providers[channel]
        
        # Validate configuration first
        is_valid, error = provider.validate_config()
        if not is_valid:
            return SendResult(
                success=False,
                channel=channel,
                error=f"Invalid configuration: {error}"
            )
        
        # Send test message
        test_message = NotificationMessage(
            event_type="test",
            title="StreamOps Test Notification",
            content=f"This is a test notification from StreamOps sent at {datetime.utcnow().isoformat()}",
            priority=NotificationPriority.LOW,
            metadata={
                "test": True,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        return await provider.send(test_message)
    
    def _get_channels_for_event(self, event_type: str) -> List[NotificationChannel]:
        """Get notification channels for an event based on rules"""
        if event_type in self.rules:
            rule = self.rules[event_type]
            channels = rule.get('channels', [])
            # Convert string channel names to enum
            return [NotificationChannel(ch) for ch in channels if ch in [c.value for c in NotificationChannel]]
        return []
    
    def _create_message(
        self,
        event_type: str,
        data: Dict[str, Any],
        priority: NotificationPriority
    ) -> NotificationMessage:
        """Create notification message from event data"""
        # Check for template
        template_id = None
        if event_type in self.rules:
            template_id = self.rules[event_type].get('template_id')
        
        if template_id and template_id in self.templates:
            # Render template
            template = self.templates[template_id]
            title = self._render_template(template.get('title', ''), data)
            content = self._render_template(template.get('content', ''), data)
        else:
            # Default formatting
            title = event_type.replace('.', ' ').title()
            content = self._format_default_content(event_type, data)
        
        return NotificationMessage(
            event_type=event_type,
            title=title,
            content=content,
            priority=priority,
            metadata=data
        )
    
    def _render_template(self, template: str, data: Dict[str, Any]) -> str:
        """Render template with data (simple string formatting for now)"""
        try:
            return template.format(**data)
        except KeyError as e:
            logger.warning(f"Template rendering error: missing key {e}")
            return template
    
    def _format_default_content(self, event_type: str, data: Dict[str, Any]) -> str:
        """Format default content for events without templates"""
        # Job events
        if event_type == NotificationEvent.JOB_COMPLETED:
            return f"Job {data.get('job_type', 'unknown')} completed for {data.get('asset_name', 'unknown asset')}"
        elif event_type == NotificationEvent.JOB_FAILED:
            return f"Job {data.get('job_type', 'unknown')} failed: {data.get('error', 'Unknown error')}"
        
        # Recording events
        elif event_type == NotificationEvent.RECORDING_CREATED:
            return f"New recording: {data.get('filename', 'unknown')}"
        elif event_type == NotificationEvent.RECORDING_STARTED:
            return f"Recording started at {data.get('start_time', 'unknown time')}"
        elif event_type == NotificationEvent.RECORDING_STOPPED:
            duration = data.get('duration_sec', 0)
            duration_str = f"{int(duration // 60)}m {int(duration % 60)}s" if duration else "unknown duration"
            return f"Recording stopped. Duration: {duration_str}"
        elif event_type == NotificationEvent.RECORDING_PROCESSED:
            return f"Recording {data.get('filename', 'unknown')} has been processed"
        elif event_type == NotificationEvent.RECORDING_FAILED:
            return f"Recording failed: {data.get('error', 'Unknown error')}"
        
        # Streaming events
        elif event_type == NotificationEvent.STREAM_STARTED:
            return f"Stream started on {data.get('platform', 'unknown platform')}"
        elif event_type == NotificationEvent.STREAM_STOPPED:
            duration = data.get('duration_sec', 0)
            duration_str = f"{int(duration // 60)}m {int(duration % 60)}s" if duration else "unknown duration"
            return f"Stream ended. Duration: {duration_str}"
        elif event_type == NotificationEvent.STREAM_HEALTH_WARNING:
            return f"Stream health warning: {data.get('issue', 'Unknown issue')}"
        elif event_type == NotificationEvent.STREAM_HEALTH_CRITICAL:
            return f"Stream health critical: {data.get('issue', 'Connection lost or severe quality degradation')}"
        elif event_type == NotificationEvent.STREAM_DISCONNECTED:
            return f"Stream disconnected from {data.get('platform', 'unknown platform')}"
        elif event_type == NotificationEvent.STREAM_RECONNECTED:
            return f"Stream reconnected to {data.get('platform', 'unknown platform')}"
        
        # OBS events
        elif event_type == NotificationEvent.OBS_CONNECTED:
            return f"Connected to OBS at {data.get('url', 'unknown URL')}"
        elif event_type == NotificationEvent.OBS_DISCONNECTED:
            return f"Disconnected from OBS"
        elif event_type == NotificationEvent.OBS_SCENE_CHANGED:
            return f"Scene changed to: {data.get('scene', 'unknown scene')}"
        elif event_type == NotificationEvent.OBS_RECORDING_STARTED:
            return f"OBS recording started (Scene: {data.get('scene', 'unknown')})"
        elif event_type == NotificationEvent.OBS_RECORDING_STOPPED:
            duration = data.get('duration_sec', 0)
            duration_str = f"{int(duration // 3600)}h {int((duration % 3600) // 60)}m" if duration > 3600 else f"{int(duration // 60)}m {int(duration % 60)}s" if duration else "unknown duration"
            markers = data.get('has_markers', False)
            marker_text = " with markers" if markers else ""
            return f"OBS recording stopped. Duration: {duration_str}{marker_text}"
        elif event_type == NotificationEvent.OBS_STREAMING_STARTED:
            return f"OBS streaming started (Scene: {data.get('scene', 'unknown')})"
        elif event_type == NotificationEvent.OBS_STREAMING_STOPPED:
            duration = data.get('duration_sec', 0)
            duration_str = f"{int(duration // 3600)}h {int((duration % 3600) // 60)}m" if duration > 3600 else f"{int(duration // 60)}m {int(duration % 60)}s" if duration else "unknown duration"
            return f"OBS streaming stopped. Duration: {duration_str}"
        
        # System events
        elif event_type == NotificationEvent.STORAGE_THRESHOLD:
            return f"Storage warning: {data.get('drive', 'unknown')} at {data.get('usage_percent', 0)}% capacity"
        elif event_type == NotificationEvent.DRIVE_OFFLINE:
            return f"Drive offline: {data.get('drive', 'unknown drive')}"
        elif event_type == NotificationEvent.SYSTEM_ALERT:
            return f"System alert: {data.get('message', 'Unknown system issue')}"
        
        else:
            return json.dumps(data, indent=2)[:500]  # Fallback to JSON
    
    async def _is_duplicate(self, message: NotificationMessage) -> bool:
        """Check if message is a duplicate (implement deduplication logic)"""
        # TODO: Implement deduplication using cache or database
        # For now, always return False
        return False
    
    async def _check_rate_limit(self, channel: NotificationChannel) -> bool:
        """Check if channel is within rate limit"""
        # TODO: Implement rate limiting with Redis or in-memory cache
        # For now, always allow
        return True
    
    async def _record_send(
        self,
        channel: NotificationChannel,
        message: NotificationMessage,
        result: SendResult
    ):
        """Record notification send in audit log"""
        # TODO: Save to database for audit trail
        if result.success:
            logger.info(f"Notification sent via {channel} for {message.event_type}")
        else:
            logger.error(f"Notification failed via {channel}: {result.error}")


# Global notification service instance
notification_service = NotificationService()