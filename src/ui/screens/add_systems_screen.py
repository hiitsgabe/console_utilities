"""
Add systems screen - Select systems to add from available list.
"""

import pygame
from typing import List, Dict, Any, Tuple, Optional

from ui.theme import Theme, default_theme
from ui.templates.list_screen import ListScreenTemplate


class AddSystemsScreen:
    """
    Add systems screen.

    Displays available systems that can be added
    to the user's system list.
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.template = ListScreenTemplate(theme)

    def render(
        self,
        screen: pygame.Surface,
        highlighted: int,
        available_systems: List[Dict[str, Any]],
    ) -> Tuple[Optional[pygame.Rect], List[pygame.Rect], int]:
        """
        Render the add systems screen.

        Args:
            screen: Surface to render to
            highlighted: Currently highlighted index
            available_systems: List of available system configs

        Returns:
            Tuple of (back_button_rect, item_rects, scroll_offset)
        """
        # Build items from available systems
        items = []
        for system in available_systems:
            name = system.get("name", "Unknown System")
            items.append(name)

        # Show message if no systems available
        if not items:
            items = ["No additional systems available"]

        return self.template.render(
            screen,
            title="Add Systems",
            items=items,
            highlighted=highlighted,
            selected=set(),
            show_back=True,
            item_height=40,
            item_spacing=8,
        )

    def get_selected_system(
        self, index: int, available_systems: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Get the system config at the given index.

        Args:
            index: Selected index
            available_systems: List of available system configs

        Returns:
            System config dict or None if invalid
        """
        if 0 <= index < len(available_systems):
            return available_systems[index]
        return None


# Default instance
add_systems_screen = AddSystemsScreen()
