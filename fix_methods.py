import os
filepath = 'd:/Windows app/PC-Toolbox/services/temp_cleaner_service.py'
with open(filepath, 'r') as f:
    lines = f.readlines()
# Find start of _validate_roots
start_v = None
for i, line in enumerate(lines):
    if line.strip().startswith('def _validate_roots'):
        start_v = i
        break
if start_v is None:
    print('Could not find _validate_roots')
    exit(1)
# Find start of _scan_dir
start_s = None
for i, line in enumerate(lines):
    if line.strip().startswith('def _scan_dir'):
        start_s = i
        break
if start_s is None:
    print('Could not find _scan_dir')
    exit(1)
# We will replace lines[start_v:start_s] with the correct _validate_roots method
# Ensure there is a blank line before the method (if not already)
# Actually we want to keep the blank line before the method if it exists.
# Let's just replace from start_v to start_s with:
#   blank line (if not already blank)
#   _validate_roots method lines
#   blank line (if not already blank after method)
# But easier: replace the whole block and then ensure blank lines.
# We'll construct the new block:
new_block = [
    '\\n',  # blank line before method
    '    def _validate_roots(self, roots: List[str]) -> List[str]:\\n',
    '        validated: List[str] = []\\n',
    '        seen_real: Set[str] = set()\\n',
    '        for r in roots:\\n',
    '            if not r or not r.strip():\\n',
    '                continue\\n',
    '            try:\\n',
    '                abs_path = os.path.abspath(r)\\n',
    '                if self._is_root_path(abs_path):\\n',
    '                    continue\\n',
    '                real_path = os.path.realpath(abs_path)\\n',
    '                if real_path in seen_real:\\n',
    '                    continue\\n',
    '                seen_real.add(real_path)\\n',
    '                validated.append(abs_path)\\n',
    '            except (OSError, ValueError):\\n',
    '                continue\\n',
    '        return validated\\n',
    '\\n'   # blank line after method
]
# Replace
lines[start_v:start_s] = new_block
with open(filepath, 'w') as f:
    f.writelines(lines)
print('Fixed _validate_roots method and ensured blank lines')