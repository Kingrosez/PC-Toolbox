import os
filepath = 'd:/Windows app/PC-Toolbox/services/temp_cleaner_service.py'
with open(filepath, 'r') as f:
    lines = f.readlines()
# lines are 0-indexed
# method starts at line 29 (index 28) and ends at line 38 (index 37) inclusive? Let's confirm by looking for the next method start.
start = 28  # line 29
# find end: look for line that starts with '    def ' after start
end = start + 1
while end < len(lines):
    if lines[end].startswith('    def ') or lines[end].startswith('    class '):
        break
    end += 1
# Now lines[start:end] is the method
old_block = ''.join(lines[start:end])
print('Old block:')
print(repr(old_block))
# New block
new_block = '''    def _is_reparse_point(self, path: str) -> bool:
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
if not new_block.endswith('\\n'):
    new_block += '\\n'
print('New block:')
print(repr(new_block))
# Replace
lines[start:end] = [new_block]
with open(filepath, 'w') as f:
    f.writelines(lines)
print('Replaced')