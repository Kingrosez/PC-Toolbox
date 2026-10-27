"""Application theme and styling for PC-Toolbox."""

import customtkinter as ctk


class ApplicationTheme:
    """Manages the color palette and typography for the application."""

    # Color palette (High-fidelity design update)
    colors = {
        "deep_background": "#080D1C",
        "sidebar_background": "#080D18",
        "glass_panel": "#101A32",
        "secondary_panel": "#14213D",
        "hover_state": "#1B2A4E",
        "border": "#1E3054",
        "primary_text": "#F0F4FF",
        "secondary_text": "#A7B7D9",
        "muted_text": "#64779E",
        "blue_accent": "#248BFF",
        "green_accent": "#24D99A",
        "red_accent": "#FF5364",
        "orange_accent": "#FF9B35",
        "purple_accent": "#9B5CFF",
        "cyan_accent": "#19C7F4",
        "white": "#FFFFFF",
    }

    # Typography (font configs - created dynamically when needed)
    font_configs = {
        "display": {"family": "Segoe UI", "size": 32, "weight": "bold"},
        "title": {"family": "Segoe UI", "size": 24, "weight": "bold"},
        "subtitle": {"family": "Segoe UI", "size": 14, "weight": "medium"},
        "body_bold": {"family": "Segoe UI", "size": 14, "weight": "bold"},
        "body": {"family": "Segoe UI", "size": 14},
        "caption": {"family": "Segoe UI", "size": 12},
        "small": {"family": "Segoe UI", "size": 11},
        "tiny": {"family": "Segoe UI", "size": 10},
        "button": {"family": "Segoe UI", "size": 14, "weight": "bold"},
    }

    # Spacing constants
    spacing = {
        "xs": 4,
        "sm": 8,
        "md": 16,
        "lg": 24,
        "xl": 32,
    }

    def __init__(self, master: ctk.CTk):
        self.master = master
        # Apply appearance mode
        ctk.set_appearance_mode("Dark")
        # Set default color theme
        ctk.set_default_color_theme("blue")