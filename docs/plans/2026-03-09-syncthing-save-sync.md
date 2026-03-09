# Syncthing Save Sync Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Syncthing-based save sync with a hub-and-spoke model (Computer <-> Knulli, Computer <-> Android) to console_utilities.

**Architecture:** A new `SyncthingService` talks to Syncthing's REST API to auto-configure shared folders. A new `SyncthingScreen` renders the config UI. Settings toggle enables the feature and adds a main menu entry. On Knulli, all save folders are auto-detected. On Android, the user picks paths per system. A computer acts as the hub relay.

**Tech Stack:** Python, requests (HTTP to Syncthing REST API), pygame (UI), existing app patterns (ListScreenTemplate, AppState dataclass, settings toggle)

---

### Task 1: Add Syncthing settings fields

**Files:**
- Modify: `src/config/settings.py`

**Step 1: Add syncthing fields to Settings dataclass**

In `src/config/settings.py`, add these fields to the `Settings` dataclass after the `web_companion_enabled` field:

```python
# Syncthing Save Sync
syncthing_enabled: bool = False
syncthing_role: str = ""  # "host" or "console"
syncthing_host_device_id: str = ""
syncthing_base_path: str = ""  # host only, default ~/game-saves/
syncthing_api_key: str = ""
syncthing_folder_overrides: Dict[str, str] = field(default_factory=dict)  # android per-system path overrides
```

**Step 2: Commit**

```bash
git add src/config/settings.py
git commit -m "feat(syncthing): add syncthing settings fields"
```

---

### Task 2: Add settings screen toggle

**Files:**
- Modify: `src/ui/screens/settings_screen.py`

**Step 1: Add SAVE_SYNC section**

Add a new section constant to `SettingsScreen`:

```python
# Save Sync section
SAVE_SYNC_SECTION = [
    "--- SAVE SYNC ---",
    "Enable Syncthing Helper",
]
```

**Step 2: Add section to _get_settings_items**

In the `_get_settings_items` method, add the save sync section. Place it after the Web Companion section and before the Android section:

```python
# Add Save Sync section
divider_indices.add(len(items))
items.extend(self.SAVE_SYNC_SECTION)
```

**Step 3: Add value display in render**

In the `render` method's item loop, add:

```python
elif item == "Enable Syncthing Helper":
    value = "ON" if settings.get("syncthing_enabled", False) else "OFF"
    items.append((item, value))
```

**Step 4: Add action mapping in get_setting_action**

In the `actions` dict inside `get_setting_action`, add:

```python
"Enable Syncthing Helper": "toggle_syncthing_enabled",
```

**Step 5: Commit**

```bash
git add src/ui/screens/settings_screen.py
git commit -m "feat(syncthing): add Enable Syncthing Helper toggle to settings"
```

---

### Task 3: Add main menu entry

**Files:**
- Modify: `src/ui/screens/systems_screen.py`

**Step 1: Add syncthing entry to _ALL_ROOT_ENTRIES**

Add after the `("Sports Game Updater", "sports_patcher")` entry:

```python
("Syncthing Sync", "syncthing"),
```

**Step 2: Add visibility filter in _build_root_menu**

In `_build_root_menu`, add a filter for the syncthing entry (after the sports_patcher filter):

```python
if action == "syncthing":
    if not settings.get("syncthing_enabled", False):
        continue
```

**Step 3: Commit**

```bash
git add src/ui/screens/systems_screen.py
git commit -m "feat(syncthing): add Syncthing Sync to main menu"
```

---

### Task 4: Create SyncthingService

**Files:**
- Create: `src/services/syncthing_service.py`

**Step 1: Write the service**

