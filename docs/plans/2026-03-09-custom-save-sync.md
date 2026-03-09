# Custom Save Sync Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Allow users to sync arbitrary save folders or specific files (for ports, standalone games) between devices via Syncthing, with metadata-driven discovery and per-device path mapping.

**Architecture:** Extends the existing Syncthing save sync feature. Source device picks a folder or files, app creates a Syncthing shared folder with `sync_info.json` metadata and optional `.stignore`. Receiving devices discover custom saves via synced metadata and map them to local paths. The host computer relays as a hub.

**Tech Stack:** Python 3, PyGame, Syncthing REST API, JSON metadata

**Design Doc:** `docs/plans/2026-03-09-custom-save-sync-design.md`

---

### Task 1: Add Custom Save State and Settings

**Files:**
- Modify: `src/state.py` — add `CustomSaveState` dataclass and fields to `SyncthingState`
- Modify: `src/config/settings.py` — add `syncthing_custom_saves` setting

**Step 1: Add CustomSaveState to state.py**

Add this dataclass after `SyncthingState` (around line 838):

```python
@dataclass
class CustomSaveEntry:
    """A single custom save sync entry."""
    name: str = ""
    folder_id: str = ""
    local_path: str = ""
    mapped: bool = False
    sync_mode: str = "folder"  # "folder" or "files"
    sync_files: List[str] = field(default_factory=list)
    source_device: str = ""
```

Add these fields to `SyncthingState` (after `configure_result`):

```python
    # Custom saves
    custom_saves: List[Dict[str, Any]] = field(default_factory=list)  # loaded from sync_info.json
    custom_highlighted: int = 0
    custom_step: str = ""  # "", "name_input", "folder_browse", "file_select"
    custom_name_input: str = ""
    custom_name_cursor: int = 0
    custom_name_shift: bool = False
    custom_source_path: str = ""
    custom_selected_files: Set[str] = field(default_factory=set)  # filenames selected in file mode
    custom_file_list: List[str] = field(default_factory=list)  # files in source folder
    custom_file_highlighted: int = 0
```

**Step 2: Add settings field**

In `src/config/settings.py`, add after `syncthing_folder_overrides` (line 70):

```python
    syncthing_custom_saves: List[Dict[str, str]] = field(default_factory=list)
    # Each: {"name": "...", "folder_id": "...", "local_path": "...", "mapped": true/false}
```

**Step 3: Verify no syntax errors**

Run: `cd /Users/gabe/Workspace/Games/console_utilities && python -c "from state import AppState; from config.settings import Settings; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add src/state.py src/config/settings.py
git commit -m "feat(custom-sync): add state and settings for custom save sync"
```

---

### Task 2: Service Layer — Custom Save Helpers

**Files:**
- Modify: `src/services/syncthing_service.py`

**Step 1: Add helper methods to SyncthingService**

Add these methods at the end of the `SyncthingService` class (after `get_system_sync_status`, line 303):

