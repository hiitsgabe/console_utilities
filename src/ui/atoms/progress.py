"""
Progress bar atom - Basic progress bar rendering.
"""

import pygame
from typing import Tuple, Optional

from ui.theme import Theme, Color, default_theme


class ProgressBar:
    """
    Progress bar rendering atom.

    Renders horizontal progress bars with customizable
    colors and styles.
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme

    def render(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        progress: float,  # 0.0 to 1.0
        track_color: Optional[Color] = None,
        fill_color: Optional[Color] = None,
        border_radius: Optional[int] = None,
        show_glow: bool = False,
    ) -> pygame.Rect:
        """
        Render a progress bar.

        Args:
            screen: Surface to render to
            rect: Progress bar rectangle
            progress: Progress value (0.0 to 1.0)
            track_color: Background track color
            fill_color: Progress fill color
            border_radius: Corner radius
            show_glow: Show glow effect at progress edge

        Returns:
            Progress bar rect
        """
        if track_color is None:
            track_color = self.theme.surface
        if fill_color is None:
            fill_color = self.theme.primary
        if border_radius is None:
            border_radius = self.theme.radius_sm

        # Clamp progress
        progress = max(0.0, min(1.0, progress))

        # Draw track
        pygame.draw.rect(screen, track_color, rect, border_radius=border_radius)

        # Draw fill
        if progress > 0:
            fill_width = int(rect.width * progress)
            fill_rect = pygame.Rect(rect.left, rect.top, fill_width, rect.height)
            pygame.draw.rect(screen, fill_color, fill_rect, border_radius=border_radius)

            # Draw glow effect
            if show_glow and fill_width > 0:
                glow_surface = pygame.Surface((20, rect.height), pygame.SRCALPHA)
                for i in range(20):
                    alpha = int(40 * (1 - i / 20))
                    pygame.draw.line(
                        glow_surface, (*fill_color, alpha), (i, 0), (i, rect.height)
                    )
                glow_x = min(fill_rect.right - 10, rect.right - 20)
                screen.blit(glow_surface, (glow_x, rect.top))

        return rect

    def render_with_text(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        progress: float,
        text: Optional[str] = None,
        text_color: Optional[Color] = None,
        track_color: Optional[Color] = None,
        fill_color: Optional[Color] = None,
    ) -> pygame.Rect:
        """
        Render a progress bar with centered text.

        Args:
            screen: Surface to render to
            rect: Progress bar rectangle
            progress: Progress value (0.0 to 1.0)
            text: Text to display (default: percentage)
            text_color: Text color
            track_color: Background track color
            fill_color: Progress fill color

        Returns:
            Progress bar rect
        """
        if text_color is None:
            text_color = self.theme.text_primary
        if text is None:
            text = f"{int(progress * 100)}%"

        # Draw progress bar
        self.render(
            screen, rect, progress, track_color=track_color, fill_color=fill_color
        )

        # Draw text
        font = pygame.font.Font(
            getattr(self.theme, "font_path", None),
            self.theme.font_size_sm,
        )
        text_surface = font.render(text, True, text_color)
        text_rect = text_surface.get_rect(center=rect.center)
        screen.blit(text_surface, text_rect)

        return rect

    def render_indeterminate(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        position: float,  # Animation position 0.0 to 1.0
        track_color: Optional[Color] = None,
        fill_color: Optional[Color] = None,
        bar_width: float = 0.3,  # Width of moving bar as fraction
    ) -> pygame.Rect:
        """
        Render an indeterminate (loading) progress bar.

        Args:
            screen: Surface to render to
            rect: Progress bar rectangle
            position: Animation position (0.0 to 1.0, loops)
            track_color: Background track color
            fill_color: Fill color
            bar_width: Width of moving bar as fraction of total

        Returns:
            Progress bar rect
        """
        if track_color is None:
            track_color = self.theme.surface
        if fill_color is None:
            fill_color = self.theme.primary

        border_radius = self.theme.radius_sm

        # Draw track
        pygame.draw.rect(screen, track_color, rect, border_radius=border_radius)

        # Calculate bar position
        total_travel = rect.width * (1 + bar_width)
        bar_start = int(position * total_travel - rect.width * bar_width)
        bar_width_px = int(rect.width * bar_width)

        # Clip to bounds
        fill_left = max(rect.left, rect.left + bar_start)
        fill_right = min(rect.right, rect.left + bar_start + bar_width_px)

        if fill_right > fill_left:
            fill_rect = pygame.Rect(
                fill_left, rect.top, fill_right - fill_left, rect.height
            )
            pygame.draw.rect(screen, fill_color, fill_rect, border_radius=border_radius)

        return rect


# Default instance
progress_bar = ProgressBar()
