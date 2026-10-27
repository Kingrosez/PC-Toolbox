"""PC-Toolbox Main Entry Point."""

import sys
import customtkinter as ctk

# Add the app module to the path
sys.path.insert(0, 'd:/Windows app/PC-Toolbox')

from app.application import PCToolboxApp


def main():
    """Launch the PC-Toolbox application."""
    print("Starting PC-Toolbox...")
    print("Using CustomTkinter for UI framework")
    print("Theme: Dark glassmorphism with blue accents")
    
    # Initialize the main application
    app = PCToolboxApp()
    
    # Set window title and configure
    app.title("PC-Toolbox v2.0")
    app.geometry("1200x800")
    app.minsize(1000, 600)
    
    # Start the main loop
    print("Application launched successfully!")
    print("Navigate using the sidebar to view different screens.")
    app.mainloop()


if __name__ == "__main__":
    main()