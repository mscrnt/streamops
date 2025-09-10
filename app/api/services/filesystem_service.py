"""
Filesystem utility service for safe path operations.
Consolidated from routers/drives.py and routers/filesystem.py
"""
import os
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class FilesystemService:
    """Service for filesystem operations with security checks"""
    
    @staticmethod
    def safe_join(base: str, relative: str) -> Optional[str]:
        """
        Safely join a base path with a relative path, preventing directory traversal.
        
        Args:
            base: The base directory path
            relative: The relative path to join
            
        Returns:
            The joined absolute path if safe, None if it would escape base directory
        """
        # Normalize the base path
        base = os.path.abspath(base)
        
        # Handle empty relative path
        if not relative or relative == ".":
            return base
            
        # Remove leading slashes to prevent absolute path interpretation
        relative = relative.lstrip("/\\")
        
        # Join and normalize the full path
        joined = os.path.abspath(os.path.join(base, relative))
        
        # Ensure the joined path is within the base directory
        if not joined.startswith(base):
            logger.warning(f"Path traversal attempt blocked: base={base}, relative={relative}")
            return None
            
        return joined
    
    @staticmethod
    def check_directory_writable(path: str) -> bool:
        """
        Check if a directory is writable by attempting to create a temporary file.
        
        Args:
            path: Directory path to check
            
        Returns:
            True if directory is writable, False otherwise
        """
        if not os.path.exists(path):
            return False
            
        if not os.path.isdir(path):
            return False
            
        try:
            # Create a unique test file name
            test_file = os.path.join(path, f".streamops_write_test_{os.getpid()}")
            
            # Attempt to create and immediately delete the test file
            try:
                with open(test_file, 'w') as f:
                    f.write("test")
                os.unlink(test_file)
                return True
            except Exception as e:
                # Try to clean up if file was created but deletion failed
                if os.path.exists(test_file):
                    try:
                        os.unlink(test_file)
                    except:
                        pass
                return False
                
        except Exception as e:
            logger.debug(f"Directory not writable: {path} - {e}")
            return False
    
    @staticmethod
    def ensure_directory_exists(path: str) -> bool:
        """
        Ensure a directory exists, creating it if necessary.
        
        Args:
            path: Directory path to ensure exists
            
        Returns:
            True if directory exists or was created, False on error
        """
        try:
            os.makedirs(path, exist_ok=True)
            return True
        except Exception as e:
            logger.error(f"Failed to create directory {path}: {e}")
            return False
    
    @staticmethod
    def get_directory_size(path: str) -> int:
        """
        Calculate the total size of a directory and its contents.
        
        Args:
            path: Directory path to measure
            
        Returns:
            Total size in bytes
        """
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    try:
                        total_size += os.path.getsize(filepath)
                    except (OSError, IOError):
                        pass
        except Exception as e:
            logger.error(f"Error calculating directory size for {path}: {e}")
        
        return total_size


# Create singleton instance for backward compatibility
filesystem_service = FilesystemService()