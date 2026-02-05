"""
Systems settings screen - List all systems with their config status.
"""

import pygame
from typing import List, Dict, Any, Tuple, Optional, Set

from ui.theme import Theme, default_theme
from ui.templates.list_screen import ListScreenTemplate


class SystemsSettingsScreen:
    """
    Systems settings screen.

    Displays all configured systems with their
    current settings status (hidden, custom folder, etc.)
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.template = ListScreenTemplate(theme)

    def render(
        self,
        screen: pygame.Surface,
        highlighted: int,
        systems: List[Dict[str, Any]],
        hidden_systems: Set[str] = None,
    ) -> Tuple[Optional[pygame.Rect], List[pygame.Rect], int]:
        """
        Render the systems settings screen.

        Args:
            screen: Surface to render to
            highlighted: Currently highlighted index
            systems: List of system configurations
            hidden_systems: Set of hidden system names

        Returns:
            Tuple of (back_button_rect, item_rects, scroll_offset)
        """
        hidden_systems = hidden_systems or set()

        # Build items with status
        items = []
        for system in systems:
            name = system.get("name", "Unknown System")

            # Build status string
            status_parts = []
            if name in hidden_systems:
                status_parts.append("Hidden")

            custom_folder = system.get("custom_folder")
            if custom_folder:
                status_parts.append("Custom Folder")

            status = ", ".join(status_parts) if status_parts else ""
            items.append((name, status))

        # Show message if no systems
        if not items:
            items = [("No systems configured", "")]

        return self.template.render(
            screen,
            title="Systems Settings",
            items=items,
            highlighted=highlighted,
            selected=set(),
            show_back=True,
            item_height=40,
            get_label=lambda x: x[0] if isinstance(x, tuple) else x,
            get_secondary=lambda x: x[1] if isinstance(x, tuple) else None,
            item_spacing=8,
        )

    def get_selected_system_index(
        self, highlighted: int, systems: List[Dict[str, Any]]
    ) -> Optional[int]:
        """
        Get the system index at the highlighted position.

        Args:
            highlighted: Currently highlighted index
            systems: List of system configurations

        Returns:
            System index or None if invalid
        """
        if 0 <= highlighted < len(systems):
            return highlighted
        return None


# Default instance
systems_settings_screen = SystemsSettingsScreen()
