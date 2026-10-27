"""Settings view for PC-Toolbox."""

import customtkinter as ctk
import tkinter.filedialog as fd
import tkinter.messagebox as mb

NAVY = "#0d1b2a"
CARD = "#1b2838"
ACCENT = "#4a90d9"
CATEGORIES = ["General", "Scan Settings", "Exclusions", "Appearance", "Notifications", "Privacy & Security", "Backup & Restore", "About"]


class SettingsView(ctk.CTkFrame):
    def __init__(self, master, navigation):
        super().__init__(master, fg_color="transparent")
        self.navigation = navigation
        self.service = getattr(navigation, "settings_service", None)
        self._dirty = False
        self._original = {}
        if self.service:
            self._original = dict(self.service.settings)
        self._current_cat = "General"
        self._build()
        self._show_category("General")

    def _build(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=20, pady=10)
        ctk.CTkLabel(header, text="\u2699", font=ctk.CTkFont(size=28)).pack(side="left")
        tf = ctk.CTkFrame(header, fg_color="transparent")
        tf.pack(side="left", padx=10)
        ctk.CTkLabel(tf, text="Settings", font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(tf, text="Configure application settings and preferences", font=ctk.CTkFont(size=12), text_color="gray").pack(anchor="w")

        # Category sidebar
        self.cat_frame = ctk.CTkFrame(self, fg_color=CARD, width=180)
        self.cat_frame.grid(row=1, column=0, sticky="nsw", padx=(20, 10), pady=10)
        for cat in CATEGORIES:
            ctk.CTkButton(self.cat_frame, text=cat, anchor="w", fg_color="transparent", command=lambda c=cat: self._show_category(c)).pack(fill="x", padx=5, pady=2)

        # Content panel
        self.content = ctk.CTkScrollableFrame(self, fg_color=CARD)
        self.content.grid(row=1, column=1, sticky="nsew", padx=(0, 20), pady=10)

        # Bottom action row
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=2, column=0, columnspan=2, sticky="ew", padx=20, pady=10)
        ctk.CTkButton(actions, text="Reset to Defaults", fg_color="#c0392b", command=self._reset).pack(side="left", padx=5)
        ctk.CTkButton(actions, text="Cancel", command=self._cancel).pack(side="left", padx=5)
        ctk.CTkButton(actions, text="Save Settings", command=self._save).pack(side="right", padx=5)
        self.status_lbl = ctk.CTkLabel(actions, text="", text_color="gray")
        self.status_lbl.pack(side="right", padx=10)

    def _clear_content(self):
        for w in self.content.winfo_children():
            w.destroy()

    def _show_category(self, cat):
        self._current_cat = cat
        self._clear_content()
        if cat == "General":
            self._general()
        elif cat == "Scan Settings":
            self._scan()
        elif cat == "Appearance":
            self._appearance()
        elif cat == "Notifications":
            self._notifications()
        elif cat == "Privacy & Security":
            self._privacy()
        elif cat == "Backup & Restore":
            self._backup()
        elif cat == "About":
            self._about()
        else:
            ctk.CTkLabel(self.content, text="%s (coming soon)" % cat).pack(pady=20)

    def _general(self):
        ctk.CTkLabel(self.content, text="General", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", pady=10)
        self._toggle("Start with Windows", "start_with_windows")
        self._toggle("Check for updates automatically", "auto_update")
        self._toggle("Show notifications for long operations", "show_notifications")
        self._toggle("Minimize to system tray (if supported)", "minimize_tray")

    def _toggle(self, label, key):
        var = ctk.BooleanVar(value=self.service.get(key) if self.service else False)
        cb = ctk.CTkCheckBox(self.content, text=label, variable=var, command=lambda: self._mark_dirty())
        cb.pack(anchor="w", pady=5)
        setattr(self, "_var_" + key, var)

    def _scan(self):
        ctk.CTkLabel(self.content, text="Scan Settings", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", pady=10)
        # threads
        ctk.CTkLabel(self.content, text="Max concurrent scan threads").pack(anchor="w")
        self.threads_var = ctk.StringVar(value=str(self.service.get("scan_threads") if self.service else 2))
        ctk.CTkOptionMenu(self.content, values=["1", "2", "4", "8"], variable=self.threads_var, command=lambda v: self._mark_dirty()).pack(anchor="w", pady=5)
        # large file threshold
        ctk.CTkLabel(self.content, text="Large-file threshold").pack(anchor="w")
        self.threshold_var = ctk.StringVar(value=str(self.service.get("large_file_threshold_mb") if self.service else 100))
        ctk.CTkOptionMenu(self.content, values=["100", "500", "1024"], variable=self.threshold_var, command=lambda v: self._mark_dirty()).pack(anchor="w", pady=5)
        # scan locations
        ctk.CTkLabel(self.content, text="Default Scan Locations").pack(anchor="w", pady=(10, 5))
        self.loc_frame = ctk.CTkFrame(self.content, fg_color="transparent")
        self.loc_frame.pack(fill="x")
        self._render_locations()
        ctk.CTkButton(self.content, text="Add Folder", command=self._add_location).pack(anchor="w", pady=5)

    def _render_locations(self):
        for w in self.loc_frame.winfo_children():
            w.destroy()
        if not self.service:
            return
        for loc in self.service.get("scan_locations") or []:
            f = ctk.CTkFrame(self.loc_frame, fg_color="transparent")
            f.pack(fill="x", pady=2)
            ctk.CTkLabel(f, text=loc).pack(side="left")
            ctk.CTkButton(f, text="Remove", width=70, command=lambda l=loc: self._remove_location(l)).pack(side="right")

    def _add_location(self):
        path = fd.askdirectory()
        if path and self.service:
            if self.service.validate_path(path):
                locs = list(self.service.get("scan_locations") or [])
                if path not in locs:
                    locs.append(path)
                    self.service.set("scan_locations", locs)
                    self._render_locations()
                    self._mark_dirty()

    def _remove_location(self, loc):
        if self.service:
            locs = [l for l in (self.service.get("scan_locations") or []) if l != loc]
            self.service.set("scan_locations", locs)
            self._render_locations()
            self._mark_dirty()

    def _appearance(self):
        ctk.CTkLabel(self.content, text="Appearance", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", pady=10)
        ctk.CTkLabel(self.content, text="Theme").pack(anchor="w")
        self.theme_var = ctk.StringVar(value=self.service.get("theme") if self.service else "Dark Navy")
        ctk.CTkOptionMenu(self.content, values=["Dark Navy"], variable=self.theme_var, command=lambda v: self._mark_dirty()).pack(anchor="w", pady=5)

    def _notifications(self):
        ctk.CTkLabel(self.content, text="Notifications", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", pady=10)
        self._toggle("Notify when scans finish", "notify_scan_complete")
        self._toggle("Notify when scans fail", "notify_scan_failed")
        self._toggle("Notify about completed maintenance", "notify_maintenance")

    def _privacy(self):
        ctk.CTkLabel(self.content, text="Privacy & Security", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", pady=10)
        if self.service:
            ctk.CTkLabel(self.content, text=self.service.get_storage_info()).pack(anchor="w", pady=5)
        ctk.CTkLabel(self.content, text="No telemetry is collected.").pack(anchor="w", pady=5)
        ctk.CTkButton(self.content, text="Open Logs", command=lambda: self.navigation.show_view("logs") if hasattr(self.navigation, "show_view") else None).pack(anchor="w", pady=5)

    def _backup(self):
        ctk.CTkLabel(self.content, text="Backup & Restore", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", pady=10)
        ctk.CTkButton(self.content, text="Export Settings", command=self._export).pack(anchor="w", pady=5)
        ctk.CTkButton(self.content, text="Import Settings", command=self._import).pack(anchor="w", pady=5)

    def _about(self):
        ctk.CTkLabel(self.content, text="About", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", pady=10)
        ctk.CTkLabel(self.content, text="PC-Toolbox v2.0").pack(anchor="w", pady=5)

    def _mark_dirty(self):
        self._dirty = True
        self.status_lbl.configure(text="Unsaved changes")

    def _save(self):
        if not self.service:
            return
        # collect
        for key in ["start_with_windows", "auto_update", "show_notifications", "minimize_tray", "notify_scan_complete", "notify_scan_failed", "notify_maintenance"]:
            var = getattr(self, "_var_" + key, None)
            if var is not None:
                self.service.set(key, bool(var.get()))
        self.service.set("scan_threads", int(self.threads_var.get()) if hasattr(self, "threads_var") else self.service.get("scan_threads"))
        if hasattr(self, "threshold_var"):
            self.service.set("large_file_threshold_mb", int(self.threshold_var.get()))
        if hasattr(self, "theme_var"):
            self.service.set("theme", self.theme_var.get())
        ok = self.service.save()
        if ok:
            self._dirty = False
            self.status_lbl.configure(text="Saved")
            self._original = dict(self.service.settings)
        else:
            self.status_lbl.configure(text="Save failed")

    def _cancel(self):
        if self.service:
            self.service.settings = dict(self._original)
        self._dirty = False
        self.status_lbl.configure(text="Cancelled")
        self._show_category(self._current_cat)

    def _reset(self):
        if not self.service:
            return
        if not mb.askyesno("Reset", "Reset all settings to defaults?"):
            return
        self.service.reset_defaults()
        self._original = dict(self.service.settings)
        self._dirty = True
        self._show_category(self._current_cat)
        self.status_lbl.configure(text="Reset (save to apply)")

    def _export(self):
        path = fd.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if path and self.service:
            if self.service.export_json(path):
                mb.showinfo("Export", "Settings exported")
            else:
                mb.showerror("Export", "Export failed")

    def _import(self):
        path = fd.askopenfilename(filetypes=[("JSON", "*.json")])
        if path and self.service:
            ok, msg = self.service.import_json(path)
            if ok:
                self._show_category(self._current_cat)
                mb.showinfo("Import", msg)
                self._mark_dirty()
            else:
                mb.showerror("Import", msg)
