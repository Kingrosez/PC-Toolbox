"""Temp Cleaner controller for PC-Toolbox.

Orchestrates the scanning service and surfaces results to the view.
"""

import threading
from typing import List, Dict, Any, Optional, Callable
from services.temp_cleaner_service import TempCleanerService
from services.activity_service import ActivityService


class TempCleanerController:
    def __init__(self, activity_service: ActivityService, exclusion_service=None):
        self.service = TempCleanerService(exclusion_service=exclusion_service)
        self.activity_service = activity_service
        self.exclusion_service = exclusion_service
        self._is_scanning = False
        self._lock = threading.Lock()
        self._cancel_scan = False

    # ---------------------------------------------------------------- settings
    def get_settings(self) -> Dict[str, Any]:
        return self.service.get_settings()

    def update_settings(self, settings: Dict[str, Any]):
        self.service.update_settings(settings)

    def get_approved_roots(self) -> List[str]:
        return self.service.get_approved_roots()

    # ---------------------------------------------------------------- scanning
    def scan(self, roots: Optional[List[str]] = None) -> Dict[str, Any]:
        with self._lock:
            if self._is_scanning:
                return {
                    "error": "Scan already in progress",
                    "files": [], "total_size": 0, "file_count": 0,
                    "errors": [], "skipped": [], "locations_scanned": 0,
                    "scan_duration": 0.0,
                }
            self._is_scanning = True
            self._cancel_scan = False

        self.activity_service.add_event("system", "Temp file scan started")

        try:
            results = self.service.scan(roots=roots, cancel_check=lambda: self._cancel_scan)

            # Normalize result shape so the view always has consistent fields.
            normalized = {
                "files": results.get("files", []),
                "total_size": results.get("total_size", 0),
                "file_count": results.get("file_count", 0),
                "errors": results.get("errors", []),
                "skipped": results.get("skipped", []),
                "locations_scanned": results.get("locations_scanned", 0),
                "scan_duration": results.get("scan_duration", 0.0),
                "error": results.get("error"),
            }

            msg = "Scan completed: %s files, %s bytes" % (normalized["file_count"], normalized["total_size"])
            self.activity_service.add_event("system", msg, severity="info", metadata={
                "file_count": normalized["file_count"],
                "total_size": normalized["total_size"],
                "errors": len(normalized["errors"]),
                "skipped": len(normalized["skipped"]),
            })

            return normalized
        except Exception as e:
            self.activity_service.add_event("system", "Scan failed: %s" % str(e), severity="error")
            return {
                "error": str(e),
                "files": [], "total_size": 0, "file_count": 0,
                "errors": [str(e)], "skipped": [],
                "locations_scanned": 0, "scan_duration": 0.0,
            }
        finally:
            with self._lock:
                self._is_scanning = False

    def cleanup(self, files, exclusion_service=None, usage_detector=None):
        results = self.service.delete_selected(files, exclusion_service=exclusion_service, usage_detector=usage_detector, approved_roots=self.service.get_approved_roots())
        try:
            self.activity_service.add_event("system", "Temp cleanup: %d deleted, %d bytes" % (results.get('deleted_count',0), results.get('deleted_bytes',0)))
        except Exception:
            pass
        return results
