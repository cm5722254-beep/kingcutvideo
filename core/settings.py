"""
Settings Manager for King Video Cutter.
Handles persistent configuration in JSON format.
"""

import json
import os
import sys
from typing import Any, Dict

def get_settings_path() -> str:
    app_data = os.getenv("APPDATA")
    if app_data:
        config_dir = os.path.join(app_data, "KingVideoCutter")
    else:
        config_dir = os.path.join(os.path.expanduser("~"), ".king_video_cutter")
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, "settings.json")

DEFAULT_SETTINGS: Dict[str, Any] = {
    "language": "km",
    "theme": "dark",
    "hw_accel": "auto",  # auto, nvenc, qsv, amf, none
    "default_output_dir": os.path.join(os.path.expanduser("~"), "Videos", "KingCutter"),
    "disk_check_enabled": True,
    "min_disk_gb": 3.0,
    "fast_mode_default": True,
    "default_split_mode": "duration",
    "default_duration_sec": 60,
    "default_parts": 10,
    "default_size_mb": 50,
    "naming_pattern": "{name}_Part_{index:03d}",
    "log_level": "INFO"
}

class SettingsManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SettingsManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.settings_file = get_settings_path()
        self.data: Dict[str, Any] = dict(DEFAULT_SETTINGS)
        self.load()

    def load(self):
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    self.data.update(saved)
            except Exception as e:
                print(f"Error loading settings: {e}", file=sys.stderr)
        else:
            self.save()

    def save(self):
        try:
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving settings: {e}", file=sys.stderr)

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default if default is not None else DEFAULT_SETTINGS.get(key))

    def set(self, key: str, value: Any):
        self.data[key] = value
        self.save()

# Global accessor
settings = SettingsManager()