```python
    @staticmethod
    def sanitize_folder_id(name: str) -> str:
        """Convert a custom save name to a Syncthing folder ID.

        Example: 'Balatro Save' -> 'custom-balatro-save'
        """
        import re
        sanitized = name.lower().strip()
        sanitized = re.sub(r'[^a-z0-9\s-]', '', sanitized)
        sanitized = re.sub(r'\s+', '-', sanitized)
        sanitized = re.sub(r'-+', '-', sanitized).strip('-')
        return f"custom-{sanitized}"

    @staticmethod
    def write_sync_info(
        folder_path: str,
        name: str,
        source_device: str,
        source_path: str,
        sync_mode: str = "folder",
        sync_files: Optional[List[str]] = None,
    ) -> bool:
        """Write sync_info.json to a folder."""
        import json
        from datetime import datetime
        info = {
            "name": name,
            "source_device": source_device,
            "source_path": source_path,
            "sync_mode": sync_mode,
            "created": datetime.now().isoformat(),
        }
        if sync_mode == "files" and sync_files:
            info["sync_files"] = sync_files
        try:
            os.makedirs(folder_path, exist_ok=True)
            with open(os.path.join(folder_path, "sync_info.json"), "w") as f:
                json.dump(info, f, indent=2)
            return True
        except Exception as e:
            log_error("Syncthing: write_sync_info failed", type(e).__name__, traceback.format_exc())
            return False

    @staticmethod
    def write_stignore(folder_path: str, allowed_files: List[str]) -> bool:
        """Write .stignore that whitelists only specific files."""
        try:
            lines = ["!sync_info.json"]
            for f in allowed_files:
                lines.append(f"!{f}")
            lines.append("*")
            with open(os.path.join(folder_path, ".stignore"), "w") as fh:
                fh.write("\n".join(lines) + "\n")
            return True
        except Exception as e:
            log_error("Syncthing: write_stignore failed", type(e).__name__, traceback.format_exc())
            return False

    @staticmethod
    def read_sync_info(folder_path: str) -> Optional[Dict[str, Any]]:
        """Read sync_info.json from a folder. Returns None if not found."""
        import json
        info_path = os.path.join(folder_path, "sync_info.json")
        try:
            if os.path.exists(info_path):
                with open(info_path, "r") as f:
                    return json.load(f)
        except Exception:
            pass
        return None

    def add_custom_save(
        self,
        name: str,
        source_path: str,
        source_device: str,
        device_ids: List[str],
        sync_mode: str = "folder",
        sync_files: Optional[List[str]] = None,
    ) -> Optional[str]:
        """
        Create a custom save sync folder in Syncthing.

        Returns folder_id on success, None on failure.
        """
        folder_id = self.sanitize_folder_id(name)

        # Write metadata
        self.write_sync_info(source_path, name, source_device, source_path, sync_mode, sync_files)

        # Write .stignore for file mode
        if sync_mode == "files" and sync_files:
            self.write_stignore(source_path, sync_files)

        # Add to Syncthing
        if self.add_folder(folder_id, name, source_path, device_ids):
            return folder_id
        return None

    def get_custom_save_statuses(self, custom_saves: List[Dict[str, str]]) -> Dict[str, str]:
        """Get sync status for custom save folders."""
        existing = set(self.get_existing_folder_ids())
        statuses = {}
        for save in custom_saves:
            fid = save.get("folder_id", "")
            if fid not in existing:
                statuses[fid] = "not_configured"
            else:
                status = self.get_folder_status(fid)
                statuses[fid] = status.get("state", "unknown")
        return statuses

    def discover_custom_saves(self, base_path: str) -> List[Dict[str, Any]]:
        """Scan custom save staging dirs for sync_info.json metadata."""
        custom_dir = os.path.join(base_path, "custom")
        saves = []
        if not os.path.isdir(custom_dir):
            return saves
        for entry in os.listdir(custom_dir):
            entry_path = os.path.join(custom_dir, entry)
            if os.path.isdir(entry_path):
                info = self.read_sync_info(entry_path)
                if info:
                    info["folder_id"] = entry
                    info["staging_path"] = entry_path
                    saves.append(info)
        return saves
```

**Step 2: Verify no syntax errors**

Run: `cd /Users/gabe/Workspace/Games/console_utilities && python -c "from services.syncthing_service import SyncthingService; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add src/services/syncthing_service.py
git commit -m "feat(custom-sync): add service helpers for custom save sync"
```

---

### Task 3: UI — Add Custom Saves Section to Syncthing Screen

**Files:**
- Modify: `src/ui/screens/syncthing_screen.py`

**Step 1: Extend `_build_configured_items` to include CUSTOM SAVES section**

In `syncthing_screen.py`, modify `_build_configured_items` to accept a `custom_saves` parameter and add the section. Replace the method (lines 93-165):

```python
    def _build_configured_items(
        self,
        settings: Dict[str, Any],
        device_id: str,
        system_statuses: Dict[str, str],
        status_message: str = "",
        custom_saves: List[Dict[str, Any]] = None,
        custom_statuses: Dict[str, str] = None,
    ) -> Tuple[List[Any], List[str], Set[int]]:
        """
        Build items, actions, and divider indices for the configured screen.
        Single source of truth used by render, action lookup, and item count.
        """
        role = settings.get("syncthing_role", "")
        items = []
        actions = []
        divider_indices = set()

        def _add_divider(label: str):
            divider_indices.add(len(items))
            items.append(label)
            actions.append("divider")

        def _add_item(display, action: str):
            items.append(display)
            actions.append(action)

        # Status header
        _add_divider("--- STATUS ---")
        role_label = "Host" if role == "host" else "Console"
        _add_item(("Role", role_label), "none")

        if role == "host":
            _add_item(("Device ID", device_id), "none")
        else:
            host_id = settings.get("syncthing_host_device_id", "")
            _add_item(("Host", host_id or "Not set"), "none")

        if status_message:
            _add_item(("Status", status_message), "none")

        # Actions
        _add_divider("--- ACTIONS ---")
        _add_item("Sync All Systems", "sync_all")

        if role == "host":
            _add_item("Change Base Path", "change_base_path")

        # System list
        _add_divider("--- SYSTEMS ---")
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
            if BUILD_TARGET == "android":
                _add_item((system.upper(), label), f"configure_{system}")
            else:
                _add_item((system.upper(), label), f"system_{system}")

        # Custom saves
        _add_divider("--- CUSTOM SAVES ---")
        _add_item("Add Custom Save", "add_custom_save")

        if custom_saves:
            cs = custom_statuses or {}
            for save in custom_saves:
                name = save.get("name", "Unknown")
                fid = save.get("folder_id", "")
                mapped = save.get("mapped", False)
                mode = save.get("sync_mode", "folder")
                files = save.get("sync_files", [])

                # Build status label
                status = cs.get(fid, "not_configured")
                if not mapped:
                    label = "Not mapped"
                elif status == "idle":
                    label = "Synced"
                elif status == "syncing":
                    label = "Syncing..."
                else:
                    label = status.capitalize() if status else "-"

                # Add file count for file mode
                suffix = f" ({len(files)} files)" if mode == "files" and files else ""
                _add_item((f"{name}{suffix}", label), f"custom_{fid}")

        # Reset
        _add_divider("--- SETTINGS ---")
        _add_item("Reconfigure", "reconfigure")

        return items, actions, divider_indices
```

