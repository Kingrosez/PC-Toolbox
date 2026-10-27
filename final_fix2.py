#!/usr/bin/env python3
"""Final fix for dashboard metric card progress bar"""

path = r'd:/Windows app/PC-Toolbox/views/dashboard.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the line with value_label.grid and insert progress bar after it
for i, line in enumerate(lines):
    if 'value_label.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 4))' in line:
        insert_idx = i + 1
        # Insert progress bar creation code
        progress_code = [
            '\n',
            '        # Progress bar (hidden for uptime)\n',
            '        progress_bar = None\n',
            '        if title.lower() != "system uptime":\n',
            '            progress_bar = ctk.CTkProgressBar(\n',
            '                card,\n',
            '                height=6,\n',
            '                corner_radius=3,\n',
            '                fg_color=self.theme.colors["glass_panel"],\n',
            '                progress_color=self.theme.colors["blue_accent"]\n',
            '            )\n',
            '            progress_bar.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 8))\n',
            '            progress_bar.set(0)\n',
            '\n'
        ]
        
        # Insert the code
        lines[insert_idx:insert_idx] = progress_code
        
        # Now find sub_label.grid and update row number
        for j in range(insert_idx, len(lines)):
            if 'sub_label.grid(row=2, column=0, sticky="w", padx=16, pady=(0, 2))' in lines[j]:
                lines[j] = '        row_num = 3 if progress_bar else 2\n        sub_label.grid(row=row_num, column=0, sticky="w", padx=16, pady=(0, 2))\n'
                break
        
        # Find footer_label.grid and update row
        for j in range(insert_idx, len(lines)):
            if 'footer_label.grid(row=3, column=0, sticky="w", padx=16, pady=(0, 16))' in lines[j]:
                lines[j] = '        footer_label.grid(row=row_num + 1, column=0, sticky="w", padx=16, pady=(0, 16))\n'
                break
        
        break

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("SUCCESS: Progress bar creation added to _create_metric_card method")