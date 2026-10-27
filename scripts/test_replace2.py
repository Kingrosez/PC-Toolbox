lines = open('d:/Windows app/PC-Toolbox/services/temp_cleaner_service.py').readlines()
print('Before:', repr(lines[42]))
lines[42] = '                if self._is_root_path(abs_path):\\n'
print('After assignment:', repr(lines[42]))
with open('d:/Windows app/PC-Toolbox/services/temp_cleaner_service.py', 'w') as f:
    f.writelines(lines)
# read back
with open('d:/Windows app/PC-Toolbox/services/temp_cleaner_service.py', 'r') as f:
    new_lines = f.readlines()
print('After write:', repr(new_lines[42]))