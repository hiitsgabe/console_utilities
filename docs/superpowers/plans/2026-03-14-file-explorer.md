# File Explorer Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a built-in file manager to the main menu with browse, copy/move/paste, delete, rename, create folder, text viewer, and zip/rar extraction.

**Architecture:** New `file_explorer` mode with `FileExplorerState` dataclass, `FileExplorerService` for filesystem ops, `FileExplorerScreen` for rendering. Follows existing patterns: state in `state.py`, service in `src/services/`, screen in `src/ui/screens/`, input routing in `app.py`.

**Tech Stack:** Python, pygame, os/shutil/zipfile stdlib, subprocess for unrar

**Spec:** `docs/superpowers/specs/2026-03-14-file-explorer-design.md`

---

## Chunk 1: State, Service, and Basic Browsing

### Task 1: Add FileExplorerState to state.py

**Files:**
- Modify: `src/state.py`

- [ ] **Step 1: Add FileEntry and FileExplorerState dataclasses**

Add after the existing state dataclasses (around line 200, near other feature states):

```python
@dataclass
class FileExplorerState:
    """State for the file explorer screen."""
    current_path: str = ""
    entries: List[Any] = field(default_factory=list)  # List of dicts from service
    highlighted: int = 0
    scroll_offset: int = 0
    selected: Set[int] = field(default_factory=set)

    # Clipboard (stores full paths, not indices)
    clipboard_paths: List[str] = field(default_factory=list)
    clipboard_mode: str = ""  # "copy" or "cut"

    # Context menu
    context_menu_open: bool = False
    context_menu_highlighted: int = 0
    context_menu_actions: List[Any] = field(default_factory=list)  # List of (action_id, label)

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

    # Keyboard input index (for char_keyboard navigation)
    kb_selected_index: int = 0

    # Error display
    error_message: str = ""
```

- [ ] **Step 2: Register in AppState.__init__**

In `AppState.__init__` (around line 952 where other states are initialized), add:

```python
self.file_explorer = FileExplorerState()
```

- [ ] **Step 3: Update enter_mode()**

In `AppState.enter_mode()` (line 1061), add after the syncthing block:

```python
elif new_mode == "file_explorer":
    self.file_explorer.highlighted = 0
    self.file_explorer.scroll_offset = 0
    self.file_explorer.selected = set()
    self.file_explorer.context_menu_open = False
    self.file_explorer.viewer_open = False
    self.file_explorer.extract_modal_open = False
    self.file_explorer.delete_modal_open = False
    self.file_explorer.input_modal_open = False
    self.file_explorer.error_message = ""
```

- [ ] **Step 4: Update close_all_modals()**

In `AppState.close_all_modals()` (line 1084), add at the end before the method returns:

```python
self.file_explorer.context_menu_open = False
self.file_explorer.viewer_open = False
self.file_explorer.extract_modal_open = False
self.file_explorer.delete_modal_open = False
self.file_explorer.input_modal_open = False
self.file_explorer.error_message = ""
```

- [ ] **Step 5: Commit**

```bash
git add src/state.py
git commit -m "Add FileExplorerState dataclass"
```

---

### Task 2: Create FileExplorerService

**Files:**
- Create: `src/services/file_explorer_service.py`

- [ ] **Step 1: Create the service file with list_directory**

