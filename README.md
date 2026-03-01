This project is an exercise to test Vibe Coding's capabilities. (CLAUDE)

# Console Utilities

<div align="center">
  <img src="assets/images/logo_big.png" alt="Console Utilities Logo" width="200"/>
  <br><br>
  <a href="https://hiitsgabe.github.io/console_utilities/">Website</a> &middot;
  <a href="https://github.com/hiitsgabe/console_utilities/releases">Downloads</a>
</div>

![Screenshot](assets/images/screenshot.png)

**Disclaimer: This application does not endorse any form of piracy. Only download games you legally own.**

A PyGame-based utility suite for handheld gaming consoles, with a retro CRT-themed interface designed for D-pad and controller navigation. Browse, download, organize, and manage game files from configurable sources. Supports HTML directory listings, JSON APIs, and Internet Archive. Runs on Batocera/Knulli handhelds, macOS, Windows, Linux, and Android.

## Features

### Download Management
- **Batch Downloads**: Select multiple games and download them in a queue with real-time progress, speed, and ETA
- **Resume Capability**: Interrupted downloads can be resumed
- **Automatic Extraction**: ZIP and RAR files are extracted and organized into the correct system folder
- **NSZ Decompression**: Built-in Nintendo Switch NSZ to NSP conversion

### Browsing & Navigation
- **Multiple View Modes**: List view and grid layout with box art thumbnails
- **Search**: Filter games by name within any system
- **Region Filtering**: USA-only filter with configurable regex per system
- **Installed Detection**: Optionally hide games already downloaded

### Sports ROM Patcher
- **Live Roster Updates**: Fetch current or historical season rosters from public sports APIs and patch them into your legally owned game ROMs
- **Multi-Platform Support**: Patchers for retro soccer and hockey titles across PS1, SNES, Genesis, and PSP
- **Step-by-Step Workflow**: Guided process — select season, fetch rosters, preview teams, pick your ROM, and patch
- **Roster Preview**: View fetched teams and players before committing changes
- **Player Attributes**: Maps real-world stats (goals, assists, speed, etc.) to in-game attribute scales
- **Team Customization**: Update team names, kit/jersey colors, and flag designs where supported
- **Historical Seasons**: Access roster data from past seasons via public APIs (availability varies by provider)
- **Non-Destructive**: Saves patched output to a new file, leaving your original ROM untouched

See the [Sports ROM Patcher Guide](docs/sports-rom-patcher.md) for detailed usage instructions.

### Utilities
- **Direct URL Download**: Download a file from any URL
- **Internet Archive Integration**: Download individual files or add entire IA collections as systems
- **Image Scraping**: Scrape game artwork from multiple providers (Libretro, ScreenScraper, TheGamesDB, RAWG, IGDB) with batch mode support
- **File Deduplication**: Detect and remove duplicate files (safe and fuzzy matching)
- **Filename Cleanup**: Batch rename files to clean formats
- **Ghost File Cleaner**: Find and remove orphaned split archives
- **ZIP/RAR Extraction**: Extract archives from the file browser

### System Management
- **Add Custom Systems**: Discover systems from directory listings or manually configure new sources
- **Per-System Settings**: Custom ROM folders, hide/show systems
- **Multiple Server Formats**: HTML directory listings, JSON APIs, Internet Archive metadata API
- **Authentication**: Bearer tokens, cookies, and IA S3 credentials

### Interface
- **CRT Theme**: Phosphor green retro aesthetic with scanlines, vignette, and bezel effects
- **Controller & Keyboard**: Full D-pad/gamepad support with acceleration and touch/mouse input
- **Auto-Updates**: Check for and install app updates from within the app

## Installation

### Development Setup

```bash
# Setup conda environment and install dependencies
make setup

# Run with auto-restart on file changes
make run

# Run without auto-restart (full error logs)
make debug
```

Or manually:

```bash
conda env create -f environment.yml
conda activate console_utilities
pip install -e .[dev]
DEV_MODE=true python src/app.py
```

### Console Installation (Batocera/Knulli)

1. Create a `downloader` folder inside your console's `pygame` roms directory
2. Run `make bundle` to create the distribution package
3. Copy `dist/pygame.zip` contents (`console_utils.pygame` + `assets/`) to the console folder
4. Rescan games in EmulationStation
5. Navigate to the PyGame library and launch Console Utilities

