"""
List screen template - Layout for list-based screens.
"""

import pygame
from typing import List, Set, Tuple, Optional, Any, Callable

from ui.theme import Theme, default_theme
from ui.organisms.header import Header
from ui.organisms.menu_list import MenuList
from constants import BEZEL_INSET


class ListScreenTemplate:
    """
    List screen template.

    Combines header and menu list into a complete
    list-based screen layout.
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.header = Header(theme)
        self.menu_list = MenuList(theme)

    def render(
        self,
        screen: pygame.Surface,
        title: str,
        items: List[Any],
        highlighted: int,
        selected: Set[int],
        show_back: bool = True,
        subtitle: Optional[str] = None,
        item_height: int = 50,
        get_label: Optional[Callable[[Any], str]] = None,
        get_thumbnail: Optional[Callable[[Any], pygame.Surface]] = None,
        get_secondary: Optional[Callable[[Any], str]] = None,
        show_checkbox: bool = False,
        divider_indices: Optional[Set[int]] = None,
        footer_height: int = 0,
        item_spacing: int = 0,
        rainbow_title: bool = False,
        center_title: bool = False,
    ) -> Tuple[Optional[pygame.Rect], List[pygame.Rect], int]:
        """
        Render a list screen.

        Args:
            screen: Surface to render to
            title: Screen title
            items: List of items
            highlighted: Highlighted index
            selected: Selected indices
            show_back: Show back button
            subtitle: Optional subtitle
            item_height: Item height
            get_label: Label extraction function
            get_thumbnail: Thumbnail extraction function
            get_secondary: Secondary text function
            show_checkbox: Show checkboxes
            divider_indices: Divider indices
            footer_height: Reserved footer space
            rainbow_title: Render title with rainbow colors
            center_title: Center the title horizontally

        Returns:
            Tuple of (back_button_rect, item_rects, scroll_offset)
        """
        # Draw header
        header_height = 60
        header_rect, back_button_rect = self.header.render(
            screen,
            title,
            show_back=show_back,
            subtitle=subtitle,
            rainbow_title=rainbow_title,
            center_title=center_title,
        )

        # Calculate content area (inset from bezel on all sides)
        inset = BEZEL_INSET
        content_rect = pygame.Rect(
            inset + self.theme.padding_sm,
            inset + header_height + self.theme.padding_sm,
            screen.get_width() - inset * 2 - self.theme.padding_sm * 2,
            screen.get_height()
            - inset * 2
            - header_height
            - self.theme.padding_sm * 2
            - footer_height,
        )

        # Draw menu list
        item_rects, scroll_offset = self.menu_list.render(
            screen,
            content_rect,
            items,
            highlighted,
            selected,
            item_height=item_height,
            get_label=get_label,
            get_thumbnail=get_thumbnail,
            get_secondary=get_secondary,
            show_checkbox=show_checkbox,
            divider_indices=divider_indices,
            item_spacing=item_spacing,
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
        **kwargs,
    ) -> Tuple[Optional[pygame.Rect], List[pygame.Rect], int, List[pygame.Rect]]:
        """
        Render a list screen with bottom action buttons.

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

        # Render main list
        back_rect, item_rects, scroll_offset = self.render(
            screen,
            title,
            items,
            highlighted,
            selected,
            show_back=show_back,
            footer_height=footer_height,
            **kwargs,
        )

        # Render bottom buttons
        button_rects = []
        if button_labels:
            inset = BEZEL_INSET
            button_width = 120
            button_height = 40
            total_width = (
                len(button_labels) * button_width
                + (len(button_labels) - 1) * self.theme.padding_sm
            )
            start_x = (screen.get_width() - total_width) // 2
            button_y = (
                screen.get_height()
                - inset
                - footer_height
                + (footer_height - button_height) // 2
            )

            for i, label in enumerate(button_labels):
                button_rect = pygame.Rect(
                    start_x + i * (button_width + self.theme.padding_sm),
                    button_y,
                    button_width,
                    button_height,
                )
                action_button.render(screen, button_rect, label)
                button_rects.append(button_rect)

        return back_rect, item_rects, scroll_offset, button_rects


# Default instance
list_screen_template = ListScreenTemplate()