```python
"""
File explorer service — filesystem operations for the file explorer screen.
"""

import os
import shutil
import subprocess
from typing import List, Optional, Tuple
from zipfile import ZipFile


def list_directory(path: str) -> Tuple[List[dict], str]:
    """
    List directory contents, folders first, alpha-sorted, hidden files excluded.

    Returns (entries, error_message). Each entry is a dict with keys:
    name, is_dir, size, modified. Symlinks are followed transparently.
    """
    path = os.path.abspath(path)
    dirs = []
    files = []

    try:
        entries = os.listdir(path)
    except PermissionError:
        return [], "Permission denied"
    except OSError as e:
        return [], str(e)[:80]

    for entry_name in entries:
        if entry_name.startswith("."):
            continue

        full_path = os.path.join(path, entry_name)
        try:
            stat = os.stat(full_path)  # follows symlinks
            is_dir = os.path.isdir(full_path)
            item = {
                "name": entry_name,
                "is_dir": is_dir,
                "size": None if is_dir else stat.st_size,
                "modified": stat.st_mtime,
            }
            if is_dir:
                dirs.append(item)
            else:
                files.append(item)
        except OSError:
            continue

    dirs.sort(key=lambda x: x["name"].lower())
    files.sort(key=lambda x: x["name"].lower())

    return dirs + files, ""


def copy_files(sources: List[str], dest_dir: str) -> Tuple[bool, str]:
    """
    Copy files/folders to destination directory.
    Auto-resolves name conflicts with ' (N)' suffix.
    """
    try:
        os.makedirs(dest_dir, exist_ok=True)
        for src in sources:
            if not os.path.exists(src):
                return False, f"Source not found: {os.path.basename(src)}"
            basename = os.path.basename(src)
            dst = _resolve_conflict(dest_dir, basename)
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
        return True, ""
    except PermissionError:
        return False, "Permission denied"
    except OSError as e:
        return False, str(e)[:80]


def move_files(sources: List[str], dest_dir: str) -> Tuple[bool, str]:
    """
    Move files/folders to destination directory.
    Auto-resolves name conflicts with ' (N)' suffix.
    """
    try:
        os.makedirs(dest_dir, exist_ok=True)
        for src in sources:
            if not os.path.exists(src):
                return False, f"Source not found: {os.path.basename(src)}"
            basename = os.path.basename(src)
            dst = _resolve_conflict(dest_dir, basename)
            shutil.move(src, dst)
        return True, ""
    except PermissionError:
        return False, "Permission denied"
    except OSError as e:
        return False, str(e)[:80]


def delete_paths(paths: List[str]) -> Tuple[bool, str]:
    """Delete files and folders (recursive for folders)."""
    try:
        for path in paths:
            if not os.path.exists(path):
                continue
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
        return True, ""
    except PermissionError:
        return False, "Permission denied"
    except OSError as e:
        return False, str(e)[:80]


def rename_path(path: str, new_name: str) -> Tuple[bool, str]:
    """Rename a file or folder. Validates no path traversal."""
    if "/" in new_name or "\\" in new_name:
        return False, "Name cannot contain slashes"
    if not new_name.strip():
        return False, "Name cannot be empty"

    parent = os.path.dirname(path)
    new_path = os.path.join(parent, new_name)
    if os.path.exists(new_path):
        return False, f"'{new_name}' already exists"

    try:
        os.rename(path, new_path)
        return True, ""
    except PermissionError:
        return False, "Permission denied"
    except OSError as e:
        return False, str(e)[:80]


def create_folder(parent: str, name: str) -> Tuple[bool, str]:
    """Create a new directory."""
    if "/" in name or "\\" in name:
        return False, "Name cannot contain slashes"
    if not name.strip():
        return False, "Name cannot be empty"

    new_path = os.path.join(parent, name)
    if os.path.exists(new_path):
        return False, f"'{name}' already exists"

    try:
        os.makedirs(new_path)
        return True, ""
    except PermissionError:
        return False, "Permission denied"
    except OSError as e:
        return False, str(e)[:80]


def read_text_file(path: str, max_lines: int = 5000) -> Tuple[List[str], bool, str]:
    """
    Read text file content.

    Returns: (lines, was_truncated, error_message)
    """
    try:
        # Binary check: read first 1024 bytes for null bytes
        with open(path, "rb") as f:
            head = f.read(1024)
        if b"\x00" in head:
            return [], False, "Cannot display binary file"

        lines = []
        truncated = False
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                if i >= max_lines:
                    truncated = True
                    break
                lines.append(line.rstrip("\n\r"))
        return lines, truncated, ""
    except PermissionError:
        return [], False, "Permission denied"
    except OSError as e:
        return [], False, str(e)[:80]


def extract_archive(path: str, to_subfolder: bool) -> Tuple[bool, str]:
    """
    Extract .zip or .rar archive.

    Args:
        path: Path to archive file
        to_subfolder: If True, extract into a subfolder named after the archive
    """
    parent_dir = os.path.dirname(path)
    basename = os.path.splitext(os.path.basename(path))[0]

    if to_subfolder:
        dest = _resolve_conflict(parent_dir, basename)
        os.makedirs(dest, exist_ok=True)
    else:
        dest = parent_dir

    ext = os.path.splitext(path)[1].lower()

    try:
        if ext == ".zip":
            with ZipFile(path, "r") as zf:
                zf.extractall(dest)
            return True, ""
        elif ext == ".rar":
            if not is_unrar_available():
                return False, "unrar not installed"
            result = subprocess.run(
                ["unrar", "x", "-o+", path, dest + "/"],
                capture_output=True,
                timeout=600,
            )
            if result.returncode != 0:
                return False, f"unrar failed: {result.stderr.decode()[:80]}"
            return True, ""
        else:
            return False, f"Unsupported archive format: {ext}"
    except PermissionError:
        return False, "Permission denied"
    except subprocess.TimeoutExpired:
        return False, "Extraction timed out"
    except OSError as e:
        return False, str(e)[:80]


def is_unrar_available() -> bool:
    """Check if unrar command is available."""
    try:
        subprocess.run(["unrar"], capture_output=True, timeout=5)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def format_size(size_bytes: Optional[int]) -> str:
    """Format file size for display."""
    if size_bytes is None:
        return ""
    if size_bytes >= 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
    elif size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes} B"


def get_file_icon(name: str, is_dir: bool) -> str:
    """Get a display icon character for file type."""
    if is_dir:
        return "D"  # Folder icon rendered by screen
    ext = os.path.splitext(name)[1].lower()
    if ext in (".zip", ".rar"):
        return "Z"  # Archive
    elif ext in (".txt", ".md", ".xml", ".log", ".cfg", ".ini", ".json"):
        return "T"  # Text
    return "F"  # Generic file


def _resolve_conflict(dest_dir: str, basename: str) -> str:
    """
    Resolve name conflict by appending ' (N)' suffix.
    Returns the full destination path.
    """
    dst = os.path.join(dest_dir, basename)
    if not os.path.exists(dst):
        return dst

    name, ext = os.path.splitext(basename)
    counter = 1
    while True:
        new_name = f"{name} ({counter}){ext}"
        dst = os.path.join(dest_dir, new_name)
        if not os.path.exists(dst):
            return dst
        counter += 1
```

- [ ] **Step 2: Commit**

```bash
git add src/services/file_explorer_service.py
git commit -m "Add file explorer service with filesystem operations"
```

---

### Task 3: Create FileExplorerScreen

**Files:**
- Create: `src/ui/screens/file_explorer_screen.py`

- [ ] **Step 1: Create the screen file**

This is a large file. It renders the main file list with breadcrumb bar, context menu overlay, text viewer modal, extract/delete confirmation modals, input modal (keyboard), and error modal. It does NOT use `ListScreenTemplate` directly — it composes `Header`, `MenuList`, `Text`, `ModalFrame`, `ActionButton`, and `CharKeyboard` organisms/atoms for the custom layout.

