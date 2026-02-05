"""
URL input modal - URL text input with keyboard.
"""

import pygame
from typing import Tuple, List, Optional

from ui.theme import Theme, default_theme
from ui.organisms.modal_frame import ModalFrame
from ui.organisms.char_keyboard import CharKeyboard
from ui.atoms.text import Text
from utils.button_hints import get_combined_hints


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
        self.text = Text(theme)

    def render(
        self,
        screen: pygame.Surface,
        input_text: str,
        cursor_position: int,
        context: str = "archive_json",
        input_mode: str = "keyboard",
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple]]:
        """
        Render the URL input modal.

        Args:
            screen: Surface to render to
            input_text: Current input text
            cursor_position: Currently selected character index
            context: Context for title ("archive_json" or "direct_download")
            input_mode: Current input mode ("keyboard", "gamepad", "touch")

        Returns:
            Tuple of (modal_rect, content_rect, close_rect, char_rects)
        """
        # Determine title based on context
        if context == "direct_download":
            title = "Download from URL"
        else:
            title = "Enter Archive URL"

        # Keyboard mode uses smaller modal (no on-screen keyboard needed)
        if input_mode == "keyboard":
            return self._render_keyboard_mode(screen, input_text, title)

        # Gamepad and touch modes use on-screen keyboard
        return self._render_onscreen_keyboard_mode(
            screen, input_text, cursor_position, title, input_mode
        )

    def _render_keyboard_mode(
        self, screen: pygame.Surface, input_text: str, title: str
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple]]:
        """Render modal for keyboard input (no on-screen keyboard)."""
        width = min(500, screen.get_width() - 40)
        height = 150

        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height, title=title, show_close=False
        )

        padding = self.theme.padding_sm
        y = content_rect.top + padding

        # Draw input field
        field_height = 40
        field_rect = pygame.Rect(
            content_rect.left + padding,
            y,
            content_rect.width - padding * 2,
            field_height,
        )

        pygame.draw.rect(
            screen,
            self.theme.surface_hover,
            field_rect,
            border_radius=self.theme.radius_sm,
        )

        # Draw text
        display_text = input_text if input_text else "Type URL..."
        text_color = self.theme.text_primary if input_text else self.theme.text_disabled
        self.text.render(
            screen,
            display_text,
            (
                field_rect.left + padding,
                field_rect.centery - self.theme.font_size_md // 2,
            ),
            color=text_color,
            size=self.theme.font_size_md,
            max_width=field_rect.width - padding * 2,
        )

        # Draw blinking cursor
        if input_text:
            cursor_x = (
                field_rect.left
                + padding
                + self.text.measure(input_text, self.theme.font_size_md)[0]
                + 2
            )
        else:
            cursor_x = field_rect.left + padding

        pygame.draw.line(
            screen,
            self.theme.primary,
            (cursor_x, field_rect.top + 8),
            (cursor_x, field_rect.bottom - 8),
            2,
        )

        y = field_rect.bottom + padding

        # Draw hints
        hints = get_combined_hints(
            [("select", "Confirm"), ("back", "Cancel")], "keyboard"
        )
        self.text.render(
            screen,
            hints,
            (content_rect.centerx, y),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
            align="center",
        )

        return modal_rect, content_rect, None, []

    def _render_onscreen_keyboard_mode(
        self,
        screen: pygame.Surface,
        input_text: str,
        cursor_position: int,
        title: str,
        input_mode: str,
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple]]:
        """Render modal with on-screen keyboard for gamepad/touch."""
        width = min(650, screen.get_width() - 40)
        height = 380

        # Show close button only for touch mode
        show_close = input_mode == "touch"
        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height, title=title, show_close=show_close
        )

        # Render character keyboard with URL charset
        char_rects, input_rect = self.char_keyboard.render(
            screen,
            content_rect,
            current_text=input_text,
            selected_index=cursor_position,
            chars_per_row=13,
            char_set="url",
            show_input_field=True,
        )

        return modal_rect, content_rect, close_rect, char_rects

    def handle_selection(
        self, cursor_position: int, current_text: str
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
