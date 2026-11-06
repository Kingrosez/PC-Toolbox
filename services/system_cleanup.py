"""Safe system and developer junk scanning/cleanup for PC-Toolbox.

The module contains filesystem and command logic only.  UI code lives in
``views/leftovers.py``.  Every deletion is validated against an explicit
allowlist owned by the category that produced the item.
"""

from __future__ import annotations

import ctypes
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import psutil

try:
    from send2trash import send2trash as _send2trash
except Exception:  # pragma: no cover - optional dependency
    _send2trash = None


TIER_SAFE = 1
TIER_DEVELOPER = 2
TIER_SYSTEM = 3
TIER_REPORT = 4

TIER_LABELS = {
    TIER_SAFE: "Tier 1 - Safe junk",
    TIER_DEVELOPER: "Tier 2 - Developer leftovers",
    TIER_SYSTEM: "Tier 3 - System-level (admin only)",
    TIER_REPORT: "Tier 4 - Report only",
}

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
ProgressCallback = Optional[Callable[[int, int, str], None]]
StatusCallback = Optional[Callable[[str], None]]
CancelCheck = Optional[Callable[[], bool]]


def format_size(size_bytes: Optional[int]) -> str:
    """Return a human readable size."""
    if size_bytes is None or size_bytes < 0:
        return "Unknown"
    value = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024.0:
            return "%.1f %s" % (value, unit)
        value /= 1024.0
    return "%.1f PB" % value


def is_admin() -> bool:
    """Return True when the current process is elevated on Windows."""
    if os.name != "nt":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def run_command(args: Sequence[str], timeout: int = 120) -> Tuple[int, str]:
    """Run a fixed argument list without a shell and capture output."""
    try:
        proc = subprocess.run(
            list(args),
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            shell=False,
            creationflags=CREATE_NO_WINDOW,
        )
        output = ((proc.stdout or "") + (proc.stderr or "")).strip()
        return proc.returncode, output
    except FileNotFoundError:
        return -1, "Command not found: %s" % args[0]
    except subprocess.TimeoutExpired:
        return -1, "Command timed out after %s seconds" % timeout
    except OSError as exc:
        return -1, str(exc)


def _expand(path: str) -> str:
    return os.path.expandvars(os.path.expanduser(str(path)))


def _normalized(path: str) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(_expand(path))))


def _is_root_path(path: str) -> bool:
    if not path:
        return True
    norm = os.path.normpath(os.path.abspath(_expand(path)))
    if os.path.dirname(norm) == norm:
        return True
    if len(norm) <= 3 and norm.endswith(":"):
        return True
    return norm in ("/", "\\")


def _is_reparse(path: str) -> bool:
    try:
        info = os.lstat(path)
    except OSError:
        return False
    if stat.S_ISLNK(info.st_mode):
        return True
    attrs = getattr(info, "st_file_attributes", 0)
    return bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def _is_under(path: str, root: str) -> bool:
    try:
        p = _normalized(path)
        r = _normalized(root)
        return p == r or p.startswith(r + os.sep)
    except (OSError, ValueError):
        return False


def _dedupe_paths(paths: Iterable[str]) -> List[str]:
    result: List[str] = []
    seen: Set[str] = set()
    for raw in paths:
        if not raw:
            continue
        try:
            expanded = os.path.abspath(_expand(raw))
            key = os.path.normcase(os.path.normpath(expanded))
        except (OSError, ValueError):
            continue
        if key in seen or _is_root_path(expanded):
            continue
        seen.add(key)
        result.append(expanded)
    return result


def _default_protected_roots() -> List[str]:
    home = os.path.expanduser("~")
    names = ["Documents", "Desktop", "Pictures", "Downloads", "OneDrive"]
    roots = [os.path.join(home, name) for name in names]
    for env_name in ("OneDrive", "OneDriveCommercial", "OneDriveConsumer"):
        value = os.environ.get(env_name)
        if value:
            roots.append(value)
    return _dedupe_paths(roots)


def _has_reparse_component(path: str, stop_at: str) -> bool:
    current = os.path.abspath(_expand(path))
    stop = _normalized(stop_at)
    while True:
        if _is_reparse(current):
            return True
        if os.path.normcase(os.path.normpath(current)) == stop:
            return False
        parent = os.path.dirname(current)
        if parent == current:
            return False
        current = parent


