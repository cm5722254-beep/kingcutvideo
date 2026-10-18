"""
Logging setup for King Video Cutter.
Writes logs to APPDATA/KingVideoCutter/king_video_cutter.log and standard output.
UTF-8 safe to handle Khmer text and Unicode file paths on Windows.
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler

def get_log_dir() -> str:
    app_data = os.getenv("APPDATA")
    if app_data:
        log_dir = os.path.join(app_data, "KingVideoCutter", "logs")
    else:
        log_dir = os.path.join(os.path.expanduser("~"), ".king_video_cutter", "logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir

def get_log_file_path() -> str:
    return os.path.join(get_log_dir(), "king_video_cutter.log")

_logger = None

def setup_logger(log_level: int = logging.INFO) -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger

    _logger = logging.getLogger("KingVideoCutter")
    _logger.setLevel(log_level)
    _logger.propagate = False

    # Prevent duplicate handlers
    if not _logger.handlers:
        formatter = logging.Formatter(
            fmt="[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        # File Handler (5 MB max, 3 backups) with UTF-8 encoding
        try:
            log_path = get_log_file_path()
            file_handler = RotatingFileHandler(
                log_path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(log_level)
            _logger.addHandler(file_handler)
        except Exception as e:
            print(f"Warning: Could not create file logger: {e}", file=sys.stderr)

        # Stream Handler
        try:
            stream_handler = logging.StreamHandler(sys.stdout)
            stream_handler.setFormatter(formatter)
            stream_handler.setLevel(log_level)
            _logger.addHandler(stream_handler)
        except Exception:
            pass

    return _logger

logger = setup_logger()