```python
"""
Syncthing REST API client for save sync configuration.
Communicates with local Syncthing instance to auto-configure shared folders.
"""

import json
import os
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple, Any

import requests

from constants import BUILD_TARGET, DEV_MODE


# Default systems with their Knulli/Batocera save paths
SYNC_SYSTEMS = [
    "psx", "snes", "n64", "scummvm", "gba", "gb", "gbc", "nds",
    "megadrive", "nes", "psp", "dreamcast", "mame", "fba",
    "segacd", "pcengine", "atari2600", "atari7800", "atarilynx",
    "wonderswan", "neogeo", "gamegear", "mastersystem",
]

SYNCTHING_API_URL = "http://localhost:8384"


class SyncthingService:
    """Client for Syncthing REST API."""

    def __init__(self, api_key: str = "", api_url: str = SYNCTHING_API_URL):
        self.api_key = api_key
        self.api_url = api_url

    def _headers(self) -> Dict[str, str]:
        return {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }

    def is_running(self) -> bool:
        """Check if Syncthing is reachable."""
        try:
            r = requests.get(
                f"{self.api_url}/rest/system/status",
                headers=self._headers(),
                timeout=3,
            )
            return r.status_code == 200
        except Exception:
            return False

    def get_device_id(self) -> str:
        """Get this device's Syncthing Device ID."""
        try:
            r = requests.get(
                f"{self.api_url}/rest/system/status",
                headers=self._headers(),
                timeout=5,
            )
            r.raise_for_status()
            return r.json().get("myID", "")
        except Exception:
            return ""

    def get_config(self) -> Dict[str, Any]:
        """Get current Syncthing config."""
        try:
            r = requests.get(
                f"{self.api_url}/rest/config",
                headers=self._headers(),
                timeout=5,
            )
            r.raise_for_status()
            return r.json()
        except Exception:
            return {}

    def add_device(self, device_id: str, name: str = "console_utils") -> bool:
        """Add a device to Syncthing."""
        try:
            device = {
                "deviceID": device_id,
                "name": name,
                "addresses": ["dynamic"],
                "autoAcceptFolders": True,
            }
            r = requests.post(
                f"{self.api_url}/rest/config/devices",
                headers=self._headers(),
                json=device,
                timeout=5,
            )
            return r.status_code in (200, 201)
        except Exception:
            return False

    def get_existing_folder_ids(self) -> List[str]:
        """Get list of existing shared folder IDs."""
        config = self.get_config()
        return [f["id"] for f in config.get("folders", [])]

    def add_folder(
        self,
        folder_id: str,
        label: str,
        path: str,
        device_ids: List[str],
    ) -> bool:
        """Add a shared folder to Syncthing."""
        try:
            devices = [{"deviceID": did} for did in device_ids]
            folder = {
                "id": folder_id,
                "label": label,
                "path": path,
                "devices": devices,
                "type": "sendreceive",
                "versioning": {
                    "type": "simple",
                    "params": {"keep": "5"},
                },
            }
            r = requests.post(
                f"{self.api_url}/rest/config/folders",
                headers=self._headers(),
                json=folder,
                timeout=5,
            )
            return r.status_code in (200, 201)
        except Exception:
            return False

    def remove_folder(self, folder_id: str) -> bool:
        """Remove a shared folder."""
        try:
            r = requests.delete(
                f"{self.api_url}/rest/config/folders/{folder_id}",
                headers=self._headers(),
                timeout=5,
            )
            return r.status_code in (200, 204)
        except Exception:
            return False

    def get_folder_status(self, folder_id: str) -> Dict[str, Any]:
        """Get sync status for a folder."""
        try:
            r = requests.get(
                f"{self.api_url}/rest/db/status",
                headers=self._headers(),
                params={"folder": folder_id},
                timeout=5,
            )
            r.raise_for_status()
            return r.json()
        except Exception:
            return {}

    def get_connections(self) -> Dict[str, Any]:
        """Get connected devices info."""
        try:
            r = requests.get(
                f"{self.api_url}/rest/system/connections",
                headers=self._headers(),
                timeout=5,
            )
            r.raise_for_status()
            return r.json().get("connections", {})
        except Exception:
            return {}

    @staticmethod
    def detect_api_key() -> str:
        """Try to read API key from Syncthing's config.xml."""
        config_paths = [
            os.path.expanduser("~/.config/syncthing/config.xml"),
            os.path.expanduser("~/.local/state/syncthing/config.xml"),
            "/userdata/system/.config/syncthing/config.xml",
        ]
        # Android
        if BUILD_TARGET == "android":
            config_paths.append(
                "/storage/emulated/0/Android/data/com.github.catfriend1.syncthingandroid/files/config.xml"
            )
        for path in config_paths:
            try:
                if os.path.exists(path):
                    tree = ET.parse(path)
                    root = tree.getroot()
                    gui = root.find(".//gui")
                    if gui is not None:
                        api_key_elem = gui.find("apikey")
                        if api_key_elem is not None and api_key_elem.text:
                            return api_key_elem.text
            except Exception:
                continue
        return ""

    @staticmethod
    def get_save_path(system: str) -> str:
        """Get the default save path for a system on the current platform."""
        if DEV_MODE:
            return os.path.join(os.path.expanduser("~"), "game-saves", system)
        elif BUILD_TARGET == "android":
            return ""  # User must configure on Android
        elif os.path.exists("/userdata"):
            return f"/userdata/saves/{system}"
        else:
            # Desktop/host
            return os.path.join(os.path.expanduser("~"), "game-saves", system)

    @staticmethod
    def get_folder_id(system: str) -> str:
        """Get the Syncthing folder ID for a system."""
        return f"saves-{system}"

    def configure_all_systems(
        self,
        role: str,
        device_ids: List[str],
        base_path: str = "",
        folder_overrides: Optional[Dict[str, str]] = None,
    ) -> Tuple[int, int, List[str]]:
        """
        Configure shared folders for all systems.

        Args:
            role: "host" or "console"
            device_ids: List of remote device IDs to share with
            base_path: Base path for host saves (ignored for console)
            folder_overrides: Per-system path overrides (for Android)

        Returns:
            Tuple of (success_count, skip_count, error_systems)
        """
        existing = set(self.get_existing_folder_ids())
        overrides = folder_overrides or {}
        success = 0
        skipped = 0
        errors = []

        for system in SYNC_SYSTEMS:
            folder_id = self.get_folder_id(system)

            # Skip if already configured
            if folder_id in existing:
                skipped += 1
                continue

            # Determine path
            if role == "host":
                path = os.path.join(
                    base_path or os.path.join(os.path.expanduser("~"), "game-saves"),
                    system,
                )
            elif system in overrides:
                path = overrides[system]
            else:
                path = self.get_save_path(system)

            # Skip if no path (Android without override)
            if not path:
                skipped += 1
                continue

            # Create directory
            os.makedirs(path, exist_ok=True)

            if self.add_folder(folder_id, f"{system} saves", path, device_ids):
                success += 1
            else:
                errors.append(system)

        return success, skipped, errors

    def get_system_sync_status(self) -> Dict[str, str]:
        """
        Get sync status for all configured systems.

        Returns:
            Dict mapping system name to status string
        """
        existing = set(self.get_existing_folder_ids())
        statuses = {}
        for system in SYNC_SYSTEMS:
            folder_id = self.get_folder_id(system)
            if folder_id not in existing:
                statuses[system] = "not_configured"
            else:
                status = self.get_folder_status(folder_id)
                state = status.get("state", "unknown")
                statuses[system] = state  # "idle", "syncing", "error", etc.
        return statuses
```

