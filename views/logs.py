"""Logs view for PC-Toolbox."""

import customtkinter as ctk
import tkinter as tk
from datetime import datetime

NAVY = "#0d1b2a"
CARD = "#1b2838"
ACCENT = "#4a90d9"


class LogsView(ctk.CTkFrame):
    def __init__(self, master, navigation):
        super().__init__(master, fg_color="transparent")
        self.navigation = navigation
        self.activity = getattr(navigation, "activity_service", None)
        self._records = []
        self._filtered = []
        self._page = 0
        self._page_size = 25
        self._severity = "All Levels"
        self._module = "All Modules"
        self._search = ""
        self._build()
        self._load()

    def _build(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=10)
        ctk.CTkLabel(header, text="\U0001F4DC", font=ctk.CTkFont(size=28)).pack(side="left")
        tf = ctk.CTkFrame(header, fg_color="transparent")
        tf.pack(side="left", padx=10)
        ctk.CTkLabel(tf, text="Logs", font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(tf, text="View application logs and activity history", font=ctk.CTkFont(size=12), text_color="gray").pack(anchor="w")
        bf = ctk.CTkFrame(header, fg_color="transparent")
        bf.pack(side="right")
        ctk.CTkButton(bf, text="Refresh", width=90, command=self._load).pack(side="left", padx=5)
        ctk.CTkButton(bf, text="Clear Logs", width=100, fg_color="#c0392b", command=self._confirm_clear).pack(side="left", padx=5)
        ctk.CTkButton(bf, text="Export", width=80, command=self._export).pack(side="left", padx=5)

        # Summary cards
        cards = ctk.CTkFrame(self, fg_color="transparent")
        cards.grid(row=0, column=0, sticky="ew", padx=20, pady=(70, 5))
        self.card_total = self._card(cards, "\U0001F4CB", "Total Logs", "0")
        self.card_info = self._card(cards, "\u2139", "Information", "0")
        self.card_warn = self._card(cards, "\u26A0", "Warnings", "0")
        self.card_err = self._card(cards, "\u2716", "Errors", "0")

        # Filter toolbar
        filt = ctk.CTkFrame(self, fg_color="transparent")
        filt.grid(row=1, column=0, sticky="ew", padx=20, pady=5)
        self.sev_var = ctk.StringVar(value="All Levels")
        ctk.CTkOptionMenu(filt, values=["All Levels", "Info", "Warning", "Error"], variable=self.sev_var, command=self._on_filter).pack(side="left", padx=3)
        self.mod_var = ctk.StringVar(value="All Modules")
        self.mod_menu = ctk.CTkOptionMenu(filt, values=["All Modules"], variable=self.mod_var, command=self._on_filter)
        self.mod_menu.pack(side="left", padx=3)
        self.search_entry = ctk.CTkEntry(filt, placeholder_text="Search logs...", width=200)
        self.search_entry.pack(side="left", padx=10)
        self.search_entry.bind("<KeyRelease>", lambda e: self._on_filter())
        ctk.CTkButton(filt, text="Clear Filters", width=100, command=self._clear_filters).pack(side="left", padx=5)

        # Table
        table_frame = ctk.CTkFrame(self, fg_color=CARD)
        table_frame.grid(row=2, column=0, sticky="nsew", padx=20, pady=5)
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        self.table = ctk.CTkScrollableFrame(table_frame, fg_color="transparent")
        self.table.grid(row=0, column=0, sticky="nsew")

        # Pagination
        pag = ctk.CTkFrame(self, fg_color="transparent")
        pag.grid(row=3, column=0, sticky="ew", padx=20, pady=10)
        self.prev_btn = ctk.CTkButton(pag, text="Prev", width=70, command=self._prev_page)
        self.prev_btn.pack(side="left", padx=5)
        self.page_lbl = ctk.CTkLabel(pag, text="Page 1")
        self.page_lbl.pack(side="left", padx=5)
        self.next_btn = ctk.CTkButton(pag, text="Next", width=70, command=self._next_page)
        self.next_btn.pack(side="left", padx=5)
        self.range_lbl = ctk.CTkLabel(pag, text="")
        self.range_lbl.pack(side="left", padx=10)
        ctk.CTkLabel(pag, text="Rows per page:").pack(side="left", padx=(20, 5))
        self.rows_var = ctk.StringVar(value="25")
        ctk.CTkOptionMenu(pag, values=["25", "50", "100"], variable=self.rows_var, command=self._on_rows_change).pack(side="left")

        self.grid_rowconfigure(2, weight=1)

    def _card(self, parent, icon, title, value):
        f = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=8)
        f.pack(side="left", padx=5, fill="x", expand=True)
        ctk.CTkLabel(f, text=icon, font=ctk.CTkFont(size=18)).pack(pady=(8, 0))
        lbl = ctk.CTkLabel(f, text=value, font=ctk.CTkFont(size=18, weight="bold"))
        lbl.pack()
        ctk.CTkLabel(f, text=title, font=ctk.CTkFont(size=11), text_color="gray").pack(pady=(0, 8))
        return lbl

    def _load(self):
        if not self.activity:
            self._records = []
            self._apply_filters()
            return
        try:
            evs = self.activity.get_recent_events(limit=10000)
        except Exception:
            evs = []
        self._records = evs or []
        # modules
        mods = sorted(set((r.get("event_type") or r.get("module") or "system") for r in self._records))
        self.mod_menu.configure(values=["All Modules"] + mods)
        self._update_cards()
        self._apply_filters()

    def _update_cards(self):
        total = len(self._records)
        info = sum(1 for r in self._records if (r.get("severity") or "").lower() == "info")
        warn = sum(1 for r in self._records if (r.get("severity") or "").lower() == "warning")
        err = sum(1 for r in self._records if (r.get("severity") or "").lower() == "error")
        self.card_total.configure(text=str(total))
        self.card_info.configure(text=str(info))
        self.card_warn.configure(text=str(warn))
        self.card_err.configure(text=str(err))

    def _on_filter(self, *args):
        self._severity = self.sev_var.get()
        self._module = self.mod_var.get()
        self._search = self.search_entry.get()
        self._page = 0
        self._apply_filters()

    def _clear_filters(self):
        self.sev_var.set("All Levels")
        self.mod_var.set("All Modules")
        self.search_entry.delete(0, "end")
        self._on_filter()

    def _apply_filters(self):
        result = list(self._records)
        if self._severity != "All Levels":
            sev = self._severity.lower().replace("s", "") if self._severity == "Warnings" else self._severity.lower()
            # normalize
            sev_map = {"info": "info", "warning": "warning", "error": "error"}
            target = self._severity.lower().rstrip("s")
            if target == "warning":
                target = "warning"
            result = [r for r in result if (r.get("severity") or "").lower() == target]
        if self._module != "All Modules":
            result = [r for r in result if (r.get("event_type") or r.get("module") or "system") == self._module]
        if self._search:
            q = self._search.lower()
            result = [r for r in result if q in str(r.get("message", "")).lower() or q in str(r.get("event_type", "")).lower() or q in str(r.get("severity", "")).lower()]
        self._filtered = result
        self._render_table()

    def _render_table(self):
        for w in self.table.winfo_children():
            w.destroy()
        self._page_size = int(self.rows_var.get())
        total = len(self._filtered)
        pages = max(1, (total + self._page_size - 1) // self._page_size)
        if self._page >= pages:
            self._page = pages - 1
        start = self._page * self._page_size
        end = min(start + self._page_size, total)
        page_items = self._filtered[start:end]
        # header
        hdr = ctk.CTkFrame(self.table, fg_color="transparent")
        hdr.pack(fill="x", pady=2)
        for col, w in [("Timestamp", 160), ("Level", 80), ("Module", 120), ("Message", 400)]:
            ctk.CTkLabel(hdr, text=col, font=ctk.CTkFont(size=11, weight="bold"), width=w).pack(side="left", padx=3)
        for r in page_items:
            row = ctk.CTkFrame(self.table, fg_color="transparent")
            row.pack(fill="x", pady=1)
            ts = r.get("timestamp_formatted") or r.get("timestamp")
            try:
                if isinstance(ts, (int, float)):
                    ts = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                ts = str(ts) if ts else "--"
            ctk.CTkLabel(row, text=str(ts), width=160).pack(side="left", padx=3)
            sev = (r.get("severity") or "info").lower()
            color = {"info": "#2ecc71", "warning": "#f39c12", "error": "#e74c3c"}.get(sev, "#95a5a6")
            ctk.CTkLabel(row, text=sev.upper(), width=80, text_color=color).pack(side="left", padx=3)
            mod = r.get("event_type") or r.get("module") or "system"
            ctk.CTkLabel(row, text=str(mod), width=120).pack(side="left", padx=3)
            msg = str(r.get("message", ""))
            ctk.CTkLabel(row, text=msg[:80], width=400, anchor="w").pack(side="left", padx=3)
            ctk.CTkButton(row, text="Details", width=70, command=lambda rec=r: self._show_details(rec)).pack(side="left", padx=3)
        self.page_lbl.configure(text="Page %d / %d" % (self._page + 1, pages))
        self.range_lbl.configure(text="%d-%d of %d" % (start + 1 if total else 0, end, total))
        self.prev_btn.configure(state="normal" if self._page > 0 else "disabled")
        self.next_btn.configure(state="normal" if self._page < pages - 1 else "disabled")

    def _prev_page(self):
        if self._page > 0:
            self._page -= 1
            self._render_table()

    def _next_page(self):
        total = len(self._filtered)
        pages = max(1, (total + self._page_size - 1) // self._page_size)
        if self._page < pages - 1:
            self._page += 1
            self._render_table()

    def _on_rows_change(self, val):
        self._page_size = int(val)
        self._page = 0
        self._render_table()

    def _show_details(self, rec):
        win = ctk.CTkToplevel(self)
        win.title("Log Details")
        win.geometry("500x400")
        box = ctk.CTkTextbox(win)
        box.pack(fill="both", expand=True, padx=10, pady=10)
        lines = []
        for k, v in rec.items():
            lines.append("%s: %s" % (k, v))
        box.insert("1.0", "\n".join(lines))
        ctk.CTkButton(win, text="Copy Details", command=lambda: self._copy(box.get("1.0", "end"))).pack(pady=5)

    def _copy(self, text):
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
        except Exception:
            pass

    def _confirm_clear(self):
        if not self.activity:
            return
        win = ctk.CTkToplevel(self)
        win.title("Confirm Clear")
        win.geometry("350x150")
        ctk.CTkLabel(win, text="Clear all log records?").pack(pady=20)
        bf = ctk.CTkFrame(win, fg_color="transparent")
        bf.pack()
        ctk.CTkButton(bf, text="Cancel", command=win.destroy).pack(side="left", padx=5)
        ctk.CTkButton(bf, text="Confirm", fg_color="#c0392b", command=lambda: self._do_clear(win)).pack(side="left", padx=5)

    def _do_clear(self, win):
        try:
            self.activity.clear_events()
            win.destroy()
            self._load()
        except Exception:
            win.destroy()

    def _export(self):
        import csv, json, tkinter.filedialog as fd
        path = fd.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv"), ("JSON", "*.json")])
        if not path:
            return
        try:
            if path.endswith(".json"):
                with open(path, "w") as f:
                    json.dump(self._filtered, f, indent=2, default=str)
            else:
                with open(path, "w", newline="") as f:
                    if self._filtered:
                        w = csv.DictWriter(f, fieldnames=list(self._filtered[0].keys()))
                        w.writeheader()
                        w.writerows(self._filtered)
            import tkinter.messagebox as mb
            mb.showinfo("Export", "Exported %d records" % len(self._filtered))
        except Exception as e:
            import tkinter.messagebox as mb
            mb.showerror("Export Failed", str(e))
