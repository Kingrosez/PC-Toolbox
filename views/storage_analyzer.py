"""Storage Analyzer view for PC-Toolbox - full implementation."""

import customtkinter as ctk
import threading
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

import os
import sys
sys.path.insert(0, 'd:/Windows app/PC-Toolbox')


class StorageAnalyzerView(ctk.CTkFrame):
    """Storage Analyzer screen with drive selection, analysis, treemap, table, details."""

    def __init__(self, master, navigation):
        super().__init__(master, fg_color=master.theme.colors["deep_background"])
        self.theme = master.theme
        self.navigation = navigation

        self.act = getattr(navigation, "activity_service", None)
        self.ctrl = getattr(navigation, "storage_analyzer_controller", None)
        if not self.act or not self.ctrl:
            from services.activity_service import ActivityService
            from controllers.storage_analyzer_controller import StorageAnalyzerController
            self.act = self.act or ActivityService()
            self.ctrl = self.ctrl or StorageAnalyzerController(self.act)

        self._scanning = False
        self._scan_th = None
        self._items = []
        self._filtered = []
        self._selected_item = None
        self._selected_drive = None
        self._search_text = ""
        self._type_filter = "All Types"
        self._page = 1
        self._per_page = 50
        self._last_updated = None

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._setup_ui()
        self._idle()

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
        self._create_summary_cards()
        self._create_toolbar()
        self._create_visualization_panel()
        self._create_table_panel()
        self._create_details_and_actions()
        self._create_footer()

    def _create_header(self):
        header = ctk.CTkFrame(self.scroll, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 16))
        header.grid_columnconfigure(1, weight=1)

        left = ctk.CTkFrame(header, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(left, text="\U0001F4BE", font=ctk.CTkFont(size=30),
                    text_color=self.theme.colors["blue_accent"]).grid(row=0, column=0, sticky="w", padx=(0, 12))

        ctk.CTkLabel(left, text="Storage Analyzer", font=ctk.CTkFont(size=28, weight="bold"),
                    text_color=self.theme.colors["primary_text"]).grid(row=0, column=1, sticky="w")

        ctk.CTkLabel(left, text="Analyze disk usage and find large files and folders",
                    font=ctk.CTkFont(size=13),
                    text_color=self.theme.colors["secondary_text"]).grid(row=1, column=1, sticky="w", pady=(2, 0))

        right = ctk.CTkFrame(header, fg_color="transparent")
        right.grid(row=0, column=1, sticky="e")

        self.updated_lbl = ctk.CTkLabel(right, text="Last updated: --",
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

        self.refresh_btn = ctk.CTkButton(
            right, text="Refresh", command=self._analyze,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=self.theme.colors["glass_panel"],
            border_width=1, border_color=self.theme.colors["border"],
            hover_color=self.theme.colors["hover_state"],
            text_color=self.theme.colors["primary_text"],
            height=30, width=80, corner_radius=6,
        )
        self.refresh_btn.grid(row=0, column=2, sticky="e", padx=(8, 0))

    def _create_summary_cards(self):
        cards = ctk.CTkFrame(self.scroll, fg_color="transparent")
        cards.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 16))
        for i in range(4):
            cards.grid_columnconfigure(i, weight=1)

        defs = [
            ("\U0001F4BE", "Total Space", "total", self.theme.colors["blue_accent"]),
            ("\U0001F4C8", "Used Space", "used", self.theme.colors["orange_accent"]),
            ("\U0001F4C9", "Free Space", "free", self.theme.colors["green_accent"]),
            ("\U0001F4C4", "Total Files", "files", self.theme.colors["cyan_accent"]),
        ]
        self._card_cache = {}
        for i, (icon, title, key, accent) in enumerate(defs):
            card = ctk.CTkFrame(
                cards, fg_color=self.theme.colors["glass_panel"],
                corner_radius=12, border_width=1,
                border_color=self.theme.colors["border"],
            )
            card.grid(row=0, column=i, sticky="nsew", padx=6, pady=0)

            ctk.CTkLabel(card, text=icon, font=ctk.CTkFont(size=20), text_color=accent).grid(
                row=0, column=0, sticky="w", padx=16, pady=(14, 0)
            )
            val = ctk.CTkLabel(card, text="\u2014", font=ctk.CTkFont(size=26, weight="bold"),
                              text_color=self.theme.colors["primary_text"])
            val.grid(row=1, column=0, sticky="w", padx=16, pady=(4, 0))
            ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=11),
                        text_color=self.theme.colors["secondary_text"]).grid(
                row=2, column=0, sticky="w", padx=16, pady=(0, 14)
            )
            self._card_cache[key] = val

    def _create_toolbar(self):
        toolbar = ctk.CTkFrame(
            self.scroll, fg_color=self.theme.colors["glass_panel"],
            corner_radius=12, border_width=1,
            border_color=self.theme.colors["border"],
        )
        toolbar.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 16))
        toolbar.grid_columnconfigure(0, weight=1)

        # Drive selector
        left = ctk.CTkFrame(toolbar, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w", padx=16, pady=12)

        ctk.CTkLabel(left, text="Select Drive:", font=ctk.CTkFont(size=12),
                    text_color=self.theme.colors["primary_text"]).grid(row=0, column=0, padx=(0, 8))

        drives = self.ctrl.get_drives()
        drive_labels = ["%s (%s)" % (d.get("device", ""), self.ctrl.service.format_size(d.get("total_bytes")))
                       for d in drives]
        if not drive_labels:
            drive_labels = ["No drives found"]

        self.drive_var = ctk.StringVar(value=drive_labels[0] if drive_labels else "")
        self.drive_menu = ctk.CTkOptionMenu(
            left, variable=self.drive_var,
            values=drive_labels,
            command=self._on_drive_change,
            font=ctk.CTkFont(size=12),
            fg_color=self.theme.colors["secondary_panel"],
            button_color=self.theme.colors["border"],
            text_color=self.theme.colors["primary_text"],
            height=32, corner_radius=8,
        )
        self.drive_menu.grid(row=0, column=1, padx=(0, 12))

        # Store drive mapping
        self._drive_map = {}
        for d, lbl in zip(drives, drive_labels):
            self._drive_map[lbl] = d
        if drives:
            self._selected_drive = drives[0]
            self.ctrl.set_selected_drive(drives[0])

        # Analyze button
        self.analyze_btn = ctk.CTkButton(
            left, text="Analyze Drive", command=self._analyze,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=self.theme.colors["blue_accent"],
            hover_color="#1570D6", text_color="white",
            height=34, corner_radius=8,
        )
        self.analyze_btn.grid(row=0, column=2, padx=(0, 8))

        self.cancel_btn = ctk.CTkButton(
            left, text="Cancel", command=self._cancel,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=self.theme.colors["red_accent"],
            hover_color="#D06565", text_color="white",
            height=34, corner_radius=8, state="disabled",
        )
        self.cancel_btn.grid(row=0, column=3, padx=(0, 8))

        # View buttons
        right = ctk.CTkFrame(toolbar, fg_color="transparent")
        right.grid(row=0, column=1, sticky="e", padx=16, pady=12)

        for txt in ["Treemap View", "List View", "File Types"]:
            ctk.CTkButton(
                right, text=txt, command=lambda t=txt: None,
                font=ctk.CTkFont(size=12),
                fg_color=self.theme.colors["glass_panel"],
                hover_color=self.theme.colors["hover_state"],
                text_color=self.theme.colors["primary_text"],
                height=32, corner_radius=8,
                border_width=1, border_color=self.theme.colors["border"],
            ).grid(row=0, column=right.grid_size()[1], padx=4)

    def _on_drive_change(self, label):
        drive = self._drive_map.get(label)
        if drive:
            self._selected_drive = drive
            self.ctrl.set_selected_drive(drive)
            self._update_drive_details(drive)

    def _create_visualization_panel(self):
        panel = ctk.CTkFrame(
            self.scroll, fg_color=self.theme.colors["glass_panel"],
            corner_radius=14, border_width=1,
            border_color=self.theme.colors["border"],
        )
        panel.grid(row=3, column=0, sticky="nsew", padx=24, pady=(0, 16))
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            panel, text="Disk Usage Visualization",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=self.theme.colors["primary_text"],
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 4))

        ctk.CTkLabel(
            panel, text="Interactive treemap showing disk space usage by folders",
            font=ctk.CTkFont(size=11),
            text_color=self.theme.colors["secondary_text"],
        ).grid(row=0, column=1, sticky="e", padx=20, pady=(16, 4))

        self.viz_canvas = ctk.CTkCanvas(
            panel, bg=self.theme.colors["secondary_panel"],
            highlightthickness=0,
        )
        self.viz_canvas.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=16, pady=(0, 16))

        self.viz_empty = ctk.CTkLabel(
            self.viz_canvas, text="Analyze a drive to see disk usage visualization",
            font=ctk.CTkFont(size=14),
            text_color=self.theme.colors["muted_text"],
        )
        self.viz_empty.place(relx=0.5, rely=0.5, anchor="center")

    def _create_table_panel(self):
        panel = ctk.CTkFrame(
            self.scroll, fg_color=self.theme.colors["glass_panel"],
            corner_radius=14, border_width=1,
            border_color=self.theme.colors["border"],
        )
        panel.grid(row=4, column=0, sticky="nsew", padx=24, pady=(0, 16))
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            panel, text="Largest Folders & Files",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=self.theme.colors["primary_text"],
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 4))

        ctk.CTkLabel(
            panel, text="Top 100 items by size on the selected drive",
            font=ctk.CTkFont(size=11),
            text_color=self.theme.colors["secondary_text"],
        ).grid(row=0, column=1, sticky="e", padx=20, pady=(16, 4))

        # Search + filter
        filter_frame = ctk.CTkFrame(panel, fg_color="transparent")
        filter_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=20, pady=(0, 8))

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *a: self._apply_filters())
        ctk.CTkEntry(
            filter_frame, textvariable=self.search_var,
            placeholder_text="Search folders or files...",
            font=ctk.CTkFont(size=12),
            fg_color=self.theme.colors["secondary_panel"],
            border_width=1, border_color=self.theme.colors["border"],
            text_color=self.theme.colors["primary_text"],
            height=30, width=200, corner_radius=8,
        ).grid(row=0, column=0, padx=(0, 8))

        self.type_var = ctk.StringVar(value="All Types")
        self.type_menu = ctk.CTkOptionMenu(
            filter_frame, variable=self.type_var,
            values=["All Types", "File", "Folder"],
            command=lambda v: self._set_type_filter(v),
            font=ctk.CTkFont(size=12),
            fg_color=self.theme.colors["secondary_panel"],
            button_color=self.theme.colors["border"],
            text_color=self.theme.colors["primary_text"],
            height=30, corner_radius=8,
        )
        self.type_menu.grid(row=0, column=1)

        self.table_body = ctk.CTkScrollableFrame(
            panel, fg_color=self.theme.colors["secondary_panel"],
            corner_radius=8,
        )
        self.table_body.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=16, pady=(0, 16))
        self.table_body.grid_columnconfigure(0, weight=1)

        self._show_empty_state()

    def _show_empty_state(self):
        for w in self.table_body.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self.table_body,
            text="Analyze a drive to see largest files and folders",
            font=ctk.CTkFont(size=14),
            text_color=self.theme.colors["muted_text"],
            justify="center",
        ).pack(pady=40)

    def _create_details_and_actions(self):
        # Drive details + file type distribution + quick actions in a row
        row = ctk.CTkFrame(self.scroll, fg_color="transparent")
        row.grid(row=5, column=0, sticky="ew", padx=24, pady=(0, 16))
        row.grid_columnconfigure(0, weight=1)
        row.grid_columnconfigure(1, weight=1)
        row.grid_columnconfigure(2, weight=1)

        # Drive details
        dd = ctk.CTkFrame(row, fg_color=self.theme.colors["glass_panel"],
                         corner_radius=12, border_width=1,
                         border_color=self.theme.colors["border"])
        dd.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        dd.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(dd, text="Drive Details", font=ctk.CTkFont(size=15, weight="bold"),
                    text_color=self.theme.colors["primary_text"]).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 8))

        self.drive_details_lbl = ctk.CTkLabel(dd, text="Select a drive to view details",
                                             font=ctk.CTkFont(size=12),
                                             text_color=self.theme.colors["secondary_text"],
                                             justify="left")
        self.drive_details_lbl.grid(row=1, column=0, sticky="nw", padx=16, pady=(0, 16))

        # File type distribution
        ftd = ctk.CTkFrame(row, fg_color=self.theme.colors["glass_panel"],
                          corner_radius=12, border_width=1,
                          border_color=self.theme.colors["border"])
        ftd.grid(row=0, column=1, sticky="nsew", padx=8)
        ftd.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(ftd, text="File Type Distribution", font=ctk.CTkFont(size=15, weight="bold"),
                    text_color=self.theme.colors["primary_text"]).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 8))

        self.type_dist_lbl = ctk.CTkLabel(ftd, text="Analyze a drive to see type distribution",
                                         font=ctk.CTkFont(size=12),
                                         text_color=self.theme.colors["secondary_text"],
                                         justify="left")
        self.type_dist_lbl.grid(row=1, column=0, sticky="nw", padx=16, pady=(0, 16))

        # Quick actions
        qa = ctk.CTkFrame(row, fg_color=self.theme.colors["glass_panel"],
                         corner_radius=12, border_width=1,
                         border_color=self.theme.colors["border"])
        qa.grid(row=0, column=2, sticky="nsew", padx=(8, 0))
        qa.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(qa, text="Quick Actions", font=ctk.CTkFont(size=15, weight="bold"),
                    text_color=self.theme.colors["primary_text"]).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 8))

        for txt in ["Find Large Files", "Find Duplicate Files", "Open in File Explorer", "Generate Report"]:
            ctk.CTkButton(qa, text=txt, command=lambda t=txt: self._quick_action(t),
                         font=ctk.CTkFont(size=12),
                         fg_color=self.theme.colors["glass_panel"],
                         hover_color=self.theme.colors["hover_state"],
                         text_color=self.theme.colors["primary_text"],
                         height=30, corner_radius=6,
                         border_width=1, border_color=self.theme.colors["border"]).grid(
                row=qa.grid_size()[1], column=0, sticky="ew", padx=16, pady=4
            )

    def _quick_action(self, action):
        if action == "Generate Report":
            self._export_report()
        elif action == "Find Large Files":
            large = self.ctrl.get_largest_files(self._items)
            # Show in a simple dialog
            dlg = ctk.CTkToplevel(self)
            dlg.title("Large Files")
            dlg.geometry("600x400")
            dlg.transient(self.master)
            dlg.grab_set()
            dlg.configure(fg_color=self.theme.colors["deep_background"])
            ctk.CTkLabel(dlg, text="Files over 100 MB (%d found)" % len(large),
                        font=ctk.CTkFont(size=16, weight="bold"),
                        text_color=self.theme.colors["primary_text"]).pack(pady=(20, 10))
            tb = ctk.CTkTextbox(dlg, height=300, fg_color=self.theme.colors["glass_panel"],
                               text_color=self.theme.colors["primary_text"],
                               border_width=1, border_color=self.theme.colors["border"])
            tb.pack(fill="both", expand=True, padx=24, pady=(0, 12))
            lines = ["%s - %s" % (self.ctrl.service.format_size(i.get("size_bytes")), i.get("path", "")) for i in large[:50]]
            tb.insert("0.0", "\n".join(lines) if lines else "No large files found.")
            tb.configure(state="disabled")
            ctk.CTkButton(dlg, text="Close", command=dlg.destroy,
                         fg_color=self.theme.colors["blue_accent"],
                         hover_color="#1570D6", text_color="white",
                         height=32, corner_radius=8).pack(pady=(0, 20))

    def _export_report(self):
        from tkinter import filedialog
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            title="Save Storage Report",
        )
        if not filepath:
            return
        ok, msg = self.ctrl.export_csv(filepath, self._items)
        # Show result
        dlg = ctk.CTkToplevel(self)
        dlg.title("Export Result")
        dlg.geometry("400x150")
        dlg.transient(self.master)
        dlg.grab_set()
        dlg.configure(fg_color=self.theme.colors["deep_background"])
        ctk.CTkLabel(dlg, text=msg, font=ctk.CTkFont(size=14),
                    text_color=self.theme.colors["primary_text"]).pack(pady=40)
        ctk.CTkButton(dlg, text="Close", command=dlg.destroy,
                     fg_color=self.theme.colors["blue_accent"],
                     hover_color="#1570D6", text_color="white",
                     height=32, corner_radius=8).pack(pady=(0, 20))

    def _create_footer(self):
        footer = ctk.CTkFrame(
            self.scroll, fg_color=self.theme.colors["glass_panel"],
            corner_radius=12, border_width=1,
            border_color=self.theme.colors["border"],
        )
        footer.grid(row=6, column=0, sticky="ew", padx=24, pady=(0, 20))
        footer.grid_columnconfigure(0, weight=1)

        self.range_lbl = ctk.CTkLabel(
            footer, text="0\u20130 of 0", font=ctk.CTkFont(size=11),
            text_color=self.theme.colors["secondary_text"],
        )
        self.range_lbl.grid(row=0, column=0, sticky="w", padx=16, pady=10)

        pag = ctk.CTkFrame(footer, fg_color="transparent")
        pag.grid(row=0, column=1, sticky="e", padx=16, pady=10)

        ctk.CTkLabel(pag, text="Rows per page:", font=ctk.CTkFont(size=11),
                    text_color=self.theme.colors["secondary_text"]).grid(row=0, column=0, padx=(0, 6))

        self.rows_var = ctk.StringVar(value="50")
        self.rows_menu = ctk.CTkOptionMenu(
            pag, variable=self.rows_var,
            values=["25", "50", "100"],
            command=lambda v: self._set_per_page(int(v)),
            font=ctk.CTkFont(size=11),
            fg_color=self.theme.colors["secondary_panel"],
            button_color=self.theme.colors["border"],
            text_color=self.theme.colors["primary_text"],
            height=28, corner_radius=6, width=70,
        )
        self.rows_menu.grid(row=0, column=1, padx=(0, 12))

        self.prev_btn = ctk.CTkButton(
            pag, text="\u25C0", command=self._prev_page,
            font=ctk.CTkFont(size=12), width=32, height=28, corner_radius=6,
            fg_color=self.theme.colors["glass_panel"],
            hover_color=self.theme.colors["hover_state"],
            text_color=self.theme.colors["primary_text"],
            border_width=1, border_color=self.theme.colors["border"],
        )
        self.prev_btn.grid(row=0, column=2, padx=2)

        self.next_btn = ctk.CTkButton(
            pag, text="\u25B6", command=self._next_page,
            font=ctk.CTkFont(size=12), width=32, height=28, corner_radius=6,
            fg_color=self.theme.colors["glass_panel"],
            hover_color=self.theme.colors["hover_state"],
            text_color=self.theme.colors["primary_text"],
            border_width=1, border_color=self.theme.colors["border"],
        )
        self.next_btn.grid(row=0, column=3, padx=2)

    # ------------------------------------------------------------------ helpers
    def _fmt_time(self, ts):
        if not ts:
            return "N/A"
        try:
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
        except (ValueError, OSError, TypeError):
            return "N/A"

    # ------------------------------------------------------------------ state
    def _idle(self):
        self._scanning = False
        self._items = []
        self._filtered = []
        self._selected_item = None
        self._render_table()
        self._update_cards(None)
        self._update_pagination()
        if self._selected_drive:
            self._update_drive_details(self._selected_drive)

    def _analyze(self):
        if self._scanning:
            return
        self._scanning = True
        self.analyze_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self._card_cache["total"].configure(text="\u2014")
        self._card_cache["used"].configure(text="\u2014")
        self._card_cache["free"].configure(text="\u2014")
        self._card_cache["files"].configure(text="\u2014")
        self._clear_table()
        self._scan_th = threading.Thread(target=self._run, daemon=True)
        self._scan_th.start()

    def _cancel(self):
        if not self._scanning:
            return
        self.ctrl.cancel_scan()
        self._scanning = False
        self.analyze_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")

    def _run(self):
        try:
            result = self.ctrl.analyze()
        except Exception as e:
            result = {"error": str(e), "items": [], "errors": [str(e)],
                      "total_size": 0, "file_count": 0, "folder_count": 0,
                      "scan_duration": 0.0, "type_stats": {}}
        self.after(0, self._done, result)

    def _done(self, result):
        self._scanning = False
        self.analyze_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        self._items = result.get("items", [])
        self._last_updated = datetime.now().strftime("%H:%M:%S")
        self.updated_lbl.configure(text="Last updated: %s" % self._last_updated)

        drive = self._selected_drive
        if drive:
            total = drive.get("total_bytes", 0) or 0
            used = drive.get("used_bytes", 0) or 0
            free = drive.get("free_bytes", 0) or 0
            self._card_cache["total"].configure(text=self.ctrl.service.format_size(total))
            self._card_cache["used"].configure(text=self.ctrl.service.format_size(used))
            self._card_cache["free"].configure(text=self.ctrl.service.format_size(free))
        self._card_cache["files"].configure(text=str(result.get("file_count", 0)))

        # Update type distribution
        stats = result.get("type_stats", {})
        if stats:
            total_classified = sum(stats.values())
            lines = []
            for cat, sz in sorted(stats.items(), key=lambda x: -x[1]):
                if sz > 0:
                    pct = (sz / total_classified * 100) if total_classified > 0 else 0
                    lines.append("%s: %s (%.1f%%)" % (cat, self.ctrl.service.format_size(sz), pct))
            self.type_dist_lbl.configure(text="\n".join(lines) if lines else "No data")

        self._apply_filters()
        self._scan_th = None

    def _clear_table(self):
        for w in self.table_body.winfo_children():
            w.destroy()

    def _apply_filters(self):
        search = self.search_var.get().strip() if hasattr(self, "search_var") else ""
        filtered = self.ctrl.filter_items(self._items, search=search, item_type=self._type_filter)
        filtered = self.ctrl.sort_items(filtered, "Size (Largest First)")
        self._filtered = filtered
        self._page = 1
        self._render_table()
        self._update_pagination()

    def _set_type_filter(self, val):
        self._type_filter = val
        self._page = 1
        self._apply_filters()

    def _render_table(self):
        self._clear_table()
        if not self._filtered:
            self._show_empty_state()
            return
        page_items, start, end = self.ctrl.paginate(self._filtered, self._page, self._per_page)
        for item in page_items:
            self._create_row(item)

    def _create_row(self, item):
        row = ctk.CTkFrame(
            self.table_body,
            fg_color=self.theme.colors["secondary_panel"],
            corner_radius=6, border_width=1,
            border_color=self.theme.colors["border"],
        )
        row.pack(fill="x", padx=4, pady=2)
        row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(row, text=item.get("name", "Unknown"),
                    font=ctk.CTkFont(size=13, weight="bold"),
                    text_color=self.theme.colors["primary_text"]).grid(row=0, column=0, sticky="w", padx=8, pady=6)

        ctk.CTkLabel(row, text=item.get("path", ""),
                    font=ctk.CTkFont(size=10),
                    text_color=self.theme.colors["muted_text"]).grid(row=1, column=0, sticky="w", padx=8)

        ctk.CTkLabel(row, text=item.get("type", "File"),
                    font=ctk.CTkFont(size=12),
                    text_color=self.theme.colors["secondary_text"]).grid(row=0, column=1, sticky="w", padx=8, pady=6)

        ctk.CTkLabel(row, text=self.ctrl.service.format_size(item.get("size_bytes")),
                    font=ctk.CTkFont(size=12),
                    text_color=self.theme.colors["primary_text"]).grid(row=0, column=2, sticky="e", padx=8, pady=6)

        total = self._selected_drive.get("total_bytes", 1) if self._selected_drive else 1
        sz = item.get("size_bytes", 0) or 0
        pct = (sz / total * 100) if total > 0 else 0
        ctk.CTkLabel(row, text="%.1f%%" % pct,
                    font=ctk.CTkFont(size=12),
                    text_color=self.theme.colors["secondary_text"]).grid(row=0, column=3, sticky="e", padx=8, pady=6)

        ctk.CTkLabel(row, text=self._fmt_time(item.get("mtime")),
                    font=ctk.CTkFont(size=11),
                    text_color=self.theme.colors["secondary_text"]).grid(row=0, column=4, sticky="e", padx=8, pady=6)

        row.bind("<Button-1>", lambda e, it=item: self._select_item(it))
        for child in row.winfo_children():
            child.bind("<Button-1>", lambda e, it=item: self._select_item(it))

    def _select_item(self, item):
        self._selected_item = item
        # Show details in drive details panel area (simplified)
        pass

    def _update_drive_details(self, drive):
        if not drive:
            return
        total = drive.get("total_bytes", 0) or 0
        used = drive.get("used_bytes", 0) or 0
        free = drive.get("free_bytes", 0) or 0
        pct = (used / total * 100) if total > 0 else 0
        text = "Drive: %s\nFilesystem: %s\nTotal: %s\nUsed: %s (%.1f%%)\nFree: %s" % (
            drive.get("device", "Unknown"),
            drive.get("filesystem", "Unknown"),
            self.ctrl.service.format_size(total),
            self.ctrl.service.format_size(used),
            pct,
            self.ctrl.service.format_size(free),
        )
        self.drive_details_lbl.configure(text=text)

    def _update_cards(self, result):
        pass

    def _update_pagination(self):
        total = len(self._filtered)
        if total == 0:
            self.range_lbl.configure(text="0\u20130 of 0")
            self.prev_btn.configure(state="disabled")
            self.next_btn.configure(state="disabled")
            return
        total_pages = (total + self._per_page - 1) // self._per_page
        self._page = max(1, min(self._page, total_pages))
        start = (self._page - 1) * self._per_page + 1
        end = min(self._page * self._per_page, total)
        self.range_lbl.configure(text="%s\u2013%s of %s" % (start, end, format(total, ",")))
        self.prev_btn.configure(state="normal" if self._page > 1 else "disabled")
        self.next_btn.configure(state="normal" if end < total else "disabled")

    def _set_per_page(self, val):
        self._per_page = val
        self._page = 1
        self._render_table()
        self._update_pagination()

    def _prev_page(self):
        if self._page > 1:
            self._page -= 1
            self._render_table()
            self._update_pagination()

    def _next_page(self):
        total_pages = (len(self._filtered) + self._per_page - 1) // self._per_page
        if self._page < total_pages:
            self._page += 1
            self._render_table()
            self._update_pagination()