**Step 2: Commit**

```bash
git add src/services/syncthing_service.py
git commit -m "feat(syncthing): add SyncthingService REST API client"
```

---

### Task 5: Add SyncthingState to AppState

**Files:**
- Modify: `src/state.py`

**Step 1: Add SyncthingState dataclass**

Add before the `AppState` class:

```python
@dataclass
class SyncthingState:
    """State for Syncthing save sync screen."""

    step: str = "checking"  # "checking", "not_found", "role_select", "device_id_input", "configured"
    device_id: str = ""  # This device's ID
    host_device_id_input: str = ""  # Input for host device ID (console mode)
    cursor_position: int = 0
    shift_active: bool = False
    status_message: str = ""
    error_message: str = ""
    system_statuses: Dict[str, str] = field(default_factory=dict)  # system -> sync status
    highlighted: int = 0
    configuring: bool = False  # True during async configure
    configure_result: str = ""  # "success", "partial", "error"
```

**Step 2: Add to AppState.__init__**

In `AppState.__init__`, add after the steam_shortcut line:

```python
# ---- Syncthing Save Sync ---- #
self.syncthing = SyncthingState()
```

**Step 3: Add to close_all_modals if needed**

No modal to close — syncthing is a full screen mode, not a modal.

**Step 4: Commit**

