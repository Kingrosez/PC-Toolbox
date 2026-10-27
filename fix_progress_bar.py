#!/usr/bin/env python3
import sys
sys.path.insert(0, r'd:/Windows app/PC-Toolbox')

path = r'd:/Windows app/PC-Toolbox/views/dashboard.py'
content = open(path, 'r', encoding='utf-8').read()

# Find the section with progress_bar reference but no definition
old_section = '''        value_label.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 4))

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

        self._widgets_cache[f"metric_card_{title.lower().replace(' ', '_')}"] = {
            "card": card,
            "status_label": status_label,
            "value_label": value_label,
            "sub_label": sub_label,
            "footer_label": footer_label,
            "progress_bar": progress_bar
        }'''

new_section = '''        value_label.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 4))

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
        }'''

if old_section in content:
    content = content.replace(old_section, new_section)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('Successfully updated _create_metric_card method')
else:
    print('Old section not found! Trying with different spacing...')
    # Try to find similar text
    idx = content.find('value_label.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 4))')
    if idx >= 0:
        snippet = content[idx:idx+600]
        print('Found snippet:')
        print(snippet[:300])