# Android Parallel Chunk Download Service Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace Android's single-stream system DownloadManager with a custom Python foreground service that downloads files using parallel HTTP range-request chunks for faster speeds.

**Architecture:** A new p4a foreground service (`DownloadService`) receives task JSON via IPC, performs HEAD to check range support, splits large files (>5MB) into 4 parallel chunk workers via `ThreadPoolExecutor`, stitches chunks, then triggers the existing `ExtractionService`. The main app's `AndroidDownloadManager` is simplified to write task JSON and poll status via existing IPC.

**Tech Stack:** Python `requests`, `concurrent.futures.ThreadPoolExecutor`, `threading`, p4a foreground service, Android notification API via pyjnius

---

### Task 1: Add download task IPC helpers

**Files:**
- Modify: `src/droid/ipc.py`

**Step 1: Add download task IPC constants and functions**

Add these constants after the existing `_CANCEL_FILENAME` line (line 14):

```python
_DOWNLOAD_TASK_FILENAME = "download_task.json"
```

Update `IPC_FILENAMES` to include the new file:

```python
IPC_FILENAMES = frozenset(
    {
        _STATUS_FILENAME,
        _CANCEL_FILENAME,
        _STATUS_FILENAME + ".tmp",
        _DOWNLOAD_TASK_FILENAME,
        _DOWNLOAD_TASK_FILENAME + ".tmp",
    }
)
```

Add these functions at the end of the file, before `_read_json`:

```python
def write_download_task(work_dir, task_dict):
    """
    Write a download task for the download service to pick up.

    Args:
        work_dir: Working directory for IPC files
        task_dict: Dict with url, filename, auth_headers, cookies, etc.
    """
    path = os.path.join(work_dir, _DOWNLOAD_TASK_FILENAME)
    _write_json(path, task_dict)


def read_download_task(work_dir):
    """
    Read the current download task. Called by the download service.

    Returns:
        Task dict or None if no task pending.
    """
    path = os.path.join(work_dir, _DOWNLOAD_TASK_FILENAME)
    return _read_json(path)


def clear_download_task(work_dir):
    """
    Clear the download task after the service has picked it up.
    """
    path = os.path.join(work_dir, _DOWNLOAD_TASK_FILENAME)
    if os.path.exists(path):
        os.remove(path)
```

**Step 2: Run lint**

Run: `cd /Users/gabe/Workspace/Games/console_utilities && make format && make lint`
Expected: PASS

**Step 3: Commit**

```bash
git add src/droid/ipc.py
git commit -m "feat(droid): add download task IPC helpers"
```

---

### Task 2: Add download notification channel

**Files:**
- Modify: `src/droid/notification.py`

**Step 1: Add download channel constants**

Add after the existing extraction constants (line 14):

```python
DOWNLOAD_CHANNEL_ID = "consoleutilities_download"
DOWNLOAD_CHANNEL_NAME = "Download Progress"
DOWNLOAD_NOTIFICATION_ID = 9002
```

**Step 2: Add download notification helpers**

Add these functions at the end of the file:

