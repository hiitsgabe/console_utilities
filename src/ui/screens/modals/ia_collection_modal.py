"""
Internet Archive collection wizard modal - Add IA collection to main menu.
"""

import pygame
from typing import Tuple, List, Optional, Dict, Any, Set

from ui.theme import Theme, default_theme
from ui.organisms.modal_frame import ModalFrame
from ui.organisms.char_keyboard import CharKeyboard
from ui.atoms.text import Text
from utils.button_hints import get_combined_hints


class IACollectionModal:
    """
    Internet Archive collection wizard modal.

    Multi-step wizard:
    1. Collection ID input - Enter the IA item identifier
    2. Validating - Show loading while validating item
    3. Name - Enter display name for the collection
    4. Folder - Enter ROM folder name
    5. Formats - Select file formats to show
    6. Options - Toggle unzip option
    7. Confirm - Review and confirm
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.modal_frame = ModalFrame(theme)
        self.char_keyboard = CharKeyboard(theme)
        self.text = Text(theme)

    def render(
        self,
        screen: pygame.Surface,
        step: str,
        url: str,
        item_id: str,
        collection_name: str,
        folder_name: str,
        available_formats: List[str],
        selected_formats: Set[int],
        format_highlighted: int,
        should_unzip: bool,
        cursor_position: int,
        error_message: str = "",
        input_mode: str = "keyboard",
        adding_custom_format: bool = False,
        custom_format_input: str = "",
        extract_contents: bool = True,
        options_highlighted: int = 0,
        shift_active: bool = False,
    ) -> Tuple[
        pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple], List[pygame.Rect]
    ]:
        """
        Render the IA collection wizard modal.

        Returns:
            Tuple of (modal_rect, content_rect, close_rect, char_rects, item_rects)
        """
        if step == "url":
            rects = self._render_url_step(
                screen, url, cursor_position, input_mode, shift_active
            )
            return (*rects, [])
        elif step == "validating":
            rects = self._render_validating_step(screen)
            return (*rects, [])
        elif step == "name":
            rects = self._render_name_step(
                screen,
                collection_name,
                cursor_position,
                input_mode,
                shift_active,
            )
            return (*rects, [])
        elif step == "folder":
            rects = self._render_folder_step(
                screen, folder_name, cursor_position, input_mode, shift_active
            )
            return (*rects, [])
        elif step == "formats":
            return self._render_formats_step(
                screen,
                available_formats,
                selected_formats,
                format_highlighted,
                input_mode,
                adding_custom_format,
                custom_format_input,
                cursor_position,
                shift_active,
            )
        elif step == "options":
            return self._render_options_step(
                screen, should_unzip, extract_contents, options_highlighted, input_mode
            )
        elif step == "confirm":
            rects = self._render_confirm_step(
                screen,
                collection_name,
                folder_name,
                available_formats,
                selected_formats,
                should_unzip,
                extract_contents,
                item_id,
                input_mode,
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
        collection_id: str,
        cursor_position: int,
        input_mode: str,
        shift_active: bool = False,
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple]]:
        """Render collection ID input step."""
        title = "Add Internet Archive Collection"

        if input_mode == "keyboard":
            return self._render_keyboard_input(
                screen,
                title,
                "Enter Item ID:",
                collection_id,
                "e.g., myrient_sony_psx",
                input_mode,
            )

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
            current_text=collection_id,
            selected_index=cursor_position,
            chars_per_row=13,
            char_set="url",  # Keep url charset for underscore and dash in IDs
            show_input_field=True,
            shift_active=shift_active,
        )

        return modal_rect, content_rect, close_rect, char_rects

    def _render_validating_step(
        self, screen: pygame.Surface
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple]]:
        """Render validating/loading step."""
        width = min(400, screen.get_width() - 40)
        height = 150

        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height, title="Add IA Collection", show_close=False
        )

        self.text.render(
            screen,
            "Validating collection...",
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

    def _render_name_step(
        self,
        screen: pygame.Surface,
        name: str,
        cursor_position: int,
        input_mode: str,
        shift_active: bool = False,
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple]]:
        """Render collection name input step."""
        title = "Add Internet Archive Collection"

        if input_mode == "keyboard":
            return self._render_keyboard_input(
                screen,
                title,
                "Collection display name:",
                name,
                "e.g., PortMaster Ports",
                input_mode,
            )

        width = min(650, screen.get_width() - 40)
        height = 420

        show_close = input_mode == "touch"
        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height, title=title, show_close=show_close
        )

        padding = self.theme.padding_sm
        self.text.render(
            screen,
            "Enter a display name for this collection:",
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
            current_text=name,
            selected_index=cursor_position,
            chars_per_row=13,
            char_set="default",
            show_input_field=True,
            shift_active=shift_active,
        )

        return modal_rect, content_rect, close_rect, char_rects

    def _render_folder_step(
        self,
        screen: pygame.Surface,
        folder: str,
        cursor_position: int,
        input_mode: str,
        shift_active: bool = False,
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple]]:
        """Render folder name input step."""
        title = "Add Internet Archive Collection"

        if input_mode == "keyboard":
            return self._render_keyboard_input(
                screen,
                title,
                "ROM folder name (within roms directory):",
                folder,
                "e.g., portmaster",
                input_mode,
            )

        width = min(650, screen.get_width() - 40)
        height = 420

        show_close = input_mode == "touch"
        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height, title=title, show_close=show_close
        )

        padding = self.theme.padding_sm
        self.text.render(
            screen,
            "Enter folder name for ROMs (will be created in roms directory):",
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
            current_text=folder,
            selected_index=cursor_position,
            chars_per_row=13,
            char_set="default",
            show_input_field=True,
            shift_active=shift_active,
        )

        return modal_rect, content_rect, close_rect, char_rects

    def _render_keyboard_input(
        self,
        screen: pygame.Surface,
        title: str,
        label: str,
        value: str,
        placeholder: str,
        input_mode: str,
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple]]:
        """Render simple keyboard text input."""
        width = min(500, screen.get_width() - 40)
        height = 180

        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height, title=title, show_close=False
        )

        padding = self.theme.padding_sm
        y = content_rect.top + padding

        self.text.render(
            screen,
            label,
            (content_rect.left + padding, y),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
        )
        y += 25

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

        display_text = value if value else placeholder
        text_color = self.theme.text_primary if value else self.theme.text_disabled
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
        if value:
            cursor_x = (
                field_rect.left
                + padding
                + self.text.measure(value, self.theme.font_size_md)[0]
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

    def _render_formats_step(
        self,
        screen: pygame.Surface,
        available_formats: List[str],
        selected_formats: Set[int],
        format_highlighted: int,
        input_mode: str,
        adding_custom_format: bool = False,
        custom_format_input: str = "",
        cursor_position: int = 0,
        shift_active: bool = False,
    ) -> Tuple[
        pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple], List[pygame.Rect]
    ]:
        """Render file format selection step."""
        # If adding custom format, show keyboard input
        if adding_custom_format:
            return self._render_custom_format_input(
                screen,
                custom_format_input,
                cursor_position,
                input_mode,
                shift_active,
            )

        width = min(500, screen.get_width() - 40)
        height = min(400, screen.get_height() - 60)

        show_close = input_mode == "touch"
        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height, title="Select File Formats", show_close=show_close
        )

        padding = self.theme.padding_sm
        y = content_rect.top + padding

        self.text.render(
            screen,
            "Select file formats (or add custom):",
            (content_rect.left + padding, y),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
        )
        y += 30

        # Format list with checkboxes + "Add custom..." option at the end
        item_rects = []
        item_height = 40
        total_items = len(available_formats) + 1  # +1 for "Add custom..."
        visible_items = (content_rect.height - 100) // item_height
        scroll_offset = max(0, format_highlighted - visible_items + 2)

        for i in range(scroll_offset, min(total_items, scroll_offset + visible_items)):
            is_highlighted = i == format_highlighted

            item_rect = pygame.Rect(
                content_rect.left + padding,
                y,
                content_rect.width - padding * 2,
                item_height - 5,
            )
            item_rects.append(item_rect)

            bg_color = (
                self.theme.primary if is_highlighted else self.theme.surface_hover
            )
            pygame.draw.rect(
                screen, bg_color, item_rect, border_radius=self.theme.radius_sm
            )

            if i < len(available_formats):
                # Regular format with checkbox
                fmt = available_formats[i]
                is_selected = i in selected_formats
                checkbox = "[X]" if is_selected else "[ ]"
                self.text.render(
                    screen,
                    f"{checkbox}  {fmt}",
                    (
                        item_rect.left + padding,
                        item_rect.centery - self.theme.font_size_sm // 2,
                    ),
                    color=self.theme.text_primary,
                    size=self.theme.font_size_sm,
                )
            else:
                # "Add custom..." option
                self.text.render(
                    screen,
                    "+ Add custom format...",
                    (
                        item_rect.left + padding,
                        item_rect.centery - self.theme.font_size_sm // 2,
                    ),
                    color=self.theme.text_secondary,
                    size=self.theme.font_size_sm,
                )

            y += item_height

        # Hints
        hints = get_combined_hints(
            [("select", "Toggle/Add"), ("start", "Continue"), ("back", "Back")],
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

        return modal_rect, content_rect, close_rect, [], item_rects

    def _render_custom_format_input(
        self,
        screen: pygame.Surface,
        custom_format: str,
        cursor_position: int,
        input_mode: str,
        shift_active: bool = False,
    ) -> Tuple[
        pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple], List[pygame.Rect]
    ]:
        """Render custom format input."""
        if input_mode == "keyboard":
            rects = self._render_keyboard_input(
                screen,
                "Add Custom Format",
                "Enter file extension:",
                custom_format,
                "e.g., .7z",
                input_mode,
            )
            return (*rects, [])

        width = min(650, screen.get_width() - 40)
        height = 420

        show_close = input_mode == "touch"
        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height, title="Add Custom Format", show_close=show_close
        )

        padding = self.theme.padding_sm
        self.text.render(
            screen,
            "Enter file extension (e.g., .7z, .iso):",
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
            current_text=custom_format,
            selected_index=cursor_position,
            chars_per_row=13,
            char_set="default",
            show_input_field=True,
            shift_active=shift_active,
        )

        return modal_rect, content_rect, close_rect, char_rects, []

    def _render_options_step(
        self,
        screen: pygame.Surface,
        should_unzip: bool,
        extract_contents: bool,
        options_highlighted: int,
        input_mode: str,
    ) -> Tuple[
        pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple], List[pygame.Rect]
    ]:
        """Render options step with list of toggleable options."""
        width = min(500, screen.get_width() - 40)
        height = 280 if should_unzip else 200

        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height, title="Collection Options", show_close=False
        )

        padding = self.theme.padding_sm
        y = content_rect.top + padding + 10
        item_height = 50
        item_rects = []

        # Option 1: Auto-extract ZIP files
        option1_rect = pygame.Rect(
            content_rect.left + padding,
            y,
            content_rect.width - padding * 2,
            item_height - 5,
        )
        item_rects.append(option1_rect)

        bg_color = (
            self.theme.primary if options_highlighted == 0 else self.theme.surface_hover
        )
        pygame.draw.rect(
            screen, bg_color, option1_rect, border_radius=self.theme.radius_sm
        )

        unzip_text = f"Auto-extract ZIP files: {'Yes' if should_unzip else 'No'}"
        self.text.render(
            screen,
            unzip_text,
            (option1_rect.left + padding, option1_rect.centery - 8),
            color=self.theme.text_primary,
            size=self.theme.font_size_sm,
        )
        y += item_height

        # Option 2: Extract mode (only shown if should_unzip is True)
        if should_unzip:
            option2_rect = pygame.Rect(
                content_rect.left + padding,
                y,
                content_rect.width - padding * 2,
                item_height - 5,
            )
            item_rects.append(option2_rect)

            bg_color = (
                self.theme.primary
                if options_highlighted == 1
                else self.theme.surface_hover
            )
            pygame.draw.rect(
                screen, bg_color, option2_rect, border_radius=self.theme.radius_sm
            )

            extract_text = (
                "Extract: Contents only"
                if extract_contents
                else "Extract: Keep folder structure"
            )
            self.text.render(
                screen,
                extract_text,
                (option2_rect.left + padding, option2_rect.centery - 8),
                color=self.theme.text_primary,
                size=self.theme.font_size_sm,
            )
            y += item_height

        # Hints
        hints = get_combined_hints(
            [("select", "Toggle"), ("start", "Continue"), ("back", "Back")],
            input_mode,
        )
        self.text.render(
            screen,
            hints,
            (content_rect.centerx, content_rect.bottom - padding - 15),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
            align="center",
        )

        return modal_rect, content_rect, None, [], item_rects

    def _render_confirm_step(
        self,
        screen: pygame.Surface,
        collection_name: str,
        folder_name: str,
        available_formats: List[str],
        selected_formats: Set[int],
        should_unzip: bool,
        extract_contents: bool,
        item_id: str,
        input_mode: str,
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Tuple]]:
        """Render confirmation step."""
        width = min(500, screen.get_width() - 40)
        height = 300 if should_unzip else 280

        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height, title="Confirm Collection", show_close=False
        )

        padding = self.theme.padding_sm
        y = content_rect.top + padding

        # Summary
        self.text.render(
            screen,
            f"Name: {collection_name}",
            (content_rect.left + padding, y),
            color=self.theme.text_primary,
            size=self.theme.font_size_sm,
        )
        y += 25

        self.text.render(
            screen,
            f"Folder: {folder_name}",
            (content_rect.left + padding, y),
            color=self.theme.text_primary,
            size=self.theme.font_size_sm,
        )
        y += 25

        self.text.render(
            screen,
            f"Source: {item_id}",
            (content_rect.left + padding, y),
            color=self.theme.text_secondary,
            size=self.theme.font_size_xs,
        )
        y += 25

        # Selected formats
        formats_str = (
            ", ".join(available_formats[i] for i in sorted(selected_formats))
            if selected_formats
            else "All formats"
        )
        self.text.render(
            screen,
            f"Formats: {formats_str}",
            (content_rect.left + padding, y),
            color=self.theme.text_primary,
            size=self.theme.font_size_sm,
            max_width=content_rect.width - padding * 2,
        )
        y += 25

        extract_mode = "Contents only" if extract_contents else "Keep folder structure"
        extract_text = (
            f"Auto-extract: {'Yes (' + extract_mode + ')' if should_unzip else 'No'}"
        )
        self.text.render(
            screen,
            extract_text,
            (content_rect.left + padding, y),
            color=self.theme.text_primary,
            size=self.theme.font_size_sm,
        )
        y += 35

        self.text.render(
            screen,
            "Add this collection to the main menu?",
            (content_rect.centerx, y),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
            align="center",
        )

        # Hints
        hints = get_combined_hints(
            [("select", "Confirm"), ("back", "Cancel")], input_mode
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

    def handle_selection(
        self,
        step: str,
        cursor_position: int,
        current_text: str,
        shift_active: bool = False,
    ) -> Tuple[str, bool, bool]:
        """Handle keyboard selection for text input steps."""
        if step == "url":
            return self.char_keyboard.handle_selection(
                cursor_position,
                current_text,
                char_set="url",
                shift_active=shift_active,
            )
        elif step == "name":
            return self.char_keyboard.handle_selection(
                cursor_position,
                current_text,
                char_set="default",
                shift_active=shift_active,
            )
        # Note: "folder" step uses folder browser modal instead of keyboard
        return current_text, False, False


# Default instance
ia_collection_modal = IACollectionModal()
