"""Temp Cleaner scanning service for PC-Toolbox.

Provides safe discovery of temporary files within explicitly approved roots.
No deletion is performed by this service.
"""

import os
import sys
from typing import List, Dict, Any, Optional, Set, Callable

sys.path.insert(0, 'd:/Windows app/PC-Toolbox')


class TempCleanerService:
    """Service for scanning approved temporary directories safely."""

    DEFAULT_WINDOWS_TEMP = r"C:\Windows\Temp"

    def __init__(self, roots: Optional[List[str]] = None):
        self._configured_roots = roots
        self._seen_paths: Set[str] = set()
    def _is_root_path(self, path: str) -> bool:
        """Return True if path is a filesystem root (e.g., drive letter root on Windows)."""
        norm = os.path.normpath(path)
        # On Windows, a root is like 'C:\\' where dirname returns same
        if os.path.dirname(norm) == norm:
            return True
        return False


    def get_approved_roots(self) -> List[str]:
        if self._configured_roots is not None:
            roots = self._configured_roots
        else:
            roots = self._discover_default_roots()
        validated: List[str] = []
        seen_real: Set[str] = set()
        for r in roots:
            if not r:
                continue
            try:
                abs_path = os.path.abspath(r)
                if abs_path in ('', '/', '\\', 'C:\\'):
                    continue
                if not os.path.isdir(abs_path):
                    continue
                real_path = os.path.realpath(abs_path)
                if real_path in seen_real:
                    continue
                seen_real.add(real_path)
                validated.append(abs_path)
            except (OSError, ValueError):
                continue
        return validated

    def _discover_default_roots(self) -> List[str]:
        candidates: List[str] = []
        for var in ('TEMP', 'TMP'):
            val = os.environ.get(var)
            if val:
                if not val.strip():
                    continue
                if os.path.normpath(val) in ('/', '\\', 'C:\\'):
                    continue
                candidates.append(val)
        uniq = []
        seen = set()
        for c in candidates:
            norm = os.path.normcase(os.path.abspath(c))
            if norm not in seen:
                seen.add(norm)
                uniq.append(c)
        if os.path.isdir(self.DEFAULT_WINDOWS_TEMP):
            uniq.append(self.DEFAULT_WINDOWS_TEMP)
        return uniq

    def scan(self, roots: Optional[List[str]] = None, cancel_check: Optional[Callable[[], bool]] = None) -> Dict[str, Any]:
        approved_roots = self.get_approved_roots() if roots is None else roots
        if roots is not None:
            approved_roots = self._validate_roots(roots)

        files: List[Dict[str, Any]] = []
        errors: List[str] = []
        skipped: List[str] = []
        self._seen_paths = set()

        for root in approved_roots:
            if cancel_check and cancel_check():
                skipped.append(f"Scan cancelled at root {root}")
                break
            try:
                if not os.path.isdir(root):
                    errors.append(f"Root not accessible or not a directory: {root}")
                    continue
                self._scan_dir(root, root, files, errors, skipped, cancel_check)
            except OSError as e:
                errors.append(f"Error scanning root {root}: {e}")

        total_size = sum(f['size'] for f in files)
        return {
            'files': files,
            'total_size': total_size,
            'file_count': len(files),
            'errors': errors,
            'skipped': skipped,
        }

    def _validate_roots(self, roots: List[str]) -> List[str]:
        validated: List[str] = []
        seen_real: Set[str] = set()
        for r in roots:
            if not r:
                continue
            try:
                abs_path = os.path.abspath(r)
                if self._is_root_path(abs_path):
                    continue
                if not os.path.isdir(abs_path):
                    continue
                real_path = os.path.realpath(abs_path)
                if real_path in seen_real:
                    continue
                seen_real.add(real_path)
                validated.append(abs_path)
            except (OSError, ValueError):
                continue
        return validated

    def _scan_dir(self, root: str, current_dir: str, files: List[Dict[str, Any]], errors: List[str], skipped: List[str], cancel_check: Optional[Callable[[], bool]]):
        try:
            with os.scandir(current_dir) as it:
                for entry in it:
                    if cancel_check and cancel_check():
                        return
                    try:
                        if entry.is_symlink():
                            skipped.append(f"Skipped symlink: {entry.path}")
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            self._scan_dir(root, entry.path, files, errors, skipped, cancel_check)
                        elif entry.is_file(follow_symlinks=False):
                            try:
                                stat_res = entry.stat(follow_symlinks=False)
                            except OSError as e:
                                errors.append(f"Stat error for {entry.path}: {e}")
                                continue
                            real_path = os.path.realpath(entry.path)
                            if real_path in self._seen_paths:
                                continue
                            self._seen_paths.add(real_path)
                            files.append({
                                'path': os.path.abspath(entry.path),
                                'size': stat_res.st_size,
                                'mtime': stat_res.st_mtime,
                                'root': root,
                            })
                    except OSError as e:
                        errors.append(f"Error accessing {entry.path}: {e}")
                        continue
        except PermissionError as e:
            errors.append(f"Permission denied for directory {current_dir}: {e}")
        except FileNotFoundError:
            errors.append(f"Directory not found during scan: {current_dir}")
        except OSError as e:
            errors.append(f"OS error scanning directory {current_dir}: {e}")

