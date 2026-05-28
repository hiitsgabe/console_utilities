"""
System Information screen - OS, device, and storage usage (read-only).
"""

import pygame
from typing import Tuple, Optional, Dict, Any

from ui.theme import Theme, default_theme
from ui.atoms.text import Text
from ui.atoms.progress import ProgressBar
from ui.organisms.header import Header
from utils.button_hints import get_button_hint
from constants import BEZEL_INSET
from services.system_info import format_bytes

SCROLL_STEP = 20
KEY_COLUMN_WIDTH = 160  # px gutter before the value column in key/value rows
BAR_HEIGHT = 12  # px height of usage progress bars


class SystemInfoScreen:
    """Read-only screen showing OS/device basics and per-disk usage bars."""

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.header = Header(theme)
        self.text = Text(theme)
        self.progress = ProgressBar(theme)

    def render(
        self,
        screen: pygame.Surface,
        info: Dict[str, Any],
        scroll_offset: int = 0,
        input_mode: str = "keyboard",
    ) -> Tuple[Optional[pygame.Rect], int]:
        """Render the screen. Returns (back_button_rect, max_scroll)."""
        t = self.theme
        header_height = t.header_height
        _, back_button_rect = self.header.render(
            screen, title="System Information", show_back=True
        )

        inset = BEZEL_INSET
        content_x = inset + t.padding_lg
        content_top = inset + header_height + t.padding_lg
        content_width = screen.get_width() - inset * 2 - t.padding_lg * 2

        hint_height = t.font_size_sm + t.padding_lg
        content_bottom = screen.get_height() - BEZEL_INSET - hint_height
        visible_height = content_bottom - content_top

        clip_rect = pygame.Rect(0, content_top, screen.get_width(), visible_height)
        old_clip = screen.get_clip()
        screen.set_clip(clip_rect)

        y = content_top - scroll_offset

        # --- Device section ---
        y = self._section_title(screen, "DEVICE", content_x, y)
        y = self._kv_row(screen, "OS", info.get("os_name"), content_x, y, content_width)
        y = self._kv_row(
            screen, "Version", info.get("os_version"), content_x, y, content_width
        )
        y = self._kv_row(
            screen, "Host", info.get("hostname"), content_x, y, content_width
        )
        y = self._kv_row(
            screen, "CPU", info.get("cpu_model"), content_x, y, content_width
        )

        # RAM with bar
        ram_total = info.get("ram_total")
        ram_used = info.get("ram_used")
        ram_text = f"{format_bytes(ram_used)} / {format_bytes(ram_total)}"
        y = self._kv_row(screen, "RAM", ram_text, content_x, y, content_width)
        ram_frac = (
            ram_used / ram_total
            if ram_used is not None and ram_total
            else 0.0
        )
        y = self._bar(screen, ram_frac, content_x, y, content_width)

        y += t.padding_md

        # --- Storage section ---
        y = self._section_title(screen, "STORAGE", content_x, y)
        disks = info.get("disks") or []
        if not disks:
            y = self._kv_row(screen, "Disks", "--", content_x, y, content_width)
        for disk in disks:
            usage_text = f"{format_bytes(disk.used)} / {format_bytes(disk.total)}"
            y = self._kv_row(
                screen, disk.label, usage_text, content_x, y, content_width
            )
            frac = disk.used / disk.total if disk.total else 0.0
            y = self._bar(screen, frac, content_x, y, content_width)
            y += t.padding_sm

        screen.set_clip(old_clip)

        total_height = (y + scroll_offset) - content_top
        max_scroll = max(0, total_height - visible_height)

        bottom_y = (
            screen.get_height() - BEZEL_INSET - t.padding_lg - t.font_size_sm
        )
        back_hint = get_button_hint("back", "Back", input_mode)
        self.text.render(
            screen,
            back_hint,
            (screen.get_width() // 2, bottom_y),
            color=t.text_disabled,
            size=t.font_size_sm,
            align="center",
        )

        return back_button_rect, max_scroll

    def _section_title(self, screen: pygame.Surface, label: str, x: int, y: int) -> int:
        self.text.render(
            screen, label, (x, y), color=self.theme.secondary,
            size=self.theme.font_size_md,
        )
        return y + self.theme.font_size_md + self.theme.padding_sm

    def _kv_row(
        self, screen: pygame.Surface, key: str, value, x: int, y: int, width: int
    ) -> int:
        self.text.render(
            screen, f"{key}:", (x, y), color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
        )
        self.text.render(
            screen, str(value) if value else "--", (x + KEY_COLUMN_WIDTH, y),
            color=self.theme.text_primary, size=self.theme.font_size_sm,
            max_width=width - KEY_COLUMN_WIDTH,
        )
        return y + self.theme.font_size_sm + self.theme.padding_xs

    def _bar(
        self, screen: pygame.Surface, frac: float, x: int, y: int, width: int
    ) -> int:
        bar_rect = pygame.Rect(x, y, width, BAR_HEIGHT)
        self.progress.render(
            screen, bar_rect, frac,
            track_color=self.theme.surface,
            fill_color=self.theme.primary,
        )
        return y + BAR_HEIGHT + self.theme.padding_sm


# Default instance
system_info_screen = SystemInfoScreen()
