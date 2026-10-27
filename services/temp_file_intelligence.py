import os
from typing import Dict, Any

try:
    from services.file_usage_detector import FileUsageDetector
    _detector = FileUsageDetector()
except Exception:
    _detector = None

try:
    from services.app_state_detector import AppStateDetector
    _app_detector = AppStateDetector()
except Exception:
    _app_detector = None


def classify(path: str, check_usage: bool = False) -> Dict[str, Any]:
    name = os.path.basename(path)
    ext = os.path.splitext(name)[1].lower()
    parent = os.path.dirname(path).lower()
    app = "Unknown"
    method = "none"
    purpose = "Unknown"
    safety = "Review"
    confidence = "Low"
    reason = "Purpose could not be established."

    exe_names = []
    # recognized temp structures
    if "chrome" in parent:
        app = "Google Chrome"
        method = "directory"
        purpose = "Browser cache/temp"
        safety = "Lower risk"
        confidence = "Medium"
        reason = "Matches recognized application temp directory (inferred, not verified creator)."
        exe_names = ["chrome.exe"]
    elif "edge" in parent:
        app = "Microsoft Edge"
        method = "directory"
        purpose = "Browser cache/temp"
        safety = "Lower risk"
        confidence = "Medium"
        reason = "Matches recognized application temp directory (inferred, not verified creator)."
        exe_names = ["msedge.exe"]
    elif "firefox" in parent:
        app = "Mozilla Firefox"
        method = "directory"
        purpose = "Browser cache/temp"
        safety = "Lower risk"
        confidence = "Medium"
        reason = "Matches recognized application temp directory (inferred, not verified creator)."
        exe_names = ["firefox.exe"]
    elif ext in (".tmp", ".temp"):
        purpose = "Temporary file"
        safety = "Review"
        confidence = "Low"
        reason = "Generic temporary extension."
    elif ext in (".log",):
        purpose = "Log file"
        safety = "Review"
        confidence = "Low"
        reason = "Log file; review before deletion."

    usage = {"status": "Not checked", "processes": [], "error": None}
    if check_usage and _detector is not None:
        try:
            u = _detector.check_file(path)
            if u:
                usage = u
        except Exception as e:
            usage = {"status": "Unknown", "processes": [], "error": str(e)}

    app_running = {"status": "Not checked", "evidence": "Not checked"}
    app_installed = {"status": "Unknown", "evidence": "Not checked"}
    if _app_detector is not None and method == "directory" and exe_names:
        try:
            app_running = _app_detector.is_running(exe_names=exe_names)
        except Exception as e:
            app_running = {"status": "Unknown", "evidence": str(e)}
        try:
            app_installed = _app_detector.is_installed(app_names=[app])
        except Exception as e:
            app_installed = {"status": "Unknown", "evidence": str(e)}

    return {
        "likely_app": app,
        "app_method": method,
        "purpose": purpose,
        "safety": safety,
        "confidence": confidence,
        "reason": reason,
        "in_use": usage.get("status"),
        "app_running": app_running.get("status"),
        "app_running_evidence": app_running.get("evidence"),
        "app_installed": app_installed.get("status"),
        "app_installed_evidence": app_installed.get("evidence"),
        "usage_processes": usage.get("processes", []),
        "usage_error": usage.get("error"),
        "usage_checked_at": None,
    }
