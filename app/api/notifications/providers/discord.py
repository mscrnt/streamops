"""Discord notification provider"""

import aiohttp
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from .base import BaseProvider, NotificationMessage, SendResult, NotificationChannel, NotificationPriority

logger = logging.getLogger(__name__)


class DiscordProvider(BaseProvider):
    """Discord webhook notification provider"""
    
    COLORS = {
        NotificationPriority.LOW: 0x95a5a6,      # Gray
        NotificationPriority.NORMAL: 0x3498db,   # Blue
        NotificationPriority.HIGH: 0xf39c12,     # Orange
        NotificationPriority.URGENT: 0xe74c3c,   # Red
    }
    
    def validate_config(self) -> tuple[bool, Optional[str]]:
        """Validate Discord configuration"""
        if not self.config.get('webhook_url'):
            return False, "Discord webhook URL is required"
        
        webhook_url = self.config['webhook_url']
        if not webhook_url.startswith('https://discord.com/api/webhooks/'):
            return False, "Invalid Discord webhook URL format"
        
        return True, None
    
    async def send(self, message: NotificationMessage) -> SendResult:
        """Send notification to Discord"""
        if not self.enabled:
            return SendResult(
                success=False,
                channel=NotificationChannel.DISCORD,
                error="Discord notifications are disabled"
            )
        
        try:
            payload = self.format_message(message)
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.config['webhook_url'],
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 204:
                        return SendResult(
                            success=True,
                            channel=NotificationChannel.DISCORD,
                            provider_message_id=None  # Discord webhooks don't return message IDs
                        )
                    else:
                        error = await response.text()
                        logger.error(f"Discord webhook failed: {response.status} - {error}")
                        return SendResult(
                            success=False,
                            channel=NotificationChannel.DISCORD,
                            error=f"Discord API error: {response.status}"
                        )
                        
        except aiohttp.ClientTimeout:
            return SendResult(
                success=False,
                channel=NotificationChannel.DISCORD,
                error="Discord webhook timeout"
            )
        except Exception as e:
            logger.error(f"Discord send failed: {e}")
            return SendResult(
                success=False,
                channel=NotificationChannel.DISCORD,
                error=str(e)
            )
    
    def format_message(self, message: NotificationMessage) -> Dict[str, Any]:
        """Format message as Discord embed"""
        embed = {
            "title": message.title or message.event_type.replace('.', ' ').title(),
            "description": message.content[:2048],  # Discord limit
            "color": self.COLORS.get(message.priority, self.COLORS[NotificationPriority.NORMAL]),
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {
                "text": "StreamOps"
            }
        }
        
        # Add fields from metadata
        if message.metadata:
            embed["fields"] = []
            for key, value in list(message.metadata.items())[:25]:  # Discord limit
                if value is not None:
                    embed["fields"].append({
                        "name": key.replace('_', ' ').title(),
                        "value": str(value)[:1024],  # Discord limit
                        "inline": True
                    })
        
        # Add thumbnail if provided
        if message.attachments and 'thumbnail' in message.attachments[0]:
            embed["thumbnail"] = {"url": message.attachments[0]['thumbnail']}
        
        # Username override if configured
        payload = {"embeds": [embed]}
        if self.config.get('username'):
            payload["username"] = self.config['username']
        if self.config.get('avatar_url'):
            payload["avatar_url"] = self.config['avatar_url']
        
        return payload