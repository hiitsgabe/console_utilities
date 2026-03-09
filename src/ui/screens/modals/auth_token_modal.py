"""
Auth token modal - Shows auth message and allows token entry.
"""

import pygame
from typing import Tuple, List, Optional

from ui.theme import Theme, default_theme
from ui.organisms.modal_frame import ModalFrame
from ui.organisms.char_keyboard import CharKeyboard
from ui.molecules.action_button import ActionButton
from ui.atoms.text import Text
from utils.button_hints import get_combined_hints


class AuthTokenModal:
    """
    Auth token modal.

    Two-step modal:
    1. "message" step: Shows the auth_message with an "Enter Token" button
    2. "input" step: On-screen keyboard for typing the token
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.modal_frame = ModalFrame(theme)
        self.char_keyboard = CharKeyboard(theme)
        self.action_button = ActionButton(theme)
        self.text = Text(theme)
        self.ok_rect = None
        self.cancel_rect = None
        self.backspace_rect = None
        self.enter_token_rect = None

    def render(
        self,
        screen: pygame.Surface,
        step: str,
        auth_message: str,
        input_text: str = "",
        cursor_position: int = 0,
        input_mode: str = "keyboard",
        shift_active: bool = False,
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple]]:
        """
        Render the auth token modal.

        Returns:
            Tuple of (modal_rect, content_rect, close_rect, char_rects)
        """
        self.ok_rect = None
        self.cancel_rect = None
        self.backspace_rect = None
        self.enter_token_rect = None

        if step == "message":
            return self._render_message_step(screen, auth_message, input_mode)
        else:
            return self._render_input_step(
                screen, input_text, cursor_position, input_mode, shift_active
            )

    def _render_message_step(
        self,
        screen: pygame.Surface,
        auth_message: str,
        input_mode: str,
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple]]:
        """Render the auth message with Enter Token button."""
        width = min(500, screen.get_width() - 40)

        # Word-wrap the message
        font = self.text.get_font(self.theme.font_size_md)
        max_text_width = width - self.theme.padding_md * 4
        wrapped_lines = self._wrap_text(auth_message, font, max_text_width)

        line_height = font.get_linesize() + 4
        text_height = len(wrapped_lines) * line_height
        button_height = 44
        height = text_height + button_height + self.theme.padding_lg * 4 + 80

        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height, title="Authentication Required", show_close=True
        )

        # Draw message lines
        y = content_rect.top + self.theme.padding_md
        for line in wrapped_lines:
            self.text.render(
                screen,
                line,
                (content_rect.centerx, y),
                color=self.theme.text_primary,
                size=self.theme.font_size_md,
                align="center",
                max_width=max_text_width,
            )
            y += line_height

        # Draw "Enter Token" button
        button_width = 160
        button_y = content_rect.bottom - button_height - self.theme.padding_md
        enter_rect = pygame.Rect(
            content_rect.centerx - button_width // 2,
            button_y,
            button_width,
            button_height,
        )
        self.action_button.render(screen, enter_rect, "Enter Token", hover=True)
        self.enter_token_rect = enter_rect

        return modal_rect, content_rect, close_rect, []

    def _render_input_step(
        self,
        screen: pygame.Surface,
        input_text: str,
        cursor_position: int,
        input_mode: str,
        shift_active: bool,
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple]]:
        """Render the token input step."""
        if input_mode == "keyboard":
            return self._render_keyboard_mode(screen, input_text)
        if input_mode == "android":
            return self._render_android_mode(screen, input_text)
        return self._render_onscreen_keyboard_mode(
            screen, input_text, cursor_position, input_mode, shift_active
        )

    def _render_keyboard_mode(
        self, screen: pygame.Surface, input_text: str
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple]]:
        """Render for keyboard input."""
        width = min(500, screen.get_width() - 40)
        height = 150

        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height, title="Enter Auth Token", show_close=False
        )

        padding = self.theme.padding_sm
        y = content_rect.top + padding

        # Input field
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

        display_text = input_text if input_text else "Paste or type token..."
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

        # Cursor
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

    def _render_android_mode(
        self, screen: pygame.Surface, input_text: str
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple]]:
        """Render for Android."""
        sw, sh = screen.get_size()
        width = min(int(sw * 0.9), 600)
        height = 230

        modal_rect, content_rect, close_rect = self.modal_frame.render_top_aligned(
            screen, width, height, title="Enter Auth Token", show_close=False
        )

        padding = self.theme.padding_sm
        y = content_rect.top + padding

        field_height = 48
        bksp_width = 48
        field_rect = pygame.Rect(
            content_rect.left + padding,
            y,
            content_rect.width - padding * 3 - bksp_width,
            field_height,
        )
        pygame.draw.rect(
            screen,
            self.theme.surface_hover,
            field_rect,
            border_radius=self.theme.radius_sm,
        )

        # Backspace button
        bksp_rect = pygame.Rect(field_rect.right + padding, y, bksp_width, field_height)
        pygame.draw.rect(
            screen,
            self.theme.surface_hover,
            bksp_rect,
            border_radius=self.theme.radius_sm,
        )
        self.text.render(
            screen,
            "<x]",
            (bksp_rect.centerx, bksp_rect.centery - self.theme.font_size_md // 2),
            color=self.theme.text_primary,
            size=self.theme.font_size_md,
            align="center",
        )
        self.backspace_rect = bksp_rect

        display_text = input_text if input_text else "Paste or type token..."
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

        # Cursor
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

        # OK / Cancel buttons
        y = field_rect.bottom + padding * 3
        button_width = 120
        button_height = 44
        button_spacing = self.theme.padding_lg

        ok_rect = pygame.Rect(
            content_rect.centerx - button_width - button_spacing // 2,
            y,
            button_width,
            button_height,
        )
        cancel_rect = pygame.Rect(
            content_rect.centerx + button_spacing // 2,
            y,
            button_width,
            button_height,
        )
        self.action_button.render(screen, ok_rect, "OK", hover=True)
        self.action_button.render_secondary(screen, cancel_rect, "Cancel", hover=False)
        self.ok_rect = ok_rect
        self.cancel_rect = cancel_rect

        return modal_rect, content_rect, None, []

    def _render_onscreen_keyboard_mode(
        self,
        screen: pygame.Surface,
        input_text: str,
        cursor_position: int,
        input_mode: str,
        shift_active: bool,
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple]]:
        """Render with on-screen keyboard."""
        width = min(650, screen.get_width() - 40)
        height = 380

        show_close = input_mode == "touch"
        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height, title="Enter Auth Token", show_close=show_close
        )

        char_rects, input_rect = self.char_keyboard.render(
            screen,
            content_rect,
            current_text=input_text,
            selected_index=cursor_position,
            chars_per_row=13,
            char_set="url",
            show_input_field=True,
            shift_active=shift_active,
        )

        return modal_rect, content_rect, close_rect, char_rects

    def handle_selection(
        self,
        cursor_position: int,
        current_text: str,
        shift_active: bool = False,
    ) -> Tuple[str, bool, bool]:
        """Handle character selection on on-screen keyboard."""
        return self.char_keyboard.handle_selection(
            cursor_position,
            current_text,
            char_set="url",
            shift_active=shift_active,
        )

    def _wrap_text(self, text: str, font, max_width: int) -> List[str]:
        """Word-wrap text to fit within max_width."""
        words = text.split()
        lines = []
        current_line = ""
        for word in words:
            test_line = f"{current_line} {word}".strip() if current_line else word
            if font.size(test_line)[0] <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)
        return lines or [""]


auth_token_modal = AuthTokenModal()
