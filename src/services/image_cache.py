"""
Image caching service for Console Utilities.
Handles async image loading, caching, and queue management for thumbnails.
"""

import hashlib
import json
import os
import re
import traceback
from io import BytesIO
from queue import Queue, Empty
from threading import Thread, Lock, Event
from typing import Dict, Any, Optional, Tuple
from urllib.parse import quote, urljoin, unquote

import pygame
import requests

from utils.logging import log_error
from constants import THUMBNAIL_SIZE, HIRES_IMAGE_SIZE, SYSTEMS_CACHE_DIR


def _clean_name_for_matching(name: str) -> str:
    """Clean a game/thumbnail name for fuzzy matching.

    Strips extension, square brackets, parenthetical tags,
    normalizes whitespace, and lowercases.
    """
    # Remove common file extensions
    name = re.sub(
        r"\.(png|jpg|jpeg|gif|bmp|zip|bin|cue|iso|7z|rar)$",
        "",
        name,
        flags=re.IGNORECASE,
    )
    # Remove square bracket tags like [!], [b1]
    name = re.sub(r"\s*\[[^\]]*\]", "", name)
    # Remove parenthetical tags like (USA), (Rev 1)
    name = re.sub(r"\s*\([^)]*\)", "", name)
    # Normalize whitespace
    name = " ".join(name.split())
    return name.strip().lower()


class _ThumbnailListingCache:
    """Caches parsed directory listings from thumbnail servers.

    Fetches the HTML listing for a boxart base URL once, parses
    all available filenames, and builds a cleaned-name lookup dict
    so game names can be fuzzy-matched to thumbnail filenames.
    """

    def __init__(self):
        self._lock = Lock()
        # boxart_url -> {cleaned_name: original_filename}
        self._listings: Dict[str, Dict[str, str]] = {}
        # boxart_url -> Event (set when fetch completes)
        self._events: Dict[str, Event] = {}
        # boxart_url -> True if fetch has been started
        self._started: Dict[str, bool] = {}

    @staticmethod
    def _get_listing_cache_path(boxart_url: str) -> str:
        """Return disk cache path for a thumbnail listing URL."""
        url_hash = hashlib.md5(boxart_url.encode()).hexdigest()
        return os.path.join(SYSTEMS_CACHE_DIR, "thumbnail_listings", f"{url_hash}.json")

    def get_thumbnail_filename(
        self, boxart_url: str, game_base_name: str
    ) -> Optional[str]:
        """Look up the best matching thumbnail filename.

        If the listing hasn't been fetched yet, kicks off a background
        fetch and waits up to 10 seconds for it to complete. Called
        from background image-loading threads, so blocking is fine.

        Returns the original server filename (unencoded) if found,
        or None if no match.
        """
        with self._lock:
            if boxart_url not in self._started:
                # Try loading from disk cache first
                disk_path = self._get_listing_cache_path(boxart_url)
                if os.path.exists(disk_path):
                    try:
                        with open(disk_path, "r", encoding="utf-8") as f:
                            self._listings[boxart_url] = json.load(f)
                        self._started[boxart_url] = True
                        event = Event()
                        event.set()
                        self._events[boxart_url] = event
                    except Exception:
                        pass

            if boxart_url not in self._started:
                # First request — start background fetch
                self._started[boxart_url] = True
                event = Event()
                self._events[boxart_url] = event
                thread = Thread(
                    target=self._fetch_listing,
                    args=(boxart_url,),
                    daemon=True,
                )
                thread.start()

        # Wait for the listing to become available (already in bg thread)
        event = self._events.get(boxart_url)
        if event:
            event.wait(timeout=30)

        lookup = self._listings.get(boxart_url, {})
        cleaned = _clean_name_for_matching(game_base_name)
        return lookup.get(cleaned)

    def clear(self):
        """Clear all cached listings."""
        with self._lock:
            self._listings.clear()
            self._started.clear()
            self._events.clear()

    def _fetch_listing(self, boxart_url: str):
        """Fetch and parse the directory listing from a thumbnail server."""
        try:
            try:
                response = requests.get(boxart_url, timeout=(10, 30))
                response.raise_for_status()
            except (requests.exceptions.SSLError, requests.exceptions.ConnectionError):
                response = requests.get(boxart_url, timeout=(10, 30), verify=False)
                response.raise_for_status()
            html = response.text

            # Parse href attributes pointing to image files
            hrefs = re.findall(
                r'href="([^"]+\.(?:png|jpg|jpeg))"',
                html,
                re.IGNORECASE,
            )

            lookup: Dict[str, str] = {}
            for href in hrefs:
                # Decode URL-encoded filename
                filename = unquote(href)
                cleaned = _clean_name_for_matching(filename)
                if cleaned and cleaned not in lookup:
                    lookup[cleaned] = filename

            self._listings[boxart_url] = lookup

            # Persist to disk cache
            try:
                disk_path = self._get_listing_cache_path(boxart_url)
                os.makedirs(os.path.dirname(disk_path), exist_ok=True)
                with open(disk_path, "w", encoding="utf-8") as f:
                    json.dump(lookup, f, ensure_ascii=False)
            except Exception:
                pass

        except Exception as e:
            log_error(
                f"Failed to fetch thumbnail listing from {boxart_url}",
                type(e).__name__,
                str(e),
            )
            self._listings[boxart_url] = {}
        finally:
            event = self._events.get(boxart_url)
            if event:
                event.set()


