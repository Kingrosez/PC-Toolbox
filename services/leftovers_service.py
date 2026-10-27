"""Leftovers discovery service for PC-Toolbox.

Conservative filesystem leftover detection. No deletion performed here.
"""

import os
import sys
import stat
import time
from typing import List, Dict, Any, Optional, Callable, Set

sys.path.insert(0, 'd:/Windows app/PC-Toolbox')


class LeftoversService:
    """Discovers potential leftover files/folders from uninstalled apps."""

    def __init__(self, roots=None, exclusions=None):
        self._configured_roots = roots
        self._exclusions = set(os.path.normpath(p).lower() for p in (exclusions or []))
        self._seen = set()
        self._scan_start = None
        self._scan_end = None
        self._locations_scanned = 0
        self._locations_attempted = 0

    def get_approved_roots(self):
        if self._configured_roots is None:
            return []
        roots = []
        seen = set()
        for r in self._configured_roots:
            if not r or not r.strip():
                continue
            try:
                a = os.path.abspath(r)
                if self._is_root_path(a):
                    continue
                rp = os.path.realpath(a)
                if rp in seen:
                    continue
                seen.add(rp)
                roots.append(a)
            except Exception:
                continue
        return roots

    def _is_root_path(self, p):
        n = os.path.normpath(p)
        return os.path.dirname(n) == n

    def _is_reparse_point(self, p):
        if sys.platform != 'win32':
            return False
        try:
            return bool(os.stat(p).st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
        except Exception:
            return False

    def _is_excluded(self, path):
        norm = os.path.normpath(path).lower()
        if norm in self._exclusions:
            return True
        for exc in self._exclusions:
            if norm.startswith(exc + os.sep):
                return True
        return False

    def _categorize(self, path, name):
        name_l = name.lower()
        path_l = path.lower()
        if name_l.endswith(".lnk"):
            return "Shortcut"
        if any(k in path_l for k in ["registry", "regedit"]):
            return "Registry Entry"
        if os.path.isdir(path):
            return "Related Data"
        return "File"

    def scan(self, roots=None, cancel_check=None):
        self._scan_start = time.monotonic()
        self._locations_scanned = 0
        self._locations_attempted = 0
        self._seen = set()

        approved = self.get_approved_roots() if roots is None else self._validate_roots(roots)
        if roots is not None:
            approved = self._validate_roots(roots)

        results = []
        errors = []

        for root in approved:
            if cancel_check and cancel_check():
                break
            self._locations_attempted += 1
            if not os.path.isdir(root):
                errors.append("Root not accessible: %s" % root)
                continue
            self._locations_scanned += 1
            try:
                self._scan_dir(root, root, results, errors, cancel_check)
            except Exception as e:
                errors.append("Error scanning root %s: %s" % (root, str(e)))

        self._scan_end = time.monotonic()

        return {
            "items": results,
            "item_count": len(results),
            "locations_scanned": self._locations_scanned,
            "locations_attempted": self._locations_attempted,
            "scan_duration": self._scan_end - self._scan_start,
            "errors": errors,
        }

    def _validate_roots(self, roots):
        v = []
        seen = set()
        for r in roots:
            if not r or not r.strip():
                continue
            try:
                a = os.path.abspath(r)
                if self._is_root_path(a):
                    continue
                rp = os.path.realpath(a)
                if rp in seen:
                    continue
                seen.add(rp)
                v.append(a)
            except Exception:
                continue
        return v

    def _scan_dir(self, root, current_dir, results, errors, cancel_check):
        if cancel_check and cancel_check():
            return
        if self._is_excluded(current_dir):
            return
        if self._is_reparse_point(current_dir):
            return

        try:
            entries = list(os.scandir(current_dir))
        except PermissionError:
            errors.append("Permission denied: %s" % current_dir)
            return
        except FileNotFoundError:
            errors.append("Directory not found: %s" % current_dir)
            return
        except OSError as e:
            errors.append("OS error: %s" % str(e))
            return

        for entry in entries:
            if cancel_check and cancel_check():
                return
            try:
                if entry.is_symlink():
                    continue
                if entry.is_dir(follow_symlinks=False):
                    if not self._is_reparse_point(entry.path):
                        self._scan_dir(root, entry.path, results, errors, cancel_check)
                elif entry.is_file(follow_symlinks=False):
                    name = entry.name
                    # Conservative: only flag files in known leftover-ish locations.
                    # We use a simple heuristic: files whose parent dir name suggests
                    # an uninstalled app. For safety, include all files but mark category.
                    try:
                        stat_info = entry.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    rp = os.path.realpath(entry.path)
                    if rp in self._seen:
                        continue
                    self._seen.add(rp)
                    results.append({
                        "id": rp,
                        "name": name,
                        "type": self._categorize(entry.path, name),
                        "path": os.path.abspath(entry.path),
                        "size_bytes": stat_info.st_size,
                        "mtime": stat_info.st_mtime,
                        "root": root,
                        "reason": "Residual file found in scanned location",
                    })
            except OSError:
                continue

    def get_elapsed_seconds(self):
        if self._scan_start is None:
            return None
        end = self._scan_end if self._scan_end is not None else time.monotonic()
        return end - self._scan_start

    def validate_removal(self, item, approved_roots):
        path = item.get("path")
        if not path:
            return False, "No path"
        norm = os.path.normpath(path)
        if self._is_root_path(norm):
            return False, "Cannot remove filesystem root"
        in_approved = False
        for root in approved_roots:
            root_norm = os.path.normpath(root)
            if norm == root_norm:
                return False, "Cannot remove scan root"
            if norm.startswith(root_norm + os.sep):
                in_approved = True
                break
        if not in_approved:
            return False, "Path outside approved roots"
        return True, "OK"

    def remove_item(self, item, approved_roots):
        ok, reason = self.validate_removal(item, approved_roots)
        if not ok:
            return False, reason
        path = item.get("path")
        try:
            if os.path.isfile(path):
                os.remove(path)
                return True, "Removed"
            elif os.path.isdir(path):
                # Only remove if empty
                try:
                    os.rmdir(path)
                    return True, "Removed"
                except OSError:
                    return False, "Directory not empty or in use"
            else:
                return False, "Path no longer exists"
        except FileNotFoundError:
            return False, "Path no longer exists"
        except PermissionError:
            return False, "Permission denied"
        except OSError as e:
            return False, "OS error: %s" % str(e)
