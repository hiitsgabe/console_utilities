"""
Internet Archive login modal - Multi-step login flow.
"""

import pygame
from typing import Tuple, List, Optional

from ui.theme import Theme, default_theme
from ui.organisms.modal_frame import ModalFrame
from ui.organisms.char_keyboard import CharKeyboard
from ui.atoms.text import Text
from utils.button_hints import get_combined_hints


class IALoginModal:
    """
    Internet Archive login modal.

    Multi-step login flow:
    1. Email input
    2. Password input
    3. Testing credentials
    4. Complete or Error
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.modal_frame = ModalFrame(theme)
        self.char_keyboard = CharKeyboard(theme)
        self.text = Text(theme)

    def render(
        self,
        screen: pygame.Surface,
        step: str,
        email: str,
        password: str,
        cursor_position: int,
        error_message: str = "",
        input_mode: str = "keyboard",
        shift_active: bool = False,
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple]]:
        """
        Render the IA login modal.

        Args:
            screen: Surface to render to
            step: Current step ("email", "password", "testing", "complete", "error")
            email: Current email input
            password: Current password input
            cursor_position: Cursor position for keyboard
            error_message: Error message to display
            input_mode: Current input mode
            shift_active: Whether shift is active

        Returns:
            Tuple of (modal_rect, content_rect, close_rect, char_rects)
        """
        if step == "email":
            return self._render_email_step(
                screen, email, cursor_position, input_mode, shift_active
            )
        elif step == "password":
            return self._render_password_step(
                screen, password, cursor_position, input_mode, shift_active
            )
        elif step == "testing":
            return self._render_testing_step(screen)
        elif step == "complete":
            return self._render_complete_step(screen, email, input_mode)
        elif step == "error":
            return self._render_error_step(screen, error_message, input_mode)
        else:
            return self._render_email_step(
                screen, email, cursor_position, input_mode, shift_active
            )

    def _render_email_step(
        self,
        screen: pygame.Surface,
        email: str,
        cursor_position: int,
        input_mode: str,
        shift_active: bool = False,
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple]]:
        """Render email input step."""
        title = "Internet Archive Login"

        if input_mode == "keyboard":
            return self._render_keyboard_input(
                screen, title, "Email:", email, "email@example.com", input_mode
            )

        # On-screen keyboard mode
        width = min(650, screen.get_width() - 40)
        height = 420

        show_close = input_mode == "touch"
        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height, title=title, show_close=show_close
        )

        # Show "Email:" label above keyboard
        padding = self.theme.padding_sm
        self.text.render(
            screen,
            "Enter your archive.org email:",
            (content_rect.left + padding, content_rect.top + padding),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
        )

        # Offset content rect for keyboard
        keyboard_rect = pygame.Rect(
            content_rect.left,
            content_rect.top + 25,
            content_rect.width,
            content_rect.height - 25,
        )

        char_rects, _ = self.char_keyboard.render(
            screen,
            keyboard_rect,
            current_text=email,
            selected_index=cursor_position,
            chars_per_row=13,
            char_set="url",  # Has @ and . for email
            show_input_field=True,
            shift_active=shift_active,
        )

        return modal_rect, content_rect, close_rect, char_rects

    def _render_password_step(
        self,
        screen: pygame.Surface,
        password: str,
        cursor_position: int,
        input_mode: str,
        shift_active: bool = False,
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple]]:
        """Render password input step."""
        title = "Internet Archive Login"

        if input_mode == "keyboard":
            # Mask password with asterisks
            masked = "*" * len(password) if password else ""
            return self._render_keyboard_input(
                screen, title, "Password:", masked, "Enter password", input_mode
            )

        # On-screen keyboard mode
        width = min(650, screen.get_width() - 40)
        height = 420

        show_close = input_mode == "touch"
        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height, title=title, show_close=show_close
        )

        # Show "Password:" label above keyboard
        padding = self.theme.padding_sm
        self.text.render(
            screen,
            "Enter your password:",
            (content_rect.left + padding, content_rect.top + padding),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
        )

        # Offset content rect for keyboard
        keyboard_rect = pygame.Rect(
            content_rect.left,
            content_rect.top + 25,
            content_rect.width,
            content_rect.height - 25,
        )

        # Mask password display
        masked = "*" * len(password) if password else ""

        char_rects, _ = self.char_keyboard.render(
            screen,
            keyboard_rect,
            current_text=masked,
            selected_index=cursor_position,
            chars_per_row=13,
            char_set="default",
            show_input_field=True,
            shift_active=shift_active,
        )

        return modal_rect, content_rect, close_rect, char_rects

    def _render_keyboard_input(
        self,
        screen: pygame.Surface,
        title: str,
        label: str,
        value: str,
        placeholder: str,
        input_mode: str,
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple]]:
        """Render simple keyboard text input (no on-screen keyboard)."""
        width = min(500, screen.get_width() - 40)
        height = 180

        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height, title=title, show_close=False
        )

        padding = self.theme.padding_sm
        y = content_rect.top + padding

        # Label
        self.text.render(
            screen,
            label,
            (content_rect.left + padding, y),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
        )
        y += 25

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
        display_text = value if value else placeholder
        text_color = self.theme.text_primary if value else self.theme.text_disabled
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
        if value:
            cursor_x = (
                field_rect.left
                + padding
                + self.text.measure(value, self.theme.font_size_md)[0]
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
            [("select", "Continue"), ("back", "Cancel")], "keyboard"
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

    def _render_testing_step(
        self, screen: pygame.Surface
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple]]:
        """Render testing/loading step."""
        width = min(400, screen.get_width() - 40)
        height = 150

        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height, title="Internet Archive Login", show_close=False
        )

        # Draw loading message
        self.text.render(
            screen,
            "Testing credentials...",
            (content_rect.centerx, content_rect.centery - 10),
            color=self.theme.text_primary,
            size=self.theme.font_size_md,
            align="center",
        )

        self.text.render(
            screen,
            "Please wait",
            (content_rect.centerx, content_rect.centery + 20),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
            align="center",
        )

        return modal_rect, content_rect, None, []

    def _render_complete_step(
        self, screen: pygame.Surface, email: str, input_mode: str
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple]]:
        """Render login complete step."""
        width = min(450, screen.get_width() - 40)
        height = 180

        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height, title="Login Successful", show_close=False
        )

        padding = self.theme.padding_sm

        # Success message
        self.text.render(
            screen,
            "Successfully logged in as:",
            (content_rect.centerx, content_rect.top + padding + 10),
            color=self.theme.text_primary,
            size=self.theme.font_size_md,
            align="center",
        )

        self.text.render(
            screen,
            email,
            (content_rect.centerx, content_rect.top + padding + 40),
            color=self.theme.success,
            size=self.theme.font_size_md,
            align="center",
        )

        # Hint
        hints = get_combined_hints([("select", "Continue")], input_mode)
        self.text.render(
            screen,
            hints,
            (content_rect.centerx, content_rect.bottom - padding - 20),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
            align="center",
        )

        return modal_rect, content_rect, None, []

    def _render_error_step(
        self, screen: pygame.Surface, error_message: str, input_mode: str
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple]]:
        """Render error step."""
        width = min(450, screen.get_width() - 40)
        height = 180

        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height, title="Login Failed", show_close=False
        )

        padding = self.theme.padding_sm

        # Error message
        self.text.render(
            screen,
            "Login failed:",
            (content_rect.centerx, content_rect.top + padding + 10),
            color=self.theme.text_primary,
            size=self.theme.font_size_md,
            align="center",
        )

        self.text.render(
            screen,
            error_message or "Unknown error",
            (content_rect.centerx, content_rect.top + padding + 40),
            color=self.theme.error,
            size=self.theme.font_size_sm,
            align="center",
            max_width=content_rect.width - padding * 2,
        )

        # Hints
        hints = get_combined_hints(
            [("select", "Try Again"), ("back", "Cancel")], input_mode
        )
        self.text.render(
            screen,
            hints,
            (content_rect.centerx, content_rect.bottom - padding - 20),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
            align="center",
        )

        return modal_rect, content_rect, None, []

    def handle_selection(
        self,
        step: str,
        cursor_position: int,
        current_text: str,
        shift_active: bool = False,
    ) -> Tuple[str, bool, bool]:
        """
        Handle character selection for email/password steps.

        Args:
            step: Current step
            cursor_position: Selected character index
            current_text: Current input text
            shift_active: Whether shift is active

        Returns:
            Tuple of (new_text, is_done, toggle_shift)
        """
        if step == "email":
            return self.char_keyboard.handle_selection(
                cursor_position,
                current_text,
                char_set="url",
                shift_active=shift_active,
            )
        elif step == "password":
            return self.char_keyboard.handle_selection(
                cursor_position,
                current_text,
                char_set="default",
                shift_active=shift_active,
            )
        return current_text, False, False


# Default instance
ia_login_modal = IALoginModal()
