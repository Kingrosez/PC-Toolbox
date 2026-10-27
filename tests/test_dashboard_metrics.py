#!/usr/bin/env python3
"""Tests for dashboard metric helpers including CPU formatting and refresh coordination."""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import unittest
from views.dashboard_helpers import update_cpu_card, RefreshLock

class TestCpuCardUpdate(unittest.TestCase):
    """Test CPU metric calculation and formatting helper."""

    def setUp(self):
        self.colors = {
            "red_accent": "#ff0000",
            "orange_accent": "#ff8800",
            "green_accent": "#00cc00",
        }

    def test_zero_percent(self):
        value, progress, status, color = update_cpu_card(0.0, self.colors)
        self.assertEqual(value, "0.0%")
        self.assertEqual(progress, 0.0)
        self.assertEqual(status, "Normal")
        self.assertEqual(color, self.colors["green_accent"])

    def test_normal_range(self):
        value, progress, status, color = update_cpu_card(45.5, self.colors)
        self.assertEqual(value, "45.5%")
        self.assertAlmostEqual(progress, 0.455)
        self.assertEqual(status, "Normal")
        self.assertEqual(color, self.colors["green_accent"])

    def test_warning_threshold(self):
        value, progress, status, color = update_cpu_card(75.0, self.colors)
        self.assertEqual(status, "Warning")
        self.assertEqual(color, self.colors["orange_accent"])

    def test_critical_threshold(self):
        value, progress, status, color = update_cpu_card(100.0, self.colors)
        self.assertEqual(status, "Critical")
        self.assertEqual(color, self.colors["red_accent"])

    def test_boundary_values(self):
        _, _, s70, _ = update_cpu_card(70.0, self.colors)
        self.assertEqual(s70, "Normal")
        _, _, s70p, _ = update_cpu_card(70.1, self.colors)
        self.assertEqual(s70p, "Warning")
        _, _, s90, _ = update_cpu_card(90.0, self.colors)
        self.assertEqual(s90, "Warning")
        _, _, s90p, _ = update_cpu_card(90.1, self.colors)
        self.assertEqual(s90p, "Critical")


class TestRefreshCoordination(unittest.TestCase):
    """Test refresh lock behavior for overlap prevention."""

    def test_initial_state(self):
        lock = RefreshLock()
        self.assertFalse(lock.in_progress)

    def test_first_acquisition_accepted(self):
        lock = RefreshLock()
        self.assertTrue(lock.acquire())
        self.assertTrue(lock.in_progress)

    def test_overlapping_rejected(self):
        lock = RefreshLock()
        lock.acquire()
        self.assertFalse(lock.acquire())
        self.assertTrue(lock.in_progress)

    def test_release_after_success(self):
        lock = RefreshLock()
        lock.acquire()
        lock.release()
        self.assertFalse(lock.in_progress)
        self.assertTrue(lock.acquire())

    def test_release_after_failure(self):
        lock = RefreshLock()
        lock.acquire()
        try:
            raise RuntimeError("fail")
        except RuntimeError:
            pass
        finally:
            lock.release()
        
        self.assertFalse(lock.in_progress)
        self.assertTrue(lock.acquire())

    def test_release_idempotent(self):
        """Releasing multiple times should not change state."""
        lock = RefreshLock()
        lock.acquire()
        lock.release()
        lock.release()
        self.assertFalse(lock.in_progress)
        self.assertTrue(lock.acquire())

    def test_error_handling_does_not_hang(self):
        """Simulate a refresh task that errors and ensure lock is released."""
        lock = RefreshLock()
        self.assertTrue(lock.acquire())
        try:
            raise RuntimeError("simulated error")
        except RuntimeError:
            pass
        finally:
            lock.release()
        self.assertFalse(lock.in_progress)


if __name__ == "__main__":
    unittest.main()
