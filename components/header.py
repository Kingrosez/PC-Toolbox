"""Header component for PC-Toolbox main window."""

import customtkinter as ctk


class Header(ctk.CTkFrame):
    """Header component with application title and search."""

    def __init__(self, master, title: str = "PC-Toolbox", subtitle: str = ""):
        super().__init__(
            master,
            fg_color=master.theme.colors["glass_panel"],
            height=60
        )
        self.grid(row=0, column=1, sticky="ew")
        self.grid_columnconfigure(2, weight=1)

        # Title section
        self.title_label = ctk.CTkLabel(
            self,
            text=title,
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=master.theme.colors["primary_text"]
        )
        self.title_label.grid(row=0, column=0, padx=20, pady=12)

        # Subtitle section
        if subtitle:
            self.subtitle_label = ctk.CTkLabel(
                self,
                text=subtitle,
                font=ctk.CTkFont(size=12),
                text_color=master.theme.colors["secondary_text"]
            )
            self.subtitle_label.grid(row=1, column=0, padx=20, pady=(0, 8))

        # Search frame
        self.search_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.search_frame.grid(row=0, column=2, rowspan=2, padx=20, pady=12, sticky="e")

        self.search_entry = ctk.CTkEntry(
            self.search_frame,
            placeholder_text="Search...",
            width=200,
            height=32,
            font=ctk.CTkFont(size=13),
            fg_color=master.theme.colors["secondary_panel"],
            border_width=1,
            border_color=master.theme.colors["muted_text"],
        )
        self.search_entry.pack(side="left")

        self.search_btn = ctk.CTkButton(
            self.search_frame,
            text="",
            width=32,
            height=32,
            fg_color="transparent",
            hover_color=master.theme.colors["hover_state"],
            command=self._on_search,
        )
        self.search_btn.pack(side="left", padx=4)

    def _on_search(self):
        """Handle search button click."""
        pass