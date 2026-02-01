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
    FPS, SCREEN_WIDTH, SCREEN_HEIGHT, FONT_SIZE,
    BACKGROUND, SCRIPT_DIR
)
from state import AppState
from config.settings import (
    load_settings, save_settings,
    load_controller_mapping, save_controller_mapping,
    needs_controller_mapping, get_controller_mapping
)
from services.data_loader import (
    load_main_systems_data, update_json_file_path,
    get_visible_systems, get_system_index_by_name
)
from services.file_listing import list_files, filter_games_by_search, load_folder_contents
from services.image_cache import ImageCache
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

    def _draw_background(self):
        """Draw the background."""
        if self.background_image:
            scaled_bg = pygame.transform.scale(
                self.background_image,
                self.screen.get_size()
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
        if self.state.selected_system < 0 or self.state.selected_system >= len(self.data):
            return None

        system_data = self.data[self.state.selected_system]
        boxart_url = system_data.get('boxarts', '')

        return self.image_cache.get_thumbnail(game, boxart_url, self.settings)

    def _get_hires_image(self, game: Any) -> Optional[pygame.Surface]:
        """Get hi-res image for a game."""
        if self.state.selected_system < 0 or self.state.selected_system >= len(self.data):
            return None

        system_data = self.data[self.state.selected_system]
        boxart_url = system_data.get('boxarts', '')

        return self.image_cache.get_hires_image(game, boxart_url, self.settings)

    def run(self):
        """Run the main application loop."""
        running = True

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
                    self._handle_key_event(event)

                elif event.type == pygame.JOYBUTTONDOWN:
                    self._handle_joystick_event(event)

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        self.touch.handle_mouse_down(event)

                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1:
                        self.touch.handle_mouse_up(
                            event,
                            on_click=self._handle_click
                        )

                elif event.type == pygame.MOUSEWHEEL:
                    self.touch.handle_mouse_wheel(
                        event,
                        on_scroll=self._handle_scroll
                    )

                elif event.type == pygame.MOUSEMOTION:
                    self.touch.handle_mouse_motion(
                        event,
                        on_scroll=self._handle_scroll
                    )

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
                get_hires_image=self._get_hires_image
            )

            # Store rects for click handling
            self.state.ui_rects.menu_items = rects.get('item_rects', [])
            self.state.ui_rects.back_button = rects.get('back')

            pygame.display.flip()

        # Cleanup
        pygame.quit()

    def _on_navigate(self, direction: str, hat: tuple):
        """Handle navigation from held direction."""
        self._move_highlight(direction)

    def _move_highlight(self, direction: str):
        """Move highlight in the given direction."""
        if self.state.mode == "systems":
            visible = get_visible_systems(self.data, self.settings)
            max_items = len(visible) + 3  # +3 for Utils, Settings, Credits

            if direction in ("up", "left"):
                self.state.highlighted = (self.state.highlighted - 1) % max_items
            elif direction in ("down", "right"):
                self.state.highlighted = (self.state.highlighted + 1) % max_items

        elif self.state.mode == "games":
            game_list = self.state.search.filtered_list if self.state.search.mode else self.state.game_list
            max_items = len(game_list)

            if self.settings.get("view_type") == "grid":
                cols = 4
                if direction == "up" and self.state.highlighted >= cols:
                    self.state.highlighted -= cols
                elif direction == "down" and self.state.highlighted + cols < max_items:
                    self.state.highlighted += cols
                elif direction == "left" and self.state.highlighted % cols > 0:
                    self.state.highlighted -= 1
                elif direction == "right" and self.state.highlighted % cols < cols - 1 and self.state.highlighted < max_items - 1:
                    self.state.highlighted += 1
            else:
                if direction in ("up", "left"):
                    self.state.highlighted = (self.state.highlighted - 1) % max_items
                elif direction in ("down", "right"):
                    self.state.highlighted = (self.state.highlighted + 1) % max_items

        elif self.state.mode in ("settings", "utils"):
            if self.state.mode == "settings":
                max_items = 11  # Number of settings items
            else:
                max_items = 2

            if direction in ("up", "left"):
                self.state.highlighted = (self.state.highlighted - 1) % max_items
            elif direction in ("down", "right"):
                self.state.highlighted = (self.state.highlighted + 1) % max_items

        elif self.state.mode == "add_systems":
            max_items = len(self.state.available_systems) or 1
            if direction in ("up", "left"):
                self.state.add_systems_highlighted = (self.state.add_systems_highlighted - 1) % max_items
            elif direction in ("down", "right"):
                self.state.add_systems_highlighted = (self.state.add_systems_highlighted + 1) % max_items

        elif self.state.mode == "systems_settings":
            max_items = len(self.data) or 1
            if direction in ("up", "left"):
                self.state.systems_settings_highlighted = (self.state.systems_settings_highlighted - 1) % max_items
            elif direction in ("down", "right"):
                self.state.systems_settings_highlighted = (self.state.systems_settings_highlighted + 1) % max_items

        elif self.state.mode == "system_settings":
            max_items = 2  # Hide System, Set Custom Folder
            if direction in ("up", "left"):
                self.state.system_settings_highlighted = (self.state.system_settings_highlighted - 1) % max_items
            elif direction in ("down", "right"):
                self.state.system_settings_highlighted = (self.state.system_settings_highlighted + 1) % max_items

        # Handle keyboard modals navigation
        elif self.state.url_input.show:
            self._navigate_keyboard_modal(direction, self.state.url_input, char_set="url")

        elif self.state.folder_name_input.show:
            self._navigate_keyboard_modal(direction, self.state.folder_name_input, char_set="default")

    def _handle_key_event(self, event: pygame.event.Event):
        """Handle keyboard events."""
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

    def _handle_joystick_event(self, event: pygame.event.Event):
        """Handle joystick button events."""
        action = self.controller.get_action_for_event(event)

        if action == "back":
            self._go_back()
        elif action == "select":
            self._select_item()
        elif action in ("up", "down", "left", "right"):
            self._move_highlight(action)

    def _handle_click(self, pos: tuple):
        """Handle click/tap events."""
        x, y = pos

        # Check back button
        if self.state.ui_rects.back_button:
            if self.state.ui_rects.back_button.collidepoint(x, y):
                self._go_back()
                return

        # Check menu items
        for i, rect in enumerate(self.state.ui_rects.menu_items):
            if rect.collidepoint(x, y):
                self.state.highlighted = i
                self._select_item()
                return

    def _handle_scroll(self, amount: float):
        """Handle scroll events."""
        if amount > 0:
            self._move_highlight("up")
        elif amount < 0:
            self._move_highlight("down")

    def _go_back(self):
        """Handle back navigation."""
        if self.state.show_search_input:
            self.state.show_search_input = False
        elif self.state.url_input.show:
            self.state.url_input.show = False
        elif self.state.folder_name_input.show:
            self.state.folder_name_input.show = False
        elif self.state.folder_browser.show:
            self.state.folder_browser.show = False
        elif self.state.game_details.show:
            self.state.game_details.show = False
        elif self.state.mode == "system_settings":
            self.state.mode = "systems_settings"
            self.state.system_settings_highlighted = 0
        elif self.state.mode in ("add_systems", "systems_settings"):
            self.state.mode = "settings"
            self.state.highlighted = 0
        elif self.state.mode in ("games", "settings", "utils", "credits"):
            self.state.mode = "systems"
            self.state.highlighted = 0

    def _select_item(self):
        """Handle item selection."""
        if self.state.mode == "systems":
            visible = get_visible_systems(self.data, self.settings)
            systems_count = len(visible)

            if self.state.highlighted < systems_count:
                # Select a system
                system = visible[self.state.highlighted]
                self.state.selected_system = get_system_index_by_name(self.data, system['name'])
                self.state.mode = "games"
                self.state.highlighted = 0
                self.state.game_list = list_files(
                    self.data[self.state.selected_system],
                    self.settings
                )
            elif self.state.highlighted == systems_count:
                self.state.mode = "utils"
                self.state.highlighted = 0
            elif self.state.highlighted == systems_count + 1:
                self.state.mode = "settings"
                self.state.highlighted = 0
            elif self.state.highlighted == systems_count + 2:
                self.state.mode = "credits"

        elif self.state.mode == "games":
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

        elif self.state.url_input.show:
            self._handle_url_input_selection()

        elif self.state.folder_name_input.show:
            self._handle_folder_name_input_selection()

    def _handle_settings_selection(self):
        """Handle settings item selection."""
        from ui.screens.settings_screen import SettingsScreen
        action = SettingsScreen.SETTINGS_ITEMS[self.state.highlighted] if self.state.highlighted < len(SettingsScreen.SETTINGS_ITEMS) else None

        if action == "Enable Box-art Display":
            self.settings["enable_boxart"] = not self.settings.get("enable_boxart", True)
            save_settings(self.settings)
        elif action == "View Type":
            current = self.settings.get("view_type", "grid")
            self.settings["view_type"] = "list" if current == "grid" else "grid"
            save_settings(self.settings)
        elif action == "USA Games Only":
            self.settings["usa_only"] = not self.settings.get("usa_only", False)
            save_settings(self.settings)
        elif action == "Work Directory":
            self._open_folder_browser("work_dir")
        elif action == "ROMs Directory":
            self._open_folder_browser("roms_dir")
        elif action == "Add Systems":
            self.state.mode = "add_systems"
            self.state.add_systems_highlighted = 0
        elif action == "Systems Settings":
            self.state.mode = "systems_settings"
            self.state.systems_settings_highlighted = 0

    def _handle_utils_selection(self):
        """Handle utils item selection."""
        if self.state.highlighted == 0:
            # Download from URL
            self.state.url_input.show = True
            self.state.url_input.context = "direct_download"
        elif self.state.highlighted == 1:
            # NSZ converter
            self._open_folder_browser("nsz_converter")

    def _open_folder_browser(self, selection_type: str):
        """Open the folder browser modal."""
        self.state.folder_browser.show = True
        self.state.folder_browser.highlighted = 0
        self.state.folder_browser.selected_system_to_add = {"type": selection_type}

        # Set initial path
        if selection_type == "work_dir":
            path = self.settings.get("work_dir", os.path.expanduser("~"))
        elif selection_type == "roms_dir":
            path = self.settings.get("roms_dir", os.path.expanduser("~"))
        else:
            path = os.path.expanduser("~")

        if os.path.exists(path):
            self.state.folder_browser.current_path = path
        else:
            self.state.folder_browser.current_path = os.path.expanduser("~")

        self.state.folder_browser.items = load_folder_contents(
            self.state.folder_browser.current_path
        )

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
            self.state.selected_system_for_settings = self.state.systems_settings_highlighted
            self.state.mode = "system_settings"
            self.state.system_settings_highlighted = 0

    def _handle_system_settings_selection(self):
        """Handle individual system settings selection."""
        from ui.screens.system_settings_screen import SystemSettingsScreen
        action = SystemSettingsScreen().get_setting_action(self.state.system_settings_highlighted)

        if self.state.selected_system_for_settings is None:
            return

        system = self.data[self.state.selected_system_for_settings]
        system_name = system.get('name', '')

        if action == "toggle_hide_system":
            # Toggle hidden state
            system_settings = self.settings.setdefault("system_settings", {})
            sys_settings = system_settings.setdefault(system_name, {})
            sys_settings['hidden'] = not sys_settings.get('hidden', False)
            save_settings(self.settings)

        elif action == "set_custom_folder":
            # Open folder browser for custom folder
            self._open_folder_browser("custom_folder")

    def _navigate_keyboard_modal(
        self,
        direction: str,
        modal_state,
        char_set: str = "default"
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

    def _handle_url_input_selection(self):
        """Handle URL input keyboard selection."""
        from ui.screens.modals.url_input_modal import UrlInputModal
        modal = UrlInputModal()
        new_text, is_done = modal.handle_selection(
            self.state.url_input.cursor_position,
            self.state.url_input.input_text
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
            self.state.folder_name_input.input_text
        )
        self.state.folder_name_input.input_text = new_text

        if is_done:
            # Folder name entry complete
            self.state.folder_name_input.show = False
            # TODO: Create the folder with the given name


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
