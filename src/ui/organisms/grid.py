"""
Grid organism - Grid layout of thumbnails.
"""

import pygame
from typing import List, Set, Tuple, Optional, Any, Callable

from ui.theme import Theme, default_theme
from ui.molecules.thumbnail import Thumbnail


class Grid:
    """
    Grid organism.

    Displays items in a grid layout with thumbnails
    and labels.
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.thumbnail = Thumbnail(theme)

    def render(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        items: List[Any],
        highlighted: int,
        selected: Set[int],
        columns: int = 4,
        cell_size: Optional[Tuple[int, int]] = None,
        get_label: Optional[Callable[[Any], str]] = None,
        get_image: Optional[Callable[[Any], pygame.Surface]] = None,
        get_placeholder: Optional[Callable[[Any], str]] = None
    ) -> Tuple[List[pygame.Rect], int]:
        """
        Render a grid of items.

        Args:
            screen: Surface to render to
            rect: Grid area rectangle
            items: List of items
            highlighted: Currently highlighted index
            selected: Set of selected indices
            columns: Number of columns
            cell_size: Size of each cell (width, height)
            get_label: Function to get label from item
            get_image: Function to get thumbnail from item
            get_placeholder: Function to get placeholder text

        Returns:
            Tuple of (list of item rects, scroll offset)
        """
        if not items:
            return [], 0

        if get_label is None:
            get_label = self._default_get_label
        if get_placeholder is None:
            get_placeholder = lambda x: self.thumbnail.get_placeholder_initials(
                get_label(x)
            )

        # Calculate cell dimensions
        if cell_size is None:
            padding = self.theme.padding_sm
            available_width = rect.width - padding * 2
            cell_width = (available_width - padding * (columns - 1)) // columns
            cell_height = cell_width + 30  # Extra space for label
            cell_size = (cell_width, cell_height)
        else:
            cell_width, cell_height = cell_size
            padding = self.theme.padding_sm

        # Calculate rows
        rows = (len(items) + columns - 1) // columns
        visible_rows = rect.height // cell_height

        # Calculate scroll offset
        highlighted_row = highlighted // columns
        scroll_row = self._calculate_scroll_row(
            highlighted_row, rows, visible_rows
        )

        # Render visible cells
        item_rects = []
        start_idx = scroll_row * columns

        y = rect.top + padding
        for row in range(visible_rows + 1):
            if y >= rect.bottom - padding:
                break

            x = rect.left + padding
            for col in range(columns):
                idx = start_idx + row * columns + col
                if idx >= len(items):
                    break

                item = items[idx]
                cell_rect = pygame.Rect(x, y, cell_width, cell_height)

                # Get item properties
                label = get_label(item)
                image = get_image(item) if get_image else None
                placeholder = get_placeholder(item)

                # Render thumbnail with label
                self.thumbnail.render_with_label(
                    screen, cell_rect,
                    label=label,
                    image=image,
                    placeholder_text=placeholder,
                    selected=(idx in selected),
                    highlighted=(idx == highlighted)
                )

                item_rects.append(cell_rect)
                x += cell_width + padding

            y += cell_height + padding

        # Draw scroll indicators
        self._draw_scroll_indicators(
            screen, rect,
            scroll_row, rows, visible_rows
        )

        return item_rects, scroll_row * columns

    def _default_get_label(self, item: Any) -> str:
        """Default label extraction."""
        if isinstance(item, dict):
            name = item.get('name', item.get('filename', str(item)))
            # Remove file extension for display
            if '.' in name:
                name = name.rsplit('.', 1)[0]
            return name
        return str(item)

    def _calculate_scroll_row(
        self,
        highlighted_row: int,
        total_rows: int,
        visible_rows: int
    ) -> int:
        """Calculate scroll row to keep highlighted row visible."""
        if total_rows <= visible_rows:
            return 0

        context = 1
        min_scroll = max(0, highlighted_row - visible_rows + context + 1)
        max_scroll = max(0, min(highlighted_row - context, total_rows - visible_rows))

        return max(min_scroll, min(max_scroll, min_scroll))

    def _draw_scroll_indicators(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        scroll_row: int,
        total_rows: int,
        visible_rows: int
    ) -> None:
        """Draw scroll indicators."""
        if total_rows <= visible_rows:
            return

        indicator_size = 8
        center_x = rect.centerx

        # Up indicator
        if scroll_row > 0:
            points = [
                (center_x - indicator_size, rect.top + indicator_size),
                (center_x, rect.top + 2),
                (center_x + indicator_size, rect.top + indicator_size)
            ]
            pygame.draw.polygon(screen, self.theme.text_secondary, points)

        # Down indicator
        if scroll_row + visible_rows < total_rows:
            points = [
                (center_x - indicator_size, rect.bottom - indicator_size),
                (center_x, rect.bottom - 2),
                (center_x + indicator_size, rect.bottom - indicator_size)
            ]
            pygame.draw.polygon(screen, self.theme.text_secondary, points)


# Default instance
grid = Grid()
