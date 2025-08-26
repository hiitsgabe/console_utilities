# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Kivy-based ROM downloader application designed for handheld gaming consoles, specifically tested with Knulli RG35xxSP. The application provides an interactive menu system for downloading game ROMs from various configured sources.

**IMPORTANT SECURITY NOTE**: This project is designed as a download management tool only and contains no ROM data. It includes comprehensive legal disclaimers and emphasizes that users must only download content they legally own.

## Development Environment

### Setup Commands
```bash
# Using Make (Recommended)
make setup    # Create conda environment and install dependencies
make run      # Run with auto-restart on file changes
make help     # Show all available commands
make clean    # Clean generated files and caches
make format   # Format code with black
make lint     # Lint code with flake8
make build    # Create distribution package for console deployment
make test     # Run tests with pytest

# Manual Setup
conda env create -f environment.yml
conda activate roms_downloader
pip install -e .[dev]

# Run application
python src/main.py
```

### Dependencies
**Runtime:**
- Python 3.11+
- kivy (UI framework)
- kivymd (material design components)
- pygame >= 2.0.0 (controller support) 
- requests >= 2.25.0 (HTTP downloads)
- nsz (Nintendo Switch decompression)

**Development:**
- watchdog (auto-restart during development)
- black (code formatting)
- flake8 (linting)
- pytest (testing framework)
- pyinstaller (distribution building)

## Architecture

### Core Components

**Main Application (`src/main.py`)**: Kivy-based application containing:
- **Screen Management**: ScreenManager with systems, games, and settings screens
- **Controller Support**: Full gamepad integration with mapping modal
- **Navigation Management**: Centralized screen navigation with transitions
- **Focus Management**: D-pad navigation for UI elements

### Component Structure

**Atomic Design Pattern**:
- `src/components/atoms/`: Basic UI elements (buttons, labels, inputs, transitions, loading animations)
- `src/components/molecules/`: Composed components (search bar, game items, navigation manager, loading indicators, virtual scroll lists)
- `src/components/organisms/`: Complex components (game browser, controller mapping modal)

**Screens**:
- `src/screens/systems_screen.py`: System selection interface
- `src/screens/games_screen.py`: Game browsing and selection
- `src/screens/settings_screen.py`: Application configuration

**Services**:
- `src/services/download_service.py`: Multi-threaded downloading with progress tracking and resume capability
- `src/services/nsz_service.py`: Nintendo Switch NSZ file decompression

**Utilities**:
- `src/utils/settings_manager.py`: JSON-based configuration management
- `src/utils/json_reader.py`: Game system configuration parser
- `src/utils/controller_manager.py`: Controller detection and mapping
- `src/utils/controller_input.py`: Input event handling and action mapping
- `src/utils/focus_manager.py`: UI focus navigation for controller support

### Key Features

**Navigation Modes**:
- `systems`: Browse available gaming systems 
- `games`: Browse and select games within a system
- `settings`: Configure application behavior

**View Types**:
- List view: Traditional vertical list with thumbnails
- Grid view: 4-column grid layout for visual browsing

**Download System**:
- Supports multiple source types: Direct URLs, HTML directory parsing, JSON APIs
- Automatic file extraction for ZIP archives and NSZ decompression
- Configurable work and ROM directories
- Real-time progress tracking with speed indicators
- Multi-threaded downloads with queue management

**Controller Support**:
- Automatic controller detection and mapping
- Controller mapping modal for initial setup
- Full D-pad navigation throughout the application
- Action callbacks for select, back, start buttons

## Configuration

### System Configuration (`assets/config/download.json`)
Each gaming system entry supports:
- `name`: Display name
- `url`: Base URL for ROM directory listing  
- `file_format`: Supported file extensions
- `roms_folder`: Target directory for downloaded files
- `regex`: Custom regex for HTML parsing (optional)
- `boxarts`: Base URL for game thumbnails
- `should_unzip`: Auto-extract ZIP files
- `should_decompress_nsz`: Decompress NSZ files (Nintendo Switch)
- `should_filter_usa`: Filter for USA region games

### User Settings (`config.json`)
Runtime settings stored in script directory:
- Display preferences (box-art, view type)
- Directory paths (work, ROM directories) 
- Cache settings and USA-only filtering

### Environment Detection
Application auto-detects platform and sets appropriate default paths:
- **Batocera/Console**: `/userdata/roms`, `/userdata/py_downloads`
- **Development**: Script directory relative paths (`./roms`, `./py_downloads`)
- **Distribution**: Built using `make build` for console deployment

## Development Guidelines

### Error Handling
All operations include comprehensive error logging to `error.log` with timestamps and stack traces. Check this file when debugging issues.

### Threading Model  
- Main UI thread handles all Kivy operations
- Background threads for downloads and file operations
- Thread-safe communication via Kivy's Clock.schedule_once for UI updates

### Controller Integration
- Controller manager handles device detection and mapping persistence
- Focus manager provides D-pad navigation for all UI elements
- Controller input system maps hardware events to application actions

### Platform Compatibility
Designed for embedded Linux systems but runs on desktop for development. The Kivy framework provides cross-platform compatibility while maintaining controller support.

### File Operations
- Work directory for temporary downloads with configurable location
- Atomic file moves to prevent corruption during transfers
- ZIP extraction and NSZ decompression with proper file organization
- Settings persistence via JSON with automatic backup/restore

### Component Development
When creating new components:
- Follow the atomic design pattern (atoms → molecules → organisms)
- Use FocusManager for controller navigation support
- Implement proper cleanup in component lifecycle methods
- Follow Kivy widget conventions for properties and events

### Build System
- **Makefile**: Provides common development tasks and CI/CD integration
- **Conda Environment**: Isolated dependency management with cross-platform support
- **Distribution Building**: Creates console-ready files in `dist/` directory
- **Code Quality**: Integrated formatting (black) and linting (flake8) with pre-commit hooks