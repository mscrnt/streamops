"""Settings management service"""

import os
import json
import asyncio
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime
import logging
from pydantic import BaseModel, Field, validator
from enum import Enum
from typing import List

try:
    from app.api.utils.encryption import (
        encrypt_sensitive_fields,
        decrypt_sensitive_fields,
        encryption_service
    )
    ENCRYPTION_ENABLED = True
except ImportError:
    # Fallback if encryption not available
    ENCRYPTION_ENABLED = False
    def encrypt_sensitive_fields(data):
        return data
    def decrypt_sensitive_fields(data):
        return data

logger = logging.getLogger(__name__)


class LogLevel(str, Enum):
    TRACE = "trace"
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


class SystemSettings(BaseModel):
    log_level: LogLevel = LogLevel.INFO
    max_workers: int = Field(4, ge=1, le=32)
    worker_timeout: int = Field(300, ge=60, le=3600)
    temp_dir: str = "/tmp"


class ProcessingSettings(BaseModel):
    cpu_throttle: int = Field(0, ge=0, le=100)
    gpu_throttle: int = Field(0, ge=0, le=100)
    default_proxy_resolution: str = "1080p"
    hardware_acceleration: Optional[str] = None
    ffmpeg_path: str = "/usr/bin/ffmpeg"  # Read-only in UI


class StorageSettings(BaseModel):
    cleanup_policy: str = "manual"  # manual, auto_days
    cleanup_days: int = Field(30, ge=1, le=365)
    max_cache_size_gb: int = Field(100, ge=1, le=10000)
    thumbnail_quality: str = "medium"  # low, medium, high
    deduplication: bool = True


class OBSSettings(BaseModel):
    url: str = "ws://host.docker.internal:4455"
    password: str = ""
    auto_connect: bool = True


class GuardrailSettings(BaseModel):
    pause_when_recording: bool = True
    pause_when_streaming: bool = True
    cpu_threshold_pct: int = Field(80, ge=0, le=100)
    gpu_threshold_pct: int = Field(80, ge=0, le=100)
    min_free_disk_gb: int = Field(10, ge=1, le=1000)


class NotificationSettings(BaseModel):
    enabled: bool = False
    
    # Discord settings
    discord_enabled: bool = False
    discord_webhook_url: str = ""
    discord_username: str = "StreamOps"
    discord_avatar_url: str = ""
    
    # Twitter/X settings
    twitter_enabled: bool = False
    twitter_auth_type: str = "bearer"  # "bearer" or "oauth1"
    twitter_bearer_token: str = ""
    twitter_api_key: str = ""
    twitter_api_secret: str = ""
    twitter_access_token: str = ""
    twitter_access_secret: str = ""
    
    # Email settings
    email_enabled: bool = False
    email_smtp_host: str = ""
    email_smtp_port: int = 587
    email_smtp_user: str = ""
    email_smtp_pass: str = ""
    email_from: str = ""
    email_to: List[str] = Field(default_factory=list)
    email_use_tls: bool = True
    email_use_ssl: bool = False
    
    # Webhook settings
    webhook_enabled: bool = False
    webhook_endpoints: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Event subscriptions - Jobs
    events_job_started: bool = False
    events_job_completed: bool = True
    events_job_failed: bool = True
    
    # Event subscriptions - Recording
    events_recording_created: bool = True
    events_recording_started: bool = True
    events_recording_stopped: bool = True
    events_recording_processed: bool = True
    events_recording_failed: bool = True
    
    # Event subscriptions - Streaming
    events_stream_started: bool = True
    events_stream_stopped: bool = True
    events_stream_health_warning: bool = True
    events_stream_health_critical: bool = True
    events_stream_disconnected: bool = True
    events_stream_reconnected: bool = True
    
    # Event subscriptions - OBS
    events_obs_connected: bool = False
    events_obs_disconnected: bool = True
    events_obs_scene_changed: bool = False
    events_obs_recording_started: bool = True
    events_obs_recording_stopped: bool = True
    events_obs_streaming_started: bool = True
    events_obs_streaming_stopped: bool = True
    
    # Event subscriptions - System
    events_storage_threshold: bool = True
    events_drive_offline: bool = True
    events_system_alert: bool = True


