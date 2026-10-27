import os
print('Script started')
filepath = 'd:/Windows app/PC-Toolbox/services/temp_cleaner_service.py'
with open(filepath, 'r') as f:
    lines = f.readlines()
start = None
for i, line in enumerate(lines):
    if line.strip().startswith('def _scan_dir'):
        start = i
        break
if start is not None:
    end = start + 1
    while end < len(lines):
        if lines[end].strip().startswith('def ') or lines[end].strip().startswith('class '):
            break
        end += 1
    old_text = ''.join(lines[start:end])
    new_text = '''    def _scan_dir(self, root: str, current_dir: str, files: List[Dict[str, Any]], errors: List[str], skipped: List[str], cancel_check: Optional[Callable[[], bool]]):
        try:
            with os.scandir(current_dir) as it:
                for entry in it:
                    if cancel_check and cancel_check():
                        return
                    try:
                        if entry.is_symlink():
                            skipped.append(f\"Skipped symlink: {entry.path}\")
                            continue
                        if self._is_reparse_point(entry.path):
                            skipped.append(f\"Skipped reparse point: {entry.path}\")
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            self._scan_dir(root, entry.path, files, errors, skipped, cancel_check)
                        elif entry.is_file(follow_symlinks=False):
                            try:
                                stat_res = entry.stat(follow_symlinks=False)
                            except OSError as e:
                                errors.append(f\"Stat error for {entry.path}: {e}\")
                                continue
                            real_path = os.path.realpath(entry.path)
                            if real_path in self._seen_paths:
                                continue
                            self._seen_paths.add(real_path)
                            files.append({
                                'path': os.path.abspath(entry.path),
                                'size': stat_res.st_size,
                                'mtime': stat_res.st_mtime,
                                'root': root,
                            })
                    except OSError as e:
                        errors.append(f\"Error accessing {entry.path}: {e}\")
                        continue
        except PermissionError as e:
            errors.append(f\"Permission denied for directory {current_dir}: {e}\")
        except FileNotFoundError:
            errors.append(f\"Directory not found during scan: {current_dir}\")
        except OSError as e:
            errors.append(f\"OS error scanning directory {current_dir}: {e}\")
    '''
    # Ensure new_text ends with newline
    if not new_text.endswith('\\n'):
        new_text += '\\n'
    lines[start:end] = [new_text]
    with open(filepath, 'w') as f:
        f.writelines(lines)
    print('Replaced _scan_dir')
else:
    print('Could not find _scan_dir')