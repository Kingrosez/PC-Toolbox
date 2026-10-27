"""Empty Folders discovery service for PC-Toolbox.

Scans directories for empty folders. No deletion is performed here.
"""

import os
import sys
import stat
import time
from typing import List, Dict, Any, Optional, Callable, Set

sys.path.insert(0, 'd:/Windows app/PC-Toolbox')

# Protected paths that must never be deleted or scanned aggressively.
PROTECTED_PATHS = [
    r"C:\Windows",
    r"C:\Program Files",
    r"C:\Program Files (x86)",
    r"C:\ProgramData",
    r"C:\$Recycle.Bin",
    r"C:\System Volume Information",
]


class EmptyFoldersService:
    """Discovers empty folders within approved roots."""

    def __init__(self, roots=None, exclusions=None):
        self._configured_roots = roots
        self._exclusions = set(os.path.normpath(p).lower() for p in (exclusions or []))
        self._seen_roots = set()
        self._scan_start = None
        self._scan_end = None
        self._locations_scanned = 0
        self._locations_attempted = 0

    # ---------------------------------------------------------------- helpers
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

    def _is_protected(self, path):
        norm = os.path.normpath(path).lower()
        for prot in PROTECTED_PATHS:
            prot_norm = os.path.normpath(prot).lower()
            if norm == prot_norm or norm.startswith(prot_norm + os.sep):
                return True
        return False

    def _is_excluded(self, path):
        norm = os.path.normpath(path).lower()
        if norm in self._exclusions:
            return True
        for exc in self._exclusions:
            if norm.startswith(exc + os.sep):
                return True
        return False

    def _compute_depth(self, root, path):
        try:
            rel = os.path.relpath(path, root)
            if rel == ".":
                return 0
            return rel.count(os.sep) + 1
        except Exception:
            return 0

    # ---------------------------------------------------------------- scanning
    def scan(self, roots=None, cancel_check=None, progress_callback=None):
        self._scan_start = time.monotonic()
        self._locations_scanned = 0
        self._locations_attempted = 0

        approved = self.get_approved_roots() if roots is None else self._validate_roots(roots)
        if roots is not None:
            approved = self._validate_roots(roots)

        results = []
        errors = []
        seen_paths = set()

        for root in approved:
            if cancel_check and cancel_check():
                break
            self._locations_attempted += 1
            if not os.path.isdir(root):
                errors.append("Root not accessible or not a directory: %s" % root)
                continue
            if self._is_protected(root):
                errors.append("Protected root skipped: %s" % root)
                continue
            self._locations_scanned += 1
            try:
                self._scan_dir(root, root, 0, results, errors, seen_paths, cancel_check, progress_callback)
            except Exception as e:
                errors.append("Error scanning root %s: %s" % (root, str(e)))

        self._scan_end = time.monotonic()

        return {
            "folders": results,
            "folder_count": len(results),
            "locations_scanned": self._locations_scanned,
            "locations_attempted": self._locations_attempted,
            "scan_duration": self._scan_end - self._scan_start,
            "errors": errors,
            "skipped": [],
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
                if self._is_protected(a):
                    continue
                rp = os.path.realpath(a)
                if rp in seen:
                    continue
                seen.add(rp)
                v.append(a)
            except Exception:
                continue
        return v

    def _scan_dir(self, root, current_dir, depth, results, errors, seen_paths, cancel_check, progress_callback):
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
            errors.append("OS error scanning %s: %s" % (current_dir, str(e)))
            return

        file_count = 0
        subdirs = []
        for entry in entries:
            if cancel_check and cancel_check():
                return
            try:
                if entry.is_symlink():
                    continue
                if entry.is_dir(follow_symlinks=False):
                    if not self._is_reparse_point(entry.path):
                        subdirs.append(entry.path)
                elif entry.is_file(follow_symlinks=False):
                    file_count += 1
            except OSError:
                continue

        # A folder is empty only if it has no files and no subdirectories.
        if file_count == 0 and len(subdirs) == 0:
            rp = os.path.realpath(current_dir)
            if rp not in seen_paths:
                seen_paths.add(rp)
                try:
                    mtime = os.path.getmtime(current_dir)
                except OSError:
                    mtime = None
                results.append({
                    "path": os.path.abspath(current_dir),
                    "parent": os.path.dirname(os.path.abspath(current_dir)),
                    "mtime": mtime,
                    "depth": depth,
                    "file_count": 0,
                    "subfolder_count": 0,
                    "size_bytes": 0,
                    "root": root,
                })
                if progress_callback:
                    progress_callback(len(results))

        # Recurse into subdirectories.
        for subdir in subdirs:
            if cancel_check and cancel_check():
                return
            self._scan_dir(root, subdir, depth + 1, results, errors, seen_paths, cancel_check, progress_callback)

    def get_elapsed_seconds(self):
        if self._scan_start is None:
            return None
        end = self._scan_end if self._scan_end is not None else time.monotonic()
        return end - self._scan_start

    # ---------------------------------------------------------------- deletion
    def validate_deletion(self, path, approved_roots):
        """Validate a path is safe to delete. Returns (ok, reason)."""
        if not path:
            return False, "Empty path"
        try:
            norm = os.path.normpath(path)
        except Exception:
            return False, "Invalid path"
        if self._is_root_path(norm):
            return False, "Cannot delete filesystem root"
        if self._is_protected(norm):
            return False, "Protected directory"
        if self._is_reparse_point(norm):
            return False, "Reparse point / symlink / junction"
        # Check approved roots
        in_approved = False
        for root in approved_roots:
            root_norm = os.path.normpath(root)
            if norm == root_norm:
                return False, "Cannot delete scan root itself"
            if norm.startswith(root_norm + os.sep):
                in_approved = True
                break
        if not in_approved:
            return False, "Path outside approved roots"
        # Re-check emptiness
        try:
            with os.scandir(norm) as it:
                for _ in it:
                    return False, "Folder is no longer empty"
        except FileNotFoundError:
            return False, "Folder no longer exists"
        except PermissionError:
            return False, "Permission denied"
        except OSError as e:
            return False, "OS error: %s" % str(e)
        return True, "OK"

    def delete_folder(self, path, approved_roots):
        """Delete a single folder if safe. Returns (success, reason)."""
        ok, reason = self.validate_deletion(path, approved_roots)
        if not ok:
            return False, reason
        try:
            os.rmdir(path)
            return True, "Deleted"
        except FileNotFoundError:
            return False, "Folder no longer exists"
        except PermissionError:
            return False, "Permission denied"
        except OSError as e:
            return False, "OS error: %s" % str(e)
