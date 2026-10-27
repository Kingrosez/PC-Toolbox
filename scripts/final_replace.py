import sys

path = 'd:/Windows app/PC-Toolbox/services/temp_cleaner_service.py'
with open(path, 'r') as f:
    data = f.read()

old1 = "                if abs_path in ('', '/', '\\\\\\\\', 'C:\\\\\\\\'):\n"
new1 = "                if self._is_root_path(abs_path):\n"
old2 = "                if os.path.normpath(val) in ('/', '\\\\\\\\', 'C:\\\\\\\\'):\n"
new2 = "                if self._is_root_path(os.path.abspath(val)):\n"

if old1 in data:
    data = data.replace(old1, new1)
    print('Replaced old1')
else:
    print('old1 not found')
if old2 in data:
    data = data.replace(old2, new2)
    print('Replaced old2')
else:
    print('old2 not found')

with open(path, 'w') as f:
    f.write(data)