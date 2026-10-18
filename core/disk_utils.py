"""
Disk space utilities for King Video Cutter.
Ensures user has sufficient storage before beginning video operations.
"""

import os
import shutil
from typing import Tuple

def get_disk_free_space(path: str) -> Tuple[float, str]:
    """
    Returns (free_space_in_gb, drive_root).
    """
    try:
        drive = os.path.splitdrive(os.path.abspath(path))[0]
        if not drive:
            drive = "C:"
        drive_path = drive + "\\" if not drive.endswith("\\") else drive
        total, used, free = shutil.disk_usage(drive_path)
        return free / (1024 ** 3), drive
    except Exception:
        # Fallback
        return 999.0, "C:"

def has_sufficient_disk_space(path: str, required_gb: float) -> Tuple[bool, float, str]:
    """
    Checks if path has at least required_gb free space.
    Returns (is_sufficient, free_gb, drive).
    """
    free_gb, drive = get_disk_free_space(path)
    return (free_gb >= required_gb), free_gb, drive
