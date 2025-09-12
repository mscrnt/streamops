import os
import json
import asyncio
from pathlib import Path
from typing import Any, Dict, Optional
import logging
from pydantic import BaseModel
from datetime import datetime

try:
    from app.api.utils.encryption import (
        encrypt_sensitive_fields,
        decrypt_sensitive_fields
    )
except ImportError:
    # Fallback if encryption not available
    def encrypt_sensitive_fields(data): return data
    def decrypt_sensitive_fields(data): return data

logger = logging.getLogger(__name__)

class StreamOpsConfig(BaseModel):
    # General settings
    instance_name: str = "StreamOps"
    
    # OBS WebSocket
    obs_ws_url: Optional[str] = None
    obs_ws_password: Optional[str] = None
    obs_ws_auto_connect: bool = True
    
    # Performance guardrails
    gpu_guard_pct: int = 40
    cpu_guard_pct: int = 70
    pause_when_recording: bool = True
    
    # File watching
    watch_poll_interval: int = 5
    file_quiet_seconds: int = 45
    
    # Processing
    default_remux_format: str = "mov"
    enable_auto_proxy: bool = True
    proxy_min_duration_sec: int = 900
    proxy_codec: str = "dnxhr_lb"
    
    # Storage paths
    default_editing_path: str = "/mnt/drive_f/Editing"
    archive_path: str = "/mnt/drive_f/Archive"
    
    # Thumbnails
    enable_hover_scrub: bool = True
    thumbnail_interval_sec: int = 20
    sprite_columns: int = 5
    
    # Features
    enable_scene_detect: bool = True
    enable_waveform: bool = True
    enable_social_exports: bool = False
    
    # Remote workers
    enable_remote_workers: bool = False
    worker_heartbeat_sec: int = 30
    
    # Metrics
    enable_metrics: bool = True
    metrics_retention_days: int = 90

class ConfigService:
    def __init__(self):
        self.config_path = Path(os.getenv("CONFIG_PATH", "/data/config/config.json"))
        self.config: StreamOpsConfig = StreamOpsConfig()
        self._custom_config: Dict[str, Any] = {}  # Store custom configuration keys
        self._lock = None
        
    async def load_config(self) -> StreamOpsConfig:
        """Load configuration from file and environment variables"""
        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            # Load from file if exists
            if self.config_path.exists():
                try:
                    with open(self.config_path, 'r') as f:
                        data = json.load(f)
                        # Decrypt sensitive fields
                        data = decrypt_sensitive_fields(data)
                        # Extract custom config if present
                        if 'custom' in data:
                            self._custom_config = data.pop('custom')
                        # Load standard config
                        self.config = StreamOpsConfig(**{k: v for k, v in data.items() if k != 'custom'})
                    logger.info(f"Loaded config from {self.config_path}")
                except Exception as e:
                    logger.error(f"Failed to load config: {e}")
            
            # Override with environment variables
            self._apply_env_overrides()
            
            # Save current config (without re-acquiring lock)
            await self._save_config_unlocked()
            
            return self.config
    
    async def _save_config_unlocked(self) -> None:
        """Save config without acquiring lock (internal use only)"""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            # Include both standard and custom config
            all_config = {
                **self.config.model_dump(),
                "custom": self._custom_config
            }
            # Encrypt sensitive fields before saving
            encrypted_config = encrypt_sensitive_fields(all_config)
            with open(self.config_path, 'w') as f:
                json.dump(
                    encrypted_config,
                    f,
                    indent=2,
                    default=str
                )
            # Secure the config file
            os.chmod(self.config_path, 0o600)
            logger.info(f"Saved encrypted config to {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
    
    async def save_config(self) -> None:
        """Save current configuration to file"""
        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            await self._save_config_unlocked()
    
    async def update_config(self, updates: Dict[str, Any]) -> StreamOpsConfig:
        """Update configuration with new values"""
        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            for key, value in updates.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
            
            await self._save_config_unlocked()
            return self.config
    
    def _apply_env_overrides(self):
        """Apply environment variable overrides to config"""
        env_mapping = {
            "OBS_WS_URL": "obs_ws_url",
            "OBS_WS_PASSWORD": "obs_ws_password",
            "GPU_GUARD_PCT": ("gpu_guard_pct", int),
            "CPU_GUARD_PCT": ("cpu_guard_pct", int),
            "PAUSE_WHEN_RECORDING": ("pause_when_recording", lambda x: x.lower() == "true"),
            "ENABLE_REMOTE_WORKERS": ("enable_remote_workers", lambda x: x.lower() == "true"),
        }
        
        for env_key, config_key in env_mapping.items():
            env_value = os.getenv(env_key)
            if env_value is not None:
                if isinstance(config_key, tuple):
                    attr_name, converter = config_key
                    try:
                        setattr(self.config, attr_name, converter(env_value))
                    except Exception as e:
                        logger.warning(f"Failed to convert env var {env_key}: {e}")
                else:
                    setattr(self.config, config_key, env_value)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key"""
        return getattr(self.config, key, default)
    
    def get_all(self) -> Dict[str, Any]:
        """Get all configuration as dictionary"""
        return self.config.model_dump()
    
    async def set_config(self, key: str, value: Any) -> None:
        """Set a custom configuration value"""
        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            self._custom_config[key] = value
            # Save both standard and custom config
            await self._save_all_config()
    
    async def get_config(self, key: str, default: Any = None) -> Any:
        """Get a custom configuration value"""
        return self._custom_config.get(key, default)
    
    async def _save_all_config(self) -> None:
        """Save both standard and custom configuration"""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            all_config = {
                **self.config.model_dump(),
                "custom": self._custom_config
            }
            # Encrypt sensitive fields before saving
            encrypted_config = encrypt_sensitive_fields(all_config)
            with open(self.config_path, 'w') as f:
                json.dump(encrypted_config, f, indent=2, default=str)
            # Secure the config file  
            os.chmod(self.config_path, 0o600)
            logger.info(f"Saved encrypted config to {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")