```python
def create_download_notification_channel(context):
    """
    Create the notification channel for download progress.

    Args:
        context: Android Context (PythonService.mService)
    """
    from jnius import autoclass

    Context = autoclass("android.content.Context")
    NotificationChannel = autoclass("android.app.NotificationChannel")
    NotificationManager = autoclass("android.app.NotificationManager")

    manager = context.getSystemService(Context.NOTIFICATION_SERVICE)

    channel = NotificationChannel(
        DOWNLOAD_CHANNEL_ID,
        DOWNLOAD_CHANNEL_NAME,
        NotificationManager.IMPORTANCE_LOW,
    )
    channel.setDescription("Shows download progress for games")
    manager.createNotificationChannel(channel)


def build_download_notification(context, title, progress=-1, max_progress=100):
    """
    Build a Notification for the download foreground service.

    Args:
        context: Android Context (PythonService.mService)
        title: Notification title text
        progress: Current progress value, or -1 for indeterminate
        max_progress: Maximum progress value

    Returns:
        Android Notification object
    """
    from jnius import autoclass

    NotificationBuilder = autoclass("android.app.Notification$Builder")

    builder = NotificationBuilder(context, DOWNLOAD_CHANNEL_ID)
    builder.setContentTitle(title)
    builder.setSmallIcon(context.getApplicationInfo().icon)
    builder.setOngoing(True)

    if progress >= 0:
        builder.setProgress(max_progress, progress, False)
        pct = int(progress * 100 / max_progress) if max_progress > 0 else 0
        builder.setContentText(f"{pct}%")
    else:
        builder.setProgress(0, 0, True)
        builder.setContentText("Starting download...")

    return builder.build()


def update_download_notification(context, title, progress=-1, max_progress=100):
    """
    Update the existing download foreground service notification.

    Args:
        context: Android Context (PythonService.mService)
        title: Updated title text
        progress: Current progress value, or -1 for indeterminate
        max_progress: Maximum progress value
    """
    from jnius import autoclass

    Context = autoclass("android.content.Context")
    NotificationManager = autoclass("android.app.NotificationManager")

    manager = context.getSystemService(Context.NOTIFICATION_SERVICE)

    notification = build_download_notification(context, title, progress, max_progress)
    manager.notify(DOWNLOAD_NOTIFICATION_ID, notification)
```

**Step 3: Run lint**

Run: `cd /Users/gabe/Workspace/Games/console_utilities && make format && make lint`
Expected: PASS

**Step 4: Commit**

```bash
git add src/droid/notification.py
git commit -m "feat(droid): add download notification channel and helpers"
```

---

### Task 3: Create the download foreground service

**Files:**
- Create: `src/droid/download_service.py`

This is the core of the feature — a p4a foreground service that performs HTTP downloads with parallel chunk support.

**Step 1: Create `src/droid/download_service.py`**

