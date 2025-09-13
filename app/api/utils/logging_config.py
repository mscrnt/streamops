"""Centralized logging configuration for StreamOps"""

import os
import logging
import logging.handlers
from pathlib import Path

def setup_logging(service_name: str = "streamops") -> None:
    """
    Configure logging for StreamOps services
    
    Args:
        service_name: Name of the service (api, worker, etc.)
    """
    # Get log level from environment
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_dir = Path(os.getenv("LOG_DIR", "/data/logs"))
    
    # Ensure log directory exists
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture all, filter at handler level
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Console handler (INFO and above)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level, logging.INFO))
    console_handler.setFormatter(simple_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler - Main log (all levels)
    main_log = log_dir / f"{service_name}.log"
    file_handler = logging.handlers.RotatingFileHandler(
        main_log,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(file_handler)
    
    # Error file handler (ERROR and CRITICAL only)
    error_log = log_dir / f"{service_name}_errors.log"
    error_handler = logging.handlers.RotatingFileHandler(
        error_log,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=3,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(error_handler)
    
    # Configure specific loggers to reduce noise
    noisy_loggers = {
        'app.api.services.gpu_service': logging.WARNING,  # Only warnings and above
        'app.worker.jobs.index': logging.WARNING,  # Reduce indexing verbosity
        'urllib3.connectionpool': logging.WARNING,  # Reduce HTTP connection logs
        'obsws_python': logging.WARNING,  # Reduce OBS websocket logs
        'watchdog': logging.WARNING,  # Reduce file watcher logs
    }
    
    for logger_name, level in noisy_loggers.items():
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)
    
    # Log the configuration
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured for {service_name}")
    logger.info(f"Log level: {log_level}")
    logger.info(f"Log directory: {log_dir}")
    logger.info(f"Main log: {main_log}")
    logger.info(f"Error log: {error_log}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)