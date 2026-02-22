"""
Libretro Thumbnails provider for game artwork.

Uses thumbnails.libretro.com which requires no authentication.
Images are accessed by constructing URLs from system name and game name.
"""

import os
import re
import traceback
import requests
from typing import List, Tuple
from urllib.parse import quote

from .base_provider import BaseProvider, GameSearchResult, GameImage


class LibretroProvider(BaseProvider):
    """
    Libretro Thumbnails provider.

    No authentication required. Constructs image URLs directly
    from system name and game name, verifying with HEAD requests.
    """

    BASE_URL = "https://thumbnails.libretro.com"

    IMAGE_TYPES = ["boxart", "screenshot", "sstitle", "wheel"]

    # Maps our image type to Libretro folder name
    IMAGE_TYPE_FOLDERS = {
        "boxart": "Named_Boxarts",
        "screenshot": "Named_Snaps",
        "sstitle": "Named_Titles",
        "wheel": "Named_Logos",
    }

    # Maps roms_folder to Libretro system name
    SYSTEM_MAP = {
        "psx": "Sony - PlayStation",
        "ps2": "Sony - PlayStation 2",
        "psp": "Sony - PlayStation Portable",
        "gb": "Nintendo - Game Boy",
        "gbc": "Nintendo - Game Boy Color",
        "gba": "Nintendo - Game Boy Advance",
        "nds": "Nintendo - Nintendo DS",
        "n3ds": "Nintendo - Nintendo 3DS",
        "nes": "Nintendo - Nintendo Entertainment System",
        "snes": ("Nintendo - Super Nintendo Entertainment System"),
        "n64": "Nintendo - Nintendo 64",
        "gc": "Nintendo - GameCube",
        "wii": "Nintendo - Wii",
        "wiiu": "Nintendo - Wii U",
        "genesis": "Sega - Mega Drive - Genesis",
        "gamegear": "Sega - Game Gear",
        "saturn": "Sega - Saturn",
        "dreamcast": "Sega - Dreamcast",
        "3do": "The 3DO Company - 3DO",
        "colecovision": "Coleco - ColecoVision",
        "intellivision": "Mattel - Intellivision",
        "xbox": "Microsoft - Xbox",
    }

    IMAGE_TYPE_LABELS = {
        "boxart": "Box Art",
        "screenshot": "Screenshot",
        "sstitle": "Title Screen",
        "wheel": "Logo",
    }

    def __init__(self, system_folder: str = ""):
        """
        Initialize Libretro provider.

        Args:
            system_folder: The roms_folder value to resolve
                the Libretro system name.
        """
        self.system_folder = system_folder

    @property
    def name(self) -> str:
        return "Libretro Thumbnails"

    @property
    def requires_auth(self) -> bool:
        return False

    def is_configured(self) -> bool:
        return bool(self.system_folder and self.system_folder in self.SYSTEM_MAP)

    def _get_system_name(self) -> str:
        """Get the Libretro system name."""
        return self.SYSTEM_MAP.get(self.system_folder, "")

    def _clean_game_name(self, name: str) -> str:
        """
        Clean a game name for URL construction.

        Preserves parenthetical tags (region, disc info)
        as required by Libretro's no-intro naming convention.
        Only removes square bracket tags like [!], [b1].
        """
        # Remove file extension if present
        name_base, _ = os.path.splitext(name)

        # Only remove square bracket tags
        name_base = re.sub(r"\s*\[[^\]]*\]", "", name_base)

        # Clean up whitespace
        name_base = " ".join(name_base.split())

        return name_base.strip()

    def _build_image_url(self, system: str, folder: str, game_name: str) -> str:
        """Build a Libretro thumbnail URL."""
        encoded_name = quote(game_name, safe="")
        encoded_sys = quote(system, safe="")
        return f"{self.BASE_URL}/{encoded_sys}" f"/{folder}/{encoded_name}.png"

    def _check_url_exists(self, url: str) -> bool:
        """Check if a URL exists via HEAD request."""
        try:
            response = requests.head(
                url,
                timeout=10,
                allow_redirects=True,
                headers={
                    "User-Agent": "ConsoleUtilities/1.0",
                },
            )
            return response.status_code == 200
        except requests.RequestException:
            return False

    def _get_name_variations(self, name: str) -> List[str]:
        """Get variations of a game name to try."""
        variations = [name]

        # Check if name already has region tags
        has_region = bool(re.search(r"\([^)]+\)", name))

        if has_region:
            # Also try without region tags as fallback
            stripped = re.sub(r"\s*\([^)]*\)", "", name).strip()
            if stripped and stripped != name:
                variations.append(stripped)
        else:
            # Try appending common region tags
            for region in [
                "(USA)",
                "(USA, Europe)",
                "(Europe)",
                "(World)",
            ]:
                variations.append(f"{name} {region}")

        # Try with/without "The " prefix
        if not name.startswith("The "):
            variations.append("The " + name)
        if name.startswith("The "):
            variations.append(name[4:])

        # Try replacing "&" with "and" and vice versa
        if "&" in name:
            variations.append(name.replace("&", "and"))
        if " and " in name.lower():
            variations.append(
                re.sub(
                    r"\band\b",
                    "&",
                    name,
                    flags=re.IGNORECASE,
                )
            )

        return variations

    def search_game(
        self, name: str, system_id: str = ""
    ) -> Tuple[bool, List[GameSearchResult], str]:
        """
        Search for a game by name.

        Constructs URLs and checks existence via HEAD
        requests since Libretro has no search API.
        """
        if not self.is_configured():
            system = self.system_folder or "unknown"
            return (
                False,
                [],
                f"System '{system}' not supported" " by Libretro Thumbnails",
            )

        system = self._get_system_name()
        if not system:
            return False, [], "System not found"

        try:
            cleaned_name = self._clean_game_name(name)
            if not cleaned_name:
                return True, [], ""

            # Try name variations
            for variation in self._get_name_variations(cleaned_name):
                boxart_url = self._build_image_url(system, "Named_Boxarts", variation)

                if self._check_url_exists(boxart_url):
                    result = GameSearchResult(
                        id=variation,
                        name=variation,
                        platform=system,
                        thumbnail_url=boxart_url,
                    )
                    return True, [result], ""

            return True, [], ""

        except requests.Timeout:
            return False, [], "Request timed out"
        except requests.RequestException as e:
            return False, [], f"Network error: {str(e)}"
        except Exception as e:
            traceback.print_exc()
            return False, [], f"Error: {str(e)}"

    def get_game_images(self, game_id: str) -> Tuple[bool, List[GameImage], str]:
        """
        Get available images for a game.

        game_id is the URL-encoded game name from search.
        """
        if not self.is_configured():
            return (
                False,
                [],
                "System not supported by Libretro",
            )

        system = self._get_system_name()
        if not system:
            return False, [], "System not found"

        try:
            images = []

            for img_type, folder in self.IMAGE_TYPE_FOLDERS.items():
                url = self._build_image_url(system, folder, game_id)

                if self._check_url_exists(url):
                    image = GameImage(
                        type=img_type,
                        url=url,
                        format="png",
                    )
                    images.append(image)

            return True, images, ""

        except requests.Timeout:
            return False, [], "Request timed out"
        except requests.RequestException as e:
            return (
                False,
                [],
                f"Network error: {str(e)}",
            )
        except Exception as e:
            traceback.print_exc()
            return False, [], f"Error: {str(e)}"

    def get_image_types(self) -> List[str]:
        """Get supported image types."""
        return self.IMAGE_TYPES.copy()

    def get_image_type_label(self, image_type: str) -> str:
        """Get human-readable label for image type."""
        return self.IMAGE_TYPE_LABELS.get(image_type, image_type)