class PathPolicy:
    """Explicit allowlist and path safety validation."""

    def __init__(
        self,
        allowed_roots: Iterable[str],
        allow_exact_roots: Optional[Iterable[str]] = None,
        protected_roots: Optional[Iterable[str]] = None,
    ):
        self.allowed_roots = _dedupe_paths(allowed_roots)
        self.allow_exact_roots = {
            _normalized(p) for p in (allow_exact_roots or []) if p
        }
        self.protected_roots = _dedupe_paths(
            protected_roots if protected_roots is not None else _default_protected_roots()
        )
        self._deny_exact = {
            _normalized(os.environ.get("SystemRoot", r"C:\Windows")),
            _normalized(os.environ.get("SystemDrive", "C:") + "\\Users"),
        }
        self._deny_trees = [
            _normalized(os.environ.get("ProgramFiles", r"C:\Program Files")),
            _normalized(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
        ] + [_normalized(p) for p in self.protected_roots]

    def validate(
        self,
        path: str,
        allow_exact: bool = False,
        allow_contents_root: bool = False,
    ) -> Tuple[bool, str]:
        """Validate a path against the allowlist and global safety rules.

        ``allow_exact`` permits deleting a root that is explicitly listed in
        ``allow_exact_roots``.  ``allow_contents_root`` permits operating on the
        contents of an allowlisted root without permitting deletion of the root
        itself.
        """
        if not path or not isinstance(path, str):
            return False, "No path supplied"
        try:
            expanded = _expand(path)
        except (OSError, ValueError) as exc:
            return False, "Invalid path: %s" % exc
        if not os.path.isabs(expanded):
            return False, "Path is not absolute"
        if expanded.startswith("\\\\") or expanded.startswith("//"):
            return False, "UNC paths are not allowed"
        abs_path = os.path.abspath(expanded)
        norm = _normalized(abs_path)

        if _is_root_path(abs_path):
            return False, "Cannot delete a filesystem root"
        for denied in self._deny_exact:
            if norm == denied:
                return False, "Protected system path"
        for denied in self._deny_trees:
            if norm == denied or norm.startswith(denied + os.sep):
                return False, "Protected user or system path"

        matched_root: Optional[str] = None
        matched_len = -1
        for root in self.allowed_roots:
            root_norm = _normalized(root)
            if norm == root_norm or norm.startswith(root_norm + os.sep):
                if len(root_norm) > matched_len:
                    matched_root = root
                    matched_len = len(root_norm)
        if matched_root is None:
            return False, "Path is outside the allowlist"

        if norm == _normalized(matched_root):
            if allow_contents_root:
                pass
            elif not allow_exact or norm not in self.allow_exact_roots:
                return False, "Refusing to delete an allowlisted root"
        if _has_reparse_component(abs_path, matched_root):
            return False, "Path contains a symlink or junction"
        return True, "OK"


def path_size(path: str, cancel_check: CancelCheck = None) -> int:
    """Calculate size recursively without following links or junctions."""
    try:
        if not os.path.lexists(path):
            return 0
        if _is_reparse(path):
            return 0
        if os.path.isfile(path):
            return int(os.path.getsize(path))
    except OSError:
        return 0
    if not os.path.isdir(path):
        return 0

    total = 0
    stack = [path]
    while stack:
        if cancel_check and cancel_check():
            break
        current = stack.pop()
        try:
            entries = list(os.scandir(current))
        except OSError:
            continue
        for entry in entries:
            try:
                if entry.is_symlink() or _is_reparse(entry.path):
                    continue
                if entry.is_dir(follow_symlinks=False):
                    stack.append(entry.path)
                elif entry.is_file(follow_symlinks=False):
                    total += int(entry.stat(follow_symlinks=False).st_size)
            except OSError:
                continue
    return total


def _new_delete_result() -> Dict[str, Any]:
    return {
        "removed": [],
        "would_remove": [],
        "failed": [],
        "skipped": [],
        "recycled": [],
        "bytes_freed": 0,
        "bytes_estimated": 0,
        "bytes_recycled": 0,
    }


def _merge_delete_result(dst: Dict[str, Any], src: Dict[str, Any]) -> None:
    for key in ("removed", "would_remove", "failed", "skipped", "recycled"):
        dst[key].extend(src.get(key, []))
    dst["bytes_freed"] += int(src.get("bytes_freed", 0) or 0)
    dst["bytes_estimated"] += int(src.get("bytes_estimated", 0) or 0)
    dst["bytes_recycled"] += int(src.get("bytes_recycled", 0) or 0)


class CleanupLog:
    """Append-only action log for system cleanup operations."""

    def __init__(self, log_dir: Optional[str] = None):
        base = Path(__file__).resolve().parent.parent
        self.log_dir = Path(log_dir) if log_dir else base / "logs"
        self.path: Optional[Path] = None
        self._lock = threading.Lock()
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.path = self.log_dir / ("system_cleanup_%s.log" % stamp)
            self._write_line("# PC-Toolbox system cleanup action log")
        except OSError:
            self.path = None

    def _write_line(self, line: str) -> None:
        if self.path is None:
            return
        try:
            with self._lock:
                with open(self.path, "a", encoding="utf-8") as handle:
                    handle.write(line + "\n")
        except OSError:
            pass

    def write(self, path: str, size: int, result: str, detail: str = "") -> None:
        """Write one action entry."""
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        suffix = (" | %s" % detail) if detail else ""
        self._write_line(
            "%s | %s | %s | %s%s" % (stamp, result, format_size(size), path, suffix)
        )


class SafeDeleter:
    """Deletion helper that validates every target and records failures."""

    def __init__(self, log: Optional[CleanupLog] = None):
        self.log = log

    def delete_contents(
        self,
        root: str,
        policy: PathPolicy,
        recoverable: bool = False,
        dry_run: bool = False,
        cancel_check: CancelCheck = None,
    ) -> Dict[str, Any]:
        result = _new_delete_result()
        ok, reason = policy.validate(root, allow_contents_root=True)
        if not ok:
            result["failed"].append({"path": root, "size": 0, "reason": reason})
            return result
        if not os.path.isdir(root):
            result["skipped"].append(
                {"path": root, "size": 0, "reason": "Directory does not exist"}
            )
            return result
        if _is_reparse(root):
            result["skipped"].append(
                {"path": root, "size": 0, "reason": "Symlink or junction"}
            )
            return result
        try:
            entries = list(os.scandir(root))
        except PermissionError:
            result["failed"].append(
                {"path": root, "size": 0, "reason": "Permission denied"}
            )
            return result
        except OSError as exc:
            result["failed"].append({"path": root, "size": 0, "reason": str(exc)})
            return result

        for entry in entries:
            if cancel_check and cancel_check():
                result["skipped"].append(
                    {"path": root, "size": 0, "reason": "Cancelled"}
                )
                break
            if entry.is_symlink() or _is_reparse(entry.path):
                result["skipped"].append(
                    {"path": entry.path, "size": 0, "reason": "Symlink or junction"}
                )
                continue
            sub = self.delete_target(
                entry.path,
                policy=policy,
                allow_exact=False,
                recoverable=recoverable,
                dry_run=dry_run,
                cancel_check=cancel_check,
            )
            _merge_delete_result(result, sub)
        return result

    def delete_target(
        self,
        path: str,
        policy: PathPolicy,
        allow_exact: bool = False,
        recoverable: bool = False,
        dry_run: bool = False,
        cancel_check: CancelCheck = None,
    ) -> Dict[str, Any]:
        result = _new_delete_result()
        ok, reason = policy.validate(path, allow_exact=allow_exact)
        if not ok:
            result["failed"].append({"path": path, "size": 0, "reason": reason})
            self._log(path, 0, "refused", reason)
            return result
        if not os.path.lexists(path):
            result["skipped"].append(
                {"path": path, "size": 0, "reason": "Path no longer exists"}
            )
            self._log(path, 0, "skipped", "Path no longer exists")
            return result
        if _is_reparse(path):
            result["skipped"].append(
                {"path": path, "size": 0, "reason": "Symlink or junction"}
            )
            self._log(path, 0, "skipped", "Symlink or junction")
            return result

        size = path_size(path, cancel_check)
        if dry_run:
            result["would_remove"].append({"path": path, "size": size})
            result["bytes_estimated"] += size
            self._log(path, size, "dry-run", "Would delete")
            return result

        if recoverable:
            if _send2trash is None:
                result["skipped"].append(
                    {
                        "path": path,
                        "size": size,
                        "reason": "send2trash is not installed; skipped for safety",
                    }
                )
                self._log(path, size, "skipped", "send2trash unavailable")
                return result
            try:
                _send2trash(path)
            except Exception as exc:
                result["failed"].append(
                    {"path": path, "size": size, "reason": str(exc)}
                )
                self._log(path, size, "failed", str(exc))
                return result
            result["removed"].append({"path": path, "size": size, "recycled": True})
            result["recycled"].append({"path": path, "size": size})
            result["bytes_recycled"] += size
            self._log(path, size, "removed", "Sent to Recycle Bin")
            return result

        if os.path.isdir(path):
            freed, removed_root = self._delete_tree(path, result, cancel_check)
            if removed_root:
                result["removed"].append({"path": path, "size": freed})
                result["bytes_freed"] += freed
                self._log(path, freed, "removed", "Deleted permanently")
            else:
                result["bytes_freed"] += freed
                self._log(path, freed, "partial", "Directory not fully removed")
            return result

        try:
            self._remove_file(path)
        except PermissionError as exc:
            result["failed"].append(
                {"path": path, "size": size, "reason": "Permission denied: %s" % exc}
            )
            self._log(path, size, "failed", "Permission denied")
            return result
        except OSError as exc:
            result["failed"].append(
                {"path": path, "size": size, "reason": str(exc)}
            )
            self._log(path, size, "failed", str(exc))
            return result
        result["removed"].append({"path": path, "size": size})
        result["bytes_freed"] += size
        self._log(path, size, "removed", "Deleted permanently")
        return result

    def _delete_tree(
        self, path: str, result: Dict[str, Any], cancel_check: CancelCheck
    ) -> Tuple[int, bool]:
        total = 0
        cancelled = False
        try:
            entries = list(os.scandir(path))
        except PermissionError:
            result["failed"].append(
                {"path": path, "size": 0, "reason": "Permission denied"}
            )
            return 0, False
        except OSError as exc:
            result["failed"].append({"path": path, "size": 0, "reason": str(exc)})
            return 0, False

        for entry in entries:
            if cancel_check and cancel_check():
                cancelled = True
                result["skipped"].append(
                    {"path": entry.path, "size": 0, "reason": "Cancelled"}
                )
                break
            try:
                if entry.is_symlink() or _is_reparse(entry.path):
                    result["skipped"].append(
                        {
                            "path": entry.path,
                            "size": 0,
                            "reason": "Symlink or junction",
                        }
                    )
                    continue
                if entry.is_dir(follow_symlinks=False):
                    sub_total, sub_ok = self._delete_tree(
                        entry.path, result, cancel_check
                    )
                    total += sub_total
                    if not sub_ok:
                        cancelled = True
                elif entry.is_file(follow_symlinks=False):
                    size = int(entry.stat(follow_symlinks=False).st_size)
                    try:
                        self._remove_file(entry.path)
                    except PermissionError as exc:
                        result["failed"].append(
                            {
                                "path": entry.path,
                                "size": size,
                                "reason": "Permission denied: %s" % exc,
                            }
                        )
                        self._log(entry.path, size, "failed", "Permission denied")
                        continue
                    except OSError as exc:
                        result["failed"].append(
                            {"path": entry.path, "size": size, "reason": str(exc)}
                        )
                        self._log(entry.path, size, "failed", str(exc))
                        continue
                    total += size
                    self._log(entry.path, size, "removed", "Deleted permanently")
            except OSError as exc:
                result["failed"].append(
                    {"path": entry.path, "size": 0, "reason": str(exc)}
                )
                self._log(entry.path, 0, "failed", str(exc))

        if cancelled:
            return total, False
        try:
            os.rmdir(path)
            return total, True
        except PermissionError:
            result["failed"].append(
                {"path": path, "size": 0, "reason": "Permission denied"}
            )
            return total, False
        except OSError as exc:
            result["failed"].append({"path": path, "size": 0, "reason": str(exc)})
            return total, False

    def _remove_file(self, path: str) -> None:
        try:
            os.remove(path)
        except PermissionError:
            os.chmod(path, stat.S_IWRITE)
            os.remove(path)

    def _log(self, path: str, size: int, result: str, detail: str = "") -> None:
        if self.log:
            self.log.write(path, size, result, detail)


def _new_clean_result() -> Dict[str, Any]:
    return {
        "removed": [],
        "would_remove": [],
        "failed": [],
        "skipped": [],
        "recycled": [],
        "bytes_freed": 0,
        "bytes_estimated": 0,
        "bytes_recycled": 0,
    }


def _merge_clean_result(
    dst: Dict[str, Any], src: Dict[str, Any], item: Dict[str, Any]
) -> None:
    for key in ("removed", "would_remove", "failed", "skipped", "recycled"):
        for entry in src.get(key, []):
            copy = dict(entry)
            copy.setdefault("id", item.get("id"))
            copy.setdefault("category", item.get("category_name"))
            copy.setdefault("tier", item.get("tier"))
            dst[key].append(copy)
    dst["bytes_freed"] += int(src.get("bytes_freed", 0) or 0)
    dst["bytes_estimated"] += int(src.get("bytes_estimated", 0) or 0)
    dst["bytes_recycled"] += int(src.get("bytes_recycled", 0) or 0)


class CleanupCategory:
    """Base class for one cleanup category."""

    key = "base"
    name = "Cleanup"
    tier = TIER_SAFE
    admin_required = False
    recoverable = False
    default_selected = False

    def __init__(
        self,
        settings_provider: Optional[Callable[[], Dict[str, Any]]] = None,
        log: Optional[CleanupLog] = None,
    ):
        self._settings_provider = settings_provider
        self.log = log
        self.notices: List[str] = []
        self._deleter = SafeDeleter(log)
        self._policy_cache: Optional[PathPolicy] = None

    def get_roots(self) -> List[str]:
        """Return the explicit allowlist roots for this category."""
        return []

    def get_exact_roots(self) -> List[str]:
        """Return allowlisted roots that may themselves be deleted."""
        return []

    def _policy(self) -> PathPolicy:
        if self._policy_cache is None:
            self._policy_cache = PathPolicy(
                self.get_roots(), allow_exact_roots=self.get_exact_roots()
            )
        return self._policy_cache

    def setting(self, key: str, default: Any) -> Any:
        if not self._settings_provider:
            return default
        try:
            settings = self._settings_provider() or {}
            return settings.get(key, default)
        except Exception:
            return default

    def _item(
        self,
        path: str,
        size: int,
        description: str,
        name: Optional[str] = None,
        delete_mode: str = "contents",
        recoverable: Optional[bool] = None,
        admin_required: Optional[bool] = None,
        default_selected: Optional[bool] = None,
        selectable: bool = True,
        allow_exact: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
        warning: Optional[str] = None,
    ) -> Dict[str, Any]:
        display = name or os.path.basename(path.rstrip("\\/")) or self.name
        item_id = "%s|%s" % (self.key, path.lower())
        return {
            "id": item_id,
            "tier": self.tier,
            "tier_label": TIER_LABELS.get(self.tier, ""),
            "category": self.key,
            "category_name": self.name,
            "name": display,
            "path": path,
            "size": int(size),
            "description": description,
            "delete_mode": delete_mode,
            "recoverable": self.recoverable if recoverable is None else recoverable,
            "admin_required": (
                self.admin_required if admin_required is None else admin_required
            ),
            "default_selected": (
                self.default_selected if default_selected is None else default_selected
            ),
            "selectable": selectable,
            "allow_exact": allow_exact,
            "metadata": metadata or {},
            "warning": warning,
        }

    def scan(
        self,
        cancel_check: CancelCheck = None,
        status_callback: StatusCallback = None,
    ) -> List[Dict[str, Any]]:
        return []

    def clean(
        self,
        items: List[Dict[str, Any]],
        dry_run: bool = False,
        cancel_check: CancelCheck = None,
        status_callback: StatusCallback = None,
    ) -> Dict[str, Any]:
        return self._clean_generic(items, dry_run, cancel_check, status_callback)

    def _clean_generic(
        self,
        items: List[Dict[str, Any]],
        dry_run: bool,
        cancel_check: CancelCheck,
        status_callback: StatusCallback,
    ) -> Dict[str, Any]:
        result = _new_clean_result()
        total = len(items)
        for index, item in enumerate(items):
            if cancel_check and cancel_check():
                result["skipped"].append(
                    {
                        "id": item.get("id"),
                        "path": item.get("path", ""),
                        "size": item.get("size", 0),
                        "category": self.name,
                        "tier": self.tier,
                        "reason": "Cancelled",
                    }
                )
                break
            if status_callback:
                status_callback(
                    "Cleaning %s (%d/%d)" % (item.get("name", self.name), index + 1, total)
                )
            mode = item.get("delete_mode")
            if mode == "contents":
                sub = self._deleter.delete_contents(
                    item.get("path", ""),
                    self._policy(),
                    recoverable=bool(item.get("recoverable")),
                    dry_run=dry_run,
                    cancel_check=cancel_check,
                )
            elif mode == "path":
                sub = self._deleter.delete_target(
                    item.get("path", ""),
                    self._policy(),
                    allow_exact=bool(item.get("allow_exact")),
                    recoverable=bool(item.get("recoverable")),
                    dry_run=dry_run,
                    cancel_check=cancel_check,
                )
            else:
                result["skipped"].append(
                    {
                        "id": item.get("id"),
                        "path": item.get("path", ""),
                        "size": item.get("size", 0),
                        "category": self.name,
                        "tier": self.tier,
                        "reason": "Unsupported cleanup action",
                    }
                )
                continue
            _merge_clean_result(result, sub, item)
        return result

    def _admin_skipped(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        result = _new_clean_result()
        for item in items:
            result["skipped"].append(
                {
                    "id": item.get("id"),
                    "path": item.get("path"),
                    "size": item.get("size", 0),
                    "category": self.name,
                    "tier": self.tier,
                    "reason": "Administrator privileges required",
                }
            )
        return result


class TempFoldersCategory(CleanupCategory):
    key = "temp_folders"
    name = "Temporary folders"
    tier = TIER_SAFE
    default_selected = True

    def get_roots(self) -> List[str]:
        roots = []
        for var in ("TEMP", "TMP"):
            value = os.environ.get(var)
            if value:
                roots.append(value)
        local = os.environ.get("LOCALAPPDATA")
        if local:
            roots.append(os.path.join(local, "Temp"))
        roots.append(r"C:\Windows\Temp")
        return _dedupe_paths(roots)

    def scan(self, cancel_check=None, status_callback=None) -> List[Dict[str, Any]]:
        items = []
        for root in self.get_roots():
            if cancel_check and cancel_check():
                break
            if not os.path.isdir(root):
                continue
            if status_callback:
                status_callback("Measuring %s" % root)
            size = path_size(root, cancel_check)
            admin = _is_under(root, os.environ.get("SystemRoot", r"C:\Windows"))
            items.append(
                self._item(
                    root,
                    size,
                    "Temporary files and folders (contents only)",
                    name=os.path.basename(root.rstrip("\\/")) or root,
                    delete_mode="contents",
                    recoverable=False,
                    admin_required=admin,
                )
            )
        return items


class RecycleBinCategory(CleanupCategory):
    key = "recycle_bin"
    name = "Recycle Bin"
    tier = TIER_SAFE
    default_selected = True

    class _Info(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.c_ulong),
            ("i64Size", ctypes.c_longlong),
            ("i64NumItems", ctypes.c_longlong),
        ]

    def _query(self) -> Tuple[int, int]:
        if os.name != "nt":
            return 0, 0
        shell32 = ctypes.windll.shell32
        total = 0
        count = 0
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            root = "%s:\\" % letter
            if not os.path.exists(root):
                continue
            info = self._Info()
            info.cbSize = ctypes.sizeof(info)
            try:
                if shell32.SHQueryRecycleBinW(ctypes.c_wchar_p(root), ctypes.byref(info)) == 0:
                    total += int(info.i64Size)
                    count += int(info.i64NumItems)
            except Exception:
                continue
        return total, count

    def scan(self, cancel_check=None, status_callback=None) -> List[Dict[str, Any]]:
        if status_callback:
            status_callback("Checking Recycle Bin")
        size, count = self._query()
        if size <= 0 and count <= 0:
            return []
        return [
            self._item(
                "Recycle Bin (all drives)",
                size,
                "Empty the Recycle Bin on all drives (%d item(s))" % count,
                name="Recycle Bin",
                delete_mode="recycle_bin",
                recoverable=False,
            )
        ]

    def clean(self, items, dry_run=False, cancel_check=None, status_callback=None):
        result = _new_clean_result()
        for item in items:
            size = int(item.get("size", 0) or 0)
            if dry_run:
                result["would_remove"].append(
                    {"id": item.get("id"), "path": item.get("path"), "size": size}
                )
                result["bytes_estimated"] += size
                if self.log:
                    self.log.write(item.get("path", ""), size, "dry-run", "Would empty")
                continue
            if os.name != "nt":
                result["skipped"].append(
                    {
                        "id": item.get("id"),
                        "path": item.get("path"),
                        "size": size,
                        "category": self.name,
                        "tier": self.tier,
                        "reason": "Recycle Bin is only supported on Windows",
                    }
                )
                continue
            try:
                code = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x7)
            except Exception as exc:
                code = -1
                detail = str(exc)
            else:
                detail = "HRESULT %s" % code
            if code == 0:
                result["removed"].append(
                    {"id": item.get("id"), "path": item.get("path"), "size": size}
                )
                result["bytes_freed"] += size
                if self.log:
                    self.log.write(item.get("path", ""), size, "removed", "Recycle Bin emptied")
            elif code == 1:
                result["skipped"].append(
                    {
                        "id": item.get("id"),
                        "path": item.get("path"),
                        "size": size,
                        "category": self.name,
                        "tier": self.tier,
                        "reason": "Recycle Bin is already empty",
                    }
                )
            else:
                result["failed"].append(
                    {
                        "id": item.get("id"),
                        "path": item.get("path"),
                        "size": size,
                        "category": self.name,
                        "tier": self.tier,
                        "reason": "Could not empty Recycle Bin (%s)" % detail,
                    }
                )
                if self.log:
                    self.log.write(item.get("path", ""), size, "failed", detail)
        return result


