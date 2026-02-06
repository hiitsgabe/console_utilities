"""
Internet Archive download wizard modal - Download files from IA items.
"""

import pygame
from typing import Tuple, List, Optional, Dict, Any

from ui.theme import Theme, default_theme
from ui.organisms.modal_frame import ModalFrame
from ui.organisms.char_keyboard import CharKeyboard
from ui.atoms.text import Text
from ui.atoms.button import Button
from utils.button_hints import get_combined_hints


class IADownloadModal:
    """
    Internet Archive download wizard modal.

    Multi-step wizard:
    1. Item ID input - Enter the IA item identifier
    2. Validating - Show loading while validating item
    3. File select - Choose file to download from item
    4. Folder - Select output folder
    5. Options - Toggle extraction for zip files
    6. Downloading - Show download progress (handled by download manager)
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.modal_frame = ModalFrame(theme)
        self.char_keyboard = CharKeyboard(theme)
        self.text = Text(theme)
        self.button = Button(theme)

    def render(
        self,
        screen: pygame.Surface,
        step: str,
        url: str,
        item_id: str,
        files_list: List[Dict[str, Any]],
        selected_file_index: int,
        output_folder: str,
        folder_items: List[Dict[str, Any]],
        folder_highlighted: int,
        should_extract: bool,
        cursor_position: int,
        error_message: str = "",
        input_mode: str = "keyboard",
    ) -> Tuple[
        pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple], List[pygame.Rect]
    ]:
        """
        Render the IA download wizard modal.

        Returns:
            Tuple of (modal_rect, content_rect, close_rect, char_rects, item_rects)
        """
        if step == "url":
            rects = self._render_url_step(screen, url, cursor_position, input_mode)
            return (*rects, [])
        elif step == "validating":
            rects = self._render_validating_step(screen)
            return (*rects, [])
        elif step == "file_select":
            return self._render_file_select_step(
                screen, item_id, files_list, selected_file_index, input_mode
            )
        elif step == "folder":
            return self._render_folder_step(
                screen, output_folder, folder_items, folder_highlighted, input_mode
            )
        elif step == "options":
            rects = self._render_options_step(
                screen, files_list, selected_file_index, should_extract, input_mode
            )
            return (*rects, [])
        elif step == "error":
            rects = self._render_error_step(screen, error_message, input_mode)
            return (*rects, [])
        else:
            rects = self._render_url_step(screen, url, cursor_position, input_mode)
            return (*rects, [])

    def _render_url_step(
        self,
        screen: pygame.Surface,
        url: str,
        cursor_position: int,
        input_mode: str,
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple]]:
        """Render URL input step."""
        title = "Download from Internet Archive"

        if input_mode == "keyboard":
            return self._render_keyboard_url_input(screen, url, input_mode)

        # On-screen keyboard mode
        width = min(650, screen.get_width() - 40)
        height = 420

        show_close = input_mode == "touch"
        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height, title=title, show_close=show_close
        )

        padding = self.theme.padding_sm
        self.text.render(
            screen,
            "Enter Item ID (e.g., myrient_sony_psx):",
            (content_rect.left + padding, content_rect.top + padding),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
        )

        keyboard_rect = pygame.Rect(
            content_rect.left,
            content_rect.top + 25,
            content_rect.width,
            content_rect.height - 25,
        )

        char_rects, _ = self.char_keyboard.render(
            screen,
            keyboard_rect,
            current_text=url,
            selected_index=cursor_position,
            chars_per_row=13,
            char_set="url",
            show_input_field=True,
        )

        return modal_rect, content_rect, close_rect, char_rects

    def _render_keyboard_url_input(
        self, screen: pygame.Surface, url: str, input_mode: str
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple]]:
        """Render URL input for keyboard mode."""
        width = min(550, screen.get_width() - 40)
        height = 180

        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen,
            width,
            height,
            title="Download from Internet Archive",
            show_close=False,
        )

        padding = self.theme.padding_sm
        y = content_rect.top + padding

        self.text.render(
            screen,
            "Enter Item ID:",
            (content_rect.left + padding, y),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
        )
        y += 25

        # Input field
        field_height = 40
        field_rect = pygame.Rect(
            content_rect.left + padding,
            y,
            content_rect.width - padding * 2,
            field_height,
        )

        pygame.draw.rect(
            screen,
            self.theme.surface_hover,
            field_rect,
            border_radius=self.theme.radius_sm,
        )

        placeholder = "e.g., myrient_sony_psx"
        display_text = url if url else placeholder
        text_color = self.theme.text_primary if url else self.theme.text_disabled
        self.text.render(
            screen,
            display_text,
            (
                field_rect.left + padding,
                field_rect.centery - self.theme.font_size_md // 2,
            ),
            color=text_color,
            size=self.theme.font_size_md,
            max_width=field_rect.width - padding * 2,
        )

        # Cursor
        if url:
            cursor_x = (
                field_rect.left
                + padding
                + self.text.measure(url, self.theme.font_size_md)[0]
                + 2
            )
        else:
            cursor_x = field_rect.left + padding

        pygame.draw.line(
            screen,
            self.theme.primary,
            (cursor_x, field_rect.top + 8),
            (cursor_x, field_rect.bottom - 8),
            2,
        )

        y = field_rect.bottom + padding

        hints = get_combined_hints(
            [("select", "Continue"), ("back", "Cancel")], "keyboard"
        )
        self.text.render(
            screen,
            hints,
            (content_rect.centerx, y),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
            align="center",
        )

        return modal_rect, content_rect, None, []

    def _render_validating_step(
        self, screen: pygame.Surface
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple]]:
        """Render validating/loading step."""
        width = min(400, screen.get_width() - 40)
        height = 150

        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen,
            width,
            height,
            title="Download from Internet Archive",
            show_close=False,
        )

        self.text.render(
            screen,
            "Validating item...",
            (content_rect.centerx, content_rect.centery - 10),
            color=self.theme.text_primary,
            size=self.theme.font_size_md,
            align="center",
        )

        self.text.render(
            screen,
            "Please wait",
            (content_rect.centerx, content_rect.centery + 20),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
            align="center",
        )

        return modal_rect, content_rect, None, []

    def _render_file_select_step(
        self,
        screen: pygame.Surface,
        item_id: str,
        files_list: List[Dict[str, Any]],
        selected_file_index: int,
        input_mode: str,
    ) -> Tuple[
        pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple], List[pygame.Rect]
    ]:
        """Render file selection step."""
        width = min(600, screen.get_width() - 40)
        height = min(450, screen.get_height() - 60)

        show_close = input_mode == "touch"
        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen,
            width,
            height,
            title=f"Select File - {item_id}",
            show_close=show_close,
        )

        padding = self.theme.padding_sm
        y = content_rect.top + padding

        self.text.render(
            screen,
            f"Found {len(files_list)} files. Select one to download:",
            (content_rect.left + padding, y),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
        )
        y += 30

        # File list
        item_rects = []
        item_height = 45
        visible_items = (content_rect.height - 80) // item_height
        scroll_offset = max(0, selected_file_index - visible_items + 2)

        for i in range(
            scroll_offset, min(len(files_list), scroll_offset + visible_items)
        ):
            file_info = files_list[i]
            is_selected = i == selected_file_index

            item_rect = pygame.Rect(
                content_rect.left + padding,
                y,
                content_rect.width - padding * 2,
                item_height - 5,
            )
            item_rects.append(item_rect)

            # Background
            bg_color = self.theme.primary if is_selected else self.theme.surface_hover
            pygame.draw.rect(
                screen, bg_color, item_rect, border_radius=self.theme.radius_sm
            )

            # Filename
            text_color = (
                self.theme.text_primary if is_selected else self.theme.text_primary
            )
            self.text.render(
                screen,
                file_info["name"],
                (item_rect.left + padding, item_rect.top + 8),
                color=text_color,
                size=self.theme.font_size_sm,
                max_width=item_rect.width - padding * 2,
            )

            # Size
            size_str = self._format_size(file_info.get("size", 0))
            self.text.render(
                screen,
                size_str,
                (item_rect.left + padding, item_rect.top + 24),
                color=(
                    self.theme.text_secondary
                    if not is_selected
                    else self.theme.text_primary
                ),
                size=self.theme.font_size_xs,
            )

            y += item_height

        # Hints at bottom
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

        return modal_rect, content_rect, close_rect, [], item_rects

    def _render_folder_step(
        self,
        screen: pygame.Surface,
        current_path: str,
        folder_items: List[Dict[str, Any]],
        highlighted: int,
        input_mode: str,
    ) -> Tuple[
        pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple], List[pygame.Rect]
    ]:
        """Render folder selection step."""
        width = min(600, screen.get_width() - 40)
        height = min(450, screen.get_height() - 60)

        show_close = input_mode == "touch"
        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height, title="Select Output Folder", show_close=show_close
        )

        padding = self.theme.padding_sm
        y = content_rect.top + padding

        # Current path
        short_path = current_path
        if len(short_path) > 50:
            short_path = "..." + short_path[-47:]
        self.text.render(
            screen,
            short_path,
            (content_rect.left + padding, y),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
        )
        y += 30

        # Folder list
        item_rects = []
        item_height = 40
        visible_items = (content_rect.height - 100) // item_height
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
                item_height - 5,
            )
            item_rects.append(item_rect)

            bg_color = self.theme.primary if is_selected else self.theme.surface_hover
            pygame.draw.rect(
                screen, bg_color, item_rect, border_radius=self.theme.radius_sm
            )

            # Icon and name
            icon = (
                "[..]"
                if item.get("type") == "parent"
                else "[+]" if item.get("type") == "create_folder" else "[ ]"
            )
            name = item.get("name", "")

            text_color = self.theme.text_primary
            self.text.render(
                screen,
                f"{icon} {name}",
                (
                    item_rect.left + padding,
                    item_rect.centery - self.theme.font_size_sm // 2,
                ),
                color=text_color,
                size=self.theme.font_size_sm,
                max_width=item_rect.width - padding * 2,
            )

            y += item_height

        # Hints
        hints = get_combined_hints(
            [("select", "Select Folder"), ("back", "Cancel")], input_mode
        )
        self.text.render(
            screen,
            hints,
            (content_rect.centerx, content_rect.bottom - padding - 10),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
            align="center",
        )

        return modal_rect, content_rect, close_rect, [], item_rects

    def _render_options_step(
        self,
        screen: pygame.Surface,
        files_list: List[Dict[str, Any]],
        selected_file_index: int,
        should_extract: bool,
        input_mode: str,
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple]]:
        """Render options step before download."""
        width = min(500, screen.get_width() - 40)
        height = 250

        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height, title="Download Options", show_close=False
        )

        padding = self.theme.padding_sm
        y = content_rect.top + padding

        # Selected file info
        if files_list and 0 <= selected_file_index < len(files_list):
            file_info = files_list[selected_file_index]
            filename = file_info["name"]
            size_str = self._format_size(file_info.get("size", 0))

            self.text.render(
                screen,
                f"File: {filename}",
                (content_rect.left + padding, y),
                color=self.theme.text_primary,
                size=self.theme.font_size_sm,
                max_width=content_rect.width - padding * 2,
            )
            y += 25

            self.text.render(
                screen,
                f"Size: {size_str}",
                (content_rect.left + padding, y),
                color=self.theme.text_secondary,
                size=self.theme.font_size_sm,
            )
            y += 35

            # Extract option (only for zip files)
            if filename.lower().endswith(".zip"):
                extract_text = "Extract ZIP: " + ("Yes" if should_extract else "No")
                self.text.render(
                    screen,
                    extract_text,
                    (content_rect.left + padding, y),
                    color=self.theme.text_primary,
                    size=self.theme.font_size_md,
                )
                y += 25

                self.text.render(
                    screen,
                    "(Press SELECT to toggle)",
                    (content_rect.left + padding, y),
                    color=self.theme.text_secondary,
                    size=self.theme.font_size_xs,
                )
                y += 30

        # Hints
        hints = get_combined_hints(
            [("start", "Download"), ("select", "Toggle Extract"), ("back", "Cancel")],
            input_mode,
        )
        self.text.render(
            screen,
            hints,
            (content_rect.centerx, content_rect.bottom - padding - 20),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
            align="center",
        )

        return modal_rect, content_rect, None, []

    def _render_error_step(
        self, screen: pygame.Surface, error_message: str, input_mode: str
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple]]:
        """Render error step."""
        width = min(450, screen.get_width() - 40)
        height = 180

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
            (content_rect.centerx, content_rect.bottom - padding - 20),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
            align="center",
        )

        return modal_rect, content_rect, None, []

    def handle_url_selection(
        self, cursor_position: int, current_text: str
    ) -> Tuple[str, bool]:
        """Handle URL keyboard selection."""
        return self.char_keyboard.handle_selection(
            cursor_position, current_text, char_set="url"
        )

    def _format_size(self, size: int) -> str:
        """Format bytes to human readable string."""
        if size == 0:
            return "Unknown size"
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0:
                return (
                    f"{size:.1f} {unit}" if size != int(size) else f"{int(size)} {unit}"
                )
            size /= 1024.0
        return f"{size:.1f} PB"


# Default instance
ia_download_modal = IADownloadModal()
