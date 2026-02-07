"""
Utils screen - Utility functions menu.
"""

import pygame
from typing import List, Tuple, Optional, Set, Dict, Any

from ui.theme import Theme, default_theme
from ui.templates.list_screen import ListScreenTemplate


class UtilsScreen:
    """
    Utils screen.

    Displays utility functions like direct download
    and NSZ conversion.
    """

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

    # Scraper section items
    SCRAPER_SECTION_ITEMS = [
        "--- SCRAPER ---",  # Divider
        "Scrape Game Images",
        "Batch Scrape Folder",
    ]

    # File management section items
    FILE_MANAGEMENT_SECTION_ITEMS = [
        "--- FILE MANAGEMENT ---",  # Divider
        "Dedupe Games",
        "Clean File Names",
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

        # Add download section
        divider_indices.add(len(items))
        items.extend(self.DOWNLOAD_SECTION_ITEMS)

        # Add IA section if enabled
        if settings.get("ia_enabled", False):
            divider_indices.add(len(items))
            items.extend(self.IA_SECTION_ITEMS)

        # Add extraction section
        divider_indices.add(len(items))
        items.extend(self.EXTRACTION_SECTION_ITEMS)

        # Add scraper section
        divider_indices.add(len(items))
        items.extend(self.SCRAPER_SECTION_ITEMS)

        # Add file management section
        divider_indices.add(len(items))
        items.extend(self.FILE_MANAGEMENT_SECTION_ITEMS)

        # Add NSZ section if enabled
        if settings.get("nsz_enabled", False):
            divider_indices.add(len(items))
            items.extend(self.NSZ_SECTION_ITEMS)

        return items, divider_indices

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
                "Download from URL": "download_url",
                "Download from Internet Archive": "ia_download",
                "Add Internet Archive Collection": "ia_add_collection",
                "Extract ZIP File": "extract_zip",
                "Extract RAR File": "extract_rar",
                "Scrape Game Images": "scrape_images",
                "Batch Scrape Folder": "batch_scrape",
                "Dedupe Games": "dedupe_games",
                "Clean File Names": "clean_filenames",
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
