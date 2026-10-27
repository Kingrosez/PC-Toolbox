"""Health indicators service for PC-Toolbox dashboard."""

from typing import Dict, List, Any
from enum import Enum


class HealthSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class HealthIndicator:
    def __init__(self, category: str, message: str, severity: HealthSeverity, 
                 metric_name: str = None, current_value: float = None, threshold: float = None):
        self.category = category
        self.message = message
        self.severity = severity
        self.metric_name = metric_name
        self.current_value = current_value
        self.threshold = threshold
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "message": self.message,
            "severity": self.severity.value,
            "metric_name": self.metric_name,
            "current_value": self.current_value,
            "threshold": self.threshold
        }


class HealthService:
    DEFAULT_THRESHOLDS = {
        "memory_usage": 85.0,
        "cpu_usage": 90.0,
        "disk_usage": 90.0,
        "critical_disk_usage": 95.0
    }
    
    def __init__(self, thresholds: Dict[str, float] = None):
        self.thresholds = thresholds or self.DEFAULT_THRESHOLDS.copy()
    
    def evaluate_metrics(self, metrics: Dict[str, Any], storage_summary: Dict[str, Any]) -> List[HealthIndicator]:
        indicators = []
        memory = metrics.get("memory", {})
        if memory.get("percent_used") is not None:
            indicators.extend(self._check_memory_usage(memory["percent_used"]))
        
        cpu_usage = metrics.get("cpu_usage")
        if cpu_usage is not None:
            indicators.extend(self._check_cpu_usage(cpu_usage))
        
        if storage_summary:
            indicators.extend(self._check_disk_usage(storage_summary))
        
        indicators.extend(self._check_collection_failures(metrics, storage_summary))
        return indicators
    
    def _check_memory_usage(self, percent_used: float) -> List[HealthIndicator]:
        indicators = []
        threshold = self.thresholds["memory_usage"]
        if percent_used >= threshold:
            indicators.append(HealthIndicator("Memory", f"High memory usage ({percent_used:.1f}%)", HealthSeverity.WARNING, "memory_usage", percent_used, threshold))
        elif percent_used >= threshold - 10:
            indicators.append(HealthIndicator("Memory", f"Memory usage elevated ({percent_used:.1f}%)", HealthSeverity.INFO, "memory_usage", percent_used, threshold))
        return indicators
    
    def _check_cpu_usage(self, cpu_percent: float) -> List[HealthIndicator]:
        indicators = []
        threshold = self.thresholds["cpu_usage"]
        if cpu_percent >= threshold:
            indicators.append(HealthIndicator("CPU", f"High CPU usage ({cpu_percent:.1f}%)", HealthSeverity.WARNING, "cpu_usage", cpu_percent, threshold))
        elif cpu_percent >= threshold - 15:
            indicators.append(HealthIndicator("CPU", f"CPU usage elevated ({cpu_percent:.1f}%)", HealthSeverity.INFO, "cpu_usage", cpu_percent, threshold))
        return indicators
    
    def _check_disk_usage(self, storage_summary: Dict[str, Any]) -> List[HealthIndicator]:
        indicators = []
        for drive in storage_summary.get("drives", []):
            if not drive.get("accessible"):
                indicators.append(HealthIndicator("Storage", f"Drive {drive.get('device')} inaccessible", HealthSeverity.ERROR, "drive_accessibility"))
                continue
            percent_used = drive.get("percent_used")
            if percent_used is None:
                continue
            device = drive.get("device", "Unknown")
            if percent_used >= self.thresholds["critical_disk_usage"]:
                indicators.append(HealthIndicator("Storage", f"Critical disk space on {device} ({percent_used:.1f}%)", HealthSeverity.ERROR, "disk_usage", percent_used, self.thresholds["critical_disk_usage"]))
            elif percent_used >= self.thresholds["disk_usage"]:
                indicators.append(HealthIndicator("Storage", f"Low disk space on {device} ({percent_used:.1f}%)", HealthSeverity.WARNING, "disk_usage", percent_used, self.thresholds["disk_usage"]))
        return indicators
    
    def _check_collection_failures(self, metrics: Dict[str, Any], storage_summary: Dict[str, Any]) -> List[HealthIndicator]:
        indicators = []
        if metrics.get("cpu_usage") is None:
            indicators.append(HealthIndicator("System", "Unable to collect CPU metrics", HealthSeverity.ERROR, "cpu_collection"))
        memory = metrics.get("memory", {})
        if memory.get("total_bytes") is None:
            indicators.append(HealthIndicator("System", "Unable to collect memory metrics", HealthSeverity.ERROR, "memory_collection"))
        if not storage_summary.get("drives"):
            indicators.append(HealthIndicator("System", "Unable to discover storage drives", HealthSeverity.WARNING, "storage_discovery"))
        return indicators
    
    def get_health_summary(self, metrics: Dict[str, Any], storage_summary: Dict[str, Any]) -> Dict[str, Any]:
        indicators = self.evaluate_metrics(metrics, storage_summary)
        summary = {"total": len(indicators), "errors": 0, "warnings": 0, "info": 0, "indicators": []}
        for indicator in indicators:
            indicator_dict = indicator.to_dict()
            summary["indicators"].append(indicator_dict)
            if indicator.severity == HealthSeverity.ERROR:
                summary["errors"] += 1
            elif indicator.severity == HealthSeverity.WARNING:
                summary["warnings"] += 1
            else:
                summary["info"] += 1
        if summary["errors"] > 0:
            summary["overall_status"] = "error"
        elif summary["warnings"] > 0:
            summary["overall_status"] = "warning"
        else:
            summary["overall_status"] = "good"
        return summary