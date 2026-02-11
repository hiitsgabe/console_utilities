"""
Game scraper service - Orchestrates game artwork scraping.

Handles searching for games, downloading images, and organizing
files according to the selected frontend's requirements.
"""

import os
import re
import traceback
import requests
from typing import List, Tuple, Dict, Any, Optional

from .scraper_providers import (
    get_provider,
    BaseProvider,
    GameSearchResult,
    GameImage,
    GameVideo,
)


class ScraperService:
    """
    Main scraper orchestration service.

    Coordinates between scraper providers, downloads images,
    and organizes them according to frontend requirements.
    """

    # Image type mapping from provider types to frontend folder names
    IMAGE_TYPE_MAP = {
        # Provider type: {frontend: folder_name}
        "box-2D": {
            "emulationstation_base": "images",
            "esde_android": "covers",
            "retroarch": "Named_Boxarts",
            "pegasus": "boxFront",
        },
        "box-3D": {
            "emulationstation_base": "images",
            "esde_android": "3dboxes",
            "retroarch": "Named_Boxarts",
            "pegasus": "boxFront",
        },
        "boxart": {
            "emulationstation_base": "images",
            "esde_android": "covers",
            "retroarch": "Named_Boxarts",
            "pegasus": "boxFront",
        },
        "mixrbv1": {
            "emulationstation_base": "miximages",
            "esde_android": "miximages",
            "retroarch": None,
            "pegasus": "miximage",
        },
        "mixrbv2": {
            "emulationstation_base": "miximages",
            "esde_android": "miximages",
            "retroarch": None,
            "pegasus": "miximage",
        },
        "ss": {
            "emulationstation_base": "screenshots",
            "esde_android": "screenshots",
            "retroarch": "Named_Snaps",
            "pegasus": "screenshot",
        },
        "screenshot": {
            "emulationstation_base": "screenshots",
            "esde_android": "screenshots",
            "retroarch": "Named_Snaps",
            "pegasus": "screenshot",
        },
        "sstitle": {
            "emulationstation_base": "titlescreens",
            "esde_android": "titlescreens",
            "retroarch": "Named_Titles",
            "pegasus": "titlescreen",
        },
        "wheel": {
            "emulationstation_base": "wheels",
            "esde_android": "marquees",
            "retroarch": None,  # Not supported
            "pegasus": "logo",
        },
        "clearlogo": {
            "emulationstation_base": "wheels",
            "esde_android": "marquees",
            "retroarch": None,
            "pegasus": "logo",
        },
        "marquee": {
            "emulationstation_base": "marquees",
            "esde_android": "marquees",
            "retroarch": None,
            "pegasus": "marquee",
        },
        "fanart": {
            "emulationstation_base": "fanart",
            "esde_android": "fanart",
            "retroarch": None,
            "pegasus": "background",
        },
        "banner": {
            "emulationstation_base": "banners",
            "esde_android": "banners",
            "retroarch": None,
            "pegasus": "banner",
        },
    }

    PROVIDER_CHAIN = [
        "libretro",
        "screenscraper",
        "thegamesdb",
        "rawg",
        "igdb",
    ]

    # Video path mapping per frontend
    VIDEO_TYPE_MAP = {
        "emulationstation_base": "videos",
        "esde_android": "videos",
        "retroarch": None,  # RetroArch doesn't support videos
        "pegasus": "video",
    }

    def __init__(self, settings: Dict[str, Any]):
        """
        Initialize scraper service.

        Args:
            settings: Application settings dictionary
        """
        self.settings = settings
        self._provider: Optional[BaseProvider] = None
        self._last_search_provider: Optional[BaseProvider] = None

    @property
    def provider(self) -> BaseProvider:
        """Get the current scraper provider."""
        if self._provider is None:
            provider_name = self.settings.get("scraper_provider", "screenscraper")
            self._provider = get_provider(provider_name, self.settings)
        return self._provider

    def reset_provider(self):
        """Reset provider to force re-creation with new settings."""
        self._provider = None
        self._last_search_provider = None

    def _get_provider_chain(
        self,
    ) -> List[Tuple[str, BaseProvider]]:
        """
        Get ordered list of providers to try.

        Primary provider is always first. If fallback is
        disabled, only the primary is returned.
        """
        fallback = self.settings.get("scraper_fallback_enabled", True)
        primary = self.settings.get("scraper_provider", "libretro")

        if not fallback:
            return [(primary, self.provider)]

        # Build ordered list: primary first, then rest
        ordered = [primary]
        for p in self.PROVIDER_CHAIN:
            if p not in ordered:
                ordered.append(p)

        providers = []
        for name in ordered:
            try:
                p = get_provider(name, self.settings)
                if p.is_configured():
                    providers.append((name, p))
            except (ValueError, Exception):
                continue

        return providers

    def extract_game_name(self, rom_path: str) -> str:
        """
        Extract a clean game name from a ROM filename.

        Removes region tags, version info, and other common suffixes.

        Args:
            rom_path: Path to ROM file

        Returns:
            Cleaned game name for searching
        """
        # Get filename without path and extension
        filename = os.path.basename(rom_path)
        name, _ = os.path.splitext(filename)

        # Remove common patterns
        patterns = [
            r"\s*\([^)]*\)",  # (USA), (Europe), etc.
            r"\s*\[[^\]]*\]",  # [!], [b1], etc.
            r"\s*v\d+(\.\d+)*",  # v1.0, v2.1, etc.
            r"\s*Rev\s*\d+",  # Rev 1, Rev A
            r"\s*\(Rev\s*[^)]*\)",  # (Rev A)
            r"\s*-\s*Disc\s*\d+",  # - Disc 1
            r"\s*,\s*The$",  # ", The" at end
        ]

        for pattern in patterns:
            name = re.sub(pattern, "", name, flags=re.IGNORECASE)

        # Handle "Name, The" -> "The Name"
        if ", The" in name:
            name = "The " + name.replace(", The", "")

        # Clean up whitespace
        name = " ".join(name.split())

        return name.strip()

    def search_game(
        self, name: str, rom_path: str = ""
    ) -> Tuple[bool, List[GameSearchResult], str]:
        """
        Search for a game, trying fallback providers
        if the primary returns no results.

        Args:
            name: Game name to search for
            rom_path: Optional ROM path for per-provider
                name adaptation

        Returns:
            Tuple of (success, list of results, error)
        """
        providers = self._get_provider_chain()

        if not providers:
            return (
                False,
                [],
                "No configured scraper providers",
            )

        last_error = ""
        for provider_name, provider in providers:
            # Adapt game name per provider
            if provider_name == "libretro" and rom_path:
                search_name = os.path.splitext(os.path.basename(rom_path))[0]
            elif rom_path:
                search_name = self.extract_game_name(rom_path)
            else:
                search_name = name

            success, results, error = provider.search_game(search_name)

            if success and results:
                self._last_search_provider = provider
                return True, results, ""

            # Skip auth errors (user needs to fix config)
            if not success and error:
                err_lower = error.lower()
                if (
                    "auth" in err_lower
                    or "credential" in err_lower
                    or "api key" in err_lower
                ):
                    continue

            if error:
                last_error = f"{provider.name}: {error}"

        return (
            False,
            [],
            last_error or "No results from any provider",
        )

    def get_game_images(self, game_id: str) -> Tuple[bool, List[GameImage], str]:
        """
        Get available images for a game.

        Uses the provider that found the search result,
        since game IDs are provider-specific.

        Args:
            game_id: Provider-specific game identifier

        Returns:
            Tuple of (success, list of images, error)
        """
        provider = self._last_search_provider or self.provider
        return provider.get_game_images(game_id)

    def get_game_videos(self, game_id: str) -> Tuple[bool, List[GameVideo], str]:
        """
        Get available videos for a game.

        Args:
            game_id: Provider-specific game identifier

        Returns:
            Tuple of (success, list of videos, error)
        """
        provider = self._last_search_provider or self.provider
        if not provider.supports_videos():
            return True, [], ""
        return provider.get_game_videos(game_id)

    def get_video_output_path(
        self, rom_path: str, video_format: str = "mp4"
    ) -> Optional[str]:
        """
        Get the output path for a video based on frontend configuration.

        Args:
            rom_path: Path to the ROM file
            video_format: Video format extension (mp4)

        Returns:
            Full output path for the video, or None if not supported
        """
        frontend = self.settings.get("scraper_frontend", "emulationstation_base")
        folder_name = self.VIDEO_TYPE_MAP.get(frontend)
        if folder_name is None:
            return None

        rom_dir = os.path.dirname(rom_path)
        rom_name = os.path.splitext(os.path.basename(rom_path))[0]

        if frontend == "emulationstation_base":
            media_dir = os.path.join(rom_dir, folder_name)
            return os.path.join(media_dir, f"{rom_name}.{video_format}")
        elif frontend == "esde_android":
            media_base = self.settings.get("esde_media_path", "")
            if not media_base:
                return None
            platform = os.path.basename(rom_dir)
            media_dir = os.path.join(media_base, platform, folder_name)
            return os.path.join(media_dir, f"{rom_name}.{video_format}")
        elif frontend == "pegasus":
            media_dir = os.path.join(rom_dir, "media", rom_name)
            return os.path.join(media_dir, f"{folder_name}.{video_format}")

        return None

    def download_video(
        self, video: GameVideo, output_path: str, progress_callback=None
    ) -> Tuple[bool, str]:
        """
        Download a video to the specified path.

        Args:
            video: GameVideo object with URL
            output_path: Where to save the video
            progress_callback: Optional callback(downloaded, total)

        Returns:
            Tuple of (success, error message)
        """
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            headers = {"User-Agent": "ConsoleUtilities/1.0"}
            response = requests.get(
                video.url, stream=True, timeout=120, headers=headers
            )
            if response.status_code != 200:
                return False, f"Download failed: {response.status_code}"

            total_size = int(response.headers.get("content-length", 0))
            downloaded = 0

            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=16384):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total_size:
                        progress_callback(downloaded, total_size)

            return True, ""

        except requests.Timeout:
            return False, "Download timed out"
        except requests.RequestException as e:
            return False, f"Network error: {str(e)}"
        except OSError as e:
            return False, f"File error: {str(e)}"
        except Exception as e:
            traceback.print_exc()
            return False, f"Error: {str(e)}"

    def get_output_path(
        self, rom_path: str, image_type: str, image_format: str = "png"
    ) -> Optional[str]:
        """
        Get the output path for an image based on frontend configuration.

        Args:
            rom_path: Path to the ROM file
            image_type: Type of image (box-2D, screenshot, etc.)
            image_format: Image format extension (png, jpg)

        Returns:
            Full output path for the image, or None if type not supported
        """
        frontend = self.settings.get("scraper_frontend", "emulationstation_base")

        # Get folder name for this image type and frontend
        type_map = self.IMAGE_TYPE_MAP.get(image_type, {})
        folder_name = type_map.get(frontend)
        if folder_name is None:
            return None

        rom_dir = os.path.dirname(rom_path)
        rom_name = os.path.splitext(os.path.basename(rom_path))[0]

        if frontend == "emulationstation_base":
            # ./<type>/<romname>.png
            media_dir = os.path.join(rom_dir, folder_name)
            return os.path.join(media_dir, f"{rom_name}.{image_format}")

        elif frontend == "esde_android":
            # Use configured paths or default
            media_base = self.settings.get("esde_media_path", "")
            if not media_base:
                return None

            # Get platform from rom directory name
            platform = os.path.basename(rom_dir)
            media_dir = os.path.join(media_base, platform, folder_name)
            return os.path.join(media_dir, f"{rom_name}.{image_format}")

        elif frontend == "retroarch":
            # RetroArch uses Named_* folders in thumbnails directory
            thumbnails_base = self.settings.get("retroarch_thumbnails_path", "")
            if not thumbnails_base:
                return None

            # Get platform from rom directory name
            platform = os.path.basename(rom_dir)
            # RetroArch uses playlist name as folder
            media_dir = os.path.join(thumbnails_base, platform, folder_name)
            # RetroArch requires specific naming with underscores
            safe_name = rom_name.replace("&", "_").replace("/", "_")
            return os.path.join(media_dir, f"{safe_name}.{image_format}")

        elif frontend == "pegasus":
            # Pegasus: ./media/<gamename>/<type>.png
            media_dir = os.path.join(rom_dir, "media", rom_name)
            return os.path.join(media_dir, f"{folder_name}.{image_format}")

        return None

    def download_image(
        self, image: GameImage, output_path: str, progress_callback=None
    ) -> Tuple[bool, str]:
        """
        Download an image to the specified path.

        Args:
            image: GameImage object with URL
            output_path: Where to save the image
            progress_callback: Optional callback(downloaded, total)

        Returns:
            Tuple of (success, error message)
        """
        try:
            # Create directory if needed
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Download the image
            headers = {
                "User-Agent": "ConsoleUtilities/1.0",
            }
            response = requests.get(image.url, stream=True, timeout=60, headers=headers)
            if response.status_code != 200:
                return False, f"Download failed: {response.status_code}"

            total_size = int(response.headers.get("content-length", 0))
            downloaded = 0

            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total_size:
                        progress_callback(downloaded, total_size)

            return True, ""

        except requests.Timeout:
            return False, "Download timed out"
        except requests.RequestException as e:
            return False, f"Network error: {str(e)}"
        except OSError as e:
            return False, f"File error: {str(e)}"
        except Exception as e:
            traceback.print_exc()
            return False, f"Error: {str(e)}"

    def download_images(
        self,
        images: List[GameImage],
        rom_path: str,
        progress_callback=None,
    ) -> Tuple[bool, List[str], str]:
        """
        Download multiple images for a ROM.

        Args:
            images: List of GameImage objects to download
            rom_path: Path to the ROM file
            progress_callback: Optional callback(current_index, total, current_name)

        Returns:
            Tuple of (success, list of downloaded paths, error message)
        """
        downloaded_paths = []
        total = len(images)

        for i, image in enumerate(images):
            if progress_callback:
                progress_callback(i, total, image.type)

            # Get output path
            image_format = image.format if image.format else "png"
            output_path = self.get_output_path(rom_path, image.type, image_format)

            if output_path is None:
                continue  # Skip unsupported image types for this frontend

            # Download
            success, error = self.download_image(image, output_path)
            if success:
                downloaded_paths.append(output_path)
            else:
                # Continue with other images even if one fails
                print(f"Failed to download {image.type}: {error}")

        if progress_callback:
            progress_callback(total, total, "")

        return True, downloaded_paths, ""

    def check_image_exists(self, rom_path: str, image_types: list = None) -> bool:
        """
        Check if images already exist for this ROM.

        Args:
            rom_path: Path to ROM file
            image_types: Image types to check (defaults to box-2D and boxart)

        Returns:
            True if any matching image file exists
        """
        if image_types is None:
            image_types = ["box-2D", "boxart"]

        for image_type in image_types:
            for fmt in ("png", "jpg", "jpeg"):
                output_path = self.get_output_path(rom_path, image_type, fmt)
                if output_path and os.path.exists(output_path):
                    return True
        return False

    def get_platform_from_rom_path(self, rom_path: str) -> str:
        """
        Extract platform/system name from ROM path.

        Args:
            rom_path: Path to ROM file

        Returns:
            Platform name (directory name)
        """
        return os.path.basename(os.path.dirname(rom_path))


# Singleton instance
_scraper_service: Optional[ScraperService] = None


def get_scraper_service(settings: Dict[str, Any]) -> ScraperService:
    """
    Get or create the scraper service instance.

    Args:
        settings: Application settings

    Returns:
        ScraperService instance
    """
    global _scraper_service
    if _scraper_service is None:
        _scraper_service = ScraperService(settings)
    else:
        _scraper_service.settings = settings
    return _scraper_service