**Step 2: Update render_configured to pass custom saves**

Update `render_configured` signature and call (lines 167-193):

```python
    def render_configured(
        self,
        screen: pygame.Surface,
        highlighted: int,
        settings: Dict[str, Any],
        device_id: str,
        system_statuses: Dict[str, str],
        status_message: str = "",
        custom_saves: List[Dict[str, Any]] = None,
        custom_statuses: Dict[str, str] = None,
    ) -> Tuple[Optional[pygame.Rect], List[pygame.Rect], int]:
        """Render configured state with system list."""
        items, _, divider_indices = self._build_configured_items(
            settings, device_id, system_statuses, status_message,
            custom_saves=custom_saves, custom_statuses=custom_statuses,
        )

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
```

**Step 3: Update get_configured_action and get_configured_item_count to accept custom saves**

```python
    def get_configured_action(
        self,
        index: int,
        settings: Dict[str, Any],
        system_statuses: Dict[str, str],
        status_message: str = "",
        custom_saves: List[Dict[str, Any]] = None,
        custom_statuses: Dict[str, str] = None,
    ) -> str:
        """Get action for configured screen."""
        _, actions, _ = self._build_configured_items(
            settings, "", system_statuses, status_message,
            custom_saves=custom_saves, custom_statuses=custom_statuses,
        )
        if index < len(actions):
            return actions[index]
        return "none"

    def get_configured_item_count(
        self,
        settings: Dict[str, Any],
        status_message: str = "",
        custom_saves: List[Dict[str, Any]] = None,
    ) -> int:
        """Get total item count for configured screen."""
        items, _, _ = self._build_configured_items(
            settings, "", {}, status_message, custom_saves=custom_saves,
        )
        return len(items)
```

**Step 4: Verify**

Run: `cd /Users/gabe/Workspace/Games/console_utilities && python -c "from ui.screens.syncthing_screen import SyncthingScreen; print('OK')"`
Expected: `OK`

**Step 5: Commit**

```bash
git add src/ui/screens/syncthing_screen.py
git commit -m "feat(custom-sync): add CUSTOM SAVES section to syncthing screen"
```

---

### Task 4: Update Screen Manager and App Rendering

**Files:**
- Modify: `src/ui/screens/screen_manager.py` — pass custom saves to render
- Modify: `src/app.py` — pass custom saves through render + navigation + action handlers

**Step 1: Update screen_manager.py render call for syncthing configured**

Find the `render_configured` call in screen_manager.py (around line 1061) and update to pass custom saves:

```python
            elif state.syncthing.step == "configured":
                back_rect, item_rects, scroll_offset = self.syncthing_screen.render_configured(
                    screen,
                    state.syncthing.highlighted,
                    settings,
                    state.syncthing.device_id,
                    state.syncthing.system_statuses,
                    state.syncthing.status_message,
                    custom_saves=state.syncthing.custom_saves,
                    custom_statuses=state.syncthing.custom_statuses if hasattr(state.syncthing, 'custom_statuses') else None,
                )
```

**Step 2: Add `custom_statuses` field to SyncthingState**

In `src/state.py`, add to SyncthingState fields (after `custom_file_highlighted`):

```python
    custom_statuses: Dict[str, str] = field(default_factory=dict)
```

