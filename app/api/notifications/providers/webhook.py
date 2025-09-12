"""Generic webhook notification provider"""

import aiohttp
import logging
import hashlib
import hmac
import json
from typing import Dict, Any, Optional
from datetime import datetime

from .base import BaseProvider, NotificationMessage, SendResult, NotificationChannel

logger = logging.getLogger(__name__)


class WebhookProvider(BaseProvider):
    """Generic webhook notification provider"""
    
    def validate_config(self) -> tuple[bool, Optional[str]]:
        """Validate webhook configuration"""
        if not self.config.get('endpoints'):
            return False, "At least one webhook endpoint is required"
        
        for endpoint in self.config['endpoints']:
            if not endpoint.get('url'):
                return False, "Webhook URL is required for each endpoint"
            
            url = endpoint['url']
            if not url.startswith(('http://', 'https://')):
                return False, f"Invalid webhook URL: {url}"
        
        return True, None
    
    async def send(self, message: NotificationMessage) -> SendResult:
        """Send notification to all configured webhooks"""
        if not self.enabled:
            return SendResult(
                success=False,
                channel=NotificationChannel.WEBHOOK,
                error="Webhook notifications are disabled"
            )
        
        results = []
        for endpoint in self.config.get('endpoints', []):
            result = await self._send_to_endpoint(message, endpoint)
            results.append(result)
        
        # Return success if at least one webhook succeeded
        successes = [r for r in results if r.success]
        if successes:
            return successes[0]  # Return first successful result
        elif results:
            return results[0]  # Return first error if all failed
        else:
            return SendResult(
                success=False,
                channel=NotificationChannel.WEBHOOK,
                error="No webhook endpoints configured"
            )
    
    async def _send_to_endpoint(self, message: NotificationMessage, endpoint: Dict[str, Any]) -> SendResult:
        """Send notification to a single webhook endpoint"""
        try:
            url = endpoint['url']
            payload = self.format_message(message)
            
            # Add endpoint-specific fields if configured
            if endpoint.get('custom_fields'):
                payload.update(endpoint['custom_fields'])
            
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'StreamOps/1.0'
            }
            
            # Add HMAC signature if secret is configured
            if endpoint.get('secret'):
                signature = self._generate_signature(payload, endpoint['secret'])
                headers['X-StreamOps-Signature'] = signature
            
            # Add custom headers if configured
            if endpoint.get('headers'):
                headers.update(endpoint['headers'])
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if 200 <= response.status < 300:
                        return SendResult(
                            success=True,
                            channel=NotificationChannel.WEBHOOK,
                            provider_message_id=endpoint.get('name', url)
                        )
                    else:
                        error = await response.text()
                        logger.error(f"Webhook failed for {url}: {response.status} - {error}")
                        return SendResult(
                            success=False,
                            channel=NotificationChannel.WEBHOOK,
                            error=f"Webhook error ({response.status}): {error[:100]}"
                        )
                        
        except aiohttp.ClientTimeout:
            return SendResult(
                success=False,
                channel=NotificationChannel.WEBHOOK,
                error=f"Webhook timeout: {endpoint.get('url')}"
            )
        except Exception as e:
            logger.error(f"Webhook send failed: {e}")
            return SendResult(
                success=False,
                channel=NotificationChannel.WEBHOOK,
                error=str(e)
            )
    
    def format_message(self, message: NotificationMessage) -> Dict[str, Any]:
        """Format message as webhook payload"""
        payload = {
            "event": message.event_type,
            "priority": message.priority,
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "title": message.title,
                "content": message.content,
                "metadata": message.metadata
            }
        }
        
        # Add attachments if present
        if message.attachments:
            payload["data"]["attachments"] = message.attachments
        
        # Add idempotency key for deduplication
        payload["idempotency_key"] = message.get_idempotency_key()
        
        return payload
    
    def _generate_signature(self, payload: Dict[str, Any], secret: str) -> str:
        """Generate HMAC-SHA256 signature for webhook payload"""
        payload_json = json.dumps(payload, separators=(',', ':'), sort_keys=True)
        signature = hmac.new(
            secret.encode('utf-8'),
            payload_json.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return f"sha256={signature}"