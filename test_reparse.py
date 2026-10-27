import sys
sys.path.insert(0, '.')
from services.temp_cleaner_service import TempCleanerService
s = TempCleanerService()
print('Testing _is_reparse_point')
try:
    result = s._is_reparse_point('C:\\Windows')
    print('Result:', result)
except Exception as e:
    print('Error', type(e), e)