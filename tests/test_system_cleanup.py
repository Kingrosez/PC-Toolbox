"""Unit tests for the System Cleanup service and controller."""

import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from controllers.system_cleanup_controller import SystemCleanupController
from services.system_cleanup import (
    AndroidSystemImagesCategory,
    CleanupCategory,
    JetBrainsCategory,
    LargeFilesReportCategory,
    OllamaModelsCategory,
    PackageCachesCategory,
    PathPolicy,
    SafeDeleter,
    TIER_SAFE,
    VSCodeCacheCategory,
    _parse_windows_size,
    format_size,
    parse_jetbrains_folder,
    parse_ollama_list,
    select_jetbrains_targets,
)


class TestPathPolicy(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.file_path = os.path.join(self.root, "file.txt")
        with open(self.file_path, "w", encoding="utf-8") as handle:
            handle.write("data")
        self.policy = PathPolicy([self.root])

    def test_allows_path_under_allowlisted_root(self):
        ok, reason = self.policy.validate(self.file_path)
        self.assertTrue(ok, reason)

    def test_rejects_path_outside_allowlist(self):
        other = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, other, True)
        ok, reason = self.policy.validate(os.path.join(other, "file.txt"))
        self.assertFalse(ok)
        self.assertIn("outside the allowlist", reason)

    def test_rejects_exact_root_for_deletion(self):
        ok, reason = self.policy.validate(self.root)
        self.assertFalse(ok)
        self.assertIn("allowlisted root", reason)

    def test_allows_exact_root_for_contents_operation(self):
        ok, reason = self.policy.validate(self.root, allow_contents_root=True)
        self.assertTrue(ok, reason)

    def test_allows_explicit_exact_root_deletion(self):
        policy = PathPolicy([self.root], allow_exact_roots=[self.root])
        ok, reason = policy.validate(self.root, allow_exact=True)
        self.assertTrue(ok, reason)

    def test_rejects_protected_tree(self):
        protected = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, protected, True)
        policy = PathPolicy([protected], protected_roots=[protected])
        ok, reason = policy.validate(os.path.join(protected, "file.txt"))
        self.assertFalse(ok)
        self.assertIn("Protected", reason)

    def test_rejects_unc_path(self):
        ok, reason = self.policy.validate(r"\\server\share\file.txt")
        self.assertFalse(ok)
        self.assertIn("UNC", reason)

    def test_rejects_filesystem_root(self):
        ok, reason = self.policy.validate(os.path.abspath(os.sep))
        self.assertFalse(ok)
        self.assertIn("filesystem root", reason)


