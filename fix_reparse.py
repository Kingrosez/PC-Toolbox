import os
filepath = 'd:/Windows app/PC-Toolbox/services/temp_cleaner_service.py'
with open(filepath, 'r') as f:
    lines = f.readlines()
# Find _is_reparse_point method
start = None
for i, line in enumerate(lines):
    if line.strip().startswith('def _is_reparse_point'):
        start = i
        break
if start is not None:
    # Find end of method
    end = start + 1
    while end < len(lines):
        stripped = lines[end].lstrip()
        if stripped.startswith('def ') or stripped.startswith('class '):
            break
        end += 1
    # Replace lines[start:end] with new method
    new_method = '''    def _is_reparse_point(self, path: str) -> bool:
        \"\"\"Return True if path is a reparse point (junction or symlink) on Windows.\"\"\"
        if sys.platform != 'win32':
            return False
        try:
            import stat
            stat_info = os.stat(path)
            return bool(stat_info.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
        except (AttributeError, OSError):
            return False
'''
    # Ensure newline at end
    if not new_method.endswith('\\n'):
        new_method += '\\n'
    lines[start:end] = [new_method]
    with open(filepath, 'w') as f:
        f.writelines(lines)
    print('Fixed _is_reparse_point')
else:
    print('Could not find _is_reparse_point')