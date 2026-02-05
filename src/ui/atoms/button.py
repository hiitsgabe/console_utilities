"""
Button atom - Basic button shape rendering.
"""

import pygame
from typing import Tuple, Optional

from ui.theme import Theme, Color, default_theme


class Button:
    """
    Basic button rendering atom.

    Renders button shapes with configurable colors, borders,
    and shadows.
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme

    def render(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        color: Optional[Color] = None,
        border_radius: Optional[int] = None,
        shadow: bool = True,
        border_color: Optional[Color] = None,
        border_width: int = 0,
        hover: bool = False,
        pressed: bool = False,
    ) -> pygame.Rect:
        """
        Render a button shape.

        Args:
            screen: Surface to render to
            rect: Button rectangle
            color: Fill color (default: primary)
            border_radius: Corner radius (default: theme.radius_md)
            shadow: Draw shadow
            border_color: Border color (optional)
            border_width: Border width
            hover: Apply hover effect
            pressed: Apply pressed effect

        Returns:
            Button rect
        """
        if color is None:
            color = self.theme.primary
        if border_radius is None:
            border_radius = self.theme.radius_md

        # Apply hover/pressed effects
        if pressed:
            color = self._darken(color, 0.2)
        elif hover:
            color = self._lighten(color, 0.1)

        # Draw shadow
        if shadow and not pressed:
            shadow_rect = rect.copy()
            shadow_rect.y += 2
            # Create a surface with alpha for shadow
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

        # Draw button
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

        return rect

    def render_icon_button(
        self,
        screen: pygame.Surface,
        center: Tuple[int, int],
        size: int,
        color: Optional[Color] = None,
        icon_color: Optional[Color] = None,
        icon_type: str = "close",  # "close", "back", "search", "download"
        hover: bool = False,
    ) -> pygame.Rect:
        """
        Render a circular icon button.

        Args:
            screen: Surface to render to
            center: Center position
            size: Button diameter
            color: Background color
            icon_color: Icon color
            icon_type: Type of icon to draw
            hover: Apply hover effect

        Returns:
            Button rect
        """
        if color is None:
            color = self.theme.surface_hover
        if icon_color is None:
            icon_color = self.theme.text_primary

        if hover:
            color = self._lighten(color, 0.1)

        rect = pygame.Rect(0, 0, size, size)
        rect.center = center

        # Draw circular background
        pygame.draw.circle(screen, color, center, size // 2)

        # Draw icon
        self._draw_icon(screen, center, size // 2, icon_color, icon_type)

        return rect

    def _draw_icon(
        self,
        screen: pygame.Surface,
        center: Tuple[int, int],
        radius: int,
        color: Color,
        icon_type: str,
    ) -> None:
        """Draw an icon inside a button."""
        cx, cy = center
        icon_size = int(radius * 0.5)

        if icon_type == "close":
            # X icon
            pygame.draw.line(
                screen,
                color,
                (cx - icon_size, cy - icon_size),
                (cx + icon_size, cy + icon_size),
                2,
            )
            pygame.draw.line(
                screen,
                color,
                (cx + icon_size, cy - icon_size),
                (cx - icon_size, cy + icon_size),
                2,
            )

        elif icon_type == "back":
            # < icon
            points = [
                (cx + icon_size // 2, cy - icon_size),
                (cx - icon_size // 2, cy),
                (cx + icon_size // 2, cy + icon_size),
            ]
            pygame.draw.lines(screen, color, False, points, 2)

        elif icon_type == "search":
            # Magnifying glass icon
            pygame.draw.circle(
                screen,
                color,
                (cx - icon_size // 4, cy - icon_size // 4),
                icon_size // 2,
                2,
            )
            pygame.draw.line(
                screen,
                color,
                (cx + icon_size // 4, cy + icon_size // 4),
                (cx + icon_size, cy + icon_size),
                2,
            )

        elif icon_type == "download":
            # Arrow down icon
            pygame.draw.line(
                screen, color, (cx, cy - icon_size), (cx, cy + icon_size // 2), 2
            )
            points = [
                (cx - icon_size // 2, cy),
                (cx, cy + icon_size),
                (cx + icon_size // 2, cy),
            ]
            pygame.draw.lines(screen, color, False, points, 2)

    def _lighten(self, color: Color, amount: float) -> Color:
        """Lighten a color by a percentage."""
        return tuple(min(255, int(c + (255 - c) * amount)) for c in color)

    def _darken(self, color: Color, amount: float) -> Color:
        """Darken a color by a percentage."""
        return tuple(max(0, int(c * (1 - amount))) for c in color)


# Default instance
button = Button()
