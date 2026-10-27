"""Application state detection using psutil and registry."""

import os
import sys
import time
import psutil


class AppStateDetector:
    def __init__(self):
        self._winreg = None
        if sys.platform == "win32":
            try:
                import winreg
                self._winreg = winreg
            except Exception:
                self._winreg = None
        self._proc_cache = None
        self._proc_cache_time = 0
        self._proc_cache_ttl = 5.0
        self._install_cache = {}
        self._install_cache_ttl = 300.0

    def _get_proc_snapshot(self):
        now = time.monotonic()
        if self._proc_cache is not None and (now - self._proc_cache_time) < self._proc_cache_ttl:
            return self._proc_cache
        procs = []
        try:
            for proc in psutil.process_iter(['name', 'exe']):
                try:
                    info = proc.info
                    procs.append({
                        'name': (info.get('name') or '').lower(),
                        'exe': info.get('exe'),
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
                except Exception:
                    continue
        except Exception:
            self._proc_cache = []
            self._proc_cache_time = now
            return self._proc_cache
        self._proc_cache = procs
        self._proc_cache_time = now
        return self._proc_cache

    def is_running(self, exe_paths=None, exe_names=None):
        exe_paths = [os.path.normcase(os.path.abspath(p)) for p in (exe_paths or []) if p]
        exe_names = [n.lower() for n in (exe_names or []) if n]
        if not exe_paths and not exe_names:
            return {"status": "Unknown", "evidence": "No executable identity"}
        procs = self._get_proc_snapshot()
        if procs is None:
            return {"status": "Unknown", "evidence": "Process enumeration unavailable"}
        for info in procs:
            name = info.get('name') or ''
            exe = info.get('exe')
            if exe_names and name in exe_names:
                return {"status": "Running", "evidence": "Process name match: %s (weaker)" % name}
            if exe and exe_paths:
                try:
                    n = os.path.normcase(os.path.abspath(exe))
                    if n in exe_paths:
                        return {"status": "Running", "evidence": "Executable path match"}
                except Exception:
                    pass
        return {"status": "Not running", "evidence": "No matching process found in snapshot"}

    def is_installed(self, exe_paths=None, app_names=None):
        exe_paths = [os.path.normcase(os.path.abspath(p)) for p in (exe_paths or []) if p]
        app_names = [n.lower() for n in (app_names or []) if n]
        key_id = tuple(sorted(exe_paths)) + tuple(sorted(app_names))
        now = time.monotonic()
        if key_id in self._install_cache:
            cached = self._install_cache[key_id]
            if now - cached['time'] < self._install_cache_ttl:
                return cached['result']
        if exe_paths:
            for p in exe_paths:
                if os.path.exists(p):
                    res = {"status": "Installed", "evidence": "Executable found at %s" % p}
                    self._install_cache[key_id] = {'result': res, 'time': now}
                    return res
        if self._winreg is None or sys.platform != "win32":
            res = {"status": "Unknown", "evidence": "Registry not available"}
            self._install_cache[key_id] = {'result': res, 'time': now}
            return res
        roots = [
            (self._winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (self._winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (self._winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]
        for hive, path in roots:
            try:
                key = self._winreg.OpenKey(hive, path, 0, self._winreg.KEY_READ)
            except Exception:
                continue
            try:
                count = self._winreg.QueryInfoKey(key)[0]
            except Exception:
                count = 0
            for i in range(count):
                try:
                    skey = self._winreg.EnumKey(key, i)
                    ssub = self._winreg.OpenKey(key, skey)
                except Exception:
                    continue
                try:
                    name = self._winreg.QueryValueEx(ssub, "DisplayName")[0]
                except Exception:
                    name = ""
                try:
                    if app_names and name and any(an in name.lower() for an in app_names):
                        self._winreg.CloseKey(ssub)
                        self._winreg.CloseKey(key)
                        res = {"status": "Installed", "evidence": "Registry uninstall entry: %s" % name}
                        self._install_cache[key_id] = {'result': res, 'time': now}
                        return res
                except Exception:
                    pass
                try:
                    self._winreg.CloseKey(ssub)
                except Exception:
                    pass
            try:
                self._winreg.CloseKey(key)
            except Exception:
                pass
        if exe_paths:
            res = {"status": "Unknown", "evidence": "No uninstall entry found; executable path not present"}
        else:
            res = {"status": "Unknown", "evidence": "No installation evidence found"}
        self._install_cache[key_id] = {'result': res, 'time': now}
        return res
