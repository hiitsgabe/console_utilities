# Console Utilities - macOS Installation Guide

A PyGame-based console utilities application for managing and downloading game backups on macOS.

## Requirements

- macOS 11 (Big Sur) or later
- Apple Silicon (M1/M2/M3) or Intel processor
- Sufficient storage space for downloads
- Network connectivity

## Installation

### Standalone Application (Recommended)

1. **Download**: Extract `macos.zip` from the release
2. **Extract**: Unzip the archive to reveal `Console Utilities.app`
3. **Install**: Drag `Console Utilities.app` to your Applications folder
4. **First Launch**: Right-click the app and select "Open" (required for unsigned apps)
5. **Security Prompt**: Click "Open" when prompted about the unidentified developer

### From Source

```bash
# Clone the repository
git clone https://github.com/hiitsgabe/console_utilities.git
cd console_utilities

# Setup conda environment
conda env create -f environment.yml
conda activate console_utilities

# Install dependencies
pip install -e .[dev]

# Run the application
python src/app.py
```

## Initial Setup

### Configuring Your Archive

1. Prepare your archive JSON file (contains URLs for your backup copies)
2. Place the JSON file in any accessible folder on your system
3. Launch Console Utilities
4. Navigate to **Settings**
5. Set the **Archive JSON Location** to point to your JSON file
6. The app will automatically refresh and load your systems

### Archive JSON Format

Your archive JSON should follow this structure:

```json
[
  {
    "name": "System Name",
    "url": "https://example.com/backups/system/",
    "file_format": [".iso", ".bin", ".zip"],
    "roms_folder": "system_folder",
    "boxarts": "https://example.com/boxart/system/",
    "should_unzip": true
  }
]
```

## Using the Application

### Navigation
- **Mouse/Trackpad**: Click to select, scroll to navigate
- **Keyboard Controls**: Arrow keys to navigate, Enter to select, Escape to go back
- **System Selection**: Browse available systems from the main menu
- **Game Selection**: Select games to download (supports multi-selection with Spacebar)
- **Settings**: Configure download directory and display preferences

### Controls
- **Arrow Keys**: Navigate up/down
- **Enter/Return**: Select/Confirm
- **Escape/⌘Q**: Back/Cancel/Quit
- **Space**: Toggle selection (in game list)
- **Page Up/Down (fn + ↑/↓)**: Jump pages or letters (in game list)

### Downloads
- Downloads are saved to your configured working directory
- Progress tracking with speed indicators
- Resume capability for interrupted downloads
- Automatic extraction for ZIP files (if configured)

## Troubleshooting

### Logs
Logs are generated in the following locations:
- Standalone: `error.log` in the same folder as the application
- After setting working directory: Inside your configured working directory
- Check `py_downloads/error.log` for detailed error information

### Common Issues

**"Cannot be opened because the developer cannot be verified"**
- Right-click the app and select "Open" instead of double-clicking
- Or: Go to System Preferences > Security & Privacy > General and click "Open Anyway"

**Application won't start**: Ensure you have permission to run applications from unidentified developers

**No games showing**: Verify your archive JSON is properly formatted and the file path is correct

**Download failures**: Check storage space, network connectivity, and firewall settings

**Performance issues**: Close other applications, check Activity Monitor for resource usage

**Gatekeeper blocking**: Run the following command to allow the app:
```bash
xattr -cr "/Applications/Console Utilities.app"
```

## Permissions

The application may request the following permissions:
- **Files and Folders**: To read archive JSON and save downloaded files
- **Network**: To download game backups and thumbnails

Grant these permissions when prompted for full functionality.

## Legal Notice and Disclaimer

**IMPORTANT LEGAL DISCLAIMER:**

- **No ROM Data Storage**: This system does not host, store, or distribute any ROM files, game data, or copyrighted content. It is purely a download management tool.

- **No Game Copies**: This application contains no copies of games, ROMs, or any copyrighted gaming content whatsoever.

- **Legal Responsibility**: Users are solely responsible for:
  - Ensuring they have legal rights to download any content
  - Complying with copyright laws in their jurisdiction
  - Verifying the legality of any download sources they configure
  - Understanding that downloading copyrighted content without permission may be illegal

- **Third-Party Sources**: Any websites or download sources referenced in configuration examples are third-party services. Users should research and evaluate the legal status of such sources independently.

- **Legal Use Only**: This tool is intended exclusively for downloading legally owned content, homebrew games, or content explicitly permitted for distribution.

**By using this software, you acknowledge that you understand these legal responsibilities and agree to use it only for lawful purposes.**

## Credits

hiitsgabe @ github
Made w/ <3 in Toronto
