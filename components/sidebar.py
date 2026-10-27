"""Sidebar component for PC-Toolbox navigation."""

import customtkinter as ctk
from typing import Callable


class Sidebar(ctk.CTkFrame):
    """Sidebar component with navigation buttons."""

    def __init__(self, master, on_nav_callback: Callable[[str], None]):
        super().__init__(
            master,
            width=240,
            fg_color=master.theme.colors["deep_background"]
        )
        self.master = master
        self.on_nav_callback = on_nav_callback
        self.grid(row=0, column=0, sticky="ns")
        self.grid_rowconfigure(5, weight=1)

        # Title in sidebar
        self.sidebar_title = ctk.CTkLabel(
            self,
            text="PC-Toolbox",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=master.theme.colors["primary_text"]
        )
        self.sidebar_title.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Subtitle
        self.sidebar_subtitle = ctk.CTkLabel(
            self,
            text="System Maintenance",
            font=ctk.CTkFont(size=12),
            text_color=master.theme.colors["secondary_text"]
        )
        self.sidebar_subtitle.grid(row=1, column=0, padx=20, pady=(0, 20))

        # Navigation buttons
        self._create_nav_buttons()

    def _create_nav_buttons(self):
        """Create navigation buttons in the sidebar."""
        nav_items = [
            ("Dashboard", "dashboard"),
            ("Temp Cleaner", "temp_cleaner"),
            ("Uninstaller", "uninstaller"),
            ("Empty Folders", "empty_folders"),
            ("Leftovers", "leftovers"),
            ("Storage Analyzer", "storage_analyzer"),
            ("PC Health", "pc_health"),
            ("Startup Manager", "startup_manager"),
            ("System Tools", "system_tools"),
            ("Logs", "logs"),
            ("Settings", "settings"),
        ]

        self.nav_buttons: Dict[str, ctk.CTkButton] = {}
        for i, (label, screen_key) in enumerate(nav_items):
            btn = ctk.CTkButton(
                self,
                text=f"  {label}",
                font=ctk.CTkFont(size=14),
                anchor="w",
                height=40,
                fg_color="transparent",
                text_color=master.theme.colors["secondary_text"],
                hover_color=master.theme.colors["hover_state"],
                command=lambda key=screen_key: self.on_nav_callback(key),
            )
            btn.grid(row=i + 2, column=0, sticky="ew", padx=10, pady=4)
            self.nav_buttons[screen_key] = btn

        # Select default active button
        if "dashboard" in self.nav_buttons:
            self.nav_buttons["dashboard"].configure(
                fg_color=master.theme.colors["secondary_panel"]
            )

    def update_selection(self, screen_key: str):
        """Update button selection state."""
        for key, btn in self.nav_buttons.items():
            if key == screen_key:
                btn.configure(
                    fg_color=self.master.theme.colors["secondary_panel"],
                    text_color=self.master.theme.colors["primary_text"],
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=self.master.theme.colors["secondary_text"],
                )