"""Startup Manager service for PC-Toolbox.

Discovers startup entries from folders and registry. Safe enable/disable.
"""

import os
import sys
import platform
from typing import List, Dict, Any, Optional, Callable

sys.path.insert(0, 'd:/Windows app/PC-Toolbox')


class StartupManagerService:
    """Discovers and manages startup entries."""

    def __init__(self, winreg_module=None):
        if winreg_module is not None:
            self._winreg = winreg_module
        else:
            try:
                import winreg
                self._winreg = winreg
            except ImportError:
                self._winreg = None

    def _read_value(self, key, name):
        if self._winreg is None or key is None:
            return None
        try:
            value, _ = self._winreg.QueryValueEx(key, name)
            return value
        except Exception:
            return None

    def _open_key(self, hive, path):
        if self._winreg is None:
            return None
        try:
            return self._winreg.OpenKey(hive, path, 0, self._winreg.KEY_READ)
        except Exception:
            return None

    def discover(self, cancel_check=None):
        entries = []
        seen = set()

        # Startup folders
        folders = []
        appdata = os.environ.get("APPDATA", "")
        programdata = os.environ.get("PROGRAMDATA", "")
        if appdata:
            folders.append((os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Startup"), "Startup Folder (User)"))
        if programdata:
            folders.append((os.path.join(programdata, "Microsoft", "Windows", "Start Menu", "Programs", "Startup"), "Startup Folder (All Users)"))

        for folder, source in folders:
            if cancel_check and cancel_check():
                break
            if not os.path.isdir(folder):
                continue
            try:
                for name in os.listdir(folder):
                    if cancel_check and cancel_check():
                        break
                    full = os.path.join(folder, name)
                    if os.path.isfile(full) or os.path.isdir(full):
                        entry_id = "folder:%s" % full.lower()
                        if entry_id in seen:
                            continue
                        seen.add(entry_id)
                        entries.append({
                            "id": entry_id,
                            "name": os.path.splitext(name)[0],
                            "publisher": None,
                            "enabled": True,
                            "impact": "Unknown",
                            "source": source,
                            "command": full,
                            "type": "startup_folder",
                            "location": folder,
                        })
            except (PermissionError, OSError):
                continue

        # Registry Run keys
        reg_locations = [
            ("HKEY_CURRENT_USER", r"Software\Microsoft\Windows\CurrentVersion\Run", "Registry Run (HKCU)"),
            ("HKEY_CURRENT_USER", r"Software\Microsoft\Windows\CurrentVersion\RunOnce", "Registry RunOnce (HKCU)"),
            ("HKEY_LOCAL_MACHINE", r"Software\Microsoft\Windows\CurrentVersion\Run", "Registry Run (HKLM)"),
            ("HKEY_LOCAL_MACHINE", r"Software\Microsoft\Windows\CurrentVersion\RunOnce", "Registry RunOnce (HKLM)"),
            ("HKEY_LOCAL_MACHINE", r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run", "Registry Run (HKLM 32-bit)"),
        ]

        if self._winreg is not None:
            for hive_name, path, source in reg_locations:
                if cancel_check and cancel_check():
                    break
                hive = getattr(self._winreg, hive_name, None)
                if hive is None:
                    continue
                key = self._open_key(hive, path)
                if key is None:
                    continue
                try:
                    count = self._winreg.QueryInfoKey(key)[1]
                except Exception:
                    count = 0
                for i in range(count):
                    if cancel_check and cancel_check():
                        break
                    try:
                        name, value, _ = self._winreg.EnumValue(key, i)
                    except Exception:
                        continue
                    entry_id = "reg:%s\\%s" % (path, name)
                    if entry_id in seen:
                        continue
                    seen.add(entry_id)
                    entries.append({
                        "id": entry_id,
                        "name": name,
                        "publisher": None,
                        "enabled": True,
                        "impact": "Unknown",
                        "source": source,
                        "command": str(value),
                        "type": "registry",
                        "hive": hive_name,
                        "key_path": path,
                        "value_name": name,
                    })
                try:
                    self._winreg.CloseKey(key)
                except Exception:
                    pass

        return {"entries": entries, "errors": []}

    def disable_entry(self, entry):
        """Disable a startup entry. Returns (success, message)."""
        if entry.get("type") == "registry":
            hive = entry.get("hive")
            path = entry.get("key_path")
            name = entry.get("value_name")
            if not (hive and path and name):
                return False, "Missing registry metadata"
            # We cannot safely delete; instead we'd need to move to a backup key.
            # For safety, report that registry modification requires manual action.
            return False, "Registry modification not enabled in this version for safety"
        elif entry.get("type") == "startup_folder":
            # Rename file to .disabled
            cmd = entry.get("command", "")
            if not os.path.exists(cmd):
                return False, "File not found"
            try:
                os.rename(cmd, cmd + ".disabled")
                return True, "Disabled (renamed to .disabled)"
            except Exception as e:
                return False, str(e)
        return False, "Unsupported entry type"

    def enable_entry(self, entry):
        """Enable a previously disabled startup entry."""
        if entry.get("type") == "startup_folder":
            cmd = entry.get("command", "")
            disabled_path = cmd + ".disabled"
            if os.path.exists(disabled_path):
                try:
                    os.rename(disabled_path, cmd)
                    return True, "Enabled"
                except Exception as e:
                    return False, str(e)
            return False, "Disabled file not found"
        return False, "Unsupported entry type"
