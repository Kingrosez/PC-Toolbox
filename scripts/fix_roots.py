import sys

path = 'd:/Windows app/PC-Toolbox/services/temp_cleaner_service.py'
with open(path, 'r') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'if abs_path in' in line and \"('', '/', '\\\\\\\\', 'C:\\\\\\\\')\" in line:
        # Keep leading whitespace
        indent = line[:len(line) - len(line.lstrip())]
        lines[i] = indent + 'if self._is_root_path(abs_path):\\n'
    if 'os.path.normpath(val)' in line and \"('', '/', '\\\\\\\\', 'C:\\\\\\\\')\" in line:
        indent = line[:len(line) - len(line.lstrip())]
        lines[i] = indent + 'if self._is_root_path(os.path.abspath(val)):\\n'

with open(path, 'w') as f:
    f.writelines(lines)