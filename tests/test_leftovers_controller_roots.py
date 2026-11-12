"""Tests for LeftoversController scan-root configuration."""

import os
import sys
import tempfile

sys.path.insert(0, "d:/Windows app/PC-Toolbox")

from controllers.leftovers_controller import LeftoversController
from services.activity_service import ActivityService
from services.settings_service import SettingsService


def _new_controller(settings_service=None):
    return LeftoversController(activity_service=ActivityService(), settings_service=settings_service)


def test_controller_accepts_settings_service():
    """LeftoversController must accept a settings_service argument."""
    ss = SettingsService(config_path=os.path.join(tempfile.mkdtemp(), "s.json"))
    ctrl = _new_controller(settings_service=ss)
    assert ctrl.settings_service is ss


def test_load_roots_returns_configured_list():
    """load_roots() must return the roots stored in settings_service."""
    ss = SettingsService(config_path=os.path.join(tempfile.mkdtemp(), "s.json"))
    ss.set("leftovers_scan_roots", [r"C:\Users\Public\Downloads", r"C:\Temp"])
    ctrl = _new_controller(settings_service=ss)

    roots = ctrl.load_roots()
    assert roots == [r"C:\Users\Public\Downloads", r"C:\Temp"]


def test_load_roots_defaults_to_empty_when_unset():
    """load_roots() must return [] when no roots have been configured."""
    ss = SettingsService(config_path=os.path.join(tempfile.mkdtemp(), "s.json"))
    ctrl = _new_controller(settings_service=ss)
    assert ctrl.load_roots() == []


def test_load_roots_persists_and_scan_uses_them():
    """load_roots() must feed the configured roots into the service."""
    ss = SettingsService(config_path=os.path.join(tempfile.mkdtemp(), "s.json"))
    ss.set("leftovers_scan_roots", [r"C:\Temp"])
    ctrl = _new_controller(settings_service=ss)

    assert ctrl.load_roots() == [r"C:\Temp"]
    # After load, the controller's approved roots must match what was loaded.
    assert ctrl.get_approved_roots() == [r"C:\Temp"]


def test_scan_with_configured_roots_finds_items():
    """A scan must run against the configured roots and return items."""
    tmp = tempfile.mkdtemp()
    with open(os.path.join(tmp, "leftover_file.txt"), "w") as f:
        f.write("leftover data")

    ss = SettingsService(config_path=os.path.join(tempfile.mkdtemp(), "s.json"))
    ss.set("leftovers_scan_roots", [tmp])
    ctrl = _new_controller(settings_service=ss)
    ctrl.load_roots()

    result = ctrl.scan()
    assert result["error"] is None
    assert result["item_count"] >= 1
    assert any("leftover_file.txt" in i["name"] for i in result["items"])


def test_scan_with_no_roots_returns_empty_gracefully():
    """A scan with no configured roots must not crash and returns zero items."""
    ss = SettingsService(config_path=os.path.join(tempfile.mkdtemp(), "s.json"))
    ctrl = _new_controller(settings_service=ss)
    ctrl.load_roots()

    result = ctrl.scan()
    assert result["error"] is None
    assert result["item_count"] == 0
    assert result["items"] == []