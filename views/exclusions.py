"""Exclusions view for PC-Toolbox."""

import customtkinter as ctk
import tkinter.filedialog as fd
import tkinter.messagebox as mb

NAVY = "#0d1b2a"
CARD = "#1b2838"

CATEGORIES = ["folder", "file", "application"]


class ExclusionsView(ctk.CTkFrame):
    def __init__(self, master, navigation):
        super().__init__(master, fg_color="transparent")
        self.navigation = navigation
        self.service = getattr(navigation, "exclusion_service", None)
        self._cat = "folder"
        self._search = ""
        self._build()
        self._render()

    def _build(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=10)
        ctk.CTkLabel(header, text="\U0001F6E1", font=ctk.CTkFont(size=28)).pack(side="left")
        tf = ctk.CTkFrame(header, fg_color="transparent")
        tf.pack(side="left", padx=10)
        ctk.CTkLabel(tf, text="Exclusions", font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(tf, text="Manage files, folders and applications to exclude from scans", font=ctk.CTkFont(size=12), text_color="gray").pack(anchor="w")

        # tabs
        tabs = ctk.CTkFrame(self, fg_color="transparent")
        tabs.grid(row=1, column=0, sticky="ew", padx=20, pady=5)
        for cat, label in [("folder", "Excluded Folders"), ("file", "Excluded Files"), ("application", "Excluded Applications")]:
            ctk.CTkButton(tabs, text=label, width=140, command=lambda c=cat: self._set_cat(c)).pack(side="left", padx=3)

        # toolbar
        tb = ctk.CTkFrame(self, fg_color="transparent")
        tb.grid(row=2, column=0, sticky="ew", padx=20, pady=5)
        self.search_entry = ctk.CTkEntry(tb, placeholder_text="Search exclusions...", width=200)
        self.search_entry.pack(side="left", padx=5)
        self.search_entry.bind("<KeyRelease>", lambda e: self._on_search())
        ctk.CTkButton(tb, text="Add", width=70, command=self._add).pack(side="left", padx=5)
        ctk.CTkButton(tb, text="Remove Selected", width=120, command=self._remove_selected).pack(side="left", padx=5)
        self.count_lbl = ctk.CTkLabel(tb, text="")
        self.count_lbl.pack(side="right", padx=5)

        # table
        tf2 = ctk.CTkFrame(self, fg_color=CARD)
        tf2.grid(row=3, column=0, sticky="nsew", padx=20, pady=10)
        tf2.grid_rowconfigure(0, weight=1)
        tf2.grid_columnconfigure(0, weight=1)
        self.table = ctk.CTkScrollableFrame(tf2, fg_color="transparent")
        self.table.grid(row=0, column=0, sticky="nsew")
        self.grid_rowconfigure(3, weight=1)

    def _set_cat(self, cat):
        self._cat = cat
        self._render()

    def _on_search(self):
        self._search = self.search_entry.get()
        self._render()

    def _render(self):
        for w in self.table.winfo_children():
            w.destroy()
        if not self.service:
            ctk.CTkLabel(self.table, text="No service available").pack(pady=20)
            return
        items = self.service.list_items(category=self._cat, search=self._search)
        self.count_lbl.configure(text="%d items" % len(items))
        if not items:
            ctk.CTkLabel(self.table, text="No exclusions configured").pack(pady=20)
            ctk.CTkLabel(self.table, text="Add a file or folder to exclude it from supported scans.", text_color="gray").pack()
            return
        for it in items:
            row = ctk.CTkFrame(self.table, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=it.get("display_path") or it["path"], anchor="w").pack(side="left", padx=5, fill="x", expand=True)
            ctk.CTkLabel(row, text=it.get("description", ""), width=120).pack(side="left", padx=5)
            ctk.CTkLabel(row, text=it.get("date_added", "")[:10], width=100).pack(side="left", padx=5)
            ctk.CTkButton(row, text="Remove", width=70, command=lambda iid=it["id"]: self._remove(iid)).pack(side="right", padx=5)

    def _add(self):
        if self._cat in ("folder",):
            path = fd.askdirectory()
        else:
            path = fd.askopenfilename()
        if not path or not self.service:
            return
        ok, res = self.service.add(self._cat, path)
        if ok:
            mb.showinfo("Exclusion", "Added")
        else:
            mb.showerror("Exclusion", res)
        self._render()

    def _remove(self, iid):
        if not mb.askyesno("Remove", "Remove this exclusion?"):
            return
        if self.service and self.service.remove(iid):
            self._render()
        else:
            mb.showerror("Remove", "Failed to remove")

    def _remove_selected(self):
        pass
