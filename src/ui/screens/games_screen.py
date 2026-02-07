"""
Games screen - Display games for a selected system.
"""

import pygame
from typing import List, Dict, Any, Tuple, Optional, Set, Callable

from ui.theme import Theme, default_theme
from ui.templates.list_screen import ListScreenTemplate
from ui.atoms.text import Text
from ui.molecules.thumbnail import Thumbnail
from ui.molecules.action_button import ActionButton
from utils.button_hints import get_download_hint
from services.installed_checker import installed_checker
from constants import BEZEL_INSET


class GamesScreen:
    """
    Games screen.

    Displays games for a selected system in list view.
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.list_template = ListScreenTemplate(theme)
        self.text = Text(theme)
        self.thumbnail = Thumbnail(theme)
        self.action_button = ActionButton(theme)

    def render(
        self,
        screen: pygame.Surface,
        system_name: str,
        games: List[Any],
        highlighted: int,
        selected_games: Set[int],
        search_query: str = "",
        get_thumbnail: Optional[Callable[[Any], pygame.Surface]] = None,
        input_mode: str = "keyboard",
        show_download_all: bool = False,
    ) -> Tuple[
        Optional[pygame.Rect],
        List[pygame.Rect],
        int,
        Optional[pygame.Rect],
        Optional[pygame.Rect],
    ]:
        """
        Render the games screen.

        Args:
            screen: Surface to render to
            system_name: Name of the current system
            games: List of games
            highlighted: Currently highlighted index
            selected_games: Set of selected game indices
            search_query: Current search query (for subtitle)
            get_thumbnail: Function to get thumbnail for a game
            input_mode: Current input mode ("keyboard", "gamepad", "touch")
            show_download_all: Whether to show "Download All" button

        Returns:
            Tuple of (back_rect, item_rects, scroll_offset, download_button_rect, download_all_rect)
        """
        title = f"{system_name} Games"
        subtitle = f"Search: {search_query}" if search_query else None

        # Reserve footer space for status bar when games are selected
        footer_height = 40 if selected_games else 0

        # Add "Download All" as an extra item if enabled
        display_items = list(games)
        if show_download_all and games:
            display_items.append({"_download_all": True, "name": "Download All Games"})

        # Adjust highlighted to not exceed display items
        display_highlighted = min(highlighted, len(display_items) - 1)

        back_rect, item_rects, scroll_offset = self.list_template.render(
            screen,
            title=title,
            items=display_items,
            highlighted=display_highlighted,
            selected=selected_games,
            show_back=True,
            subtitle=subtitle,
            item_height=50,
            get_label=self._get_game_label,
            get_thumbnail=get_thumbnail,
            show_checkbox=True,
            footer_height=footer_height,
        )

        # Draw status bar when games are selected
        download_button_rect = None
        if selected_games:
            download_button_rect = self._render_status_bar(
                screen, len(selected_games), input_mode
            )

        # Get the "Download All" button rect if shown
        download_all_rect = None
        if show_download_all and games and item_rects:
            # The last item rect is the "Download All" button
            if len(item_rects) > len(games) - scroll_offset:
                download_all_rect = item_rects[-1]

        return (
            back_rect,
            item_rects,
            scroll_offset,
            download_button_rect,
            download_all_rect,
        )

    def render_with_buttons(
        self,
        screen: pygame.Surface,
        system_name: str,
        games: List[Any],
        highlighted: int,
        selected_games: Set[int],
        search_query: str = "",
        get_thumbnail: Optional[Callable[[Any], pygame.Surface]] = None,
    ) -> Tuple[Optional[pygame.Rect], List[pygame.Rect], int, List[pygame.Rect]]:
        """
        Render games screen with action buttons.

        Returns:
            Tuple of (back_rect, item_rects, scroll_offset, button_rects)
        """
        title = f"{system_name} Games"
        subtitle = f"Search: {search_query}" if search_query else None

        buttons = ["Search", "Download"] if selected_games else ["Search"]

        return self.list_template.render_with_buttons(
            screen,
            title=title,
            items=games,
            highlighted=highlighted,
            selected=selected_games,
            button_labels=buttons,
            show_back=True,
            subtitle=subtitle,
            item_height=50,
            get_label=self._get_game_label,
            get_thumbnail=get_thumbnail,
            show_checkbox=True,
        )

    def _get_game_label(self, game: Any) -> str:
        """Extract display label from game."""
        if isinstance(game, dict):
            # Check for special "Download All" item
            if game.get("_download_all"):
                return "[ Download All Games ]"
            name = game.get("filename", game.get("name", str(game)))
        else:
            name = str(game)

        # Remove file extension for display
        if "." in name:
            name = name.rsplit(".", 1)[0]

        # Check installed status lazily
        if installed_checker.is_installed(game):
            name = f"[Installed] {name}"

        return name

    def _render_status_bar(
        self, screen: pygame.Surface, selected_count: int, input_mode: str = "keyboard"
    ) -> Optional[pygame.Rect]:
        """Render status bar showing selected games count and download hint/button.

        Returns:
            Download button rect if in touch mode, None otherwise.
        """
        screen_width, screen_height = screen.get_size()
        inset = BEZEL_INSET
        safe_width = screen_width - inset * 2
        bar_height = 40
        bar_y = screen_height - inset - bar_height

        # Draw semi-transparent background
        bar_surface = pygame.Surface((safe_width, bar_height), pygame.SRCALPHA)
        bar_surface.fill((*self.theme.surface[:3], 230))
        screen.blit(bar_surface, (inset, bar_y))

        # Draw selected count on the left
        count_text = (
            f"{selected_count} game{'s' if selected_count != 1 else ''} selected"
        )
        self.text.render(
            screen,
            count_text,
            (inset + self.theme.padding_md, bar_y + bar_height // 2),
            color=self.theme.secondary,
            size=self.theme.font_size_md,
            align="left",
        )

        download_button_rect = None

        if input_mode == "touch":
            # For touch mode, render a tappable download button
            button_width = 100
            button_height = 32
            button_rect = pygame.Rect(
                screen_width - inset - self.theme.padding_md - button_width,
                bar_y + (bar_height - button_height) // 2,
                button_width,
                button_height,
            )
            self.action_button.render(screen, button_rect, "Download", hover=True)
            download_button_rect = button_rect
        else:
            # For keyboard/gamepad, show hint text
            hint_text = get_download_hint(input_mode)
            self.text.render(
                screen,
                hint_text,
                (
                    screen_width - inset - self.theme.padding_md,
                    bar_y + bar_height // 2,
                ),
                color=self.theme.warning,
                size=self.theme.font_size_md,
                align="right",
            )

        return download_button_rect


# Default instance
games_screen = GamesScreen()
