"""
Header organism - Title bar with navigation.
"""

import pygame
from typing import Tuple, Optional, Callable

from ui.theme import Theme, default_theme
from ui.atoms.text import Text
from ui.atoms.button import Button
from constants import BEZEL_INSET


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
        height: int = 60,
        rainbow_title: bool = False,
        center_title: bool = False,
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
            rainbow_title: Render title with rainbow colors
            center_title: Center the title horizontally

        Returns:
            Tuple of (header_rect, back_button_rect or None)
        """
        screen_width = screen.get_width()
        inset = BEZEL_INSET
        header_rect = pygame.Rect(inset, inset, screen_width - inset * 2, height)

        # Draw background
        pygame.draw.rect(screen, self.theme.surface, header_rect)

        # Draw bottom border (green line)
        border_y = inset + height - 1
        pygame.draw.line(
            screen,
            self.theme.primary,
            (inset, border_y),
            (inset + header_rect.width, border_y),
        )

        back_button_rect = None
        content_left = inset + self.theme.padding_md

        # Draw back button if needed
        if show_back:
            back_size = 36
            back_button_rect = pygame.Rect(
                inset + self.theme.padding_sm,
                inset + (height - back_size) // 2,
                back_size,
                back_size,
            )
            self.button.render_icon_button(
                screen, back_button_rect.center, back_size, icon_type="back"
            )
            content_left = back_button_rect.right + self.theme.padding_sm

        # Draw title
        title_y = inset + height // 2 - self.theme.font_size_lg // 4
        if subtitle:
            title_y = inset + height // 3 - self.theme.font_size_lg // 4

        # Determine title position and alignment
        if center_title:
            title_x = screen_width // 2
            title_align = "center"
        else:
            title_x = content_left
            title_align = "left"

        if rainbow_title:
            self.text.render_rainbow(
                screen,
                title,
                (title_x, title_y),
                size=self.theme.font_size_lg,
                align=title_align,
            )
        else:
            self.text.render(
                screen,
                title,
                (title_x, title_y),
                color=self.theme.text_primary,
                size=self.theme.font_size_lg,
                align=title_align,
            )

        # Draw subtitle if provided
        if subtitle:
            subtitle_y = inset + height * 2 // 3 - self.theme.font_size_sm // 4
            self.text.render(
                screen,
                subtitle,
                (content_left, subtitle_y),
                color=self.theme.text_secondary,
                size=self.theme.font_size_sm,
            )

        # Draw right text if provided
        if right_text:
            self.text.render(
                screen,
                right_text,
                (
                    screen_width - inset - self.theme.padding_md,
                    inset + height // 2,
                ),
                color=self.theme.text_secondary,
                size=self.theme.font_size_sm,
                align="right",
            )

        return header_rect, back_button_rect

    def get_content_area(
        self, screen: pygame.Surface, header_height: int = 60
    ) -> pygame.Rect:
        """
        Get the content area below the header.

        Args:
            screen: Screen surface
            header_height: Height of header

        Returns:
            Content area rect
        """
        inset = BEZEL_INSET
        return pygame.Rect(
            inset,
            inset + header_height,
            screen.get_width() - inset * 2,
            screen.get_height() - inset * 2 - header_height,
        )


# Default instance
header = Header()
