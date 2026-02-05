"""
Surface atom - Card and panel surface rendering.
"""

import pygame
from typing import Tuple, Optional

from ui.theme import Theme, Color, default_theme


class Surface:
    """
    Surface rendering atom.

    Renders card/panel surfaces with optional shadows,
    borders, and selection states.
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme

    def render(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        color: Optional[Color] = None,
        border_radius: Optional[int] = None,
        shadow: bool = False,
        shadow_offset: int = 2,
        border_color: Optional[Color] = None,
        border_width: int = 0,
        selected: bool = False,
        highlighted: bool = False,
    ) -> pygame.Rect:
        """
        Render a surface/card.

        Args:
            screen: Surface to render to
            rect: Surface rectangle
            color: Fill color (default: surface)
            border_radius: Corner radius
            shadow: Draw drop shadow
            shadow_offset: Shadow offset in pixels
            border_color: Border color
            border_width: Border width
            selected: Apply selected state
            highlighted: Apply highlighted/hover state

        Returns:
            Surface rect
        """
        # Determine color based on state
        if color is None:
            if selected:
                color = self.theme.surface_selected
            elif highlighted:
                color = self.theme.surface_hover
            else:
                color = self.theme.surface

        if border_radius is None:
            border_radius = self.theme.radius_lg

        # Draw shadow
        if shadow:
            shadow_rect = rect.copy()
            shadow_rect.y += shadow_offset
            shadow_surface = pygame.Surface(
                (shadow_rect.width, shadow_rect.height), pygame.SRCALPHA
            )
            pygame.draw.rect(
                shadow_surface,
                self.theme.shadow,
                shadow_surface.get_rect(),
                border_radius=border_radius,
            )
            screen.blit(shadow_surface, shadow_rect.topleft)

        # Draw main surface
        pygame.draw.rect(screen, color, rect, border_radius=border_radius)

        # Draw border
        if border_color and border_width > 0:
            pygame.draw.rect(
                screen,
                border_color,
                rect,
                width=border_width,
                border_radius=border_radius,
            )

        # Draw selection indicator
        if selected:
            indicator_rect = pygame.Rect(rect.left + 4, rect.centery - 10, 4, 20)
            pygame.draw.rect(
                screen, self.theme.primary, indicator_rect, border_radius=2
            )

        return rect

    def render_card(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        selected: bool = False,
        highlighted: bool = False,
        padding: Optional[int] = None,
    ) -> Tuple[pygame.Rect, pygame.Rect]:
        """
        Render a card with padding and return content rect.

        Args:
            screen: Surface to render to
            rect: Card rectangle
            selected: Selected state
            highlighted: Highlighted state
            padding: Internal padding

        Returns:
            Tuple of (card_rect, content_rect)
        """
        if padding is None:
            padding = self.theme.padding_sm

        self.render(
            screen, rect, shadow=True, selected=selected, highlighted=highlighted
        )

        content_rect = rect.inflate(-padding * 2, -padding * 2)
        return rect, content_rect

    def render_modal_backdrop(self, screen: pygame.Surface, alpha: int = 128) -> None:
        """
        Render a semi-transparent modal backdrop.

        Args:
            screen: Surface to render to
            alpha: Backdrop opacity (0-255)
        """
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((*self.theme.background, alpha))
        screen.blit(overlay, (0, 0))

    def render_modal(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        title: Optional[str] = None,
        with_backdrop: bool = True,
    ) -> Tuple[pygame.Rect, pygame.Rect]:
        """
        Render a modal dialog surface.

        Args:
            screen: Surface to render to
            rect: Modal rectangle
            title: Optional modal title
            with_backdrop: Draw backdrop

        Returns:
            Tuple of (modal_rect, content_rect)
        """
        if with_backdrop:
            self.render_modal_backdrop(screen)

        # Draw modal surface
        self.render(
            screen, rect, color=self.theme.surface, shadow=True, shadow_offset=4
        )

        content_rect = rect.inflate(
            -self.theme.padding_lg * 2, -self.theme.padding_lg * 2
        )

        # Draw title if provided
        if title:
            font = pygame.font.Font(None, self.theme.font_size_lg)
            title_surface = font.render(title, True, self.theme.text_primary)
            title_rect = title_surface.get_rect(
                centerx=rect.centerx, top=rect.top + self.theme.padding_lg
            )
            screen.blit(title_surface, title_rect)

            # Adjust content rect to account for title
            content_rect.top = title_rect.bottom + self.theme.padding_md

        return rect, content_rect


# Default instance
surface = Surface()