```python
"""
DownloadService — p4a foreground service for parallel chunk HTTP downloads.

Replaces Android's system DownloadManager with a custom Python implementation
that supports HTTP range requests for parallel chunk downloads of large files.

Same lifecycle pattern as ExtractionService (service.py):
- Launched via startForegroundService()
- Runs with wake lock + foreground notification
- Communicates progress via shared JSON files (ipc.py)
- On download complete, triggers ExtractionService for post-processing

p4a service argument: task JSON via PYTHON_SERVICE_ARGUMENT env var.
"""

import json
import os
import shutil
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Dict, List, Optional
from urllib.parse import urljoin

# Add src to path (p4a service may not have it)
_service_dir = os.path.dirname(os.path.abspath(__file__))
_src_dir = os.path.dirname(_service_dir)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from droid.ipc import write_status, read_cancel, clear_cancel, clear_download_task
from droid.notification import (
    create_download_notification_channel,
    build_download_notification,
    update_download_notification,
    DOWNLOAD_NOTIFICATION_ID,
)

from jnius import autoclass

PythonService = autoclass("org.kivy.android.PythonService")
PowerManager = autoclass("android.os.PowerManager")
Context = autoclass("android.content.Context")

# Parallel download constants (match desktop download_manager.py)
PARALLEL_MIN_SIZE = 5 * 1024 * 1024  # 5 MB
PARALLEL_WORKERS = 4


def run_service():
    """
    Main entry point for the download foreground service.

    Reads task info from PYTHON_SERVICE_ARGUMENT env var, downloads the file
    (with parallel chunks if supported), and communicates progress via IPC.
    On success, starts the ExtractionService for post-processing.
    """
    service = PythonService.mService

    # Acquire wake lock to keep CPU active during download
    power_manager = service.getSystemService(Context.POWER_SERVICE)
    wake_lock = power_manager.newWakeLock(
        PowerManager.PARTIAL_WAKE_LOCK, "consoleutilities:download"
    )
    wake_lock.acquire()

    try:
        # Set up notification channel and start foreground
        create_download_notification_channel(service)
        notification = build_download_notification(service, "Preparing download...")
        service.startForeground(DOWNLOAD_NOTIFICATION_ID, notification)

        # Read task info
        task_json = os.environ.get("PYTHON_SERVICE_ARGUMENT", "")
        if not task_json:
            return

        task = json.loads(task_json)
        _process_download(service, task)

    except Exception as e:
        try:
            task_json = os.environ.get("PYTHON_SERVICE_ARGUMENT", "")
            if task_json:
                task = json.loads(task_json)
                write_status(
                    task["work_dir"],
                    task["item_id"],
                    {
                        "status": "failed",
                        "progress": 0.0,
                        "error": f"{type(e).__name__}: {str(e)[:100]}",
                    },
                )
        except Exception:
            pass
    finally:
        if wake_lock.isHeld():
            wake_lock.release()
        service.stopForeground(True)
        service.stopSelf()


def _process_download(service, task):
    """
    Download a file, then trigger ExtractionService on success.
    """
    import requests

    item_id = task["item_id"]
    url = task["url"]
    filename = task["filename"]
    work_dir = task["work_dir"]
    auth_headers = task.get("auth_headers", {})
    cookies = task.get("cookies", {})

    os.makedirs(work_dir, exist_ok=True)

    # Clear the task file now that we've picked it up
    clear_download_task(work_dir)

    # Build request headers
    request_headers = _build_download_headers(url)
    request_headers.update(auth_headers)

    # Resolve final URL (follow redirects for IA auth)
    is_ia = "archive.org" in url
    is_ia_auth = bool(auth_headers.get("authorization", ""))

    try:
        resolved_url = url
        if is_ia and is_ia_auth:
            resolved_url = _resolve_redirects(url, request_headers, cookies)
            if resolved_url is None:
                write_status(work_dir, item_id, {
                    "status": "failed",
                    "progress": 0.0,
                    "error": "IA auth redirect resolution failed",
                })
                return
        else:
            # Do a HEAD to resolve redirects and check range support
            resp = requests.head(
                url,
                headers=request_headers,
                cookies=cookies,
                timeout=(15, 30),
                allow_redirects=True,
            )
            resp.raise_for_status()
            resolved_url = resp.url

        # Probe for range support and content length
        resp = requests.head(
            resolved_url,
            headers=request_headers,
            cookies=cookies,
            timeout=(15, 30),
            allow_redirects=True,
        )
        total_size = int(resp.headers.get("content-length", 0))
        accept_ranges = resp.headers.get("accept-ranges", "").lower()

        write_status(work_dir, item_id, {
            "status": "downloading",
            "progress": 0.0,
            "downloaded": 0,
            "total_size": total_size,
            "speed": 0.0,
        })

        update_download_notification(service, f"Downloading: {filename}", 0, 100)

        # Choose download strategy
        if accept_ranges == "bytes" and total_size > PARALLEL_MIN_SIZE:
            file_path = _download_parallel(
                service, item_id, resolved_url, filename, total_size,
                work_dir, request_headers, cookies,
            )
        else:
            file_path = _download_single(
                service, item_id, resolved_url, filename, total_size,
                work_dir, request_headers, cookies,
            )

        if file_path is None:
            # Cancelled or failed — status already written
            return

        # Download complete — trigger extraction service
        update_download_notification(service, f"Downloaded: {filename}", 100, 100)
        _start_extraction_service(service, task, file_path)

    except Exception as e:
        error_msg = str(e)[:100]
        if (
            hasattr(e, "response")
            and e.response is not None
            and e.response.status_code in (401, 403)
            and "archive.org" in url
        ):
            error_msg = "ia_auth_required"
        write_status(work_dir, item_id, {
            "status": "failed",
            "progress": 0.0,
            "error": error_msg,
        })


def _download_single(
    service, item_id, url, filename, total_size,
    work_dir, headers, cookies,
):
    """Single-stream download. Returns file path or None."""
    import requests

    file_path = os.path.join(work_dir, filename)
    downloaded = 0
    last_update = time.time()
    last_downloaded = 0
    speed_samples = []

    resp = requests.get(
        url,
        stream=True,
        timeout=(15, 60),
        headers=headers,
        cookies=cookies,
        allow_redirects=True,
    )
    resp.raise_for_status()

    # Update total_size from response if HEAD didn't provide it
    if total_size == 0:
        total_size = int(resp.headers.get("content-length", 0))

    with open(file_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=262144):
            # Check cancel
            if _check_cancel(work_dir, item_id):
                f.close()
                if os.path.exists(file_path):
                    os.remove(file_path)
                return None

            if chunk:
                f.write(chunk)
                downloaded += len(chunk)

                now = time.time()
                elapsed = now - last_update
                if elapsed >= 0.5:
                    speed = (downloaded - last_downloaded) / elapsed
                    speed_samples.append(speed)
                    if len(speed_samples) > 4:
                        speed_samples.pop(0)
                    avg_speed = sum(speed_samples) / len(speed_samples)
                    last_downloaded = downloaded
                    last_update = now

                    progress = downloaded / total_size if total_size > 0 else 0.0
                    write_status(work_dir, item_id, {
                        "status": "downloading",
                        "progress": progress,
                        "downloaded": downloaded,
                        "total_size": total_size,
                        "speed": avg_speed,
                    })
                    pct = int(progress * 100)
                    update_download_notification(
                        service, f"Downloading: {filename}", pct, 100
                    )

    return file_path


def _download_parallel(
    service, item_id, url, filename, total_size,
    work_dir, headers, cookies,
    num_workers=PARALLEL_WORKERS,
):
    """Parallel range-request download. Returns file path or None."""
    file_path = os.path.join(work_dir, filename)

    # Compute chunk boundaries
    chunk_size = total_size // num_workers
    chunks = []
    for i in range(num_workers):
        start = i * chunk_size
        end = (total_size - 1) if i == num_workers - 1 else ((i + 1) * chunk_size - 1)
        chunks.append((start, end))

    progress_array = [0] * num_workers
    chunk_paths = [
        os.path.join(work_dir, f".{filename}.part{i}")
        for i in range(num_workers)
    ]
    chunk_failed = threading.Event()

    def worker(chunk_index):
        return _download_chunk(
            url, headers, cookies,
            chunks[chunk_index][0], chunks[chunk_index][1],
            chunk_paths[chunk_index], chunk_index,
            progress_array, chunk_failed,
        )

    executor = ThreadPoolExecutor(max_workers=num_workers)
    futures = []
    try:
        for i in range(num_workers):
            futures.append(executor.submit(worker, i))

        # Poll progress
        last_update = time.time()
        last_downloaded = 0
        speed_samples = []

        while not all(f.done() for f in futures):
            # Check cancel
            if _check_cancel(work_dir, item_id):
                chunk_failed.set()
                executor.shutdown(wait=False, cancel_futures=True)
                _cleanup_chunks(chunk_paths)
                return None

            time.sleep(0.1)

            downloaded = sum(progress_array)
            now = time.time()
            elapsed = now - last_update
            if elapsed >= 0.5:
                speed = (downloaded - last_downloaded) / elapsed
                speed_samples.append(speed)
                if len(speed_samples) > 4:
                    speed_samples.pop(0)
                avg_speed = sum(speed_samples) / len(speed_samples)
                last_downloaded = downloaded
                last_update = now

                progress = downloaded / total_size if total_size > 0 else 0.0
                write_status(work_dir, item_id, {
                    "status": "downloading",
                    "progress": progress,
                    "downloaded": downloaded,
                    "total_size": total_size,
                    "speed": avg_speed,
                })
                pct = int(progress * 100)
                update_download_notification(
                    service, f"Downloading: {filename}", pct, 100
                )

        # Check results
        for f in futures:
            if not f.result():
                write_status(work_dir, item_id, {
                    "status": "failed",
                    "progress": 0.0,
                    "error": "Chunk download failed",
                })
                _cleanup_chunks(chunk_paths)
                return None

    except Exception:
        chunk_failed.set()
        executor.shutdown(wait=False, cancel_futures=True)
        _cleanup_chunks(chunk_paths)
        raise
    finally:
        executor.shutdown(wait=False)

    # Stitch chunks into final file
    try:
        with open(file_path, "wb") as out_f:
            for cp in chunk_paths:
                with open(cp, "rb") as in_f:
                    shutil.copyfileobj(in_f, out_f)
        _cleanup_chunks(chunk_paths)
    except Exception as e:
        _cleanup_chunks(chunk_paths)
        if os.path.exists(file_path):
            os.remove(file_path)
        write_status(work_dir, item_id, {
            "status": "failed",
            "progress": 0.0,
            "error": f"Stitch failed: {str(e)[:50]}",
        })
        return None

    return file_path


def _download_chunk(url, headers, cookies, start, end, chunk_path,
                    chunk_index, progress_array, failed_event):
    """Download a single byte range to a temp file."""
    import requests

    try:
        range_headers = dict(headers)
        range_headers["Range"] = f"bytes={start}-{end}"

        resp = requests.get(
            url,
            stream=True,
            timeout=(15, 60),
            headers=range_headers,
            cookies=cookies,
            allow_redirects=True,
        )
        resp.raise_for_status()

        with open(chunk_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=262144):
                if failed_event.is_set():
                    return False
                if chunk:
                    f.write(chunk)
                    progress_array[chunk_index] += len(chunk)

        return True
    except Exception:
        failed_event.set()
        return False


def _cleanup_chunks(chunk_paths):
    """Remove temp .partN files."""
    for path in chunk_paths:
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass


def _check_cancel(work_dir, item_id):
    """Check for cancel signal. Returns True if should stop."""
    cancel = read_cancel(work_dir)
    if cancel:
        cancel_type = cancel.get("type", "")
        if cancel_type in ("current", "all"):
            clear_cancel(work_dir)
            write_status(work_dir, item_id, {
                "status": "cancelled",
                "progress": 0.0,
            })
            return True
    return False


def _start_extraction_service(service, task, file_path):
    """Start ExtractionService for post-download processing."""
    _EXTRACTION_SERVICE_CLASS = (
        "com.consoleutilities.consoleutilities.ServiceExtractionservice"
    )

    task_info = {
        "file_path": file_path,
        "filename": task["filename"],
        "work_dir": task["work_dir"],
        "roms_folder": task["roms_folder"],
        "system_data": task["system_data"],
        "item_id": task["item_id"],
    }

    try:
        ServiceClass = autoclass(_EXTRACTION_SERVICE_CLASS)
        ServiceClass.start(service, json.dumps(task_info))
    except Exception:
        # If extraction service fails to start, still mark download as complete
        # so user can see the file was downloaded
        write_status(task["work_dir"], task["item_id"], {
            "status": "completed",
            "progress": 1.0,
        })


def _resolve_redirects(url, headers, cookies, max_redirects=5):
    """Follow redirects manually, preserving auth headers. Returns final URL or None."""
    import requests

    current_url = url
    verify = True
    for _ in range(max_redirects):
        try:
            resp = requests.get(
                current_url,
                stream=True,
                timeout=30,
                headers=headers,
                cookies=cookies,
                allow_redirects=False,
                verify=verify,
            )
            if resp.status_code in (301, 302, 303, 307, 308):
                current_url = resp.headers.get("Location", current_url)
                resp.close()
                continue
            else:
                resp.close()
                return current_url
        except (requests.exceptions.SSLError, requests.exceptions.ConnectionError):
            if verify:
                verify = False
                continue
            return None
        except Exception:
            return None
    return None


def _build_download_headers(url):
    """Build browser-like headers so download servers don't reject the request."""
    import random

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


# p4a service entry point
if __name__ == "__main__":
    run_service()
```

