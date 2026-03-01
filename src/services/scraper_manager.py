"""
Scraper manager service for Console Utilities.
Manages background batch scraping with threading support.
"""

import os
import threading
import traceback
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
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
        download_video: bool = False,
        system: str = "",
    ):
        """
        Start a background batch scraping job.

        Args:
            folder_path: ROM folder being scraped
            roms: List of ROM dicts (name, path)
            default_images: Image types to download
            auto_select: Auto-select first search result
            download_video: Download video for each ROM
            system: Platform override for this batch (e.g. "psx", "snes")
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
        self.queue.download_video = download_video
        self.queue.system = system
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
        """Background thread that processes the scrape queue using a worker pool."""
        try:
            from services.scraper_service import ScraperService
            from services.metadata_writer import MetadataWriter

            batch_dir = os.path.basename(self.queue.folder_path)
            items = self.queue.items
            total = len(items)
            workers = self.settings.get("scraper_parallel_downloads", 1)
            self.queue.parallel_workers = workers
            metadata_lock = threading.Lock()

            def scrape_item(i, item):
                """Process a single ROM — each call gets its own service instance."""
                if self._stop_requested:
                    item.status = "skipped"
                    item.skip_reason = "cancelled"
                    return

                # Each worker gets its own ScraperService to avoid shared state races
                worker_settings = dict(self.settings)
                worker_settings["current_system_folder"] = batch_dir
                if self.queue.system:
                    worker_settings["scraper_preferred_system"] = self.queue.system
                else:
                    worker_settings.pop("scraper_preferred_system", None)
                service = ScraperService(worker_settings)

                # Skip if already has images
                if service.check_image_exists(item.path, self.queue.default_images):
                    item.status = "skipped"
                    item.skip_reason = "image_exists"
                    return

                # Search
                item.status = "searching"

                game_name = service.extract_game_name(item.path)
                success, results, error = service.search_game(
                    game_name, rom_path=item.path
                )

                if not success or not results:
                    item.status = "error"
                    item.error = error or "No results"
                    log_error(
                        f"Scraper: {item.name} - Search failed: {error or 'No results'}",
                        "ScraperSearchError",
                        "",
                    )
                    return

                # Auto-select first result
                game = results[0]
                game_info = {
                    "id": game.id,
                    "name": game.name,
                    "platform": game.platform,
                    "release_date": game.release_date,
                    "description": game.description,
                }

                # Get images (with fallback to other providers)
                item.status = "downloading"

                success, images, error, fb_info = service.get_game_images_with_fallback(
                    game.id,
                    game_name,
                    item.path,
                    self.queue.default_images,
                )
                if not success or not images:
                    item.status = "error"
                    item.error = error or "No images"
                    log_error(
                        f"Scraper: {item.name} - Image fetch failed: {error or 'No images'}",
                        "ScraperImageError",
                        "",
                    )
                    return

                # Use fallback game info for metadata if primary failed
                if fb_info:
                    game_info = fb_info

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
                    log_error(
                        f"Scraper: {item.name} - Download failed: {error or 'Download failed'}",
                        "ScraperDownloadError",
                        "",
                    )
                    return

                # Download video if enabled
                if self.queue.download_video:
                    try:
                        v_success, videos, v_error = service.get_game_videos(game.id)
                        if v_success and videos:
                            # Pick first normalized video, or first available
                            video = next((v for v in videos if v.normalized), videos[0])
                            video_path = service.get_video_output_path(
                                item.path, video.format or "mp4"
                            )
                            if video_path:
                                dl_ok, dl_err = service.download_video(
                                    video, video_path
                                )
                                if dl_ok:
                                    paths.append(video_path)
                                else:
                                    log_error(
                                        f"Scraper: {item.name} - Video download failed: {dl_err}",
                                        "ScraperVideoError",
                                        "",
                                    )
                    except Exception as ve:
                        log_error(
                            f"Scraper: {item.name} - Video error: {ve}",
                            type(ve).__name__,
                            traceback.format_exc(),
                        )

                # Metadata write with lock (prevents gamelist.xml corruption)
                with metadata_lock:
                    writer = MetadataWriter(worker_settings)
                    writer.update_metadata(item.path, game_info, paths)

                item.status = "done"

            # Submit all items to thread pool
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {}
                for i, item in enumerate(items):
                    if self._stop_requested:
                        # Mark remaining as skipped
                        for remaining in items[i:]:
                            remaining.status = "skipped"
                            remaining.skip_reason = "cancelled"
                        break
                    future = executor.submit(scrape_item, i, item)
                    futures[future] = (i, item)

                # Update status as futures complete
                for future in concurrent.futures.as_completed(futures):
                    i, item = futures[future]
                    try:
                        future.result()
                    except Exception as e:
                        item.status = "error"
                        item.error = str(e)[:50]
                        log_error(
                            f"Scraper: {item.name} - {e}",
                            type(e).__name__,
                            traceback.format_exc(),
                        )

                    # Update overall progress
                    done = sum(
                        1 for it in items if it.status in ("done", "error", "skipped")
                    )
                    self.queue.current_index = done - 1
                    self.queue.current_status = f"Scraping: {done}/{total} complete"

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
