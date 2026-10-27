import sys
sys.path.insert(0, '.')
import importlib
import services.temp_cleaner_service as m
importlib.reload(m)
print('stat' in dir(m))
print('module globals keys:', [k for k in m.__dict__ if k.startswith('stat')])
