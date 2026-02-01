"""
URL input modal - URL text input with keyboard.
"""

import pygame
from typing import Tuple, List, Optional

from ui.theme import Theme, default_theme
from ui.organisms.modal_frame import ModalFrame
from ui.organisms.char_keyboard import CharKeyboard


class UrlInputModal:
    """
    URL input modal.

    On-screen keyboard for entering URLs.
    Uses char_set="url" for URL-friendly characters (includes :/.-)
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.modal_frame = ModalFrame(theme)
        self.char_keyboard = CharKeyboard(theme)

    def render(
        self,
        screen: pygame.Surface,
        input_text: str,
        cursor_position: int,
        context: str = "archive_json"
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple]]:
        """
        Render the URL input modal.

        Args:
            screen: Surface to render to
            input_text: Current input text
            cursor_position: Currently selected character index
            context: Context for title ("archive_json" or "direct_download")

        Returns:
            Tuple of (modal_rect, content_rect, close_rect, char_rects)
        """
        # Calculate modal size (slightly larger for URL chars)
        width = min(650, screen.get_width() - 40)
        height = 380

        # Determine title based on context
        if context == "direct_download":
            title = "Download from URL"
        else:
            title = "Enter Archive URL"

        # Render modal frame
        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height,
            title=title,
            show_close=True
        )

        # Render character keyboard with URL charset
        char_rects, input_rect = self.char_keyboard.render(
            screen, content_rect,
            current_text=input_text,
            selected_index=cursor_position,
            chars_per_row=13,
            char_set="url",
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
            current_text: Current input text

        Returns:
            Tuple of (new_text, is_done)
        """
        return self.char_keyboard.handle_selection(
            cursor_position, current_text, char_set="url"
        )


# Default instance
url_input_modal = UrlInputModal()