```bash
git add src/state.py
git commit -m "feat(syncthing): add SyncthingState to AppState"
```

---

### Task 6: Create SyncthingScreen

**Files:**
- Create: `src/ui/screens/syncthing_screen.py`

**Step 1: Write the screen**

```python
"""
Syncthing Sync screen - Configure save sync between devices.
"""

import pygame
from typing import List, Dict, Any, Tuple, Optional, Set

from ui.theme import Theme, default_theme
from ui.templates.list_screen import ListScreenTemplate
from constants import BUILD_TARGET
from services.syncthing_service import SYNC_SYSTEMS


class SyncthingScreen:
    """
    Syncthing sync configuration screen.

    Shows different views based on setup step:
    - Checking: "Checking Syncthing..."
    - Not found: "Syncthing not running" message
    - Role select: Host vs Console choice
    - Device ID input: Enter host device ID (console mode)
    - Configured: System list with sync status
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.template = ListScreenTemplate(theme)

    def render_checking(
        self, screen: pygame.Surface
    ) -> Tuple[Optional[pygame.Rect], List[pygame.Rect], int]:
        """Render checking state."""
        return self.template.render(
            screen,
            title="Syncthing Sync",
            items=["Checking Syncthing connection..."],
            highlighted=0,
            selected=set(),
            show_back=True,
            item_height=40,
        )

    def render_not_found(
        self, screen: pygame.Surface, highlighted: int
    ) -> Tuple[Optional[pygame.Rect], List[pygame.Rect], int]:
        """Render not found state."""
        items = [
            "--- STATUS ---",
            "Syncthing is not running",
            "",
            "--- INSTRUCTIONS ---",
            "Install Syncthing on this device",
            "and make sure it is running.",
            "",
            "Retry Connection",
        ]
        divider_indices = {0, 3}
        return self.template.render(
            screen,
            title="Syncthing Sync",
            items=items,
            highlighted=highlighted,
            selected=set(),
            show_back=True,
            item_height=40,
            item_spacing=8,
            divider_indices=divider_indices,
        )

    def render_role_select(
        self, screen: pygame.Surface, highlighted: int
    ) -> Tuple[Optional[pygame.Rect], List[pygame.Rect], int]:
        """Render role selection."""
        items = [
            "--- SELECT ROLE ---",
            "Host (Computer)",
            "Console (Knulli/Android)",
        ]
        divider_indices = {0}
        return self.template.render(
            screen,
            title="Syncthing Sync",
            items=items,
            highlighted=highlighted,
            selected=set(),
            show_back=True,
            item_height=40,
            item_spacing=8,
            divider_indices=divider_indices,
        )

    def render_configured(
        self,
        screen: pygame.Surface,
        highlighted: int,
        settings: Dict[str, Any],
        device_id: str,
        system_statuses: Dict[str, str],
        status_message: str = "",
    ) -> Tuple[Optional[pygame.Rect], List[pygame.Rect], int]:
        """Render configured state with system list."""
        role = settings.get("syncthing_role", "")
        items = []
        divider_indices = set()

        # Status header
        divider_indices.add(len(items))
        items.append("--- STATUS ---")
        role_label = "Host" if role == "host" else "Console"
        items.append(("Role", role_label))

        if role == "host":
            # Show device ID for copying
            short_id = device_id[:20] + "..." if len(device_id) > 20 else device_id
            items.append(("Device ID", short_id))
        else:
            host_id = settings.get("syncthing_host_device_id", "")
            short_id = host_id[:20] + "..." if len(host_id) > 20 else host_id
            items.append(("Host", short_id or "Not set"))

        if status_message:
            items.append(("Status", status_message))

        # Actions
        divider_indices.add(len(items))
        items.append("--- ACTIONS ---")
        items.append("Sync All Systems")

        if role == "host":
            items.append("Change Base Path")

        # System list
        divider_indices.add(len(items))
        items.append("--- SYSTEMS ---")
        for system in SYNC_SYSTEMS:
            status = system_statuses.get(system, "not_configured")
            status_labels = {
                "not_configured": "-",
                "idle": "Synced",
                "syncing": "Syncing...",
                "scanning": "Scanning...",
                "error": "Error",
                "unknown": "?",
            }
            label = status_labels.get(status, status)
            items.append((system.upper(), label))

        # Reset
        divider_indices.add(len(items))
        items.append("--- SETTINGS ---")
        items.append("Reconfigure")

        return self.template.render(
            screen,
            title="Syncthing Sync",
            items=items,
            highlighted=highlighted,
            selected=set(),
            show_back=True,
            item_height=40,
            get_label=lambda x: x[0] if isinstance(x, tuple) else x,
            get_secondary=lambda x: x[1] if isinstance(x, tuple) else None,
            item_spacing=8,
            divider_indices=divider_indices,
        )

    def get_not_found_action(self, index: int) -> str:
        """Get action for not found screen."""
        # "Retry Connection" is at index 7
        if index == 7:
            return "retry"
        return "none"

    def get_role_select_action(self, index: int) -> str:
        """Get action for role select screen."""
        if index == 1:
            return "select_host"
        elif index == 2:
            return "select_console"
        return "none"

    def get_configured_action(
        self,
        index: int,
        settings: Dict[str, Any],
        system_statuses: Dict[str, str],
    ) -> str:
        """Get action for configured screen."""
        role = settings.get("syncthing_role", "")

        # Build same item structure to find action by index
        current = 0

        # --- STATUS --- (divider)
        current += 1
        # Role
        current += 1
        # Device ID or Host
        current += 1
        # Status message (optional — check if present)
        # We skip status_message here since we can't know. Actions don't apply to status items anyway.

        # --- ACTIONS --- (divider)
        # We need to count carefully. Let's use a simpler approach:
        # Build a flat action list matching the items
        actions = []
        actions.append("divider")  # --- STATUS ---
        actions.append("none")  # Role
        actions.append("copy_device_id" if role == "host" else "none")  # Device ID / Host
        actions.append("divider")  # --- ACTIONS ---
        actions.append("sync_all")  # Sync All Systems

        if role == "host":
            actions.append("change_base_path")  # Change Base Path

        actions.append("divider")  # --- SYSTEMS ---
        for system in SYNC_SYSTEMS:
            status = system_statuses.get(system, "not_configured")
            if BUILD_TARGET == "android" and status == "not_configured":
                actions.append(f"configure_{system}")
            else:
                actions.append(f"system_{system}")

        actions.append("divider")  # --- SETTINGS ---
        actions.append("reconfigure")  # Reconfigure

        if index < len(actions):
            return actions[index]
        return "none"

    def get_configured_item_count(
        self,
        settings: Dict[str, Any],
    ) -> int:
        """Get total item count for configured screen."""
        role = settings.get("syncthing_role", "")
        # STATUS: divider + role + device_id = 3
        # ACTIONS: divider + sync_all + (change_base_path if host) = 2 or 3
        # SYSTEMS: divider + len(SYNC_SYSTEMS)
        # SETTINGS: divider + reconfigure = 2
        count = 3 + 2 + 1 + len(SYNC_SYSTEMS) + 2
        if role == "host":
            count += 1
        return count


# Default instance
syncthing_screen = SyncthingScreen()
```

