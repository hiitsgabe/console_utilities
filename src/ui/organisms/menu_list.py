"""
Menu list organism - Scrollable list of menu items.
"""

import pygame
from typing import List, Set, Tuple, Optional, Any, Callable

from ui.theme import Theme, default_theme
from ui.molecules.menu_item import MenuItem


class MenuList:
    """
    Menu list organism.

    Displays a scrollable list of menu items with
    selection and highlight support.
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.menu_item = MenuItem(theme)

    def render(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        items: List[Any],
        highlighted: int,
        selected: Set[int],
        item_height: int = 50,
        get_label: Optional[Callable[[Any], str]] = None,
        get_thumbnail: Optional[Callable[[Any], pygame.Surface]] = None,
        get_secondary: Optional[Callable[[Any], str]] = None,
        show_checkbox: bool = False,
        divider_indices: Optional[Set[int]] = None
    ) -> Tuple[List[pygame.Rect], int]:
        """
        Render a menu list.

        Args:
            screen: Surface to render to
            rect: List area rectangle
            items: List of items
            highlighted: Currently highlighted index
            selected: Set of selected indices
            item_height: Height of each item
            get_label: Function to get label from item
            get_thumbnail: Function to get thumbnail from item
            get_secondary: Function to get secondary text
            show_checkbox: Show selection checkboxes
            divider_indices: Indices that are dividers

        Returns:
            Tuple of (list of item rects, scroll offset)
        """
        if not items:
            return [], 0

        if get_label is None:
            get_label = self._default_get_label

        if divider_indices is None:
            divider_indices = set()

        # Calculate visible range
        visible_count = rect.height // item_height
        scroll_offset = self._calculate_scroll(
            highlighted, len(items), visible_count
        )

        # Render visible items
        item_rects = []
        y = rect.top

        for i in range(scroll_offset, min(scroll_offset + visible_count + 1, len(items))):
            if y >= rect.bottom:
                break

            item = items[i]
            item_rect = pygame.Rect(
                rect.left,
                y,
                rect.width,
                item_height
            )

            # Check if this is a divider
            if i in divider_indices:
                label = get_label(item)
                self.menu_item.render_divider(screen, item_rect, label)
            else:
                # Get item properties
                label = get_label(item)
                thumbnail = get_thumbnail(item) if get_thumbnail else None
                secondary = get_secondary(item) if get_secondary else None

                self.menu_item.render(
                    screen, item_rect, label,
                    selected=(i in selected),
                    highlighted=(i == highlighted),
                    thumbnail=thumbnail,
                    secondary_text=secondary,
                    show_checkbox=show_checkbox
                )

            item_rects.append(item_rect)
            y += item_height

        # Draw scroll indicators if needed
        self._draw_scroll_indicators(
            screen, rect,
            scroll_offset, len(items), visible_count
        )

        return item_rects, scroll_offset

    def _default_get_label(self, item: Any) -> str:
        """Default label extraction."""
        if isinstance(item, dict):
            return item.get('name', item.get('filename', str(item)))
        return str(item)

    def _calculate_scroll(
        self,
        highlighted: int,
        total_items: int,
        visible_count: int
    ) -> int:
        """Calculate scroll offset to keep highlighted item visible."""
        if total_items <= visible_count:
            return 0

        # Keep highlighted item in view with some context
        context = 2
        min_scroll = max(0, highlighted - visible_count + context + 1)
        max_scroll = max(0, min(highlighted - context, total_items - visible_count))

        return max(min_scroll, min(max_scroll, min_scroll))

    def _draw_scroll_indicators(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        scroll_offset: int,
        total_items: int,
        visible_count: int
    ) -> None:
        """Draw scroll indicators if list is scrollable."""
        if total_items <= visible_count:
            return

        indicator_size = 8
        indicator_x = rect.right - indicator_size - 4

        # Up indicator
        if scroll_offset > 0:
            points = [
                (indicator_x, rect.top + indicator_size),
                (indicator_x + indicator_size // 2, rect.top + 2),
                (indicator_x + indicator_size, rect.top + indicator_size)
            ]
            pygame.draw.polygon(screen, self.theme.text_secondary, points)

        # Down indicator
        if scroll_offset + visible_count < total_items:
            points = [
                (indicator_x, rect.bottom - indicator_size),
                (indicator_x + indicator_size // 2, rect.bottom - 2),
                (indicator_x + indicator_size, rect.bottom - indicator_size)
            ]
            pygame.draw.polygon(screen, self.theme.text_secondary, points)

        # Draw scrollbar
        scrollbar_height = rect.height * visible_count // total_items
        scrollbar_y = rect.top + (rect.height - scrollbar_height) * scroll_offset // (total_items - visible_count)
        scrollbar_rect = pygame.Rect(
            rect.right - 4,
            scrollbar_y,
            3,
            scrollbar_height
        )
        pygame.draw.rect(
            screen,
            self.theme.surface_hover,
            scrollbar_rect,
            border_radius=2
        )


# Default instance
menu_list = MenuList()
