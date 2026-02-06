"""
TheGamesDB API provider for game artwork.

API Documentation: https://api.thegamesdb.net/
"""

import traceback
import requests
from typing import List, Tuple, Dict, Any

from .base_provider import BaseProvider, GameSearchResult, GameImage


class TheGamesDBProvider(BaseProvider):
    """
    TheGamesDB API provider.

    Requires API key (request via their forums).
    Has limited requests (1K queries/month for free tier).
    """

    BASE_URL = "https://api.thegamesdb.net/v1"
    IMAGE_BASE_URL = "https://cdn.thegamesdb.net/images"

    IMAGE_TYPES = [
        "boxart",
        "screenshot",
        "fanart",
        "clearlogo",
        "banner",
    ]

    def __init__(self, api_key: str = ""):
        """
        Initialize TheGamesDB provider.

        Args:
            api_key: TheGamesDB API key
        """
        self.api_key = api_key

    @property
    def name(self) -> str:
        return "TheGamesDB"

    @property
    def requires_auth(self) -> bool:
        return True

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def search_game(self, name: str) -> Tuple[bool, List[GameSearchResult], str]:
        """
        Search for a game by name.

        Uses the Games/ByGameName endpoint.
        """
        if not self.is_configured():
            return False, [], "TheGamesDB API key not configured"

        try:
            params = {
                "apikey": self.api_key,
                "name": name,
                "include": "boxart",
            }

            response = requests.get(
                f"{self.BASE_URL}/Games/ByGameName",
                params=params,
                timeout=30,
            )

            if response.status_code == 401:
                return False, [], "Invalid API key"
            elif response.status_code == 403:
                return False, [], "API quota exceeded"
            elif response.status_code != 200:
                return False, [], f"API error: {response.status_code}"

            data = response.json()
            if data.get("code") != 200:
                return False, [], data.get("status", "Unknown error")

            games = data.get("data", {}).get("games", [])
            if not games:
                return True, [], ""

            # Get boxart info
            boxart_data = data.get("include", {}).get("boxart", {})
            base_url = boxart_data.get("base_url", {})
            small_url = base_url.get("small", "")
            boxart_map = boxart_data.get("data", {})

            results = []
            for game in games[:20]:  # Limit to 20 results
                result = self._parse_game_result(game, boxart_map, small_url)
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

    def _parse_game_result(
        self, game: Dict[str, Any], boxart_map: Dict, small_url: str
    ) -> GameSearchResult:
        """Parse a game result from API response."""
        try:
            game_id = str(game.get("id", ""))
            name = game.get("game_title", "")
            platform = ""  # Would need platform lookup
            release_date = game.get("release_date", "")
            description = game.get("overview", "")[:200] if game.get("overview") else ""

            # Get thumbnail from boxart
            thumbnail_url = ""
            game_boxart = boxart_map.get(game_id, [])
            if isinstance(game_boxart, list):
                for art in game_boxart:
                    if art.get("side") == "front":
                        thumbnail_url = small_url + art.get("filename", "")
                        break

            return GameSearchResult(
                id=game_id,
                name=name,
                platform=platform,
                release_date=release_date,
                description=description,
                thumbnail_url=thumbnail_url,
            )
        except Exception:
            return None

    def get_game_images(self, game_id: str) -> Tuple[bool, List[GameImage], str]:
        """
        Get available images for a game.

        Uses the Games/Images endpoint.
        """
        if not self.is_configured():
            return False, [], "TheGamesDB API key not configured"

        try:
            params = {
                "apikey": self.api_key,
                "games_id": game_id,
            }

            response = requests.get(
                f"{self.BASE_URL}/Games/Images",
                params=params,
                timeout=30,
            )

            if response.status_code == 401:
                return False, [], "Invalid API key"
            elif response.status_code == 403:
                return False, [], "API quota exceeded"
            elif response.status_code != 200:
                return False, [], f"API error: {response.status_code}"

            data = response.json()
            if data.get("code") != 200:
                return False, [], data.get("status", "Unknown error")

            images_data = data.get("data", {}).get("images", {}).get(game_id, [])
            base_url = data.get("data", {}).get("base_url", {})
            original_url = base_url.get("original", "")

            images = []
            seen_types = set()

            for img in images_data:
                img_type = img.get("type", "")
                if img_type not in self.IMAGE_TYPES:
                    continue

                filename = img.get("filename", "")
                if not filename:
                    continue

                # For boxart, prefer front side
                if img_type == "boxart":
                    side = img.get("side", "")
                    if side != "front" and "boxart" in seen_types:
                        continue
                    if side == "front":
                        # Remove existing back boxart if we found front
                        images = [i for i in images if i.type != "boxart"]

                if img_type in seen_types and img_type != "screenshot":
                    continue

                seen_types.add(img_type)

                url = original_url + filename
                image = GameImage(
                    type=img_type,
                    url=url,
                    region=img.get("side", ""),  # Use side as region for boxart
                    format=filename.split(".")[-1] if "." in filename else "",
                    extra={"resolution": img.get("resolution", "")},
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
            "boxart": "Box Art",
            "screenshot": "Screenshot",
            "fanart": "Fan Art",
            "clearlogo": "Clear Logo",
            "banner": "Banner",
        }
        return labels.get(image_type, image_type)
