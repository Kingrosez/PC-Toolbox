"""Storage service for PC-Toolbox dashboard."""

import psutil
from typing import Dict, List, Any, Optional


class StorageService:
    """Service for discovering and monitoring storage drives."""
    
    def __init__(self):
        self._drive_type_map = {
            0: "Unknown",
            1: "No Root Dir",
            2: "Removable",
            3: "Fixed",
            4: "Remote",
            5: "CDROM",
            6: "RAM"
        }
    
    def get_drives_info(self) -> List[Dict[str, Any]]:
        """
        Discover and collect information about available drives.
        
        Returns:
            List of dictionaries with drive information
        """
        drives = []
        
        try:
            partitions = psutil.disk_partitions(all=False)
        except (psutil.Error, OSError) as e:
            return []
        
        for partition in partitions:
            try:
                drive_info = self._get_drive_info(partition)
                if drive_info:
                    drives.append(drive_info)
            except (psutil.Error, OSError, PermissionError) as e:
                # Continue with other drives if one fails
                continue
        
        return drives
    
    def _get_drive_info(self, partition) -> Optional[Dict[str, Any]]:
        """
        Get information for a single drive partition.
        
        Args:
            partition: psutil partition object
            
        Returns:
            Dictionary with drive information or None if unavailable
        """
        try:
            # Basic partition info
            device = partition.device
            mountpoint = partition.mountpoint
            fstype = partition.fstype
            opts = partition.opts
            
            # Determine drive type
            drive_type = self._get_drive_type(device, mountpoint)
            
            # Skip if not a fixed drive or accessible drive on Windows
            if self._should_skip_drive(device, mountpoint, drive_type):
                return None
            
            # Get disk usage
            try:
                usage = psutil.disk_usage(mountpoint)
                total_bytes = usage.total
                used_bytes = usage.used
                free_bytes = usage.free
                percent_used = round((used_bytes / total_bytes * 100) if total_bytes > 0 else 0, 1)
            except (psutil.Error, OSError, PermissionError):
                # Drive is inaccessible
                total_bytes = None
                used_bytes = None
                free_bytes = None
                percent_used = None
            
            drive_info = {
                "device": device,
                "mountpoint": mountpoint,
                "filesystem": fstype,
                "options": opts,
                "drive_type": drive_type,
                "total_bytes": total_bytes,
                "used_bytes": used_bytes,
                "free_bytes": free_bytes,
                "percent_used": percent_used,
                "accessible": total_bytes is not None
            }
            
            return drive_info
            
        except Exception:
            return None
    
    def _get_drive_type(self, device: str, mountpoint: str) -> str:
        """
        Determine drive type based on device and mountpoint.
        
        Args:
            device: Device path
            mountpoint: Mount point
            
        Returns:
            Drive type string
        """
        # Try to use psutil to get drive type where available
        try:
            # On Windows, check drive type using Windows API or heuristic
            if ':' in device or ':' in mountpoint:
                # Likely a Windows drive letter
                return "Fixed"
        except:
            pass
        
        return "Unknown"
    
    def _should_skip_drive(self, device: str, mountpoint: str, drive_type: str) -> bool:
        """
        Determine if a drive should be skipped.
        
        Args:
            device: Device path
            mountpoint: Mount point
            drive_type: Drive type
            
        Returns:
            True if drive should be skipped
        """
        # Skip system reserved partitions and other special mounts
        if device and device.lower() in ['\\device\\harddiskvolume1', '']:
            return True
        
        # On Windows, skip non-fixed drives for main dashboard view
        # but still include them in the list with proper type
        return False
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """
        Get consolidated storage statistics.
        
        Returns:
            Dictionary with total and used space across all accessible drives
        """
        drives = self.get_drives_info()
        
        total_space = 0
        used_space = 0
        free_space = 0
        accessible_count = 0
        
        for drive in drives:
            if drive.get("accessible") and drive.get("total_bytes"):
                total_space += drive["total_bytes"]
                used_space += drive["used_bytes"] or 0
                free_space += drive["free_bytes"] or 0
                accessible_count += 1
        
        return {
            "drives": drives,
            "total_drives": len(drives),
            "accessible_drives": accessible_count,
            "total_space_bytes": total_space,
            "used_space_bytes": used_space,
            "free_space_bytes": free_space,
            "percent_used": round((used_space / total_space * 100) if total_space > 0 else 0, 1)
        }