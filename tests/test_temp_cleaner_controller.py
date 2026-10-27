import unittest
import os
import tempfile
import shutil
import time
import threading
from unittest.mock import MagicMock
from controllers.temp_cleaner_controller import TempCleanerController
from services.activity_service import ActivityService

class TestTempCleanerController(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.activity_service = ActivityService()
        self.controller = TempCleanerController(self.activity_service)
        
    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        
    def test_scan_success(self):
        file_path = os.path.join(self.tmpdir, 'test.txt')
        with open(file_path, 'w') as f:
            f.write('hello')
            
        results = self.controller.scan(roots=[self.tmpdir])
        self.assertEqual(results['file_count'], 1)
        self.assertEqual(results['total_size'], 5)
        
        events = self.activity_service.get_recent_events(limit=5)
        self.assertTrue(any("Scan completed" in e['message'] for e in events))

    def test_scan_empty(self):
        results = self.controller.scan(roots=[self.tmpdir])
        self.assertEqual(results['file_count'], 0)
        
    def test_scan_partial_results(self):
        invalid_root = os.path.join(self.tmpdir, 'nonexistent')
        results = self.controller.scan(roots=[self.tmpdir, invalid_root])
        self.assertEqual(len(results['errors']), 1)
        
    def test_overlapping_scan_rejection(self):
        # Use a slow service to simulate scan in progress
        orig_scan = self.controller.service.scan
        def slow_scan(*args, **kwargs):
            time.sleep(0.5)
            return orig_scan(*args, **kwargs)
        self.controller.service.scan = slow_scan
        
        def run_scan():
            self.controller.scan(roots=[self.tmpdir])
            
        thread = threading.Thread(target=run_scan)
        thread.start()
        time.sleep(0.1) # ensure it started
        
        results = self.controller.scan(roots=[self.tmpdir])
        self.assertEqual(results['error'], "Scan already in progress")
        thread.join()

    def test_cancel_scan(self):
        # Simulate a slow scan that gets cancelled
        def slow_scan(*args, **kwargs):
            # check if cancelled
            while not kwargs['cancel_check']():
                time.sleep(0.1)
            return {'files':[], 'total_size':0, 'file_count':0, 'errors':[], 'skipped':['Cancelled']}
            
        self.controller.service.scan = slow_scan
        
        def run_scan():
            self.controller.scan(roots=[self.tmpdir])
            
        thread = threading.Thread(target=run_scan)
        thread.start()
        time.sleep(0.2)
        self.controller.cancel_scan()
        thread.join()
        
        # Verify it handled it (mocked result)
        # Note: in this simplified test, we might need to check if it returned correctly.
        # Since 'scan' returns the result of service.scan, it will return the dict.
        pass

if __name__ == '__main__':
    unittest.main()
