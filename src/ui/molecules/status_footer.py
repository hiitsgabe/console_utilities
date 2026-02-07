"""
Status footer molecule - Generic footer bar for background tasks.

Replaces the download-specific status bar with a reusable component
that can display progress for downloads, scraping, or any background task.
"""

import pygame
from typing import Optional, List

from ui.theme import Theme, Color, default_theme
from ui.atoms.text import Text
from ui.atoms.progress import ProgressBar
from constants import BEZEL_INSET


class StatusFooterItem:
    """
    Data for a single status footer entry.

    Attributes:
        label: Status text displayed on the left
        progress: Optional progress value (0.0 to 1.0), None for no bar
        color: Accent color for the progress bar
    """

    def __init__(
        self,
        label: str,
        progress: Optional[float] = None,
        color: Optional[Color] = None,
    ):
        self.label = label
        self.progress = progress
        self.color = color


class StatusFooter:
    """
    Generic status footer molecule.

    Renders one or more stacked status bars at the bottom of the screen.
    Each bar shows a label and optional compact progress indicator.
    """

    BAR_HEIGHT = 30

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.text = Text(theme)
        self.progress_bar = ProgressBar(theme)

    def render(
        self,
        screen: pygame.Surface,
        items: List[StatusFooterItem],
    ) -> int:
        """
        Render stacked status footer bars.

        Args:
            screen: Surface to render to
            items: List of StatusFooterItem to display (bottom-up stacking)

        Returns:
            Total height consumed by all footer bars
        """
        if not items:
            return 0

        screen_width, screen_height = screen.get_size()
        inset = BEZEL_INSET
        safe_width = screen_width - inset * 2
        total_height = len(items) * self.BAR_HEIGHT

        for i, item in enumerate(items):
            # Stack from bottom: last item is at very bottom, above bezel
            bar_y = screen_height - inset - (len(items) - i) * self.BAR_HEIGHT
            bar_rect = pygame.Rect(inset, bar_y, safe_width, self.BAR_HEIGHT)

            # Background with top border
            pygame.draw.rect(screen, self.theme.surface, bar_rect)
            pygame.draw.line(
                screen,
                self.theme.surface_hover,
                (inset, bar_rect.top),
                (inset + safe_width, bar_rect.top),
            )

            # Left side: status text
            self.text.render(
                screen,
                item.label,
                (inset + self.theme.padding_md, bar_rect.centery),
                color=self.theme.text_primary,
                size=self.theme.font_size_sm,
                align="left",
                max_width=safe_width - 140,
            )

            # Right side: compact progress bar (if progress is set)
            if item.progress is not None:
                bar_width = 100
                bar_height = 10
                fill_color = item.color or self.theme.secondary
                progress_rect = pygame.Rect(
                    inset + safe_width - self.theme.padding_md - bar_width,
                    bar_rect.centery - bar_height // 2,
                    bar_width,
                    bar_height,
                )
                self.progress_bar.render(
                    screen,
                    progress_rect,
                    item.progress,
                    fill_color=fill_color,
                )

        return total_height


# Default instance
status_footer = StatusFooter()