class SecuritySettings(BaseModel):
    enable_authentication: bool = False
    username: str = ""
    password_hash: str = ""  # Never return raw password
    
    enable_https: bool = False
    cert_path: str = ""
    key_path: str = ""
    
    allow_downloads: bool = True


class InterfaceSettings(BaseModel):
    theme: str = "auto"  # auto, light, dark
    items_per_page: int = 25
    refresh_interval: int = 5
    show_advanced: bool = False


class Settings(BaseModel):
    """Complete settings model"""
    system: SystemSettings = Field(default_factory=SystemSettings)
    processing: ProcessingSettings = Field(default_factory=ProcessingSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    obs: OBSSettings = Field(default_factory=OBSSettings)
    guardrails: GuardrailSettings = Field(default_factory=GuardrailSettings)
    notifications: NotificationSettings = Field(default_factory=NotificationSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    interface: InterfaceSettings = Field(default_factory=InterfaceSettings)


class SettingsService:
    """Service for managing application settings"""
    
    def __init__(self):
        self._settings_path = Path(os.getenv("SETTINGS_PATH", "/data/settings.json"))
        self._settings: Optional[Settings] = None
        self._lock = asyncio.Lock()
        
        # Ensure the directory exists
        try:
            self._settings_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"Could not create settings directory: {e}")
    
    async def load_settings(self) -> Settings:
        """Load settings from disk"""
        async with self._lock:
            if self._settings_path.exists():
                try:
                    with open(self._settings_path) as f:
                        data = json.load(f)
                        # Decrypt sensitive fields before creating Settings object
                        data = decrypt_sensitive_fields(data)
                        self._settings = Settings(**data)
                except Exception as e:
                    logger.error(f"Failed to load settings: {e}")
                    self._settings = Settings()
            else:
                # Create default settings
                self._settings = Settings()
                await self._save_settings_unlocked()
            
            return self._settings
    
    async def get_settings_internal(self) -> Dict[str, Any]:
        """Get current settings as dict (internal use, unredacted)"""
        if not self._settings:
            await self.load_settings()
        
        # Return unredacted settings
        return self._settings.dict()
    
    async def get_settings(self) -> Dict[str, Any]:
        """Get current settings as dict (with secrets redacted)"""
        if not self._settings:
            await self.load_settings()
        
        # Convert to dict and redact secrets
        data = self._settings.dict()
        
        # Redact sensitive fields
        if data["obs"]["password"]:
            data["obs"]["password"] = "*" * 8
        
        # Redact sensitive notification fields
        if data["notifications"]["email_smtp_pass"]:
            data["notifications"]["email_smtp_pass"] = "*" * 8
        if data["notifications"]["twitter_bearer_token"]:
            data["notifications"]["twitter_bearer_token"] = "*" * 8
        if data["notifications"]["twitter_api_secret"]:
            data["notifications"]["twitter_api_secret"] = "*" * 8
        if data["notifications"]["twitter_access_secret"]:
            data["notifications"]["twitter_access_secret"] = "*" * 8
        if data["notifications"]["discord_webhook_url"] and "webhook" in data["notifications"]["discord_webhook_url"]:
            # Partial redaction of Discord webhook URL
            parts = data["notifications"]["discord_webhook_url"].split('/')
            if len(parts) > 5:
                parts[-1] = "*" * 8
                data["notifications"]["discord_webhook_url"] = '/'.join(parts)
        
        if data["security"]["password_hash"]:
            data["security"]["password_hash"] = "*" * 8
        
        return data
    
    async def update_settings(self, updates: Dict[str, Any]) -> Settings:
        """Update settings with partial data"""
        async with self._lock:
            if not self._settings:
                await self.load_settings()
            
            # Get current data (already decrypted in memory)
            current_data = self._settings.dict()
            
            # Handle password fields specially - don't update if masked
            if "obs" in updates:
                if updates["obs"].get("password") == "*" * 8:
                    # Keep existing password
                    updates["obs"]["password"] = current_data["obs"]["password"]
            
            if "notifications" in updates:
                # Clean up Google App Passwords (remove spaces)
                if updates["notifications"].get("email_smtp_pass") and updates["notifications"]["email_smtp_pass"] != "*" * 8:
                    # Remove spaces from password (Google App Passwords come with spaces)
                    cleaned_pass = updates["notifications"]["email_smtp_pass"].replace(" ", "").strip()
                    updates["notifications"]["email_smtp_pass"] = cleaned_pass
                    logger.info(f"Cleaned email password: removed spaces from {len(updates['notifications']['email_smtp_pass'])} to {len(cleaned_pass)} chars")
                
                # Restore redacted notification secrets
                if updates["notifications"].get("email_smtp_pass") == "*" * 8:
                    updates["notifications"]["email_smtp_pass"] = current_data["notifications"].get("email_smtp_pass", "")
                if updates["notifications"].get("twitter_bearer_token") == "*" * 8:
                    updates["notifications"]["twitter_bearer_token"] = current_data["notifications"].get("twitter_bearer_token", "")
                if updates["notifications"].get("twitter_api_secret") == "*" * 8:
                    updates["notifications"]["twitter_api_secret"] = current_data["notifications"].get("twitter_api_secret", "")
                if updates["notifications"].get("twitter_access_secret") == "*" * 8:
                    updates["notifications"]["twitter_access_secret"] = current_data["notifications"].get("twitter_access_secret", "")
                if "*" in updates["notifications"].get("discord_webhook_url", ""):
                    updates["notifications"]["discord_webhook_url"] = current_data["notifications"].get("discord_webhook_url", "")
            
            if "security" in updates:
                if updates["security"].get("password_hash") == "*" * 8:
                    updates["security"]["password_hash"] = current_data["security"]["password_hash"]
            
            # Merge updates
            for section, values in updates.items():
                if section in current_data and isinstance(values, dict):
                    current_data[section].update(values)
            
            # Validate and save
            self._settings = Settings(**current_data)
            await self._save_settings_unlocked()
            
            return self._settings
    
    async def _save_settings_unlocked(self):
        """Save settings to disk (must be called with lock held)"""
        try:
            # Ensure directory exists
            self._settings_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Get settings as dict and encrypt sensitive fields
            data = self._settings.dict()
            encrypted_data = encrypt_sensitive_fields(data)
            
            # Write to temp file first (atomic write)
            temp_path = self._settings_path.with_suffix('.tmp')
            with open(temp_path, 'w') as f:
                json.dump(encrypted_data, f, indent=2)
            
            # Atomic rename
            temp_path.replace(self._settings_path)
            
            # Try to set permissions (may fail in some environments)
            try:
                os.chmod(self._settings_path, 0o644)
            except OSError:
                pass  # Ignore permission errors
            
            if ENCRYPTION_ENABLED:
                logger.info("Settings saved successfully with encryption")
            else:
                logger.info("Settings saved successfully (encryption not available)")
        
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            raise
    
    async def reset_section(self, section: str) -> Settings:
        """Reset a specific section to defaults"""
        async with self._lock:
            if not self._settings:
                await self.load_settings()
            
            # Create default for the section
            if section == "system":
                self._settings.system = SystemSettings()
            elif section == "processing":
                self._settings.processing = ProcessingSettings()
            elif section == "storage":
                self._settings.storage = StorageSettings()
            elif section == "obs":
                self._settings.obs = OBSSettings()
            elif section == "guardrails":
                self._settings.guardrails = GuardrailSettings()
            elif section == "notifications":
                self._settings.notifications = NotificationSettings()
            elif section == "security":
                self._settings.security = SecuritySettings()
            elif section == "interface":
                self._settings.interface = InterfaceSettings()
            else:
                raise ValueError(f"Unknown section: {section}")
            
            await self._save_settings_unlocked()
            return self._settings
    
    def get_setting(self, path: str) -> Any:
        """Get a specific setting by dot-notation path"""
        if not self._settings:
            raise RuntimeError("Settings not loaded")
        
        parts = path.split('.')
        value = self._settings.dict()
        
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return None
        
        return value


# Global instance
settings_service = SettingsService()