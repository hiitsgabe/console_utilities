"""
Menu item molecule - Text-based menu items.
"""

import pygame
from typing import Tuple, Optional, Any

from ui.theme import Theme, Color, default_theme
from ui.atoms.text import Text


class MenuItem:
    """
    Menu item molecule.

    Renders text-based menu items with highlight states
    and optional thumbnail/checkbox support.
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.text = Text(theme)

    def render(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        label: str,
        selected: bool = False,
        highlighted: bool = False,
        thumbnail: Optional[pygame.Surface] = None,
        secondary_text: Optional[str] = None,
        show_checkbox: bool = False,
    ) -> pygame.Rect:
        """
        Render a menu item.

        Args:
            screen: Surface to render to
            rect: Item rectangle
            label: Primary text
            selected: Item is selected
            highlighted: Item is highlighted/hovered
            thumbnail: Optional thumbnail image
            secondary_text: Optional secondary text (right side)
            show_checkbox: Show selection checkbox

        Returns:
            Item rect
        """
        # Calculate content areas
        padding = self.theme.padding_sm
        content_left = rect.left + padding
        content_right = rect.right - padding

        # Draw checkbox if enabled
        if show_checkbox:
            checkbox_size = 20
            checkbox_rect = pygame.Rect(
                content_left,
                rect.centery - checkbox_size // 2,
                checkbox_size,
                checkbox_size,
            )

            # Checkbox background
            pygame.draw.rect(
                screen, self.theme.surface_hover, checkbox_rect, border_radius=4
            )

            # Checkbox border
            pygame.draw.rect(
                screen,
                self.theme.text_secondary if not selected else self.theme.primary,
                checkbox_rect,
                width=2,
                border_radius=4,
            )

            # Checkmark if selected
            if selected:
                # Draw checkmark
                points = [
                    (checkbox_rect.left + 4, checkbox_rect.centery),
                    (checkbox_rect.centerx - 2, checkbox_rect.bottom - 5),
                    (checkbox_rect.right - 4, checkbox_rect.top + 5),
                ]
                pygame.draw.lines(screen, self.theme.primary, False, points, 2)

            content_left = checkbox_rect.right + padding

        # Draw thumbnail if provided
        if thumbnail:
            thumb_size = min(rect.height - padding * 2, 48)
            thumb_rect = pygame.Rect(
                content_left, rect.centery - thumb_size // 2, thumb_size, thumb_size
            )

            # Scale thumbnail to fit (smoothscale for better quality)
            scaled_thumb = pygame.transform.smoothscale(
                thumbnail, (thumb_size, thumb_size)
            )
            screen.blit(scaled_thumb, thumb_rect)

            content_left = thumb_rect.right + padding

        # Draw secondary text if provided (right side)
        if secondary_text:
            secondary_width, _ = self.text.measure(
                secondary_text, size=self.theme.font_size_sm
            )
            self.text.render(
                screen,
                secondary_text,
                (content_right, rect.centery),
                color=self.theme.text_secondary,
                size=self.theme.font_size_sm,
                align="right",
            )
            content_right -= secondary_width + padding

        # Draw main label
        max_text_width = content_right - content_left - padding

        # Determine text color based on state
        if highlighted:
            text_color = self.theme.primary
        else:
            text_color = self.theme.text_secondary

        # Add cursor prefix for highlighted items (retro terminal style)
        cursor = getattr(self.theme, "menu_cursor", "")
        if cursor:
            display_label = (
                cursor + label if highlighted else (" " * len(cursor) + label)
            )
        else:
            display_label = label

        self.text.render(
            screen,
            display_label,
            (content_left, rect.centery - self.theme.font_size_md // 4),
            color=text_color,
            size=self.theme.font_size_md,
            max_width=max_text_width,
        )

        return rect

    def render_divider(
        self, screen: pygame.Surface, rect: pygame.Rect, label: str
    ) -> pygame.Rect:
        """
        Render a divider/section header item.

        Args:
            screen: Surface to render to
            rect: Item rectangle
            label: Divider label

        Returns:
            Item rect
        """
        # Draw label centered
        self.text.render(
            screen,
            label,
            (rect.centerx, rect.centery - self.theme.font_size_sm // 4),
            color=self.theme.text_disabled,
            size=self.theme.font_size_sm,
            align="center",
        )

        # Draw lines on either side
        font = pygame.font.Font(
            getattr(self.theme, "font_path", None),
            self.theme.font_size_sm,
        )
        text_width = font.size(label)[0]
        gap = 10

        line_y = rect.centery
        line_left_end = rect.centerx - text_width // 2 - gap
        line_right_start = rect.centerx + text_width // 2 + gap

        if line_left_end > rect.left + 20:
            pygame.draw.line(
                screen,
                self.theme.text_disabled,
                (rect.left + 20, line_y),
                (line_left_end, line_y),
            )

        if line_right_start < rect.right - 20:
            pygame.draw.line(
                screen,
                self.theme.text_disabled,
                (line_right_start, line_y),
                (rect.right - 20, line_y),
            )

        return rect


# Default instance
menu_item = MenuItem()
