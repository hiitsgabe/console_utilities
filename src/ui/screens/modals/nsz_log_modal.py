"""
NSZ log viewer modal.

Shows captured NSZ decompression diagnostics in a scrollable view with a
"Save to error.log" action. Used after an NSZ extraction fails so the logs are
visible in-app even when the nsz.log file is unreachable.
"""

import pygame
from typing import List, Tuple

from ui.theme import Theme, default_theme
from ui.templates.modal_template import ModalTemplate
from ui.atoms.text import Text


class NszLogModal:
    """Scrollable NSZ log viewer with Save/Close actions."""

    WIDTH = 660
    HEIGHT = 360
    LINE_HEIGHT = 18

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.modal_template = ModalTemplate(theme)
        self.text = Text(theme)

    # Vertical space taken by the title bar above the log content.
    TITLE_ALLOWANCE = 50

    def _visible_lines(self) -> int:
        """Number of log lines that fit in the content area.

        Conservative (accounts for the title bar) so the newest line at the
        bottom of the scroll is fully visible rather than clipped behind the
        button row.
        """
        usable = self.HEIGHT - self.TITLE_ALLOWANCE - self.theme.padding_md * 2
        return max(1, usable // self.LINE_HEIGHT)

    def max_scroll_offset(self, lines: List[str]) -> int:
        """Largest valid top-line index so the last line stays visible."""
        return max(0, len(lines) - self._visible_lines())

    def render(
        self,
        screen: pygame.Surface,
        lines: List[str],
        scroll_offset: int = 0,
        button_index: int = 0,
    ) -> Tuple[pygame.Rect, pygame.Rect, pygame.Rect]:
        """
        Render the NSZ log modal.

        Args:
            screen: Surface to render to
            lines: Log lines to display (oldest first)
            scroll_offset: Index of the first visible line
            button_index: Focused button (0 = Refresh, 1 = Close)

        Returns:
            Tuple of (modal_rect, refresh_button_rect, close_button_rect)
        """
        # Focused button gets the primary style; the other stays secondary.
        refresh_style = "primary" if button_index == 0 else "secondary"
        close_style = "primary" if button_index == 1 else "secondary"
        buttons = [
            ("Refresh", refresh_style),
            ("Close", close_style),
        ]

        modal_rect, content_rect, _close_rect, button_rects = (
            self.modal_template.render(
                screen,
                self.WIDTH,
                self.HEIGHT,
                title="NSZ / Extraction Log (error.log)",
                show_close=False,
                buttons=buttons,
            )
        )

        visible = self._visible_lines()
        max_offset = self.max_scroll_offset(lines)
        offset = max(0, min(scroll_offset, max_offset))

        if not lines:
            self.text.render(
                screen,
                "No NSZ log entries captured yet.",
                (content_rect.left, content_rect.top),
                color=self.theme.text_secondary,
                size=self.theme.font_size_sm,
                max_width=content_rect.width,
            )
        else:
            prev_clip = screen.get_clip()
            screen.set_clip(content_rect)
            y = content_rect.top
            for line in lines[offset:offset + visible]:
                self.text.render(
                    screen,
                    line if line else " ",
                    (content_rect.left, y),
                    color=self.theme.text_primary,
                    size=self.theme.font_size_xs,
                    max_width=content_rect.width,
                )
                y += self.LINE_HEIGHT
            screen.set_clip(prev_clip)

            # Scroll indicators.
            if offset > 0:
                self._scroll_arrow(screen, content_rect, "up")
            if offset < max_offset:
                self._scroll_arrow(screen, content_rect, "down")

        # Draw an unmistakable focus outline around the selected button so
        # left/right navigation is clearly visible (the primary/secondary
        # styles alone read as too similar on-device).
        focused = button_rects[button_index] if button_rects else None
        if focused is not None:
            pygame.draw.rect(
                screen,
                self.theme.text_primary,
                focused.inflate(6, 6),
                width=2,
                border_radius=self.theme.radius_sm,
            )

        refresh_rect, close_button_rect = button_rects[0], button_rects[1]
        return modal_rect, refresh_rect, close_button_rect

    def _scroll_arrow(
        self, screen: pygame.Surface, content_rect: pygame.Rect, direction: str
    ):
        size = 14
        half = size // 2
        x = content_rect.right - size
        if direction == "up":
            y = content_rect.top
            points = [(x, y), (x - half, y + half), (x + half, y + half)]
        else:
            y = content_rect.bottom - half
            points = [(x - half, y - half), (x + half, y - half), (x, y)]
        pygame.draw.polygon(screen, self.theme.text_secondary, points)


# Default instance
nsz_log_modal = NszLogModal()
