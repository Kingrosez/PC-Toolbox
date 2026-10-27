import os
filepath = 'd:/Windows app/PC-Toolbox/services/temp_cleaner_service.py'
with open(filepath, 'r') as f:
    lines = f.readlines()
# line 83 is index 82 (0-indexed)
if len(lines) > 82:
    lines[82] = '\\n'
    with open(filepath, 'w') as f:
        f.writelines(lines)
    print('Fixed line 83')
else:
    print('Line 83 out of range')