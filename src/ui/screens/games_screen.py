"""
Games screen - Display games for a selected system.
"""

import pygame
from typing import List, Dict, Any, Tuple, Optional, Set, Callable

from ui.theme import Theme, default_theme
from ui.templates.list_screen import ListScreenTemplate
from ui.templates.grid_screen import GridScreenTemplate
from ui.atoms.text import Text
from ui.molecules.thumbnail import Thumbnail


class GamesScreen:
    """
    Games screen.

    Displays games for a selected system in either
    list or grid view.
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.list_template = ListScreenTemplate(theme)
        self.grid_template = GridScreenTemplate(theme)
        self.text = Text(theme)
        self.thumbnail = Thumbnail(theme)

    def render(
        self,
        screen: pygame.Surface,
        system_name: str,
        games: List[Any],
        highlighted: int,
        selected_games: Set[int],
        view_type: str = "grid",
        search_query: str = "",
        get_thumbnail: Optional[Callable[[Any], pygame.Surface]] = None
    ) -> Tuple[Optional[pygame.Rect], List[pygame.Rect], int]:
        """
        Render the games screen.

        Args:
            screen: Surface to render to
            system_name: Name of the current system
            games: List of games
            highlighted: Currently highlighted index
            selected_games: Set of selected game indices
            view_type: "list" or "grid"
            search_query: Current search query (for subtitle)
            get_thumbnail: Function to get thumbnail for a game

        Returns:
            Tuple of (back_button_rect, item_rects, scroll_offset)
        """
        title = f"{system_name} Games"
        subtitle = f"Search: {search_query}" if search_query else None

        # Reserve footer space for status bar when games are selected
        footer_height = 40 if selected_games else 0

        if view_type == "grid":
            back_rect, item_rects, scroll_offset = self.grid_template.render(
                screen,
                title=title,
                items=games,
                highlighted=highlighted,
                selected=selected_games,
                show_back=True,
                subtitle=subtitle,
                columns=4,
                get_label=self._get_game_label,
                get_image=get_thumbnail,
                get_placeholder=self._get_placeholder,
                footer_height=footer_height
            )
        else:
            back_rect, item_rects, scroll_offset = self.list_template.render(
                screen,
                title=title,
                items=games,
                highlighted=highlighted,
                selected=selected_games,
                show_back=True,
                subtitle=subtitle,
                item_height=50,
                get_label=self._get_game_label,
                get_thumbnail=get_thumbnail,
                show_checkbox=True,
                footer_height=footer_height
            )

        # Draw status bar when games are selected
        if selected_games:
            self._render_status_bar(screen, len(selected_games))

        return back_rect, item_rects, scroll_offset

    def render_with_buttons(
        self,
        screen: pygame.Surface,
        system_name: str,
        games: List[Any],
        highlighted: int,
        selected_games: Set[int],
        view_type: str = "grid",
        search_query: str = "",
        get_thumbnail: Optional[Callable[[Any], pygame.Surface]] = None
    ) -> Tuple[Optional[pygame.Rect], List[pygame.Rect], int, List[pygame.Rect]]:
        """
        Render games screen with action buttons.

        Returns:
            Tuple of (back_rect, item_rects, scroll_offset, button_rects)
        """
        title = f"{system_name} Games"
        subtitle = f"Search: {search_query}" if search_query else None

        buttons = ["Search", "Download"] if selected_games else ["Search"]

        if view_type == "grid":
            return self.grid_template.render_with_buttons(
                screen,
                title=title,
                items=games,
                highlighted=highlighted,
                selected=selected_games,
                button_labels=buttons,
                show_back=True,
                subtitle=subtitle,
                columns=4,
                get_label=self._get_game_label,
                get_image=get_thumbnail,
                get_placeholder=self._get_placeholder
            )
        else:
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
                show_checkbox=True
            )

    def _get_game_label(self, game: Any) -> str:
        """Extract display label from game."""
        if isinstance(game, dict):
            name = game.get('filename', game.get('name', str(game)))
        else:
            name = str(game)

        # Remove file extension for display
        if '.' in name:
            name = name.rsplit('.', 1)[0]

        return name

    def _get_placeholder(self, game: Any) -> str:
        """Get placeholder initials for game."""
        label = self._get_game_label(game)
        return self.thumbnail.get_placeholder_initials(label)

    def _render_status_bar(self, screen: pygame.Surface, selected_count: int):
        """Render status bar showing selected games count and download hint."""
        screen_width, screen_height = screen.get_size()
        bar_height = 40
        bar_y = screen_height - bar_height

        # Draw semi-transparent background
        bar_surface = pygame.Surface((screen_width, bar_height), pygame.SRCALPHA)
        bar_surface.fill((*self.theme.surface[:3], 230))
        screen.blit(bar_surface, (0, bar_y))

        # Draw selected count on the left
        count_text = f"{selected_count} game{'s' if selected_count != 1 else ''} selected"
        self.text.render(
            screen,
            count_text,
            (self.theme.padding_md, bar_y + bar_height // 2),
            color=self.theme.secondary,
            size=self.theme.font_size_md,
            align="left"
        )

        # Draw download hint on the right
        hint_text = "Press SPACE to download"
        self.text.render(
            screen,
            hint_text,
            (screen_width - self.theme.padding_md, bar_y + bar_height // 2),
            color=self.theme.warning,
            size=self.theme.font_size_md,
            align="right"
        )


# Default instance
games_screen = GamesScreen()
