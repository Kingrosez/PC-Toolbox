"""Dashboard controller for PC-Toolbox."""

import sys
sys.path.insert(0, 'd:/Windows app/PC-Toolbox')

from typing import Dict, Any, Optional
from services.system_metrics import SystemMetricsService
from services.storage_service import StorageService
from services.health_service import HealthService
from services.activity_service import ActivityService


class DashboardController:
    """Controller for coordinating dashboard data collection and presentation."""
    
    def __init__(self):
        self.system_metrics_service = SystemMetricsService()
        self.storage_service = StorageService()
        self.health_service = HealthService()
        self.activity_service = ActivityService()
        
        self._last_refresh_time = None
        self._current_data = None
    
    @property
    def data(self) -> Optional[Dict[str, Any]]:
        """Provide backward compatible data property."""
        return self._current_data
    
    def refresh_data(self) -> Dict[str, Any]:
        try:
            metrics = self.system_metrics_service.get_all_metrics()
            storage_summary = self.storage_service.get_summary_stats()
            health_summary = self.health_service.get_health_summary(metrics, storage_summary)
            recent_activity = self.activity_service.get_recent_events(limit=10)
            activity_summary = self.activity_service.get_event_summary()
            
            success = (metrics.get("cpu_usage") is not None or metrics.get("memory", {}).get("total_bytes") is not None)
            self.activity_service.record_metrics_refresh(success, metrics_count=3)
            self.activity_service.record_health_check(
                warning_count=health_summary.get("warnings", 0),
                error_count=health_summary.get("errors", 0)
            )
            
            dashboard_data = {
                "timestamp": metrics.get("timestamp"),
                "system_metrics": metrics,
                "storage": storage_summary,
                "health": health_summary,
                "activity": {
                    "recent_events": recent_activity,
                    "summary": activity_summary
                },
                "refresh_status": "success" if success else "partial",
                "error": None
            }
            
            self._current_data = dashboard_data
            return dashboard_data
            
        except Exception as e:
            error_data = {
                "timestamp": None,
                "system_metrics": {},
                "storage": {"drives": [], "total_drives": 0},
                "health": {"overall_status": "error", "errors": 1, "warnings": 0, "total": 1, "indicators": []},
                "activity": {"recent_events": [], "summary": {}},
                "refresh_status": "error",
                "error": str(e)
            }
            
            self.activity_service.add_event(
                event_type="system",
                message=f"Dashboard refresh failed: {str(e)}",
                severity="error"
            )
            
            self._current_data = error_data
            return error_data
    
    def get_system_overview(self) -> Dict[str, Any]:
        if not self._current_data:
            self.refresh_data()
        
        metrics = self._current_data.get("system_metrics", {})
        system_info = metrics.get("system", {})
        memory = metrics.get("memory", {})
        
        return {
            "cpu_usage": metrics.get("cpu_usage"),
            "memory_total_bytes": memory.get("total_bytes"),
            "memory_used_bytes": memory.get("used_bytes"),
            "memory_percent": memory.get("percent_used"),
            "uptime_seconds": system_info.get("uptime_seconds"),
            "hostname": system_info.get("hostname"),
            "os_name": system_info.get("os_name"),
            "os_version": system_info.get("os_version"),
            "architecture": system_info.get("architecture"),
            "cpu_physical_cores": system_info.get("cpu_count_physical"),
            "cpu_logical_cores": system_info.get("cpu_count_logical")
        }
    
    def get_storage_overview(self) -> Dict[str, Any]:
        if not self._current_data:
            self.refresh_data()
        
        storage = self._current_data.get("storage", {})
        
        return {
            "drives": storage.get("drives", []),
            "total_drives": storage.get("total_drives", 0),
            "accessible_drives": storage.get("accessible_drives", 0),
            "total_space_bytes": storage.get("total_space_bytes", 0),
            "used_space_bytes": storage.get("used_space_bytes", 0),
            "free_space_bytes": storage.get("free_space_bytes", 0),
            "percent_used": storage.get("percent_used", 0)
        }
    
    def get_health_summary(self) -> Dict[str, Any]:
        if not self._current_data:
            self.refresh_data()
        
        return self._current_data.get("health", {})
    
    def get_recent_activity(self, limit: int = 10) -> Dict[str, Any]:
        if not self._current_data:
            self.refresh_data()
        
        activity = self._current_data.get("activity", {})
        
        return {
            "recent_events": activity.get("recent_events", [])[:limit],
            "summary": activity.get("summary", {})
        }
    
    def format_bytes(self, bytes_value: Optional[int]) -> str:
        if bytes_value is None:
            return "Unknown"
        
        for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.1f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.1f} EB"
    
    def format_uptime(self, seconds: Optional[int]) -> str:
        if seconds is None:
            return "Unknown"
        
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        minutes = (seconds % 3600) // 60
        
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
    
    def get_cached_data(self) -> Optional[Dict[str, Any]]:
        return self._current_data