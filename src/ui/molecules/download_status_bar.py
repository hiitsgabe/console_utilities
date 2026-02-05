"""
Download status bar molecule - Footer status when downloads are active.
"""

import pygame
from typing import Optional

from ui.theme import Theme, default_theme
from ui.atoms.text import Text
from ui.atoms.progress import ProgressBar
from state import DownloadQueueState


class DownloadStatusBar:
    """
    Download status bar molecule.

    A small status bar rendered at the bottom of non-download
    screens when downloads are active in the background.
    """

    HEIGHT = 30

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.text = Text(theme)
        self.progress_bar = ProgressBar(theme)

    def render(
        self, screen: pygame.Surface, queue: DownloadQueueState
    ) -> Optional[pygame.Rect]:
        """
        Render the download status bar.

        Args:
            screen: Surface to render to
            queue: Download queue state

        Returns:
            Status bar rect if rendered, None otherwise
        """
        # Only render if there are active downloads
        if not self._should_render(queue):
            return None

        screen_width, screen_height = screen.get_size()
        bar_rect = pygame.Rect(
            0, screen_height - self.HEIGHT, screen_width, self.HEIGHT
        )

        # Draw background with top border
        pygame.draw.rect(screen, self.theme.surface, bar_rect)
        pygame.draw.line(
            screen,
            self.theme.surface_hover,
            (0, bar_rect.top),
            (screen_width, bar_rect.top),
        )

        # Calculate progress stats
        total = len(queue.items)
        completed = sum(1 for item in queue.items if item.status == "completed")
        in_progress = sum(
            1
            for item in queue.items
            if item.status in ("downloading", "extracting", "moving")
        )

        # Left side: status text
        if in_progress > 0:
            current = completed + 1
            status_text = f"Downloading {current} of {total} games"
        else:
            waiting = sum(1 for item in queue.items if item.status == "waiting")
            if waiting > 0:
                status_text = f"Queued: {waiting} games"
            else:
                status_text = f"Downloads complete ({completed}/{total})"

        self.text.render(
            screen,
            status_text,
            (self.theme.padding_md, bar_rect.centery),
            color=self.theme.text_primary,
            size=self.theme.font_size_sm,
            align="left",
        )

        # Right side: small progress indicator for active download
        active_item = self._get_active_item(queue)
        if active_item and active_item.status == "downloading":
            # Draw compact progress bar
            bar_width = 100
            bar_height = 10
            progress_rect = pygame.Rect(
                screen_width - self.theme.padding_md - bar_width,
                bar_rect.centery - bar_height // 2,
                bar_width,
                bar_height,
            )
            self.progress_bar.render(
                screen,
                progress_rect,
                active_item.progress,
                fill_color=self.theme.secondary,
            )

        return bar_rect

    def _should_render(self, queue: DownloadQueueState) -> bool:
        """Check if status bar should be rendered."""
        if not queue.items:
            return False

        # Show if any items are in progress or waiting
        for item in queue.items:
            if item.status in ("waiting", "downloading", "extracting", "moving"):
                return True

        return False

    def _get_active_item(self, queue: DownloadQueueState):
        """Get the currently active download item."""
        for item in queue.items:
            if item.status in ("downloading", "extracting", "moving"):
                return item
        return None


# Default instance
download_status_bar = DownloadStatusBar()