class WindowsUpdateDownloadCategory(CleanupCategory):
    key = "windows_update_download"
    name = "Windows Update download cache"
    tier = TIER_SAFE
    admin_required = True
    default_selected = True

    def get_roots(self) -> List[str]:
        return [r"C:\Windows\SoftwareDistribution\Download"]

    def scan(self, cancel_check=None, status_callback=None) -> List[Dict[str, Any]]:
        root = self.get_roots()[0]
        if not os.path.isdir(root):
            return []
        if status_callback:
            status_callback("Measuring Windows Update cache")
        return [
            self._item(
                root,
                path_size(root, cancel_check),
                "Downloaded Windows Update files (services are stopped during cleanup)",
                name="Windows Update downloads",
                delete_mode="contents",
                recoverable=False,
                admin_required=True,
            )
        ]

    def clean(self, items, dry_run=False, cancel_check=None, status_callback=None):
        if not items:
            return _new_clean_result()
        if not dry_run and not is_admin():
            result = _new_clean_result()
            for item in items:
                result["skipped"].append(
                    {
                        "id": item.get("id"),
                        "path": item.get("path"),
                        "size": item.get("size", 0),
                        "category": self.name,
                        "tier": self.tier,
                        "reason": "Administrator privileges required",
                    }
                )
            return result
        if dry_run:
            return self._clean_generic(items, dry_run, cancel_check, status_callback)

        stopped = []
        for service in ("wuauserv", "bits"):
            code, output = run_command(["sc.exe", "stop", service], timeout=60)
            if code in (0, 1056, 1060, 1062):
                stopped.append(service)
            else:
                if self.log:
                    self.log.write(service, 0, "warning", "Stop failed: %s" % output[:200])
        try:
            return self._clean_generic(items, dry_run, cancel_check, status_callback)
        finally:
            for service in stopped:
                code, output = run_command(["sc.exe", "start", service], timeout=60)
                if code not in (0, 1056) and self.log:
                    self.log.write(service, 0, "warning", "Start failed: %s" % output[:200])


class ThumbnailCacheCategory(CleanupCategory):
    key = "thumbnail_cache"
    name = "Explorer thumbnail cache"
    tier = TIER_SAFE
    default_selected = True

    def get_roots(self) -> List[str]:
        local = os.environ.get("LOCALAPPDATA")
        if not local:
            return []
        return [os.path.join(local, "Microsoft", "Windows", "Explorer")]

    def scan(self, cancel_check=None, status_callback=None) -> List[Dict[str, Any]]:
        items = []
        for root in self.get_roots():
            if not os.path.isdir(root):
                continue
            try:
                names = os.listdir(root)
            except OSError:
                continue
            for name in names:
                if not name.lower().startswith("thumbcache_") or not name.lower().endswith(".db"):
                    continue
                path = os.path.join(root, name)
                if os.path.isfile(path):
                    items.append(
                        self._item(
                            path,
                            path_size(path),
                            "Windows Explorer thumbnail cache",
                            name=name,
                            delete_mode="path",
                            recoverable=False,
                        )
                    )
        return items


class CrashLogsCategory(CleanupCategory):
    key = "crash_logs"
    name = "Crash dumps and Windows logs"
    tier = TIER_SAFE
    default_selected = True

    def get_roots(self) -> List[str]:
        roots = [
            r"C:\Windows\Minidump",
            r"C:\Windows\MEMORY.DMP",
            r"C:\Windows\Logs",
            r"C:\ProgramData\Microsoft\Windows\WER",
        ]
        local = os.environ.get("LOCALAPPDATA")
        if local:
            roots.append(os.path.join(local, "CrashDumps"))
        return _dedupe_paths(roots)

    def get_exact_roots(self) -> List[str]:
        return [r"C:\Windows\MEMORY.DMP"]

    def scan(self, cancel_check=None, status_callback=None) -> List[Dict[str, Any]]:
        items = []
        for root in self.get_roots():
            if cancel_check and cancel_check():
                break
            if not os.path.exists(root):
                continue
            if status_callback:
                status_callback("Measuring %s" % root)
            admin = _is_under(root, os.environ.get("SystemRoot", r"C:\Windows"))
            is_file = os.path.isfile(root)
            items.append(
                self._item(
                    root,
                    path_size(root, cancel_check),
                    "Crash dump or Windows log data",
                    name=os.path.basename(root.rstrip("\\/")) or root,
                    delete_mode="path" if is_file else "contents",
                    recoverable=False,
                    admin_required=admin,
                    allow_exact=is_file,
                )
            )
        return items