**Step 2: Run lint**

Run: `cd /Users/gabe/Workspace/Games/console_utilities && make format && make lint`
Expected: PASS

**Step 3: Commit**

```bash
git add src/droid/download_service.py
git commit -m "feat(droid): add parallel chunk download foreground service"
```

---

### Task 4: Register the download service in buildozer.spec

**Files:**
- Modify: `buildozer.spec` (line 23)

**Step 1: Add DownloadService to the services line**

Change:
```
services = ExtractionService:./src/droid/service.py:foreground:sticky
```

To:
```
services = ExtractionService:./src/droid/service.py:foreground:sticky,DownloadService:./src/droid/download_service.py:foreground:sticky
```

This tells p4a to generate `com.consoleutilities.consoleutilities.ServiceDownloadservice` Java class.

**Step 2: Commit**

```bash
git add buildozer.spec
git commit -m "feat(droid): register DownloadService in buildozer.spec"
```

---

### Task 5: Rewrite AndroidDownloadManager to use the download service

**Files:**
- Modify: `src/droid/download_manager.py`

This is the largest change. The class keeps its queue management but replaces all Android system DM Java API calls with IPC to the new DownloadService.

**Step 1: Rewrite the class**

Replace the entire file with:

```python
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
_DOWNLOAD_SERVICE_CLASS = (
    "com.consoleutilities.consoleutilities.ServiceDownloadservice"
)


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
```

