"""
Scraper providers package.

Provides different game artwork scraping APIs.
"""

from .base_provider import (
    BaseProvider,
    ScraperResult,
    GameSearchResult,
    GameImage,
    GameVideo,
)
from .screenscraper import ScreenScraperProvider
from .thegamesdb import TheGamesDBProvider
from .libretro import LibretroProvider
from .rawg import RAWGProvider
from .igdb import IGDBProvider


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
    elif provider_name == "rawg":
        return RAWGProvider(
            api_key=settings.get("rawg_api_key", ""),
        )
    elif provider_name == "igdb":
        return IGDBProvider(
            client_id=settings.get("igdb_client_id", ""),
            client_secret=settings.get("igdb_client_secret", ""),
        )
    else:
        raise ValueError(f"Unknown provider: {provider_name}")


__all__ = [
    "BaseProvider",
    "ScraperResult",
    "GameSearchResult",
    "GameImage",
    "GameVideo",
    "LibretroProvider",
    "ScreenScraperProvider",
    "TheGamesDBProvider",
    "RAWGProvider",
    "IGDBProvider",
    "get_provider",
]
