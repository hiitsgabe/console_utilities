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
from .modals.confirm_modal import ConfirmModal
from .modals.ia_login_modal import IALoginModal
from .modals.ia_download_modal import IADownloadModal
from .modals.ia_collection_modal import IACollectionModal
from .modals.scraper_wizard_modal import ScraperWizardModal
from .modals.scraper_login_modal import ScraperLoginModal
from .modals.dedupe_wizard_modal import DedupeWizardModal
from .modals.rename_wizard_modal import RenameWizardModal
from .modals.ghost_cleaner_modal import GhostCleanerModal
from .downloads_screen import DownloadsScreen
from .scraper_downloads_screen import ScraperDownloadsScreen
from ui.molecules.status_footer import StatusFooter, StatusFooterItem


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
        self.downloads_screen = DownloadsScreen(theme)
        self.scraper_downloads_screen = ScraperDownloadsScreen(theme)

        # Initialize modals
        self.search_modal = SearchModal(theme)
        self.folder_browser_modal = FolderBrowserModal(theme)
        self.game_details_modal = GameDetailsModal(theme)
        self.loading_modal = LoadingModal(theme)
        self.error_modal = ErrorModal(theme)
        self.url_input_modal = UrlInputModal(theme)
        self.folder_name_modal = FolderNameModal(theme)
        self.confirm_modal = ConfirmModal(theme)
        self.ia_login_modal = IALoginModal(theme)
        self.ia_download_modal = IADownloadModal(theme)
        self.ia_collection_modal = IACollectionModal(theme)
        self.scraper_login_modal = ScraperLoginModal(theme)
        self.scraper_wizard_modal = ScraperWizardModal(theme)
        self.dedupe_wizard_modal = DedupeWizardModal(theme)
        self.rename_wizard_modal = RenameWizardModal(theme)
        self.ghost_cleaner_modal = GhostCleanerModal(theme)

        # Initialize generic status footer
        self.status_footer = StatusFooter(theme)

    def render(
        self,
        screen: pygame.Surface,
        state: Any,
        settings: Dict[str, Any],
        data: List[Dict[str, Any]],
        get_thumbnail=None,
        get_hires_image=None,
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
        # Loading modal has highest priority
        if state.loading.show:
            self.loading_modal.render(
                screen,
                state.loading.message,
                state.loading.progress / 100.0 if state.loading.progress else None,
            )
            return rects

        if state.confirm_modal.show:
            modal_rect, ok_rect, cancel_rect, close_rect = self.confirm_modal.render(
                screen,
                state.confirm_modal.title,
                state.confirm_modal.message_lines,
                state.confirm_modal.ok_label,
                state.confirm_modal.cancel_label,
                state.confirm_modal.button_index,
            )
            rects["modal"] = modal_rect
            rects["confirm_ok"] = ok_rect
            rects["confirm_cancel"] = cancel_rect
            rects["close"] = close_rect
            return rects

        if state.show_search_input:
            modal_rect, content_rect, close_rect, char_rects = self.search_modal.render(
                screen,
                state.search.input_text,
                state.search.cursor_position,
                input_mode=state.input_mode,
                shift_active=state.search.shift_active,
            )
            rects["modal"] = modal_rect
            rects["close"] = close_rect
            rects["char_rects"] = char_rects
            return rects

        if state.folder_browser.show:
            modal_rect, item_rects, select_rect, cancel_rect, close_rect = (
                self.folder_browser_modal.render(
                    screen,
                    state.folder_browser.current_path,
                    state.folder_browser.items,
                    state.folder_browser.highlighted,
                    (
                        state.folder_browser.selected_system_to_add.get(
                            "type", "folder"
                        )
                        if state.folder_browser.selected_system_to_add
                        else "folder"
                    ),
                    focus_area=state.folder_browser.focus_area,
                    button_index=state.folder_browser.button_index,
                )
            )
            rects["modal"] = modal_rect
            rects["item_rects"] = item_rects
            rects["select_button"] = select_rect
            rects["cancel_button"] = cancel_rect
            rects["close"] = close_rect
            return rects

        if state.game_details.show and state.game_details.current_game:
            hires_image = (
                get_hires_image(state.game_details.current_game)
                if get_hires_image
                else None
            )
            modal_rect, download_rect, close_rect = self.game_details_modal.render(
                screen,
                state.game_details.current_game,
                hires_image,
                button_focused=state.game_details.button_focused,
                loading_size=state.game_details.loading_size,
                input_mode=state.input_mode,
                text_scroll_offset=state.text_scroll_offset,
            )
            rects["modal"] = modal_rect
            rects["download_button"] = download_rect
            rects["close"] = close_rect
            return rects

        if state.url_input.show:
            modal_rect, content_rect, close_rect, char_rects = (
                self.url_input_modal.render(
                    screen,
                    state.url_input.input_text,
                    state.url_input.cursor_position,
                    state.url_input.context,
                    input_mode=state.input_mode,
                    shift_active=state.url_input.shift_active,
                )
            )
            rects["modal"] = modal_rect
            rects["close"] = close_rect
            rects["char_rects"] = char_rects
            return rects

        if state.folder_name_input.show:
            modal_rect, content_rect, close_rect, char_rects = (
                self.folder_name_modal.render(
                    screen,
                    state.folder_name_input.input_text,
                    state.folder_name_input.cursor_position,
                    input_mode=state.input_mode,
                    shift_active=state.folder_name_input.shift_active,
                )
            )
            rects["modal"] = modal_rect
            rects["close"] = close_rect
            rects["char_rects"] = char_rects
            return rects

        # Internet Archive modals
        if state.ia_login.show:
            modal_rect, content_rect, close_rect, char_rects = (
                self.ia_login_modal.render(
                    screen,
                    state.ia_login.step,
                    state.ia_login.email,
                    state.ia_login.password,
                    state.ia_login.cursor_position,
                    state.ia_login.error_message,
                    input_mode=state.input_mode,
                    shift_active=state.ia_login.shift_active,
                )
            )
            rects["modal"] = modal_rect
            rects["close"] = close_rect
            rects["char_rects"] = char_rects
            return rects

        if state.ia_download_wizard.show:
            modal_rect, content_rect, close_rect, char_rects, item_rects = (
                self.ia_download_modal.render(
                    screen,
                    state.ia_download_wizard.step,
                    state.ia_download_wizard.url,
                    state.ia_download_wizard.item_id,
                    state.ia_download_wizard.files_list,
                    state.ia_download_wizard.selected_file_index,
                    state.ia_download_wizard.output_folder,
                    state.ia_download_wizard.should_extract,
                    state.ia_download_wizard.cursor_position,
                    state.ia_download_wizard.error_message,
                    input_mode=state.input_mode,
                    shift_active=state.ia_download_wizard.shift_active,
                    display_items=state.ia_download_wizard.display_items,
                    current_folder=state.ia_download_wizard.current_folder,
                )
            )
            rects["modal"] = modal_rect
            rects["close"] = close_rect
            rects["char_rects"] = char_rects
            rects["item_rects"] = item_rects
            return rects

        if state.ia_collection_wizard.show:
            modal_rect, content_rect, close_rect, char_rects, item_rects = (
                self.ia_collection_modal.render(
                    screen,
                    state.ia_collection_wizard.step,
                    state.ia_collection_wizard.url,
                    state.ia_collection_wizard.item_id,
                    state.ia_collection_wizard.collection_name,
                    state.ia_collection_wizard.folder_name,
                    state.ia_collection_wizard.available_formats,
                    state.ia_collection_wizard.selected_formats,
                    state.ia_collection_wizard.format_highlighted,
                    state.ia_collection_wizard.should_unzip,
                    state.ia_collection_wizard.cursor_position,
                    state.ia_collection_wizard.error_message,
                    input_mode=state.input_mode,
                    adding_custom_format=state.ia_collection_wizard.adding_custom_format,
                    custom_format_input=state.ia_collection_wizard.custom_format_input,
                    extract_contents=state.ia_collection_wizard.extract_contents,
                    options_highlighted=state.ia_collection_wizard.options_highlighted,
                    shift_active=state.ia_collection_wizard.shift_active,
                )
            )
            rects["modal"] = modal_rect
            rects["close"] = close_rect
            rects["char_rects"] = char_rects
            rects["item_rects"] = item_rects
            return rects

        if state.scraper_login.show:
            modal_rect, content_rect, close_rect, char_rects = (
                self.scraper_login_modal.render(
                    screen,
                    state.scraper_login.provider,
                    state.scraper_login.step,
                    state.scraper_login.username,
                    state.scraper_login.password,
                    state.scraper_login.api_key,
                    state.scraper_login.cursor_position,
                    state.scraper_login.error_message,
                    input_mode=state.input_mode,
                    shift_active=state.scraper_login.shift_active,
                )
            )
            rects["modal"] = modal_rect
            rects["close"] = close_rect
            rects["char_rects"] = char_rects
            return rects

        if state.scraper_wizard.show:
            modal_rect, content_rect, close_rect, item_rects = (
                self.scraper_wizard_modal.render(
                    screen,
                    state.scraper_wizard.step,
                    state.scraper_wizard.folder_items,
                    state.scraper_wizard.folder_highlighted,
                    state.scraper_wizard.folder_current_path,
                    state.scraper_wizard.selected_rom_path,
                    state.scraper_wizard.selected_rom_name,
                    state.scraper_wizard.search_results,
                    state.scraper_wizard.selected_game_index,
                    state.scraper_wizard.available_images,
                    state.scraper_wizard.selected_images,
                    state.scraper_wizard.image_highlighted,
                    state.scraper_wizard.download_progress,
                    state.scraper_wizard.current_download,
                    state.scraper_wizard.error_message,
                    input_mode=state.input_mode,
                    available_videos=state.scraper_wizard.available_videos,
                    selected_video_index=state.scraper_wizard.selected_video_index,
                    video_highlighted=state.scraper_wizard.video_highlighted,
                    batch_mode=state.scraper_wizard.batch_mode,
                    batch_roms=state.scraper_wizard.batch_roms,
                    batch_current_index=state.scraper_wizard.batch_current_index,
                    batch_auto_select=state.scraper_wizard.batch_auto_select,
                    batch_default_images=state.scraper_wizard.batch_default_images,
                    mixed_images_enabled=(
                        settings.get("scraper_mixed_images", False)
                        and settings.get("scraper_provider", "libretro")
                        == "screenscraper"
                    ),
                    download_video=state.scraper_queue.download_video,
                )
            )
            rects["modal"] = modal_rect
            rects["close"] = close_rect
            rects["item_rects"] = item_rects
            return rects

        if state.dedupe_wizard.show:
            modal_rect, content_rect, close_rect, item_rects = (
                self.dedupe_wizard_modal.render(
                    screen,
                    state.dedupe_wizard.step,
                    state.dedupe_wizard.mode,
                    state.dedupe_wizard.folder_path,
                    state.dedupe_wizard.folder_items,
                    state.dedupe_wizard.folder_highlighted,
                    state.dedupe_wizard.duplicate_groups,
                    state.dedupe_wizard.current_group_index,
                    state.dedupe_wizard.selected_to_keep,
                    state.dedupe_wizard.scan_progress,
                    state.dedupe_wizard.process_progress,
                    state.dedupe_wizard.files_scanned,
                    state.dedupe_wizard.total_files,
                    state.dedupe_wizard.files_removed,
                    state.dedupe_wizard.space_freed,
                    state.dedupe_wizard.error_message,
                    mode_highlighted=state.dedupe_wizard.mode_highlighted,
                    input_mode=state.input_mode,
                    confirmed_groups=state.dedupe_wizard.confirmed_groups,
                )
            )
            rects["modal"] = modal_rect
            rects["close"] = close_rect
            rects["item_rects"] = item_rects
            return rects

        if state.rename_wizard.show:
            modal_rect, content_rect, close_rect, item_rects = (
                self.rename_wizard_modal.render(
                    screen,
                    state.rename_wizard.step,
                    state.rename_wizard.mode,
                    state.rename_wizard.rename_items,
                    state.rename_wizard.current_item_index,
                    state.rename_wizard.scan_progress,
                    state.rename_wizard.process_progress,
                    state.rename_wizard.files_scanned,
                    state.rename_wizard.total_files,
                    state.rename_wizard.files_renamed,
                    state.rename_wizard.error_message,
                    mode_highlighted=state.rename_wizard.mode_highlighted,
                    input_mode=state.input_mode,
                )
            )
            rects["modal"] = modal_rect
            rects["close"] = close_rect
            rects["item_rects"] = item_rects
            return rects

        if state.ghost_cleaner_wizard.show:
            modal_rect, content_rect, close_rect, item_rects = (
                self.ghost_cleaner_modal.render(
                    screen,
                    state.ghost_cleaner_wizard.step,
                    state.ghost_cleaner_wizard.folder_path,
                    state.ghost_cleaner_wizard.ghost_files,
                    state.ghost_cleaner_wizard.scan_progress,
                    state.ghost_cleaner_wizard.clean_progress,
                    state.ghost_cleaner_wizard.files_scanned,
                    state.ghost_cleaner_wizard.total_files,
                    state.ghost_cleaner_wizard.files_removed,
                    state.ghost_cleaner_wizard.space_freed,
                    state.ghost_cleaner_wizard.error_message,
                    input_mode=state.input_mode,
                )
            )
            rects["modal"] = modal_rect
            rects["close"] = close_rect
            rects["item_rects"] = item_rects
            return rects

        # Render main screens based on mode
        if state.mode == "systems":
            back_rect, item_rects, scroll_offset = self.systems_screen.render(
                screen, [], state.highlighted
            )
            rects["back"] = back_rect
            rects["item_rects"] = item_rects
            rects["scroll_offset"] = scroll_offset

        elif state.mode == "systems_list":
            visible_systems = self._get_visible_systems(data, settings)
            back_rect, item_rects, scroll_offset = (
                self.systems_screen.render_systems_list(
                    screen, visible_systems, state.systems_list_highlighted
                )
            )
            rects["back"] = back_rect
            rects["item_rects"] = item_rects
            rects["scroll_offset"] = scroll_offset

        elif state.mode == "games":
            current_system = (
                data[state.selected_system] if state.selected_system < len(data) else {}
            )
            system_name = current_system.get("name", "Unknown")
            game_list = (
                state.search.filtered_list if state.search.mode else state.game_list
            )

            back_rect, item_rects, scroll_offset, download_btn, download_all_btn = (
                self.games_screen.render(
                    screen,
                    system_name,
                    game_list,
                    state.highlighted,
                    state.selected_games,
                    search_query=state.search.query if state.search.mode else "",
                    get_thumbnail=get_thumbnail,
                    input_mode=state.input_mode,
                    show_download_all=settings.get("show_download_all", False),
                    text_scroll_offset=state.text_scroll_offset,
                )
            )
            rects["back"] = back_rect
            rects["item_rects"] = item_rects
            rects["scroll_offset"] = scroll_offset
            if download_btn:
                rects["download_button"] = download_btn
            if download_all_btn:
                rects["download_all_button"] = download_all_btn

        elif state.mode == "settings":
            back_rect, item_rects, scroll_offset = self.settings_screen.render(
                screen, state.highlighted, settings, data
            )
            rects["back"] = back_rect
            rects["item_rects"] = item_rects
            rects["scroll_offset"] = scroll_offset

        elif state.mode == "utils":
            back_rect, item_rects, scroll_offset = self.utils_screen.render(
                screen, state.highlighted, settings
            )
            rects["back"] = back_rect
            rects["item_rects"] = item_rects
            rects["scroll_offset"] = scroll_offset

        elif state.mode == "credits":
            back_rect, max_scroll = self.credits_screen.render(
                screen,
                input_mode=state.input_mode,
                scroll_offset=state.credits_scroll_offset,
            )
            rects["back"] = back_rect
            rects["credits_max_scroll"] = max_scroll

        elif state.mode == "add_systems":
            back_rect, item_rects, scroll_offset = self.add_systems_screen.render(
                screen, state.add_systems_highlighted, state.available_systems
            )
            rects["back"] = back_rect
            rects["item_rects"] = item_rects
            rects["scroll_offset"] = scroll_offset

        elif state.mode == "systems_settings":
            hidden_systems = self._get_hidden_system_names(data, settings)
            back_rect, item_rects, scroll_offset = self.systems_settings_screen.render(
                screen, state.systems_settings_highlighted, data, hidden_systems
            )
            rects["back"] = back_rect
            rects["item_rects"] = item_rects
            rects["scroll_offset"] = scroll_offset

        elif state.mode == "system_settings":
            if (
                state.selected_system_for_settings is not None
                and state.selected_system_for_settings < len(data)
            ):
                system = data[state.selected_system_for_settings]
                system_name = system.get("name", "")
                system_settings = settings.get("system_settings", {})
                is_hidden = system_settings.get(system_name, {}).get("hidden", False)
                back_rect, item_rects, scroll_offset = (
                    self.system_settings_screen.render(
                        screen, state.system_settings_highlighted, system, is_hidden
                    )
                )
                rects["back"] = back_rect
                rects["item_rects"] = item_rects
                rects["scroll_offset"] = scroll_offset

        elif state.mode == "downloads":
            back_rect, item_rects, scroll_offset = self.downloads_screen.render(
                screen,
                state.download_queue,
                get_thumbnail=get_thumbnail,
                input_mode=state.input_mode,
            )
            rects["back"] = back_rect
            rects["item_rects"] = item_rects
            rects["scroll_offset"] = scroll_offset

        elif state.mode == "scraper_downloads":
            back_rect, item_rects, scroll_offset = (
                self.scraper_downloads_screen.render(
                    screen,
                    state.scraper_queue,
                    input_mode=state.input_mode,
                )
            )
            rects["back"] = back_rect
            rects["item_rects"] = item_rects
            rects["scroll_offset"] = scroll_offset

        # Render stacked status footers on non-download screens
        if state.mode not in ("downloads", "scraper_downloads"):
            footer_items = self._build_footer_items(state)
            if footer_items:
                self.status_footer.render(screen, footer_items)

        return rects

    def _build_footer_items(self, state) -> list:
        """Build list of StatusFooterItems from active background tasks."""
        items = []

        # Download queue footer
        dq = state.download_queue
        if dq.items:
            has_active = any(
                it.status in ("waiting", "downloading", "extracting", "moving")
                for it in dq.items
            )
            if has_active:
                total = len(dq.items)
                completed = sum(1 for it in dq.items if it.status == "completed")
                active_item = None
                for it in dq.items:
                    if it.status in ("downloading", "extracting", "moving"):
                        active_item = it
                        break

                if active_item:
                    label = f"Downloading {completed + 1} of {total} games"
                    progress = (
                        active_item.progress
                        if active_item.status == "downloading"
                        else None
                    )
                else:
                    waiting = sum(1 for it in dq.items if it.status == "waiting")
                    label = (
                        f"Queued: {waiting} games"
                        if waiting
                        else f"Downloads complete ({completed}/{total})"
                    )
                    progress = None

                items.append(
                    StatusFooterItem(
                        label=label,
                        progress=progress,
                        color=self.theme.secondary,
                    )
                )

        # Scraper queue footer (only while actively scraping)
        sq = state.scraper_queue
        if sq.active:
            total = len(sq.items)
            done = sum(1 for it in sq.items if it.status == "done")
            progress = done / total if total > 0 else 0.0
            items.append(
                StatusFooterItem(
                    label=sq.current_status or f"Scraping: {done}/{total}",
                    progress=progress,
                    color=self.theme.primary,
                )
            )

        return items

    def _get_visible_systems(
        self, data: List[Dict[str, Any]], settings: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Get visible systems (not hidden, not list_systems, respects NSZ setting)."""
        from services.data_loader import get_visible_systems

        # Use the same function as navigation to ensure consistency
        return get_visible_systems(data, settings)

    def _get_hidden_system_names(
        self, data: List[Dict[str, Any]], settings: Dict[str, Any]
    ) -> set:
        """Get set of hidden system names."""
        system_settings = settings.get("system_settings", {})
        return {
            name
            for name, sys_settings in system_settings.items()
            if sys_settings.get("hidden", False)
        }


# Default instance
screen_manager = ScreenManager()
