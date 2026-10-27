#!/usr/bin/env python3
"""Generate the test file for dashboard metrics."""

import os

test_dir = r"d:/Windows app/PC-Toolbox/tests"
os.makedirs(test_dir, exist_ok=True)

filepath = os.path.join(test_dir, "test_dashboard_metrics.py")

content = """#!/usr/bin/env python3
\"\"\"Headless unit tests for dashboard metric card data binding.\"\"\"

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import unittest
from unittest.mock import Mock, patch
from views.dashboard import DashboardView


class MockTheme:
    class Colors:
        deep_background = "#1a1a1a"
        secondary_panel = "#2a2a2a"
        glass_panel = "#3a3a3a"
        primary_text = "#ffffff"
        secondary_text = "#cccccc"
        muted_text = "#888888"
        blue_accent = "#007acc"
        green_accent = "#00cc00"
        orange_accent = "#ff8800"
        red_accent = "#ff0000"
        border = "#444444"
        hover_state = "#3a3a3a"
    colors = Colors


class MockNavigation:
    def navigate_to(self): pass


class TestDashboardMetricsHeadless(unittest.TestCase):
    def setUp(self):
        self.mock_theme = MockTheme()
        self.mock_navigation = MockNavigation()
        self.mock_master = Mock()
        self.mock_master.theme = self.mock_theme
        self.mock_master._last_child_ids = {}
        self.patcher = patch("views.dashboard.ctk", autospec=True)
        self.mock_ctk = self.patcher.start()
        self.mock_ctk.CTkFrame.return_value = Mock()
        self.mock_ctk.CTkScrollableFrame.return_value = Mock()
        self.mock_ctk.CTkLabel.return_value = Mock()
        self.mock_ctk.CTkProgressBar.return_value = Mock()
        self.mock_ctk.CTkButton.return_value = Mock()
        self.dashboard = DashboardView(self.mock_master, self.mock_navigation)

    def tearDown(self):
        self.patcher.stop()

"""

with open(filepath, "w") as f:
    f.write(content)

print(f"Created minimal test file at {filepath}")