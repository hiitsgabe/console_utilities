"""
Header organism - Title bar with navigation.
"""

import pygame
from typing import Tuple, Optional, Callable

from ui.theme import Theme, default_theme
from ui.atoms.text import Text
from ui.atoms.button import Button


class Header:
    """
    Header organism.

    Displays a title bar with optional back button
    and action buttons.
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.text = Text(theme)
        self.button = Button(theme)

    def render(
        self,
        screen: pygame.Surface,
        title: str,
        show_back: bool = False,
        subtitle: Optional[str] = None,
        right_text: Optional[str] = None,
        height: int = 60
    ) -> Tuple[pygame.Rect, Optional[pygame.Rect]]:
        """
        Render a header.

        Args:
            screen: Surface to render to
            title: Header title
            show_back: Show back button
            subtitle: Optional subtitle
            right_text: Optional right-aligned text
            height: Header height

        Returns:
            Tuple of (header_rect, back_button_rect or None)
        """
        screen_width = screen.get_width()
        header_rect = pygame.Rect(0, 0, screen_width, height)

        # Draw background
        pygame.draw.rect(screen, self.theme.surface, header_rect)

        # Draw bottom border
        pygame.draw.line(
            screen,
            self.theme.surface_hover,
            (0, height - 1),
            (screen_width, height - 1)
        )

        back_button_rect = None
        content_left = self.theme.padding_md

        # Draw back button if needed
        if show_back:
            back_size = 36
            back_button_rect = pygame.Rect(
                self.theme.padding_sm,
                (height - back_size) // 2,
                back_size,
                back_size
            )
            self.button.render_icon_button(
                screen,
                back_button_rect.center,
                back_size,
                icon_type="back"
            )
            content_left = back_button_rect.right + self.theme.padding_sm

        # Draw title
        title_y = height // 2 - self.theme.font_size_lg // 4
        if subtitle:
            title_y = height // 3 - self.theme.font_size_lg // 4

        self.text.render(
            screen,
            title,
            (content_left, title_y),
            color=self.theme.text_primary,
            size=self.theme.font_size_lg
        )

        # Draw subtitle if provided
        if subtitle:
            subtitle_y = height * 2 // 3 - self.theme.font_size_sm // 4
            self.text.render(
                screen,
                subtitle,
                (content_left, subtitle_y),
                color=self.theme.text_secondary,
                size=self.theme.font_size_sm
            )

        # Draw right text if provided
        if right_text:
            self.text.render(
                screen,
                right_text,
                (screen_width - self.theme.padding_md, height // 2),
                color=self.theme.text_secondary,
                size=self.theme.font_size_sm,
                align="right"
            )

        return header_rect, back_button_rect

    def get_content_area(
        self,
        screen: pygame.Surface,
        header_height: int = 60
    ) -> pygame.Rect:
        """
        Get the content area below the header.

        Args:
            screen: Screen surface
            header_height: Height of header

        Returns:
            Content area rect
        """
        return pygame.Rect(
            0,
            header_height,
            screen.get_width(),
            screen.get_height() - header_height
        )


# Default instance
header = Header()
