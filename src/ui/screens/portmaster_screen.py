"""
PortMaster screen - Display available ports from PortMaster.
"""

import pygame
from typing import List, Dict, Any, Tuple, Optional, Callable

from ui.theme import Theme, default_theme
from ui.templates.list_screen import ListScreenTemplate
from ui.atoms.text import Text
from ui.molecules.thumbnail import Thumbnail


class PortMasterScreen:
    """
    PortMaster screen.

    Displays available ports in list view with genre filtering.
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.list_template = ListScreenTemplate(theme)
        self.text = Text(theme)
        self.thumbnail = Thumbnail(theme)

    def render(
        self,
        screen: pygame.Surface,
        ports: List[Dict[str, Any]],
        highlighted: int,
        genre: str = "All",
        search_query: str = "",
        get_thumbnail: Optional[Callable[[Any], pygame.Surface]] = None,
        text_scroll_offset: int = 0,
    ) -> Tuple[Optional[pygame.Rect], List[pygame.Rect], int]:
        """
        Render the PortMaster screen.

        Args:
            screen: Surface to render to
            ports: List of port dicts
            highlighted: Currently highlighted index
            genre: Current genre filter
            search_query: Current search query
            get_thumbnail: Function to get thumbnail for a port
            text_scroll_offset: Horizontal text scroll offset

        Returns:
            Tuple of (back_rect, item_rects, scroll_offset)
        """
        title = "PortMaster"
        subtitle_parts = []
        if genre and genre != "All":
            subtitle_parts.append(f"Genre: {genre}")
        if search_query:
            subtitle_parts.append(f"Search: {search_query}")
        subtitle = " | ".join(subtitle_parts) if subtitle_parts else None

        back_rect, item_rects, scroll_offset = self.list_template.render(
            screen,
            title=title,
            items=ports,
            highlighted=highlighted,
            selected=set(),
            show_back=True,
            subtitle=subtitle,
            item_height=50,
            get_label=self._get_port_label,
            get_thumbnail=get_thumbnail,
            text_scroll_offset=text_scroll_offset,
        )

        return back_rect, item_rects, scroll_offset

    def _get_port_label(self, port: Any) -> str:
        """Extract display label from port."""
        if isinstance(port, dict):
            title = port.get("title", port.get("name", str(port)))
            if port.get("rtr"):
                title = f"{title} [RTR]"
            return title
        return str(port)


# Default instance
portmaster_screen = PortMasterScreen()
