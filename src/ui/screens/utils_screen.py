"""
Utils screen - Utility functions menu.
"""

import os
import pygame
from typing import List, Tuple, Optional, Set, Dict, Any
from xml.etree import ElementTree as ET

from ui.theme import Theme, default_theme
from ui.templates.list_screen import ListScreenTemplate
from constants import SCRIPT_DIR


class UtilsScreen:
    """
    Utils screen.

    Displays utility functions like direct download
    and NSZ conversion.
    """

    # System section items
    SYSTEM_SECTION_ITEMS = [
        "--- SYSTEM ---",  # Divider
        "System Information",
    ]

    # Download section items
    DOWNLOAD_SECTION_ITEMS = [
        "--- DOWNLOAD ---",  # Divider
        "Download from URL",
    ]

    # Internet Archive section items (only shown when IA is enabled)
    IA_SECTION_ITEMS = [
        "--- INTERNET ARCHIVE ---",  # Divider
        "Download from Internet Archive",
        "Add Internet Archive Collection",
    ]

    # Extraction section items
    EXTRACTION_SECTION_ITEMS = [
        "--- EXTRACTION ---",  # Divider
        "Extract ZIP File",
        "Extract RAR File",
    ]

    # File management section items
    FILE_MANAGEMENT_SECTION_ITEMS = [
        "--- FILE MANAGEMENT ---",  # Divider
        "Dedupe Games",
        "Clean File Names",
        "Ghost File Cleaner",
    ]

    # Steam section items
    STEAM_SECTION_ITEMS = [
        "--- STEAM ---",  # Divider
        "Steam Shortcut Creator",
    ]

    # NSZ section items (only shown when NSZ is enabled)
    NSZ_SECTION_ITEMS = [
        "--- NSZ ---",  # Divider
        "NSZ to NSP Converter",
    ]

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.template = ListScreenTemplate(theme)

    def _get_utils_items(self, settings: Dict[str, Any]) -> Tuple[List[str], Set[int]]:
        """
        Build the utils items list dynamically based on settings.

        Args:
            settings: Current settings dictionary

        Returns:
            Tuple of (items list, divider indices set)
        """
        items = []
        divider_indices = set()

        # Add system section (first)
        divider_indices.add(len(items))
        items.extend(self.SYSTEM_SECTION_ITEMS)

        # Only offer the frontend link while the app is not registered yet
        if not self._is_linked_to_frontend(settings):
            items.append("Link App to Frontend")

        # Add download section
        divider_indices.add(len(items))
        items.extend(self.DOWNLOAD_SECTION_ITEMS)

        # Add IA section
        divider_indices.add(len(items))
        items.extend(self.IA_SECTION_ITEMS)

        # Add extraction section
        divider_indices.add(len(items))
        items.extend(self.EXTRACTION_SECTION_ITEMS)

        # Add file management section
        divider_indices.add(len(items))
        items.extend(self.FILE_MANAGEMENT_SECTION_ITEMS)

        # Add Steam section
        divider_indices.add(len(items))
        items.extend(self.STEAM_SECTION_ITEMS)

        # Add NSZ section if enabled
        if settings.get("nsz_enabled", False):
            divider_indices.add(len(items))
            items.extend(self.NSZ_SECTION_ITEMS)

        return items, divider_indices

    def _is_linked_to_frontend(self, settings: Dict[str, Any]) -> bool:
        """Check if the app is already registered in the frontend gamelist.xml."""
        from constants import BUILD_TARGET

        roms_dir = settings.get("roms_dir", "")
        if not roms_dir:
            return False

        build_folder = BUILD_TARGET if BUILD_TARGET != "source" else "pygame"
        gamelist_path = os.path.join(roms_dir, build_folder, "gamelist.xml")

        if not os.path.exists(gamelist_path):
            return False

        pygame_file = None
        try:
            for f in os.listdir(SCRIPT_DIR):
                if f.endswith(".pygame"):
                    pygame_file = f
                    break
        except OSError:
            pass

        if not pygame_file:
            pygame_file = "console_utils.pygame"

        game_path = f"./{pygame_file}"

        try:
            tree = ET.parse(gamelist_path)
            root = tree.getroot()
            for game in root.findall("game"):
                path_elem = game.find("path")
                if path_elem is not None and path_elem.text == game_path:
                    return True
        except (ET.ParseError, OSError):
            pass

        return False

    def render(
        self, screen: pygame.Surface, highlighted: int, settings: Dict[str, Any]
    ) -> Tuple[Optional[pygame.Rect], List[pygame.Rect], int]:
        """
        Render the utils screen.

        Args:
            screen: Surface to render to
            highlighted: Currently highlighted index
            settings: Current settings dictionary

        Returns:
            Tuple of (back_button_rect, item_rects, scroll_offset)
        """
        items, divider_indices = self._get_utils_items(settings)
        return self.template.render(
            screen,
            title="Utilities",
            items=items,
            highlighted=highlighted,
            selected=set(),
            show_back=True,
            item_height=40,
            item_spacing=8,
            divider_indices=divider_indices,
        )

    def get_util_action(self, index: int, settings: Dict[str, Any]) -> str:
        """
        Get the action for a utils item.

        Args:
            index: Selected index
            settings: Current settings dictionary

        Returns:
            Action string
        """
        items, divider_indices = self._get_utils_items(settings)

        if index in divider_indices:
            return "divider"

        if index < len(items):
            item = items[index]
            actions = {
                "System Information": "system_info",
                "Link App to Frontend": "add_to_frontend",
                "Download from URL": "download_url",
                "Download from Internet Archive": "ia_download",
                "Add Internet Archive Collection": "ia_add_collection",
                "Extract ZIP File": "extract_zip",
                "Extract RAR File": "extract_rar",
                "Extract 7z File": "extract_7z",
                "Dedupe Games": "dedupe_games",
                "Clean File Names": "clean_filenames",
                "Ghost File Cleaner": "ghost_cleaner",
                "Steam Shortcut Creator": "steam_shortcut",
                "NSZ to NSP Converter": "nsz_converter",
            }
            return actions.get(item, "unknown")
        return "unknown"

    def get_max_items(self, settings: Dict[str, Any]) -> int:
        """
        Get the maximum number of items based on settings.

        Args:
            settings: Current settings dictionary

        Returns:
            Number of items
        """
        items, _ = self._get_utils_items(settings)
        return len(items)


# Default instance
utils_screen = UtilsScreen()
