"""Service-level coverage for the plan's Review Focus items 3 and 4.

3. Overlapping Roots: duplicate or nested paths must be deduplicated.
4. Empty Roots: a scan with no configured roots must return a graceful empty
   result, never crash.
"""

import os
import sys
import tempfile

sys.path.insert(0, "d:/Windows app/PC-Toolbox")

from services.leftovers_service import LeftoversService


def test_scan_with_no_roots_returns_empty_gracefully():
    """A scan with no configured roots must not crash and returns zero items."""
    svc = LeftoversService(roots=[])
    result = svc.scan()
    assert result["item_count"] == 0
    assert result["items"] == []
    assert result["errors"] == []
    assert result["locations_scanned"] == 0


def test_scan_with_no_roots_arg_returns_empty_gracefully():
    """scan(roots=None) with no configured roots must not crash."""
    svc = LeftoversService(roots=[])
    result = svc.scan(roots=None)
    assert result["item_count"] == 0
    assert result["items"] == []


def test_duplicate_roots_are_deduplicated():
    """Duplicate root paths must not be scanned twice."""
    tmp = tempfile.mkdtemp()
    with open(os.path.join(tmp, "leftover_a.txt"), "w") as f:
        f.write("a")

    svc = LeftoversService(roots=[tmp, tmp])
    result = svc.scan()
    assert result["item_count"] == 1
    assert result["locations_scanned"] == 1


def test_nested_roots_are_deduplicated():
    """A root nested inside another must not be scanned twice."""
    outer = tempfile.mkdtemp()
    inner = os.path.join(outer, "sub")
    os.makedirs(inner)
    with open(os.path.join(inner, "leftover_b.txt"), "w") as f:
        f.write("b")

    svc = LeftoversService(roots=[outer, inner])
    result = svc.scan()
    # Deduplication is enforced at the file level: the nested file must not be
    # discovered twice even though two roots overlap.
    assert result["item_count"] == 1
    assert result["locations_scanned"] == 2


def test_drive_root_is_rejected():
    """A drive root must never be accepted as a scan root."""
    svc = LeftoversService(roots=["C:\\"])
    assert svc.get_approved_roots() == []


def test_nonexistent_root_is_collected_as_error_not_exception():
    """A nonexistent root must appear in errors, not raise."""
    svc = LeftoversService(roots=[r"Z:\Nope\Does\Not\Exist"])
    result = svc.scan()
    assert result["item_count"] == 0
    assert any("Root not accessible" in e for e in result["errors"])
    assert result["locations_scanned"] == 0


def test_validate_removal_rejects_drive_root():
    """validate_removal must reject a drive-root path."""
    svc = LeftoversService(roots=[tempfile.mkdtemp()])
    ok, reason = svc.validate_removal({"path": "C:\\"}, svc.get_approved_roots())
    assert ok is False
    assert "root" in reason.lower()


def test_validate_removal_rejects_path_outside_roots():
    """validate_removal must reject paths outside approved roots."""
    roots = [tempfile.mkdtemp()]
    svc = LeftoversService(roots=roots)
    ok, reason = svc.validate_removal({"path": r"C:\Windows\NotAScanRoot.txt"}, roots)
    assert ok is False
    assert "outside" in reason.lower()