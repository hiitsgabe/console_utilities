"""
Divider atom - Line separator rendering.
"""

import pygame
from typing import Tuple, Optional

from ui.theme import Theme, Color, default_theme


class Divider:
    """
    Divider rendering atom.

    Renders horizontal or vertical divider lines.
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme

    def render_horizontal(
        self,
        screen: pygame.Surface,
        y: int,
        x_start: int,
        x_end: int,
        color: Optional[Color] = None,
        thickness: int = 1,
    ) -> pygame.Rect:
        """
        Render a horizontal divider.

        Args:
            screen: Surface to render to
            y: Y position
            x_start: Start X position
            x_end: End X position
            color: Line color
            thickness: Line thickness

        Returns:
            Divider rect
        """
        if color is None:
            color = self.theme.text_disabled

        rect = pygame.Rect(x_start, y, x_end - x_start, thickness)
        pygame.draw.rect(screen, color, rect)
        return rect

    def render_vertical(
        self,
        screen: pygame.Surface,
        x: int,
        y_start: int,
        y_end: int,
        color: Optional[Color] = None,
        thickness: int = 1,
    ) -> pygame.Rect:
        """
        Render a vertical divider.

        Args:
            screen: Surface to render to
            x: X position
            y_start: Start Y position
            y_end: End Y position
            color: Line color
            thickness: Line thickness

        Returns:
            Divider rect
        """
        if color is None:
            color = self.theme.text_disabled

        rect = pygame.Rect(x, y_start, thickness, y_end - y_start)
        pygame.draw.rect(screen, color, rect)
        return rect

    def render_with_label(
        self,
        screen: pygame.Surface,
        y: int,
        x_start: int,
        x_end: int,
        label: str,
        color: Optional[Color] = None,
        text_color: Optional[Color] = None,
    ) -> pygame.Rect:
        """
        Render a horizontal divider with a label in the middle.

        Args:
            screen: Surface to render to
            y: Y position
            x_start: Start X position
            x_end: End X position
            label: Label text
            color: Line color
            text_color: Text color

        Returns:
            Divider rect including label
        """
        if color is None:
            color = self.theme.text_disabled
        if text_color is None:
            text_color = self.theme.text_disabled

        font = pygame.font.Font(None, self.theme.font_size_sm)
        text_surface = font.render(label, True, text_color)
        text_rect = text_surface.get_rect(centery=y, centerx=(x_start + x_end) // 2)

        # Draw lines on either side of label
        gap = 8
        if text_rect.left > x_start + gap:
            self.render_horizontal(screen, y, x_start, text_rect.left - gap, color)
        if text_rect.right < x_end - gap:
            self.render_horizontal(screen, y, text_rect.right + gap, x_end, color)

        # Draw label
        screen.blit(text_surface, text_rect)

        return pygame.Rect(
            x_start, y - text_rect.height // 2, x_end - x_start, text_rect.height
        )


# Default instance
divider = Divider()
