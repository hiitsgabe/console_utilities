"""Scraper menu screen - scraper actions and settings sub-menu."""

import os
import pygame
from typing import List, Dict, Any, Tuple, Optional, Set
from xml.etree import ElementTree as ET

from ui.theme import Theme, default_theme
from ui.templates.list_screen import ListScreenTemplate
from constants import SCRIPT_DIR


class ScraperMenuScreen:

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.template = ListScreenTemplate(theme)

    def _get_items(self, settings: Dict[str, Any]) -> Tuple[List[str], Set[int]]:
        """Build items list dynamically based on current settings."""
        items = []
        divider_indices = set()

        # Action items first (no divider)
        items.append("Scrape Game Images")
        items.append("Batch Scrape Folder")

        # Settings section
        scraper_frontend = settings.get("scraper_frontend", "emulationstation_base")
        scraper_provider = settings.get("scraper_provider", "libretro")

        divider_indices.add(len(items))
        items.append("--- SETTINGS ---")
        items.append("Scraper Provider")
        items.append("Provider Fallback")
        items.append("Parallel Downloads")

        # Provider-specific settings
        if scraper_provider == "screenscraper":
            items.append("Mixed Images")
            items.append("ScreenScraper Login")
        elif scraper_provider == "thegamesdb":
            items.append("TheGamesDB API Key")
        elif scraper_provider == "rawg":
            items.append("RAWG API Key")
        elif scraper_provider == "igdb":
            items.append("IGDB Login")

        # Frontend-specific paths
        if scraper_frontend == "esde_android":
            items.append("ES-DE Media Path")
            items.append("ES-DE Gamelists Path")
        elif scraper_frontend == "retroarch":
            items.append("RetroArch Thumbnails")

        # Only show "Link App to Frontend" if not already linked
        if not self._is_linked_to_frontend(settings):
            items.append("Link App to Frontend")

        return items, divider_indices

    def render(
        self, screen: pygame.Surface, highlighted: int, settings: Dict[str, Any]
    ) -> Tuple[Optional[pygame.Rect], List[pygame.Rect], int]:
        raw_items, divider_indices = self._get_items(settings)

        items = []
        for i, item in enumerate(raw_items):
            if i in divider_indices:
                items.append(item)
            elif item in ("Scrape Game Images", "Batch Scrape Folder", "Link App to Frontend"):
                items.append((item, ""))
            elif item == "Scraper Provider":
                provider = settings.get("scraper_provider", "libretro")
                labels = {
                    "libretro": "Libretro Thumbnails",
                    "screenscraper": "ScreenScraper",
                    "thegamesdb": "TheGamesDB",
                    "rawg": "RAWG",
                    "igdb": "IGDB (Twitch)",
                }
                items.append((item, labels.get(provider, provider)))
            elif item == "Provider Fallback":
                enabled = settings.get("scraper_fallback_enabled", True)
                items.append((item, "Enabled" if enabled else "Disabled"))
            elif item == "Parallel Downloads":
                items.append((item, str(settings.get("scraper_parallel_downloads", 1))))
            elif item == "Mixed Images":
                value = "ON" if settings.get("scraper_mixed_images", False) else "OFF"
                items.append((item, value))
            elif item == "ScreenScraper Login":
                username = settings.get("screenscraper_username", "")
                if username:
                    value = username[:12] + "..." if len(username) > 15 else username
                else:
                    value = "Not logged in"
                items.append((item, value))
            elif item == "TheGamesDB API Key":
                items.append((item, "Set" if settings.get("thegamesdb_api_key", "") else "Not Set"))
            elif item == "RAWG API Key":
                items.append((item, "Set" if settings.get("rawg_api_key", "") else "Not Set"))
            elif item == "IGDB Login":
                client_id = settings.get("igdb_client_id", "")
                if client_id:
                    value = client_id[:12] + "..." if len(client_id) > 15 else client_id
                else:
                    value = "Not configured"
                items.append((item, value))
            elif item == "ES-DE Media Path":
                path = settings.get("esde_media_path", "")
                items.append((item, self._shorten_path(path) if path else "Not Set"))
            elif item == "ES-DE Gamelists Path":
                path = settings.get("esde_gamelists_path", "")
                items.append((item, self._shorten_path(path) if path else "Not Set"))
            elif item == "RetroArch Thumbnails":
                path = settings.get("retroarch_thumbnails_path", "")
                items.append((item, self._shorten_path(path) if path else "Not Set"))
            else:
                items.append((item, ""))

        return self.template.render(
            screen,
            title="Scraper",
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

    def get_action(self, index: int, settings: Dict[str, Any]) -> str:
        items, divider_indices = self._get_items(settings)
        if index in divider_indices:
            return "divider"
        if 0 <= index < len(items):
            actions = {
                "Scrape Game Images": "scrape_images",
                "Batch Scrape Folder": "batch_scrape",
                "Scraper Provider": "toggle_scraper_provider",
                "Provider Fallback": "toggle_scraper_fallback",
                "Parallel Downloads": "cycle_parallel_downloads",
                "Mixed Images": "toggle_mixed_images",
                "ScreenScraper Login": "screenscraper_login",
                "TheGamesDB API Key": "thegamesdb_api_key",
                "RAWG API Key": "rawg_api_key",
                "IGDB Login": "igdb_login",
                "ES-DE Media Path": "select_esde_media_path",
                "ES-DE Gamelists Path": "select_esde_gamelists_path",
                "RetroArch Thumbnails": "select_retroarch_thumbnails",
                "Link App to Frontend": "add_to_frontend",
            }
            return actions.get(items[index], "unknown")
        return "unknown"

    def get_max_items(self, settings: Dict[str, Any]) -> int:
        items, _ = self._get_items(settings)
        return len(items)

    def _is_linked_to_frontend(self, settings: dict) -> bool:
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

    def _shorten_path(self, path: str, max_length: int = 25) -> str:
        """Shorten a path for display."""
        if not path:
            return "Not Set"
        if len(path) <= max_length:
            return path
        parts = path.replace("\\", "/").split("/")
        result = ""
        for part in reversed(parts):
            if len(result) + len(part) + 1 <= max_length - 3:
                result = "/" + part + result if result else part
            else:
                break
        return "..." + result if result else "..." + path[-max_length + 3:]


scraper_menu_screen = ScraperMenuScreen()
