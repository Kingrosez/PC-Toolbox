"""Uninstaller view for PC-Toolbox - full implementation."""

import customtkinter as ctk
import threading
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

import sys
sys.path.insert(0, 'd:/Windows app/PC-Toolbox')


class UninstallerView(ctk.CTkFrame):
    """Uninstaller screen with discovery, filtering, sorting, pagination, details."""

    def __init__(self, master, navigation):
        super().__init__(master, fg_color=master.theme.colors["deep_background"])
        self.theme = master.theme
        self.navigation = navigation

        self.act = getattr(navigation, "activity_service", None)
        self.ctrl = getattr(navigation, "uninstaller_controller", None)
        if not self.act or not self.ctrl:
            from services.activity_service import ActivityService
            from controllers.uninstaller_controller import UninstallerController
            self.act = self.act or ActivityService()
            self.ctrl = self.ctrl or UninstallerController(self.act)

        self._scanning = False
        self._scan_th = None
        self._apps = []
        self._filtered = []
        self._selected_ids = set()
        self._selected_app = None
        self._search_text = ""
        self._category = "All Categories"
        self._size_filter = "All Sizes"
        self._publisher = "All Publishers"
        self._sort_by = "Name (A-Z)"
        self._page = 1
        self._per_page = 25
        self._last_updated = None

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._setup_ui()
        self._idle()
        self._start_scan()

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
        self._create_summary_cards()
        self._create_toolbar()
        self._create_table_panel()
        self._create_footer()

    def _create_header(self):
        header = ctk.CTkFrame(self.scroll, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 16))
        header.grid_columnconfigure(1, weight=1)

        left = ctk.CTkFrame(header, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            left, text="\U0001F4E6", font=ctk.CTkFont(size=30),
            text_color=self.theme.colors["blue_accent"],
        ).grid(row=0, column=0, sticky="w", padx=(0, 12))

        ctk.CTkLabel(
            left, text="Uninstaller", font=ctk.CTkFont(size=28, weight="bold"),
            text_color=self.theme.colors["primary_text"],
        ).grid(row=0, column=1, sticky="w")

        ctk.CTkLabel(
            left, text="Manage installed applications and free up disk space",
            font=ctk.CTkFont(size=13),
            text_color=self.theme.colors["secondary_text"],
        ).grid(row=1, column=1, sticky="w", pady=(2, 0))

        right = ctk.CTkFrame(header, fg_color="transparent")
        right.grid(row=0, column=1, sticky="e")

        self.online_lbl = ctk.CTkLabel(
            right, text="System Online  \u25CF",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=self.theme.colors["green_accent"],
        )
        self.online_lbl.grid(row=0, column=0, sticky="e")

        self.updated_lbl = ctk.CTkLabel(
            right, text="Last updated: --",
            font=ctk.CTkFont(size=11),
            text_color=self.theme.colors["muted_text"],
        )
        self.updated_lbl.grid(row=1, column=0, sticky="e", pady=(2, 0))

        self.refresh_btn = ctk.CTkButton(
            right, text="Refresh", command=self._start_scan,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=self.theme.colors["glass_panel"],
            border_width=1, border_color=self.theme.colors["border"],
            hover_color=self.theme.colors["hover_state"],
            text_color=self.theme.colors["primary_text"],
            height=30, width=80, corner_radius=6,
        )
        self.refresh_btn.grid(row=0, column=1, rowspan=2, sticky="e", padx=(16, 0))

    def _create_summary_cards(self):
        cards = ctk.CTkFrame(self.scroll, fg_color="transparent")
        cards.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 16))
        for i in range(4):
            cards.grid_columnconfigure(i, weight=1)

        defs = [
            ("\U0001F4E6", "Installed Applications", "total_count", self.theme.colors["blue_accent"]),
            ("\U0001F4BE", "Total Size", "total_size", self.theme.colors["purple_accent"]),
            ("\U0001F4C8", "Large Applications (> 1 GB)", "large_count", self.theme.colors["green_accent"]),
            ("\u23F1", "Recently Installed", "recent_count", self.theme.colors["orange_accent"]),
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
            val = ctk.CTkLabel(
                card, text="\u2014", font=ctk.CTkFont(size=26, weight="bold"),
                text_color=self.theme.colors["primary_text"],
            )
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

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *a: self._apply_filters())
        search_entry = ctk.CTkEntry(
            toolbar, textvariable=self.search_var,
            placeholder_text="Search applications...",
            font=ctk.CTkFont(size=12),
            fg_color=self.theme.colors["secondary_panel"],
            border_width=1, border_color=self.theme.colors["border"],
            text_color=self.theme.colors["primary_text"],
            height=32, width=220, corner_radius=8,
        )
        search_entry.grid(row=0, column=0, padx=16, pady=12, sticky="w")

        self.category_var = ctk.StringVar(value="All Categories")
        self.category_menu = ctk.CTkOptionMenu(
            toolbar, variable=self.category_var,
            values=["All Categories", "Browsers", "Development", "Utilities", "Security", "Other"],
            command=lambda v: self._set_filter("category", v),
            font=ctk.CTkFont(size=12),
            fg_color=self.theme.colors["secondary_panel"],
            button_color=self.theme.colors["border"],
            text_color=self.theme.colors["primary_text"],
            height=32, corner_radius=8,
        )
        self.category_menu.grid(row=0, column=1, padx=6, pady=12)

        self.size_var = ctk.StringVar(value="All Sizes")
        self.size_menu = ctk.CTkOptionMenu(
            toolbar, variable=self.size_var,
            values=["All Sizes", "Under 100 MB", "100 MB-1 GB", "Over 1 GB", "Unknown Size"],
            command=lambda v: self._set_filter("size", v),
            font=ctk.CTkFont(size=12),
            fg_color=self.theme.colors["secondary_panel"],
            button_color=self.theme.colors["border"],
            text_color=self.theme.colors["primary_text"],
            height=32, corner_radius=8,
        )
        self.size_menu.grid(row=0, column=2, padx=6, pady=12)

        self.publisher_var = ctk.StringVar(value="All Publishers")
        self.publisher_menu = ctk.CTkOptionMenu(
            toolbar, variable=self.publisher_var,
            values=["All Publishers"],
            command=lambda v: self._set_filter("publisher", v),
            font=ctk.CTkFont(size=12),
            fg_color=self.theme.colors["secondary_panel"],
            button_color=self.theme.colors["border"],
            text_color=self.theme.colors["primary_text"],
            height=32, corner_radius=8,
        )
        self.publisher_menu.grid(row=0, column=3, padx=6, pady=12)

        self.sort_var = ctk.StringVar(value="Name (A-Z)")
        self.sort_menu = ctk.CTkOptionMenu(
            toolbar, variable=self.sort_var,
            values=["Name (A-Z)", "Name (Z-A)", "Size (Largest First)",
                    "Size (Smallest First)", "Installation Date (Newest First)", "Publisher"],
            command=lambda v: self._set_sort(v),
            font=ctk.CTkFont(size=12),
            fg_color=self.theme.colors["secondary_panel"],
            button_color=self.theme.colors["border"],
            text_color=self.theme.colors["primary_text"],
            height=32, corner_radius=8,
        )
        self.sort_menu.grid(row=0, column=4, padx=6, pady=12)

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

        # Table container (left)
        table_container = ctk.CTkFrame(panel, fg_color="transparent")
        table_container.grid(row=0, column=0, sticky="nsew", padx=(16, 8), pady=16)
        table_container.grid_columnconfigure(0, weight=1)
        table_container.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            table_container, text="Installed Applications",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=self.theme.colors["primary_text"],
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        self.table_body = ctk.CTkScrollableFrame(
            table_container, fg_color=self.theme.colors["secondary_panel"],
            corner_radius=8,
        )
        self.table_body.grid(row=1, column=0, sticky="nsew")
        self.table_body.grid_columnconfigure(0, weight=1)

        # Details panel (right)
        self.details_panel = ctk.CTkFrame(
            panel, fg_color=self.theme.colors["secondary_panel"],
            corner_radius=10, border_width=1,
            border_color=self.theme.colors["border"],
        )
        self.details_panel.grid(row=0, column=1, sticky="nsew", padx=(8, 16), pady=16)
        self.details_panel.grid_columnconfigure(0, weight=1)
        self._show_no_selection()

    def _show_no_selection(self):
        for w in self.details_panel.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self.details_panel, text="No application selected",
            font=ctk.CTkFont(size=14),
            text_color=self.theme.colors["muted_text"],
            justify="center",
        ).pack(pady=40)

    def _show_details(self, app):
        for w in self.details_panel.winfo_children():
            w.destroy()

        name = app.get("name", "Unknown")
        version = app.get("version") or "Unknown"
        publisher = app.get("publisher") or "Unknown"
        install_date = app.get("install_date") or "Unknown"
        size = self.ctrl.format_size(app.get("size_bytes"))
        location = app.get("install_location") or "Unknown"
        category = app.get("category") or "Other"
        has_uninstall = bool(app.get("uninstall_string"))
        has_modify = bool(app.get("modify_path"))

        ctk.CTkLabel(
            self.details_panel, text=name,
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=self.theme.colors["primary_text"],
            wraplength=220,
        ).pack(padx=16, pady=(16, 4), anchor="w")

        ctk.CTkLabel(
            self.details_panel, text="Version: %s" % version,
            font=ctk.CTkFont(size=12),
            text_color=self.theme.colors["secondary_text"],
        ).pack(padx=16, pady=2, anchor="w")

        ctk.CTkLabel(
            self.details_panel, text="Publisher: %s" % publisher,
            font=ctk.CTkFont(size=12),
            text_color=self.theme.colors["secondary_text"],
        ).pack(padx=16, pady=2, anchor="w")

        ctk.CTkLabel(
            self.details_panel, text="Install Date: %s" % install_date,
            font=ctk.CTkFont(size=12),
            text_color=self.theme.colors["secondary_text"],
        ).pack(padx=16, pady=2, anchor="w")

        ctk.CTkLabel(
            self.details_panel, text="Size: %s" % size,
            font=ctk.CTkFont(size=12),
            text_color=self.theme.colors["secondary_text"],
        ).pack(padx=16, pady=2, anchor="w")

        ctk.CTkLabel(
            self.details_panel, text="Location: %s" % location,
            font=ctk.CTkFont(size=11),
            text_color=self.theme.colors["muted_text"],
            wraplength=220,
        ).pack(padx=16, pady=2, anchor="w")

        ctk.CTkLabel(
            self.details_panel, text="Category: %s" % category,
            font=ctk.CTkFont(size=12),
            text_color=self.theme.colors["secondary_text"],
        ).pack(padx=16, pady=2, anchor="w")

        # Actions
        btn_frame = ctk.CTkFrame(self.details_panel, fg_color="transparent")
        btn_frame.pack(fill="x", padx=16, pady=12)

        if app.get("install_location"):
            ctk.CTkButton(
                btn_frame, text="Open Installation Folder",
                command=lambda: None,
                font=ctk.CTkFont(size=12),
                fg_color=self.theme.colors["glass_panel"],
                hover_color=self.theme.colors["hover_state"],
                text_color=self.theme.colors["primary_text"],
                height=30, corner_radius=6,
            ).pack(fill="x", pady=2)

        ctk.CTkButton(
            btn_frame, text="Search Online",
            command=lambda: None,
            font=ctk.CTkFont(size=12),
            fg_color=self.theme.colors["glass_panel"],
            hover_color=self.theme.colors["hover_state"],
            text_color=self.theme.colors["primary_text"],
            height=30, corner_radius=6,
        ).pack(fill="x", pady=2)

        uninstall_btn = ctk.CTkButton(
            btn_frame, text="Uninstall",
            command=lambda: self._confirm_uninstall(app),
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=self.theme.colors["red_accent"],
            hover_color="#D06565", text_color="white",
            height=32, corner_radius=6,
            state="normal" if has_uninstall else "disabled",
        )
        uninstall_btn.pack(fill="x", pady=2)

        if has_modify:
            ctk.CTkButton(
                btn_frame, text="Modify / Repair",
                command=lambda: None,
                font=ctk.CTkFont(size=12),
                fg_color=self.theme.colors["glass_panel"],
                hover_color=self.theme.colors["hover_state"],
                text_color=self.theme.colors["primary_text"],
                height=30, corner_radius=6,
            ).pack(fill="x", pady=2)

    def _confirm_uninstall(self, app):
        from components.dialogs import ConfirmationDialog
        dialog = ConfirmationDialog(
            self.master,
            title="Confirm Uninstall",
            message="Are you sure you want to uninstall %s (%s)?\n\nUninstalling may remove application data or settings." % (
                app.get("name", "Unknown"), app.get("publisher") or "Unknown"
            ),
            confirm_text="Continue to Uninstall",
            cancel_text="Cancel",
            confirm_color=self.theme.colors["red_accent"],
        )
        dialog.show()
        # Log the confirmation attempt
        try:
            self.act.add_event(
                "system", "Uninstall confirmation opened for %s" % app.get("name", "Unknown"),
                severity="info",
            )
        except Exception:
            pass
        # Do NOT execute any uninstall command in this phase.

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

    # ------------------------------------------------------------------ state
    def _idle(self):
        self._scanning = False
        self._apps = []
        self._filtered = []
        self._selected_ids.clear()
        self._selected_app = None
        self._show_no_selection()
        self._render_table()
        self._update_cards(None)
        self._update_pagination()
        self._update_selection_summary()

    def _start_scan(self):
        if self._scanning:
            return
        self._scanning = True
        self.refresh_btn.configure(state="disabled")
        self.status_lbl.configure(text="Scanning installed applications...", text_color=self.theme.colors["blue_accent"]) if hasattr(self, "status_lbl") else None
        self._scan_th = threading.Thread(target=self._run_scan, daemon=True)
        self._scan_th.start()

    def _run_scan(self):
        try:
            result = self.ctrl.scan()
        except Exception as e:
            result = {"error": str(e), "applications": [], "errors": [str(e)], "count": 0}
        self.after(0, self._on_scan_done, result)

    def _on_scan_done(self, result):
        self._scanning = False
        self.refresh_btn.configure(state="normal")
        self._apps = result.get("applications", [])
        self._last_updated = datetime.now().strftime("%H:%M:%S")
        self.updated_lbl.configure(text="Last updated: %s" % self._last_updated)
        errors = result.get("errors", [])
        if result.get("error"):
            self.status_lbl.configure(text="Scan failed", text_color=self.theme.colors["red_accent"]) if hasattr(self, "status_lbl") else None
        elif errors:
            self.status_lbl.configure(text="Completed with %d warning(s)" % len(errors), text_color=self.theme.colors["orange_accent"]) if hasattr(self, "status_lbl") else None
        else:
            self.status_lbl.configure(text="Scan completed", text_color=self.theme.colors["green_accent"]) if hasattr(self, "status_lbl") else None

        self._apply_filters()
        self._update_cards(result)
        self._scan_th = None

    # ------------------------------------------------------------------ filters
    def _set_filter(self, kind, value):
        if kind == "category":
            self._category = value
        elif kind == "size":
            self._size_filter = value
        elif kind == "publisher":
            self._publisher = value
        self._page = 1
        self._apply_filters()

    def _set_sort(self, value):
        self._sort_by = value
        self._page = 1
        self._apply_filters()

    def _apply_filters(self):
        search = self.search_var.get().strip() if hasattr(self, "search_var") else ""
        filtered = self.ctrl.filter_applications(
            self._apps, search=search, category=self._category,
            size_filter=self._size_filter, publisher=self._publisher,
        )
        filtered = self.ctrl.sort_applications(filtered, self._sort_by)
        self._filtered = filtered

        # Update publisher dropdown
        pubs = self.ctrl.get_publishers(self._apps)
        if hasattr(self, "publisher_menu"):
            self.publisher_menu.configure(values=pubs)
            if self._publisher not in pubs:
                self._publisher = "All Publishers"
                self.publisher_var.set("All Publishers")

        self._render_table()
        self._update_pagination()
        self._update_selection_summary()

    def _render_table(self):
        for w in self.table_body.winfo_children():
            w.destroy()

        if not self._filtered:
            ctk.CTkLabel(
                self.table_body, text="No applications found",
                font=ctk.CTkFont(size=13),
                text_color=self.theme.colors["muted_text"],
            ).pack(pady=20)
            return

        page_apps, start, end = self.ctrl.paginate(self._filtered, self._page, self._per_page)
        for app in page_apps:
            self._create_row(app)

    def _create_row(self, app):
        row = ctk.CTkFrame(
            self.table_body,
            fg_color=self.theme.colors["secondary_panel"],
            corner_radius=6, border_width=1,
            border_color=self.theme.colors["border"],
        )
        row.pack(fill="x", padx=4, pady=2)
        row.grid_columnconfigure(1, weight=1)

        # Checkbox
        var = ctk.BooleanVar(value=app.get("id") in self._selected_ids)
        cb = ctk.CTkCheckBox(
            row, text="", variable=var, width=20, height=20,
            command=lambda aid=app.get("id"): self._toggle_select(aid, var.get()),
            fg_color=self.theme.colors["blue_accent"],
            hover_color=self.theme.colors["hover_state"],
            border_color=self.theme.colors["border"],
        )
        cb.grid(row=0, column=0, sticky="w", padx=(8, 4), pady=6)

        # Name + version
        name_frame = ctk.CTkFrame(row, fg_color="transparent")
        name_frame.grid(row=0, column=1, sticky="ew", padx=4, pady=6)
        name_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            name_frame, text=app.get("name", "Unknown"),
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=self.theme.colors["primary_text"], anchor="w",
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            name_frame, text=app.get("version") or "Unknown version",
            font=ctk.CTkFont(size=10),
            text_color=self.theme.colors["muted_text"], anchor="w",
        ).grid(row=1, column=0, sticky="w")

        # Publisher
        ctk.CTkLabel(
            row, text=app.get("publisher") or "Unknown",
            font=ctk.CTkFont(size=12),
            text_color=self.theme.colors["secondary_text"],
        ).grid(row=0, column=2, sticky="w", padx=8, pady=6)

        # Install date
        ctk.CTkLabel(
            row, text=app.get("install_date") or "Unknown",
            font=ctk.CTkFont(size=12),
            text_color=self.theme.colors["secondary_text"],
        ).grid(row=0, column=3, sticky="w", padx=8, pady=6)

        # Size
        ctk.CTkLabel(
            row, text=self.ctrl.format_size(app.get("size_bytes")),
            font=ctk.CTkFont(size=12),
            text_color=self.theme.colors["primary_text"],
        ).grid(row=0, column=4, sticky="e", padx=8, pady=6)

        # Row click to select details
        row.bind("<Button-1>", lambda e, a=app: self._select_app(a))
        for child in row.winfo_children():
            child.bind("<Button-1>", lambda e, a=app: self._select_app(a))

    def _toggle_select(self, app_id, selected):
        if selected:
            self._selected_ids.add(app_id)
        else:
            self._selected_ids.discard(app_id)
        self._update_selection_summary()

    def _select_app(self, app):
        self._selected_app = app
        self._show_details(app)

    def _update_selection_summary(self):
        total_size = 0
        size_known = False
        for aid in self._selected_ids:
            app = next((a for a in self._apps if a.get("id") == aid), None)
            if app and app.get("size_bytes") is not None:
                total_size += app["size_bytes"]
                size_known = True
        size_str = self.ctrl.format_size(total_size) if size_known else "Unknown"
        self.selection_lbl.configure(
            text="%d selected | %s" % (len(self._selected_ids), size_str)
        )

    def _update_cards(self, result):
        summary = self.ctrl.get_summary(self._apps)
        self._card_cache["total_count"].configure(text=str(summary["total_count"]))
        if summary["total_size_bytes"] is not None:
            self._card_cache["total_size"].configure(text=self.ctrl.format_size(summary["total_size_bytes"]))
        else:
            self._card_cache["total_size"].configure(text="Unknown")
        if summary["large_count"] is not None:
            self._card_cache["large_count"].configure(text=str(summary["large_count"]))
        else:
            self._card_cache["large_count"].configure(text="\u2014")
        if summary["recent_count"] is not None:
            self._card_cache["recent_count"].configure(text=str(summary["recent_count"]))
        else:
            self._card_cache["recent_count"].configure(text="\u2014")

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
