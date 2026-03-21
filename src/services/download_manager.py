"""
Download manager service for Console Utilities.
Manages background download queue with threading support.
"""

import os
import shutil
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin
from zipfile import ZipFile

import requests

from state import DownloadQueueItem, DownloadQueueState
from utils.logging import log_error
from utils.nsz import decompress_nsz_file
from constants import SCRIPT_DIR

# Minimum file size for parallel downloads (50 MB)
PARALLEL_MIN_SIZE = 50 * 1024 * 1024
# Number of parallel download workers
PARALLEL_WORKERS = 4
# iter_content chunk size (2 MB — reduces Python/GIL overhead vs 256 KB)
STREAM_CHUNK_SIZE = 2 * 1024 * 1024


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
        self._session = self._make_session()

    @staticmethod
    def _make_session() -> requests.Session:
        """Create a requests session with connection pooling."""
        s = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=6, pool_maxsize=6
        )
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        return s

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
                if item.status in ("waiting", "failed", "cancelled"):
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
        Uses parallel chunk downloads when the server supports range requests
        and the file is larger than PARALLEL_MIN_SIZE.

        Returns:
            File path if successful, None if cancelled/failed
        """
        # Prepare authentication
        headers = {}
        cookies = {}
        system_data = item.system_data

        if "auth" in system_data:
            auth_config = system_data["auth"]
            if auth_config.get("type") == "ia_s3":
                access_key = auth_config.get("access_key") or None
                secret_key = auth_config.get("secret_key") or None
                if access_key and secret_key:
                    headers["authorization"] = f"LOW {access_key}:{secret_key}"
            elif auth_config.get("cookies", False) and "token" in auth_config:
                cookie_name = auth_config.get("cookie_name", "auth_token")
                cookies[cookie_name] = auth_config["token"]
            elif "token" in auth_config:
                headers["Authorization"] = f"Bearer {auth_config['token']}"

        try:
            request_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "*/*",
                "Accept-Encoding": "identity",
                "Accept-Language": "en-US,en;q=0.9",
            }
            # Merge auth headers so they persist to parallel/single downloads
            request_headers.update(headers)
            has_auth = bool(headers) or bool(cookies)

            # Resolve the final URL and get initial response.
            # requests strips Authorization/Cookie on cross-host redirects,
            # so for all authenticated downloads we follow redirects manually.
            resolved_url = url
            if has_auth:
                current_url = url
                for _ in range(5):
                    resp = self._session.get(
                        current_url,
                        stream=True,
                        timeout=(15, 30),
                        headers=request_headers,
                        cookies=cookies,
                        allow_redirects=False,
                    )
                    if resp.status_code in (301, 302, 303, 307, 308):
                        current_url = resp.headers.get("Location", current_url)
                        continue
                    else:
                        resp.raise_for_status()
                        response = resp
                        resolved_url = current_url
                        break
                else:
                    raise requests.exceptions.TooManyRedirects("Too many redirects")
            else:
                response = self._session.get(
                    url,
                    stream=True,
                    timeout=(15, 30),
                    headers=request_headers,
                    cookies=cookies,
                )
                response.raise_for_status()
                resolved_url = response.url

            total_size = int(response.headers.get("content-length", 0))
            accept_ranges = response.headers.get("accept-ranges", "").lower()
            item.total_size = total_size

            # Close the initial response - we'll either re-open or use parallel
            response.close()

            os.makedirs(self.work_dir, exist_ok=True)

            # Use parallel downloads if server supports ranges and file is large.
            # IA CDN throttles concurrent auth requests — use 2 workers instead of 4.
            if accept_ranges == "bytes" and total_size > PARALLEL_MIN_SIZE:
                ia_auth = has_auth and "archive.org" in url
                workers = 2 if ia_auth else PARALLEL_WORKERS
                return self._download_file_parallel(
                    item,
                    resolved_url,
                    filename,
                    total_size,
                    request_headers,
                    cookies,
                    num_workers=workers,
                )

            # Fall back to single-stream download
            return self._download_file_single(
                item,
                resolved_url,
                filename,
                total_size,
                request_headers,
                cookies,
            )

        except requests.exceptions.RequestException as e:
            log_error(f"Download request failed: {e}")
            log_error(f"Failed URL: {url}")
            item.status = "failed"
            if (
                hasattr(e, "response")
                and e.response is not None
                and e.response.status_code in (401, 403)
                and "archive.org" in url
            ):
                item.error = "ia_auth_required"
            elif hasattr(e, "response") and e.response is not None:
                item.error = f"HTTP {e.response.status_code}: {str(e)[:40]}"
            else:
                item.error = f"Network error: {str(e)[:50]}"
            return None

    def _download_file_single(
        self,
        item: DownloadQueueItem,
        url: str,
        filename: str,
        total_size: int,
        headers: Dict[str, str],
        cookies: Dict[str, str],
    ) -> Optional[str]:
        """Single-stream download (fallback path)."""
        item.downloaded = 0
        last_update = time.time()
        last_downloaded = 0
        speed_samples = []

        file_path = os.path.join(self.work_dir, filename)

        response = self._session.get(
            url,
            stream=True,
            timeout=(15, 30),
            headers=headers,
            cookies=cookies,
            allow_redirects=True,
        )
        response.raise_for_status()

        with open(file_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=STREAM_CHUNK_SIZE):
                if self._cancel_current:
                    f.close()
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    return None

                if chunk:
                    f.write(chunk)
                    item.downloaded += len(chunk)

                    current_time = time.time()
                    elapsed = current_time - last_update
                    if elapsed >= 0.5:
                        instant_speed = (item.downloaded - last_downloaded) / elapsed
                        speed_samples.append(instant_speed)
                        if len(speed_samples) > 4:
                            speed_samples.pop(0)
                        item.speed = sum(speed_samples) / len(speed_samples)
                        last_downloaded = item.downloaded
                        last_update = current_time

                        if item.total_size > 0:
                            item.progress = item.downloaded / item.total_size

        return file_path

    def _download_file_parallel(
        self,
        item: DownloadQueueItem,
        url: str,
        filename: str,
        total_size: int,
        headers: Dict[str, str],
        cookies: Dict[str, str],
        num_workers: int = PARALLEL_WORKERS,
    ) -> Optional[str]:
        """Download a file using parallel range-request workers.

        Workers write directly to the final file at their byte
        offsets, eliminating the chunk-stitching step entirely.
        """
        file_path = os.path.join(self.work_dir, filename)
        item.downloaded = 0

        # Compute chunk boundaries
        chunk_size = total_size // num_workers
        chunks = []
        for i in range(num_workers):
            start = i * chunk_size
            end = (
                (total_size - 1)
                if i == num_workers - 1
                else ((i + 1) * chunk_size - 1)
            )
            chunks.append((start, end))

        # Pre-allocate the output file
        with open(file_path, "wb") as f:
            f.truncate(total_size)

        # Shared progress array (one entry per worker)
        progress_array = [0] * num_workers

        chunk_failed = threading.Event()

        def worker(chunk_index: int) -> bool:
            return self._download_chunk(
                url,
                headers,
                cookies,
                chunks[chunk_index][0],
                chunks[chunk_index][1],
                file_path,
                chunk_index,
                progress_array,
                chunk_failed,
            )

        executor = ThreadPoolExecutor(max_workers=num_workers)
        futures: List[Future] = []
        try:
            for i in range(num_workers):
                futures.append(executor.submit(worker, i))

            # Poll progress until all workers complete
            last_update = time.time()
            last_downloaded = 0
            speed_samples = []

            while not all(f.done() for f in futures):
                if self._cancel_current:
                    chunk_failed.set()
                    executor.shutdown(wait=False, cancel_futures=True)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    return None

                time.sleep(0.1)

                # Aggregate progress
                item.downloaded = sum(progress_array)
                current_time = time.time()
                elapsed = current_time - last_update
                if elapsed >= 0.5:
                    dl = item.downloaded - last_downloaded
                    instant_speed = dl / elapsed
                    speed_samples.append(instant_speed)
                    if len(speed_samples) > 4:
                        speed_samples.pop(0)
                    item.speed = (
                        sum(speed_samples) / len(speed_samples)
                    )
                    last_downloaded = item.downloaded
                    last_update = current_time
                    if total_size > 0:
                        item.progress = (
                            item.downloaded / total_size
                        )

            # Final progress update
            item.downloaded = sum(progress_array)
            if total_size > 0:
                item.progress = item.downloaded / total_size

            # Check for failures
            for f in futures:
                if not f.result():
                    item.status = "failed"
                    if not item.error:
                        item.error = "Chunk download failed"
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    return None

        except Exception as e:
            chunk_failed.set()
            executor.shutdown(wait=False, cancel_futures=True)
            if os.path.exists(file_path):
                os.remove(file_path)
            raise
        finally:
            executor.shutdown(wait=False)

        return file_path

    def _download_chunk(
        self,
        url: str,
        headers: Dict[str, str],
        cookies: Dict[str, str],
        start: int,
        end: int,
        file_path: str,
        chunk_index: int,
        progress_array: List[int],
        failed_event: threading.Event,
    ) -> bool:
        """Download a byte range directly into the output file.

        Each worker opens its own fd and writes to disjoint byte
        ranges, so no locking is needed.
        """
        try:
            range_headers = dict(headers)
            range_headers["Range"] = f"bytes={start}-{end}"

            resp = self._session.get(
                url,
                stream=True,
                timeout=(15, 60),
                headers=range_headers,
                cookies=cookies,
                allow_redirects=True,
            )
            resp.raise_for_status()

            offset = start
            with open(file_path, "r+b") as f:
                for chunk in resp.iter_content(chunk_size=STREAM_CHUNK_SIZE):
                    if self._cancel_current or failed_event.is_set():
                        return False
                    if chunk:
                        f.seek(offset)
                        f.write(chunk)
                        offset += len(chunk)
                        progress_array[chunk_index] += len(chunk)

            return True
        except Exception as e:
            log_error(f"Chunk {chunk_index} failed: {e}")
            failed_event.set()
            return False

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

            # Handle ZIP extraction (per-system settings override system_data default)
            system_name = item.system_data.get("name", "")
            per_sys = self.settings.get("system_settings", {}).get(system_name, {})
            should_unzip = per_sys.get(
                "should_unzip", item.system_data.get("should_unzip", False)
            )
            if filename.endswith(".zip") and should_unzip:
                item.status = "extracting"
                extract_contents = item.system_data.get("extract_contents", True)

                # Extract directly to roms folder to avoid
                # extra move step (major speedup on slow storage)
                extract_dir = roms_folder if extract_contents else self.work_dir

                with ZipFile(file_path, "r") as zip_ref:
                    members = zip_ref.infolist()
                    total = len(members)
                    # Update progress every ~5% to keep overhead low
                    update_interval = max(1, total // 20)
                    for i, member in enumerate(members):
                        if self._cancel_current:
                            return False
                        zip_ref.extract(member, extract_dir)
                        if (i + 1) % update_interval == 0 or i == total - 1:
                            item.progress = (i + 1) / total

                os.remove(file_path)

                # Handle extract mode (keep folder structure)
                if not extract_contents:
                    item.status = "moving"
                    item.progress = 0.0
                    extracted_items = [
                        f for f in os.listdir(self.work_dir) if not f.startswith(".")
                    ]
                    # Filter: keep directories and files matching formats
                    items_to_move = []
                    for f in extracted_items:
                        src_path = os.path.join(self.work_dir, f)
                        if os.path.isdir(src_path):
                            items_to_move.append(f)
                        elif any(f.lower().endswith(ext.lower()) for ext in formats):
                            items_to_move.append(f)

                    for i, extracted_item in enumerate(items_to_move):
                        if self._cancel_current:
                            return False
                        src_path = os.path.join(self.work_dir, extracted_item)
                        dst_path = os.path.join(roms_folder, extracted_item)
                        if os.path.exists(dst_path):
                            if os.path.isdir(dst_path):
                                shutil.rmtree(dst_path)
                            else:
                                os.remove(dst_path)
                        self._fast_move(src_path, dst_path)
                        item.progress = (i + 1) / max(len(items_to_move), 1)

                    # Clean up remaining files in work directory
                    for f in os.listdir(self.work_dir):
                        file_to_remove = os.path.join(self.work_dir, f)
                        if os.path.isfile(file_to_remove):
                            try:
                                os.remove(file_to_remove)
                            except Exception:
                                pass
                    return True

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
                            self._fast_move(src_path, dst_path)

                    if os.path.exists(file_path):
                        os.remove(file_path)
                    return True
                else:
                    return False

            # Move compatible files to ROMs folder
            item.status = "moving"
            item.progress = 0.0

            # Include .zip in move filter when not extracting
            move_formats = list(formats)
            if filename.endswith(".zip") and ".zip" not in [
                ext.lower() for ext in move_formats
            ]:
                move_formats.append(".zip")

            files_to_move = [
                f
                for f in os.listdir(self.work_dir)
                if any(f.lower().endswith(ext.lower()) for ext in move_formats)
            ]

            for i, f in enumerate(files_to_move):
                if self._cancel_current:
                    return False
                src_path = os.path.join(self.work_dir, f)
                dst_path = os.path.join(roms_folder, f)
                self._fast_move(src_path, dst_path)
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

    @staticmethod
    def _fast_move(src: str, dst: str):
        """Move a file or directory, preferring os.rename (instant on same FS)."""
        try:
            os.rename(src, dst)
        except OSError:
            shutil.move(src, dst)

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
            # Use per-game base URL (from multi-URL listing) or resolve from url field
            base_url = game.get("_base_url") if isinstance(game, dict) else None
            if not base_url:
                url_field = system_data["url"]
                base_url = url_field[0] if isinstance(url_field, list) else url_field
            if isinstance(game, dict) and "href" in game:
                return urljoin(base_url, game["href"])
            else:
                return urljoin(base_url, filename)
        return None

    def _get_roms_folder(self, system_data: Dict[str, Any]) -> str:
        """Get the target ROMs folder for a system."""
        system_name = system_data.get("name", "")
        system_settings = self.settings.get("system_settings", {})
        custom_folder = system_settings.get(system_name, {}).get("custom_folder", "")

        if custom_folder and os.path.exists(custom_folder):
            return custom_folder
        else:
            roms_folder = system_data.get("roms_folder", "")
            # If roms_folder is an absolute path (e.g., from IA collection), use it directly
            if roms_folder and os.path.isabs(roms_folder):
                return roms_folder
            return os.path.join(self.roms_dir, roms_folder)
