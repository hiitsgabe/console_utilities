"""
Screen manager - Coordinates screen rendering based on app state.
"""

import pygame
from typing import Dict, Any, Optional, Tuple, List

from ui.theme import Theme, default_theme
from .systems_screen import SystemsScreen
from .games_screen import GamesScreen
from .settings_screen import SettingsScreen
from .utils_screen import UtilsScreen
from .credits_screen import CreditsScreen
from .add_systems_screen import AddSystemsScreen
from .systems_settings_screen import SystemsSettingsScreen
from .system_settings_screen import SystemSettingsScreen
from .modals.search_modal import SearchModal
from .modals.folder_browser_modal import FolderBrowserModal
from .modals.game_details_modal import GameDetailsModal
from .modals.loading_modal import LoadingModal
from .modals.error_modal import ErrorModal
from .modals.url_input_modal import UrlInputModal
from .modals.folder_name_modal import FolderNameModal


class ScreenManager:
    """
    Screen manager.

    Coordinates which screen to render based on
    application state.
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme

        # Initialize screens
        self.systems_screen = SystemsScreen(theme)
        self.games_screen = GamesScreen(theme)
        self.settings_screen = SettingsScreen(theme)
        self.utils_screen = UtilsScreen(theme)
        self.credits_screen = CreditsScreen(theme)
        self.add_systems_screen = AddSystemsScreen(theme)
        self.systems_settings_screen = SystemsSettingsScreen(theme)
        self.system_settings_screen = SystemSettingsScreen(theme)

        # Initialize modals
        self.search_modal = SearchModal(theme)
        self.folder_browser_modal = FolderBrowserModal(theme)
        self.game_details_modal = GameDetailsModal(theme)
        self.loading_modal = LoadingModal(theme)
        self.error_modal = ErrorModal(theme)
        self.url_input_modal = UrlInputModal(theme)
        self.folder_name_modal = FolderNameModal(theme)

    def render(
        self,
        screen: pygame.Surface,
        state: Any,
        settings: Dict[str, Any],
        data: List[Dict[str, Any]],
        get_thumbnail=None,
        get_hires_image=None
    ) -> Dict[str, Any]:
        """
        Render the appropriate screen based on state.

        Args:
            screen: Surface to render to
            state: Application state object
            settings: Settings dictionary
            data: System data list
            get_thumbnail: Function to get thumbnail for a game
            get_hires_image: Function to get hi-res image

        Returns:
            Dictionary of interactive element rects
        """
        rects = {}

        # Check for modals first (they overlay the current screen)
        if state.show_search_input:
            modal_rect, content_rect, close_rect, char_rects = self.search_modal.render(
                screen,
                state.search.input_text,
                state.search.cursor_position
            )
            rects['modal'] = modal_rect
            rects['close'] = close_rect
            rects['char_rects'] = char_rects
            return rects

        if state.folder_browser.show:
            modal_rect, item_rects, select_rect, cancel_rect = self.folder_browser_modal.render(
                screen,
                state.folder_browser.current_path,
                state.folder_browser.items,
                state.folder_browser.highlighted,
                state.folder_browser.selected_system_to_add.get('type', 'folder') if state.folder_browser.selected_system_to_add else 'folder'
            )
            rects['modal'] = modal_rect
            rects['item_rects'] = item_rects
            rects['select_button'] = select_rect
            rects['cancel_button'] = cancel_rect
            return rects

        if state.game_details.show and state.game_details.current_game:
            hires_image = get_hires_image(state.game_details.current_game) if get_hires_image else None
            modal_rect, download_rect, close_rect = self.game_details_modal.render(
                screen,
                state.game_details.current_game,
                hires_image
            )
            rects['modal'] = modal_rect
            rects['download_button'] = download_rect
            rects['close'] = close_rect
            return rects

        if state.url_input.show:
            modal_rect, content_rect, close_rect, char_rects = self.url_input_modal.render(
                screen,
                state.url_input.input_text,
                state.url_input.cursor_position,
                state.url_input.context
            )
            rects['modal'] = modal_rect
            rects['close'] = close_rect
            rects['char_rects'] = char_rects
            return rects

        if state.folder_name_input.show:
            modal_rect, content_rect, close_rect, char_rects = self.folder_name_modal.render(
                screen,
                state.folder_name_input.input_text,
                state.folder_name_input.cursor_position
            )
            rects['modal'] = modal_rect
            rects['close'] = close_rect
            rects['char_rects'] = char_rects
            return rects

        # Render main screens based on mode
        if state.mode == "systems":
            visible_systems = self._get_visible_systems(data, settings)
            back_rect, item_rects, scroll_offset = self.systems_screen.render(
                screen, visible_systems, state.highlighted
            )
            rects['back'] = back_rect
            rects['item_rects'] = item_rects
            rects['scroll_offset'] = scroll_offset

        elif state.mode == "games":
            current_system = data[state.selected_system] if state.selected_system < len(data) else {}
            system_name = current_system.get('name', 'Unknown')
            game_list = state.search.filtered_list if state.search.mode else state.game_list

            back_rect, item_rects, scroll_offset = self.games_screen.render(
                screen,
                system_name,
                game_list,
                state.highlighted,
                state.selected_games,
                view_type=settings.get('view_type', 'grid'),
                search_query=state.search.query if state.search.mode else "",
                get_thumbnail=get_thumbnail
            )
            rects['back'] = back_rect
            rects['item_rects'] = item_rects
            rects['scroll_offset'] = scroll_offset

        elif state.mode == "settings":
            back_rect, item_rects, scroll_offset = self.settings_screen.render(
                screen, state.highlighted, settings
            )
            rects['back'] = back_rect
            rects['item_rects'] = item_rects
            rects['scroll_offset'] = scroll_offset

        elif state.mode == "utils":
            back_rect, item_rects, scroll_offset = self.utils_screen.render(
                screen, state.highlighted
            )
            rects['back'] = back_rect
            rects['item_rects'] = item_rects
            rects['scroll_offset'] = scroll_offset

        elif state.mode == "credits":
            back_rect = self.credits_screen.render(screen)
            rects['back'] = back_rect

        elif state.mode == "add_systems":
            back_rect, item_rects, scroll_offset = self.add_systems_screen.render(
                screen, state.add_systems_highlighted, state.available_systems
            )
            rects['back'] = back_rect
            rects['item_rects'] = item_rects
            rects['scroll_offset'] = scroll_offset

        elif state.mode == "systems_settings":
            hidden_systems = self._get_hidden_system_names(data, settings)
            back_rect, item_rects, scroll_offset = self.systems_settings_screen.render(
                screen, state.systems_settings_highlighted, data, hidden_systems
            )
            rects['back'] = back_rect
            rects['item_rects'] = item_rects
            rects['scroll_offset'] = scroll_offset

        elif state.mode == "system_settings":
            if state.selected_system_for_settings is not None and state.selected_system_for_settings < len(data):
                system = data[state.selected_system_for_settings]
                system_name = system.get('name', '')
                system_settings = settings.get("system_settings", {})
                is_hidden = system_settings.get(system_name, {}).get('hidden', False)
                back_rect, item_rects, scroll_offset = self.system_settings_screen.render(
                    screen, state.system_settings_highlighted, system, is_hidden
                )
                rects['back'] = back_rect
                rects['item_rects'] = item_rects
                rects['scroll_offset'] = scroll_offset

        return rects

    def _get_visible_systems(
        self,
        data: List[Dict[str, Any]],
        settings: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Get visible systems (not hidden, not list_systems)."""
        system_settings = settings.get("system_settings", {})
        return [
            d for d in data
            if not d.get('list_systems', False)
            and not system_settings.get(d['name'], {}).get('hidden', False)
        ]

    def _get_hidden_system_names(
        self,
        data: List[Dict[str, Any]],
        settings: Dict[str, Any]
    ) -> set:
        """Get set of hidden system names."""
        system_settings = settings.get("system_settings", {})
        return {
            name for name, sys_settings in system_settings.items()
            if sys_settings.get('hidden', False)
        }


# Default instance
screen_manager = ScreenManager()