```python
"""
File explorer screen — full-screen file manager with D-pad navigation.
"""

import os
import pygame
from typing import Dict, List, Optional, Set, Tuple, Any

from ui.theme import Theme, default_theme
from ui.organisms.header import Header
from ui.organisms.menu_list import MenuList
from ui.organisms.modal_frame import ModalFrame
from ui.organisms.char_keyboard import CharKeyboard
from ui.atoms.text import Text
from ui.atoms.surface import Surface
from ui.molecules.action_button import ActionButton
from utils.button_hints import get_button_name
from services.file_explorer_service import format_size, get_file_icon


class FileExplorerScreen:
    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.header = Header(theme)
        self.menu_list = MenuList(theme)
        self.text = Text(theme)
        self.surface = Surface(theme)
        self.modal_frame = ModalFrame(theme)
        self.action_button = ActionButton(theme)
        self.char_keyboard = CharKeyboard(theme)

    def render(
        self,
        screen: pygame.Surface,
        state: Any,
        input_mode: str = "keyboard",
    ) -> Dict[str, Any]:
        """
        Render the file explorer screen.

        Returns dict of interactive rects for touch/click handling.
        """
        rects: Dict[str, Any] = {}
        fe = state.file_explorer
        w, h = screen.get_size()

        # Background
        screen.fill(self.theme.background)

        # Header
        header_rect, back_rect = self.header.render(
            screen,
            title="File Explorer",
            show_back=True,
        )
        rects["back"] = back_rect

        # Breadcrumb bar
        breadcrumb_y = header_rect.bottom
        breadcrumb_h = 28
        breadcrumb_rect = pygame.Rect(0, breadcrumb_y, w, breadcrumb_h)
        pygame.draw.rect(screen, self.theme.surface, breadcrumb_rect)

        breadcrumb_text = self._format_breadcrumb(fe.current_path, w)
        self.text.render(
            screen,
            breadcrumb_text,
            (self.theme.padding_md, breadcrumb_y + breadcrumb_h // 2),
            color=self.theme.primary,
            size=self.theme.font_size_sm,
            v_align="center",
        )

        # Footer area
        footer_h = 36
        footer_y = h - footer_h

        # Touch buttons or hint text in footer
        footer_rect = pygame.Rect(0, footer_y, w, footer_h)
        pygame.draw.rect(screen, self.theme.surface, footer_rect)

        touch_rects = self._render_footer(
            screen, footer_rect, fe, input_mode
        )
        rects.update(touch_rects)

        # File list area
        list_y = breadcrumb_rect.bottom
        list_h = footer_y - list_y
        list_rect = pygame.Rect(0, list_y, w, list_h)

        if not fe.entries:
            # Empty state
            self.text.render(
                screen,
                "This folder is empty",
                (w // 2, list_y + list_h // 2),
                color=self.theme.text_secondary,
                size=self.theme.font_size_md,
                align="center",
                v_align="center",
            )
            rects["item_rects"] = []
            rects["scroll_offset"] = 0
        else:
            item_rects, scroll_offset = self.menu_list.render(
                screen,
                list_rect,
                fe.entries,
                fe.highlighted,
                fe.selected,
                item_height=44,
                get_label=self._get_item_label,
                get_secondary=self._get_item_secondary,
                show_checkbox=bool(fe.selected),
            )
            rects["item_rects"] = item_rects
            rects["scroll_offset"] = scroll_offset

        # Modals (rendered on top, in priority order)
        if fe.error_message:
            self._render_error_modal(screen, fe, rects)
        elif fe.delete_modal_open:
            self._render_delete_modal(screen, fe, rects)
        elif fe.extract_modal_open:
            self._render_extract_modal(screen, fe, rects)
        elif fe.input_modal_open:
            self._render_input_modal(screen, fe, input_mode, rects)
        elif fe.viewer_open:
            self._render_viewer(screen, fe, rects)
        elif fe.context_menu_open:
            self._render_context_menu(screen, fe, rects)

        return rects

    def _format_breadcrumb(self, path: str, max_width: int) -> str:
        """Format path as breadcrumb: / > roms > psx"""
        if not path:
            return "/"
        parts = path.split(os.sep)
        parts = [p for p in parts if p]
        if len(parts) > 4:
            return "/ > ... > " + " > ".join(parts[-3:])
        return "/ > " + " > ".join(parts) if parts else "/"

    def _get_item_label(self, item: Any) -> str:
        """Get display label for a file entry."""
        if isinstance(item, dict):
            name = item.get("name", "")
            icon = get_file_icon(name, item.get("is_dir", False))
            prefix = {"D": "[DIR] ", "Z": "[ZIP] ", "T": "[TXT] "}.get(icon, "")
            return f"{prefix}{name}"
        return str(getattr(item, "name", item))

    def _get_item_secondary(self, item: Any) -> str:
        """Get secondary text (size) for a file entry."""
        if isinstance(item, dict):
            if item.get("is_dir"):
                return "Folder"
            return format_size(item.get("size"))
        return ""

    def _render_footer(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        fe: Any,
        input_mode: str,
    ) -> Dict[str, Any]:
        """Render footer with hints or touch buttons."""
        rects: Dict[str, Any] = {}
        mid_y = rect.top + rect.height // 2

        # Left side: item count or clipboard status
        if fe.clipboard_paths:
            count = len(fe.clipboard_paths)
            mode_label = "copied" if fe.clipboard_mode == "copy" else "cut"
            left_text = f"{count} file{'s' if count > 1 else ''} {mode_label}"
            left_color = (
                self.theme.primary
                if fe.clipboard_mode == "copy"
                else self.theme.warning
            )
        elif fe.selected:
            left_text = f"{len(fe.selected)} selected"
            left_color = self.theme.text_primary
        else:
            left_text = f"{len(fe.entries)} items"
            left_color = self.theme.text_secondary

        self.text.render(
            screen,
            left_text,
            (rect.left + self.theme.padding_md, mid_y),
            color=left_color,
            size=self.theme.font_size_sm,
            v_align="center",
        )

        if input_mode == "touch":
            # Render touch buttons
            rects.update(
                self._render_touch_buttons(screen, rect, fe)
            )
        else:
            # Render button hints text
            hints = self._get_button_hints(fe, input_mode)
            self.text.render(
                screen,
                hints,
                (rect.right - self.theme.padding_md, mid_y),
                color=self.theme.text_secondary,
                size=self.theme.font_size_sm,
                align="right",
                v_align="center",
            )

        return rects

    def _render_touch_buttons(
        self, screen: pygame.Surface, rect: pygame.Rect, fe: Any
    ) -> Dict[str, Any]:
        """Render on-screen touch action buttons."""
        rects: Dict[str, Any] = {}
        btn_h = 28
        btn_y = rect.top + (rect.height - btn_h) // 2
        btn_x = rect.right - self.theme.padding_md
        btn_spacing = 8

        buttons = []
        if fe.clipboard_paths:
            buttons = [("Paste", "touch_paste"), ("Back", "touch_back")]
        elif fe.selected:
            buttons = [
                ("Actions", "touch_actions"),
                ("Deselect", "touch_deselect"),
                ("Back", "touch_back"),
            ]
        else:
            buttons = [
                ("Open", "touch_open"),
                ("Actions", "touch_actions"),
                ("Back", "touch_back"),
            ]

        for label, key in reversed(buttons):
            btn_w = max(60, len(label) * 9 + 16)
            btn_x -= btn_w
            btn_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
            self.action_button.render(screen, btn_rect, label)
            rects[key] = btn_rect
            btn_x -= btn_spacing

        return rects

    def _get_button_hints(self, fe: Any, input_mode: str) -> str:
        """Build button hints string for keyboard/gamepad."""
        a = get_button_name("select", input_mode)
        b = get_button_name("back", input_mode)
        x = get_button_name("search", input_mode)
        y = get_button_name("detail", input_mode)

        if fe.clipboard_paths:
            return f"[{x}] Paste  [{b}] Back"
        elif fe.selected:
            return f"[{y}] Actions  [{x}] Toggle  [{b}] Back"
        else:
            return f"[{y}] Actions  [{a}] Open  [{b}] Back"

    def _render_context_menu(
        self, screen: pygame.Surface, fe: Any, rects: Dict
    ):
        """Render context menu modal overlay."""
        w, h = screen.get_size()
        actions = fe.context_menu_actions
        if not actions:
            return

        menu_w = min(300, w - 40)
        item_h = 40
        menu_h = min(len(actions) * item_h + 20, h - 100)
        menu_x = (w - menu_w) // 2
        menu_y = (h - menu_h) // 2

        # Dim background
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        screen.blit(overlay, (0, 0))

        # Menu background
        menu_rect = pygame.Rect(menu_x, menu_y, menu_w, menu_h)
        pygame.draw.rect(screen, self.theme.surface, menu_rect, border_radius=8)
        pygame.draw.rect(
            screen, self.theme.text_secondary, menu_rect, width=1, border_radius=8
        )

        # Render items
        ctx_item_rects = []
        for i, (action_id, label) in enumerate(actions):
            item_y = menu_y + 10 + i * item_h
            item_rect = pygame.Rect(menu_x + 4, item_y, menu_w - 8, item_h)

            if i == fe.context_menu_highlighted:
                pygame.draw.rect(
                    screen, self.theme.primary, item_rect, border_radius=4
                )
                text_color = self.theme.background
            else:
                text_color = self.theme.text_primary

            # Red text for delete
            if action_id == "delete":
                text_color = (
                    self.theme.background
                    if i == fe.context_menu_highlighted
                    else self.theme.error
                )

            self.text.render(
                screen,
                label,
                (menu_x + 20, item_y + item_h // 2),
                color=text_color,
                size=self.theme.font_size_md,
                v_align="center",
            )
            ctx_item_rects.append(item_rect)

        rects["context_menu_items"] = ctx_item_rects

    def _render_viewer(self, screen: pygame.Surface, fe: Any, rects: Dict):
        """Render full-screen text viewer modal."""
        w, h = screen.get_size()

        # Full screen overlay
        screen.fill(self.theme.background)

        # Header
        header_rect, close_rect = self.header.render(
            screen, title=fe.viewer_title, show_back=True
        )
        rects["viewer_close"] = close_rect

        # Content area
        content_y = header_rect.bottom + 4
        content_h = h - content_y
        line_h = 18
        visible_lines = content_h // line_h
        max_scroll = max(0, len(fe.viewer_content) - visible_lines)
        scroll = min(fe.viewer_scroll, max_scroll)

        for i in range(visible_lines):
            line_idx = scroll + i
            if line_idx >= len(fe.viewer_content):
                break
            line = fe.viewer_content[line_idx]
            y = content_y + i * line_h
            self.text.render(
                screen,
                line[:120],  # Truncate long lines
                (self.theme.padding_md, y),
                color=self.theme.text_primary,
                size=self.theme.font_size_sm,
            )

        # Truncation indicator
        if fe.viewer_truncated and scroll >= max_scroll:
            self.text.render(
                screen,
                "--- File truncated (5000 lines shown) ---",
                (w // 2, h - 20),
                color=self.theme.warning,
                size=self.theme.font_size_sm,
                align="center",
            )

        # Scroll indicator
        if len(fe.viewer_content) > visible_lines:
            pct = scroll / max(max_scroll, 1)
            bar_h = max(20, int(content_h * visible_lines / len(fe.viewer_content)))
            bar_y = content_y + int((content_h - bar_h) * pct)
            bar_rect = pygame.Rect(w - 6, bar_y, 4, bar_h)
            pygame.draw.rect(screen, self.theme.text_secondary, bar_rect, border_radius=2)

    def _render_error_modal(
        self, screen: pygame.Surface, fe: Any, rects: Dict
    ):
        """Render error message modal."""
        w, h = screen.get_size()

        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        screen.blit(overlay, (0, 0))

        modal_w = min(400, w - 40)
        modal_h = 140
        modal_rect = pygame.Rect(
            (w - modal_w) // 2, (h - modal_h) // 2, modal_w, modal_h
        )
        pygame.draw.rect(screen, self.theme.surface, modal_rect, border_radius=8)

        self.text.render(
            screen,
            "Error",
            (modal_rect.centerx, modal_rect.top + 25),
            color=self.theme.error,
            size=self.theme.font_size_lg,
            align="center",
        )
        self.text.render(
            screen,
            fe.error_message[:60],
            (modal_rect.centerx, modal_rect.centery),
            color=self.theme.text_primary,
            size=self.theme.font_size_md,
            align="center",
        )

        # OK button
        btn_w = 80
        btn_h = 32
        btn_rect = pygame.Rect(
            modal_rect.centerx - btn_w // 2,
            modal_rect.bottom - btn_h - 15,
            btn_w,
            btn_h,
        )
        self.action_button.render(screen, btn_rect, "OK", hover=True)
        rects["error_ok"] = btn_rect

    def _render_delete_modal(
        self, screen: pygame.Surface, fe: Any, rects: Dict
    ):
        """Render delete confirmation modal."""
        w, h = screen.get_size()

        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        screen.blit(overlay, (0, 0))

        count = len(fe.delete_targets)
        modal_w = min(400, w - 40)
        modal_h = min(60 + count * 20 + 60, h - 80)
        modal_rect = pygame.Rect(
            (w - modal_w) // 2, (h - modal_h) // 2, modal_w, modal_h
        )
        pygame.draw.rect(screen, self.theme.surface, modal_rect, border_radius=8)

        self.text.render(
            screen,
            f"Delete {count} item{'s' if count > 1 else ''}?",
            (modal_rect.centerx, modal_rect.top + 25),
            color=self.theme.error,
            size=self.theme.font_size_lg,
            align="center",
        )

        # Show file names (up to 5)
        for i, name in enumerate(fe.delete_targets[:5]):
            self.text.render(
                screen,
                os.path.basename(name),
                (modal_rect.centerx, modal_rect.top + 50 + i * 18),
                color=self.theme.text_secondary,
                size=self.theme.font_size_sm,
                align="center",
            )
        if count > 5:
            self.text.render(
                screen,
                f"... and {count - 5} more",
                (modal_rect.centerx, modal_rect.top + 50 + 5 * 18),
                color=self.theme.text_secondary,
                size=self.theme.font_size_sm,
                align="center",
            )

        # Yes/No buttons
        btn_w = 80
        btn_h = 32
        btn_y = modal_rect.bottom - btn_h - 15
        gap = 20

        yes_rect = pygame.Rect(
            modal_rect.centerx - btn_w - gap // 2, btn_y, btn_w, btn_h
        )
        no_rect = pygame.Rect(
            modal_rect.centerx + gap // 2, btn_y, btn_w, btn_h
        )
        self.action_button.render(
            screen, yes_rect, "Yes", hover=(fe.delete_highlighted == 0)
        )
        self.action_button.render(
            screen, no_rect, "No", hover=(fe.delete_highlighted == 1)
        )
        rects["delete_yes"] = yes_rect
        rects["delete_no"] = no_rect

    def _render_extract_modal(
        self, screen: pygame.Surface, fe: Any, rects: Dict
    ):
        """Render extract destination choice modal."""
        w, h = screen.get_size()

        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        screen.blit(overlay, (0, 0))

        modal_w = min(400, w - 40)
        modal_h = 160
        modal_rect = pygame.Rect(
            (w - modal_w) // 2, (h - modal_h) // 2, modal_w, modal_h
        )
        pygame.draw.rect(screen, self.theme.surface, modal_rect, border_radius=8)

        archive_name = os.path.basename(fe.extract_target)
        self.text.render(
            screen,
            f"Extract: {archive_name}",
            (modal_rect.centerx, modal_rect.top + 20),
            color=self.theme.text_primary,
            size=self.theme.font_size_md,
            align="center",
        )

        options = ["Extract to current folder", "Extract to new subfolder"]
        for i, label in enumerate(options):
            opt_y = modal_rect.top + 55 + i * 38
            opt_rect = pygame.Rect(
                modal_rect.left + 15, opt_y, modal_rect.width - 30, 34
            )
            if i == fe.extract_highlighted:
                pygame.draw.rect(
                    screen, self.theme.primary, opt_rect, border_radius=4
                )
                color = self.theme.background
            else:
                color = self.theme.text_primary
            self.text.render(
                screen,
                label,
                (opt_rect.left + 12, opt_rect.centery),
                color=color,
                size=self.theme.font_size_md,
                v_align="center",
            )

        rects["extract_options"] = [
            pygame.Rect(
                modal_rect.left + 15,
                modal_rect.top + 55 + i * 38,
                modal_rect.width - 30,
                34,
            )
            for i in range(2)
        ]

    def _render_input_modal(
        self,
        screen: pygame.Surface,
        fe: Any,
        input_mode: str,
        rects: Dict,
    ):
        """Render rename / new folder input modal with char keyboard."""
        w, h = screen.get_size()

        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        screen.blit(overlay, (0, 0))

        modal_w = min(500, w - 20)
        modal_h = min(380, h - 40)
        modal_rect = pygame.Rect(
            (w - modal_w) // 2, (h - modal_h) // 2, modal_w, modal_h
        )
        pygame.draw.rect(screen, self.theme.surface, modal_rect, border_radius=8)

        self.text.render(
            screen,
            fe.input_modal_title,
            (modal_rect.centerx, modal_rect.top + 20),
            color=self.theme.text_primary,
            size=self.theme.font_size_md,
            align="center",
        )

        # Input field display
        input_y = modal_rect.top + 48
        input_rect = pygame.Rect(
            modal_rect.left + 15, input_y, modal_rect.width - 30, 30
        )
        pygame.draw.rect(screen, self.theme.background, input_rect, border_radius=4)
        pygame.draw.rect(
            screen, self.theme.primary, input_rect, width=1, border_radius=4
        )
        self.text.render(
            screen,
            fe.input_modal_value or " ",
            (input_rect.left + 8, input_rect.centery),
            color=self.theme.text_primary,
            size=self.theme.font_size_md,
            v_align="center",
        )

        # Character keyboard below input
        kb_rect = pygame.Rect(
            modal_rect.left + 10,
            input_y + 40,
            modal_rect.width - 20,
            modal_h - 100,
        )

        char_rects, _ = self.char_keyboard.render(
            screen,
            kb_rect,
            fe.input_modal_value,
            fe.kb_selected_index,
            show_input_field=False,
        )
        rects["kb_char_rects"] = char_rects
```

