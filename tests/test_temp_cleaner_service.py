"""Unit tests for TempCleanerService."""

import os
import tempfile
import unittest
from services.temp_cleaner_service import TempCleanerService


class TestTempCleanerService(unittest.TestCase):
    def setUp(self):
        # Create temporary directory structure
        self.tmpdir = tempfile.mkdtemp()
        self.subdir = os.path.join(self.tmpdir, 'sub')
        os.makedirs(self.subdir)
        # Create files
        self.file1 = os.path.join(self.tmpdir, 'a.txt')
        with open(self.file1, 'w') as f:
            f.write('hello')
        self.file2 = os.path.join(self.subdir, 'b.bin')
        with open(self.file2, 'wb') as f:
            f.write(b'\x00' * 1024)
        self.service = TempCleanerService(roots=[self.tmpdir])

    def tearDown(self):
        # Cleanup
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_valid_files_discovered(self):
        result = self.service.scan()
        paths = {f['path'] for f in result['files']}
        self.assertIn(os.path.abspath(self.file1), paths)
        self.assertIn(os.path.abspath(self.file2), paths)
        self.assertEqual(result['file_count'], 2)

    def test_total_size_and_count(self):
        result = self.service.scan()
        expected_size = 5 + 1024
        self.assertEqual(result['total_size'], expected_size)
        self.assertEqual(result['file_count'], 2)

    def test_duplicate_roots_no_double_count(self):
        service = TempCleanerService(roots=[self.tmpdir, self.tmpdir])
        result = service.scan()
        self.assertEqual(result['file_count'], 2)

    def test_symlink_skipped(self):
        # Symlink support may vary; test only if os.symlink is available
        if hasattr(os, 'symlink'):
            link_path = os.path.join(self.tmpdir, 'link_to_a')
            try:
                os.symlink(self.file1, link_path)
                result = self.service.scan()
                # Symlink itself should be skipped, target already counted once
                paths = [f['path'] for f in result['files']]
                self.assertNotIn(os.path.abspath(link_path), paths)
                # Count remains 2
                self.assertEqual(result['file_count'], 2)
            except OSError:
                self.skipTest('Symlink creation not permitted')
        else:
            self.skipTest('Symlink not supported')

    def test_missing_root_handled_gracefully(self):
        service = TempCleanerService(roots=['/nonexistent/path/12345'])
        result = service.scan()
        self.assertEqual(result['file_count'], 0)
        self.assertTrue(len(result['errors']) > 0)

    def test_invalid_roots_rejected(self):
        service = TempCleanerService(roots=['', '   ', '/'])
        result = service.scan()
        self.assertEqual(result['file_count'], 0)

    def test_files_outside_approved_roots_not_scanned(self):
        other_dir = tempfile.mkdtemp()
        other_file = os.path.join(other_dir, 'c.txt')
        with open(other_file, 'w') as f:
            f.write('outside')
        try:
            result = self.service.scan()
            paths = {f['path'] for f in result['files']}
            self.assertNotIn(os.path.abspath(other_file), paths)
        finally:
            import shutil
            shutil.rmtree(other_dir, ignore_errors=True)

    def test_no_deletion_on_scan(self):
        self.assertTrue(os.path.exists(self.file1))
        result = self.service.scan()
        self.assertTrue(os.path.exists(self.file1))
        self.assertGreater(result['file_count'], 0)


if __name__ == '__main__':
    unittest.main()
