"""Startup Manager controller for PC-Toolbox."""

import threading
from typing import List, Dict, Any, Optional, Callable


class StartupManagerController:
    def __init__(self, service, activity_service=None):
        self.service = service
        self.activity_service = activity_service
        self.entries: List[Dict[str, Any]] = []
        self.selected_id: Optional[str] = None
        self._lock = threading.Lock()
        self._refreshing = False

    def refresh(self, on_complete: Callable, on_error: Callable = None, cancel_check=None):
        if self._refreshing:
            return
        self._refreshing = True

        def worker():
            try:
                result = self.service.discover(cancel_check=cancel_check)
                with self._lock:
                    self.entries = result.get("entries", [])
                    self._refreshing = False
                on_complete(self.entries)
            except Exception as e:
                self._refreshing = False
                if on_error:
                    on_error(str(e))

        threading.Thread(target=worker, daemon=True).start()

    @property
    def is_refreshing(self):
        return self._refreshing

    def get_summary(self):
        total = len(self.entries)
        enabled = sum(1 for e in self.entries if e.get("enabled"))
        disabled = total - enabled
        return {
            "total": total,
            "enabled": enabled,
            "disabled": disabled,
            "boot_impact": "Not measured",
        }

    def filter_entries(self, filter_type="all", search="", sort_by="name"):
        result = list(self.entries)
        if filter_type == "enabled":
            result = [e for e in result if e.get("enabled")]
        elif filter_type == "disabled":
            result = [e for e in result if not e.get("enabled")]
        elif filter_type == "high":
            result = [e for e in result if e.get("impact") == "High"]
        if search:
            q = search.lower()
            result = [e for e in result if q in (e.get("name") or "").lower() or q in (e.get("publisher") or "").lower() or q in (e.get("source") or "").lower()]
        key_map = {"name": "name", "publisher": "publisher", "impact": "impact"}
        key = key_map.get(sort_by, "name")
        result.sort(key=lambda e: (e.get(key) or "").lower())
        return result

    def select(self, entry_id):
        self.selected_id = entry_id
        for e in self.entries:
            if e["id"] == entry_id:
                return e
        return None

    def get_selected(self):
        return self.select(self.selected_id) if self.selected_id else None

    def disable(self, entry_id, confirm_callback=None):
        entry = self.select(entry_id)
        if not entry:
            return {"success": False, "message": "Entry not found"}
        if confirm_callback and not confirm_callback(entry):
            return {"success": False, "message": "Cancelled by user"}
        result = self.service.disable_entry(entry)
        if result[0]:
            entry["enabled"] = False
            if self.activity_service:
                try:
                    self.activity_service.log("Startup disabled: %s" % entry.get("name"))
                except Exception:
                    pass
        return {"success": result[0], "message": result[1]}

    def enable(self, entry_id, confirm_callback=None):
        entry = self.select(entry_id)
        if not entry:
            return {"success": False, "message": "Entry not found"}
        if confirm_callback and not confirm_callback(entry):
            return {"success": False, "message": "Cancelled by user"}
        result = self.service.enable_entry(entry)
        if result[0]:
            entry["enabled"] = True
            if self.activity_service:
                try:
                    self.activity_service.log("Startup enabled: %s" % entry.get("name"))
                except Exception:
                    pass
        return {"success": result[0], "message": result[1]}