class BrowserCacheCategory(CleanupCategory):
    key = "browser_cache"
    name = "Browser caches"
    tier = TIER_SAFE
    default_selected = True

    CHROMIUM_CACHE_DIRS = ("Cache", "Code Cache", "GPUCache", "ShaderCache", "GrShaderCache")
    FIREFOX_CACHE_DIRS = ("cache2", "startupCache")

    def get_roots(self) -> List[str]:
        local = os.environ.get("LOCALAPPDATA")
        if not local:
            return []
        return _dedupe_paths(
            [
                os.path.join(local, "Google", "Chrome", "User Data"),
                os.path.join(local, "Microsoft", "Edge", "User Data"),
                os.path.join(local, "BraveSoftware", "Brave-Browser", "User Data"),
                os.path.join(local, "Mozilla", "Firefox", "Profiles"),
            ]
        )

    def _chromium_items(self, base: str, browser: str) -> List[Dict[str, Any]]:
        items = []
        if not os.path.isdir(base):
            return items
        try:
            profiles = [
                entry
                for entry in os.scandir(base)
                if entry.is_dir(follow_symlinks=False) and not _is_reparse(entry.path)
            ]
        except OSError:
            return items
        for profile in profiles:
            for cache_name in self.CHROMIUM_CACHE_DIRS:
                cache_path = os.path.join(profile.path, cache_name)
                if not os.path.isdir(cache_path) or _is_reparse(cache_path):
                    continue
                items.append(
                    self._item(
                        cache_path,
                        path_size(cache_path),
                        "%s cache for profile %s (cookies, passwords and history are never touched)"
                        % (browser, profile.name),
                        name="%s - %s - %s" % (browser, profile.name, cache_name),
                        delete_mode="contents",
                        recoverable=False,
                    )
                )
        return items

    def _firefox_items(self, base: str) -> List[Dict[str, Any]]:
        items = []
        if not os.path.isdir(base):
            return items
        try:
            profiles = [
                entry
                for entry in os.scandir(base)
                if entry.is_dir(follow_symlinks=False) and not _is_reparse(entry.path)
            ]
        except OSError:
            return items
        for profile in profiles:
            for cache_name in self.FIREFOX_CACHE_DIRS:
                cache_path = os.path.join(profile.path, cache_name)
                if not os.path.isdir(cache_path) or _is_reparse(cache_path):
                    continue
                items.append(
                    self._item(
                        cache_path,
                        path_size(cache_path),
                        "Firefox cache for profile %s (cookies, passwords and history are never touched)"
                        % profile.name,
                        name="Firefox - %s - %s" % (profile.name, cache_name),
                        delete_mode="contents",
                        recoverable=False,
                    )
                )
        return items

    def scan(self, cancel_check=None, status_callback=None) -> List[Dict[str, Any]]:
        local = os.environ.get("LOCALAPPDATA")
        if not local:
            return []
        items: List[Dict[str, Any]] = []
        if status_callback:
            status_callback("Scanning browser caches")
        items.extend(
            self._chromium_items(
                os.path.join(local, "Google", "Chrome", "User Data"), "Chrome"
            )
        )
        items.extend(
            self._chromium_items(
                os.path.join(local, "Microsoft", "Edge", "User Data"), "Edge"
            )
        )
        items.extend(
            self._chromium_items(
                os.path.join(local, "BraveSoftware", "Brave-Browser", "User Data"),
                "Brave",
            )
        )
        items.extend(
            self._firefox_items(os.path.join(local, "Mozilla", "Firefox", "Profiles"))
        )
        return items


class DeliveryOptimizationCategory(CleanupCategory):
    key = "delivery_optimization"
    name = "Delivery Optimization cache"
    tier = TIER_SAFE
    admin_required = True
    default_selected = True

    def get_roots(self) -> List[str]:
        return [
            r"C:\Windows\SoftwareDistribution\DeliveryOptimization",
            r"C:\ProgramData\Microsoft\Windows\DeliveryOptimization\Cache",
        ]

    def scan(self, cancel_check=None, status_callback=None) -> List[Dict[str, Any]]:
        items = []
        for root in self.get_roots():
            if not os.path.isdir(root):
                continue
            if status_callback:
                status_callback("Measuring Delivery Optimization cache")
            items.append(
                self._item(
                    root,
                    path_size(root, cancel_check),
                    "Windows Delivery Optimization cache",
                    name="Delivery Optimization - %s" % os.path.basename(root),
                    delete_mode="contents",
                    recoverable=False,
                    admin_required=True,
                )
            )
        return items


JETBRAINS_PROCESS_STEMS = {
    "idea",
    "idea64",
    "pycharm",
    "pycharm64",
    "webstorm",
    "webstorm64",
    "phpstorm",
    "phpstorm64",
    "rubymine",
    "rubymine64",
    "clion",
    "clion64",
    "goland",
    "goland64",
    "datagrip",
    "datagrip64",
    "rider",
    "rider64",
    "appcode",
    "appcode64",
    "dataspell",
    "dataspell64",
    "rustrover",
    "rustrover64",
    "aqua",
    "aqua64",
    "gateway",
    "gateway64",
    "fleet",
    "fleet64",
}

_PRODUCT_ALIASES = {
    "intellijidea": ("intellij_idea", "IntelliJ IDEA"),
    "ideaic": ("intellij_idea", "IntelliJ IDEA"),
    "idea": ("intellij_idea", "IntelliJ IDEA"),
    "intellij": ("intellij_idea", "IntelliJ IDEA"),
    "pycharm": ("pycharm", "PyCharm"),
    "webstorm": ("webstorm", "WebStorm"),
    "phpstorm": ("phpstorm", "PhpStorm"),
    "rubymine": ("rubymine", "RubyMine"),
    "clion": ("clion", "CLion"),
    "goland": ("goland", "GoLand"),
    "datagrip": ("datagrip", "DataGrip"),
    "rider": ("rider", "Rider"),
    "appcode": ("appcode", "AppCode"),
    "dataspell": ("dataspell", "DataSpell"),
    "rustrover": ("rustrover", "RustRover"),
    "aqua": ("aqua", "Aqua"),
    "gateway": ("gateway", "Gateway"),
    "fleet": ("fleet", "Fleet"),
}

_JETBRAINS_VERSION_RE = re.compile(
    r"^(?P<product>.+?)(?P<year>\d{4})\.(?P<minor>\d+)(?P<suffix>.*)$"
)


@dataclass(frozen=True)
class JetBrainsFolder:
    """Parsed JetBrains version folder name."""

    name: str
    product_key: str
    product_name: str
    version: Tuple[int, int]
    is_backup: bool


def parse_jetbrains_folder(name: str) -> Optional[JetBrainsFolder]:
    """Parse names such as ``IntelliJIdea2026.1`` or ``PyCharm2026.2-backup``."""
    if not name or not isinstance(name, str):
        return None
    is_backup = bool(re.search(r"-backup$", name, re.IGNORECASE))
    base = re.sub(r"-backup$", "", name, flags=re.IGNORECASE).strip()
    match = _JETBRAINS_VERSION_RE.match(base)
    if not match:
        return None
    product = match.group("product").strip()
    if not product or any(sep in product for sep in ("\\", "/")):
        return None
    key_raw = re.sub(r"[^a-z0-9]+", "", product.lower())
    product_key, product_name = _PRODUCT_ALIASES.get(
        key_raw, (key_raw or product.lower(), product)
    )
    return JetBrainsFolder(
        name=name,
        product_key=product_key,
        product_name=product_name,
        version=(int(match.group("year")), int(match.group("minor"))),
        is_backup=is_backup,
    )


def select_jetbrains_targets(names: Iterable[str]) -> List[str]:
    """Return older version folders and all backup folders for each product."""
    groups: Dict[str, List[JetBrainsFolder]] = {}
    for name in names:
        parsed = parse_jetbrains_folder(name)
        if parsed is None:
            continue
        groups.setdefault(parsed.product_key, []).append(parsed)

    targets: List[str] = []
    for folders in groups.values():
        regular = sorted(
            (folder for folder in folders if not folder.is_backup),
            key=lambda folder: (folder.version, folder.name.lower()),
            reverse=True,
        )
        keep = regular[0].name if regular else None
        for folder in folders:
            if folder.is_backup or folder.name != keep:
                targets.append(folder.name)
    return sorted(set(targets))


def _jetbrains_running() -> bool:
    for process in psutil.process_iter(["name", "exe"]):
        try:
            name = (process.info.get("name") or "").lower()
            exe = (process.info.get("exe") or "").lower()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        stem = name.rsplit(".", 1)[0]
        if stem in JETBRAINS_PROCESS_STEMS:
            return True
        if "\\jetbrains\\" in exe:
            return True
    return False


class JetBrainsCategory(CleanupCategory):
    key = "jetbrains"
    name = "JetBrains leftovers"
    tier = TIER_DEVELOPER
    recoverable = False

    def get_roots(self) -> List[str]:
        roots = []
        for env_name in ("APPDATA", "LOCALAPPDATA"):
            base = os.environ.get(env_name)
            if base:
                roots.append(os.path.join(base, "JetBrains"))
        return _dedupe_paths(roots)

    def scan(self, cancel_check=None, status_callback=None) -> List[Dict[str, Any]]:
        if _jetbrains_running():
            self.notices.append(
                "JetBrains is running. Close all JetBrains IDEs before cleaning their folders."
            )
            return []
        folders: List[Tuple[str, str]] = []
        for root in self.get_roots():
            if not os.path.isdir(root):
                continue
            try:
                entries = list(os.scandir(root))
            except OSError:
                continue
            for entry in entries:
                if not entry.is_dir(follow_symlinks=False) or _is_reparse(entry.path):
                    continue
                if parse_jetbrains_folder(entry.name) is None:
                    continue
                folders.append((entry.name, entry.path))
        if status_callback:
            status_callback("Evaluating JetBrains versions")
        targets = set(select_jetbrains_targets(name for name, _path in folders))
        items = []
        for name, path in folders:
            if name not in targets:
                continue
            parsed = parse_jetbrains_folder(name)
            if parsed is None:
                continue
            label = "backup" if parsed.is_backup else "old version"
            items.append(
                self._item(
                    path,
                    path_size(path, cancel_check),
                    "%s JetBrains folder for %s %s"
                    % (label.capitalize(), parsed.product_name, "%d.%d" % parsed.version),
                    name=name,
                    delete_mode="path",
                    recoverable=False,
                    default_selected=False,
                )
            )
        return items

    def clean(self, items, dry_run=False, cancel_check=None, status_callback=None):
        if _jetbrains_running():
            result = _new_clean_result()
            for item in items:
                result["skipped"].append(
                    {
                        "id": item.get("id"),
                        "path": item.get("path"),
                        "size": item.get("size", 0),
                        "category": self.name,
                        "tier": self.tier,
                        "reason": "JetBrains is running",
                    }
                )
            return result
        return self._clean_generic(items, dry_run, cancel_check, status_callback)


class AndroidSystemImagesCategory(CleanupCategory):
    key = "android_system_images"
    name = "Android SDK system images"
    tier = TIER_DEVELOPER
    recoverable = False

    def get_roots(self) -> List[str]:
        local = os.environ.get("LOCALAPPDATA")
        if not local:
            return []
        return [os.path.join(local, "Android", "Sdk", "system-images")]

    def scan(self, cancel_check=None, status_callback=None) -> List[Dict[str, Any]]:
        items = []
        for root in self.get_roots():
            if not os.path.isdir(root):
                continue
            if status_callback:
                status_callback("Scanning Android system images")
            try:
                apis = [e for e in os.scandir(root) if e.is_dir(follow_symlinks=False)]
            except OSError:
                continue
            for api in apis:
                if _is_reparse(api.path):
                    continue
                try:
                    tags = [e for e in os.scandir(api.path) if e.is_dir(follow_symlinks=False)]
                except OSError:
                    continue
                for tag in tags:
                    if _is_reparse(tag.path):
                        continue
                    try:
                        abis = [e for e in os.scandir(tag.path) if e.is_dir(follow_symlinks=False)]
                    except OSError:
                        continue
                    for abi in abis:
                        if cancel_check and cancel_check():
                            return items
                        if _is_reparse(abi.path):
                            continue
                        items.append(
                            self._item(
                                abi.path,
                                path_size(abi.path, cancel_check),
                                "Android SDK system image %s / %s / %s"
                                % (api.name, tag.name, abi.name),
                                name="%s - %s - %s" % (api.name, tag.name, abi.name),
                                delete_mode="path",
                                recoverable=False,
                            )
                        )
        return items


