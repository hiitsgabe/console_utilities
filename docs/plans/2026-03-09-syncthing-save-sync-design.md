# Syncthing Save Sync — Design

## Overview

Syncthing integration inside console_utilities that auto-configures save folder syncing between devices using a hub-and-spoke model (Computer <-> Knulli, Computer <-> Android).

## Architecture

### New files
- `src/services/syncthing_service.py` — Syncthing REST API client (check status, add device, add/remove folders, get device ID)
- `src/ui/screens/syncthing_screen.py` — Main sync config screen
- `src/ui/screens/modals/syncthing_folder_modal.py` — Android folder picker for per-system path selection

### Modified files
- `src/ui/screens/settings_screen.py` — Add `--- SAVE SYNC ---` section with `Enable Syncthing Helper` toggle
- `src/config/settings.py` — Add syncthing settings fields
- `src/ui/screens/screen_manager.py` — Register syncthing screen
- `src/app.py` — Handle syncthing screen navigation + actions
- `src/constants.py` — Add default save paths per platform

## Screen Flow

```
Main Menu -> "Syncthing Sync" (only when enabled)
          -> Syncthing Screen
```

### First time setup
1. Check if Syncthing API is reachable (`localhost:8384`)
2. If not found -> show "Syncthing is not installed or not running"
3. If found -> ask role: "Host (Computer)" or "Console (Knulli/Android)"
4. If console -> show char_keyboard to enter host's Device ID
5. Auto-configure all save folders

### After setup — Knulli (simple)
- Status: "Connected to Host: [device name]"
- "Sync All Systems" button — creates folders for all systems at `/userdata/saves/<system>/`
- List of systems with status (Synced / Not synced)
- "Reconfigure" / "Reset" at bottom

### After setup — Android (detailed)
- Same header with connection status
- "Sync All Systems" button at top
- List of systems, each tappable to set/change the local save folder path
- Shows current path per system (or "Not configured")

### After setup — Computer/Host
- Shows Device ID prominently (for consoles to copy)
- Base path setting (default `~/game-saves/`)
- List of systems with status
- "Sync All Systems" creates `<base_path>/<system>/` for each

## Syncthing REST API Usage
- `GET /rest/system/status` — check if running, get device ID
- `GET /rest/config` — read current config
- `POST /rest/config/devices` — add a device (pairing)
- `POST /rest/config/folders` — add a shared folder
- `DELETE /rest/config/folders/{id}` — remove a folder
- API key read from Syncthing's config XML or prompted from user

## Device Pairing
- Host displays its Device ID on screen
- Console user enters it via char_keyboard (Knulli) or paste (Android)
- App adds the host as a device via Syncthing API and shares folders with it

## Default Save Paths

### Knulli/Batocera
`/userdata/saves/<system>/` — auto-detected, no user input needed

### Android
User selects per system. Depends on emulator/core in use.

### Computer (Host)
`~/game-saves/<system>/` — configurable base path, acts as relay/storage

## System List (priority order)
psx, snes, n64, scummvm, gba, gb, gbc, nds, megadrive, nes, psp, dreamcast, mame, fba, segacd, pcengine, atari2600, atari7800, atarilynx, wonderswan, neogeo, gamegear, mastersystem

## Settings Fields
```python
syncthing_enabled: bool = False
syncthing_role: str = ""            # "host" or "console"
syncthing_host_device_id: str = ""
syncthing_base_path: str = ""       # host only, default ~/game-saves/
syncthing_api_key: str = ""
syncthing_folder_overrides: Dict[str, str] = {}  # android per-system path overrides
```