**Step 2: Commit**

```bash
git add src/ui/screens/syncthing_screen.py
git commit -m "feat(syncthing): add SyncthingScreen UI"
```

---

### Task 7: Register screen in ScreenManager

**Files:**
- Modify: `src/ui/screens/screen_manager.py`

**Step 1: Add import**

Add to the imports at the top:

```python
from .syncthing_screen import SyncthingScreen
```

**Step 2: Add screen instance**

In `ScreenManager.__init__`, add:

```python
self.syncthing_screen = SyncthingScreen(theme)
```

**Step 3: Add render case**

In the `render` method, find where modes are checked and add a case for `"syncthing"`. Follow the same pattern as other modes — check `state.mode == "syncthing"` and delegate to the appropriate render method based on `state.syncthing.step`.

Find the section that handles screen rendering by mode and add:

```python
elif state.mode == "syncthing":
    if state.syncthing.step == "checking":
        back_rect, item_rects, scroll = self.syncthing_screen.render_checking(screen)
    elif state.syncthing.step == "not_found":
        back_rect, item_rects, scroll = self.syncthing_screen.render_not_found(
            screen, state.syncthing.highlighted
        )
    elif state.syncthing.step == "role_select":
        back_rect, item_rects, scroll = self.syncthing_screen.render_role_select(
            screen, state.syncthing.highlighted
        )
    elif state.syncthing.step == "device_id_input":
        # Will be handled by char_keyboard modal overlay
        back_rect, item_rects, scroll = self.syncthing_screen.render_checking(screen)
    elif state.syncthing.step == "configured":
        back_rect, item_rects, scroll = self.syncthing_screen.render_configured(
            screen,
            state.syncthing.highlighted,
            settings,
            state.syncthing.device_id,
            state.syncthing.system_statuses,
            state.syncthing.status_message,
        )
```

