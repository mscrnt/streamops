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
    cpu_threshold_pct: int = Field(80, ge=0, le=100)
    gpu_threshold_pct: int = Field(80, ge=0, le=100)
    min_free_disk_gb: int = Field(10, ge=1, le=1000)


class NotificationSettings(BaseModel):
    email_enabled: bool = False
    email_smtp_server: str = ""
    email_smtp_port: int = 587
    email_from: str = ""
    email_password: str = ""
    
    webhook_enabled: bool = False
    webhook_url: str = ""
    
    events_job_completed: bool = True
    events_job_failed: bool = True
    events_drive_offline: bool = True
    events_system_error: bool = True


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
        self._settings_path = Path(os.getenv("CONFIG_PATH", "/data/config/settings.json"))
        self._settings: Optional[Settings] = None
        self._lock = asyncio.Lock()
    
    async def load_settings(self) -> Settings:
        """Load settings from disk"""
        async with self._lock:
            if self._settings_path.exists():
                try:
                    with open(self._settings_path) as f:
                        data = json.load(f)
                        self._settings = Settings(**data)
                except Exception as e:
                    logger.error(f"Failed to load settings: {e}")
                    self._settings = Settings()
            else:
                # Create default settings
                self._settings = Settings()
                await self._save_settings_unlocked()
            
            return self._settings
    
    async def get_settings(self) -> Dict[str, Any]:
        """Get current settings as dict (with secrets redacted)"""
        if not self._settings:
            await self.load_settings()
        
        # Convert to dict and redact secrets
        data = self._settings.dict()
        
        # Redact sensitive fields
        if data["obs"]["password"]:
            data["obs"]["password"] = "*" * 8
        
        if data["notifications"]["email_password"]:
            data["notifications"]["email_password"] = "*" * 8
        
        if data["security"]["password_hash"]:
            data["security"]["password_hash"] = "*" * 8
        
        return data
    
    async def update_settings(self, updates: Dict[str, Any]) -> Settings:
        """Update settings with partial data"""
        async with self._lock:
            if not self._settings:
                await self.load_settings()
            
            # Get current data
            current_data = self._settings.dict()
            
            # Handle password fields specially - don't update if masked
            if "obs" in updates:
                if updates["obs"].get("password") == "*" * 8:
                    # Keep existing password
                    updates["obs"]["password"] = current_data["obs"]["password"]
            
            if "notifications" in updates:
                if updates["notifications"].get("email_password") == "*" * 8:
                    updates["notifications"]["email_password"] = current_data["notifications"]["email_password"]
            
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
            
            # Write to temp file first (atomic write)
            temp_path = self._settings_path.with_suffix('.tmp')
            with open(temp_path, 'w') as f:
                json.dump(self._settings.dict(), f, indent=2)
            
            # Atomic rename
            temp_path.replace(self._settings_path)
            
            logger.info("Settings saved successfully")
        
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