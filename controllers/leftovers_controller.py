"""Leftovers controller for PC-Toolbox."""

import threading
import time
from typing import List, Dict, Any, Optional

from services.leftovers_service import LeftoversService
from services.activity_service import ActivityService


CATEGORIES = ["All Items", "Files", "Registry Entries", "Shortcuts", "Related Data"]


class LeftoversController:
    def __init__(self, activity_service: ActivityService, service=None):
        self.activity_service = activity_service
        self.service = service or LeftoversService()
        self._is_scanning = False
        self._lock = threading.Lock()
        self._cancel = False
        self._is_removing = False
        self._items = []
        self._errors = []
        self._last_scan_time = None
        self._approved_roots = []

    def set_roots(self, roots):
        self.service._configured_roots = roots
        self._approved_roots = self.service.get_approved_roots()

    def get_approved_roots(self):
        if self._approved_roots:
            return list(self._approved_roots)
        return self.service.get_approved_roots()

    def scan(self, roots=None) -> Dict[str, Any]:
        with self._lock:
            if self._is_scanning:
                return {"error": "Scan already in progress", "items": [], "errors": []}
            self._is_scanning = True
            self._cancel = False

        if roots is not None:
            self.set_roots(roots)
        approved = self.get_approved_roots()

        self.activity_service.add_event("system", "Leftovers scan started")

        try:
            result = self.service.scan(roots=approved, cancel_check=lambda: self._cancel)
            items = result.get("items", [])
            errors = result.get("errors", [])
            self._items = items
            self._errors = errors
            self._last_scan_time = time.time()

            msg = "Scan completed: %d leftover items found" % len(items)
            sev = "info" if not errors else "warning"
            self.activity_service.add_event("system", msg, severity=sev, metadata={
                "count": len(items), "errors": len(errors),
            })

            return {
                "items": items,
                "item_count": len(items),
                "locations_scanned": result.get("locations_scanned", 0),
                "scan_duration": result.get("scan_duration", 0.0),
                "errors": errors,
                "error": None,
            }
        except Exception as e:
            self.activity_service.add_event("system", "Scan failed: %s" % str(e), severity="error")
            return {
                "error": str(e), "items": [], "item_count": 0,
                "locations_scanned": 0, "scan_duration": 0.0, "errors": [str(e)],
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

    def filter_items(self, items, search="", category="All Items", item_type="All Types"):
        result = list(items)
        search_l = (search or "").strip().lower()
        if search_l:
            result = [i for i in result
                      if search_l in (i.get("name") or "").lower()
                      or search_l in (i.get("path") or "").lower()]
        if category and category != "All Items":
            result = [i for i in result if i.get("type") == category]
        if item_type and item_type != "All Types":
            result = [i for i in result if i.get("type") == item_type]
        return result

    def sort_items(self, items, sort_by="Name (A-Z)"):
        items = list(items)
        if sort_by == "Name (A-Z)":
            items.sort(key=lambda i: (i.get("name") or "").lower())
        elif sort_by == "Name (Z-A)":
            items.sort(key=lambda i: (i.get("name") or "").lower(), reverse=True)
        elif sort_by == "Size (Largest First)":
            items.sort(key=lambda i: (i.get("size_bytes") or 0), reverse=True)
        elif sort_by == "Size (Smallest First)":
            items.sort(key=lambda i: (i.get("size_bytes") or 0))
        elif sort_by == "Modified (Newest First)":
            items.sort(key=lambda i: (i.get("mtime") or 0), reverse=True)
        return items

    def paginate(self, items, page=1, per_page=25):
        total = len(items)
        if total == 0:
            return [], 0, 0
        total_pages = (total + per_page - 1) // per_page
        page = max(1, min(page, total_pages))
        start = (page - 1) * per_page
        end = min(start + per_page, total)
        return items[start:end], start + 1, end

    def get_summary(self, items):
        total_size = 0
        size_known = False
        apps = set()
        for i in items:
            sz = i.get("size_bytes")
            if sz is not None:
                total_size += sz
                size_known = True
            # Association confidence: none tracked; count distinct roots as proxy
        return {
            "total_count": len(items),
            "total_size_bytes": total_size if size_known else None,
            "apps_found": len(set(i.get("root") for i in items if i.get("root"))),
            "size_known": size_known,
        }

    def remove_items(self, items, approved_roots):
        with self._lock:
            if self._is_removing:
                return {"error": "Removal already in progress", "removed": [], "skipped": [], "failed": []}
            self._is_removing = True

        self.activity_service.add_event("system", "Leftover removal confirmed: %d items" % len(items))

        removed = []
        skipped = []
        failed = []

        for item in items:
            try:
                ok, reason = self.service.validate_removal(item, approved_roots)
                if not ok:
                    skipped.append({"item": item, "reason": reason})
                    continue
                success, msg = self.service.remove_item(item, approved_roots)
                if success:
                    removed.append(item.get("id"))
                else:
                    failed.append({"item": item, "reason": msg})
            except Exception as e:
                failed.append({"item": item, "reason": str(e)})

        self.activity_service.add_event(
            "system", "Leftover removal completed: %d removed, %d skipped, %d failed" % (
                len(removed), len(skipped), len(failed)
            ), severity="info" if not failed else "warning",
        )

        with self._lock:
            self._is_removing = False

        removed_ids = set(removed)
        self._items = [i for i in self._items if i.get("id") not in removed_ids]

        return {"removed": removed, "skipped": skipped, "failed": failed}

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
