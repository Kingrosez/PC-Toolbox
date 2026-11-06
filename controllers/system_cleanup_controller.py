"""Controller for the Leftovers System Cleanup section."""

from __future__ import annotations

import os
import shutil
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from services.activity_service import ActivityService
from services.system_cleanup import SystemCleanupEngine, format_size, is_admin


CLEANUP_SETTING_DEFAULTS = {
    "system_cleanup_scan_node_modules": False,
    "system_cleanup_stale_node_modules_days": 90,
    "system_cleanup_enable_docker_prune": False,
    "system_cleanup_large_file_threshold_mb": 500,
}


class SystemCleanupController:
    """Orchestrates scans and cleans while keeping UI paths constrained."""

    def __init__(
        self,
        activity_service: ActivityService,
        settings_service=None,
        log_dir: Optional[str] = None,
        engine: Optional[SystemCleanupEngine] = None,
    ):
        self.activity_service = activity_service
        self.settings_service = settings_service
        self.engine = engine or SystemCleanupEngine(
            settings_provider=self.get_settings,
            log_dir=log_dir,
        )
        self._lock = threading.Lock()
        self._is_scanning = False
        self._is_cleaning = False
        self._cancel_scan = False
        self._cancel_clean = False
        self._items: List[Dict[str, Any]] = []
        self._items_by_id: Dict[str, Dict[str, Any]] = {}
        self._last_scan_time: Optional[float] = None

    # ------------------------------------------------------------- settings
    def get_settings(self) -> Dict[str, Any]:
        """Return cleanup settings with defaults applied."""
        settings = dict(CLEANUP_SETTING_DEFAULTS)
        if self.settings_service:
            for key in CLEANUP_SETTING_DEFAULTS:
                settings[key] = self.settings_service.get(key, CLEANUP_SETTING_DEFAULTS[key])
        return settings

    def update_settings(self, values: Dict[str, Any]) -> None:
        """Persist supported cleanup settings."""
        if not self.settings_service:
            return
        for key, value in values.items():
            if key in CLEANUP_SETTING_DEFAULTS:
                self.settings_service.set(key, value)
        self.settings_service.save()

    # ------------------------------------------------------------- helpers
    @staticmethod
    def format_size(size_bytes: Optional[int]) -> str:
        return format_size(size_bytes)

    def is_admin(self) -> bool:
        return is_admin()

    def get_log_path(self) -> Optional[str]:
        return self.engine.get_log_path()

    def open_log(self) -> bool:
        path = self.get_log_path()
        if not path or not os.path.exists(path):
            return False
        try:
            os.startfile(path)
            return True
        except OSError:
            return False

    def get_free_space(self, path: str = "C:\\") -> Optional[int]:
        try:
            return int(shutil.disk_usage(path).free)
        except OSError:
            return None

    def get_items(self) -> List[Dict[str, Any]]:
        return list(self._items)

    # ------------------------------------------------------------- scanning
    def scan(self, progress_callback=None) -> Dict[str, Any]:
        with self._lock:
            if self._is_scanning:
                return {
                    "error": "Scan already in progress",
                    "items": [],
                    "notices": [],
                }
            self._is_scanning = True
            self._cancel_scan = False

        self.activity_service.add_event("system", "System cleanup scan started")
        try:
            result = self.engine.scan(
                progress_callback=progress_callback,
                cancel_check=lambda: self._cancel_scan,
            )
            items = result.get("items", [])
            self._items = items
            self._items_by_id = {item.get("id"): item for item in items if item.get("id")}
            self._last_scan_time = time.time()

            self.activity_service.add_event(
                "system",
                "System cleanup scan completed: %d item(s), %d notice(s)"
                % (len(items), len(result.get("notices", []))),
                severity="info" if not result.get("notices") else "warning",
                metadata={"item_count": len(items)},
            )
            result["error"] = None
            result["free_space"] = self.get_free_space()
            return result
        except Exception as exc:
            self._items = []
            self._items_by_id = {}
            self.activity_service.add_event(
                "system", "System cleanup scan failed: %s" % exc, severity="error"
            )
            return {
                "error": str(exc),
                "items": [],
                "notices": [str(exc)],
                "scan_duration": 0.0,
                "admin": self.is_admin(),
                "free_space": self.get_free_space(),
            }
        finally:
            with self._lock:
                self._is_scanning = False

    def cancel_scan(self) -> None:
        self._cancel_scan = True
        self.activity_service.add_event(
            "system", "System cleanup scan cancelled", severity="info"
        )

    def cancel_clean(self) -> None:
        self._cancel_clean = True

    def _safe_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Replace caller-supplied items with the scanned originals by id."""
        safe: List[Dict[str, Any]] = []
        for item in items or []:
            item_id = item.get("id") if isinstance(item, dict) else None
            original = self._items_by_id.get(item_id)
            if original is not None:
                safe.append(original)
        return safe

    def _drop_removed(self, removed: List[Dict[str, Any]]) -> None:
        removed_ids = {entry.get("id") for entry in removed if entry.get("id")}
        if not removed_ids:
            return
        self._items = [item for item in self._items if item.get("id") not in removed_ids]
        for item_id in removed_ids:
            self._items_by_id.pop(item_id, None)

    # ------------------------------------------------------------- cleaning
    def clean(
        self,
        items: List[Dict[str, Any]],
        dry_run: bool = False,
        progress_callback=None,
    ) -> Dict[str, Any]:
        with self._lock:
            if self._is_cleaning:
                return {
                    "error": "Cleanup already in progress",
                    "removed": [],
                    "would_remove": [],
                    "failed": [],
                    "skipped": [],
                    "bytes_freed": 0,
                    "bytes_estimated": 0,
                    "bytes_recycled": 0,
                    "bytes_by_category": {},
                    "recycled_by_category": {},
                    "estimated_by_category": {},
                }
            self._is_cleaning = True
            self._cancel_clean = False

        safe_items = self._safe_items(items)
        if not safe_items:
            with self._lock:
                self._is_cleaning = False
            return {
                "error": "No valid scanned items selected",
                "removed": [],
                "would_remove": [],
                "failed": [],
                "skipped": [],
                "bytes_freed": 0,
                "bytes_estimated": 0,
                "bytes_recycled": 0,
                "bytes_by_category": {},
                "recycled_by_category": {},
                "estimated_by_category": {},
            }

        free_before = self.get_free_space()
        self.activity_service.add_event(
            "system",
            "System cleanup %s started: %d item(s)"
            % ("dry run" if dry_run else "confirmed", len(safe_items)),
        )
        try:
            result = self.engine.clean(
                safe_items,
                dry_run=dry_run,
                progress_callback=progress_callback,
                cancel_check=lambda: self._cancel_clean,
            )
            if not dry_run:
                self._drop_removed(result.get("removed", []))
            result["free_before"] = free_before
            result["free_after"] = self.get_free_space()
            result["error"] = None
            self.activity_service.add_event(
                "system",
                "System cleanup finished: %d removed, %d skipped, %d failed, %s freed, %s recycled"
                % (
                    len(result.get("removed", [])),
                    len(result.get("skipped", [])),
                    len(result.get("failed", [])),
                    format_size(result.get("bytes_freed", 0)),
                    format_size(result.get("bytes_recycled", 0)),
                ),
                severity="warning" if result.get("failed") else "info",
            )
            return result
        except Exception as exc:
            self.activity_service.add_event(
                "system", "System cleanup failed: %s" % exc, severity="error"
            )
            return {
                "error": str(exc),
                "removed": [],
                "would_remove": [],
                "failed": [],
                "skipped": [],
                "bytes_freed": 0,
                "bytes_estimated": 0,
                "bytes_recycled": 0,
                "bytes_by_category": {},
                "recycled_by_category": {},
                "estimated_by_category": {},
                "free_before": free_before,
                "free_after": self.get_free_space(),
            }
        finally:
            with self._lock:
                self._is_cleaning = False

    def empty_recycle_bin(self) -> Dict[str, Any]:
        """Permanently empty the Windows Recycle Bin on all drives."""
        with self._lock:
            if self._is_cleaning:
                return {
                    "error": "Cleanup already in progress",
                    "removed": [],
                    "would_remove": [],
                    "failed": [],
                    "skipped": [],
                    "recycled": [],
                    "bytes_freed": 0,
                    "bytes_estimated": 0,
                    "bytes_recycled": 0,
                }
            self._is_cleaning = True

        free_before = self.get_free_space()
        self.activity_service.add_event("system", "Empty Recycle Bin started")
        try:
            result = self.engine.empty_recycle_bin()
            result["free_before"] = free_before
            result["free_after"] = self.get_free_space()
            result["error"] = None
            self.activity_service.add_event(
                "system",
                "Recycle Bin emptied: %s freed"
                % format_size(result.get("bytes_freed", 0)),
                severity="warning" if result.get("failed") else "info",
            )
            return result
        except Exception as exc:
            self.activity_service.add_event(
                "system", "Empty Recycle Bin failed: %s" % exc, severity="error"
            )
            return {
                "error": str(exc),
                "removed": [],
                "would_remove": [],
                "failed": [],
                "skipped": [],
                "recycled": [],
                "bytes_freed": 0,
                "bytes_estimated": 0,
                "bytes_recycled": 0,
                "free_before": free_before,
                "free_after": self.get_free_space(),
            }
        finally:
            with self._lock:
                self._is_cleaning = False

    def recycle_report_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Explicitly send one Tier 4 report item to the Recycle Bin."""
        original = self._items_by_id.get(item.get("id") if isinstance(item, dict) else None)
        if original is None:
            return {"error": "Item is no longer available", "removed": [], "failed": [], "skipped": []}
        if not (original.get("metadata") or {}).get("allow_recycle"):
            return {"error": "This item is report-only", "removed": [], "failed": [], "skipped": []}
        return self.clean([original], dry_run=False)