- [ ] **Step 2: Commit**

```bash
git add src/ui/screens/file_explorer_screen.py
git commit -m "Add file explorer screen with all modal renderers"
```

---

### Task 4: Wire into Screen Manager and Main Menu

**Files:**
- Modify: `src/ui/screens/screen_manager.py`
- Modify: `src/ui/screens/systems_screen.py`

- [ ] **Step 1: Add import and instantiation in screen_manager.py**

Add import near the other screen imports (around line 10):
```python
from .file_explorer_screen import FileExplorerScreen
```

Add instantiation in `ScreenManager.__init__()` (around line 82):
```python
self.file_explorer_screen = FileExplorerScreen(theme)
```

- [ ] **Step 2: Add render routing in screen_manager.py**

In the `render()` method, add an elif block for file_explorer mode (around line 900, near other mode renders):

```python
elif state.mode == "file_explorer":
    fe_rects = self.file_explorer_screen.render(
        screen, state, state.input_mode
    )
    rects.update(fe_rects)
```

- [ ] **Step 3: Add menu entry in systems_screen.py**

In `_ALL_ROOT_ENTRIES` (line 12), add after Utils:
```python
("File Explorer", "file_explorer"),
```

So the list becomes:
```python
_ALL_ROOT_ENTRIES = [
    ("Backup Games", "systems_list"),
    ("Artbox Games Scraper", "scraper_menu"),
    ("Sports Game Updater", "sports_patcher"),
    ("Syncthing Sync", "syncthing"),
    ("Utils", "utils"),
    ("File Explorer", "file_explorer"),
    ("Settings", "settings"),
    ("Credits", "credits"),
]
```

