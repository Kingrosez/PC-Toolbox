"""Button variants for PC-Toolbox."""

import customtkinter as ctk


class PrimaryButton(ctk.CTkButton):
    """Primary action button."""

    def __init__(self, master, text: str, command, height: int = 40, **kwargs):
        super().__init__(
            master,
            text=text,
            command=command,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=master.theme.colors["blue_accent"],
            hover_color="#4A8BDO",
            height=height,
            text_color="white",
            **kwargs
        )


class SecondaryButton(ctk.CTkButton):
    """Secondary action button."""

    def __init__(self, master, text: str, command, height: int = 40, **kwargs):
        super().__init__(
            master,
            text=text,
            command=command,
            font=ctk.CTkFont(size=14),
            fg_color="transparent",
            hover_color=master.theme.colors["hover_state"],
            height=height,
            text_color=master.theme.colors["primary_text"],
            **kwargs
        )


class DangerButton(ctk.CTkButton):
    """Destructive action button (delete, uninstall, etc.)."""

    def __init__(self, master, text: str, command, height: int = 40, **kwargs):
        super().__init__(
            master,
            text=text,
            command=command,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=master.theme.colors["red_accent"],
            hover_color="#D06565",
            height=height,
            text_color="white",
            **kwargs
        )


class SuccessButton(ctk.CTkButton):
    """Success action button."""

    def __init__(self, master, text: str, command, height: int = 40, **kwargs):
        super().__init__(
            master,
            text=text,
            command=command,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=master.theme.colors["green_accent"],
            hover_color="#38C96A",
            height=height,
            text_color="white",
            **kwargs
        )


class OutlineButton(ctk.CTkButton):
    """Outline button for secondary actions."""

    def __init__(self, master, text: str, command, height: int = 40, **kwargs):
        super().__init__(
            master,
            text=text,
            command=command,
            font=ctk.CTkFont(size=14),
            fg_color="transparent",
            border_width=1,
            border_color=master.theme.colors["muted_text"],
            hover_color=master.theme.colors["hover_state"],
            height=height,
            text_color=master.theme.colors["primary_text"],
            **kwargs
        )


class GhostButton(ctk.CTkButton):
    """Ghost button for minimal actions."""

    def __init__(self, master, text: str, command, **kwargs):
        super().__init__(
            master,
            text=text,
            command=command,
            font=ctk.CTkFont(size=13),
            fg_color="transparent",
            hover_color=master.theme.colors["hover_state"],
            text_color=master.theme.colors["secondary_text"],
            **kwargs
        )