class PackageCachesCategory(CleanupCategory):
    key = "package_caches"
    name = "Developer package caches"
    tier = TIER_DEVELOPER
    recoverable = False

    def _specs(self) -> List[Dict[str, Any]]:
        home = os.path.expanduser("~")
        local = os.environ.get("LOCALAPPDATA", "")
        specs: List[Dict[str, Any]] = []

        npm_cmd = shutil.which("npm")
        npm_paths = [os.path.join(local, "npm-cache")] if local else []
        specs.append(
            {
                "tool": "npm",
                "paths": npm_paths,
                "command": [npm_cmd, "cache", "clean", "--force"] if npm_cmd else None,
            }
        )

        pip_paths = [os.path.join(local, "pip", "Cache")] if local else []
        specs.append(
            {
                "tool": "pip",
                "paths": pip_paths,
                "command": [sys.executable, "-m", "pip", "cache", "purge"],
            }
        )

        dotnet = shutil.which("dotnet")
        nuget_paths = [
            os.path.join(home, ".nuget", "packages"),
        ]
        if local:
            nuget_paths.append(os.path.join(local, "NuGet", "v3-cache"))
        specs.append(
            {
                "tool": "NuGet",
                "paths": nuget_paths,
                "command": [dotnet, "nuget", "locals", "all", "--clear"] if dotnet else None,
            }
        )

        specs.append(
            {
                "tool": "Gradle",
                "paths": [os.path.join(home, ".gradle", "caches")],
                "command": None,
            }
        )
        specs.append(
            {
                "tool": "Maven",
                "paths": [os.path.join(home, ".m2", "repository")],
                "command": None,
            }
        )

        yarn = shutil.which("yarn")
        yarn_paths = [os.path.join(home, ".cache", "yarn")]
        if local:
            yarn_paths.append(os.path.join(local, "Yarn", "Cache"))
        specs.append(
            {
                "tool": "Yarn",
                "paths": yarn_paths,
                "command": [yarn, "cache", "clean"] if yarn else None,
            }
        )

        pnpm = shutil.which("pnpm")
        pnpm_paths = [os.path.join(local, "pnpm", "store")] if local else []
        specs.append(
            {
                "tool": "pnpm",
                "paths": pnpm_paths,
                "command": [pnpm, "store", "prune"] if pnpm else None,
            }
        )
        return specs

    def get_roots(self) -> List[str]:
        roots: List[str] = []
        for spec in self._specs():
            roots.extend(spec["paths"])
        return _dedupe_paths(roots)

    def scan(self, cancel_check=None, status_callback=None) -> List[Dict[str, Any]]:
        items = []
        for spec in self._specs():
            if cancel_check and cancel_check():
                break
            existing = [path for path in spec["paths"] if os.path.isdir(path)]
            if not existing:
                continue
            if status_callback:
                status_callback("Measuring %s cache" % spec["tool"])
            size = sum(path_size(path, cancel_check) for path in existing)
            command = spec["command"]
            items.append(
                self._item(
                    existing[0],
                    size,
                    "%s package cache%s"
                    % (
                        spec["tool"],
                        " (cleaned with the tool's own command)"
                        if command
                        else " (cache directory contents)",
                    ),
                    name="%s cache" % spec["tool"],
                    delete_mode="command" if command else "contents",
                    recoverable=False,
                    metadata={"paths": existing, "command": command},
                )
            )
        return items

    def clean(self, items, dry_run=False, cancel_check=None, status_callback=None):
        result = _new_clean_result()
        for index, item in enumerate(items):
            if cancel_check and cancel_check():
                break
            if status_callback:
                status_callback(
                    "Cleaning %s (%d/%d)" % (item.get("name"), index + 1, len(items))
                )
            metadata = item.get("metadata") or {}
            paths = [p for p in metadata.get("paths", [item.get("path", "")]) if p]
            invalid = []
            for path in paths:
                ok, reason = self._policy().validate(path, allow_contents_root=True)
                if not ok:
                    invalid.append("%s: %s" % (path, reason))
            if invalid:
                result["failed"].append(
                    {
                        "id": item.get("id"),
                        "path": item.get("path", ""),
                        "size": item.get("size", 0),
                        "category": self.name,
                        "tier": self.tier,
                        "reason": "; ".join(invalid),
                    }
                )
                continue

            command = metadata.get("command")
            if command:
                if dry_run:
                    result["would_remove"].append(
                        {
                            "id": item.get("id"),
                            "path": item.get("path", ""),
                            "size": item.get("size", 0),
                        }
                    )
                    result["bytes_estimated"] += int(item.get("size", 0) or 0)
                    if self.log:
                        self.log.write(
                            item.get("path", ""),
                            item.get("size", 0),
                            "dry-run",
                            "Would run %s" % " ".join(str(x) for x in command),
                        )
                    continue
                code, output = run_command(command, timeout=1800)
                if code == 0:
                    result["removed"].append(
                        {
                            "id": item.get("id"),
                            "path": item.get("path", ""),
                            "size": item.get("size", 0),
                        }
                    )
                    result["bytes_freed"] += int(item.get("size", 0) or 0)
                    if self.log:
                        self.log.write(
                            item.get("path", ""),
                            item.get("size", 0),
                            "removed",
                            "Cache command completed",
                        )
                else:
                    result["failed"].append(
                        {
                            "id": item.get("id"),
                            "path": item.get("path", ""),
                            "size": item.get("size", 0),
                            "category": self.name,
                            "tier": self.tier,
                            "reason": "Command failed (%s): %s" % (code, output[:300]),
                        }
                    )
                    if self.log:
                        self.log.write(
                            item.get("path", ""),
                            item.get("size", 0),
                            "failed",
                            output[:300],
                        )
                continue

            for path in paths:
                sub = self._deleter.delete_contents(
                    path,
                    self._policy(),
                    recoverable=False,
                    dry_run=dry_run,
                    cancel_check=cancel_check,
                )
                _merge_clean_result(result, sub, item)
        return result


class VSCodeCacheCategory(CleanupCategory):
    key = "vscode_cache"
    name = "VS Code caches"
    tier = TIER_DEVELOPER
    recoverable = False

    def get_roots(self) -> List[str]:
        appdata = os.environ.get("APPDATA")
        if not appdata:
            return []
        return [os.path.join(appdata, "Code")]

    def scan(self, cancel_check=None, status_callback=None) -> List[Dict[str, Any]]:
        items = []
        for root in self.get_roots():
            if not os.path.isdir(root):
                continue
            for name in ("Cache", "CachedData", "logs"):
                path = os.path.join(root, name)
                if not os.path.isdir(path) or _is_reparse(path):
                    continue
                items.append(
                    self._item(
                        path,
                        path_size(path, cancel_check),
                        "VS Code %s data" % name,
                        name="VS Code %s" % name,
                        delete_mode="contents",
                        recoverable=False,
                    )
                )
        return items


def parse_ollama_list(output: str) -> List[Tuple[str, int]]:
    """Parse ``ollama list`` output into (model, size bytes) pairs."""
    models: List[Tuple[str, int]] = []
    for line in (output or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.upper().startswith("NAME"):
            continue
        parts = stripped.split()
        if len(parts) < 3:
            continue
        name = parts[0]
        size = 0
        match = re.search(r"(\d+(?:\.\d+)?)\s*([KMGT]?B)\b", stripped, re.IGNORECASE)
        if match:
            value = float(match.group(1))
            unit = match.group(2).upper()
            multiplier = {"B": 1, "KB": 1024, "MB": 1024 ** 2, "GB": 1024 ** 3, "TB": 1024 ** 4}
            size = int(value * multiplier.get(unit, 1))
        models.append((name, size))
    return models


def _ollama_manifest_models(root: str) -> Dict[str, List[str]]:
    """Map model names to their manifest files under manifests/manifests-v2."""
    result: Dict[str, List[str]] = {}
    for folder in ("manifests", "manifests-v2"):
        base = os.path.join(root, folder)
        if not os.path.isdir(base):
            continue
        for current, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if not _is_reparse(os.path.join(current, d))]
            for filename in files:
                manifest_path = os.path.join(current, filename)
                rel = os.path.relpath(manifest_path, base).split(os.sep)
                if len(rel) < 3:
                    continue
                parts = rel[1:]
                if parts and parts[0].lower() == "library":
                    parts = parts[1:]
                if len(parts) < 2:
                    continue
                model_name = "%s:%s" % ("/".join(parts[:-1]), parts[-1])
                result.setdefault(model_name, []).append(manifest_path)
    return result


def _ollama_manifest_digests(path: str) -> set:
    digests = set()
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError, TypeError):
        return digests
    entries = []
    config = data.get("config")
    if isinstance(config, dict):
        entries.append(config)
    layers = data.get("layers")
    if isinstance(layers, list):
        entries.extend(layers)
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        digest = str(entry.get("digest", ""))
        if digest.startswith("sha256:"):
            digests.add(digest.split(":", 1)[1])
    return digests


def _ollama_all_digests(
    manifests: Dict[str, List[str]], excluded_paths: set
) -> set:
    digests = set()
    for paths in manifests.values():
        for path in paths:
            if path in excluded_paths:
                continue
            digests.update(_ollama_manifest_digests(path))
    return digests


def _ollama_recycle_plan(
    root: str,
    model: str,
    manifests: Dict[str, List[str]],
) -> Optional[Dict[str, Any]]:
    manifest_paths = manifests.get(model, [])
    if not manifest_paths:
        return None
    target_digests = set()
    for path in manifest_paths:
        target_digests.update(_ollama_manifest_digests(path))
    other_digests = _ollama_all_digests(manifests, set(manifest_paths))
    unique_digests = target_digests - other_digests
    paths = list(manifest_paths)
    for digest in unique_digests:
        blob = os.path.join(root, "blobs", "sha256-" + digest)
        if os.path.isfile(blob):
            paths.append(blob)
        metadata = os.path.join(root, "metadata", "sha256-%s.json" % digest)
        if os.path.isfile(metadata):
            paths.append(metadata)
    paths = _dedupe_paths(paths)
    size = 0
    for path in paths:
        try:
            size += int(os.path.getsize(path))
        except OSError:
            continue
    return {"paths": paths, "size": size, "manifests": manifest_paths}