- [ ] **Step 4: Commit**

```bash
git add src/ui/screens/screen_manager.py src/ui/screens/systems_screen.py
git commit -m "Wire file explorer into screen manager and main menu"
```

---

### Task 5: Add app.py Integration — Mode Entry and Basic Navigation

**Files:**
- Modify: `src/app.py`

This is the largest task. It adds all the input handling for the file explorer mode in app.py. Due to the size, this is broken into sub-steps.

- [ ] **Step 1: Add import**

Near the top of app.py, add:
```python
from services import file_explorer_service
```

- [ ] **Step 2: Add mode entry handler**

In the `_select_item()` method (around line 3340), where other menu actions like `"systems_list"`, `"downloads"`, etc. are handled, add:

```python
elif action == "file_explorer":
    self.state.enter_mode("file_explorer")
    self.state.file_explorer.current_path = self.settings.get(
        "roms_dir", os.path.join(SCRIPT_DIR, "roms")
    )
    self._refresh_file_explorer()
```

- [ ] **Step 3: Add _refresh_file_explorer helper**

Add this method to the app class:

```python
def _refresh_file_explorer(self):
    """Reload file explorer entries from current path."""
    fe = self.state.file_explorer
    entries, err = file_explorer_service.list_directory(fe.current_path)
    if err:
        fe.error_message = err
    fe.entries = entries
    fe.selected = set()
    fe.highlighted = min(fe.highlighted, max(0, len(fe.entries) - 1))
    fe.scroll_offset = 0
```

- [ ] **Step 4: Add navigation (D-pad) handler**

In `_move_highlight()` (around line 1071), add a block for file_explorer mode:

