# PC-Toolbox

A Windows desktop application for PC maintenance and system management.

## Features

- **Dashboard** - Overview of PC maintenance categories, storage status, recent activity
- **Temp Cleaner** - Temporary file management and cleanup
- **Uninstaller** - Manage installed applications
- **Empty Folders** - Scan and manage unused folders
- **Leftovers** - Handle residual items and scans
- **Storage Analyzer** - Drive and folder size analysis
- **PC Health** - System health metrics and diagnostics
- **Startup Manager** - Application startup configuration
- **System Tools** - Diagnostic utility cards
- **Logs** - Operation history and troubleshooting
- **Settings** - Theme and preference controls

## Architecture

This application uses CustomTkinter for the UI framework with a modular component-based architecture. All screens are designed to follow the Google Stitch design reference with a dark glassmorphism theme.

## Project Structure

```
PC-Toolbox/
├── main.py                    # Entry point
├── requirements.txt           # Dependencies
├── README.md                  # Documentation
├── app/                      # Core application logic
│   ├── __init__.py
│   ├── application.py         # Main application controller
│   ├── navigation.py          # View navigation manager
│   ├── theme.py               # Theme and styling
│   └── mock_data.py           # Mock data generators
└── components/                # Reusable UI components
    ├── __init__.py
    ├── sidebar.py             # Navigation sidebar
    ├── header.py              # Header and title bar
    ├── metric_card.py         # Statistic cards
    ├── buttons.py             # Button variants
    ├── tables.py              # Data tables
    ├── dialogs.py             # Modal dialogs
    └── notifications.py       # Toast and notification system
```

## Getting Started

1. Install dependencies: `pip install -r requirements.txt`
2. Run the application: `python main.py`

## Design Palette

- **Deep Background**: #0D0D12
- **Glass Panel**: #1A1A2E
- **Secondary Panel**: #232342
- **Hover State**: #2D2D5A
- **Primary Text**: #F0F0F5
- **Secondary Text**: #A0A0B8
- **Muted Text**: #707088
- **Blue Accent**: #5A9FFF
- **Green Accent**: #4ADE80
- **Red Accent**: #F87171
- **Orange Accent**: #FB923C

## Screens

- Dashboard - PC maintenance overview
- Temp Cleaner - Temporary file management
- Uninstaller - Application inventory
- Empty Folders - Unused folder scanning
- Leftovers - Residual item handling
- Storage Analyzer - Drive and folder analysis
- PC Health - System health metrics
- Startup Manager - Application startup config
- System Tools - Diagnostic utilities
- Logs - Operation history
- Settings - Configuration and preferences

## Development Notes

- Uses CustomTkinter for modern, responsive UI
- Dark glassmorphism theme with subtle borders
- Fully navigable between all screens
- Mock data for demonstration purposes
- Ready for backend integration