**Step 4: Commit**

```bash
git add src/ui/screens/screen_manager.py
git commit -m "feat(syncthing): register SyncthingScreen in ScreenManager"
```

---

### Task 8: Wire up app.py — settings toggle + menu entry + screen logic

**Files:**
- Modify: `src/app.py`

**Step 1: Add SyncthingService import**

Add to imports at the top:

```python
from services.syncthing_service import SyncthingService
```

**Step 2: Initialize service in __init__**

In `ConsoleUtilitiesApp.__init__`, add:

```python
self.syncthing_service = None  # Initialized lazily when needed
```

**Step 3: Handle settings toggle**

In the settings action handler (where `toggle_portmaster_enabled`, `toggle_scraper_enabled` etc. are handled), add:

```python
elif action == "toggle_syncthing_enabled":
    self.settings["syncthing_enabled"] = not self.settings.get(
        "syncthing_enabled", False
    )
    save_settings(self.settings)
```

**Step 4: Handle main menu action**

In the root menu action handler (where `action == "systems_list"`, `action == "settings"` etc. are), add:

```python
elif action == "syncthing":
    self._enter_syncthing()
```

**Step 5: Add _enter_syncthing method**

```python
def _enter_syncthing(self):
    """Enter the Syncthing sync screen."""
    import threading

    self.state.mode = "syncthing"
    self.state.syncthing.step = "checking"
    self.state.syncthing.highlighted = 1  # Skip first divider
    self.state.syncthing.error_message = ""
    self.state.syncthing.status_message = ""

    def check_syncthing():
        # Try to detect API key
        api_key = self.settings.get("syncthing_api_key", "")
        if not api_key:
            api_key = SyncthingService.detect_api_key()
            if api_key:
                self.settings["syncthing_api_key"] = api_key
                save_settings(self.settings)

        self.syncthing_service = SyncthingService(api_key=api_key)

        if self.syncthing_service.is_running():
            device_id = self.syncthing_service.get_device_id()
            self.state.syncthing.device_id = device_id

            role = self.settings.get("syncthing_role", "")
            if role:
                # Already configured — go to status view
                self.state.syncthing.step = "configured"
                self.state.syncthing.system_statuses = (
                    self.syncthing_service.get_system_sync_status()
                )
            else:
                self.state.syncthing.step = "role_select"
        else:
            self.state.syncthing.step = "not_found"

    threading.Thread(target=check_syncthing, daemon=True).start()
```

