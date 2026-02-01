"""
Modal frame organism - Modal dialog container.
"""

import pygame
from typing import Tuple, Optional

from ui.theme import Theme, default_theme
from ui.atoms.surface import Surface
from ui.atoms.text import Text
from ui.atoms.button import Button


class ModalFrame:
    """
    Modal frame organism.

    Provides a modal dialog container with backdrop,
    title, and close button.
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.surface = Surface(theme)
        self.text = Text(theme)
        self.button = Button(theme)

    def render(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        title: Optional[str] = None,
        show_close: bool = True,
        with_backdrop: bool = True,
        backdrop_alpha: int = 180
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect]]:
        """
        Render a modal frame.

        Args:
            screen: Surface to render to
            rect: Modal rectangle
            title: Optional title
            show_close: Show close button
            with_backdrop: Draw backdrop
            backdrop_alpha: Backdrop opacity

        Returns:
            Tuple of (modal_rect, content_rect, close_button_rect or None)
        """
        # Draw backdrop
        if with_backdrop:
            self.surface.render_modal_backdrop(screen, backdrop_alpha)

        # Draw modal surface
        pygame.draw.rect(
            screen,
            self.theme.surface,
            rect,
            border_radius=self.theme.radius_lg
        )

        # Draw shadow
        shadow_rect = rect.copy()
        shadow_rect.y += 4
        shadow_surface = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(
            shadow_surface,
            (*self.theme.background, 100),
            shadow_surface.get_rect(),
            border_radius=self.theme.radius_lg
        )

        # Calculate header and content areas
        header_height = 50 if title else 0
        padding = self.theme.padding_lg

        content_rect = pygame.Rect(
            rect.left + padding,
            rect.top + header_height + padding,
            rect.width - padding * 2,
            rect.height - header_height - padding * 2
        )

        close_button_rect = None

        # Draw header if title provided
        if title:
            # Draw header background
            header_rect = pygame.Rect(
                rect.left,
                rect.top,
                rect.width,
                header_height
            )
            pygame.draw.rect(
                screen,
                self.theme.surface_hover,
                header_rect,
                border_radius=self.theme.radius_lg
            )
            # Fix bottom corners
            pygame.draw.rect(
                screen,
                self.theme.surface_hover,
                pygame.Rect(
                    rect.left,
                    rect.top + header_height - self.theme.radius_lg,
                    rect.width,
                    self.theme.radius_lg
                )
            )

            # Draw title
            self.text.render(
                screen,
                title,
                (rect.left + padding, rect.top + header_height // 2 - 4),
                color=self.theme.text_primary,
                size=self.theme.font_size_lg
            )

            # Draw close button
            if show_close:
                close_size = 30
                close_button_rect = pygame.Rect(
                    rect.right - padding - close_size,
                    rect.top + (header_height - close_size) // 2,
                    close_size,
                    close_size
                )
                self.button.render_icon_button(
                    screen,
                    close_button_rect.center,
                    close_size,
                    icon_type="close"
                )

        return rect, content_rect, close_button_rect

    def render_centered(
        self,
        screen: pygame.Surface,
        width: int,
        height: int,
        title: Optional[str] = None,
        show_close: bool = True
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect]]:
        """
        Render a centered modal.

        Args:
            screen: Surface to render to
            width: Modal width
            height: Modal height
            title: Optional title
            show_close: Show close button

        Returns:
            Tuple of (modal_rect, content_rect, close_button_rect or None)
        """
        screen_rect = screen.get_rect()
        modal_rect = pygame.Rect(
            (screen_rect.width - width) // 2,
            (screen_rect.height - height) // 2,
            width,
            height
        )

        return self.render(screen, modal_rect, title, show_close)

    def render_fullscreen(
        self,
        screen: pygame.Surface,
        margin: int = 40,
        title: Optional[str] = None,
        show_close: bool = True
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect]]:
        """
        Render a nearly fullscreen modal.

        Args:
            screen: Surface to render to
            margin: Margin from screen edges
            title: Optional title
            show_close: Show close button

        Returns:
            Tuple of (modal_rect, content_rect, close_button_rect or None)
        """
        screen_rect = screen.get_rect()
        modal_rect = screen_rect.inflate(-margin * 2, -margin * 2)

        return self.render(screen, modal_rect, title, show_close)


# Default instance
modal_frame = ModalFrame()
