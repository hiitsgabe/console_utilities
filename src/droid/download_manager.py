"""
Android DownloadManager — drop-in replacement for the desktop DownloadManager.

Uses Android's system DownloadManager for HTTP downloads (survives app
backgrounding/kill) and a foreground service for post-download extraction.

All pyjnius/android imports are deferred to method scope so this module
is never loaded on desktop/macOS/Windows/console.

Same public API as src/services/download_manager.py:
- add_to_queue(games, system_data, system_name)
- remove_from_queue(index)
- cancel_current()
- cancel_all()
- clear_completed()
- Properties: is_active, active_item, current_progress_text, waiting_count, completed_count
"""

import json
import os
import random
import threading
import time
import traceback
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin

from state import DownloadQueueItem, DownloadQueueState
from droid.ipc import read_status, clear_status, write_cancel
from utils.logging import log_error
from constants import SCRIPT_DIR


# App package name — must match buildozer.spec package.domain + package.name.
# p4a generates service class as: <domain>.<name>.Service<Servicename>
# domain=com.consoleutilities, name=consoleutilities → com.consoleutilities.consoleutilities
_SERVICE_CLASS = "com.consoleutilities.consoleutilities.ServiceExtractionservice"


class AndroidDownloadManager:
    """
    Android-native download manager using system DownloadManager + foreground service.

    Phase 1 (download): Android DownloadManager handles HTTP downloads.
    Phase 2 (extraction): Foreground service handles ZIP/NSZ/move processing.
    """

    def __init__(self, settings: Dict[str, Any], download_queue: DownloadQueueState):
        self.settings = settings
        self.queue = download_queue
        self._lock = threading.Lock()

        # Mapping: android_download_id (long) → DownloadQueueItem
        self._download_ids: Dict[int, DownloadQueueItem] = {}

        # Mapping: item_id (str) → DownloadQueueItem (for extraction IPC)
        self._item_ids: Dict[str, DownloadQueueItem] = {}
        self._next_item_id = 0

        # Android API references (lazy-loaded)
        self._dm = None  # android.app.DownloadManager
        self._activity = None
        self._receiver = None

        # Poll thread for download progress + extraction status
        self._poll_thread: Optional[threading.Thread] = None
        self._stop_poll = False

        self._init_android()

    def _init_android(self):
        """Initialize Android API references and broadcast receiver."""
        from jnius import autoclass

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Context = autoclass("android.content.Context")

        self._activity = PythonActivity.mActivity
        self._dm = self._activity.getSystemService(Context.DOWNLOAD_SERVICE)

        # Register broadcast receiver for download completions
        from droid.receiver import create_download_complete_receiver

        self._receiver = create_download_complete_receiver(
            self._on_download_complete
        )

    @property
    def work_dir(self) -> str:
        return self.settings.get("work_dir", os.path.join(SCRIPT_DIR, "downloads"))

    @property
    def roms_dir(self) -> str:
        return self.settings.get("roms_dir", os.path.join(SCRIPT_DIR, "roms"))

    @property
    def is_active(self) -> bool:
        return self.queue.active or any(
            item.status in ("waiting", "downloading", "extracting", "moving")
            for item in self.queue.items
        )

    @property
    def current_progress_text(self) -> str:
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
        for item in self.queue.items:
            if item.status in ("downloading", "extracting", "moving"):
                return item
        return None

    @property
    def waiting_count(self) -> int:
        return sum(1 for item in self.queue.items if item.status == "waiting")

    @property
    def completed_count(self) -> int:
        return sum(1 for item in self.queue.items if item.status == "completed")

    def add_to_queue(
        self, games: List[Any], system_data: Dict[str, Any], system_name: str
    ):
        with self._lock:
            for game in games:
                item = DownloadQueueItem(
                    game=game,
                    system_data=system_data,
                    system_name=system_name,
                    status="waiting",
                )
                self.queue.items.append(item)

        # Start processing queue
        self._process_next()
        self._start_poll_thread()

    def remove_from_queue(self, index: int) -> bool:
        with self._lock:
            if 0 <= index < len(self.queue.items):
                item = self.queue.items[index]
                if item.status == "waiting":
                    self.queue.items.pop(index)
                    if self.queue.highlighted >= len(self.queue.items):
                        self.queue.highlighted = max(0, len(self.queue.items) - 1)
                    return True
        return False

    def cancel_current(self):
        """Cancel the currently active download or extraction."""
        with self._lock:
            active = self.active_item
            if active is None:
                return

            if active.status == "downloading":
                # Cancel via Android DownloadManager
                download_id = self._find_download_id(active)
                if download_id is not None:
                    self._dm.remove(download_id)
                    self._download_ids.pop(download_id, None)
                active.status = "cancelled"
            elif active.status in ("extracting", "moving"):
                # Signal the extraction service to cancel
                write_cancel(self.work_dir, "current")
                # Status will be updated when service writes to IPC

        # Process next item
        self._process_next()

    def cancel_all(self):
        with self._lock:
            # Cancel active download
            active = self.active_item
            if active and active.status == "downloading":
                download_id = self._find_download_id(active)
                if download_id is not None:
                    self._dm.remove(download_id)
                    self._download_ids.pop(download_id, None)
                active.status = "cancelled"
            elif active and active.status in ("extracting", "moving"):
                write_cancel(self.work_dir, "all")

            # Cancel all waiting items
            for item in self.queue.items:
                if item.status == "waiting":
                    item.status = "cancelled"

    def clear_completed(self):
        with self._lock:
            self.queue.items = [
                item
                for item in self.queue.items
                if item.status not in ("completed", "failed", "cancelled")
            ]
            if self.queue.highlighted >= len(self.queue.items):
                self.queue.highlighted = max(0, len(self.queue.items) - 1)

    # ---- Internal: enqueue downloads via Android DM ----

    def _process_next(self):
        """Find the next waiting item and start its download."""
        with self._lock:
            while True:
                # Check if something is already active
                if any(
                    item.status in ("downloading", "extracting", "moving")
                    for item in self.queue.items
                ):
                    return

                # Find next waiting item
                next_item = None
                for item in self.queue.items:
                    if item.status == "waiting":
                        next_item = item
                        break

                if next_item is None:
                    self.queue.active = False
                    return

                self.queue.active = True
                if self._enqueue_download(next_item):
                    return
                # Enqueue failed (e.g. bad URL) — loop to try next item

    def _enqueue_download(self, item: DownloadQueueItem) -> bool:
        """
        Enqueue a file download via Android DownloadManager.

        Returns True if successfully enqueued, False if failed (caller should
        try next item). Must be called while holding self._lock.
        """
        from jnius import autoclass

        DownloadManagerClass = autoclass("android.app.DownloadManager")
        Request = autoclass("android.app.DownloadManager$Request")
        Uri = autoclass("android.net.Uri")
        Environment = autoclass("android.os.Environment")

        filename = self._get_filename(item.game)
        url = self._get_download_url(item.system_data, item.game, filename)

        if not url:
            item.status = "failed"
            item.error = "Could not determine download URL"
            return False

        # Ensure filename has extension
        formats = item.system_data.get("file_format", [])
        if "download_url" in item.system_data and "." not in filename:
            fmt = formats[0] if formats else ""
            filename = filename + fmt

        # Resolve auth and determine final URL.
        # Android DM strips auth headers on redirect, so for IA authenticated
        # downloads we resolve redirects ourselves to get the final direct URL.
        auth_headers = {}
        is_ia = "archive.org" in url
        is_ia_auth = False

        if "auth" in item.system_data:
            auth_config = item.system_data["auth"]
            if auth_config.get("type") == "ia_s3":
                access_key = auth_config.get("access_key") or None
                secret_key = auth_config.get("secret_key") or None
                if access_key and secret_key:
                    auth_headers["authorization"] = f"LOW {access_key}:{secret_key}"
                    is_ia_auth = True
            elif "token" in auth_config:
                if auth_config.get("cookies", False):
                    cookie_name = auth_config.get("cookie_name", "auth_token")
                    auth_headers["Cookie"] = f"{cookie_name}={auth_config['token']}"
                else:
                    auth_headers["Authorization"] = f"Bearer {auth_config['token']}"

        if is_ia and is_ia_auth:
            # IA auth: manually follow redirects to get the final direct URL
            # (Android DM would strip the auth header on redirect)
            final_url = _resolve_ia_redirects(url, auth_headers)
            if final_url is None:
                item.status = "failed"
                item.error = "IA auth redirect resolution failed"
                return False
            url = final_url

        uri = Uri.parse(url)
        request = Request(uri)

        # Add browser-like headers (servers reject bare requests)
        for name, value in _build_download_headers(url).items():
            request.addRequestHeader(name, value)

        # Add auth headers to the request
        for name, value in auth_headers.items():
            request.addRequestHeader(name, value)

        # Download to app's external files directory
        request.setDestinationInExternalFilesDir(
            self._activity, Environment.DIRECTORY_DOWNLOADS, filename
        )
        request.setTitle(f"Downloading: {filename}")
        request.setDescription(f"Console Utilities - {item.system_name}")
        request.setNotificationVisibility(
            Request.VISIBILITY_VISIBLE
        )

        # Enqueue the download
        download_id = self._dm.enqueue(request)

        item.status = "downloading"
        item.progress = 0.0
        item.downloaded = 0
        item.speed = 0.0

        # Track the mapping
        item_id = str(self._next_item_id)
        self._next_item_id += 1
        self._download_ids[download_id] = item
        self._item_ids[item_id] = item
        # Store item_id on the item for IPC lookup
        item._android_item_id = item_id
        item._android_download_id = download_id
        item._android_filename = filename

        return True

    def _on_download_complete(self, download_id: int):
        """Callback from BroadcastReceiver when a download finishes."""
        with self._lock:
            item = self._download_ids.pop(download_id, None)
            if item is None:
                return

            # Check if download succeeded
            from jnius import autoclass

            DownloadManagerClass = autoclass("android.app.DownloadManager")
            Query = autoclass("android.app.DownloadManager$Query")

            query = Query()
            query.setFilterById(download_id)
            cursor = self._dm.query(query)

            if cursor and cursor.moveToFirst():
                status_col = cursor.getColumnIndex(
                    DownloadManagerClass.COLUMN_STATUS
                )
                status = cursor.getInt(status_col)
                cursor.close()

                if status == DownloadManagerClass.STATUS_SUCCESSFUL:
                    # Get the downloaded file path
                    file_path = self._get_downloaded_file_path(download_id)
                    if file_path:
                        self._start_extraction_service(item, file_path)
                    else:
                        item.status = "failed"
                        item.error = "Downloaded file not found"
                else:
                    item.status = "failed"
                    # Check if this is an IA URL without auth — likely needs login
                    url = self._get_download_url(
                        item.system_data, item.game, ""
                    )
                    if url and "archive.org" in url and "auth" not in item.system_data:
                        item.error = "ia_auth_required"
                    else:
                        item.error = f"Download failed (status: {status})"
            else:
                if cursor:
                    cursor.close()
                item.status = "failed"
                item.error = "Download status unknown"

        # Process next (outside lock to avoid holding lock during Java calls)
        if item and item.status == "failed":
            self._process_next()

    def _get_downloaded_file_path(self, download_id: int) -> Optional[str]:
        """Get the local file path for a completed download."""
        from jnius import autoclass
        from urllib.parse import unquote

        DownloadManagerClass = autoclass("android.app.DownloadManager")
        Query = autoclass("android.app.DownloadManager$Query")

        query = Query()
        query.setFilterById(download_id)
        cursor = self._dm.query(query)

        if cursor and cursor.moveToFirst():
            uri_col = cursor.getColumnIndex(
                DownloadManagerClass.COLUMN_LOCAL_URI
            )
            local_uri = cursor.getString(uri_col)
            cursor.close()

            if local_uri and local_uri.startswith("file://"):
                return unquote(local_uri[7:])  # Strip file:// and decode %20 etc.
            return local_uri

        if cursor:
            cursor.close()
        return None

    def _start_extraction_service(self, item: DownloadQueueItem, file_path: str):
        """Start the foreground extraction service for a downloaded file."""
        from jnius import autoclass

        item.status = "extracting"
        item.progress = 0.0

        item_id = getattr(item, "_android_item_id", str(id(item)))
        filename = getattr(item, "_android_filename", os.path.basename(file_path))

        roms_folder = self._get_roms_folder(item.system_data)

        task_info = {
            "file_path": file_path,
            "filename": filename,
            "work_dir": self.work_dir,
            "roms_folder": roms_folder,
            "system_data": item.system_data,
            "item_id": item_id,
        }

        # Use p4a's generated service class .start() method
        # The service receives the argument via PYTHON_SERVICE_ARGUMENT env var
        ServiceClass = autoclass(_SERVICE_CLASS)
        ServiceClass.start(self._activity, json.dumps(task_info))

    # ---- Poll thread for progress updates ----

    def _start_poll_thread(self):
        """Start a background thread to poll download progress and extraction status."""
        if self._poll_thread and self._poll_thread.is_alive():
            return
        self._stop_poll = False
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

    def _poll_loop(self):
        """Poll Android DM for download progress and IPC for extraction status."""
        while not self._stop_poll:
            try:
                self._poll_download_progress()
                self._poll_extraction_status()
            except Exception as e:
                log_error(
                    f"Poll loop error: {e}",
                    type(e).__name__,
                    traceback.format_exc(),
                )
            time.sleep(0.5)

            # Stop polling if nothing is active
            if not self.is_active:
                break

    def _poll_download_progress(self):
        """Query Android DownloadManager for current download progress."""
        from jnius import autoclass

        DownloadManagerClass = autoclass("android.app.DownloadManager")
        Query = autoclass("android.app.DownloadManager$Query")

        now = time.time()
        failed_items = []

        with self._lock:
            for download_id, item in list(self._download_ids.items()):
                if item.status != "downloading":
                    continue

                query = Query()
                query.setFilterById(download_id)
                cursor = self._dm.query(query)

                if cursor and cursor.moveToFirst():
                    status_col = cursor.getColumnIndex(
                        DownloadManagerClass.COLUMN_STATUS
                    )
                    downloaded_col = cursor.getColumnIndex(
                        DownloadManagerClass.COLUMN_BYTES_DOWNLOADED_SO_FAR
                    )
                    total_col = cursor.getColumnIndex(
                        DownloadManagerClass.COLUMN_TOTAL_SIZE_BYTES
                    )

                    dm_status = cursor.getInt(status_col)
                    downloaded = cursor.getLong(downloaded_col)
                    total = cursor.getLong(total_col)

                    # Check for failure
                    if dm_status == DownloadManagerClass.STATUS_FAILED:
                        reason_col = cursor.getColumnIndex(
                            DownloadManagerClass.COLUMN_REASON
                        )
                        reason = cursor.getInt(reason_col)
                        cursor.close()
                        item.status = "failed"
                        item.error = f"Download failed (reason: {reason})"
                        self._download_ids.pop(download_id, None)
                        failed_items.append(item)
                        continue

                    cursor.close()

                    old_downloaded = item.downloaded
                    item.downloaded = downloaded
                    item.total_size = total if total > 0 else item.total_size

                    if item.total_size > 0:
                        item.progress = item.downloaded / item.total_size

                    # Speed based on actual elapsed time
                    last_poll = getattr(item, "_last_poll_time", 0.0)
                    elapsed = now - last_poll if last_poll > 0 else 0.5
                    if elapsed > 0.1:
                        item.speed = (downloaded - old_downloaded) / elapsed
                        item._last_poll_time = now
                else:
                    if cursor:
                        cursor.close()

        # Process next item if any failed (outside lock)
        if failed_items:
            self._process_next()

    def _poll_extraction_status(self):
        """Check IPC status files for extraction progress updates."""
        statuses = read_status(self.work_dir)
        needs_next = False

        with self._lock:
            for item_id, status_data in statuses.items():
                item = self._item_ids.get(item_id)
                if item is None:
                    continue

                new_status = status_data.get("status", "")
                progress = status_data.get("progress", 0.0)
                error = status_data.get("error", "")

                if new_status in ("extracting", "moving"):
                    item.status = new_status
                    item.progress = progress
                elif new_status == "completed":
                    item.status = "completed"
                    item.progress = 1.0
                    clear_status(self.work_dir, item_id)
                    needs_next = True
                elif new_status == "failed":
                    item.status = "failed"
                    item.error = error or "Extraction failed"
                    clear_status(self.work_dir, item_id)
                    needs_next = True
                elif new_status == "cancelled":
                    item.status = "cancelled"
                    clear_status(self.work_dir, item_id)
                    needs_next = True

        # Process next outside the lock
        if needs_next:
            self._process_next()

    # ---- Helpers (mirrors desktop DownloadManager) ----

    def _find_download_id(self, item: DownloadQueueItem) -> Optional[int]:
        """Find the Android download ID for a queue item."""
        for download_id, mapped_item in self._download_ids.items():
            if mapped_item is item:
                return download_id
        return None

    def _get_filename(self, game: Any) -> str:
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
        system_name = system_data.get("name", "")
        system_settings = self.settings.get("system_settings", {})
        custom_folder = system_settings.get(system_name, {}).get("custom_folder", "")

        if custom_folder and os.path.exists(custom_folder):
            return custom_folder
        else:
            roms_folder = system_data.get("roms_folder", "")
            if roms_folder and os.path.isabs(roms_folder):
                return roms_folder
            return os.path.join(self.roms_dir, roms_folder)


