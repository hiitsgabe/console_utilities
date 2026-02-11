"""
Scraper downloads screen - Display batch scraper queue with status.
"""

import pygame
from typing import List, Tuple, Optional, Any

from ui.theme import Theme, default_theme
from ui.organisms.header import Header
from ui.atoms.text import Text
from state import ScraperQueueState, ScraperQueueItem
from utils.button_hints import get_button_hint
from constants import BEZEL_INSET


class ScraperDownloadsScreen:
    """
    Scraper downloads screen.

    Displays the batch scraper queue with status indicators
    for each ROM being scraped.
    """

    ITEM_HEIGHT = 50
    VISIBLE_ITEMS = 8

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.header = Header(theme)
        self.text = Text(theme)

    def render(
        self,
        screen: pygame.Surface,
        queue: ScraperQueueState,
        input_mode: str = "keyboard",
    ) -> Tuple[Optional[pygame.Rect], List[pygame.Rect], int]:
        """
        Render the scraper downloads screen.

        Args:
            screen: Surface to render to
            queue: Scraper queue state
            input_mode: Current input mode

        Returns:
            Tuple of (back_button_rect, item_rects, scroll_offset)
        """
        total_items = len(queue.items)
        right_text = (
            f"{queue.highlighted + 1}/{total_items}" if total_items > 0 else "0/0"
        )

        # Draw header
        header_rect, back_button_rect = self.header.render(
            screen, "Scraper", show_back=True, right_text=right_text
        )

        # Calculate content area
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
            screen, content_rect, queue, scroll_offset
        )

        # Draw footer
        self._render_footer(screen, queue, input_mode)

        return back_button_rect, item_rects, scroll_offset

    def _calculate_scroll_offset(
        self, highlighted: int, total_items: int, content_height: int
    ) -> int:
        """Calculate scroll offset to keep highlighted item visible."""
        visible_items = content_height // self.ITEM_HEIGHT

        if total_items <= visible_items:
            return 0

        half_visible = visible_items // 2
        scroll_offset = max(0, highlighted - half_visible)
        max_offset = total_items - visible_items
        scroll_offset = min(scroll_offset, max_offset)

        return scroll_offset

    def _render_queue_items(
        self,
        screen: pygame.Surface,
        content_rect: pygame.Rect,
        queue: ScraperQueueState,
        scroll_offset: int,
    ) -> List[pygame.Rect]:
        """Render the queue items list."""
        item_rects = []
        visible_items = content_rect.height // self.ITEM_HEIGHT

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
                self.ITEM_HEIGHT - 4,
            )

            is_highlighted = i == queue.highlighted
            self._render_queue_item(screen, item_rect, item, i + 1, is_highlighted)
            item_rects.append(item_rect)

        screen.set_clip(None)

        # Scroll indicators
        if scroll_offset > 0:
            self._draw_scroll_indicator(screen, content_rect, "up")
        if scroll_offset + visible_items < len(queue.items):
            self._draw_scroll_indicator(screen, content_rect, "down")

        return item_rects

    def _render_queue_item(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        item: ScraperQueueItem,
        position: int,
        is_highlighted: bool,
    ):
        """Render a single queue item."""
        padding = self.theme.padding_sm

        # Background
        bg_color = self.theme.primary if is_highlighted else self.theme.surface
        pygame.draw.rect(screen, bg_color, rect, border_radius=self.theme.radius_md)

        # Position number
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

        # ROM name
        name_x = rect.left + pos_width + padding
        name_width = rect.width - pos_width - 200 - padding * 3
        name = self._get_rom_name(item.name)

        self.text.render(
            screen,
            name,
            (name_x, rect.centery),
            color=(
                self.theme.background if is_highlighted else self.theme.text_primary
            ),
            size=self.theme.font_size_md,
            max_width=name_width,
        )

        # Status area (right)
        status_x = rect.right - 190
        status_width = 180
        status_rect = pygame.Rect(
            status_x, rect.top + padding, status_width, rect.height - padding * 2
        )
        self._render_status(screen, item, status_rect, is_highlighted)

    def _render_status(
        self,
        screen: pygame.Surface,
        item: ScraperQueueItem,
        rect: pygame.Rect,
        is_highlighted: bool,
    ):
        """Render status text for an item."""
        if item.status == "pending":
            text = "Waiting"
            color = (
                self.theme.background if is_highlighted else self.theme.text_secondary
            )
        elif item.status == "searching":
            text = "Searching..."
            color = self.theme.background if is_highlighted else self.theme.warning
        elif item.status == "downloading":
            text = "Downloading..."
            color = self.theme.background if is_highlighted else self.theme.warning
        elif item.status == "done":
            text = "Done"
            color = self.theme.background if is_highlighted else self.theme.success
        elif item.status == "error":
            text = item.error[:20] if item.error else "Error"
            color = self.theme.background if is_highlighted else self.theme.error
        elif item.status == "skipped":
            if item.skip_reason == "image_exists":
                text = "Already has images"
                color = (
                    self.theme.background
                    if is_highlighted
                    else self.theme.text_disabled
                )
            elif item.skip_reason == "cancelled":
                text = "Cancelled"
                color = (
                    self.theme.background
                    if is_highlighted
                    else self.theme.text_disabled
                )
            else:
                text = "Skipped"
                color = (
                    self.theme.background
                    if is_highlighted
                    else self.theme.text_disabled
                )
        else:
            text = item.status
            color = (
                self.theme.background if is_highlighted else self.theme.text_secondary
            )

        self.text.render(
            screen,
            text,
            (rect.centerx, rect.centery),
            color=color,
            size=self.theme.font_size_sm,
            align="center",
        )

    def _render_footer(
        self,
        screen: pygame.Surface,
        queue: ScraperQueueState,
        input_mode: str = "keyboard",
    ):
        """Render footer hints."""
        screen_width, screen_height = screen.get_size()
        inset = BEZEL_INSET
        safe_width = screen_width - inset * 2
        bar_height = 40
        bar_y = screen_height - inset - bar_height

        # Semi-transparent background
        bar_surface = pygame.Surface((safe_width, bar_height), pygame.SRCALPHA)
        bar_surface.fill((*self.theme.surface[:3], 230))
        screen.blit(bar_surface, (inset, bar_y))

        # Left: completion status
        done = sum(
            1 for item in queue.items if item.status in ("done", "error", "skipped")
        )
        total = len(queue.items)
        status_text = f"{done}/{total} completed"
        self.text.render(
            screen,
            status_text,
            (inset + self.theme.padding_md, bar_y + bar_height // 2),
            color=self.theme.secondary,
            size=self.theme.font_size_sm,
            align="left",
        )

        # Right: back hint
        hint_text = get_button_hint("back", "Back", input_mode)
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

    def _get_rom_name(self, name: str) -> str:
        """Extract display name from ROM filename."""
        if "." in name:
            name = name.rsplit(".", 1)[0]
        return name
