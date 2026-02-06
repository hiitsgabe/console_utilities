"""
Settings screen - Application settings menu.
"""

import pygame
from typing import List, Dict, Any, Tuple, Optional, Set

from ui.theme import Theme, default_theme
from ui.templates.list_screen import ListScreenTemplate


class SettingsScreen:
    """
    Settings screen.

    Displays application settings with toggles
    and navigation options.
    """

    # Directories section
    DIRECTORIES_SECTION = [
        "--- DIRECTORIES ---",
        "Select Archive Json",
        "Work Directory",
        "ROMs Directory",
    ]

    # Systems section
    SYSTEMS_SECTION = [
        "--- SYSTEMS ---",
        "Add Systems",
        "Systems Settings",
    ]

    # View options section
    VIEW_OPTIONS_SECTION = [
        "--- VIEW OPTIONS ---",
        "Enable Box-art Display",
        "View Type",
        "USA Games Only",
        "Show Download All Button",
    ]

    # Input section
    INPUT_SECTION = [
        "--- INPUT ---",
        "Remap Controller",
    ]

    # Internet Archive section items
    IA_SECTION = [
        "--- INTERNET ARCHIVE ---",
        "Enable Internet Archive",
        "Internet Archive Login",  # Only shown when IA is enabled
    ]

    # Scraper section
    SCRAPER_SECTION = [
        "--- SCRAPER ---",
        "Scraper Frontend",
        "Scraper Provider",
        "ScreenScraper Login",  # Only shown when provider = screenscraper
        "TheGamesDB API Key",  # Only shown when provider = thegamesdb
        "ES-DE Media Path",  # Only shown when frontend = esde_android
        "ES-DE Gamelists Path",  # Only shown when frontend = esde_android
        "RetroArch Thumbnails",  # Only shown when frontend = retroarch
    ]

    # NSZ section (last)
    NSZ_SECTION = [
        "--- NSZ ---",
        "Enable NSZ",
        "NSZ Keys",  # Only shown when NSZ is enabled
    ]

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.template = ListScreenTemplate(theme)

    def _get_settings_items(
        self, settings: Dict[str, Any]
    ) -> Tuple[List[str], Set[int]]:
        """
        Build the settings items list dynamically based on current settings.

        Args:
            settings: Current settings dictionary

        Returns:
            Tuple of (items list, divider indices set)
        """
        items = []
        divider_indices = set()

        # Add Directories section
        divider_indices.add(len(items))
        items.extend(self.DIRECTORIES_SECTION)

        # Add Systems section
        divider_indices.add(len(items))
        items.extend(self.SYSTEMS_SECTION)

        # Add View Options section
        divider_indices.add(len(items))
        items.extend(self.VIEW_OPTIONS_SECTION)

        # Add Input section
        divider_indices.add(len(items))
        items.extend(self.INPUT_SECTION)

        # Add Internet Archive section
        ia_enabled = settings.get("ia_enabled", False)
        divider_indices.add(len(items))
        items.append(self.IA_SECTION[0])  # Divider
        items.append(self.IA_SECTION[1])  # Enable toggle
        # Only show login if IA is enabled
        if ia_enabled:
            items.append(self.IA_SECTION[2])  # Login

        # Add Scraper section
        scraper_frontend = settings.get("scraper_frontend", "emulationstation_base")
        scraper_provider = settings.get("scraper_provider", "screenscraper")
        divider_indices.add(len(items))
        items.append(self.SCRAPER_SECTION[0])  # Divider
        items.append(self.SCRAPER_SECTION[1])  # Frontend
        items.append(self.SCRAPER_SECTION[2])  # Provider
        # Show provider-specific settings
        if scraper_provider == "screenscraper":
            items.append(self.SCRAPER_SECTION[3])  # ScreenScraper Login
        elif scraper_provider == "thegamesdb":
            items.append(self.SCRAPER_SECTION[4])  # TheGamesDB API Key
        # Show frontend-specific paths
        if scraper_frontend == "esde_android":
            items.append(self.SCRAPER_SECTION[5])  # ES-DE Media Path
            items.append(self.SCRAPER_SECTION[6])  # ES-DE Gamelists Path
        elif scraper_frontend == "retroarch":
            items.append(self.SCRAPER_SECTION[7])  # RetroArch Thumbnails

        # Add NSZ section (last)
        nsz_enabled = settings.get("nsz_enabled", False)
        divider_indices.add(len(items))
        items.append(self.NSZ_SECTION[0])  # Divider
        items.append(self.NSZ_SECTION[1])  # Enable toggle
        # Only show NSZ Keys if NSZ is enabled
        if nsz_enabled:
            items.append(self.NSZ_SECTION[2])  # NSZ Keys

        return items, divider_indices

    def render(
        self, screen: pygame.Surface, highlighted: int, settings: Dict[str, Any]
    ) -> Tuple[Optional[pygame.Rect], List[pygame.Rect], int]:
        """
        Render the settings screen.

        Args:
            screen: Surface to render to
            highlighted: Currently highlighted index
            settings: Current settings dictionary

        Returns:
            Tuple of (back_button_rect, item_rects, scroll_offset)
        """
        # Build items dynamically based on settings
        settings_items, divider_indices = self._get_settings_items(settings)

        # Build items with current values
        items = []
        for i, item in enumerate(settings_items):
            if i in divider_indices:
                items.append(item)
            elif item == "Enable Box-art Display":
                value = "ON" if settings.get("enable_boxart", True) else "OFF"
                items.append((item, value))
            elif item == "View Type":
                value = settings.get("view_type", "grid").capitalize()
                items.append((item, value))
            elif item == "USA Games Only":
                value = "ON" if settings.get("usa_only", False) else "OFF"
                items.append((item, value))
            elif item == "Show Download All Button":
                value = "ON" if settings.get("show_download_all", False) else "OFF"
                items.append((item, value))
            elif item == "Work Directory":
                path = settings.get("work_dir", "")
                short_path = self._shorten_path(path)
                items.append((item, short_path))
            elif item == "ROMs Directory":
                path = settings.get("roms_dir", "")
                short_path = self._shorten_path(path)
                items.append((item, short_path))
            elif item == "NSZ Keys":
                path = settings.get("nsz_keys_path", "")
                value = "Set" if path else "Not Set"
                items.append((item, value))
            elif item == "Select Archive Json":
                path = settings.get("archive_json_path", "")
                value = "Set" if path else "Not Set"
                items.append((item, value))
            elif item == "Enable Internet Archive":
                value = "ON" if settings.get("ia_enabled", False) else "OFF"
                items.append((item, value))
            elif item == "Internet Archive Login":
                email = settings.get("ia_email", "")
                if email:
                    # Truncate email if too long
                    if len(email) > 20:
                        value = email[:17] + "..."
                    else:
                        value = email
                else:
                    value = "Not logged in"
                items.append((item, value))
            elif item == "Enable NSZ":
                value = "ON" if settings.get("nsz_enabled", False) else "OFF"
                items.append((item, value))
            elif item == "Scraper Frontend":
                frontend = settings.get("scraper_frontend", "emulationstation_base")
                frontend_labels = {
                    "emulationstation_base": "ES Base",
                    "esde_android": "ES-DE Android",
                    "retroarch": "RetroArch",
                    "pegasus": "Pegasus",
                }
                items.append((item, frontend_labels.get(frontend, frontend)))
            elif item == "Scraper Provider":
                provider = settings.get("scraper_provider", "screenscraper")
                provider_labels = {
                    "screenscraper": "ScreenScraper",
                    "thegamesdb": "TheGamesDB",
                }
                items.append((item, provider_labels.get(provider, provider)))
            elif item == "ScreenScraper Login":
                username = settings.get("screenscraper_username", "")
                if username:
                    if len(username) > 15:
                        value = username[:12] + "..."
                    else:
                        value = username
                else:
                    value = "Not logged in"
                items.append((item, value))
            elif item == "TheGamesDB API Key":
                api_key = settings.get("thegamesdb_api_key", "")
                value = "Set" if api_key else "Not Set"
                items.append((item, value))
            elif item == "ES-DE Media Path":
                path = settings.get("esde_media_path", "")
                value = self._shorten_path(path) if path else "Not Set"
                items.append((item, value))
            elif item == "ES-DE Gamelists Path":
                path = settings.get("esde_gamelists_path", "")
                value = self._shorten_path(path) if path else "Not Set"
                items.append((item, value))
            elif item == "RetroArch Thumbnails":
                path = settings.get("retroarch_thumbnails_path", "")
                value = self._shorten_path(path) if path else "Not Set"
                items.append((item, value))
            else:
                items.append((item, ""))

        return self.template.render(
            screen,
            title="Settings",
            items=items,
            highlighted=highlighted,
            selected=set(),
            show_back=True,
            item_height=40,
            get_label=lambda x: x[0] if isinstance(x, tuple) else x,
            get_secondary=lambda x: x[1] if isinstance(x, tuple) else None,
            divider_indices=divider_indices,
            item_spacing=8,
        )

    def _shorten_path(self, path: str, max_length: int = 25) -> str:
        """Shorten a path for display."""
        if not path:
            return "Not Set"
        if len(path) <= max_length:
            return path

        # Show last parts of path
        parts = path.replace("\\", "/").split("/")
        result = ""
        for part in reversed(parts):
            if len(result) + len(part) + 1 <= max_length - 3:
                result = "/" + part + result if result else part
            else:
                break

        return "..." + result if result else "..." + path[-max_length + 3 :]

    def get_setting_action(self, index: int, settings: Dict[str, Any]) -> str:
        """
        Get the action for a settings item.

        Args:
            index: Selected index
            settings: Current settings dictionary

        Returns:
            Action string
        """
        # Build items dynamically to match what's displayed
        settings_items, divider_indices = self._get_settings_items(settings)

        if index in divider_indices:
            return "divider"

        if index < len(settings_items):
            item = settings_items[index]
            actions = {
                "Select Archive Json": "select_archive_json",
                "Work Directory": "select_work_dir",
                "ROMs Directory": "select_roms_dir",
                "NSZ Keys": "select_nsz_keys",
                "Remap Controller": "remap_controller",
                "Add Systems": "add_systems",
                "Systems Settings": "systems_settings",
                "Enable Internet Archive": "toggle_ia_enabled",
                "Internet Archive Login": "ia_login",
                "Enable Box-art Display": "toggle_boxart",
                "View Type": "toggle_view_type",
                "USA Games Only": "toggle_usa_only",
                "Show Download All Button": "toggle_download_all",
                "Enable NSZ": "toggle_nsz_enabled",
                "Scraper Frontend": "toggle_scraper_frontend",
                "Scraper Provider": "toggle_scraper_provider",
                "ScreenScraper Login": "screenscraper_login",
                "TheGamesDB API Key": "thegamesdb_api_key",
                "ES-DE Media Path": "select_esde_media_path",
                "ES-DE Gamelists Path": "select_esde_gamelists_path",
                "RetroArch Thumbnails": "select_retroarch_thumbnails",
            }
            return actions.get(item, "unknown")

        return "unknown"

    def get_max_items(self, settings: Dict[str, Any]) -> int:
        """
        Get the maximum number of items based on current settings.

        Args:
            settings: Current settings dictionary

        Returns:
            Number of items
        """
        settings_items, _ = self._get_settings_items(settings)
        return len(settings_items)


# Default instance
settings_screen = SettingsScreen()
