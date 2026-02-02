"""
Credits screen - Application credits and information.
"""

import pygame
from typing import Tuple, Optional

from ui.theme import Theme, default_theme
from ui.atoms.text import Text
from ui.organisms.header import Header


class CreditsScreen:
    """
    Credits screen.

    Displays application credits, version info,
    and legal disclaimers.
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.header = Header(theme)
        self.text = Text(theme)

    def render(
        self,
        screen: pygame.Surface,
        version: str = "1.0.0"
    ) -> Optional[pygame.Rect]:
        """
        Render the credits screen.

        Args:
            screen: Surface to render to
            version: Application version

        Returns:
            Back button rect
        """
        # Draw header
        header_height = 60
        _, back_button_rect = self.header.render(
            screen,
            title="Credits",
            show_back=True
        )

        # Content area
        content_x = self.theme.padding_lg
        content_y = header_height + self.theme.padding_lg
        content_width = screen.get_width() - self.theme.padding_lg * 2

        # App title
        self.text.render(
            screen,
            "Console Utilities",
            (content_x, content_y),
            color=self.theme.primary,
            size=self.theme.font_size_xl
        )
        content_y += self.theme.font_size_xl + self.theme.padding_sm

        # Version
        self.text.render(
            screen,
            f"Version {version}",
            (content_x, content_y),
            color=self.theme.text_secondary,
            size=self.theme.font_size_md
        )
        content_y += self.theme.font_size_md + self.theme.padding_lg

        # Description
        description = [
            "A download management tool for handheld gaming consoles.",
            "",
            "Designed for Knulli RG35xxSP and similar devices.",
            "",
        ]

        for line in description:
            if line:
                self.text.render(
                    screen,
                    line,
                    (content_x, content_y),
                    color=self.theme.text_primary,
                    size=self.theme.font_size_sm,
                    max_width=content_width
                )
            content_y += self.theme.font_size_sm + 4

        content_y += self.theme.padding_md

        # Legal disclaimer
        self.text.render(
            screen,
            "LEGAL DISCLAIMER",
            (content_x, content_y),
            color=self.theme.warning,
            size=self.theme.font_size_md
        )
        content_y += self.theme.font_size_md + self.theme.padding_sm

        disclaimer = [
            "This application is a download management tool only.",
            "It contains no game data or copyrighted content.",
            "",
            "Users must only download content they legally own.",
            "The developers are not responsible for misuse.",
        ]

        for line in disclaimer:
            if line:
                self.text.render(
                    screen,
                    line,
                    (content_x, content_y),
                    color=self.theme.text_secondary,
                    size=self.theme.font_size_sm,
                    max_width=content_width
                )
            content_y += self.theme.font_size_sm + 4

        # Bottom text
        bottom_y = screen.get_height() - self.theme.padding_lg - self.theme.font_size_sm
        self.text.render(
            screen,
            "Press B to go back",
            (screen.get_width() // 2, bottom_y),
            color=self.theme.text_disabled,
            size=self.theme.font_size_sm,
            align="center"
        )

        return back_button_rect


# Default instance
credits_screen = CreditsScreen()
