"""Navigation manager for PC-Toolbox screen transitions."""

import customtkinter as ctk
from typing import Dict, Type, Optional
import sys
sys.path.insert(0, 'd:/Windows app/PC-Toolbox')

from views import dashboard, temp_cleaner, uninstaller, empty_folders, leftovers, storage_analyzer, pc_health, startup_manager, system_tools, logs, settings, exclusions, about

from PIL import Image, ImageDraw

ICON_CONCEPTS = {
    "dashboard": "home",
    "temp_cleaner": "trash",
    "uninstaller": "package",
    "empty_folders": "folder",
    "leftovers": "search",
    "storage_analyzer": "drive",
    "pc_health": "heart",
    "startup_manager": "power",
    "system_tools": "wrench",
    "logs": "doc",
    "settings": "gear",
    "exclusions": "shield",
    "about": "info",
}


def _make_icon(concept, size=20):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = (160, 180, 220, 255)
    # simple shapes per concept
    if concept == "home":
        d.polygon([(size//2, 2), (2, size//2), (size-2, size//2)], fill=c)
        d.rectangle([4, size//2, size-4, size-2], fill=c)
    elif concept == "trash":
        d.rectangle([6, 6, size-6, size-2], outline=c, width=2)
        d.line([4, 4, size-4, 4], fill=c, width=2)
    elif concept == "package":
        d.rectangle([3, 3, size-3, size-3], outline=c, width=2)
        d.line([size//2, 3, size//2, size-3], fill=c, width=1)
    elif concept == "folder":
        d.rectangle([2, 6, size-2, size-3], outline=c, width=2)
        d.polygon([(2, 6), (8, 6), (10, 4), (size-2, 4), (size-2, 6)], fill=c)
    elif concept == "search":
        d.ellipse([2, 2, size-6, size-6], outline=c, width=2)
        d.line([size-6, size-6, size-2, size-2], fill=c, width=2)
    elif concept == "drive":
        d.ellipse([2, 2, size-2, size-2], outline=c, width=2)
        d.pieslice([2, 2, size-2, size-2], 0, 120, fill=c)
    elif concept == "heart":
        d.ellipse([2, 2, size//2+2, size//2+2], fill=c)
        d.ellipse([size//2-2, 2, size-2, size//2+2], fill=c)
        d.polygon([(2, size//2), (size//2, size-2), (size-2, size//2)], fill=c)
    elif concept == "power":
        d.arc([4, 4, size-4, size-4], 45, 315, fill=c, width=2)
        d.line([size//2, 2, size//2, size//2], fill=c, width=2)
    elif concept == "wrench":
        d.line([4, size-4, size-4, 4], fill=c, width=3)
        d.ellipse([size-7, 1, size-1, 7], outline=c, width=2)
    elif concept == "doc":
        d.rectangle([4, 2, size-4, size-2], outline=c, width=2)
        d.line([7, 7, size-7, 7], fill=c, width=1)
        d.line([7, 11, size-7, 11], fill=c, width=1)
    elif concept == "gear":
        d.ellipse([5, 5, size-5, size-5], outline=c, width=2)
        d.ellipse([8, 8, size-8, size-8], fill=c)
    elif concept == "shield":
        d.polygon([(size//2, 2), (size-3, 6), (size-3, size//2), (size//2, size-2), (3, size//2), (3, 6)], fill=c)
    elif concept == "info":
        d.ellipse([size//2-6, 2, size//2+6, 14], outline=c, width=2)
        d.line([size//2, 16, size//2, size-2], fill=c, width=2)
    else:
        d.rectangle([2, 2, size-2, size-2], outline=c, width=2)
    return img


class NavigationManager:
    """Manages screen navigation and content switching."""

    def __init__(self, master: ctk.CTk):
        self.master = master
        self.frames: Dict[str, ctk.CTkFrame] = {}
        self.current_screen: Optional[str] = None
        self.content_frame = None

        # Register all screens
        self.screens: Dict[str, Type[ctk.CTkFrame]] = {
            "dashboard": dashboard.DashboardView,
            "temp_cleaner": temp_cleaner.TempCleanerView,
            "uninstaller": uninstaller.UninstallerView,
            "empty_folders": empty_folders.EmptyFoldersView,
            "leftovers": leftovers.LeftoversView,
            "storage_analyzer": storage_analyzer.StorageAnalyzerView,
            "pc_health": pc_health.PCHealthView,
            "startup_manager": startup_manager.StartupManagerView,
            "system_tools": system_tools.SystemToolsView,
            "logs": logs.LogsView,
            "settings": settings.SettingsView,
            "exclusions": exclusions.ExclusionsView,
            "about": about.AboutView,
        }

    def create_sidebar(self):
        """Create the application sidebar with navigation buttons."""
        self.sidebar = ctk.CTkFrame(
            self.master,
            width=220,
            fg_color=self.master.theme.colors["deep_background"]
        )
        self.sidebar.grid(row=0, column=0, sticky="ns")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_rowconfigure(1, weight=1)
        self.sidebar.grid_columnconfigure(0, weight=1)

        # Branding
        brand = ctk.CTkFrame(self.sidebar, fg_color="transparent", height=110)
        brand.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 4))
        brand.grid_propagate(False)
        ctk.CTkLabel(brand, text="PC-Toolbox", font=ctk.CTkFont(size=20, weight="bold"),
                     text_color=self.master.theme.colors["primary_text"]).pack(anchor="w")
        ctk.CTkLabel(brand, text="System Maintenance", font=ctk.CTkFont(size=12),
                     text_color=self.master.theme.colors["secondary_text"]).pack(anchor="w")

        # Scrollable nav middle
        self.nav_scroll = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent")
        self.nav_scroll.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        self.nav_scroll.grid_columnconfigure(0, weight=1)

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
            ("Exclusions", "exclusions"),
            ("About", "about"),
        ]
        self.nav_buttons = {}
        self._icons = {}
        for label, key in nav_items:
            concept = ICON_CONCEPTS.get(key, "info")
            pil_img = _make_icon(concept, 20)
            ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(20, 20))
            self._icons[key] = ctk_img
            btn = ctk.CTkButton(
                self.nav_scroll,
                text="  " + label,
                image=ctk_img,
                compound="left",
                font=ctk.CTkFont(size=14),
                anchor="w",
                height=44,
                fg_color="transparent",
                text_color=self.master.theme.colors["secondary_text"],
                hover_color=self.master.theme.colors["hover_state"],
                corner_radius=8,
                command=lambda k=key: self.show_screen(k),
            )
            btn.pack(fill="x", padx=12, pady=2)
            self.nav_buttons[key] = btn

        # Footer
        footer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=12, pady=(4, 12))
        settings_img = ctk.CTkImage(light_image=_make_icon("gear", 20), dark_image=_make_icon("gear", 20), size=(20, 20))
        self._icons["settings"] = settings_img
        settings_btn = ctk.CTkButton(
            footer,
            text="  Settings",
            image=settings_img,
            compound="left",
            font=ctk.CTkFont(size=14),
            anchor="w",
            height=44,
            fg_color="transparent",
            text_color=self.master.theme.colors["secondary_text"],
            hover_color=self.master.theme.colors["hover_state"],
            corner_radius=8,
            command=lambda: self.show_screen("settings"),
        )
        settings_btn.pack(fill="x", pady=2)
        self.nav_buttons["settings"] = settings_btn
        ctk.CTkLabel(footer, text="v2.0.0", font=ctk.CTkFont(size=11),
                     text_color=self.master.theme.colors["secondary_text"]).pack(anchor="w", pady=(6, 0))

        if "dashboard" in self.nav_buttons:
            self.nav_buttons["dashboard"].configure(
                fg_color=self.master.theme.colors["secondary_panel"],
                text_color=self.master.theme.colors["primary_text"],
            )

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

        self.nav_buttons = {}
        for i, (label, screen_key) in enumerate(nav_items):
            btn = ctk.CTkButton(
                self.sidebar,
                text=f"  {label}",
                font=ctk.CTkFont(size=14),
                anchor="w",
                height=40,
                fg_color="transparent",
                text_color=self.master.theme.colors["secondary_text"],
                hover_color=self.master.theme.colors["hover_state"],
                command=lambda key=screen_key: self.show_screen(key),
            )
            btn.grid(row=i + 2, column=0, sticky="ew", padx=10, pady=4)
            self.nav_buttons[screen_key] = btn

        # Select the default active button
        if "dashboard" in self.nav_buttons:
            self.nav_buttons["dashboard"].configure(fg_color=self.master.theme.colors["secondary_panel"])

    def show_screen(self, screen_key: str):
        """Switch to the specified screen."""
        if screen_key not in self.screens:
            return

        # Deselect previous button
        if self.current_screen and self.current_screen in self.nav_buttons:
            self.nav_buttons[self.current_screen].configure(
                fg_color="transparent",
                text_color=self.master.theme.colors["secondary_text"],
            )

        # Select new button
        if screen_key in self.nav_buttons:
            self.nav_buttons[screen_key].configure(
                fg_color=self.master.theme.colors["secondary_panel"],
                text_color=self.master.theme.colors["primary_text"],
            )

        self.current_screen = screen_key

        # Create or reuse frame
        if screen_key not in self.frames:
            self.frames[screen_key] = self.screens[screen_key](self.master, self)
        frame_to_show = self.frames[screen_key]

        # Hide all frames by unpacking them
        for frame in self.frames.values():
            try:
                frame.pack_forget()
            except:
                pass

        # Show the selected frame
        frame_to_show.pack(in_=self.content_frame, fill="both", expand=True)