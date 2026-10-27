# Helper functions for pure calculations

def format_uptime(seconds):
    """Format uptime in seconds to d/h/m string."""
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    minutes = int((seconds % 3600) // 60)
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"

def calculate_storage_metrics(drives):
    """Calculate aggregate storage metrics."""
    total_used = sum(d.get("used_bytes", 0) for d in drives if d.get("accessible", False))
    total_cap = sum(d.get("total_bytes", 0) for d in drives if d.get("accessible", False))
    total_free = total_cap - total_used
    percent_used = (total_used / total_cap * 100) if total_cap > 0 else 0
    volume_count = len([d for d in drives if d.get('accessible')])
    
    return {
        "total_used_tb": total_used / (1024**4),
        "total_cap_tb": total_cap / (1024**4),
        "total_free_tb": total_free / (1024**4),
        "percent_used": percent_used,
        "volume_count": volume_count
    }

def update_cpu_card(cpu_usage, theme_colors):
    """
    Update CPU card data based on cpu_usage and theme colors.
    
    Args:
        cpu_usage (float): CPU usage percentage (0-100)
        theme_colors (dict): Dictionary of theme colors
    
    Returns:
        tuple: (value_text, progress_value, status_text, status_color)
    """
    value_text = f"{cpu_usage:.1f}%"
    progress_value = cpu_usage / 100.0
    if cpu_usage > 90:
        status_text = "Critical"
        status_color = theme_colors["red_accent"]
    elif cpu_usage > 70:
        status_text = "Warning"
        status_color = theme_colors["orange_accent"]
    else:
        status_text = "Normal"
        status_color = theme_colors["green_accent"]
    return value_text, progress_value, status_text, status_color

class RefreshLock:
    """Simple lock to prevent overlapping refresh operations."""
    def __init__(self):
        self._in_progress = False
    
    def acquire(self):
        """Attempt to acquire the lock. Returns True if successful, False if already in progress."""
        if self._in_progress:
            return False
        self._in_progress = True
        return True
    
    def release(self):
        """Release the lock."""
        self._in_progress = False
    
    @property
    def in_progress(self):
        """Check if refresh is currently in progress."""
        return self._in_progress
