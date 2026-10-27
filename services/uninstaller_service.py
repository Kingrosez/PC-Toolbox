"""Uninstaller discovery service for PC-Toolbox.

Reads Windows uninstall registry entries. No uninstallation is performed.
"""

import os
import sys
import platform
from typing import List, Dict, Any, Optional, Callable

sys.path.insert(0, 'd:/Windows app/PC-Toolbox')


# Registry locations to inspect (64-bit and 32-bit views on Windows).
REGISTRY_LOCATIONS = [
    # (hive, path, view_flag, source_label)
    ("HKLM", r"Software\Microsoft\Windows\CurrentVersion\Uninstall", 0, "HKLM"),
    ("HKLM", r"Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall", 0, "HKLM (32-bit)"),
    ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Uninstall", 0, "HKCU"),
]


class UninstallerService:
    """Discovers installed applications from Windows registry."""

    def __init__(self, winreg_module=None):
        # Allow injection of a mock winreg for testing.
        if winreg_module is not None:
            self._winreg = winreg_module
        else:
            try:
                import winreg
                self._winreg = winreg
            except ImportError:
                self._winreg = None

    # ---------------------------------------------------------------- helpers
    def _open_key(self, hive_name, path, view_flag=0):
        if self._winreg is None:
            return None
        try:
            hive = getattr(self._winreg, hive_name)
            access = self._winreg.KEY_READ
            if view_flag:
                access |= view_flag
            return self._winreg.OpenKey(hive, path, 0, access)
        except Exception:
            return None

    def _read_value(self, key, name):
        if self._winreg is None or key is None:
            return None
        try:
            value, _ = self._winreg.QueryValueEx(key, name)
            return value
        except Exception:
            return None

    def _is_system_component(self, entry: Dict[str, Any]) -> bool:
        # Conservative filtering: skip Windows updates and system components.
        name = (entry.get("name") or "").lower()
        if not name:
            return True
        if entry.get("system_component") is True:
            return True
        if entry.get("windows_installer") and "update" in name:
            # Heuristic: updates often have "Update" in name
            return False  # keep, let user decide; safer not to hide
        # Skip obvious system entries
        skip_keywords = ["security update", "hotfix", "update for windows", "update for microsoft"]
        for kw in skip_keywords:
            if kw in name:
                return True
        # Skip entries with no uninstall string and no modify path
        if not entry.get("uninstall_string") and not entry.get("modify_path"):
            return True
        return False

    def _categorize(self, name: str, publisher: str) -> str:
        text = ("%s %s" % (name, publisher)).lower()
        if any(k in text for k in ["chrome", "firefox", "edge", "browser", "opera", "brave"]):
            return "Browsers"
        if any(k in text for k in ["python", "visual studio", "gcc", "compiler", "sdk", "git", "node", "jdk", "java"]):
            return "Development"
        if any(k in text for k in ["antivirus", "security", "defender", "firewall", "malware"]):
            return "Security"
        return "Utilities"

    def _safe_int(self, value) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, bool):
            return None
        try:
            v = int(value)
            if v < 0:
                return None
            return v
        except (ValueError, TypeError):
            return None

    def _convert_size(self, estimated_size_kb) -> Optional[int]:
        """Convert EstimatedSize (KB) to bytes. Returns None if unavailable/invalid."""
        kb = self._safe_int(estimated_size_kb)
        if kb is None or kb <= 0:
            return None
        return kb * 1024

    def _parse_install_date(self, raw) -> Optional[str]:
        if raw is None:
            return None
        s = str(raw).strip()
        if not s:
            return None
        # Format: YYYYMMDD
        if len(s) == 8 and s.isdigit():
            try:
                return "%s-%s-%s" % (s[0:4], s[4:6], s[6:8])
            except Exception:
                return None
        return s

    # ---------------------------------------------------------------- discovery
    def discover(self, cancel_check: Optional[Callable] = None) -> Dict[str, Any]:
        apps = []
        errors = []
        seen_ids = set()

        if self._winreg is None:
            return {
                "applications": [],
                "errors": ["winreg unavailable on this platform"],
                "warnings": [],
            }

        for hive_name, path, view_flag, source_label in REGISTRY_LOCATIONS:
            if cancel_check and cancel_check():
                break
            key = self._open_key(hive_name, path, view_flag)
            if key is None:
                continue
            try:
                count = self._winreg.QueryInfoKey(key)[0]
            except Exception:
                try:
                    self._winreg.CloseKey(key)
                except Exception:
                    pass
                errors.append("Could not enumerate %s\\%s" % (hive_name, path))
                continue

            for i in range(count):
                if cancel_check and cancel_check():
                    break
                try:
                    subkey_name = self._winreg.EnumKey(key, i)
                except Exception:
                    continue
                subkey = None
                try:
                    subkey = self._winreg.OpenKey(key, subkey_name)
                except Exception:
                    continue
                try:
                    entry = self._read_entry(subkey, hive_name, path, subkey_name, source_label)
                    if entry is None:
                        continue
                    if self._is_system_component(entry):
                        continue
                    app_id = entry.get("id")
                    if app_id in seen_ids:
                        continue
                    seen_ids.add(app_id)
                    apps.append(entry)
                except Exception as e:
                    errors.append("Error reading entry %s: %s" % (subkey_name, str(e)))
                finally:
                    try:
                        self._winreg.CloseKey(subkey)
                    except Exception:
                        pass
            try:
                self._winreg.CloseKey(key)
            except Exception:
                pass

        return {
            "applications": apps,
            "errors": errors,
            "warnings": [],
        }

    def _read_entry(self, subkey, hive_name, path, subkey_name, source_label):
        name = self._read_value(subkey, "DisplayName")
        if not name:
            return None
        name = str(name).strip()
        if not name:
            return None

        version = self._read_value(subkey, "DisplayVersion")
        publisher = self._read_value(subkey, "Publisher")
        install_date_raw = self._read_value(subkey, "InstallDate")
        install_location = self._read_value(subkey, "InstallLocation")
        estimated_size = self._read_value(subkey, "EstimatedSize")
        uninstall_string = self._read_value(subkey, "UninstallString")
        modify_path = self._read_value(subkey, "ModifyPath")
        system_component = self._read_value(subkey, "SystemComponent")
        windows_installer = self._read_value(subkey, "WindowsInstaller")

        app_id = "%s\\%s\\%s" % (hive_name, path, subkey_name)

        return {
            "id": app_id,
            "name": name,
            "version": str(version).strip() if version else None,
            "publisher": str(publisher).strip() if publisher else None,
            "install_date": self._parse_install_date(install_date_raw),
            "install_location": str(install_location).strip() if install_location else None,
            "size_bytes": self._convert_size(estimated_size),
            "uninstall_string": str(uninstall_string).strip() if uninstall_string else None,
            "modify_path": str(modify_path).strip() if modify_path else None,
            "system_component": (system_component == 1) if system_component is not None else None,
            "windows_installer": bool(windows_installer) if windows_installer is not None else None,
            "registry_source": source_label,
            "registry_key": subkey_name,
            "category": self._categorize(name, publisher or ""),
        }
