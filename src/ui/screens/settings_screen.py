"""
Settings screen - Application settings menu.
"""

import pygame
from typing import List, Dict, Any, Tuple, Optional, Set

from ui.theme import Theme, default_theme
from ui.templates.list_screen import ListScreenTemplate


class SettingsScreen:
    """
    Settings screen.

    Displays application settings with toggles
    and navigation options.
    """

    # Settings menu items
    SETTINGS_ITEMS = [
        "Select Archive Json",
        "Work Directory",
        "ROMs Directory",
        "NSZ Keys",
        "Remap Controller",
        "Add Systems",
        "Systems Settings",
        "--- VIEW OPTIONS ---",  # Divider
        "Enable Box-art Display",
        "View Type",
        "USA Games Only"
    ]

    DIVIDER_INDEX = 7

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.template = ListScreenTemplate(theme)

    def render(
        self,
        screen: pygame.Surface,
        highlighted: int,
        settings: Dict[str, Any]
    ) -> Tuple[Optional[pygame.Rect], List[pygame.Rect], int]:
        """
        Render the settings screen.

        Args:
            screen: Surface to render to
            highlighted: Currently highlighted index
            settings: Current settings dictionary

        Returns:
            Tuple of (back_button_rect, item_rects, scroll_offset)
        """
        # Build items with current values
        items = []
        for i, item in enumerate(self.SETTINGS_ITEMS):
            if i == self.DIVIDER_INDEX:
                items.append(item)
            elif item == "Enable Box-art Display":
                value = "ON" if settings.get("enable_boxart", True) else "OFF"
                items.append((item, value))
            elif item == "View Type":
                value = settings.get("view_type", "grid").capitalize()
                items.append((item, value))
            elif item == "USA Games Only":
                value = "ON" if settings.get("usa_only", False) else "OFF"
                items.append((item, value))
            elif item == "Work Directory":
                path = settings.get("work_dir", "")
                short_path = self._shorten_path(path)
                items.append((item, short_path))
            elif item == "ROMs Directory":
                path = settings.get("roms_dir", "")
                short_path = self._shorten_path(path)
                items.append((item, short_path))
            elif item == "NSZ Keys":
                path = settings.get("nsz_keys_path", "")
                value = "Set" if path else "Not Set"
                items.append((item, value))
            elif item == "Select Archive Json":
                path = settings.get("archive_json_path", "")
                value = "Set" if path else "Not Set"
                items.append((item, value))
            else:
                items.append((item, ""))

        return self.template.render(
            screen,
            title="Settings",
            items=items,
            highlighted=highlighted,
            selected=set(),
            show_back=True,
            item_height=50,
            get_label=lambda x: x[0] if isinstance(x, tuple) else x,
            get_secondary=lambda x: x[1] if isinstance(x, tuple) else None,
            divider_indices={self.DIVIDER_INDEX}
        )

    def _shorten_path(self, path: str, max_length: int = 25) -> str:
        """Shorten a path for display."""
        if not path:
            return "Not Set"
        if len(path) <= max_length:
            return path

        # Show last parts of path
        parts = path.replace("\\", "/").split("/")
        result = ""
        for part in reversed(parts):
            if len(result) + len(part) + 1 <= max_length - 3:
                result = "/" + part + result if result else part
            else:
                break

        return "..." + result if result else "..." + path[-max_length+3:]

    def get_setting_action(self, index: int) -> str:
        """
        Get the action for a settings item.

        Args:
            index: Selected index

        Returns:
            Action string
        """
        if index == self.DIVIDER_INDEX:
            return "divider"

        if index < len(self.SETTINGS_ITEMS):
            item = self.SETTINGS_ITEMS[index]
            actions = {
                "Select Archive Json": "select_archive_json",
                "Work Directory": "select_work_dir",
                "ROMs Directory": "select_roms_dir",
                "NSZ Keys": "select_nsz_keys",
                "Remap Controller": "remap_controller",
                "Add Systems": "add_systems",
                "Systems Settings": "systems_settings",
                "Enable Box-art Display": "toggle_boxart",
                "View Type": "toggle_view_type",
                "USA Games Only": "toggle_usa_only"
            }
            return actions.get(item, "unknown")

        return "unknown"


# Default instance
settings_screen = SettingsScreen()
