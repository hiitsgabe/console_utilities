"""
Credits screen - Application credits and information.
"""

import pygame
from typing import Tuple, Optional

from ui.theme import Theme, default_theme
from ui.atoms.text import Text
from ui.organisms.header import Header
from utils.button_hints import get_button_hint
from constants import BEZEL_INSET, APP_VERSION, BUILD_TARGET

SCROLL_STEP = 20


class CreditsScreen:
    """
    Credits screen.

    Displays application credits, version info,
    and legal disclaimers with D-pad scrolling.
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.header = Header(theme)
        self.text = Text(theme)
        self.total_content_height = 0

    def render(
        self,
        screen: pygame.Surface,
        input_mode: str = "keyboard",
        scroll_offset: int = 0,
    ) -> Tuple[Optional[pygame.Rect], int]:
        """
        Render the credits screen.

        Args:
            screen: Surface to render to
            input_mode: Current input mode
            scroll_offset: Pixel scroll offset

        Returns:
            Tuple of (back_button_rect, max_scroll)
        """
        # Draw header
        header_height = 60
        _, back_button_rect = self.header.render(
            screen, title="Credits", show_back=True
        )

        # Content area (inset from bezel)
        inset = BEZEL_INSET
        content_x = inset + self.theme.padding_lg
        content_top = inset + header_height + self.theme.padding_lg
        content_width = screen.get_width() - inset * 2 - self.theme.padding_lg * 2

        # Bottom hint area
        hint_height = self.theme.font_size_sm + self.theme.padding_lg
        content_bottom = screen.get_height() - BEZEL_INSET - hint_height
        visible_height = content_bottom - content_top

        # Set clipping rect for scrollable area
        clip_rect = pygame.Rect(0, content_top, screen.get_width(), visible_height)
        old_clip = screen.get_clip()
        screen.set_clip(clip_rect)

        # Draw content with scroll offset
        y = content_top - scroll_offset

        # App title
        self.text.render(
            screen,
            "Console Utilities",
            (content_x, y),
            color=self.theme.primary,
            size=self.theme.font_size_xl,
        )
        y += self.theme.font_size_xl + self.theme.padding_sm

        # Version and build target
        version_text = f"Version {APP_VERSION}"
        if BUILD_TARGET != "source":
            version_text += f" ({BUILD_TARGET})"
        self.text.render(
            screen,
            version_text,
            (content_x, y),
            color=self.theme.text_secondary,
            size=self.theme.font_size_md,
        )
        y += self.theme.font_size_md + self.theme.padding_lg

        # Description
        description = [
            "A download management tool for handheld",
            "gaming consoles.",
            "",
            "Designed for Knulli RG35xxSP and Odin 2 Android using Emulation Station, should work on similar devices.",
            "",
        ]

        for line in description:
            if line:
                self.text.render(
                    screen,
                    line,
                    (content_x, y),
                    color=self.theme.text_primary,
                    size=self.theme.font_size_sm,
                    max_width=content_width,
                )
            y += self.theme.font_size_sm + 4

        y += self.theme.padding_md

        # Legal disclaimer
        self.text.render(
            screen,
            "LEGAL DISCLAIMER",
            (content_x, y),
            color=self.theme.warning,
            size=self.theme.font_size_md,
        )
        y += self.theme.font_size_md + self.theme.padding_sm

        disclaimer = [
            "This application is a download management",
            "tool only. It contains no game data or",
            "copyrighted content.",
            "",
            "Users must only download content they",
            "legally own. The developers are not",
            "responsible for misuse.",
        ]

        for line in disclaimer:
            if line:
                self.text.render(
                    screen,
                    line,
                    (content_x, y),
                    color=self.theme.text_secondary,
                    size=self.theme.font_size_sm,
                    max_width=content_width,
                )
            y += self.theme.font_size_sm + 4

        # Restore clipping
        screen.set_clip(old_clip)

        # Calculate total content height and max scroll
        total_height = (y + scroll_offset) - content_top
        self.total_content_height = total_height
        max_scroll = max(0, total_height - visible_height)

        # Bottom hint text (outside clipped area)
        bottom_y = (
            screen.get_height()
            - BEZEL_INSET
            - self.theme.padding_lg
            - self.theme.font_size_sm
        )
        back_hint = get_button_hint("back", "Back", input_mode)
        self.text.render(
            screen,
            back_hint,
            (screen.get_width() // 2, bottom_y),
            color=self.theme.text_disabled,
            size=self.theme.font_size_sm,
            align="center",
        )

        return back_button_rect, max_scroll


# Default instance
credits_screen = CreditsScreen()
