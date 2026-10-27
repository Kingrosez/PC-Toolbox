"""PC Health view for PC-Toolbox - full implementation."""

import customtkinter as ctk
import threading
from datetime import datetime
from typing import List, Dict, Any, Optional

import sys
sys.path.insert(0, 'd:/Windows app/PC-Toolbox')


class PCHealthView(ctk.CTkFrame):
    """PC Health screen with diagnostics, checks, recommendations, and quick actions."""

    def __init__(self, master, navigation):
        super().__init__(master, fg_color=master.theme.colors["deep_background"])
        self.theme = master.theme
        self.navigation = navigation

        self.act = getattr(navigation, "activity_service", None)
        self.ctrl = getattr(navigation, "pc_health_controller", None)
        if not self.act or not self.ctrl:
            from services.activity_service import ActivityService
            from controllers.pc_health_controller import PCHealthController
            self.act = self.act or ActivityService()
            self.ctrl = self.ctrl or PCHealthController(self.act)

        self._checking = False
        self._check_th = None
        self._last_result = None

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._setup_ui()
        self._run_check()

    def _setup_ui(self):
        self.scroll = ctk.CTkScrollableFrame(
            self,
            fg_color=self.theme.colors["deep_background"],
            scrollbar_fg_color=self.theme.colors["glass_panel"],
            scrollbar_button_color=self.theme.colors["border"],
            scrollbar_button_hover_color=self.theme.colors["blue_accent"],
        )
        self.scroll.pack(fill="both", expand=True)
        self.scroll.grid_columnconfigure(0, weight=1)

        self._create_header()
        self._create_overall_and_metrics()
        self._create_info_and_checks()
        self._create_recommendations()
        self._create_quick_actions()

    def _create_header(self):
        header = ctk.CTkFrame(self.scroll, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 16))
        header.grid_columnconfigure(1, weight=1)

        left = ctk.CTkFrame(header, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(left, text="\u2764", font=ctk.CTkFont(size=30),
                    text_color=self.theme.colors["red_accent"]).grid(row=0, column=0, sticky="w", padx=(0, 12))

        ctk.CTkLabel(left, text="PC Health", font=ctk.CTkFont(size=28, weight="bold"),
                    text_color=self.theme.colors["primary_text"]).grid(row=0, column=1, sticky="w")

        ctk.CTkLabel(left, text="Check your system health and get recommendations",
                    font=ctk.CTkFont(size=13),
                    text_color=self.theme.colors["secondary_text"]).grid(row=1, column=1, sticky="w", pady=(2, 0))

        right = ctk.CTkFrame(header, fg_color="transparent")
        right.grid(row=0, column=1, sticky="e")

        self.updated_lbl = ctk.CTkLabel(right, text="Last checked: --",
                                       font=ctk.CTkFont(size=11),
                                       text_color=self.theme.colors["muted_text"])
        self.updated_lbl.grid(row=1, column=0, sticky="e", pady=(2, 0))

        ctk.CTkButton(
            right, text="View All Logs", command=lambda: self.navigation.navigate_to("logs"),
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=self.theme.colors["glass_panel"],
            hover_color=self.theme.colors["hover_state"],
            text_color=self.theme.colors["primary_text"],
            height=30, width=120, corner_radius=6,
            border_width=1, border_color=self.theme.colors["border"],
        ).grid(row=0, column=1, sticky="e", padx=(8, 0))

        self.check_btn = ctk.CTkButton(
            right, text="Run Full Check", command=self._run_check,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=self.theme.colors["blue_accent"],
            hover_color="#1570D6", text_color="white",
            height=30, width=120, corner_radius=6,
        )
        self.check_btn.grid(row=0, column=2, sticky="e", padx=(8, 0))

    def _create_overall_and_metrics(self):
        row = ctk.CTkFrame(self.scroll, fg_color="transparent")
        row.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 16))
        row.grid_columnconfigure(0, weight=1)
        row.grid_columnconfigure(1, weight=3)

        # Overall health card (left)
        overall = ctk.CTkFrame(row, fg_color=self.theme.colors["glass_panel"],
                              corner_radius=14, border_width=1,
                              border_color=self.theme.colors["border"])
        overall.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        ctk.CTkLabel(overall, text="Overall Health", font=ctk.CTkFont(size=16, weight="bold"),
                    text_color=self.theme.colors["primary_text"]).pack(padx=20, pady=(20, 8))

        self.score_lbl = ctk.CTkLabel(overall, text="\u2014", font=ctk.CTkFont(size=48, weight="bold"),
                                     text_color=self.theme.colors["green_accent"])
        self.score_lbl.pack(pady=(0, 4))

        self.status_lbl = ctk.CTkLabel(overall, text="Checking...", font=ctk.CTkFont(size=14, weight="bold"),
                                      text_color=self.theme.colors["secondary_text"])
        self.status_lbl.pack(pady=(0, 8))

        self.desc_lbl = ctk.CTkLabel(overall, text="Running system health checks...",
                                    font=ctk.CTkFont(size=12),
                                    text_color=self.theme.colors["secondary_text"],
                                    wraplength=200, justify="center")
        self.desc_lbl.pack(padx=20, pady=(0, 8))

        self.recs_count_lbl = ctk.CTkLabel(overall, text="0 recommendations",
                                          font=ctk.CTkFont(size=11),
                                          text_color=self.theme.colors["muted_text"])
        self.recs_count_lbl.pack(padx=20, pady=(0, 20))

        # Metric cards (right)
        metrics = ctk.CTkFrame(row, fg_color="transparent")
        metrics.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        for i in range(2):
            metrics.grid_columnconfigure(i, weight=1)
        for i in range(2):
            metrics.grid_rowconfigure(i, weight=1)

        defs = [
            ("CPU", "cpu", self.theme.colors["blue_accent"]),
            ("Memory", "memory", self.theme.colors["purple_accent"]),
            ("Storage", "storage", self.theme.colors["red_accent"]),
            ("System", "system", self.theme.colors["green_accent"]),
        ]
        self._metric_cache = {}
        for i, (title, key, accent) in enumerate(defs):
            r, c = divmod(i, 2)
            card = ctk.CTkFrame(metrics, fg_color=self.theme.colors["glass_panel"],
                               corner_radius=12, border_width=1,
                               border_color=self.theme.colors["border"])
            card.grid(row=r, column=c, sticky="nsew", padx=6, pady=6)

            ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=13, weight="bold"),
                        text_color=self.theme.colors["primary_text"]).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 4))

            val = ctk.CTkLabel(card, text="\u2014", font=ctk.CTkFont(size=24, weight="bold"),
                              text_color=accent)
            val.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 2))

            sub = ctk.CTkLabel(card, text="", font=ctk.CTkFont(size=11),
                              text_color=self.theme.colors["secondary_text"])
            sub.grid(row=2, column=0, sticky="w", padx=16, pady=(0, 14))

            self._metric_cache[key] = {"value": val, "sub": sub, "accent": accent}

    def _create_info_and_checks(self):
        row = ctk.CTkFrame(self.scroll, fg_color="transparent")
        row.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 16))
        row.grid_columnconfigure(0, weight=1)
        row.grid_columnconfigure(1, weight=1)

        # System info panel
        info_panel = ctk.CTkFrame(row, fg_color=self.theme.colors["glass_panel"],
                                 corner_radius=14, border_width=1,
                                 border_color=self.theme.colors["border"])
        info_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        info_panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(info_panel, text="System Information", font=ctk.CTkFont(size=16, weight="bold"),
                    text_color=self.theme.colors["primary_text"]).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 8))

        self.info_lbl = ctk.CTkLabel(info_panel, text="Loading...",
                                    font=ctk.CTkFont(size=12),
                                    text_color=self.theme.colors["secondary_text"],
                                    justify="left")
        self.info_lbl.grid(row=1, column=0, sticky="nw", padx=20, pady=(0, 16))

        # Health checks panel
        checks_panel = ctk.CTkFrame(row, fg_color=self.theme.colors["glass_panel"],
                                   corner_radius=14, border_width=1,
                                   border_color=self.theme.colors["border"])
        checks_panel.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        checks_panel.grid_columnconfigure(0, weight=1)
        checks_panel.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(checks_panel, text="Health Checks", font=ctk.CTkFont(size=16, weight="bold"),
                    text_color=self.theme.colors["primary_text"]).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 8))

        self.checks_frame = ctk.CTkScrollableFrame(
            checks_panel, fg_color=self.theme.colors["secondary_panel"],
            corner_radius=8,
        )
        self.checks_frame.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        self.checks_frame.grid_columnconfigure(0, weight=1)

    def _create_recommendations(self):
        panel = ctk.CTkFrame(self.scroll, fg_color=self.theme.colors["glass_panel"],
                            corner_radius=14, border_width=1,
                            border_color=self.theme.colors["border"])
        panel.grid(row=3, column=0, sticky="ew", padx=24, pady=(0, 16))
        panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(panel, text="Recommendations", font=ctk.CTkFont(size=16, weight="bold"),
                    text_color=self.theme.colors["primary_text"]).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 8))

        self.recs_frame = ctk.CTkFrame(panel, fg_color="transparent")
        self.recs_frame.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 16))
        self.recs_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self.recs_frame, text="Run a full check to see recommendations",
                    font=ctk.CTkFont(size=12),
                    text_color=self.theme.colors["muted_text"]).grid(row=0, column=0, sticky="w")

    def _create_quick_actions(self):
        panel = ctk.CTkFrame(self.scroll, fg_color=self.theme.colors["glass_panel"],
                            corner_radius=14, border_width=1,
                            border_color=self.theme.colors["border"])
        panel.grid(row=4, column=0, sticky="ew", padx=24, pady=(0, 20))
        panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(panel, text="Quick Actions", font=ctk.CTkFont(size=16, weight="bold"),
                    text_color=self.theme.colors["primary_text"]).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 8))

        qa = ctk.CTkFrame(panel, fg_color="transparent")
        qa.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 16))
        for i in range(4):
            qa.grid_columnconfigure(i, weight=1)

        actions = [
            ("Open Temp Cleaner", "temp_cleaner"),
            ("Open Storage Analyzer", "storage_analyzer"),
            ("Manage Startup", "startup_manager"),
            ("Check Updates", "system_tools"),
        ]
        for i, (label, key) in enumerate(actions):
            ctk.CTkButton(
                qa, text=label, command=lambda k=key: self.navigation.navigate_to(k),
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color=self.theme.colors["glass_panel"],
                hover_color=self.theme.colors["hover_state"],
                text_color=self.theme.colors["primary_text"],
                height=36, corner_radius=8,
                border_width=1, border_color=self.theme.colors["border"],
            ).grid(row=0, column=i, sticky="ew", padx=6)

    # ------------------------------------------------------------------ check
    def _run_check(self):
        if self._checking:
            return
        self._checking = True
        self.check_btn.configure(state="disabled")
        self.score_lbl.configure(text="\u2014", text_color=self.theme.colors["secondary_text"])
        self.status_lbl.configure(text="Checking...", text_color=self.theme.colors["secondary_text"])
        self.desc_lbl.configure(text="Running system health checks...")
        self._check_th = threading.Thread(target=self._run, daemon=True)
        self._check_th.start()

    def _run(self):
        try:
            result = self.ctrl.run_full_check()
        except Exception as e:
            result = {"error": str(e)}
        try:
            if self.winfo_exists():
                self.after(0, self._done, result)
        except Exception:
            pass

    def _done(self, result):
        self._checking = False
        self.check_btn.configure(state="normal")
        if result.get("error"):
            self.score_lbl.configure(text="!", text_color=self.theme.colors["red_accent"])
            self.status_lbl.configure(text="Error", text_color=self.theme.colors["red_accent"])
            self.desc_lbl.configure(text=result.get("error", "Unknown error"))
            return

        self._last_result = result
        score = result.get("score", 0)
        status = result.get("status", "Unknown")
        color = self.theme.colors["green_accent"]
        if score < 50:
            color = self.theme.colors["red_accent"]
        elif score < 80:
            color = self.theme.colors["orange_accent"]

        self.score_lbl.configure(text=str(score), text_color=color)
        self.status_lbl.configure(text=status, text_color=color)
        self.desc_lbl.configure(text="System health score based on %d checks" % result.get("passed_count", 0))
        self.recs_count_lbl.configure(text="%d recommendations" % len(result.get("recommendations", [])))

        # Update metrics
        m = result.get("metrics", {})
        cpu = m.get("cpu_usage")
        mem_pct = m.get("memory_percent")
        mem_used = m.get("memory_used_bytes")
        mem_total = m.get("memory_total_bytes")
        stor_pct = m.get("storage_percent")
        stor_used = m.get("storage_used_bytes")
        stor_total = m.get("storage_total_bytes")
        stor_free = m.get("storage_free_bytes")

        cpu_status = "Normal"
        if cpu is not None:
            if cpu >= 90:
                cpu_status = "Critical"
            elif cpu >= 70:
                cpu_status = "Elevated"
        self._metric_cache["cpu"]["value"].configure(text="%.1f%%" % cpu if cpu is not None else "\u2014")
        self._metric_cache["cpu"]["sub"].configure(text=cpu_status)

        mem_status = "Normal"
        if mem_pct is not None:
            if mem_pct >= 90:
                mem_status = "Critical"
            elif mem_pct >= 70:
                mem_status = "Elevated"
        self._metric_cache["memory"]["value"].configure(text="%.1f%%" % mem_pct if mem_pct is not None else "\u2014")
        self._metric_cache["memory"]["sub"].configure(
            text="%s / %s" % (self.ctrl.format_size(mem_used), self.ctrl.format_size(mem_total)) if mem_used and mem_total else mem_status
        )

        stor_status = "Normal"
        if stor_pct is not None:
            if stor_pct >= 95:
                stor_status = "Critical"
            elif stor_pct >= 85:
                stor_status = "Elevated"
        self._metric_cache["storage"]["value"].configure(text="%.1f%%" % stor_pct if stor_pct is not None else "\u2014")
        self._metric_cache["storage"]["sub"].configure(
            text="%s free" % self.ctrl.format_size(stor_free) if stor_free else stor_status
        )

        passed = result.get("passed_count", 0)
        warnings = result.get("warning_count", 0)
        errors = result.get("error_count", 0)
        self._metric_cache["system"]["value"].configure(text="%d/%d" % (passed, passed + warnings + errors))
        self._metric_cache["system"]["sub"].configure(text="%d warnings, %d errors" % (warnings, errors))

        # System info
        si = result.get("system_info", {})
        info_lines = [
            "OS: %s %s" % (si.get("os_name", "Unknown"), si.get("os_version", "")),
            "Build: %s" % si.get("os_build", "Unknown"),
            "Processor: %s" % si.get("processor", "Unknown"),
            "Cores: %s physical / %s logical" % (si.get("physical_cores", 0), si.get("logical_cores", 0)),
            "Memory: %s" % self.ctrl.format_size(si.get("total_memory")),
            "Architecture: %s" % si.get("architecture", "Unknown"),
            "Uptime: %s" % self.ctrl.format_uptime(si.get("uptime_seconds")),
            "Hostname: %s" % si.get("hostname", "Unknown"),
        ]
        self.info_lbl.configure(text="\n".join(info_lines))

        # Health checks
        for w in self.checks_frame.winfo_children():
            w.destroy()
        for check in result.get("checks", []):
            row = ctk.CTkFrame(self.checks_frame, fg_color="transparent")
            row.pack(fill="x", pady=4)
            row.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(row, text=check.get("icon", "\u2139"), font=ctk.CTkFont(size=16)).grid(
                row=0, column=0, sticky="w", padx=(0, 8)
            )
            name_lbl = ctk.CTkLabel(row, text=check.get("name", "Check"),
                                   font=ctk.CTkFont(size=13, weight="bold"),
                                   text_color=self.theme.colors["primary_text"])
            name_lbl.grid(row=0, column=1, sticky="w")

            status = check.get("status", "Info")
            status_color = self.theme.colors["green_accent"]
            if status in ("Warning", "Fail"):
                status_color = self.theme.colors["orange_accent"] if status == "Warning" else self.theme.colors["red_accent"]
            elif status == "Info":
                status_color = self.theme.colors["blue_accent"]

            ctk.CTkLabel(row, text=status, font=ctk.CTkFont(size=11, weight="bold"),
                        text_color=status_color).grid(row=0, column=2, sticky="e", padx=(8, 0))

            detail_lbl = ctk.CTkLabel(row, text=check.get("detail", ""),
                                     font=ctk.CTkFont(size=10),
                                     text_color=self.theme.colors["muted_text"],
                                     wraplength=300)
            detail_lbl.grid(row=1, column=1, columnspan=2, sticky="w", pady=(2, 0))

        # Recommendations
        for w in self.recs_frame.winfo_children():
            w.destroy()
        recs = result.get("recommendations", [])
        if not recs:
            ctk.CTkLabel(self.recs_frame, text="No recommendations. System looks healthy.",
                        font=ctk.CTkFont(size=12),
                        text_color=self.theme.colors["green_accent"]).grid(row=0, column=0, sticky="w")
        for i, rec in enumerate(recs):
            r = ctk.CTkFrame(self.recs_frame, fg_color="transparent")
            r.grid(row=i, column=0, sticky="ew", pady=4)
            r.grid_columnconfigure(1, weight=1)

            sev = rec.get("severity", "info")
            sev_color = self.theme.colors["blue_accent"]
            if sev == "warning":
                sev_color = self.theme.colors["orange_accent"]
            elif sev == "error":
                sev_color = self.theme.colors["red_accent"]

            ctk.CTkLabel(r, text=sev.upper(), font=ctk.CTkFont(size=10, weight="bold"),
                        text_color=sev_color).grid(row=0, column=0, sticky="w", padx=(0, 8))

            ctk.CTkLabel(r, text="%s: %s" % (rec.get("title", "System"), rec.get("message", "")),
                        font=ctk.CTkFont(size=12),
                        text_color=self.theme.colors["primary_text"],
                        wraplength=500).grid(row=0, column=1, sticky="w")

        self.updated_lbl.configure(text="Last checked: %s" % datetime.now().strftime("%H:%M:%S"))
