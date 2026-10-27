lines = open('d:/Windows app/PC-Toolbox/services/temp_cleaner_service.py').readlines()
print('Before line 42:', repr(lines[42]))
print('Before line 62:', repr(lines[62]))
lines[42] = '                if self._is_root_path(abs_path):\\n'
lines[62] = '                if self._is_root_path(os.path.abspath(val)):\\n'
print('After line 42:', repr(lines[42]))
print('After line 62:', repr(lines[62]))
with open('d:/Windows app/PC-Toolbox/services/temp_cleaner_service.py', 'w') as f:
    f.writelines(lines)