"""Storage Analyzer controller for PC-Toolbox."""

import threading
import time
import csv
import os
from typing import List, Dict, Any, Optional

from services.storage_analyzer_service import StorageAnalyzerService
from services.activity_service import ActivityService


class StorageAnalyzerController:
    def __init__(self, activity_service: ActivityService, service=None):
        self.activity_service = activity_service
        self.service = service or StorageAnalyzerService()
        self._is_scanning = False
        self._lock = threading.Lock()
        self._cancel = False
        self._items = []
        self._errors = []
        self._last_result = None
        self._selected_drive = None
        self._last_scan_time = None

    def get_drives(self):
        return self.service.get_drives()

    def set_selected_drive(self, drive):
        self._selected_drive = drive

    def get_selected_drive(self):
        return self._selected_drive

    def analyze(self, root_path=None) -> Dict[str, Any]:
        with self._lock:
            if self._is_scanning:
                return {"error": "Scan already in progress", "items": [], "errors": []}
            self._is_scanning = True
            self._cancel = False

        if root_path is None:
            drive = self._selected_drive
            root_path = drive.get("mountpoint") if drive else None

        self.activity_service.add_event("system", "Storage analysis started: %s" % (root_path or "unknown"))

        try:
            result = self.service.analyze(root_path, cancel_check=lambda: self._cancel)
            items = result.get("items", [])
            errors = result.get("errors", [])
            self._items = items
            self._errors = errors
            self._last_result = result
            self._last_scan_time = time.time()

            msg = "Analysis completed: %d items, %s" % (len(items), self.service.format_size(result.get("total_size", 0)))
            sev = "info" if not errors else "warning"
            self.activity_service.add_event("system", msg, severity=sev, metadata={
                "count": len(items), "errors": len(errors),
            })

            return {
                "items": items,
                "errors": errors,
                "total_size": result.get("total_size", 0),
                "file_count": result.get("file_count", 0),
                "folder_count": result.get("folder_count", 0),
                "scan_duration": result.get("scan_duration", 0.0),
                "type_stats": result.get("type_stats", {}),
                "root": result.get("root"),
                "error": None,
            }
        except Exception as e:
            self.activity_service.add_event("system", "Analysis failed: %s" % str(e), severity="error")
            return {
                "error": str(e), "items": [], "errors": [str(e)],
                "total_size": 0, "file_count": 0, "folder_count": 0,
                "scan_duration": 0.0, "type_stats": {}, "root": root_path,
            }
        finally:
            with self._lock:
                self._is_scanning = False

    def cancel_scan(self):
        self._cancel = True

    def is_scanning(self):
        return self._is_scanning

    def get_items(self):
        return list(self._items)

    def get_errors(self):
        return list(self._errors)

    def get_last_result(self):
        return self._last_result

    def filter_items(self, items, search="", item_type="All Types"):
        result = list(items)
        search_l = (search or "").strip().lower()
        if search_l:
            result = [i for i in result
                      if search_l in (i.get("name") or "").lower()
                      or search_l in (i.get("path") or "").lower()]
        if item_type and item_type != "All Types":
            result = [i for i in result if i.get("type") == item_type]
        return result

    def sort_items(self, items, sort_by="Size (Largest First)"):
        items = list(items)
        if sort_by == "Size (Largest First)":
            items.sort(key=lambda i: (i.get("size_bytes") or 0), reverse=True)
        elif sort_by == "Size (Smallest First)":
            items.sort(key=lambda i: (i.get("size_bytes") or 0))
        elif sort_by == "Name (A-Z)":
            items.sort(key=lambda i: (i.get("name") or "").lower())
        elif sort_by == "Name (Z-A)":
            items.sort(key=lambda i: (i.get("name") or "").lower(), reverse=True)
        elif sort_by == "Modified (Newest First)":
            items.sort(key=lambda i: (i.get("mtime") or 0), reverse=True)
        return items

    def paginate(self, items, page=1, per_page=50):
        total = len(items)
        if total == 0:
            return [], 0, 0
        total_pages = (total + per_page - 1) // per_page
        page = max(1, min(page, total_pages))
        start = (page - 1) * per_page
        end = min(start + per_page, total)
        return items[start:end], start + 1, end

    def get_largest_files(self, items, threshold_bytes=100 * 1024 * 1024):
        return [i for i in items if i.get("type") == "File" and (i.get("size_bytes") or 0) >= threshold_bytes]

    def find_duplicates(self, items):
        # Group by size first, then hash
        from collections import defaultdict
        by_size = defaultdict(list)
        for i in items:
            if i.get("type") == "File":
                by_size[i.get("size_bytes", 0)].append(i)
        dup_groups = []
        for sz, group in by_size.items():
            if len(group) < 2 or sz == 0:
                continue
            # Hash each file
            hashes = defaultdict(list)
            for item in group:
                h = self._hash_file(item.get("path"))
                if h:
                    hashes[h].append(item)
            for h, hgroup in hashes.items():
                if len(hgroup) > 1:
                    dup_groups.append(hgroup)
        return dup_groups

    def _hash_file(self, path):
        import hashlib
        try:
            h = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            return h.hexdigest()
        except Exception:
            return None

    def get_type_stats(self):
        if self._last_result:
            return self._last_result.get("type_stats", {})
        return {}

    def export_csv(self, filepath, items, drive_info=None):
        try:
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Name", "Path", "Type", "Size (bytes)", "Modified", "Root"])
                for item in items:
                    writer.writerow([
                        item.get("name", ""),
                        item.get("path", ""),
                        item.get("type", ""),
                        item.get("size_bytes", 0),
                        item.get("mtime", ""),
                        item.get("root", ""),
                    ])
            return True, "Exported successfully"
        except Exception as e:
            return False, str(e)

    def format_size(self, size_bytes):
        if size_bytes is None:
            return "Unknown"
        if size_bytes < 0:
            return "Unknown"
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size_bytes < 1024.0:
                return "%.1f %s" % (size_bytes, unit)
            size_bytes /= 1024.0
        return "%.1f PB" % size_bytes

    def format_time(self, seconds):
        if seconds is None or seconds < 0:
            return "\u2014"
        seconds = int(seconds)
        if seconds < 60:
            return "%ds" % seconds
        if seconds < 3600:
            m = seconds // 60
            s = seconds % 60
            return "%dm %ds" % (m, s)
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return "%dh %dm" % (h, m)
