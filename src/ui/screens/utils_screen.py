"""
Utils screen - Utility functions menu.
"""

import pygame
from typing import List, Tuple, Optional, Set

from ui.theme import Theme, default_theme
from ui.templates.list_screen import ListScreenTemplate


class UtilsScreen:
    """
    Utils screen.

    Displays utility functions like direct download
    and NSZ conversion.
    """

    UTILS_ITEMS = ["Download from URL", "NSZ to NSP Converter"]

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.template = ListScreenTemplate(theme)

    def render(
        self, screen: pygame.Surface, highlighted: int
    ) -> Tuple[Optional[pygame.Rect], List[pygame.Rect], int]:
        """
        Render the utils screen.

        Args:
            screen: Surface to render to
            highlighted: Currently highlighted index

        Returns:
            Tuple of (back_button_rect, item_rects, scroll_offset)
        """
        return self.template.render(
            screen,
            title="Utilities",
            items=self.UTILS_ITEMS,
            highlighted=highlighted,
            selected=set(),
            show_back=True,
            item_height=40,
            item_spacing=8,
        )

    def get_util_action(self, index: int) -> str:
        """
        Get the action for a utils item.

        Args:
            index: Selected index

        Returns:
            Action string
        """
        actions = {0: "download_url", 1: "nsz_converter"}
        return actions.get(index, "unknown")


# Default instance
utils_screen = UtilsScreen()
