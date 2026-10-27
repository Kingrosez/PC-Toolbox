import shutil
shutil.copy('d:/Windows app/PC-Toolbox/services/temp_cleaner_service.py.bak', 'd:/Windows app/PC-Toolbox/services/temp_cleaner_service.py')
lines = open('d:/Windows app/PC-Toolbox/services/temp_cleaner_service.py').readlines()
lines[42] = '                if self._is_root_path(abs_path):\\n'
lines[62] = '                if self._is_root_path(os.path.abspath(val)):\\n'
with open('d:/Windows app/PC-Toolbox/services/temp_cleaner_service.py', 'w') as f:
    f.writelines(lines)