class OllamaModelsCategory(CleanupCategory):
    key = "ollama_models"
    name = "Ollama models"
    tier = TIER_DEVELOPER
    recoverable = True

    def get_roots(self) -> List[str]:
        return [self._models_root()]

    def _models_root(self) -> str:
        return os.environ.get("OLLAMA_MODELS") or os.path.join(
            os.path.expanduser("~"), ".ollama", "models"
        )

    def _cli(self) -> Optional[str]:
        return shutil.which("ollama")

    def _fallback_models(self, root: str) -> List[Tuple[str, int, str]]:
        manifests = _ollama_manifest_models(root)
        models: List[Tuple[str, int, str]] = []
        for model_name, paths in manifests.items():
            digests = set()
            for path in paths:
                digests.update(_ollama_manifest_digests(path))
            size = 0
            for digest in digests:
                blob = os.path.join(root, "blobs", "sha256-" + digest)
                if os.path.isfile(blob):
                    try:
                        size += int(os.path.getsize(blob))
                    except OSError:
                        pass
            models.append((model_name, size, paths[0]))
        return models

    def _ollama_item(
        self,
        name: str,
        size: int,
        plan: Optional[Dict[str, Any]],
        root: str,
    ) -> Dict[str, Any]:
        if plan is None:
            return self._item(
                "ollama:%s" % name,
                size,
                "Ollama model files were not found on disk; use the Ollama CLI",
                name=name,
                delete_mode="report",
                recoverable=False,
                selectable=False,
                metadata={"open_location": root},
                warning="Could not map this model to files on disk; report-only.",
            )
        return self._item(
            plan["manifests"][0],
            plan["size"] or size,
            "Ollama model; model files are sent to the Recycle Bin (shared blobs preserved)",
            name=name,
            delete_mode="ollama_recycle",
            recoverable=True,
            metadata={"model": name, "paths": plan["paths"]},
        )

    def scan(self, cancel_check=None, status_callback=None) -> List[Dict[str, Any]]:
        root = self._models_root()
        if not os.path.isdir(root):
            return []
        if status_callback:
            status_callback("Listing Ollama models")
        manifest_map = _ollama_manifest_models(root)
        cli = self._cli()
        if cli:
            code, output = run_command([cli, "list"], timeout=30)
            if code == 0:
                items = []
                for name, size in parse_ollama_list(output):
                    plan = _ollama_recycle_plan(root, name, manifest_map)
                    items.append(self._ollama_item(name, size, plan, root))
                return items
            self.notices.append("Could not list Ollama models: %s" % output[:200])

        items = []
        for name, size, manifest_path in self._fallback_models(root):
            plan = _ollama_recycle_plan(root, name, manifest_map)
            if plan is not None:
                items.append(self._ollama_item(name, size, plan, root))
            else:
                items.append(
                    self._item(
                        manifest_path,
                        size,
                        "Ollama model found on disk; install the Ollama CLI to remove it safely",
                        name=name,
                        delete_mode="report",
                        recoverable=False,
                        selectable=False,
                        metadata={"open_location": root},
                        warning="Ollama CLI not available; this item is report-only.",
                    )
                )
        return items

    def clean(self, items, dry_run=False, cancel_check=None, status_callback=None):
        result = _new_clean_result()
        for index, item in enumerate(items):
            if cancel_check and cancel_check():
                break
            if status_callback:
                status_callback(
                    "Recycling Ollama model %s (%d/%d)"
                    % (item.get("name"), index + 1, len(items))
                )
            metadata = item.get("metadata") or {}
            paths = [p for p in metadata.get("paths", []) if p]
            if item.get("delete_mode") != "ollama_recycle" or not paths:
                result["skipped"].append(
                    {
                        "id": item.get("id"),
                        "path": item.get("path"),
                        "size": item.get("size", 0),
                        "category": self.name,
                        "tier": self.tier,
                        "reason": "Report-only item",
                    }
                )
                continue
            for path in paths:
                sub = self._deleter.delete_target(
                    path,
                    self._policy(),
                    allow_exact=False,
                    recoverable=True,
                    dry_run=dry_run,
                    cancel_check=cancel_check,
                )
                _merge_clean_result(result, sub, item)
        return result


def _scan_roots() -> List[str]:
    home = os.path.expanduser("~")
    roots = [home]
    for name in ("source", "repos", "projects", "dev", "code", "workspace", "git"):
        candidate = os.path.join(home, name)
        if os.path.isdir(candidate):
            roots.append(candidate)
    deduped = _dedupe_paths(roots)
    result: List[str] = []
    for root in deduped:
        if any(
            _is_under(root, other)
            and os.path.normcase(os.path.normpath(root))
            != os.path.normcase(os.path.normpath(other))
            for other in deduped
        ):
            continue
        result.append(root)
    return result or deduped


def _is_protected_scan_path(path: str) -> bool:
    for protected in _default_protected_roots():
        if _is_under(path, protected):
            return True
    return False


class StaleNodeModulesCategory(CleanupCategory):
    key = "stale_node_modules"
    name = "Stale node_modules"
    tier = TIER_DEVELOPER
    recoverable = True

    def get_roots(self) -> List[str]:
        return _scan_roots()

    def scan(self, cancel_check=None, status_callback=None) -> List[Dict[str, Any]]:
        enabled = bool(self.setting("system_cleanup_scan_node_modules", False))
        if not enabled:
            return []
        days = int(self.setting("system_cleanup_stale_node_modules_days", 90) or 90)
        cutoff = time.time() - max(1, days) * 86400
        items: List[Dict[str, Any]] = []

        def walk(directory: str, depth: int) -> None:
            if cancel_check and cancel_check():
                return
            if depth > 10 or _is_protected_scan_path(directory) or _is_reparse(directory):
                return
            try:
                entries = list(os.scandir(directory))
            except OSError:
                return
            for entry in entries:
                if cancel_check and cancel_check():
                    return
                try:
                    if entry.is_symlink() or _is_reparse(entry.path):
                        continue
                    if not entry.is_dir(follow_symlinks=False):
                        continue
                    if entry.name == "node_modules":
                        if _is_protected_scan_path(entry.path):
                            continue
                        try:
                            modified = entry.stat(follow_symlinks=False).st_mtime
                        except OSError:
                            continue
                        if modified <= cutoff:
                            if status_callback:
                                status_callback("Found %s" % entry.path)
                            items.append(
                                self._item(
                                    entry.path,
                                    path_size(entry.path, cancel_check),
                                    "node_modules not modified for at least %d days" % days,
                                    name="node_modules - %s" % os.path.basename(directory),
                                    delete_mode="path",
                                    recoverable=True,
                                )
                            )
                        continue
                    if entry.name in (".git", ".venv", "venv", "__pycache__", "AppData"):
                        continue
                    walk(entry.path, depth + 1)
                except OSError:
                    continue

        for root in self.get_roots():
            if os.path.isdir(root):
                walk(root, 0)
        return items

    def clean(self, items, dry_run=False, cancel_check=None, status_callback=None):
        result = _new_clean_result()
        for item in items:
            path = item.get("path", "")
            if os.path.basename(path.rstrip("\\/")).lower() != "node_modules":
                result["skipped"].append(
                    {
                        "id": item.get("id"),
                        "path": path,
                        "size": item.get("size", 0),
                        "category": self.name,
                        "tier": self.tier,
                        "reason": "Not a node_modules folder",
                    }
                )
                continue
            sub = self._deleter.delete_target(
                path,
                self._policy(),
                allow_exact=False,
                recoverable=True,
                dry_run=dry_run,
                cancel_check=cancel_check,
            )
            _merge_clean_result(result, sub, item)
        return result


class DockerPruneCategory(CleanupCategory):
    key = "docker_prune"
    name = "Docker unused data"
    tier = TIER_DEVELOPER

    def _cli(self) -> Optional[str]:
        return shutil.which("docker")

    def scan(self, cancel_check=None, status_callback=None) -> List[Dict[str, Any]]:
        if not self.setting("system_cleanup_enable_docker_prune", False):
            return []
        cli = self._cli()
        if not cli:
            return []
        if status_callback:
            status_callback("Checking Docker reclaimable space")
        code, output = run_command(
            [cli, "system", "df", "--format", "{{.Type}}\t{{.Reclaimable}}"], timeout=30
        )
        size = 0
        if code == 0:
            for line in output.splitlines():
                match = re.search(r"(\d+(?:\.\d+)?)\s*([KMGT]?B)", line, re.IGNORECASE)
                if not match:
                    continue
                value = float(match.group(1))
                unit = match.group(2).upper()
                multiplier = {"B": 1, "KB": 1024, "MB": 1024 ** 2, "GB": 1024 ** 3, "TB": 1024 ** 4}
                size += int(value * multiplier.get(unit, 1))
        return [
            self._item(
                "docker:system-prune",
                size,
                "Run 'docker system prune -f'. Volumes and named images are not removed.",
                name="Docker unused data",
                delete_mode="command",
                recoverable=False,
                metadata={"command": [cli, "system", "prune", "-f"]},
            )
        ]

    def clean(self, items, dry_run=False, cancel_check=None, status_callback=None):
        result = _new_clean_result()
        cli = self._cli()
        if not cli:
            for item in items:
                result["skipped"].append(
                    {
                        "id": item.get("id"),
                        "path": item.get("path"),
                        "size": item.get("size", 0),
                        "category": self.name,
                        "tier": self.tier,
                        "reason": "Docker CLI is not available",
                    }
                )
            return result
        for item in items:
            size = int(item.get("size", 0) or 0)
            if dry_run:
                result["would_remove"].append(
                    {"id": item.get("id"), "path": item.get("path"), "size": size}
                )
                result["bytes_estimated"] += size
                if self.log:
                    self.log.write(item.get("path", ""), size, "dry-run", "Would run docker system prune -f")
                continue
            code, output = run_command([cli, "system", "prune", "-f"], timeout=1800)
            if code == 0:
                result["removed"].append(
                    {"id": item.get("id"), "path": item.get("path"), "size": size}
                )
                result["bytes_freed"] += size
                if self.log:
                    self.log.write(item.get("path", ""), size, "removed", "docker system prune completed")
            else:
                result["failed"].append(
                    {
                        "id": item.get("id"),
                        "path": item.get("path"),
                        "size": size,
                        "category": self.name,
                        "tier": self.tier,
                        "reason": "docker prune failed: %s" % output[:300],
                    }
                )
        return result


