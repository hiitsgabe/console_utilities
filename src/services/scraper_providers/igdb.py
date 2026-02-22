"""
IGDB (Internet Game Database) API provider for game artwork.

Uses Twitch OAuth2 client_credentials flow for authentication.
API Documentation: https://api-docs.igdb.com/
"""

import time
import traceback
import requests
from typing import List, Tuple, Dict, Any, Optional

from .base_provider import BaseProvider, GameSearchResult, GameImage


class IGDBProvider(BaseProvider):
    """
    IGDB API provider (powered by Twitch).

    Requires Twitch Client ID and Client Secret.
    Rate limit: 4 requests/second.
    """

    AUTH_URL = "https://id.twitch.tv/oauth2/token"
    BASE_URL = "https://api.igdb.com/v4"
    IMAGE_BASE_URL = "https://images.igdb.com/igdb/image/upload"

    IMAGE_TYPES = [
        "box-2D",
        "screenshot",
        "fanart",
    ]

    # IGDB image size presets
    IMAGE_SIZES = {
        "thumb": "t_thumb",  # 90x90
        "cover_small": "t_cover_small",  # 90x128
        "cover_big": "t_cover_big",  # 264x374
        "screenshot_med": "t_screenshot_med",  # 569x320
        "screenshot_big": "t_screenshot_big",  # 889x500
        "screenshot_huge": "t_screenshot_huge",  # 1280x720
        "720p": "t_720p",  # 1280x720
        "1080p": "t_1080p",  # 1920x1080
    }

    def __init__(self, client_id: str = "", client_secret: str = ""):
        """
        Initialize IGDB provider.

        Args:
            client_id: Twitch application Client ID
            client_secret: Twitch application Client Secret
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0
        self._last_request_time: float = 0

    @property
    def name(self) -> str:
        return "IGDB"

    @property
    def requires_auth(self) -> bool:
        return True

    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def _get_access_token(self) -> Tuple[bool, str]:
        """
        Get a valid access token, refreshing if expired.

        Returns:
            Tuple of (success, error_message)
        """
        if self._access_token and time.time() < self._token_expires_at:
            return True, ""

        if not self.is_configured():
            return False, "IGDB credentials not configured"

        try:
            response = requests.post(
                self.AUTH_URL,
                params={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "client_credentials",
                },
                timeout=15,
            )

            if response.status_code != 200:
                return (
                    False,
                    f"Auth failed: {response.status_code}",
                )

            data = response.json()
            self._access_token = data.get("access_token")
            expires_in = data.get("expires_in", 0)
            # Refresh 5 minutes before actual expiry
            self._token_expires_at = time.time() + expires_in - 300

            if not self._access_token:
                return False, "No access token in response"

            return True, ""

        except requests.Timeout:
            return False, "Auth request timed out"
        except requests.RequestException as e:
            return False, f"Auth network error: {str(e)}"
        except Exception as e:
            return False, f"Auth error: {str(e)}"

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with auth token."""
        return {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {self._access_token}",
        }

    def _api_request(self, endpoint: str, body: str) -> Tuple[bool, Any, str]:
        """
        Make an authenticated POST request to the IGDB API.

        Args:
            endpoint: API endpoint (e.g., "games", "covers")
            body: Apicalypse query body

        Returns:
            Tuple of (success, response_data, error)
        """
        success, error = self._get_access_token()
        if not success:
            return False, None, error

        # Rate limit: max 4 requests/second
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < 0.25:
            time.sleep(0.25 - elapsed)
        self._last_request_time = time.time()

        try:
            response = requests.post(
                f"{self.BASE_URL}/{endpoint}",
                headers=self._get_headers(),
                data=body,
                timeout=30,
            )

            if response.status_code == 401:
                # Token may have been invalidated, clear and retry
                self._access_token = None
                self._token_expires_at = 0
                return False, None, "Authentication failed"
            elif response.status_code == 429:
                return False, None, "Rate limit exceeded"
            elif response.status_code != 200:
                return (
                    False,
                    None,
                    f"API error: {response.status_code}",
                )

            return True, response.json(), ""

        except requests.Timeout:
            return False, None, "Request timed out"
        except requests.RequestException as e:
            return False, None, f"Network error: {str(e)}"
        except Exception as e:
            traceback.print_exc()
            return False, None, f"Error: {str(e)}"

    def _build_image_url(self, image_id: str, size: str = "cover_big") -> str:
        """
        Build an IGDB image URL from an image_id.

        Args:
            image_id: The image hash from the API
            size: Image size preset key

        Returns:
            Full image URL
        """
        size_prefix = self.IMAGE_SIZES.get(size, "t_cover_big")
        return f"{self.IMAGE_BASE_URL}/{size_prefix}/{image_id}.jpg"

    def search_game(
        self, name: str, system_id: str = ""
    ) -> Tuple[bool, List[GameSearchResult], str]:
        """Search for a game by name."""
        if not self.is_configured():
            return False, [], "IGDB credentials not configured"

        body = (
            f'search "{name}";'
            " fields name,platforms.name,"
            "first_release_date,summary,"
            "cover.image_id;"
            " where category = 0;"
            " limit 20;"
        )

        success, data, error = self._api_request("games", body)
        if not success:
            return False, [], error

        if not data:
            return True, [], ""

        results = []
        for game in data:
            result = self._parse_game_result(game)
            if result:
                results.append(result)

        return True, results, ""

    def _parse_game_result(self, game: Dict[str, Any]) -> Optional[GameSearchResult]:
        """Parse a game result from API response."""
        try:
            game_id = str(game.get("id", ""))
            name = game.get("name", "")

            # Get platform names
            platforms = game.get("platforms", [])
            platform_names = []
            for p in platforms:
                if isinstance(p, dict):
                    platform_names.append(p.get("name", ""))
            platform = ", ".join(platform_names[:3])
            if len(platform_names) > 3:
                platform += "..."

            # Parse release date (unix timestamp)
            release_date = ""
            timestamp = game.get("first_release_date")
            if timestamp:
                import datetime

                dt = datetime.datetime.fromtimestamp(
                    timestamp, tz=datetime.timezone.utc
                )
                release_date = dt.strftime("%Y-%m-%d")

            description = game.get("summary", "")
            if description and len(description) > 200:
                description = description[:200]

            # Get cover thumbnail URL
            thumbnail_url = ""
            cover = game.get("cover")
            if isinstance(cover, dict):
                image_id = cover.get("image_id", "")
                if image_id:
                    thumbnail_url = self._build_image_url(image_id, "cover_small")

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
        """Get available images for a game."""
        if not self.is_configured():
            return False, [], "IGDB credentials not configured"

        images = []

        # Fetch cover
        cover_body = f"fields image_id;" f" where game = {game_id};" f" limit 1;"
        success, data, error = self._api_request("covers", cover_body)
        if success and data:
            for item in data:
                image_id = item.get("image_id", "")
                if image_id:
                    images.append(
                        GameImage(
                            type="box-2D",
                            url=self._build_image_url(image_id, "cover_big"),
                            format="jpg",
                        )
                    )

        # Fetch artworks (fan art / promotional)
        art_body = f"fields image_id;" f" where game = {game_id};" f" limit 3;"
        success, data, error = self._api_request("artworks", art_body)
        if success and data:
            for item in data[:1]:  # Just first artwork
                image_id = item.get("image_id", "")
                if image_id:
                    images.append(
                        GameImage(
                            type="fanart",
                            url=self._build_image_url(image_id, "screenshot_huge"),
                            format="jpg",
                        )
                    )

        # Fetch screenshots
        ss_body = f"fields image_id;" f" where game = {game_id};" f" limit 5;"
        success, data, error = self._api_request("screenshots", ss_body)
        if success and data:
            for item in data[:2]:  # First 2 screenshots
                image_id = item.get("image_id", "")
                if image_id:
                    images.append(
                        GameImage(
                            type="screenshot",
                            url=self._build_image_url(image_id, "screenshot_big"),
                            format="jpg",
                        )
                    )

        if not images:
            return True, [], "No images found"

        return True, images, ""

    def get_image_types(self) -> List[str]:
        """Get supported image types."""
        return self.IMAGE_TYPES.copy()

    def get_image_type_label(self, image_type: str) -> str:
        """Get human-readable label for image type."""
        labels = {
            "box-2D": "Cover Art",
            "screenshot": "Screenshot",
            "fanart": "Artwork",
        }
        return labels.get(image_type, image_type.replace("-", " ").title())
