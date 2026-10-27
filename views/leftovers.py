"""Leftovers view for PC-Toolbox - full implementation."""

import customtkinter as ctk
import threading
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

import os
import sys
sys.path.insert(0, 'd:/Windows app/PC-Toolbox')


class LeftoversView(ctk.CTkFrame):
    """Leftovers screen with scan, filters, pagination, details, and safe removal."""

    CATEGORIES = ["All Items", "Files", "Registry Entries", "Shortcuts", "Related Data"]

    def __init__(self, master, navigation):
        super().__init__(master, fg_color=master.theme.colors["deep_background"])
        self.theme = master.theme
        self.navigation = navigation

        self.act = getattr(navigation, "activity_service", None)
        self.ctrl = getattr(navigation, "leftovers_controller", None)
        if not self.act or not self.ctrl:
            from services.activity_service import ActivityService
            from controllers.leftovers_controller import LeftoversController
            self.act = self.act or ActivityService()
            self.ctrl = self.ctrl or LeftoversController(self.act)

        self._scanning = False
        self._scan_th = None
        self._items = []
        self._filtered = []
        self._selected_ids = set()
        self._selected_item = None
        self._search_text = ""
        self._category = "All Items"
        self._type_filter = "All Types"
        self._page = 1
        self._per_page = 25
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

        ctk.CTkLabel(left, text="\U0001F5D1", font=ctk.CTkFont(size=30),
                    text_color=self.theme.colors["blue_accent"]).grid(row=0, column=0, sticky="w", padx=(0, 12))

        ctk.CTkLabel(left, text="Leftovers", font=ctk.CTkFont(size=28, weight="bold"),
                    text_color=self.theme.colors["primary_text"]).grid(row=0, column=1, sticky="w")

        ctk.CTkLabel(left, text="Find and remove leftover files from uninstalled applications",
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
            right, text="Refresh", command=self._scan,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=self.theme.colors["glass_panel"],
            border_width=1, border_color=self.theme.colors["border"],
            hover_color=self.theme.colors["hover_state"],
            text_color=self.theme.colors["primary_text"],
            height=30, width=80, corner_radius=6,
        )
        self.refresh_btn.grid(row=0, column=2, sticky="e", padx=(8, 0))

    def _create_controls(self):
        row = ctk.CTkFrame(self.scroll, fg_color="transparent")
        row.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 16))
        row.grid_columnconfigure(0, weight=1)
        row.grid_columnconfigure(1, weight=1)
        row.grid_columnconfigure(2, weight=0)

        self.scan_b = ctk.CTkButton(
            row, text="Scan for Leftovers", command=self._scan,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=self.theme.colors["blue_accent"],
            hover_color="#1570D6", text_color="white",
            height=52, corner_radius=10,
        )
        self.scan_b.grid(row=0, column=0, padx=(0, 8), sticky="ew")

        ctk.CTkLabel(row, text="Find residual files and registry entries",
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

        ctk.CTkLabel(settings_frame, text="Select locations and categories",
                    font=ctk.CTkFont(size=11),
                    text_color=self.theme.colors["secondary_text"]).grid(row=1, column=0, padx=12, pady=(0, 8), sticky="w")

    def _create_summary_cards(self):
        cards = ctk.CTkFrame(self.scroll, fg_color="transparent")
        cards.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 16))
        for i in range(4):
            cards.grid_columnconfigure(i, weight=1)

        defs = [
            ("\U0001F5D1", "Leftover Items", "count", self.theme.colors["blue_accent"]),
            ("\U0001F4BE", "Total Size", "size", self.theme.colors["purple_accent"]),
            ("\U0001F4E6", "Applications Found", "apps", self.theme.colors["cyan_accent"]),
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
        table_container.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            table_container, text="Leftover Items (0)",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=self.theme.colors["primary_text"],
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        # Filter bar
        filter_frame = ctk.CTkFrame(table_container, fg_color="transparent")
        filter_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))

        # Category buttons
        self._filter_buttons = {}
        for i, cat in enumerate(self.CATEGORIES):
            btn = ctk.CTkButton(
                filter_frame, text=cat, command=lambda c=cat: self._set_category(c),
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color=self.theme.colors["glass_panel"],
                hover_color=self.theme.colors["hover_state"],
                text_color=self.theme.colors["secondary_text"],
                height=28, corner_radius=6,
                border_width=1, border_color=self.theme.colors["border"],
            )
            btn.grid(row=0, column=i, padx=4, sticky="w")
            self._filter_buttons[cat] = btn

        # Search + type filter
        search_frame = ctk.CTkFrame(filter_frame, fg_color="transparent")
        search_frame.grid(row=0, column=len(self.CATEGORIES) + 1, sticky="e")

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *a: self._apply_filters())
        ctk.CTkEntry(
            search_frame, textvariable=self.search_var,
            placeholder_text="Search leftovers...",
            font=ctk.CTkFont(size=12),
            fg_color=self.theme.colors["secondary_panel"],
            border_width=1, border_color=self.theme.colors["border"],
            text_color=self.theme.colors["primary_text"],
            height=30, width=180, corner_radius=8,
        ).grid(row=0, column=0, padx=(0, 8))

        self.type_var = ctk.StringVar(value="All Types")
        self.type_menu = ctk.CTkOptionMenu(
            search_frame, variable=self.type_var,
            values=["All Types", "File", "Shortcut", "Registry Entry", "Related Data"],
            command=lambda v: self._set_type_filter(v),
            font=ctk.CTkFont(size=12),
            fg_color=self.theme.colors["secondary_panel"],
            button_color=self.theme.colors["border"],
            text_color=self.theme.colors["primary_text"],
            height=30, corner_radius=8,
        )
        self.type_menu.grid(row=0, column=1)

        self.table_body = ctk.CTkScrollableFrame(
            table_container, fg_color=self.theme.colors["secondary_panel"],
            corner_radius=8,
        )
        self.table_body.grid(row=2, column=0, sticky="nsew")
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
            text="Ready to scan\n\nScan to find leftover files and registry entries.",
            font=ctk.CTkFont(size=14),
            text_color=self.theme.colors["muted_text"],
            justify="center",
        ).pack(pady=40)

    def _show_no_results_state(self):
        for w in self.table_body.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self.table_body,
            text="No leftover items found\n\nNo eligible leftover items were found.",
            font=ctk.CTkFont(size=14),
            text_color=self.theme.colors["muted_text"],
            justify="center",
        ).pack(pady=40)

    def _show_no_selection(self):
        for w in self.details_panel.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self.details_panel, text="Select an item to view its details",
            font=ctk.CTkFont(size=14),
            text_color=self.theme.colors["muted_text"],
            justify="center",
        ).pack(pady=40)

    def _show_details(self, item):
        for w in self.details_panel.winfo_children():
            w.destroy()

        name = item.get("name", "Unknown")
        item_type = item.get("type", "File")
        path = item.get("path", "Unknown")
        size = self.ctrl.format_size(item.get("size_bytes"))
        mtime = self._fmt_time(item.get("mtime"))
        reason = item.get("reason", "Residual item found in scanned location")

        ctk.CTkLabel(self.details_panel, text="\U0001F4C4  %s" % name,
                    font=ctk.CTkFont(size=16, weight="bold"),
                    text_color=self.theme.colors["primary_text"],
                    wraplength=220).pack(padx=16, pady=(16, 4), anchor="w")

        badge = ctk.CTkLabel(
            self.details_panel, text=item_type,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="white",
            fg_color=self.theme.colors["blue_accent"],
            corner_radius=4,
        )
        badge.pack(padx=16, pady=(0, 8), anchor="w")

        for label, val in [
            ("Full Location", path),
            ("Size", size),
            ("Last Modified", mtime),
            ("Reason", reason),
        ]:
            ctk.CTkLabel(self.details_panel, text="%s: %s" % (label, val),
                        font=ctk.CTkFont(size=12),
                        text_color=self.theme.colors["secondary_text"],
                        wraplength=220).pack(padx=16, pady=2, anchor="w")

        btn_frame = ctk.CTkFrame(self.details_panel, fg_color="transparent")
        btn_frame.pack(fill="x", padx=16, pady=12)

        ctk.CTkButton(btn_frame, text="Open Location", command=lambda: None,
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

        ctk.CTkButton(btn_frame, text="Add to Exclusions", command=lambda: None,
                     font=ctk.CTkFont(size=12),
                     fg_color=self.theme.colors["glass_panel"],
                     hover_color=self.theme.colors["hover_state"],
                     text_color=self.theme.colors["primary_text"],
                     height=30, corner_radius=6).pack(fill="x", pady=2)

        self.remove_btn = ctk.CTkButton(
            btn_frame, text="Remove Selected",
            command=self._confirm_remove,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=self.theme.colors["red_accent"],
            hover_color="#D06565", text_color="white",
            height=32, corner_radius=6,
            state="disabled",
        )
        self.remove_btn.pack(fill="x", pady=(8, 2))

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
        self._items = []
        self._filtered = []
        self._selected_ids.clear()
        self._selected_item = None
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
        self._card_cache["apps"].configure(text="0")
        self._card_cache["time"].configure(text="0s")
        self._clear_table()
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
            result = self.ctrl.scan()
        except Exception as e:
            result = {"error": str(e), "items": [], "item_count": 0,
                      "locations_scanned": 0, "scan_duration": 0.0, "errors": [str(e)]}
        self.after(0, self._done, result)

    def _done(self, result):
        self._scanning = False
        self.scan_b.configure(state="normal")
        self.can_b.configure(state="disabled")
        self._items = result.get("items", [])
        self._last_updated = datetime.now().strftime("%H:%M:%S")
        self.updated_lbl.configure(text="Last updated: %s" % self._last_updated)

        ic = result.get("item_count", 0)
        summary = self.ctrl.get_summary(self._items)
        dur = result.get("scan_duration", 0.0)

        self._card_cache["count"].configure(text="%s" % format(ic, ","))
        if summary.get("total_size_bytes") is not None:
            self._card_cache["size"].configure(text=self.ctrl.format_size(summary["total_size_bytes"]))
        else:
            self._card_cache["size"].configure(text="Unknown")
        self._card_cache["apps"].configure(text=str(summary.get("apps_found", 0)))
        self._card_cache["time"].configure(text=self._fmt_duration(dur))

        self._apply_filters()
        self._scan_th = None

    def _clear_table(self):
        for w in self.table_body.winfo_children():
            w.destroy()

    def _apply_filters(self):
        search = self.search_var.get().strip() if hasattr(self, "search_var") else ""
        filtered = self.ctrl.filter_items(self._items, search=search, category=self._category, item_type=self._type_filter)
        filtered = self.ctrl.sort_items(filtered, "Name (A-Z)")
        self._filtered = filtered
        self._page = 1

        # Update table title
        try:
            self.table_title_lbl.configure(text="Leftover Items (%s)" % format(len(filtered), ","))
        except Exception:
            pass

        self._render_table()
        self._update_pagination()
        self._update_selection_summary()

    def _set_category(self, cat):
        self._category = cat
        self._page = 1
        for c, btn in self._filter_buttons.items():
            if c == cat:
                btn.configure(fg_color=self.theme.colors["blue_accent"], text_color="white")
            else:
                btn.configure(fg_color=self.theme.colors["glass_panel"], text_color=self.theme.colors["secondary_text"])
        self._apply_filters()

    def _set_type_filter(self, val):
        self._type_filter = val
        self._page = 1
        self._apply_filters()

    def _render_table(self):
        self._clear_table()
        if not self._filtered:
            if self._items:
                self._show_no_results_state()
            else:
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

        var = ctk.BooleanVar(value=item.get("id") in self._selected_ids)
        cb = ctk.CTkCheckBox(
            row, text="", variable=var, width=20, height=20,
            command=lambda iid=item.get("id"): self._toggle_select(iid, var.get()),
            fg_color=self.theme.colors["blue_accent"],
            hover_color=self.theme.colors["hover_state"],
            border_color=self.theme.colors["border"],
        )
        cb.grid(row=0, column=0, sticky="w", padx=(8, 4), pady=6)

        name_frame = ctk.CTkFrame(row, fg_color="transparent")
        name_frame.grid(row=0, column=1, sticky="ew", padx=4, pady=6)
        name_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(name_frame, text=item.get("name", "Unknown"),
                    font=ctk.CTkFont(size=13, weight="bold"),
                    text_color=self.theme.colors["primary_text"], anchor="w").grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(name_frame, text=item.get("path", ""),
                    font=ctk.CTkFont(size=10),
                    text_color=self.theme.colors["muted_text"], anchor="w").grid(row=1, column=0, sticky="w")

        ctk.CTkLabel(row, text=item.get("type", "File"),
                    font=ctk.CTkFont(size=12),
                    text_color=self.theme.colors["secondary_text"]).grid(row=0, column=2, sticky="w", padx=8, pady=6)

        ctk.CTkLabel(row, text=self.ctrl.format_size(item.get("size_bytes")),
                    font=ctk.CTkFont(size=12),
                    text_color=self.theme.colors["primary_text"]).grid(row=0, column=3, sticky="e", padx=8, pady=6)

        ctk.CTkLabel(row, text=self._fmt_time(item.get("mtime")),
                    font=ctk.CTkFont(size=11),
                    text_color=self.theme.colors["secondary_text"]).grid(row=0, column=4, sticky="e", padx=8, pady=6)

        row.bind("<Button-1>", lambda e, it=item: self._select_item(it))
        for child in row.winfo_children():
            child.bind("<Button-1>", lambda e, it=item: self._select_item(it))

    def _toggle_select(self, item_id, selected):
        if selected:
            self._selected_ids.add(item_id)
        else:
            self._selected_ids.discard(item_id)
        self._update_selection_summary()
        self._update_remove_button()

    def _select_item(self, item):
        self._selected_item = item
        self._show_details(item)

    def _update_selection_summary(self):
        total_size = 0
        size_known = False
        for iid in self._selected_ids:
            item = next((i for i in self._items if i.get("id") == iid), None)
            if item and item.get("size_bytes") is not None:
                total_size += item["size_bytes"]
                size_known = True
        size_str = self.ctrl.format_size(total_size) if size_known else "Unknown"
        self.selection_lbl.configure(text="%s selected | %s" % (len(self._selected_ids), size_str))

    def _update_remove_button(self):
        if hasattr(self, "remove_btn"):
            if self._selected_ids:
                self.remove_btn.configure(state="normal")
            else:
                self.remove_btn.configure(state="disabled")

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

    def _confirm_remove(self):
        if not self._selected_ids:
            return
        paths = [next((i.get("path") for i in self._items if i.get("id") == iid), iid) for iid in self._selected_ids]
        dialog = ctk.CTkToplevel(self)
        dialog.title("Confirm Removal")
        dialog.geometry("600x400")
        dialog.transient(self.master)
        dialog.grab_set()
        dialog.configure(fg_color=self.theme.colors["deep_background"])

        ctk.CTkLabel(dialog, text="Remove %d item(s)?" % len(paths),
                    font=ctk.CTkFont(size=18, weight="bold"),
                    text_color=self.theme.colors["primary_text"]).pack(pady=(20, 10))

        ctk.CTkLabel(dialog, text="This action may be permanent. Review the items below:",
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

        def remove():
            dialog.destroy()
            self._execute_remove()

        ctk.CTkButton(btn_frame, text="Cancel", command=cancel,
                     fg_color="transparent", hover_color=self.theme.colors["hover_state"],
                     text_color=self.theme.colors["secondary_text"],
                     height=32, corner_radius=8).pack(side="left", padx=(0, 8))

        ctk.CTkButton(btn_frame, text="Remove Selected", command=remove,
                     fg_color=self.theme.colors["red_accent"], hover_color="#D06565",
                     text_color="white", height=32, corner_radius=8).pack(side="left")

    def _execute_remove(self):
        items_to_remove = [i for i in self._items if i.get("id") in self._selected_ids]
        approved = self.ctrl.get_approved_roots()
        result = self.ctrl.remove_items(items_to_remove, approved)

        removed = result.get("removed", [])
        skipped = result.get("skipped", [])
        failed = result.get("failed", [])

        dlg = ctk.CTkToplevel(self)
        dlg.title("Removal Results")
        dlg.geometry("500x350")
        dlg.transient(self.master)
        dlg.grab_set()
        dlg.configure(fg_color=self.theme.colors["deep_background"])

        ctk.CTkLabel(dlg, text="Removal Complete",
                    font=ctk.CTkFont(size=18, weight="bold"),
                    text_color=self.theme.colors["primary_text"]).pack(pady=(20, 10))

        ctk.CTkLabel(dlg, text="Removed: %d  |  Skipped: %d  |  Failed: %d" % (
            len(removed), len(skipped), len(failed)),
            font=ctk.CTkFont(size=13),
            text_color=self.theme.colors["secondary_text"]).pack(pady=(0, 12))

        textbox = ctk.CTkTextbox(dlg, height=180,
                                fg_color=self.theme.colors["glass_panel"],
                                text_color=self.theme.colors["primary_text"],
                                border_width=1, border_color=self.theme.colors["border"])
        textbox.pack(fill="both", expand=True, padx=24, pady=(0, 12))

        lines = []
        if removed:
            lines.append("Removed:")
            for r in removed:
                lines.append("  %s" % r)
            lines.append("")
        if skipped:
            lines.append("Skipped:")
            for s in skipped:
                lines.append("  %s - %s" % (s.get("item", {}).get("path", ""), s.get("reason", "")))
            lines.append("")
        if failed:
            lines.append("Failed:")
            for f in failed:
                lines.append("  %s - %s" % (f.get("item", {}).get("path", ""), f.get("reason", "")))
        textbox.insert("0.0", "\n".join(lines) if lines else "No details.")
        textbox.configure(state="disabled")

        ctk.CTkButton(dlg, text="Close", command=dlg.destroy,
                     fg_color=self.theme.colors["blue_accent"],
                     hover_color="#1570D6", text_color="white",
                     height=32, corner_radius=8).pack(pady=(0, 20))

        self._selected_ids.clear()
        self._apply_filters()
        self._update_selection_summary()
        self._update_remove_button()

    def _open_settings(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title("Scan Settings")
        dlg.geometry("500x300")
        dlg.transient(self.master)
        dlg.grab_set()
        dlg.configure(fg_color=self.theme.colors["deep_background"])

        ctk.CTkLabel(dlg, text="Scan Settings",
                    font=ctk.CTkFont(size=18, weight="bold"),
                    text_color=self.theme.colors["primary_text"]).pack(pady=(20, 10))

        ctk.CTkLabel(dlg, text="Session-only settings.",
                    font=ctk.CTkFont(size=11),
                    text_color=self.theme.colors["secondary_text"]).pack(pady=(0, 16))

        ctk.CTkLabel(dlg, text="Approved roots:",
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color=self.theme.colors["primary_text"]).pack(anchor="w", padx=24, pady=(0, 4))

        roots_text = ctk.CTkTextbox(dlg, height=100,
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
