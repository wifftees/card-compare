"""Logging configuration with file rotation support"""
import logging
import logging.handlers
import os
import sys
from pathlib import Path
from bot.config import settings


def setup_logging():
    """
    Setup logging configuration with file rotation.
    
    Supports two rotation strategies:
    - size: Rotates when file reaches max_bytes (default: 10MB)
    - time: Rotates daily at midnight
    
    Rotated files are named:
    - Size rotation: app.log, app.log.1, app.log.2, etc.
    - Time rotation: app.log, app.log.2026-02-08, app.log.2026-02-07, etc.
    """
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    
    # Create detailed formatter with more context
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    
    # Create logs directory if it doesn't exist
    logs_dir = Path(settings.log_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)
    
    # Choose file handler based on rotation type
    log_file = logs_dir / "app.log"
    
    if settings.log_rotation_type == "time":
        # Time-based rotation: creates new file daily at midnight
        # Files named: app.log.2026-02-08, app.log.2026-02-07, etc.
        file_handler = logging.handlers.TimedRotatingFileHandler(
            log_file,
            when='midnight',
            interval=1,
            backupCount=settings.log_file_backup_count,
            encoding='utf-8',
            utc=False
        )
        logging.info("Using time-based log rotation (daily at midnight)")
    else:
        # Size-based rotation: creates new file when current exceeds max_bytes
        # Files named: app.log, app.log.1, app.log.2, etc.
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=settings.log_file_max_bytes,
            backupCount=settings.log_file_backup_count,
            encoding='utf-8'
        )
        size_mb = settings.log_file_max_bytes / (1024 * 1024)
        logging.info(f"Using size-based log rotation (max {size_mb:.1f}MB per file)")
    
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Clear existing handlers to avoid duplicates
    root_logger.handlers.clear()
    
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # Configure specific library loggers
    logging.getLogger("aiogram").setLevel(logging.INFO)
    logging.getLogger("playwright").setLevel(logging.WARNING)
    
    # Silence noisy HTTP/network libraries
    logging.getLogger("hpack").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    
    # Log initial configuration
    root_logger.info(f"Logging initialized: level={settings.log_level}, dir={logs_dir}, backups={settings.log_file_backup_count}")
    
    return root_logger
