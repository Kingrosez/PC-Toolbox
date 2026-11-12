"""Tests for Temp Cleaner settings persistence via SettingsService.

Verifies the Temp Cleaner's Scan Settings dialog can round-trip its
toggles through the shared SettingsService, so user choices survive
restarts and are consistent with the rest of the app.
"""

import os
import sys
import tempfile

sys.path.insert(0, "d:/Windows app/PC-Toolbox")

from services.temp_cleaner_service import TempCleanerService
from services.settings_service import SettingsService


def test_settings_round_trip_through_settings_service():
    """Temp Cleaner settings must persist via SettingsService and reload on init."""
    cfg = os.path.join(tempfile.mkdtemp(), "settings.json")
    ss = SettingsService(config_path=cfg)

    svc = TempCleanerService(settings_service=ss)
    svc.update_settings({
        "include_browser_caches": False,
        "include_app_caches": False,
        "include_log_files": False,
        "include_windows_temp": False,
    })
    assert ss.save() is True

    # Reload from disk into a fresh service.
    ss2 = SettingsService(config_path=cfg)
    svc2 = TempCleanerService(settings_service=ss2)
    s = svc2.get_settings()
    assert s["include_browser_caches"] is False
    assert s["include_app_caches"] is False
    assert s["include_log_files"] is False
    assert s["include_windows_temp"] is False


def test_settings_defaults_when_no_persistence():
    """Temp Cleaner must fall back to defaults when no settings are stored."""
    svc = TempCleanerService(settings_service=None)
    s = svc.get_settings()
    assert s["include_browser_caches"] is True
    assert s["include_windows_temp"] is True
    assert s["include_user_temp"] is True


def test_settings_custom_roots_persist():
    """Custom scan roots must round-trip through SettingsService."""
    cfg = os.path.join(tempfile.mkdtemp(), "settings.json")
    ss = SettingsService(config_path=cfg)

    svc = TempCleanerService(settings_service=ss)
    svc.update_settings({"custom_roots": [r"C:\Custom\Temp"]})
    ss.save()

    ss2 = SettingsService(config_path=cfg)
    svc2 = TempCleanerService(settings_service=ss2)
    assert svc2.get_settings()["custom_roots"] == [r"C:\Custom\Temp"]