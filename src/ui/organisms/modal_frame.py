"""
Modal frame organism - Modal dialog container.
"""

import pygame
from typing import Tuple, Optional

from ui.theme import Theme, default_theme
from ui.atoms.surface import Surface
from ui.atoms.text import Text
from constants import BEZEL_INSET


class ModalFrame:
    """
    Modal frame organism.

    Provides a modal dialog container with backdrop and title.
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.surface = Surface(theme)
        self.text = Text(theme)

    def render(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        title: Optional[str] = None,
        with_backdrop: bool = True,
        backdrop_alpha: int = 180,
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect]]:
        """
        Render a modal frame.

        Args:
            screen: Surface to render to
            rect: Modal rectangle
            title: Optional title
            with_backdrop: Draw backdrop
            backdrop_alpha: Backdrop opacity

        Returns:
            Tuple of (modal_rect, content_rect, None). The third slot is where
            the close button used to be reported; modals close with the back
            button, so nothing is drawn there any more.
        """
        # Draw backdrop
        if with_backdrop:
            self.surface.render_modal_backdrop(screen, backdrop_alpha)

        # Draw modal surface with green border
        pygame.draw.rect(
            screen,
            self.theme.surface,
            rect,
            border_radius=self.theme.radius_lg,
        )
        pygame.draw.rect(
            screen,
            self.theme.primary,
            rect,
            width=2,
            border_radius=self.theme.radius_lg,
        )

        # Calculate header and content areas
        header_height = 50 if title else 0
        padding = self.theme.padding_lg

        content_rect = pygame.Rect(
            rect.left + padding,
            rect.top + header_height + padding,
            rect.width - padding * 2,
            rect.height - header_height - padding * 2,
        )

        close_button_rect = None

        # Draw header if title provided
        if title:
            # Draw title text
            self.text.render(
                screen,
                title,
                (rect.left + padding, rect.top + header_height // 2 - 4),
                color=self.theme.text_primary,
                size=self.theme.font_size_lg,
            )

            # Green underline beneath title
            pygame.draw.line(
                screen,
                self.theme.primary,
                (rect.left + 2, rect.top + header_height),
                (rect.right - 2, rect.top + header_height),
                1,
            )

        return rect, content_rect, close_button_rect

    def render_centered(
        self,
        screen: pygame.Surface,
        width: int,
        height: int,
        title: Optional[str] = None,
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect]]:
        """
        Render a centered modal.

        Args:
            screen: Surface to render to
            width: Modal width
            height: Modal height
            title: Optional title

        Returns:
            Tuple of (modal_rect, content_rect, None)
        """
        screen_rect = screen.get_rect()
        inset = BEZEL_INSET
        # Clamp modal dimensions to stay within bezel-safe area
        max_w = screen_rect.width - inset * 2
        max_h = screen_rect.height - inset * 2
        clamped_w = min(width, max_w)
        clamped_h = min(height, max_h)
        modal_rect = pygame.Rect(
            (screen_rect.width - clamped_w) // 2,
            (screen_rect.height - clamped_h) // 2,
            clamped_w,
            clamped_h,
        )

        return self.render(screen, modal_rect, title)

    def render_fullscreen(
        self,
        screen: pygame.Surface,
        margin: int = 40,
        title: Optional[str] = None,
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect]]:
        """
        Render a nearly fullscreen modal.

        Args:
            screen: Surface to render to
            margin: Margin from screen edges
            title: Optional title

        Returns:
            Tuple of (modal_rect, content_rect, None)
        """
        effective_margin = max(margin, BEZEL_INSET)
        screen_rect = screen.get_rect()
        modal_rect = screen_rect.inflate(-effective_margin * 2, -effective_margin * 2)

        return self.render(screen, modal_rect, title)


# Default instance
modal_frame = ModalFrame()
