"""
Systems screen - Root menu and systems list submenu.
"""

import pygame
from typing import List, Dict, Any, Tuple, Optional, Set

from ui.theme import Theme, default_theme
from ui.templates.list_screen import ListScreenTemplate

# Root menu items
ROOT_MENU_ITEMS = ["Systems", "Utils", "Settings", "Credits"]


class SystemsScreen:
    """
    Systems screen.

    Displays the root menu (Systems/Utils/Settings/Credits)
    and the systems list submenu.
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
        Render the root menu screen.

        Args:
            screen: Surface to render to
            systems: List of system configurations (unused in root)
            highlighted: Currently highlighted index
            extra_items: Override menu items

        Returns:
            Tuple of (back_button_rect, item_rects, scroll_offset)
        """
        items = extra_items if extra_items is not None else ROOT_MENU_ITEMS

        return self.template.render(
            screen,
            title="Console Utils",
            items=items,
            highlighted=highlighted,
            selected=set(),
            show_back=False,
            item_height=40,
            get_label=lambda x: x,
            item_spacing=8,
            rainbow_title=True,
            center_title=True,
        )

    def render_systems_list(
        self,
        screen: pygame.Surface,
        systems: List[Dict[str, Any]],
        highlighted: int,
    ) -> Tuple[Optional[pygame.Rect], List[pygame.Rect], int]:
        """
        Render the systems list submenu.

        Args:
            screen: Surface to render to
            systems: List of system configurations
            highlighted: Currently highlighted index

        Returns:
            Tuple of (back_button_rect, item_rects, scroll_offset)
        """
        items = [s["name"] for s in systems]

        return self.template.render(
            screen,
            title="Systems",
            items=items,
            highlighted=highlighted,
            selected=set(),
            show_back=True,
            item_height=40,
            get_label=lambda x: x,
            item_spacing=8,
        )

    def get_root_menu_action(self, index: int) -> str:
        """
        Get the action for a root menu selection.

        Args:
            index: Selected index

        Returns:
            Action string: "systems_list", "utils", "settings", "credits"
        """
        actions = ["systems_list", "utils", "settings", "credits"]
        if 0 <= index < len(actions):
            return actions[index]
        return "unknown"

    def get_root_menu_count(self) -> int:
        """Get number of root menu items."""
        return len(ROOT_MENU_ITEMS)

    def get_selection_type(self, index: int, systems_count: int) -> Tuple[str, int]:
        """
        Determine what type of item was selected in systems list.

        Args:
            index: Selected index
            systems_count: Number of systems

        Returns:
            Tuple of (type, adjusted_index)
        """
        if index < systems_count:
            return ("system", index)
        return ("unknown", 0)


# Default instance
systems_screen = SystemsScreen()
