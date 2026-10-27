"""Dashboard view for PC-Toolbox - redesigned glassmorphism layout."""

import customtkinter as ctk
import sys
import threading
from datetime import datetime

sys.path.insert(0, 'd:/Windows app/PC-Toolbox')

from controllers.dashboard_controller import DashboardController
from views.dashboard_helpers import update_cpu_card, RefreshLock


class DashboardView(ctk.CTkFrame):
    """Dashboard screen with system overview, storage, health, activity, and quick actions."""

    def __init__(self, master, navigation):
        self.theme = master.theme
        super().__init__(master, fg_color=self.theme.colors["deep_background"])
        self.navigation = navigation
        self.controller = DashboardController()
        self._widgets_cache = {}
        self._refresh_lock = RefreshLock()
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._setup_ui()
        self._load_data()

    def _format_bytes(self, bytes_value):
        if not bytes_value:
            return "0 B"
        for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.1f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.1f} EB"

    def _setup_ui(self):
        self.content = ctk.CTkScrollableFrame(
            self,
            fg_color=self.theme.colors["deep_background"],
            scrollbar_fg_color=self.theme.colors["glass_panel"],
            scrollbar_button_color=self.theme.colors["border"],
            scrollbar_button_hover_color=self.theme.colors["blue_accent"],
        )
        self.content.pack(fill="both", expand=True)
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_columnconfigure(1, weight=1)

        self._create_header()
        self._create_metric_cards()
        self._create_middle_section()
        self._create_bottom_section()

    def _create_header(self):
        header = ctk.CTkFrame(self.content, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=24, pady=(20, 10))
        header.grid_columnconfigure(1, weight=1)

        title = ctk.CTkLabel(
            header,
            text="Dashboard",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=self.theme.colors["primary_text"],
        )
        title.grid(row=0, column=0, sticky="w")

        subtitle = ctk.CTkLabel(
            header,
            text="System maintenance overview",
            font=ctk.CTkFont(size=13),
            text_color=self.theme.colors["secondary_text"],
        )
        subtitle.grid(row=1, column=0, sticky="w", pady=(2, 0))

        right = ctk.CTkFrame(header, fg_color="transparent")
        right.grid(row=0, column=1, rowspan=2, sticky="e")
        right.grid_columnconfigure(0, weight=1)

        self.online_lbl = ctk.CTkLabel(
            right,
            text="System Online  \u25CF",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=self.theme.colors["green_accent"],
        )
        self.online_lbl.grid(row=0, column=0, sticky="e")

        self.updated_lbl = ctk.CTkLabel(
            right,
            text="Last updated: --",
            font=ctk.CTkFont(size=11),
            text_color=self.theme.colors["muted_text"],
        )
        self.updated_lbl.grid(row=1, column=0, sticky="e", pady=(2, 0))

        self.refresh_btn = ctk.CTkButton(
            right,
            text="Refresh",
            command=self._load_data,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=self.theme.colors["glass_panel"],
            border_width=1,
            border_color=self.theme.colors["border"],
            hover_color=self.theme.colors["hover_state"],
            text_color=self.theme.colors["primary_text"],
            height=30,
            width=80,
            corner_radius=6,
        )
        self.refresh_btn.grid(row=0, column=1, rowspan=2, sticky="e", padx=(16, 0))

    def _create_metric_cards(self):
        cards_frame = ctk.CTkFrame(self.content, fg_color="transparent")
        cards_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=24, pady=(0, 16))
        for i in range(4):
            cards_frame.grid_columnconfigure(i, weight=1)

        self._create_metric_card(
            cards_frame, 0, 0,
            icon="\U0001F4BB",
            title="CPU Usage",
            accent=self.theme.colors["blue_accent"],
        )
        self._create_metric_card(
            cards_frame, 0, 1,
            icon="\U0001F4A5",
            title="Memory Usage",
            accent=self.theme.colors["purple_accent"],
        )
        self._create_metric_card(
            cards_frame, 0, 2,
            icon="\U0001F4BE",
            title="Storage Used",
            accent=self.theme.colors["cyan_accent"],
        )
        self._create_metric_card(
            cards_frame, 0, 3,
            icon="\u23F1",
            title="System Uptime",
            accent=self.theme.colors["green_accent"],
        )

    def _create_metric_card(self, parent, row, col, icon, title, accent):
        card = ctk.CTkFrame(
            parent,
            fg_color=self.theme.colors["glass_panel"],
            corner_radius=14,
            border_width=1,
            border_color=self.theme.colors["border"],
        )
        card.grid(row=row, column=col, sticky="nsew", padx=6, pady=0)
        card.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 8))
        top.grid_columnconfigure(0, weight=1)
        top.grid_columnconfigure(1, weight=0)

        # Left side: icon + title (independent from status)
        left_frame = ctk.CTkFrame(top, fg_color="transparent")
        left_frame.grid(row=0, column=0, sticky="w")
        left_frame.grid_columnconfigure(1, weight=1)

        icon_lbl = ctk.CTkLabel(
            left_frame,
            text=icon,
            font=ctk.CTkFont(size=20),
            text_color=accent,
        )
        icon_lbl.grid(row=0, column=0, sticky="w", padx=(0, 8))

        title_lbl = ctk.CTkLabel(
            left_frame,
            text=title,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=self.theme.colors["primary_text"],
        )
        title_lbl.grid(row=0, column=1, sticky="w")

        # Right side: status badge (independent position, no overlap)
        status_lbl = ctk.CTkLabel(
            top,
            text="Normal",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=self.theme.colors["green_accent"],
        )
        status_lbl.grid(row=0, column=1, sticky="e")

        value_lbl = ctk.CTkLabel(
            card,
            text="--",
            font=ctk.CTkFont(size=30, weight="bold"),
            text_color=self.theme.colors["primary_text"],
        )
        value_lbl.grid(row=1, column=0, sticky="w", padx=18, pady=(0, 4))

        progress = ctk.CTkProgressBar(
            card,
            height=6,
            corner_radius=3,
            fg_color=self.theme.colors["secondary_panel"],
            progress_color=accent,
        )
        progress.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 6))
        progress.set(0)

        sub_lbl = ctk.CTkLabel(
            card,
            text="--",
            font=ctk.CTkFont(size=11),
            text_color=self.theme.colors["secondary_text"],
        )
        sub_lbl.grid(row=3, column=0, sticky="w", padx=18, pady=(0, 2))

        footer_lbl = ctk.CTkLabel(
            card,
            text="--",
            font=ctk.CTkFont(size=10),
            text_color=self.theme.colors["muted_text"],
        )
        footer_lbl.grid(row=4, column=0, sticky="w", padx=18, pady=(0, 16))

        key = title.lower().replace(" ", "_")
        self._widgets_cache[key] = {
            "card": card,
            "value_label": value_lbl,
            "status_label": status_lbl,
            "progress_bar": progress,
            "sub_label": sub_lbl,
            "footer_label": footer_lbl,
            "accent": accent,
        }

    def _create_middle_section(self):
        storage_panel = ctk.CTkFrame(
            self.content,
            fg_color=self.theme.colors["glass_panel"],
            corner_radius=14,
            border_width=1,
            border_color=self.theme.colors["border"],
        )
        storage_panel.grid(row=2, column=0, sticky="nsew", padx=(24, 10), pady=(0, 16))
        storage_panel.grid_columnconfigure(0, weight=1)
        storage_panel.grid_rowconfigure(1, weight=1)

        self.content.grid_rowconfigure(2, weight=1)

        s_header = ctk.CTkFrame(storage_panel, fg_color="transparent")
        s_header.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 10))
        s_header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            s_header,
            text="Storage Overview",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=self.theme.colors["primary_text"],
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            s_header,
            text="View in Storage Analyzer",
            font=ctk.CTkFont(size=11),
            text_color=self.theme.colors["blue_accent"],
        ).grid(row=0, column=1, sticky="e")

        self.storage_list = ctk.CTkScrollableFrame(
            storage_panel,
            fg_color=self.theme.colors["secondary_panel"],
            corner_radius=10,
            scrollbar_fg_color=self.theme.colors["glass_panel"],
        )
        self.storage_list.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 16))
        self.storage_list.grid_columnconfigure(0, weight=1)

        self._widgets_cache["storage_list"] = self.storage_list

        health_panel = ctk.CTkFrame(
            self.content,
            fg_color=self.theme.colors["glass_panel"],
            corner_radius=14,
            border_width=1,
            border_color=self.theme.colors["border"],
        )
        health_panel.grid(row=2, column=1, sticky="nsew", padx=(10, 24), pady=(0, 16))
        health_panel.grid_columnconfigure(0, weight=1)
        health_panel.grid_rowconfigure(1, weight=1)

        h_header = ctk.CTkFrame(health_panel, fg_color="transparent")
        h_header.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 10))
        h_header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            h_header,
            text="Health Summary",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=self.theme.colors["primary_text"],
        ).grid(row=0, column=0, sticky="w")

        self.health_status_lbl = ctk.CTkLabel(
            h_header,
            text="Good",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=self.theme.colors["green_accent"],
        )
        self.health_status_lbl.grid(row=0, column=1, sticky="e")

        self.health_list = ctk.CTkScrollableFrame(
            health_panel,
            fg_color=self.theme.colors["secondary_panel"],
            corner_radius=10,
            scrollbar_fg_color=self.theme.colors["glass_panel"],
        )
        self.health_list.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 16))
        self.health_list.grid_columnconfigure(0, weight=1)

        self._widgets_cache["health_list"] = self.health_list

    def _create_bottom_section(self):
        activity_panel = ctk.CTkFrame(
            self.content,
            fg_color=self.theme.colors["glass_panel"],
            corner_radius=14,
            border_width=1,
            border_color=self.theme.colors["border"],
        )
        activity_panel.grid(row=3, column=0, sticky="nsew", padx=(24, 10), pady=(0, 20))
        activity_panel.grid_columnconfigure(0, weight=1)
        activity_panel.grid_rowconfigure(1, weight=1)

        self.content.grid_rowconfigure(3, weight=1)

        a_header = ctk.CTkFrame(activity_panel, fg_color="transparent")
        a_header.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 10))
        a_header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            a_header,
            text="Recent Activity",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=self.theme.colors["primary_text"],
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            a_header,
            text="View All Logs",
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            hover_color=self.theme.colors["hover_state"],
            text_color=self.theme.colors["blue_accent"],
            height=24,
            width=90,
            command=lambda: self.navigation.navigate_to("logs"),
        ).grid(row=0, column=1, sticky="e")

        self.activity_list = ctk.CTkScrollableFrame(
            activity_panel,
            fg_color=self.theme.colors["secondary_panel"],
            corner_radius=10,
            scrollbar_fg_color=self.theme.colors["glass_panel"],
        )
        self.activity_list.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 16))
        self.activity_list.grid_columnconfigure(0, weight=1)

        self._widgets_cache["activity_list"] = self.activity_list

        quick_panel = ctk.CTkFrame(
            self.content,
            fg_color=self.theme.colors["glass_panel"],
            corner_radius=14,
            border_width=1,
            border_color=self.theme.colors["border"],
        )
        quick_panel.grid(row=3, column=1, sticky="nsew", padx=(10, 24), pady=(0, 20))
        quick_panel.grid_columnconfigure(0, weight=1)
        quick_panel.grid_rowconfigure(1, weight=1)

        q_header = ctk.CTkFrame(quick_panel, fg_color="transparent")
        q_header.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 10))
        q_header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            q_header,
            text="Quick Actions",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=self.theme.colors["primary_text"],
        ).grid(row=0, column=0, sticky="w")

        q_grid = ctk.CTkFrame(quick_panel, fg_color="transparent")
        q_grid.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 16))
        for i in range(2):
            q_grid.grid_columnconfigure(i, weight=1)
        for i in range(2):
            q_grid.grid_rowconfigure(i, weight=1)

        actions = [
            ("\U0001F5D1", "Temp Cleaner", "Clean temporary files", "temp_cleaner", self.theme.colors["blue_accent"]),
            ("\U0001F4BB", "Uninstaller", "Manage installed apps", "uninstaller", self.theme.colors["purple_accent"]),
            ("\U0001F4BE", "Storage Analyzer", "Analyze drive usage", "storage_analyzer", self.theme.colors["cyan_accent"]),
            ("\U0001F3E5", "PC Health", "System health check", "pc_health", self.theme.colors["green_accent"]),
        ]

        for i, (icon, title, desc, key, accent) in enumerate(actions):
            r, c = divmod(i, 2)
            card = ctk.CTkFrame(
                q_grid,
                fg_color=self.theme.colors["secondary_panel"],
                corner_radius=10,
                border_width=1,
                border_color=self.theme.colors["border"],
            )
            card.grid(row=r, column=c, sticky="nsew", padx=6, pady=6)
            card.grid_columnconfigure(0, weight=1)

            icon_lbl = ctk.CTkLabel(
                card, text=icon, font=ctk.CTkFont(size=20), text_color=accent
            )
            icon_lbl.grid(row=0, column=0, sticky="w", padx=14, pady=(12, 4))

            title_lbl = ctk.CTkLabel(
                card, text=title, font=ctk.CTkFont(size=13, weight="bold"),
                text_color=self.theme.colors["primary_text"],
            )
            title_lbl.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 2))

            desc_lbl = ctk.CTkLabel(
                card, text=desc, font=ctk.CTkFont(size=11),
                text_color=self.theme.colors["secondary_text"],
            )
            desc_lbl.grid(row=2, column=0, sticky="w", padx=14, pady=(0, 10))

            card.bind("<Button-1>", lambda e, k=key: self.navigation.navigate_to(k))
            for child in card.winfo_children():
                child.bind("<Button-1>", lambda e, k=key: self.navigation.navigate_to(k))

    def _status_for_value(self, value, warn=75, crit=90):
        if value >= crit:
            return "Critical", self.theme.colors["red_accent"]
        if value >= warn:
            return "Warning", self.theme.colors["orange_accent"]
        return "Normal", self.theme.colors["green_accent"]

    def _drive_status(self, percent):
        return self._status_for_value(percent, warn=75, crit=90)

    def _update_ui(self):
        try:
            data = self.controller.data
            now = datetime.now().strftime("%H:%M:%S")
            if hasattr(self, "updated_lbl"):
                self.updated_lbl.configure(text="Last updated: %s" % now)

            if data and data.get("system_metrics"):
                system_overview = self.controller.get_system_overview()
                storage_overview = self.controller.get_storage_overview()

                card_data = {
                    "cpu_usage": system_overview.get("cpu_usage", 0),
                    "cpu_physical_cores": system_overview.get("cpu_physical_cores"),
                    "cpu_logical_cores": system_overview.get("cpu_logical_cores"),
                    "memory_percent": system_overview.get("memory_percent", 0),
                    "memory_total_bytes": system_overview.get("memory_total_bytes", 0),
                    "memory_used_bytes": system_overview.get("memory_used_bytes", 0),
                    "uptime_seconds": system_overview.get("uptime_seconds"),
                    "os_name": system_overview.get("os_name", ""),
                    "os_version": system_overview.get("os_version", ""),
                    "hostname": system_overview.get("hostname", ""),
                    "storage": storage_overview,
                }
                self._update_card_data(card_data)

            if data and data.get("storage"):
                self._update_storage_panel(data["storage"])

            if data and data.get("health"):
                self._update_health_panel(data["health"])

            if data and data.get("activity"):
                self._update_activity_panel(data["activity"])

            if hasattr(self, "status_label"):
                self.status_label.configure(text="Dashboard updated")

        except Exception as e:
            print("Error updating UI: %s" % e)

    def _update_card_data(self, system_data):
        cpu_key = "cpu_usage"
        if cpu_key in self._widgets_cache:
            cache = self._widgets_cache[cpu_key]
            cpu_value = system_data.get("cpu_usage", 0)
            value_text, progress_value, status_text, status_color = update_cpu_card(cpu_value, self.theme.colors)
            cache["value_label"].configure(text=value_text)
            cache["progress_bar"].set(progress_value)
            cache["status_label"].configure(text=status_text, text_color=status_color)
            physical = system_data.get("cpu_physical_cores")
            logical = system_data.get("cpu_logical_cores")
            cache["sub_label"].configure(
                text="%s Cores" % physical if physical is not None else "Unknown cores"
            )
            cache["footer_label"].configure(
                text="%s Logical Processors" % logical if logical is not None else "Unknown processors"
            )

        mem_key = "memory_usage"
        if mem_key in self._widgets_cache:
            cache = self._widgets_cache[mem_key]
            mem_percent = system_data.get("memory_percent", 0)
            mem_total = system_data.get("memory_total_bytes", 0)
            mem_used = system_data.get("memory_used_bytes", 0)
            mem_free = mem_total - mem_used if mem_total and mem_used else 0

            status_text, status_color = self._status_for_value(mem_percent, warn=85, crit=95)
            cache["value_label"].configure(text="%.1f%%" % mem_percent)
            cache["progress_bar"].set(mem_percent / 100.0)
            cache["status_label"].configure(text=status_text, text_color=status_color)
            if mem_total and mem_used:
                total_gb = mem_total / (1024 ** 3)
                used_gb = mem_used / (1024 ** 3)
                cache["sub_label"].configure(text="%.1f GB / %.1f GB" % (used_gb, total_gb))
                cache["footer_label"].configure(text="%s Free" % self._format_bytes(mem_free))
            else:
                cache["sub_label"].configure(text="--")
                cache["footer_label"].configure(text="--")

        stor_key = "storage_used"
        if stor_key in self._widgets_cache:
            cache = self._widgets_cache[stor_key]
            drives = system_data.get("storage", {}).get("drives", [])
            total_used = sum(d.get("used_bytes", 0) for d in drives if d.get("accessible", False))
            total_cap = sum(d.get("total_bytes", 0) for d in drives if d.get("accessible", False))
            total_free = total_cap - total_used
            percent_used = (total_used / total_cap * 100) if total_cap > 0 else 0
            status_text, status_color = self._status_for_value(percent_used, warn=75, crit=90)
            cache["value_label"].configure(text="%.1f%%" % percent_used)
            cache["progress_bar"].set(min(percent_used / 100.0, 1.0))
            cache["status_label"].configure(text=status_text, text_color=status_color)
            cache["sub_label"].configure(text="%s / %s" % (self._format_bytes(total_used), self._format_bytes(total_cap)))
            cache["footer_label"].configure(text="%s Free" % self._format_bytes(total_free))

        upt_key = "system_uptime"
        if upt_key in self._widgets_cache:
            cache = self._widgets_cache[upt_key]
            uptime_seconds = system_data.get("uptime_seconds", 0)
            days = int(uptime_seconds // 86400)
            hours = int((uptime_seconds % 86400) // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            if days > 0:
                uptime_str = "%dd %dh %dm" % (days, hours, minutes)
            elif hours > 0:
                uptime_str = "%dh %dm" % (hours, minutes)
            else:
                uptime_str = "%dm" % minutes
            cache["value_label"].configure(text=uptime_str)
            cache["status_label"].configure(text="Kernel Stable", text_color=self.theme.colors["green_accent"])
            cache["sub_label"].configure(text="%s" % system_data.get("os_name", ""))
            cache["footer_label"].configure(text="%s %s" % (system_data.get("os_version", ""), system_data.get("hostname", "")))

    def _update_storage_panel(self, storage):
        list_frame = self._widgets_cache.get("storage_list")
        if not list_frame:
            return
        for w in list_frame.winfo_children():
            w.destroy()

        drives = storage.get("drives", [])
        if not drives:
            ctk.CTkLabel(
                list_frame, text="No drives found.",
                text_color=self.theme.colors["muted_text"],
            ).pack(padx=10, pady=10)
            return

        for drive in drives:
            row = ctk.CTkFrame(list_frame, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=5)
            row.grid_columnconfigure(1, weight=1)

            icon_lbl = ctk.CTkLabel(
                row, text="\U0001F4BE", font=ctk.CTkFont(size=14),
                text_color=self.theme.colors["cyan_accent"],
            )
            icon_lbl.grid(row=0, column=0, sticky="w", padx=(0, 8))

            letter = drive.get("device", "Unknown")
            mount = drive.get("mountpoint", "")
            letter_lbl = ctk.CTkLabel(
                row, text="%s  %s" % (letter, mount),
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=self.theme.colors["primary_text"],
            )
            letter_lbl.grid(row=0, column=1, sticky="w")

            percent_used = drive.get("percent_used", 0)
            accessible = drive.get("accessible", False)
            if not accessible:
                status_text, status_color = "Inaccessible", self.theme.colors["red_accent"]
                percent_used = 0
            else:
                status_text, status_color = self._drive_status(percent_used)

            status_lbl = ctk.CTkLabel(
                row, text=status_text,
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color=status_color,
            )
            status_lbl.grid(row=0, column=2, sticky="e")

            used_bytes = drive.get("used_bytes", 0) or 0
            total_bytes = drive.get("total_bytes", 0) or 0
            free_bytes = total_bytes - used_bytes if total_bytes and used_bytes else 0

            bar = ctk.CTkProgressBar(
                row, height=6, corner_radius=3,
                fg_color=self.theme.colors["secondary_panel"],
                progress_color=status_color if accessible else self.theme.colors["muted_text"],
            )
            bar.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(4, 0))
            bar.set((percent_used / 100.0) if accessible else 0)

            info_lbl = ctk.CTkLabel(
                row,
                text="%s used  \u00B7  %s free" % (self._format_bytes(used_bytes), self._format_bytes(free_bytes)),
                font=ctk.CTkFont(size=10),
                text_color=self.theme.colors["secondary_text"],
            )
            info_lbl.grid(row=2, column=0, columnspan=3, sticky="w", pady=(2, 0))

    def _update_health_panel(self, health):
        list_frame = self._widgets_cache.get("health_list")
        if not list_frame:
            return
        for w in list_frame.winfo_children():
            w.destroy()

        overall = health.get("overall_status", "good")
        status_color = self.theme.colors["green_accent"]
        if overall == "warning":
            status_color = self.theme.colors["orange_accent"]
        elif overall == "error":
            status_color = self.theme.colors["red_accent"]
        self.health_status_lbl.configure(text=overall.upper(), text_color=status_color)

        indicators = health.get("indicators", [])
        if not indicators:
            ctk.CTkLabel(
                list_frame,
                text="\u2713 All systems within range",
                text_color=self.theme.colors["secondary_text"],
            ).pack(padx=10, pady=10)
            return

        severity_icon = {
            "error": "\u2716",
            "warning": "\u26A0",
            "info": "\u2139",
        }
        severity_color = {
            "error": self.theme.colors["red_accent"],
            "warning": self.theme.colors["orange_accent"],
            "info": self.theme.colors["blue_accent"],
        }

        for ind in indicators[:6]:
            sev = ind.get("severity", "info")
            row = ctk.CTkFrame(list_frame, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=4)
            row.grid_columnconfigure(1, weight=1)

            icon_lbl = ctk.CTkLabel(
                row, text=severity_icon.get(sev, "\u2139"),
                font=ctk.CTkFont(size=13),
                text_color=severity_color.get(sev, self.theme.colors["blue_accent"]),
            )
            icon_lbl.grid(row=0, column=0, sticky="w", padx=(0, 8))

            title_lbl = ctk.CTkLabel(
                row, text="%s: %s" % (ind.get("category", "System"), ind.get("message", "")),
                font=ctk.CTkFont(size=12),
                text_color=self.theme.colors["primary_text"],
            )
            title_lbl.grid(row=0, column=1, sticky="w")

    def _update_activity_panel(self, activity_data):
        list_frame = self._widgets_cache.get("activity_list")
        if not list_frame:
            return
        for w in list_frame.winfo_children():
            w.destroy()

        activities = activity_data.get("recent_events", []) if activity_data else []
        if not activities:
            ctk.CTkLabel(
                list_frame, text="No recent activity",
                text_color=self.theme.colors["muted_text"],
            ).pack(padx=10, pady=10)
            return

        severity_icon = {
            "error": "\u2716",
            "warning": "\u26A0",
            "info": "\u2139",
        }
        severity_color = {
            "error": self.theme.colors["red_accent"],
            "warning": self.theme.colors["orange_accent"],
            "info": self.theme.colors["blue_accent"],
        }

        for activity in activities[:6]:
            row = ctk.CTkFrame(list_frame, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=4)
            row.grid_columnconfigure(1, weight=1)

            sev = activity.get("severity", "info")
            icon_lbl = ctk.CTkLabel(
                row, text=severity_icon.get(sev, "\u2139"),
                font=ctk.CTkFont(size=12),
                text_color=severity_color.get(sev, self.theme.colors["blue_accent"]),
            )
            icon_lbl.grid(row=0, column=0, sticky="w", padx=(0, 8))

            title_lbl = ctk.CTkLabel(
                row, text="%s: %s" % (activity.get("event_type", "System"), activity.get("message", "")),
                font=ctk.CTkFont(size=12),
                text_color=self.theme.colors["primary_text"],
            )
            title_lbl.grid(row=0, column=1, sticky="w")

            ts_lbl = ctk.CTkLabel(
                row, text=activity.get("timestamp_formatted", ""),
                font=ctk.CTkFont(size=10),
                text_color=self.theme.colors["muted_text"],
            )
            ts_lbl.grid(row=1, column=1, sticky="e", pady=(1, 0))

    def _load_data(self):
        if not self._refresh_lock.acquire():
            return
        def _refresh_task():
            try:
                self.controller.refresh_data()
                print("Dashboard data loaded")
            except Exception as e:
                print("Error loading data: %s" % e)
            finally:
                try:
                    if self.winfo_exists():
                        self.after(0, self._update_ui)
                except Exception:
                    pass
                self._refresh_lock.release()
        threading.Thread(target=_refresh_task, daemon=True).start()
