"""
Download progress molecule - Progress bar with stats.
"""

import pygame
from typing import Tuple, Optional

from ui.theme import Theme, Color, default_theme
from ui.atoms.progress import ProgressBar
from ui.atoms.text import Text


class DownloadProgress:
    """
    Download progress molecule.

    Combines a progress bar with download statistics
    (speed, size, percentage).
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.progress_bar = ProgressBar(theme)
        self.text = Text(theme)

    def render(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        progress: float,
        label: str,
        downloaded: int = 0,
        total_size: int = 0,
        speed: float = 0,  # bytes per second
    ) -> pygame.Rect:
        """
        Render download progress with stats.

        Args:
            screen: Surface to render to
            rect: Total area
            progress: Progress (0.0 to 1.0)
            label: Status label (e.g., "Downloading...")
            downloaded: Bytes downloaded
            total_size: Total bytes
            speed: Download speed in bytes/second

        Returns:
            Total rect
        """
        padding = self.theme.padding_sm

        # Calculate layout
        label_height = self.theme.font_size_md
        stats_height = self.theme.font_size_sm
        progress_height = 20

        # Draw label
        label_y = rect.top
        self.text.render(
            screen,
            label,
            (rect.left, label_y),
            color=self.theme.text_primary,
            size=self.theme.font_size_md,
        )

        # Draw progress bar
        progress_y = label_y + label_height + padding
        progress_rect = pygame.Rect(rect.left, progress_y, rect.width, progress_height)
        self.progress_bar.render(screen, progress_rect, progress, show_glow=True)

        # Draw percentage in center of progress bar
        percent_text = f"{int(progress * 100)}%"
        self.text.render(
            screen,
            percent_text,
            progress_rect.center,
            color=self.theme.text_primary,
            size=self.theme.font_size_sm,
            align="center",
        )

        # Draw stats below progress bar
        stats_y = progress_rect.bottom + padding

        # Size stats (left)
        size_text = self._format_size_progress(downloaded, total_size)
        self.text.render(
            screen,
            size_text,
            (rect.left, stats_y),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
        )

        # Speed (right)
        if speed > 0:
            speed_text = self._format_speed(speed)
            self.text.render(
                screen,
                speed_text,
                (rect.right, stats_y),
                color=self.theme.text_secondary,
                size=self.theme.font_size_sm,
                align="right",
            )

        return rect

    def render_compact(
        self, screen: pygame.Surface, rect: pygame.Rect, progress: float, label: str
    ) -> pygame.Rect:
        """
        Render compact progress (just bar and label).

        Args:
            screen: Surface to render to
            rect: Total area
            progress: Progress (0.0 to 1.0)
            label: Status label

        Returns:
            Total rect
        """
        # Draw label on left
        label_width = rect.width // 3
        self.text.render(
            screen,
            label,
            (rect.left, rect.centery - self.theme.font_size_sm // 4),
            color=self.theme.text_primary,
            size=self.theme.font_size_sm,
            max_width=label_width,
        )

        # Draw progress bar on right
        bar_rect = pygame.Rect(
            rect.left + label_width + self.theme.padding_sm,
            rect.centery - 10,
            rect.width - label_width - self.theme.padding_sm,
            20,
        )
        self.progress_bar.render_with_text(screen, bar_rect, progress)

        return rect

    def _format_size(self, size_bytes: int) -> str:
        """Format bytes to human readable."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"

    def _format_size_progress(self, downloaded: int, total: int) -> str:
        """Format download progress as size."""
        if total > 0:
            return f"{self._format_size(downloaded)} / {self._format_size(total)}"
        elif downloaded > 0:
            return self._format_size(downloaded)
        return ""

    def _format_speed(self, bytes_per_second: float) -> str:
        """Format download speed."""
        if bytes_per_second >= 1024 * 1024:
            return f"{bytes_per_second / (1024 * 1024):.1f} MB/s"
        elif bytes_per_second >= 1024:
            return f"{bytes_per_second / 1024:.1f} KB/s"
        else:
            return f"{bytes_per_second:.0f} B/s"


# Default instance
download_progress = DownloadProgress()
