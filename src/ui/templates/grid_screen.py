"""
Grid screen template - Layout for grid-based screens.
"""

import pygame
from typing import List, Set, Tuple, Optional, Any, Callable

from ui.theme import Theme, default_theme
from ui.organisms.header import Header
from ui.organisms.grid import Grid


class GridScreenTemplate:
    """
    Grid screen template.

    Combines header and grid into a complete
    grid-based screen layout.
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.header = Header(theme)
        self.grid = Grid(theme)

    def render(
        self,
        screen: pygame.Surface,
        title: str,
        items: List[Any],
        highlighted: int,
        selected: Set[int],
        show_back: bool = True,
        subtitle: Optional[str] = None,
        columns: int = 4,
        get_label: Optional[Callable[[Any], str]] = None,
        get_image: Optional[Callable[[Any], pygame.Surface]] = None,
        get_placeholder: Optional[Callable[[Any], str]] = None,
        footer_height: int = 0
    ) -> Tuple[Optional[pygame.Rect], List[pygame.Rect], int]:
        """
        Render a grid screen.

        Args:
            screen: Surface to render to
            title: Screen title
            items: List of items
            highlighted: Highlighted index
            selected: Selected indices
            show_back: Show back button
            subtitle: Optional subtitle
            columns: Number of grid columns
            get_label: Label extraction function
            get_image: Image extraction function
            get_placeholder: Placeholder text function
            footer_height: Reserved footer space

        Returns:
            Tuple of (back_button_rect, item_rects, scroll_offset)
        """
        # Draw background
        screen.fill(self.theme.background)

        # Draw header
        header_height = 60
        header_rect, back_button_rect = self.header.render(
            screen, title,
            show_back=show_back,
            subtitle=subtitle
        )

        # Calculate content area
        content_rect = pygame.Rect(
            self.theme.padding_sm,
            header_height + self.theme.padding_sm,
            screen.get_width() - self.theme.padding_sm * 2,
            screen.get_height() - header_height - self.theme.padding_sm * 2 - footer_height
        )

        # Draw grid
        item_rects, scroll_offset = self.grid.render(
            screen, content_rect,
            items, highlighted, selected,
            columns=columns,
            get_label=get_label,
            get_image=get_image,
            get_placeholder=get_placeholder
        )

        return back_button_rect, item_rects, scroll_offset

    def render_with_buttons(
        self,
        screen: pygame.Surface,
        title: str,
        items: List[Any],
        highlighted: int,
        selected: Set[int],
        button_labels: List[str],
        show_back: bool = True,
        **kwargs
    ) -> Tuple[Optional[pygame.Rect], List[pygame.Rect], int, List[pygame.Rect]]:
        """
        Render a grid screen with bottom action buttons.

        Args:
            screen: Surface to render to
            title: Screen title
            items: List of items
            highlighted: Highlighted index
            selected: Selected indices
            button_labels: Labels for bottom buttons
            show_back: Show back button
            **kwargs: Additional arguments for render()

        Returns:
            Tuple of (back_button_rect, item_rects, scroll_offset, button_rects)
        """
        from ui.molecules.action_button import ActionButton
        action_button = ActionButton(self.theme)

        # Calculate footer height for buttons
        footer_height = 60 if button_labels else 0

        # Render main grid
        back_rect, item_rects, scroll_offset = self.render(
            screen, title, items, highlighted, selected,
            show_back=show_back,
            footer_height=footer_height,
            **kwargs
        )

        # Render bottom buttons
        button_rects = []
        if button_labels:
            button_width = 120
            button_height = 40
            total_width = len(button_labels) * button_width + (len(button_labels) - 1) * self.theme.padding_sm
            start_x = (screen.get_width() - total_width) // 2
            button_y = screen.get_height() - footer_height + (footer_height - button_height) // 2

            for i, label in enumerate(button_labels):
                button_rect = pygame.Rect(
                    start_x + i * (button_width + self.theme.padding_sm),
                    button_y,
                    button_width,
                    button_height
                )
                action_button.render(screen, button_rect, label)
                button_rects.append(button_rect)

        return back_rect, item_rects, scroll_offset, button_rects


# Default instance
grid_screen_template = GridScreenTemplate()
