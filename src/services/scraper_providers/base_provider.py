"""
Base provider interface for game scraping APIs.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any


@dataclass
class ScraperResult:
    """Result from a scraper operation."""

    success: bool
    data: Any = None
    error: str = ""


@dataclass
class GameSearchResult:
    """A game found from search."""

    id: str
    name: str
    platform: str = ""
    release_date: str = ""
    description: str = ""
    thumbnail_url: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GameImage:
    """An available image for a game."""

    type: str  # box-2D, screenshot, wheel, etc.
    url: str
    region: str = ""  # us, eu, jp, etc.
    size: int = 0
    format: str = ""  # png, jpg
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GameVideo:
    """An available video for a game."""

    url: str
    region: str = ""  # us, eu, jp, etc.
    format: str = "mp4"
    size: int = 0
    normalized: bool = False  # True if video is normalized/compressed


class BaseProvider(ABC):
    """
    Abstract base class for scraper providers.

    All providers must implement these methods to search for games
    and retrieve available artwork.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider display name."""
        pass

    @property
    @abstractmethod
    def requires_auth(self) -> bool:
        """Whether this provider requires authentication."""
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if provider has required credentials configured."""
        pass

    @abstractmethod
    def search_game(
        self, name: str, system_id: str = ""
    ) -> Tuple[bool, List[GameSearchResult], str]:
        """
        Search for a game by name.

        Args:
            name: Game name to search for
            system_id: Optional system hint (e.g. "psx", "snes") to filter results

        Returns:
            Tuple of (success, list of results, error message)
        """
        pass

    @abstractmethod
    def get_game_images(self, game_id: str) -> Tuple[bool, List[GameImage], str]:
        """
        Get available images for a game.

        Args:
            game_id: Provider-specific game identifier

        Returns:
            Tuple of (success, list of images, error message)
        """
        pass

    @abstractmethod
    def get_image_types(self) -> List[str]:
        """
        Get list of supported image types.

        Returns:
            List of image type identifiers
        """
        pass

    def supports_videos(self) -> bool:
        """Whether this provider supports video downloads."""
        return False

    def get_game_videos(self, game_id: str) -> Tuple[bool, List[GameVideo], str]:
        """
        Get available videos for a game.

        Args:
            game_id: Provider-specific game identifier

        Returns:
            Tuple of (success, list of videos, error message)
        """
        return True, [], ""

    def get_image_type_label(self, image_type: str) -> str:
        """
        Get human-readable label for an image type.

        Args:
            image_type: Image type identifier

        Returns:
            Human-readable label
        """
        labels = {
            "box-2D": "Box Art (2D)",
            "box-3D": "Box Art (3D)",
            "boxart": "Box Art",
            "mixrbv1": "Mix V1 (Screenshot+Box+Logo)",
            "mixrbv2": "Mix V2 (Screenshot+Box+Logo+Media)",
            "screenshot": "Screenshot",
            "ss": "Screenshot",
            "sstitle": "Title Screen",
            "wheel": "Wheel/Logo",
            "clearlogo": "Clear Logo",
            "marquee": "Marquee",
            "fanart": "Fan Art",
            "banner": "Banner",
            "thumb": "Thumbnail",
        }
        return labels.get(image_type, image_type.replace("-", " ").title())
