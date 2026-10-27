"""PC Health controller for PC-Toolbox."""

import threading
import time
import platform
import sys
from typing import List, Dict, Any, Optional

sys.path.insert(0, 'd:/Windows app/PC-Toolbox')

from services.system_metrics import SystemMetricsService
from services.storage_service import StorageService
from services.health_service import HealthService
from services.activity_service import ActivityService


class PCHealthController:
    def __init__(self, activity_service: ActivityService):
        self.activity_service = activity_service
        self.metrics_service = SystemMetricsService()
        self.storage_service = StorageService()
        self.health_service = HealthService()
        self._is_checking = False
        self._lock = threading.Lock()
        self._cancel = False
        self._last_check_time = None

    def run_full_check(self) -> Dict[str, Any]:
        with self._lock:
            if self._is_checking:
                return {"error": "Check already in progress"}
            self._is_checking = True
            self._cancel = False

        self.activity_service.add_event("system", "PC health full check started")

        try:
            metrics = self.metrics_service.get_all_metrics()
            storage = self.storage_service.get_summary_stats()
            health = self.health_service.get_health_summary(metrics, storage)

            # System info
            si = metrics.get("system", {})
            mem = metrics.get("memory", {})

            # Build system info dict
            system_info = {
                "os_name": si.get("os_name", "Unknown"),
                "os_version": si.get("os_version", "Unknown"),
                "os_build": si.get("os_release", "Unknown"),
                "processor": si.get("processor", "Unknown"),
                "logical_cores": si.get("cpu_count_logical", 0),
                "physical_cores": si.get("cpu_count_physical", 0),
                "total_memory_bytes": mem.get("total_bytes"),
                "architecture": si.get("architecture", "Unknown"),
                "uptime_seconds": si.get("uptime_seconds"),
                "hostname": si.get("hostname", "Unknown"),
            }

            # Health checks list
            checks = self._build_checks(metrics, storage, health)

            # Score calculation
            score = self._calculate_score(health, metrics, storage)

            # Recommendations
            recommendations = self._build_recommendations(health, metrics, storage)

            self._last_check_time = time.time()

            self.activity_service.add_event("system", "PC health check completed", severity="info", metadata={
                "score": score, "errors": health.get("errors", 0),
            })

            return {
                "score": score,
                "status": self._score_status(score),
                "metrics": {
                    "cpu_usage": metrics.get("cpu_usage"),
                    "memory_percent": mem.get("percent_used"),
                    "memory_used_bytes": mem.get("used_bytes"),
                    "memory_total_bytes": mem.get("total_bytes"),
                    "storage_percent": storage.get("percent_used"),
                    "storage_used_bytes": storage.get("used_space_bytes"),
                    "storage_total_bytes": storage.get("total_space_bytes"),
                    "storage_free_bytes": storage.get("free_space_bytes"),
                },
                "system_info": system_info,
                "health": health,
                "checks": checks,
                "recommendations": recommendations,
                "passed_count": health.get("total", 0) - health.get("errors", 0) - health.get("warnings", 0),
                "warning_count": health.get("warnings", 0),
                "error_count": health.get("errors", 0),
                "error": None,
            }
        except Exception as e:
            self.activity_service.add_event("system", "PC health check failed: %s" % str(e), severity="error")
            return {"error": str(e), "score": 0, "status": "Unknown"}
        finally:
            with self._lock:
                self._is_checking = False

    def _calculate_score(self, health, metrics, storage):
        score = 100
        errors = health.get("errors", 0)
        warnings = health.get("warnings", 0)
        score -= errors * 25
        score -= warnings * 10
        if score < 0:
            score = 0
        return score

    def _score_status(self, score):
        if score >= 80:
            return "Good"
        if score >= 50:
            return "Fair"
        return "Needs Attention"

    def _build_checks(self, metrics, storage, health):
        checks = []
        indicators = health.get("indicators", [])
        ind_map = {i.get("category", ""): i for i in indicators}

        # Disk Space
        disk_status = "Pass"
        disk_detail = "All drives have adequate free space"
        for ind in indicators:
            if ind.get("category") == "Storage":
                disk_status = "Warning" if ind.get("severity") == "warning" else "Fail"
                disk_detail = ind.get("message", "")
                break
        checks.append({"name": "Disk Space", "description": "Checks available disk space on all drives",
                      "status": disk_status, "detail": disk_detail, "icon": "\U0001F4BE"})

        # Memory Usage
        mem_status = "Pass"
        mem_detail = "Memory usage within normal range"
        for ind in indicators:
            if ind.get("category") == "Memory":
                mem_status = "Warning" if ind.get("severity") == "warning" else "Fail"
                mem_detail = ind.get("message", "")
                break
        checks.append({"name": "Memory Usage", "description": "Checks RAM utilization",
                      "status": mem_status, "detail": mem_detail, "icon": "\U0001F9E0"})

        # CPU Usage
        cpu_status = "Pass"
        cpu_detail = "CPU usage within normal range"
        for ind in indicators:
            if ind.get("category") == "CPU":
                cpu_status = "Warning" if ind.get("severity") == "warning" else "Fail"
                cpu_detail = ind.get("message", "")
                break
        checks.append({"name": "CPU Usage", "description": "Checks processor utilization",
                      "status": cpu_status, "detail": cpu_detail, "icon": "\u2699"})

        # System File Integrity
        checks.append({"name": "System File Integrity", "description": "Windows system file verification (requires admin)",
                      "status": "Info", "detail": "Run SFC /scannow for detailed verification",
                      "icon": "\U0001F6E1"})

        # Startup Items
        checks.append({"name": "Startup Items", "description": "Review startup applications",
                      "status": "Info", "detail": "Check startup manager for high-impact items",
                      "icon": "\U0001F680"})

        # Temporary Files
        checks.append({"name": "Temporary Files", "description": "Check for accumulated temporary files",
                      "status": "Info", "detail": "Use Temp Cleaner to scan and review",
                      "icon": "\U0001F5D1"})

        # Windows Update
        checks.append({"name": "Windows Update", "description": "Check for pending updates",
                      "status": "Info", "detail": "Use system tools to check for updates",
                      "icon": "\U0001F504"})

        return checks

    def _build_recommendations(self, health, metrics, storage):
        recs = []
        indicators = health.get("indicators", [])
        for ind in indicators:
            sev = ind.get("severity", "info")
            if sev in ("warning", "error"):
                recs.append({
                    "severity": sev,
                    "title": ind.get("category", "System"),
                    "message": ind.get("message", ""),
                    "value": ind.get("current_value"),
                })
        # Add temp files recommendation
        recs.append({
            "severity": "info",
            "title": "Temporary Files",
            "message": "Run Temp Cleaner to find and review temporary files",
            "value": None,
        })
        return recs

    def get_system_info(self):
        metrics = self.metrics_service.get_all_metrics()
        si = metrics.get("system", {})
        mem = metrics.get("memory", {})
        return {
            "os_name": si.get("os_name", "Unknown"),
            "os_version": si.get("os_version", "Unknown"),
            "os_build": si.get("os_release", "Unknown"),
            "processor": si.get("processor", "Unknown"),
            "logical_cores": si.get("cpu_count_logical", 0),
            "physical_cores": si.get("cpu_count_physical", 0),
            "total_memory": mem.get("total_bytes"),
            "architecture": si.get("architecture", "Unknown"),
            "uptime_seconds": si.get("uptime_seconds"),
            "hostname": si.get("hostname", "Unknown"),
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

    def format_uptime(self, seconds):
        if seconds is None or seconds < 0:
            return "Unknown"
        seconds = int(seconds)
        if seconds < 60:
            return "%ds" % seconds
        if seconds < 3600:
            m = seconds // 60
            s = seconds % 60
            return "%dm %ds" % (m, s)
        d = seconds // 86400
        h = (seconds % 86400) // 3600
        m = (seconds % 3600) // 60
        if d > 0:
            return "%dd %dh %dm" % (d, h, m)
        return "%dh %dm" % (h, m)

    def is_checking(self):
        return self._is_checking
