import sys

path = 'd:/Windows app/PC-Toolbox/services/temp_cleaner_service.py'
with open(path, 'r') as f:
    lines = f.readlines()

# line numbers are 0-indexed
# get_approved_roots line: we found at index 42
lines[42] = '                if self._is_root_path(abs_path):\\n'
# _discover_default_roots line: index 62
lines[62] = '                if self._is_root_path(os.path.abspath(val)):\\n'

with open(path, 'w') as f:
    f.writelines(lines)