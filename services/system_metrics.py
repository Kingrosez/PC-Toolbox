"""System metrics service for PC-Toolbox dashboard."""

import psutil
import platform
import time
from typing import Dict, Any, Optional


class SystemMetricsService:
    """Service for collecting real-time system metrics using psutil."""
    
    def __init__(self):
        pass
    
    def get_cpu_usage(self, interval: float = 0.1) -> Optional[float]:
        """
        Get CPU utilization percentage.
        
        Args:
            interval: Sampling interval in seconds for accurate measurement
            
        Returns:
            CPU usage percentage or None if unavailable
        """
        try:
            cpu_percent = psutil.cpu_percent(interval=interval)
            if cpu_percent is None:
                return None
            return round(cpu_percent, 1)
        except (psutil.Error, OSError, AttributeError) as e:
            return None
    
    def get_memory_info(self) -> Dict[str, Any]:
        """
        Get memory usage information.
        
        Returns:
            Dictionary with total, used, available RAM in bytes and utilization percentage
        """
        try:
            mem = psutil.virtual_memory()
            return {
                "total_bytes": mem.total,
                "used_bytes": mem.used,
                "available_bytes": mem.available,
                "percent_used": round(mem.percent, 1),
                "free_bytes": mem.free
            }
        except (psutil.Error, OSError, AttributeError) as e:
            return {
                "total_bytes": None,
                "used_bytes": None,
                "available_bytes": None,
                "percent_used": None,
                "free_bytes": None,
                "error": str(e)
            }
    
    def get_system_info(self) -> Dict[str, Any]:
        """
        Get basic system information.
        
        Returns:
            Dictionary with OS name, version, hostname, architecture, uptime
        """
        try:
            # Basic system info
            system_info = {
                "os_name": platform.system(),
                "os_version": platform.version(),
                "os_release": platform.release(),
                "hostname": platform.node(),
                "architecture": platform.machine(),
                "processor": platform.processor()
            }
            
            # CPU info
            try:
                system_info["cpu_count_physical"] = psutil.cpu_count(logical=False)
                system_info["cpu_count_logical"] = psutil.cpu_count(logical=True)
            except (psutil.Error, AttributeError):
                system_info["cpu_count_physical"] = None
                system_info["cpu_count_logical"] = None
            
            # Uptime
            try:
                boot_time = psutil.boot_time()
                uptime_seconds = time.time() - boot_time
                system_info["uptime_seconds"] = int(uptime_seconds)
                system_info["boot_time"] = boot_time
            except (psutil.Error, AttributeError, OSError):
                system_info["uptime_seconds"] = None
                system_info["boot_time"] = None
            
            return system_info
        except Exception as e:
            return {
                "os_name": None,
                "os_version": None,
                "hostname": None,
                "architecture": None,
                "error": str(e)
            }
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """
        Get all system metrics in a single call.
        
        Returns:
            Consolidated dictionary of all metrics
        """
        metrics = {
            "timestamp": time.time(),
            "cpu_usage": self.get_cpu_usage(),
            "memory": self.get_memory_info(),
            "system": self.get_system_info()
        }
        return metrics