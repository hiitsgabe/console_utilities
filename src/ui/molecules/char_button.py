"""
Character button molecule - Single character selection button.
"""

import pygame
from typing import Tuple, Optional

from ui.theme import Theme, Color, default_theme
from ui.atoms.text import Text


class CharButton:
    """
    Character button molecule.

    Used in character selection keyboards for text input.
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.text = Text(theme)

    def render(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        char: str,
        selected: bool = False,
        highlighted: bool = False,
        special: bool = False  # For DEL, CLEAR, DONE buttons
    ) -> pygame.Rect:
        """
        Render a character button.

        Args:
            screen: Surface to render to
            rect: Button rectangle
            char: Character to display
            selected: Currently selected
            highlighted: Currently highlighted
            special: Is a special action button

        Returns:
            Button rect
        """
        # Determine colors
        if selected:
            bg_color = self.theme.primary
            text_color = self.theme.text_primary
        elif highlighted:
            bg_color = self.theme.surface_hover
            text_color = self.theme.text_primary
        else:
            bg_color = self.theme.surface
            text_color = self.theme.text_secondary

        # Special buttons get different treatment
        if special and not selected:
            if char == "DONE":
                bg_color = self.theme.secondary_dark
                text_color = self.theme.text_primary
            elif char == "DEL":
                bg_color = self.theme.error
                text_color = self.theme.text_primary
            elif char == "CLEAR":
                bg_color = self.theme.warning
                text_color = self.theme.background

        # Draw background
        pygame.draw.rect(
            screen, bg_color, rect,
            border_radius=self.theme.radius_sm
        )

        # Draw border if selected
        if selected:
            pygame.draw.rect(
                screen,
                self.theme.primary_light,
                rect,
                width=2,
                border_radius=self.theme.radius_sm
            )

        # Determine display text and font size
        if char == " ":
            display_text = "SPC"
            font_size = int(self.theme.font_size_sm * 0.8)
        elif len(char) > 1:  # DEL, CLEAR, DONE
            display_text = char
            font_size = int(self.theme.font_size_sm * 0.7)
        else:
            display_text = char.upper()
            font_size = self.theme.font_size_md

        # Draw character - center both horizontally and vertically
        text_width, text_height = self.text.measure(display_text, font_size)
        text_y = rect.centery - text_height // 2
        self.text.render(
            screen,
            display_text,
            (rect.centerx, text_y),
            color=text_color,
            size=font_size,
            align="center"
        )

        return rect

    def render_keyboard_row(
        self,
        screen: pygame.Surface,
        start_pos: Tuple[int, int],
        chars: list,
        button_size: int,
        spacing: int,
        selected_index: int,
        start_index: int = 0
    ) -> list:
        """
        Render a row of character buttons.

        Args:
            screen: Surface to render to
            start_pos: (x, y) start position
            chars: List of characters
            button_size: Size of each button
            spacing: Space between buttons
            selected_index: Currently selected index (absolute)
            start_index: Index of first char in this row

        Returns:
            List of (rect, char_index, char) tuples
        """
        x, y = start_pos
        rects = []

        for i, char in enumerate(chars):
            char_index = start_index + i
            rect = pygame.Rect(x, y, button_size, button_size)

            special = len(char) > 1 or char == " "

            self.render(
                screen, rect, char,
                selected=(char_index == selected_index),
                special=special
            )

            rects.append((rect, char_index, char))
            x += button_size + spacing

        return rects


# Default instance
char_button = CharButton()
