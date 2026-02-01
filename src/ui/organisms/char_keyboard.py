"""
Character keyboard organism - On-screen character selection.
"""

import pygame
from typing import List, Tuple, Optional

from ui.theme import Theme, default_theme
from ui.molecules.char_button import CharButton
from ui.atoms.text import Text


class CharKeyboard:
    """
    Character keyboard organism.

    On-screen keyboard for text input on devices
    without physical keyboards.
    """

    # Default character set
    CHARS_ALPHA = list("abcdefghijklmnopqrstuvwxyz")
    CHARS_NUMERIC = list("0123456789")
    CHARS_SPECIAL = [" ", "DEL", "CLEAR", "DONE"]

    # URL-friendly characters
    CHARS_URL = list("abcdefghijklmnopqrstuvwxyz0123456789.:/-_")
    CHARS_URL_SPECIAL = [" ", "DEL", "CLEAR", "DONE"]

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.char_button = CharButton(theme)
        self.text = Text(theme)

    def render(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        current_text: str,
        selected_index: int,
        chars_per_row: int = 13,
        char_set: str = "default",  # "default" or "url"
        show_input_field: bool = True
    ) -> Tuple[List[Tuple[pygame.Rect, int, str]], pygame.Rect]:
        """
        Render a character keyboard.

        Args:
            screen: Surface to render to
            rect: Keyboard area rectangle
            current_text: Current input text
            selected_index: Currently selected character index
            chars_per_row: Characters per row
            char_set: Character set to use
            show_input_field: Show text input field

        Returns:
            Tuple of (list of (rect, index, char) tuples, input_field_rect)
        """
        # Get character set
        if char_set == "url":
            chars = self.CHARS_URL + self.CHARS_URL_SPECIAL
        else:
            chars = self.CHARS_ALPHA + self.CHARS_NUMERIC + self.CHARS_SPECIAL

        padding = self.theme.padding_sm
        input_field_rect = pygame.Rect(0, 0, 0, 0)

        # Calculate button size
        button_size = min(
            (rect.width - padding * 2) // chars_per_row - padding,
            40
        )

        # Calculate total keyboard width
        keyboard_width = chars_per_row * (button_size + padding) - padding

        # Start position (centered)
        start_x = rect.left + (rect.width - keyboard_width) // 2
        y = rect.top + padding

        # Draw input field if enabled
        if show_input_field:
            field_height = 40
            input_field_rect = pygame.Rect(
                start_x,
                y,
                keyboard_width,
                field_height
            )

            # Draw field background
            pygame.draw.rect(
                screen,
                self.theme.surface_hover,
                input_field_rect,
                border_radius=self.theme.radius_sm
            )

            # Draw text
            display_text = current_text if current_text else "Type here..."
            text_color = self.theme.text_primary if current_text else self.theme.text_disabled
            self.text.render(
                screen,
                display_text,
                (input_field_rect.left + padding, input_field_rect.centery - 4),
                color=text_color,
                size=self.theme.font_size_md,
                max_width=input_field_rect.width - padding * 2
            )

            # Draw cursor
            if current_text:
                cursor_x = input_field_rect.left + padding + self.text.measure(
                    current_text, self.theme.font_size_md
                )[0] + 2
                pygame.draw.line(
                    screen,
                    self.theme.primary,
                    (cursor_x, input_field_rect.top + 8),
                    (cursor_x, input_field_rect.bottom - 8),
                    2
                )

            y = input_field_rect.bottom + padding * 2

        # Render character buttons
        char_rects = []
        x = start_x
        row_start_idx = 0

        for i, char in enumerate(chars):
            # Check for row wrap
            if i > 0 and i % chars_per_row == 0:
                x = start_x
                y += button_size + padding

            char_rect = pygame.Rect(x, y, button_size, button_size)

            # Determine if special button
            special = len(char) > 1 or char == " "

            self.char_button.render(
                screen, char_rect, char,
                selected=(i == selected_index),
                special=special
            )

            char_rects.append((char_rect, i, char))
            x += button_size + padding

        return char_rects, input_field_rect

    def get_char_at_index(
        self,
        index: int,
        char_set: str = "default"
    ) -> str:
        """
        Get character at given index.

        Args:
            index: Character index
            char_set: Character set

        Returns:
            Character at index
        """
        if char_set == "url":
            chars = self.CHARS_URL + self.CHARS_URL_SPECIAL
        else:
            chars = self.CHARS_ALPHA + self.CHARS_NUMERIC + self.CHARS_SPECIAL

        if 0 <= index < len(chars):
            return chars[index]
        return ""

    def get_total_chars(self, char_set: str = "default") -> int:
        """
        Get total number of characters in set.

        Args:
            char_set: Character set

        Returns:
            Number of characters
        """
        if char_set == "url":
            return len(self.CHARS_URL) + len(self.CHARS_URL_SPECIAL)
        return len(self.CHARS_ALPHA) + len(self.CHARS_NUMERIC) + len(self.CHARS_SPECIAL)

    def handle_selection(
        self,
        index: int,
        current_text: str,
        char_set: str = "default"
    ) -> Tuple[str, bool]:
        """
        Handle character selection.

        Args:
            index: Selected character index
            current_text: Current input text
            char_set: Character set

        Returns:
            Tuple of (new_text, is_done)
        """
        char = self.get_char_at_index(index, char_set)

        if char == "DEL":
            return current_text[:-1] if current_text else "", False
        elif char == "CLEAR":
            return "", False
        elif char == "DONE":
            return current_text, True
        elif char == " ":
            return current_text + " ", False
        else:
            return current_text + char, False


# Default instance
char_keyboard = CharKeyboard()
