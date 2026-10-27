"""Settings service for PC-Toolbox."""

import json
import os
from typing import Dict, Any

DEFAULTS = {
    "language": "English",
    "start_with_windows": False,
    "auto_update": True,
    "show_notifications": True,
    "minimize_tray": False,
    "theme": "Dark Navy",
    "scan_threads": 2,
    "large_file_threshold_mb": 100,
    "scan_locations": [],
    "notify_scan_complete": True,
    "notify_scan_failed": True,
    "notify_maintenance": True,
}


class SettingsService:
    def __init__(self, config_path=None):
        if config_path is None:
            config_path = os.path.join(os.path.expanduser("~"), ".pc_toolbox_settings.json")
        self.config_path = config_path
        self.settings = dict(DEFAULTS)
        self.load()

    def load(self):
        if not os.path.exists(self.config_path):
            self.settings = dict(DEFAULTS)
            return
        try:
            with open(self.config_path, "r") as f:
                data = json.load(f)
            # merge with defaults for backward compat
            merged = dict(DEFAULTS)
            if isinstance(data, dict):
                for k, v in data.items():
                    if k in DEFAULTS:
                        merged[k] = v
            self.settings = merged
        except Exception:
            self.settings = dict(DEFAULTS)

    def save(self):
        try:
            tmp = self.config_path + ".tmp"
            with open(tmp, "w") as f:
                json.dump(self.settings, f, indent=2)
            os.replace(tmp, self.config_path)
            return True
        except Exception:
            return False

    def get(self, key, default=None):
        return self.settings.get(key, default if default is not None else DEFAULTS.get(key))

    def set(self, key, value):
        if key in DEFAULTS:
            self.settings[key] = value

    def reset_defaults(self):
        self.settings = dict(DEFAULTS)

    def export_json(self, path):
        try:
            with open(path, "w") as f:
                json.dump(self.settings, f, indent=2)
            return True
        except Exception:
            return False

    def import_json(self, path):
        try:
            with open(path, "r") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return False, "Invalid format"
            merged = dict(self.settings)
            for k, v in data.items():
                if k in DEFAULTS:
                    merged[k] = v
            self.settings = merged
            return True, "Imported"
        except Exception as e:
            return False, str(e)

    def validate_path(self, path):
        if not path or not os.path.isabs(path):
            return False
        if path in ("/", "C:\\", "C:/"):
            return False
        return True

    def get_storage_info(self):
        return "Settings: %s" % self.config_path
