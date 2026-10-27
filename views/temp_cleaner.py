"""Temp Cleaner view for PC-Toolbox - full implementation per spec."""

import customtkinter as ctk
import threading
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

import sys
sys.path.insert(0, 'd:/Windows app/PC-Toolbox')


class TempCleanerView(ctk.CTkFrame):
    """Temp Cleaner screen with scan, cancel, filters, table, pagination, and details."""

    CATEGORIES = ["All Files", "Windows", "Applications", "Browser", "Caches", "Logs"]

    def __init__(self, master, navigation):
        super().__init__(master, fg_color=master.theme.colors["deep_background"])
        self.theme = master.theme
        self.navigation = navigation

        self.act = getattr(navigation, "activity_service", None)
        self.ctrl = getattr(navigation, "temp_cleaner_controller", None)
        if not self.act or not self.ctrl:
            from services.activity_service import ActivityService
            from controllers.temp_cleaner_controller import TempCleanerController
            self.act = self.act or ActivityService()
            self.excl = getattr(navigation, "exclusion_service", None)
            self.ctrl = self.ctrl or TempCleanerController(self.act, exclusion_service=self.excl)

        # State
        self._scanning = False
        self._scan_th = None
        self._user_cancel = False
        self._rows = []
        self._pending_callbacks = []
        self._last_result = None
        self._all_files = []
        self._filtered_files = []
        self._selected_paths = set()
        self._current_category = "All Files"
        self._search_text = ""
        self._location_filter = "All Locations"
        self._current_page = 1
        self._rows_per_page = 25
        self._scan_start_time = None
        self._scan_duration = 0.0

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._setup_ui()
        self._idle()

    # ------------------------------------------------------------------ setup
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
        self._create_controls()
        self._create_summary_cards()
        self._create_filter_bar()
        self._create_table_panel()
        self._create_footer()

    def _create_header(self):
        header = ctk.CTkFrame(self.scroll, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 16))
        header.grid_columnconfigure(1, weight=1)

        left = ctk.CTkFrame(header, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w")
        left.grid_columnconfigure(1, weight=1)

        icon_lbl = ctk.CTkLabel(
            left, text="\U0001F5D1", font=ctk.CTkFont(size=30),
            text_color=self.theme.colors["blue_accent"],
        )
        icon_lbl.grid(row=0, column=0, sticky="w", padx=(0, 12))

        title_lbl = ctk.CTkLabel(
            left, text="Temp Cleaner", font=ctk.CTkFont(size=28, weight="bold"),
            text_color=self.theme.colors["primary_text"],
        )
        title_lbl.grid(row=0, column=1, sticky="w")

        subtitle_lbl = ctk.CTkLabel(
            left, text="Find and manage temporary files to free up disk space",
            font=ctk.CTkFont(size=13),
            text_color=self.theme.colors["secondary_text"],
        )
        subtitle_lbl.grid(row=1, column=1, sticky="w", pady=(2, 0))

        right = ctk.CTkFrame(header, fg_color="transparent")
        right.grid(row=0, column=1, sticky="e")

        self.view_logs_btn = ctk.CTkButton(
            right, text="View All Logs", command=lambda: self.navigation.navigate_to("logs"),
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=self.theme.colors["glass_panel"],
            hover_color=self.theme.colors["hover_state"],
            text_color=self.theme.colors["primary_text"],
            height=34, width=130, corner_radius=8,
            border_width=1, border_color=self.theme.colors["border"],
        )
        self.view_logs_btn.grid(row=0, column=0, sticky="e")

    def _create_controls(self):
        row = ctk.CTkFrame(self.scroll, fg_color="transparent")
        row.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 16))
        row.grid_columnconfigure(0, weight=1)
        row.grid_columnconfigure(1, weight=1)
        row.grid_columnconfigure(2, weight=0)

        # Scan button
        self.scan_b = ctk.CTkButton(
            row, text="Scan for Temporary Files",
            command=self._scan,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=self.theme.colors["blue_accent"],
            hover_color="#1570D6", text_color="white",
            height=52, corner_radius=10,
        )
        self.scan_b.grid(row=0, column=0, padx=(0, 8), sticky="ew")

        scan_sub = ctk.CTkLabel(
            row, text="Find junk files in system and apps",
            font=ctk.CTkFont(size=11),
            text_color=self.theme.colors["secondary_text"],
        )
        scan_sub.grid(row=1, column=0, padx=(0, 8), sticky="w")

        # Cancel button
        self.can_b = ctk.CTkButton(
            row, text="Cancel Scan",
            command=self._cancel,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=self.theme.colors["red_accent"],
            hover_color="#D06565", text_color="white",
            height=52, corner_radius=10,
            state="disabled",
        )
        self.can_b.grid(row=0, column=1, padx=8, sticky="ew")

        cancel_sub = ctk.CTkLabel(
            row, text="Stop current scan",
            font=ctk.CTkFont(size=11),
            text_color=self.theme.colors["secondary_text"],
        )
        cancel_sub.grid(row=1, column=1, padx=8, sticky="w")

        # Settings button
        settings_frame = ctk.CTkFrame(
            row, fg_color=self.theme.colors["glass_panel"],
            corner_radius=10, border_width=1,
            border_color=self.theme.colors["border"],
        )
        settings_frame.grid(row=0, column=2, rowspan=2, padx=(8, 0), sticky="nsew")

        self.settings_btn = ctk.CTkButton(
            settings_frame, text="\u2699  Scan Settings",
            command=self._open_settings,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="transparent",
            hover_color=self.theme.colors["hover_state"],
            text_color=self.theme.colors["primary_text"],
            height=52, corner_radius=8,
        )
        self.settings_btn.grid(row=0, column=0, padx=12, pady=8, sticky="ew")

        settings_sub = ctk.CTkLabel(
            settings_frame, text="Select locations and file types",
            font=ctk.CTkFont(size=11),
            text_color=self.theme.colors["secondary_text"],
        )
        settings_sub.grid(row=1, column=0, padx=12, pady=(0, 8), sticky="w")

    def _create_summary_cards(self):
        cards = ctk.CTkFrame(self.scroll, fg_color="transparent")
        cards.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 16))
        for i in range(4):
            cards.grid_columnconfigure(i, weight=1)

        card_defs = [
            ("\U0001F4C4", "Files Found", "files_found", self.theme.colors["blue_accent"]),
            ("\U0001F4BE", "Total Size", "total_size", self.theme.colors["purple_accent"]),
            ("\U0001F4C1", "Locations Scanned", "locations_scanned", self.theme.colors["cyan_accent"]),
            ("\u23F1", "Scan Time", "scan_time", self.theme.colors["green_accent"]),
        ]
        self._card_cache = {}
        for i, (icon, title, key, accent) in enumerate(card_defs):
            card = ctk.CTkFrame(
                cards, fg_color=self.theme.colors["glass_panel"],
                corner_radius=12, border_width=1,
                border_color=self.theme.colors["border"],
            )
            card.grid(row=0, column=i, sticky="nsew", padx=6, pady=0)

            icon_lbl = ctk.CTkLabel(card, text=icon, font=ctk.CTkFont(size=20), text_color=accent)
            icon_lbl.grid(row=0, column=0, sticky="w", padx=16, pady=(14, 0))

            val_lbl = ctk.CTkLabel(
                card, text="\u2014", font=ctk.CTkFont(size=26, weight="bold"),
                text_color=self.theme.colors["primary_text"],
            )
            val_lbl.grid(row=1, column=0, sticky="w", padx=16, pady=(4, 0))

            title_lbl = ctk.CTkLabel(
                card, text=title, font=ctk.CTkFont(size=11),
                text_color=self.theme.colors["secondary_text"],
            )
            title_lbl.grid(row=2, column=0, sticky="w", padx=16, pady=(0, 14))

            self._card_cache[key] = val_lbl

    def _create_filter_bar(self):
        bar = ctk.CTkFrame(self.scroll, fg_color="transparent")
        bar.grid(row=3, column=0, sticky="ew", padx=24, pady=(0, 16))
        bar.grid_columnconfigure(0, weight=1)

        self._filter_buttons = {}
        for i, cat in enumerate(self.CATEGORIES):
            btn = ctk.CTkButton(
                bar, text=cat, command=lambda c=cat: self._set_category(c),
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color=self.theme.colors["glass_panel"],
                hover_color=self.theme.colors["hover_state"],
                text_color=self.theme.colors["secondary_text"],
                height=30, corner_radius=8,
                border_width=1, border_color=self.theme.colors["border"],
            )
            btn.grid(row=0, column=i, padx=4, sticky="w")
            self._filter_buttons[cat] = btn
        self._rec_filter = "All"
        rec_frame = ctk.CTkFrame(bar, fg_color="transparent")
        rec_frame.grid(row=0, column=len(self.CATEGORIES), padx=12, sticky="w")
        ctk.CTkLabel(rec_frame, text="Recommendation:", font=ctk.CTkFont(size=11), text_color=self.theme.colors["secondary_text"]).pack(side="left")
        self.rec_var = ctk.StringVar(value="All")
        ctk.CTkOptionMenu(rec_frame, values=["All", "Candidate", "Review", "Do not clean", "Unknown"], variable=self.rec_var, command=self._set_rec_filter).pack(side="left", padx=4)

    def _create_table_panel(self):
        panel = ctk.CTkFrame(
            self.scroll, fg_color=self.theme.colors["glass_panel"],
            corner_radius=14, border_width=1,
            border_color=self.theme.colors["border"],
        )
        panel.grid(row=4, column=0, sticky="nsew", padx=24, pady=(0, 16))
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(2, weight=1)

        # Panel header
        ph = ctk.CTkFrame(panel, fg_color="transparent")
        ph.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 10))
        ph.grid_columnconfigure(0, weight=1)

        self.table_title = ctk.CTkLabel(
            ph, text="Temporary Files (0)",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=self.theme.colors["primary_text"],
        )
        self.table_title.grid(row=0, column=0, sticky="w")

        self.table_subtitle = ctk.CTkLabel(
            ph, text="Review the files found. No files will be deleted until you confirm.",
            font=ctk.CTkFont(size=11),
            text_color=self.theme.colors["secondary_text"],
        )
        self.table_subtitle.grid(row=1, column=0, sticky="w", pady=(2, 0))

        # Search + location filter
        controls = ctk.CTkFrame(ph, fg_color="transparent")
        controls.grid(row=0, column=1, rowspan=2, sticky="e")

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *a: self._apply_filters())
        search_entry = ctk.CTkEntry(
            controls, textvariable=self.search_var,
            placeholder_text="Search files...",
            font=ctk.CTkFont(size=12),
            fg_color=self.theme.colors["secondary_panel"],
            border_width=1, border_color=self.theme.colors["border"],
            text_color=self.theme.colors["primary_text"],
            height=32, width=200, corner_radius=8,
        )
        search_entry.grid(row=0, column=0, padx=(0, 8))

        self.location_var = ctk.StringVar(value="All Locations")
        self.location_dropdown = ctk.CTkOptionMenu(
            controls,
            variable=self.location_var,
            values=["All Locations"],
            command=lambda v: self._set_location_filter(v),
            font=ctk.CTkFont(size=12),
            fg_color=self.theme.colors["secondary_panel"],
            button_color=self.theme.colors["border"],
            text_color=self.theme.colors["primary_text"],
            height=32, corner_radius=8,
        )
        self.location_dropdown.grid(row=0, column=1)

        # Status label
        self.status_lbl = ctk.CTkLabel(
            panel, text="Ready to scan",
            font=ctk.CTkFont(size=12),
            text_color=self.theme.colors["secondary_text"],
        )
        self.status_lbl.grid(row=1, column=0, sticky="w", padx=20, pady=(0, 8))

        # Table body
        self.table_body = ctk.CTkScrollableFrame(
            panel, fg_color=self.theme.colors["secondary_panel"],
            corner_radius=8,
        )
        self.table_body.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 12))
        self.table_body.grid_columnconfigure(0, weight=1)

        self._empty_state_label = None
        self._show_empty_state()

    def _show_empty_state(self):
        for w in self.table_body.winfo_children():
            w.destroy()
        self._empty_state_label = ctk.CTkLabel(
            self.table_body,
            text="Ready to scan\n\nScan approved temporary locations to find reclaimable files.",
            font=ctk.CTkFont(size=14),
            text_color=self.theme.colors["muted_text"],
            justify="center",
        )
        self._empty_state_label.pack(pady=40)

    def _create_footer(self):
        footer = ctk.CTkFrame(
            self.scroll, fg_color=self.theme.colors["glass_panel"],
            corner_radius=12, border_width=1,
            border_color=self.theme.colors["border"],
        )
        footer.grid(row=5, column=0, sticky="ew", padx=24, pady=(0, 20))
        footer.grid_columnconfigure(0, weight=1)
        footer.grid_columnconfigure(1, weight=0)

        # Left: selection summary
        self.selection_lbl = ctk.CTkLabel(
            footer, text="0 files selected | 0 B",
            font=ctk.CTkFont(size=12),
            text_color=self.theme.colors["primary_text"],
        )
        self.selection_lbl.grid(row=0, column=0, sticky="w", padx=16, pady=10)

        # Right: pagination
        pag = ctk.CTkFrame(footer, fg_color="transparent")
        pag.grid(row=0, column=1, sticky="e", padx=16, pady=10)

        ctk.CTkLabel(
            pag, text="Rows per page:", font=ctk.CTkFont(size=11),
            text_color=self.theme.colors["secondary_text"],
        ).grid(row=0, column=0, padx=(0, 6))

        self.rows_var = ctk.StringVar(value="25")
        self.rows_menu = ctk.CTkOptionMenu(
            pag, variable=self.rows_var,
            values=["25", "50", "100"],
            command=lambda v: self._set_rows_per_page(int(v)),
            font=ctk.CTkFont(size=11),
            fg_color=self.theme.colors["secondary_panel"],
            button_color=self.theme.colors["border"],
            text_color=self.theme.colors["primary_text"],
            height=28, corner_radius=6, width=70,
        )
        self.rows_menu.grid(row=0, column=1, padx=(0, 12))

        self.range_lbl = ctk.CTkLabel(
            pag, text="0\u20130 of 0",
            font=ctk.CTkFont(size=11),
            text_color=self.theme.colors["secondary_text"],
        )
        self.range_lbl.grid(row=0, column=2, padx=(0, 12))

        self.prev_btn = ctk.CTkButton(
            pag, text="\u25C0", command=self._prev_page,
            font=ctk.CTkFont(size=12), width=32, height=28, corner_radius=6,
            fg_color=self.theme.colors["glass_panel"],
            hover_color=self.theme.colors["hover_state"],
            text_color=self.theme.colors["primary_text"],
            border_width=1, border_color=self.theme.colors["border"],
        )
        self.prev_btn.grid(row=0, column=3, padx=2)

        self.next_btn = ctk.CTkButton(
            pag, text="\u25B6", command=self._next_page,
            font=ctk.CTkFont(size=12), width=32, height=28, corner_radius=6,
            fg_color=self.theme.colors["glass_panel"],
            hover_color=self.theme.colors["hover_state"],
            text_color=self.theme.colors["primary_text"],
            border_width=1, border_color=self.theme.colors["border"],
        )
        # Clean button
        self.clean_b = ctk.CTkButton(
            footer, text="Clean Selected", command=self._clean,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=self.theme.colors["glass_panel"],
            hover_color=self.theme.colors["hover_state"],
            text_color=self.theme.colors["primary_text"],
            height=32, corner_radius=8,
            border_width=1, border_color=self.theme.colors["border"],
        )
        self.clean_b.grid(row=0, column=2, sticky="e", padx=(0, 16), pady=10)

    # ------------------------------------------------------------------ helpers
    def _fmt_size(self, b):
        if b is None or b < 0:
            return "0 B"
        units = ["B", "KB", "MB", "GB", "TB", "PB"]
        s = float(b)
        i = 0
        while s >= 1024.0 and i < len(units) - 1:
            s /= 1024.0
            i += 1
        return "%s %s" % ("%.1f" % s, units[i])

    def _fmt_time(self, seconds):
        if seconds is None or seconds < 0:
            return "\u2014"
        seconds = int(seconds)
        if seconds < 60:
            return "%ds" % seconds
        if seconds < 3600:
            m = seconds // 60
            s = seconds % 60
            return "%dm %ds" % (m, s)
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return "%dh %dm" % (h, m)

    def _fmt_timestamp(self, ts):
        if not ts:
            return "N/A"
        try:
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
        except (ValueError, OSError, TypeError):
            return "N/A"

    def _set_category(self, cat):
        self._current_category = cat
        self._current_page = 1
        for c, btn in self._filter_buttons.items():
            if c == cat:
                btn.configure(
                    fg_color=self.theme.colors["blue_accent"],
                    text_color="white",
                )
            else:
                btn.configure(
                    fg_color=self.theme.colors["glass_panel"],
                    text_color=self.theme.colors["secondary_text"],
                )
        self._apply_filters()

    def _set_rec_filter(self, val):
        self._rec_filter = val
        self._current_page = 1
        self._apply_filters()

    def _set_rows_per_page(self, val):
        self._rows_per_page = val
        self._current_page = 1
        self._render_page()

    def _cancel_pending(self):
        for cb_id in self._pending_callbacks:
            try:
                self.after_cancel(cb_id)
            except Exception:
                pass
        self._pending_callbacks.clear()

    # ------------------------------------------------------------------ state
    def _idle(self):
        self._scanning = False
        self._user_cancel = False
        self.scan_b.configure(state="normal")
        self.can_b.configure(state="disabled")
        self.status_lbl.configure(text="Ready to scan", text_color=self.theme.colors["secondary_text"])
        self._card_cache["files_found"].configure(text="\u2014")
        self._card_cache["total_size"].configure(text="\u2014")
        self._card_cache["locations_scanned"].configure(text="\u2014")
        self._card_cache["scan_time"].configure(text="\u2014")
        self._empty_state_label = None
        self._show_empty_state()
        self._all_files = []
        self._filtered_files = []
        self._selected_paths.clear()
        self._update_selection_summary()
        self._update_pagination()

    def _scan_st(self):
        self._scanning = True
        self._user_cancel = False
        self.scan_b.configure(state="disabled")
        self.can_b.configure(state="normal")
        self.status_lbl.configure(text="Scanning temporary files...", text_color=self.theme.colors["blue_accent"])
        self._card_cache["files_found"].configure(text="0")
        self._card_cache["total_size"].configure(text="0 B")
        self._card_cache["locations_scanned"].configure(text="0")
        self._card_cache["scan_time"].configure(text="0s")
        self._cancel_pending()
        self._clear_table()
        self._scan_start_time = time.monotonic()

    def _done(self, r):
        self._comp_st(r)
        self._update_preview_summary(r)
        self._scan_th = None

    def _update_preview_summary(self, r):
        files = r.get('files', [])
        cand = 0; cand_s = 0
        rev = 0; rev_s = 0
        blk = 0; blk_s = 0
        unk = 0; unk_s = 0
        for f in files:
            intel = f.get('intel') or {}
            rec = intel.get('recommendation') or {}
            st = rec.get('status', 'Unknown')
            sz = f.get('size', 0)
            if st == 'Candidate':
                cand += 1; cand_s += sz
            elif st == 'Review':
                rev += 1; rev_s += sz
            elif st == 'Do not clean':
                blk += 1; blk_s += sz
            else:
                unk += 1; unk_s += sz
        self.status_lbl.configure(text="Preview: Candidate %d (%s) | Review %d (%s) | Blocked %d (%s) | Unknown %d (%s)" % (cand, self._fmt_size(cand_s), rev, self._fmt_size(rev_s), blk, self._fmt_size(blk_s), unk, self._fmt_size(unk_s)))

        fc = res.get("file_count", 0)
        ts = res.get("total_size", 0)
        ls = res.get("locations_scanned", 0)
        dur = res.get("scan_duration", 0.0)

        self._card_cache["files_found"].configure(text="%s" % format(fc, ","))
        self._card_cache["total_size"].configure(text=self._fmt_size(ts))
        self._card_cache["locations_scanned"].configure(text="%s" % ls)
        self._card_cache["scan_time"].configure(text=self._fmt_time(dur))

        if res.get("error"):
            self.status_lbl.configure(text="Scan failed", text_color=self.theme.colors["red_accent"])
        elif self._user_cancel:
            self.status_lbl.configure(text="Scan cancelled", text_color=self.theme.colors["orange_accent"])
        elif res.get("skipped") and not res.get("errors"):
            self.status_lbl.configure(text="Completed with issues", text_color=self.theme.colors["orange_accent"])
        elif res.get("errors"):
            self.status_lbl.configure(text="Completed with issues", text_color=self.theme.colors["orange_accent"])
        else:
            self.status_lbl.configure(text="Completed", text_color=self.theme.colors["green_accent"])

        self._all_files = res.get("files", [])
        self._apply_filters()

        errors = res.get("errors", [])
        skipped = res.get("skipped", [])
        if errors or skipped:
            self._show_details_button = True
        else:
            self._show_details_button = False

    def _can_st(self):
        self._scanning = False
        self._user_cancel = True
        self.scan_b.configure(state="normal")
        self.can_b.configure(state="disabled")
        self.status_lbl.configure(text="Scan cancelled", text_color=self.theme.colors["orange_accent"])

    def _clear_table(self):
        self._cancel_pending()
        for w in self.table_body.winfo_children():
            w.destroy()

    def _show_empty_state(self):
        self._clear_table()
        lbl = ctk.CTkLabel(
            self.table_body,
            text="Ready to scan\n\nScan approved temporary locations to find reclaimable files.",
            font=ctk.CTkFont(size=14),
            text_color=self.theme.colors["muted_text"],
            justify="center",
        )
        lbl.pack(pady=40)

    def _show_no_results_state(self):
        self._clear_table()
        lbl = ctk.CTkLabel(
            self.table_body,
            text="No temporary files found\n\nNo eligible files were found in the selected locations.",
            font=ctk.CTkFont(size=14),
            text_color=self.theme.colors["muted_text"],
            justify="center",
        )
        lbl.pack(pady=40)

    # ------------------------------------------------------------------ filters
    def _apply_filters(self):
        if not self._all_files:
            self._filtered_files = []
            if not self._scanning:
                self._show_empty_state()
            self._update_table_title()
            self._update_pagination()
            return

        filtered = list(self._all_files)

        # Category filter
        if self._current_category != "All Files":
            filtered = [f for f in filtered if f.get("category") == self._current_category]

        # Location filter
        if self._location_filter != "All Locations":
            filtered = [f for f in filtered if f.get("root") == self._location_filter]

        # Recommendation filter
        if getattr(self, '_rec_filter', 'All') != 'All':
            rec = self._rec_filter
            filtered = [f for f in filtered if (f.get('intel') or {}).get('recommendation', {}).get('status') == rec]

        self._filtered_files = filtered
        self._current_page = 1
        self._update_table_title()
        self._update_location_dropdown()
        self._render_page()
        self._update_pagination()

    def _update_table_title(self):
        count = len(self._filtered_files)
        self.table_title.configure(text="Temporary Files (%s)" % format(count, ","))

    def _update_location_dropdown(self):
        roots = sorted(set(f.get("root", "") for f in self._all_files if f.get("root")))
        values = ["All Locations"] + roots
        self.location_dropdown.configure(values=values)
        if self.location_var.get() not in values:
            self.location_var.set("All Locations")
            self._location_filter = "All Locations"

    # ------------------------------------------------------------------ pagination
    def _render_page(self):
        self._cancel_pending()
        for w in self.table_body.winfo_children():
            w.destroy()

        if not self._filtered_files:
            if self._all_files:
                self._show_no_results_state()
            else:
                self._show_empty_state()
            return

        start = (self._current_page - 1) * self._rows_per_page
        end = min(start + self._rows_per_page, len(self._filtered_files))
        page_files = self._filtered_files[start:end]

        for i, f in enumerate(page_files):
            self._create_row(f, i)

        self._update_pagination()

    def _create_row(self, f, index):
        row = ctk.CTkFrame(
            self.table_body,
            fg_color=self.theme.colors["secondary_panel"] if index % 2 == 0 else self.theme.colors["glass_panel"],
            corner_radius=6,
            border_width=1,
            border_color=self.theme.colors["border"],
        )
        row.pack(fill="x", padx=4, pady=2)
        row.grid_columnconfigure(1, weight=1)

        # Checkbox
        var = ctk.BooleanVar(value=f.get("path") in self._selected_paths)
        cb = ctk.CTkCheckBox(
            row, text="", variable=var, width=20, height=20,
            command=lambda p=f.get("path"): self._toggle_selection(p, var.get()),
            fg_color=self.theme.colors["blue_accent"],
            hover_color=self.theme.colors["hover_state"],
            border_color=self.theme.colors["border"],
        )
        cb.grid(row=0, column=0, sticky="w", padx=(8, 4), pady=6)

        # File name / path
        name_frame = ctk.CTkFrame(row, fg_color="transparent")
        name_frame.grid(row=0, column=1, sticky="ew", padx=4, pady=6)
        name_frame.grid_columnconfigure(0, weight=1)

        name_lbl = ctk.CTkLabel(
            name_frame, text=f.get("path", "").split("\\")[-1],
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=self.theme.colors["primary_text"],
            anchor="w",
        )
        name_lbl.grid(row=0, column=0, sticky="w")

        path_lbl = ctk.CTkLabel(
            name_frame, text=f.get("path", ""),
            font=ctk.CTkFont(size=10),
            text_color=self.theme.colors["muted_text"],
            anchor="w",
        )
        path_lbl.grid(row=1, column=0, sticky="w")

        # Size
        size_lbl = ctk.CTkLabel(
            row, text=self._fmt_size(f.get("size", 0)),
            font=ctk.CTkFont(size=12),
            text_color=self.theme.colors["primary_text"],
        )
        size_lbl.grid(row=0, column=2, sticky="e", padx=8, pady=6)

        # Type badge
        cat = f.get("category", "Other")
        cat_colors = {
            "Cache": self.theme.colors["blue_accent"],
            "Browser": self.theme.colors["purple_accent"],
            "Log": self.theme.colors["orange_accent"],
            "Application": self.theme.colors["cyan_accent"],
            "Windows": self.theme.colors["green_accent"],
            "Other": self.theme.colors["muted_text"],
        }
        badge = ctk.CTkLabel(
            row, text=cat,
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="white",
            fg_color=cat_colors.get(cat, self.theme.colors["muted_text"]),
            corner_radius=4,
        )
        badge.grid(row=0, column=3, sticky="e", padx=8, pady=6)

        # Last modified
        mtime_lbl = ctk.CTkLabel(
            row, text=self._fmt_timestamp(f.get("mtime")),
            font=ctk.CTkFont(size=11),
            text_color=self.theme.colors["secondary_text"],
        )
        mtime_lbl.grid(row=0, column=4, sticky="e", padx=8, pady=6)

        # App / intelligence
        intel = f.get("intel") or {}
        app_lbl = ctk.CTkLabel(
            row, text=intel.get("likely_app", "Unknown"),
            font=ctk.CTkFont(size=11),
            text_color=self.theme.colors["primary_text"],
            width=120,
        )
        app_lbl.grid(row=0, column=6, sticky="e", padx=8, pady=6)

        usage_lbl = ctk.CTkLabel(
            row, text=intel.get("in_use", "Unknown"),
            font=ctk.CTkFont(size=11),
            text_color=self.theme.colors["secondary_text"],
            width=90,
        )
        usage_lbl.grid(row=0, column=7, sticky="e", padx=8, pady=6)

        rec_lbl = ctk.CTkLabel(
            row, text=intel.get("safety", "Review"),
            font=ctk.CTkFont(size=11),
            text_color=self.theme.colors["secondary_text"],
            width=80,
        )
        rec_lbl.grid(row=0, column=8, sticky="e", padx=8, pady=6)

        ctk.CTkButton(
            row, text="Details",
            width=60,
            height=24,
            font=ctk.CTkFont(size=10),
            command=lambda file=f: self._show_file_details(file),
        ).grid(row=0, column=8, sticky="e", padx=8, pady=6)

    def _toggle_selection(self, path, selected):
        if selected:
            self._selected_paths.add(path)
        else:
            self._selected_paths.discard(path)
        self._update_selection_summary()

    def _update_selection_summary(self):
        total = sum(
            f.get("size", 0) for f in self._all_files
            if f.get("path") in self._selected_paths
        )
        self.selection_lbl.configure(
            text="%s files selected | %s" % (len(self._selected_paths), self._fmt_size(total))
        )

    def _update_pagination(self):
        total = len(self._filtered_files)
        if total == 0:
            self.range_lbl.configure(text="0\u20130 of 0")
            self.prev_btn.configure(state="disabled")
            self.next_btn.configure(state="disabled")
            return
        start = (self._current_page - 1) * self._rows_per_page + 1
        end = min(self._current_page * self._rows_per_page, total)
        self.range_lbl.configure(text="%s\u2013%s of %s" % (start, end, format(total, ",")))
        self.prev_btn.configure(state="normal" if self._current_page > 1 else "disabled")
        self.next_btn.configure(state="normal" if end < total else "disabled")

    def _prev_page(self):
        if self._current_page > 1:
            self._current_page -= 1
            self._render_page()

    def _next_page(self):
        total_pages = (len(self._filtered_files) + self._rows_per_page - 1) // self._rows_per_page
        if self._current_page < total_pages:
            self._current_page += 1
            self._render_page()

    def _clean(self):
        # Only allow candidates
        cand = []
        for p in self._selected_paths:
            for f in self._all_files:
                if f.get('path') == p:
                    intel = f.get('intel') or {}
                    rec = intel.get('recommendation') or {}
                    if rec.get('status') == 'Candidate':
                        cand.append(f)
                    break
        if not cand:
            return
        import tkinter.messagebox as mb
        if not mb.askyesno("Confirm Cleanup", "Delete %d candidate files permanently?" % len(cand)):
            return
        excl = getattr(self.navigation, "exclusion_service", None)
        try:
            from services.file_usage_detector import FileUsageDetector
            ud = FileUsageDetector()
        except Exception:
            ud = None
        res = self.ctrl.cleanup(cand, exclusion_service=excl, usage_detector=ud)
        mb.showinfo("Cleanup", "Deleted %d files, %d bytes" % (res.get('deleted_count',0), res.get('deleted_bytes',0)))
        if self._scanning:
            return
        self._scan_st()
        self._scan_th = threading.Thread(target=self._run, daemon=True)
        self._scan_th.start()

    def _cancel(self):
        if not self._scanning:
            return
        self.ctrl.cancel_scan()
        self._can_st()

    def _run(self):
        try:
            r = self.ctrl.scan()
        except Exception as e:
            r = {
                "error": str(e), "files": [], "total_size": 0,
                "file_count": 0, "errors": [str(e)], "skipped": [],
                "locations_scanned": 0, "scan_duration": 0.0,
            }
        finally:
            self.after(0, self._done, r)

        self._comp_st(r)

    # ------------------------------------------------------------------ settings
    def _open_settings(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title("Scan Settings")
        dlg.geometry("500x400")
        dlg.transient(self.master)
        dlg.grab_set()
        dlg.configure(fg_color=self.theme.colors["deep_background"])

        ctk.CTkLabel(
            dlg, text="Scan Settings",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=self.theme.colors["primary_text"],
        ).pack(pady=(20, 10))

        ctk.CTkLabel(
            dlg, text="Session-only settings. Approved roots are controlled by the service.",
            font=ctk.CTkFont(size=11),
            text_color=self.theme.colors["secondary_text"],
        ).pack(pady=(0, 16))

        settings = self.ctrl.get_settings()
        toggles = {}
        for key, label in [
            ("include_browser_caches", "Include browser caches"),
            ("include_app_caches", "Include application caches"),
            ("include_log_files", "Include log files"),
            ("include_windows_temp", "Include Windows temp"),
        ]:
            var = ctk.BooleanVar(value=settings.get(key, True))
            cb = ctk.CTkCheckBox(
                dlg, text=label, variable=var,
                fg_color=self.theme.colors["blue_accent"],
                hover_color=self.theme.colors["hover_state"],
                text_color=self.theme.colors["primary_text"],
            )
            cb.pack(anchor="w", padx=24, pady=6)
            toggles[key] = var

        # Approved roots display
        ctk.CTkLabel(
            dlg, text="Approved roots (read-only):",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=self.theme.colors["primary_text"],
        ).pack(anchor="w", padx=24, pady=(12, 4))

        roots_text = ctk.CTkTextbox(
            dlg, height=80, fg_color=self.theme.colors["glass_panel"],
            text_color=self.theme.colors["secondary_text"],
            border_width=1, border_color=self.theme.colors["border"],
        )
        roots_text.pack(fill="x", padx=24, pady=(0, 12))
        roots_text.insert("0.0", "\n".join(self.ctrl.get_approved_roots()))
        roots_text.configure(state="disabled")

        btn_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_frame.pack(fill="x", padx=24, pady=12)

        def apply():
            new_settings = {k: v.get() for k, v in toggles.items()}
            self.ctrl.update_settings(new_settings)
            dlg.destroy()

        ctk.CTkButton(
            btn_frame, text="Cancel", command=dlg.destroy,
            fg_color="transparent", hover_color=self.theme.colors["hover_state"],
            text_color=self.theme.colors["secondary_text"],
            height=32, corner_radius=8,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_frame, text="Apply", command=apply,
            fg_color=self.theme.colors["blue_accent"], hover_color="#1570D6",
            text_color="white", height=32, corner_radius=8,
        ).pack(side="left")

    def _show_file_details(self, f):
        intel = f.get("intel") or {}
        popup = ctk.CTkToplevel(self)
        popup.title("File Details")
        popup.geometry("520x420")
        popup.transient(self.master)
        popup.grab_set()
        popup.configure(fg_color=self.theme.colors["deep_background"])
        box = ctk.CTkTextbox(
            popup, fg_color=self.theme.colors["glass_panel"],
            text_color=self.theme.colors["primary_text"],
            border_width=1, border_color=self.theme.colors["border"],
        )
        box.pack(fill="both", expand=True, padx=16, pady=16)
        lines = [
            "Path: %s" % f.get("path", ""),
            "Size: %s" % self._fmt_size(f.get("size", 0)),
            "Modified: %s" % self._fmt_timestamp(f.get("mtime")),
            "Category: %s" % f.get("category", ""),
            "Root: %s" % f.get("root", ""),
            "",
            "Intelligence (from temp_file_intelligence):",
            "Associated application: %s" % intel.get("likely_app", "Unknown"),
            "Identification method: %s" % intel.get("app_method", "none"),
            "Application running: %s" % intel.get("app_running", "Unknown"),
            "App running evidence: %s" % intel.get("app_running_evidence", ""),
            "Application installed: %s" % intel.get("app_installed", "Unknown"),
            "App installed evidence: %s" % intel.get("app_installed_evidence", ""),
            "Purpose: %s" % intel.get("purpose", "Unknown"),
            "Cleanup recommendation: %s" % (intel.get("recommendation") or {}).get("status", intel.get("safety", "Review")),
            "Recommendation reasons: %s" % (intel.get("recommendation") or {}).get("reasons", []),
            "Recommendation evidence: %s" % (intel.get("recommendation") or {}).get("evidence", []),
            "Confidence: %s" % intel.get("confidence", "Low"),
            "Explanation: %s" % intel.get("reason", ""),
            "File in use: %s" % intel.get("in_use", "Unknown"),
            "Usage processes: %s" % intel.get("usage_processes", []),
            "Usage error: %s" % intel.get("usage_error"),
            "Last checked: %s" % intel.get("usage_checked_at", "Never"),
            "",
            "Notes:",
            "Directory-based associations are inferred, not verified as creator.",
            "App running != file in use. 'No current use detected' does not mean safe to delete. Candidate = user-reviewed cleanup, not guaranteed safe.",
        ]
        box.insert("1.0", "\n".join(lines))
        box.configure(state="disabled")

        def check_usage():
            try:
                from services.temp_file_intelligence import classify
                from datetime import datetime
                res = classify(f.get("path"), check_usage=True)
                f["intel"] = res
                res["usage_checked_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.after(0, self._render_page)
                box.destroy()
                self._show_file_details(f)
            except Exception as e:
                pass

        btn_frame = ctk.CTkFrame(popup, fg_color="transparent")
        btn_frame.pack(fill="x", padx=16, pady=(0, 12))
        ctk.CTkButton(btn_frame, text="Check file usage", command=check_usage).pack(side="left")
        ctk.CTkButton(btn_frame, text="Close", command=popup.destroy).pack(side="right")
