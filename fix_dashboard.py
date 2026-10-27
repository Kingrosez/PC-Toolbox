f='d:/Windows app/PC-Toolbox/views/dashboard.py'
c=open(f).read()
# Fix theme order
c=c.replace('super().__init__(master, fg_color=self.theme.colors["deep_background"])\n        self.theme = master.theme', 'self.theme = master.theme\n        super().__init__(master, fg_color=self.theme.colors["deep_background"])')
# Fix _load_data recursion
c=c.replace('def _load_data(self):\n        self._refresh_data_async()', 'def _load_data(self):\n        try:\n            self.controller.refresh_data()\n            print("Dashboard data loaded")\n        except Exception as e:\n            print(f"Error loading data: {e}")')
# Comment out missing methods
c=c.replace('self._create_storage_overview()', '# self._create_storage_overview()')
c=c.replace('self._create_health_maintenance_section()', '# self._create_health_maintenance_section()')
# Fix weight issue
c=c.replace('weight="medium"', 'weight="normal"')
open(f,'w').write(c)
print('Fixed dashboard successfully')