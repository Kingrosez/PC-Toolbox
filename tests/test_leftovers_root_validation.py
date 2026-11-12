"""Tests for root validation in the Leftovers Configure Roots dialog.

Covers the plan's Review Focus items 1 (invalid paths) and 5 (path traversal):
users typing `C:\\`, `..\\..\\Windows`, relative paths, or garbage must get a
rejection, never a persisted root that later hangs a scan.
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
    view._scanning = False
    view._scan_th = None
    view._items = []
    view._filtered = []
    view._selected_ids = set()
    view._selected_item = None
    view._search_text = ""
    view._category = "All Items"
    view._type_filter = "All Types"
    view._page = 1
    view._per_page = 25
    view._last_updated = None
    view._cleanup_scanning = False
    view._cleanup_cleaning = False
    view._cleanup_items = []
    view._cleanup_by_id = {}
    view._cleanup_selected = set()
    view._cleanup_vars = {}
    view._cleanup_progress_queue = MagicMock()
    view._cleanup_poll_id = None
    view._cleanup_admin = False
    view._cleanup_dry_run = MagicMock(value=False)
    view._cleanup_free_space = None
    view._cleanup_log_path = None
    return view


def test_configure_roots_rejects_drive_root():
    """`C:\\` must never be accepted as a scan root."""
    view = _make_view()
    view._roots_textbox = MagicMock()
    view._roots_textbox.get.return_value = "C:\\"
    view._roots_dialog = MagicMock()

    with patch("tkinter.messagebox.askyesno", return_value=True), \
            patch("tkinter.messagebox.showwarning") as mock_warn:
        view._configure_roots()

    view.ctrl.set_roots.assert_not_called()
    view.navigation.settings_service.set.assert_not_called()
    mock_warn.assert_called_once()


def test_configure_roots_rejects_relative_path():
    """Relative paths like `..\\..\\Windows` must be rejected."""
    view = _make_view()
    view._roots_textbox = MagicMock()
    view._roots_textbox.get.return_value = "..\\..\\Windows"
    view._roots_dialog = MagicMock()

    with patch("tkinter.messagebox.askyesno", return_value=True), \
            patch("tkinter.messagebox.showwarning") as mock_warn:
        view._configure_roots()

    view.ctrl.set_roots.assert_not_called()
    mock_warn.assert_called_once()


def test_configure_roots_rejects_nonexistent_path():
    """A path that does not exist on disk must be rejected."""
    view = _make_view()
    view._roots_textbox = MagicMock()
    view._roots_textbox.get.return_value = "Z:\\Does\\Not\\Exist"
    view._roots_dialog = MagicMock()

    with patch("tkinter.messagebox.askyesno", return_value=True), \
            patch("tkinter.messagebox.showwarning") as mock_warn:
        view._configure_roots()

    view.ctrl.set_roots.assert_not_called()
    mock_warn.assert_called_once()


def test_configure_roots_rejects_garbage():
    """Gibberish input must be rejected, not persisted."""
    view = _make_view()
    view._roots_textbox = MagicMock()
    view._roots_textbox.get.return_value = "not a path at all !!!"
    view._roots_dialog = MagicMock()

    with patch("tkinter.messagebox.askyesno", return_value=True), \
            patch("tkinter.messagebox.showwarning") as mock_warn:
        view._configure_roots()

    view.ctrl.set_roots.assert_not_called()
    mock_warn.assert_called_once()


def test_configure_roots_accepts_valid_path():
    """A real, existing directory must be accepted and applied."""
    tmp = tempfile.mkdtemp()
    view = _make_view()
    view._roots_textbox = MagicMock()
    view._roots_textbox.get.return_value = tmp
    view._roots_dialog = MagicMock()

    with patch("tkinter.messagebox.askyesno", return_value=True):
        view._configure_roots()

    view.ctrl.set_roots.assert_called_once()
    assert view.ctrl.set_roots.call_args[0][0] == [tmp]
    view.navigation.settings_service.set.assert_called_once()
    view._roots_dialog.destroy.assert_called_once()


def test_configure_roots_mixed_valid_and_invalid():
    """A mix must keep only the valid root and warn about the invalid one."""
    tmp = tempfile.mkdtemp()
    view = _make_view()
    view._roots_textbox = MagicMock()
    view._roots_textbox.get.return_value = tmp + "\nC:\\"
    view._roots_dialog = MagicMock()

    with patch("tkinter.messagebox.askyesno", return_value=True), \
            patch("tkinter.messagebox.showwarning") as mock_warn:
        view._configure_roots()

    view.ctrl.set_roots.assert_called_once()
    assert view.ctrl.set_roots.call_args[0][0] == [tmp]
    mock_warn.assert_called_once()