"""Windows Restart Manager file usage detection."""

import ctypes
from ctypes import wintypes
import os
import sys
from typing import Dict, Any, List


class RM_UNIQUE_PROCESS(ctypes.Structure):
    _fields_ = [
        ("dwProcessId", wintypes.DWORD),
        ("ProcessStartTime", wintypes.FILETIME),
    ]


class RM_PROCESS_INFO(ctypes.Structure):
    _fields_ = [
        ("Process", RM_UNIQUE_PROCESS),
        ("strAppName", wintypes.WCHAR * 256),
        ("strServiceShortName", wintypes.WCHAR * 64),
        ("ApplicationType", wintypes.DWORD),
        ("AppStatus", wintypes.DWORD),
        ("TSSessionId", wintypes.DWORD),
        ("bRestartable", wintypes.BOOL),
    ]


class FileUsageDetector:
    def __init__(self):
        self._rstrtmgr = None
        if sys.platform == "win32":
            try:
                self._rstrtmgr = ctypes.windll.LoadLibrary("rstrtmgr.dll")
            except Exception:
                self._rstrtmgr = None

    def check_file(self, path: str) -> Dict[str, Any]:
        if self._rstrtmgr is None or sys.platform != "win32":
            return {"status": "Unsupported", "processes": [], "error": "Restart Manager unavailable"}
        if not os.path.exists(path):
            return {"status": "Unknown", "processes": [], "error": "File does not exist"}

        session_handle = wintypes.DWORD()
        session_key = ctypes.create_unicode_buffer(64)
        try:
            res = self._rstrtmgr.RmStartSession(ctypes.byref(session_handle), 0, session_key)
            if res != 0:
                return {"status": "Unknown", "processes": [], "error": "RmStartSession failed: %d" % res}

            file_path = ctypes.c_wchar_p(os.path.abspath(path))
            res = self._rstrtmgr.RmRegisterResources(session_handle, 1, ctypes.byref(file_path), 0, None, 0, None)
            if res != 0:
                self._rstrtmgr.RmEndSession(session_handle)
                return {"status": "Unknown", "processes": [], "error": "RmRegisterResources failed: %d" % res}

            n_proc = wintypes.UINT(0)
            n_session = wintypes.UINT(0)
            reason = wintypes.DWORD(0)
            res = self._rstrtmgr.RmGetList(session_handle, ctypes.byref(n_proc), ctypes.byref(n_proc), None, ctypes.byref(reason))
            if res == 234:  # ERROR_MORE_DATA
                proc_array = (RM_PROCESS_INFO * n_proc.value)()
                res = self._rstrtmgr.RmGetList(session_handle, ctypes.byref(n_proc), ctypes.byref(n_proc), proc_array, ctypes.byref(reason))
                if res != 0:
                    self._rstrtmgr.RmEndSession(session_handle)
                    return {"status": "Unknown", "processes": [], "error": "RmGetList failed: %d" % res}
                procs = []
                for i in range(n_proc.value):
                    p = proc_array[i]
                    procs.append({
                        "pid": p.Process.dwProcessId,
                        "app_name": p.strAppName,
                        "service_name": p.strServiceShortName,
                    })
                self._rstrtmgr.RmEndSession(session_handle)
                if procs:
                    return {"status": "In use", "processes": procs, "error": None}
                else:
                    return {"status": "No current use detected", "processes": [], "error": None}
            elif res == 0:
                self._rstrtmgr.RmEndSession(session_handle)
                return {"status": "No current use detected", "processes": [], "error": None}
            else:
                self._rstrtmgr.RmEndSession(session_handle)
                return {"status": "Unknown", "processes": [], "error": "RmGetList failed: %d" % res}
        except Exception as e:
            try:
                self._rstrtmgr.RmEndSession(session_handle)
            except Exception:
                pass
            return {"status": "Unknown", "processes": [], "error": str(e)}
