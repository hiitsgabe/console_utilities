"""
Search modal - Text input for searching games.
"""

import pygame
from typing import Tuple, List, Optional

from ui.theme import Theme, default_theme
from ui.organisms.modal_frame import ModalFrame
from ui.organisms.char_keyboard import CharKeyboard


class SearchModal:
    """
    Search modal.

    On-screen keyboard for entering search queries.
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.modal_frame = ModalFrame(theme)
        self.char_keyboard = CharKeyboard(theme)

    def render(
        self,
        screen: pygame.Surface,
        search_text: str,
        cursor_position: int
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple]]:
        """
        Render the search modal.

        Args:
            screen: Surface to render to
            search_text: Current search text
            cursor_position: Currently selected character index

        Returns:
            Tuple of (modal_rect, content_rect, close_rect, char_rects)
        """
        # Calculate modal size
        width = min(600, screen.get_width() - 40)
        height = 350

        # Render modal frame
        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height,
            title="Search Games",
            show_close=True
        )

        # Render character keyboard
        char_rects, input_rect = self.char_keyboard.render(
            screen, content_rect,
            current_text=search_text,
            selected_index=cursor_position,
            chars_per_row=13,
            show_input_field=True
        )

        return modal_rect, content_rect, close_rect, char_rects

    def handle_selection(
        self,
        cursor_position: int,
        current_text: str
    ) -> Tuple[str, bool]:
        """
        Handle character selection.

        Args:
            cursor_position: Selected character index
            current_text: Current search text

        Returns:
            Tuple of (new_text, is_done)
        """
        return self.char_keyboard.handle_selection(
            cursor_position, current_text
        )


# Default instance
search_modal = SearchModal()
