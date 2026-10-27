"""Startup Manager view for PC-Toolbox."""

import customtkinter as ctk
from datetime import datetime

NAVY = "#0d1b2a"
CARD = "#1b2838"
ACCENT = "#4a90d9"


class StartupManagerView(ctk.CTkFrame):
    def __init__(self, master, navigation):
        super().__init__(master, fg_color="transparent")
        self.navigation = navigation
        self.controller = None
        self._entries = []
        self._filter = "all"
        self._search = ""
        self._sort = "name"
        self._page = 0
        self._page_size = 20
        self._selected = None
        self._last_updated = None
        self._build()

    def set_controller(self, controller):
        self.controller = controller

    def _build(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=10)
        ctk.CTkLabel(header, text="\U0001F552", font=ctk.CTkFont(size=28)).pack(side="left")
        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.pack(side="left", padx=10)
        ctk.CTkLabel(title_frame, text="Startup Manager", font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(title_frame, text="Manage startup programs to improve boot time", font=ctk.CTkFont(size=12), text_color="gray").pack(anchor="w")
        btn_frame = ctk.CTkFrame(header, fg_color="transparent")
        btn_frame.pack(side="right")
        self.refresh_btn = ctk.CTkButton(btn_frame, text="Refresh", width=90, command=self._on_refresh)
        self.refresh_btn.pack(side="left", padx=5)
        self.lastupd_lbl = ctk.CTkLabel(btn_frame, text="Last updated: --", font=ctk.CTkFont(size=11), text_color="gray")
        self.lastupd_lbl.pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="View All Logs", width=110).pack(side="left", padx=5)

        # Main content
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        content.grid_rowconfigure(1, weight=1)
        content.grid_columnconfigure(0, weight=3)
        content.grid_columnconfigure(1, weight=1)

        # Summary cards
        cards = ctk.CTkFrame(content, fg_color="transparent")
        cards.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        self.card_total = self._card(cards, "Startup Programs", "0")
        self.card_enabled = self._card(cards, "Enabled", "0")
        self.card_disabled = self._card(cards, "Disabled", "0")
        self.card_impact = self._card(cards, "Boot Impact", "Not measured")

        # Filters row
        filt = ctk.CTkFrame(content, fg_color="transparent")
        filt.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        for label, val in [("All Items", "all"), ("Enabled", "enabled"), ("Disabled", "disabled"), ("High Impact", "high")]:
            ctk.CTkButton(filt, text=label, width=90, command=lambda v=val: self._set_filter(v)).pack(side="left", padx=3)
        self.search_entry = ctk.CTkEntry(filt, placeholder_text="Search startup items...", width=200)
        self.search_entry.pack(side="left", padx=10)
        self.search_entry.bind("<KeyRelease>", lambda e: self._on_search())
        self.sort_var = ctk.StringVar(value="Name")
        ctk.CTkOptionMenu(filt, values=["Name", "Publisher", "Impact"], variable=self.sort_var, command=self._on_sort).pack(side="left", padx=5)

        # Table
        table_frame = ctk.CTkFrame(content, fg_color=CARD)
        table_frame.grid(row=2, column=0, sticky="nsew", pady=(0, 10))
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        self.table = ctk.CTkScrollableFrame(table_frame, fg_color="transparent")
        self.table.grid(row=0, column=0, sticky="nsew")
        self._render_table()

        # Pagination
        pag = ctk.CTkFrame(content, fg_color="transparent")
        pag.grid(row=3, column=0, sticky="ew")
        self.prev_btn = ctk.CTkButton(pag, text="Prev", width=70, command=self._prev_page)
        self.prev_btn.pack(side="left", padx=5)
        self.page_lbl = ctk.CTkLabel(pag, text="Page 1")
        self.page_lbl.pack(side="left", padx=5)
        self.next_btn = ctk.CTkButton(pag, text="Next", width=70, command=self._next_page)
        self.next_btn.pack(side="left", padx=5)

        # Details panel
        details = ctk.CTkFrame(content, fg_color=CARD)
        details.grid(row=1, column=1, rowspan=3, sticky="nsew", padx=(10, 0))
        self.details_lbl = ctk.CTkLabel(details, text="Select an entry", font=ctk.CTkFont(size=14, weight="bold"))
        self.details_lbl.pack(pady=20, padx=10)
        self.details_body = ctk.CTkTextbox(details, height=300)
        self.details_body.pack(fill="both", expand=True, padx=10, pady=10)

    def _card(self, parent, title, value):
        f = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=8)
        f.pack(side="left", padx=5, fill="x", expand=True)
        ctk.CTkLabel(f, text=title, font=ctk.CTkFont(size=11), text_color="gray").pack(pady=(8, 0))
        lbl = ctk.CTkLabel(f, text=value, font=ctk.CTkFont(size=18, weight="bold"))
        lbl.pack(pady=(0, 8))
        return lbl

    def _on_refresh(self):
        if self.controller:
            self.controller.refresh(self._on_loaded, self._on_error)

    def _on_loaded(self, entries):
        self._entries = entries
        self._last_updated = datetime.now().strftime("%H:%M:%S")
        self.lastupd_lbl.configure(text="Last updated: %s" % self._last_updated)
        self._update_cards()
        self._render_table()

    def _on_error(self, msg):
        pass

    def _update_cards(self):
        if not self.controller:
            return
        s = self.controller.get_summary()
        self.card_total.configure(text=str(s["total"]))
        self.card_enabled.configure(text=str(s["enabled"]))
        self.card_disabled.configure(text=str(s["disabled"]))
        self.card_impact.configure(text=s["boot_impact"])

    def _set_filter(self, f):
        self._filter = f
        self._page = 0
        self._render_table()

    def _on_search(self):
        self._search = self.search_entry.get()
        self._page = 0
        self._render_table()

    def _on_sort(self, val):
        mapping = {"Name": "name", "Publisher": "publisher", "Impact": "impact"}
        self._sort = mapping.get(val, "name")
        self._render_table()

    def _filtered(self):
        if not self.controller:
            return []
        return self.controller.filter_entries(self._filter, self._search, self._sort)

    def _render_table(self):
        for w in self.table.winfo_children():
            w.destroy()
        items = self._filtered()
        start = self._page * self._page_size
        end = start + self._page_size
        page_items = items[start:end]
        # Header
        hdr = ctk.CTkFrame(self.table, fg_color="transparent")
        hdr.pack(fill="x", pady=2)
        for col, w in [("Name", 180), ("Publisher", 120), ("Status", 80), ("Impact", 80), ("Source", 160)]:
            ctk.CTkLabel(hdr, text=col, font=ctk.CTkFont(size=11, weight="bold"), width=w).pack(side="left", padx=3)
        for e in page_items:
            row = ctk.CTkFrame(self.table, fg_color="transparent")
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(row, text=e.get("name", ""), width=180).pack(side="left", padx=3)
            ctk.CTkLabel(row, text=e.get("publisher") or "Unknown", width=120).pack(side="left", padx=3)
            ctk.CTkLabel(row, text="Enabled" if e.get("enabled") else "Disabled", width=80).pack(side="left", padx=3)
            ctk.CTkLabel(row, text=e.get("impact", "Unknown"), width=80).pack(side="left", padx=3)
            ctk.CTkLabel(row, text=e.get("source", ""), width=160).pack(side="left", padx=3)
            ctk.CTkButton(row, text="...", width=30, command=lambda eid=e["id"]: self._select(eid)).pack(side="left", padx=3)
        self.page_lbl.configure(text="Page %d / %d" % (self._page + 1, max(1, (len(items) + self._page_size - 1) // self._page_size)))

    def _select(self, eid):
        if self.controller:
            self._selected = self.controller.select(eid)
            self._show_details(self._selected)

    def _show_details(self, e):
        if not e:
            return
        self.details_lbl.configure(text=e.get("name", ""))
        lines = [
            "Publisher: %s" % (e.get("publisher") or "Unknown"),
            "Status: %s" % ("Enabled" if e.get("enabled") else "Disabled"),
            "Source: %s" % e.get("source", ""),
            "Command: %s" % e.get("command", ""),
            "Type: %s" % e.get("type", ""),
            "Impact: %s" % e.get("impact", "Unknown"),
        ]
        self.details_body.delete("1.0", "end")
        self.details_body.insert("1.0", "\n".join(lines))

    def _prev_page(self):
        if self._page > 0:
            self._page -= 1
            self._render_table()

    def _next_page(self):
        items = self._filtered()
        if (self._page + 1) * self._page_size < len(items):
            self._page += 1
            self._render_table()
