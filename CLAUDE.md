# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A PyGame-based console utilities application designed for handheld gaming consoles (primarily Knulli RG35xxSP and Batocera-based devices). Features an interactive menu system with D-pad/controller navigation, download management, and automatic file organization.

## Development Commands

### Environment Setup
```bash
make setup      # Create conda environment and install dependencies
make install    # Install in development mode
make dev        # Install with dev dependencies
```

### Running the Application
```bash
make run        # Run with auto-restart on file changes (default)
make debug      # Run without auto-restart to see full error logs
```

### Code Quality
```bash
make format     # Format code with black
make lint       # Lint with flake8
make test       # Run tests with pytest
make clean      # Clean generated files and caches
```

### Building Distributions
```bash
make bundle           # Create pygame bundle (.pygame file + assets)
make bundle-macos     # Create macOS .app bundle (standalone)
make bundle-windows   # Create Windows .exe bundle (standalone)
make build-android    # Build Android APK using Docker
```

## Architecture

### Entry Point
- **src/app.py**: Main application class (`ConsoleUtilitiesApp`) that orchestrates all components and runs the main game loop

### State Management
- **Centralized state in src/state.py**: All application state is managed through the `AppState` dataclass
- State includes: navigation, touch input, download progress, screen state, and application lifecycle
- Services and UI components receive state as parameters rather than managing their own state

### UI Architecture (Atomic Design Pattern)
The UI follows Atomic Design principles for component composition:

- **src/ui/atoms/**: Basic building blocks (buttons, surfaces, progress bars, text)
- **src/ui/molecules/**: Simple component compositions (action_button, download_progress, menu_item, thumbnail)
- **src/ui/organisms/**: Complex UI sections (header, modal_frame, menu_list, grid, char_keyboard)
- **src/ui/templates/**: Page layouts (grid_screen, list_screen, modal_template)
- **src/ui/screens/**: Complete screens (systems_screen, games_screen, settings_screen, etc.)
- **src/ui/screens/modals/**: Modal dialogs (loading_modal, error_modal, search_modal, etc.)
- **src/ui/screens/screen_manager.py**: Manages navigation between screens and modal state

### Services Layer
- **src/services/data_loader.py**: Loads system configurations and manages game data
- **src/services/download.py**: Handles file downloads with progress tracking and resume capability
- **src/services/file_listing.py**: Lists and filters files from remote sources (HTML parsing or JSON APIs)
- **src/services/image_cache.py**: Manages thumbnail loading and caching for game artwork

### Input Handling
- **src/input/controller.py**: Controller/gamepad input handling with button mapping
- **src/input/navigation.py**: D-pad navigation with acceleration and repeat handling
- **src/input/touch.py**: Touch/mouse input with gesture detection (swipe, scroll, tap)

### Configuration
- **src/constants.py**: Global constants, paths, colors, and environment detection (DEV_MODE vs console)
- **src/config/settings.py**: User settings persistence (display preferences, paths, cache settings)
- **src/ui/theme.py**: Centralized design tokens using immutable Theme dataclass

### NSZ Integration
- **src/nsz/**: Embedded NSZ library from [nicoboss/nsz](https://github.com/nicoboss/nsz)
- Provides Nintendo Switch file (NSZ/NSP) decompression capability
- **src/utils/nsz.py**: Wrapper utilities for NSZ decompression operations

## Development Patterns

### Adding New UI Components
1. Place components in the appropriate atomic design folder (atoms, molecules, organisms)
2. Components should accept `state: AppState` and `theme: Theme` as parameters
3. Return pygame Surface objects that can be composed into larger components
4. Use theme tokens from `theme.py` for all colors and spacing

### Adding New Screens
1. Create screen file in `src/ui/screens/`
2. Screens should inherit from base templates when appropriate (list_screen, grid_screen)
3. Register screen in `ScreenManager` (screen_manager.py)
4. Implement screen transition logic using `state.current_screen`

### State Updates
- State is updated in `app.py` through the main event loop
- Services and handlers return new state values or modify state objects passed to them
- UI components are pure functions that render based on current state

### Platform Detection
- `constants.py` detects whether running in DEV_MODE or on console
- Paths automatically adjust based on environment (py_downloads/ vs console paths)
- DEV_MODE is set via environment variable: `DEV_MODE=true`

## Configuration Files

### download.json / added_systems.json
Located in `workdir/` (dev) or root (console). Defines gaming systems with:
- `name`: System display name
- `url`: ROM directory URL (HTML or JSON API)
- `file_format`: Supported file extensions array
- `roms_folder`: Target directory within roms folder
- `regex`: Optional custom HTML parsing regex
- `boxarts`: Optional thumbnail base URL
- `should_unzip`: Auto-extract ZIP files

### config.json
Auto-generated user settings:
- Display preferences (show_thumbnails, view_type)
- Directory paths (work_dir, roms_dir)
- Cache settings and filtering options

## Console Target Environment

The application is designed for Batocera-based handheld consoles:
- Assumes pygame is pre-installed on console
- Native dependencies (zstandard, pycryptodome) must be installed separately
- Pure Python dependencies (requests) are bundled in the .pygame file
- Input mapping configured for common handheld console button layouts
- 800x600 display resolution optimized for small screens
