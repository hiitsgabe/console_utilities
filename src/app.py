"""
Console Utilities Application - Main orchestrator.

This module provides the main application class that coordinates
all components: state, settings, services, input, and UI.
"""

import pygame
import os
import sys
from typing import Optional, Dict, Any

from constants import (
    FPS,
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    FONT_SIZE,
    BACKGROUND,
    SCRIPT_DIR,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    SUCCESS,
    PRIMARY,
)
from state import AppState
from config.settings import (
    load_settings,
    save_settings,
    load_controller_mapping,
    save_controller_mapping,
    needs_controller_mapping,
    get_controller_mapping,
)
from services.data_loader import (
    load_main_systems_data,
    update_json_file_path,
    get_visible_systems,
    get_system_index_by_name,
    add_system_to_added_systems,
)
from services.internet_archive import (
    get_ia_s3_credentials,
    validate_ia_url,
    list_ia_files,
    get_ia_download_url,
    get_available_formats,
    encode_password,
)
from services.file_listing import (
    list_files,
    filter_games_by_search,
    load_folder_contents,
    get_file_size,
    get_roms_folder_for_system,
)
from services.installed_checker import installed_checker
from services.image_cache import ImageCache
from services.download_manager import DownloadManager
from input.navigation import NavigationHandler
from input.controller import ControllerHandler
from input.touch import TouchHandler
from ui.theme import Theme
from ui.screens.screen_manager import ScreenManager
from utils.logging import log_error, init_log_file


