"""System Tools service for PC-Toolbox."""

import subprocess
import sys
import platform
import webbrowser
import os
from typing import Dict, Any, Callable


class SystemToolsService:
    def __init__(self, activity_service=None):
        self.activity_service = activity_service

    def is_windows(self):
        return platform.system() == "Windows"

    def launch(self, exe, args=None, shell=False):
        args = args or []
        try:
            subprocess.Popen([exe] + list(args), shell=shell)
            self._log("Launched: %s" % exe)
            return {"success": True, "message": "Launched %s" % exe}
        except Exception as e:
            self._log("Failed to launch %s: %s" % (exe, e))
            return {"success": False, "message": str(e)}

    def open_path(self, path):
        if not os.path.exists(path):
            return {"success": False, "message": "Path not found: %s" % path}
        try:
            os.startfile(path)
            return {"success": True, "message": "Opened %s" % path}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def open_url(self, url):
        try:
            webbrowser.open(url)
            return {"success": True, "message": "Opened browser"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def _log(self, msg):
        if self.activity_service:
            try:
                self.activity_service.log(msg)
            except Exception:
                pass

    def get_tools(self):
        win = self.is_windows()
        tools = [
            {"id": "disk_cleanup", "group": "System Maintenance", "name": "Disk Cleanup", "desc": "Open Windows Disk Cleanup", "action": lambda: self.launch("cleanmgr.exe")},
            {"id": "sfc", "group": "System Maintenance", "name": "System File Checker", "desc": "Run sfc /scannow (elevated)", "action": lambda: self.launch("sfc", ["/scannow"])},
            {"id": "chkdsk", "group": "System Maintenance", "name": "Check Disk", "desc": "Check disk for errors", "action": lambda: self.launch("chkdsk")},
            {"id": "win_security", "group": "System Maintenance", "name": "Windows Security", "desc": "Open Windows Security", "action": lambda: self.launch("windowsdefender:") if False else self.launch("cmd", ["/c", "start", "windowsdefender:"])},
            {"id": "msinfo", "group": "System Information", "name": "System Information", "desc": "Open msinfo32", "action": lambda: self.launch("msinfo32.exe")},
            {"id": "taskmgr", "group": "System Information", "name": "Task Manager", "desc": "Open Task Manager", "action": lambda: self.launch("taskmgr.exe")},
            {"id": "devmgmt", "group": "System Information", "name": "Device Manager", "desc": "Open Device Manager", "action": lambda: self.launch("devmgmt.msc")},
            {"id": "eventvwr", "group": "System Information", "name": "Event Viewer", "desc": "Open Event Viewer", "action": lambda: self.launch("eventvwr.msc")},
            {"id": "ipconfig", "group": "Network Tools", "name": "IP Configuration", "desc": "Show IP config", "action": lambda: self.launch("ipconfig", ["/all"])},
            {"id": "ping", "group": "Network Tools", "name": "Ping Test", "desc": "Ping a host", "action": None},
            {"id": "dns_flush", "group": "Network Tools", "name": "DNS Flush", "desc": "Flush DNS cache", "action": lambda: self.launch("ipconfig", ["/flushdns"])},
            {"id": "netconn", "group": "Network Tools", "name": "Network Connections", "desc": "Open network connections", "action": lambda: self.launch("ncpa.cpl")},
            {"id": "services", "group": "Administrative Tools", "name": "Services", "desc": "Open Services", "action": lambda: self.launch("services.msc")},
            {"id": "regedit", "group": "Administrative Tools", "name": "Registry Editor", "desc": "Open Registry Editor", "action": lambda: self.launch("regedit.exe")},
            {"id": "gpedit", "group": "Administrative Tools", "name": "Group Policy", "desc": "Open Group Policy Editor", "action": lambda: self.launch("gpedit.msc")},
            {"id": "msconfig", "group": "Administrative Tools", "name": "System Configuration", "desc": "Open msconfig", "action": lambda: self.launch("msconfig.exe")},
            {"id": "temp_folder", "group": "File and Folder Tools", "name": "Open Temp Folder", "desc": "Open user temp directory", "action": lambda: self.open_path(os.environ.get("TEMP", ""))},
            {"id": "appdata", "group": "File and Folder Tools", "name": "Open AppData", "desc": "Open AppData folder", "action": lambda: self.open_path(os.environ.get("APPDATA", ""))},
            {"id": "hosts", "group": "File and Folder Tools", "name": "Open Hosts File", "desc": "Open hosts file (read-only)", "action": lambda: self.launch("notepad.exe", [r"C:\Windows\System32\drivers\etc\hosts"])},
            {"id": "perms", "group": "File and Folder Tools", "name": "File Permissions", "desc": "Display permissions", "action": None},
            {"id": "winupdate", "group": "Other Utilities", "name": "Windows Update", "desc": "Open Windows Update", "action": lambda: self.launch("control", ["/name", "Microsoft.WindowsUpdate"])},
            {"id": "power", "group": "Other Utilities", "name": "Power Options", "desc": "Open Power Options", "action": lambda: self.launch("powercfg.cpl")},
            {"id": "fonts", "group": "Other Utilities", "name": "Installed Fonts", "desc": "Open Fonts folder", "action": lambda: self.open_path(r"C:\Windows\Fonts")},
            {"id": "envvars", "group": "Other Utilities", "name": "Environment Variables", "desc": "Display env vars", "action": None},
        ]
        if not win:
            for t in tools:
                t["available"] = False
        else:
            for t in tools:
                t["available"] = True
        return tools
