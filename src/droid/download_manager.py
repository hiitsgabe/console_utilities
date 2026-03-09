"""
Android DownloadManager — drop-in replacement for the desktop DownloadManager.

Uses a custom Python foreground service (DownloadService) for HTTP downloads
with parallel chunk support, and ExtractionService for post-download processing.

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
import threading
import time
import traceback
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin

from state import DownloadQueueItem, DownloadQueueState
from droid.ipc import (
    read_status,
    clear_status,
    write_cancel,
    write_download_task,
)
from utils.logging import log_error
from constants import SCRIPT_DIR


# p4a generates service class as: <domain>.<name>.Service<Servicename>
_DOWNLOAD_SERVICE_CLASS = "com.consoleutilities.consoleutilities.ServiceDownloadservice"


class AndroidDownloadManager:
    """
    Android download manager using custom DownloadService + ExtractionService.

    Phase 1 (download): DownloadService handles HTTP downloads with parallel chunks.
    Phase 2 (extraction): ExtractionService handles ZIP/NSZ/move processing.
    """

    def __init__(self, settings: Dict[str, Any], download_queue: DownloadQueueState):
        self.settings = settings
        self.queue = download_queue
        self._lock = threading.Lock()

        # Mapping: item_id (str) → DownloadQueueItem
        self._item_ids: Dict[str, DownloadQueueItem] = {}
        self._next_item_id = 0

        # Android API references (lazy-loaded)
        self._activity = None

        # Poll thread for download/extraction status via IPC
        self._poll_thread: Optional[threading.Thread] = None
        self._stop_poll = False

        self._init_android()

    def _init_android(self):
        """Initialize Android API references."""
        from jnius import autoclass

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        self._activity = PythonActivity.mActivity

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
            write_cancel(self.work_dir, "current")

    def cancel_all(self):
        with self._lock:
            write_cancel(self.work_dir, "all")
            for item in self.queue.items:
                if item.status == "waiting":
                    item.status = "cancelled"

    def pause(self):
        """Pause polling when the Android activity is backgrounded."""
        pass  # Download service runs independently; no JNI to pause

    def resume(self):
        """Resume polling when the Android activity is foregrounded."""
        # Re-acquire activity reference
        try:
            from jnius import autoclass

            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            self._activity = PythonActivity.mActivity
        except Exception as e:
            log_error(f"Failed to re-acquire activity: {e}")

        # Restart poll thread if downloads are active
        if self.is_active:
            self._start_poll_thread()

    def clear_completed(self):
        with self._lock:
            self.queue.items = [
                item
                for item in self.queue.items
                if item.status not in ("completed", "failed", "cancelled")
            ]
            if self.queue.highlighted >= len(self.queue.items):
                self.queue.highlighted = max(0, len(self.queue.items) - 1)

    # ---- Internal: dispatch downloads to DownloadService ----

    def _process_next(self):
        """Find the next waiting item and start its download via DownloadService."""
        with self._lock:
            while True:
                if any(
                    item.status in ("downloading", "extracting", "moving")
                    for item in self.queue.items
                ):
                    return

                next_item = None
                for item in self.queue.items:
                    if item.status == "waiting":
                        next_item = item
                        break

                if next_item is None:
                    self.queue.active = False
                    return

                self.queue.active = True
                if self._start_download(next_item):
                    return
                # Start failed — loop to try next item

    def _start_download(self, item: DownloadQueueItem) -> bool:
        """
        Start a download via DownloadService.

        Returns True if successfully started, False if failed.
        Must be called while holding self._lock.
        """
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

        # Build auth headers and cookies
        auth_headers = {}
        cookies = {}
        if "auth" in item.system_data:
            auth_config = item.system_data["auth"]
            if auth_config.get("type") == "ia_s3":
                access_key = auth_config.get("access_key") or None
                secret_key = auth_config.get("secret_key") or None
                if access_key and secret_key:
                    auth_headers["authorization"] = f"LOW {access_key}:{secret_key}"
            elif "token" in auth_config:
                if auth_config.get("cookies", False):
                    cookie_name = auth_config.get("cookie_name", "auth_token")
                    cookies[cookie_name] = auth_config["token"]
                else:
                    auth_headers["Authorization"] = f"Bearer {auth_config['token']}"

        item.status = "downloading"
        item.progress = 0.0
        item.downloaded = 0
        item.speed = 0.0

        # Assign item ID
        item_id = str(self._next_item_id)
        self._next_item_id += 1
        self._item_ids[item_id] = item
        item._android_item_id = item_id

        roms_folder = self._get_roms_folder(item.system_data)

        # Merge per-system settings overrides
        effective_system_data = dict(item.system_data)
        system_name = effective_system_data.get("name", "")
        per_sys = self.settings.get("system_settings", {}).get(system_name, {})
        if "should_unzip" in per_sys:
            effective_system_data["should_unzip"] = per_sys["should_unzip"]

        task_info = {
            "item_id": item_id,
            "url": url,
            "filename": filename,
            "work_dir": self.work_dir,
            "roms_folder": roms_folder,
            "system_data": effective_system_data,
            "system_name": item.system_name,
            "auth_headers": auth_headers,
            "cookies": cookies,
        }

        # Write task and start service
        try:
            write_download_task(self.work_dir, task_info)

            from jnius import autoclass

            ServiceClass = autoclass(_DOWNLOAD_SERVICE_CLASS)
            ServiceClass.start(self._activity, json.dumps(task_info))
            return True
        except Exception as e:
            item.status = "failed"
            item.error = f"Failed to start download: {e}"
            log_error(
                f"Download service start failed: {e}",
                type(e).__name__,
                traceback.format_exc(),
            )
            return False

    # ---- Poll thread for status updates via IPC ----

    def _start_poll_thread(self):
        if self._poll_thread and self._poll_thread.is_alive():
            return
        self._stop_poll = False
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

    def _poll_loop(self):
        """Poll IPC status files for download and extraction progress."""
        while not self._stop_poll:
            try:
                self._poll_status()
            except Exception as e:
                log_error(
                    f"Poll loop error: {e}",
                    type(e).__name__,
                    traceback.format_exc(),
                )
            time.sleep(0.5)

            if not self.is_active:
                break

    def _poll_status(self):
        """Check IPC status files for download/extraction progress."""
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

                if new_status == "downloading":
                    item.status = "downloading"
                    item.progress = progress
                    item.downloaded = status_data.get("downloaded", 0)
                    item.total_size = status_data.get("total_size", 0)
                    item.speed = status_data.get("speed", 0.0)
                elif new_status in ("extracting", "moving"):
                    item.status = new_status
                    item.progress = progress
                elif new_status == "completed":
                    item.status = "completed"
                    item.progress = 1.0
                    clear_status(self.work_dir, item_id)
                    needs_next = True
                elif new_status == "failed":
                    item.status = "failed"
                    item.error = error or "Download failed"
                    clear_status(self.work_dir, item_id)
                    needs_next = True
                elif new_status == "cancelled":
                    item.status = "cancelled"
                    clear_status(self.work_dir, item_id)
                    needs_next = True

        if needs_next:
            self._process_next()

    # ---- Helpers ----

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
