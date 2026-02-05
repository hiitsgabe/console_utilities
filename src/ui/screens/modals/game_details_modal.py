"""
Game details modal - Shows game information and download option.
"""

import pygame
from typing import Dict, Any, Tuple, Optional

from ui.theme import Theme, default_theme
from ui.organisms.modal_frame import ModalFrame
from ui.molecules.thumbnail import Thumbnail
from ui.molecules.action_button import ActionButton
from ui.atoms.text import Text
from utils.button_hints import get_game_details_hints
from services.installed_checker import installed_checker


class GameDetailsModal:
    """
    Game details modal.

    Displays detailed information about a game
    with hi-res thumbnail and download option.

    Vertical layout:
    - Game name (title)
    - Large thumbnail image
    - Complete filename
    - File size
    - Download button
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.modal_frame = ModalFrame(theme)
        self.thumbnail = Thumbnail(theme)
        self.action_button = ActionButton(theme)
        self.text = Text(theme)

    def render(
        self,
        screen: pygame.Surface,
        game: Dict[str, Any],
        hires_image: Optional[pygame.Surface] = None,
        button_focused: bool = True,
        loading_size: bool = False,
        input_mode: str = "keyboard",
    ) -> Tuple[pygame.Rect, Optional[pygame.Rect], Optional[pygame.Rect]]:
        """
        Render the game details modal.

        Args:
            screen: Surface to render to
            game: Game data dictionary
            hires_image: Optional hi-res thumbnail
            button_focused: Whether download button is focused
            loading_size: Whether file size is being loaded
            input_mode: Current input mode ("touch", "keyboard", "gamepad")

        Returns:
            Tuple of (modal_rect, download_button_rect, close_button_rect)
        """
        screen_width, screen_height = screen.get_size()

        # Make modal bigger - use most of the screen
        width = min(500, screen_width - 40)
        height = min(screen_height - 60, 600)

        # Render modal frame - only show close button in touch mode
        show_close = input_mode == "touch"
        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height, title="Game Details", show_close=show_close
        )

        # Vertical layout - centered
        center_x = content_rect.centerx
        y = content_rect.top

        # Game name at top (centered)
        game_name = self._get_game_name(game)
        self.text.render(
            screen,
            game_name,
            (center_x, y),
            color=self.theme.text_primary,
            size=self.theme.font_size_lg,
            max_width=content_rect.width - self.theme.padding_md * 2,
            align="center",
        )
        y += self.theme.font_size_lg + self.theme.padding_sm

        # Calculate space for image - use as much as possible
        # Reserve space for: filename, size, button, padding
        reserved_height = (
            self.theme.font_size_sm * 2  # filename + size
            + self.theme.padding_sm * 3  # padding between elements
            + 50  # button height
            + self.theme.padding_md  # bottom padding
        )

        available_for_image = content_rect.bottom - y - reserved_height
        image_size = min(
            available_for_image,
            content_rect.width - self.theme.padding_md * 2,
            350,  # max size
        )
        image_size = max(image_size, 100)  # min size

        # Thumbnail image (centered, large)
        image_rect = pygame.Rect(center_x - image_size // 2, y, image_size, image_size)
        placeholder = self.thumbnail.get_placeholder_initials(game_name)
        self.thumbnail.render(
            screen, image_rect, image=hires_image, placeholder_text=placeholder
        )
        y += image_size + self.theme.padding_sm

        # Complete filename (centered)
        filename = game.get("filename", game.get("name", ""))
        if filename:
            self.text.render(
                screen,
                filename,
                (center_x, y),
                color=self.theme.text_secondary,
                size=self.theme.font_size_sm,
                max_width=content_rect.width - self.theme.padding_sm * 2,
                align="center",
            )
            y += self.theme.font_size_sm + self.theme.padding_sm

        # File size (centered) - show loading if fetching
        if loading_size:
            self.text.render(
                screen,
                "Loading size...",
                (center_x, y),
                color=self.theme.text_disabled,
                size=self.theme.font_size_sm,
                align="center",
            )
        else:
            size_str = self._get_size_string(game)
            if size_str:
                self.text.render(
                    screen,
                    size_str,
                    (center_x, y),
                    color=self.theme.text_secondary,
                    size=self.theme.font_size_sm,
                    align="center",
                )
        y += self.theme.font_size_sm + self.theme.padding_sm

        # Installed status indicator (lazy check)
        if installed_checker.is_installed(game):
            self.text.render(
                screen,
                "Already Installed",
                (center_x, y),
                color=self.theme.success,
                size=self.theme.font_size_sm,
                align="center",
            )

        # Bottom section - show button for touch, hints for keyboard/gamepad
        download_rect = None

        if input_mode == "touch":
            # Download button at bottom (centered)
            button_width = 150
            button_height = 45
            download_rect = pygame.Rect(
                center_x - button_width // 2,
                content_rect.bottom - button_height - self.theme.padding_sm,
                button_width,
                button_height,
            )
            self.action_button.render(
                screen, download_rect, "Download", hover=button_focused
            )
        else:
            # Show hints for keyboard/gamepad
            hints = get_game_details_hints(input_mode)

            self.text.render(
                screen,
                hints,
                (center_x, content_rect.bottom - self.theme.padding_md),
                color=self.theme.text_secondary,
                size=self.theme.font_size_sm,
                align="center",
            )

        return modal_rect, download_rect, close_rect

    def _get_game_name(self, game: Dict[str, Any]) -> str:
        """Extract display name from game."""
        name = game.get("filename", game.get("name", "Unknown Game"))

        # Remove file extension
        if "." in name:
            name = name.rsplit(".", 1)[0]

        return name

    def _get_size_string(self, game: Dict[str, Any]) -> str:
        """Get formatted size string from game data."""
        size = game.get("size") or game.get("filesize") or game.get("file_size")

        if not size:
            return ""

        # If it's already a string (formatted), return as-is
        if isinstance(size, str):
            return f"Size: {size}"

        # If it's a number (bytes), format it
        return f"Size: {self._format_bytes(size)}"

    def _format_bytes(self, size: int) -> str:
        """Format bytes to human readable string."""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0:
                return (
                    f"{size:.1f} {unit}" if size != int(size) else f"{int(size)} {unit}"
                )
            size /= 1024.0
        return f"{size:.1f} PB"


# Default instance
game_details_modal = GameDetailsModal()
