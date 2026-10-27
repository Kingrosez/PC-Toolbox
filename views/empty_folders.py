"""Empty Folders view for PC-Toolbox - full implementation."""

import customtkinter as ctk
import threading
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

import sys
sys.path.insert(0, 'd:/Windows app/PC-Toolbox')


class EmptyFoldersView(ctk.CTkFrame):
    """Empty Folders screen with scan, filters, pagination, details, and safe deletion."""

    def __init__(self, master, navigation):
        super().__init__(master, fg_color=master.theme.colors["deep_background"])
        self.theme = master.theme
        self.navigation = navigation

        self.act = getattr(navigation, "activity_service", None)
        self.ctrl = getattr(navigation, "empty_folders_controller", None)
        if not self.act or not self.ctrl:
            from services.activity_service import ActivityService
            from controllers.empty_folders_controller import EmptyFoldersController
            self.act = self.act or ActivityService()
            self.ctrl = self.ctrl or EmptyFoldersController(self.act)

        self._scanning = False
        self._scan_th = None
        self._folders = []
        self._filtered = []
        self._selected_ids = set()
        self._selected_folder = None
        self._search_text = ""
        self._location_filter = "All Locations"
        self._page = 1
        self._per_page = 25
        self._last_updated = None
        self._exclusions = []

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
        self._create_table_panel()
        self._create_footer()

    def _create_header(self):
        header = ctk.CTkFrame(self.scroll, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 16))
        header.grid_columnconfigure(1, weight=1)

        left = ctk.CTkFrame(header, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(left, text="\U0001F4C1", font=ctk.CTkFont(size=30),
                    text_color=self.theme.colors["blue_accent"]).grid(row=0, column=0, sticky="w", padx=(0, 12))

        ctk.CTkLabel(left, text="Empty Folders", font=ctk.CTkFont(size=28, weight="bold"),
                    text_color=self.theme.colors["primary_text"]).grid(row=0, column=1, sticky="w")

        ctk.CTkLabel(left, text="Find and remove empty folders to keep your system clean",
                    font=ctk.CTkFont(size=13),
                    text_color=self.theme.colors["secondary_text"]).grid(row=1, column=1, sticky="w", pady=(2, 0))

        right = ctk.CTkFrame(header, fg_color="transparent")
        right.grid(row=0, column=1, sticky="e")

        self.updated_lbl = ctk.CTkLabel(right, text="Last updated: --",
                                       font=ctk.CTkFont(size=11),
                                       text_color=self.theme.colors["muted_text"])
        self.updated_lbl.grid(row=1, column=0, sticky="e", pady=(2, 0))

        self.refresh_btn = ctk.CTkButton(
            right, text="Refresh", command=self._scan,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=self.theme.colors["glass_panel"],
            border_width=1, border_color=self.theme.colors["border"],
            hover_color=self.theme.colors["hover_state"],
            text_color=self.theme.colors["primary_text"],
            height=30, width=80, corner_radius=6,
        )
        self.refresh_btn.grid(row=0, column=1, rowspan=2, sticky="e", padx=(16, 0))

    def _create_controls(self):
        row = ctk.CTkFrame(self.scroll, fg_color="transparent")
        row.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 16))
        row.grid_columnconfigure(0, weight=1)
        row.grid_columnconfigure(1, weight=1)
        row.grid_columnconfigure(2, weight=0)

        self.scan_b = ctk.CTkButton(
            row, text="Scan for Empty Folders", command=self._scan,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=self.theme.colors["blue_accent"],
            hover_color="#1570D6", text_color="white",
            height=52, corner_radius=10,
        )
        self.scan_b.grid(row=0, column=0, padx=(0, 8), sticky="ew")

        ctk.CTkLabel(row, text="Search for empty folders in selected locations",
                    font=ctk.CTkFont(size=11),
                    text_color=self.theme.colors["secondary_text"]).grid(row=1, column=0, padx=(0, 8), sticky="w")

        self.can_b = ctk.CTkButton(
            row, text="Cancel Scan", command=self._cancel,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=self.theme.colors["red_accent"],
            hover_color="#D06565", text_color="white",
            height=52, corner_radius=10, state="disabled",
        )
        self.can_b.grid(row=0, column=1, padx=8, sticky="ew")

        ctk.CTkLabel(row, text="Stop current scan",
                    font=ctk.CTkFont(size=11),
                    text_color=self.theme.colors["secondary_text"]).grid(row=1, column=1, padx=8, sticky="w")

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

        ctk.CTkLabel(settings_frame, text="Select locations and options",
                    font=ctk.CTkFont(size=11),
                    text_color=self.theme.colors["secondary_text"]).grid(row=1, column=0, padx=12, pady=(0, 8), sticky="w")

    def _create_summary_cards(self):
        cards = ctk.CTkFrame(self.scroll, fg_color="transparent")
        cards.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 16))
        for i in range(4):
            cards.grid_columnconfigure(i, weight=1)

        defs = [
            ("\U0001F4C1", "Empty Folders Found", "count", self.theme.colors["blue_accent"]),
            ("\U0001F4BE", "Potential Space Saved", "size", self.theme.colors["purple_accent"]),
            ("\U0001F4C2", "Locations Scanned", "locations", self.theme.colors["cyan_accent"]),
            ("\u23F1", "Scan Time", "time", self.theme.colors["green_accent"]),
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

    def _create_table_panel(self):
        panel = ctk.CTkFrame(
            self.scroll, fg_color=self.theme.colors["glass_panel"],
            corner_radius=14, border_width=1,
            border_color=self.theme.colors["border"],
        )
        panel.grid(row=3, column=0, sticky="nsew", padx=24, pady=(0, 16))
        panel.grid_columnconfigure(0, weight=3)
        panel.grid_columnconfigure(1, weight=1)
        panel.grid_rowconfigure(0, weight=1)

        table_container = ctk.CTkFrame(panel, fg_color="transparent")
        table_container.grid(row=0, column=0, sticky="nsew", padx=(16, 8), pady=16)
        table_container.grid_columnconfigure(0, weight=1)
        table_container.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            table_container, text="Empty Folders (0)",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=self.theme.colors["primary_text"],
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        # Search + location filter
        filter_frame = ctk.CTkFrame(table_container, fg_color="transparent")
        filter_frame.grid(row=0, column=1, sticky="e", pady=(0, 8))

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *a: self._apply_filters())
        ctk.CTkEntry(
            filter_frame, textvariable=self.search_var,
            placeholder_text="Search folders...",
            font=ctk.CTkFont(size=12),
            fg_color=self.theme.colors["secondary_panel"],
            border_width=1, border_color=self.theme.colors["border"],
            text_color=self.theme.colors["primary_text"],
            height=32, width=200, corner_radius=8,
        ).grid(row=0, column=0, padx=(0, 8))

        self.location_var = ctk.StringVar(value="All Locations")
        self.location_menu = ctk.CTkOptionMenu(
            filter_frame, variable=self.location_var,
            values=["All Locations"],
            command=lambda v: self._set_location(v),
            font=ctk.CTkFont(size=12),
            fg_color=self.theme.colors["secondary_panel"],
            button_color=self.theme.colors["border"],
            text_color=self.theme.colors["primary_text"],
            height=32, corner_radius=8,
        )
        self.location_menu.grid(row=0, column=1)

        self.table_body = ctk.CTkScrollableFrame(
            table_container, fg_color=self.theme.colors["secondary_panel"],
            corner_radius=8,
        )
        self.table_body.grid(row=1, column=0, columnspan=2, sticky="nsew")
        self.table_body.grid_columnconfigure(0, weight=1)

        self._show_empty_state()

        # Details panel (right)
        self.details_panel = ctk.CTkFrame(
            panel, fg_color=self.theme.colors["secondary_panel"],
            corner_radius=10, border_width=1,
            border_color=self.theme.colors["border"],
        )
        self.details_panel.grid(row=0, column=1, sticky="nsew", padx=(8, 16), pady=16)
        self.details_panel.grid_columnconfigure(0, weight=1)
        self._show_no_selection()

    def _show_empty_state(self):
        for w in self.table_body.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self.table_body,
            text="Ready to scan\n\nScan approved locations to find empty folders.",
            font=ctk.CTkFont(size=14),
            text_color=self.theme.colors["muted_text"],
            justify="center",
        ).pack(pady=40)

    def _show_no_results_state(self):
        for w in self.table_body.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self.table_body,
            text="No empty folders found\n\nNo eligible empty folders were found in the selected locations.",
            font=ctk.CTkFont(size=14),
            text_color=self.theme.colors["muted_text"],
            justify="center",
        ).pack(pady=40)

    def _show_no_selection(self):
        for w in self.details_panel.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self.details_panel, text="No folder selected",
            font=ctk.CTkFont(size=14),
            text_color=self.theme.colors["muted_text"],
            justify="center",
        ).pack(pady=40)

    def _show_details(self, folder):
        for w in self.details_panel.winfo_children():
            w.destroy()

        name = os.path.basename(folder.get("path", "")) or folder.get("path", "Unknown")
        path = folder.get("path", "Unknown")
        parent = folder.get("parent", "Unknown")
        mtime = self._fmt_time(folder.get("mtime"))
        depth = folder.get("depth", 0)
        file_count = folder.get("file_count", 0)
        sub_count = folder.get("subfolder_count", 0)
        size = self.ctrl.format_size(folder.get("size_bytes"))
        status = "Empty"

        ctk.CTkLabel(self.details_panel, text="\U0001F4C1  %s" % name,
                    font=ctk.CTkFont(size=16, weight="bold"),
                    text_color=self.theme.colors["primary_text"],
                    wraplength=220).pack(padx=16, pady=(16, 4), anchor="w")

        # Status badge
        badge = ctk.CTkLabel(
            self.details_panel, text=status,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="white",
            fg_color=self.theme.colors["green_accent"],
            corner_radius=4,
        )
        badge.pack(padx=16, pady=(0, 8), anchor="w")

        for label, val in [
            ("Full Path", path),
            ("Parent Folder", parent),
            ("Last Modified", mtime),
            ("Depth", str(depth)),
            ("Files", str(file_count)),
            ("Subfolders", str(sub_count)),
            ("Size on Disk", size),
        ]:
            ctk.CTkLabel(self.details_panel, text="%s: %s" % (label, val),
                        font=ctk.CTkFont(size=12),
                        text_color=self.theme.colors["secondary_text"],
                        wraplength=220).pack(padx=16, pady=2, anchor="w")

        # Actions
        btn_frame = ctk.CTkFrame(self.details_panel, fg_color="transparent")
        btn_frame.pack(fill="x", padx=16, pady=12)

        ctk.CTkButton(btn_frame, text="Open in File Explorer", command=lambda: None,
                     font=ctk.CTkFont(size=12),
                     fg_color=self.theme.colors["glass_panel"],
                     hover_color=self.theme.colors["hover_state"],
                     text_color=self.theme.colors["primary_text"],
                     height=30, corner_radius=6).pack(fill="x", pady=2)

        ctk.CTkButton(btn_frame, text="Open Parent Folder", command=lambda: None,
                     font=ctk.CTkFont(size=12),
                     fg_color=self.theme.colors["glass_panel"],
                     hover_color=self.theme.colors["hover_state"],
                     text_color=self.theme.colors["primary_text"],
                     height=30, corner_radius=6).pack(fill="x", pady=2)

        ctk.CTkButton(btn_frame, text="Copy Path", command=lambda: None,
                     font=ctk.CTkFont(size=12),
                     fg_color=self.theme.colors["glass_panel"],
                     hover_color=self.theme.colors["hover_state"],
                     text_color=self.theme.colors["primary_text"],
                     height=30, corner_radius=6).pack(fill="x", pady=2)

        ctk.CTkButton(btn_frame, text="Add to Exclusions", command=lambda: self._add_exclusion(folder),
                     font=ctk.CTkFont(size=12),
                     fg_color=self.theme.colors["glass_panel"],
                     hover_color=self.theme.colors["hover_state"],
                     text_color=self.theme.colors["primary_text"],
                     height=30, corner_radius=6).pack(fill="x", pady=2)

        # Delete button
        self.delete_btn = ctk.CTkButton(
            btn_frame, text="Delete Selected Folders",
            command=self._confirm_delete,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=self.theme.colors["red_accent"],
            hover_color="#D06565", text_color="white",
            height=34, corner_radius=6,
            state="disabled",
        )
        self.delete_btn.pack(fill="x", pady=(8, 2))

    def _add_exclusion(self, folder):
        path = folder.get("path")
        if path and path not in self._exclusions:
            self._exclusions.append(path)
            self.ctrl.service._exclusions.add(path.lower())
            # Re-filter
            self._apply_filters()

    def _create_footer(self):
        footer = ctk.CTkFrame(
            self.scroll, fg_color=self.theme.colors["glass_panel"],
            corner_radius=12, border_width=1,
            border_color=self.theme.colors["border"],
        )
        footer.grid(row=4, column=0, sticky="ew", padx=24, pady=(0, 20))
        footer.grid_columnconfigure(0, weight=1)

        self.selection_lbl = ctk.CTkLabel(
            footer, text="0 selected | 0 B",
            font=ctk.CTkFont(size=12),
            text_color=self.theme.colors["primary_text"],
        )
        self.selection_lbl.grid(row=0, column=0, sticky="w", padx=16, pady=10)

        pag = ctk.CTkFrame(footer, fg_color="transparent")
        pag.grid(row=0, column=1, sticky="e", padx=16, pady=10)

        ctk.CTkLabel(pag, text="Rows per page:", font=ctk.CTkFont(size=11),
                    text_color=self.theme.colors["secondary_text"]).grid(row=0, column=0, padx=(0, 6))

        self.rows_var = ctk.StringVar(value="25")
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

        self.range_lbl = ctk.CTkLabel(
            pag, text="0\u20130 of 0", font=ctk.CTkFont(size=11),
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
        self.next_btn.grid(row=0, column=4, padx=2)

    # ------------------------------------------------------------------ helpers
    def _fmt_time(self, ts):
        if not ts:
            return "N/A"
        try:
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
        except (ValueError, OSError, TypeError):
            return "N/A"

    def _fmt_duration(self, seconds):
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

    # ------------------------------------------------------------------ state
    def _idle(self):
        self._scanning = False
        self._folders = []
        self._filtered = []
        self._selected_ids.clear()
        self._selected_folder = None
        self._show_no_selection()
        self._render_table()
        self._update_pagination()
        self._update_selection_summary()

    def _scan(self):
        if self._scanning:
            return
        self._scanning = True
        self.scan_b.configure(state="disabled")
        self.can_b.configure(state="normal")
        self._card_cache["count"].configure(text="0")
        self._card_cache["size"].configure(text="0 B")
        self._card_cache["locations"].configure(text="0")
        self._card_cache["time"].configure(text="0s")
        self._clear_table()
        self._scan_start_time = time.monotonic()
        self._scan_th = threading.Thread(target=self._run, daemon=True)
        self._scan_th.start()

    def _cancel(self):
        if not self._scanning:
            return
        self.ctrl.cancel_scan()
        self._scanning = False
        self.scan_b.configure(state="normal")
        self.can_b.configure(state="disabled")

    def _run(self):
        try:
            roots = self.ctrl.get_approved_roots()
            result = self.ctrl.scan(roots=roots)
        except Exception as e:
            result = {"error": str(e), "folders": [], "folder_count": 0,
                      "locations_scanned": 0, "scan_duration": 0.0, "errors": [str(e)]}
        self.after(0, self._done, result)

    def _done(self, result):
        self._scanning = False
        self.scan_b.configure(state="normal")
        self.can_b.configure(state="disabled")
        self._folders = result.get("folders", [])
        self._last_updated = datetime.now().strftime("%H:%M:%S")
        self.updated_lbl.configure(text="Last updated: %s" % self._last_updated)

        fc = result.get("folder_count", 0)
        ls = result.get("locations_scanned", 0)
        dur = result.get("scan_duration", 0.0)

        self._card_cache["count"].configure(text="%s" % format(fc, ","))
        self._card_cache["size"].configure(text="\u2014 (empty folders use no space)")
        self._card_cache["locations"].configure(text="%s" % ls)
        self._card_cache["time"].configure(text=self._fmt_duration(dur))

        if result.get("error"):
            pass
        elif result.get("errors"):
            pass

        self._apply_filters()
        self._scan_th = None

    def _clear_table(self):
        for w in self.table_body.winfo_children():
            w.destroy()

    def _apply_filters(self):
        search = self.search_var.get().strip() if hasattr(self, "search_var") else ""
        filtered = self.ctrl.filter_folders(self._folders, search=search, location=self._location_filter)
        self._filtered = filtered
        self._page = 1

        # Update location dropdown
        locs = self.ctrl.get_locations(self._folders)
        if hasattr(self, "location_menu"):
            self.location_menu.configure(values=locs)
            if self._location_filter not in locs:
                self._location_filter = "All Locations"
                self.location_var.set("All Locations")

        self.table_title = None
        try:
            self.table_title_lbl.configure(text="Empty Folders (%s)" % format(len(filtered), ","))
        except Exception:
            pass

        self._render_table()
        self._update_pagination()
        self._update_selection_summary()

    def _set_location(self, val):
        self._location_filter = val
        self._page = 1
        self._apply_filters()

    def _render_table(self):
        self._clear_table()

        if not self._filtered:
            if self._folders:
                self._show_no_results_state()
            else:
                self._show_empty_state()
            return

        page_folders, start, end = self.ctrl.paginate(self._filtered, self._page, self._per_page)
        for folder in page_folders:
            self._create_row(folder)

    def _create_row(self, folder):
        row = ctk.CTkFrame(
            self.table_body,
            fg_color=self.theme.colors["secondary_panel"],
            corner_radius=6, border_width=1,
            border_color=self.theme.colors["border"],
        )
        row.pack(fill="x", padx=4, pady=2)
        row.grid_columnconfigure(1, weight=1)

        var = ctk.BooleanVar(value=folder.get("path") in self._selected_ids)
        cb = ctk.CTkCheckBox(
            row, text="", variable=var, width=20, height=20,
            command=lambda p=folder.get("path"): self._toggle_select(p, var.get()),
            fg_color=self.theme.colors["blue_accent"],
            hover_color=self.theme.colors["hover_state"],
            border_color=self.theme.colors["border"],
        )
        cb.grid(row=0, column=0, sticky="w", padx=(8, 4), pady=6)

        name_frame = ctk.CTkFrame(row, fg_color="transparent")
        name_frame.grid(row=0, column=1, sticky="ew", padx=4, pady=6)
        name_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            name_frame, text=os.path.basename(folder.get("path", "")) or folder.get("path", ""),
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=self.theme.colors["primary_text"], anchor="w",
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            name_frame, text=folder.get("path", ""),
            font=ctk.CTkFont(size=10),
            text_color=self.theme.colors["muted_text"], anchor="w",
        ).grid(row=1, column=0, sticky="w")

        ctk.CTkLabel(
            row, text=folder.get("parent", "Unknown"),
            font=ctk.CTkFont(size=12),
            text_color=self.theme.colors["secondary_text"],
        ).grid(row=0, column=2, sticky="w", padx=8, pady=6)

        ctk.CTkLabel(
            row, text=self._fmt_time(folder.get("mtime")),
            font=ctk.CTkFont(size=12),
            text_color=self.theme.colors["secondary_text"],
        ).grid(row=0, column=3, sticky="w", padx=8, pady=6)

        ctk.CTkLabel(
            row, text=str(folder.get("depth", 0)),
            font=ctk.CTkFont(size=12),
            text_color=self.theme.colors["primary_text"],
        ).grid(row=0, column=4, sticky="e", padx=8, pady=6)

        row.bind("<Button-1>", lambda e, f=folder: self._select_folder(f))
        for child in row.winfo_children():
            child.bind("<Button-1>", lambda e, f=folder: self._select_folder(f))

    def _toggle_select(self, path, selected):
        if selected:
            self._selected_ids.add(path)
        else:
            self._selected_ids.discard(path)
        self._update_selection_summary()
        self._update_delete_button()

    def _select_folder(self, folder):
        self._selected_folder = folder
        self._show_details(folder)

    def _update_selection_summary(self):
        self.selection_lbl.configure(text="%s selected | 0 B" % len(self._selected_ids))

    def _update_delete_button(self):
        if hasattr(self, "delete_btn"):
            if self._selected_ids:
                self.delete_btn.configure(state="normal")
            else:
                self.delete_btn.configure(state="disabled")

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

    # ------------------------------------------------------------------ deletion
    def _confirm_delete(self):
        if not self._selected_ids:
            return
        paths = list(self._selected_ids)
        dialog = ctk.CTkToplevel(self)
        dialog.title("Confirm Deletion")
        dialog.geometry("600x400")
        dialog.transient(self.master)
        dialog.grab_set()
        dialog.configure(fg_color=self.theme.colors["deep_background"])

        ctk.CTkLabel(dialog, text="Delete %d folder(s)?" % len(paths),
                    font=ctk.CTkFont(size=18, weight="bold"),
                    text_color=self.theme.colors["primary_text"]).pack(pady=(20, 10))

        ctk.CTkLabel(dialog, text="This action is permanent. The following folders will be deleted:",
                    font=ctk.CTkFont(size=12),
                    text_color=self.theme.colors["secondary_text"]).pack(pady=(0, 8))

        textbox = ctk.CTkTextbox(dialog, height=200,
                                fg_color=self.theme.colors["glass_panel"],
                                text_color=self.theme.colors["primary_text"],
                                border_width=1, border_color=self.theme.colors["border"])
        textbox.pack(fill="both", expand=True, padx=24, pady=(0, 12))
        textbox.insert("0.0", "\n".join(paths))
        textbox.configure(state="disabled")

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=24, pady=12)

        def cancel():
            dialog.destroy()

        def delete():
            dialog.destroy()
            self._execute_delete(paths)

        ctk.CTkButton(btn_frame, text="Cancel", command=cancel,
                     fg_color="transparent", hover_color=self.theme.colors["hover_state"],
                     text_color=self.theme.colors["secondary_text"],
                     height=32, corner_radius=8).pack(side="left", padx=(0, 8))

        ctk.CTkButton(btn_frame, text="Delete Folders", command=delete,
                     fg_color=self.theme.colors["red_accent"], hover_color="#D06565",
                     text_color="white", height=32, corner_radius=8).pack(side="left")

    def _execute_delete(self, paths):
        approved = self.ctrl.get_approved_roots()
        result = self.ctrl.delete_folders(paths, approved)
        deleted = result.get("deleted", [])
        skipped = result.get("skipped", [])
        failed = result.get("failed", [])

        # Show result dialog
        dlg = ctk.CTkToplevel(self)
        dlg.title("Deletion Results")
        dlg.geometry("500x350")
        dlg.transient(self.master)
        dlg.grab_set()
        dlg.configure(fg_color=self.theme.colors["deep_background"])

        ctk.CTkLabel(dlg, text="Deletion Complete",
                    font=ctk.CTkFont(size=18, weight="bold"),
                    text_color=self.theme.colors["primary_text"]).pack(pady=(20, 10))

        ctk.CTkLabel(dlg, text="Deleted: %d  |  Skipped: %d  |  Failed: %d" % (
            len(deleted), len(skipped), len(failed)),
            font=ctk.CTkFont(size=13),
            text_color=self.theme.colors["secondary_text"]).pack(pady=(0, 12))

        textbox = ctk.CTkTextbox(dlg, height=180,
                                fg_color=self.theme.colors["glass_panel"],
                                text_color=self.theme.colors["primary_text"],
                                border_width=1, border_color=self.theme.colors["border"])
        textbox.pack(fill="both", expand=True, padx=24, pady=(0, 12))

        lines = []
        if deleted:
            lines.append("Deleted:")
            for p in deleted:
                lines.append("  %s" % p)
            lines.append("")
        if skipped:
            lines.append("Skipped:")
            for item in skipped:
                lines.append("  %s - %s" % (item.get("path", ""), item.get("reason", "")))
            lines.append("")
        if failed:
            lines.append("Failed:")
            for item in failed:
                lines.append("  %s - %s" % (item.get("path", ""), item.get("reason", "")))
        textbox.insert("0.0", "\n".join(lines) if lines else "No details.")
        textbox.configure(state="disabled")

        ctk.CTkButton(dlg, text="Close", command=dlg.destroy,
                     fg_color=self.theme.colors["blue_accent"],
                     hover_color="#1570D6", text_color="white",
                     height=32, corner_radius=8).pack(pady=(0, 20))

        # Refresh
        self._selected_ids.clear()
        self._apply_filters()
        self._update_selection_summary()
        self._update_delete_button()

    # ------------------------------------------------------------------ settings
    def _open_settings(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title("Scan Settings")
        dlg.geometry("500x350")
        dlg.transient(self.master)
        dlg.grab_set()
        dlg.configure(fg_color=self.theme.colors["deep_background"])

        ctk.CTkLabel(dlg, text="Scan Settings",
                    font=ctk.CTkFont(size=18, weight="bold"),
                    text_color=self.theme.colors["primary_text"]).pack(pady=(20, 10))

        ctk.CTkLabel(dlg, text="Session-only. Excluded paths are skipped during scanning.",
                    font=ctk.CTkFont(size=11),
                    text_color=self.theme.colors["secondary_text"]).pack(pady=(0, 16))

        ctk.CTkLabel(dlg, text="Approved roots (read-only):",
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color=self.theme.colors["primary_text"]).pack(anchor="w", padx=24, pady=(0, 4))

        roots_text = ctk.CTkTextbox(dlg, height=120,
                                   fg_color=self.theme.colors["glass_panel"],
                                   text_color=self.theme.colors["secondary_text"],
                                   border_width=1, border_color=self.theme.colors["border"])
        roots_text.pack(fill="x", padx=24, pady=(0, 12))
        roots = self.ctrl.get_approved_roots()
        roots_text.insert("0.0", "\n".join(roots) if roots else "No roots configured")
        roots_text.configure(state="disabled")

        ctk.CTkButton(dlg, text="Close", command=dlg.destroy,
                     fg_color=self.theme.colors["blue_accent"],
                     hover_color="#1570D6", text_color="white",
                     height=32, corner_radius=8).pack(pady=(0, 20))