```python
elif self.state.mode == "file_explorer":
    fe = self.state.file_explorer
    if fe.context_menu_open:
        if direction == "up":
            fe.context_menu_highlighted = (fe.context_menu_highlighted - 1) % len(fe.context_menu_actions)
        elif direction == "down":
            fe.context_menu_highlighted = (fe.context_menu_highlighted + 1) % len(fe.context_menu_actions)
    elif fe.viewer_open:
        line_h = 18
        screen_h = 600  # Approximate
        visible = screen_h // line_h
        if direction == "up":
            fe.viewer_scroll = max(0, fe.viewer_scroll - 1)
        elif direction == "down":
            max_scroll = max(0, len(fe.viewer_content) - visible)
            fe.viewer_scroll = min(max_scroll, fe.viewer_scroll + 1)
    elif fe.delete_modal_open:
        if direction in ("left", "right"):
            fe.delete_highlighted = 1 - fe.delete_highlighted
    elif fe.extract_modal_open:
        if direction in ("up", "down"):
            fe.extract_highlighted = 1 - fe.extract_highlighted
    elif fe.input_modal_open:
        # Keyboard navigation handled by char_keyboard
        pass
    else:
        # Main file list navigation
        if fe.entries:
            if direction == "up":
                fe.highlighted = max(0, fe.highlighted - 1)
            elif direction == "down":
                fe.highlighted = min(len(fe.entries) - 1, fe.highlighted + 1)
```

- [ ] **Step 5: Add select (A button) handler**

In `_select_item()`, add the file_explorer mode handler:

```python
elif self.state.mode == "file_explorer":
    self._handle_file_explorer_select()
```

And add the method:

```python
def _handle_file_explorer_select(self):
    """Handle A button press in file explorer."""
    fe = self.state.file_explorer

    # Error modal — dismiss
    if fe.error_message:
        fe.error_message = ""
        self._refresh_file_explorer()
        return

    # Delete modal — confirm
    if fe.delete_modal_open:
        if fe.delete_highlighted == 0:  # Yes
            ok, err = file_explorer_service.delete_paths(fe.delete_targets)
            if not ok:
                fe.error_message = err
            fe.delete_modal_open = False
            fe.delete_targets = []
            self._refresh_file_explorer()
        else:  # No
            fe.delete_modal_open = False
            fe.delete_targets = []
        return

    # Extract modal — confirm
    if fe.extract_modal_open:
        to_subfolder = fe.extract_highlighted == 1
        ok, err = file_explorer_service.extract_archive(
            fe.extract_target, to_subfolder
        )
        if not ok:
            fe.error_message = err
        fe.extract_modal_open = False
        fe.extract_target = ""
        self._refresh_file_explorer()
        return

    # Input modal — handled by char_keyboard
    if fe.input_modal_open:
        self._handle_file_explorer_kb_select()
        return

    # Context menu — execute action
    if fe.context_menu_open:
        self._handle_file_explorer_context_action()
        return

    # Viewer — do nothing (B closes)
    if fe.viewer_open:
        return

    # Main list — open folder or view text file
    if not fe.entries or fe.highlighted >= len(fe.entries):
        return

    entry = fe.entries[fe.highlighted]
    full_path = os.path.join(fe.current_path, entry["name"])

    if entry["is_dir"]:
        fe.current_path = full_path
        fe.highlighted = 0
        self._refresh_file_explorer()
    else:
        ext = os.path.splitext(entry["name"])[1].lower()
        if ext in (".txt", ".md", ".xml", ".log", ".cfg", ".ini", ".json"):
            lines, truncated, err = file_explorer_service.read_text_file(full_path)
            if err:
                fe.error_message = err
            else:
                fe.viewer_open = True
                fe.viewer_content = lines
                fe.viewer_title = entry["name"]
                fe.viewer_scroll = 0
                fe.viewer_truncated = truncated
```

- [ ] **Step 6: Add back (B button) handler**

In `_go_back()`, add:

```python
elif self.state.mode == "file_explorer":
    self._handle_file_explorer_back()
```

And add the method:

```python
def _handle_file_explorer_back(self):
    """Handle B button press in file explorer."""
    fe = self.state.file_explorer

    if fe.error_message:
        fe.error_message = ""
        self._refresh_file_explorer()
    elif fe.context_menu_open:
        fe.context_menu_open = False
    elif fe.viewer_open:
        fe.viewer_open = False
    elif fe.delete_modal_open:
        fe.delete_modal_open = False
        fe.delete_targets = []
    elif fe.extract_modal_open:
        fe.extract_modal_open = False
        fe.extract_target = ""
    elif fe.input_modal_open:
        fe.input_modal_open = False
    else:
        # Navigate up or exit
        parent = os.path.dirname(fe.current_path)
        if parent and parent != fe.current_path:
            fe.current_path = parent
            fe.highlighted = 0
            self._refresh_file_explorer()
        else:
            # At root — exit file explorer, clear clipboard
            fe.clipboard_paths = []
            fe.clipboard_mode = ""
            self.state.mode = "systems"
            self.state.highlighted = 0
```

- [ ] **Step 7: Add detail (Y button) handler — context menu**

In `_handle_detail_action()`, add:

```python
elif self.state.mode == "file_explorer":
    self._open_file_explorer_context_menu()
```

And add the method:

```python
def _open_file_explorer_context_menu(self):
    """Open context menu for highlighted file/folder."""
    fe = self.state.file_explorer
    if fe.context_menu_open or fe.viewer_open or fe.input_modal_open:
        return

    actions = []

    # New Folder always available
    actions.append(("mkdir", "New Folder"))

    # Paste available when clipboard active
    if fe.clipboard_paths:
        actions.append(("paste", "Paste Here"))

    # If we have entries and a valid highlight
    if fe.entries and fe.highlighted < len(fe.entries):
        if fe.selected:
            # Bulk actions
            count = len(fe.selected)
            actions.append(("copy", f"Copy ({count} items)"))
            actions.append(("cut", f"Cut ({count} items)"))
            actions.append(("delete", f"Delete ({count} items)"))
        else:
            entry = fe.entries[fe.highlighted]
            name = entry["name"]
            ext = os.path.splitext(name)[1].lower()

            if entry["is_dir"]:
                actions.append(("open", "Open"))
            elif ext in (".txt", ".md", ".xml", ".log", ".cfg", ".ini", ".json"):
                actions.append(("view", "View"))

            if ext in (".zip", ".rar"):
                if ext == ".zip" or file_explorer_service.is_unrar_available():
                    actions.append(("extract", "Extract Here"))

            actions.append(("copy", "Copy"))
            actions.append(("cut", "Cut"))
            actions.append(("rename", "Rename"))
            actions.append(("delete", "Delete"))

    fe.context_menu_actions = actions
    fe.context_menu_highlighted = 0
    fe.context_menu_open = True
```

