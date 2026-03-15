# File Explorer — Design Spec

## Overview

A built-in file manager for the pygame app, accessible from the main menu as "File Explorer". Supports browsing, copy/move/paste, delete, rename, create folder, view text files, and extract zip/rar archives. Designed for handheld consoles with D-pad/joystick and touchscreen input.

## User Experience

### Entry Point

- Added to `_ALL_ROOT_ENTRIES` in `systems_screen.py` as `("File Explorer", "file_explorer")`
- Always visible (no settings toggle)
- Opens to the user's configured ROMs directory (`roms_dir` from settings)
- Initialization done in `AppState.enter_mode()` alongside existing mode init logic

### Layout

- **Header**: "File Explorer" title + back button
- **Breadcrumb bar**: below header, shows path segments (e.g., `/ > roms > psx`)
- **File list**: scrollable list with icon, name, and size per entry
  - Folders first (alphabetical), then files (alphabetical)
  - Hidden files (dot-files) filtered out; symlinks shown normally (followed transparently)
  - Icons differentiate: folder, archive (.zip/.rar), text file (.txt/.md/.xml), generic file
  - Highlighted item shown with accent background + left border
  - Selected items show a checkmark
- **Empty state**: when a folder has no visible entries, show "This folder is empty" centered text
- **Footer**: dynamic, shows item count + button hints or clipboard state

### Footer States

| State | Left Side | Right Side |
|-------|-----------|------------|
| Default | `6 items` | `[Y] Actions  [A] Open  [B] Back` |
| Items selected | `3 selected` | `[Y] Actions  [X] Toggle  [B] Back` |
| Clipboard (copy) | `2 files copied` | `[X] Paste Here  [B] Back` |
| Clipboard (cut) | `1 file cut` | `[X] Paste Here  [B] Back` |

Button hint labels are resolved from the current controller mapping via `button_hints` utility, not hardcoded.

### Input Handling

**Joystick/Controller** — uses action names through the existing controller mapping system (`src/input/controller.py`). Never hardcodes key/button codes.

| Action Name | Behavior |
|-------------|----------|
| `select` (A) | Open folder / View text file |
| `back` (B) | Go up to parent / Close modal / Exit file explorer |
| `search` (X) | Toggle selection on highlighted item. When clipboard is active: X always pastes — selection toggle is unavailable while clipboard has content |
| `detail` (Y) | Open context menu for highlighted item |
| `left_shoulder` (L) | Page up |
| `right_shoulder` (R) | Page down |
| D-pad up/down | Navigate file list / Scroll viewer / Navigate context menu |

**X button priority rule:** When clipboard is active, X always triggers paste. Selection toggle is disabled. The user must paste (or clear clipboard via context menu) before selecting more items. This avoids ambiguity.

**Touchscreen** — when touch input is detected, on-screen action buttons appear at the bottom:

- Default: **Open**, **Actions**, **Back** buttons
- With selection: **Actions**, **Deselect**, **Back**
- With clipboard: **Paste**, **Back**
- Tap item to highlight it
- Double-tap or tap Open button to enter folder / view file
- Long-press on item opens context menu (equivalent to `detail` action)
- Context menu items are tappable

### Context Menu

Triggered by Y button (joystick) or long-press (touch). Appears as a modal overlay list. "New Folder" always appears at the top of the context menu regardless of what's highlighted. Remaining actions adapt based on file type:

**Folders:**
- New Folder
- Open
- Copy
- Cut
- Rename
- Delete

**Text files (.txt, .md, .xml):**
- New Folder
- View
- Copy
- Cut
- Rename
- Delete

**Archives (.zip, .rar):**
- New Folder
- Extract Here (hidden if .rar and `unrar` not available)
- Copy
- Cut
- Rename
- Delete

**Other files:**
- New Folder
- Copy
- Cut
- Rename
- Delete

**Empty directory** (no entries, Y pressed):
- New Folder (only option)

When multiple items are selected and Y is pressed, the context menu shows bulk actions only:
- New Folder
- Copy (N items)
- Cut (N items)
- Delete (N items)

When clipboard is active, "Paste Here" is added after "New Folder":
- New Folder
- Paste Here
- (remaining actions for highlighted item)

### Copy/Move Flow (Clipboard)

