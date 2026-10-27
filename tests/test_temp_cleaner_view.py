import unittest
from unittest.mock import MagicMock, patch
import customtkinter as ctk
from views.temp_cleaner import TempCleanerView
class TestTempCleanerView(unittest.TestCase):
    def setUp(self):
        # Mock master widget (CTk) for the view
        self.master = MagicMock(spec=ctk.CTk)
        # Add required attributes for customtkinter
        self.master.tk = MagicMock()
        self.master.children = MagicMock()
        self.master.winfo_screenwidth = MagicMock(return_value=1920)
        self.master.winfo_screenheight = MagicMock(return_value=1080)
        # Create mock navigation with activity_service and controller
        self.mock_activity_service = MagicMock()
        self.mock_controller = MagicMock()
        self.mock_navigation = MagicMock()
        self.mock_navigation.activity_service = self.mock_activity_service
        self.mock_navigation.temp_cleaner_controller = self.mock_controller
        try:
            # Create the view
            self.view = TempCleanerView(self.master, self.mock_navigation)
        except Exception as e:
            self.skipTest(f"Unable to create view due to GUI requirements: {e}")

    def test_initialization(self):
        # Check that the view has the correct attributes
        self.assertIsNotNone(self.view.act)
        self.assertIsNotNone(self.view.ctrl)
        self.assertIsInstance(self.view, ctk.CTkFrame)

    def test_idle_state(self):
        # Ensure idle state sets scanning to False
        self.view._idle()
        self.assertFalse(self.view._scanning)
        self.assertFalse(self.view._user_cancel)
        # Check button states
        self.assertEqual(self.view.scan_b['state'], 'normal')
        self.assertEqual(self.view.can_b['state'], 'disabled')

    def test_scanning_state(self):
        self.view._scan_st()
        self.assertTrue(self.view._scanning)
        self.assertFalse(self.view._user_cancel)
        self.assertEqual(self.view.scan_b['state'], 'disabled')
        self.assertEqual(self.view.can_b['state'], 'normal')

    def test_completion_state_with_results(self):
        mock_results = {
            'file_count': 5,
            'total_size': 1024,
            'errors': ['error1', 'error2'],
            'skipped': ['skip1'],
            'files': []
        }
        self.view._comp_st(mock_results)
        self.assertFalse(self.view._scanning)
        self.assertEqual(self.view.scan_b['state'], 'normal')
        self.assertEqual(self.view.can_b['state'], 'disabled')

    def test_cancelled_state(self):
        self.view._can_st()
        self.assertTrue(self.view._user_cancel)
        self.assertEqual(self.view.scan_b['state'], 'normal')
        self.assertEqual(self.view.can_b['state'], 'disabled')

    def test_scan_method_starts_thread(self):
        # Mock the thread start
        with patch.object(threading.Thread, 'start') as mock_start:
            self.view._scan()
            mock_start.assert_called_once()

    def test_cancel_method_calls_controller(self):
        self.view._scanning = True
        self.view._cancel()
        self.mock_controller.cancel_scan.assert_called_once()
        self.assertTrue(self.view._user_cancel)

    def test_run_method_updates_ui(self):
        # Mock controller.scan to return a result
        mock_result = {'file_count': 3, 'total_size': 500, 'errors': [], 'skipped': [], 'files': []}
        self.mock_controller.scan.return_value = mock_result
        self.view._run()
        # Since _run calls after(0, self._done, res), we need to simulate the mainloop?
        # In a test environment, we can call _done directly after _run.
        # Actually, _run schedules the _done call via after, but we can't easily run the mainloop.
        # We'll mock the after method to call _done immediately.
        with patch.object(self.view, 'after') as mock_after:
            # Configure mock_after to call the callback immediately
            def call_callback(callback, *args):
                callback(*args)
            mock_after.side_effect = call_callback
            self.view._run()
            # Ensure after was called with _done
            mock_after.assert_called_once_with(0, self.view._done, mock_result)

    def test_done_calls_comp_state(self):
        mock_result = {'file_count': 10, 'total_size': 2048, 'errors': [], 'skipped': [], 'files': []}
        with patch.object(self.view, '_comp_st') as mock_comp:
            self.view._done(mock_result)
            mock_comp.assert_called_once_with(mock_result)

if __name__ == '__main__':
    unittest.main()