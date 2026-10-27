"""Main application controller for PC-Toolbox."""

import customtkinter as ctk
from .navigation import NavigationManager
from .theme import ApplicationTheme


class PCToolboxApp(ctk.CTk):
    """Main application window for PC-Toolbox."""

    def __init__(self):
        super().__init__()

        # Configure main window
        self.title("PC-Toolbox")
        self.geometry("1200x800")
        self.minsize(1000, 600)

        # Initialize theme and navigation
        self.theme = ApplicationTheme(self)
        self.navigation = NavigationManager(self)

        # Set up the main layout
        self._setup_layout()

        # Initialize appearance mode
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

    def _setup_layout(self):
        """Set up the main application layout with sidebar and content area."""
        # Configure grid layout
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, minsize=220)
        self.grid_columnconfigure(1, weight=1)

        # Create sidebar
        self.navigation.create_sidebar()

        # Create content frame
        self.content_frame = ctk.CTkFrame(self, fg_color=self.theme.colors["deep_background"])
        self.content_frame.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)

        # Set content frame in navigation manager
        self.navigation.content_frame = self.content_frame

        # Show default screen
        self.navigation.show_screen("dashboard")


if __name__ == "__main__":
    app = PCToolboxApp()
    app.mainloop()