1. User highlights or selects file(s)
2. Opens context menu (Y / long-press), chooses Copy or Cut
3. File paths + mode stored in clipboard state
4. Footer updates to show clipboard status (e.g., "2 files copied")
5. User navigates to destination folder
6. Presses X (joystick) or Paste button (touch) to paste
7. On name conflict: if destination has a file with the same name, append ` (1)` suffix (incrementing as needed). No prompt — auto-resolve silently.
8. Files are copied or moved; clipboard is cleared; selection is cleared
9. File list refreshes to show results
10. On failure (e.g., source no longer exists, permission denied): show error modal with message, clear clipboard

Clipboard persists across folder navigation until paste or until user clears it (pressing B when at the root exits file explorer and clears clipboard).

### Extract Flow

1. User highlights a .zip or .rar file
2. Opens context menu, selects "Extract Here"
3. Modal appears: "Extract to current folder" / "Extract to new subfolder"
4. D-pad up/down to pick option, A to confirm, B to cancel
5. Extraction runs (with progress indicator for large archives)
6. On failure: show error modal with message
7. File list refreshes

### Text Viewer

1. User highlights a .txt, .md, or .xml file and presses A (or selects "View" from context menu)
2. Full-screen modal overlay appears with file content
3. If file exceeds 5000 lines, content is truncated with a "--- File truncated (5000 lines shown) ---" indicator at the bottom
4. If file contains binary content (detected by null bytes in the first 1024 bytes), show "Cannot display binary file" message instead
5. Scrollable with D-pad up/down, L/R for page up/down
6. B to close and return to file list
7. Read-only, no editing

### Delete Flow

1. User selects file(s) and chooses Delete from context menu
2. Confirmation modal: "Delete N items?" with item names listed
3. D-pad to highlight Yes/No, A to confirm
4. Files/folders deleted (recursive for folders)
5. On failure (e.g., permission denied): show error modal with message
6. Selection cleared; file list refreshes

### Rename Flow

1. User highlights a file/folder and chooses Rename from context menu
2. Input modal opens with current name pre-filled (reuses existing `char_keyboard` organism)
3. User edits name, confirms with Start/A
4. On failure (e.g., name conflict, permission denied): show error modal
5. File/folder renamed; file list refreshes

### Create Folder

1. User selects "New Folder" from context menu (always available at top)
2. Input modal opens (reuses `char_keyboard`)
3. User types folder name, confirms
4. On failure (e.g., name exists, permission denied): show error modal
5. Folder created in current directory; file list refreshes

### Error Handling

All filesystem operations that fail show an error modal with a descriptive message. The modal is dismissible with B or A. After dismissal, the file list is refreshed (in case partial changes occurred). The `FileExplorerState` includes an `error_message` field; when non-empty, the screen renders an error modal overlay.

## Architecture

### State

New `FileExplorerState` dataclass in `src/state.py`:

```python
@dataclass
class FileEntry:
    name: str
    is_dir: bool
    size: Optional[int]  # None for directories
    modified: float  # Unix timestamp

@dataclass
class FileExplorerState:
    current_path: str = ""
    entries: List[FileEntry] = field(default_factory=list)
    highlighted: int = 0
    scroll_offset: int = 0
    selected: Set[int] = field(default_factory=set)

    # Clipboard (stores full paths, not indices)
    clipboard_paths: List[str] = field(default_factory=list)
    clipboard_mode: str = ""  # "copy" or "cut"

    # Context menu
    context_menu_open: bool = False
    context_menu_highlighted: int = 0
    context_menu_actions: List[Tuple[str, str]] = field(default_factory=list)  # (action_id, label)

    # Text viewer
    viewer_open: bool = False
    viewer_content: List[str] = field(default_factory=list)
    viewer_title: str = ""
    viewer_scroll: int = 0
    viewer_truncated: bool = False

    # Extract modal
    extract_modal_open: bool = False
    extract_target: str = ""
    extract_highlighted: int = 0  # 0 = current folder, 1 = subfolder

    # Delete confirmation
    delete_modal_open: bool = False
    delete_targets: List[str] = field(default_factory=list)
    delete_highlighted: int = 0  # 0 = Yes, 1 = No

    # Rename / New folder input
    input_modal_open: bool = False
    input_modal_title: str = ""
    input_modal_value: str = ""
    input_modal_action: str = ""  # "rename" or "mkdir"

    # Error display
    error_message: str = ""
```