class ConsoleUtilitiesApp:
    """
    Main application class for Console Utilities.

    Orchestrates all components and runs the main game loop.
    """

    def __init__(self):
        """Initialize the application."""
        # Initialize logging
        init_log_file()

        # Initialize pygame
        pygame.init()
        pygame.display.set_caption("Console Utilities")

        # Create display
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, FONT_SIZE)

        # Initialize joystick
        pygame.joystick.init()
        self.joystick: Optional[pygame.joystick.JoystickType] = None
        if pygame.joystick.get_count() > 0:
            self.joystick = pygame.joystick.Joystick(0)
            self.joystick.init()
            print(f"Joystick detected: {self.joystick.get_name()}")
        else:
            print("No joystick detected, using keyboard")

        # Initialize theme
        self.theme = Theme()

        # Initialize state
        self.state = AppState()

        # Load settings and data
        self.settings = load_settings()
        update_json_file_path(self.settings)
        self.data = load_main_systems_data(self.settings)

        # Load controller mapping
        load_controller_mapping()
        self.controller_mapping = get_controller_mapping()

        # Initialize handlers
        self.navigation = NavigationHandler()
        self.navigation.set_joystick(self.joystick)
        self.navigation.set_controller_mapping(self.controller_mapping)

        self.controller = ControllerHandler(self.controller_mapping)
        self.controller.set_joystick(self.joystick)

        self.touch = TouchHandler()

        # Initialize screen manager
        self.screen_manager = ScreenManager(self.theme)

        # Initialize image cache service
        self.image_cache = ImageCache()

        # Initialize download manager
        self.download_manager = DownloadManager(
            self.settings, self.state.download_queue
        )

        # Load background image
        self.background_image = self._load_background_image()

        # Check if controller mapping needed
        self.needs_mapping = needs_controller_mapping()

    def _load_background_image(self) -> Optional[pygame.Surface]:
        """Load the background image."""
        possible_paths = [
            os.path.join(SCRIPT_DIR, "assets", "images", "background.png"),
            os.path.join(os.getcwd(), "assets", "images", "background.png"),
        ]

        for path in possible_paths:
            if os.path.exists(path):
                try:
                    return pygame.image.load(path)
                except Exception as e:
                    log_error(f"Failed to load background: {e}")

        return None

    def _collect_controller_mapping(self) -> bool:
        """
        Collect controller button mapping from user input.
        Runs a blocking loop showing which button to press next.

        Returns:
            True if mapping completed, False if cancelled.
        """
        from config.settings import save_controller_mapping

        essential_buttons = [
            ("up", "D-pad UP"),
            ("down", "D-pad DOWN"),
            ("left", "D-pad LEFT"),
            ("right", "D-pad RIGHT"),
            ("select", "SELECT/CONFIRM button (A)"),
            ("back", "BACK/CANCEL button (B)"),
            ("start", "START/MENU button"),
            ("detail", "DETAIL button (Y)"),
            ("search", "SEARCH button (X)"),
            ("left_shoulder", "Left Shoulder (L)"),
            ("right_shoulder", "Right Shoulder (R)"),
        ]

        mapping = {}
        current_index = 0
        last_input_time = 0

        while current_index < len(essential_buttons):
            current_time = pygame.time.get_ticks()

            # Draw
            self._draw_background()

            title_surf = self.font.render("Controller Setup", True, TEXT_PRIMARY)
            self.screen.blit(title_surf, (20, 20))

            button_key, button_desc = essential_buttons[current_index]
            instruction_surf = self.font.render(
                f"Press the {button_desc}", True, TEXT_PRIMARY
            )
            self.screen.blit(instruction_surf, (20, 80))

            progress_surf = self.font.render(
                f"Button {current_index + 1} of {len(essential_buttons)}",
                True,
                TEXT_SECONDARY,
            )
            self.screen.blit(progress_surf, (20, 120))

            # Show already mapped buttons
            y_offset = 160
            for i, (mapped_key, _) in enumerate(essential_buttons[:current_index]):
                val = mapping.get(mapped_key, "?")
                mapped_surf = self.font.render(f"{mapped_key}: {val}", True, SUCCESS)
                self.screen.blit(mapped_surf, (20, y_offset + i * 25))

            pygame.display.flip()

            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return False

                elif event.type == pygame.KEYDOWN:
                    log_error(f"MAPPING KEYDOWN: key={event.key}")
                    if event.key == pygame.K_ESCAPE:
                        return False

                elif event.type == pygame.JOYBUTTONDOWN:
                    log_error(f"MAPPING JOYBUTTONDOWN: button={event.button}")
                    if current_time - last_input_time > 300:
                        mapping[button_key] = event.button
                        current_index += 1
                        last_input_time = current_time

                elif event.type == pygame.JOYHATMOTION:
                    log_error(f"MAPPING JOYHATMOTION: value={event.value}")
                    if current_time - last_input_time > 300:
                        hat_x, hat_y = event.value
                        if button_key == "up" and hat_y == 1:
                            mapping[button_key] = ("hat", 0, 1)
                            current_index += 1
                            last_input_time = current_time
                        elif button_key == "down" and hat_y == -1:
                            mapping[button_key] = ("hat", 0, -1)
                            current_index += 1
                            last_input_time = current_time
                        elif button_key == "left" and hat_x == -1:
                            mapping[button_key] = ("hat", -1, 0)
                            current_index += 1
                            last_input_time = current_time
                        elif button_key == "right" and hat_x == 1:
                            mapping[button_key] = ("hat", 1, 0)
                            current_index += 1
                            last_input_time = current_time

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    # Touchscreen mode: skip mapping
                    mapping = {"touchscreen_mode": True}
                    save_controller_mapping(mapping)
                    return True

            pygame.time.wait(16)

        # Save completed mapping
        save_controller_mapping(mapping)

        # Update handlers with new mapping
        self.controller_mapping = mapping
        self.controller.set_mapping(mapping)
        self.navigation.set_controller_mapping(mapping)

        return True

    def _draw_background(self):
        """Draw the background."""
        if self.background_image:
            scaled_bg = pygame.transform.scale(
                self.background_image, self.screen.get_size()
            )
            self.screen.blit(scaled_bg, (0, 0))

            # Semi-transparent overlay
            overlay = pygame.Surface(self.screen.get_size())
            overlay.set_alpha(100)
            overlay.fill((0, 0, 0))
            self.screen.blit(overlay, (0, 0))
        else:
            self.screen.fill(BACKGROUND)

    def _get_thumbnail(self, game: Any) -> Optional[pygame.Surface]:
        """Get thumbnail for a game."""
        if self.state.selected_system < 0 or self.state.selected_system >= len(
            self.data
        ):
            return None

        system_data = self.data[self.state.selected_system]
        boxart_url = system_data.get("boxarts", "")

        return self.image_cache.get_thumbnail(game, boxart_url, self.settings)

    def _get_hires_image(self, game: Any) -> Optional[pygame.Surface]:
        """Get hi-res image for a game."""
        if self.state.selected_system < 0 or self.state.selected_system >= len(
            self.data
        ):
            return None

        system_data = self.data[self.state.selected_system]
        boxart_url = system_data.get("boxarts", "")

        return self.image_cache.get_hires_image(game, boxart_url, self.settings)

    def _show_loading(self, message: str = "Loading..."):
        """Show loading spinner and update display."""
        self.state.loading.show = True
        self.state.loading.message = message
        self.state.loading.progress = 0
        self._render_frame()

    def _hide_loading(self):
        """Hide loading spinner."""
        self.state.loading.show = False
        self.state.loading.message = ""
        self.state.loading.progress = 0

    def _extract_zip_file(self, zip_path: str):
        """Extract a ZIP file to the same folder."""
        import threading
        from zipfile import ZipFile

        output_folder = os.path.dirname(zip_path)
        zip_name = os.path.basename(zip_path)

        self.state.folder_browser.show = False
        self._show_loading(f"Extracting {zip_name}...")

        def extract():
            try:
                with ZipFile(zip_path, "r") as zip_ref:
                    total_files = len(zip_ref.namelist())
                    for i, file_info in enumerate(zip_ref.infolist()):
                        zip_ref.extract(file_info, output_folder)
                        progress = int((i + 1) / total_files * 100)
                        self.state.loading.progress = progress
                        self.state.loading.message = (
                            f"Extracting {zip_name}... {progress}%"
                        )

                self._hide_loading()
            except Exception as e:
                from utils.logging import log_error

                log_error(f"Failed to extract ZIP: {e}")
                self._hide_loading()

        thread = threading.Thread(target=extract, daemon=True)
        thread.start()

    def _render_frame(self):
        """Render a single frame (used during loading)."""
        self._draw_background()
        self.screen_manager.render(
            self.screen,
            self.state,
            self.settings,
            self.data,
            get_thumbnail=self._get_thumbnail,
            get_hires_image=self._get_hires_image,
        )
        pygame.display.flip()
        # Process events to prevent freezing
        pygame.event.pump()

    def run(self):
        """Run the main application loop."""
        running = True

        # Force controller mapping on first run (or if mapping is incomplete)
        if self.needs_mapping and self.joystick is not None:
            if not self._collect_controller_mapping():
                pygame.quit()
                return
            self.needs_mapping = False

        while running:
            self.clock.tick(FPS)

            # Update navigation state
            self.navigation.update()

            # Handle continuous navigation
            if not self.needs_mapping:
                self.navigation.handle_continuous(self._on_navigate)

            # Process events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.KEYDOWN:
                    log_error(
                        f"KEYDOWN: key={event.key}, unicode='{event.unicode}', joystick={'connected' if self.joystick else 'none'}"
                    )
                    # Skip keyboard navigation keys if joystick is connected (prevents double input)
                    if self.joystick is not None and event.key in (
                        pygame.K_UP,
                        pygame.K_DOWN,
                        pygame.K_LEFT,
                        pygame.K_RIGHT,
                        pygame.K_RETURN,
                        pygame.K_ESCAPE,
                        pygame.K_SPACE,
                    ):
                        continue
                    self.state.input_mode = "keyboard"
                    self._handle_key_event(event)

                elif event.type == pygame.JOYBUTTONDOWN:
                    log_error(f"JOYBUTTONDOWN: button={event.button}, joy={event.joy}")
                    self.state.input_mode = "gamepad"
                    self._handle_joystick_event(event)

                elif event.type == pygame.JOYHATMOTION:
                    log_error(f"JOYHATMOTION: value={event.value}, joy={event.joy}")
                    self.state.input_mode = "gamepad"
                    self._handle_joystick_event(event)

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        self.state.input_mode = "touch"
                        self.touch.handle_mouse_down(event)

                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1:
                        self.touch.handle_mouse_up(event, on_click=self._handle_click)

                elif event.type == pygame.MOUSEWHEEL:
                    self.touch.handle_mouse_wheel(event, on_scroll=self._handle_scroll)

                elif event.type == pygame.MOUSEMOTION:
                    self.touch.handle_mouse_motion(event, on_scroll=self._handle_scroll)

            # Update image cache (process loaded images from background threads)
            self.image_cache.update()

            # Draw
            self._draw_background()

            # Render current screen
            rects = self.screen_manager.render(
                self.screen,
                self.state,
                self.settings,
                self.data,
                get_thumbnail=self._get_thumbnail,
                get_hires_image=self._get_hires_image,
            )

            # Store rects for click handling
            self.state.ui_rects.menu_items = rects.get("item_rects", [])
            self.state.ui_rects.back_button = rects.get("back")
            self.state.ui_rects.download_button = rects.get("download_button")
            self.state.ui_rects.close_button = rects.get("close")
            self.state.ui_rects.modal_char_rects = rects.get("char_rects", [])
            self.state.ui_rects.scroll_offset = rects.get("scroll_offset", 0)
            self.state.ui_rects.folder_select_button = rects.get("select_button")
            self.state.ui_rects.folder_cancel_button = rects.get("cancel_button")
            self.state.ui_rects.confirm_ok_button = rects.get("confirm_ok")
            self.state.ui_rects.confirm_cancel_button = rects.get("confirm_cancel")

            pygame.display.flip()

        # Cleanup
        pygame.quit()

    def _on_navigate(self, direction: str, hat: tuple):
        """Handle navigation from held direction."""
        self._move_highlight(direction)

    def _move_highlight(self, direction: str):
        """Move highlight in the given direction."""
        # Check modals first (they take priority over modes)
        if self.state.show_search_input:
            self._navigate_keyboard_modal(
                direction, self.state.search, char_set="default"
            )
            return

        if self.state.game_details.show:
            # Game details modal has only Download button, always focused
            return

        if self.state.folder_browser.show:
            self._navigate_folder_browser(direction)
            return

        if self.state.url_input.show:
            self._navigate_keyboard_modal(
                direction, self.state.url_input, char_set="url"
            )
            return

        if self.state.folder_name_input.show:
            self._navigate_keyboard_modal(
                direction, self.state.folder_name_input, char_set="default"
            )
            return

        if self.state.confirm_modal.show:
            # Navigate between OK and Cancel buttons
            if direction in ("left", "right"):
                self.state.confirm_modal.button_index = (
                    1 - self.state.confirm_modal.button_index
                )
            return

        # Internet Archive modals navigation
        if self.state.ia_login.show:
            step = self.state.ia_login.step
            if step in ("email", "password"):
                char_set = "url" if step == "email" else "default"
                self._navigate_keyboard_modal(
                    direction, self.state.ia_login, char_set=char_set
                )
            return

        if self.state.ia_download_wizard.show:
            step = self.state.ia_download_wizard.step
            if step == "url":
                self._navigate_keyboard_modal(
                    direction, self.state.ia_download_wizard, char_set="url"
                )
            elif step == "file_select":
                self._navigate_ia_file_select(direction)
            elif step == "folder":
                self._navigate_ia_folder_select(direction)
            return

        if self.state.ia_collection_wizard.show:
            step = self.state.ia_collection_wizard.step
            if step == "url":
                self._navigate_keyboard_modal(
                    direction, self.state.ia_collection_wizard, char_set="url"
                )
            elif step == "name":
                self._navigate_keyboard_modal(
                    direction, self.state.ia_collection_wizard, char_set="default"
                )
            # Note: "folder" step uses folder browser modal, navigation handled there
            elif step == "formats":
                if self.state.ia_collection_wizard.adding_custom_format:
                    self._navigate_keyboard_modal(
                        direction, self.state.ia_collection_wizard, char_set="default"
                    )
                else:
                    self._navigate_ia_format_select(direction)
            elif step == "options":
                self._navigate_ia_options_select(direction)
            return

        # Mode-based navigation
        if self.state.mode == "systems":
            visible = get_visible_systems(self.data, self.settings)
            max_items = len(visible) + 3  # +3 for Utils, Settings, Credits

            if direction in ("up", "left"):
                self.state.highlighted = (self.state.highlighted - 1) % max_items
            elif direction in ("down", "right"):
                self.state.highlighted = (self.state.highlighted + 1) % max_items

        elif self.state.mode == "games":
            game_list = (
                self.state.search.filtered_list
                if self.state.search.mode
                else self.state.game_list
            )
            # Add 1 for "Download All" button if enabled
            extra_items = 1 if self.settings.get("show_download_all", False) else 0
            max_items = len(game_list) + extra_items

            if self.settings.get("view_type") == "grid":
                cols = 4
                if direction == "up" and self.state.highlighted >= cols:
                    self.state.highlighted -= cols
                elif direction == "down" and self.state.highlighted + cols < max_items:
                    self.state.highlighted += cols
                elif direction == "left" and self.state.highlighted % cols > 0:
                    self.state.highlighted -= 1
                elif (
                    direction == "right"
                    and self.state.highlighted % cols < cols - 1
                    and self.state.highlighted < max_items - 1
                ):
                    self.state.highlighted += 1
            else:
                if direction in ("up", "left"):
                    self.state.highlighted = (self.state.highlighted - 1) % max_items
                elif direction in ("down", "right"):
                    self.state.highlighted = (self.state.highlighted + 1) % max_items

        elif self.state.mode in ("settings", "utils"):
            if self.state.mode == "settings":
                from ui.screens.settings_screen import settings_screen

                max_items = settings_screen.get_max_items(self.settings)
            else:
                from ui.screens.utils_screen import utils_screen

                max_items = utils_screen.get_max_items(self.settings)

            if direction in ("up", "left"):
                self.state.highlighted = (self.state.highlighted - 1) % max_items
            elif direction in ("down", "right"):
                self.state.highlighted = (self.state.highlighted + 1) % max_items

        elif self.state.mode == "add_systems":
            max_items = len(self.state.available_systems) or 1
            if direction in ("up", "left"):
                self.state.add_systems_highlighted = (
                    self.state.add_systems_highlighted - 1
                ) % max_items
            elif direction in ("down", "right"):
                self.state.add_systems_highlighted = (
                    self.state.add_systems_highlighted + 1
                ) % max_items

        elif self.state.mode == "systems_settings":
            max_items = len(self.data) or 1
            if direction in ("up", "left"):
                self.state.systems_settings_highlighted = (
                    self.state.systems_settings_highlighted - 1
                ) % max_items
            elif direction in ("down", "right"):
                self.state.systems_settings_highlighted = (
                    self.state.systems_settings_highlighted + 1
                ) % max_items

        elif self.state.mode == "system_settings":
            max_items = 2  # Hide System, Set Custom Folder
            if direction in ("up", "left"):
                self.state.system_settings_highlighted = (
                    self.state.system_settings_highlighted - 1
                ) % max_items
            elif direction in ("down", "right"):
                self.state.system_settings_highlighted = (
                    self.state.system_settings_highlighted + 1
                ) % max_items

        elif self.state.mode == "downloads":
            max_items = len(self.state.download_queue.items) or 1
            if direction in ("up", "left"):
                self.state.download_queue.highlighted = (
                    self.state.download_queue.highlighted - 1
                ) % max_items
            elif direction in ("down", "right"):
                self.state.download_queue.highlighted = (
                    self.state.download_queue.highlighted + 1
                ) % max_items

    def _handle_key_event(self, event: pygame.event.Event):
        """Handle keyboard events."""
        # Handle keyboard text input for search modal
        if self.state.show_search_input and self.state.input_mode == "keyboard":
            if event.key == pygame.K_ESCAPE:
                self._go_back()
            elif event.key == pygame.K_RETURN:
                self._submit_search_keyboard_input()
            elif event.key == pygame.K_BACKSPACE:
                # Delete last character
                if self.state.search.input_text:
                    self.state.search.input_text = self.state.search.input_text[:-1]
                    self.state.search.query = self.state.search.input_text
            elif event.unicode and event.unicode.isprintable():
                # Add typed character
                self.state.search.input_text += event.unicode
                self.state.search.query = self.state.search.input_text
            return

        # Handle keyboard text input for IA login modal
        if self.state.ia_login.show and self.state.input_mode == "keyboard":
            step = self.state.ia_login.step
            if step in ("email", "password"):
                if event.key == pygame.K_ESCAPE:
                    self._go_back()
                elif event.key == pygame.K_RETURN:
                    self._handle_ia_login_selection()
                elif event.key == pygame.K_BACKSPACE:
                    if step == "email" and self.state.ia_login.email:
                        self.state.ia_login.email = self.state.ia_login.email[:-1]
                    elif step == "password" and self.state.ia_login.password:
                        self.state.ia_login.password = self.state.ia_login.password[:-1]
                elif event.unicode and event.unicode.isprintable():
                    if step == "email":
                        self.state.ia_login.email += event.unicode
                    elif step == "password":
                        self.state.ia_login.password += event.unicode
                return

        # Handle keyboard text input for IA download wizard
        if self.state.ia_download_wizard.show and self.state.input_mode == "keyboard":
            step = self.state.ia_download_wizard.step
            if step == "url":
                if event.key == pygame.K_ESCAPE:
                    self._go_back()
                elif event.key == pygame.K_RETURN:
                    self._handle_ia_download_wizard_selection()
                elif event.key == pygame.K_BACKSPACE:
                    if self.state.ia_download_wizard.url:
                        self.state.ia_download_wizard.url = (
                            self.state.ia_download_wizard.url[:-1]
                        )
                elif event.unicode and event.unicode.isprintable():
                    self.state.ia_download_wizard.url += event.unicode
                return

        # Handle keyboard text input for IA collection wizard
        # Skip if folder browser is open (it handles its own input)
        if (
            self.state.ia_collection_wizard.show
            and self.state.input_mode == "keyboard"
            and not self.state.folder_browser.show
        ):
            step = self.state.ia_collection_wizard.step
            wizard = self.state.ia_collection_wizard

            # Handle custom format input mode
            if step == "formats" and wizard.adding_custom_format:
                if event.key == pygame.K_ESCAPE:
                    wizard.adding_custom_format = False
                    wizard.custom_format_input = ""
                elif event.key == pygame.K_RETURN:
                    self._handle_ia_collection_wizard_selection()
                elif event.key == pygame.K_BACKSPACE:
                    if wizard.custom_format_input:
                        wizard.custom_format_input = wizard.custom_format_input[:-1]
                elif event.unicode and event.unicode.isprintable():
                    wizard.custom_format_input += event.unicode
                return

            # Handle URL and name text input steps
            if step in ("url", "name"):
                if event.key == pygame.K_ESCAPE:
                    self._go_back()
                elif event.key == pygame.K_RETURN:
                    self._handle_ia_collection_wizard_selection()
                elif event.key == pygame.K_BACKSPACE:
                    if step == "url" and wizard.url:
                        wizard.url = wizard.url[:-1]
                    elif step == "name" and wizard.collection_name:
                        wizard.collection_name = wizard.collection_name[:-1]
                elif event.unicode and event.unicode.isprintable():
                    if step == "url":
                        wizard.url += event.unicode
                    elif step == "name":
                        wizard.collection_name += event.unicode
                return

        if event.key == pygame.K_ESCAPE:
            self._go_back()
        elif event.key == pygame.K_RETURN:
            self._select_item()
        elif event.key == pygame.K_UP:
            self._move_highlight("up")
        elif event.key == pygame.K_DOWN:
            self._move_highlight("down")
        elif event.key == pygame.K_LEFT:
            self._move_highlight("left")
        elif event.key == pygame.K_RIGHT:
            self._move_highlight("right")
        elif event.key == pygame.K_s:
            self._handle_search_action()
        elif event.key == pygame.K_d:
            self._handle_detail_action()
        elif event.key == pygame.K_SPACE:
            self._handle_start_action()

    def _handle_joystick_event(self, event: pygame.event.Event):
        """Handle joystick button events."""
        action = self.controller.get_action_for_event(event)

        if action == "back":
            self._go_back()
        elif action == "select":
            self._select_item()
        elif action in ("up", "down", "left", "right"):
            self._move_highlight(action)
        elif action == "search":
            self._handle_search_action()
        elif action == "detail":
            self._handle_detail_action()
        elif action == "start":
            self._handle_start_action()

    def _handle_click(self, pos: tuple):
        """Handle click/tap events."""
        x, y = pos

        # Check modal close button first
        if self.state.ui_rects.close_button:
            if self.state.ui_rects.close_button.collidepoint(x, y):
                self._go_back()
                return

        # Check confirm modal buttons
        if self.state.confirm_modal.show:
            if self.state.ui_rects.confirm_ok_button:
                if self.state.ui_rects.confirm_ok_button.collidepoint(x, y):
                    self._handle_confirm_modal_ok()
                    return
            if self.state.ui_rects.confirm_cancel_button:
                if self.state.ui_rects.confirm_cancel_button.collidepoint(x, y):
                    self._handle_confirm_modal_cancel()
                    return
            return

        # Check folder browser buttons
        if self.state.folder_browser.show:
            if self.state.ui_rects.folder_select_button:
                if self.state.ui_rects.folder_select_button.collidepoint(x, y):
                    self._handle_folder_browser_confirm()
                    return
            if self.state.ui_rects.folder_cancel_button:
                if self.state.ui_rects.folder_cancel_button.collidepoint(x, y):
                    self.state.folder_browser.show = False
                    self.state.folder_browser.focus_area = "list"
                    return
            # Check folder browser items
            for i, rect in enumerate(self.state.ui_rects.menu_items):
                if rect.collidepoint(x, y):
                    self.state.folder_browser.highlighted = i
                    self._handle_folder_browser_selection()
                    return
            return

        # Check IA download wizard list items (for steps with lists)
        if self.state.ia_download_wizard.show:
            step = self.state.ia_download_wizard.step
            if step in ("file_select", "folder"):
                for i, rect in enumerate(self.state.ui_rects.menu_items):
                    if rect.collidepoint(x, y):
                        if step == "file_select":
                            self.state.ia_download_wizard.selected_file_index = i
                            self._handle_ia_download_wizard_selection()
                        elif step == "folder":
                            self.state.ia_download_wizard.folder_highlighted = i
                            self._handle_ia_download_folder_selection()
                        return
                # Only return if in list mode - fall through to char_rect check otherwise
                return

        # Check IA collection wizard list items (format selection)
        if self.state.ia_collection_wizard.show:
            step = self.state.ia_collection_wizard.step
            if step == "formats":
                for i, rect in enumerate(self.state.ui_rects.menu_items):
                    if rect.collidepoint(x, y):
                        self.state.ia_collection_wizard.format_highlighted = i
                        self._handle_ia_collection_wizard_selection()
                        return
                # Only return if in formats mode - fall through to char_rect check otherwise
                return

        # Check download button (modal or games screen)
        if self.state.ui_rects.download_button:
            if self.state.ui_rects.download_button.collidepoint(x, y):
                if self.state.game_details.show:
                    self._handle_game_details_selection()
                elif self.state.mode == "games" and self.state.selected_games:
                    self._start_download()
                return

        # Check modal character buttons (search/url input/IA modals)
        if self.state.ui_rects.modal_char_rects:
            for char_rect, char_index, char in self.state.ui_rects.modal_char_rects:
                if char_rect.collidepoint(x, y):
                    # Set cursor position and trigger selection based on active modal
                    if self.state.show_search_input:
                        self.state.search.cursor_position = char_index
                        self._handle_search_input_selection()
                    elif self.state.url_input.show:
                        self.state.url_input.cursor_position = char_index
                        self._handle_url_input_selection()
                    elif self.state.folder_name_input.show:
                        self.state.folder_name_input.cursor_position = char_index
                        self._handle_folder_name_input_selection()
                    elif self.state.ia_login.show:
                        self.state.ia_login.cursor_position = char_index
                        self._handle_ia_login_selection()
                    elif self.state.ia_download_wizard.show:
                        self.state.ia_download_wizard.cursor_position = char_index
                        self._handle_ia_download_wizard_selection()
                    elif self.state.ia_collection_wizard.show:
                        self.state.ia_collection_wizard.cursor_position = char_index
                        self._handle_ia_collection_wizard_selection()
                    return

        # Check back button
        if self.state.ui_rects.back_button:
            if self.state.ui_rects.back_button.collidepoint(x, y):
                self._go_back()
                return

        # Check menu items (account for scroll offset)
        for i, rect in enumerate(self.state.ui_rects.menu_items):
            if rect.collidepoint(x, y):
                # Add scroll offset to get actual item index
                actual_index = i + self.state.ui_rects.scroll_offset
                self.state.highlighted = actual_index
                self._select_item()
                return

    def _handle_scroll(self, amount: float):
        """Handle scroll events. Amount is in items (can be multiple)."""
        # Handle multiple items at once for smoother scrolling
        steps = int(abs(amount))
        if steps == 0:
            steps = 1 if amount != 0 else 0

        direction = "up" if amount > 0 else "down"
        for _ in range(steps):
            self._move_highlight(direction)

    def _go_back(self):
        """Handle back navigation."""
        if self.state.show_search_input:
            # Reset search state when closing search modal
            self.state.show_search_input = False
            self.state.search.mode = False
            self.state.search.query = ""
            self.state.search.input_text = ""
            self.state.search.cursor_position = 0
            self.state.search.filtered_list = []
            self.state.highlighted = 0
        elif self.state.confirm_modal.show:
            self._handle_confirm_modal_cancel()
        elif self.state.url_input.show:
            self.state.url_input.show = False
        elif self.state.folder_name_input.show:
            self.state.folder_name_input.show = False
        elif self.state.folder_browser.show:
            # Check if folder browser was opened for IA collection
            selection_type = self.state.folder_browser.selected_system_to_add.get(
                "type", "folder"
            )
            self.state.folder_browser.show = False
            self.state.folder_browser.focus_area = "list"
            if selection_type == "ia_collection_folder":
                # Go back to name step in IA collection wizard
                self.state.ia_collection_wizard.step = "name"
                self.state.ia_collection_wizard.cursor_position = 0
        elif self.state.ia_login.show:
            self._close_ia_login()
        elif self.state.ia_download_wizard.show:
            self._close_ia_download_wizard()
        elif self.state.ia_collection_wizard.show:
            # Check if we're in custom format input mode
            if self.state.ia_collection_wizard.adding_custom_format:
                self.state.ia_collection_wizard.adding_custom_format = False
                self.state.ia_collection_wizard.custom_format_input = ""
                self.state.ia_collection_wizard.cursor_position = 0
            else:
                self._close_ia_collection_wizard()
        elif self.state.game_details.show:
            self.state.game_details.show = False
            self.state.game_details.current_game = None
        elif self.state.mode == "system_settings":
            self.state.mode = "systems_settings"
            self.state.system_settings_highlighted = 0
        elif self.state.mode in ("add_systems", "systems_settings"):
            self.state.mode = "settings"
            self.state.highlighted = 0
        elif self.state.mode == "games":
            # Reset selected games and search when leaving games mode
            self.state.selected_games.clear()
            self.state.search.mode = False
            self.state.search.query = ""
            self.state.search.input_text = ""
            self.state.search.cursor_position = 0
            self.state.search.filtered_list = []
            self.state.mode = "systems"
            self.state.highlighted = 0
        elif self.state.mode == "downloads":
            # Go back to games if we came from there, otherwise systems
            if self.state.selected_system >= 0 and self.state.game_list:
                self.state.mode = "games"
            else:
                self.state.mode = "systems"
            self.state.highlighted = 0
        elif self.state.mode in ("settings", "utils", "credits"):
            self.state.mode = "systems"
            self.state.highlighted = 0

    def _select_item(self):
        """Handle item selection."""
        # Check modals first (they take priority over modes)
        if self.state.confirm_modal.show:
            if self.state.confirm_modal.button_index == 0:
                self._handle_confirm_modal_ok()
            else:
                self._handle_confirm_modal_cancel()
            return

        if self.state.show_search_input:
            self._handle_search_input_selection()
            return

        if self.state.game_details.show:
            self._handle_game_details_selection()
            return

        if self.state.folder_browser.show:
            if self.state.folder_browser.focus_area == "buttons":
                self._handle_folder_browser_button_selection()
            else:
                self._handle_folder_browser_selection()
            return

        if self.state.url_input.show:
            self._handle_url_input_selection()
            return

        if self.state.folder_name_input.show:
            self._handle_folder_name_input_selection()
            return

        # Internet Archive modal selection
        if self.state.ia_login.show:
            self._handle_ia_login_selection()
            return

        if self.state.ia_download_wizard.show:
            self._handle_ia_download_wizard_selection()
            return

        if self.state.ia_collection_wizard.show:
            self._handle_ia_collection_wizard_selection()
            return

        # Mode-based selection
        if self.state.mode == "systems":
            visible = get_visible_systems(self.data, self.settings)
            systems_count = len(visible)

            if self.state.highlighted < systems_count:
                # Select a system
                system = visible[self.state.highlighted]
                self.state.selected_system = get_system_index_by_name(
                    self.data, system["name"]
                )

                # Show loading while fetching games
                self._show_loading(f"Loading {system['name']}...")
                system_data = self.data[self.state.selected_system]
                self.state.game_list = list_files(system_data, self.settings)

                # Set up installed checker for lazy evaluation
                roms_folder = get_roms_folder_for_system(system_data, self.settings)
                installed_checker.set_roms_folder(roms_folder)
                self._hide_loading()

                self.state.mode = "games"
                self.state.highlighted = 0
            elif self.state.highlighted == systems_count:
                self.state.mode = "utils"
                self.state.highlighted = 0
            elif self.state.highlighted == systems_count + 1:
                self.state.mode = "settings"
                self.state.highlighted = 0
            elif self.state.highlighted == systems_count + 2:
                self.state.mode = "credits"

        elif self.state.mode == "games":
            game_list = (
                self.state.search.filtered_list
                if self.state.search.mode
                else self.state.game_list
            )
            # Check if "Download All" button is selected
            if self.settings.get(
                "show_download_all", False
            ) and self.state.highlighted >= len(game_list):
                self._show_download_all_confirm()
            else:
                # Toggle game selection
                if self.state.highlighted in self.state.selected_games:
                    self.state.selected_games.remove(self.state.highlighted)
                else:
                    self.state.selected_games.add(self.state.highlighted)

        elif self.state.mode == "settings":
            self._handle_settings_selection()

        elif self.state.mode == "utils":
            self._handle_utils_selection()

        elif self.state.mode == "add_systems":
            self._handle_add_systems_selection()

        elif self.state.mode == "systems_settings":
            self._handle_systems_settings_selection()

        elif self.state.mode == "system_settings":
            self._handle_system_settings_selection()

        elif self.state.mode == "downloads":
            self._handle_downloads_selection()

    def _handle_downloads_selection(self):
        """Handle downloads screen selection (remove waiting item)."""
        queue = self.state.download_queue
        if queue.items and 0 <= queue.highlighted < len(queue.items):
            item = queue.items[queue.highlighted]
            if item.status == "waiting":
                self.download_manager.remove_from_queue(queue.highlighted)

    def _show_download_all_confirm(self):
        """Show confirmation modal for downloading all games."""
        game_list = (
            self.state.search.filtered_list
            if self.state.search.mode
            else self.state.game_list
        )

        if not game_list:
            return

        num_games = len(game_list)

        # Show simple confirmation modal
        self.state.confirm_modal.show = True
        self.state.confirm_modal.title = "Download All Games"
        self.state.confirm_modal.message_lines = [
            f"Download all {num_games} games?",
            "",
            "This may take a while.",
        ]
        self.state.confirm_modal.ok_label = "Download"
        self.state.confirm_modal.cancel_label = "Cancel"
        self.state.confirm_modal.button_index = 0
        self.state.confirm_modal.context = "download_all"
        self.state.confirm_modal.data = list(game_list)  # Copy the list
        self.state.confirm_modal.loading = False

    def _handle_confirm_modal_ok(self):
        """Handle confirm modal OK button."""
        context = self.state.confirm_modal.context
        data = self.state.confirm_modal.data

        if context == "download_all" and data:
            # Add all games to download queue
            system_data = self.data[self.state.selected_system]
            system_name = system_data.get("name", "Unknown")
            self.download_manager.add_to_queue(data, system_data, system_name)

            # Navigate to downloads screen
            self.state.mode = "downloads"
            self.state.download_queue.highlighted = 0

        # Close the modal
        self._handle_confirm_modal_cancel()

    def _handle_confirm_modal_cancel(self):
        """Handle confirm modal Cancel button."""
        self.state.confirm_modal.show = False
        self.state.confirm_modal.title = ""
        self.state.confirm_modal.message_lines = []
        self.state.confirm_modal.context = ""
        self.state.confirm_modal.data = None
        self.state.confirm_modal.button_index = 0
        self.state.confirm_modal.loading = False
        self.state.confirm_modal.loading_current = 0
        self.state.confirm_modal.loading_total = 0
        self.state.confirm_modal.total_size = 0

    def _format_bytes(self, size: int) -> str:
        """Format bytes to human readable string."""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0:
                return (
                    f"{size:.1f} {unit}" if size != int(size) else f"{int(size)} {unit}"
                )
            size /= 1024.0
        return f"{size:.1f} PB"

    def _handle_settings_selection(self):
        """Handle settings item selection."""
        from ui.screens.settings_screen import settings_screen

        action = settings_screen.get_setting_action(
            self.state.highlighted, self.settings
        )

        if action == "select_archive_json":
            self._open_folder_browser("archive_json")
        elif action == "select_nsz_keys":
            self._open_folder_browser("nsz_keys")
        elif action == "toggle_boxart":
            self.settings["enable_boxart"] = not self.settings.get(
                "enable_boxart", True
            )
            save_settings(self.settings)
        elif action == "toggle_view_type":
            current = self.settings.get("view_type", "grid")
            self.settings["view_type"] = "list" if current == "grid" else "grid"
            save_settings(self.settings)
        elif action == "toggle_usa_only":
            self.settings["usa_only"] = not self.settings.get("usa_only", False)
            save_settings(self.settings)
        elif action == "toggle_download_all":
            self.settings["show_download_all"] = not self.settings.get(
                "show_download_all", False
            )
            save_settings(self.settings)
        elif action == "select_work_dir":
            self._open_folder_browser("work_dir")
        elif action == "select_roms_dir":
            self._open_folder_browser("roms_dir")
        elif action == "add_systems":
            self.state.mode = "add_systems"
            self.state.add_systems_highlighted = 0
        elif action == "systems_settings":
            self.state.mode = "systems_settings"
            self.state.systems_settings_highlighted = 0
        elif action == "remap_controller":
            self._start_controller_mapping()
        elif action == "toggle_ia_enabled":
            self.settings["ia_enabled"] = not self.settings.get("ia_enabled", False)
            save_settings(self.settings)
        elif action == "ia_login":
            self._show_ia_login()
        elif action == "toggle_nsz_enabled":
            self.settings["nsz_enabled"] = not self.settings.get("nsz_enabled", False)
            save_settings(self.settings)

    def _handle_utils_selection(self):
        """Handle utils item selection."""
        from ui.screens.utils_screen import utils_screen

        action = utils_screen.get_util_action(self.state.highlighted, self.settings)

        if action == "divider":
            # Skip divider items
            return
        elif action == "download_url":
            self.state.url_input.show = True
            self.state.url_input.context = "direct_download"
        elif action == "ia_download":
            self._show_ia_download_wizard()
        elif action == "ia_add_collection":
            self._show_ia_collection_wizard()
        elif action == "extract_zip":
            self._open_folder_browser("extract_zip")
        elif action == "nsz_converter":
            self._open_folder_browser("nsz_converter")

    def _open_folder_browser(self, selection_type: str):
        """Open the folder browser modal."""
        self.state.folder_browser.show = True
        self.state.folder_browser.highlighted = 0
        self.state.folder_browser.focus_area = "list"
        self.state.folder_browser.button_index = 0
        self.state.folder_browser.selected_system_to_add = {"type": selection_type}

        # Set initial path based on selection type
        if selection_type == "work_dir":
            path = self.settings.get("work_dir", os.path.expanduser("~"))
        elif selection_type == "roms_dir":
            path = self.settings.get("roms_dir", os.path.expanduser("~"))
        elif selection_type == "archive_json":
            current = self.settings.get("archive_json_path", "")
            path = os.path.dirname(current) if current else os.path.expanduser("~")
        elif selection_type == "nsz_keys":
            current = self.settings.get("nsz_keys_path", "")
            path = os.path.dirname(current) if current else os.path.expanduser("~")
        else:
            path = os.path.expanduser("~")

        if os.path.exists(path):
            self.state.folder_browser.current_path = path
        else:
            self.state.folder_browser.current_path = os.path.expanduser("~")

        self.state.folder_browser.items = load_folder_contents(
            self.state.folder_browser.current_path
        )

    def _open_ia_collection_folder_browser(self):
        """Open folder browser for IA collection ROM folder selection."""
        self.state.ia_collection_wizard.step = "folder"
        self.state.folder_browser.show = True
        self.state.folder_browser.highlighted = 0
        self.state.folder_browser.focus_area = "list"
        self.state.folder_browser.button_index = 0
        self.state.folder_browser.selected_system_to_add = {
            "type": "ia_collection_folder"
        }

        # Start from roms directory
        path = self.settings.get("roms_dir", os.path.expanduser("~"))
        if os.path.exists(path):
            self.state.folder_browser.current_path = path
        else:
            self.state.folder_browser.current_path = os.path.expanduser("~")

        self.state.folder_browser.items = load_folder_contents(
            self.state.folder_browser.current_path
        )

    def _handle_folder_browser_selection(self):
        """Handle folder browser item selection."""
        items = self.state.folder_browser.items
        highlighted = self.state.folder_browser.highlighted

        if highlighted >= len(items):
            return

        item = items[highlighted]
        item_type = item.get("type", "")
        item_path = item.get("path", "")
        selection_type = self.state.folder_browser.selected_system_to_add.get(
            "type", "folder"
        )

        if item_type == "parent":
            # Navigate to parent directory
            self.state.folder_browser.current_path = item_path
            self.state.folder_browser.items = load_folder_contents(item_path)
            self.state.folder_browser.highlighted = 0
            self.state.folder_browser.focus_area = "list"

        elif item_type == "create_folder":
            # Show folder name input modal
            self.state.folder_name_input.show = True
            self.state.folder_name_input.input_text = ""
            self.state.folder_name_input.cursor_position = 0

        elif item_type == "folder":
            # Navigate into the folder
            self.state.folder_browser.current_path = item_path
            self.state.folder_browser.items = load_folder_contents(item_path)
            self.state.folder_browser.highlighted = 0
            self.state.folder_browser.focus_area = "list"

        elif item_type in ("json_file", "keys_file", "zip_file", "file"):
            # Select the file based on selection type
            self._complete_folder_browser_selection(item_path, selection_type)

    def _complete_folder_browser_selection(self, path: str, selection_type: str):
        """Complete folder browser selection with chosen path."""
        if selection_type == "work_dir":
            self.settings["work_dir"] = path
            save_settings(self.settings)
        elif selection_type == "roms_dir":
            self.settings["roms_dir"] = path
            save_settings(self.settings)
        elif selection_type == "archive_json":
            self.settings["archive_json_path"] = path
            save_settings(self.settings)
            # Reload data with new JSON
            self._show_loading("Loading systems data...")
            update_json_file_path(self.settings)
            self.data = load_main_systems_data(self.settings)
            self._hide_loading()
        elif selection_type == "nsz_keys":
            self.settings["nsz_keys_path"] = path
            save_settings(self.settings)
        elif selection_type == "extract_zip":
            # Extract ZIP file to same folder
            self._extract_zip_file(path)
            # Don't close modal yet, extraction will handle it
            return

        # Close the modal
        self.state.folder_browser.show = False

    def _handle_folder_browser_confirm(self):
        """Handle folder browser Select button (select current folder)."""
        selection_type = self.state.folder_browser.selected_system_to_add.get(
            "type", "folder"
        )
        current_path = self.state.folder_browser.current_path

        # For folder selection types, select the current directory
        if selection_type in ("work_dir", "roms_dir", "custom_folder"):
            self._complete_folder_browser_selection(current_path, selection_type)
        elif selection_type == "ia_collection_folder":
            # Set the folder path for IA collection and continue wizard
            self.state.ia_collection_wizard.folder_name = current_path
            self.state.folder_browser.show = False
            self.state.ia_collection_wizard.step = "formats"
        else:
            # For file selection, user needs to select a file
            pass

    def _handle_add_systems_selection(self):
        """Handle add systems item selection."""
        if not self.state.available_systems:
            return

        if self.state.add_systems_highlighted < len(self.state.available_systems):
            system = self.state.available_systems[self.state.add_systems_highlighted]
            # Open folder browser to select location for the new system
            self.state.folder_browser.show = True
            self.state.folder_browser.highlighted = 0
            self.state.folder_browser.selected_system_to_add = system
            self.state.folder_browser.current_path = os.path.expanduser("~")
            self.state.folder_browser.items = load_folder_contents(
                self.state.folder_browser.current_path
            )

    def _handle_systems_settings_selection(self):
        """Handle systems settings item selection."""
        if self.state.systems_settings_highlighted < len(self.data):
            self.state.selected_system_for_settings = (
                self.state.systems_settings_highlighted
            )
            self.state.mode = "system_settings"
            self.state.system_settings_highlighted = 0

    def _handle_system_settings_selection(self):
        """Handle individual system settings selection."""
        from ui.screens.system_settings_screen import SystemSettingsScreen

        action = SystemSettingsScreen().get_setting_action(
            self.state.system_settings_highlighted
        )

        if self.state.selected_system_for_settings is None:
            return

        system = self.data[self.state.selected_system_for_settings]
        system_name = system.get("name", "")

        if action == "toggle_hide_system":
            # Toggle hidden state
            system_settings = self.settings.setdefault("system_settings", {})
            sys_settings = system_settings.setdefault(system_name, {})
            sys_settings["hidden"] = not sys_settings.get("hidden", False)
            save_settings(self.settings)

        elif action == "set_custom_folder":
            # Open folder browser for custom folder
            self._open_folder_browser("custom_folder")

    def _navigate_keyboard_modal(
        self, direction: str, modal_state, char_set: str = "default"
    ):
        """Navigate keyboard modal."""
        from ui.organisms.char_keyboard import CharKeyboard

        keyboard = CharKeyboard()
        total_chars = keyboard.get_total_chars(char_set)
        chars_per_row = 13

        if direction == "up":
            if modal_state.cursor_position >= chars_per_row:
                modal_state.cursor_position -= chars_per_row
        elif direction == "down":
            if modal_state.cursor_position + chars_per_row < total_chars:
                modal_state.cursor_position += chars_per_row
        elif direction == "left":
            if modal_state.cursor_position > 0:
                modal_state.cursor_position -= 1
        elif direction == "right":
            if modal_state.cursor_position < total_chars - 1:
                modal_state.cursor_position += 1

    def _navigate_folder_browser(self, direction: str):
        """Navigate folder browser modal with list and button support."""
        fb = self.state.folder_browser
        max_items = len(fb.items) or 1

        if fb.focus_area == "list":
            if direction == "up":
                if fb.highlighted > 0:
                    fb.highlighted -= 1
                # else stay at top, don't wrap
            elif direction == "down":
                if fb.highlighted < max_items - 1:
                    fb.highlighted += 1
                else:
                    # Move to buttons when at bottom of list
                    fb.focus_area = "buttons"
                    fb.button_index = 0
            elif direction == "left":
                if fb.highlighted > 0:
                    fb.highlighted -= 1
            elif direction == "right":
                if fb.highlighted < max_items - 1:
                    fb.highlighted += 1
        else:  # focus_area == "buttons"
            if direction == "up":
                # Move back to list
                fb.focus_area = "list"
            elif direction == "left":
                fb.button_index = 0  # Select button
            elif direction == "right":
                fb.button_index = 1  # Cancel button

    def _navigate_ia_file_select(self, direction: str):
        """Navigate IA download wizard file selection."""
        wizard = self.state.ia_download_wizard
        max_items = len(wizard.files_list) or 1

        if direction in ("up", "left"):
            if wizard.selected_file_index > 0:
                wizard.selected_file_index -= 1
        elif direction in ("down", "right"):
            if wizard.selected_file_index < max_items - 1:
                wizard.selected_file_index += 1

    def _navigate_ia_folder_select(self, direction: str):
        """Navigate IA download wizard folder selection."""
        wizard = self.state.ia_download_wizard
        max_items = len(wizard.folder_items) or 1

        if direction in ("up", "left"):
            if wizard.folder_highlighted > 0:
                wizard.folder_highlighted -= 1
        elif direction in ("down", "right"):
            if wizard.folder_highlighted < max_items - 1:
                wizard.folder_highlighted += 1

    def _navigate_ia_format_select(self, direction: str):
        """Navigate IA collection wizard format selection."""
        wizard = self.state.ia_collection_wizard
        # +1 for "Add custom format..." option at the end
        max_items = (len(wizard.available_formats) + 1) or 1

        if direction in ("up", "left"):
            if wizard.format_highlighted > 0:
                wizard.format_highlighted -= 1
        elif direction in ("down", "right"):
            if wizard.format_highlighted < max_items - 1:
                wizard.format_highlighted += 1

    def _navigate_ia_options_select(self, direction: str):
        """Navigate IA collection wizard options selection."""
        wizard = self.state.ia_collection_wizard
        # If unzip is enabled, we have 2 options, otherwise just 1
        max_items = 2 if wizard.should_unzip else 1

        if direction in ("up", "left"):
            if wizard.options_highlighted > 0:
                wizard.options_highlighted -= 1
        elif direction in ("down", "right"):
            if wizard.options_highlighted < max_items - 1:
                wizard.options_highlighted += 1

    def _handle_url_input_selection(self):
        """Handle URL input keyboard selection."""
        from ui.screens.modals.url_input_modal import UrlInputModal

        modal = UrlInputModal()
        new_text, is_done = modal.handle_selection(
            self.state.url_input.cursor_position, self.state.url_input.input_text
        )
        self.state.url_input.input_text = new_text

        if is_done:
            # URL entry complete - handle the URL
            self.state.url_input.show = False
            # TODO: Process the URL based on context

    def _handle_folder_name_input_selection(self):
        """Handle folder name input keyboard selection."""
        from ui.screens.modals.folder_name_modal import FolderNameModal

        modal = FolderNameModal()
        new_text, is_done = modal.handle_selection(
            self.state.folder_name_input.cursor_position,
            self.state.folder_name_input.input_text,
        )
        self.state.folder_name_input.input_text = new_text

        if is_done:
            # Folder name entry complete
            self.state.folder_name_input.show = False
            # TODO: Create the folder with the given name

    def _handle_search_input_selection(self):
        """Handle search input on-screen keyboard selection."""
        from ui.screens.modals.search_modal import SearchModal

        modal = SearchModal()
        new_text, is_done = modal.handle_selection(
            self.state.search.cursor_position, self.state.search.input_text
        )
        self.state.search.input_text = new_text
        self.state.search.query = new_text

        if is_done:
            self._apply_search_filter()

    def _submit_search_keyboard_input(self):
        """Handle search submission from physical keyboard."""
        self._apply_search_filter()

    def _apply_search_filter(self):
        """Apply search filter and close search modal."""
        self.state.show_search_input = False
        if self.state.search.query:
            self.state.search.filtered_list = filter_games_by_search(
                self.state.game_list, self.state.search.query
            )
        else:
            self.state.search.mode = False
            self.state.search.filtered_list = []
        self.state.highlighted = 0

    def _handle_game_details_selection(self):
        """Handle game details modal selection (Download button)."""
        game = self.state.game_details.current_game
        if game:
            # Add game to selection and trigger download
            game_list = (
                self.state.search.filtered_list
                if self.state.search.mode
                else self.state.game_list
            )
            # Find game index in list
            for i, g in enumerate(game_list):
                game_name = (
                    g.get("filename", g.get("name", "")) if isinstance(g, dict) else g
                )
                current_name = game.get("filename", game.get("name", ""))
                if game_name == current_name:
                    self.state.selected_games.add(i)
                    break

            # Close modal and start download
            self.state.game_details.show = False
            self.state.game_details.current_game = None
            self._start_download()

    def _handle_folder_browser_button_selection(self):
        """Handle folder browser button selection (Select/Cancel)."""
        if self.state.folder_browser.button_index == 0:
            # Select button - confirm current folder
            self._handle_folder_browser_confirm()
        else:
            # Cancel button - close modal
            self.state.folder_browser.show = False
            self.state.folder_browser.focus_area = "list"

    def _handle_search_action(self):
        """Handle search key press."""
        # Only show search in games mode
        if self.state.mode == "games":
            self.state.show_search_input = True
            self.state.search.mode = True
            self.state.search.query = ""

    def _handle_detail_action(self):
        """Handle detail key press."""
        # Only show details in games mode with a valid selection
        if self.state.mode == "games":
            game_list = (
                self.state.search.filtered_list
                if self.state.search.mode
                else self.state.game_list
            )
            if game_list and 0 <= self.state.highlighted < len(game_list):
                game = game_list[self.state.highlighted]
                # Normalize game to dictionary format (games can be strings or dicts)
                if isinstance(game, str):
                    game = {"name": game, "filename": game}
                else:
                    # Make a copy to avoid modifying the original
                    game = dict(game)

                # Show modal immediately
                self.state.game_details.show = True
                self.state.game_details.current_game = game
                self.state.game_details.loading_size = False

                # Fetch file size in background if not already present
                if "size" not in game and self.state.selected_system >= 0:
                    self.state.game_details.loading_size = True
                    system_data = self.data[self.state.selected_system]

                    def fetch_size():
                        file_size = get_file_size(system_data, game)
                        if file_size and self.state.game_details.current_game is game:
                            game["size"] = file_size
                        self.state.game_details.loading_size = False

                    from threading import Thread

                    thread = Thread(target=fetch_size, daemon=True)
                    thread.start()

    def _handle_start_action(self):
        """Handle start key press - download selected games or go home."""
        # If in games mode with selected games, start download
        if self.state.mode == "games" and self.state.selected_games:
            self._start_download()
            return

        # Handle IA download wizard - start button triggers download on options step
        if self.state.ia_download_wizard.show:
            step = self.state.ia_download_wizard.step
            if step == "options":
                self._start_ia_download()
                return
            elif step == "folder":
                # Select current folder and move to options
                self.state.ia_download_wizard.step = "options"
                return

        # Handle IA collection wizard - start button advances through steps
        if self.state.ia_collection_wizard.show:
            step = self.state.ia_collection_wizard.step
            if step == "formats":
                self.state.ia_collection_wizard.step = "options"
                return
            elif step == "options":
                self.state.ia_collection_wizard.step = "confirm"
                return

        # Close any open modals
        self.state.show_search_input = False
        self.state.url_input.show = False
        self.state.folder_name_input.show = False
        self.state.folder_browser.show = False
        self.state.game_details.show = False
        self.state.game_details.current_game = None
        self.state.ia_login.show = False
        self.state.ia_download_wizard.show = False
        self.state.ia_collection_wizard.show = False

        # Go to systems (home) screen
        self.state.mode = "systems"
        self.state.highlighted = 0

    def _start_download(self):
        """Start downloading selected games by adding to background queue."""
        if not self.state.selected_games or self.state.selected_system < 0:
            return

        system_data = self.data[self.state.selected_system]
        game_list = (
            self.state.search.filtered_list
            if self.state.search.mode
            else self.state.game_list
        )
        system_name = system_data.get("name", "Unknown")

        # Get selected games
        selected_games = [game_list[i] for i in self.state.selected_games]

        # Add to download queue (non-blocking)
        self.download_manager.add_to_queue(selected_games, system_data, system_name)

        # Clear selection
        self.state.selected_games.clear()

        # Navigate to downloads screen
        self.state.mode = "downloads"
        self.state.download_queue.highlighted = max(
            0, len(self.state.download_queue.items) - len(selected_games)
        )

    # ---- Internet Archive Handlers ---- #

    def _show_ia_login(self):
        """Show the Internet Archive login modal."""
        self.state.ia_login.show = True
        self.state.ia_login.step = "email"
        self.state.ia_login.email = self.settings.get("ia_email", "")
        self.state.ia_login.password = ""
        self.state.ia_login.cursor_position = 0
        self.state.ia_login.error_message = ""

    def _close_ia_login(self):
        """Close the Internet Archive login modal."""
        self.state.ia_login.show = False
        self.state.ia_login.step = "email"
        self.state.ia_login.email = ""
        self.state.ia_login.password = ""
        self.state.ia_login.cursor_position = 0
        self.state.ia_login.error_message = ""

    def _handle_ia_login_selection(self):
        """Handle selection in IA login modal."""
        step = self.state.ia_login.step

        if step == "email":
            if self.state.input_mode == "keyboard":
                # Keyboard mode - Enter pressed, move to password
                if self.state.ia_login.email:
                    self.state.ia_login.step = "password"
                    self.state.ia_login.cursor_position = 0
            else:
                # Gamepad/touch mode - handle on-screen keyboard
                from ui.screens.modals.ia_login_modal import IALoginModal

                modal = IALoginModal()
                new_text, is_done = modal.handle_selection(
                    step, self.state.ia_login.cursor_position, self.state.ia_login.email
                )
                self.state.ia_login.email = new_text
                if is_done and new_text:
                    self.state.ia_login.step = "password"
                    self.state.ia_login.cursor_position = 0

        elif step == "password":
            if self.state.input_mode == "keyboard":
                # Keyboard mode - Enter pressed, test credentials
                if self.state.ia_login.password:
                    self._test_ia_credentials()
            else:
                # Gamepad/touch mode - handle on-screen keyboard
                from ui.screens.modals.ia_login_modal import IALoginModal

                modal = IALoginModal()
                new_text, is_done = modal.handle_selection(
                    step,
                    self.state.ia_login.cursor_position,
                    self.state.ia_login.password,
                )
                self.state.ia_login.password = new_text
                if is_done and new_text:
                    self._test_ia_credentials()

        elif step == "complete":
            # Close modal on success
            self._close_ia_login()

        elif step == "error":
            # Go back to email step to retry
            self.state.ia_login.step = "email"
            self.state.ia_login.password = ""
            self.state.ia_login.cursor_position = 0
            self.state.ia_login.error_message = ""

    def _test_ia_credentials(self):
        """Test IA credentials in background thread."""
        self.state.ia_login.step = "testing"

        email = self.state.ia_login.email
        password = self.state.ia_login.password

        def test_credentials():
            success, access_key, secret_key, error = get_ia_s3_credentials(
                email, password
            )

            if success:
                # Save credentials
                self.settings["ia_email"] = email
                self.settings["ia_access_key"] = access_key
                self.settings["ia_secret_key"] = encode_password(secret_key)
                save_settings(self.settings)
                self.state.ia_login.step = "complete"
            else:
                self.state.ia_login.step = "error"
                self.state.ia_login.error_message = error

        from threading import Thread

        thread = Thread(target=test_credentials, daemon=True)
        thread.start()

    def _show_ia_download_wizard(self):
        """Show the IA download wizard modal."""
        self.state.ia_download_wizard.show = True
        self.state.ia_download_wizard.step = "url"
        self.state.ia_download_wizard.url = ""
        self.state.ia_download_wizard.item_id = ""
        self.state.ia_download_wizard.filename = ""
        self.state.ia_download_wizard.output_folder = self.settings.get("work_dir", "")
        self.state.ia_download_wizard.should_extract = True
        self.state.ia_download_wizard.cursor_position = 0
        self.state.ia_download_wizard.error_message = ""
        self.state.ia_download_wizard.files_list = []
        self.state.ia_download_wizard.selected_file_index = 0
        self.state.ia_download_wizard.folder_items = []
        self.state.ia_download_wizard.folder_highlighted = 0

    def _close_ia_download_wizard(self):
        """Close the IA download wizard modal."""
        self.state.ia_download_wizard.show = False
        self.state.ia_download_wizard.step = "url"
        self.state.ia_download_wizard.url = ""
        self.state.ia_download_wizard.item_id = ""
        self.state.ia_download_wizard.files_list = []

    def _handle_ia_download_wizard_selection(self):
        """Handle selection in IA download wizard."""
        step = self.state.ia_download_wizard.step

        if step == "url":
            if self.state.input_mode == "keyboard":
                # Keyboard mode - Enter pressed, validate URL
                if self.state.ia_download_wizard.url:
                    self._validate_ia_download_item()
            else:
                # Gamepad/touch mode - handle on-screen keyboard
                from ui.screens.modals.ia_download_modal import IADownloadModal

                modal = IADownloadModal()
                new_text, is_done = modal.handle_url_selection(
                    self.state.ia_download_wizard.cursor_position,
                    self.state.ia_download_wizard.url,
                )
                self.state.ia_download_wizard.url = new_text
                if is_done and new_text:
                    self._validate_ia_download_item()

        elif step == "file_select":
            # File selected, move to folder selection
            if self.state.ia_download_wizard.files_list:
                self.state.ia_download_wizard.step = "folder"
                self.state.ia_download_wizard.folder_items = load_folder_contents(
                    self.state.ia_download_wizard.output_folder
                )
                self.state.ia_download_wizard.folder_highlighted = 0

        elif step == "folder":
            # Handle folder selection
            self._handle_ia_download_folder_selection()

        elif step == "options":
            # Toggle extract option
            self.state.ia_download_wizard.should_extract = (
                not self.state.ia_download_wizard.should_extract
            )

        elif step == "error":
            # Go back to URL step to retry
            self.state.ia_download_wizard.step = "url"
            self.state.ia_download_wizard.cursor_position = 0
            self.state.ia_download_wizard.error_message = ""

    def _validate_ia_download_item(self):
        """Validate IA item URL in background."""
        self.state.ia_download_wizard.step = "validating"
        url = self.state.ia_download_wizard.url

        def validate_item():
            valid, item_id, error = validate_ia_url(url)
            if not valid:
                self.state.ia_download_wizard.step = "error"
                self.state.ia_download_wizard.error_message = error
                return

            self.state.ia_download_wizard.item_id = item_id

            # Get credentials if available (use None if not set)
            access_key = self.settings.get("ia_access_key") or None
            secret_key = self.settings.get("ia_secret_key") or None
            if secret_key:
                from services.internet_archive import decode_password

                secret_key = decode_password(secret_key)

            # List files in the item (pass None if no credentials)
            success, files, error = list_ia_files(
                item_id,
                access_key if access_key else None,
                secret_key if secret_key else None,
            )
            if not success:
                self.state.ia_download_wizard.step = "error"
                self.state.ia_download_wizard.error_message = error
                return

            if not files:
                self.state.ia_download_wizard.step = "error"
                self.state.ia_download_wizard.error_message = "No files found in item"
                return

            self.state.ia_download_wizard.files_list = files
            self.state.ia_download_wizard.selected_file_index = 0
            self.state.ia_download_wizard.step = "file_select"

        from threading import Thread

        thread = Thread(target=validate_item, daemon=True)
        thread.start()

    def _handle_ia_download_folder_selection(self):
        """Handle folder selection in IA download wizard."""
        wizard = self.state.ia_download_wizard
        items = wizard.folder_items
        highlighted = wizard.folder_highlighted

        if highlighted >= len(items):
            return

        item = items[highlighted]
        item_type = item.get("type", "")
        item_path = item.get("path", "")

        if item_type == "parent":
            # Navigate to parent
            wizard.output_folder = item_path
            wizard.folder_items = load_folder_contents(item_path)
            wizard.folder_highlighted = 0
        elif item_type == "folder":
            # Navigate into folder
            wizard.output_folder = item_path
            wizard.folder_items = load_folder_contents(item_path)
            wizard.folder_highlighted = 0
        else:
            # Select current folder and move to options
            wizard.step = "options"

    def _start_ia_download(self):
        """Start the IA download."""
        wizard = self.state.ia_download_wizard

        if not wizard.files_list or wizard.selected_file_index >= len(
            wizard.files_list
        ):
            return

        file_info = wizard.files_list[wizard.selected_file_index]
        filename = file_info["name"]
        download_url = get_ia_download_url(wizard.item_id, filename)

        # Create a game-like object for the download manager
        game = {
            "name": filename,
            "filename": filename,
            "href": download_url,
            "size": file_info.get("size", 0),
        }

        # Create system data for download
        system_data = {
            "name": f"IA: {wizard.item_id}",
            "url": "",
            "download_url": True,  # Indicates direct download URL in href
            "file_format": [
                "." + filename.rsplit(".", 1)[-1] if "." in filename else ""
            ],
            "roms_folder": wizard.output_folder,
            "should_unzip": wizard.should_extract,
        }

        # Add auth only if credentials are available
        access_key = self.settings.get("ia_access_key") or None
        secret_key = self.settings.get("ia_secret_key") or None
        if access_key and secret_key:
            from services.internet_archive import decode_password

            system_data["auth"] = {
                "type": "ia_s3",
                "access_key": access_key,
                "secret_key": decode_password(secret_key),
            }

        # Add to download queue
        self.download_manager.add_to_queue([game], system_data, f"IA: {wizard.item_id}")

        # Close wizard and go to downloads
        self._close_ia_download_wizard()
        self.state.mode = "downloads"
        self.state.download_queue.highlighted = max(
            0, len(self.state.download_queue.items) - 1
        )

    def _show_ia_collection_wizard(self):
        """Show the IA collection wizard modal."""
        self.state.ia_collection_wizard.show = True
        self.state.ia_collection_wizard.step = "url"
        self.state.ia_collection_wizard.url = ""
        self.state.ia_collection_wizard.item_id = ""
        self.state.ia_collection_wizard.collection_name = ""
        self.state.ia_collection_wizard.folder_name = ""
        self.state.ia_collection_wizard.file_formats = [".zip"]
        self.state.ia_collection_wizard.should_unzip = True
        self.state.ia_collection_wizard.cursor_position = 0
        self.state.ia_collection_wizard.error_message = ""
        self.state.ia_collection_wizard.available_formats = []
        self.state.ia_collection_wizard.selected_formats = set()
        self.state.ia_collection_wizard.format_highlighted = 0

    def _close_ia_collection_wizard(self):
        """Close the IA collection wizard modal."""
        self.state.ia_collection_wizard.show = False
        self.state.ia_collection_wizard.step = "url"
        self.state.ia_collection_wizard.url = ""
        self.state.ia_collection_wizard.item_id = ""
        self.state.ia_collection_wizard.collection_name = ""
        self.state.ia_collection_wizard.folder_name = ""
        self.state.ia_collection_wizard.available_formats = []
        self.state.ia_collection_wizard.selected_formats = set()

    def _handle_ia_collection_wizard_selection(self):
        """Handle selection in IA collection wizard."""
        step = self.state.ia_collection_wizard.step

        if step == "url":
            if self.state.input_mode == "keyboard":
                if self.state.ia_collection_wizard.url:
                    self._validate_ia_collection_item()
            else:
                from ui.screens.modals.ia_collection_modal import IACollectionModal

                modal = IACollectionModal()
                new_text, is_done = modal.handle_selection(
                    step,
                    self.state.ia_collection_wizard.cursor_position,
                    self.state.ia_collection_wizard.url,
                )
                self.state.ia_collection_wizard.url = new_text
                if is_done and new_text:
                    self._validate_ia_collection_item()

        elif step == "name":
            if self.state.input_mode == "keyboard":
                if self.state.ia_collection_wizard.collection_name:
                    # Open folder browser for folder selection
                    self._open_ia_collection_folder_browser()
            else:
                from ui.screens.modals.ia_collection_modal import IACollectionModal

                modal = IACollectionModal()
                new_text, is_done = modal.handle_selection(
                    step,
                    self.state.ia_collection_wizard.cursor_position,
                    self.state.ia_collection_wizard.collection_name,
                )
                self.state.ia_collection_wizard.collection_name = new_text
                if is_done and new_text:
                    # Open folder browser for folder selection
                    self._open_ia_collection_folder_browser()

        elif step == "folder":
            # Folder step is now handled by folder browser modal
            # This case handles if user somehow gets here without folder browser
            if self.state.ia_collection_wizard.folder_name:
                self.state.ia_collection_wizard.step = "formats"
            else:
                # Open folder browser if not already open
                if not self.state.folder_browser.show:
                    self._open_ia_collection_folder_browser()

        elif step == "formats":
            wizard = self.state.ia_collection_wizard

            # Check if we're in custom format input mode
            if wizard.adding_custom_format:
                # Handle keyboard selection for custom format
                if self.state.input_mode == "keyboard":
                    # Keyboard mode - Enter pressed, add the format
                    if wizard.custom_format_input:
                        fmt = wizard.custom_format_input
                        # Ensure format starts with a dot
                        if not fmt.startswith("."):
                            fmt = "." + fmt
                        # Add to available formats if not already there
                        if fmt not in wizard.available_formats:
                            wizard.available_formats.append(fmt)
                            # Select the newly added format
                            wizard.selected_formats.add(
                                len(wizard.available_formats) - 1
                            )
                    wizard.adding_custom_format = False
                    wizard.custom_format_input = ""
                    wizard.cursor_position = 0
                else:
                    # Gamepad/touch mode - handle on-screen keyboard
                    from ui.screens.modals.ia_collection_modal import IACollectionModal

                    modal = IACollectionModal()
                    new_text, is_done = modal.char_keyboard.handle_selection(
                        wizard.cursor_position,
                        wizard.custom_format_input,
                        char_set="default",
                    )
                    wizard.custom_format_input = new_text
                    if is_done:
                        if new_text:
                            fmt = new_text
                            if not fmt.startswith("."):
                                fmt = "." + fmt
                            if fmt not in wizard.available_formats:
                                wizard.available_formats.append(fmt)
                                wizard.selected_formats.add(
                                    len(wizard.available_formats) - 1
                                )
                        wizard.adding_custom_format = False
                        wizard.custom_format_input = ""
                        wizard.cursor_position = 0
            else:
                # Check if highlighted is on "Add custom format..." option
                if wizard.format_highlighted >= len(wizard.available_formats):
                    # Enter custom format input mode
                    wizard.adding_custom_format = True
                    wizard.custom_format_input = ""
                    wizard.cursor_position = 0
                else:
                    # Toggle format selection
                    if wizard.format_highlighted in wizard.selected_formats:
                        wizard.selected_formats.discard(wizard.format_highlighted)
                    else:
                        wizard.selected_formats.add(wizard.format_highlighted)

        elif step == "options":
            wizard = self.state.ia_collection_wizard
            if wizard.options_highlighted == 0:
                # Toggle unzip option
                wizard.should_unzip = not wizard.should_unzip
                # If unzip is turned off, reset options_highlighted to 0
                if not wizard.should_unzip:
                    wizard.options_highlighted = 0
            elif wizard.options_highlighted == 1 and wizard.should_unzip:
                # Toggle extract mode
                wizard.extract_contents = not wizard.extract_contents

        elif step == "confirm":
            # Create the collection
            self._create_ia_collection()

        elif step == "error":
            # Go back to URL step
            self.state.ia_collection_wizard.step = "url"
            self.state.ia_collection_wizard.cursor_position = 0
            self.state.ia_collection_wizard.error_message = ""

    def _validate_ia_collection_item(self):
        """Validate IA collection ID in background."""
        self.state.ia_collection_wizard.step = "validating"
        # The url field now stores the collection_id directly
        item_id = self.state.ia_collection_wizard.url.strip()

        # Get credentials if available (use None if not set)
        access_key = self.settings.get("ia_access_key") or None
        secret_key = self.settings.get("ia_secret_key") or None
        if secret_key:
            from services.internet_archive import decode_password

            secret_key = decode_password(secret_key)

        def validate_item():
            if not item_id:
                self.state.ia_collection_wizard.step = "error"
                self.state.ia_collection_wizard.error_message = "Collection ID is empty"
                return

            self.state.ia_collection_wizard.item_id = item_id

            # Get available formats (pass auth if available)
            success, formats, error = get_available_formats(
                item_id,
                access_key if access_key else None,
                secret_key if secret_key else None,
            )
            if not success:
                self.state.ia_collection_wizard.step = "error"
                self.state.ia_collection_wizard.error_message = error
                return

            if not formats:
                self.state.ia_collection_wizard.step = "error"
                self.state.ia_collection_wizard.error_message = "No files found in item"
                return

            # Only show .zip in the format list (user can add custom formats)
            if ".zip" in formats:
                self.state.ia_collection_wizard.available_formats = [".zip"]
                self.state.ia_collection_wizard.selected_formats.add(0)
            else:
                # No .zip available, start with empty list
                self.state.ia_collection_wizard.available_formats = []

            # Pre-fill name from item_id
            self.state.ia_collection_wizard.collection_name = item_id.replace(
                "_", " "
            ).title()
            self.state.ia_collection_wizard.folder_name = item_id.lower().replace(
                " ", "_"
            )

            self.state.ia_collection_wizard.step = "name"
            self.state.ia_collection_wizard.cursor_position = 0

        from threading import Thread

        thread = Thread(target=validate_item, daemon=True)
        thread.start()

    def _create_ia_collection(self):
        """Create the IA collection and add to systems."""
        wizard = self.state.ia_collection_wizard

        # Get selected formats
        selected_formats = (
            [wizard.available_formats[i] for i in sorted(wizard.selected_formats)]
            if wizard.selected_formats
            else wizard.available_formats
        )

        # Build the system URL
        system_url = f"https://archive.org/download/{wizard.item_id}/"

        # Build auth config only if credentials are available
        auth = None
        access_key = self.settings.get("ia_access_key") or None
        secret_key = self.settings.get("ia_secret_key") or None
        if access_key and secret_key:
            from services.internet_archive import decode_password

            auth = {
                "type": "ia_s3",
                "access_key": access_key,
                "secret_key": decode_password(secret_key),
            }

        # Add the system
        success = add_system_to_added_systems(
            system_name=wizard.collection_name,
            rom_folder=wizard.folder_name,
            system_url=system_url,
            file_formats=selected_formats,
            should_unzip=wizard.should_unzip,
            extract_contents=wizard.extract_contents,
            auth=auth,
        )

        if success:
            # Reload data
            self.data = load_main_systems_data(self.settings)
            self._close_ia_collection_wizard()
            # Go to systems screen
            self.state.mode = "systems"
            self.state.highlighted = 0
        else:
            wizard.step = "error"
            wizard.error_message = "Failed to save collection"


def main():
    """Entry point for the application."""
    try:
        app = ConsoleUtilitiesApp()
        app.run()
    except Exception as e:
        import traceback

        log_error(f"Application error: {e}", type(e).__name__, traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