**Step 3: Update app.py navigation for syncthing configured**

In app.py, update the syncthing navigation section (around line 1508-1518) where `_build_configured_items` is called — add custom_saves params:

```python
            elif step == "configured":
                _, _, divider_indices = (
                    self.screen_manager.syncthing_screen._build_configured_items(
                        self.settings, "", self.state.syncthing.system_statuses,
                        self.state.syncthing.status_message,
                        custom_saves=self.state.syncthing.custom_saves,
                        custom_statuses=self.state.syncthing.custom_statuses,
                    )
                )
                max_items = self.screen_manager.syncthing_screen.get_configured_item_count(
                    self.settings,
                    status_message=self.state.syncthing.status_message,
                    custom_saves=self.state.syncthing.custom_saves,
                )
```

**Step 4: Update app.py get_configured_action calls**

In `_handle_syncthing_select` (around line 6245), update the `get_configured_action` call:

```python
            action = self.screen_manager.syncthing_screen.get_configured_action(
                self.state.syncthing.highlighted,
                self.settings,
                self.state.syncthing.system_statuses,
                status_message=self.state.syncthing.status_message,
                custom_saves=self.state.syncthing.custom_saves,
                custom_statuses=self.state.syncthing.custom_statuses,
            )
```

**Step 5: Load custom saves on enter**

In `_enter_syncthing`, after setting `system_statuses` in the `check_syncthing` thread (around line 6197), add custom save discovery:

```python
                    # Load custom saves from settings
                    self.state.syncthing.custom_saves = self.settings.get(
                        "syncthing_custom_saves", []
                    )
                    # Discover any new custom saves from staging (host/receiving)
                    if role == "host":
                        base = self.settings.get("syncthing_base_path", "") or os.path.join(
                            os.path.expanduser("~"), "game-saves"
                        )
                        discovered = self.syncthing_service.discover_custom_saves(base)
                        # Merge discovered with saved
                        known_ids = {s["folder_id"] for s in self.state.syncthing.custom_saves}
                        for d in discovered:
                            if d.get("folder_id") not in known_ids:
                                self.state.syncthing.custom_saves.append({
                                    "name": d["name"],
                                    "folder_id": d["folder_id"],
                                    "local_path": d.get("staging_path", ""),
                                    "mapped": False,
                                    "sync_mode": d.get("sync_mode", "folder"),
                                    "sync_files": d.get("sync_files", []),
                                })
                    # Get custom save statuses
                    if self.state.syncthing.custom_saves:
                        self.state.syncthing.custom_statuses = (
                            self.syncthing_service.get_custom_save_statuses(
                                self.state.syncthing.custom_saves
                            )
                        )
```

