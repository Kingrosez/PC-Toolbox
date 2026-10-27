"""Toast notification component for PC-Toolbox."""

import customtkinter as ctk


class ToastNotification:
    """Toast notification that appears transiently."""

    def __init__(self, master, message: str, duration: int = 3000,
                 notification_type: str = "info"):
        self.master = master
        self.message = message
        self.duration = duration
        self.notification_type = notification_type
        self.toast = None

        # Determine colors based on type
        if notification_type == "success":
            self.color = master.theme.colors["green_accent"]
            self.text_color = "white"
        elif notification_type == "error":
            self.color = master.theme.colors["red_accent"]
            self.text_color = "white"
        elif notification_type == "warning":
            self.color = master.theme.colors["orange_accent"]
            self.text_color = "white"
        else:
            self.color = master.theme.colors["blue_accent"]
            self.text_color = "white"

    def show(self, x: int = None, y: int = None):
        """Show the toast notification."""
        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()
        toast_width = 300
        toast_height = 50
        x = screen_width - toast_width - 20 if x is None else x
        y = screen_height - toast_height - 20 if y is None else y

        self.toast = ctk.CTkFrame(
            self.master,
            fg_color=self.color,
            corner_radius=4
        )
        self.toast.place(x=x, y=y, width=toast_width, height=toast_height)

        # Message label
        label = ctk.CTkLabel(
            self.toast,
            text=self.message,
            font=ctk.CTkFont(size=13),
            text_color=self.text_color
        )
        label.pack(pady=8)

        # Auto-hide after duration
        self.toast.after(self.duration, self.hide)

    def hide(self):
        """Hide the toast notification."""
        if self.toast:
            self.toast.destroy()
            self.toast = None