class TestSafeDeleter(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.policy = PathPolicy([self.root])
        self.deleter = SafeDeleter()

    def test_contents_dry_run_does_not_delete(self):
        path = os.path.join(self.root, "keep.txt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("keep")
        result = self.deleter.delete_contents(self.root, self.policy, dry_run=True)
        self.assertEqual(len(result["would_remove"]), 1)
        self.assertTrue(os.path.exists(path))
        self.assertEqual(result["bytes_freed"], 0)

    def test_contents_delete_removes_children_but_keeps_root(self):
        path = os.path.join(self.root, "remove.txt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("remove")
        subdir = os.path.join(self.root, "subdir")
        os.makedirs(subdir)
        with open(os.path.join(subdir, "nested.txt"), "w", encoding="utf-8") as handle:
            handle.write("nested")
        result = self.deleter.delete_contents(self.root, self.policy)
        self.assertFalse(os.path.exists(path))
        self.assertFalse(os.path.exists(subdir))
        self.assertTrue(os.path.isdir(self.root))
        self.assertGreater(result["bytes_freed"], 0)

    def test_refuses_to_delete_allowlisted_root(self):
        result = self.deleter.delete_target(self.root, self.policy)
        self.assertEqual(len(result["failed"]), 1)
        self.assertTrue(os.path.isdir(self.root))

    def test_recoverable_delete_skips_without_send2trash(self):
        path = os.path.join(self.root, "recycle.txt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("recycle")
        with patch("services.system_cleanup._send2trash", None):
            result = self.deleter.delete_target(
                path, self.policy, recoverable=True
            )
        self.assertEqual(len(result["skipped"]), 1)
        self.assertTrue(os.path.exists(path))

    def test_recoverable_delete_tracks_recycled_bytes(self):
        path = os.path.join(self.root, "recycle.txt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("recycle")
        with patch("services.system_cleanup._send2trash") as send2trash:
            result = self.deleter.delete_target(
                path, self.policy, recoverable=True
            )
        send2trash.assert_called_once_with(path)
        self.assertEqual(result["bytes_freed"], 0)
        self.assertGreater(result["bytes_recycled"], 0)
        self.assertEqual(len(result["recycled"]), 1)
        self.assertTrue(result["removed"][0]["recycled"])


class _ContentsCategory(CleanupCategory):
    key = "test_contents"
    name = "Test contents"
    tier = TIER_SAFE

    def __init__(self, root):
        super().__init__()
        self.root = root

    def get_roots(self):
        return [self.root]


class TestCategoryClean(unittest.TestCase):
    def test_contents_clean_removes_children_but_keeps_allowlisted_root(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        path = os.path.join(root, "child.txt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("child")
        category = _ContentsCategory(root)
        item = category._item(
            root,
            5,
            "Test contents",
            delete_mode="contents",
        )
        result = category.clean([item])
        self.assertEqual(len(result["removed"]), 1)
        self.assertFalse(os.path.exists(path))
        self.assertTrue(os.path.isdir(root))


class TestParsers(unittest.TestCase):
    def test_format_size(self):
        self.assertEqual(format_size(0), "0.0 B")
        self.assertEqual(format_size(1024), "1.0 KB")
        self.assertEqual(format_size(None), "Unknown")

    def test_parse_jetbrains_folder(self):
        parsed = parse_jetbrains_folder("IntelliJIdea2026.1")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.product_key, "intellij_idea")
        self.assertEqual(parsed.product_name, "IntelliJ IDEA")
        self.assertEqual(parsed.version, (2026, 1))
        self.assertFalse(parsed.is_backup)

    def test_parse_jetbrains_backup_folder(self):
        parsed = parse_jetbrains_folder("PyCharm2026.2-backup")
        self.assertIsNotNone(parsed)
        self.assertTrue(parsed.is_backup)

    def test_parse_jetbrains_invalid_folder(self):
        self.assertIsNone(parse_jetbrains_folder("plugins"))
        self.assertIsNone(parse_jetbrains_folder(""))

    def test_select_jetbrains_targets_keeps_newest_and_backups(self):
        targets = select_jetbrains_targets(
            [
                "IntelliJIdea2026.1",
                "IntelliJIdea2025.3",
                "IntelliJIdea2024.2-backup",
                "PyCharm2026.1",
                "PyCharm2025.3",
            ]
        )
        self.assertEqual(
            targets,
            ["IntelliJIdea2024.2-backup", "IntelliJIdea2025.3", "PyCharm2025.3"],
        )

    def test_parse_ollama_list(self):
        output = (
            "NAME\tID\tSIZE\tMODIFIED\n"
            "llama3:latest\tabc123\t4.7 GB\t2 days ago\n"
            "tiny:latest\tdef456\t512 MB\t1 hour ago\n"
        )
        models = parse_ollama_list(output)
        self.assertEqual([name for name, _size in models], ["llama3:latest", "tiny:latest"])
        self.assertGreater(models[0][1], models[1][1])

    def test_parse_windows_size(self):
        self.assertEqual(_parse_windows_size("Used: 1.5 GB"), 1610612736)
        self.assertIsNone(_parse_windows_size("no size here"))


class TestJetBrainsCategory(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.base, True)
        self.appdata = os.path.join(self.base, "appdata")
        self.localappdata = os.path.join(self.base, "localappdata")
        self.appdata_jetbrains = os.path.join(self.appdata, "JetBrains")
        self.local_jetbrains = os.path.join(self.localappdata, "JetBrains")
        os.makedirs(self.appdata_jetbrains)
        os.makedirs(self.local_jetbrains)

        for name in ("IntelliJIdea2026.1", "IntelliJIdea2025.3"):
            path = os.path.join(self.appdata_jetbrains, name)
            os.makedirs(path)
            with open(os.path.join(path, "data.txt"), "w", encoding="utf-8") as handle:
                handle.write("data")
        old_local = os.path.join(self.local_jetbrains, "IntelliJIdea2025.3")
        os.makedirs(old_local)
        with open(os.path.join(old_local, "data.txt"), "w", encoding="utf-8") as handle:
            handle.write("data")

    def test_scan_returns_old_folder_in_both_roots(self):
        with patch.dict(
            os.environ,
            {"APPDATA": self.appdata, "LOCALAPPDATA": self.localappdata},
        ):
            category = JetBrainsCategory()
            with patch(
                "services.system_cleanup._jetbrains_running", return_value=False
            ):
                items = category.scan()

        self.assertEqual(len(items), 2)
        self.assertEqual(
            {item["path"] for item in items},
            {
                os.path.join(self.appdata_jetbrains, "IntelliJIdea2025.3"),
                os.path.join(self.local_jetbrains, "IntelliJIdea2025.3"),
            },
        )
        for item in items:
            self.assertEqual(item["tier"], 2)
            self.assertFalse(item["recoverable"])
            self.assertFalse(item["default_selected"])


class TestRegenerableCachesPermanent(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.base, True)

    def _file(self, *parts):
        path = os.path.join(self.base, *parts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("cache")
        return path

    def test_package_cache_items_are_permanent(self):
        cache = os.path.join(self.base, "npm-cache")
        os.makedirs(cache)
        path = self._file("npm-cache", "data.bin")
        specs = [{"tool": "npm", "paths": [cache], "command": None}]
        category = PackageCachesCategory()
        with patch.object(PackageCachesCategory, "_specs", return_value=specs):
            items = category.scan()
            self.assertEqual(len(items), 1)
            self.assertFalse(items[0]["recoverable"])
            with patch("services.system_cleanup._send2trash") as send2trash:
                result = category.clean(items)
        send2trash.assert_not_called()
        self.assertFalse(os.path.exists(path))
        self.assertGreater(result["bytes_freed"], 0)
        self.assertEqual(result["bytes_recycled"], 0)

    def test_vscode_cache_items_are_permanent(self):
        appdata = os.path.join(self.base, "appdata")
        path = self._file("appdata", "Code", "Cache", "data.bin")
        with patch.dict(os.environ, {"APPDATA": appdata}):
            category = VSCodeCacheCategory()
            items = category.scan()
            self.assertEqual(len(items), 1)
            self.assertFalse(items[0]["recoverable"])
            with patch("services.system_cleanup._send2trash") as send2trash:
                result = category.clean(items)
        send2trash.assert_not_called()
        self.assertFalse(os.path.exists(path))
        self.assertGreater(result["bytes_freed"], 0)
        self.assertEqual(result["bytes_recycled"], 0)

    def test_android_system_image_items_are_permanent(self):
        local = os.path.join(self.base, "localappdata")
        path = self._file(
            "localappdata", "Android", "Sdk", "system-images",
            "35", "google_apis", "x86_64", "data.bin",
        )
        with patch.dict(os.environ, {"LOCALAPPDATA": local}):
            category = AndroidSystemImagesCategory()
            items = category.scan()
            self.assertEqual(len(items), 1)
            self.assertFalse(items[0]["recoverable"])
            with patch("services.system_cleanup._send2trash") as send2trash:
                result = category.clean(items)
        send2trash.assert_not_called()
        self.assertFalse(os.path.exists(path))
        self.assertGreater(result["bytes_freed"], 0)
        self.assertEqual(result["bytes_recycled"], 0)

    def test_jetbrains_old_folder_is_permanent(self):
        appdata = os.path.join(self.base, "appdata")
        local = os.path.join(self.base, "localappdata")
        old = self._file("appdata", "JetBrains", "IntelliJIdea2025.3", "data.bin")
        newest = self._file("appdata", "JetBrains", "IntelliJIdea2026.1", "data.bin")
        with patch.dict(
            os.environ, {"APPDATA": appdata, "LOCALAPPDATA": local}
        ):
            category = JetBrainsCategory()
            with patch(
                "services.system_cleanup._jetbrains_running", return_value=False
            ):
                items = category.scan()
                self.assertEqual(len(items), 1)
                self.assertFalse(items[0]["recoverable"])
                with patch("services.system_cleanup._send2trash") as send2trash:
                    result = category.clean(items)
        send2trash.assert_not_called()
        self.assertFalse(os.path.exists(old))
        self.assertTrue(os.path.exists(newest))
        self.assertGreater(result["bytes_freed"], 0)
        self.assertEqual(result["bytes_recycled"], 0)


class TestLargeFilesReportRecycle(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.home, True)
        self.downloads = os.path.join(self.home, "Downloads")
        self.documents = os.path.join(self.home, "Documents")
        self.desktop = os.path.join(self.home, "Desktop")
        self.protected = [self.downloads, self.documents, self.desktop]
        for directory in self.protected:
            os.makedirs(directory)

    def _large_file(self, directory, name):
        path = os.path.join(directory, name)
        with open(path, "wb") as handle:
            handle.truncate(1024 * 1024 + 32)
        return path

    def _category(self):
        category = LargeFilesReportCategory(
            lambda: {"system_cleanup_large_file_threshold_mb": 1}
        )
        return category

    def test_scan_includes_downloads_and_documents_but_not_desktop(self):
        download_file = self._large_file(self.downloads, "download.bin")
        document_file = self._large_file(self.documents, "document.bin")
        desktop_file = self._large_file(self.desktop, "desktop.bin")
        with patch(
            "services.system_cleanup._scan_roots", return_value=[self.home]
        ), patch(
            "services.system_cleanup._default_protected_roots",
            return_value=self.protected,
        ):
            items = self._category().scan()
        paths = {item["path"] for item in items}
        self.assertIn(download_file, paths)
        self.assertIn(document_file, paths)
        self.assertNotIn(desktop_file, paths)

    def test_selected_report_file_is_recycled_never_permanent(self):
        path = self._large_file(self.downloads, "download.bin")
        with patch(
            "services.system_cleanup._scan_roots", return_value=[self.home]
        ), patch(
            "services.system_cleanup._default_protected_roots",
            return_value=self.protected,
        ):
            category = self._category()
            items = category.scan()
            self.assertEqual(len(items), 1)
            with patch("services.system_cleanup._send2trash") as send2trash:
                result = category.clean(items)
        send2trash.assert_called_once_with(path)
        self.assertTrue(os.path.exists(path))
        self.assertEqual(result["bytes_freed"], 0)
        self.assertGreater(result["bytes_recycled"], 0)
        self.assertEqual(len(result["recycled"]), 1)

    def test_report_cleanup_blocks_system_paths(self):
        path = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "notepad.exe")
        category = self._category()
        item = category._item(
            path,
            1024 * 1024,
            "Large file",
            delete_mode="path",
            recoverable=True,
            selectable=False,
            metadata={"allow_recycle": True, "kind": "file"},
        )
        with patch(
            "services.system_cleanup._scan_roots", return_value=[self.home]
        ), patch(
            "services.system_cleanup._default_protected_roots",
            return_value=self.protected,
        ), patch("services.system_cleanup._send2trash") as send2trash:
            result = category.clean([item])
        send2trash.assert_not_called()
        self.assertFalse(result["removed"])
        self.assertTrue(result["failed"] or result["skipped"])

    def test_downloads_file_recycles_permanent_delete_refused(self):
        """A file in Downloads is recycled via send2trash; permanent delete is refused."""
        path = self._large_file(self.downloads, "download.bin")
        with patch(
            "services.system_cleanup._scan_roots", return_value=[self.home]
        ), patch(
            "services.system_cleanup._default_protected_roots",
            return_value=self.protected,
        ):
            category = self._category()
            items = category.scan()
            self.assertEqual(len(items), 1)
            item = items[0]
            self.assertEqual(item["path"], path)
            self.assertTrue(item["recoverable"])
            self.assertEqual(item["delete_mode"], "path")

            # Recycle should succeed (send2trash called, bytes_recycled > 0)
            with patch("services.system_cleanup._send2trash") as send2trash:
                result = category.clean(items)
            send2trash.assert_called_once_with(path)
            self.assertEqual(result["bytes_freed"], 0)
            self.assertGreater(result["bytes_recycled"], 0)
            self.assertEqual(len(result["recycled"]), 1)

            # Force permanent delete (recoverable=False) should be refused
            # because the item is marked recoverable=True
            forced_item = dict(item)
            forced_item["recoverable"] = False  # try to force permanent
            with patch("services.system_cleanup._send2trash") as send2trash:
                result = category.clean([forced_item])
            send2trash.assert_called_once_with(path)
            self.assertEqual(result["bytes_freed"], 0)
            self.assertGreater(result["bytes_recycled"], 0)


class TestOllamaRecycle(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.manifest = os.path.join(
            self.root,
            "manifests",
            "registry.ollama.ai",
            "library",
            "foo",
            "latest",
        )
        os.makedirs(os.path.dirname(self.manifest))
        with open(self.manifest, "w", encoding="utf-8") as handle:
            handle.write(
                '{"layers": [{"digest": "sha256:aaa", '
                '"mediaType": "application/vnd.ollama.image.model"}]}'
            )
        os.makedirs(os.path.join(self.root, "blobs"))
        with open(
            os.path.join(self.root, "blobs", "sha256-aaa"), "wb"
        ) as handle:
            handle.write(b"model")
        os.makedirs(os.path.join(self.root, "metadata"))
        with open(
            os.path.join(self.root, "metadata", "sha256-aaa.json"),
            "w",
            encoding="utf-8",
        ) as handle:
            handle.write("{}")

    def test_ollama_model_uses_send2trash(self):
        with patch.dict(os.environ, {"OLLAMA_MODELS": self.root}), patch.object(
            OllamaModelsCategory, "_cli", return_value=None
        ):
            category = OllamaModelsCategory()
            items = category.scan()
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["delete_mode"], "ollama_recycle")
            self.assertTrue(items[0]["recoverable"])
            with patch("services.system_cleanup._send2trash") as send2trash:
                result = category.clean(items)
        self.assertEqual(len(result["recycled"]), 3)
        self.assertEqual(result["bytes_freed"], 0)
        self.assertGreater(result["bytes_recycled"], 0)
        called = {call.args[0] for call in send2trash.call_args_list}
        self.assertIn(self.manifest, called)
        self.assertIn(os.path.join(self.root, "blobs", "sha256-aaa"), called)
        self.assertIn(
            os.path.join(self.root, "metadata", "sha256-aaa.json"), called
        )


class TestSystemCleanupController(unittest.TestCase):
    def setUp(self):
        self.activity = MagicMock()
        self.engine = MagicMock()
        self.engine.get_log_path.return_value = "cleanup.log"
        self.item = {
            "id": "temp_folders|c:\\temp",
            "tier": 1,
            "category": "temp_folders",
            "category_name": "Temporary folders",
            "name": "Temp",
            "path": r"C:\Temp",
            "size": 10,
            "delete_mode": "contents",
            "recoverable": False,
            "admin_required": False,
            "selectable": True,
            "default_selected": True,
        }
        self.engine.scan.return_value = {
            "items": [self.item],
            "notices": [],
            "scan_duration": 0.1,
            "admin": False,
            "log_path": "cleanup.log",
        }
        self.engine.clean.return_value = {
            "removed": [],
            "would_remove": [],
            "failed": [],
            "skipped": [],
            "bytes_freed": 0,
            "bytes_estimated": 0,
        }
        self.controller = SystemCleanupController(self.activity, engine=self.engine)

    def test_scan_caches_scanned_items(self):
        result = self.controller.scan()
        self.assertIsNone(result["error"])
        self.assertEqual(self.controller.get_items(), [self.item])

    def test_clean_only_uses_scanned_originals(self):
        self.controller.scan()
        caller_item = {"id": self.item["id"], "path": r"C:\Windows\System32"}
        result = self.controller.clean([caller_item])
        self.assertIsNone(result["error"])
        cleaned = self.engine.clean.call_args.args[0]
        self.assertEqual(cleaned[0]["path"], r"C:\Temp")

    def test_clean_rejects_unknown_item_ids(self):
        self.controller.scan()
        result = self.controller.clean([{"id": "unknown", "path": r"C:\Windows"}])
        self.assertIn("No valid scanned items", result["error"])
        self.engine.clean.assert_not_called()

    def test_settings_defaults(self):
        settings = self.controller.get_settings()
        self.assertFalse(settings["system_cleanup_scan_node_modules"])
        self.assertEqual(settings["system_cleanup_stale_node_modules_days"], 90)
        self.assertEqual(settings["system_cleanup_large_file_threshold_mb"], 500)


class TestFreeSpaceTracking(unittest.TestCase):
    """Follow-up 2: Empty Recycle Bin button and C: free space before/after."""

    def setUp(self):
        self.activity = MagicMock()
        self.engine = MagicMock()
        self.engine.get_log_path.return_value = "cleanup.log"
        self.item = {
            "id": "large_files|c:\\users\\jdoe\\Downloads\\big.bin",
            "tier": 4,
            "category": "large_files",
            "category_name": "Large files and .git folders",
            "name": "big.bin",
            "path": r"C:\Users\jdoe\Downloads\big.bin",
            "size": 1024 * 1024,
            "description": "File larger than 500 MB",
            "delete_mode": "path",
            "recoverable": True,
            "admin_required": False,
            "selectable": False,
            "default_selected": False,
            "metadata": {"allow_recycle": True, "kind": "file"},
        }
        self.engine.scan.return_value = {
            "items": [self.item],
            "notices": [],
            "scan_duration": 0.1,
            "admin": False,
            "log_path": "cleanup.log",
        }
        self.engine.clean.return_value = {
            "removed": [{"id": self.item["id"], "path": self.item["path"], "size": self.item["size"], "recycled": True}],
            "would_remove": [],
            "failed": [],
            "skipped": [],
            "recycled": [{"id": self.item["id"], "path": self.item["path"], "size": self.item["size"]}],
            "bytes_freed": 0,
            "bytes_estimated": self.item["size"],
            "bytes_recycled": self.item["size"],
            "bytes_by_category": {},
            "recycled_by_category": {"Large files and .git folders": self.item["size"]},
            "estimated_by_category": {},
            "dry_run": False,
            "log_path": "cleanup.log",
        }
        self.engine.empty_recycle_bin.return_value = {
            "removed": [{"id": "recycle_bin", "path": "Recycle Bin (all drives)", "size": 2048}],
            "would_remove": [],
            "failed": [],
            "skipped": [],
            "recycled": [],
            "bytes_freed": 2048,
            "bytes_estimated": 2048,
            "bytes_recycled": 0,
        }
        self.controller = SystemCleanupController(self.activity, engine=self.engine)

    def test_get_free_space_returns_int_or_none(self):
        with patch("controllers.system_cleanup_controller.shutil.disk_usage") as disk_usage:
            disk_usage.return_value = MagicMock(free=123456789)
            self.assertEqual(self.controller.get_free_space(), 123456789)
        with patch("controllers.system_cleanup_controller.shutil.disk_usage", side_effect=OSError("boom")):
            self.assertIsNone(self.controller.get_free_space())

    def test_clean_reports_free_space_before_and_after(self):
        self.controller.scan()
        with patch.object(self.controller, "get_free_space", side_effect=[1000, 900]):
            result = self.controller.clean([self.item])
        self.assertEqual(result["free_before"], 1000)
        self.assertEqual(result["free_after"], 900)
        self.assertIsNone(result["error"])

    def test_recycle_report_item_reports_free_space_before_and_after(self):
        self.controller.scan()
        with patch.object(self.controller, "get_free_space", side_effect=[1000, 900]):
            result = self.controller.recycle_report_item(self.item)
        self.assertEqual(result["free_before"], 1000)
        self.assertEqual(result["free_after"], 900)
        self.assertEqual(result["bytes_recycled"], self.item["size"])

    def test_empty_recycle_bin_reports_free_space_before_and_after(self):
        with patch.object(self.controller, "get_free_space", side_effect=[5000, 4998]):
            result = self.controller.empty_recycle_bin()
        self.assertEqual(result["free_before"], 5000)
        self.assertEqual(result["free_after"], 4998)
        self.assertEqual(result["bytes_freed"], 2048)
        self.assertIsNone(result["error"])

    def test_empty_recycle_bin_reports_failure_with_free_space(self):
        self.engine.empty_recycle_bin.return_value = {
            "removed": [], "would_remove": [], "failed": [
                {"path": "Recycle Bin", "size": 0, "reason": "Could not empty Recycle Bin"}
            ],
            "skipped": [], "recycled": [],
            "bytes_freed": 0, "bytes_estimated": 0, "bytes_recycled": 0,
        }
        with patch.object(self.controller, "get_free_space", side_effect=[5000, 5000]):
            result = self.controller.empty_recycle_bin()
        self.assertEqual(result["free_before"], 5000)
        self.assertEqual(result["free_after"], 5000)
        self.assertTrue(result["failed"])


class TestRecycleItemConfirmation(unittest.TestCase):
    """Follow-up 3: per-item confirmation (full path + size) and capacity warning."""

    def _make_view(self):
        """Create a LeftoversView instance without a real tkinter root."""
        import views.leftovers as leftovers_module
        view = leftovers_module.LeftoversView.__new__(leftovers_module.LeftoversView)
        view._cleanup_scanning = False
        view._cleanup_cleaning = False
        view.cleanup_ctrl = MagicMock()
        view.cleanup_ctrl.format_size.side_effect = lambda v: "%d B" % (v or 0)
        view.cleanup_ctrl.get_free_space.return_value = None
        view._cleanup_update_summary = MagicMock()
        return view

    def test_confirmation_message_includes_path_and_size(self):
        """Verify the confirmation dialog includes full path and file size."""
        view = self._make_view()
        item = {
            "path": r"C:\Users\jdoe\Downloads\big.bin",
            "size": 2 * 1024 * 1024 * 1024,  # 2 GB
        }
        with patch("tkinter.messagebox.askyesno", return_value=False) as mock_ask, \
                patch("views.leftovers.threading.Thread") as mock_thread:
            view._cleanup_recycle_item(item)
        mock_ask.assert_called_once()
        message = mock_ask.call_args[0][1]
        self.assertIn("Send this item to the Recycle Bin", message)
        self.assertIn(item["path"], message)
        self.assertIn("2147483648 B", message)
        mock_thread.start.assert_not_called()

    def test_confirmation_warns_when_item_exceeds_recycle_bin_max(self):
        """Verify warning appears when item exceeds the Recycle Bin's max capacity."""
        view = self._make_view()
        item = {
            "path": r"C:\Users\jdoe\Downloads\huge.bin",
            "size": 15 * 1024 ** 3,  # 15 GB
        }
        with patch.object(view, "_get_recycle_bin_info", return_value=(5000, 10 * 1024 ** 3)), \
                patch("tkinter.messagebox.askyesno", return_value=False) as mock_ask:
            view._cleanup_recycle_item(item)
        message = mock_ask.call_args[0][1]
        self.assertIn("⚠ Warning", message)
        self.assertIn("permanently delete", message)
        self.assertIn("10737418240 B", message)  # max capacity shown

    def test_confirmation_warns_when_item_exceeds_drive_free_space(self):
        """Verify warning appears when item exceeds the C: drive's free space."""
        view = self._make_view()
        item = {
            "path": r"C:\Users\jdoe\Downloads\huge.bin",
            "size": 5 * 1024 ** 3,  # 5 GB
        }
        view._get_recycle_bin_info = MagicMock(return_value=(5000, 10 * 1024 ** 3))
        view.cleanup_ctrl.get_free_space.return_value = 1 * 1024 ** 3  # 1 GB free
        with patch("tkinter.messagebox.askyesno", return_value=False) as mock_ask:
            view._cleanup_recycle_item(item)
        message = mock_ask.call_args[0][1]
        self.assertIn("⚠ Warning", message)
        self.assertIn("free space", message)
        self.assertIn("1073741824 B", message)  # free space shown

    def test_confirmation_no_warning_when_item_fits(self):
        """Verify no warning when item fits within Recycle Bin max and free space."""
        view = self._make_view()
        item = {
            "path": r"C:\Users\jdoe\Downloads\small.bin",
            "size": 1024,
        }
        view._get_recycle_bin_info = MagicMock(return_value=(5000, 10 * 1024 ** 3))
        view.cleanup_ctrl.get_free_space.return_value = 100 * 1024 ** 3  # 100 GB free
        with patch("tkinter.messagebox.askyesno", return_value=False) as mock_ask:
            view._cleanup_recycle_item(item)
        message = mock_ask.call_args[0][1]
        self.assertNotIn("⚠ Warning", message)
        self.assertNotIn("permanently delete", message)

    def test_confirmation_shows_recycle_bin_current_size(self):
        """Verify the confirmation shows the Recycle Bin's current size."""
        view = self._make_view()
        item = {"path": r"C:\Users\jdoe\Downloads\file.bin", "size": 1024}
        with patch.object(view, "_get_recycle_bin_info", return_value=(5000, 10 * 1024 ** 3)), \
                patch("tkinter.messagebox.askyesno", return_value=False) as mock_ask:
            view._cleanup_recycle_item(item)
        message = mock_ask.call_args[0][1]
        self.assertIn("5000 B", message)
        self.assertIn("Recycle Bin", message)

    def test_recycle_item_blocked_during_scan(self):
        """Verify recycle is blocked while a scan is in progress."""
        view = self._make_view()
        view._cleanup_scanning = True
        with patch("tkinter.messagebox.askyesno") as mock_ask, \
                patch("views.leftovers.threading.Thread") as mock_thread:
            view._cleanup_recycle_item({"path": "x", "size": 1})
        mock_ask.assert_not_called()
        mock_thread.start.assert_not_called()

    def test_get_recycle_bin_info_function_exists(self):
        """Verify _get_recycle_bin_info method exists on LeftoversView."""
        import views.leftovers as leftovers_module
        self.assertTrue(hasattr(leftovers_module.LeftoversView, "_get_recycle_bin_info"))

    def test_rb_info_structure_defined(self):
        """Verify _RecycleBinInfo structure is properly defined."""
        import views.leftovers as leftovers_module
        self.assertTrue(hasattr(leftovers_module, "_RecycleBinInfo"))


if __name__ == "__main__":
    unittest.main()