**Step 2: Run lint**

Run: `cd /Users/gabe/Workspace/Games/console_utilities && make format && make lint`
Expected: PASS

**Step 3: Commit**

```bash
git add src/droid/download_manager.py
git commit -m "feat(droid): rewrite AndroidDownloadManager to use DownloadService"
```

---

### Task 6: Clean up unused receiver module

**Files:**
- Modify: `src/droid/receiver.py`

The `BroadcastReceiver` for `ACTION_DOWNLOAD_COMPLETE` is no longer used since we no longer use Android's system DownloadManager.

**Step 1: Verify receiver.py is not imported elsewhere**

Run: `grep -r "from droid.receiver\|from droid import receiver\|import receiver" src/`
Expected: No matches (the old import was in `download_manager.py` which was just rewritten)

**Step 2: Delete receiver.py**

```bash
rm src/droid/receiver.py
```

**Step 3: Run lint**

Run: `cd /Users/gabe/Workspace/Games/console_utilities && make format && make lint`
Expected: PASS

**Step 4: Commit**

```bash
git add -u src/droid/receiver.py
git commit -m "refactor(droid): remove unused BroadcastReceiver for system DownloadManager"
```

---

### Task 7: Verify the DOWNLOAD_WITHOUT_NOTIFICATION permission can be removed

