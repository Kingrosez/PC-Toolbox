import os
filepath = 'd:/Windows app/PC-Toolbox/services/temp_cleaner_service.py'
with open(filepath, 'r') as f:
    lines = f.readlines()
# line 114 (1-indexed) is index 113
if len(lines) > 113:
    lines[113] = '\\n'
    with open(filepath, 'w') as f:
        f.writelines(lines)
    print('Fixed line 114')
else:
    print('Line 114 out of range')