### Building for Other Platforms

```bash
make bundle            # PyGame bundle for consoles
make bundle-macos      # macOS .app standalone
make bundle-windows    # Windows .exe standalone
make build-android     # Android APK (Docker-based)
```

## Configuration

### System Sources (`bundled_data.json`)

Systems are configured via JSON files that define where to find files and how to parse server responses. See the docs for details:

- [Server Response Format](docs/server-response-format.md) - How your server needs to respond for the app to detect files
- [Adding a System](docs/adding-a-system.md) - How to add custom systems

### User Settings (`config.json`)

Runtime settings are auto-generated and stored in `config.json`:

- **Directories**: Working directory, ROMs directory
- **Display**: Box art thumbnails, USA-only filter, skip installed games
- **Internet Archive**: Enable/disable, S3 credentials
- **Scraper**: Provider selection (Libretro, ScreenScraper, TheGamesDB, RAWG, IGDB), frontend format (EmulationStation, ES-DE, RetroArch, Pegasus), API credentials
- **NSZ**: Enable/disable, keys file path

## Controls

### System Selection
- **D-pad Up/Down** or **Arrow Keys**: Navigate systems
- **B Button** or **Enter**: Select system
- **A Button** or **Escape**: Exit application
- **SELECT**: Toggle between list and grid view

### Game Selection
- **D-pad Up/Down** or **Arrow Keys**: Navigate games
- **D-pad Left/Right** or **Page Up/Down**: Jump by letter
- **B Button** or **Space**: Toggle game selection
- **A Button** or **Escape**: Return to systems
- **START** or **Enter**: Begin download
- **SELECT**: Toggle view type and thumbnail display

### During Download
- **A Button** or **Escape**: Cancel download
- Real-time progress display with speed and ETA

## Project Structure

```
console_utilities/
├── src/
│   ├── app.py                          # Main application entry point
│   ├── state.py                        # Centralized state management
│   ├── constants.py                    # Global constants and paths
│   ├── config/
│   │   └── settings.py                # User settings persistence
│   ├── services/
│   │   ├── data_loader.py            # System/game data loading
│   │   ├── download_manager.py       # Download queue management
│   │   ├── file_listing.py           # Remote file listing (HTML/JSON/IA)
│   │   ├── image_cache.py            # Thumbnail caching
│   │   ├── installed_checker.py      # Local file detection
│   │   ├── internet_archive.py       # Internet Archive API integration
│   │   ├── scraper_manager.py        # Image scraper orchestration
│   │   ├── scraper_providers/        # Libretro, ScreenScraper, etc.
│   │   ├── we_patcher/              # PS1 soccer ROM patcher
│   │   ├── iss_patcher/             # SNES soccer ROM patcher
│   │   ├── nhl94_genesis_patcher/   # Genesis hockey ROM patcher
│   │   ├── nhl94_snes_patcher/      # SNES hockey ROM patcher
│   │   └── nhl07_psp_patcher/       # PSP hockey ISO patcher
│   ├── input/
│   │   ├── controller.py             # Controller/gamepad input
│   │   ├── navigation.py             # D-pad navigation with acceleration
│   │   └── touch.py                  # Touch/mouse input
│   ├── ui/                            # UI components (Atomic Design)
│   │   ├── theme.py                  # Design tokens and theming
│   │   ├── atoms/                    # Basic components
│   │   ├── molecules/                # Composite components
│   │   ├── organisms/                # Complex sections
│   │   ├── templates/                # Page layouts
│   │   └── screens/                  # Complete screens and modals
│   ├── utils/                         # Logging, formatting, NSZ wrapper
│   └── nsz/                           # Embedded NSZ library
├── assets/
│   ├── bundled_data.json             # System configuration
│   ├── docs/                         # Platform-specific build docs
│   ├── examples/                     # Example configuration files
│   ├── fonts/                        # VT323 retro font
│   └── images/                       # Logo and screenshots
├── docs/                              # User documentation
│   ├── sports-rom-patcher.md        # Sports ROM patcher guide
│   ├── server-response-format.md     # Server response format guide
│   └── adding-a-system.md           # Adding custom systems guide
├── workdir/                           # Development runtime data
├── dist/                              # Built distributions
├── Makefile                           # Build and development commands
├── buildozer.spec                     # Android build configuration
├── console_utils.spec                 # macOS PyInstaller configuration
├── console_utils_win.spec             # Windows PyInstaller configuration
├── environment.yml                    # Conda environment specification
├── pyproject.toml                     # Python project configuration
└── README.md
```

