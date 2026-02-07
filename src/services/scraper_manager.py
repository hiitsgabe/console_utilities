"""
Scraper manager service for Console Utilities.
Manages background batch scraping with threading support.
"""

import os
import threading
import traceback
from typing import Dict, Any, List, Optional

from state import ScraperQueueItem, ScraperQueueState
from utils.logging import log_error


class ScraperManager:
    """
    Manages background batch scraping.

    Scraping jobs run sequentially in a daemon thread,
    allowing the UI to remain responsive.
    """

    ROM_EXTENSIONS = {
        ".nes",
        ".sfc",
        ".smc",
        ".gba",
        ".gbc",
        ".gb",
        ".n64",
        ".z64",
        ".nds",
        ".3ds",
        ".iso",
        ".bin",
        ".cue",
        ".chd",
        ".pbp",
        ".zip",
        ".7z",
        ".rar",
        ".nsz",
        ".nsp",
        ".xci",
    }

    def __init__(self, settings: Dict[str, Any], scraper_queue: ScraperQueueState):
        self.settings = settings
        self.queue = scraper_queue
        self._thread: Optional[threading.Thread] = None
        self._stop_requested = False

    @property
    def is_active(self) -> bool:
        """True if scraping is in progress."""
        return self.queue.active

    def scan_folder(self, folder_path: str) -> List[Dict[str, str]]:
        """
        Scan a folder for ROM files.

        Args:
            folder_path: Path to scan

        Returns:
            List of dicts with 'name' and 'path' keys
        """
        roms = []
        try:
            for item in sorted(os.listdir(folder_path)):
                item_path = os.path.join(folder_path, item)
                if os.path.isfile(item_path):
                    ext = os.path.splitext(item)[1].lower()
                    if ext in self.ROM_EXTENSIONS:
                        roms.append({"name": item, "path": item_path})
        except Exception:
            pass
        return roms

    def start_batch(
        self,
        folder_path: str,
        roms: List[Dict[str, str]],
        default_images: List[str],
        auto_select: bool = True,
    ):
        """
        Start a background batch scraping job.

        Args:
            folder_path: ROM folder being scraped
            roms: List of ROM dicts (name, path)
            default_images: Image types to download
            auto_select: Auto-select first search result
        """
        if self.queue.active:
            return  # Already running

        # Build queue items (thread-safe: replace whole list)
        items = [ScraperQueueItem(name=r["name"], path=r["path"]) for r in roms]
        self.queue.items = items
        self.queue.current_index = 0
        self.queue.current_status = "Starting..."
        self.queue.folder_path = folder_path
        self.queue.auto_select = auto_select
        self.queue.default_images = list(default_images)
        self.queue.active = True

        self._stop_requested = False
        self._thread = threading.Thread(target=self._scrape_thread, daemon=True)
        self._thread.start()

    def stop(self):
        """Request the scraper thread to stop after current item."""
        self._stop_requested = True

    def clear(self):
        """Clear the queue (only when not active)."""
        if not self.queue.active:
            self.queue.items = []
            self.queue.current_index = 0
            self.queue.current_status = ""

    def _scrape_thread(self):
        """Background thread that processes the scrape queue."""
        try:
            from services.scraper_service import get_scraper_service
            from services.metadata_writer import get_metadata_writer

            # Set system context from batch folder for Libretro
            batch_dir = os.path.basename(self.queue.folder_path)
            self.settings["current_system_folder"] = batch_dir

            service = get_scraper_service(self.settings)
            service.reset_provider()

            items = self.queue.items
            total = len(items)

            for i, item in enumerate(items):
                if self._stop_requested:
                    item.status = "skipped"
                    item.skip_reason = "cancelled"
                    continue

                self.queue.current_index = i
                self.queue.current_status = f"Scraping {i + 1}/{total}: {item.name}"

                # Skip if already has images
                if service.check_image_exists(item.path, self.queue.default_images):
                    item.status = "skipped"
                    item.skip_reason = "image_exists"
                    continue

                # Search
                item.status = "searching"
                self.queue.current_status = f"Searching {i + 1}/{total}: {item.name}"

                game_name = service.extract_game_name(item.path)
                success, results, error = service.search_game(
                    game_name, rom_path=item.path
                )

                if not success or not results:
                    item.status = "error"
                    item.error = error or "No results"
                    continue

                # Auto-select first result
                game = results[0]
                game_info = {
                    "id": game.id,
                    "name": game.name,
                    "platform": game.platform,
                    "release_date": game.release_date,
                    "description": game.description,
                }

                # Get images
                item.status = "downloading"
                self.queue.current_status = f"Downloading {i + 1}/{total}: {item.name}"

                success, images, error = service.get_game_images(game.id)
                if not success or not images:
                    item.status = "error"
                    item.error = error or "No images"
                    continue

                # Filter to default image types
                filtered = [
                    img for img in images if img.type in self.queue.default_images
                ]
                if not filtered:
                    filtered = images[:2]

                # Download
                success, paths, error = service.download_images(filtered, item.path)

                if not success:
                    item.status = "error"
                    item.error = error or "Download failed"
                    continue

                # Update metadata
                writer = get_metadata_writer(self.settings)
                writer.update_metadata(item.path, game_info, paths)

                item.status = "done"

            # Final status
            done_count = sum(1 for it in items if it.status == "done")
            err_count = sum(1 for it in items if it.status == "error")
            skip_count = sum(1 for it in items if it.status == "skipped")
            self.queue.current_status = f"Complete: {done_count} scraped, {err_count} errors, {skip_count} skipped"

        except Exception as e:
            log_error(
                f"Scraper thread error: {e}",
                type(e).__name__,
                traceback.format_exc(),
            )
            self.queue.current_status = f"Error: {str(e)[:50]}"
        finally:
            self.queue.active = False
