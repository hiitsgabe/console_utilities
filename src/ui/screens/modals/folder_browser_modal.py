"""
Folder browser modal - File/folder selection dialog.
"""

import pygame
from typing import List, Dict, Any, Tuple, Optional

from ui.theme import Theme, default_theme
from ui.organisms.modal_frame import ModalFrame
from ui.organisms.menu_list import MenuList
from ui.molecules.action_button import ActionButton
from ui.atoms.text import Text


class FolderBrowserModal:
    """
    Folder browser modal.

    File and folder selection dialog for choosing
    directories, JSON files, keys files, etc.
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.modal_frame = ModalFrame(theme)
        self.menu_list = MenuList(theme)
        self.action_button = ActionButton(theme)
        self.text = Text(theme)

    def render(
        self,
        screen: pygame.Surface,
        current_path: str,
        items: List[Dict[str, Any]],
        highlighted: int,
        selection_type: str = "folder",  # "folder", "json", "keys", "nsz"
        focus_area: str = "list",  # "list" or "buttons"
        button_index: int = 0,  # 0 = Select, 1 = Cancel
    ) -> Tuple[
        pygame.Rect,
        List[pygame.Rect],
        Optional[pygame.Rect],
        Optional[pygame.Rect],
        Optional[pygame.Rect],
    ]:
        """
        Render the folder browser modal.

        Args:
            screen: Surface to render to
            current_path: Current directory path
            items: List of folder/file items
            highlighted: Currently highlighted index
            selection_type: What type of selection is expected

        Returns:
            Tuple of (modal_rect, item_rects, select_button_rect, cancel_button_rect, close_rect)
        """
        # Calculate modal size (nearly fullscreen)
        margin = 30
        width = screen.get_width() - margin * 2
        height = screen.get_height() - margin * 2

        modal_rect = pygame.Rect(margin, margin, width, height)

        # Render modal frame
        _, content_rect, close_rect = self.modal_frame.render(
            screen,
            modal_rect,
            title="Select " + selection_type.replace("_", " ").title(),
            show_close=True,
        )

        # Draw current path
        path_y = content_rect.top
        self.text.render(
            screen,
            current_path,
            (content_rect.left, path_y),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
            max_width=content_rect.width,
        )

        # List area (below path, above buttons)
        button_height = 44
        button_area_height = button_height + self.theme.padding_lg + self.theme.padding_sm
        list_rect = pygame.Rect(
            content_rect.left,
            path_y + self.theme.font_size_sm + self.theme.padding_sm,
            content_rect.width,
            content_rect.height
            - self.theme.font_size_sm
            - self.theme.padding_sm
            - button_area_height,
        )

        # Render folder list
        item_rects, _ = self.menu_list.render(
            screen,
            list_rect,
            items,
            highlighted,
            set(),
            item_height=45,
            get_label=self._get_item_label,
            get_secondary=self._get_item_type_label,
        )

        # Draw action buttons anchored to bottom of content area
        button_y = content_rect.bottom - button_height - self.theme.padding_sm
        button_width = 140
        button_spacing = self.theme.padding_lg

        # Select button
        select_label = self._get_select_label(selection_type)
        select_rect = pygame.Rect(
            content_rect.centerx - button_width - button_spacing // 2,
            button_y,
            button_width,
            button_height,
        )
        select_focused = focus_area == "buttons" and button_index == 0
        self.action_button.render_success(
            screen, select_rect, select_label, hover=select_focused
        )

        # Cancel button
        cancel_rect = pygame.Rect(
            content_rect.centerx + button_spacing // 2,
            button_y,
            button_width,
            button_height,
        )
        cancel_focused = focus_area == "buttons" and button_index == 1
        self.action_button.render_secondary(
            screen, cancel_rect, "Cancel", hover=cancel_focused
        )

        return modal_rect, item_rects, select_rect, cancel_rect, close_rect

    def _get_item_label(self, item: Dict[str, Any]) -> str:
        """Get display label for item."""
        name = item.get("name", "")
        item_type = item.get("type", "")

        # Add icon prefix based on type
        if item_type == "parent":
            return ".. (Parent Directory)"
        elif item_type == "create_folder":
            return "+ Create New Folder"
        elif item_type == "folder":
            return f"[DIR] {name}"
        else:
            return name

    def _get_item_type_label(self, item: Dict[str, Any]) -> str:
        """Get type label for item."""
        item_type = item.get("type", "")
        type_labels = {
            "folder": "Folder",
            "parent": "",
            "create_folder": "",
            "keys_file": ".keys",
            "json_file": ".json",
            "nsz_file": ".nsz",
            "zip_file": ".zip",
            "rar_file": ".rar",
            "7z_file": ".7z",
            "file": "File",
        }
        return type_labels.get(item_type, "")

    def _get_select_label(self, selection_type: str) -> str:
        """Get select button label based on selection type."""
        labels = {
            "folder": "Select",
            "work_dir": "Select",
            "roms_dir": "Select",
            "json": "Select JSON",
            "keys": "Select Keys",
            "nsz": "Convert",
            "archive_json": "Select JSON",
            "nsz_keys": "Select Keys",
            "system_folder": "Select",
            "extract_zip": "Extract",
            "extract_rar": "Extract",
            "extract_7z": "Extract",
        }
        return labels.get(selection_type, "Select")


# Default instance
folder_browser_modal = FolderBrowserModal()
