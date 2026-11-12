"""Tests for LeftoversView scan-roots configuration dialog."""

import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

sys.path.insert(0, "d:/Windows app/PC-Toolbox")

import views.leftovers as leftovers_module


def _make_view():
    """Build a LeftoversView without a real tkinter root (headless)."""
    view = leftovers_module.LeftoversView.__new__(leftovers_module.LeftoversView)
    view.theme = MagicMock()
    view.theme.colors = {
        "deep_background": "#111",
        "primary_text": "#fff",
        "secondary_text": "#999",
        "glass_panel": "#222",
        "blue_accent": "#1570D6",
        "hover_state": "#333",
        "border": "#444",
        "orange_accent": "#ff8800",
        "red_accent": "#ff4444",
        "muted_text": "#777",
        "green_accent": "#44ff44",
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


def test_open_settings_shows_configured_roots():
    """_open_settings must display the controller's approved roots."""
    view = _make_view()
    view.ctrl.get_approved_roots.return_value = [r"C:\Temp", r"C:\Users\Public\Downloads"]

    with patch("views.leftovers.ctk.CTkToplevel"), \
            patch("views.leftovers.ctk.CTkLabel"), \
            patch("views.leftovers.ctk.CTkFont"), \
            patch("views.leftovers.ctk.CTkTextbox") as mock_textbox, \
            patch("views.leftovers.ctk.CTkButton"):
        view._open_settings()

    inserted = [c.args[1] for c in mock_textbox.return_value.insert.call_args_list if len(c.args) >= 2]
    assert any("Temp" in t and "Downloads" in t for t in inserted)


def test_open_settings_shows_no_roots_message_when_empty():
    """_open_settings must show a placeholder when no roots are configured."""
    view = _make_view()
    view.ctrl.get_approved_roots.return_value = []

    with patch("views.leftovers.ctk.CTkToplevel"), \
            patch("views.leftovers.ctk.CTkLabel"), \
            patch("views.leftovers.ctk.CTkFont"), \
            patch("views.leftovers.ctk.CTkTextbox") as mock_textbox, \
            patch("views.leftovers.ctk.CTkButton"):
        view._open_settings()

    inserted = [c.args[1] for c in mock_textbox.return_value.insert.call_args_list if len(c.args) >= 2]
    assert any("No roots configured" in t for t in inserted)


def test_configure_roots_writes_to_settings_and_applies():
    """_configure_roots must persist roots via settings_service and apply them."""
    view = _make_view()
    view.ctrl = MagicMock()
    view.ctrl.get_approved_roots.return_value = []
    view.navigation.settings_service = MagicMock()

    view._roots_textbox = MagicMock()
    view._roots_textbox.get.return_value = "C:\\Temp\nC:\\Users\\Public\\Downloads"
    view._roots_dialog = MagicMock()

    with patch("tkinter.messagebox.askyesno", return_value=True):
        view._configure_roots()

    view.ctrl.set_roots.assert_called_once()
    roots = view.ctrl.set_roots.call_args[0][0]
    assert roots == [r"C:\Temp", r"C:\Users\Public\Downloads"]
    view.navigation.settings_service.set.assert_called_once()
    assert view.navigation.settings_service.set.call_args[0][0] == "leftovers_scan_roots"
    view._roots_dialog.destroy.assert_called_once()


def test_configure_roots_cancels_on_user_decline():
    """_configure_roots must do nothing when the user declines the prompt."""
    view = _make_view()
    view.ctrl = MagicMock()
    view.ctrl.get_approved_roots.return_value = []
    view.navigation.settings_service = MagicMock()

    view._roots_textbox = MagicMock()
    view._roots_textbox.get.return_value = "C:\\Temp"
    view._roots_dialog = MagicMock()

    with patch("tkinter.messagebox.askyesno", return_value=False):
        view._configure_roots()

    view.ctrl.set_roots.assert_not_called()
    view.navigation.settings_service.set.assert_not_called()
    view._roots_dialog.destroy.assert_called_once()