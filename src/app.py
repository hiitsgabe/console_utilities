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
    DEV_MODE,
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
    load_available_systems,
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
from services.scraper_manager import ScraperManager
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

        # Create display - auto-detect native resolution on console
        if DEV_MODE:
            self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        else:
            display_info = pygame.display.Info()
            self.screen = pygame.display.set_mode(
                (display_info.current_w, display_info.current_h),
                pygame.FULLSCREEN,
            )
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font("assets/fonts/VT323-Regular.ttf", FONT_SIZE)

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

        # CRT scanline overlay (use actual screen size)
        sw, sh = self.screen.get_size()
        self.scanline_surface = None
        if self.theme.crt_scanlines:
            self.scanline_surface = pygame.Surface((sw, sh), pygame.SRCALPHA)
            for y in range(0, sh, 3):
                pygame.draw.line(
                    self.scanline_surface,
                    (0, 0, 0, 40),
                    (0, y),
                    (sw, y),
                )

        # CRT bezel overlay (physical monitor frame)
        self.bezel_surface = self._create_crt_bezel()

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

        # Initialize scraper manager
        self.scraper_manager = ScraperManager(self.settings, self.state.scraper_queue)

        # CRT vignette overlay (edge darkening)
        self.vignette_surface = self._create_vignette()

        # Check if controller mapping needed
        self.needs_mapping = needs_controller_mapping()

    def _create_vignette(self) -> pygame.Surface:
        """Create a pre-rendered vignette overlay for CRT edge darkening."""
        sw, sh = self.screen.get_size()
        vignette = pygame.Surface((sw, sh), pygame.SRCALPHA)

        # Draw concentric dark borders to simulate brightness falloff
        border_rects = [
            (40, (0, 0, 0, 50)),  # 40px border, alpha 50
            (30, (0, 0, 0, 35)),  # 30px border, alpha 35
            (20, (0, 0, 0, 20)),  # 20px border, alpha 20
            (10, (0, 0, 0, 10)),  # 10px border, alpha 10
        ]

        for width, color in border_rects:
            # Top
            pygame.draw.rect(vignette, color, (0, 0, sw, width))
            # Bottom
            pygame.draw.rect(vignette, color, (0, sh - width, sw, width))
            # Left
            pygame.draw.rect(vignette, color, (0, 0, width, sh))
            # Right
            pygame.draw.rect(vignette, color, (sw - width, 0, width, sh))

        # Subtle center phosphor glow
        center = pygame.Surface((sw, sh), pygame.SRCALPHA)
        pygame.draw.ellipse(
            center,
            (0, 15, 0, 25),  # Very subtle green glow
            (sw // 4, sh // 4, sw // 2, sh // 2),
        )
        vignette.blit(center, (0, 0))

        return vignette

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

            if self.scanline_surface:
                self.screen.blit(self.scanline_surface, (0, 0))
            self.screen.blit(self.bezel_surface, (0, 0))
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
        """Draw the CRT monitor background."""
        self.screen.fill(BACKGROUND)
        self.screen.blit(self.vignette_surface, (0, 0))

    def _create_crt_bezel(self) -> pygame.Surface:
        """
        Create a pre-rendered CRT monitor bezel overlay.

        Draws a beige/tan monitor casing frame around the screen edges,
        with an inner bevel for depth. The center is left transparent
        so the green content shows through. Uses actual screen dimensions
        for responsive rendering on different display sizes.
        """
        w, h = self.screen.get_size()
        bezel = pygame.Surface((w, h), pygame.SRCALPHA)

        # Bezel dimensions
        outer_width = 22  # Outer beige frame thickness
        inner_width = 4  # Inner dark bevel thickness
        corner_radius = 10  # Rounding on the outer corners

        # Colors
        bezel_color = (190, 170, 140)  # Warm beige for the monitor casing
        bevel_dark = (150, 130, 100)  # Darker inner bevel for depth
        bevel_highlight = (210, 195, 170)  # Lighter top/left highlight edge

        # --- Outer bezel frame ---
        # Top edge
        pygame.draw.rect(bezel, bezel_color, (0, 0, w, outer_width))
        # Bottom edge
        pygame.draw.rect(
            bezel,
            bezel_color,
            (0, h - outer_width, w, outer_width),
        )
        # Left edge
        pygame.draw.rect(bezel, bezel_color, (0, 0, outer_width, h))
        # Right edge
        pygame.draw.rect(
            bezel,
            bezel_color,
            (w - outer_width, 0, outer_width, h),
        )

        # Rounded corners (filled quarter-circles in bezel color)
        pygame.draw.circle(
            bezel, bezel_color, (corner_radius, corner_radius), corner_radius
        )
        pygame.draw.circle(
            bezel,
            bezel_color,
            (w - corner_radius, corner_radius),
            corner_radius,
        )
        pygame.draw.circle(
            bezel,
            bezel_color,
            (corner_radius, h - corner_radius),
            corner_radius,
        )
        pygame.draw.circle(
            bezel,
            bezel_color,
            (w - corner_radius, h - corner_radius),
            corner_radius,
        )

        # --- Highlight edge (top and left, simulates light source) ---
        pygame.draw.line(bezel, bevel_highlight, (0, 0), (w, 0), 2)
        pygame.draw.line(bezel, bevel_highlight, (0, 0), (0, h), 2)

        # --- Inner bevel (darker edge where bezel meets screen) ---
        inner_x = outer_width
        inner_y = outer_width
        inner_w = w - 2 * outer_width
        inner_h = h - 2 * outer_width

        # Dark bevel lines around the screen opening
        # Top inner edge
        pygame.draw.rect(bezel, bevel_dark, (inner_x, inner_y, inner_w, inner_width))
        # Bottom inner edge
        pygame.draw.rect(
            bezel,
            bevel_dark,
            (inner_x, inner_y + inner_h - inner_width, inner_w, inner_width),
        )
        # Left inner edge
        pygame.draw.rect(bezel, bevel_dark, (inner_x, inner_y, inner_width, inner_h))
        # Right inner edge
        pygame.draw.rect(
            bezel,
            bevel_dark,
            (inner_x + inner_w - inner_width, inner_y, inner_width, inner_h),
        )

        # --- Shadow edge (bottom and right outer, simulates depth) ---
        pygame.draw.line(
            bezel,
            (120, 105, 80),
            (0, h - 1),
            (w, h - 1),
            2,
        )
        pygame.draw.line(
            bezel,
            (120, 105, 80),
            (w - 1, 0),
            (w - 1, h),
            2,
        )

        return bezel

    def _get_thumbnail(
        self, game: Any, system_data: Optional[dict] = None
    ) -> Optional[pygame.Surface]:
        """Get thumbnail for a game."""
        if system_data:
            boxart_url = system_data.get("boxarts", "")
        else:
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

    def _extract_rar_file(self, rar_path: str):
        """Extract a RAR file to the same folder using rarfile."""
        import threading
        import rarfile

        output_folder = os.path.dirname(rar_path)
        rar_name = os.path.basename(rar_path)

        self.state.folder_browser.show = False
        self._show_loading(f"Extracting {rar_name}...")

        def extract():
            try:
                with rarfile.RarFile(rar_path, "r") as rf:
                    members = rf.infolist()
                    total = len(members)
                    for i, member in enumerate(members):
                        rf.extract(member, output_folder)
                        progress = int((i + 1) / total * 100)
                        self.state.loading.progress = progress
                        self.state.loading.message = (
                            f"Extracting {rar_name}... {progress}%"
                        )
                self._hide_loading()
            except Exception as e:
                from utils.logging import log_error

                log_error(f"Failed to extract RAR: {e}")
                self._hide_loading()

        thread = threading.Thread(target=extract, daemon=True)
        thread.start()

    def _extract_7z_file(self, sz_path: str):
        """Extract a 7z file to the same folder using rarfile."""
        import threading
        import rarfile

        output_folder = os.path.dirname(sz_path)
        sz_name = os.path.basename(sz_path)

        self.state.folder_browser.show = False
        self._show_loading(f"Extracting {sz_name}...")

        def extract():
            try:
                with rarfile.RarFile(sz_path, "r") as rf:
                    members = rf.infolist()
                    total = len(members)
                    for i, member in enumerate(members):
                        rf.extract(member, output_folder)
                        progress = int((i + 1) / total * 100)
                        self.state.loading.progress = progress
                        self.state.loading.message = (
                            f"Extracting {sz_name}... {progress}%"
                        )
                self._hide_loading()
            except Exception as e:
                from utils.logging import log_error

                log_error(f"Failed to extract 7z: {e}")
                self._hide_loading()

        thread = threading.Thread(target=extract, daemon=True)
        thread.start()

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
        if self.scanline_surface:
            self.screen.blit(self.scanline_surface, (0, 0))
        self.screen.blit(self.bezel_surface, (0, 0))
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
                    # Skip ALL keyboard events if joystick is connected
                    # Some consoles/controllers generate keyboard events alongside joystick events
                    # which causes double input. Joystick takes priority.
                    if self.joystick is not None:
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
            self.state.ui_rects.rects = rects

            if self.scanline_surface:
                self.screen.blit(self.scanline_surface, (0, 0))
            self.screen.blit(self.bezel_surface, (0, 0))
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
            # Left/right scroll the game name text horizontally
            if direction in ("left", "right"):
                scroll_step = 20
                if direction == "right":
                    self.state.text_scroll_offset += scroll_step
                else:
                    self.state.text_scroll_offset = max(
                        0, self.state.text_scroll_offset - scroll_step
                    )
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

        if self.state.scraper_login.show:
            step = self.state.scraper_login.step
            if step in ("username", "password", "api_key"):
                char_set = "url" if step == "api_key" else "default"
                self._navigate_keyboard_modal(
                    direction, self.state.scraper_login, char_set=char_set
                )
            return

        if self.state.scraper_wizard.show:
            self._navigate_scraper_wizard(direction)
            return

        if self.state.dedupe_wizard.show:
            self._navigate_dedupe_wizard(direction)
            return

        if self.state.rename_wizard.show:
            self._navigate_rename_wizard(direction)
            return

        # Mode-based navigation
        if self.state.mode == "systems":
            from ui.screens.systems_screen import systems_screen

            max_items = systems_screen.get_root_menu_count()

            if direction in ("up", "left"):
                self.state.highlighted = (self.state.highlighted - 1) % max_items
            elif direction in ("down", "right"):
                self.state.highlighted = (self.state.highlighted + 1) % max_items

        elif self.state.mode == "systems_list":
            visible = get_visible_systems(self.data, self.settings)
            max_items = len(visible)

            if max_items > 0:
                if direction in ("up", "left"):
                    self.state.systems_list_highlighted = (
                        self.state.systems_list_highlighted - 1
                    ) % max_items
                elif direction in ("down", "right"):
                    self.state.systems_list_highlighted = (
                        self.state.systems_list_highlighted + 1
                    ) % max_items

        elif self.state.mode == "games":
            game_list = (
                self.state.search.filtered_list
                if self.state.search.mode
                else self.state.game_list
            )
            # Add 1 for "Download All" button if enabled
            extra_items = 1 if self.settings.get("show_download_all", False) else 0
            max_items = len(game_list) + extra_items

            if direction in ("left", "right"):
                # Left/right scroll the highlighted item's text horizontally
                scroll_step = 20
                if direction == "right":
                    self.state.text_scroll_offset += scroll_step
                else:
                    self.state.text_scroll_offset = max(
                        0, self.state.text_scroll_offset - scroll_step
                    )
            elif direction == "up":
                self.state.highlighted = (self.state.highlighted - 1) % max_items
                self.state.text_scroll_offset = 0
            elif direction == "down":
                self.state.highlighted = (self.state.highlighted + 1) % max_items
                self.state.text_scroll_offset = 0

        elif self.state.mode in ("settings", "utils"):
            if self.state.mode == "settings":
                from ui.screens.settings_screen import settings_screen

                max_items = settings_screen.get_max_items(self.settings, self.data)
                _, divider_indices = settings_screen._get_settings_items(
                    self.settings, self.data
                )
            else:
                from ui.screens.utils_screen import utils_screen

                max_items = utils_screen.get_max_items(self.settings)
                _, divider_indices = utils_screen._get_utils_items(self.settings)

            if direction in ("up", "left"):
                new_pos = (self.state.highlighted - 1) % max_items
                # Skip divider items
                while new_pos in divider_indices and max_items > len(divider_indices):
                    new_pos = (new_pos - 1) % max_items
                self.state.highlighted = new_pos
            elif direction in ("down", "right"):
                new_pos = (self.state.highlighted + 1) % max_items
                while new_pos in divider_indices and max_items > len(divider_indices):
                    new_pos = (new_pos + 1) % max_items
                self.state.highlighted = new_pos

        elif self.state.mode == "credits":
            from ui.screens.credits_screen import SCROLL_STEP

            max_scroll = self.state.ui_rects.rects.get("credits_max_scroll", 0)
            if direction == "down":
                self.state.credits_scroll_offset = min(
                    self.state.credits_scroll_offset + SCROLL_STEP,
                    max_scroll,
                )
            elif direction == "up":
                self.state.credits_scroll_offset = max(
                    self.state.credits_scroll_offset - SCROLL_STEP,
                    0,
                )

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

        elif self.state.mode == "scraper_downloads":
            max_items = len(self.state.scraper_queue.items) or 1
            if direction in ("up", "left"):
                self.state.scraper_queue.highlighted = (
                    self.state.scraper_queue.highlighted - 1
                ) % max_items
            elif direction in ("down", "right"):
                self.state.scraper_queue.highlighted = (
                    self.state.scraper_queue.highlighted + 1
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

        # Handle keyboard text input for scraper login modal
        if self.state.scraper_login.show and self.state.input_mode == "keyboard":
            step = self.state.scraper_login.step
            if step in ("username", "password", "api_key"):
                if event.key == pygame.K_ESCAPE:
                    self._go_back()
                elif event.key == pygame.K_RETURN:
                    self._handle_scraper_login_selection()
                elif event.key == pygame.K_BACKSPACE:
                    if step == "username" and self.state.scraper_login.username:
                        self.state.scraper_login.username = (
                            self.state.scraper_login.username[:-1]
                        )
                    elif step == "password" and self.state.scraper_login.password:
                        self.state.scraper_login.password = (
                            self.state.scraper_login.password[:-1]
                        )
                    elif step == "api_key" and self.state.scraper_login.api_key:
                        self.state.scraper_login.api_key = (
                            self.state.scraper_login.api_key[:-1]
                        )
                elif event.unicode and event.unicode.isprintable():
                    if step == "username":
                        self.state.scraper_login.username += event.unicode
                    elif step == "password":
                        self.state.scraper_login.password += event.unicode
                    elif step == "api_key":
                        self.state.scraper_login.api_key += event.unicode
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
        elif event.key == pygame.K_q:
            self._toggle_keyboard_shift()
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
        elif action == "left_shoulder":
            self._toggle_keyboard_shift()
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

        # Check IA download wizard list items
        if self.state.ia_download_wizard.show:
            step = self.state.ia_download_wizard.step
            if step == "file_select":
                for i, rect in enumerate(self.state.ui_rects.menu_items):
                    if rect.collidepoint(x, y):
                        self.state.ia_download_wizard.selected_file_index = i
                        self._handle_ia_download_wizard_selection()
                        return
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
            # Navigate up if inside a folder, otherwise close
            if (
                self.state.ia_download_wizard.step == "file_select"
                and self.state.ia_download_wizard.current_folder
            ):
                self._ia_navigate_up()
            else:
                self._close_ia_download_wizard()
        elif self.state.ia_collection_wizard.show:
            # Check if we're in custom format input mode
            if self.state.ia_collection_wizard.adding_custom_format:
                self.state.ia_collection_wizard.adding_custom_format = False
                self.state.ia_collection_wizard.custom_format_input = ""
                self.state.ia_collection_wizard.cursor_position = 0
            else:
                self._close_ia_collection_wizard()
        elif self.state.scraper_login.show:
            self._close_scraper_login()
        elif self.state.scraper_wizard.show:
            if self.state.scraper_wizard.step == "video_select":
                self.state.scraper_wizard.step = "image_select"
            else:
                self._close_scraper_wizard()
        elif self.state.dedupe_wizard.show:
            self._close_dedupe_wizard()
        elif self.state.rename_wizard.show:
            self._close_rename_wizard()
        elif self.state.ghost_cleaner_wizard.show:
            self._close_ghost_cleaner()
        elif self.state.game_details.show:
            self.state.game_details.show = False
            self.state.game_details.current_game = None
            self.state.text_scroll_offset = 0
        elif self.state.mode == "system_settings":
            self.state.mode = "systems_settings"
            self.state.system_settings_highlighted = 0
        elif self.state.mode in ("add_systems", "systems_settings"):
            self.state.mode = "settings"
            self.state.highlighted = 1  # Skip first divider
        elif self.state.mode == "systems_list":
            self.state.mode = "systems"
            self.state.highlighted = 0
        elif self.state.mode == "games":
            # Reset selected games and search when leaving games mode
            self.state.selected_games.clear()
            self.state.search.mode = False
            self.state.search.query = ""
            self.state.search.input_text = ""
            self.state.search.cursor_position = 0
            self.state.search.filtered_list = []
            self.state.mode = "systems_list"
            self.state.highlighted = 0
        elif self.state.mode == "downloads":
            # Go back to games if we came from there, otherwise systems_list
            if self.state.selected_system >= 0 and self.state.game_list:
                self.state.mode = "games"
            else:
                self.state.mode = "systems_list"
            self.state.highlighted = 0
        elif self.state.mode == "scraper_downloads":
            # Go back to utils; scraping continues in background
            self.state.mode = "utils"
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

        if self.state.scraper_login.show:
            self._handle_scraper_login_selection()
            return

        if self.state.scraper_wizard.show:
            self._handle_scraper_wizard_selection()
            return

        if self.state.dedupe_wizard.show:
            self._handle_dedupe_wizard_selection()
            return

        if self.state.rename_wizard.show:
            self._handle_rename_wizard_selection()
            return

        if self.state.ghost_cleaner_wizard.show:
            self._handle_ghost_cleaner_selection()
            return

        # Mode-based selection
        if self.state.mode == "systems":
            from ui.screens.systems_screen import systems_screen

            action = systems_screen.get_root_menu_action(self.state.highlighted)
            if action == "systems_list":
                self.state.mode = "systems_list"
                # Don't reset systems_list_highlighted to preserve position
            elif action == "utils":
                self.state.mode = "utils"
                self.state.highlighted = 1  # Skip first divider
            elif action == "settings":
                self.state.mode = "settings"
                self.state.highlighted = 1  # Skip first divider
            elif action == "credits":
                self.state.mode = "credits"

        elif self.state.mode == "systems_list":
            visible = get_visible_systems(self.data, self.settings)
            if visible and self.state.systems_list_highlighted < len(visible):
                system = visible[self.state.systems_list_highlighted]
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

        total_games = len(game_list)

        # Filter out installed games if setting is on
        exclude_installed = self.settings.get("exclude_installed_on_download_all", True)
        if exclude_installed:
            download_list = [
                g for g in game_list if not installed_checker.is_installed(g)
            ]
            installed_count = total_games - len(download_list)
        else:
            download_list = list(game_list)
            installed_count = 0

        if not download_list:
            self.state.confirm_modal.show = True
            self.state.confirm_modal.title = "All Installed"
            self.state.confirm_modal.message_lines = [
                f"All {total_games} games are already installed.",
            ]
            self.state.confirm_modal.ok_label = "OK"
            self.state.confirm_modal.cancel_label = ""
            self.state.confirm_modal.button_index = 0
            self.state.confirm_modal.context = ""
            self.state.confirm_modal.data = None
            self.state.confirm_modal.loading = False
            return

        # Build message
        if installed_count > 0:
            msg_lines = [
                f"Download {len(download_list)} of {total_games} games?",
                f"({installed_count} already installed, skipped)",
                "",
                "This may take a while.",
            ]
        else:
            msg_lines = [
                f"Download all {total_games} games?",
                "",
                "This may take a while.",
            ]

        # Show simple confirmation modal
        self.state.confirm_modal.show = True
        self.state.confirm_modal.title = "Download All Games"
        self.state.confirm_modal.message_lines = msg_lines
        self.state.confirm_modal.ok_label = "Download"
        self.state.confirm_modal.cancel_label = "Cancel"
        self.state.confirm_modal.button_index = 0
        self.state.confirm_modal.context = "download_all"
        self.state.confirm_modal.data = download_list
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
        elif context == "apply_update" and data:
            self._apply_update(data)
            return  # Don't close modal yet - _apply_update manages its own UI

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
            self.state.highlighted, self.settings, self.data
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
        elif action == "toggle_usa_only":
            self.settings["usa_only"] = not self.settings.get("usa_only", False)
            save_settings(self.settings)
        elif action == "toggle_download_all":
            self.settings["show_download_all"] = not self.settings.get(
                "show_download_all", False
            )
            save_settings(self.settings)
        elif action == "toggle_exclude_installed":
            self.settings["exclude_installed_on_download_all"] = not self.settings.get(
                "exclude_installed_on_download_all", True
            )
            save_settings(self.settings)
        elif action == "select_work_dir":
            self._open_folder_browser("work_dir")
        elif action == "select_roms_dir":
            self._open_folder_browser("roms_dir")
        elif action == "add_systems":
            self._load_add_systems()
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
        elif action == "toggle_scraper_frontend":
            frontends = [
                "emulationstation_base",
                "esde_android",
                "retroarch",
                "pegasus",
            ]
            current = self.settings.get("scraper_frontend", "emulationstation_base")
            idx = frontends.index(current) if current in frontends else 0
            self.settings["scraper_frontend"] = frontends[(idx + 1) % len(frontends)]
            save_settings(self.settings)
        elif action == "toggle_scraper_provider":
            providers = [
                "libretro",
                "screenscraper",
                "thegamesdb",
                "rawg",
                "igdb",
            ]
            current = self.settings.get("scraper_provider", "libretro")
            idx = providers.index(current) if current in providers else 0
            self.settings["scraper_provider"] = providers[(idx + 1) % len(providers)]
            save_settings(self.settings)
        elif action == "toggle_scraper_fallback":
            current = self.settings.get("scraper_fallback_enabled", True)
            self.settings["scraper_fallback_enabled"] = not current
            save_settings(self.settings)
        elif action == "toggle_mixed_images":
            current = self.settings.get("scraper_mixed_images", False)
            self.settings["scraper_mixed_images"] = not current
            save_settings(self.settings)
        elif action == "cycle_parallel_downloads":
            options = [1, 2, 3, 4, 5]
            current = self.settings.get("scraper_parallel_downloads", 1)
            idx = options.index(current) if current in options else 0
            self.settings["scraper_parallel_downloads"] = options[
                (idx + 1) % len(options)
            ]
            save_settings(self.settings)
        elif action == "screenscraper_login":
            self._show_screenscraper_login()
        elif action == "thegamesdb_api_key":
            self._show_thegamesdb_api_key_input()
        elif action == "rawg_api_key":
            self._show_rawg_api_key_input()
        elif action == "igdb_login":
            self._show_igdb_login()
        elif action == "select_esde_media_path":
            self._open_folder_browser("esde_media_path")
        elif action == "select_esde_gamelists_path":
            self._open_folder_browser("esde_gamelists_path")
        elif action == "select_retroarch_thumbnails":
            self._open_folder_browser("retroarch_thumbnails")
        elif action == "add_to_frontend":
            self._add_to_frontend()
        elif action == "check_for_updates":
            self._check_for_updates()

    def _load_add_systems(self):
        """Load available systems in a background thread."""
        import threading

        self._show_loading("Loading available systems...")

        def _do_load():
            result = load_available_systems(self.data)
            self.state.available_systems = result
            self._hide_loading()
            self.state.mode = "add_systems"
            self.state.add_systems_highlighted = 0

        thread = threading.Thread(target=_do_load, daemon=True)
        thread.start()

    def _add_to_frontend(self):
        """Register Console Utilities in the frontend gamelist.xml."""
        from constants import BUILD_TARGET
        from xml.etree import ElementTree as ET
        from xml.dom import minidom

        roms_dir = self.settings.get("roms_dir", "")
        if not roms_dir:
            self.state.confirm_modal.show = True
            self.state.confirm_modal.title = "Link App to Frontend"
            self.state.confirm_modal.message_lines = [
                "ROMs directory is not set.",
                "",
                "Please set the ROMs directory first.",
            ]
            self.state.confirm_modal.ok_label = "OK"
            self.state.confirm_modal.cancel_label = ""
            self.state.confirm_modal.button_index = 0
            self.state.confirm_modal.context = ""
            return

        # Determine the build folder name (e.g., "pygame")
        build_folder = BUILD_TARGET if BUILD_TARGET != "source" else "pygame"
        target_dir = os.path.join(roms_dir, build_folder)

        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)

        gamelist_path = os.path.join(target_dir, "gamelist.xml")

        # Find the .pygame file in SCRIPT_DIR
        pygame_file = None
        for f in os.listdir(SCRIPT_DIR):
            if f.endswith(".pygame"):
                pygame_file = f
                break

        if not pygame_file:
            pygame_file = "console_utils.pygame"

        # Resolve assets directory - try SCRIPT_DIR first (bundle),
        # then SCRIPT_DIR/.. (dev mode where SCRIPT_DIR=src/)
        assets_dir = os.path.join(SCRIPT_DIR, "assets", "images")
        if not os.path.exists(assets_dir):
            assets_dir = os.path.join(SCRIPT_DIR, "..", "assets", "images")

        # Copy images into the target folder so the XML is self-contained
        import shutil

        images_dir = os.path.join(target_dir, "images")
        os.makedirs(images_dir, exist_ok=True)

        logo_src = os.path.join(assets_dir, "logo.png")
        screenshot_src = os.path.join(assets_dir, "screenshot.png")
        logo_dest = os.path.join(images_dir, "logo.png")
        screenshot_dest = os.path.join(images_dir, "screenshot.png")

        if os.path.exists(logo_src):
            shutil.copy2(logo_src, logo_dest)
        if os.path.exists(screenshot_src):
            shutil.copy2(screenshot_src, screenshot_dest)

        # Load or create gamelist.xml
        if os.path.exists(gamelist_path):
            try:
                tree = ET.parse(gamelist_path)
                root = tree.getroot()
            except ET.ParseError:
                root = ET.Element("gameList")
        else:
            root = ET.Element("gameList")

        # Find existing entry or create new
        game_path = f"./{pygame_file}"
        game_elem = None
        for game in root.findall("game"):
            path_elem = game.find("path")
            if path_elem is not None and path_elem.text == game_path:
                game_elem = game
                break

        if game_elem is None:
            game_elem = ET.SubElement(root, "game")

        def _set_elem(parent, tag, text):
            elem = parent.find(tag)
            if elem is None:
                elem = ET.SubElement(parent, tag)
            elem.text = text

        _set_elem(game_elem, "path", game_path)
        _set_elem(game_elem, "name", "Console Utilities")
        _set_elem(
            game_elem,
            "desc",
            "A download management tool for handheld gaming consoles. "
            "Manage ROMs, scrape game metadata, and organize your library.",
        )
        if os.path.exists(logo_dest):
            _set_elem(game_elem, "image", "./images/logo.png")
        if os.path.exists(screenshot_dest):
            _set_elem(game_elem, "thumbnail", "./images/screenshot.png")
        _set_elem(game_elem, "rating", "1")
        _set_elem(game_elem, "releasedate", "20250101T000000")

        # Write pretty XML
        xml_str = ET.tostring(root, encoding="unicode")
        dom = minidom.parseString(xml_str)
        pretty_xml = dom.toprettyxml(indent="  ")
        lines = [line for line in pretty_xml.split("\n") if line.strip()]
        if lines and lines[0].startswith("<?xml"):
            lines = lines[1:]
        final_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n' + "\n".join(lines)
        )

        with open(gamelist_path, "w", encoding="utf-8") as f:
            f.write(final_xml)

        # Show success
        self.state.confirm_modal.show = True
        self.state.confirm_modal.title = "Link App to Frontend"
        self.state.confirm_modal.message_lines = [
            "Console Utilities linked!",
            "",
            f"Gamelist: {build_folder}/gamelist.xml",
            "",
            "Rescan games in your frontend",
            "to see it.",
        ]
        self.state.confirm_modal.ok_label = "OK"
        self.state.confirm_modal.cancel_label = ""
        self.state.confirm_modal.button_index = 0
        self.state.confirm_modal.context = ""

    def _check_for_updates(self):
        """Check GitHub releases for a newer version."""
        import threading
        from services.update_service import check_for_update
        from constants import APP_VERSION, BUILD_TARGET

        self.state.loading.show = True
        self.state.loading.message = "Checking for updates..."
        self.state.loading.progress = 0

        def _do_check():
            update_available, release_info, error = check_for_update()

            self.state.loading.show = False

            if error and not update_available:
                if error == "Cannot check updates in dev mode":
                    self.state.confirm_modal.show = True
                    self.state.confirm_modal.title = "Check for Updates"
                    self.state.confirm_modal.message_lines = [
                        "Cannot check for updates in dev mode.",
                        "",
                        f"Current: {APP_VERSION} ({BUILD_TARGET})",
                    ]
                    self.state.confirm_modal.ok_label = "OK"
                    self.state.confirm_modal.cancel_label = ""
                    self.state.confirm_modal.button_index = 0
                    self.state.confirm_modal.context = ""
                else:
                    self.state.confirm_modal.show = True
                    self.state.confirm_modal.title = "Update Error"
                    self.state.confirm_modal.message_lines = [error]
                    self.state.confirm_modal.ok_label = "OK"
                    self.state.confirm_modal.cancel_label = ""
                    self.state.confirm_modal.button_index = 0
                    self.state.confirm_modal.context = ""
                return

            if not update_available:
                self.state.confirm_modal.show = True
                self.state.confirm_modal.title = "Up to Date"
                self.state.confirm_modal.message_lines = [
                    "You are running the latest version.",
                    "",
                    f"Current: {APP_VERSION}",
                ]
                self.state.confirm_modal.ok_label = "OK"
                self.state.confirm_modal.cancel_label = ""
                self.state.confirm_modal.button_index = 0
                self.state.confirm_modal.context = ""
                return

            # Update available - show details
            lines = [
                f"New version available: {release_info['tag']}",
                f"Current version: {APP_VERSION}",
                "",
            ]

            can_auto_update = BUILD_TARGET == "pygame" and release_info.get("asset_url")

            if can_auto_update:
                size = release_info.get("asset_size", 0)
                if size > 0:
                    size_str = self._format_bytes(size)
                    lines.append(f"Download size: {size_str}")
                lines.append("")
                lines.append("Update now?")
            else:
                lines.append("Visit GitHub releases to download")
                lines.append("the latest version for your platform.")

            self.state.confirm_modal.show = True
            self.state.confirm_modal.title = "Update Available"
            self.state.confirm_modal.message_lines = lines
            self.state.confirm_modal.button_index = 0
            self.state.confirm_modal.context = "apply_update" if can_auto_update else ""
            self.state.confirm_modal.data = release_info
            if can_auto_update:
                self.state.confirm_modal.ok_label = "Update"
                self.state.confirm_modal.cancel_label = "Later"
            else:
                self.state.confirm_modal.ok_label = "OK"
                self.state.confirm_modal.cancel_label = ""

        thread = threading.Thread(target=_do_check, daemon=True)
        thread.start()

    def _apply_update(self, release_info):
        """Apply a pygame update from release_info."""
        from services.update_service import apply_pygame_update

        self.state.confirm_modal.show = False
        self.state.loading.show = True
        self.state.loading.message = "Downloading update..."
        self.state.loading.progress = 0

        def on_progress(progress, status):
            self.state.loading.progress = int(progress * 100)
            self.state.loading.message = status

        def on_complete():
            self.state.loading.show = False
            self.state.confirm_modal.show = True
            self.state.confirm_modal.title = "Update Complete"
            self.state.confirm_modal.message_lines = [
                f"Updated to {release_info['tag']}.",
                "",
                "Please restart the application",
                "to use the new version.",
            ]
            self.state.confirm_modal.ok_label = "OK"
            self.state.confirm_modal.cancel_label = ""
            self.state.confirm_modal.button_index = 0
            self.state.confirm_modal.context = ""

        def on_error(error):
            self.state.loading.show = False
            self.state.confirm_modal.show = True
            self.state.confirm_modal.title = "Update Failed"
            self.state.confirm_modal.message_lines = [
                "Failed to apply update:",
                str(error),
            ]
            self.state.confirm_modal.ok_label = "OK"
            self.state.confirm_modal.cancel_label = ""
            self.state.confirm_modal.button_index = 0
            self.state.confirm_modal.context = ""

        apply_pygame_update(
            release_info["asset_url"],
            on_progress=on_progress,
            on_complete=on_complete,
            on_error=on_error,
        )

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
        elif action == "extract_rar":
            self._open_folder_browser("extract_rar")
        elif action == "extract_7z":
            self._open_folder_browser("extract_7z")
        elif action == "nsz_converter":
            self._open_folder_browser("nsz_converter")
        elif action == "scrape_images":
            self._show_scraper_wizard(batch_mode=False)
        elif action == "batch_scrape":
            self._show_scraper_wizard(batch_mode=True)
        elif action == "dedupe_games":
            self._show_dedupe_wizard()
        elif action == "clean_filenames":
            self._show_rename_wizard()
        elif action == "ghost_cleaner":
            self._show_ghost_cleaner()

    def _show_dedupe_wizard(self):
        """Show the dedupe games wizard."""
        from state import DedupeWizardState

        # Reset wizard state
        self.state.dedupe_wizard = DedupeWizardState()
        self.state.dedupe_wizard.show = True
        self.state.dedupe_wizard.step = "mode_select"
        self.state.dedupe_wizard.mode_highlighted = 0

    def _open_folder_browser(self, selection_type: str):
        """Open the folder browser modal."""
        self.state.folder_browser.show = True
        self.state.folder_browser.highlighted = 0
        self.state.folder_browser.focus_area = "list"
        self.state.folder_browser.button_index = 0
        # Preserve selected_system_to_add if already set (e.g. add_system_folder)
        if (
            not self.state.folder_browser.selected_system_to_add
            or self.state.folder_browser.selected_system_to_add.get("type")
            != selection_type
        ):
            self.state.folder_browser.selected_system_to_add = {"type": selection_type}

        # Set initial path based on selection type
        if selection_type == "work_dir":
            path = self.settings.get("work_dir", SCRIPT_DIR)
        elif selection_type == "roms_dir":
            path = self.settings.get("roms_dir", SCRIPT_DIR)
        elif selection_type == "archive_json":
            current = self.settings.get("archive_json_path", "")
            path = os.path.dirname(current) if current else SCRIPT_DIR
        elif selection_type == "nsz_keys":
            current = self.settings.get("nsz_keys_path", "")
            path = os.path.dirname(current) if current else SCRIPT_DIR
        elif selection_type == "esde_media_path":
            current = self.settings.get("esde_media_path", "")
            path = current if current else SCRIPT_DIR
        elif selection_type == "esde_gamelists_path":
            current = self.settings.get("esde_gamelists_path", "")
            path = current if current else SCRIPT_DIR
        elif selection_type == "retroarch_thumbnails":
            current = self.settings.get("retroarch_thumbnails_path", "")
            path = current if current else SCRIPT_DIR
        elif selection_type == "scraper_rom_select":
            path = self.settings.get("roms_dir", SCRIPT_DIR)
        elif selection_type == "dedupe_folder":
            path = self.settings.get("roms_dir", SCRIPT_DIR)
        elif selection_type in ("extract_zip", "extract_rar", "extract_7z"):
            path = self.settings.get("work_dir", SCRIPT_DIR)
        elif selection_type == "rename_folder":
            path = self.settings.get("roms_dir", SCRIPT_DIR)
        elif selection_type == "ia_download_folder":
            path = self.state.ia_download_wizard.output_folder or self.settings.get(
                "work_dir", SCRIPT_DIR
            )
        elif selection_type == "add_system_folder":
            path = self.settings.get("roms_dir", SCRIPT_DIR)
        else:
            path = SCRIPT_DIR

        if os.path.exists(path):
            self.state.folder_browser.current_path = path
        else:
            self.state.folder_browser.current_path = SCRIPT_DIR

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
        path = self.settings.get("roms_dir", SCRIPT_DIR)
        if os.path.exists(path):
            self.state.folder_browser.current_path = path
        else:
            self.state.folder_browser.current_path = SCRIPT_DIR

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

        elif item_type in (
            "json_file",
            "keys_file",
            "zip_file",
            "rar_file",
            "7z_file",
            "file",
        ):
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
        elif selection_type == "extract_rar":
            self._extract_rar_file(path)
            return
        elif selection_type == "extract_7z":
            self._extract_7z_file(path)
            return
        elif selection_type == "esde_media_path":
            self.settings["esde_media_path"] = path
            save_settings(self.settings)
        elif selection_type == "esde_gamelists_path":
            self.settings["esde_gamelists_path"] = path
            save_settings(self.settings)
        elif selection_type == "retroarch_thumbnails":
            self.settings["retroarch_thumbnails_path"] = path
            save_settings(self.settings)

        # Close the modal
        self.state.folder_browser.show = False

    def _handle_folder_browser_confirm(self):
        """Handle folder browser Select button (select current folder)."""
        selection_type = self.state.folder_browser.selected_system_to_add.get(
            "type", "folder"
        )
        current_path = self.state.folder_browser.current_path

        # For folder selection types, select the current directory
        if selection_type in (
            "work_dir",
            "roms_dir",
            "custom_folder",
            "esde_media_path",
            "esde_gamelists_path",
            "retroarch_thumbnails",
        ):
            self._complete_folder_browser_selection(current_path, selection_type)
        elif selection_type == "add_system_folder":
            self.state.folder_browser.show = False
            self._complete_add_system(current_path)
        elif selection_type == "ia_collection_folder":
            # Set the folder path for IA collection and continue wizard
            self.state.ia_collection_wizard.folder_name = current_path
            self.state.folder_browser.show = False
            self.state.ia_collection_wizard.step = "formats"
        elif selection_type == "dedupe_folder":
            # Set the folder path for dedupe and start scanning
            self.state.dedupe_wizard.folder_path = current_path
            self.state.folder_browser.show = False
            self._start_dedupe_scan()
        elif selection_type == "rename_folder":
            self.state.rename_wizard.folder_path = current_path
            self.state.folder_browser.show = False
            self._start_rename_scan()
        elif selection_type == "ghost_cleaner_folder":
            self.state.ghost_cleaner_wizard.folder_path = current_path
            self.state.folder_browser.show = False
            self._start_ghost_scan()
        elif selection_type == "ia_download_folder":
            self.state.ia_download_wizard.output_folder = current_path
            self.state.folder_browser.show = False
            self.state.ia_download_wizard.step = "options"
        else:
            # For file selection, user needs to select a file
            pass

    def _handle_add_systems_selection(self):
        """Handle add systems item selection — open folder browser for destination."""
        if not self.state.available_systems:
            return

        if self.state.add_systems_highlighted >= len(self.state.available_systems):
            return

        system = self.state.available_systems[self.state.add_systems_highlighted]

        # Store the selected system and open folder browser to pick destination
        self.state.folder_browser.selected_system_to_add = {
            "type": "add_system_folder",
            "system": system,
        }
        self._open_folder_browser("add_system_folder")

    def _complete_add_system(self, folder_path: str):
        """Complete adding a system after folder selection."""
        system = self.state.folder_browser.selected_system_to_add.get("system", {})
        if not system:
            return

        # Find the parent list_systems entry to inherit config
        parent = next((d for d in self.data if d.get("list_systems") is True), None)

        # Build system config from parent entry, inheriting all relevant fields
        file_formats = parent.get("file_format", [".zip"]) if parent else [".zip"]
        should_unzip = parent.get("should_unzip", True) if parent else True
        extract_contents = parent.get("extract_contents", True) if parent else True
        boxarts_url = parent.get("boxarts", "") if parent else ""
        auth = parent.get("auth") if parent else None

        # Inherit extra fields from parent (download_url, regex, auth config, etc.)
        inherit_keys = {
            "download_url",
            "regex",
            "list_url",
            "list_json_file_location",
            "list_item_id",
            "usa_regex",
            "ignore_extension_filtering",
            "should_filter_usa",
            "should_decompress_nsz",
        }
        extra_fields = {}
        if parent:
            for key in inherit_keys:
                if key in parent:
                    extra_fields[key] = parent[key]

        success = add_system_to_added_systems(
            system_name=system["name"],
            rom_folder=folder_path,
            system_url=system["url"],
            boxarts_url=boxarts_url,
            file_formats=file_formats,
            should_unzip=should_unzip,
            extract_contents=extract_contents,
            auth=auth,
            extra_fields=extra_fields if extra_fields else None,
        )

        if success:
            # Reload data
            self.data = load_main_systems_data(self.settings)
            # Show confirmation
            self.state.confirm_modal.show = True
            self.state.confirm_modal.title = "System Added"
            self.state.confirm_modal.message_lines = [
                f'"{system["name"]}" has been added.',
                "",
                "It will now appear in your systems list.",
            ]
            self.state.confirm_modal.ok_label = "OK"
            self.state.confirm_modal.cancel_label = ""
            self.state.confirm_modal.button_index = 0
            self.state.confirm_modal.context = ""
            # Return to settings
            self.state.mode = "settings"

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

    def _toggle_keyboard_shift(self):
        """Toggle shift state for the currently active keyboard modal."""
        if self.state.show_search_input:
            self.state.search.shift_active = not self.state.search.shift_active
        elif self.state.url_input.show:
            self.state.url_input.shift_active = not self.state.url_input.shift_active
        elif self.state.folder_name_input.show:
            self.state.folder_name_input.shift_active = (
                not self.state.folder_name_input.shift_active
            )
        elif self.state.ia_login.show and self.state.ia_login.step in (
            "email",
            "password",
        ):
            self.state.ia_login.shift_active = not self.state.ia_login.shift_active
        elif (
            self.state.ia_download_wizard.show
            and self.state.ia_download_wizard.step == "url"
        ):
            self.state.ia_download_wizard.shift_active = (
                not self.state.ia_download_wizard.shift_active
            )
        elif self.state.ia_collection_wizard.show and (
            self.state.ia_collection_wizard.step in ("url", "name")
        ):
            self.state.ia_collection_wizard.shift_active = (
                not self.state.ia_collection_wizard.shift_active
            )
        elif self.state.scraper_login.show and (
            self.state.scraper_login.step in ("username", "password", "api_key")
        ):
            self.state.scraper_login.shift_active = (
                not self.state.scraper_login.shift_active
            )

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
                # Jump to buttons - Cancel button (index 1)
                fb.focus_area = "buttons"
                fb.button_index = 1
            elif direction == "right":
                # Jump to buttons - Select button (index 0)
                fb.focus_area = "buttons"
                fb.button_index = 0
        else:  # focus_area == "buttons"
            if direction == "up":
                # Move back to list
                fb.focus_area = "list"
            elif direction == "down":
                # Also move back to list from buttons
                fb.focus_area = "list"
            elif direction == "left":
                if fb.button_index > 0:
                    fb.button_index -= 1
                else:
                    # From leftmost button, go back to list
                    fb.focus_area = "list"
            elif direction == "right":
                if fb.button_index < 1:
                    fb.button_index += 1
                else:
                    # From rightmost button, go back to list
                    fb.focus_area = "list"

    def _navigate_ia_file_select(self, direction: str):
        """Navigate IA download wizard file selection."""
        wizard = self.state.ia_download_wizard
        items = wizard.display_items or wizard.files_list
        max_items = len(items) or 1

        if direction in ("up", "left"):
            if wizard.selected_file_index > 0:
                wizard.selected_file_index -= 1
        elif direction in ("down", "right"):
            if wizard.selected_file_index < max_items - 1:
                wizard.selected_file_index += 1

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
        new_text, is_done, toggle_shift = modal.handle_selection(
            self.state.url_input.cursor_position,
            self.state.url_input.input_text,
            shift_active=self.state.url_input.shift_active,
        )
        if toggle_shift:
            self.state.url_input.shift_active = not self.state.url_input.shift_active
        self.state.url_input.input_text = new_text

        if is_done:
            # URL entry complete - handle the URL
            self.state.url_input.show = False
            # TODO: Process the URL based on context

    def _handle_folder_name_input_selection(self):
        """Handle folder name input keyboard selection."""
        from ui.screens.modals.folder_name_modal import FolderNameModal

        modal = FolderNameModal()
        new_text, is_done, toggle_shift = modal.handle_selection(
            self.state.folder_name_input.cursor_position,
            self.state.folder_name_input.input_text,
            shift_active=self.state.folder_name_input.shift_active,
        )
        if toggle_shift:
            self.state.folder_name_input.shift_active = (
                not self.state.folder_name_input.shift_active
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
        new_text, is_done, toggle_shift = modal.handle_selection(
            self.state.search.cursor_position,
            self.state.search.input_text,
            shift_active=self.state.search.shift_active,
        )
        if toggle_shift:
            self.state.search.shift_active = not self.state.search.shift_active
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
                self.state.text_scroll_offset = 0

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

        # Handle IA download wizard - start button triggers download
        if self.state.ia_download_wizard.show:
            step = self.state.ia_download_wizard.step
            if step == "options":
                self._start_ia_download()
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

        # Handle scraper wizard - start button triggers download on image_select step
        if self.state.scraper_wizard.show:
            step = self.state.scraper_wizard.step
            if step == "image_select":
                wizard = self.state.scraper_wizard
                if wizard.available_videos:
                    wizard.step = "video_select"
                    wizard.video_highlighted = 0
                else:
                    self._start_scraper_download()
                return
            elif step == "video_select":
                self._start_scraper_download()
                return
            elif step == "folder_select":
                # Select current folder for batch mode
                self._select_batch_folder()
                return
            elif step == "rom_list":
                # Continue to batch options
                self.state.scraper_wizard.step = "batch_options"
                self.state.scraper_wizard.image_highlighted = 0
                return
            elif step == "batch_options":
                # Start batch processing
                self._start_batch_scrape()
                return

        # Handle dedupe wizard - don't close on Start button
        if self.state.dedupe_wizard.show:
            return

        # Handle ghost cleaner wizard
        if self.state.ghost_cleaner_wizard.show:
            return

        # Handle rename wizard - Start confirms in manual mode
        if self.state.rename_wizard.show:
            if (
                self.state.rename_wizard.step == "review"
                and self.state.rename_wizard.mode == "manual"
            ):
                self._process_renames()
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
        self.state.scraper_login.show = False
        self.state.scraper_wizard.show = False
        self.state.dedupe_wizard.show = False
        self.state.rename_wizard.show = False
        self.state.ghost_cleaner_wizard.show = False

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
                new_text, is_done, toggle_shift = modal.handle_selection(
                    step,
                    self.state.ia_login.cursor_position,
                    self.state.ia_login.email,
                    shift_active=self.state.ia_login.shift_active,
                )
                if toggle_shift:
                    self.state.ia_login.shift_active = (
                        not self.state.ia_login.shift_active
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
                new_text, is_done, toggle_shift = modal.handle_selection(
                    step,
                    self.state.ia_login.cursor_position,
                    self.state.ia_login.password,
                    shift_active=self.state.ia_login.shift_active,
                )
                if toggle_shift:
                    self.state.ia_login.shift_active = (
                        not self.state.ia_login.shift_active
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
        self.state.ia_download_wizard.current_folder = ""
        self.state.ia_download_wizard.folder_stack = []
        self.state.ia_download_wizard.display_items = []

    def _close_ia_download_wizard(self):
        """Close the IA download wizard modal."""
        self.state.ia_download_wizard.show = False
        self.state.ia_download_wizard.step = "url"
        self.state.ia_download_wizard.url = ""
        self.state.ia_download_wizard.item_id = ""
        self.state.ia_download_wizard.files_list = []
        self.state.ia_download_wizard.current_folder = ""
        self.state.ia_download_wizard.folder_stack = []
        self.state.ia_download_wizard.display_items = []

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
                new_text, is_done, toggle_shift = modal.handle_url_selection(
                    self.state.ia_download_wizard.cursor_position,
                    self.state.ia_download_wizard.url,
                    shift_active=self.state.ia_download_wizard.shift_active,
                )
                if toggle_shift:
                    self.state.ia_download_wizard.shift_active = (
                        not self.state.ia_download_wizard.shift_active
                    )
                self.state.ia_download_wizard.url = new_text
                if is_done and new_text:
                    self._validate_ia_download_item()

        elif step == "file_select":
            wizard = self.state.ia_download_wizard
            if not wizard.display_items:
                return
            idx = wizard.selected_file_index
            if idx >= len(wizard.display_items):
                return
            item = wizard.display_items[idx]
            item_type = item.get("type", "file")

            if item_type == "parent":
                # Navigate up to parent folder
                self._ia_navigate_up()
            elif item_type == "folder":
                # Navigate into folder
                self._ia_navigate_into(item["name"])
            else:
                # File selected, open folder browser
                self._open_folder_browser("ia_download_folder")

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
            self.state.ia_download_wizard.current_folder = ""
            self.state.ia_download_wizard.folder_stack = []
            # Build display items for folder view
            from services.internet_archive import build_display_items

            self.state.ia_download_wizard.display_items = build_display_items(files, "")
            self.state.ia_download_wizard.step = "file_select"

        from threading import Thread

        thread = Thread(target=validate_item, daemon=True)
        thread.start()

    def _start_ia_download(self):
        """Start the IA download."""
        wizard = self.state.ia_download_wizard

        # Get file from display_items if available
        items = wizard.display_items or wizard.files_list
        if not items or wizard.selected_file_index >= len(items):
            return

        file_info = items[wizard.selected_file_index]
        if file_info.get("type") in ("folder", "parent"):
            return  # Can't download a folder entry
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

    def _ia_navigate_into(self, folder_name: str):
        """Navigate into a subfolder in IA download wizard."""
        wizard = self.state.ia_download_wizard
        wizard.folder_stack.append(wizard.current_folder)
        if wizard.current_folder:
            wizard.current_folder += "/" + folder_name
        else:
            wizard.current_folder = folder_name
        wizard.selected_file_index = 0
        from services.internet_archive import build_display_items

        wizard.display_items = build_display_items(
            wizard.files_list, wizard.current_folder
        )

    def _ia_navigate_up(self):
        """Navigate up to parent folder in IA download wizard."""
        wizard = self.state.ia_download_wizard
        if wizard.folder_stack:
            wizard.current_folder = wizard.folder_stack.pop()
        else:
            wizard.current_folder = ""
        wizard.selected_file_index = 0
        from services.internet_archive import build_display_items

        wizard.display_items = build_display_items(
            wizard.files_list, wizard.current_folder
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
                new_text, is_done, toggle_shift = modal.handle_selection(
                    step,
                    self.state.ia_collection_wizard.cursor_position,
                    self.state.ia_collection_wizard.url,
                    shift_active=self.state.ia_collection_wizard.shift_active,
                )
                if toggle_shift:
                    self.state.ia_collection_wizard.shift_active = (
                        not self.state.ia_collection_wizard.shift_active
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
                new_text, is_done, toggle_shift = modal.handle_selection(
                    step,
                    self.state.ia_collection_wizard.cursor_position,
                    self.state.ia_collection_wizard.collection_name,
                    shift_active=self.state.ia_collection_wizard.shift_active,
                )
                if toggle_shift:
                    self.state.ia_collection_wizard.shift_active = (
                        not self.state.ia_collection_wizard.shift_active
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
                    new_text, is_done, toggle_shift = (
                        modal.char_keyboard.handle_selection(
                            wizard.cursor_position,
                            wizard.custom_format_input,
                            char_set="default",
                            shift_active=self.state.ia_collection_wizard.shift_active,
                        )
                    )
                    if toggle_shift:
                        self.state.ia_collection_wizard.shift_active = (
                            not self.state.ia_collection_wizard.shift_active
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

    # ---- Scraper Wizard Handlers ---- #

    def _show_scraper_wizard(self, batch_mode: bool = False):
        """Show the game image scraper wizard modal."""
        wizard = self.state.scraper_wizard
        wizard.show = True
        wizard.batch_mode = batch_mode
        wizard.step = "folder_select" if batch_mode else "rom_select"
        wizard.folder_current_path = self.settings.get("roms_dir", SCRIPT_DIR)
        wizard.folder_items = load_folder_contents(wizard.folder_current_path)
        wizard.folder_highlighted = 0
        wizard.selected_rom_path = ""
        wizard.selected_rom_name = ""
        wizard.search_results = []
        wizard.selected_game_index = 0
        wizard.available_images = []
        wizard.selected_images = set()
        wizard.image_highlighted = 0
        wizard.available_videos = []
        wizard.selected_video_index = -1
        wizard.video_highlighted = 0
        wizard.download_progress = 0.0
        wizard.current_download = ""
        wizard.error_message = ""
        wizard.batch_roms = []
        wizard.batch_current_index = 0
        wizard.batch_auto_select = True
        if (
            self.settings.get("scraper_mixed_images", False)
            and self.settings.get("scraper_provider", "libretro") == "screenscraper"
        ):
            wizard.batch_default_images = ["mixrbv2"]
        else:
            wizard.batch_default_images = ["box-2D", "boxart"]

    def _close_scraper_wizard(self):
        """Close the scraper wizard modal."""
        wizard = self.state.scraper_wizard
        wizard.show = False
        wizard.step = "rom_select"
        wizard.folder_items = []
        wizard.search_results = []
        wizard.available_images = []
        wizard.selected_images = set()
        wizard.available_videos = []
        wizard.selected_video_index = -1
        wizard.batch_roms = []
        self.screen_manager.scraper_wizard_modal.clear_thumbs()

    def _navigate_scraper_wizard(self, direction: str):
        """Handle navigation in scraper wizard."""
        wizard = self.state.scraper_wizard
        step = wizard.step

        if step in ("rom_select", "folder_select"):
            max_items = len(wizard.folder_items) or 1
            if direction in ("up", "left"):
                wizard.folder_highlighted = max(0, wizard.folder_highlighted - 1)
            elif direction in ("down", "right"):
                wizard.folder_highlighted = min(
                    max_items - 1, wizard.folder_highlighted + 1
                )

        elif step == "game_select":
            max_items = len(wizard.search_results) or 1
            if direction in ("up", "left"):
                wizard.selected_game_index = max(0, wizard.selected_game_index - 1)
            elif direction in ("down", "right"):
                wizard.selected_game_index = min(
                    max_items - 1, wizard.selected_game_index + 1
                )

        elif step == "image_select":
            max_items = len(wizard.available_images) or 1
            if direction in ("up", "left"):
                wizard.image_highlighted = max(0, wizard.image_highlighted - 1)
            elif direction in ("down", "right"):
                wizard.image_highlighted = min(
                    max_items - 1, wizard.image_highlighted + 1
                )

        elif step == "video_select":
            # Items: "No Video" + available videos
            max_items = 1 + len(wizard.available_videos)
            if direction in ("up", "left"):
                wizard.video_highlighted = max(0, wizard.video_highlighted - 1)
            elif direction in ("down", "right"):
                wizard.video_highlighted = min(
                    max_items - 1, wizard.video_highlighted + 1
                )

        elif step == "rom_list":
            max_items = len(wizard.batch_roms) or 1
            if direction in ("up", "left"):
                wizard.batch_current_index = max(0, wizard.batch_current_index - 1)
            elif direction in ("down", "right"):
                wizard.batch_current_index = min(
                    max_items - 1, wizard.batch_current_index + 1
                )

        elif step == "batch_options":
            mixed = (
                self.settings.get("scraper_mixed_images", False)
                and self.settings.get("scraper_provider", "libretro") == "screenscraper"
            )
            # Auto-select + image types + Download Video toggle
            max_items = (8 if mixed else 6) + 1
            if direction in ("up", "left"):
                wizard.image_highlighted = max(0, wizard.image_highlighted - 1)
            elif direction in ("down", "right"):
                wizard.image_highlighted = min(
                    max_items - 1, wizard.image_highlighted + 1
                )

    def _handle_scraper_wizard_selection(self):
        """Handle selection in scraper wizard."""
        wizard = self.state.scraper_wizard
        step = wizard.step

        if step == "rom_select":
            self._handle_scraper_rom_selection()

        elif step == "folder_select":
            self._handle_scraper_folder_selection()

        elif step == "game_select":
            if wizard.search_results:
                self._fetch_scraper_images()

        elif step == "image_select":
            # Toggle image selection
            if wizard.image_highlighted in wizard.selected_images:
                wizard.selected_images.discard(wizard.image_highlighted)
            else:
                wizard.selected_images.add(wizard.image_highlighted)

        elif step == "video_select":
            # Select/deselect video (radio-style: 0=no video, 1+=video index)
            if wizard.video_highlighted == 0:
                wizard.selected_video_index = -1  # No video
            else:
                idx = wizard.video_highlighted - 1
                if wizard.selected_video_index == idx:
                    wizard.selected_video_index = -1  # Deselect
                else:
                    wizard.selected_video_index = idx

        elif step == "rom_list":
            # Toggle ROM skip status
            if wizard.batch_current_index < len(wizard.batch_roms):
                rom = wizard.batch_roms[wizard.batch_current_index]
                if rom.get("status") == "skipped":
                    rom["status"] = "pending"
                else:
                    rom["status"] = "skipped"

        elif step == "batch_options":
            self._handle_batch_options_selection()

        elif step in ("complete", "batch_complete"):
            self._close_scraper_wizard()

        elif step == "error":
            # Go back to rom_select to retry
            wizard.step = "folder_select" if wizard.batch_mode else "rom_select"
            wizard.error_message = ""

    def _handle_scraper_rom_selection(self):
        """Handle ROM file selection in scraper wizard."""
        wizard = self.state.scraper_wizard
        items = wizard.folder_items
        highlighted = wizard.folder_highlighted

        if highlighted >= len(items):
            return

        item = items[highlighted]
        item_type = item.get("type", "")
        item_path = item.get("path", "")

        if item_type == "parent":
            wizard.folder_current_path = item_path
            wizard.folder_items = load_folder_contents(item_path)
            wizard.folder_highlighted = 0

        elif item_type == "folder":
            wizard.folder_current_path = item_path
            wizard.folder_items = load_folder_contents(item_path)
            wizard.folder_highlighted = 0

        elif item_type in ("file", "zip_file"):
            # ROM file selected, start searching
            wizard.selected_rom_path = item_path
            wizard.selected_rom_name = item.get("name", os.path.basename(item_path))
            self._search_scraper_game()

    def _handle_scraper_folder_selection(self):
        """Handle folder selection in batch mode."""
        wizard = self.state.scraper_wizard
        items = wizard.folder_items
        highlighted = wizard.folder_highlighted

        if highlighted >= len(items):
            return

        item = items[highlighted]
        item_type = item.get("type", "")
        item_path = item.get("path", "")

        if item_type == "parent":
            wizard.folder_current_path = item_path
            wizard.folder_items = load_folder_contents(item_path)
            wizard.folder_highlighted = 0

        elif item_type == "folder":
            wizard.folder_current_path = item_path
            wizard.folder_items = load_folder_contents(item_path)
            wizard.folder_highlighted = 0

    def _select_batch_folder(self):
        """Select current folder for batch scraping."""
        wizard = self.state.scraper_wizard

        # Scan folder for ROM files
        rom_extensions = {
            ".nes",
            ".sfc",
            ".smc",
            ".gba",
            ".gbc",
            ".gb",
            ".n64",
            ".z64",
            ".nds",
            ".3ds",
            ".iso",
            ".bin",
            ".cue",
            ".chd",
            ".pbp",
            ".zip",
            ".7z",
            ".rar",
            ".nsz",
            ".nsp",
            ".xci",
        }

        roms = []
        try:
            for item in os.listdir(wizard.folder_current_path):
                item_path = os.path.join(wizard.folder_current_path, item)
                if os.path.isfile(item_path):
                    ext = os.path.splitext(item)[1].lower()
                    if ext in rom_extensions:
                        roms.append(
                            {
                                "name": item,
                                "path": item_path,
                                "status": "pending",
                            }
                        )
        except Exception:
            pass

        if not roms:
            wizard.error_message = "No ROM files found in folder"
            wizard.step = "error"
            return

        wizard.batch_roms = roms
        wizard.batch_current_index = 0
        wizard.step = "rom_list"

    def _handle_batch_options_selection(self):
        """Handle selection in batch options step."""
        wizard = self.state.scraper_wizard
        highlighted = wizard.image_highlighted

        if highlighted == 0:
            # Toggle auto-select
            wizard.batch_auto_select = not wizard.batch_auto_select
        else:
            # Toggle image type or video
            if (
                self.settings.get("scraper_mixed_images", False)
                and self.settings.get("scraper_provider", "libretro") == "screenscraper"
            ):
                all_types = [
                    "box-2D",
                    "boxart",
                    "mixrbv1",
                    "mixrbv2",
                    "screenshot",
                    "wheel",
                    "fanart",
                ]
            else:
                all_types = ["box-2D", "boxart", "screenshot", "wheel", "fanart"]

            img_index = highlighted - 1
            if img_index < len(all_types):
                img_type = all_types[img_index]
                if img_type in wizard.batch_default_images:
                    wizard.batch_default_images.remove(img_type)
                else:
                    wizard.batch_default_images.append(img_type)
            else:
                # Download Video toggle
                self.state.scraper_queue.download_video = (
                    not self.state.scraper_queue.download_video
                )

    def _search_scraper_game(self):
        """Search for game info using scraper provider."""
        wizard = self.state.scraper_wizard
        wizard.step = "searching"

        from services.scraper_service import get_scraper_service

        # Set system context from ROM path for Libretro
        rom_dir = os.path.basename(os.path.dirname(wizard.selected_rom_path))
        self.settings["current_system_folder"] = rom_dir

        service = get_scraper_service(self.settings)
        service.reset_provider()

        rom_path = wizard.selected_rom_path
        game_name = service.extract_game_name(rom_path)
        wizard.selected_rom_name = game_name

        def search():
            success, results, error = service.search_game(game_name, rom_path=rom_path)

            if not success:
                wizard.step = "error"
                wizard.error_message = error or "Search failed"
                return

            if not results:
                wizard.step = "error"
                wizard.error_message = f"No results for: {game_name}"
                return

            # Convert results to dict format for display
            wizard.search_results = [
                {
                    "id": r.id,
                    "name": r.name,
                    "platform": r.platform,
                    "release_date": r.release_date,
                    "description": r.description,
                }
                for r in results
            ]
            wizard.selected_game_index = 0
            wizard.step = "game_select"

        from threading import Thread

        thread = Thread(target=search, daemon=True)
        thread.start()

    def _fetch_scraper_images(self):
        """Fetch available images for selected game."""
        wizard = self.state.scraper_wizard
        wizard.step = "searching"

        if not wizard.search_results or wizard.selected_game_index >= len(
            wizard.search_results
        ):
            return

        game = wizard.search_results[wizard.selected_game_index]
        game_id = game.get("id", "")

        from services.scraper_service import get_scraper_service

        service = get_scraper_service(self.settings)

        def fetch():
            success, images, error = service.get_game_images(game_id)

            if not success:
                wizard.step = "error"
                wizard.error_message = error or "Failed to fetch images"
                return

            if not images:
                wizard.step = "error"
                wizard.error_message = "No images available"
                return

            # Convert images to dict format for display
            wizard.available_images = [
                {
                    "type": img.type,
                    "url": img.url,
                    "region": img.region,
                    "label": service.provider.get_image_type_label(img.type),
                }
                for img in images
            ]
            # Pre-select all images
            wizard.selected_images = set(range(len(wizard.available_images)))
            wizard.image_highlighted = 0

            # Also fetch videos if provider supports them
            wizard.available_videos = []
            wizard.selected_video_index = -1
            v_success, videos, _ = service.get_game_videos(game_id)
            if v_success and videos:
                wizard.available_videos = [
                    {
                        "url": v.url,
                        "region": v.region,
                        "format": v.format,
                        "normalized": v.normalized,
                        "label": "Video (Normalized)" if v.normalized else "Video",
                    }
                    for v in videos
                ]

            wizard.step = "image_select"

        from threading import Thread

        thread = Thread(target=fetch, daemon=True)
        thread.start()

    def _start_scraper_download(self):
        """Start downloading selected images and optional video."""
        wizard = self.state.scraper_wizard

        if not wizard.selected_images or not wizard.available_images:
            return

        wizard.step = "downloading"
        wizard.download_progress = 0.0

        # Get selected images
        selected = [
            wizard.available_images[i]
            for i in sorted(wizard.selected_images)
            if i < len(wizard.available_images)
        ]

        # Get selected video (if any)
        selected_video = None
        if wizard.selected_video_index >= 0 and wizard.selected_video_index < len(
            wizard.available_videos
        ):
            selected_video = wizard.available_videos[wizard.selected_video_index]

        # Get game info for metadata
        game_info = {}
        if wizard.search_results and wizard.selected_game_index < len(
            wizard.search_results
        ):
            game_info = wizard.search_results[wizard.selected_game_index]

        from services.scraper_service import get_scraper_service
        from services.scraper_providers.base_provider import GameImage, GameVideo
        from services.metadata_writer import get_metadata_writer

        service = get_scraper_service(self.settings)

        def download():
            # Convert dict images back to GameImage objects
            images = [
                GameImage(
                    type=img["type"],
                    url=img["url"],
                    region=img.get("region", ""),
                )
                for img in selected
            ]

            total_items = len(images) + (1 if selected_video else 0)

            def progress_callback(current, total, current_name):
                progress = current / total_items if total_items > 0 else 0
                wizard.download_progress = min(progress, 1.0)
                wizard.current_download = current_name

            success, paths, error = service.download_images(
                images, wizard.selected_rom_path, progress_callback
            )

            if not success:
                wizard.step = "error"
                wizard.error_message = error or "Download failed"
                return

            # Download video if selected
            if selected_video:
                wizard.current_download = "Video"
                video = GameVideo(
                    url=selected_video["url"],
                    region=selected_video.get("region", ""),
                    format=selected_video.get("format", "mp4"),
                    normalized=selected_video.get("normalized", False),
                )
                video_path = service.get_video_output_path(
                    wizard.selected_rom_path, video.format
                )
                if video_path:
                    v_success, v_error = service.download_video(video, video_path)
                    if v_success:
                        paths.append(video_path)
                    else:
                        print(f"Failed to download video: {v_error}")

            wizard.download_progress = 1.0

            # Update metadata
            wizard.step = "updating_metadata"
            writer = get_metadata_writer(self.settings)
            writer.update_metadata(wizard.selected_rom_path, game_info, paths)

            wizard.step = "complete"

        from threading import Thread

        thread = Thread(target=download, daemon=True)
        thread.start()

    def _start_batch_scrape(self):
        """Start background batch scraping and close wizard."""
        wizard = self.state.scraper_wizard

        # Build ROM list from wizard state (filter out skipped)
        roms = [
            {"name": r["name"], "path": r["path"]}
            for r in wizard.batch_roms
            if r.get("status") != "skipped"
        ]

        if not roms:
            return

        # Start background scraping via ScraperManager
        self.scraper_manager.start_batch(
            folder_path=wizard.folder_current_path,
            roms=roms,
            default_images=list(wizard.batch_default_images),
            auto_select=wizard.batch_auto_select,
            download_video=self.state.scraper_queue.download_video,
        )

        # Close wizard and navigate to scraper downloads screen
        self._close_scraper_wizard()
        self.state.mode = "scraper_downloads"
        self.state.scraper_queue.highlighted = 0

    def _show_screenscraper_login(self):
        """Show ScreenScraper login modal."""
        self.state.scraper_login.show = True
        self.state.scraper_login.provider = "screenscraper"
        self.state.scraper_login.step = "username"
        self.state.scraper_login.username = self.settings.get(
            "screenscraper_username", ""
        )
        self.state.scraper_login.password = ""
        self.state.scraper_login.cursor_position = 0
        self.state.scraper_login.error_message = ""

    def _show_thegamesdb_api_key_input(self):
        """Show TheGamesDB API key input modal."""
        self.state.scraper_login.show = True
        self.state.scraper_login.provider = "thegamesdb"
        self.state.scraper_login.step = "api_key"
        self.state.scraper_login.api_key = self.settings.get("thegamesdb_api_key", "")
        self.state.scraper_login.cursor_position = 0
        self.state.scraper_login.error_message = ""

    def _show_rawg_api_key_input(self):
        """Show RAWG API key input modal."""
        self.state.scraper_login.show = True
        self.state.scraper_login.provider = "rawg"
        self.state.scraper_login.step = "api_key"
        self.state.scraper_login.api_key = self.settings.get("rawg_api_key", "")
        self.state.scraper_login.cursor_position = 0
        self.state.scraper_login.error_message = ""

    def _show_igdb_login(self):
        """Show IGDB login modal (Client ID + Client Secret)."""
        self.state.scraper_login.show = True
        self.state.scraper_login.provider = "igdb"
        self.state.scraper_login.step = "username"
        self.state.scraper_login.username = self.settings.get("igdb_client_id", "")
        self.state.scraper_login.password = ""
        self.state.scraper_login.cursor_position = 0
        self.state.scraper_login.error_message = ""

    def _close_scraper_login(self):
        """Close the scraper login modal."""
        self.state.scraper_login.show = False
        self.state.scraper_login.step = "username"
        self.state.scraper_login.username = ""
        self.state.scraper_login.password = ""
        self.state.scraper_login.api_key = ""
        self.state.scraper_login.cursor_position = 0
        self.state.scraper_login.error_message = ""

    def _handle_scraper_login_selection(self):
        """Handle selection in scraper login modal."""
        login = self.state.scraper_login
        step = login.step
        provider = login.provider

        if provider == "screenscraper":
            if step == "username":
                if self.state.input_mode == "keyboard":
                    # Keyboard mode - Enter pressed, move to password
                    if login.username:
                        login.step = "password"
                        login.cursor_position = 0
                else:
                    # Gamepad/touch mode - handle on-screen keyboard
                    from ui.screens.modals.scraper_login_modal import ScraperLoginModal

                    modal = ScraperLoginModal()
                    new_text, is_done, toggle_shift = modal.handle_selection(
                        provider,
                        step,
                        login.cursor_position,
                        login.username,
                        shift_active=self.state.scraper_login.shift_active,
                    )
                    if toggle_shift:
                        self.state.scraper_login.shift_active = (
                            not self.state.scraper_login.shift_active
                        )
                    login.username = new_text
                    if is_done and new_text:
                        login.step = "password"
                        login.cursor_position = 0

            elif step == "password":
                if self.state.input_mode == "keyboard":
                    # Keyboard mode - Enter pressed, test credentials
                    if login.password:
                        self._test_screenscraper_credentials()
                else:
                    from ui.screens.modals.scraper_login_modal import ScraperLoginModal

                    modal = ScraperLoginModal()
                    new_text, is_done, toggle_shift = modal.handle_selection(
                        provider,
                        step,
                        login.cursor_position,
                        login.password,
                        shift_active=self.state.scraper_login.shift_active,
                    )
                    if toggle_shift:
                        self.state.scraper_login.shift_active = (
                            not self.state.scraper_login.shift_active
                        )
                    login.password = new_text
                    if is_done and new_text:
                        self._test_screenscraper_credentials()

            elif step == "complete":
                self._close_scraper_login()

            elif step == "error":
                # Go back to username step to retry
                login.step = "username"
                login.password = ""
                login.cursor_position = 0
                login.error_message = ""

        elif provider == "thegamesdb":
            if step == "api_key":
                if self.state.input_mode == "keyboard":
                    if login.api_key:
                        self._test_thegamesdb_credentials()
                else:
                    from ui.screens.modals.scraper_login_modal import ScraperLoginModal

                    modal = ScraperLoginModal()
                    new_text, is_done, toggle_shift = modal.handle_selection(
                        provider,
                        step,
                        login.cursor_position,
                        login.api_key,
                        shift_active=self.state.scraper_login.shift_active,
                    )
                    if toggle_shift:
                        self.state.scraper_login.shift_active = (
                            not self.state.scraper_login.shift_active
                        )
                    login.api_key = new_text
                    if is_done and new_text:
                        self._test_thegamesdb_credentials()

            elif step == "complete":
                self._close_scraper_login()

            elif step == "error":
                login.step = "api_key"
                login.cursor_position = 0
                login.error_message = ""

        elif provider == "rawg":
            if step == "api_key":
                if self.state.input_mode == "keyboard":
                    if login.api_key:
                        self._test_rawg_credentials()
                else:
                    from ui.screens.modals.scraper_login_modal import ScraperLoginModal

                    modal = ScraperLoginModal()
                    new_text, is_done, toggle_shift = modal.handle_selection(
                        provider,
                        step,
                        login.cursor_position,
                        login.api_key,
                        shift_active=self.state.scraper_login.shift_active,
                    )
                    if toggle_shift:
                        self.state.scraper_login.shift_active = (
                            not self.state.scraper_login.shift_active
                        )
                    login.api_key = new_text
                    if is_done and new_text:
                        self._test_rawg_credentials()

            elif step == "complete":
                self._close_scraper_login()

            elif step == "error":
                login.step = "api_key"
                login.cursor_position = 0
                login.error_message = ""

        elif provider == "igdb":
            if step == "username":
                if self.state.input_mode == "keyboard":
                    if login.username:
                        login.step = "password"
                        login.cursor_position = 0
                else:
                    from ui.screens.modals.scraper_login_modal import (
                        ScraperLoginModal,
                    )

                    modal = ScraperLoginModal()
                    new_text, is_done, toggle_shift = modal.handle_selection(
                        provider,
                        step,
                        login.cursor_position,
                        login.username,
                        shift_active=login.shift_active,
                    )
                    if toggle_shift:
                        login.shift_active = not login.shift_active
                    login.username = new_text
                    if is_done and new_text:
                        login.step = "password"
                        login.cursor_position = 0

            elif step == "password":
                if self.state.input_mode == "keyboard":
                    if login.password:
                        self._test_igdb_credentials()
                else:
                    from ui.screens.modals.scraper_login_modal import (
                        ScraperLoginModal,
                    )

                    modal = ScraperLoginModal()
                    new_text, is_done, toggle_shift = modal.handle_selection(
                        provider,
                        step,
                        login.cursor_position,
                        login.password,
                        shift_active=login.shift_active,
                    )
                    if toggle_shift:
                        login.shift_active = not login.shift_active
                    login.password = new_text
                    if is_done and new_text:
                        self._test_igdb_credentials()

            elif step == "complete":
                self._close_scraper_login()

            elif step == "error":
                login.step = "username"
                login.password = ""
                login.cursor_position = 0
                login.error_message = ""

    def _test_screenscraper_credentials(self):
        """Test ScreenScraper credentials in background thread."""
        import base64

        login = self.state.scraper_login
        login.step = "testing"

        username = login.username
        password = login.password

        def test_credentials():
            from services.scraper_providers.screenscraper import ScreenScraperProvider

            encoded_password = base64.b64encode(password.encode()).decode()
            provider = ScreenScraperProvider(
                username=username,
                password=encoded_password,
            )

            success, error = provider.test_credentials()

            if success:
                # Save credentials
                self.settings["screenscraper_username"] = username
                self.settings["screenscraper_password"] = encoded_password
                save_settings(self.settings)
                login.step = "complete"
            else:
                login.step = "error"
                login.error_message = error or "Invalid credentials"

        from threading import Thread

        thread = Thread(target=test_credentials, daemon=True)
        thread.start()

    def _test_thegamesdb_credentials(self):
        """Test TheGamesDB API key in background thread."""
        login = self.state.scraper_login
        login.step = "testing"

        api_key = login.api_key

        def test_credentials():
            from services.scraper_providers.thegamesdb import TheGamesDBProvider

            provider = TheGamesDBProvider(api_key=api_key)

            success, results, error = provider.search_game("Mario")

            if success:
                # Save API key
                self.settings["thegamesdb_api_key"] = api_key
                save_settings(self.settings)
                login.step = "complete"
            else:
                login.step = "error"
                login.error_message = error or "Invalid API key"

        from threading import Thread

        thread = Thread(target=test_credentials, daemon=True)
        thread.start()

    def _test_rawg_credentials(self):
        """Test RAWG API key in background thread."""
        login = self.state.scraper_login
        login.step = "testing"

        api_key = login.api_key

        def test_credentials():
            from services.scraper_providers.rawg import RAWGProvider

            provider = RAWGProvider(api_key=api_key)

            success, results, error = provider.search_game("Mario")

            if success:
                # Save API key
                self.settings["rawg_api_key"] = api_key
                save_settings(self.settings)
                login.step = "complete"
            else:
                login.step = "error"
                login.error_message = error or "Invalid API key"

        from threading import Thread

        thread = Thread(target=test_credentials, daemon=True)
        thread.start()

    def _test_igdb_credentials(self):
        """Test IGDB credentials in background thread."""
        login = self.state.scraper_login
        login.step = "testing"

        client_id = login.username
        client_secret = login.password

        def test_credentials():
            from services.scraper_providers.igdb import IGDBProvider

            provider = IGDBProvider(
                client_id=client_id,
                client_secret=client_secret,
            )

            success, results, error = provider.search_game("Mario")

            if success:
                self.settings["igdb_client_id"] = client_id
                self.settings["igdb_client_secret"] = client_secret
                save_settings(self.settings)
                login.step = "complete"
            else:
                login.step = "error"
                login.error_message = error or "Invalid credentials"

        from threading import Thread

        thread = Thread(target=test_credentials, daemon=True)
        thread.start()

    # ========== Dedupe Wizard Methods ========== #

    def _close_dedupe_wizard(self):
        """Close the dedupe wizard modal."""
        from state import DedupeWizardState

        self.state.dedupe_wizard = DedupeWizardState()

    def _show_rename_wizard(self):
        """Show the file rename wizard."""
        from state import RenameWizardState

        self.state.rename_wizard = RenameWizardState()
        self.state.rename_wizard.show = True
        self.state.rename_wizard.step = "mode_select"
        self.state.rename_wizard.mode_highlighted = 0

    def _close_rename_wizard(self):
        """Close the file rename wizard."""
        from state import RenameWizardState

        self.state.rename_wizard = RenameWizardState()

    def _navigate_rename_wizard(self, direction: str):
        """Handle navigation in rename wizard."""
        wizard = self.state.rename_wizard
        step = wizard.step

        if step == "scanning":
            return

        if step == "mode_select":
            if direction in ("up", "left"):
                wizard.mode_highlighted = max(0, wizard.mode_highlighted - 1)
            elif direction in ("down", "right"):
                wizard.mode_highlighted = min(1, wizard.mode_highlighted + 1)

        elif step == "review":
            max_items = len(wizard.rename_items) or 1
            if direction in ("left", "up"):
                wizard.current_item_index = max(0, wizard.current_item_index - 1)
            elif direction in ("right", "down"):
                wizard.current_item_index = min(
                    max_items - 1,
                    wizard.current_item_index + 1,
                )

    def _handle_rename_wizard_selection(self):
        """Handle selection in rename wizard."""
        wizard = self.state.rename_wizard
        step = wizard.step

        if step == "scanning":
            return

        if step == "mode_select":
            wizard.mode = "automatic" if wizard.mode_highlighted == 0 else "manual"
            self._open_folder_browser("rename_folder")

        elif step == "review":
            if wizard.mode == "automatic":
                self._process_renames()
            else:
                # Toggle current item selected state
                if wizard.rename_items:
                    idx = wizard.current_item_index
                    item = wizard.rename_items[idx]
                    item["selected"] = not item.get("selected", True)

        elif step in (
            "complete",
            "no_changes",
            "error",
        ):
            self._close_rename_wizard()

    def _start_rename_scan(self):
        """Start scanning for files to rename."""
        wizard = self.state.rename_wizard
        wizard.step = "scanning"
        wizard.scan_progress = 0.0

        folder_path = wizard.folder_path

        from threading import Thread
        from services.dedupe_service import (
            generate_clean_names,
        )

        def scan():
            def progress_callback(current, total):
                wizard.files_scanned = current
                wizard.total_files = total
                if total > 0:
                    wizard.scan_progress = current / total

            try:
                items = generate_clean_names(folder_path, progress_callback)
                wizard.rename_items = items
                wizard.current_item_index = 0

                if items:
                    wizard.step = "review"
                else:
                    wizard.step = "no_changes"
            except Exception as e:
                wizard.step = "error"
                wizard.error_message = str(e)

        thread = Thread(target=scan, daemon=True)
        thread.start()

    def _process_renames(self):
        """Process file renames."""
        wizard = self.state.rename_wizard
        wizard.step = "processing"

        items_to_rename = [
            item for item in wizard.rename_items if item.get("selected", True)
        ]

        from threading import Thread

        def process():
            renamed = 0
            total = len(items_to_rename)

            for i, item in enumerate(items_to_rename):
                try:
                    old_path = item["path"]
                    new_path = os.path.join(
                        os.path.dirname(old_path),
                        item["new_name"],
                    )

                    if not os.path.exists(new_path):
                        os.rename(old_path, new_path)
                        renamed += 1

                    if total > 0:
                        wizard.process_progress = (i + 1) / total
                except OSError:
                    pass

            wizard.files_renamed = renamed
            wizard.step = "complete"

        thread = Thread(target=process, daemon=True)
        thread.start()

    def _navigate_dedupe_wizard(self, direction: str):
        """Handle navigation in dedupe wizard."""
        wizard = self.state.dedupe_wizard
        step = wizard.step

        if step == "scanning":
            # Ignore navigation during scanning
            return

        if step == "mode_select":
            # Two modes: safe (0) and manual (1)
            if direction in ("up", "left"):
                wizard.mode_highlighted = max(0, wizard.mode_highlighted - 1)
            elif direction in ("down", "right"):
                wizard.mode_highlighted = min(1, wizard.mode_highlighted + 1)

        elif step == "review":
            if wizard.mode == "safe":
                # In safe mode, left/right navigates between groups
                max_groups = len(wizard.duplicate_groups) or 1
                if direction == "left":
                    wizard.current_group_index = max(0, wizard.current_group_index - 1)
                elif direction == "right":
                    wizard.current_group_index = min(
                        max_groups - 1, wizard.current_group_index + 1
                    )
            else:
                # In manual mode, up/down selects which file to keep
                if wizard.duplicate_groups:
                    current_group = wizard.duplicate_groups[wizard.current_group_index]
                    max_items = len(current_group) or 1
                    max_groups = len(wizard.duplicate_groups) or 1

                    if direction in ("up",):
                        wizard.selected_to_keep = max(0, wizard.selected_to_keep - 1)
                    elif direction in ("down",):
                        wizard.selected_to_keep = min(
                            max_items - 1, wizard.selected_to_keep + 1
                        )
                    elif direction == "left":
                        wizard.current_group_index = max(
                            0, wizard.current_group_index - 1
                        )
                        wizard.selected_to_keep = 0
                    elif direction == "right":
                        wizard.current_group_index = min(
                            max_groups - 1, wizard.current_group_index + 1
                        )
                        wizard.selected_to_keep = 0

    def _handle_dedupe_wizard_selection(self):
        """Handle selection in dedupe wizard."""
        wizard = self.state.dedupe_wizard
        step = wizard.step

        if step == "scanning":
            # Ignore input during scanning
            return

        if step == "mode_select":
            # Set mode based on selection
            wizard.mode = "safe" if wizard.mode_highlighted == 0 else "manual"
            # Open folder browser to select folder to scan
            self._open_folder_browser("dedupe_folder")

        elif step == "review":
            if wizard.mode == "safe":
                # Confirm current group and move to next, or process all confirmed
                self._confirm_dedupe_safe_selection()
            else:
                # Confirm current selection and move to next group or process
                self._confirm_dedupe_manual_selection()

        elif step in ("complete", "no_duplicates", "error"):
            self._close_dedupe_wizard()

    def _start_dedupe_scan(self):
        """Start scanning for duplicates (called when Start button pressed)."""
        wizard = self.state.dedupe_wizard
        wizard.step = "scanning"
        wizard.scan_progress = 0.0
        wizard.files_scanned = 0
        wizard.total_files = 0

        folder_path = wizard.folder_path
        mode = wizard.mode

        from threading import Thread
        from services.dedupe_service import (
            scan_folder_for_games,
            find_duplicates_safe,
            find_duplicates_manual,
        )

        def scan():
            def progress_callback(current, total):
                wizard.files_scanned = current
                wizard.total_files = total
                wizard.scan_progress = current / total if total > 0 else 0

            try:
                games = scan_folder_for_games(folder_path, progress_callback)

                if mode == "safe":
                    duplicates = find_duplicates_safe(games)
                else:
                    duplicates = find_duplicates_manual(games)

                wizard.duplicate_groups = duplicates
                wizard.current_group_index = 0
                wizard.selected_to_keep = 0

                if duplicates:
                    wizard.step = "review"
                else:
                    wizard.step = "no_duplicates"

            except Exception as e:
                wizard.step = "error"
                wizard.error_message = str(e)

        thread = Thread(target=scan, daemon=True)
        thread.start()

    def _confirm_dedupe_safe_selection(self):
        """Confirm current safe-mode group and advance or process all."""
        wizard = self.state.dedupe_wizard

        if not wizard.duplicate_groups:
            return

        idx = wizard.current_group_index

        # Record the confirmation for this group (keep first = largest)
        current_group = wizard.duplicate_groups[idx]
        keep_file = current_group[0]
        remove_files = current_group[1:]

        # Use dict keyed by group index to avoid duplicate confirmations
        wizard.confirmed_groups[idx] = {
            "keep": keep_file["path"],
            "remove": [f["path"] for f in remove_files],
        }

        # Move to next unconfirmed group or process all
        if wizard.current_group_index < len(wizard.duplicate_groups) - 1:
            wizard.current_group_index += 1
        else:
            # All groups confirmed, start processing
            self._process_dedupe_confirmed()

    def _confirm_dedupe_manual_selection(self):
        """Confirm manual selection and move to next group or process."""
        wizard = self.state.dedupe_wizard

        if not wizard.duplicate_groups:
            return

        idx = wizard.current_group_index
        current_group = wizard.duplicate_groups[idx]

        # Record which file to keep and which to remove
        keep_file = current_group[wizard.selected_to_keep]
        remove_files = [
            f for i, f in enumerate(current_group) if i != wizard.selected_to_keep
        ]

        # Use dict keyed by group index to avoid duplicate confirmations
        wizard.confirmed_groups[idx] = {
            "keep": keep_file["path"],
            "remove": [f["path"] for f in remove_files],
        }

        # Move to next group or start processing
        if wizard.current_group_index < len(wizard.duplicate_groups) - 1:
            wizard.current_group_index += 1
            wizard.selected_to_keep = 0
        else:
            # All groups confirmed, start processing
            self._process_dedupe_confirmed()

    def _process_dedupe_confirmed(self):
        """Process all confirmed dedupe selections (both safe and manual modes)."""
        wizard = self.state.dedupe_wizard
        wizard.step = "processing"
        wizard.process_progress = 0.0

        # Collect all files to delete from confirmed groups (dict values)
        files_to_delete = []
        for group_decision in wizard.confirmed_groups.values():
            files_to_delete.extend(group_decision["remove"])

        base_folder = wizard.folder_path

        from threading import Thread
        from services.dedupe_service import delete_files

        def process():
            def progress_callback(current, total, bytes_freed):
                wizard.process_progress = current / total if total > 0 else 0
                wizard.space_freed = bytes_freed

            files_deleted, bytes_freed = delete_files(
                files_to_delete, progress_callback, base_folder=base_folder
            )
            wizard.files_removed = files_deleted
            wizard.space_freed = bytes_freed
            wizard.step = "complete"

        thread = Thread(target=process, daemon=True)
        thread.start()

    # ========== Ghost File Cleaner Methods ========== #

    def _show_ghost_cleaner(self):
        """Show the ghost file cleaner wizard."""
        from state import GhostCleanerWizardState

        self.state.ghost_cleaner_wizard = GhostCleanerWizardState()
        self.state.ghost_cleaner_wizard.show = True
        # Open folder browser to select folder (default to roms_dir)
        self._open_folder_browser("ghost_cleaner_folder")

    def _close_ghost_cleaner(self):
        """Close the ghost file cleaner wizard."""
        from state import GhostCleanerWizardState

        self.state.ghost_cleaner_wizard = GhostCleanerWizardState()

    def _handle_ghost_cleaner_selection(self):
        """Handle selection in ghost cleaner wizard."""
        wizard = self.state.ghost_cleaner_wizard
        step = wizard.step

        if step == "scanning":
            return

        if step == "review":
            # User confirmed - start cleaning
            self._start_ghost_clean()

        elif step in ("complete", "no_ghosts", "error"):
            self._close_ghost_cleaner()

    def _start_ghost_scan(self):
        """Start scanning for ghost files."""
        wizard = self.state.ghost_cleaner_wizard
        wizard.step = "scanning"
        wizard.scan_progress = 0.0
        wizard.files_scanned = 0
        wizard.total_files = 0

        folder_path = wizard.folder_path

        from threading import Thread
        from services.ghost_cleaner import scan_ghost_files

        def scan():
            def progress_callback(current, total):
                wizard.files_scanned = current
                wizard.total_files = total
                wizard.scan_progress = current / total if total > 0 else 0

            try:
                ghost_files = scan_ghost_files(
                    folder_path, recursive=True, progress_callback=progress_callback
                )
                wizard.ghost_files = ghost_files

                if ghost_files:
                    wizard.step = "review"
                else:
                    wizard.step = "no_ghosts"

            except Exception as e:
                wizard.step = "error"
                wizard.error_message = str(e)

        thread = Thread(target=scan, daemon=True)
        thread.start()

    def _start_ghost_clean(self):
        """Start cleaning ghost files."""
        wizard = self.state.ghost_cleaner_wizard
        wizard.step = "cleaning"
        wizard.clean_progress = 0.0

        ghost_files = list(wizard.ghost_files)
        base_folder = wizard.folder_path

        from threading import Thread
        from services.ghost_cleaner import clean_ghost_files

        def clean():
            def progress_callback(current, total, bytes_freed):
                wizard.clean_progress = current / total if total > 0 else 0
                wizard.space_freed = bytes_freed

            files_removed, bytes_freed = clean_ghost_files(
                ghost_files, progress_callback, base_folder=base_folder
            )
            wizard.files_removed = files_removed
            wizard.space_freed = bytes_freed
            wizard.step = "complete"

        thread = Thread(target=clean, daemon=True)
        thread.start()


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
