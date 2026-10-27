#!/usr/bin/env python3
"""Refactored tests for dashboard metric calculations."""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
from views.dashboard_helpers import format_uptime, calculate_storage_metrics

class TestDashboardCalculations(unittest.TestCase):
    """Test pure calculation functions."""

    def test_format_uptime(self):
        self.assertEqual(format_uptime(0), "0m")
        self.assertEqual(format_uptime(60), "1m")
        self.assertEqual(format_uptime(3660), "1h 1m")
        self.assertEqual(format_uptime(90000), "1d 1h 0m")

    def test_calculate_storage_metrics(self):
        drives = [
            {"accessible": True, "used_bytes": 1024**4, "total_bytes": 2 * 1024**4},
            {"accessible": False, "used_bytes": 100, "total_bytes": 200}
        ]
        metrics = calculate_storage_metrics(drives)
        self.assertEqual(metrics["total_used_tb"], 1.0)
        self.assertEqual(metrics["total_cap_tb"], 2.0)
        self.assertEqual(metrics["percent_used"], 50.0)
        self.assertEqual(metrics["volume_count"], 1)

    def test_calculate_storage_empty(self):
        metrics = calculate_storage_metrics([])
        self.assertEqual(metrics["percent_used"], 0)
        self.assertEqual(metrics["volume_count"], 0)

if __name__ == "__main__":
    unittest.main()
