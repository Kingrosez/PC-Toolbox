"""Leftovers view for PC-Toolbox - full implementation."""

import customtkinter as ctk
import ctypes
import queue
import threading
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

import os
import sys
sys.path.insert(0, 'd:/Windows app/PC-Toolbox')


class _RecycleBinInfo(ctypes.Structure):
    """SHQUERYRECBINW structure used to query the Recycle Bin contents."""

    _fields_ = [
        ("cbSize", ctypes.c_ulong),
        ("i64Size", ctypes.c_longlong),
        ("i64NumItems", ctypes.c_longlong),
    ]


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

        self.cleanup_ctrl = getattr(navigation, "system_cleanup_controller", None)
        if not self.cleanup_ctrl:
            from services.activity_service import ActivityService
            from controllers.system_cleanup_controller import SystemCleanupController
            self.cleanup_ctrl = SystemCleanupController(
                self.act or ActivityService(),
                getattr(navigation, "settings_service", None),
            )

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

        self._cleanup_scanning = False
        self._cleanup_cleaning = False
        self._cleanup_items = []
        self._cleanup_by_id = {}
        self._cleanup_selected = set()
        self._cleanup_vars = {}
        self._cleanup_progress_queue = queue.Queue()
        self._cleanup_poll_id = None
        self._cleanup_admin = self.cleanup_ctrl.is_admin()
        self._cleanup_dry_run = ctk.BooleanVar(value=False)
        self._cleanup_free_space = None
        self._cleanup_log_path = self.cleanup_ctrl.get_log_path()

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._setup_ui()
        self._idle()

    def _setup_ui(self):
        c = self.theme.colors
        self.tabs = ctk.CTkTabview(
            self,
            fg_color=c["deep_background"],
            segmented_button_fg_color=c["glass_panel"],
            segmented_button_selected_color=c["blue_accent"],
            segmented_button_selected_hover_color="#1570D6",
            segmented_button_unselected_color=c["glass_panel"],
            segmented_button_unselected_hover_color=c["hover_state"],
            text_color=c["primary_text"],
        )
        self.tabs.pack(fill="both", expand=True)
        self.leftovers_tab = self.tabs.add("Leftovers")
        self.cleanup_tab = self.tabs.add("System Cleanup")
        for tab in (self.leftovers_tab, self.cleanup_tab):
            tab.grid_rowconfigure(0, weight=1)
            tab.grid_columnconfigure(0, weight=1)

        self.scroll = ctk.CTkScrollableFrame(
            self.leftovers_tab,
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
        self._create_system_cleanup_ui(self.cleanup_tab)

    def _create_header(self):
        c = self.theme.colors
        header = ctk.CTkFrame(self.scroll, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=28, pady=(24, 16))
        header.grid_columnconfigure(1, weight=1)

        icon_box = ctk.CTkFrame(
            header, fg_color=c["secondary_panel"], corner_radius=10, width=44, height=44
        )
        icon_box.grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 14))
        icon_box.grid_propagate(False)
        ctk.CTkLabel(
            icon_box, text="\U0001F5D1", font=ctk.CTkFont(size=19),
            text_color=c["orange_accent"],
        ).place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            header, text="Leftovers", font=ctk.CTkFont(size=24, weight="bold"),
            text_color=c["primary_text"],
        ).grid(row=0, column=1, sticky="sw")

        ctk.CTkLabel(
            header, text="Find and remove leftover files from uninstalled applications",
            font=ctk.CTkFont(size=12),
            text_color=c["secondary_text"],
        ).grid(row=1, column=1, sticky="nw", pady=(2, 0))

        right = ctk.CTkFrame(header, fg_color="transparent")
        right.grid(row=0, column=2, rowspan=2, sticky="e")

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
        panel.grid_columnconfigure(0, weight=4)
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
                font=ctk.CTkFont(size=10, weight="bold"),
                fg_color=self.theme.colors["glass_panel"],
                hover_color=self.theme.colors["hover_state"],
                text_color=self.theme.colors["secondary_text"],
                height=28, width=94, corner_radius=6,
                border_width=1, border_color=self.theme.colors["border"],
            )
            btn.grid(row=0, column=i, padx=4, sticky="w")
            self._filter_buttons[cat] = btn

        # Search + type filter
        search_frame = ctk.CTkFrame(filter_frame, fg_color="transparent")
        search_frame.grid(row=0, column=len(self.CATEGORIES) + 1, sticky="e")

        self.search_var = ctk.StringVar()
        self.search_var.trace("w", lambda *a: self._apply_filters())
        ctk.CTkEntry(
            search_frame, textvariable=self.search_var,
            placeholder_text="Search leftovers...",
            font=ctk.CTkFont(size=11),
            fg_color=self.theme.colors["secondary_panel"],
            border_width=1, border_color=self.theme.colors["border"],
            text_color=self.theme.colors["primary_text"],
            height=30, width=150, corner_radius=8,
        ).grid(row=0, column=0, padx=(0, 8))

        self.type_var = ctk.StringVar(value="All Types")
        self.type_menu = ctk.CTkOptionMenu(
            search_frame, variable=self.type_var,
            values=["All Types", "File", "Shortcut", "Registry Entry", "Related Data"],
            command=lambda v: self._set_type_filter(v),
            font=ctk.CTkFont(size=11),
            fg_color=self.theme.colors["secondary_panel"],
            button_color=self.theme.colors["border"],
            text_color=self.theme.colors["primary_text"],
            height=30, width=108, corner_radius=8,
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
            font=ctk.CTkFont(size=13),
            text_color=self.theme.colors["muted_text"],
            justify="center", wraplength=170,
        ).pack(pady=40, padx=8)

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
                    wraplength=180).pack(padx=16, pady=(16, 4), anchor="w")

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
                        wraplength=170).pack(padx=16, pady=2, anchor="w")

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

    # --------------------------------------------------------- system cleanup
    def _create_system_cleanup_ui(self, parent):
        c = self.theme.colors
        self.cleanup_scroll = ctk.CTkScrollableFrame(
            parent,
            fg_color=c["deep_background"],
            scrollbar_fg_color=c["glass_panel"],
            scrollbar_button_color=c["border"],
            scrollbar_button_hover_color=c["blue_accent"],
        )
        self.cleanup_scroll.pack(fill="both", expand=True)
        self.cleanup_scroll.grid_columnconfigure(0, weight=1)

        self._create_cleanup_header()
        self._create_cleanup_controls()
        self._create_cleanup_progress()
        self._create_cleanup_cards()
        self._create_cleanup_results()
        self._create_cleanup_footer()
        self._cleanup_update_admin_ui()

    def _create_cleanup_header(self):
        c = self.theme.colors
        header = ctk.CTkFrame(self.cleanup_scroll, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=28, pady=(24, 16))
        header.grid_columnconfigure(1, weight=1)

        icon_box = ctk.CTkFrame(
            header, fg_color=c["secondary_panel"], corner_radius=10, width=44, height=44
        )
        icon_box.grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 14))
        icon_box.grid_propagate(False)
        ctk.CTkLabel(
            icon_box, text="\U0001F9F9", font=ctk.CTkFont(size=19),
            text_color=c["green_accent"],
        ).place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            header, text="System Cleanup", font=ctk.CTkFont(size=24, weight="bold"),
            text_color=c["primary_text"],
        ).grid(row=0, column=1, sticky="sw")
        ctk.CTkLabel(
            header,
            text="Find and safely remove system, browser and developer junk",
            font=ctk.CTkFont(size=12),
            text_color=c["secondary_text"],
        ).grid(row=1, column=1, sticky="nw", pady=(2, 0))

        right = ctk.CTkFrame(header, fg_color="transparent")
        right.grid(row=0, column=2, rowspan=2, sticky="e")

        self.cleanup_admin_lbl = ctk.CTkLabel(
            right, text="", font=ctk.CTkFont(size=11, weight="bold"),
            text_color=c["secondary_text"],
        )
        self.cleanup_admin_lbl.grid(row=0, column=0, sticky="e", padx=(0, 8))

        self.cleanup_restart_btn = None
        if not self._cleanup_admin:
            self.cleanup_restart_btn = ctk.CTkButton(
                right, text="Restart as administrator",
                command=self._cleanup_restart_admin,
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color=c["orange_accent"], hover_color="#E08A2E",
                text_color="white", height=30, width=160, corner_radius=6,
            )
            self.cleanup_restart_btn.grid(row=0, column=1, sticky="e", padx=(0, 8))

        ctk.CTkButton(
            right, text="Open log", command=self._cleanup_open_log,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=c["glass_panel"], hover_color=c["hover_state"],
            text_color=c["primary_text"], height=30, width=90, corner_radius=6,
            border_width=1, border_color=c["border"],
        ).grid(row=0, column=2, sticky="e")

    def _create_cleanup_controls(self):
        c = self.theme.colors
        row = ctk.CTkFrame(self.cleanup_scroll, fg_color="transparent")
        row.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 14))
        row.grid_columnconfigure(0, weight=1)
        row.grid_columnconfigure(1, weight=1)
        row.grid_columnconfigure(2, weight=0)

        self.cleanup_scan_b = ctk.CTkButton(
            row, text="Scan System Junk", command=self._cleanup_scan,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=c["blue_accent"], hover_color="#1570D6",
            text_color="white", height=52, corner_radius=10,
        )
        self.cleanup_scan_b.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        ctk.CTkLabel(
            row, text="Tier 1 is pre-ticked; higher tiers are opt-in",
            font=ctk.CTkFont(size=11), text_color=c["secondary_text"],
        ).grid(row=1, column=0, padx=(0, 8), sticky="w")

        self.cleanup_cancel_b = ctk.CTkButton(
            row, text="Cancel Scan", command=self._cleanup_cancel_scan,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=c["red_accent"], hover_color="#D06565",
            text_color="white", height=52, corner_radius=10, state="disabled",
        )
        self.cleanup_cancel_b.grid(row=0, column=1, padx=8, sticky="ew")
        ctk.CTkLabel(
            row, text="Stop the current scan safely",
            font=ctk.CTkFont(size=11), text_color=c["secondary_text"],
        ).grid(row=1, column=1, padx=8, sticky="w")

        settings = ctk.CTkFrame(
            row, fg_color=c["glass_panel"], corner_radius=10,
            border_width=1, border_color=c["border"],
        )
        settings.grid(row=0, column=2, rowspan=2, padx=(8, 0), sticky="nsew")
        self.cleanup_dry_switch = ctk.CTkSwitch(
            settings, text="Dry run (no deletion)", variable=self._cleanup_dry_run,
            command=self._cleanup_update_summary,
            font=ctk.CTkFont(size=11, weight="bold"),
            progress_color=c["blue_accent"], button_color=c["primary_text"],
            text_color=c["primary_text"],
        )
        self.cleanup_dry_switch.grid(row=0, column=0, padx=12, pady=(10, 4), sticky="w")
        self.cleanup_options_b = ctk.CTkButton(
            settings, text="\u2699  Cleanup Options", command=self._cleanup_open_options,
            font=ctk.CTkFont(size=11), fg_color="transparent",
            hover_color=c["hover_state"], text_color=c["secondary_text"],
            height=26, corner_radius=6,
        )
        self.cleanup_options_b.grid(row=1, column=0, padx=12, pady=(0, 8), sticky="w")

    def _create_cleanup_progress(self):
        c = self.theme.colors
        frame = ctk.CTkFrame(self.cleanup_scroll, fg_color="transparent")
        frame.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 12))
        frame.grid_columnconfigure(0, weight=1)

        self.cleanup_progress = ctk.CTkProgressBar(
            frame, height=8, corner_radius=4,
            fg_color=c["secondary_panel"], progress_color=c["green_accent"],
        )
        self.cleanup_progress.grid(row=0, column=0, sticky="ew")
        self.cleanup_progress.set(0)

        self.cleanup_status_lbl = ctk.CTkLabel(
            frame, text="Ready to scan", font=ctk.CTkFont(size=11),
            text_color=c["secondary_text"],
        )
        self.cleanup_status_lbl.grid(row=1, column=0, sticky="w", pady=(4, 0))

        self.cleanup_notice_lbl = ctk.CTkLabel(
            frame, text="", font=ctk.CTkFont(size=10),
            text_color=c["orange_accent"], justify="left", wraplength=980,
        )
        self.cleanup_notice_lbl.grid(row=2, column=0, sticky="w", pady=(2, 0))

    def _create_cleanup_cards(self):
        c = self.theme.colors
        cards = ctk.CTkFrame(self.cleanup_scroll, fg_color="transparent")
        cards.grid(row=3, column=0, sticky="ew", padx=24, pady=(0, 14))
        for i in range(3):
            cards.grid_columnconfigure(i, weight=1)

        defs = [
            ("\U0001F4B0", "Selected to free", "selected", c["green_accent"]),
            ("\U0001F4BE", "Free space on C:", "free", c["purple_accent"]),
            ("\U0001F4E6", "Items found", "count", c["cyan_accent"]),
        ]
        self._cleanup_cards = {}
        for i, (icon, title, key, accent) in enumerate(defs):
            card = ctk.CTkFrame(
                cards, fg_color=c["glass_panel"], corner_radius=12,
                border_width=1, border_color=c["border"],
            )
            card.grid(row=0, column=i, sticky="nsew", padx=6)
            ctk.CTkLabel(
                card, text=icon, font=ctk.CTkFont(size=20), text_color=accent,
            ).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 0))
            value = ctk.CTkLabel(
                card, text="\u2014", font=ctk.CTkFont(size=26, weight="bold"),
                text_color=c["primary_text"],
            )
            value.grid(row=1, column=0, sticky="w", padx=16, pady=(4, 0))
            ctk.CTkLabel(
                card, text=title, font=ctk.CTkFont(size=11),
                text_color=c["secondary_text"],
            ).grid(row=2, column=0, sticky="w", padx=16, pady=(0, 14))
            self._cleanup_cards[key] = value

    def _create_cleanup_results(self):
        c = self.theme.colors
        panel = ctk.CTkFrame(
            self.cleanup_scroll, fg_color=c["glass_panel"], corner_radius=14,
            border_width=1, border_color=c["border"],
        )
        panel.grid(row=4, column=0, sticky="ew", padx=24, pady=(0, 14))
        panel.grid_columnconfigure(0, weight=1)

        title_row = ctk.CTkFrame(panel, fg_color="transparent")
        title_row.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 8))
        title_row.grid_columnconfigure(0, weight=1)

        self.cleanup_table_title = ctk.CTkLabel(
            title_row, text="System Cleanup Items (0)",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=c["primary_text"],
        )
        self.cleanup_table_title.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            title_row,
            text="Nothing is deleted until you review and confirm the selection.",
            font=ctk.CTkFont(size=11), text_color=c["secondary_text"],
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        self.cleanup_results = ctk.CTkFrame(
            panel, fg_color=c["secondary_panel"], corner_radius=8,
        )
        self.cleanup_results.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 14))
        self.cleanup_results.grid_columnconfigure(0, weight=1)
        self._cleanup_show_empty()

    def _create_cleanup_footer(self):
        c = self.theme.colors
        footer = ctk.CTkFrame(
            self.cleanup_scroll, fg_color=c["glass_panel"], corner_radius=12,
            border_width=1, border_color=c["border"],
        )
        footer.grid(row=5, column=0, sticky="ew", padx=24, pady=(0, 20))
        footer.grid_columnconfigure(0, weight=1)

        self.cleanup_selection_lbl = ctk.CTkLabel(
            footer, text="0 selected | 0 B",
            font=ctk.CTkFont(size=12), text_color=c["primary_text"],
        )
        self.cleanup_selection_lbl.grid(row=0, column=0, sticky="w", padx=16, pady=10)

        self.cleanup_select_all_b = ctk.CTkButton(
            footer, text="Select all safe", command=self._cleanup_select_all_safe,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=c["glass_panel"], hover_color=c["hover_state"],
            text_color=c["primary_text"], height=32, width=120, corner_radius=8,
            border_width=1, border_color=c["border"],
        )
        self.cleanup_select_all_b.grid(row=0, column=1, sticky="e", padx=(0, 8), pady=10)

        self.cleanup_clean_b = ctk.CTkButton(
            footer, text="Clean Selected", command=self._cleanup_clean,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=c["green_accent"], hover_color="#1CB884",
            text_color="white", height=32, width=140, corner_radius=8,
            state="disabled",
        )
        self.cleanup_clean_b.grid(row=0, column=2, sticky="e", padx=(0, 16), pady=10)

    def _cleanup_show_empty(self):
        for widget in self.cleanup_results.winfo_children():
            widget.destroy()
        ctk.CTkLabel(
            self.cleanup_results,
            text="Ready to scan\n\nScan to find safe system junk and developer leftovers.",
            font=ctk.CTkFont(size=13),
            text_color=self.theme.colors["muted_text"],
            justify="center",
        ).pack(pady=36)

    def _cleanup_show_no_results(self):
        for widget in self.cleanup_results.winfo_children():
            widget.destroy()
        ctk.CTkLabel(
            self.cleanup_results,
            text="No cleanup items found\n\nNothing eligible was found on this PC.",
            font=ctk.CTkFont(size=13),
            text_color=self.theme.colors["muted_text"],
            justify="center",
        ).pack(pady=36)

    def _cleanup_update_admin_ui(self):
        c = self.theme.colors
        if self._cleanup_admin:
            self.cleanup_admin_lbl.configure(
                text="\u25CF Administrator", text_color=c["green_accent"]
            )
            if self.cleanup_restart_btn is not None:
                self.cleanup_restart_btn.grid_remove()
        else:
            self.cleanup_admin_lbl.configure(
                text="\u25CF Standard user", text_color=c["orange_accent"]
            )
            if self.cleanup_restart_btn is not None:
                self.cleanup_restart_btn.grid()

    # --------------------------------------------------------- cleanup scan
    def _cleanup_scan(self):
        if self._cleanup_scanning or self._cleanup_cleaning:
            return
        self._cleanup_scanning = True
        self._cleanup_items = []
        self._cleanup_by_id = {}
        self._cleanup_selected.clear()
        self._cleanup_vars = {}
        self._cleanup_free_space = None
        self._cleanup_progress_queue = queue.Queue()
        self._cleanup_scan_b.configure(state="disabled")
        self._cleanup_cancel_b.configure(state="normal")
        self._cleanup_clean_b.configure(state="disabled")
        self._cleanup_select_all_b.configure(state="disabled")
        self.cleanup_progress.set(0)
        self.cleanup_status_lbl.configure(
            text="Scanning system and developer junk...",
            text_color=self.theme.colors["blue_accent"],
        )
        self.cleanup_notice_lbl.configure(text="")
        self._cleanup_cards["selected"].configure(text="0 B")
        self._cleanup_cards["free"].configure(text="\u2014")
        self._cleanup_cards["count"].configure(text="0")
        self.cleanup_table_title.configure(text="System Cleanup Items (0)")
        self._cleanup_show_empty()
        self._cleanup_start_poll()
        threading.Thread(target=self._cleanup_scan_thread, daemon=True).start()

    def _cleanup_cancel_scan(self):
        if not self._cleanup_scanning:
            return
        self.cleanup_ctrl.cancel_scan()
        self._cleanup_cancel_b.configure(state="disabled")
        self.cleanup_status_lbl.configure(
            text="Cancelling scan...", text_color=self.theme.colors["orange_accent"]
        )

    def _cleanup_scan_thread(self):
        try:
            result = self.cleanup_ctrl.scan(
                progress_callback=self._cleanup_progress_from_thread
            )
        except Exception as exc:
            result = {
                "error": str(exc), "items": [], "notices": [str(exc)],
                "scan_duration": 0.0, "admin": self.cleanup_ctrl.is_admin(),
                "free_space": self.cleanup_ctrl.get_free_space(),
            }
        self.after(0, self._cleanup_scan_done, result)

    def _cleanup_progress_from_thread(self, current, total, message):
        self._cleanup_progress_queue.put(("progress", current, total, message))

    def _cleanup_start_poll(self):
        if self._cleanup_poll_id is None:
            self._cleanup_poll_id = self.after(100, self._cleanup_poll)

    def _cleanup_poll(self):
        self._cleanup_poll_id = None
        while True:
            try:
                _kind, current, total, message = self._cleanup_progress_queue.get_nowait()
            except queue.Empty:
                break
            if total:
                self.cleanup_progress.set(max(0.0, min(1.0, float(current) / float(total))))
            self.cleanup_status_lbl.configure(
                text=message, text_color=self.theme.colors["blue_accent"]
            )
        if self._cleanup_scanning or self._cleanup_cleaning:
            self._cleanup_poll_id = self.after(100, self._cleanup_poll)

    def _cleanup_scan_done(self, result):
        self._cleanup_scanning = False
        self._cleanup_scan_b.configure(state="normal")
        self._cleanup_cancel_b.configure(state="disabled")
        self._cleanup_admin = bool(result.get("admin", self.cleanup_ctrl.is_admin()))
        self._cleanup_log_path = result.get("log_path") or self.cleanup_ctrl.get_log_path()
        self._cleanup_free_space = result.get("free_space")
        self._cleanup_update_admin_ui()

        self._cleanup_items = result.get("items", []) or []
        self._cleanup_by_id = {
            item.get("id"): item for item in self._cleanup_items if item.get("id")
        }
        self._cleanup_selected.clear()
        for item in self._cleanup_items:
            if (
                item.get("tier") == 1
                and item.get("default_selected")
                and item.get("selectable", True)
                and (self._cleanup_admin or not item.get("admin_required"))
            ):
                self._cleanup_selected.add(item.get("id"))

        self.cleanup_progress.set(1 if not result.get("error") else 0)
        notices = result.get("notices", []) or []
        if notices:
            self.cleanup_notice_lbl.configure(text="  |  ".join(notices[:4]))
        else:
            self.cleanup_notice_lbl.configure(text="")

        if result.get("error"):
            self.cleanup_status_lbl.configure(
                text="Scan failed: %s" % result.get("error"),
                text_color=self.theme.colors["red_accent"],
            )
        else:
            total_size = sum(int(item.get("size", 0) or 0) for item in self._cleanup_items)
            self.cleanup_status_lbl.configure(
                text="Scan complete: %d item(s), %s"
                % (len(self._cleanup_items), self.cleanup_ctrl.format_size(total_size)),
                text_color=self.theme.colors["green_accent"],
            )
        self._cleanup_render()
        self._cleanup_update_summary()

    # --------------------------------------------------------- cleanup render
    def _cleanup_render(self):
        for widget in self.cleanup_results.winfo_children():
            widget.destroy()
        self._cleanup_vars = {}
        self.cleanup_table_title.configure(
            text="System Cleanup Items (%s)" % format(len(self._cleanup_items), ",")
        )
        if not self._cleanup_items:
            self._cleanup_show_no_results()
            return
        for tier in (1, 2, 3, 4):
            tier_items = [
                item for item in self._cleanup_items if item.get("tier") == tier
            ]
            if not tier_items:
                continue
            self._create_cleanup_tier_header(tier, tier_items)
            for item in tier_items:
                self._create_cleanup_row(item)

    def _create_cleanup_tier_header(self, tier, items):
        c = self.theme.colors
        colors = {
            1: c["green_accent"],
            2: c["blue_accent"],
            3: c["orange_accent"],
            4: c["muted_text"],
        }
        labels = {
            1: "TIER 1 - Safe junk (pre-ticked)",
            2: "TIER 2 - Developer leftovers",
            3: "TIER 3 - System-level (admin only)",
            4: "TIER 4 - Report only (never deleted automatically)",
        }
        total = sum(int(item.get("size", 0) or 0) for item in items)
        frame = ctk.CTkFrame(self.cleanup_results, fg_color="transparent")
        frame.pack(fill="x", padx=8, pady=(10, 4))
        ctk.CTkLabel(
            frame, text=labels.get(tier, "Tier %d" % tier),
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=colors.get(tier, c["secondary_text"]),
        ).pack(side="left")
        ctk.CTkLabel(
            frame,
            text="%d item(s) | %s" % (len(items), self.cleanup_ctrl.format_size(total)),
            font=ctk.CTkFont(size=10), text_color=c["secondary_text"],
        ).pack(side="right")

    def _create_cleanup_row(self, item):
        c = self.theme.colors
        item_id = item.get("id")
        admin_locked = bool(item.get("admin_required")) and not self._cleanup_admin
        selectable = bool(item.get("selectable", True)) and not admin_locked
        row = ctk.CTkFrame(
            self.cleanup_results, fg_color=c["glass_panel"], corner_radius=6,
            border_width=1, border_color=c["border"],
        )
        row.pack(fill="x", padx=8, pady=2)
        row.grid_columnconfigure(1, weight=1)

        var = ctk.BooleanVar(value=item_id in self._cleanup_selected)
        self._cleanup_vars[item_id] = var
        checkbox = ctk.CTkCheckBox(
            row, text="", variable=var, width=20, height=20,
            command=lambda iid=item_id, v=var: self._cleanup_toggle_item(iid, v.get()),
            fg_color=c["blue_accent"], hover_color=c["hover_state"],
            border_color=c["border"],
            state="normal" if selectable else "disabled",
        )
        checkbox.grid(row=0, column=0, sticky="w", padx=(8, 4), pady=8)

        info = ctk.CTkFrame(row, fg_color="transparent")
        info.grid(row=0, column=1, sticky="ew", padx=4, pady=6)
        info.grid_columnconfigure(0, weight=1)
        name_color = c["primary_text"] if selectable else c["muted_text"]
        ctk.CTkLabel(
            info, text=item.get("name", "Item"),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=name_color, anchor="w",
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            info, text=item.get("path", ""),
            font=ctk.CTkFont(size=10), text_color=c["muted_text"], anchor="w",
        ).grid(row=1, column=0, sticky="w")
        ctk.CTkLabel(
            info, text=item.get("description", ""),
            font=ctk.CTkFont(size=10), text_color=c["secondary_text"],
            anchor="w", wraplength=620, justify="left",
        ).grid(row=2, column=0, sticky="w", pady=(1, 0))

        badges = ctk.CTkFrame(row, fg_color="transparent")
        badges.grid(row=0, column=2, sticky="e", padx=6, pady=6)
        if item.get("admin_required"):
            ctk.CTkLabel(
                badges, text="Admin", font=ctk.CTkFont(size=9, weight="bold"),
                text_color="white", fg_color=c["orange_accent"], corner_radius=4,
            ).pack(side="left", padx=2)
        if item.get("recoverable"):
            ctk.CTkLabel(
                badges, text="Recycle", font=ctk.CTkFont(size=9, weight="bold"),
                text_color="white", fg_color=c["green_accent"], corner_radius=4,
            ).pack(side="left", padx=2)
        if not item.get("selectable", True):
            ctk.CTkLabel(
                badges, text="Report", font=ctk.CTkFont(size=9, weight="bold"),
                text_color="white", fg_color=c["muted_text"], corner_radius=4,
            ).pack(side="left", padx=2)
        if item.get("delete_mode") == "command":
            ctk.CTkLabel(
                badges, text="Tool", font=ctk.CTkFont(size=9, weight="bold"),
                text_color="white", fg_color=c["blue_accent"], corner_radius=4,
            ).pack(side="left", padx=2)

        ctk.CTkLabel(
            row, text=self.cleanup_ctrl.format_size(item.get("size", 0)),
            font=ctk.CTkFont(size=12), text_color=c["primary_text"],
        ).grid(row=0, column=3, sticky="e", padx=8, pady=6)

        actions = ctk.CTkFrame(row, fg_color="transparent")
        actions.grid(row=0, column=4, sticky="e", padx=(0, 8), pady=6)
        metadata = item.get("metadata") or {}
        action = metadata.get("action")
        if action == "virtual_memory":
            ctk.CTkButton(
                actions, text="Virtual Memory", width=104, height=24,
                font=ctk.CTkFont(size=10),
                command=lambda it=item: self._cleanup_open_location(it),
            ).pack(side="left", padx=2)
        elif action == "open_location":
            ctk.CTkButton(
                actions, text="Open location", width=90, height=24,
                font=ctk.CTkFont(size=10),
                command=lambda it=item: self._cleanup_open_location(it),
            ).pack(side="left", padx=2)
        if metadata.get("allow_recycle"):
            ctk.CTkButton(
                actions, text="Open in Explorer", width=110, height=24,
                font=ctk.CTkFont(size=10),
                command=lambda it=item: self._cleanup_open_location(it),
            ).pack(side="left", padx=2)
            ctk.CTkButton(
                actions, text="Send to Recycle Bin", width=120, height=24,
                font=ctk.CTkFont(size=10), fg_color=c["red_accent"],
                hover_color="#D06565", text_color="white",
                command=lambda it=item: self._cleanup_recycle_item(it),
            ).pack(side="left", padx=2)

        if admin_locked:
            tip = "Run PC-Toolbox as administrator to enable this item."
            for widget in (row, checkbox, info):
                self._cleanup_attach_tooltip(widget, tip)
        if item.get("warning"):
            self._cleanup_attach_tooltip(row, item.get("warning"))

    def _cleanup_toggle_item(self, item_id, selected):
        if selected:
            self._cleanup_selected.add(item_id)
        else:
            self._cleanup_selected.discard(item_id)
        self._cleanup_update_summary()

    def _cleanup_select_all_safe(self):
        if self._cleanup_scanning or self._cleanup_cleaning:
            return
        count = 0
        for item in self._cleanup_items:
            if item.get("tier") != 1 or not item.get("selectable", True):
                continue
            if item.get("admin_required") and not self._cleanup_admin:
                continue
            item_id = item.get("id")
            self._cleanup_selected.add(item_id)
            var = self._cleanup_vars.get(item_id)
            if var is not None:
                var.set(True)
            count += 1
        self.cleanup_status_lbl.configure(
            text="Selected %d safe Tier 1 item(s)" % count,
            text_color=self.theme.colors["green_accent"],
        )
        self._cleanup_update_summary()

    def _cleanup_update_summary(self):
        selected_items = [
            self._cleanup_by_id[item_id]
            for item_id in self._cleanup_selected
            if item_id in self._cleanup_by_id
        ]
        total = sum(int(item.get("size", 0) or 0) for item in selected_items)
        self._cleanup_cards["selected"].configure(
            text=self.cleanup_ctrl.format_size(total)
        )
        self._cleanup_cards["count"].configure(
            text=format(len(self._cleanup_items), ",")
        )
        if self._cleanup_free_space is None:
            self._cleanup_cards["free"].configure(text="\u2014")
        else:
            self._cleanup_cards["free"].configure(
                text=self.cleanup_ctrl.format_size(self._cleanup_free_space)
            )
        self.cleanup_selection_lbl.configure(
            text="%d selected | %s"
            % (len(selected_items), self.cleanup_ctrl.format_size(total))
        )
        busy = self._cleanup_scanning or self._cleanup_cleaning
        self.cleanup_clean_b.configure(
            state="normal" if selected_items and not busy else "disabled",
            text="Run Dry Run" if self._cleanup_dry_run.get() else "Clean Selected",
        )
        self.cleanup_select_all_b.configure(
            state="normal" if self._cleanup_items and not busy else "disabled"
        )

    # --------------------------------------------------------- cleanup clean
    def _cleanup_clean(self):
        if self._cleanup_scanning or self._cleanup_cleaning:
            return
        items = [
            self._cleanup_by_id[item_id]
            for item_id in self._cleanup_selected
            if item_id in self._cleanup_by_id
        ]
        if not items:
            return
        dry_run = bool(self._cleanup_dry_run.get())
        self._cleanup_confirm_dialog(
            items, dry_run, lambda: self._cleanup_begin_clean(items, dry_run)
        )

    def _cleanup_confirm_dialog(self, items, dry_run, on_confirm):
        c = self.theme.colors
        dialog = ctk.CTkToplevel(self)
        dialog.title("Confirm Dry Run" if dry_run else "Confirm System Cleanup")
        dialog.geometry("700x560")
        dialog.transient(self.master)
        dialog.grab_set()
        dialog.configure(fg_color=c["deep_background"])

        ctk.CTkLabel(
            dialog, text="Dry run - nothing will be deleted" if dry_run else "Review cleanup selection",
            font=ctk.CTkFont(size=18, weight="bold"), text_color=c["primary_text"],
        ).pack(pady=(18, 6))
        total = sum(int(item.get("size", 0) or 0) for item in items)
        ctk.CTkLabel(
            dialog,
            text="%d item(s), up to %s" % (len(items), self.cleanup_ctrl.format_size(total)),
            font=ctk.CTkFont(size=12), text_color=c["secondary_text"],
        ).pack(pady=(0, 8))
        if any(item.get("tier") == 3 for item in items) and not dry_run:
            ctk.CTkLabel(
                dialog, text="Tier 3 items will ask for an individual confirmation.",
                font=ctk.CTkFont(size=11), text_color=c["orange_accent"],
            ).pack(pady=(0, 8))

        textbox = ctk.CTkTextbox(
            dialog, fg_color=c["glass_panel"], text_color=c["primary_text"],
            border_width=1, border_color=c["border"],
        )
        textbox.pack(fill="both", expand=True, padx=22, pady=(0, 12))
        lines = []
        for tier in (1, 2, 3, 4):
            tier_items = [item for item in items if item.get("tier") == tier]
            if not tier_items:
                continue
            lines.append("TIER %d" % tier)
            for item in tier_items:
                lines.append(
                    "  [%s] %s  (%s)"
                    % (
                        item.get("category_name", ""),
                        item.get("path", ""),
                        self.cleanup_ctrl.format_size(item.get("size", 0)),
                    )
                )
            lines.append("")
        textbox.insert("0.0", "\n".join(lines))
        textbox.configure(state="disabled")

        buttons = ctk.CTkFrame(dialog, fg_color="transparent")
        buttons.pack(fill="x", padx=22, pady=(0, 16))

        def confirm():
            dialog.destroy()
            on_confirm()

        ctk.CTkButton(
            buttons, text="Cancel", command=dialog.destroy,
            fg_color="transparent", hover_color=c["hover_state"],
            text_color=c["secondary_text"], height=32, corner_radius=8,
        ).pack(side="left")
        ctk.CTkButton(
            buttons, text="Run Dry Run" if dry_run else "Clean Selected",
            command=confirm,
            fg_color=c["blue_accent"] if dry_run else c["red_accent"],
            hover_color="#1570D6" if dry_run else "#D06565",
            text_color="white", height=32, corner_radius=8,
        ).pack(side="left", padx=8)

    def _cleanup_confirm_tier3(self, item):
        import tkinter.messagebox as mb

        warning = item.get("warning") or "This system-level action may not be reversible."
        return mb.askyesno(
            "Confirm Tier 3 action",
            "%s\n\n%s\n\nDo you want to run this action?" % (item.get("name"), warning),
        )

    def _cleanup_begin_clean(self, items, dry_run):
        if not items:
            return
        confirmed = []
        for item in items:
            if item.get("tier") == 3 and not dry_run:
                if not self._cleanup_confirm_tier3(item):
                    continue
            confirmed.append(item)
        if not confirmed:
            self.cleanup_status_lbl.configure(
                text="Cleanup cancelled", text_color=self.theme.colors["orange_accent"]
            )
            return

        self._cleanup_cleaning = True
        self._cleanup_progress_queue = queue.Queue()
        self._cleanup_scan_b.configure(state="disabled")
        self._cleanup_cancel_b.configure(state="disabled")
        self._cleanup_clean_b.configure(state="disabled")
        self._cleanup_select_all_b.configure(state="disabled")
        self.cleanup_progress.set(0)
        self.cleanup_status_lbl.configure(
            text="Dry run in progress..." if dry_run else "Cleanup in progress...",
            text_color=self.theme.colors["blue_accent"],
        )
        self.cleanup_notice_lbl.configure(text="")
        self._cleanup_start_poll()
        threading.Thread(
            target=self._cleanup_clean_thread,
            args=(confirmed, dry_run),
            daemon=True,
        ).start()

    def _cleanup_clean_thread(self, items, dry_run):
        try:
            result = self.cleanup_ctrl.clean(
                items,
                dry_run=dry_run,
                progress_callback=self._cleanup_progress_from_thread,
            )
        except Exception as exc:
            result = {
                "error": str(exc), "removed": [], "would_remove": [],
                "failed": [], "skipped": [], "recycled": [],
                "bytes_freed": 0, "bytes_estimated": 0, "bytes_recycled": 0,
                "bytes_by_category": {}, "recycled_by_category": {},
                "estimated_by_category": {}, "dry_run": dry_run,
                "free_before": None, "free_after": self.cleanup_ctrl.get_free_space(),
            }
        self.after(0, self._cleanup_clean_done, result)

    def _cleanup_clean_done(self, result):
        self._cleanup_cleaning = False
        self._cleanup_scan_b.configure(state="normal")
        self._cleanup_cancel_b.configure(state="disabled")
        self._cleanup_free_space = result.get("free_after")
        if result.get("error"):
            self.cleanup_progress.set(0)
            self.cleanup_status_lbl.configure(
                text="Cleanup failed: %s" % result.get("error"),
                text_color=self.theme.colors["red_accent"],
            )
            self._cleanup_update_summary()
            import tkinter.messagebox as mb
            mb.showerror("System Cleanup", "Cleanup failed:\n%s" % result.get("error"))
            return

        if not result.get("dry_run"):
            removed_ids = {
                entry.get("id") for entry in result.get("removed", []) if entry.get("id")
            }
            if removed_ids:
                self._cleanup_items = [
                    item for item in self._cleanup_items
                    if item.get("id") not in removed_ids
                ]
                self._cleanup_by_id = {
                    item.get("id"): item for item in self._cleanup_items if item.get("id")
                }
                for item_id in removed_ids:
                    self._cleanup_selected.discard(item_id)

        self.cleanup_progress.set(1)
        if result.get("dry_run"):
            message = "Dry run complete: %s would be freed" % self.cleanup_ctrl.format_size(
                result.get("bytes_estimated", 0)
            )
        else:
            permanent = int(result.get("bytes_freed", 0) or 0)
            recycled = int(result.get("bytes_recycled", 0) or 0)
            parts = []
            if permanent:
                parts.append("%s permanently freed" % self.cleanup_ctrl.format_size(permanent))
            if recycled:
                parts.append("%s moved to Recycle Bin" % self.cleanup_ctrl.format_size(recycled))
            message = "Cleanup complete: " + (" | ".join(parts) if parts else "nothing removed")
        self.cleanup_status_lbl.configure(
            text=message, text_color=self.theme.colors["green_accent"]
        )
        self._cleanup_render()
        self._cleanup_update_summary()
        self._cleanup_show_summary(result)

    def _cleanup_show_summary(self, result):
        c = self.theme.colors
        dry_run = bool(result.get("dry_run"))
        dialog = ctk.CTkToplevel(self)
        dialog.title("Dry Run Summary" if dry_run else "Cleanup Summary")
        dialog.geometry("720x600")
        dialog.transient(self.master)
        dialog.grab_set()
        dialog.configure(fg_color=c["deep_background"])

        ctk.CTkLabel(
            dialog, text="Dry Run Complete" if dry_run else "Cleanup Complete",
            font=ctk.CTkFont(size=18, weight="bold"), text_color=c["primary_text"],
        ).pack(pady=(18, 6))

        amount = result.get("bytes_estimated", 0) if dry_run else result.get("bytes_freed", 0)
        recycled = int(result.get("bytes_recycled", 0) or 0)
        if dry_run:
            amount_text = "Would free: %s" % self.cleanup_ctrl.format_size(amount)
        elif recycled:
            parts = []
            if amount:
                parts.append("Permanently freed: %s" % self.cleanup_ctrl.format_size(amount))
            parts.append("Moved to Recycle Bin: %s" % self.cleanup_ctrl.format_size(recycled))
            amount_text = " | ".join(parts)
        else:
            amount_text = "Space freed: %s" % self.cleanup_ctrl.format_size(amount)
        ctk.CTkLabel(
            dialog,
            text=amount_text,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=c["green_accent"],
        ).pack(pady=(0, 2))

        before = result.get("free_before")
        after = result.get("free_after")
        free_text = "C: free space: %s \u2192 %s" % (
            self.cleanup_ctrl.format_size(before) if before is not None else "Unknown",
            self.cleanup_ctrl.format_size(after) if after is not None else "Unknown",
        )
        ctk.CTkLabel(
            dialog, text=free_text, font=ctk.CTkFont(size=11),
            text_color=c["secondary_text"],
        ).pack(pady=(0, 8))

        textbox = ctk.CTkTextbox(
            dialog, fg_color=c["glass_panel"], text_color=c["primary_text"],
            border_width=1, border_color=c["border"],
        )
        textbox.pack(fill="both", expand=True, padx=22, pady=(0, 12))

        lines = ["By category:"]
        by_category = result.get("estimated_by_category" if dry_run else "bytes_by_category", {}) or {}
        if by_category:
            for name in sorted(by_category):
                lines.append("  %s: %s" % (name, self.cleanup_ctrl.format_size(by_category[name])))
        else:
            lines.append("  No category totals reported.")

        if not dry_run:
            recycled_by_category = result.get("recycled_by_category", {}) or {}
            if any(recycled_by_category.values()):
                lines.append("")
                lines.append("Moved to Recycle Bin by category:")
                for name in sorted(recycled_by_category):
                    if recycled_by_category[name]:
                        lines.append(
                            "  %s: %s"
                            % (name, self.cleanup_ctrl.format_size(recycled_by_category[name]))
                        )

        removed = result.get("would_remove", []) if dry_run else result.get("removed", [])
        lines.append("")
        lines.append("%s (%d):" % ("Would remove" if dry_run else "Removed", len(removed)))
        for entry in removed[:100]:
            marker = " [Recycle Bin]" if entry.get("recycled") else ""
            lines.append(
                "  %s  (%s)%s"
                % (entry.get("path", ""), self.cleanup_ctrl.format_size(entry.get("size", 0)), marker)
            )
        if len(removed) > 100:
            lines.append("  ... and %d more" % (len(removed) - 100))

        failed = result.get("failed", []) or []
        lines.append("")
        lines.append("Failed (%d):" % len(failed))
        for entry in failed[:100]:
            lines.append("  %s - %s" % (entry.get("path", ""), entry.get("reason", "")))
        if len(failed) > 100:
            lines.append("  ... and %d more" % (len(failed) - 100))

        skipped = result.get("skipped", []) or []
        lines.append("")
        lines.append("Skipped (%d):" % len(skipped))
        for entry in skipped[:100]:
            lines.append("  %s - %s" % (entry.get("path", ""), entry.get("reason", "")))
        if len(skipped) > 100:
            lines.append("  ... and %d more" % (len(skipped) - 100))

        log_path = result.get("log_path") or self.cleanup_ctrl.get_log_path()
        lines.append("")
        lines.append("Action log: %s" % (log_path or "Unavailable"))
        textbox.insert("0.0", "\n".join(lines))
        textbox.configure(state="disabled")

        buttons = ctk.CTkFrame(dialog, fg_color="transparent")
        buttons.pack(fill="x", padx=22, pady=(0, 16))
        ctk.CTkButton(
            buttons, text="Open log", command=self._cleanup_open_log,
            fg_color=c["glass_panel"], hover_color=c["hover_state"],
            text_color=c["primary_text"], height=32, corner_radius=8,
        ).pack(side="left")
        if not dry_run and result.get("recycled"):
            ctk.CTkButton(
                buttons, text="Empty Recycle Bin now",
                command=lambda: self._cleanup_empty_recycle_bin(dialog),
                fg_color=c["orange_accent"], hover_color="#C07020",
                text_color="white", height=32, corner_radius=8,
            ).pack(side="left", padx=8)
        ctk.CTkButton(
            buttons, text="Close", command=dialog.destroy,
            fg_color=c["blue_accent"], hover_color="#1570D6",
            text_color="white", height=32, corner_radius=8,
        ).pack(side="left", padx=8)

    def _cleanup_empty_recycle_bin(self, dialog):
        import tkinter.messagebox as mb

        if self._cleanup_scanning or self._cleanup_cleaning:
            return
        if not mb.askyesno(
            "Empty Recycle Bin",
            "Permanently delete everything currently in the Recycle Bin on all drives?\n\n"
            "This cannot be undone.",
        ):
            return
        dialog.destroy()
        self._cleanup_cleaning = True
        self.cleanup_status_lbl.configure(
            text="Emptying Recycle Bin...", text_color=self.theme.colors["blue_accent"]
        )
        self._cleanup_update_summary()
        threading.Thread(target=self._cleanup_empty_recycle_thread, daemon=True).start()

    def _cleanup_empty_recycle_thread(self):
        try:
            result = self.cleanup_ctrl.empty_recycle_bin()
        except Exception as exc:
            result = {
                "error": str(exc),
                "bytes_freed": 0,
                "free_before": None,
                "free_after": self.cleanup_ctrl.get_free_space(),
            }
        self.after(0, self._cleanup_empty_recycle_done, result)

    def _cleanup_empty_recycle_done(self, result):
        self._cleanup_cleaning = False
        import tkinter.messagebox as mb

        self._cleanup_free_space = result.get("free_after")
        if result.get("error"):
            self.cleanup_status_lbl.configure(
                text="Could not empty Recycle Bin: %s" % result.get("error"),
                text_color=self.theme.colors["red_accent"],
            )
            mb.showerror("Empty Recycle Bin", result.get("error"))
            self._cleanup_update_summary()
            return

        before = result.get("free_before")
        after = result.get("free_after")
        message = "Recycle Bin emptied: %s permanently freed\n\nC: free space: %s \u2192 %s" % (
            self.cleanup_ctrl.format_size(result.get("bytes_freed", 0)),
            self.cleanup_ctrl.format_size(before) if before is not None else "Unknown",
            self.cleanup_ctrl.format_size(after) if after is not None else "Unknown",
        )
        self.cleanup_status_lbl.configure(
            text="Recycle Bin emptied: %s freed"
            % self.cleanup_ctrl.format_size(result.get("bytes_freed", 0)),
            text_color=self.theme.colors["green_accent"],
        )
        self._cleanup_update_summary()
        mb.showinfo("Empty Recycle Bin", message)

    # --------------------------------------------------------- report actions
    def _get_recycle_bin_info(self) -> tuple[int, int]:
        """Return (current_size_bytes, max_size_bytes) for Recycle Bin on C: drive."""
        if os.name != "nt":
            return 0, 0
        try:
            shell32 = ctypes.windll.shell32
            info = _RecycleBinInfo()
            info.cbSize = ctypes.sizeof(info)
            if shell32.SHQueryRecycleBinW(ctypes.c_wchar_p("C:\\"), ctypes.byref(info)) == 0:
                current = int(info.i64Size)
                max_size = self._get_recycle_bin_max_size()
                return current, max_size
        except Exception:
            pass
        return 0, 0

    @staticmethod
    def _get_recycle_bin_max_size() -> int:
        """Read the Recycle Bin max capacity (bytes) from the BitBucket registry.

        Falls back to 10 GB when the registry value is unavailable.
        """
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\BitBucket\Volume",
            )
            try:
                for i in range(10):
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                    except OSError:
                        break
                    try:
                        subkey = winreg.OpenKey(key, subkey_name)
                    except OSError:
                        continue
                    try:
                        value, _ = winreg.QueryValueEx(subkey, "MaxCapacity")
                    except OSError:
                        continue
                    finally:
                        try:
                            winreg.CloseKey(subkey)
                        except OSError:
                            pass
                    try:
                        mb = int(value)
                        if mb > 0:
                            return mb * 1024 * 1024
                    except (ValueError, TypeError):
                        continue
            finally:
                winreg.CloseKey(key)
        except Exception:
            pass
        return 10 * 1024 ** 3  # 10 GB fallback

    def _cleanup_recycle_item(self, item):
        if self._cleanup_scanning or self._cleanup_cleaning:
            return
        import tkinter.messagebox as mb

        path = item.get("path", "")
        size = int(item.get("size", 0) or 0)
        size_str = self.cleanup_ctrl.format_size(size)

        # Query Recycle Bin current size and max capacity on C:
        rb_current, rb_max = self._get_recycle_bin_info()
        rb_current_str = self.cleanup_ctrl.format_size(rb_current) if rb_current else "Unknown"
        rb_max_str = self.cleanup_ctrl.format_size(rb_max) if rb_max else "Unknown"

        message = (
            "Send this item to the Recycle Bin?\n\n"
            "Path: %s\n"
            "Size: %s\n"
            "Recycle Bin (C:) currently contains: %s\n"
            "Recycle Bin (C:) maximum capacity: %s\n\n"
            % (path, size_str, rb_current_str, rb_max_str)
        )
        # Warn if item exceeds the Recycle Bin's max capacity
        if rb_max and size > rb_max:
            message += (
                "⚠ Warning: This item (%s) is larger than the Recycle Bin's maximum "
                "capacity (%s). Windows may permanently delete it instead of moving it "
                "to the Recycle Bin.\n\n"
                % (size_str, rb_max_str)
            )
        # Warn if item is larger than the drive's free space
        free_space = self.cleanup_ctrl.get_free_space()
        if free_space and size > free_space:
            message += (
                "⚠ Warning: This item (%s) is larger than the C: drive's free space "
                "(%s). Windows may permanently delete it instead of moving it to the "
                "Recycle Bin.\n\n"
                % (size_str, self.cleanup_ctrl.format_size(free_space))
            )

        if not mb.askyesno("Send to Recycle Bin", message):
            return
        self._cleanup_cleaning = True
        self.cleanup_status_lbl.configure(
            text="Sending to Recycle Bin...", text_color=self.theme.colors["blue_accent"]
        )
        self._cleanup_update_summary()
        threading.Thread(
            target=self._cleanup_recycle_thread, args=(item,), daemon=True
        ).start()

    def _cleanup_recycle_thread(self, item):
        try:
            result = self.cleanup_ctrl.recycle_report_item(item)
        except Exception as exc:
            result = {"error": str(exc), "removed": []}
        self.after(0, self._cleanup_recycle_done, item, result)

    def _cleanup_recycle_done(self, item, result):
        self._cleanup_cleaning = False
        import tkinter.messagebox as mb

        if result.get("error"):
            self.cleanup_status_lbl.configure(
                text="Could not recycle item: %s" % result.get("error"),
                text_color=self.theme.colors["red_accent"],
            )
            mb.showerror("Send to Recycle Bin", result.get("error"))
        elif result.get("removed"):
            item_id = item.get("id")
            self._cleanup_items = [
                existing for existing in self._cleanup_items
                if existing.get("id") != item_id
            ]
            self._cleanup_by_id.pop(item_id, None)
            self._cleanup_selected.discard(item_id)
            self._cleanup_free_space = result.get("free_after")
            self.cleanup_status_lbl.configure(
                text="Item sent to Recycle Bin", text_color=self.theme.colors["green_accent"]
            )
            self._cleanup_render()
            self._cleanup_update_summary()
            self._cleanup_show_summary(result)
            return
        else:
            reason = ""
            if result.get("skipped"):
                reason = result["skipped"][0].get("reason", "")
            elif result.get("failed"):
                reason = result["failed"][0].get("reason", "")
            self.cleanup_status_lbl.configure(
                text="Item was not removed: %s" % reason,
                text_color=self.theme.colors["orange_accent"],
            )
        self._cleanup_update_summary()

    def _cleanup_open_location(self, item):
        import subprocess

        metadata = item.get("metadata") or {}
        if metadata.get("action") == "virtual_memory":
            try:
                subprocess.Popen(
                    ["SystemPropertiesPerformance.exe", "/pagefile"],
                    shell=False,
                )
            except OSError:
                subprocess.Popen(
                    ["rundll32.exe", "shell32.dll,Control_RunDLL", "sysdm.cpl,,3"],
                    shell=False,
                )
            return

        path = item.get("path", "")
        if not path or not os.path.exists(path):
            import tkinter.messagebox as mb
            mb.showinfo("Open location", "The path no longer exists.")
            return
        try:
            if os.path.isdir(path):
                os.startfile(path)
            else:
                subprocess.Popen(
                    ["explorer.exe", "/select,", path],
                    shell=False,
                )
        except OSError as exc:
            import tkinter.messagebox as mb
            mb.showerror("Open location", str(exc))

    def _cleanup_open_log(self):
        if not self.cleanup_ctrl.open_log():
            import tkinter.messagebox as mb
            mb.showinfo("Action log", "No action log is available yet.")

    def _cleanup_open_options(self):
        c = self.theme.colors
        settings = self.cleanup_ctrl.get_settings()
        dialog = ctk.CTkToplevel(self)
        dialog.title("System Cleanup Options")
        dialog.geometry("520x430")
        dialog.transient(self.master)
        dialog.grab_set()
        dialog.configure(fg_color=c["deep_background"])

        ctk.CTkLabel(
            dialog, text="System Cleanup Options",
            font=ctk.CTkFont(size=18, weight="bold"), text_color=c["primary_text"],
        ).pack(pady=(18, 6))
        ctk.CTkLabel(
            dialog,
            text="Scans stay inside your user profile and known developer folders.",
            font=ctk.CTkFont(size=11), text_color=c["secondary_text"],
            wraplength=460,
        ).pack(pady=(0, 12))

        node_var = ctk.BooleanVar(
            value=bool(settings.get("system_cleanup_scan_node_modules", False))
        )
        ctk.CTkCheckBox(
            dialog, text="Scan for stale node_modules folders",
            variable=node_var, fg_color=c["blue_accent"],
            hover_color=c["hover_state"], text_color=c["primary_text"],
        ).pack(anchor="w", padx=24, pady=5)

        days_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        days_frame.pack(anchor="w", padx=24, pady=5)
        ctk.CTkLabel(
            days_frame, text="Only if not modified for (days):",
            font=ctk.CTkFont(size=12), text_color=c["secondary_text"],
        ).pack(side="left")
        days_var = ctk.StringVar(
            value=str(settings.get("system_cleanup_stale_node_modules_days", 90))
        )
        ctk.CTkEntry(
            days_frame, textvariable=days_var, width=80, height=28,
            fg_color=c["secondary_panel"], text_color=c["primary_text"],
            border_width=1, border_color=c["border"],
        ).pack(side="left", padx=8)

        docker_var = ctk.BooleanVar(
            value=bool(settings.get("system_cleanup_enable_docker_prune", False))
        )
        ctk.CTkCheckBox(
            dialog, text="Offer Docker system prune (extra confirmation required)",
            variable=docker_var, fg_color=c["blue_accent"],
            hover_color=c["hover_state"], text_color=c["primary_text"],
        ).pack(anchor="w", padx=24, pady=5)

        threshold_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        threshold_frame.pack(anchor="w", padx=24, pady=5)
        ctk.CTkLabel(
            threshold_frame, text="Large file threshold (MB):",
            font=ctk.CTkFont(size=12), text_color=c["secondary_text"],
        ).pack(side="left")
        threshold_var = ctk.StringVar(
            value=str(settings.get("system_cleanup_large_file_threshold_mb", 500))
        )
        ctk.CTkEntry(
            threshold_frame, textvariable=threshold_var, width=80, height=28,
            fg_color=c["secondary_panel"], text_color=c["primary_text"],
            border_width=1, border_color=c["border"],
        ).pack(side="left", padx=8)

        def apply():
            try:
                days = max(1, int(days_var.get().strip() or "90"))
            except ValueError:
                days = 90
            try:
                threshold = max(1, int(threshold_var.get().strip() or "500"))
            except ValueError:
                threshold = 500
            self.cleanup_ctrl.update_settings(
                {
                    "system_cleanup_scan_node_modules": bool(node_var.get()),
                    "system_cleanup_stale_node_modules_days": days,
                    "system_cleanup_enable_docker_prune": bool(docker_var.get()),
                    "system_cleanup_large_file_threshold_mb": threshold,
                }
            )
            dialog.destroy()
            self.cleanup_status_lbl.configure(
                text="Cleanup options saved. Scan again to apply them.",
                text_color=self.theme.colors["green_accent"],
            )

        buttons = ctk.CTkFrame(dialog, fg_color="transparent")
        buttons.pack(fill="x", padx=24, pady=16)
        ctk.CTkButton(
            buttons, text="Cancel", command=dialog.destroy,
            fg_color="transparent", hover_color=c["hover_state"],
            text_color=c["secondary_text"], height=32, corner_radius=8,
        ).pack(side="left")
        ctk.CTkButton(
            buttons, text="Save", command=apply,
            fg_color=c["blue_accent"], hover_color="#1570D6",
            text_color="white", height=32, corner_radius=8,
        ).pack(side="left", padx=8)

    def _cleanup_restart_admin(self):
        import ctypes
        import subprocess
        import tkinter.messagebox as mb

        try:
            script = os.path.abspath(sys.argv[0])
            params = '"%s"' % script
            result = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, params, None, 1
            )
            if result > 32:
                self.winfo_toplevel().destroy()
            else:
                mb.showerror(
                    "Restart as administrator",
                    "Windows did not start the elevated instance (code %s)." % result,
                )
        except Exception as exc:
            mb.showerror("Restart as administrator", str(exc))

    def _cleanup_attach_tooltip(self, widget, text):
        state = {"window": None}

        def show(_event):
            if state["window"] is not None:
                return
            try:
                window = ctk.CTkToplevel(widget)
                window.wm_overrideredirect(True)
                window.attributes("-topmost", True)
                window.wm_geometry(
                    "+%d+%d" % (widget.winfo_rootx() + 16, widget.winfo_rooty() + 20)
                )
                ctk.CTkLabel(
                    window, text=text, font=ctk.CTkFont(size=10),
                    fg_color=self.theme.colors["secondary_panel"],
                    text_color=self.theme.colors["primary_text"],
                    corner_radius=4, wraplength=320, justify="left",
                ).pack(padx=8, pady=4)
                state["window"] = window
            except Exception:
                state["window"] = None

        def hide(_event):
            window = state.get("window")
            if window is not None:
                try:
                    window.destroy()
                except Exception:
                    pass
            state["window"] = None

        widget.bind("<Enter>", show, add="+")
        widget.bind("<Leave>", hide, add="+")

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
