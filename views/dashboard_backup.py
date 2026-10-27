"""Dashboard view for PC-Toolbox."""

import customtkinter as ctk
import sys

sys.path.insert(0, 'd:/Windows app/PC-Toolbox')

from controllers.dashboard_controller import DashboardController
import threading


class DashboardView(ctk.CTkFrame):
    def __init__(self, master, navigation):
        self.theme = master.theme
        self.theme = master.theme
        super().__init__(master, fg_color=self.theme.colors["deep_background"])
        self.navigation = navigation
        self.controller = DashboardController()
        self._widgets_cache = {}
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        print("Dashboard: Setting up UI with high-fidelity design...")
        
        # Main container
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Scrollable content frame
        self.content = ctk.CTkScrollableFrame(
            self, 
            fg_color=self.theme.colors["deep_background"],
            scrollbar_fg_color=self.theme.colors["secondary_panel"]
        )
        self.content.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.content.grid_rowconfigure(0, weight=0)
        self.content.grid_columnconfigure(0, weight=1)
        
        # Dashboard header
        self._create_dashboard_header()
        
        # Metric cards row
        self._create_metric_cards()
        
        # Storage Overview
        self._create_storage_overview()

        # Health and Maintenance section (two columns)
        self._create_health_maintenance_section()

        self.status_label = ctk.CTkLabel(
            self.content,
            text="Loading dashboard data...",
            font=ctk.CTkFont(size=14),
            text_color=self.theme.colors["secondary_text"]
        )
        self.status_label.grid(row=99, column=0, pady=20, sticky="w")
        print("Dashboard: UI setup complete")

    def _create_dashboard_header(self):
        """Create dashboard header with title and subtitle."""
        header_frame = ctk.CTkFrame(self.content, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        header_frame.grid_columnconfigure(1, weight=1)
        
        title = ctk.CTkLabel(
            header_frame,
            text="Your PC at a glance",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=self.theme.colors["primary_text"]
        )
        title.grid(row=0, column=0, sticky="w")
        
        subtitle = ctk.CTkLabel(
            header_frame,
            text="Performance counters and persistent health metrics",
            font=ctk.CTkFont(size=12),
            text_color=self.theme.colors["secondary_text"]
        )
        subtitle.grid(row=1, column=0, sticky="w", pady=(2, 0))
        
        self._widgets_cache["header"] = header_frame

    def _create_metric_cards(self):
        """Create the four main metric cards."""
        cards_frame = ctk.CTkFrame(self.content, fg_color="transparent")
        cards_frame.grid(row=1, column=0, sticky="ew", pady=(0, 20))
        cards_frame.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="metrics")
        cards_frame.grid_rowconfigure(0, weight=0)
        
        # CPU Usage card
        self._create_metric_card(
            cards_frame, 0, 0,
            title="CPU Usage",
            status="Normal <70%",
            status_color=self.theme.colors["green_accent"],
            value="24%",
            sub_value="3.82 GHz Base",
            footer="AMD Ryzen 9 5900X"
        )
        
        # Memory Usage card
        self._create_metric_card(
            cards_frame, 0, 1,
            title="Memory Usage",
            status="42% Used",
            status_color=self.theme.colors["blue_accent"],
            value="6.7 / 16.0 GB",
            sub_value="DDR4 3200MHz",
            footer="Available uncommitted"
        )
        
        # Aggregate Storage card
        self._create_metric_card(
            cards_frame, 0, 2,
            title="Aggregate Storage",
            status="3 Volumes",
            status_color=self.theme.colors["primary_text"],
            value="1.42 / 2.08 TB",
            sub_value="68% Utilized",
            footer="Across NVMe & RAID"
        )
        
        # System Uptime card
        self._create_metric_card(
            cards_frame, 0, 3,
            title="System Uptime",
            status="Kernel Stable",
            status_color=self.theme.colors["green_accent"],
            value="4d 18h 32m",
            sub_value="0 Crashes",
            footer="Windows 11 Pro (23H2)"
        )

    def _create_metric_card(self, parent, row, col, title, status, status_color, value, sub_value, footer):
        """Create a structured metric card with header, value, and footer."""
        card = ctk.CTkFrame(
            parent,
            fg_color=self.theme.colors["secondary_panel"],
            corner_radius=12
        )
        card.grid(row=row, column=col, sticky="nsew", padx=8, pady=0)
        card.grid_rowconfigure(1, weight=1)
        card.grid_columnconfigure(0, weight=1)
        
        # Header with title and status
        header_frame = ctk.CTkFrame(card, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        header_frame.grid_columnconfigure(1, weight=1)
        
        title_label = ctk.CTkLabel(
            header_frame,
            text=title,
            font=ctk.CTkFont(size=12, weight="normal"),
            text_color=self.theme.colors["secondary_text"]
        )
        title_label.grid(row=0, column=0, sticky="w")
        
        status_label = ctk.CTkLabel(
            header_frame,
            text=status,
            font=ctk.CTkFont(size=10),
            text_color=status_color
        )
        status_label.grid(row=0, column=1, sticky="e")
        
        # Main value
        value_label = ctk.CTkLabel(
            card,
            text=value,
            font=ctk.CTkFont(size=32, weight="bold"),
            text_color=self.theme.colors["primary_text"]
        )
        value_label.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 4))
        
        # Sub value
        sub_label = ctk.CTkLabel(
            card,
            text=sub_value,
            font=ctk.CTkFont(size=11),
            text_color=self.theme.colors["secondary_text"]
        )
        sub_label.grid(row=2, column=0, sticky="w", padx=16, pady=(0, 2))
        
        # Footer
        footer_label = ctk.CTkLabel(
            card,
            text=footer,
            font=ctk.CTkFont(size=10),
            text_color=self.theme.colors["muted_text"]
        )
        footer_label.grid(row=3, column=0, sticky="w", padx=16, pady=(0, 16))
        
        self._widgets_cache[f"metric_card_{title.lower().replace(' ', '_')}"] = card

    def _create_storage_overview(self):
        """Create storage overview section with analysis panel."""
        storage_frame = ctk.CTkFrame(self.content, fg_color="transparent")
        storage_frame.grid(row=2, column=0, sticky="ew", pady=(0, 20))
        storage_frame.grid_columnconfigure(0, weight=1)

        # Storage Overview header
        header_frame = ctk.CTkFrame(storage_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        header_frame.grid_columnconfigure(1, weight=1)

        title_label = ctk.CTkLabel(
            header_frame,
            text="Storage Overview",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=self.theme.colors["primary_text"]
        )
        title_label.grid(row=0, column=0, sticky="w")

        subtitle_label = ctk.CTkLabel(
            header_frame,
            text="View in Storage Analyzer",
            font=ctk.CTkFont(size=12),
            text_color=self.theme.colors["blue_accent"]
        )
        subtitle_label.grid(row=0, column=1, sticky="e")
        subtitle_label.bind("<Button-1>", lambda e: self.navigation.navigate_to("storage_analyzer"))

        # Storage panel
        panel = ctk.CTkFrame(
            storage_frame,
            fg_color=self.theme.colors["secondary_panel"],
            corner_radius=12
        )
        panel.grid(row=1, column=0, sticky="ew")
        panel.grid_columnconfigure(0, weight=1)

        # Placeholder for storage data
        # Data binding will be handled by _update_storage_widgets
        self._widgets_cache["storage_panel"] = panel
        self._widgets_cache["storage_header"] = header_frame

    def _create_health_maintenance_section(self):
        """Create two-column health and maintenance section."""
        section_frame = ctk.CTkFrame(self.content, fg_color="transparent")
        section_frame.grid(row=3, column=0, sticky="ew", pady=(0, 20))
        section_frame.grid_columnconfigure(0, weight=1, minsize=280)
        section_frame.grid_columnconfigure(1, weight=1, minsize=280)
        section_frame.grid_columnconfigure(2, weight=1, minsize=280)

        # Health Summary
        health_frame = ctk.CTkFrame(
            section_frame,
            fg_color=self.theme.colors["secondary_panel"],
            corner_radius=12
        )
        health_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        health_frame.grid_rowconfigure(1, weight=1)
        health_frame.grid_columnconfigure(0, weight=1)

        self._create_health_summary(health_frame)

        # Quick Maintenance
        maintenance_frame = ctk.CTkFrame(
            section_frame,
            fg_color=self.theme.colors["secondary_panel"],
            corner_radius=12
        )
        maintenance_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 10))
        maintenance_frame.grid_rowconfigure(1, weight=1)
        maintenance_frame.grid_columnconfigure(0, weight=1)

        self._create_quick_maintenance(maintenance_frame)

        # Recent Activity
        activity_frame = ctk.CTkFrame(
            section_frame,
            fg_color=self.theme.colors["secondary_panel"],
            corner_radius=12
        )
        activity_frame.grid(row=0, column=2, sticky="nsew")
        activity_frame.grid_rowconfigure(1, weight=1)
        activity_frame.grid_columnconfigure(0, weight=1)

        self._create_recent_activity(activity_frame)

    def _create_health_summary(self, parent):
        """Create health summary widget."""
        # Header
        header_frame = ctk.CTkFrame(parent, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        header_frame.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(
            header_frame,
            text="Health Summary",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=self.theme.colors["primary_text"]
        )
        title_label.grid(row=0, column=0, sticky="w")

        # Content area for health data
        content_frame = ctk.CTkFrame(parent, fg_color="transparent")
        content_frame.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        content_frame.grid_columnconfigure(0, weight=1)

        self._widgets_cache["health_summary_content"] = content_frame

    def _create_quick_maintenance(self, parent):
        """Create quick maintenance widget with action buttons."""
        # Header
        header_frame = ctk.CTkFrame(parent, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        header_frame.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(
            header_frame,
            text="Quick Maintenance",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=self.theme.colors["primary_text"]
        )
        title_label.grid(row=0, column=0, sticky="w")

        # Content area for maintenance actions
        content_frame = ctk.CTkFrame(parent, fg_color="transparent")
        content_frame.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        content_frame.grid_rowconfigure(0, weight=1)
        content_frame.grid_columnconfigure(0, weight=1)

        self._widgets_cache["quick_maintenance_content"] = content_frame

    def _create_recent_activity(self, parent):
        """Create recent activity widget."""
        # Header
        header_frame = ctk.CTkFrame(parent, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        header_frame.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(
            header_frame,
            text="Recent Activity",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=self.theme.colors["primary_text"]
        )
        title_label.grid(row=0, column=0, sticky="w")

        view_all_btn = ctk.CTkButton(
            header_frame,
            text="View All Logs",
            font=ctk.CTkFont(size=10),
            fg_color="transparent",
            hover_color=self.theme.colors["hover_state"],
            text_color=self.theme.colors["blue_accent"],
            height=24,
            width=80
        )
        view_all_btn.grid(row=0, column=1, sticky="e")
        view_all_btn.configure(command=lambda: self.navigation.navigate_to("logs"))

        # Content area for activity data
        content_frame = ctk.CTkFrame(parent, fg_color="transparent")
        content_frame.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        content_frame.grid_columnconfigure(0, weight=1)

        self._widgets_cache["recent_activity_content"] = content_frame

    def _update_storage_panel(self, storage):
        """Update storage bars in the storage panel."""
        panel = self._widgets_cache.get("storage_panel")
        if not panel: return

        # Clear panel
        for w in panel.winfo_children(): w.destroy()

        drives = storage.get("drives", [])
        for i, drive in enumerate(drives[:3]): # Show top 3 drives
            drive_frame = ctk.CTkFrame(panel, fg_color="transparent")
            drive_frame.grid(row=i, column=0, sticky="ew", padx=16, pady=8)
            drive_frame.grid_columnconfigure(0, weight=1)

            # Label row
            lbl_row = ctk.CTkFrame(drive_frame, fg_color="transparent")
            lbl_row.grid(row=0, column=0, sticky="ew")
            lbl_row.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(lbl_row, text=f"{drive.get('device')} ({drive.get('mountpoint')})", 
                        font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, sticky="w")
            
            used_gb = drive.get("used_bytes", 0) / (1024**3)
            total_gb = drive.get("total_bytes", 0) / (1024**3)
            ctk.CTkLabel(lbl_row, text=f"{used_gb:.1f} GB / {total_gb:.1f} GB", 
                        font=ctk.CTkFont(size=11), text_color=self.theme.colors["secondary_text"]).grid(row=0, column=1, sticky="e")

            # Progress bar
            progress = ctk.CTkProgressBar(drive_frame, height=8, corner_radius=4)
            progress.grid(row=1, column=0, sticky="ew", pady=(4, 0))
            progress.set(drive.get("percent_used", 0) / 100)
            
            # Color based on usage
            if drive.get("percent_used", 0) > 90:
                progress.configure(progress_color=self.theme.colors["red_accent"])
            elif drive.get("percent_used", 0) > 75:
                progress.configure(progress_color=self.theme.colors["orange_accent"])
            else:
                progress.configure(progress_color=self.theme.colors["blue_accent"])

    def _update_health_panel(self, health):
        """Update health summary content."""
        content = self._widgets_cache.get("health_summary_content")
        if not content: return
        for w in content.winfo_children(): w.destroy()

        status = health.get("overall_status", "good")
        status_color = self.theme.colors["green_accent"] if status == "good" else self.theme.colors["orange_accent"]
        if status == "critical": status_color = self.theme.colors["red_accent"]

        status_lbl = ctk.CTkLabel(content, text=f"System Status: {status.upper()}", 
                                font=ctk.CTkFont(size=16, weight="bold"), text_color=status_color)
        status_lbl.grid(row=0, column=0, sticky="w", pady=(0, 10))

        indicators = health.get("indicators", [])
        if not indicators:
            ctk.CTkLabel(content, text="• All hardware sensors within range", 
                        font=ctk.CTkFont(size=12), text_color=self.theme.colors["secondary_text"]).grid(row=1, column=0, sticky="w")
        else:
            for i, ind in enumerate(indicators[:3]):
                ctk.CTkLabel(content, text=f"• {ind.get('message')}", 
                            font=ctk.CTkFont(size=12), text_color=self.theme.colors["secondary_text"]).grid(row=i+1, column=0, sticky="w")

    def _update_maintenance_panel(self):
        """Update maintenance panel with buttons."""
        content = self._widgets_cache.get("quick_maintenance_content")
        if not content: return
        if content.winfo_children(): return # Already created

        # Quick Actions
        actions = [
            ("Clean Temp Files", "system_cleaner"),
            ("Optimize Memory", "performance"),
            ("Security Scan", None)
        ]

        for i, (text, target) in enumerate(actions):
            btn = ctk.CTkButton(
                content,
                text=text,
                font=ctk.CTkFont(size=12),
                fg_color=self.theme.colors["glass_panel"],
                border_width=1,
                border_color=self.theme.colors["border"],
                hover_color=self.theme.colors["hover_state"],
                anchor="w",
                height=32
            )
            btn.grid(row=i, column=0, sticky="ew", pady=4)
            if target:
                btn.configure(command=lambda t=target: self.navigation.navigate_to(t))

    def _update_activity_panel(self):
        """Update recent activity list."""
        content = self._widgets_cache.get("recent_activity_content")
        if not content: return
        for w in content.winfo_children(): w.destroy()

        # Mock activity for design
        activities = [
            ("System Cleaned", "1.2 GB recovered", "10m ago"),
            ("High CPU Alert", "Process: chrome.exe", "1h ago"),
            ("Drive C: Scan", "No errors found", "2h ago")
        ]

        for i, (title, desc, time) in enumerate(activities):
            item = ctk.CTkFrame(content, fg_color="transparent")
            item.grid(row=i, column=0, sticky="ew", pady=4)
            item.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(item, text=title, font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, sticky="w")
            ctk.CTkLabel(item, text=time, font=ctk.CTkFont(size=10), text_color=self.theme.colors["muted_text"]).grid(row=0, column=1, sticky="e")
            ctk.CTkLabel(item, text=desc, font=ctk.CTkFont(size=11), text_color=self.theme.colors["secondary_text"]).grid(row=1, column=0, sticky="w")

    def _load_data(self):
        try:
            self.controller.refresh_data()
            print("Dashboard data loaded")
            self._update_ui()
        except Exception as e:
            print(f"Error loading data: {e}")

