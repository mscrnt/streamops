"""Twitter/X notification provider"""

import aiohttp
import logging
import hashlib
import hmac
import time
import urllib.parse
import base64
import secrets
from typing import Dict, Any, Optional

from .base import BaseProvider, NotificationMessage, SendResult, NotificationChannel

logger = logging.getLogger(__name__)


class TwitterProvider(BaseProvider):
    """Twitter/X API v2 notification provider"""
    
    API_URL = "https://api.twitter.com/2/tweets"
    
    def validate_config(self) -> tuple[bool, Optional[str]]:
        """Validate Twitter configuration"""
        # For OAuth 1.0a
        if self.config.get('auth_type') == 'oauth1':
            required = ['api_key', 'api_secret', 'access_token', 'access_secret']
            for field in required:
                if not self.config.get(field):
                    return False, f"Twitter {field} is required for OAuth 1.0a"
        
        # For OAuth 2.0 Bearer Token
        elif self.config.get('auth_type') == 'bearer':
            if not self.config.get('bearer_token'):
                return False, "Twitter bearer_token is required for OAuth 2.0"
        
        else:
            return False, "Twitter auth_type must be 'oauth1' or 'bearer'"
        
        return True, None
    
    async def send(self, message: NotificationMessage) -> SendResult:
        """Send tweet to Twitter/X"""
        if not self.enabled:
            return SendResult(
                success=False,
                channel=NotificationChannel.TWITTER,
                error="Twitter notifications are disabled"
            )
        
        try:
            payload = self.format_message(message)
            headers = self._get_auth_headers(payload)
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.API_URL,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    data = await response.json()
                    
                    if response.status == 201:
                        tweet_id = data.get('data', {}).get('id')
                        return SendResult(
                            success=True,
                            channel=NotificationChannel.TWITTER,
                            provider_message_id=tweet_id
                        )
                    else:
                        error_msg = data.get('errors', [{}])[0].get('message', 'Unknown error')
                        logger.error(f"Twitter API failed: {response.status} - {error_msg}")
                        return SendResult(
                            success=False,
                            channel=NotificationChannel.TWITTER,
                            error=f"Twitter API error: {error_msg}"
                        )
                        
        except aiohttp.ClientTimeout:
            return SendResult(
                success=False,
                channel=NotificationChannel.TWITTER,
                error="Twitter API timeout"
            )
        except Exception as e:
            logger.error(f"Twitter send failed: {e}")
            return SendResult(
                success=False,
                channel=NotificationChannel.TWITTER,
                error=str(e)
            )
    
    def format_message(self, message: NotificationMessage) -> Dict[str, Any]:
        """Format message for Twitter API v2"""
        # Build tweet text
        text = ""
        
        if message.title:
            text = f"{message.title}\n\n"
        
        text += message.content
        
        # Add key metadata as hashtags or mentions
        if message.metadata:
            # Add important metadata
            for key in ['job_type', 'asset_name', 'status']:
                if key in message.metadata and message.metadata[key]:
                    hashtag = str(message.metadata[key]).replace(' ', '')
                    if len(text) + len(hashtag) + 3 <= 280:  # Twitter limit
                        text += f" #{hashtag}"
        
        # Truncate if needed
        if len(text) > 280:
            text = text[:277] + "..."
        
        return {"text": text}
    
    def _get_auth_headers(self, payload: Dict[str, Any]) -> Dict[str, str]:
        """Generate authentication headers"""
        if self.config.get('auth_type') == 'bearer':
            return {
                'Authorization': f"Bearer {self.config['bearer_token']}",
                'Content-Type': 'application/json'
            }
        else:
            # OAuth 1.0a - simplified implementation
            # In production, use a proper OAuth library like requests-oauthlib
            return {
                'Content-Type': 'application/json',
                'Authorization': self._generate_oauth1_header()
            }
    
    def _generate_oauth1_header(self) -> str:
        """Generate OAuth 1.0a authorization header"""
        # OAuth 1.0a parameters
        oauth_params = {
            'oauth_consumer_key': self.config['api_key'],
            'oauth_nonce': secrets.token_urlsafe(32),
            'oauth_signature_method': 'HMAC-SHA1',
            'oauth_timestamp': str(int(time.time())),
            'oauth_token': self.config['access_token'],
            'oauth_version': '1.0'
        }
        
        # Create signature base string
        method = 'POST'
        url = self.API_URL
        
        # Collect parameters (OAuth params only for POST with JSON body)
        params = oauth_params.copy()
        
        # Sort parameters
        sorted_params = sorted(params.items())
        param_string = '&'.join([f"{k}={urllib.parse.quote(v, safe='')}" for k, v in sorted_params])
        
        # Create signature base
        signature_base = f"{method}&{urllib.parse.quote(url, safe='')}&{urllib.parse.quote(param_string, safe='')}"
        
        # Create signing key
        signing_key = f"{urllib.parse.quote(self.config['api_secret'], safe='')}&{urllib.parse.quote(self.config['access_secret'], safe='')}"
        
        # Generate signature
        signature = base64.b64encode(
            hmac.new(
                signing_key.encode('utf-8'),
                signature_base.encode('utf-8'),
                hashlib.sha1
            ).digest()
        ).decode('utf-8')
        
        oauth_params['oauth_signature'] = signature
        
        # Build authorization header
        auth_header = 'OAuth ' + ', '.join([
            f'{k}="{urllib.parse.quote(v, safe="")}"'
            for k, v in sorted(oauth_params.items())
        ])
        
        return auth_header