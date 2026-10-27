line = open('d:/Windows app/PC-Toolbox/services/temp_cleaner_service.py').readlines()[42]
print(repr(line))
target = \"('', '/', '\\\\\\\\', 'C:\\\\\\\\')\"
print(repr(target))
print('target in line:', target in line)