- [ ] **Step 8: Add context menu action executor**

```python
def _handle_file_explorer_context_action(self):
    """Execute the selected context menu action."""
    fe = self.state.file_explorer
    if not fe.context_menu_actions:
        return

    action_id, _ = fe.context_menu_actions[fe.context_menu_highlighted]
    fe.context_menu_open = False

    if action_id == "mkdir":
        fe.input_modal_open = True
        fe.input_modal_title = "New Folder"
        fe.input_modal_value = ""
        fe.input_modal_action = "mkdir"

    elif action_id == "rename":
        entry = fe.entries[fe.highlighted]
        fe.input_modal_open = True
        fe.input_modal_title = "Rename"
        fe.input_modal_value = entry["name"]
        fe.input_modal_action = "rename"

    elif action_id == "delete":
        if fe.selected:
            paths = [
                os.path.join(fe.current_path, fe.entries[i]["name"])
                for i in sorted(fe.selected)
                if i < len(fe.entries)
            ]
        else:
            entry = fe.entries[fe.highlighted]
            paths = [os.path.join(fe.current_path, entry["name"])]
        fe.delete_modal_open = True
        fe.delete_targets = paths
        fe.delete_highlighted = 1  # Default to "No"

    elif action_id == "copy":
        if fe.selected:
            fe.clipboard_paths = [
                os.path.join(fe.current_path, fe.entries[i]["name"])
                for i in sorted(fe.selected)
                if i < len(fe.entries)
            ]
        else:
            entry = fe.entries[fe.highlighted]
            fe.clipboard_paths = [os.path.join(fe.current_path, entry["name"])]
        fe.clipboard_mode = "copy"
        fe.selected = set()

    elif action_id == "cut":
        if fe.selected:
            fe.clipboard_paths = [
                os.path.join(fe.current_path, fe.entries[i]["name"])
                for i in sorted(fe.selected)
                if i < len(fe.entries)
            ]
        else:
            entry = fe.entries[fe.highlighted]
            fe.clipboard_paths = [os.path.join(fe.current_path, entry["name"])]
        fe.clipboard_mode = "cut"
        fe.selected = set()

    elif action_id == "paste":
        self._file_explorer_paste()

    elif action_id == "open":
        entry = fe.entries[fe.highlighted]
        full_path = os.path.join(fe.current_path, entry["name"])
        if entry["is_dir"]:
            fe.current_path = full_path
            fe.highlighted = 0
            self._refresh_file_explorer()

    elif action_id == "view":
        entry = fe.entries[fe.highlighted]
        full_path = os.path.join(fe.current_path, entry["name"])
        lines, truncated, err = file_explorer_service.read_text_file(full_path)
        if err:
            fe.error_message = err
        else:
            fe.viewer_open = True
            fe.viewer_content = lines
            fe.viewer_title = entry["name"]
            fe.viewer_scroll = 0
            fe.viewer_truncated = truncated

    elif action_id == "extract":
        entry = fe.entries[fe.highlighted]
        fe.extract_modal_open = True
        fe.extract_target = os.path.join(fe.current_path, entry["name"])
        fe.extract_highlighted = 0
```

- [ ] **Step 9: Add paste and keyboard input helpers**

```python
def _file_explorer_paste(self):
    """Paste clipboard contents into current directory."""
    fe = self.state.file_explorer
    if not fe.clipboard_paths:
        return

    if fe.clipboard_mode == "copy":
        ok, err = file_explorer_service.copy_files(
            fe.clipboard_paths, fe.current_path
        )
    else:
        ok, err = file_explorer_service.move_files(
            fe.clipboard_paths, fe.current_path
        )

    if not ok:
        fe.error_message = err

    fe.clipboard_paths = []
    fe.clipboard_mode = ""
    self._refresh_file_explorer()


def _handle_file_explorer_kb_select(self):
    """Handle character keyboard selection in file explorer input modal."""
    fe = self.state.file_explorer
    kb_index = fe.kb_selected_index

    new_text, is_done, toggle_shift = self.screen_manager.file_explorer_screen.char_keyboard.handle_selection(
        kb_index, fe.input_modal_value
    )

    fe.input_modal_value = new_text

    if is_done:
        fe.input_modal_open = False
        if fe.input_modal_action == "mkdir":
            ok, err = file_explorer_service.create_folder(
                fe.current_path, fe.input_modal_value
            )
            if not ok:
                fe.error_message = err
            self._refresh_file_explorer()
        elif fe.input_modal_action == "rename":
            entry = fe.entries[fe.highlighted]
            old_path = os.path.join(fe.current_path, entry["name"])
            ok, err = file_explorer_service.rename_path(
                old_path, fe.input_modal_value
            )
            if not ok:
                fe.error_message = err
            self._refresh_file_explorer()
```

- [ ] **Step 10: Add search (X button) handler — select toggle / paste**

In the method that handles the X/search action, add:

```python
elif self.state.mode == "file_explorer":
    fe = self.state.file_explorer
    if fe.context_menu_open or fe.viewer_open or fe.input_modal_open:
        return
    if fe.clipboard_paths:
        # X = paste when clipboard active
        self._file_explorer_paste()
    elif fe.entries and fe.highlighted < len(fe.entries):
        # X = toggle selection
        if fe.highlighted in fe.selected:
            fe.selected.discard(fe.highlighted)
        else:
            fe.selected.add(fe.highlighted)
```

- [ ] **Step 11: Add shoulder button handlers (L/R page up/down)**

In the shoulder button handlers, add for file_explorer mode:

```python
elif self.state.mode == "file_explorer":
    fe = self.state.file_explorer
    if fe.viewer_open:
        # Page up/down in viewer
        page_size = 20
        if action == "left_shoulder":
            fe.viewer_scroll = max(0, fe.viewer_scroll - page_size)
        else:
            max_scroll = max(0, len(fe.viewer_content) - page_size)
            fe.viewer_scroll = min(max_scroll, fe.viewer_scroll + page_size)
    elif not fe.context_menu_open:
        # Page up/down in file list
        page_size = 10
        if action == "left_shoulder":
            fe.highlighted = max(0, fe.highlighted - page_size)
        else:
            fe.highlighted = min(len(fe.entries) - 1, fe.highlighted + page_size)
```

- [ ] **Step 12: Commit**

```bash
git add src/app.py
git commit -m "Add file explorer input handling and mode integration"
```

---

### Task 6: Manual Testing

- [ ] **Step 1: Run the app and verify basic flow**

