# Syncthing Save Sync

> **This is not Syncthing.** Console Utilities does not include, bundle, or replace [Syncthing](https://syncthing.net/). This feature is a **helper tool** that talks to an already-installed Syncthing instance through its REST API. It simplifies the setup of shared folders and device pairing so you don't have to configure everything manually through the Syncthing Web UI. You still need Syncthing installed and running on every device you want to sync.

---

## What It Does

Game saves on Batocera and Knulli consoles live in system-specific folders (`/userdata/saves/psx/`, `/userdata/saves/snes/`, etc.). If you also play on a computer, Android device, or a second console, keeping saves in sync between all of them is tedious — you'd need to manually set up dozens of shared folders in Syncthing, pair devices, and configure ignore patterns.

This helper automates all of that. It:

- **Creates shared folders** for 22+ gaming systems with one button press
- **Pairs devices** by entering a Device ID (no need to open the Syncthing Web UI)
- **Monitors sync status** for each system directly in the app
- **Supports custom saves** for standalone games or non-standard save locations
- **Configures versioning** automatically (5 previous versions of each file are kept)

---

## How It Works

### Hub-and-Spoke Architecture

The sync model uses a **hub (computer)** and **spokes (consoles/Android)**:

```
                    ┌─────────────────┐
                    │   Computer      │
                    │   (Host)        │
                    │                 │
                    │  ~/game-saves/  │
                    │    psx/         │
                    │    snes/        │
                    │    n64/         │
                    │    ...          │
                    └────┬───────┬────┘
                         │       │
              ┌──────────┘       └──────────┐
              │                             │
     ┌────────┴────────┐          ┌─────────┴───────┐
     │  Knulli Console │          │  Android Device  │
     │                 │          │                  │
     │ /userdata/      │          │ (emulator save   │
     │   saves/psx/    │          │  folders)        │
     │   saves/snes/   │          │                  │
     └─────────────────┘          └──────────────────┘
```

- **Host (Computer):** Central relay that stores save backups. Can pair with multiple consoles. Saves are stored in `~/game-saves/<system>/` by default (configurable).
- **Console (Knulli/Batocera/Android):** Syncs saves to the host. Each console pairs with one host.

All folders are **bidirectional** (`sendreceive`) — changes on any device propagate to all others.

---

## Prerequisites

1. **Syncthing installed and running** on every device you want to sync
   - Linux: `sudo apt install syncthing` or `systemctl --user start syncthing`
   - macOS: `brew install syncthing` or download from [syncthing.net](https://syncthing.net/)
   - Android: Install [Syncthing-Fork](https://github.com/catfriend1/syncthing-android) from F-Droid or Play Store
   - Knulli/Batocera: Check your firmware's package manager or built-in Syncthing support
2. **Syncthing accessible** at `http://localhost:8384` (default)
3. **Devices on the same network** (or with relay servers configured in Syncthing)

---

## Setup

### Step 1: Enable the Feature

Go to **Settings > Save Sync > Enable Syncthing Helper** and toggle it on. A "Syncthing Sync" entry will appear in the main menu.

### Step 2: Choose Your Role

When you open Syncthing Sync, the app checks if Syncthing is running. If it connects successfully, you'll be asked to pick a role:

| Role | Use When |
|------|----------|
| **Host (Computer)** | This is your computer — the central hub that stores all save backups |
| **Console (Knulli/Android)** | This is a handheld console or Android device that syncs to the host |

### Step 3a: Host Setup

1. Choose **Host (Computer)**
2. The screen shows your **Device ID** — a 56-character identifier like `XXXXXXX-XXXXXXX-XXXXXXX-XXXXXXX-XXXXXXX-XXXXXXX-XXXXXXX-XXXXXXX`
3. Share this Device ID with your console (screenshot it, write it down, etc.)
4. Click **Sync All Systems** to create shared folders for all 22 systems
5. Done — the host is ready and waiting for consoles to connect

### Step 3b: Console Setup (Knulli/Batocera)

1. Choose **Console (Knulli/Android)**
2. Enter the host's Device ID using the on-screen keyboard
3. The app pairs with the host automatically
4. Click **Sync All Systems** — folders are created at `/userdata/saves/<system>/`
5. Play games — saves sync automatically whenever both devices are on the network

### Step 3c: Console Setup (Android)

Same as Knulli, but with one extra step: **Android emulators store saves in different locations**, so you need to tell the app where each system's saves are.

1. Choose **Console (Knulli/Android)** and enter the host's Device ID
2. For each system you play, tap its name in the system list
3. A folder browser opens — navigate to where your emulator stores saves for that system
4. Select the folder
5. Repeat for other systems, then click **Sync All Systems**

---

## Supported Systems

| System | Folder ID |
|--------|-----------|
| PlayStation (PSX) | `psx` |
| Super Nintendo (SNES) | `snes` |
| Nintendo 64 (N64) | `n64` |
| Game Boy Advance (GBA) | `gba` |
| Game Boy | `gb` |
| Game Boy Color | `gbc` |
| Nintendo DS | `nds` |
| PlayStation Portable (PSP) | `psp` |
| Sega Mega Drive / Genesis | `megadrive` |
| Nintendo Entertainment System (NES) | `nes` |
| Sega Dreamcast | `dreamcast` |
| MAME | `mame` |
| Final Burn Alpha (FBA) | `fba` |
| Sega CD | `segacd` |
| PC Engine / TurboGrafx-16 | `pcengine` |
| Atari 2600 | `atari2600` |
| Atari 7800 | `atari7800` |
| Atari Lynx | `atarilynx` |
| WonderSwan | `wonderswan` |
| Neo Geo | `neogeo` |
| Sega Game Gear | `gamegear` |
| Sega Master System | `mastersystem` |
| ScummVM | `scummvm` |

---

## Custom Saves

Standard sync covers the 22+ systems above. For anything else — standalone games, mods with custom save locations, or specific files you want backed up — use **Custom Saves**.

### Creating a Custom Save

1. From the Syncthing Sync screen, select **Add Custom Save**
2. Enter a name (e.g., "Balatro Save", "Doom Config")
3. Browse to the folder containing your save data
4. Choose sync mode:
   - **Entire Folder** — syncs everything in the folder
   - **Select Files** — pick specific files; everything else is ignored

### File Selection Mode

When you choose "Select Files", a checklist of all files in the folder appears. Only checked files are synced. Behind the scenes, the app writes a `.stignore` file that whitelists your selections:

```
# Only these files are synced:
!sync_info.json
!save_slot_1.dat
!config.ini
*
```

This is useful for large folders where only a few files matter.

### Mapping Custom Saves on Other Devices

When a custom save is created on the host, it appears as **"Not mapped"** on consoles. To map it:

1. Tap the custom save name
2. Select **Change Path**
3. Browse to where you want the files to live on this device
4. Files begin syncing to the chosen location

---

## Status Indicators

The system list shows the current sync state for each system:

| Status | Meaning |
|--------|---------|
| **Synced** | All files are in sync across devices |
| **Syncing...** | Files are actively transferring |
| **Scanning...** | Syncthing is checking for changes |
| **Error** | Something went wrong (check Syncthing Web UI for details) |
| **-** | Folder not yet created/configured |
| **Not configured** | Android: save folder path not set for this system |
| **Not mapped** | Custom save received but local path not chosen yet |

---

## Versioning & File Recovery

Every shared folder is configured with **simple versioning** that keeps the last **5 versions** of each file. If a save gets corrupted or accidentally overwritten, you can recover a previous version.

To restore an old version, open the **Syncthing Web UI** (`http://localhost:8384`), find the affected folder, and look under version history. There is no in-app UI for version recovery — use Syncthing directly.

---

## Reconfiguring

To start fresh (change role, re-pair with a different host, etc.):

1. From the Syncthing Sync screen, select **Reconfigure**
2. Confirm the reset
3. Your role and device pairing are cleared
4. Existing shared folders in Syncthing are **not deleted** — you can remove them manually in the Syncthing Web UI if needed

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Syncthing not found" | Make sure Syncthing is installed and running. On Linux: `systemctl --user start syncthing`. Click **Retry Connection**. |
| Saves not syncing | Check that both devices are on the same network. Verify folder status in the Syncthing Web UI (`localhost:8384`). |
| "Failed to detect API key" | The app looks for Syncthing's `config.xml` in standard locations. If your install is non-standard, get the API key from **Syncthing Web UI > Settings > API Key**. |
| Android system shows "Not configured" | Tap the system name and select the folder where your emulator stores saves for that system. |
| Custom save shows "Not mapped" | Tap the custom save and choose **Change Path** to set where the files should go on this device. |
| Accidentally deleted a save | Open Syncthing Web UI, find the folder, and restore from version history (up to 5 previous versions). |
| Conflict between devices | If the same file is modified on two devices at the same time, Syncthing keeps both — one as a `.sync-conflict` file. You choose which to keep. |

---

## Settings Reference

All Syncthing settings are stored in `config.json`:

| Setting | Description |
|---------|-------------|
| `syncthing_enabled` | Feature toggle (true/false) |
| `syncthing_role` | `"host"` or `"console"` |
| `syncthing_host_device_id` | The paired host's Device ID (console only) |
| `syncthing_base_path` | Where the host stores saves (default: `~/game-saves`) |
| `syncthing_api_key` | Auto-detected from Syncthing's config.xml |
| `syncthing_folder_overrides` | Per-system path overrides (Android) |
| `syncthing_custom_saves` | List of custom save configurations |

---

## Important Notes

- **This tool does not replace Syncthing.** It only automates folder and device configuration through Syncthing's REST API. All actual file syncing is done by Syncthing itself.
- **Syncthing must be running** on all devices for sync to work. If Syncthing is stopped, saves won't sync until it's started again.
- **No data passes through Console Utilities.** Save files travel directly between devices via Syncthing's own encrypted protocol.
- **First sync may take time** depending on how many saves you have and your network speed.
- **Back up your saves** before enabling sync for the first time, just in case.
