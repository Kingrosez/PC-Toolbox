"""System Tools view for PC-Toolbox."""

import customtkinter as ctk

NAVY = "#0d1b2a"
CARD = "#1b2838"
ACCENT = "#4a90d9"
GROUPS = ["System Maintenance", "System Information", "Network Tools", "Administrative Tools", "File and Folder Tools", "Other Utilities"]


class SystemToolsView(ctk.CTkFrame):
    def __init__(self, master, navigation):
        super().__init__(master, fg_color="transparent")
        self.navigation = navigation
        self.service = None
        self._build()

    def set_service(self, service):
        self.service = service
        self._load_tools()

    def _build(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=10)
        ctk.CTkLabel(header, text="\U0001F527", font=ctk.CTkFont(size=28)).pack(side="left")
        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.pack(side="left", padx=10)
        ctk.CTkLabel(title_frame, text="System Tools", font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(title_frame, text="Useful Windows tools and utilities", font=ctk.CTkFont(size=12), text_color="gray").pack(anchor="w")
        ctk.CTkButton(header, text="View All Logs", width=110).pack(side="right", padx=5)

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)

    def _load_tools(self):
        if not self.service:
            return
        tools = self.service.get_tools()
        # Group
        by_group = {}
        for t in tools:
            by_group.setdefault(t["group"], []).append(t)

        for group in GROUPS:
            gframe = ctk.CTkFrame(self.scroll, fg_color=CARD, corner_radius=8)
            gframe.pack(fill="x", pady=8, padx=5)
            ctk.CTkLabel(gframe, text=group, font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=10, pady=(8, 4))
            grid = ctk.CTkFrame(gframe, fg_color="transparent")
            grid.pack(fill="x", padx=10, pady=(0, 8))
            items = by_group.get(group, [])
            for i, t in enumerate(items):
                r, c = divmod(i, 2)
                card = ctk.CTkFrame(grid, fg_color=NAVY, corner_radius=6)
                card.grid(row=r, column=c, padx=5, pady=5, sticky="ew")
                grid.grid_columnconfigure(c, weight=1)
                ctk.CTkLabel(card, text=t["name"], font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=8, pady=(6, 0))
                ctk.CTkLabel(card, text=t["desc"], font=ctk.CTkFont(size=11), text_color="gray").pack(anchor="w", padx=8, pady=(0, 4))
                action = t.get("action")
                if action:
                    ctk.CTkButton(card, text="→", width=30, command=lambda a=action: self._run(a)).pack(anchor="e", padx=8, pady=(0, 6))
                else:
                    ctk.CTkLabel(card, text="(info only)", font=ctk.CTkFont(size=10), text_color="gray").pack(anchor="e", padx=8, pady=(0, 6))

    def _run(self, action):
        if callable(action):
            try:
                result = action()
                if isinstance(result, dict) and not result.get("success", True):
                    pass
            except Exception:
                pass