```bash
make run
```

Test the following:
1. File Explorer appears in main menu
2. Entering opens the ROMs directory
3. D-pad navigation works through file list
4. A button enters folders
5. B button navigates up and eventually exits to main menu
6. Y button opens context menu
7. Context menu shows correct options based on file type
8. Copy/Cut/Paste flow works (clipboard footer updates)
9. Delete confirmation modal works
10. Rename and New Folder input modals work
11. Text file viewer opens for .txt/.md/.xml files
12. Extract modal appears for .zip files
13. L/R page up/down works in file list and viewer
14. Empty folder shows "This folder is empty"
15. Error messages display correctly

- [ ] **Step 2: Fix any issues found during testing**

- [ ] **Step 3: Commit fixes**

```bash
git add -A
git commit -m "Fix file explorer issues from manual testing"
```

---

## Chunk 2: Touch Support and Polish

### Task 7: Add Touch Click Handling in app.py

**Files:**
- Modify: `src/app.py`

- [ ] **Step 1: Add touch click handling for file explorer**

In `_handle_click()` (around line 2524), add handling for file explorer rects:

```python
elif self.state.mode == "file_explorer":
    fe = self.state.file_explorer
    rects = self.state.ui_rects

    # Error OK button
    if fe.error_message:
        error_ok = rects.get("error_ok")
        if error_ok and error_ok.collidepoint(x, y):
            fe.error_message = ""
            self._refresh_file_explorer()
        return

    # Delete modal buttons
    if fe.delete_modal_open:
        if rects.get("delete_yes") and rects["delete_yes"].collidepoint(x, y):
            fe.delete_highlighted = 0
            self._handle_file_explorer_select()
        elif rects.get("delete_no") and rects["delete_no"].collidepoint(x, y):
            fe.delete_highlighted = 1
            self._handle_file_explorer_select()
        return

    # Extract modal options
    if fe.extract_modal_open:
        for i, opt_rect in enumerate(rects.get("extract_options", [])):
            if opt_rect.collidepoint(x, y):
                fe.extract_highlighted = i
                self._handle_file_explorer_select()
                return
        return

    # Context menu items
    if fe.context_menu_open:
        for i, item_rect in enumerate(rects.get("context_menu_items", [])):
            if item_rect.collidepoint(x, y):
                fe.context_menu_highlighted = i
                self._handle_file_explorer_context_action()
                return
        # Click outside closes context menu
        fe.context_menu_open = False
        return

    # Viewer close
    if fe.viewer_open:
        viewer_close = rects.get("viewer_close")
        if viewer_close and viewer_close.collidepoint(x, y):
            fe.viewer_open = False
        return

    # Keyboard char rects
    if fe.input_modal_open:
        for char_rect, idx, char in rects.get("kb_char_rects", []):
            if char_rect.collidepoint(x, y):
                fe.kb_selected_index = idx
                self._handle_file_explorer_kb_select()
                return
        return

    # Touch action buttons
    if rects.get("touch_back") and rects["touch_back"].collidepoint(x, y):
        self._handle_file_explorer_back()
        return
    if rects.get("touch_open") and rects["touch_open"].collidepoint(x, y):
        self._handle_file_explorer_select()
        return
    if rects.get("touch_actions") and rects["touch_actions"].collidepoint(x, y):
        self._open_file_explorer_context_menu()
        return
    if rects.get("touch_paste") and rects["touch_paste"].collidepoint(x, y):
        self._file_explorer_paste()
        return
    if rects.get("touch_deselect") and rects["touch_deselect"].collidepoint(x, y):
        fe.selected = set()
        return

    # File list item taps (double-tap to open)
    import time as _time
    item_rects = rects.get("item_rects", [])
    for i, rect_item in enumerate(item_rects):
        if rect_item.collidepoint(x, y):
            now = _time.time()
            if (
                fe.highlighted == i
                and hasattr(self, "_fe_last_tap_time")
                and now - self._fe_last_tap_time < 0.4
            ):
                # Double-tap — open/enter
                self._handle_file_explorer_select()
                self._fe_last_tap_time = 0
            else:
                fe.highlighted = i
                self._fe_last_tap_time = now
            return
```

- [ ] **Step 2: Add long-press handling**

In the touch/long-press handler section of app.py, add:

```python
elif self.state.mode == "file_explorer":
    fe = self.state.file_explorer
    if not fe.context_menu_open and not fe.viewer_open:
        # Check if long press is on a file list item
        item_rects = self.state.ui_rects.get("item_rects", [])
        for i, rect_item in enumerate(item_rects):
            if rect_item.collidepoint(x, y):
                fe.highlighted = i
                self._open_file_explorer_context_menu()
                return
```

- [ ] **Step 3: Commit**

```bash
git add src/app.py
git commit -m "Add file explorer touch and long-press support"
```

---

### Task 8: Store UI Rects for Touch

**Files:**
- Modify: `src/app.py`

- [ ] **Step 1: Store file explorer rects from render**

In the main render loop of app.py, where `screen_manager.render()` returns rects, make sure the file explorer rects are stored on `self.state.ui_rects` so click handlers can access them. This may already work if the screen manager returns rects into the main rects dict. Verify by checking how other screens store rects.

Look at the render loop — it typically does:
```python
rects = self.screen_manager.render(screen, self.state)
# Store for click handling
self.state.ui_rects = rects
```

If the screen manager's `render()` already returns the file explorer rects (from Task 4 Step 2), this should work automatically. Verify and fix if needed.

- [ ] **Step 2: Commit if changes needed**

```bash
git add src/app.py
git commit -m "Ensure file explorer rects available for touch handling"
```

---

### Task 9: Final Integration Testing

- [ ] **Step 1: Test complete flow**

```bash
make run
```

Full test checklist:
1. Navigate to File Explorer from main menu
2. Browse into folders, back out
3. Select files with X, see checkmarks + footer update
4. Copy via context menu → navigate → paste with X
5. Cut via context menu → navigate → paste with X
6. Delete single file → confirm → file removed
7. Delete multiple selected files → confirm
8. Rename a file via context menu → type new name → confirm
9. Create New Folder via context menu → type name → confirm
10. View a .txt file → scroll with D-pad → close with B
11. Extract a .zip → choose subfolder or current folder
12. Test on empty folder (empty state message, only New Folder in context menu)
13. Touch: tap to highlight, double-tap to open, long-press for context menu
14. Touch buttons: Open, Actions, Back, Paste, Deselect all work
15. L/R shoulder for page navigation
16. Error handling: try to delete a protected file, see error modal

- [ ] **Step 2: Fix issues**

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "File explorer: final fixes and polish"
```
