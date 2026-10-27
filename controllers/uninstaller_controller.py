"""Uninstaller controller for PC-Toolbox.

Orchestrates discovery and exposes filtered/sorted/paginated data to the view.
"""

import threading
import time
from typing import List, Dict, Any, Optional

from services.uninstaller_service import UninstallerService
from services.activity_service import ActivityService


CATEGORIES = ["All Categories", "Browsers", "Development", "Utilities", "Security", "Other"]
SIZE_FILTERS = ["All Sizes", "Under 100 MB", "100 MB-1 GB", "Over 1 GB", "Unknown Size"]
SORT_OPTIONS = [
    "Name (A-Z)", "Name (Z-A)",
    "Size (Largest First)", "Size (Smallest First)",
    "Installation Date (Newest First)", "Publisher",
]


class UninstallerController:
    def __init__(self, activity_service: ActivityService, service: Optional[UninstallerService] = None):
        self.activity_service = activity_service
        self.service = service or UninstallerService()
        self._is_scanning = False
        self._lock = threading.Lock()
        self._cancel = False
        self._applications: List[Dict[str, Any]] = []
        self._errors: List[str] = []
        self._last_scan_time = None

    # ---------------------------------------------------------------- scanning
    def scan(self) -> Dict[str, Any]:
        with self._lock:
            if self._is_scanning:
                return {"error": "Scan already in progress", "applications": [], "errors": []}
            self._is_scanning = True
            self._cancel = False

        self.activity_service.add_event("system", "Installed application scan started")

        try:
            result = self.service.discover(cancel_check=lambda: self._cancel)
            apps = result.get("applications", [])
            errors = result.get("errors", [])
            self._applications = apps
            self._errors = errors
            self._last_scan_time = time.time()

            msg = "Scan completed: %d applications found" % len(apps)
            sev = "info" if not errors else "warning"
            self.activity_service.add_event("system", msg, severity=sev, metadata={
                "count": len(apps),
                "errors": len(errors),
            })

            return {
                "applications": apps,
                "errors": errors,
                "count": len(apps),
                "error": None,
            }
        except Exception as e:
            self.activity_service.add_event("system", "Scan failed: %s" % str(e), severity="error")
            return {
                "error": str(e),
                "applications": [],
                "errors": [str(e)],
                "count": 0,
            }
        finally:
            with self._lock:
                self._is_scanning = False

    def cancel_scan(self):
        self._cancel = True

    def is_scanning(self) -> bool:
        return self._is_scanning

    # ---------------------------------------------------------------- data
    def get_applications(self) -> List[Dict[str, Any]]:
        return list(self._applications)

    def get_errors(self) -> List[str]:
        return list(self._errors)

    def get_last_scan_time(self):
        return self._last_scan_time

    # ---------------------------------------------------------------- filtering / sorting / pagination
    def filter_applications(self, apps, search="", category="All Categories",
                            size_filter="All Sizes", publisher="All Publishers"):
        result = list(apps)
        search_l = (search or "").strip().lower()
        if search_l:
            result = [
                a for a in result
                if search_l in (a.get("name") or "").lower()
                or search_l in (a.get("publisher") or "").lower()
                or search_l in (a.get("version") or "").lower()
            ]
        if category and category != "All Categories":
            result = [a for a in result if a.get("category") == category]
        if publisher and publisher != "All Publishers":
            result = [a for a in result if a.get("publisher") == publisher]
        if size_filter and size_filter != "All Sizes":
            def size_ok(a):
                sz = a.get("size_bytes")
                if size_filter == "Unknown Size":
                    return sz is None
                if sz is None:
                    return False
                if size_filter == "Under 100 MB":
                    return sz < 100 * 1024 * 1024
                if size_filter == "100 MB-1 GB":
                    return 100 * 1024 * 1024 <= sz <= 1024 * 1024 * 1024
                if size_filter == "Over 1 GB":
                    return sz > 1024 * 1024 * 1024
                return True
            result = [a for a in result if size_ok(a)]
        return result

    def sort_applications(self, apps, sort_by="Name (A-Z)"):
        apps = list(apps)
        if sort_by == "Name (A-Z)":
            apps.sort(key=lambda a: (a.get("name") or "").lower())
        elif sort_by == "Name (Z-A)":
            apps.sort(key=lambda a: (a.get("name") or "").lower(), reverse=True)
        elif sort_by == "Size (Largest First)":
            apps.sort(key=lambda a: (a.get("size_bytes") or 0), reverse=True)
        elif sort_by == "Size (Smallest First)":
            apps.sort(key=lambda a: (a.get("size_bytes") or 0))
        elif sort_by == "Installation Date (Newest First)":
            apps.sort(key=lambda a: (a.get("install_date") or ""), reverse=True)
        elif sort_by == "Publisher":
            apps.sort(key=lambda a: (a.get("publisher") or "").lower())
        return apps

    def get_publishers(self, apps) -> List[str]:
        pubs = sorted(set(a.get("publisher") for a in apps if a.get("publisher")))
        return ["All Publishers"] + pubs

    def paginate(self, apps, page=1, per_page=25):
        total = len(apps)
        if total == 0:
            return [], 0, 0
        total_pages = (total + per_page - 1) // per_page
        page = max(1, min(page, total_pages))
        start = (page - 1) * per_page
        end = min(start + per_page, total)
        return apps[start:end], start + 1, end

    # ---------------------------------------------------------------- summary
    def get_summary(self, apps) -> Dict[str, Any]:
        total_size = 0
        size_known = False
        large_count = 0
        recent_count = 0
        for a in apps:
            sz = a.get("size_bytes")
            if sz is not None:
                total_size += sz
                size_known = True
                if sz > 1024 * 1024 * 1024:
                    large_count += 1
            # recently installed (last 30 days) - based on install_date if parseable
            # We can't reliably compute without a date parse; mark unknown.
        return {
            "total_count": len(apps),
            "total_size_bytes": total_size if size_known else None,
            "large_count": large_count if size_known else None,
            "recent_count": None,  # unknown unless install dates parseable
            "size_known": size_known,
        }

    # ---------------------------------------------------------------- uninstall safety
    def validate_uninstall(self, app: Dict[str, Any]) -> Dict[str, Any]:
        """Validate whether an uninstall can be safely initiated."""
        us = app.get("uninstall_string")
        if not us:
            return {"valid": False, "reason": "No uninstall command available"}
        # Never execute automatically; just validate metadata presence.
        return {"valid": True, "reason": "Uninstall command present (manual confirmation required)"}

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
