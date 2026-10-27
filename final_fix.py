#!/usr/bin/env python3
"""Final fix for dashboard metric card progress bar"""

path = r'd:/Windows app/PC-Toolbox/views/dashboard.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# The current content has grid_rowconfigure(2 but no progress bar creation
# Let's find the value_label grid line and insert progress bar after it
search_str = '        value_label.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 4))\n\n        # Sub value'
replace_str = '''        value_label.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 4))

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

        # Sub value'''

if search_str in content:
    content = content.replace(search_str, replace_str)
    # Also need to update sub_label grid row
    search_str2 = '        sub_label.grid(row=2, column=0, sticky="w", padx=16, pady=(0, 2))'
    replace_str2 = '        row_num = 3 if progress_bar else 2\n        sub_label.grid(row=row_num, column=0, sticky="w", padx=16, pady=(0, 2))'
    
    if search_str2 in content:
        content = content.replace(search_str2, replace_str2)
    
    # Update footer grid row
    search_str3 = '        footer_label.grid(row=3, column=0, sticky="w", padx=16, pady=(0, 16))'
    replace_str3 = '        footer_label.grid(row=row_num + 1, column=0, sticky="w", padx=16, pady=(0, 16))'
    
    if search_str3 in content:
        content = content.replace(search_str3, replace_str3)
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("SUCCESS: Progress bar creation added to _create_metric_card method")
else:
    print("ERROR: Could not find search string in file")
    print("Searching for value_label.grid line...")
    idx = content.find('value_label.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 4))')
    if idx >= 0:
        print(f"Found at index {idx}")
        print(content[idx-50:idx+200])