**Step 6: Add _handle_syncthing_select method**

```python
def _handle_syncthing_select(self):
    """Handle selection on the syncthing screen."""
    import threading

    step = self.state.syncthing.step

    if step == "not_found":
        action = self.screen_manager.syncthing_screen.get_not_found_action(
            self.state.syncthing.highlighted
        )
        if action == "retry":
            self._enter_syncthing()

    elif step == "role_select":
        action = self.screen_manager.syncthing_screen.get_role_select_action(
            self.state.syncthing.highlighted
        )
        if action == "select_host":
            self.settings["syncthing_role"] = "host"
            save_settings(self.settings)
            self.state.syncthing.step = "configured"
            self.state.syncthing.highlighted = 1
            self.state.syncthing.system_statuses = (
                self.syncthing_service.get_system_sync_status()
            )
        elif action == "select_console":
            self.settings["syncthing_role"] = "console"
            save_settings(self.settings)
            # Need host device ID — open URL input modal for text entry
            self.state.url_input.show = True
            self.state.url_input.input_text = self.settings.get(
                "syncthing_host_device_id", ""
            )
            self.state.url_input.cursor_position = len(
                self.state.url_input.input_text
            )
            self.state.url_input.context = "syncthing_device_id"

    elif step == "configured":
        action = self.screen_manager.syncthing_screen.get_configured_action(
            self.state.syncthing.highlighted,
            self.settings,
            self.state.syncthing.system_statuses,
        )
        if action == "sync_all":
            self._syncthing_sync_all()
        elif action == "reconfigure":
            self.settings["syncthing_role"] = ""
            self.settings["syncthing_host_device_id"] = ""
            save_settings(self.settings)
            self._enter_syncthing()
        elif action == "change_base_path":
            self._open_folder_browser("syncthing_base_path")
        elif action and action.startswith("configure_"):
            system = action.replace("configure_", "")
            self.state.folder_browser.show = True
            self.state.folder_browser.selected_system_to_add = {"syncthing_system": system}
            self._open_folder_browser(f"syncthing_override_{system}")
```

**Step 7: Add _syncthing_sync_all method**

```python
def _syncthing_sync_all(self):
    """Configure all system save folders in Syncthing."""
    import threading

    if not self.syncthing_service:
        return

    self.state.syncthing.status_message = "Configuring..."
    self.state.syncthing.configuring = True

    role = self.settings.get("syncthing_role", "")
    host_device_id = self.settings.get("syncthing_host_device_id", "")

    # Determine which device IDs to share with
    if role == "host":
        # Host shares with all known console devices
        # For now, get connected devices
        connections = self.syncthing_service.get_connections()
        device_ids = list(connections.keys())
        if not device_ids:
            self.state.syncthing.status_message = "No devices connected"
            self.state.syncthing.configuring = False
            return
    else:
        # Console shares with host
        if not host_device_id:
            self.state.syncthing.status_message = "No host device ID set"
            self.state.syncthing.configuring = False
            return
        device_ids = [host_device_id]

    def do_sync():
        # Add host device if console
        if role == "console" and host_device_id:
            self.syncthing_service.add_device(host_device_id, "game-saves-host")

        success, skipped, errors = self.syncthing_service.configure_all_systems(
            role=role,
            device_ids=device_ids,
            base_path=self.settings.get("syncthing_base_path", ""),
            folder_overrides=self.settings.get("syncthing_folder_overrides", {}),
        )

        # Update status
        self.state.syncthing.system_statuses = (
            self.syncthing_service.get_system_sync_status()
        )
        self.state.syncthing.configuring = False

        if errors:
            self.state.syncthing.status_message = (
                f"Done: {success} added, {len(errors)} failed"
            )
        elif success == 0 and skipped > 0:
            self.state.syncthing.status_message = "All systems already configured"
        else:
            self.state.syncthing.status_message = f"Configured {success} systems"

    threading.Thread(target=do_sync, daemon=True).start()
```

