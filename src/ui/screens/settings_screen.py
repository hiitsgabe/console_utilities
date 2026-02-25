"""
Settings screen - Application settings menu.
"""

import pygame
from typing import List, Dict, Any, Tuple, Optional, Set

from ui.theme import Theme, default_theme
from ui.templates.list_screen import ListScreenTemplate
from constants import APP_VERSION, BUILD_TARGET


class SettingsScreen:
    """
    Settings screen.

    Displays application settings with toggles
    and navigation options.
    """

    # Directories section
    DIRECTORIES_SECTION = [
        "--- DIRECTORIES ---",
        "Work Directory",
        "ROMs Directory",
    ]

    # Systems section
    SYSTEMS_SECTION = [
        "--- GAME BACKUP ---",
        "Remote Games Bkp File",
        "Add Game System",
        "Games Systems Preference",
    ]

    # View options section
    VIEW_OPTIONS_SECTION = [
        "--- VIEW OPTIONS ---",
        "Enable Box-art Display",
        "USA Games Only",
        "Show Download All Button",
        "Skip Installed Games",
    ]

    # PortMaster section (only shown for pygame builds)
    PORTMASTER_SECTION = [
        "--- PORTMASTER (BETA) ---",
        "Enable PortMaster (beta)",
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

    # Sports Roster section
    SPORTS_ROSTER_SECTION = [
        "--- SPORTS ROSTER ---",
        "Enable Sports Updater",
        "Roster Soccer Data Source",
        "API-Football Key",
        "Roster Hockey Data Source",
    ]

    # Scraper section
    SCRAPER_SECTION = [
        "--- ARTBOX GAMES SCRAPER ---",
        "Enable Scraper",
        "Scraper Frontend",
    ]

    # NSZ section
    NSZ_SECTION = [
        "--- NSZ ---",
        "Enable NSZ",
        "NSZ Keys",  # Only shown when NSZ is enabled
    ]

    # App section (last)
    APP_SECTION = [
        "--- APP ---",
        "Check for Updates",
    ]

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.template = ListScreenTemplate(theme)

    def _get_settings_items(
        self,
        settings: Dict[str, Any],
        data: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[List[str], Set[int]]:
        """
        Build the settings items list dynamically based on current settings.

        Args:
            settings: Current settings dictionary
            data: Optional system data list to check for list_systems entries

        Returns:
            Tuple of (items list, divider indices set)
        """
        items = []
        divider_indices = set()

        # Check if data has a list_systems entry (backup list available)
        has_backup_list = data and any(d.get("list_systems") is True for d in data)

        # Add Input section first (Remap Controller)
        divider_indices.add(len(items))
        items.extend(self.INPUT_SECTION)

        # Add Directories section
        divider_indices.add(len(items))
        items.extend(self.DIRECTORIES_SECTION)

        # Add Systems section
        divider_indices.add(len(items))
        items.append(self.SYSTEMS_SECTION[0])  # Divider
        items.append(self.SYSTEMS_SECTION[1])  # Remote Games Bkp File
        # Only show "Add Game System" when data has a list_systems entry
        if has_backup_list:
            items.append(self.SYSTEMS_SECTION[2])  # Add Game System
        items.append(self.SYSTEMS_SECTION[3])  # Games Systems Preference

        # Add View Options section
        divider_indices.add(len(items))
        items.extend(self.VIEW_OPTIONS_SECTION)

        # Add PortMaster section (only for pygame builds)
        if BUILD_TARGET in ("pygame", "source"):
            divider_indices.add(len(items))
            items.extend(self.PORTMASTER_SECTION)

        # Add Internet Archive section
        ia_enabled = settings.get("ia_enabled", False)
        divider_indices.add(len(items))
        items.append(self.IA_SECTION[0])  # Divider
        items.append(self.IA_SECTION[1])  # Enable toggle
        # Only show login if IA is enabled
        if ia_enabled:
            items.append(self.IA_SECTION[2])  # Login

        # Add Sports Roster section
        sports_roster_enabled = settings.get("sports_roster_enabled", False)
        divider_indices.add(len(items))
        items.append(self.SPORTS_ROSTER_SECTION[0])
        items.append(self.SPORTS_ROSTER_SECTION[1])
        if sports_roster_enabled:
            items.append(self.SPORTS_ROSTER_SECTION[2])  # Roster Soccer Data Source
            if settings.get("sports_roster_provider", "espn") == "api_football":
                items.append(self.SPORTS_ROSTER_SECTION[3])  # API-Football Key
            items.append(self.SPORTS_ROSTER_SECTION[4])  # Roster Hockey Data Source

        # Add Scraper section
        scraper_enabled = settings.get("scraper_enabled", False)
        divider_indices.add(len(items))
        items.append(self.SCRAPER_SECTION[0])
        items.append(self.SCRAPER_SECTION[1])
        if scraper_enabled:
            items.append(self.SCRAPER_SECTION[2])  # Scraper Frontend

        # Add NSZ section
        nsz_enabled = settings.get("nsz_enabled", False)
        divider_indices.add(len(items))
        items.append(self.NSZ_SECTION[0])  # Divider
        items.append(self.NSZ_SECTION[1])  # Enable toggle
        # Only show NSZ Keys if NSZ is enabled
        if nsz_enabled:
            items.append(self.NSZ_SECTION[2])  # NSZ Keys

        # Add App section (last)
        divider_indices.add(len(items))
        items.extend(self.APP_SECTION)

        return items, divider_indices

    def render(
        self,
        screen: pygame.Surface,
        highlighted: int,
        settings: Dict[str, Any],
        data: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[Optional[pygame.Rect], List[pygame.Rect], int]:
        """
        Render the settings screen.

        Args:
            screen: Surface to render to
            highlighted: Currently highlighted index
            settings: Current settings dictionary
            data: Optional system data list

        Returns:
            Tuple of (back_button_rect, item_rects, scroll_offset)
        """
        # Build items dynamically based on settings
        settings_items, divider_indices = self._get_settings_items(settings, data)

        # Build items with current values
        items = []
        for i, item in enumerate(settings_items):
            if i in divider_indices:
                items.append(item)
            elif item == "Enable Box-art Display":
                value = "ON" if settings.get("enable_boxart", True) else "OFF"
                items.append((item, value))
            elif item == "USA Games Only":
                value = "ON" if settings.get("usa_only", False) else "OFF"
                items.append((item, value))
            elif item == "Show Download All Button":
                value = "ON" if settings.get("show_download_all", False) else "OFF"
                items.append((item, value))
            elif item == "Skip Installed Games":
                value = (
                    "ON"
                    if settings.get("exclude_installed_on_download_all", True)
                    else "OFF"
                )
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
            elif item == "Remote Games Bkp File":
                path = settings.get("archive_json_path", "")
                value = "Set" if path else "Not Set"
                items.append((item, value))
            elif item == "Enable PortMaster (beta)":
                value = "ON" if settings.get("portmaster_enabled", False) else "OFF"
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
            elif item == "Enable Sports Updater":
                value = "ON" if settings.get("sports_roster_enabled", False) else "OFF"
                items.append((item, value))
            elif item == "Roster Soccer Data Source":
                provider = settings.get("sports_roster_provider", "espn")
                provider_labels = {
                    "espn": "ESPN (Free)",
                    "api_football": "API-Football (Paid)",
                }
                items.append((item, provider_labels.get(provider, provider)))
            elif item == "API-Football Key":
                key = settings.get("api_football_key", "")
                if key:
                    value = "••••••" + key[-3:] if len(key) > 3 else "••••••"
                else:
                    value = "Not set"
                items.append((item, value))
            elif item == "Roster Hockey Data Source":
                nhl_provider = settings.get("nhl94_provider", "espn")
                nhl_labels = {
                    "espn": "ESPN (Current Season)",
                    "nhl": "NHL API (Historical)",
                }
                items.append((item, nhl_labels.get(nhl_provider, nhl_provider)))
            elif item == "Enable Scraper":
                value = "ON" if settings.get("scraper_enabled", False) else "OFF"
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
            elif item == "Enable NSZ":
                value = "ON" if settings.get("nsz_enabled", False) else "OFF"
                items.append((item, value))
            elif item == "Check for Updates":
                items.append((item, APP_VERSION))
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

    def get_setting_action(
        self,
        index: int,
        settings: Dict[str, Any],
        data: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """
        Get the action for a settings item.

        Args:
            index: Selected index
            settings: Current settings dictionary
            data: Optional system data list

        Returns:
            Action string
        """
        # Build items dynamically to match what's displayed
        settings_items, divider_indices = self._get_settings_items(settings, data)

        if index in divider_indices:
            return "divider"

        if index < len(settings_items):
            item = settings_items[index]
            actions = {
                "Remote Games Bkp File": "select_archive_json",
                "Work Directory": "select_work_dir",
                "ROMs Directory": "select_roms_dir",
                "NSZ Keys": "select_nsz_keys",
                "Remap Controller": "remap_controller",
                "Add Game System": "add_systems",
                "Games Systems Preference": "systems_settings",
                "Enable PortMaster (beta)": "toggle_portmaster_enabled",
                "Enable Internet Archive": "toggle_ia_enabled",
                "Internet Archive Login": "ia_login",
                "Enable Box-art Display": "toggle_boxart",
                "USA Games Only": "toggle_usa_only",
                "Show Download All Button": "toggle_download_all",
                "Skip Installed Games": "toggle_exclude_installed",
                "Enable Sports Updater": "toggle_sports_roster_enabled",
                "Roster Soccer Data Source": "toggle_roster_provider",
                "API-Football Key": "edit_api_football_key",
                "Roster Hockey Data Source": "toggle_nhl94_provider",
                "Enable Scraper": "toggle_scraper_enabled",
                "Scraper Frontend": "toggle_scraper_frontend",
                "Enable NSZ": "toggle_nsz_enabled",
                "Check for Updates": "check_for_updates",
            }
            return actions.get(item, "unknown")

        return "unknown"

    def get_max_items(
        self,
        settings: Dict[str, Any],
        data: Optional[List[Dict[str, Any]]] = None,
    ) -> int:
        """
        Get the maximum number of items based on current settings.

        Args:
            settings: Current settings dictionary
            data: Optional system data list

        Returns:
            Number of items
        """
        settings_items, _ = self._get_settings_items(settings, data)
        return len(settings_items)


# Default instance
settings_screen = SettingsScreen()