Added to `AppState` as `self.file_explorer = FileExplorerState()`.

**Important:** `selected` stores indices into `entries`. After any filesystem mutation (delete, rename, paste, extract, mkdir), `selected` must be cleared and the entry list re-loaded. This prevents stale index references.

### Service

New `src/services/file_explorer_service.py`:

- `list_directory(path: str) -> List[FileEntry]` — lists directory, folders first, alpha-sorted, hidden files excluded, symlinks followed transparently
- `copy_files(sources: List[str], dest: str) -> Tuple[bool, str]` — copies files/folders to destination; auto-resolves name conflicts with ` (1)` suffix
- `move_files(sources: List[str], dest: str) -> Tuple[bool, str]` — moves files/folders to destination; auto-resolves name conflicts
- `delete_paths(paths: List[str]) -> Tuple[bool, str]` — deletes files and folders (recursive)
- `rename_path(path: str, new_name: str) -> Tuple[bool, str]` — renames, validates no path traversal
- `create_folder(parent: str, name: str) -> Tuple[bool, str]` — creates directory
- `read_text_file(path: str, max_lines: int = 5000) -> Tuple[List[str], bool]` — reads text content with line limit; returns (lines, was_truncated); detects binary files via null-byte check
- `extract_archive(path: str, to_subfolder: bool) -> Tuple[bool, str]` — extracts .zip (zipfile) or .rar (subprocess `unrar`)
- `is_unrar_available() -> bool` — checks if `unrar` command exists on system

All operations return `Tuple[bool, str]` — success flag and error message (empty on success). This feeds directly into `state.error_message`.

Uses standard library (`os`, `shutil`, `zipfile`). RAR extraction uses `unrar` command via subprocess (commonly available on Batocera/Linux consoles). If `unrar` is not available, "Extract Here" is hidden from the context menu for .rar files. ZIP extraction always works.

### Screen

New `src/ui/screens/file_explorer_screen.py`:

- Renders header, breadcrumb bar, file list, and footer as custom layout (does not directly extend `ListScreenTemplate` — the breadcrumb bar and dynamic footer require custom composition of `Header`, `MenuList`, and text rendering atoms)
- Renders context menu as modal overlay (reuses `ModalFrame` organism)
- Renders text viewer as full-screen modal
- Renders extract/delete confirmation modals
- Renders input modals using `char_keyboard` organism
- Renders error modal when `error_message` is non-empty
- Renders empty state text when directory has no entries

### Screen Manager Integration

- Import and instantiate `FileExplorerScreen` in `screen_manager.py`
- Add render routing for `mode == "file_explorer"`

### App Integration (`app.py`)

- Add `file_explorer` to mode handling in:
  - Navigation handler (D-pad)
  - Selection handler (A button)
  - Back handler (B button)
  - Detail handler (Y button)
  - Search handler (X button — select toggle or paste)
  - Shoulder button handlers (L/R for page up/down)
- Add `_handle_file_explorer_select()`, `_handle_file_explorer_back()`, etc.
- Initialize `file_explorer.current_path` from `settings["roms_dir"]` in `AppState.enter_mode()`
- Refresh file list and clear `selected` set on every operation that modifies filesystem
- Add file explorer modal states to `AppState.close_all_modals()`

### Main Menu

Add to `_ALL_ROOT_ENTRIES` in `systems_screen.py`:
```python
("File Explorer", "file_explorer"),
```

Positioned after existing utility entries. No conditional visibility.

## File Summary

| File | Change |
|------|--------|
| `src/state.py` | Add `FileEntry`, `FileExplorerState` dataclasses; update `enter_mode()` and `close_all_modals()` |
| `src/services/file_explorer_service.py` | **New** — filesystem operations |
| `src/ui/screens/file_explorer_screen.py` | **New** — screen rendering |
| `src/ui/screens/screen_manager.py` | Import + instantiate + render routing |
| `src/ui/screens/systems_screen.py` | Add menu entry |
| `src/app.py` | Mode handling, input routing, action methods |
