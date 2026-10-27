import os
filepath = 'd:/Windows app/PC-Toolbox/services/temp_cleaner_service.py'
with open(filepath, 'r') as f:
    lines = f.readlines()
# line 113 (index 112) is the closing brace of scan method: '        }\\n'
# We will replace lines[113:130] (indices 113 to 129 inclusive) with new content.
start_idx = 113  # index of line 114 (1-indexed)
end_idx = 130    # exclusive index of line 131 (1-indexed) which is the start of _scan_dir
# Build replacement
replacement = [
    '\\n',  # blank line
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
    '        return validated\\n'
]
# Replace
lines[start_idx:end_idx] = replacement
with open(filepath, 'w') as f:
    f.writelines(lines)
print('Fixed _validate_roots method')