Also add the `import os` at the top of the thread function if not already imported (it's already imported at file level).

**Step 6: Verify app starts**

Run: `cd /Users/gabe/Workspace/Games/console_utilities && python -c "from app import ConsoleUtilitiesApp; print('OK')" 2>/dev/null || echo "Check imports"`

**Step 7: Commit**

```bash
git add src/state.py src/ui/screens/screen_manager.py src/app.py
git commit -m "feat(custom-sync): wire custom saves through render pipeline"
```

---

### Task 5: Add Custom Save Action — Name Input

**Files:**
- Modify: `src/app.py`

**Step 1: Handle "add_custom_save" action**

In `_handle_syncthing_select`, add a handler for the `add_custom_save` action (after the existing `elif action == "change_base_path":` block, around line 6266):

```python
            elif action == "add_custom_save":
                # Open name input using the URL input modal (reused for text entry)
                self.state.url_input.show = True
                self.state.url_input.input_text = ""
                self.state.url_input.cursor_position = 0
                self.state.url_input.context = "custom_save_name"
```

**Step 2: Handle name input completion**

In the URL input callback section (around line 5533, where `syncthing_device_id` context is handled), add a handler for `custom_save_name`:

```python
            elif self.state.url_input.context == "custom_save_name":
                name = self.state.url_input.input_text.strip()
                self.state.url_input.show = False
                if name:
                    self.state.syncthing.custom_name_input = name
                    # Open folder browser to pick source folder
                    self._open_folder_browser("custom_save_source")
```

**Step 3: Add folder browser initial path for custom_save_source**

In `_open_folder_browser` (around line 4386), add:

```python
        elif selection_type == "custom_save_source":
            path = self.settings.get("roms_dir", SCRIPT_DIR)
```

**Step 4: Commit**

```bash
git add src/app.py
git commit -m "feat(custom-sync): add name input flow for custom saves"
```

---

### Task 6: Folder/File Selection for Custom Save Source

**Files:**
- Modify: `src/app.py`

This is the key interaction: when the user selects a folder in the browser for `custom_save_source`, they can either:
- **Select the folder** → `sync_mode: "folder"` (full folder sync)
- **Enter the folder and pick files** → not yet possible with current folder browser

Since the current folder browser selects folders (not files within them), we'll use the following approach:
- Selecting a folder from the browser = folder mode (sync entire folder)
- After folder selection, show a confirm modal asking "Sync entire folder?" with options "Entire Folder" / "Select Files"
- If "Select Files", re-open browser in file-select mode (we'll reuse the folder browser with a file list)

**Step 1: Handle custom_save_source folder selection**

In the `_complete_folder_browser_selection` method or the folder browser confirm handler (around line 5120 where `syncthing_base_path` is handled), add handling for `custom_save_source`:

```python
        elif selection_type == "custom_save_source":
            self.state.folder_browser.show = False
            self.state.syncthing.custom_source_path = current_path
            # Ask: entire folder or select files?
            self.state.confirm_modal.show = True
            self.state.confirm_modal.title = "Sync Mode"
            self.state.confirm_modal.message_lines = [
                f"Folder: {os.path.basename(current_path)}",
                "",
                "Sync the entire folder, or",
                "select specific files?",
            ]
            self.state.confirm_modal.ok_label = "Entire Folder"
            self.state.confirm_modal.cancel_label = "Select Files"
            self.state.confirm_modal.button_index = 0
            self.state.confirm_modal.context = "custom_save_mode"
```

Also add `"custom_save_source"` to the tuple check that routes to `_complete_folder_browser_selection` (around line 5120):

Find the line:
```python
        ) or selection_type.startswith("syncthing_override_"):
```
And add `or selection_type == "custom_save_source"` to it.

**Step 2: Handle confirm modal for sync mode**

In the confirm modal OK handler (around line 3482), add:

```python
        elif context == "custom_save_mode":
            # "Entire Folder" chosen — create the custom save immediately
            self._create_custom_save("folder")
```

In the confirm modal Cancel handler (wherever cancels are processed), add special handling for `custom_save_mode`:

```python
        # In the cancel handler, check if this is custom_save_mode
        if self.state.confirm_modal.context == "custom_save_mode":
            # "Select Files" chosen
            self.state.confirm_modal.show = False
            self._enter_custom_file_select()
            return
```

**Step 3: Add file select method**

Add to app.py in the Syncthing Handlers section:

```python
    def _enter_custom_file_select(self):
        """Enter file selection mode for custom save."""
        path = self.state.syncthing.custom_source_path
        try:
            files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
            files.sort()
        except Exception:
            files = []

        self.state.syncthing.custom_file_list = files
        self.state.syncthing.custom_selected_files = set()
        self.state.syncthing.custom_file_highlighted = 0
        self.state.syncthing.custom_step = "file_select"
```

**Step 4: Add _create_custom_save method**

```python
    def _create_custom_save(self, sync_mode: str):
        """Create a custom save sync in Syncthing."""
        import threading

        if not self.syncthing_service:
            return

        name = self.state.syncthing.custom_name_input
        source_path = self.state.syncthing.custom_source_path
        sync_files = list(self.state.syncthing.custom_selected_files) if sync_mode == "files" else None
        device_id = self.state.syncthing.device_id

        role = self.settings.get("syncthing_role", "")
        host_device_id = self.settings.get("syncthing_host_device_id", "")

        if role == "host":
            config = self.syncthing_service.get_config()
            my_id = self.syncthing_service.get_device_id()
            device_ids = [d["deviceID"] for d in config.get("devices", []) if d["deviceID"] != my_id]
        else:
            device_ids = [host_device_id] if host_device_id else []

        if not device_ids:
            self.state.syncthing.status_message = "No devices paired"
            return

        self.state.syncthing.status_message = "Creating custom save..."

        def do_create():
            folder_id = self.syncthing_service.add_custom_save(
                name=name,
                source_path=source_path,
                source_device=device_id,
                device_ids=device_ids,
                sync_mode=sync_mode,
                sync_files=sync_files,
            )
            if folder_id:
                # Save to settings
                saves = self.settings.get("syncthing_custom_saves", [])
                saves.append({
                    "name": name,
                    "folder_id": folder_id,
                    "local_path": source_path,
                    "mapped": True,  # Source device is always mapped
                    "sync_mode": sync_mode,
                    "sync_files": sync_files or [],
                })
                self.settings["syncthing_custom_saves"] = saves
                save_settings(self.settings)
                # Update state
                self.state.syncthing.custom_saves = saves
                self.state.syncthing.status_message = f"Created: {name}"
            else:
                self.state.syncthing.status_message = f"Failed to create: {name}"

            # Reset custom save flow
            self.state.syncthing.custom_step = ""
            self.state.syncthing.custom_name_input = ""
            self.state.syncthing.custom_source_path = ""
            self.state.syncthing.custom_selected_files = set()

        threading.Thread(target=do_create, daemon=True).start()
```

**Step 5: Commit**

```bash
git add src/app.py
git commit -m "feat(custom-sync): add folder/file selection and creation flow"
```

---

### Task 7: File Selection UI (Inline in Syncthing Screen)

**Files:**
- Modify: `src/ui/screens/syncthing_screen.py` — add file select render method
- Modify: `src/ui/screens/screen_manager.py` — render file select step
- Modify: `src/app.py` — handle file select navigation and confirmation

**Step 1: Add render_file_select to SyncthingScreen**

```python
    def render_file_select(
        self,
        screen: pygame.Surface,
        highlighted: int,
        folder_name: str,
        files: List[str],
        selected: Set[str],
    ) -> Tuple[Optional[pygame.Rect], List[pygame.Rect], int]:
        """Render file selection for custom save."""
        items = []
        divider_indices = set()
        selected_indices = set()

        # Header
        divider_indices.add(0)
        items.append(f"--- Select files in {folder_name} ---")

        for i, filename in enumerate(files):
            items.append(filename)
            if filename in selected:
                selected_indices.add(i + 1)  # +1 for header

        # Confirm button
        items.append(f"Confirm ({len(selected)} files)")

        return self.template.render(
            screen,
            title="Custom Save - Files",
            items=items,
            highlighted=highlighted,
            selected=selected_indices,
            show_back=True,
            item_height=40,
            item_spacing=8,
            divider_indices=divider_indices,
        )
```

**Step 2: Add render dispatch in screen_manager.py**

In the syncthing render section, add before the `elif state.syncthing.step == "configured"` check:

```python
            elif state.syncthing.custom_step == "file_select":
                folder_name = os.path.basename(state.syncthing.custom_source_path)
                back_rect, item_rects, scroll_offset = self.syncthing_screen.render_file_select(
                    screen,
                    state.syncthing.custom_file_highlighted,
                    folder_name,
                    state.syncthing.custom_file_list,
                    state.syncthing.custom_selected_files,
                )
```

Add `import os` at the top of screen_manager.py if not already present.

**Step 3: Handle file select navigation in app.py**

In the syncthing navigation handler (around line 1499), add a check for `custom_step == "file_select"` before the regular step checks:

```python
        elif self.state.mode == "syncthing":
            # Check custom save sub-steps first
            if self.state.syncthing.custom_step == "file_select":
                max_items = len(self.state.syncthing.custom_file_list) + 2  # header + files + confirm
                divider_indices = {0}
                if direction in ("up", "left"):
                    new_pos = (self.state.syncthing.custom_file_highlighted - 1) % max_items
                    while new_pos in divider_indices and max_items > len(divider_indices):
                        new_pos = (new_pos - 1) % max_items
                    self.state.syncthing.custom_file_highlighted = new_pos
                elif direction in ("down", "right"):
                    new_pos = (self.state.syncthing.custom_file_highlighted + 1) % max_items
                    while new_pos in divider_indices and max_items > len(divider_indices):
                        new_pos = (new_pos + 1) % max_items
                    self.state.syncthing.custom_file_highlighted = new_pos
                return  # Don't fall through to regular syncthing nav
```

**Step 4: Handle file select item selection**

In `_handle_syncthing_select`, add at the top before the step checks:

```python
        if self.state.syncthing.custom_step == "file_select":
            idx = self.state.syncthing.custom_file_highlighted
            if idx == 0:
                return  # Header divider
            elif idx <= len(self.state.syncthing.custom_file_list):
                # Toggle file selection
                filename = self.state.syncthing.custom_file_list[idx - 1]
                if filename in self.state.syncthing.custom_selected_files:
                    self.state.syncthing.custom_selected_files.discard(filename)
                else:
                    self.state.syncthing.custom_selected_files.add(filename)
            else:
                # Confirm button
                if self.state.syncthing.custom_selected_files:
                    self._create_custom_save("files")
            return
```

**Step 5: Handle back from file select**

In the back handler for syncthing mode (around line 2996), add:

```python
        elif self.state.mode == "syncthing":
            if self.state.syncthing.custom_step == "file_select":
                self.state.syncthing.custom_step = ""
                return
            self.state.mode = "systems"
            self.state.highlighted = 0
```

**Step 6: Handle touch/click for file select**

In the touch handler for syncthing (around line 2864), add a check:

```python
                elif self.state.mode == "syncthing":
                    if self.state.syncthing.custom_step == "file_select":
                        self.state.syncthing.custom_file_highlighted = actual_index
                    else:
                        self.state.syncthing.highlighted = actual_index
```

**Step 7: Commit**

```bash
git add src/ui/screens/syncthing_screen.py src/ui/screens/screen_manager.py src/app.py
git commit -m "feat(custom-sync): add file selection UI for custom saves"
```

---

### Task 8: Receiving Device — Map Custom Save to Local Path

**Files:**
- Modify: `src/app.py`

**Step 1: Handle custom save item selection (tap on existing custom save)**

In `_handle_syncthing_select`, in the configured step handler, add after the existing action handlers:

```python
            elif action and action.startswith("custom_"):
                folder_id = action.replace("custom_", "")
                # Find the save entry
                saves = self.settings.get("syncthing_custom_saves", [])
                save = next((s for s in saves if s.get("folder_id") == folder_id), None)
                if save:
                    if save.get("mapped"):
                        # Already mapped — show options (change path or remove)
                        self.state.confirm_modal.show = True
                        self.state.confirm_modal.title = save.get("name", "Custom Save")
                        self.state.confirm_modal.message_lines = [
                            f"Path: {save.get('local_path', 'N/A')}",
                            "",
                            "Change local path or remove?",
                        ]
                        self.state.confirm_modal.ok_label = "Change Path"
                        self.state.confirm_modal.cancel_label = "Remove"
                        self.state.confirm_modal.button_index = 0
                        self.state.confirm_modal.context = f"custom_save_manage_{folder_id}"
                        self.state.confirm_modal.data = save
                    else:
                        # Not mapped — open folder browser to pick local path
                        self.state.syncthing.custom_step = "mapping"
                        self._open_folder_browser(f"custom_save_map_{folder_id}")
```

**Step 2: Handle folder browser for mapping**

In `_open_folder_browser`, add:

```python
        elif selection_type.startswith("custom_save_map_"):
            path = self.settings.get("roms_dir", SCRIPT_DIR)
```

Add `custom_save_map_` to the route that goes to `_complete_folder_browser_selection` (same tuple/condition around line 5120).

**Step 3: Handle folder selection for mapping**

In `_complete_folder_browser_selection`, add:

```python
        elif selection_type.startswith("custom_save_map_"):
            folder_id = selection_type.replace("custom_save_map_", "")
            self.state.folder_browser.show = False
            self._map_custom_save(folder_id, current_path)
```

**Step 4: Add _map_custom_save method**

```python
    def _map_custom_save(self, folder_id: str, local_path: str):
        """Map a custom save to a local path on this device."""
        import threading
        import shutil

        if not self.syncthing_service:
            return

        self.state.syncthing.status_message = "Mapping custom save..."

        def do_map():
            saves = self.settings.get("syncthing_custom_saves", [])
            save = next((s for s in saves if s.get("folder_id") == folder_id), None)
            if not save:
                self.state.syncthing.status_message = "Save not found"
                return

            staging_path = save.get("local_path", "")

            # Move files from staging to chosen folder
            if staging_path and os.path.isdir(staging_path) and staging_path != local_path:
                os.makedirs(local_path, exist_ok=True)
                for item in os.listdir(staging_path):
                    src = os.path.join(staging_path, item)
                    dst = os.path.join(local_path, item)
                    if os.path.isfile(src):
                        shutil.copy2(src, dst)

            # Reconfigure Syncthing folder to point to new path
            # Remove and re-add with new path
            config = self.syncthing_service.get_config()
            my_id = self.syncthing_service.get_device_id()
            device_ids = [d["deviceID"] for d in config.get("devices", []) if d["deviceID"] != my_id]

            self.syncthing_service.remove_folder(folder_id)
            self.syncthing_service.add_folder(folder_id, save.get("name", ""), local_path, device_ids + [my_id])

            # Write .stignore if file mode
            if save.get("sync_mode") == "files" and save.get("sync_files"):
                SyncthingService.write_stignore(local_path, save["sync_files"])

            # Update settings
            save["local_path"] = local_path
            save["mapped"] = True
            self.settings["syncthing_custom_saves"] = saves
            save_settings(self.settings)

            # Update state
            self.state.syncthing.custom_saves = saves
            self.state.syncthing.custom_step = ""
            self.state.syncthing.status_message = f"Mapped: {save.get('name', '')}"

        threading.Thread(target=do_map, daemon=True).start()
```

**Step 5: Handle manage modal (change path / remove)**

In the confirm modal OK handler, add:

```python
        elif context and context.startswith("custom_save_manage_"):
            folder_id = context.replace("custom_save_manage_", "")
            # "Change Path" chosen
            self._open_folder_browser(f"custom_save_map_{folder_id}")
```

In the confirm modal Cancel handler, add for remove:

```python
        if self.state.confirm_modal.context and self.state.confirm_modal.context.startswith("custom_save_manage_"):
            folder_id = self.state.confirm_modal.context.replace("custom_save_manage_", "")
            self._remove_custom_save(folder_id)
            self.state.confirm_modal.show = False
            return
```

**Step 6: Add _remove_custom_save method**

```python
    def _remove_custom_save(self, folder_id: str):
        """Remove a custom save sync."""
        if self.syncthing_service:
            self.syncthing_service.remove_folder(folder_id)
        saves = self.settings.get("syncthing_custom_saves", [])
        saves = [s for s in saves if s.get("folder_id") != folder_id]
        self.settings["syncthing_custom_saves"] = saves
        save_settings(self.settings)
        self.state.syncthing.custom_saves = saves
        self.state.syncthing.status_message = "Custom save removed"
```

**Step 7: Commit**

```bash
git add src/app.py
git commit -m "feat(custom-sync): add mapping, manage, and remove for custom saves"
```

---

### Task 9: Integration Testing & Edge Cases

**Files:**
- Modify: `src/app.py` — fix edge cases
- Modify: `src/services/syncthing_service.py` — handle duplicate folder IDs

**Step 1: Handle duplicate folder ID**

In `SyncthingService.add_custom_save`, before adding the folder, check for duplicates:

```python
        # Check if folder ID already exists
        existing = set(self.get_existing_folder_ids())
        if folder_id in existing:
            # Append number to make unique
            i = 2
            while f"{folder_id}-{i}" in existing:
                i += 1
            folder_id = f"{folder_id}-{i}"
```

**Step 2: Guard against empty file selection**

In the file select confirm handler (Task 7 Step 4), the guard `if self.state.syncthing.custom_selected_files` already prevents empty selection. Add visual feedback:

```python
                # Confirm button
                if self.state.syncthing.custom_selected_files:
                    self._create_custom_save("files")
                else:
                    self.state.syncthing.status_message = "Select at least one file"
```

**Step 3: Guard against missing syncthing_service**

Ensure `_enter_custom_file_select` and `_create_custom_save` check `self.syncthing_service` early.

**Step 4: Manual test checklist**

Test the following flows manually:

1. **Add custom save (folder mode):**
   - Syncthing screen → CUSTOM SAVES → Add Custom Save
   - Enter name → Browse to folder → Select "Entire Folder"
   - Verify sync_info.json created in folder
   - Verify appears in CUSTOM SAVES list with "Synced" status

2. **Add custom save (file mode):**
   - Add Custom Save → Enter name → Browse to folder
   - Select "Select Files" → Check files → Confirm
   - Verify .stignore created with correct whitelist
   - Verify appears with "(N files)" suffix

3. **Receiving device mapping:**
   - Verify "Not mapped" saves show folder browser on tap
   - Select local folder → verify files moved from staging
   - Verify status changes to "Synced"

4. **Manage existing save:**
   - Tap mapped save → "Change Path" or "Remove"
   - Verify remove cleans up Syncthing folder

**Step 5: Commit**

```bash
git add src/app.py src/services/syncthing_service.py
git commit -m "fix(custom-sync): handle edge cases and duplicate folder IDs"
```

---

### Task 10: Final Polish & Cleanup

**Files:**
- All modified files

**Step 1: Run linter**

Run: `cd /Users/gabe/Workspace/Games/console_utilities && make lint`
Fix any issues.

**Step 2: Run formatter**

Run: `cd /Users/gabe/Workspace/Games/console_utilities && make format`

**Step 3: Verify app starts and renders**

Run: `cd /Users/gabe/Workspace/Games/console_utilities && make debug`
Navigate to Syncthing screen, verify CUSTOM SAVES section appears.

**Step 4: Commit any fixes**

```bash
git add -u
git commit -m "chore(custom-sync): lint and format cleanup"
```
