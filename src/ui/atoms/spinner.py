"""
Spinner atom - Animated loading spinner.
"""

import pygame
import math
import time
from typing import Tuple, Optional

from ui.theme import Theme, Color, default_theme


class Spinner:
    """
    Animated loading spinner.

    Renders a circular spinning animation for loading states.
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme

    def render(
        self,
        screen: pygame.Surface,
        center: Tuple[int, int],
        size: int = 40,
        color: Optional[Color] = None,
        thickness: int = 4,
        speed: float = 1.0,
    ) -> None:
        """
        Render an animated spinner.

        Args:
            screen: Surface to render to
            center: Center position (x, y)
            size: Diameter of the spinner
            color: Spinner color (defaults to primary)
            thickness: Line thickness
            speed: Animation speed multiplier
        """
        if color is None:
            color = self.theme.primary

        radius = size // 2
        cx, cy = center

        # Calculate rotation based on time
        rotation = (time.time() * speed * 2 * math.pi) % (2 * math.pi)

        # Draw arc segments with varying opacity
        num_segments = 8
        arc_length = math.pi / 3  # Length of each arc segment

        for i in range(num_segments):
            # Calculate segment angle
            segment_angle = rotation + (i * 2 * math.pi / num_segments)

            # Calculate opacity (fading trail effect)
            opacity = int(255 * (1 - i / num_segments))

            # Create color with opacity
            segment_color = (
                (*color[:3], opacity) if len(color) == 4 else (*color, opacity)
            )

            # Draw arc segment
            self._draw_arc(
                screen,
                (cx, cy),
                radius,
                segment_angle,
                segment_angle + arc_length,
                segment_color,
                thickness,
            )

    def _draw_arc(
        self,
        screen: pygame.Surface,
        center: Tuple[int, int],
        radius: int,
        start_angle: float,
        end_angle: float,
        color: Tuple[int, int, int, int],
        thickness: int,
    ) -> None:
        """Draw an arc segment."""
        cx, cy = center
        points = []
        steps = 10

        for i in range(steps + 1):
            angle = start_angle + (end_angle - start_angle) * i / steps
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            points.append((x, y))

        if len(points) >= 2:
            # Create a surface with alpha for the arc
            arc_surface = pygame.Surface(
                (radius * 2 + thickness * 2, radius * 2 + thickness * 2),
                pygame.SRCALPHA,
            )
            offset = radius + thickness

            # Adjust points to arc surface coordinates
            adjusted_points = [(x - cx + offset, y - cy + offset) for x, y in points]

            pygame.draw.lines(arc_surface, color, False, adjusted_points, thickness)

            # Blit the arc surface
            screen.blit(arc_surface, (cx - offset, cy - offset))

    def render_simple(
        self,
        screen: pygame.Surface,
        center: Tuple[int, int],
        size: int = 40,
        color: Optional[Color] = None,
    ) -> None:
        """
        Render a simple rotating spinner (no alpha blending).

        Args:
            screen: Surface to render to
            center: Center position (x, y)
            size: Diameter of the spinner
            color: Spinner color (defaults to primary)
        """
        if color is None:
            color = self.theme.primary

        radius = size // 2
        cx, cy = center

        # Calculate rotation based on time
        rotation = (time.time() * 2 * math.pi) % (2 * math.pi)

        # Draw background circle (faded)
        pygame.draw.circle(screen, self.theme.surface_hover, center, radius, 3)

        # Draw rotating arc
        arc_length = math.pi * 0.75

        # Draw the arc using lines
        points = []
        steps = 20
        for i in range(steps + 1):
            angle = rotation + arc_length * i / steps
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            points.append((x, y))

        if len(points) >= 2:
            pygame.draw.lines(screen, color, False, points, 3)


# Default instance
spinner = Spinner()
