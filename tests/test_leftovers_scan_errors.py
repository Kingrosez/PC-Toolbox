"""Tests for scan-error surfacing in the Leftovers view.

Covers the plan's Review Focus item 2: permission denied and
root-not-accessible errors collected during a scan must reach the UI,
so a failing scan is not mistaken for a clean one with zero items.
"""

import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

sys.path.insert(0, "d:/Windows app/PC-Toolbox")

import views.leftovers as leftovers_module


def _make_view():
    view = leftovers_module.LeftoversView.__new__(leftovers_module.LeftoversView)
    view.theme = MagicMock()
    view.theme.colors = {
        "deep_background": "#111", "primary_text": "#fff", "secondary_text": "#999",
        "glass_panel": "#222", "blue_accent": "#1570D6", "hover_state": "#333",
        "border": "#444", "orange_accent": "#ff8800", "red_accent": "#ff4444",
        "muted_text": "#777", "green_accent": "#44ff44",
    }
    view.master = MagicMock()
    view.master.theme = view.theme
    view.navigation = MagicMock()
    view.ctrl = MagicMock()
    view.ctrl.get_approved_roots.return_value = []
    view.ctrl.get_summary.return_value = {
        "total_size_bytes": None, "apps_found": 0, "size_known": False,
    }
    view.scan_b = MagicMock()
    view.can_b = MagicMock()
    view.updated_lbl = MagicMock()
    view._card_cache = {"count": MagicMock(), "size": MagicMock(), "apps": MagicMock(), "time": MagicMock()}
    view._items = []
    view._scan_errors = []
    view._error_banner = MagicMock()
    view._error_text = MagicMock()
    view._apply_filters = MagicMock()
    view._scan_th = None
    return view


def test_done_surfaces_scan_errors_in_banner():
    """_done must show the error banner when the scan reported problems."""
    view = _make_view()
    view._error_banner.grid_remove = MagicMock()

    view._done({
        "items": [], "item_count": 0, "scan_duration": 1.2,
        "errors": ["Permission denied: C:\\Windows\\WinSxS"],
    })

    view._error_banner.grid.assert_called_once()
    view._error_banner.grid_remove.assert_not_called()
    text = view._error_text.configure.call_args.kwargs.get("text", "")
    assert "Permission denied" in text
    assert "1 problem" in text


def test_done_hides_banner_when_no_errors():
    """_done must hide the error banner when the scan was clean."""
    view = _make_view()
    view._error_banner.grid = MagicMock()

    view._done({
        "items": [], "item_count": 0, "scan_duration": 0.5,
        "errors": [],
    })

    view._error_banner.grid_remove.assert_called_once()
    view._error_banner.grid.assert_not_called()


def test_done_keeps_errors_across_filter_changes():
    """Scan errors must persist on the view so the banner survives filtering."""
    view = _make_view()
    view._error_banner.grid_remove = MagicMock()

    view._done({
        "items": [], "item_count": 0, "scan_duration": 1.0,
        "errors": ["Root not accessible: Z:\\Missing"],
    })

    assert view._scan_errors == ["Root not accessible: Z:\\Missing"]
    # Re-rendering the table (e.g. after a filter change) must not clear them.
    view._apply_filters()
    assert view._scan_errors == ["Root not accessible: Z:\\Missing"]


def test_configure_roots_warns_when_save_fails():
    """A failed settings save must produce a warning, not silent loss."""
    view = leftovers_module.LeftoversView.__new__(leftovers_module.LeftoversView)
    view.theme = MagicMock()
    view.theme.colors = {
        "deep_background": "#111", "primary_text": "#fff", "secondary_text": "#999",
        "glass_panel": "#222", "blue_accent": "#1570D6", "hover_state": "#333",
        "border": "#444", "orange_accent": "#ff8800", "red_accent": "#ff4444",
        "muted_text": "#777", "green_accent": "#44ff44",
    }
    view.master = MagicMock()
    view.master.theme = view.theme
    view.navigation = MagicMock()
    view.navigation.settings_service = MagicMock()
    view.navigation.settings_service.save.return_value = False
    view.ctrl = MagicMock()
    view.ctrl.get_approved_roots.return_value = []
    view._roots_textbox = MagicMock()
    view._roots_textbox.get.return_value = "C:\\Temp"
    view._roots_dialog = MagicMock()

    import tempfile
    tmp = tempfile.mkdtemp()
    with patch("tkinter.messagebox.askyesno", return_value=True), \
            patch("tkinter.messagebox.showwarning") as mock_warn:
        view._configure_roots()

    view.ctrl.set_roots.assert_called_once()
    mock_warn.assert_called_once()
    assert "could not be saved" in mock_warn.call_args[0][1]