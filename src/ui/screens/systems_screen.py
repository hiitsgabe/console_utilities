"""
Systems screen - Main menu showing available systems.
"""

import pygame
from typing import List, Dict, Any, Tuple, Optional, Set

from ui.theme import Theme, default_theme
from ui.templates.list_screen import ListScreenTemplate


class SystemsScreen:
    """
    Systems screen.

    Displays the main menu with available game systems,
    utilities, settings, and credits options.
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.template = ListScreenTemplate(theme)

    def render(
        self,
        screen: pygame.Surface,
        systems: List[Dict[str, Any]],
        highlighted: int,
        extra_items: List[str] = None,
    ) -> Tuple[Optional[pygame.Rect], List[pygame.Rect], int]:
        """
        Render the systems screen.

        Args:
            screen: Surface to render to
            systems: List of system configurations
            highlighted: Currently highlighted index
            extra_items: Extra menu items (e.g., ["Utils", "Settings", "Credits"])

        Returns:
            Tuple of (back_button_rect, item_rects, scroll_offset)
        """
        if extra_items is None:
            extra_items = ["Utils", "Settings", "Credits"]

        # Build items list: systems + extra items
        items = [s["name"] for s in systems] + extra_items

        return self.template.render(
            screen,
            title="Console Utils",
            items=items,
            highlighted=highlighted,
            selected=set(),
            show_back=False,
            item_height=40,
            get_label=lambda x: x if isinstance(x, str) else x.get("name", str(x)),
            item_spacing=8,
            rainbow_title=True,
            center_title=True,
        )

    def get_selection_type(self, index: int, systems_count: int) -> Tuple[str, int]:
        """
        Determine what type of item was selected.

        Args:
            index: Selected index
            systems_count: Number of systems

        Returns:
            Tuple of (type, adjusted_index)
            type is one of: "system", "utils", "settings", "credits"
        """
        if index < systems_count:
            return ("system", index)
        elif index == systems_count:
            return ("utils", 0)
        elif index == systems_count + 1:
            return ("settings", 0)
        else:
            return ("credits", 0)


# Default instance
systems_screen = SystemsScreen()
