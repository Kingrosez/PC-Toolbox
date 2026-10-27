import os
src_path = 'd:/Windows app/PC-Toolbox/services/temp_cleaner_service.py'
# Read current content
with open(src_path, 'r') as f:
    current = f.read()
# Header (first 18 lines of original? but we can compute from current lines)
lines = current.splitlines(keepends=True)
header = ''.join(lines[:18]) if len(lines) >= 18 else ''
# If header is empty, we fallback to reading the original file from backup? We'll assume it's there.
# Compact class content
class_content = '''class TempCleanerService:
    DEFAULT_WINDOWS_TEMP=r"C:\\Windows\\Temp"
    def __init__(self,roots=None):
        self._configured_roots=roots
        self._seen_paths=set()
    def _is_root_path(self,p):
        n=os.path.normpath(p)
        return os.path.dirname(n)==n
    def _is_reparse_point(self,p):
        if sys.platform!='win32':return False
        try:return bool(os.stat(p).st_file_attributes&stat.FILE_ATTRIBUTE_REPARSE_POINT)
        except:return False
    def get_approved_roots(self):
        r=self._configured_roots if self._configured_roots is not None else self._discover_default_roots()
        v=[];s=set()
        for x in r:
            if not x or not x.strip():continue
            try:
                a=os.path.abspath(x)
                if self._is_root_path(a):continue
                rp=os.path.realpath(a)
                if rp in s:continue
                s.add(rp)
                v.append(a)
            except:continue
        return v
    def _discover_default_roots(self):
        c=[]
        for v in('TEMP','TMP'):
            x=os.environ.get(v)
            if x and x.strip() and not self._is_root_path(os.path.abspath(x)):c.append(x)
        u=[];s=set()
        for x in c:
            n=os.path.normcase(os.path.abspath(x))
            if n not in s:
                s.add(n)
                u.append(x)
        if os.path.isdir(self.DEFAULT_WINDOWS_TEMP):u.append(self.DEFAULT_WINDOWS_TEMP)
        return u
    def scan(self,roots=None,cancel_check=None):
        a=self.get_approved_roots() if roots is None else roots
        if roots is not None:a=self._validate_roots(roots)
        f=[];e=[];sk=[];self._seen_paths=set()
        for r in a:
            if cancel_check and cancel_check():sk.append(f"Scan cancelled at root {r}");break
            try:
                if not os.path.isdir(r):e.append(f"Root not accessible or not a directory: {r}");continue
                self._scan_dir(r,r,f,e,sk,cancel_check)
            except OSError as h:e.append(f"Error scanning root {r}: {h}")
        t=sum(x['size'] for x in f)
        return {'files':f,'total_size':t,'file_count':len(f),'errors':e,'skipped':sk}
    def _validate_roots(self,roots):
        v=[];s=set()
        for r in roots:
            if not r or not r.strip():continue
            try:
                a=os.path.abspath(r)
                if self._is_root_path(a):continue
                rp=os.path.realpath(a)
                if rp in s:continue
                s.add(rp)
                v.append(a)
            except:continue
        return v
    def _scan_dir(self,r,current_dir,f,e,sk,cancel_check):
        try:
            with os.scandir(current_dir) as it:
                for x in it:
                    if cancel_check and cancel_check():return
                    try:
                        if x.is_symlink():sk.append(f"Skipped symlink: {x.path}");continue
                        if self._is_reparse_point(x.path):sk.append(f"Skipped reparse point: {x.path}");continue
                        if x.is_dir(follow_symlinks=False):self._scan_dir(r,x.path,f,e,sk,cancel_check)
                        elif x.is_file(follow_symlinks=False):
                            try:stat=x.stat(follow_symlinks=False)
                            except OSError as h:e.append(f"Stat error for {x.path}: {h}");continue
                            rp=os.path.realpath(x.path)
                            if rp in self._seen_paths:continue
                            self._seen_paths.add(rp)
                            f.append({'path':os.path.abspath(x.path),'size':stat.st_size,'mtime':stat.st_mtime,'root':r})
                    except OSError as h:e.append(f"Error accessing {x.path}: {h}");continue
        except PermissionError as h:e.append(f"Permission denied for directory {current_dir}: {h}")
        except FileNotFoundError:e.append(f"Directory not found during scan: {current_dir}")
        except OSError as h:e.append(f"OS error scanning directory {current_dir}: {h}")
'''
new_content = header + class_content
with open(src_path, 'w') as f:
    f.write(new_content)
print('File overwritten')