"""
Scraper providers package.

Provides different game artwork scraping APIs.
"""

from .base_provider import BaseProvider, ScraperResult, GameSearchResult, GameImage
from .screenscraper import ScreenScraperProvider
from .thegamesdb import TheGamesDBProvider
from .libretro import LibretroProvider


def get_provider(provider_name: str, settings: dict) -> BaseProvider:
    """
    Factory function to get a scraper provider instance.

    Args:
        provider_name: Name of the provider
        settings: Application settings dict containing credentials

    Returns:
        Provider instance
    """
    if provider_name == "libretro":
        return LibretroProvider(
            system_folder=settings.get("current_system_folder", ""),
        )
    elif provider_name == "screenscraper":
        return ScreenScraperProvider(
            username=settings.get("screenscraper_username", ""),
            password=settings.get("screenscraper_password", ""),
        )
    elif provider_name == "thegamesdb":
        return TheGamesDBProvider(
            api_key=settings.get("thegamesdb_api_key", ""),
        )
    else:
        raise ValueError(f"Unknown provider: {provider_name}")


__all__ = [
    "BaseProvider",
    "ScraperResult",
    "GameSearchResult",
    "GameImage",
    "LibretroProvider",
    "ScreenScraperProvider",
    "TheGamesDBProvider",
    "get_provider",
]
