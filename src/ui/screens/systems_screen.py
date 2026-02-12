"""
Systems screen - Root menu and systems list submenu.
"""

import pygame
from typing import List, Dict, Any, Tuple, Optional, Set

from ui.theme import Theme, default_theme
from ui.templates.list_screen import ListScreenTemplate

# All possible root menu entries and their action keys (in order)
_ALL_ROOT_ENTRIES = [
    ("Backup Games", "systems_list"),
    ("PortMaster (beta)", "portmaster"),
    ("Utils", "utils"),
    ("Settings", "settings"),
    ("Credits", "credits"),
]


def _build_root_menu(settings: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """Return (labels, actions) for the root menu based on settings."""
    from constants import BUILD_TARGET

    labels = []
    actions = []
    for label, action in _ALL_ROOT_ENTRIES:
        if action == "portmaster":
            if BUILD_TARGET not in ("pygame", "source") or not settings.get("portmaster_enabled", False):
                continue
        labels.append(label)
        actions.append(action)
    return labels, actions


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
        settings: Dict[str, Any] = None,
        extra_items: List[str] = None,
    ) -> Tuple[Optional[pygame.Rect], List[pygame.Rect], int]:
        """
        Render the root menu screen.

        Args:
            screen: Surface to render to
            systems: List of system configurations (unused in root)
            highlighted: Currently highlighted index
            settings: Current settings dictionary
            extra_items: Override menu items

        Returns:
            Tuple of (back_button_rect, item_rects, scroll_offset)
        """
        if extra_items is not None:
            items = extra_items
        else:
            items, _ = _build_root_menu(settings or {})

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
            title="Backup Games",
            items=items,
            highlighted=highlighted,
            selected=set(),
            show_back=True,
            item_height=40,
            get_label=lambda x: x,
            item_spacing=8,
        )

    def get_root_menu_action(self, index: int, settings: Dict[str, Any] = None) -> str:
        """
        Get the action for a root menu selection.

        Args:
            index: Selected index
            settings: Current settings dictionary

        Returns:
            Action string: "systems_list", "portmaster", "utils", "settings", "credits"
        """
        _, actions = _build_root_menu(settings or {})
        if 0 <= index < len(actions):
            return actions[index]
        return "unknown"

    def get_root_menu_count(self, settings: Dict[str, Any] = None) -> int:
        """Get number of root menu items."""
        labels, _ = _build_root_menu(settings or {})
        return len(labels)

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
