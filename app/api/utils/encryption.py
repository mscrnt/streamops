"""Encryption utilities for sensitive data"""

import os
import base64
import logging
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from typing import Optional

logger = logging.getLogger(__name__)


class EncryptionService:
    """Service for encrypting/decrypting sensitive configuration data"""
    
    def __init__(self):
        self._cipher = None
        self._initialize_cipher()
    
    def _initialize_cipher(self):
        """Initialize the encryption cipher using a derived key"""
        try:
            # Get or generate encryption salt
            salt_path = "/data/config/.salt"
            if os.path.exists(salt_path):
                with open(salt_path, 'rb') as f:
                    salt = f.read()
            else:
                # Generate new salt
                salt = os.urandom(16)
                os.makedirs(os.path.dirname(salt_path), exist_ok=True)
                with open(salt_path, 'wb') as f:
                    f.write(salt)
                # Secure the salt file
                os.chmod(salt_path, 0o600)
            
            # Derive key from container hostname and salt
            # This ensures data is only decryptable within the same container
            hostname = os.environ.get('HOSTNAME', 'streamops')
            container_id = os.environ.get('CONTAINER_ID', hostname)
            
            # Create a stable key material from environment
            key_material = f"{hostname}:{container_id}:streamops-encryption".encode()
            
            # Use PBKDF2HMAC to derive a key
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(key_material))
            
            self._cipher = Fernet(key)
            logger.info("Encryption service initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize encryption: {e}")
            # Fall back to a default key (less secure but functional)
            default_key = Fernet.generate_key()
            self._cipher = Fernet(default_key)
            logger.warning("Using fallback encryption key - less secure!")
    
    def encrypt(self, plaintext: str) -> str:
        """Encrypt a string value"""
        if not plaintext:
            return ""
        
        try:
            encrypted = self._cipher.encrypt(plaintext.encode())
            # Return base64 encoded for JSON storage
            return base64.b64encode(encrypted).decode('utf-8')
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            # Return the plaintext if encryption fails (with warning prefix)
            return f"UNENCRYPTED:{plaintext}"
    
    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a string value"""
        if not ciphertext:
            return ""
        
        # Check if it's unencrypted (fallback)
        if ciphertext.startswith("UNENCRYPTED:"):
            return ciphertext[12:]
        
        try:
            # Decode from base64 and decrypt
            encrypted = base64.b64decode(ciphertext.encode('utf-8'))
            decrypted = self._cipher.decrypt(encrypted)
            return decrypted.decode('utf-8')
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            # If decryption fails, it might be plain text from old config
            # Return as-is but log warning
            logger.warning("Returning potentially unencrypted value")
            return ciphertext
    
    def is_encrypted(self, value: str) -> bool:
        """Check if a value appears to be encrypted"""
        if not value:
            return False
        
        if value.startswith("UNENCRYPTED:"):
            return False
        
        try:
            # Try to decode as base64
            decoded = base64.b64decode(value.encode('utf-8'))
            # Check if it looks like Fernet token (starts with version byte)
            return len(decoded) > 0 and decoded[0] == 0x80
        except:
            return False


# Global instance
encryption_service = EncryptionService()


# List of sensitive fields that should be encrypted
SENSITIVE_FIELDS = [
    'email_smtp_pass',
    'discord_webhook_url', 
    'twitter_bearer_token',
    'twitter_api_secret',
    'twitter_access_secret',
    'obs.password',
    'security.password_hash'
]


def encrypt_sensitive_fields(data: dict, path: str = "") -> dict:
    """Recursively encrypt sensitive fields in a dictionary"""
    result = {}
    
    for key, value in data.items():
        current_path = f"{path}.{key}" if path else key
        
        if isinstance(value, dict):
            # Recurse into nested dictionaries
            result[key] = encrypt_sensitive_fields(value, current_path)
        elif current_path in SENSITIVE_FIELDS or key in SENSITIVE_FIELDS:
            # Encrypt sensitive field if it's not already encrypted
            if value and isinstance(value, str):
                if not encryption_service.is_encrypted(value):
                    result[key] = encryption_service.encrypt(value)
                    logger.debug(f"Encrypted field: {current_path}")
                else:
                    result[key] = value
            else:
                result[key] = value
        else:
            result[key] = value
    
    return result


def decrypt_sensitive_fields(data: dict, path: str = "") -> dict:
    """Recursively decrypt sensitive fields in a dictionary"""
    result = {}
    
    for key, value in data.items():
        current_path = f"{path}.{key}" if path else key
        
        if isinstance(value, dict):
            # Recurse into nested dictionaries
            result[key] = decrypt_sensitive_fields(value, current_path)
        elif current_path in SENSITIVE_FIELDS or key in SENSITIVE_FIELDS:
            # Decrypt sensitive field if it's encrypted
            if value and isinstance(value, str):
                if encryption_service.is_encrypted(value):
                    result[key] = encryption_service.decrypt(value)
                    logger.debug(f"Decrypted field: {current_path}")
                else:
                    result[key] = value
            else:
                result[key] = value
        else:
            result[key] = value
    
    return result