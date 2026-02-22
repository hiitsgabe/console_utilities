"""
Scraper login modal - Multi-step login flow for ScreenScraper/TheGamesDB/RAWG.
"""

import pygame
from typing import Tuple, List, Optional

from ui.theme import Theme, default_theme
from ui.organisms.modal_frame import ModalFrame
from ui.organisms.char_keyboard import CharKeyboard
from ui.atoms.text import Text
from utils.button_hints import get_combined_hints


class ScraperLoginModal:
    """
    Scraper login modal.

    Multi-step login flow for ScreenScraper:
    1. Username input
    2. Password input
    3. Testing credentials
    4. Complete or Error

    For TheGamesDB/RAWG:
    1. API key input
    2. Testing credentials
    3. Complete or Error
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.modal_frame = ModalFrame(theme)
        self.char_keyboard = CharKeyboard(theme)
        self.text = Text(theme)

    def render(
        self,
        screen: pygame.Surface,
        provider: str,
        step: str,
        username: str,
        password: str,
        api_key: str,
        cursor_position: int,
        error_message: str = "",
        input_mode: str = "keyboard",
        shift_active: bool = False,
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple]]:
        """
        Render the scraper login modal.

        Args:
            screen: Surface to render to
            provider: Provider name ("screenscraper" or "thegamesdb")
            step: Current step
            username: Current username input
            password: Current password input
            api_key: Current API key input
            cursor_position: Cursor position for keyboard
            error_message: Error message to display
            input_mode: Current input mode

        Returns:
            Tuple of (modal_rect, content_rect, close_rect, char_rects)
        """
        if provider == "preferred_system":
            return self._render_api_key_flow(
                screen,
                step,
                api_key,
                cursor_position,
                error_message,
                input_mode,
                shift_active,
                provider_label="Preferred System",
                input_label="Preferred System",
                input_prompt="e.g. psx, snes, gba, genesis",
            )
        elif provider == "thegamesdb":
            return self._render_api_key_flow(
                screen,
                step,
                api_key,
                cursor_position,
                error_message,
                input_mode,
                shift_active,
                provider_label="TheGamesDB",
            )
        elif provider == "rawg":
            return self._render_api_key_flow(
                screen,
                step,
                api_key,
                cursor_position,
                error_message,
                input_mode,
                shift_active,
                provider_label="RAWG",
            )
        elif provider == "igdb":
            return self._render_igdb_flow(
                screen,
                step,
                username,
                password,
                cursor_position,
                error_message,
                input_mode,
                shift_active,
            )
        else:
            return self._render_screenscraper(
                screen,
                step,
                username,
                password,
                cursor_position,
                error_message,
                input_mode,
                shift_active,
            )

    def _render_screenscraper(
        self,
        screen: pygame.Surface,
        step: str,
        username: str,
        password: str,
        cursor_position: int,
        error_message: str,
        input_mode: str,
        shift_active: bool = False,
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple]]:
        """Render ScreenScraper login flow."""
        if step == "username":
            return self._render_username_step(
                screen, username, cursor_position, input_mode, shift_active
            )
        elif step == "password":
            return self._render_password_step(
                screen, password, cursor_position, input_mode, shift_active
            )
        elif step == "testing":
            return self._render_testing_step(screen, "ScreenScraper")
        elif step == "complete":
            return self._render_complete_step(
                screen, username, "ScreenScraper", input_mode
            )
        elif step == "error":
            return self._render_error_step(
                screen, error_message, "ScreenScraper", input_mode
            )
        else:
            return self._render_username_step(
                screen, username, cursor_position, input_mode, shift_active
            )

    def _render_api_key_flow(
        self,
        screen: pygame.Surface,
        step: str,
        api_key: str,
        cursor_position: int,
        error_message: str,
        input_mode: str,
        shift_active: bool = False,
        provider_label: str = "TheGamesDB",
        input_label: str = "",
        input_prompt: str = "",
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple]]:
        """Render API key login flow for any provider."""
        if step == "api_key":
            return self._render_api_key_step(
                screen,
                api_key,
                cursor_position,
                input_mode,
                shift_active,
                provider_label=provider_label,
                input_label=input_label,
                input_prompt=input_prompt,
            )
        elif step == "testing":
            return self._render_testing_step(screen, provider_label)
        elif step == "complete":
            return self._render_complete_step(screen, "", provider_label, input_mode)
        elif step == "error":
            return self._render_error_step(
                screen, error_message, provider_label, input_mode
            )
        else:
            return self._render_api_key_step(
                screen,
                api_key,
                cursor_position,
                input_mode,
                shift_active,
                provider_label=provider_label,
            )

    def _render_igdb_flow(
        self,
        screen: pygame.Surface,
        step: str,
        username: str,
        password: str,
        cursor_position: int,
        error_message: str,
        input_mode: str,
        shift_active: bool = False,
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple]]:
        """Render IGDB login flow (Client ID + Client Secret)."""
        if step == "username":
            return self._render_igdb_input_step(
                screen,
                "Client ID:",
                "Enter Twitch Client ID",
                username,
                cursor_position,
                input_mode,
                shift_active,
            )
        elif step == "password":
            return self._render_igdb_input_step(
                screen,
                "Client Secret:",
                "Enter Twitch Client Secret",
                password,
                cursor_position,
                input_mode,
                shift_active,
            )
        elif step == "testing":
            return self._render_testing_step(screen, "IGDB")
        elif step == "complete":
            return self._render_complete_step(screen, "", "IGDB", input_mode)
        elif step == "error":
            return self._render_error_step(screen, error_message, "IGDB", input_mode)
        else:
            return self._render_igdb_input_step(
                screen,
                "Client ID:",
                "Enter Twitch Client ID",
                username,
                cursor_position,
                input_mode,
                shift_active,
            )

    def _render_igdb_input_step(
        self,
        screen: pygame.Surface,
        label: str,
        prompt: str,
        value: str,
        cursor_position: int,
        input_mode: str,
        shift_active: bool = False,
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple]]:
        """Render an IGDB credential input step."""
        title = "IGDB Login"

        if input_mode == "keyboard":
            return self._render_keyboard_input(
                screen, title, label, value, prompt, input_mode
            )

        # On-screen keyboard mode
        width = min(650, screen.get_width() - 40)
        height = 420

        show_close = input_mode == "touch"
        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen,
            width,
            height,
            title=title,
            show_close=show_close,
        )

        padding = self.theme.padding_sm
        self.text.render(
            screen,
            prompt + ":",
            (content_rect.left + padding, content_rect.top + padding),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
        )

        keyboard_rect = pygame.Rect(
            content_rect.left,
            content_rect.top + 25,
            content_rect.width,
            content_rect.height - 25,
        )

        char_rects, _ = self.char_keyboard.render(
            screen,
            keyboard_rect,
            current_text=value,
            selected_index=cursor_position,
            chars_per_row=13,
            char_set="url",
            show_input_field=True,
            shift_active=shift_active,
        )

        return modal_rect, content_rect, close_rect, char_rects

    def _render_username_step(
        self,
        screen: pygame.Surface,
        username: str,
        cursor_position: int,
        input_mode: str,
        shift_active: bool = False,
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple]]:
        """Render username input step."""
        title = "ScreenScraper Login"

        if input_mode == "keyboard":
            return self._render_keyboard_input(
                screen, title, "Username:", username, "Enter username", input_mode
            )

        # On-screen keyboard mode
        width = min(650, screen.get_width() - 40)
        height = 420

        show_close = input_mode == "touch"
        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height, title=title, show_close=show_close
        )

        padding = self.theme.padding_sm
        self.text.render(
            screen,
            "Enter your ScreenScraper username:",
            (content_rect.left + padding, content_rect.top + padding),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
        )

        keyboard_rect = pygame.Rect(
            content_rect.left,
            content_rect.top + 25,
            content_rect.width,
            content_rect.height - 25,
        )

        char_rects, _ = self.char_keyboard.render(
            screen,
            keyboard_rect,
            current_text=username,
            selected_index=cursor_position,
            chars_per_row=13,
            char_set="default",
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
        title = "ScreenScraper Login"

        if input_mode == "keyboard":
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

        padding = self.theme.padding_sm
        self.text.render(
            screen,
            "Enter your password:",
            (content_rect.left + padding, content_rect.top + padding),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
        )

        keyboard_rect = pygame.Rect(
            content_rect.left,
            content_rect.top + 25,
            content_rect.width,
            content_rect.height - 25,
        )

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

    def _render_api_key_step(
        self,
        screen: pygame.Surface,
        api_key: str,
        cursor_position: int,
        input_mode: str,
        shift_active: bool = False,
        provider_label: str = "TheGamesDB",
        input_label: str = "",
        input_prompt: str = "",
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple]]:
        """Render API key input step."""
        title = input_label or f"{provider_label} API Key"
        prompt = input_prompt or f"Enter your {provider_label} API key:"
        label = input_label or "API Key:"
        placeholder = input_prompt or "Enter API key"

        if input_mode == "keyboard":
            return self._render_keyboard_input(
                screen, title, label, api_key, placeholder, input_mode
            )

        # On-screen keyboard mode
        width = min(650, screen.get_width() - 40)
        height = 420

        show_close = input_mode == "touch"
        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height, title=title, show_close=show_close
        )

        padding = self.theme.padding_sm
        self.text.render(
            screen,
            prompt,
            (content_rect.left + padding, content_rect.top + padding),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
        )

        keyboard_rect = pygame.Rect(
            content_rect.left,
            content_rect.top + 25,
            content_rect.width,
            content_rect.height - 25,
        )

        char_rects, _ = self.char_keyboard.render(
            screen,
            keyboard_rect,
            current_text=api_key,
            selected_index=cursor_position,
            chars_per_row=13,
            char_set="url",  # Has alphanumeric chars
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

        self.text.render(
            screen,
            label,
            (content_rect.left + padding, y),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
        )
        y += 25

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
        self, screen: pygame.Surface, provider_name: str
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple]]:
        """Render testing/loading step."""
        width = min(400, screen.get_width() - 40)
        height = 150

        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height, title=f"{provider_name} Login", show_close=False
        )

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
        self,
        screen: pygame.Surface,
        username: str,
        provider_name: str,
        input_mode: str,
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple]]:
        """Render login complete step."""
        width = min(450, screen.get_width() - 40)
        height = 180

        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height, title="Login Successful", show_close=False
        )

        padding = self.theme.padding_sm

        self.text.render(
            screen,
            f"{provider_name} configured successfully!",
            (content_rect.centerx, content_rect.top + padding + 20),
            color=self.theme.success,
            size=self.theme.font_size_md,
            align="center",
        )

        if username:
            self.text.render(
                screen,
                f"Logged in as: {username}",
                (content_rect.centerx, content_rect.top + padding + 50),
                color=self.theme.text_primary,
                size=self.theme.font_size_sm,
                align="center",
            )

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
        self,
        screen: pygame.Surface,
        error_message: str,
        provider_name: str,
        input_mode: str,
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple]]:
        """Render error step."""
        width = min(450, screen.get_width() - 40)
        height = 180

        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height, title="Login Failed", show_close=False
        )

        padding = self.theme.padding_sm

        self.text.render(
            screen,
            f"{provider_name} login failed:",
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
        provider: str,
        step: str,
        cursor_position: int,
        current_text: str,
        shift_active: bool = False,
    ) -> Tuple[str, bool, bool]:
        """
        Handle character selection for input steps.

        Args:
            provider: Provider name
            step: Current step
            cursor_position: Selected character index
            current_text: Current input text
            shift_active: Whether shift is active

        Returns:
            Tuple of (new_text, is_done, toggle_shift)
        """
        if step in ("username", "password"):
            cs = "url" if provider == "igdb" else "default"
            return self.char_keyboard.handle_selection(
                cursor_position,
                current_text,
                char_set=cs,
                shift_active=shift_active,
            )
        elif step == "api_key":
            return self.char_keyboard.handle_selection(
                cursor_position,
                current_text,
                char_set="url",
                shift_active=shift_active,
            )
        return current_text, False, False


# Default instance
scraper_login_modal = ScraperLoginModal()
