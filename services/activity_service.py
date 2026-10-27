"""Activity service for PC-Toolbox dashboard."""

import time
from typing import Dict, List, Any, Optional
from datetime import datetime


class ActivityEvent:
    """Represents a single activity event."""
    
    def __init__(self, 
                 event_type: str,
                 message: str,
                 severity: str = "info",
                 timestamp: float = None,
                 metadata: Dict[str, Any] = None):
        self.event_type = event_type
        self.message = message
        self.severity = severity
        self.timestamp = timestamp or time.time()
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "event_type": self.event_type,
            "message": self.message,
            "severity": self.severity,
            "timestamp": self.timestamp,
            "timestamp_formatted": datetime.fromtimestamp(self.timestamp).strftime("%Y-%m-%d %H:%M:%S"),
            "metadata": self.metadata
        }


class ActivityService:
    """Service for tracking dashboard activity events."""
    
    def __init__(self, max_events: int = 100):
        self.max_events = max_events
        self._events: List[ActivityEvent] = []
        self._initialize_default_events()
    
    def _initialize_default_events(self):
        self.add_event(
            event_type="system",
            message="Dashboard initialized",
            severity="info"
        )
    
    def add_event(self, event_type: str, message: str, severity: str = "info", metadata: Dict[str, Any] = None):
        event = ActivityEvent(
            event_type=event_type,
            message=message,
            severity=severity,
            metadata=metadata
        )
        self._events.append(event)
        if len(self._events) > self.max_events:
            self._events = self._events[-self.max_events:]
        return event
    
    def get_recent_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        events = self._events[-limit:] if self._events else []
        return [event.to_dict() for event in reversed(events)]
    
    def get_events_by_type(self, event_type: str, limit: int = 50) -> List[Dict[str, Any]]:
        events = [e for e in self._events if e.event_type == event_type]
        events = events[-limit:] if events else []
        return [event.to_dict() for event in reversed(events)]
    
    def record_metrics_refresh(self, success: bool, metrics_count: int = 0):
        if success:
            self.add_event(
                event_type="metrics",
                message=f"Metrics refreshed successfully ({metrics_count} metrics)",
                severity="info",
                metadata={"metrics_count": metrics_count}
            )
        else:
            self.add_event(
                event_type="metrics",
                message="Metrics refresh failed",
                severity="error",
                metadata={"metrics_count": metrics_count}
            )
    
    def record_health_check(self, warning_count: int, error_count: int):
        if error_count > 0:
            severity = "error"
            message = f"Health check found {error_count} error(s) and {warning_count} warning(s)"
        elif warning_count > 0:
            severity = "warning"
            message = f"Health check found {warning_count} warning(s)"
        else:
            severity = "info"
            message = "Health check completed - all systems normal"
        
        self.add_event(
            event_type="health",
            message=message,
            severity=severity,
            metadata={
                "warning_count": warning_count,
                "error_count": error_count
            }
        )
    
    def clear_events(self):
        self._events.clear()
        self.add_event(
            event_type="system",
            message="Activity history cleared",
            severity="info"
        )
    
    def get_event_summary(self) -> Dict[str, Any]:
        total = len(self._events)
        by_type = {}
        by_severity = {"info": 0, "warning": 0, "error": 0}
        
        for event in self._events:
            event_type = event.event_type
            by_type[event_type] = by_type.get(event_type, 0) + 1
            if event.severity in by_severity:
                by_severity[event.severity] += 1
        
        return {
            "total_events": total,
            "by_type": by_type,
            "by_severity": by_severity,
            "has_events": total > 0
        }