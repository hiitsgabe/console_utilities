# Console Utilities - Windows Installation Guide

A PyGame-based console utilities application for managing and downloading game backups on Windows.

## Requirements

- Windows 10 or later (64-bit)
- Sufficient storage space for downloads
- Network connectivity

## Installation

### Standalone Executable (Recommended)

1. **Download**: Extract `windows.zip` from the release
2. **Extract**: Unzip the archive to your desired location
3. **Run**: Double-click `Console Utilities.exe` to launch the application
4. **Windows Defender**: If prompted, allow the application to run (it's not signed but safe)

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
- **Mouse Controls**: Click to select, scroll to navigate
- **Keyboard Controls**: Arrow keys to navigate, Enter to select, Escape to go back
- **System Selection**: Browse available systems from the main menu
- **Game Selection**: Select games to download (supports multi-selection with Spacebar)
- **Settings**: Configure download directory and display preferences

### Controls
- **Arrow Keys**: Navigate up/down
- **Enter**: Select/Confirm
- **Escape**: Back/Cancel
- **Space**: Toggle selection (in game list)
- **Page Up/Down**: Jump pages or letters (in game list)

### Downloads
- Downloads are saved to your configured working directory
- Progress tracking with speed indicators
- Resume capability for interrupted downloads
- Automatic extraction for ZIP files (if configured)

## Troubleshooting

### Logs
Logs are generated in the following locations:
- Standalone: `error.log` in the same folder as the executable
- After setting working directory: Inside your configured working directory
- Check `py_downloads/error.log` for detailed error information

### Common Issues

**Application won't start**: Ensure you have the Visual C++ Redistributable installed

**No games showing**: Verify your archive JSON is properly formatted and the file path is correct

**Download failures**: Check storage space, network connectivity, and firewall settings

**Performance issues**: Close other applications, ensure your system meets minimum requirements

**Antivirus blocking**: Add the application folder to your antivirus exceptions

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
