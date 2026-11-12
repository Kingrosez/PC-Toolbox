"""Navigation manager for PC-Toolbox screen transitions."""

import customtkinter as ctk
from typing import Dict, Type, Optional
import sys
sys.path.insert(0, 'd:/Windows app/PC-Toolbox')

from views import dashboard, temp_cleaner, uninstaller, empty_folders, leftovers, storage_analyzer, pc_health, startup_manager, system_tools, logs, settings, exclusions, about

from services.activity_service import ActivityService
from services.settings_service import SettingsService
from services.exclusion_service import ExclusionService
from services.system_tools_service import SystemToolsService
from services.startup_manager_service import StartupManagerService
from controllers.dashboard_controller import DashboardController
from controllers.temp_cleaner_controller import TempCleanerController
from controllers.uninstaller_controller import UninstallerController
from controllers.empty_folders_controller import EmptyFoldersController
from controllers.leftovers_controller import LeftoversController
from controllers.system_cleanup_controller import SystemCleanupController
from controllers.storage_analyzer_controller import StorageAnalyzerController
from controllers.pc_health_controller import PCHealthController
from controllers.startup_manager_controller import StartupManagerController

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


def _make_icon(concept, size=20, color=(160, 180, 220, 255)):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = color
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
    elif concept == "laptop":
        d.rectangle([2, 4, size-2, size-6], outline=c, width=2)
        d.line([1, size-4, size-1, size-4], fill=c, width=2)
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

        # Shared services and controllers. Views consume these through the
        # navigation object so activity, settings, and exclusions stay consistent.
        self.activity_service = ActivityService()
        self.settings_service = SettingsService()
        self.exclusion_service = ExclusionService(activity_service=self.activity_service)
        self.system_tools_service = SystemToolsService(self.activity_service)
        self.dashboard_controller = DashboardController(self.activity_service)
        self.temp_cleaner_controller = TempCleanerController(
            self.activity_service, self.exclusion_service, self.settings_service
        )
        self.uninstaller_controller = UninstallerController(self.activity_service)
        self.empty_folders_controller = EmptyFoldersController(
            self.activity_service, self.exclusion_service, self.settings_service
        )
        self.leftovers_controller = LeftoversController(
            self.activity_service, settings_service=self.settings_service
        )
        self.system_cleanup_controller = SystemCleanupController(
            self.activity_service, self.settings_service
        )
        self.storage_analyzer_controller = StorageAnalyzerController(self.activity_service)
        self.pc_health_controller = PCHealthController(self.activity_service)
        self.startup_manager_controller = StartupManagerController(
            StartupManagerService(), self.activity_service
        )

    def create_sidebar(self):
        """Create the application sidebar with navigation buttons."""
        c = self.master.theme.colors
        self.sidebar = ctk.CTkFrame(
            self.master,
            width=240,
            fg_color=c["sidebar_background"],
            corner_radius=0,
        )
        self.sidebar.grid(row=0, column=0, sticky="ns")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_rowconfigure(1, weight=1)
        self.sidebar.grid_columnconfigure(0, weight=1)

        # Branding
        brand = ctk.CTkFrame(self.sidebar, fg_color="transparent", height=100)
        brand.grid(row=0, column=0, sticky="ew", padx=16, pady=(20, 8))
        brand.grid_propagate(False)
        brand.grid_columnconfigure(1, weight=1)

        brand_icon = _make_icon("laptop", 34, (36, 139, 255, 255))
        self._brand_img = ctk.CTkImage(
            light_image=brand_icon, dark_image=brand_icon, size=(34, 34)
        )
        ctk.CTkLabel(
            brand, text="", image=self._brand_img, width=34, height=34
        ).grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 10))

        ctk.CTkLabel(
            brand, text="PC-Toolbox",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=c["primary_text"],
        ).grid(row=0, column=1, sticky="w")

        ctk.CTkLabel(
            brand, text="System Maintenance",
            font=ctk.CTkFont(size=11),
            text_color=c["secondary_text"],
        ).grid(row=1, column=1, sticky="w", pady=(1, 0))

        # Scrollable nav middle
        self.nav_scroll = ctk.CTkScrollableFrame(
            self.sidebar, fg_color="transparent",
            scrollbar_button_color=c["border"],
            scrollbar_button_hover_color=c["blue_accent"],
        )
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
            ("Settings", "settings"),
        ]
        self.nav_buttons = {}
        self._icons = {}
        self._icon_pairs = {}
        for label, key in nav_items:
            concept = ICON_CONCEPTS.get(key, "info")
            normal_img = ctk.CTkImage(
                light_image=_make_icon(concept, 20, (135, 155, 190, 255)),
                dark_image=_make_icon(concept, 20, (135, 155, 190, 255)),
                size=(20, 20),
            )
            active_img = ctk.CTkImage(
                light_image=_make_icon(concept, 20, (255, 255, 255, 255)),
                dark_image=_make_icon(concept, 20, (255, 255, 255, 255)),
                size=(20, 20),
            )
            self._icons[key] = normal_img
            self._icon_pairs[key] = (normal_img, active_img)
            btn = ctk.CTkButton(
                self.nav_scroll,
                text="  " + label,
                image=normal_img,
                compound="left",
                font=ctk.CTkFont(size=13),
                anchor="w",
                height=42,
                fg_color="transparent",
                text_color=c["secondary_text"],
                hover_color=c["hover_state"],
                corner_radius=8,
                command=lambda k=key: self.show_screen(k),
            )
            btn.pack(fill="x", padx=12, pady=2)
            self.nav_buttons[key] = btn

        # Footer account block
        footer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=16, pady=(8, 16))
        footer.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            footer, text="v2.0.0",
            font=ctk.CTkFont(size=10),
            text_color=c["muted_text"],
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            footer, text="PC-Toolbox",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=c["secondary_text"],
        ).grid(row=1, column=0, sticky="w", pady=(0, 8))

        account = ctk.CTkFrame(
            footer, fg_color=c["glass_panel"], corner_radius=8,
            border_width=1, border_color=c["border"],
        )
        account.grid(row=2, column=0, sticky="ew")
        account.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            account, text="\u25CF", font=ctk.CTkFont(size=10),
            text_color=c["green_accent"],
        ).grid(row=0, column=0, rowspan=2, sticky="w", padx=(10, 6), pady=8)

        ctk.CTkLabel(
            account, text="Administrator",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=c["primary_text"],
        ).grid(row=0, column=1, sticky="w", pady=(8, 0))

        ctk.CTkLabel(
            account, text="Elevated privileges",
            font=ctk.CTkFont(size=9),
            text_color=c["muted_text"],
        ).grid(row=1, column=1, sticky="w", pady=(0, 8))

        ctk.CTkLabel(
            account, text="\u203A", font=ctk.CTkFont(size=16),
            text_color=c["secondary_text"],
        ).grid(row=0, column=2, rowspan=2, sticky="e", padx=(4, 10))

        self._set_nav_active("dashboard")

    def _set_nav_active(self, screen_key):
        """Apply the active/inactive style to sidebar buttons."""
        c = self.master.theme.colors
        target = "settings" if screen_key in ("exclusions", "about") else screen_key
        for key, btn in self.nav_buttons.items():
            if key == target:
                normal = self._icon_pairs.get(key, (None, None))[1]
                btn.configure(
                    fg_color=c["blue_accent"],
                    text_color=c["primary_text"],
                    image=normal,
                )
            else:
                normal = self._icon_pairs.get(key, (None, None))[0]
                btn.configure(
                    fg_color="transparent",
                    text_color=c["secondary_text"],
                    image=normal,
                )

    def navigate_to(self, screen_key: str):
        """Backward-compatible alias used by views."""
        self.show_screen(screen_key)

    def show_screen(self, screen_key: str):
        """Switch to the specified screen."""
        if screen_key not in self.screens:
            return

        self.current_screen = screen_key
        self._set_nav_active(screen_key)

        # Create or reuse frame
        if screen_key not in self.frames:
            frame = self.screens[screen_key](self.master, self)
            self.frames[screen_key] = frame
            if screen_key == "system_tools" and hasattr(frame, "set_service"):
                frame.set_service(self.system_tools_service)
            elif screen_key == "startup_manager" and hasattr(frame, "set_controller"):
                frame.set_controller(self.startup_manager_controller)
        frame_to_show = self.frames[screen_key]

        # Hide all frames by unpacking them
        for frame in self.frames.values():
            try:
                frame.pack_forget()
            except Exception:
                pass

        # Show the selected frame
        frame_to_show.pack(in_=self.content_frame, fill="both", expand=True)