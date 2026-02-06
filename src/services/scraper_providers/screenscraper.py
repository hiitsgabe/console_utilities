"""
ScreenScraper.fr API provider for game artwork.

API Documentation: https://www.screenscraper.fr/webapi2.php
"""

import base64
import hashlib
import traceback
import requests
from typing import List, Tuple, Dict, Any
from urllib.parse import quote

from .base_provider import BaseProvider, GameSearchResult, GameImage


class ScreenScraperProvider(BaseProvider):
    """
    ScreenScraper.fr API provider.

    Requires user account credentials from screenscraper.fr.
    Has generous rate limits (20K/day for registered users).
    """

    BASE_URL = "https://api.screenscraper.fr/api2"
    # Dev credentials - users should register their own on screenscraper.fr
    DEV_ID = "consoleutils"
    DEV_PASSWORD = "Q3Zlcld1MmRGSmM="  # base64 encoded

    IMAGE_TYPES = [
        "box-2D",
        "box-3D",
        "ss",
        "sstitle",
        "wheel",
        "marquee",
        "fanart",
    ]

    def __init__(self, username: str = "", password: str = ""):
        """
        Initialize ScreenScraper provider.

        Args:
            username: ScreenScraper account username
            password: ScreenScraper account password (base64 encoded)
        """
        self.username = username
        self.password = self._decode_password(password) if password else ""

    def _decode_password(self, encoded: str) -> str:
        """Decode base64 encoded password."""
        try:
            return base64.b64decode(encoded).decode("utf-8")
        except Exception:
            return encoded

    @property
    def name(self) -> str:
        return "ScreenScraper"

    @property
    def requires_auth(self) -> bool:
        return True

    def is_configured(self) -> bool:
        return bool(self.username and self.password)

    def _get_auth_params(self) -> Dict[str, str]:
        """Get authentication parameters for API requests."""
        dev_password = base64.b64decode(self.DEV_PASSWORD).decode("utf-8")
        params = {
            "devid": self.DEV_ID,
            "devpassword": dev_password,
            "softname": "ConsoleUtilities",
            "output": "json",
        }
        if self.username and self.password:
            params["ssid"] = self.username
            params["sspassword"] = self.password
        return params

    def search_game(self, name: str) -> Tuple[bool, List[GameSearchResult], str]:
        """
        Search for a game by name.

        Uses the jeuRecherche.php endpoint.
        """
        if not self.is_configured():
            return False, [], "ScreenScraper credentials not configured"

        try:
            params = self._get_auth_params()
            params["recherche"] = name

            response = requests.get(
                f"{self.BASE_URL}/jeuRecherche.php",
                params=params,
                timeout=30,
            )

            if response.status_code == 401:
                return False, [], "Authentication failed - check credentials"
            elif response.status_code == 404:
                return True, [], ""  # No results found
            elif response.status_code == 430:
                return False, [], "Too many requests - please wait"
            elif response.status_code != 200:
                return False, [], f"API error: {response.status_code}"

            data = response.json()
            if not data.get("response"):
                return True, [], ""

            jeux = data["response"].get("jeux", [])
            results = []

            for jeu in jeux[:20]:  # Limit to 20 results
                result = self._parse_game_result(jeu)
                if result:
                    results.append(result)

            return True, results, ""

        except requests.Timeout:
            return False, [], "Request timed out"
        except requests.RequestException as e:
            return False, [], f"Network error: {str(e)}"
        except Exception as e:
            traceback.print_exc()
            return False, [], f"Error: {str(e)}"

    def _parse_game_result(self, jeu: Dict[str, Any]) -> GameSearchResult:
        """Parse a game result from API response."""
        try:
            game_id = str(jeu.get("id", ""))
            names = jeu.get("noms", [])
            name = ""
            for n in names:
                if n.get("region") in ("us", "wor", "ss"):
                    name = n.get("text", "")
                    break
            if not name and names:
                name = names[0].get("text", "")

            system_info = jeu.get("systeme", {})
            platform = system_info.get("text", "")

            dates = jeu.get("dates", [])
            release_date = ""
            for d in dates:
                if d.get("region") in ("us", "wor"):
                    release_date = d.get("text", "")
                    break
            if not release_date and dates:
                release_date = dates[0].get("text", "")

            synopsis = jeu.get("synopsis", [])
            description = ""
            for s in synopsis:
                if s.get("langue") == "en":
                    description = s.get("text", "")
                    break
            if not description and synopsis:
                description = synopsis[0].get("text", "")

            medias = jeu.get("medias", [])
            thumbnail_url = ""
            for media in medias:
                if media.get("type") == "box-2D":
                    thumbnail_url = media.get("url", "")
                    break

            return GameSearchResult(
                id=game_id,
                name=name,
                platform=platform,
                release_date=release_date,
                description=description[:200] if description else "",
                thumbnail_url=thumbnail_url,
                extra={"rom_id": jeu.get("romid", "")},
            )
        except Exception:
            return None

    def get_game_images(self, game_id: str) -> Tuple[bool, List[GameImage], str]:
        """
        Get available images for a game.

        Uses the jeuInfos.php endpoint.
        """
        if not self.is_configured():
            return False, [], "ScreenScraper credentials not configured"

        try:
            params = self._get_auth_params()
            params["gameid"] = game_id

            response = requests.get(
                f"{self.BASE_URL}/jeuInfos.php",
                params=params,
                timeout=30,
            )

            if response.status_code == 401:
                return False, [], "Authentication failed"
            elif response.status_code == 404:
                return False, [], "Game not found"
            elif response.status_code != 200:
                return False, [], f"API error: {response.status_code}"

            data = response.json()
            jeu = data.get("response", {}).get("jeu", {})
            medias = jeu.get("medias", [])

            images = []
            seen_types = set()

            for media in medias:
                media_type = media.get("type", "")
                if media_type not in self.IMAGE_TYPES:
                    continue

                region = media.get("region", "")
                url = media.get("url", "")

                if not url:
                    continue

                # Prefer US region, then world, then any
                type_key = f"{media_type}_{region}"
                if media_type in seen_types and region not in ("us", "wor"):
                    continue

                if region in ("us", "wor"):
                    seen_types.add(media_type)

                # Check if we already have this type with better region
                existing = next((i for i in images if i.type == media_type), None)
                if existing:
                    if region in ("us", "wor") and existing.region not in ("us", "wor"):
                        images.remove(existing)
                    else:
                        continue

                image = GameImage(
                    type=media_type,
                    url=url,
                    region=region,
                    format=media.get("format", ""),
                    extra={"parent": media.get("parent", "")},
                )
                images.append(image)

            return True, images, ""

        except requests.Timeout:
            return False, [], "Request timed out"
        except requests.RequestException as e:
            return False, [], f"Network error: {str(e)}"
        except Exception as e:
            traceback.print_exc()
            return False, [], f"Error: {str(e)}"

    def get_image_types(self) -> List[str]:
        """Get supported image types."""
        return self.IMAGE_TYPES.copy()

    def get_image_type_label(self, image_type: str) -> str:
        """Get human-readable label for image type."""
        labels = {
            "box-2D": "Box Art (2D)",
            "box-3D": "Box Art (3D)",
            "ss": "Screenshot",
            "sstitle": "Title Screen",
            "wheel": "Wheel/Logo",
            "marquee": "Marquee",
            "fanart": "Fan Art",
        }
        return labels.get(image_type, image_type)
