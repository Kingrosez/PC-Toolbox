import re

with open('d:/Windows app/PC-Toolbox/services/temp_cleaner_service.py', 'r') as f:
    content = f.read()

# Replace in get_approved_roots
content = re.sub(r'\\s*if abs_path in \\(\'\', \'/\', \'\\\\\\\\\\\\\\\\', \'C:\\\\\\\\\\\\\\\\'\\):', r'            if self._is_root_path(abs_path):', content)

# Replace in _discover_default_roots
content = re.sub(r'if os\\.path\\.normpath\\(val\\) in \\(\'\', \'/\', \'\\\\\\\\\\\\\\\\', \'C:\\\\\\\\\\\\\\\\'\\):', r'                if self._is_root_path(os.path.abspath(val)):', content)

with open('d:/Windows app/PC-Toolbox/services/temp_cleaner_service.py', 'w') as f:
    f.write(content)