## Dependencies

- Python 3.11+
- pygame >= 2.0.0
- requests >= 2.25.0
- rarfile (bundled for console)
- watchdog (development only)
- black, flake8 (development only)

## Compatibility

- **Console**: Knulli RG35xxSP and other Batocera-based handheld consoles
- **Desktop**: macOS (.app bundle), Windows (.exe bundle), Linux
- **Mobile**: Android (APK via Buildozer)
- **Display**: 800x600 resolution, optimized for small screens

## Documentation

- [Sports ROM Patcher Guide](docs/sports-rom-patcher.md) - How the sports roster patcher works
- [Server Response Format](docs/server-response-format.md) - How your server needs to respond for the app to detect and list files
- [Adding a System](docs/adding-a-system.md) - How to add custom gaming systems
- [PyGame Bundle Guide](assets/docs/pygame.md) - Deploying to Batocera/Knulli consoles
- [macOS Build Guide](assets/docs/macos.md) - Building the macOS standalone app
- [Windows Build Guide](assets/docs/windows.md) - Building the Windows standalone app
- [Android Build Guide](assets/docs/android.md) - Building the Android APK

## Legal Notice and Disclaimer

**IMPORTANT LEGAL DISCLAIMER:**

- **No ROM Data Storage**: This system does not host, store, or distribute any ROM files, game data, or copyrighted content. It is purely a download management and ROM patching tool.

- **No Game Copies**: This application contains no copies of games, ROMs, ISOs, or any copyrighted gaming content whatsoever.

- **ROM Patching — Original Copies Only**: The sports ROM patcher feature requires users to provide their own legally obtained ROM or ISO files dumped from original game media they own. This project does not provide, link to, or facilitate the acquisition of any game files. Any ROM or ISO used with the patcher must come from an original copy of the game that you legally own.

- **No Affiliation**: This project is not affiliated with, endorsed by, or associated with any game publishers, developers, sports leagues, or rights holders.

- **Example Configuration**: Any included configuration files serve as examples only. They demonstrate how the system works but do not endorse or recommend any specific download sources.

- **Legal Responsibility**: Users are solely responsible for:
  - Ensuring they have legal rights to download any content
  - Providing only legally owned ROM/ISO files for patching
  - Complying with copyright laws in their jurisdiction
  - Verifying the legality of any download sources they configure
  - Understanding that downloading copyrighted content without permission may be illegal

- **Third-Party Sources**: Any websites or download sources referenced in configuration examples are third-party services. Users should research and evaluate the legal status of such sources independently.

- **Legal Use Only**: This tool is intended exclusively for downloading legally owned content, homebrew games, or content explicitly permitted for distribution. The ROM patching features are intended solely for personal use with games you legally own.

- **No Liability**: The developers and contributors of this project assume no responsibility or liability for any misuse of this software. Users bear full responsibility for how they use this tool and must ensure compliance with all applicable laws.

**By using this software, you acknowledge that you understand these legal responsibilities and agree to use it only for lawful purposes.**

## Credits & Acknowledgments

This project incorporates the following open source libraries:

- **NSZ Library**: NSZ compression/decompression functionality provided by [nicoboss/nsz](https://github.com/nicoboss/nsz) - A compression/decompression tool with fast compression and decompression for various file formats.

## Troubleshooting

### Error Logging
- Check `error.log` in the application directory for detailed error information
- On Batocera systems: `/userdata/roms/pygame/downloader/error.log`
- Development: `py_downloads/error.log` in the project root

### Common Issues
- **No games showing**: Verify your system configuration and network connectivity
- **Download failures**: Check available disk space and directory permissions
- **Display issues**: Ensure pygame dependencies are properly installed
- **Thumbnails not loading**: Check that the `boxarts` URL is correct and accessible

### Development
```bash
make format    # Format code with black
make lint      # Lint code with flake8
make test      # Run tests with pytest
make clean     # Clean build artifacts
```

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss proposed modifications.
