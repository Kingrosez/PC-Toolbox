"""Empty Folders controller for PC-Toolbox."""

import threading
import time
from typing import List, Dict, Any, Optional

from services.empty_folders_service import EmptyFoldersService
from services.activity_service import ActivityService


class EmptyFoldersController:
    def __init__(self, activity_service: ActivityService, service: Optional[EmptyFoldersService] = None):
        self.activity_service = activity_service
        self.service = service or EmptyFoldersService()
        self._is_scanning = False
        self._lock = threading.Lock()
        self._cancel = False
        self._is_deleting = False
        self._folders = []
        self._errors = []
        self._last_scan_time = None
        self._approved_roots = []

    # ---------------------------------------------------------------- roots
    def set_roots(self, roots):
        self.service._configured_roots = roots
        self._approved_roots = self.service.get_approved_roots()

    def get_approved_roots(self):
        return list(self._approved_roots) if self._approved_roots else self.service.get_approved_roots()

    # ---------------------------------------------------------------- scanning
    def scan(self, roots=None) -> Dict[str, Any]:
        with self._lock:
            if self._is_scanning:
                return {"error": "Scan already in progress", "folders": [], "errors": []}
            self._is_scanning = True
            self._cancel = False

        if roots is not None:
            self.set_roots(roots)
        approved = self.get_approved_roots()

        self.activity_service.add_event("system", "Empty folders scan started")

        try:
            result = self.service.scan(roots=approved, cancel_check=lambda: self._cancel)
            folders = result.get("folders", [])
            errors = result.get("errors", [])
            self._folders = folders
            self._errors = errors
            self._last_scan_time = time.time()

            msg = "Scan completed: %d empty folders found" % len(folders)
            sev = "info" if not errors else "warning"
            self.activity_service.add_event("system", msg, severity=sev, metadata={
                "count": len(folders),
                "errors": len(errors),
            })

            return {
                "folders": folders,
                "folder_count": len(folders),
                "locations_scanned": result.get("locations_scanned", 0),
                "scan_duration": result.get("scan_duration", 0.0),
                "errors": errors,
                "error": None,
            }
        except Exception as e:
            self.activity_service.add_event("system", "Scan failed: %s" % str(e), severity="error")
            return {
                "error": str(e),
                "folders": [],
                "folder_count": 0,
                "locations_scanned": 0,
                "scan_duration": 0.0,
                "errors": [str(e)],
            }
        finally:
            with self._lock:
                self._is_scanning = False

    def cancel_scan(self):
        self._cancel = True

    def is_scanning(self):
        return self._is_scanning

    # ---------------------------------------------------------------- data
    def get_folders(self):
        return list(self._folders)

    def get_errors(self):
        return list(self._errors)

    # ---------------------------------------------------------------- filtering
    def filter_folders(self, folders, search="", location="All Locations"):
        result = list(folders)
        search_l = (search or "").strip().lower()
        if search_l:
            result = [f for f in result if search_l in f.get("path", "").lower()
                      or search_l in f.get("parent", "").lower()]
        if location and location != "All Locations":
            result = [f for f in result if f.get("root") == location]
        return result

    def get_locations(self, folders):
        locs = sorted(set(f.get("root") for f in folders if f.get("root")))
        return ["All Locations"] + locs

    # ---------------------------------------------------------------- pagination
    def paginate(self, folders, page=1, per_page=25):
        total = len(folders)
        if total == 0:
            return [], 0, 0
        total_pages = (total + per_page - 1) // per_page
        page = max(1, min(page, total_pages))
        start = (page - 1) * per_page
        end = min(start + per_page, total)
        return folders[start:end], start + 1, end

    # ---------------------------------------------------------------- summary
    def get_summary(self, folders):
        return {
            "total_count": len(folders),
            "locations_scanned": self.service._locations_scanned,
        }

    # ---------------------------------------------------------------- deletion
    def delete_folders(self, paths, approved_roots):
        with self._lock:
            if self._is_deleting:
                return {"error": "Deletion already in progress", "deleted": [], "skipped": [], "failed": []}
            self._is_deleting = True

        self.activity_service.add_event("system", "Folder deletion confirmed: %d folders" % len(paths))

        deleted = []
        skipped = []
        failed = []

        for p in paths:
            try:
                ok, reason = self.service.validate_deletion(p, approved_roots)
                if not ok:
                    skipped.append({"path": p, "reason": reason})
                    continue
                success, msg = self.service.delete_folder(p, approved_roots)
                if success:
                    deleted.append(p)
                else:
                    failed.append({"path": p, "reason": msg})
            except Exception as e:
                failed.append({"path": p, "reason": str(e)})

        self.activity_service.add_event(
            "system", "Folder deletion completed: %d deleted, %d skipped, %d failed" % (
                len(deleted), len(skipped), len(failed)
            ), severity="info" if not failed else "warning",
        )

        with self._lock:
            self._is_deleting = False

        # Remove deleted from current list
        deleted_set = set(deleted)
        self._folders = [f for f in self._folders if f.get("path") not in deleted_set]

        return {
            "deleted": deleted,
            "skipped": skipped,
            "failed": failed,
        }

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
