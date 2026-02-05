"""
System settings screen - Individual system settings.
"""

import pygame
from typing import List, Dict, Any, Tuple, Optional, Set

from ui.theme import Theme, default_theme
from ui.templates.list_screen import ListScreenTemplate


class SystemSettingsScreen:
    """
    Individual system settings screen.

    Displays settings for a single system:
    - Hide/Show system
    - Set custom folder
    """

    SETTINGS_ITEMS = ["Hide System", "Set Custom Folder"]

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.template = ListScreenTemplate(theme)

    def render(
        self,
        screen: pygame.Surface,
        highlighted: int,
        system: Dict[str, Any],
        is_hidden: bool = False,
    ) -> Tuple[Optional[pygame.Rect], List[pygame.Rect], int]:
        """
        Render the system settings screen.

        Args:
            screen: Surface to render to
            highlighted: Currently highlighted index
            system: System configuration dict
            is_hidden: Whether the system is currently hidden

        Returns:
            Tuple of (back_button_rect, item_rects, scroll_offset)
        """
        system_name = system.get("name", "Unknown System")
        custom_folder = system.get("custom_folder", "")

        # Build items with current values
        items = []
        for item in self.SETTINGS_ITEMS:
            if item == "Hide System":
                value = "ON" if is_hidden else "OFF"
                items.append((item, value))
            elif item == "Set Custom Folder":
                value = (
                    self._shorten_path(custom_folder) if custom_folder else "Default"
                )
                items.append((item, value))

        return self.template.render(
            screen,
            title=f"{system_name} Settings",
            items=items,
            highlighted=highlighted,
            selected=set(),
            show_back=True,
            item_height=40,
            get_label=lambda x: x[0] if isinstance(x, tuple) else x,
            get_secondary=lambda x: x[1] if isinstance(x, tuple) else None,
            item_spacing=8,
        )

    def _shorten_path(self, path: str, max_length: int = 25) -> str:
        """Shorten a path for display."""
        if not path:
            return ""
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

        return "..." + result if result else "..." + path[-max_length + 3 :]

    def get_setting_action(self, index: int) -> str:
        """
        Get the action for a settings item.

        Args:
            index: Selected index

        Returns:
            Action string
        """
        if index < len(self.SETTINGS_ITEMS):
            item = self.SETTINGS_ITEMS[index]
            actions = {
                "Hide System": "toggle_hide_system",
                "Set Custom Folder": "set_custom_folder",
            }
            return actions.get(item, "unknown")

        return "unknown"


# Default instance
system_settings_screen = SystemSettingsScreen()
