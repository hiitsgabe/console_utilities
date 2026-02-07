"""
Action button molecule - Button with label.
"""

import pygame
from typing import Tuple, Optional

from ui.theme import Theme, Color, default_theme
from ui.atoms.button import Button
from ui.atoms.text import Text


class ActionButton:
    """
    Action button molecule.

    Combines a button with text label, supporting
    various styles and states.
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.button = Button(theme)
        self.text = Text(theme)

    def render(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        label: str,
        color: Optional[Color] = None,
        text_color: Optional[Color] = None,
        hover: bool = False,
        pressed: bool = False,
        disabled: bool = False,
        icon: Optional[str] = None,  # "back", "search", "download", "close"
    ) -> pygame.Rect:
        """
        Render an action button.

        Args:
            screen: Surface to render to
            rect: Button rectangle
            label: Button label
            color: Background color
            text_color: Text color
            hover: Hover state
            pressed: Pressed state
            disabled: Disabled state
            icon: Optional icon type

        Returns:
            Button rect
        """
        if disabled:
            color = self.theme.surface
            text_color = self.theme.text_disabled
        else:
            if color is None:
                color = self.theme.primary
            if text_color is None:
                text_color = self.theme.text_primary
            # Hover fills background with primary, so use dark text for contrast
            if hover:
                text_color = self.theme.background

        # Draw button
        self.button.render(
            screen,
            rect,
            color=color,
            hover=hover and not disabled,
            pressed=pressed and not disabled,
            shadow=not disabled,
        )

        # Calculate text position
        text_x = rect.centerx
        text_y = rect.centery - self.theme.font_size_md // 4

        if icon:
            # Draw icon on left side
            icon_size = 20
            icon_x = rect.left + self.theme.padding_md + icon_size // 2
            icon_y = rect.centery

            self._draw_icon(screen, (icon_x, icon_y), icon_size, text_color, icon)

            # Shift text to the right
            text_x = (icon_x + icon_size + rect.right) // 2

        # Draw label
        self.text.render(
            screen,
            label,
            (text_x, text_y),
            color=text_color,
            size=self.theme.font_size_md,
            align="center",
        )

        return rect

    def render_secondary(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        label: str,
        hover: bool = False,
        pressed: bool = False,
    ) -> pygame.Rect:
        """
        Render a secondary style button.

        Args:
            screen: Surface to render to
            rect: Button rectangle
            label: Button label
            hover: Hover state
            pressed: Pressed state

        Returns:
            Button rect
        """
        return self.render(
            screen,
            rect,
            label,
            color=self.theme.surface_hover,
            text_color=self.theme.text_primary,
            hover=hover,
            pressed=pressed,
        )

    def render_success(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        label: str,
        hover: bool = False,
        pressed: bool = False,
    ) -> pygame.Rect:
        """
        Render a success style button.

        Args:
            screen: Surface to render to
            rect: Button rectangle
            label: Button label
            hover: Hover state
            pressed: Pressed state

        Returns:
            Button rect
        """
        return self.render(
            screen, rect, label, color=self.theme.success, hover=hover, pressed=pressed
        )

    def render_danger(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        label: str,
        hover: bool = False,
        pressed: bool = False,
    ) -> pygame.Rect:
        """
        Render a danger/error style button.

        Args:
            screen: Surface to render to
            rect: Button rectangle
            label: Button label
            hover: Hover state
            pressed: Pressed state

        Returns:
            Button rect
        """
        return self.render(
            screen, rect, label, color=self.theme.error, hover=hover, pressed=pressed
        )

    def _draw_icon(
        self,
        screen: pygame.Surface,
        center: Tuple[int, int],
        size: int,
        color: Color,
        icon_type: str,
    ) -> None:
        """Draw an icon."""
        cx, cy = center
        half = size // 2

        if icon_type == "back":
            points = [
                (cx + half // 2, cy - half),
                (cx - half // 2, cy),
                (cx + half // 2, cy + half),
            ]
            pygame.draw.lines(screen, color, False, points, 2)

        elif icon_type == "search":
            pygame.draw.circle(screen, color, (cx - 2, cy - 2), half // 2, 2)
            pygame.draw.line(screen, color, (cx + 2, cy + 2), (cx + half, cy + half), 2)

        elif icon_type == "download":
            pygame.draw.line(screen, color, (cx, cy - half), (cx, cy + half // 2), 2)
            points = [(cx - half // 2, cy), (cx, cy + half), (cx + half // 2, cy)]
            pygame.draw.lines(screen, color, False, points, 2)

        elif icon_type == "close":
            pygame.draw.line(
                screen,
                color,
                (cx - half // 2, cy - half // 2),
                (cx + half // 2, cy + half // 2),
                2,
            )
            pygame.draw.line(
                screen,
                color,
                (cx + half // 2, cy - half // 2),
                (cx - half // 2, cy + half // 2),
                2,
            )


# Default instance
action_button = ActionButton()
