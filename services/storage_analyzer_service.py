"""Storage Analyzer service for PC-Toolbox.

Scans a selected drive/folder for files and folders, calculates sizes.
No deletion performed.
"""

import os
import sys
import time
from typing import List, Dict, Any, Optional, Callable

sys.path.insert(0, 'd:/Windows app/PC-Toolbox')

import psutil


class StorageAnalyzerService:
    """Analyzes disk usage for a selected drive or folder."""

    def __init__(self):
        self._storage_service = None
        try:
            from services.storage_service import StorageService
            self._storage_service = StorageService()
        except Exception:
            pass

    def get_drives(self):
        if self._storage_service:
            return self._storage_service.get_drives_info()
        drives = []
        try:
            for p in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(p.mountpoint)
                    drives.append({
                        "device": p.device,
                        "mountpoint": p.mountpoint,
                        "filesystem": p.fstype,
                        "total_bytes": usage.total,
                        "used_bytes": usage.used,
                        "free_bytes": usage.free,
                        "percent_used": round(usage.used / usage.total * 100, 1) if usage.total > 0 else 0,
                        "accessible": True,
                    })
                except Exception:
                    continue
        except Exception:
            pass
        return drives

    def analyze(self, root_path, cancel_check=None, progress_callback=None):
        start = time.monotonic()
        items = []
        errors = []
        seen = set()
        total_size = 0
        file_count = 0
        folder_count = 0

        if not root_path or not os.path.isdir(root_path):
            return {
                "items": [], "errors": ["Invalid or inaccessible root: %s" % root_path],
                "total_size": 0, "file_count": 0, "folder_count": 0,
                "scan_duration": 0.0, "root": root_path,
            }

        # Walk the tree
        try:
            for dirpath, dirnames, filenames in os.walk(root_path, topdown=True, followlinks=False):
                if cancel_check and cancel_check():
                    break
                # Skip reparse points / symlinks
                try:
                    if os.path.islink(dirpath):
                        dirnames[:] = []
                        continue
                except Exception:
                    pass
                # Filter out symlinked dirs
                dirnames[:] = [d for d in dirnames if not os.path.islink(os.path.join(dirpath, d))]

                # Calculate folder size (sum of files directly, not recursive double-count)
                folder_size = 0
                for fn in filenames:
                    if cancel_check and cancel_check():
                        break
                    fpath = os.path.join(dirpath, fn)
                    try:
                        st = os.stat(fpath, follow_symlinks=False)
                        sz = st.st_size
                        folder_size += sz
                        total_size += sz
                        file_count += 1
                        ext = os.path.splitext(fn)[1].lower()
                        items.append({
                            "id": fpath,
                            "name": fn,
                            "path": fpath,
                            "type": "File",
                            "size_bytes": sz,
                            "mtime": st.st_mtime,
                            "extension": ext,
                            "root": root_path,
                        })
                    except (OSError, PermissionError):
                        errors.append("Cannot access: %s" % fpath)
                        continue
                folder_count += 1
                if dirpath != root_path:
                    items.append({
                        "id": dirpath,
                        "name": os.path.basename(dirpath) or dirpath,
                        "path": dirpath,
                        "type": "Folder",
                        "size_bytes": folder_size,
                        "mtime": None,
                        "extension": "",
                        "root": root_path,
                    })
                if progress_callback:
                    progress_callback(len(items))
        except Exception as e:
            errors.append("Scan error: %s" % str(e))

        duration = time.monotonic() - start

        # Calculate file type distribution
        type_stats = self._calculate_type_stats(items)

        return {
            "items": items,
            "errors": errors,
            "total_size": total_size,
            "file_count": file_count,
            "folder_count": folder_count,
            "scan_duration": duration,
            "root": root_path,
            "type_stats": type_stats,
        }

    def _calculate_type_stats(self, items):
        groups = {
            "Documents": [".doc", ".docx", ".pdf", ".txt", ".rtf", ".odt", ".xls", ".xlsx", ".ppt", ".pptx", ".csv"],
            "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".ico", ".webp", ".tiff"],
            "Videos": [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm"],
            "Audio": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a"],
            "Archives": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"],
            "Applications": [".exe", ".msi", ".dll", ".bat", ".cmd", ".ps1"],
        }
        stats = {k: 0 for k in groups}
        stats["Other"] = 0
        for item in items:
            if item.get("type") != "File":
                continue
            ext = item.get("extension", "").lower()
            sz = item.get("size_bytes", 0) or 0
            matched = False
            for group, exts in groups.items():
                if ext in exts:
                    stats[group] += sz
                    matched = True
                    break
            if not matched:
                stats["Other"] += sz
        return stats

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
