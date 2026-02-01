"""
Games screen - Display games for a selected system.
"""

import pygame
from typing import List, Dict, Any, Tuple, Optional, Set, Callable

from ui.theme import Theme, default_theme
from ui.templates.list_screen import ListScreenTemplate
from ui.templates.grid_screen import GridScreenTemplate


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

        if view_type == "grid":
            return self.grid_template.render(
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
                get_placeholder=self._get_placeholder
            )
        else:
            return self.list_template.render(
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
                show_checkbox=True
            )

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
        if not label:
            return "?"

        words = label.split()
        if len(words) >= 2:
            return (words[0][0] + words[1][0]).upper()
        elif len(label) >= 2:
            return label[:2].upper()
        return label[0].upper() if label else "?"


# Default instance
games_screen = GamesScreen()
