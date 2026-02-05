"""
Image caching service for Console Utilities.
Handles async image loading, caching, and queue management for thumbnails.
"""

import os
import traceback
from io import BytesIO
from queue import Queue, Empty
from threading import Thread
from typing import Dict, Any, Optional, Callable, Tuple
from urllib.parse import urljoin

import pygame
import requests

from utils.logging import log_error
from constants import THUMBNAIL_SIZE, HIRES_IMAGE_SIZE


class ImageCache:
    """
    Manages image loading and caching for thumbnails and high-resolution images.

    Uses background threads to load images asynchronously and queues
    to safely pass them back to the main thread.
    """

    def __init__(self):
        """Initialize the image cache."""
        self._thumbnail_cache: Dict[str, Any] = {}
        self._thumbnail_queue: Queue = Queue()

        self._hires_cache: Dict[str, Any] = {}
        self._hires_queue: Queue = Queue()

    def get_thumbnail(
        self, game_item: Any, boxart_url: str, settings: Dict[str, Any]
    ) -> Optional[pygame.Surface]:
        """
        Get thumbnail for game, loading async if not cached.

        Args:
            game_item: Game item (string or dictionary)
            boxart_url: Base URL for box art images
            settings: Application settings

        Returns:
            pygame.Surface if available, None if not ready or disabled
        """
        # Check if box-art is enabled
        if not settings.get("enable_boxart", True):
            return None

        # Extract game name
        game_name = self._extract_game_name(game_item)

        # Generate cache key and image URL
        cache_key, image_url = self._get_cache_key_and_url(
            game_item, game_name, boxart_url, prefix=""
        )

        if cache_key is None:
            return None

        # Return cached image if available
        if cache_key in self._thumbnail_cache:
            cached = self._thumbnail_cache[cache_key]
            if cached != "loading":
                return cached
            return None

        # Start loading if not already in cache
        self._thumbnail_cache[cache_key] = "loading"

        if isinstance(game_item, dict) and game_item.get("banner_url"):
            # Direct URL format
            thread = Thread(
                target=self._load_image_async,
                args=(
                    image_url,
                    cache_key,
                    game_name,
                    THUMBNAIL_SIZE,
                    self._thumbnail_queue,
                ),
            )
        else:
            # Standard format - try multiple extensions
            base_name = os.path.splitext(game_name)[0]
            image_formats = [".png", ".jpg", ".jpeg", ".gif", ".bmp"]
            thread = Thread(
                target=self._load_image_with_fallback,
                args=(
                    boxart_url,
                    base_name,
                    image_formats,
                    cache_key,
                    game_name,
                    THUMBNAIL_SIZE,
                    self._thumbnail_queue,
                ),
            )

        thread.daemon = True
        thread.start()

        return None  # Not ready yet

    def get_hires_image(
        self, game_item: Any, boxart_url: str, settings: Dict[str, Any]
    ) -> Optional[pygame.Surface]:
        """
        Get high-resolution image for game detail modal.

        Args:
            game_item: Game item (string or dictionary)
            boxart_url: Base URL for box art images
            settings: Application settings

        Returns:
            pygame.Surface if available, "loading" string if loading, None if disabled
        """
        if not settings.get("enable_boxart", True):
            return None

        game_name = self._extract_game_name(game_item)

        cache_key, image_url = self._get_cache_key_and_url(
            game_item, game_name, boxart_url, prefix="hires_"
        )

        if cache_key is None:
            return None

        # Return cached high-res image if available
        if cache_key in self._hires_cache:
            cached = self._hires_cache[cache_key]
            if cached != "loading":
                return cached
            return "loading"

        # Start loading high-res image
        self._hires_cache[cache_key] = "loading"

        if isinstance(game_item, dict) and game_item.get("banner_url"):
            # Direct URL format
            thread = Thread(
                target=self._load_image_async,
                args=(
                    image_url,
                    cache_key,
                    game_name,
                    HIRES_IMAGE_SIZE,
                    self._hires_queue,
                ),
            )
        else:
            # Standard format - try different extensions
            base_name = os.path.splitext(game_name)[0]
            image_formats = [".png", ".jpg", ".jpeg", ".gif", ".bmp"]
            thread = Thread(
                target=self._load_hires_with_fallback,
                args=(boxart_url, base_name, image_formats, cache_key, game_name),
            )

        thread.daemon = True
        thread.start()

        return "loading"

    def update(self):
        """
        Process loaded images from background threads.
        Should be called from main thread each frame.
        """
        self._process_queue(self._thumbnail_queue, self._thumbnail_cache)
        self._process_queue(self._hires_queue, self._hires_cache)

    def clear(self):
        """Clear all cached images and queues."""
        self._thumbnail_cache.clear()
        self._hires_cache.clear()

        # Drain queues
        self._drain_queue(self._thumbnail_queue)
        self._drain_queue(self._hires_queue)

    def _extract_game_name(self, game_item: Any) -> str:
        """Extract game name from item."""
        if isinstance(game_item, str):
            return game_item
        elif isinstance(game_item, dict):
            if "name" in game_item:
                return game_item.get("name", "")
            elif "filename" in game_item:
                return game_item.get("filename", "")
            else:
                return str(game_item)
        return str(game_item)

    def _get_cache_key_and_url(
        self, game_item: Any, game_name: str, boxart_url: str, prefix: str = ""
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Generate cache key and image URL for a game item.

        Args:
            game_item: Game item
            game_name: Extracted game name
            boxart_url: Base URL for box art
            prefix: Prefix for cache key (e.g., "hires_")

        Returns:
            Tuple of (cache_key, image_url), both None if not applicable
        """
        if isinstance(game_item, dict) and game_item.get("banner_url"):
            image_url = game_item.get("banner_url") or game_item.get("icon_url")
            cache_key = f"{prefix}direct_{image_url}_{game_name}"
            return cache_key, image_url
        elif boxart_url:
            base_name = os.path.splitext(game_name)[0]
            image_url = urljoin(boxart_url, f"{base_name}.png")
            cache_key = f"{prefix}{boxart_url}_{game_name}"
            return cache_key, image_url

        return None, None

    def _load_image_async(
        self,
        url: str,
        cache_key: str,
        game_name: str,
        target_size: Tuple[int, int],
        queue: Queue,
    ):
        """Load image in background thread."""
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            image_data = BytesIO(response.content)
            image = pygame.image.load(image_data).convert_alpha()
            scaled_image = pygame.transform.smoothscale(image, target_size)

            queue.put((cache_key, scaled_image))

        except Exception as e:
            log_error(
                f"Failed to load image from {url}",
                type(e).__name__,
                traceback.format_exc(),
            )
            queue.put((cache_key, None))

    def _load_image_with_fallback(
        self,
        base_url: str,
        base_name: str,
        formats: list,
        cache_key: str,
        game_name: str,
        target_size: Tuple[int, int],
        queue: Queue,
    ):
        """Try loading image with different format extensions."""
        for fmt in formats:
            try:
                image_url = urljoin(base_url, f"{base_name}{fmt}")
                response = requests.get(image_url, timeout=5)
                response.raise_for_status()

                image_data = BytesIO(response.content)
                image = pygame.image.load(image_data).convert_alpha()
                scaled_image = pygame.transform.smoothscale(image, target_size)

                queue.put((cache_key, scaled_image))
                return

            except Exception:
                continue

        # All formats failed
        queue.put((cache_key, None))

    def _load_hires_with_fallback(
        self,
        base_url: str,
        base_name: str,
        formats: list,
        cache_key: str,
        game_name: str,
    ):
        """Try loading high-resolution image with different extensions."""
        for fmt in formats:
            try:
                url = f"{base_url}/{base_name}{fmt}"
                response = requests.get(url, timeout=10)
                response.raise_for_status()

                image_data = BytesIO(response.content)
                image = pygame.image.load(image_data)

                # Only scale down if extremely large
                original_size = image.get_size()
                max_dimension = max(original_size)

                if max_dimension > 800:
                    scale_factor = 800 / max_dimension
                    new_width = int(original_size[0] * scale_factor)
                    new_height = int(original_size[1] * scale_factor)
                    scaled_image = pygame.transform.smoothscale(
                        image, (new_width, new_height)
                    )
                else:
                    scaled_image = image

                self._hires_queue.put((cache_key, scaled_image))
                return

            except Exception:
                continue

        # Try to use thumbnail as fallback
        thumbnail_key = cache_key.replace("hires_", "")
        if thumbnail_key in self._thumbnail_cache:
            thumbnail = self._thumbnail_cache[thumbnail_key]
            if thumbnail and thumbnail != "loading":
                upscaled = pygame.transform.smoothscale(thumbnail, HIRES_IMAGE_SIZE)
                self._hires_queue.put((cache_key, upscaled))
                return

        self._hires_queue.put((cache_key, None))

    def _process_queue(self, queue: Queue, cache: Dict):
        """Process items from queue into cache."""
        while not queue.empty():
            try:
                cache_key, image = queue.get_nowait()
                cache[cache_key] = image
            except Empty:
                break

    def _drain_queue(self, queue: Queue):
        """Drain all items from a queue."""
        while not queue.empty():
            try:
                queue.get_nowait()
            except Empty:
                break


# Default instance for convenience
image_cache = ImageCache()
