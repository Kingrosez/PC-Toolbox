"""About view for PC-Toolbox."""

import customtkinter as ctk
import platform
import sys
import webbrowser
import os

NAVY = "#0d1b2a"
CARD = "#1b2838"

try:
    from app.version import APP_NAME, APP_VERSION, APP_DESCRIPTION
except Exception:
    APP_NAME = "PC-Toolbox"
    APP_VERSION = "2.0.0"
    APP_DESCRIPTION = "System Maintenance Utility"


class AboutView(ctk.CTkFrame):
    def __init__(self, master, navigation):
        super().__init__(master, fg_color="transparent")
        self.navigation = navigation
        self._build()

    def _build(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=10)
        ctk.CTkLabel(header, text="\u2139", font=ctk.CTkFont(size=28)).pack(side="left")
        tf = ctk.CTkFrame(header, fg_color="transparent")
        tf.pack(side="left", padx=10)
        ctk.CTkLabel(tf, text="About PC-Toolbox", font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(tf, text="Application information, version details and useful links", font=ctk.CTkFont(size=12), text_color="gray").pack(anchor="w")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        # Left panel
        left = ctk.CTkFrame(body, fg_color=CARD, corner_radius=8)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        ctk.CTkLabel(left, text=APP_NAME, font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(20, 5))
        ctk.CTkLabel(left, text="Version %s" % APP_VERSION, font=ctk.CTkFont(size=14)).pack()
        ctk.CTkLabel(left, text=APP_DESCRIPTION, font=ctk.CTkFont(size=12), text_color="gray").pack(pady=(5, 15))
        ctk.CTkLabel(left, text="Python %s" % sys.version.split()[0]).pack(anchor="w", padx=20)
        ctk.CTkLabel(left, text="OS: %s %s" % (platform.system(), platform.release())).pack(anchor="w", padx=20)
        ctk.CTkLabel(left, text="Arch: %s" % platform.machine()).pack(anchor="w", padx=20)
        ctk.CTkLabel(left, text="Automatic update checking is not configured.", text_color="gray").pack(anchor="w", padx=20, pady=(15, 5))

        # Right panel
        right = ctk.CTkFrame(body, fg_color=CARD, corner_radius=8)
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        ctk.CTkLabel(right, text="Quick Links", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=20, pady=(20, 10))
        links = [
            ("Project Website", "Not configured"),
            ("Documentation", "Not configured"),
            ("Report an Issue", "Not configured"),
            ("Feature Request", "Not configured"),
            ("Support", "Not configured"),
        ]
        for title, url in links:
            f = ctk.CTkFrame(right, fg_color=NAVY, corner_radius=6)
            f.pack(fill="x", padx=20, pady=4)
            ctk.CTkLabel(f, text=title, font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=10, pady=(6, 0))
            ctk.CTkLabel(f, text=url, font=ctk.CTkFont(size=11), text_color="gray").pack(anchor="w", padx=10, pady=(0, 6))

        # Credits
        credits = ctk.CTkFrame(self, fg_color=CARD, corner_radius=8)
        credits.grid(row=2, column=0, columnspan=1, sticky="ew", padx=20, pady=10)
        ctk.CTkLabel(credits, text="Third-party libraries: CustomTkinter, Pillow, psutil (see requirements.txt)", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=20, pady=10)

        # Footer
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=3, column=0, sticky="ew", padx=20, pady=5)
        ctk.CTkLabel(footer, text="PC-Toolbox v%s" % APP_VERSION, text_color="gray", font=ctk.CTkFont(size=11)).pack()
