import os
filepath = 'd:/Windows app/PC-Toolbox/services/temp_cleaner_service.py'
with open(filepath, 'r') as f:
    lines = f.readlines()
# Find the line after the blank line after _discover_default_roots
# We know that the blank line is at line 83 (1-indexed) = index 82
# The scan method should start at line 84 (1-indexed) = index 83
# We will replace from index 83 to the line before _validate_roots method.
# Find the start of _validate_roots method
start_scan = 83  # index of line 84
# Find the line that starts with '    def _validate_roots'
end_scan = None
for i, line in enumerate(lines):
    if line.strip().startswith('def _validate_roots'):
        end_scan = i
        break
if end_scan is None:
    print('Could not find _validate_roots method')
    exit(1)
# Replace lines[start_scan:end_scan] with the correct scan method
new_scan = '''    def scan(self, roots: Optional[List[str]] = None, cancel_check: Optional[Callable[[], bool]] = None) -> Dict[str, Any]:
        approved_roots = self.get_approved_roots() if roots is None else roots
        if roots is not None:
            approved_roots = self._validate_roots(roots)

        files: List[Dict[str, Any]] = []
        errors: List[str] = []
        skipped: List[str] = []
        self._seen_paths = set()

        for root in approved_roots:
            if cancel_check and cancel_check():
                skipped.append(f\"Scan cancelled at root {root}\")
                break
            try:
                if not os.path.isdir(root):
                    errors.append(f\"Root not accessible or not a directory: {root}\")
                    continue
                self._scan_dir(root, root, files, errors, skipped, cancel_check)
            except OSError as e:
                errors.append(f\"Error scanning root {root}: {e}\")

        total_size = sum(f['size'] for f in files)
        return {
            'files': files,
            'total_size': total_size,
            'file_count': len(files),
            'errors': errors,
            'skipped': skipped,
        }
'''
# Ensure newline at end
if not new_scan.endswith('\\n'):
    new_scan += '\\n'
# Replace
lines[start_scan:end_scan] = [new_scan]
with open(filepath, 'w') as f:
    f.writelines(lines)
print('Replaced scan method')