# Module-level singleton for thumbnail listings
_listing_cache = _ThumbnailListingCache()


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

        self._retry_counts: Dict[str, int] = {}
        self._max_retries = 2

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
            # Standard format - use listing-based matching
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

    def update(self) -> bool:
        """
        Process loaded images from background threads.
        Should be called from main thread each frame.

        Returns:
            True if any new images were processed (screen needs redraw).
        """
        a = self._process_queue(self._thumbnail_queue, self._thumbnail_cache)
        b = self._process_queue(self._hires_queue, self._hires_cache)
        return a or b

    def clear(self):
        """Clear all cached images and queues."""
        self._thumbnail_cache.clear()
        self._hires_cache.clear()
        self._retry_counts.clear()

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
            image_url = urljoin(boxart_url, quote(f"{base_name}.png", safe=""))
            cache_key = f"{prefix}{boxart_url}_{game_name}"
            return cache_key, image_url

        return None, None

    def _resolve_thumbnail_url(self, base_url: str, base_name: str) -> Optional[str]:
        """Resolve a thumbnail URL using the listing cache.

        Tries to match the game name against the pre-fetched
        thumbnail listing. Returns the full image URL if found.
        """
        matched = _listing_cache.get_thumbnail_filename(base_url, base_name)
        if matched:
            return urljoin(base_url, quote(matched, safe=""))
        return None

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
        """Try loading image using listing-based matching, then format fallback."""
        # First try listing-based fuzzy match
        matched_url = self._resolve_thumbnail_url(base_url, base_name)
        if matched_url:
            try:
                response = requests.get(matched_url, timeout=5)
                response.raise_for_status()

                image_data = BytesIO(response.content)
                image = pygame.image.load(image_data).convert_alpha()
                scaled_image = pygame.transform.smoothscale(image, target_size)

                queue.put((cache_key, scaled_image))
                return
            except Exception:
                pass

        # Fall back to trying exact name with different extensions
        for fmt in formats:
            try:
                image_url = urljoin(base_url, quote(f"{base_name}{fmt}", safe=""))
                response = requests.get(image_url, timeout=5)
                response.raise_for_status()

                image_data = BytesIO(response.content)
                image = pygame.image.load(image_data).convert_alpha()
                scaled_image = pygame.transform.smoothscale(image, target_size)

                queue.put((cache_key, scaled_image))
                return

            except Exception:
                continue

        # All attempts failed
        queue.put((cache_key, None))

    def _load_hires_with_fallback(
        self,
        base_url: str,
        base_name: str,
        formats: list,
        cache_key: str,
        game_name: str,
    ):
        """Try loading high-resolution image with listing match then extension fallback."""
        # First try listing-based fuzzy match
        matched_url = self._resolve_thumbnail_url(base_url, base_name)
        if matched_url:
            try:
                response = requests.get(matched_url, timeout=10)
                response.raise_for_status()

                image_data = BytesIO(response.content)
                image = pygame.image.load(image_data)

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
                pass

        # Fall back to exact name with different extensions
        for fmt in formats:
            try:
                url = urljoin(
                    base_url if base_url.endswith("/") else base_url + "/",
                    quote(f"{base_name}{fmt}", safe=""),
                )
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

    def _process_queue(self, queue: Queue, cache: Dict) -> bool:
        """Process items from queue into cache. Returns True if any items processed."""
        processed = False
        while not queue.empty():
            try:
                cache_key, image = queue.get_nowait()
                processed = True
                if image is not None:
                    cache[cache_key] = image
                    self._retry_counts.pop(cache_key, None)
                else:
                    retries = self._retry_counts.get(cache_key, 0)
                    if retries < self._max_retries:
                        # Allow retry by removing from cache
                        self._retry_counts[cache_key] = retries + 1
                        cache.pop(cache_key, None)
                    else:
                        # Max retries reached, cache as not found
                        cache[cache_key] = None
            except Empty:
                break
        return processed

    def _drain_queue(self, queue: Queue):
        """Drain all items from a queue."""
        while not queue.empty():
            try:
                queue.get_nowait()
            except Empty:
                break


# Default instance for convenience
image_cache = ImageCache()
