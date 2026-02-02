"""
Search modal - Text input for searching games.
"""

import pygame
from typing import Tuple, List, Optional

from ui.theme import Theme, default_theme
from ui.organisms.modal_frame import ModalFrame
from ui.organisms.char_keyboard import CharKeyboard
from ui.atoms.text import Text


class SearchModal:
    """
    Search modal.

    On-screen keyboard for entering search queries.
    Adapts to input mode: keyboard uses physical keys,
    gamepad/touch use on-screen keyboard.
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.modal_frame = ModalFrame(theme)
        self.char_keyboard = CharKeyboard(theme)
        self.text = Text(theme)

    def render(
        self,
        screen: pygame.Surface,
        search_text: str,
        cursor_position: int,
        input_mode: str = "keyboard"
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple]]:
        """
        Render the search modal.

        Args:
            screen: Surface to render to
            search_text: Current search text
            cursor_position: Currently selected character index
            input_mode: Current input mode ("keyboard", "gamepad", "touch")

        Returns:
            Tuple of (modal_rect, content_rect, close_rect, char_rects)
        """
        # Keyboard mode uses smaller modal (no on-screen keyboard needed)
        if input_mode == "keyboard":
            return self._render_keyboard_mode(screen, search_text)

        # Gamepad and touch modes use on-screen keyboard
        return self._render_onscreen_keyboard_mode(
            screen, search_text, cursor_position, input_mode
        )

    def _render_keyboard_mode(
        self,
        screen: pygame.Surface,
        search_text: str
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple]]:
        """Render modal for keyboard input (no on-screen keyboard)."""
        width = min(500, screen.get_width() - 40)
        height = 150

        # No close button for keyboard mode
        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height,
            title="Search Games",
            show_close=False
        )

        padding = self.theme.padding_sm
        y = content_rect.top + padding

        # Draw input field
        field_height = 40
        field_rect = pygame.Rect(
            content_rect.left + padding,
            y,
            content_rect.width - padding * 2,
            field_height
        )

        pygame.draw.rect(
            screen,
            self.theme.surface_hover,
            field_rect,
            border_radius=self.theme.radius_sm
        )

        # Draw text
        display_text = search_text if search_text else "Type to search..."
        text_color = self.theme.text_primary if search_text else self.theme.text_disabled
        self.text.render(
            screen,
            display_text,
            (field_rect.left + padding, field_rect.centery - self.theme.font_size_md // 2),
            color=text_color,
            size=self.theme.font_size_md,
            max_width=field_rect.width - padding * 2
        )

        # Draw blinking cursor
        if search_text:
            cursor_x = field_rect.left + padding + self.text.measure(
                search_text, self.theme.font_size_md
            )[0] + 2
        else:
            cursor_x = field_rect.left + padding

        pygame.draw.line(
            screen,
            self.theme.primary,
            (cursor_x, field_rect.top + 8),
            (cursor_x, field_rect.bottom - 8),
            2
        )

        y = field_rect.bottom + padding

        # Draw hints
        hints = "Enter: Search    Esc: Cancel    Backspace: Delete"
        self.text.render(
            screen,
            hints,
            (content_rect.centerx, y),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
            align="center"
        )

        return modal_rect, content_rect, None, []

    def _render_onscreen_keyboard_mode(
        self,
        screen: pygame.Surface,
        search_text: str,
        cursor_position: int,
        input_mode: str
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple]]:
        """Render modal with on-screen keyboard for gamepad/touch."""
        width = min(600, screen.get_width() - 40)
        height = 350

        # Show close button only for touch mode
        show_close = (input_mode == "touch")
        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height,
            title="Search Games",
            show_close=show_close
        )

        # Render character keyboard
        char_rects, input_rect = self.char_keyboard.render(
            screen, content_rect,
            current_text=search_text,
            selected_index=cursor_position,
            chars_per_row=13,
            show_input_field=True
        )

        # Show gamepad hints at bottom if in gamepad mode
        if input_mode == "gamepad":
            hints = "A: Select    B: Back"
            self.text.render(
                screen,
                hints,
                (content_rect.centerx, content_rect.bottom - self.theme.padding_sm),
                color=self.theme.text_secondary,
                size=self.theme.font_size_sm,
                align="center"
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
