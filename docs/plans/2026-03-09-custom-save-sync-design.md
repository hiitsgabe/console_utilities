# Custom Save Sync — Design

## Overview

Extends the Syncthing save sync feature to support arbitrary save folders or specific files (for ports, standalone games, etc.). A user picks a folder (full sync) or specific files within a folder (filtered sync via `.stignore`). The host computer relays, and receiving devices map to their own local paths.

## sync_info.json

Each custom sync folder contains a `sync_info.json`:

```json
{
  "name": "Balatro Save",
  "source_device": "Knulli RG35xxSP",
  "source_path": "/userdata/roms/ports/Balatro/",
  "sync_mode": "files",
  "sync_files": ["save.dat", "progress.sav"],
  "created": "2026-03-09T12:00:00"
}
```

- `sync_mode`: `"folder"` (everything) or `"files"` (filtered)
- `sync_files`: only present when `sync_mode` is `"files"`

## .stignore (generated for file mode)

```
!sync_info.json
!save.dat
!progress.sav
*
```

Always whitelists `sync_info.json` so metadata syncs to all devices.

## UI Flow — Source Device (Adding)

1. Syncthing screen -> CUSTOM SAVES -> "Add Custom Save"
2. Name input (e.g., "Balatro Save")
3. Folder browser opens
4. User either:
   - **Selects the folder** (press Select on the folder itself) -> `sync_mode: "folder"`
   - **Enters the folder and selects specific files** (checkboxes) -> `sync_mode: "files"`
5. App creates Syncthing shared folder + writes `sync_info.json` + `.stignore` if file mode

## UI Flow — Receiving Device

In CUSTOM SAVES section:

```
--- CUSTOM SAVES ---
Add Custom Save
Balatro Save (2 files)     Not mapped
Stardew Valley Save        Synced
```

- "Not mapped" -> tap -> folder browser to pick local folder
- If `sync_mode: "files"`, the same `.stignore` is applied to the mapped folder
- "Synced" -> tap -> option to change path or remove

## Host Behavior

- Receives at `<base_path>/custom/<folder-id>/`
- `autoAcceptFolders: true` handles this automatically
- Just stores and relays — no UI needed

## Settings

```python
syncthing_custom_saves: List[Dict[str, str]] = field(default_factory=list)
# Each: {"name": "...", "folder_id": "...", "local_path": "...", "mapped": true/false}
```

## Folder ID Convention

- `custom-<sanitized-name>` (lowercase, spaces to hyphens, strip special chars)
- Example: "Balatro Save" -> `custom-balatro-save`

## Receiving Device Mapping

When Device B maps a custom save:

1. Syncthing initially syncs to staging: `<base_path>/custom/<id>/`
2. User picks local folder (e.g., `/storage/emulated/0/Balatro/`)
3. App moves synced files from staging to the chosen folder
4. Reconfigures the Syncthing folder path to point to the chosen folder
5. Writes the same `.stignore` if file mode

## Data Flow

```
Device A (source path) <-> Host (~/game-saves/custom/<id>/) <-> Device B (mapped path)
```

All three use the same Syncthing folder ID. On Device A and mapped Device B, the folder points to the actual save location. On the host and unmapped devices, it points to a staging directory.
