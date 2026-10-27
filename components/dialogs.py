"""Dialog and notification components for PC-Toolbox."""

import customtkinter as ctk
from typing import Callable, Optional


class ConfirmationDialog(ctk.CTkToplevel):
    """Confirmation dialog for destructive actions."""

    def __init__(self, master, title: str, message: str,
                 confirm_text: str = "Confirm", cancel_text: str = "Cancel",
                 confirm_color: str = None):
        super().__init__(master)
        self.master = master
        self.result = False
        self.geometry("400x200")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        # Center the dialog
        self.update_idletasks()
        width = 400
        height = 200
        x = self.master.winfo_x() + (self.master.winfo_width() - width) // 2
        y = self.master.winfo_y() + (self.master.winfo_height() - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")

        # Configure dialog
        self.configure(fg_color=self.master.theme.colors["deep_background"])

        # Message
        self.message_label = ctk.CTkLabel(
            self,
            text=message,
            font=ctk.CTkFont(size=14),
            text_color=self.master.theme.colors["primary_text"],
            wraplength=350
        )
        self.message_label.pack(pady=20, padx=20)

        # Button frame
        self.button_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.button_frame.pack(pady=10)

        # Cancel button
        self.cancel_btn = ctk.CTkButton(
            self.button_frame,
            text=cancel_text,
            font=ctk.CTkFont(size=13),
            fg_color="transparent",
            hover_color=self.master.theme.colors["hover_state"],
            height=32,
            command=self._on_cancel
        )
        self.cancel_btn.pack(side="left", padx=20)

        # Confirm button
        color = confirm_color or self.master.theme.colors["red_accent"]
        self.confirm_btn = ctk.CTkButton(
            self.button_frame,
            text=confirm_text,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=color,
            hover_color=self._darken_color(color),
            height=32,
            command=self._on_confirm
        )
        self.confirm_btn.pack(side="left", padx=20)

        # Focus on cancel initially
        self.cancel_btn.focus_set()

    def _on_confirm(self):
        """Handle confirm button click."""
        self.result = True
        self.destroy()

    def _on_cancel(self):
        """Handle cancel button click."""
        self.result = False
        self.destroy()

    def _darken_color(self, color_hex: str) -> str:
        """Darken a hex color by 20%."""
        color_no_hash = color_hex.lstrip('#')
        rgb = tuple(int(color_no_hash[i:i+2], 16) for i in (0, 2, 2))
        darkened = tuple(max(0, c - 51) for c in rgb)
        return f"#{darkened[0]:02x}{darkened[1]:02x}{darkened[2]:02x}"

    def show(self):
        """Show the dialog and wait for response."""
        self.mainloop()


class InfoDialog(ctk.CTkToplevel):
    """Information dialog with OK button."""

    def __init__(self, master, title: str, message: str):
        super().__init__(master)
        self.master = master
        self.geometry("400x200")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        # Center the dialog
        self.update_idletasks()
        width = 400
        height = 200
        x = self.master.winfo_x() + (self.master.winfo_width() - width) // 2
        y = self.master.winfo_y() + (self.master.winfo_height() - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")

        self.configure(fg_color=self.master.theme.colors["deep_background"])

        # Message
        self.message_label = ctk.CTkLabel(
            self,
            text=message,
            font=ctk.CTkFont(size=14),
            text_color=self.master.theme.colors["primary_text"],
            wraplength=350
        )
        self.message_label.pack(pady=40)

        # OK button
        self.ok_btn = ctk.CTkButton(
            self,
            text="OK",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=self.master.theme.colors["blue_accent"],
            hover_color="#4A8BDO",
            height=32,
            command=self.destroy
        )
        self.ok_btn.pack(pady=20)

    def show(self):
        """Show the dialog and wait for response."""
        self.mainloop()