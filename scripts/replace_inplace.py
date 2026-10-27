import fileinput
import sys

path = 'd:/Windows app/PC-Toolbox/services/temp_cleaner_service.py'
changed = False
for line in fileinput.FileInput(path, inplace=1):
    if line.strip().startswith('if abs_path in') and \"('', '/', '\\\\\\\\', 'C:\\\\\\\\')\" in line:
        # preserve indentation
        indent = line[:len(line) - len(line.lstrip())]
        line = indent + 'if self._is_root_path(abs_path):\\n'
        changed = True
    if line.strip().startswith('if os.path.normpath(val)') and \"('', '/', '\\\\\\\\', 'C:\\\\\\\\')\" in line:
        indent = line[:len(line) - len(line.lstrip())]
        line = indent + 'if self._is_root_path(os.path.abspath(val)):\\n'
        changed = True
    sys.stdout.write(line)
if changed:
    print('Replacements made')
else:
    print('No changes')