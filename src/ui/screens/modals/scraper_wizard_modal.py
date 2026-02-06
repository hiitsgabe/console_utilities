"""
Game image scraper wizard modal - Multi-step wizard for scraping game artwork.

Steps:
1. rom_select - Browse and select a ROM file
2. searching - Loading indicator while searching for game
3. game_select - Select from search results
4. image_select - Choose which images to download
5. downloading - Download progress
6. updating_metadata - Brief loading while updating metadata
7. complete - Success message
8. error - Error with retry option

Batch mode steps:
1. folder_select - Select folder containing ROMs
2. rom_list - Review ROMs found, deselect any
3. batch_options - Select default images, auto-select toggle
4. batch_processing - Progress through each ROM
5. batch_complete - Summary of successes/failures
"""

import pygame
from typing import Tuple, List, Optional, Dict, Any, Set

from ui.theme import Theme, default_theme
from ui.organisms.modal_frame import ModalFrame
from ui.atoms.text import Text
from ui.atoms.progress import ProgressBar
from utils.button_hints import get_combined_hints


class ScraperWizardModal:
    """
    Multi-step wizard modal for game image scraping.

    Guides users through selecting a ROM, searching for game info,
    choosing images to download, and updating metadata.
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.modal_frame = ModalFrame(theme)
        self.text = Text(theme)
        self.progress_bar = ProgressBar(theme)

    def render(
        self,
        screen: pygame.Surface,
        step: str,
        folder_items: List[Dict[str, Any]],
        folder_highlighted: int,
        folder_current_path: str,
        selected_rom_path: str,
        selected_rom_name: str,
        search_results: List[Dict[str, Any]],
        selected_game_index: int,
        available_images: List[Dict[str, Any]],
        selected_images: Set[int],
        image_highlighted: int,
        download_progress: float,
        current_download: str,
        error_message: str,
        input_mode: str = "keyboard",
        batch_mode: bool = False,
        batch_roms: List[Dict[str, Any]] = None,
        batch_current_index: int = 0,
        batch_auto_select: bool = True,
        batch_default_images: List[str] = None,
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[pygame.Rect]]:
        """
        Render the scraper wizard modal.

        Returns:
            Tuple of (modal_rect, content_rect, close_rect, item_rects)
        """
        batch_roms = batch_roms or []
        batch_default_images = batch_default_images or []

        if step == "rom_select":
            return self._render_rom_select(
                screen,
                folder_items,
                folder_highlighted,
                folder_current_path,
                input_mode,
            )
        elif step == "searching":
            return self._render_searching(screen, selected_rom_name)
        elif step == "game_select":
            return self._render_game_select(
                screen,
                search_results,
                selected_game_index,
                selected_rom_name,
                input_mode,
            )
        elif step == "image_select":
            return self._render_image_select(
                screen, available_images, selected_images, image_highlighted, input_mode
            )
        elif step == "downloading":
            return self._render_downloading(screen, download_progress, current_download)
        elif step == "updating_metadata":
            return self._render_updating_metadata(screen)
        elif step == "complete":
            return self._render_complete(screen, input_mode)
        elif step == "error":
            return self._render_error(screen, error_message, input_mode)
        # Batch mode steps
        elif step == "folder_select":
            return self._render_folder_select(
                screen,
                folder_items,
                folder_highlighted,
                folder_current_path,
                input_mode,
            )
        elif step == "rom_list":
            return self._render_rom_list(
                screen, batch_roms, batch_current_index, input_mode
            )
        elif step == "batch_options":
            return self._render_batch_options(
                screen,
                batch_auto_select,
                batch_default_images,
                image_highlighted,
                input_mode,
            )
        elif step == "batch_processing":
            return self._render_batch_processing(
                screen,
                batch_roms,
                batch_current_index,
                download_progress,
                current_download,
            )
        elif step == "batch_complete":
            return self._render_batch_complete(screen, batch_roms, input_mode)
        else:
            return self._render_rom_select(
                screen,
                folder_items,
                folder_highlighted,
                folder_current_path,
                input_mode,
            )

    def _render_rom_select(
        self,
        screen: pygame.Surface,
        folder_items: List[Dict[str, Any]],
        highlighted: int,
        current_path: str,
        input_mode: str,
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[pygame.Rect]]:
        """Render ROM selection step (file browser)."""
        width = min(600, screen.get_width() - 40)
        height = min(480, screen.get_height() - 60)

        show_close = input_mode == "touch"
        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height, title="Select ROM to Scrape", show_close=show_close
        )

        padding = self.theme.padding_sm
        y = content_rect.top + padding

        # Current path
        short_path = current_path
        if len(short_path) > 55:
            short_path = "..." + short_path[-52:]
        self.text.render(
            screen,
            short_path,
            (content_rect.left + padding, y),
            color=self.theme.text_secondary,
            size=self.theme.font_size_xs,
        )
        y += 22

        # File list
        item_rects = []
        item_height = 38
        visible_items = (content_rect.height - 90) // item_height
        scroll_offset = max(0, highlighted - visible_items + 2)

        for i in range(
            scroll_offset, min(len(folder_items), scroll_offset + visible_items)
        ):
            item = folder_items[i]
            is_selected = i == highlighted

            item_rect = pygame.Rect(
                content_rect.left + padding,
                y,
                content_rect.width - padding * 2,
                item_height - 4,
            )
            item_rects.append(item_rect)

            bg_color = self.theme.primary if is_selected else self.theme.surface_hover
            pygame.draw.rect(
                screen, bg_color, item_rect, border_radius=self.theme.radius_sm
            )

            # Icon and name
            item_type = item.get("type", "")
            icon = (
                "[..]"
                if item_type == "parent"
                else "[ ]" if item_type == "folder" else " * "
            )
            name = item.get("name", "")

            self.text.render(
                screen,
                f"{icon} {name}",
                (
                    item_rect.left + padding,
                    item_rect.centery - self.theme.font_size_sm // 2,
                ),
                color=self.theme.text_primary,
                size=self.theme.font_size_sm,
                max_width=item_rect.width - padding * 2,
            )

            y += item_height

        # Hints
        hints = get_combined_hints(
            [("select", "Select"), ("back", "Cancel")], input_mode
        )
        self.text.render(
            screen,
            hints,
            (content_rect.centerx, content_rect.bottom - padding - 10),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
            align="center",
        )

        return modal_rect, content_rect, close_rect, item_rects

    def _render_searching(
        self, screen: pygame.Surface, rom_name: str
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[pygame.Rect]]:
        """Render searching step."""
        width = min(450, screen.get_width() - 40)
        height = 180

        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height, title="Searching...", show_close=False
        )

        self.text.render(
            screen,
            f"Searching for: {rom_name}",
            (content_rect.centerx, content_rect.centery - 15),
            color=self.theme.text_primary,
            size=self.theme.font_size_md,
            align="center",
            max_width=content_rect.width - 40,
        )

        self.text.render(
            screen,
            "Please wait...",
            (content_rect.centerx, content_rect.centery + 15),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
            align="center",
        )

        return modal_rect, content_rect, None, []

    def _render_game_select(
        self,
        screen: pygame.Surface,
        search_results: List[Dict[str, Any]],
        selected_index: int,
        rom_name: str,
        input_mode: str,
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[pygame.Rect]]:
        """Render game selection from search results."""
        width = min(600, screen.get_width() - 40)
        height = min(450, screen.get_height() - 60)

        show_close = input_mode == "touch"
        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height, title="Select Game", show_close=show_close
        )

        padding = self.theme.padding_sm
        y = content_rect.top + padding

        if not search_results:
            self.text.render(
                screen,
                f"No results found for: {rom_name}",
                (content_rect.centerx, content_rect.centery - 20),
                color=self.theme.text_secondary,
                size=self.theme.font_size_md,
                align="center",
            )

            hints = get_combined_hints([("back", "Go Back")], input_mode)
            self.text.render(
                screen,
                hints,
                (content_rect.centerx, content_rect.bottom - padding - 10),
                color=self.theme.text_secondary,
                size=self.theme.font_size_sm,
                align="center",
            )
            return modal_rect, content_rect, close_rect, []

        self.text.render(
            screen,
            f"Found {len(search_results)} matches:",
            (content_rect.left + padding, y),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
        )
        y += 25

        # Results list
        item_rects = []
        item_height = 55
        visible_items = (content_rect.height - 90) // item_height
        scroll_offset = max(0, selected_index - visible_items + 2)

        for i in range(
            scroll_offset, min(len(search_results), scroll_offset + visible_items)
        ):
            result = search_results[i]
            is_selected = i == selected_index

            item_rect = pygame.Rect(
                content_rect.left + padding,
                y,
                content_rect.width - padding * 2,
                item_height - 5,
            )
            item_rects.append(item_rect)

            bg_color = self.theme.primary if is_selected else self.theme.surface_hover
            pygame.draw.rect(
                screen, bg_color, item_rect, border_radius=self.theme.radius_sm
            )

            # Game name
            self.text.render(
                screen,
                result.get("name", "Unknown"),
                (item_rect.left + padding, item_rect.top + 8),
                color=self.theme.text_primary,
                size=self.theme.font_size_sm,
                max_width=item_rect.width - padding * 2,
            )

            # Platform and date
            platform = result.get("platform", "")
            release = result.get("release_date", "")
            info = f"{platform}" + (f" - {release}" if release else "")
            self.text.render(
                screen,
                info,
                (item_rect.left + padding, item_rect.top + 28),
                color=(
                    self.theme.text_secondary
                    if not is_selected
                    else self.theme.text_primary
                ),
                size=self.theme.font_size_xs,
            )

            y += item_height

        hints = get_combined_hints(
            [("select", "Select"), ("back", "Cancel")], input_mode
        )
        self.text.render(
            screen,
            hints,
            (content_rect.centerx, content_rect.bottom - padding - 10),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
            align="center",
        )

        return modal_rect, content_rect, close_rect, item_rects

    def _render_image_select(
        self,
        screen: pygame.Surface,
        available_images: List[Dict[str, Any]],
        selected_images: Set[int],
        highlighted: int,
        input_mode: str,
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[pygame.Rect]]:
        """Render image type selection (checkboxes)."""
        width = min(500, screen.get_width() - 40)
        height = min(400, screen.get_height() - 60)

        show_close = input_mode == "touch"
        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height, title="Select Images", show_close=show_close
        )

        padding = self.theme.padding_sm
        y = content_rect.top + padding

        if not available_images:
            self.text.render(
                screen,
                "No images available for this game.",
                (content_rect.centerx, content_rect.centery),
                color=self.theme.text_secondary,
                size=self.theme.font_size_md,
                align="center",
            )
            return modal_rect, content_rect, close_rect, []

        self.text.render(
            screen,
            "Select images to download:",
            (content_rect.left + padding, y),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
        )
        y += 25

        # Image list with checkboxes
        item_rects = []
        item_height = 40
        visible_items = (content_rect.height - 100) // item_height
        scroll_offset = max(0, highlighted - visible_items + 2)

        for i in range(
            scroll_offset, min(len(available_images), scroll_offset + visible_items)
        ):
            image = available_images[i]
            is_selected = i == highlighted
            is_checked = i in selected_images

            item_rect = pygame.Rect(
                content_rect.left + padding,
                y,
                content_rect.width - padding * 2,
                item_height - 5,
            )
            item_rects.append(item_rect)

            bg_color = self.theme.primary if is_selected else self.theme.surface_hover
            pygame.draw.rect(
                screen, bg_color, item_rect, border_radius=self.theme.radius_sm
            )

            # Checkbox
            checkbox = "[X]" if is_checked else "[ ]"
            label = image.get("label", image.get("type", "Unknown"))
            region = image.get("region", "")
            if region:
                label += f" ({region.upper()})"

            self.text.render(
                screen,
                f"{checkbox} {label}",
                (
                    item_rect.left + padding,
                    item_rect.centery - self.theme.font_size_sm // 2,
                ),
                color=self.theme.text_primary,
                size=self.theme.font_size_sm,
            )

            y += item_height

        # Hints
        hints = get_combined_hints(
            [("select", "Toggle"), ("start", "Download"), ("back", "Cancel")],
            input_mode,
        )
        self.text.render(
            screen,
            hints,
            (content_rect.centerx, content_rect.bottom - padding - 10),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
            align="center",
        )

        return modal_rect, content_rect, close_rect, item_rects

    def _render_downloading(
        self, screen: pygame.Surface, progress: float, current_item: str
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[pygame.Rect]]:
        """Render download progress."""
        width = min(450, screen.get_width() - 40)
        height = 180

        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height, title="Downloading Images", show_close=False
        )

        padding = self.theme.padding_sm

        self.text.render(
            screen,
            f"Downloading: {current_item}",
            (content_rect.centerx, content_rect.centery - 30),
            color=self.theme.text_primary,
            size=self.theme.font_size_sm,
            align="center",
            max_width=content_rect.width - padding * 2,
        )

        # Progress bar
        bar_rect = pygame.Rect(
            content_rect.left + padding * 2,
            content_rect.centery,
            content_rect.width - padding * 4,
            20,
        )
        self.progress_bar.render(screen, bar_rect, progress)

        self.text.render(
            screen,
            f"{int(progress * 100)}%",
            (content_rect.centerx, content_rect.centery + 35),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
            align="center",
        )

        return modal_rect, content_rect, None, []

    def _render_updating_metadata(
        self, screen: pygame.Surface
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[pygame.Rect]]:
        """Render metadata update step."""
        width = min(400, screen.get_width() - 40)
        height = 150

        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height, title="Updating Metadata", show_close=False
        )

        self.text.render(
            screen,
            "Updating game metadata...",
            (content_rect.centerx, content_rect.centery),
            color=self.theme.text_primary,
            size=self.theme.font_size_md,
            align="center",
        )

        return modal_rect, content_rect, None, []

    def _render_complete(
        self, screen: pygame.Surface, input_mode: str
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[pygame.Rect]]:
        """Render completion step."""
        width = min(400, screen.get_width() - 40)
        height = 180

        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height, title="Complete", show_close=False
        )

        padding = self.theme.padding_sm

        self.text.render(
            screen,
            "Images downloaded successfully!",
            (content_rect.centerx, content_rect.centery - 10),
            color=self.theme.success,
            size=self.theme.font_size_md,
            align="center",
        )

        hints = get_combined_hints([("select", "Done")], input_mode)
        self.text.render(
            screen,
            hints,
            (content_rect.centerx, content_rect.bottom - padding - 15),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
            align="center",
        )

        return modal_rect, content_rect, None, []

    def _render_error(
        self, screen: pygame.Surface, error_message: str, input_mode: str
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[pygame.Rect]]:
        """Render error step."""
        width = min(450, screen.get_width() - 40)
        height = 200

        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height, title="Error", show_close=False
        )

        padding = self.theme.padding_sm

        self.text.render(
            screen,
            error_message or "An error occurred",
            (content_rect.centerx, content_rect.centery - 10),
            color=self.theme.error,
            size=self.theme.font_size_md,
            align="center",
            max_width=content_rect.width - padding * 2,
        )

        hints = get_combined_hints(
            [("select", "Try Again"), ("back", "Cancel")], input_mode
        )
        self.text.render(
            screen,
            hints,
            (content_rect.centerx, content_rect.bottom - padding - 15),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
            align="center",
        )

        return modal_rect, content_rect, None, []

    # Batch mode rendering methods

    def _render_folder_select(
        self,
        screen: pygame.Surface,
        folder_items: List[Dict[str, Any]],
        highlighted: int,
        current_path: str,
        input_mode: str,
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[pygame.Rect]]:
        """Render batch folder selection step."""
        width = min(600, screen.get_width() - 40)
        height = min(480, screen.get_height() - 60)

        show_close = input_mode == "touch"
        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height, title="Select ROM Folder", show_close=show_close
        )

        padding = self.theme.padding_sm
        y = content_rect.top + padding

        short_path = current_path
        if len(short_path) > 55:
            short_path = "..." + short_path[-52:]
        self.text.render(
            screen,
            short_path,
            (content_rect.left + padding, y),
            color=self.theme.text_secondary,
            size=self.theme.font_size_xs,
        )
        y += 22

        item_rects = []
        item_height = 38
        visible_items = (content_rect.height - 90) // item_height
        scroll_offset = max(0, highlighted - visible_items + 2)

        for i in range(
            scroll_offset, min(len(folder_items), scroll_offset + visible_items)
        ):
            item = folder_items[i]
            is_selected = i == highlighted

            item_rect = pygame.Rect(
                content_rect.left + padding,
                y,
                content_rect.width - padding * 2,
                item_height - 4,
            )
            item_rects.append(item_rect)

            bg_color = self.theme.primary if is_selected else self.theme.surface_hover
            pygame.draw.rect(
                screen, bg_color, item_rect, border_radius=self.theme.radius_sm
            )

            item_type = item.get("type", "")
            icon = "[..]" if item_type == "parent" else "[ ]"
            name = item.get("name", "")

            self.text.render(
                screen,
                f"{icon} {name}",
                (
                    item_rect.left + padding,
                    item_rect.centery - self.theme.font_size_sm // 2,
                ),
                color=self.theme.text_primary,
                size=self.theme.font_size_sm,
                max_width=item_rect.width - padding * 2,
            )

            y += item_height

        hints = get_combined_hints(
            [("start", "Select Folder"), ("select", "Open"), ("back", "Cancel")],
            input_mode,
        )
        self.text.render(
            screen,
            hints,
            (content_rect.centerx, content_rect.bottom - padding - 10),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
            align="center",
        )

        return modal_rect, content_rect, close_rect, item_rects

    def _render_rom_list(
        self,
        screen: pygame.Surface,
        batch_roms: List[Dict[str, Any]],
        highlighted: int,
        input_mode: str,
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[pygame.Rect]]:
        """Render batch ROM list for review."""
        width = min(600, screen.get_width() - 40)
        height = min(480, screen.get_height() - 60)

        show_close = input_mode == "touch"
        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen,
            width,
            height,
            title=f"ROMs Found ({len(batch_roms)})",
            show_close=show_close,
        )

        padding = self.theme.padding_sm
        y = content_rect.top + padding

        self.text.render(
            screen,
            "Toggle to skip, press START to continue:",
            (content_rect.left + padding, y),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
        )
        y += 25

        item_rects = []
        item_height = 38
        visible_items = (content_rect.height - 90) // item_height
        scroll_offset = max(0, highlighted - visible_items + 2)

        for i in range(
            scroll_offset, min(len(batch_roms), scroll_offset + visible_items)
        ):
            rom = batch_roms[i]
            is_selected = i == highlighted
            is_skipped = rom.get("status") == "skipped"

            item_rect = pygame.Rect(
                content_rect.left + padding,
                y,
                content_rect.width - padding * 2,
                item_height - 4,
            )
            item_rects.append(item_rect)

            bg_color = self.theme.primary if is_selected else self.theme.surface_hover
            pygame.draw.rect(
                screen, bg_color, item_rect, border_radius=self.theme.radius_sm
            )

            checkbox = "[ ]" if is_skipped else "[X]"
            name = rom.get("name", "Unknown")
            text_color = (
                self.theme.text_disabled if is_skipped else self.theme.text_primary
            )

            self.text.render(
                screen,
                f"{checkbox} {name}",
                (
                    item_rect.left + padding,
                    item_rect.centery - self.theme.font_size_sm // 2,
                ),
                color=text_color,
                size=self.theme.font_size_sm,
                max_width=item_rect.width - padding * 2,
            )

            y += item_height

        hints = get_combined_hints(
            [("select", "Toggle"), ("start", "Continue"), ("back", "Cancel")],
            input_mode,
        )
        self.text.render(
            screen,
            hints,
            (content_rect.centerx, content_rect.bottom - padding - 10),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
            align="center",
        )

        return modal_rect, content_rect, close_rect, item_rects

    def _render_batch_options(
        self,
        screen: pygame.Surface,
        auto_select: bool,
        default_images: List[str],
        highlighted: int,
        input_mode: str,
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[pygame.Rect]]:
        """Render batch options selection."""
        width = min(500, screen.get_width() - 40)
        height = min(350, screen.get_height() - 60)

        show_close = input_mode == "touch"
        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height, title="Batch Options", show_close=show_close
        )

        padding = self.theme.padding_sm
        y = content_rect.top + padding

        item_rects = []
        item_height = 40

        # Auto-select option
        auto_rect = pygame.Rect(
            content_rect.left + padding,
            y,
            content_rect.width - padding * 2,
            item_height - 5,
        )
        item_rects.append(auto_rect)

        bg_color = self.theme.primary if highlighted == 0 else self.theme.surface_hover
        pygame.draw.rect(
            screen, bg_color, auto_rect, border_radius=self.theme.radius_sm
        )

        checkbox = "[X]" if auto_select else "[ ]"
        self.text.render(
            screen,
            f"{checkbox} Auto-select first result",
            (
                auto_rect.left + padding,
                auto_rect.centery - self.theme.font_size_sm // 2,
            ),
            color=self.theme.text_primary,
            size=self.theme.font_size_sm,
        )
        y += item_height

        # Default images section
        self.text.render(
            screen,
            "Default images to download:",
            (content_rect.left + padding, y + 5),
            color=self.theme.text_secondary,
            size=self.theme.font_size_xs,
        )
        y += 25

        all_image_types = ["box-2D", "boxart", "screenshot", "wheel", "fanart"]
        for i, img_type in enumerate(all_image_types):
            img_rect = pygame.Rect(
                content_rect.left + padding,
                y,
                content_rect.width - padding * 2,
                item_height - 5,
            )
            item_rects.append(img_rect)

            is_selected = highlighted == i + 1
            is_checked = img_type in default_images

            bg_color = self.theme.primary if is_selected else self.theme.surface_hover
            pygame.draw.rect(
                screen, bg_color, img_rect, border_radius=self.theme.radius_sm
            )

            checkbox = "[X]" if is_checked else "[ ]"
            label = img_type.replace("-", " ").title()
            self.text.render(
                screen,
                f"{checkbox} {label}",
                (
                    img_rect.left + padding,
                    img_rect.centery - self.theme.font_size_sm // 2,
                ),
                color=self.theme.text_primary,
                size=self.theme.font_size_sm,
            )
            y += item_height

        hints = get_combined_hints(
            [("select", "Toggle"), ("start", "Start Batch"), ("back", "Cancel")],
            input_mode,
        )
        self.text.render(
            screen,
            hints,
            (content_rect.centerx, content_rect.bottom - padding - 10),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
            align="center",
        )

        return modal_rect, content_rect, close_rect, item_rects

    def _render_batch_processing(
        self,
        screen: pygame.Surface,
        batch_roms: List[Dict[str, Any]],
        current_index: int,
        progress: float,
        current_item: str,
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[pygame.Rect]]:
        """Render batch processing progress."""
        width = min(500, screen.get_width() - 40)
        height = 220

        total = len(batch_roms)
        done = sum(
            1 for r in batch_roms if r.get("status") in ("done", "error", "skipped")
        )

        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen,
            width,
            height,
            title=f"Processing ({done}/{total})",
            show_close=False,
        )

        padding = self.theme.padding_sm
        y = content_rect.top + padding

        if current_index < len(batch_roms):
            current_rom = batch_roms[current_index]
            self.text.render(
                screen,
                f"Current: {current_rom.get('name', 'Unknown')}",
                (content_rect.left + padding, y),
                color=self.theme.text_primary,
                size=self.theme.font_size_sm,
                max_width=content_rect.width - padding * 2,
            )
        y += 25

        self.text.render(
            screen,
            current_item or "Processing...",
            (content_rect.left + padding, y),
            color=self.theme.text_secondary,
            size=self.theme.font_size_xs,
        )
        y += 25

        # Overall progress
        overall_progress = done / total if total > 0 else 0
        bar_rect = pygame.Rect(
            content_rect.left + padding * 2,
            y,
            content_rect.width - padding * 4,
            20,
        )
        self.progress_bar.render(screen, bar_rect, overall_progress)

        y += 35
        self.text.render(
            screen,
            f"Overall: {int(overall_progress * 100)}%",
            (content_rect.centerx, y),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
            align="center",
        )

        return modal_rect, content_rect, None, []

    def _render_batch_complete(
        self,
        screen: pygame.Surface,
        batch_roms: List[Dict[str, Any]],
        input_mode: str,
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[pygame.Rect]]:
        """Render batch completion summary."""
        width = min(450, screen.get_width() - 40)
        height = 220

        done = sum(1 for r in batch_roms if r.get("status") == "done")
        errors = sum(1 for r in batch_roms if r.get("status") == "error")
        skipped = sum(1 for r in batch_roms if r.get("status") == "skipped")

        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height, title="Batch Complete", show_close=False
        )

        padding = self.theme.padding_sm
        y = content_rect.top + padding + 10

        self.text.render(
            screen,
            f"Successful: {done}",
            (content_rect.centerx, y),
            color=self.theme.success,
            size=self.theme.font_size_md,
            align="center",
        )
        y += 30

        if errors > 0:
            self.text.render(
                screen,
                f"Failed: {errors}",
                (content_rect.centerx, y),
                color=self.theme.error,
                size=self.theme.font_size_md,
                align="center",
            )
            y += 30

        if skipped > 0:
            self.text.render(
                screen,
                f"Skipped: {skipped}",
                (content_rect.centerx, y),
                color=self.theme.text_secondary,
                size=self.theme.font_size_md,
                align="center",
            )

        hints = get_combined_hints([("select", "Done")], input_mode)
        self.text.render(
            screen,
            hints,
            (content_rect.centerx, content_rect.bottom - padding - 15),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
            align="center",
        )

        return modal_rect, content_rect, None, []


# Default instance
scraper_wizard_modal = ScraperWizardModal()