**Step 8: Wire up navigation and back**

In the navigation handler where modes are checked, add syncthing mode handling for up/down navigation (follows the same pattern as settings/utils):

Find where `self.state.mode == "settings"` navigation is handled and add nearby:

```python
elif self.state.mode == "syncthing":
    step = self.state.syncthing.step
    if step == "not_found":
        max_items = 8
    elif step == "role_select":
        max_items = 3
    elif step == "configured":
        max_items = self.screen_manager.syncthing_screen.get_configured_item_count(
            self.settings
        )
    else:
        max_items = 1

    if direction == "up":
        self.state.syncthing.highlighted = (
            self.state.syncthing.highlighted - 1
        ) % max_items
    elif direction == "down":
        self.state.syncthing.highlighted = (
            self.state.syncthing.highlighted + 1
        ) % max_items
```

In the select/confirm handler, add:

```python
elif self.state.mode == "syncthing":
    self._handle_syncthing_select()
```

In the back/cancel handler, add:

```python
elif self.state.mode == "syncthing":
    self.state.mode = "systems"
    self.state.highlighted = 0
```

**Step 9: Handle URL input callback for device ID**

In the URL input confirmation handler (where `self.state.url_input.context` is checked), add:

```python
elif self.state.url_input.context == "syncthing_device_id":
    device_id = self.state.url_input.input_text.strip()
    self.settings["syncthing_host_device_id"] = device_id
    save_settings(self.settings)
    self.state.url_input.show = False
    # Add host device
    if self.syncthing_service and device_id:
        self.syncthing_service.add_device(device_id, "game-saves-host")
    self.state.syncthing.step = "configured"
    self.state.syncthing.highlighted = 1
    if self.syncthing_service:
        self.state.syncthing.system_statuses = (
            self.syncthing_service.get_system_sync_status()
        )
```

**Step 10: Handle folder browser callback for syncthing paths**

In the folder browser confirmation handler, add handling for syncthing base path and per-system overrides:

```python
# Check for syncthing folder overrides
if context and context.startswith("syncthing_override_"):
    system = context.replace("syncthing_override_", "")
    overrides = self.settings.get("syncthing_folder_overrides", {})
    overrides[system] = selected_path
    self.settings["syncthing_folder_overrides"] = overrides
    save_settings(self.settings)
elif context == "syncthing_base_path":
    self.settings["syncthing_base_path"] = selected_path
    save_settings(self.settings)
```

**Step 11: Commit**

```bash
git add src/app.py
git commit -m "feat(syncthing): wire up syncthing screen, settings, and menu in app.py"
```

---

### Task 9: Add enter_mode support for syncthing

**Files:**
- Modify: `src/state.py`

**Step 1: Add syncthing to enter_mode**

In `AppState.enter_mode`, add:

```python
elif new_mode == "syncthing":
    self.syncthing.highlighted = 0
```

**Step 2: Commit**

```bash
git add src/state.py
git commit -m "feat(syncthing): add syncthing to enter_mode"
```

---

### Task 10: Manual integration test

**Step 1: Run the app in dev mode**

```bash
cd /Users/gabe/Workspace/Games/console_utilities
DEV_MODE=true make run
```

**Step 2: Verify**

1. Open Settings -> scroll to "SAVE SYNC" section -> toggle "Enable Syncthing Helper" ON
2. Go back to main menu -> "Syncthing Sync" should appear
3. Click it -> should show "Checking..." then either "not found" (if Syncthing isn't running) or role selection
4. If Syncthing is running: select role, enter device ID (console mode), sync all systems

**Step 3: Commit any fixes**

```bash
git add -A
git commit -m "fix(syncthing): integration test fixes"
```
