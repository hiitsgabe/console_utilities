"""
RAWG.io API provider for game artwork.

API Documentation: https://rawg.io/apidocs
"""

import traceback
import requests
from typing import List, Tuple, Dict, Any

from .base_provider import BaseProvider, GameSearchResult, GameImage


class RAWGProvider(BaseProvider):
    """
    RAWG.io game database provider.

    Requires a free API key (register at https://rawg.io/apidocs).
    """

    BASE_URL = "https://api.rawg.io/api"

    IMAGE_TYPES = [
        "boxart",
        "screenshot",
        "fanart",
    ]

    def __init__(self, api_key: str = ""):
        """
        Initialize RAWG provider.

        Args:
            api_key: RAWG API key
        """
        self.api_key = api_key

    @property
    def name(self) -> str:
        return "RAWG"

    @property
    def requires_auth(self) -> bool:
        return True

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def search_game(self, name: str) -> Tuple[bool, List[GameSearchResult], str]:
        """
        Search for a game by name.

        Uses the /games endpoint with search parameter.
        """
        if not self.is_configured():
            return False, [], "RAWG API key not configured"

        try:
            params = {
                "key": self.api_key,
                "search": name,
                "page_size": 10,
            }

            response = requests.get(
                f"{self.BASE_URL}/games",
                params=params,
                timeout=30,
            )

            if response.status_code == 401:
                return False, [], "Invalid API key"
            elif response.status_code == 403:
                return False, [], "API access forbidden"
            elif response.status_code == 429:
                return False, [], "API rate limit exceeded"
            elif response.status_code != 200:
                return False, [], f"API error: {response.status_code}"

            data = response.json()
            games = data.get("results", [])
            if not games:
                return True, [], ""

            results = []
            for game in games[:20]:
                result = self._parse_game_result(game)
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

    def _parse_game_result(self, game: Dict[str, Any]) -> GameSearchResult:
        """Parse a game result from API response."""
        try:
            game_id = str(game.get("id", ""))
            name = game.get("name", "")
            release_date = game.get("released", "") or ""
            thumbnail_url = game.get("background_image", "") or ""

            # Build platform string from platforms list
            platforms = game.get("platforms") or []
            platform_names = []
            for p in platforms:
                plat = p.get("platform", {})
                if plat.get("name"):
                    platform_names.append(plat["name"])
            platform = ", ".join(platform_names[:3])
            if len(platform_names) > 3:
                platform += f" +{len(platform_names) - 3}"

            return GameSearchResult(
                id=game_id,
                name=name,
                platform=platform,
                release_date=release_date,
                thumbnail_url=thumbnail_url,
            )
        except Exception:
            return None

    def get_game_images(self, game_id: str) -> Tuple[bool, List[GameImage], str]:
        """
        Get available images for a game.

        Fetches the main background image from game details and
        screenshots from the screenshots endpoint.
        """
        if not self.is_configured():
            return False, [], "RAWG API key not configured"

        try:
            images = []

            # Get game details for background_image
            params = {"key": self.api_key}
            response = requests.get(
                f"{self.BASE_URL}/games/{game_id}",
                params=params,
                timeout=30,
            )

            if response.status_code == 401:
                return False, [], "Invalid API key"
            elif response.status_code == 429:
                return False, [], "API rate limit exceeded"
            elif response.status_code != 200:
                return False, [], f"API error: {response.status_code}"

            data = response.json()

            # Main background image as boxart
            bg_image = data.get("background_image", "")
            if bg_image:
                fmt = bg_image.rsplit(".", 1)[-1] if "." in bg_image else "jpg"
                images.append(
                    GameImage(
                        type="boxart",
                        url=bg_image,
                        format=fmt,
                    )
                )

            # Additional background image as fanart
            bg_additional = data.get("background_image_additional", "")
            if bg_additional:
                fmt = (
                    bg_additional.rsplit(".", 1)[-1] if "." in bg_additional else "jpg"
                )
                images.append(
                    GameImage(
                        type="fanart",
                        url=bg_additional,
                        format=fmt,
                    )
                )

            # Get screenshots
            ss_response = requests.get(
                f"{self.BASE_URL}/games/{game_id}/screenshots",
                params=params,
                timeout=30,
            )

            if ss_response.status_code == 200:
                ss_data = ss_response.json()
                screenshots = ss_data.get("results", [])
                for ss in screenshots[:5]:
                    ss_url = ss.get("image", "")
                    if ss_url:
                        fmt = ss_url.rsplit(".", 1)[-1] if "." in ss_url else "jpg"
                        images.append(
                            GameImage(
                                type="screenshot",
                                url=ss_url,
                                format=fmt,
                            )
                        )

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
        }
        return labels.get(image_type, image_type)
