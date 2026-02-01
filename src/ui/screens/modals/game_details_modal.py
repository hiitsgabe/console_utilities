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


class GameDetailsModal:
    """
    Game details modal.

    Displays detailed information about a game
    with hi-res thumbnail and download option.
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
        hires_image: Optional[pygame.Surface] = None
    ) -> Tuple[pygame.Rect, Optional[pygame.Rect], Optional[pygame.Rect]]:
        """
        Render the game details modal.

        Args:
            screen: Surface to render to
            game: Game data dictionary
            hires_image: Optional hi-res thumbnail

        Returns:
            Tuple of (modal_rect, download_button_rect, close_button_rect)
        """
        # Calculate modal size
        width = min(500, screen.get_width() - 60)
        height = min(450, screen.get_height() - 60)

        # Render modal frame
        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height,
            title="Game Details",
            show_close=True
        )

        # Layout
        image_size = min(200, content_rect.width // 2 - self.theme.padding_md)
        image_rect = pygame.Rect(
            content_rect.left,
            content_rect.top,
            image_size,
            image_size
        )

        info_left = image_rect.right + self.theme.padding_lg
        info_width = content_rect.right - info_left

        # Render thumbnail
        game_name = self._get_game_name(game)
        placeholder = self.thumbnail.get_placeholder_initials(game_name)
        self.thumbnail.render(
            screen, image_rect,
            image=hires_image,
            placeholder_text=placeholder
        )

        # Render game name
        y = content_rect.top
        self.text.render(
            screen,
            game_name,
            (info_left, y),
            color=self.theme.text_primary,
            size=self.theme.font_size_lg,
            max_width=info_width
        )
        y += self.theme.font_size_lg + self.theme.padding_sm

        # Render file info
        filename = game.get('filename', game.get('name', ''))
        if filename:
            self.text.render(
                screen,
                f"File: {filename}",
                (info_left, y),
                color=self.theme.text_secondary,
                size=self.theme.font_size_sm,
                max_width=info_width
            )
            y += self.theme.font_size_sm + 4

        # Render additional info if available
        if 'size' in game:
            self.text.render(
                screen,
                f"Size: {game['size']}",
                (info_left, y),
                color=self.theme.text_secondary,
                size=self.theme.font_size_sm
            )
            y += self.theme.font_size_sm + 4

        if 'region' in game:
            self.text.render(
                screen,
                f"Region: {game['region']}",
                (info_left, y),
                color=self.theme.text_secondary,
                size=self.theme.font_size_sm
            )
            y += self.theme.font_size_sm + 4

        # Download button
        button_width = 150
        button_height = 45
        download_rect = pygame.Rect(
            content_rect.centerx - button_width // 2,
            content_rect.bottom - button_height - self.theme.padding_sm,
            button_width,
            button_height
        )
        self.action_button.render(
            screen, download_rect,
            "Download",
            icon="download"
        )

        return modal_rect, download_rect, close_rect

    def _get_game_name(self, game: Dict[str, Any]) -> str:
        """Extract display name from game."""
        name = game.get('filename', game.get('name', 'Unknown Game'))

        # Remove file extension
        if '.' in name:
            name = name.rsplit('.', 1)[0]

        return name


# Default instance
game_details_modal = GameDetailsModal()