**Files:**
- Modify: `buildozer.spec` (line 22)

**Step 1: Check if DOWNLOAD_WITHOUT_NOTIFICATION is used elsewhere**

Run: `grep -r "DOWNLOAD_WITHOUT_NOTIFICATION" .`
Expected: Only `buildozer.spec`

**Step 2: Remove the permission**

Remove `DOWNLOAD_WITHOUT_NOTIFICATION` from the `android.permissions` line in `buildozer.spec`. This permission was only needed for Android's system DownloadManager.

**Step 3: Commit**

```bash
git add buildozer.spec
git commit -m "chore(droid): remove DOWNLOAD_WITHOUT_NOTIFICATION permission"
```

---

### Task 8: Manual integration test

**Step 1: Build the APK**

Run: `make build-android`
Expected: APK builds successfully with both services registered

**Step 2: Test parallel download**

Install on device, navigate to a system with large ROMs (e.g., PS1, PSP), select a game, download it. Verify:
- Notification appears with progress bar
- Progress updates smoothly in the app UI
- Speed is displayed
- File appears in target roms folder after extraction

**Step 3: Test small file fallback**

Download a small ROM (<5MB, e.g., Game Boy). Verify it uses single-stream and completes normally.

**Step 4: Test cancellation**

Start a large download, cancel mid-way. Verify:
- `.partN` temp files are cleaned up
- Item shows as cancelled
- Next queued item starts

**Step 5: Test app backgrounding**

Start a download, switch to another app, come back. Verify:
- Download continued in background (wake lock)
- Notification showed progress while backgrounded
- UI picks up correct state on resume