def _build_download_headers(url):
    """Build browser-like headers so download servers don't reject the request."""
    languages = [
        "en-US,en;q=0.9",
        "en-GB,en;q=0.9",
        "en-US,en;q=0.8,es;q=0.6",
        "en-US,en;q=0.9,de;q=0.7",
    ]
    platforms = ['"Windows"', '"macOS"', '"Linux"']

    major = random.randint(135, 139)
    build = random.randint(0, 9)
    pick = random.randint(0, 99)
    if pick < 55:
        ua = (
            f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            f" (KHTML, like Gecko) Chrome/{major}.0.{build}.0 Safari/537.36"
        )
    elif pick < 80:
        ff = random.randint(125, 128)
        ua = f"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:{ff}.0) Gecko/20100101 Firefox/{ff}.0"
    else:
        sv = random.randint(0, 5)
        ua = (
            f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15"
            f" (KHTML, like Gecko) Version/17.{sv} Safari/605.1.15"
        )

    referer_end = url.rfind("/")
    referer = url[: referer_end + 1] if referer_end > 0 else url

    chrome_ver = random.randint(135, 139)
    headers = {
        "User-Agent": ua,
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,image/apng,*/*;q=0.8,"
            "application/signed-exchange;v=b3;q=0.7"
        ),
        "Accept-Language": random.choice(languages),
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Connection": "keep-alive",
        "Pragma": "no-cache",
        "Cache-Control": "no-cache",
        "Referer": referer,
        "sec-ch-ua": f'"Not)A;Brand";v="8", "Chromium";v="{chrome_ver}", "Google Chrome";v="{chrome_ver}"',
        "sec-ch-ua-mobile": "?0" if random.random() > 0.5 else "?1",
        "sec-ch-ua-platform": random.choice(platforms),
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "same-origin" if random.randint(0, 9) < 8 else "none",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
    }
    return headers


def _resolve_ia_redirects(url, auth_headers, max_redirects=5):
    """
    Follow IA redirects manually, preserving auth headers across hops.

    Android DownloadManager strips Authorization on redirect. So we resolve
    the final direct-download URL here and hand that to Android DM.

    Returns the final URL, or None on failure.
    """
    import requests

    request_headers = _build_download_headers(url)
    request_headers.update(auth_headers)

    current_url = url
    for _ in range(max_redirects):
        try:
            resp = requests.get(
                current_url,
                stream=True,
                timeout=30,
                headers=request_headers,
                allow_redirects=False,
            )
            if resp.status_code in (301, 302, 303, 307, 308):
                current_url = resp.headers.get("Location", current_url)
                resp.close()
                continue
            else:
                resp.close()
                return current_url
        except Exception:
            return None
    return None
