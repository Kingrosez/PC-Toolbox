import os
filepath = 'd:/Windows app/PC-Toolbox/services/temp_cleaner_service.py'
with open(filepath, 'r') as f:
    lines = f.readlines()
# We will replace lines 29 to 58 (0-indexed) with the correct methods.
# Line numbers: 29 is the start of _is_reparse_point (we hope)
# We'll replace up to but not including the scan method which starts at line 59.
start = 28  # line 29 index
end = 58    # line 59 index exclusive? We'll replace up to line 58 inclusive? Let's see.
# We'll replace lines[start:end] where end is exclusive, so we want to replace lines 28 to 57 inclusive? Let's just replace lines 28-57 (30 lines) and see.
# We'll compute by finding the line that starts with '    def scan'
scan_start = None
for i, line in enumerate(lines):
    if line.strip().startswith('def scan'):
        scan_start = i
        break
if scan_start is None:
    print('Could not find scan method')
    exit(1)
# Replace lines from 28 to scan_start-1
start_idx = 28
end_idx = scan_start  # exclusive
print(f'Replacing lines {start_idx} to {end_idx-1}')
# Build new content for the replaced section
new_section = '''    def _is_reparse_point(self, path: str) -> bool:
        \"\"\"Return True if path is a reparse point (junction or symlink) on Windows.\"\"\"
        if sys.platform != 'win32':
            return False
        try:
            import stat
            stat_info = os.stat(path)
            return bool(stat_info.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
        except (AttributeError, OSError):
            return False

    def get_approved_roots(self) -> List[str]:
        if self._configured_roots is not None:
            roots = self._configured_roots
        else:
            roots = self._discover_default_roots()
        validated: List[str] = []
        seen_real: Set[str] = set()
        for r in roots:
            if not r or not r.strip():
                continue
            try:
                abs_path = os.path.abspath(r)
                if self._is_root_path(abs_path):
                    continue
                real_path = os.path.realpath(abs_path)
                if real_path in seen_real:
                    continue
                seen_real.add(real_path)
                validated.append(abs_path)
            except (OSError, ValueError):
                continue
        return validated

    def _discover_default_roots(self) -> List[str]:
        candidates: List[str] = []
        for var in ('TEMP', 'TMP'):
            val = os.environ.get(var)
            if val:
                if not val.strip():
                    continue
                if self._is_root_path(os.path.abspath(val)):
                    continue
                candidates.append(val)
        uniq = []
        seen = set()
        for c in candidates:
            norm = os.path.normcase(os.path.abspath(c))
            if norm not in seen:
                seen.add(norm)
                uniq.append(c)
        if os.path.isdir(self.DEFAULT_WINDOWS_TEMP):
            uniq.append(self.DEFAULT_WINDOWS_TEMP)
        return uniq
'''
# Ensure newline at end
if not new_section.endswith('\\n'):
    new_section += '\\n'
# Replace
lines[start_idx:end_idx] = [new_section]
with open(filepath, 'w') as f:
    f.writelines(lines)
print('Replaced section')