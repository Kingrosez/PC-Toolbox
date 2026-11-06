import unittest
from unittest.mock import MagicMock, patch

class MockTheme:
    colors = {
        'deep_background': '#080D1C', 'glass_panel': '#101A32',
        'border': '#1E3054', 'blue_accent': '#248BFF',
        'red_accent': '#FF5364', 'green_accent': '#24D99A',
        'secondary_panel': '#14213D', 'hover_state': '#1B2A4E',
        'primary_text': '#F0F4FF', 'secondary_text': '#A7B7D9',
        'muted_text': '#64779E', 'purple_accent': '#9B5CFF',
        'cyan_accent': '#19C7F4', 'orange_accent': '#FF9B35',
        'white': '#FFFFFF',
    }

def _make_mock_widget():
    w = MagicMock()
    w.configure = MagicMock()
    w.grid = MagicMock()
    w.pack = MagicMock()
    w.destroy = MagicMock()
    w.winfo_children = MagicMock(return_value=[])
    w.set = MagicMock()
    w.get = MagicMock(return_value='')
    w.insert = MagicMock()
    w.delete = MagicMock()
    return w

class TestTempCleanerView(unittest.TestCase):
    def setUp(self):
        self.mock_master = MagicMock()
        self.mock_master.theme = MockTheme()
        self.mock_activity_service = MagicMock()
        self.mock_controller = MagicMock()
        self.mock_controller.scan.return_value = {
            'files': [], 'total_size': 0, 'file_count': 0,
            'errors': [], 'skipped': [], 'locations_scanned': 0,
            'scan_duration': 0.0, 'error': None,
        }
        self.mock_controller.get_approved_roots.return_value = ['/tmp']
        self.mock_navigation = MagicMock()
        self.mock_navigation.activity_service = self.mock_activity_service
        self.mock_navigation.temp_cleaner_controller = self.mock_controller
        import customtkinter as ctk
        import views.temp_cleaner as temp_cleaner_module
        self._patchers = [
            patch.object(ctk.CTkFrame, '__init__', lambda *a, **k: None),
            patch.object(temp_cleaner_module.TempCleanerView, '_setup_ui', lambda self: None),
            patch.object(temp_cleaner_module.TempCleanerView, 'grid_rowconfigure', lambda *a, **k: None),
            patch.object(temp_cleaner_module.TempCleanerView, 'grid_columnconfigure', lambda *a, **k: None),
        ]
        for p in self._patchers: p.start()
        with patch.object(temp_cleaner_module.TempCleanerView, '_idle', lambda self: None):
            self.view = temp_cleaner_module.TempCleanerView(self.mock_master, self.mock_navigation)
        self.view.scan_b = _make_mock_widget()
        self.view.can_b = _make_mock_widget()
        self.view.quick_b = _make_mock_widget()
        self.view.status_lbl = _make_mock_widget()
        self.view._card_cache = {
            'files_found': _make_mock_widget(), 'total_size': _make_mock_widget(),
            'locations_scanned': _make_mock_widget(), 'scan_time': _make_mock_widget(),
        }
        self.view._filter_buttons = {}
        self.view._empty_state_label = None
        self.view.table_body = _make_mock_widget()
        self.view._all_files = []
        self.view._filtered_files = []
        self.view._selected_paths = set()
        self.view._pending_callbacks = []
        self._method_patchers = [
            patch.object(self.view, '_apply_filters', lambda: None),
            patch.object(self.view, '_update_selection_summary', lambda: None),
            patch.object(self.view, '_update_pagination', lambda: None),
            patch.object(self.view, '_show_empty_state', lambda: None),
            patch.object(self.view, '_clear_table', lambda: None),
            patch.object(self.view, '_render_page', lambda: None),
            patch.object(self.view, '_update_preview_summary', lambda r: None),
        ]
        for p in self._method_patchers: p.start()
    def tearDown(self):
        for p in self._method_patchers: p.stop()
        for p in self._patchers: p.stop()
    def test_initialization(self):
        self.assertIsNotNone(self.view.act); self.assertIsNotNone(self.view.ctrl)
    def test_idle_state(self):
        self.view._idle()
        self.assertFalse(self.view._scanning); self.assertFalse(self.view._user_cancel)
        self.view.scan_b.configure.assert_called_with(state='normal')
        self.view.can_b.configure.assert_called_with(state='disabled')
    def test_scanning_state(self):
        self.view._scan_st()
        self.assertTrue(self.view._scanning); self.assertFalse(self.view._user_cancel)
        self.view.scan_b.configure.assert_called_with(state='disabled')
        self.view.can_b.configure.assert_called_with(state='normal')
    def test_completion_state_with_results(self):
        mock_results = {'file_count': 5, 'total_size': 1024, 'errors': ['e1'], 'skipped': ['s1'], 'files': []}
        self.view._comp_st(mock_results)
        self.assertFalse(self.view._scanning)
        self.view.scan_b.configure.assert_called_with(state='normal')
        self.view.can_b.configure.assert_called_with(state='disabled')
    def test_cancelled_state(self):
        self.view._can_st()
        self.assertTrue(self.view._user_cancel)
        self.view.scan_b.configure.assert_called_with(state='normal')
        self.view.can_b.configure.assert_called_with(state='disabled')
    def test_scan_method_starts_thread(self):
        with patch('threading.Thread.start') as mock_start:
            self.view._scan(); mock_start.assert_called_once()
    def test_cancel_method_calls_controller(self):
        self.view._scanning = True; self.view._cancel()
        self.mock_controller.cancel_scan.assert_called_once()
        self.assertTrue(self.view._user_cancel)
    def test_run_method_calls_controller(self):
        mock_result = {'file_count': 3, 'total_size': 500, 'errors': [], 'skipped': [], 'files': []}
        self.mock_controller.scan.return_value = mock_result
        with patch.object(self.view, 'after') as mock_after:
            mock_after.side_effect = lambda _delay, cb, *args: cb(*args)
            self.view._run(); self.mock_controller.scan.assert_called_once()
    def test_done_calls_comp_state(self):
        mock_result = {'file_count': 10, 'total_size': 2048, 'errors': [], 'skipped': [], 'files': []}
        with patch.object(self.view, '_comp_st') as mock_comp:
            with patch.object(self.view, '_idle'):
                self.view._done(mock_result); mock_comp.assert_called_once_with(mock_result)

    def test_quick_clean_targets_filters_likely_temp_files(self):
        files = [
            {'path': 'C:\\Temp\\a.tmp', 'category': 'Applications', 'intel': {'purpose': 'Temporary file'}},
            {'path': 'C:\\Temp\\b.txt', 'category': 'Applications', 'intel': {'purpose': 'Document'}},
            {'path': 'C:\\Temp\\cache.dat', 'category': 'Caches', 'intel': {}},
            {'path': 'C:\\Temp\\required.tmp', 'category': 'Applications', 'intel': {'purpose': 'Temporary file', 'required': True}},
            {'path': 'C:\\Temp\\active.tmp', 'category': 'Applications', 'intel': {'purpose': 'Temporary file', 'active': True}},
        ]
        targets = self.view._quick_clean_targets(files)
        self.assertEqual([f['path'] for f in targets], ['C:\\Temp\\a.tmp', 'C:\\Temp\\cache.dat'])

    def test_clean_files_warns_for_required_and_active(self):
        safe = {'path': 'C:\\Temp\\safe.tmp', 'size': 10, 'intel': {}}
        required = {'path': 'C:\\Windows\\Temp\\pending_update.tmp', 'size': 20, 'intel': {}}
        active = {'path': 'C:\\Temp\\active.tmp', 'size': 30, 'intel': {}}
        protected = [
            {'file': required, 'kind': 'required', 'reasons': ['Required by Windows.']},
            {'file': active, 'kind': 'active', 'reasons': ['A running process is using this file.']},
        ]
        self.mock_controller.cleanup.return_value = {
            'deleted_count': 1, 'deleted_bytes': 10, 'skipped': [],
            'errors': [], 'protected': [],
        }
        with patch.object(self.view, '_recheck_candidates', return_value=([safe], 0, 2, protected)), \
                patch('tkinter.messagebox.askyesno', return_value=True) as mock_ask, \
                patch('tkinter.messagebox.showinfo'), \
                patch('views.temp_cleaner.threading.Thread'):
            result = self.view._clean_files([safe, required, active], mode='selected')
        self.assertTrue(result)
        detail = mock_ask.call_args[0][1]
        self.assertIn('WARNING', detail)
        self.assertIn('Required by Windows', detail)
        self.assertIn('Active or in use', detail)
        self.mock_controller.cleanup.assert_called_once()
        passed_files = self.mock_controller.cleanup.call_args[0][0]
        self.assertEqual(
            [f['path'] for f in passed_files], ['C:\\Temp\\safe.tmp']
        )

    def test_clean_files_warns_when_all_files_are_protected(self):
        required = {'path': 'C:\\Windows\\Temp\\pending_update.tmp', 'size': 20, 'intel': {}}
        protected = [
            {'file': required, 'kind': 'required', 'reasons': ['Required by Windows.']},
        ]
        with patch.object(self.view, '_recheck_candidates', return_value=([], 0, 1, protected)), \
                patch('tkinter.messagebox.showwarning') as mock_warn, \
                patch('tkinter.messagebox.showinfo'):
            result = self.view._clean_files([required], mode='quick')
        self.assertFalse(result)
        mock_warn.assert_called_once()
        message = mock_warn.call_args[0][1]
        self.assertIn('WARNING', message)
        self.assertIn('Required by Windows', message)
        self.mock_controller.cleanup.assert_not_called()

    def test_quick_clean_without_scan_requests_scan(self):
        self.view._all_files = []
        with patch.object(self.view, '_scan') as mock_scan:
            with patch('tkinter.messagebox.askyesno', return_value=True):
                self.view._quick_clean()
        self.assertTrue(self.view._quick_clean_pending)
        mock_scan.assert_called_once()

    def test_done_runs_pending_quick_clean_after_scan(self):
        with patch.object(self.view, '_comp_st'), \
                patch.object(self.view, '_update_preview_summary'), \
                patch.object(self.view, '_quick_clean_ready') as mock_ready:
            self.view._quick_clean_pending = True
            with patch.object(self.view, 'after') as mock_after:
                mock_after.side_effect = lambda _delay, cb, *args: cb(*args)
                self.view._done({'error': None})
        mock_ready.assert_called_once()

if __name__ == '__main__':
    unittest.main()
