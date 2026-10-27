import os
filepath = 'd:/Windows app/PC-Toolbox/services/temp_cleaner_service.py'
with open(filepath, 'rb') as f:
    data = f.read()
# Replace all occurrences of b'\\n' (backslash n) with b'' (empty)
# Actually we want to remove the backslash and n characters.
# The sequence is backslash (0x5C) followed by 'n' (0x6E).
new_data = data.replace(b'\\x5C\\x6E', b'')
# Write back
with open(filepath, 'wb') as f:
    f.write(new_data)
print('Removed all backslash-n sequences')
print('Original length:', len(data))
print('New length:', len(new_data))