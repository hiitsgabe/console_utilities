"""
Download manager service for Console Utilities.
Manages background download queue with threading support.
"""

import os
import threading
import time
import traceback
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin
from zipfile import ZipFile

import requests

from state import DownloadQueueItem, DownloadQueueState
from utils.logging import log_error
from utils.nsz import decompress_nsz_file
from constants import SCRIPT_DIR


class DownloadManager:
    """
    Manages a background download queue.

    Downloads are processed sequentially in a daemon thread,
    allowing the UI to remain responsive.
    """

    def __init__(self, settings: Dict[str, Any], download_queue: DownloadQueueState):
        """
        Initialize download manager.

        Args:
            settings: Application settings dictionary
            download_queue: Reference to the queue state in AppState
        """
        self.settings = settings
        self.queue = download_queue
        self._thread: Optional[threading.Thread] = None
        self._cancel_current = False
        self._stop_thread = False
        self._lock = threading.Lock()

    @property
    def work_dir(self) -> str:
        """Get the work directory from settings."""
        return self.settings.get("work_dir", os.path.join(SCRIPT_DIR, "downloads"))

    @property
    def roms_dir(self) -> str:
        """Get the ROMs directory from settings."""
        return self.settings.get("roms_dir", os.path.join(SCRIPT_DIR, "roms"))

    @property
    def is_active(self) -> bool:
        """True if any items are downloading or waiting."""
        return self.queue.active or any(
            item.status in ("waiting", "downloading", "extracting", "moving")
            for item in self.queue.items
        )

    @property
    def current_progress_text(self) -> str:
        """Returns 'Downloading X of Y' string for the footer."""
        total = len(self.queue.items)
        completed = sum(1 for item in self.queue.items if item.status == "completed")
        in_progress = sum(
            1
            for item in self.queue.items
            if item.status in ("downloading", "extracting", "moving")
        )

        if in_progress > 0:
            current = completed + 1
            return f"Downloading {current} of {total} games"
        elif total > completed:
            return f"Waiting... ({completed}/{total} complete)"
        else:
            return f"All {total} downloads complete"

    @property
    def active_item(self) -> Optional[DownloadQueueItem]:
        """Get the currently active download item."""
        for item in self.queue.items:
            if item.status in ("downloading", "extracting", "moving"):
                return item
        return None

    @property
    def waiting_count(self) -> int:
        """Count of waiting items."""
        return sum(1 for item in self.queue.items if item.status == "waiting")

    @property
    def completed_count(self) -> int:
        """Count of completed items."""
        return sum(1 for item in self.queue.items if item.status == "completed")

    def add_to_queue(
        self, games: List[Any], system_data: Dict[str, Any], system_name: str
    ):
        """
        Add games to the download queue.

        Args:
            games: List of game objects/dicts to download
            system_data: System configuration for downloads
            system_name: Display name of the system
        """
        with self._lock:
            for game in games:
                item = DownloadQueueItem(
                    game=game,
                    system_data=system_data,
                    system_name=system_name,
                    status="waiting",
                )
                self.queue.items.append(item)

        # Start thread if not running
        self._start_thread_if_needed()

    def remove_from_queue(self, index: int) -> bool:
        """
        Remove a waiting item from the queue by index.

        Args:
            index: Index of item to remove

        Returns:
            True if removed, False if not removable
        """
        with self._lock:
            if 0 <= index < len(self.queue.items):
                item = self.queue.items[index]
                if item.status == "waiting":
                    self.queue.items.pop(index)
                    # Adjust highlighted index if needed
                    if self.queue.highlighted >= len(self.queue.items):
                        self.queue.highlighted = max(0, len(self.queue.items) - 1)
                    return True
        return False

    def cancel_current(self):
        """Cancel the currently downloading item."""
        self._cancel_current = True

    def cancel_all(self):
        """Cancel active download and clear all waiting items."""
        with self._lock:
            self._cancel_current = True
            # Cancel all waiting items
            for item in self.queue.items:
                if item.status == "waiting":
                    item.status = "cancelled"

    def clear_completed(self):
        """Remove all completed and failed items from the queue."""
        with self._lock:
            self.queue.items = [
                item
                for item in self.queue.items
                if item.status not in ("completed", "failed", "cancelled")
            ]
            # Adjust highlighted index
            if self.queue.highlighted >= len(self.queue.items):
                self.queue.highlighted = max(0, len(self.queue.items) - 1)

    def _start_thread_if_needed(self):
        """Start the download thread if not already running."""
        if self._thread is None or not self._thread.is_alive():
            self._stop_thread = False
            self._thread = threading.Thread(target=self._download_thread, daemon=True)
            self._thread.start()

    def _download_thread(self):
        """Background thread that processes download queue."""
        self.queue.active = True

        try:
            while not self._stop_thread:
                # Find next waiting item
                item = self._get_next_waiting_item()
                if item is None:
                    break

                # Process this item
                self._process_item(item)

        except Exception as e:
            log_error(
                f"Download thread error: {e}", type(e).__name__, traceback.format_exc()
            )
        finally:
            self.queue.active = False

    def _get_next_waiting_item(self) -> Optional[DownloadQueueItem]:
        """Get the next waiting item from the queue."""
        with self._lock:
            for item in self.queue.items:
                if item.status == "waiting":
                    return item
        return None

    def _process_item(self, item: DownloadQueueItem):
        """Process a single download item."""
        self._cancel_current = False
        item.status = "downloading"
        item.progress = 0.0
        item.downloaded = 0
        item.speed = 0.0
        item.error = ""

        try:
            # Get filename and URL
            filename = self._get_filename(item.game)
            url = self._get_download_url(item.system_data, item.game, filename)

            if not url:
                item.status = "failed"
                item.error = "Could not determine download URL"
                return

            # Ensure filename has extension
            formats = item.system_data.get("file_format", [])
            if "download_url" in item.system_data and "." not in filename:
                fmt = formats[0] if formats else ""
                filename = filename + fmt

            # Download the file
            file_path = self._download_file(item, url, filename)

            if file_path is None:
                # Download was cancelled or failed
                if item.status != "failed":
                    item.status = "cancelled"
                return

            # Process the downloaded file
            item.status = "extracting"
            item.progress = 0.0

            roms_folder = self._get_roms_folder(item.system_data)
            success = self._process_downloaded_file(
                item, file_path, filename, roms_folder
            )

            if success:
                item.status = "completed"
                item.progress = 1.0
            elif item.status != "cancelled":
                item.status = "failed"
                if not item.error:
                    item.error = "Processing failed"

        except Exception as e:
            log_error(
                f"Error processing download: {e}",
                type(e).__name__,
                traceback.format_exc(),
            )
            item.status = "failed"
            item.error = str(e)

    def _download_file(
        self, item: DownloadQueueItem, url: str, filename: str
    ) -> Optional[str]:
        """
        Download a file with progress updates.

        Returns:
            File path if successful, None if cancelled/failed
        """
        # Prepare authentication
        headers = {}
        cookies = {}
        system_data = item.system_data

        if "auth" in system_data:
            auth_config = system_data["auth"]
            if auth_config.get("cookies", False) and "token" in auth_config:
                cookie_name = auth_config.get("cookie_name", "auth_token")
                cookies[cookie_name] = auth_config["token"]
            elif "token" in auth_config:
                headers["Authorization"] = f"Bearer {auth_config['token']}"

        try:
            response = requests.get(
                url, stream=True, timeout=30, headers=headers, cookies=cookies
            )
            response.raise_for_status()

            item.total_size = int(response.headers.get("content-length", 0))
            item.downloaded = 0
            start_time = time.time()
            last_update = start_time
            last_downloaded = 0

            file_path = os.path.join(self.work_dir, filename)
            os.makedirs(self.work_dir, exist_ok=True)

            with open(file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if self._cancel_current:
                        f.close()
                        if os.path.exists(file_path):
                            os.remove(file_path)
                        return None

                    if chunk:
                        f.write(chunk)
                        item.downloaded += len(chunk)

                        # Update progress and speed every 500ms
                        current_time = time.time()
                        if current_time - last_update >= 0.5:
                            item.speed = (item.downloaded - last_downloaded) * 2
                            last_downloaded = item.downloaded
                            last_update = current_time

                            if item.total_size > 0:
                                item.progress = item.downloaded / item.total_size

            return file_path

        except requests.exceptions.RequestException as e:
            log_error(f"Download request failed: {e}")
            item.status = "failed"
            item.error = f"Network error: {str(e)[:50]}"
            return None

    def _process_downloaded_file(
        self, item: DownloadQueueItem, file_path: str, filename: str, roms_folder: str
    ) -> bool:
        """
        Process a downloaded file (extract, decompress, move).

        Returns:
            True if successful
        """
        try:
            formats = item.system_data.get("file_format", [])
            os.makedirs(roms_folder, exist_ok=True)

            # Handle ZIP extraction
            if filename.endswith(".zip") and item.system_data.get(
                "should_unzip", False
            ):
                item.status = "extracting"
                with ZipFile(file_path, "r") as zip_ref:
                    total_files = len(zip_ref.namelist())
                    for i, file_info in enumerate(zip_ref.infolist()):
                        if self._cancel_current:
                            return False
                        zip_ref.extract(file_info, self.work_dir)
                        item.progress = (i + 1) / total_files

                os.remove(file_path)

            # Handle NSZ decompression
            elif filename.endswith(".nsz"):
                item.status = "extracting"

                def nsz_progress(text: str, percent: int):
                    item.progress = percent / 100.0

                keys_path = self.settings.get("nsz_keys_path", "")
                success = decompress_nsz_file(
                    file_path, self.work_dir, keys_path, nsz_progress
                )

                if success:
                    # Move NSP files
                    for f in os.listdir(self.work_dir):
                        if f.endswith(".nsp"):
                            src_path = os.path.join(self.work_dir, f)
                            dst_path = os.path.join(roms_folder, f)
                            os.rename(src_path, dst_path)

                    if os.path.exists(file_path):
                        os.remove(file_path)
                    return True
                else:
                    return False

            # Move compatible files to ROMs folder
            item.status = "moving"
            item.progress = 0.0

            files_to_move = [
                f
                for f in os.listdir(self.work_dir)
                if any(f.endswith(ext) for ext in formats)
            ]

            for i, f in enumerate(files_to_move):
                if self._cancel_current:
                    return False
                src_path = os.path.join(self.work_dir, f)
                dst_path = os.path.join(roms_folder, f)
                os.rename(src_path, dst_path)
                item.progress = (i + 1) / max(len(files_to_move), 1)

            # Clean up work directory
            for f in os.listdir(self.work_dir):
                file_to_remove = os.path.join(self.work_dir, f)
                if os.path.isfile(file_to_remove):
                    try:
                        os.remove(file_to_remove)
                    except Exception:
                        pass

            return True

        except Exception as e:
            log_error(f"Error processing file {filename}: {e}")
            item.error = str(e)[:50]
            return False

    def _get_filename(self, game: Any) -> str:
        """Extract filename from game item."""
        if isinstance(game, dict):
            if "name" in game:
                return game["name"]
            elif "filename" in game:
                return game["filename"]
            else:
                return str(game)
        return str(game)

    def _get_download_url(
        self, system_data: Dict[str, Any], game: Any, filename: str
    ) -> Optional[str]:
        """Get download URL for a game item."""
        if "download_url" in system_data:
            return game.get("href") if isinstance(game, dict) else None
        elif "url" in system_data:
            if isinstance(game, dict) and "href" in game:
                return urljoin(system_data["url"], game["href"])
            else:
                return urljoin(system_data["url"], filename)
        return None

    def _get_roms_folder(self, system_data: Dict[str, Any]) -> str:
        """Get the target ROMs folder for a system."""
        system_name = system_data.get("name", "")
        system_settings = self.settings.get("system_settings", {})
        custom_folder = system_settings.get(system_name, {}).get("custom_folder", "")

        if custom_folder and os.path.exists(custom_folder):
            return custom_folder
        else:
            return os.path.join(self.roms_dir, system_data.get("roms_folder", ""))
