"""
Downloads screen - Display download queue with progress.
"""

import pygame
from typing import List, Tuple, Optional, Callable, Any

from ui.theme import Theme, default_theme
from ui.organisms.header import Header
from ui.atoms.text import Text
from ui.atoms.progress import ProgressBar
from state import DownloadQueueState, DownloadQueueItem
from utils.button_hints import get_button_hint
from constants import BEZEL_INSET


class DownloadsScreen:
    """
    Downloads screen.

    Displays the download queue with progress bars,
    status indicators, and queue management.
    """

    ITEM_HEIGHT = 70
    VISIBLE_ITEMS = 6

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.header = Header(theme)
        self.text = Text(theme)
        self.progress_bar = ProgressBar(theme)

    def render(
        self,
        screen: pygame.Surface,
        queue: DownloadQueueState,
        get_thumbnail: Optional[Callable[[Any], pygame.Surface]] = None,
        input_mode: str = "keyboard",
    ) -> Tuple[Optional[pygame.Rect], List[pygame.Rect], int]:
        """
        Render the downloads screen.

        Args:
            screen: Surface to render to
            queue: Download queue state
            get_thumbnail: Optional function to get game thumbnails
            input_mode: Current input mode ("keyboard", "gamepad", "touch")

        Returns:
            Tuple of (back_button_rect, item_rects, scroll_offset)
        """
        total_items = len(queue.items)
        right_text = (
            f"{queue.highlighted + 1}/{total_items}" if total_items > 0 else "0/0"
        )

        # Draw header
        header_rect, back_button_rect = self.header.render(
            screen, "Downloads", show_back=True, right_text=right_text
        )

        # Calculate content area (inset from bezel on all sides)
        header_height = 60
        footer_height = 40
        inset = BEZEL_INSET
        content_rect = pygame.Rect(
            inset + self.theme.padding_sm,
            inset + header_height + self.theme.padding_sm,
            screen.get_width() - inset * 2 - self.theme.padding_sm * 2,
            screen.get_height()
            - inset * 2
            - header_height
            - self.theme.padding_sm * 2
            - footer_height,
        )

        # Calculate scroll offset
        scroll_offset = self._calculate_scroll_offset(
            queue.highlighted, total_items, content_rect.height
        )

        # Draw queue items
        item_rects = self._render_queue_items(
            screen, content_rect, queue, scroll_offset, get_thumbnail
        )

        # Draw footer hints
        self._render_footer(screen, queue, input_mode)

        return back_button_rect, item_rects, scroll_offset

    def _calculate_scroll_offset(
        self, highlighted: int, total_items: int, content_height: int
    ) -> int:
        """Calculate scroll offset to keep highlighted item visible."""
        visible_items = content_height // self.ITEM_HEIGHT

        if total_items <= visible_items:
            return 0

        # Keep highlighted item centered when possible
        half_visible = visible_items // 2
        scroll_offset = max(0, highlighted - half_visible)
        max_offset = total_items - visible_items
        scroll_offset = min(scroll_offset, max_offset)

        return scroll_offset

    def _render_queue_items(
        self,
        screen: pygame.Surface,
        content_rect: pygame.Rect,
        queue: DownloadQueueState,
        scroll_offset: int,
        get_thumbnail: Optional[Callable],
    ) -> List[pygame.Rect]:
        """Render the queue items list."""
        item_rects = []
        visible_items = content_rect.height // self.ITEM_HEIGHT

        # Create a clipping surface
        clip_rect = content_rect
        screen.set_clip(clip_rect)

        for i, item in enumerate(queue.items):
            if i < scroll_offset:
                continue
            if i >= scroll_offset + visible_items + 1:
                break

            y_pos = content_rect.top + (i - scroll_offset) * self.ITEM_HEIGHT
            item_rect = pygame.Rect(
                content_rect.left,
                y_pos,
                content_rect.width,
                self.ITEM_HEIGHT - 4,  # 4px spacing
            )

            is_highlighted = i == queue.highlighted
            self._render_queue_item(
                screen, item_rect, item, i + 1, is_highlighted, get_thumbnail
            )
            item_rects.append(item_rect)

        screen.set_clip(None)

        # Draw scroll indicators if needed
        if scroll_offset > 0:
            self._draw_scroll_indicator(screen, content_rect, "up")
        if scroll_offset + visible_items < len(queue.items):
            self._draw_scroll_indicator(screen, content_rect, "down")

        return item_rects

    def _render_queue_item(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        item: DownloadQueueItem,
        position: int,
        is_highlighted: bool,
        get_thumbnail: Optional[Callable],
    ):
        """Render a single queue item."""
        padding = self.theme.padding_sm

        # Draw background
        bg_color = self.theme.primary if is_highlighted else self.theme.surface
        pygame.draw.rect(screen, bg_color, rect, border_radius=self.theme.radius_md)

        # Layout:
        # [#pos] [thumbnail] [name + system] [status area]

        # Position number (left, small)
        pos_text = f"#{position}"
        pos_width = 40
        self.text.render(
            screen,
            pos_text,
            (rect.left + padding, rect.centery),
            color=(
                self.theme.text_secondary
                if not is_highlighted
                else self.theme.background
            ),
            size=self.theme.font_size_sm,
            align="left",
        )

        # Thumbnail (48x48)
        thumb_size = 48
        thumb_x = rect.left + pos_width + padding
        thumb_y = rect.centery - thumb_size // 2
        thumb_rect = pygame.Rect(thumb_x, thumb_y, thumb_size, thumb_size)

        # Draw thumbnail placeholder
        pygame.draw.rect(
            screen,
            self.theme.surface_hover,
            thumb_rect,
            border_radius=self.theme.radius_sm,
        )

        # Try to get actual thumbnail (pass system_data for boxart URL)
        if get_thumbnail:
            try:
                thumbnail = get_thumbnail(item.game, item.system_data)
                if thumbnail:
                    scaled = pygame.transform.scale(thumbnail, (thumb_size, thumb_size))
                    screen.blit(scaled, thumb_rect)
            except Exception:
                pass

        # Name and system (middle section)
        name_x = thumb_rect.right + padding
        name_width = rect.width // 2 - name_x + rect.left
        name = self._get_game_name(item.game)

        self.text.render(
            screen,
            name,
            (name_x, rect.centery - 10),
            color=(
                self.theme.background
                if is_highlighted
                else self.theme.text_primary
            ),
            size=self.theme.font_size_md,
            max_width=name_width,
        )

        self.text.render(
            screen,
            item.system_name,
            (name_x, rect.centery + 12),
            color=(
                self.theme.text_secondary
                if not is_highlighted
                else self.theme.background
            ),
            size=self.theme.font_size_sm,
        )

        # Status area (right section)
        status_x = rect.right - 200
        status_width = 190

        self._render_status_area(
            screen,
            item,
            pygame.Rect(
                status_x, rect.top + padding, status_width, rect.height - padding * 2
            ),
            is_highlighted,
        )

    def _render_status_area(
        self,
        screen: pygame.Surface,
        item: DownloadQueueItem,
        rect: pygame.Rect,
        is_highlighted: bool,
    ):
        """Render the status area for an item."""
        if item.status == "downloading":
            # Progress bar with percentage and speed
            bar_rect = pygame.Rect(rect.left, rect.centery - 8, rect.width - 60, 16)
            self.progress_bar.render_with_text(
                screen, bar_rect, item.progress, fill_color=self.theme.secondary
            )

            # Speed
            speed_text = self._format_speed(item.speed)
            self.text.render(
                screen,
                speed_text,
                (rect.right, rect.centery),
                color=self.theme.text_secondary,
                size=self.theme.font_size_xs,
                align="right",
            )

        elif item.status == "extracting":
            # Indeterminate progress or text
            self.text.render(
                screen,
                "Extracting...",
                (rect.centerx, rect.centery),
                color=self.theme.warning,
                size=self.theme.font_size_sm,
                align="center",
            )

        elif item.status == "moving":
            self.text.render(
                screen,
                "Moving files...",
                (rect.centerx, rect.centery),
                color=self.theme.warning,
                size=self.theme.font_size_sm,
                align="center",
            )

        elif item.status == "waiting":
            self.text.render(
                screen,
                "Waiting",
                (rect.centerx, rect.centery),
                color=self.theme.text_secondary,
                size=self.theme.font_size_sm,
                align="center",
            )

        elif item.status == "completed":
            self.text.render(
                screen,
                "Done",
                (rect.centerx, rect.centery),
                color=self.theme.success,
                size=self.theme.font_size_sm,
                align="center",
            )

        elif item.status == "failed":
            error_text = item.error[:20] if item.error else "Failed"
            self.text.render(
                screen,
                error_text,
                (rect.centerx, rect.centery),
                color=self.theme.error,
                size=self.theme.font_size_sm,
                align="center",
            )

        elif item.status == "cancelled":
            self.text.render(
                screen,
                "Cancelled",
                (rect.centerx, rect.centery),
                color=self.theme.text_disabled,
                size=self.theme.font_size_sm,
                align="center",
            )

    def _render_footer(
        self,
        screen: pygame.Surface,
        queue: DownloadQueueState,
        input_mode: str = "keyboard",
    ):
        """Render footer hints."""
        screen_width, screen_height = screen.get_size()
        inset = BEZEL_INSET
        safe_width = screen_width - inset * 2
        bar_height = 40
        bar_y = screen_height - inset - bar_height

        # Draw semi-transparent background
        bar_surface = pygame.Surface((safe_width, bar_height), pygame.SRCALPHA)
        bar_surface.fill((*self.theme.surface[:3], 230))
        screen.blit(bar_surface, (inset, bar_y))

        # Left side: status summary
        completed = sum(1 for item in queue.items if item.status == "completed")
        total = len(queue.items)
        status_text = f"{completed}/{total} completed"
        self.text.render(
            screen,
            status_text,
            (inset + self.theme.padding_md, bar_y + bar_height // 2),
            color=self.theme.secondary,
            size=self.theme.font_size_sm,
            align="left",
        )

        # Right side: hints based on highlighted item status
        hints = []
        if queue.items and 0 <= queue.highlighted < len(queue.items):
            item = queue.items[queue.highlighted]
            if item.status == "waiting":
                hints.append(get_button_hint("select", "Remove", input_mode))

        hints.append(get_button_hint("back", "Back", input_mode))
        hint_text = " | ".join(hints)

        self.text.render(
            screen,
            hint_text,
            (
                screen_width - inset - self.theme.padding_md,
                bar_y + bar_height // 2,
            ),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
            align="right",
        )

    def _draw_scroll_indicator(
        self, screen: pygame.Surface, content_rect: pygame.Rect, direction: str
    ):
        """Draw scroll indicator arrow."""
        arrow_size = 20
        x = content_rect.centerx

        if direction == "up":
            y = content_rect.top + 5
            points = [
                (x, y),
                (x - arrow_size // 2, y + arrow_size // 2),
                (x + arrow_size // 2, y + arrow_size // 2),
            ]
        else:
            y = content_rect.bottom - 5
            points = [
                (x - arrow_size // 2, y - arrow_size // 2),
                (x + arrow_size // 2, y - arrow_size // 2),
                (x, y),
            ]

        pygame.draw.polygon(screen, self.theme.text_secondary, points)

    def _get_game_name(self, game: Any) -> str:
        """Extract display name from game."""
        if isinstance(game, dict):
            name = game.get("filename", game.get("name", str(game)))
        else:
            name = str(game)

        # Remove file extension for display
        if "." in name:
            name = name.rsplit(".", 1)[0]

        return name

    def _format_speed(self, bytes_per_second: float) -> str:
        """Format download speed."""
        if bytes_per_second >= 1024 * 1024:
            return f"{bytes_per_second / (1024 * 1024):.1f} MB/s"
        elif bytes_per_second >= 1024:
            return f"{bytes_per_second / 1024:.1f} KB/s"
        else:
            return f"{bytes_per_second:.0f} B/s"


# Default instance
downloads_screen = DownloadsScreen()
