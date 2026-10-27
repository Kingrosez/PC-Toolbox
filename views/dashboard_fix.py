#!/usr/bin/env python3
"""Script to fix metric card data binding in dashboard.py"""

import sys
sys.path.insert(0, 'd:/Windows app/PC-Toolbox')

path = 'd:/Windows app/PC-Toolbox/views/dashboard.py'
lines = open(path, 'r', encoding='utf-8').readlines()

# New _create_metric_card method - replaces lines 138-197 (0-indexed 137-196)
new_method = """    def _create_metric_card(self, parent, row, col, title, status, status_color, value, sub_value, footer):
        """Create a structured metric card with header, value, and footer."""
        card = ctk.CTkFrame(
            parent,
            fg_color=self.theme.colors["secondary_panel"],
            corner_radius=12
        )
        card.grid(row=row, column=col, sticky="nsew", padx=8, pady=0)
        card.grid_rowconfigure(2, weight=1)
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

        # Progress bar (hidden for uptime)
        progress_bar = None
        if title.lower() != "system uptime":
            progress_bar = ctk.CTkProgressBar(
                card,
                height=6,
                corner_radius=3,
                fg_color=self.theme.colors["glass_panel"],
                progress_color=self.theme.colors["blue_accent"]
            )
            progress_bar.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 8))
            progress_bar.set(0)

        # Sub value
        sub_label = ctk.CTkLabel(
            card,
            text=sub_value,
            font=ctk.CTkFont(size=11),
            text_color=self.theme.colors["secondary_text"]
        )
        row_num = 3 if progress_bar else 2
        sub_label.grid(row=row_num, column=0, sticky="w", padx=16, pady=(0, 2))

        # Footer
        footer_label = ctk.CTkLabel(
            card,
            text=footer,
            font=ctk.CTkFont(size=10),
            text_color=self.theme.colors["muted_text"]
        )
        footer_label.grid(row=row_num + 1, column=0, sticky="w", padx=16, pady=(0, 16))

        # Store references for live updates
        card_key = title.lower().replace(" ", "_")
        self._widgets_cache[f"metric_card_{card_key}"] = {
            "card": card,
            "status_label": status_label,
            "value_label": value_label,
            "sub_label": sub_label,
            "footer_label": footer_label,
            "progress_bar": progress_bar
        }

"""

# Find the start and end of the old method
start_idx = None
end_idx = None
for i, line in enumerate(lines):
    if 'def _create_metric_card' in line:
        start_idx = i
        break

if start_idx is None:
    print("ERROR: Could not find _create_metric_card method")
    sys.exit(1)

# Find the end of the method (next def or end of file)
for i in range(start_idx + 1, len(lines)):
    if lines[i].startswith('def '):
        end_idx = i
        break

if end_idx is None:
    end_idx = len(lines)

print(f"Found method at lines {start_idx+1} to {end_idx}")
print(f"Old method ends at line {end_idx}, which is: {lines[end_idx-1] if end_idx > start_idx else 'N/A'}")

# Replace the method
new_lines = lines[:start_idx] + [new_method] + lines[end_idx:]

# Write the modified content
with open(path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print(f"Successfully replaced _create_metric_card method")
print(f"Removed {end_idx - start_idx} lines, added {len(new_method.split(chr(10)))} lines")