class DismCleanupCategory(CleanupCategory):
    key = "dism_cleanup"
    name = "DISM component cleanup"
    tier = TIER_SYSTEM
    admin_required = True

    def scan(self, cancel_check=None, status_callback=None) -> List[Dict[str, Any]]:
        return [
            self._item(
                "dism:StartComponentCleanup",
                0,
                "Runs DISM /Online /Cleanup-Image /StartComponentCleanup",
                name="DISM component store cleanup",
                delete_mode="command",
                recoverable=False,
                admin_required=True,
                warning="May take a long time. Existing component updates may be removed.",
            )
        ]

    def clean(self, items, dry_run=False, cancel_check=None, status_callback=None):
        result = _new_clean_result()
        if not items:
            return result
        if not is_admin() and not dry_run:
            return self._admin_skipped(items)
        for item in items:
            if dry_run:
                result["would_remove"].append(
                    {"id": item.get("id"), "path": item.get("path"), "size": 0}
                )
                continue
            if status_callback:
                status_callback("Running DISM component cleanup")
            code, output = run_command(
                ["dism.exe", "/Online", "/Cleanup-Image", "/StartComponentCleanup"],
                timeout=3600,
            )
            if code == 0:
                result["removed"].append(
                    {"id": item.get("id"), "path": item.get("path"), "size": 0}
                )
                if self.log:
                    self.log.write(item.get("path", ""), 0, "removed", "DISM cleanup completed")
            else:
                result["failed"].append(
                    {
                        "id": item.get("id"),
                        "path": item.get("path"),
                        "size": 0,
                        "category": self.name,
                        "tier": self.tier,
                        "reason": "DISM failed (%s): %s" % (code, output[:300]),
                    }
                )
        return result


class WindowsOldCategory(CleanupCategory):
    key = "windows_old"
    name = "Windows.old"
    tier = TIER_SYSTEM
    admin_required = True

    def get_roots(self) -> List[str]:
        return [r"C:\Windows.old"]

    def get_exact_roots(self) -> List[str]:
        return [r"C:\Windows.old"]

    def scan(self, cancel_check=None, status_callback=None) -> List[Dict[str, Any]]:
        root = r"C:\Windows.old"
        if not os.path.isdir(root):
            return []
        if status_callback:
            status_callback("Measuring Windows.old")
        return [
            self._item(
                root,
                path_size(root, cancel_check),
                "Previous Windows installation. Some protected files may require Disk Cleanup.",
                name="Windows.old",
                delete_mode="path",
                recoverable=False,
                admin_required=True,
                allow_exact=True,
                warning="Permanently deletes the previous Windows installation.",
            )
        ]

    def clean(self, items, dry_run=False, cancel_check=None, status_callback=None):
        if not items:
            return _new_clean_result()
        if not is_admin() and not dry_run:
            return self._admin_skipped(items)
        return self._clean_generic(items, dry_run, cancel_check, status_callback)


class HibernateCategory(CleanupCategory):
    key = "hibernate"
    name = "Hibernation file"
    tier = TIER_SYSTEM
    admin_required = True

    def scan(self, cancel_check=None, status_callback=None) -> List[Dict[str, Any]]:
        path = r"C:\hiberfil.sys"
        if not os.path.exists(path):
            return []
        try:
            size = int(os.path.getsize(path))
        except OSError:
            size = 0
        return [
            self._item(
                path,
                size,
                "Runs 'powercfg /h off'. This disables hibernation and Fast Startup.",
                name="Hibernation file (powercfg /h off)",
                delete_mode="command",
                recoverable=False,
                admin_required=True,
                warning="Fast Startup will be disabled and hiberfil.sys removed.",
            )
        ]

    def clean(self, items, dry_run=False, cancel_check=None, status_callback=None):
        result = _new_clean_result()
        if not items:
            return result
        if not is_admin() and not dry_run:
            return self._admin_skipped(items)
        for item in items:
            size = int(item.get("size", 0) or 0)
            if dry_run:
                result["would_remove"].append(
                    {"id": item.get("id"), "path": item.get("path"), "size": size}
                )
                result["bytes_estimated"] += size
                continue
            code, output = run_command(["powercfg.exe", "/h", "off"], timeout=120)
            if code == 0:
                result["removed"].append(
                    {"id": item.get("id"), "path": item.get("path"), "size": size}
                )
                result["bytes_freed"] += size
                if self.log:
                    self.log.write(item.get("path", ""), size, "removed", "Hibernation disabled")
            else:
                result["failed"].append(
                    {
                        "id": item.get("id"),
                        "path": item.get("path"),
                        "size": size,
                        "category": self.name,
                        "tier": self.tier,
                        "reason": "powercfg failed (%s): %s" % (code, output[:300]),
                    }
                )
        return result


class SystemRestoreCategory(CleanupCategory):
    key = "system_restore"
    name = "System Restore storage"
    tier = TIER_SYSTEM
    admin_required = True

    def _query(self) -> Tuple[int, int]:
        code, output = run_command(["vssadmin.exe", "list", "shadowstorage"], timeout=60)
        if code != 0:
            return 0, 0
        used = 0
        maximum = 0
        for line in output.splitlines():
            lower = line.lower()
            size = _parse_windows_size(line)
            if size is None:
                continue
            if "used" in lower:
                used = max(used, size)
            elif "maximum" in lower or "max" in lower:
                maximum = max(maximum, size)
        return used, maximum

    def scan(self, cancel_check=None, status_callback=None) -> List[Dict[str, Any]]:
        if status_callback:
            status_callback("Checking System Restore storage")
        used, maximum = self._query()
        if used <= 0 and maximum <= 0:
            description = "Shrinks System Restore shadow storage to 5% of the C: drive"
        else:
            description = (
                "System Restore storage: %s used of %s maximum. Shrinks the maximum to 5%% of C:."
                % (format_size(used), format_size(maximum))
            )
        return [
            self._item(
                "vssadmin:resize-shadowstorage",
                used,
                description,
                name="Shrink System Restore storage",
                delete_mode="command",
                recoverable=False,
                admin_required=True,
                warning="Older restore points may be deleted when the maximum size is reduced.",
            )
        ]

    def clean(self, items, dry_run=False, cancel_check=None, status_callback=None):
        result = _new_clean_result()
        if not items:
            return result
        if not is_admin() and not dry_run:
            return self._admin_skipped(items)
        for item in items:
            size = int(item.get("size", 0) or 0)
            if dry_run:
                result["would_remove"].append(
                    {"id": item.get("id"), "path": item.get("path"), "size": size}
                )
                result["bytes_estimated"] += size
                continue
            code, output = run_command(
                [
                    "vssadmin.exe",
                    "resize",
                    "shadowstorage",
                    "/for=C:",
                    "/on=C:",
                    "/maxsize=5%",
                ],
                timeout=300,
            )
            if code == 0:
                result["removed"].append(
                    {"id": item.get("id"), "path": item.get("path"), "size": size}
                )
                if self.log:
                    self.log.write(item.get("path", ""), size, "removed", "Shadow storage resized")
            else:
                result["failed"].append(
                    {
                        "id": item.get("id"),
                        "path": item.get("path"),
                        "size": size,
                        "category": self.name,
                        "tier": self.tier,
                        "reason": "vssadmin failed (%s): %s" % (code, output[:300]),
                    }
                )
        return result


def _parse_windows_size(text: str) -> Optional[int]:
    match = re.search(
        r"(\d+(?:[.,]\d+)?)\s*([KMGT]?B)\b", text or "", re.IGNORECASE
    )
    if not match:
        return None
    value = float(match.group(1).replace(",", "."))
    unit = match.group(2).upper()
    multiplier = {"B": 1, "KB": 1024, "MB": 1024 ** 2, "GB": 1024 ** 3, "TB": 1024 ** 4}
    return int(value * multiplier.get(unit, 1))


class PagefileReportCategory(CleanupCategory):
    key = "pagefile_report"
    name = "Pagefile report"
    tier = TIER_REPORT

    def scan(self, cancel_check=None, status_callback=None) -> List[Dict[str, Any]]:
        try:
            swap = psutil.swap_memory()
            total = int(swap.total)
        except Exception:
            total = 0
        try:
            ram = int(psutil.virtual_memory().total)
        except Exception:
            ram = 0
        if total <= 0:
            recommendation = "No pagefile detected. Consider letting Windows manage it."
        elif ram and total < ram * 0.25:
            recommendation = "Pagefile is small compared with RAM. Consider letting Windows manage it."
        elif ram and total > ram:
            recommendation = "Pagefile is larger than RAM. A smaller custom size may be appropriate."
        else:
            recommendation = "Pagefile size looks reasonable."
        return [
            self._item(
                "pagefile:settings",
                total,
                "Current pagefile total: %s. %s" % (format_size(total), recommendation),
                name="Pagefile",
                delete_mode="report",
                recoverable=False,
                selectable=False,
                metadata={"action": "virtual_memory"},
            )
        ]


class VirtualDiskReportCategory(CleanupCategory):
    key = "virtual_disks"
    name = "Virtual disk files"
    tier = TIER_REPORT

    def _paths(self) -> List[str]:
        local = os.environ.get("LOCALAPPDATA", "")
        paths: List[str] = []
        if local:
            paths.extend(
                str(path)
                for path in Path(local, "Packages").glob("*/LocalState/ext4.vhdx")
            )
            paths.extend(str(path) for path in Path(local, "WSL").glob("*/ext4.vhdx"))
            paths.extend(
                str(path)
                for path in Path(local, "Docker", "wsl").glob("*/data/ext4.vhdx")
            )
        paths.extend(
            str(path)
            for path in Path(r"C:\ProgramData\Microsoft\Windows\Hyper-V\Virtual Hard Disks").glob("*.vhdx")
        )
        paths.extend(
            str(path)
            for path in Path(r"C:\Users\Public\Documents\Hyper-V\Virtual Hard Disks").glob("*.vhdx")
        )
        return _dedupe_paths(paths)

    def scan(self, cancel_check=None, status_callback=None) -> List[Dict[str, Any]]:
        items = []
        for path in self._paths():
            if not os.path.isfile(path) or _is_reparse(path):
                continue
            try:
                size = int(os.path.getsize(path))
            except OSError:
                continue
            items.append(
                self._item(
                    path,
                    size,
                    "Virtual disk file. Report only; use the Open location button.",
                    name=os.path.basename(path),
                    delete_mode="report",
                    recoverable=False,
                    selectable=False,
                    metadata={"action": "open_location"},
                )
            )
        return items


