"""Metric card component for PC-Toolbox dashboard statistics."""

import customtkinter as ctk


class MetricCard(ctk.CTkFrame):
    """Statistic card component displaying a metric value."""

    def __init__(self, master, label: str, value: str, unit: str = "",
                   color: str = "#5A9FFF", theme=None):
        
        # Determine theme
        if theme:
            self.theme = theme
        else:
            self.theme = master.theme

        super().__init__(
            master,
            fg_color=self.theme.colors["secondary_panel"],
            corner_radius=8
        )

        # Icon/label area
        self.icon_label = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=24)
        )
        self.icon_label.grid(row=0, column=0, padx=16, pady=12)

        # Text content
        self.text_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.text_frame.grid(row=0, column=1, padx=12, pady=12, sticky="nsw")

        self.label = ctk.CTkLabel(
            self.text_frame,
            text=label,
            font=ctk.CTkFont(size=12),
            text_color=master.theme.colors["muted_text"]
        )
        self.label.pack(anchor="w")

        self.value_label = ctk.CTkLabel(
            self.text_frame,
            text=value + (" " + unit if unit else ""),
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=color
        )
        self.value_label.pack(anchor="w", pady=(4, 0))

    def set_value(self, value: str, unit: str = ""):
        """Update the metric value."""
        self.value_label.configure(text=value + (" " + unit if unit else ""))