class LargeFilesReportCategory(CleanupCategory):
    key = "large_files"
    name = "Large files and .git folders"
    tier = TIER_REPORT
    recoverable = True

    GIT_THRESHOLD = 1024 ** 3

    def get_roots(self) -> List[str]:
        return _scan_roots()

    def _report_roots(self) -> List[str]:
        roots = _scan_roots()
        home = roots[0] if roots else os.path.expanduser("~")
        return [
            os.path.join(home, "Downloads"),
            os.path.join(home, "Documents"),
        ]

    def _is_allowed_report_path(self, path: str) -> bool:
        return any(_is_under(path, root) for root in self._report_roots())

    def _report_policy(self) -> PathPolicy:
        if getattr(self, "_report_policy_cache", None) is None:
            self._report_policy_cache = PathPolicy(
                self.get_roots(), protected_roots=[]
            )
        return self._report_policy_cache

    def scan(self, cancel_check=None, status_callback=None) -> List[Dict[str, Any]]:
        threshold_mb = int(self.setting("system_cleanup_large_file_threshold_mb", 500) or 500)
        threshold = max(1, threshold_mb) * 1024 ** 2
        items: List[Dict[str, Any]] = []

        def walk(directory: str, depth: int) -> None:
            if cancel_check and cancel_check():
                return
            if depth > 14 or _is_reparse(directory):
                return
            if _is_protected_scan_path(directory) and not self._is_allowed_report_path(directory):
                return
            try:
                entries = list(os.scandir(directory))
            except OSError:
                return
            for entry in entries:
                if cancel_check and cancel_check():
                    return
                try:
                    if entry.is_symlink() or _is_reparse(entry.path):
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name in ("AppData", "node_modules", ".venv", "venv", "__pycache__"):
                            continue
                        if entry.name == ".git":
                            if status_callback:
                                status_callback("Measuring %s" % entry.path)
                            size = path_size(entry.path, cancel_check)
                            if size >= self.GIT_THRESHOLD:
                                items.append(
                                    self._item(
                                        entry.path,
                                        size,
                                        "Git repository metadata larger than 1 GB",
                                        name=".git - %s" % os.path.basename(directory),
                                        delete_mode="path",
                                        recoverable=True,
                                        selectable=False,
                                        metadata={"allow_recycle": True, "kind": "git"},
                                    )
                                )
                            continue
                        walk(entry.path, depth + 1)
                    elif entry.is_file(follow_symlinks=False):
                        size = int(entry.stat(follow_symlinks=False).st_size)
                        if size >= threshold:
                            items.append(
                                self._item(
                                    entry.path,
                                    size,
                                    "File larger than %d MB" % threshold_mb,
                                    name=entry.name,
                                    delete_mode="path",
                                    recoverable=True,
                                    selectable=False,
                                    metadata={"allow_recycle": True, "kind": "file"},
                                )
                            )
                except OSError:
                    continue

        for root in self.get_roots():
            if os.path.isdir(root):
                walk(root, 0)
        return items

    def clean(self, items, dry_run=False, cancel_check=None, status_callback=None):
        result = _new_clean_result()
        threshold_mb = int(self.setting("system_cleanup_large_file_threshold_mb", 500) or 500)
        threshold = max(1, threshold_mb) * 1024 ** 2
        for item in items:
            metadata = item.get("metadata") or {}
            if not metadata.get("allow_recycle"):
                result["skipped"].append(
                    {
                        "id": item.get("id"),
                        "path": item.get("path"),
                        "size": item.get("size", 0),
                        "category": self.name,
                        "tier": self.tier,
                        "reason": "Report-only item",
                    }
                )
                continue
            path = item.get("path", "")
            if _is_protected_scan_path(path) and not self._is_allowed_report_path(path):
                result["skipped"].append(
                    {
                        "id": item.get("id"),
                        "path": path,
                        "size": item.get("size", 0),
                        "category": self.name,
                        "tier": self.tier,
                        "reason": "Protected folder",
                    }
                )
                continue
            if metadata.get("kind") == "git":
                if os.path.basename(path.rstrip("\\/")).lower() != ".git":
                    result["skipped"].append(
                        {
                            "id": item.get("id"),
                            "path": path,
                            "size": item.get("size", 0),
                            "category": self.name,
                            "tier": self.tier,
                            "reason": "Not a .git folder",
                        }
                    )
                    continue
            else:
                try:
                    current_size = os.path.getsize(path)
                except OSError:
                    current_size = 0
                if current_size < threshold:
                    result["skipped"].append(
                        {
                            "id": item.get("id"),
                            "path": path,
                            "size": item.get("size", 0),
                            "category": self.name,
                            "tier": self.tier,
                            "reason": "Below the configured threshold",
                        }
                    )
                    continue
            sub = self._deleter.delete_target(
                path,
                self._report_policy(),
                allow_exact=False,
                recoverable=True,
                dry_run=dry_run,
                cancel_check=cancel_check,
            )
            _merge_clean_result(result, sub, item)
        return result


def build_categories(
    settings_provider: Optional[Callable[[], Dict[str, Any]]] = None,
    log: Optional[CleanupLog] = None,
) -> List[CleanupCategory]:
    """Create all categories in display order."""
    return [
        TempFoldersCategory(settings_provider, log),
        RecycleBinCategory(settings_provider, log),
        WindowsUpdateDownloadCategory(settings_provider, log),
        ThumbnailCacheCategory(settings_provider, log),
        CrashLogsCategory(settings_provider, log),
        BrowserCacheCategory(settings_provider, log),
        DeliveryOptimizationCategory(settings_provider, log),
        JetBrainsCategory(settings_provider, log),
        AndroidSystemImagesCategory(settings_provider, log),
        PackageCachesCategory(settings_provider, log),
        VSCodeCacheCategory(settings_provider, log),
        OllamaModelsCategory(settings_provider, log),
        StaleNodeModulesCategory(settings_provider, log),
        DockerPruneCategory(settings_provider, log),
        DismCleanupCategory(settings_provider, log),
        WindowsOldCategory(settings_provider, log),
        HibernateCategory(settings_provider, log),
        SystemRestoreCategory(settings_provider, log),
        PagefileReportCategory(settings_provider, log),
        VirtualDiskReportCategory(settings_provider, log),
        LargeFilesReportCategory(settings_provider, log),
    ]


class SystemCleanupEngine:
    """Coordinates all cleanup categories."""

    def __init__(
        self,
        settings_provider: Optional[Callable[[], Dict[str, Any]]] = None,
        log_dir: Optional[str] = None,
    ):
        self.log = CleanupLog(log_dir)
        self.categories = build_categories(settings_provider, self.log)
        self._category_map = {category.key: category for category in self.categories}

    def get_category(self, key: str) -> Optional[CleanupCategory]:
        return self._category_map.get(key)

    def get_log_path(self) -> Optional[str]:
        return str(self.log.path) if self.log.path else None

    @staticmethod
    def _report(
        callback: ProgressCallback, current: int, total: int, message: str
    ) -> None:
        if callback:
            try:
                callback(current, total, message)
            except Exception:
                pass

    def scan(
        self,
        progress_callback: ProgressCallback = None,
        cancel_check: CancelCheck = None,
    ) -> Dict[str, Any]:
        start = time.monotonic()
        items: List[Dict[str, Any]] = []
        notices: List[str] = []
        total = len(self.categories)
        for index, category in enumerate(self.categories):
            if cancel_check and cancel_check():
                notices.append("Scan cancelled")
                break
            self._report(
                progress_callback,
                index,
                total,
                "Scanning %s..." % category.name,
            )
            category.notices = []
            try:
                category_items = category.scan(
                    cancel_check=cancel_check,
                    status_callback=lambda message, i=index: self._report(
                        progress_callback, i, total, message
                    ),
                )
                items.extend(category_items)
                notices.extend(category.notices)
            except Exception as exc:
                notices.append("%s scan failed: %s" % (category.name, exc))
            self._report(
                progress_callback,
                index + 1,
                total,
                "Scanned %s" % category.name,
            )
        return {
            "items": items,
            "notices": notices,
            "scan_duration": round(time.monotonic() - start, 3),
            "admin": is_admin(),
            "log_path": self.get_log_path(),
        }

    def clean(
        self,
        items: List[Dict[str, Any]],
        dry_run: bool = False,
        progress_callback: ProgressCallback = None,
        cancel_check: CancelCheck = None,
    ) -> Dict[str, Any]:
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        order: List[str] = []
        for item in items:
            key = item.get("category")
            if key not in self._category_map:
                continue
            if key not in grouped:
                grouped[key] = []
                order.append(key)
            grouped[key].append(item)

        result = _new_clean_result()
        by_category: Dict[str, int] = {}
        recycled_by_category: Dict[str, int] = {}
        estimated_by_category: Dict[str, int] = {}
        total = len(order)
        for index, key in enumerate(order):
            if cancel_check and cancel_check():
                result["skipped"].append(
                    {
                        "path": "",
                        "size": 0,
                        "category": self._category_map[key].name,
                        "tier": self._category_map[key].tier,
                        "reason": "Cancelled",
                    }
                )
                break
            category = self._category_map[key]
            self._report(
                progress_callback,
                index,
                total,
                "Cleaning %s..." % category.name,
            )
            try:
                category_result = category.clean(
                    grouped[key],
                    dry_run=dry_run,
                    cancel_check=cancel_check,
                    status_callback=lambda message, i=index: self._report(
                        progress_callback, i, total, message
                    ),
                )
            except Exception as exc:
                category_result = _new_clean_result()
                for item in grouped[key]:
                    category_result["failed"].append(
                        {
                            "id": item.get("id"),
                            "path": item.get("path", ""),
                            "size": item.get("size", 0),
                            "category": category.name,
                            "tier": category.tier,
                            "reason": str(exc),
                        }
                    )
            _merge_clean_result(
                result,
                category_result,
                {"category_name": category.name, "tier": category.tier},
            )
            by_category[category.name] = by_category.get(category.name, 0) + int(
                category_result.get("bytes_freed", 0) or 0
            )
            recycled_by_category[category.name] = recycled_by_category.get(
                category.name, 0
            ) + int(category_result.get("bytes_recycled", 0) or 0)
            estimated_by_category[category.name] = estimated_by_category.get(
                category.name, 0
            ) + int(category_result.get("bytes_estimated", 0) or 0)
            self._report(
                progress_callback,
                index + 1,
                total,
                "Cleaned %s" % category.name,
            )

        return {
            "removed": result["removed"],
            "would_remove": result["would_remove"],
            "failed": result["failed"],
            "skipped": result["skipped"],
            "recycled": result["recycled"],
            "bytes_freed": result["bytes_freed"],
            "bytes_estimated": result["bytes_estimated"],
            "bytes_recycled": result["bytes_recycled"],
            "bytes_by_category": by_category,
            "recycled_by_category": recycled_by_category,
            "estimated_by_category": estimated_by_category,
            "dry_run": dry_run,
            "log_path": self.get_log_path(),
        }

    def empty_recycle_bin(self) -> Dict[str, Any]:
        category = self.get_category("recycle_bin")
        if category is None:
            result = _new_clean_result()
            result["failed"].append(
                {
                    "path": "Recycle Bin",
                    "size": 0,
                    "reason": "Recycle Bin category unavailable",
                }
            )
            result["log_path"] = self.get_log_path()
            return result
        items = category.scan()
        if not items:
            result = _new_clean_result()
            result["log_path"] = self.get_log_path()
            return result
        result = category.clean(items)
        result["log_path"] = self.get_log_path()
        return result
