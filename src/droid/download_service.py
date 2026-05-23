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
import traceback  # noqa: F401
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional  # noqa: F401
from urllib.parse import urljoin  # noqa: F401

# Add src to path (p4a service may not have it)
_service_dir = os.path.dirname(os.path.abspath(__file__))
_src_dir = os.path.dirname(_service_dir)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from droid.ipc import (
    write_status,
    read_cancel,
    clear_cancel,
    clear_download_task,
)
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
PARALLEL_MIN_SIZE = 50 * 1024 * 1024  # 50 MB
PARALLEL_WORKERS = 4
# iter_content chunk size (2 MB — reduces Python/GIL overhead vs 256 KB)
STREAM_CHUNK_SIZE = 2 * 1024 * 1024


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

    # Triage log: confirm what reached the service from the main app.
    try:
        from utils.logging import log_error as _log

        _log(
            f"DownloadService start item={item_id} url={url} "
            f"cookies={sorted(cookies.keys())} "
            f"cookie_lens={ {k: len(v) for k, v in cookies.items()} } "
            f"auth_headers={sorted(auth_headers.keys())}"
        )
    except Exception:
        pass

    # Build request headers.
    has_auth = bool(auth_headers) or bool(cookies)
    if has_auth and "archive.org" not in url:
        request_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "*/*",
            "Accept-Encoding": "identity",
            "Accept-Language": "en-US,en;q=0.9",
        }
    else:
        request_headers = _build_download_headers(url)
    request_headers.update(auth_headers)

    try:
        resolved_url = url
        response = None

        if has_auth:
            from utils.logging import log_error as _log

            current_url = url
            for hop in range(5):
                resp = requests.get(
                    current_url,
                    stream=True,
                    timeout=(15, 30),
                    headers=request_headers,
                    cookies=cookies,
                    allow_redirects=False,
                )
                # Triage log per hop
                _log(
                    f"DownloadService redirect[{hop}] item={item_id} "
                    f"host={current_url.split('/')[2][:60]} "
                    f"status={resp.status_code} "
                    f"location={resp.headers.get('Location', '-')[:120]}"
                )
                if resp.status_code in (301, 302, 303, 307, 308):
                    current_url = resp.headers.get("Location", current_url)
                    resp.close()
                    continue
                resp.raise_for_status()
                response = resp
                resolved_url = current_url
                break
            else:
                raise requests.exceptions.TooManyRedirects("Too many redirects")
        else:
            response = requests.get(
                url,
                stream=True,
                timeout=(15, 30),
                headers=request_headers,
                cookies=cookies,
                allow_redirects=True,
            )
            response.raise_for_status()
            resolved_url = response.url

        total_size = int(response.headers.get("content-length", 0))
        accept_ranges = response.headers.get("accept-ranges", "").lower()
        response.close()

        write_status(
            work_dir,
            item_id,
            {
                "status": "downloading",
                "progress": 0.0,
                "downloaded": 0,
                "total_size": total_size,
                "speed": 0.0,
            },
        )

        update_download_notification(service, f"Downloading: {filename}", 0, 100)

        # Choose download strategy
        if accept_ranges == "bytes" and total_size > PARALLEL_MIN_SIZE:
            file_path = _download_parallel(
                service,
                item_id,
                resolved_url,
                filename,
                total_size,
                work_dir,
                request_headers,
                cookies,
            )
        else:
            file_path = _download_single(
                service,
                item_id,
                resolved_url,
                filename,
                total_size,
                work_dir,
                request_headers,
                cookies,
            )

        if file_path is None:
            # Cancelled or failed — status already written
            return

        # Download complete — trigger extraction service
        update_download_notification(service, f"Downloaded: {filename}", 100, 100)
        _start_extraction_service(service, task, file_path)

    except Exception as e:
        import traceback as _tb

        from utils.logging import log_error as _log

        error_msg = str(e)[:100]
        # Capture diagnostic details for triage. Lands in IPC status so the UI
        # surfaces it AND in the standard error.log via log_error.
        diag = {
            "exc_type": type(e).__name__,
            "url_orig": url,
            "has_cookies": bool(cookies),
            "cookie_names": sorted(cookies.keys()) if cookies else [],
            "cookie_value_lens": (
                {k: len(v) for k, v in cookies.items()} if cookies else {}
            ),
            "has_auth_headers": bool(auth_headers),
            "header_keys": sorted(request_headers.keys()),
        }
        if hasattr(e, "response") and e.response is not None:
            diag["http_status"] = e.response.status_code
            diag["resp_url"] = getattr(e.response, "url", "?")
            diag["resp_headers"] = dict(e.response.headers)
            try:
                diag["resp_body_snip"] = e.response.text[:400]
            except Exception:
                diag["resp_body_snip"] = "<unreadable>"
            status = e.response.status_code
            if status in (401, 403) and "archive.org" in url:
                error_msg = "ia_auth_required"
            elif status in (401, 403):
                error_msg = (
                    f"HTTP {status} at {getattr(e.response, 'url', url)[:80]}"
                    f"  cookies={list(cookies.keys()) if cookies else 'none'}"
                )

        # Persist to error.log so we can retrieve it for triage.
        _log(
            f"DownloadService failure for item={item_id} url={url}\n"
            f"  diag={diag}",
            type(e).__name__,
            _tb.format_exc(),
        )

        write_status(
            work_dir,
            item_id,
            {
                "status": "failed",
                "progress": 0.0,
                "error": error_msg,
                "diag": diag,
            },
        )


def _download_single(
    service,
    item_id,
    url,
    filename,
    total_size,
    work_dir,
    headers,
    cookies,
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
        for chunk in resp.iter_content(chunk_size=STREAM_CHUNK_SIZE):
            # Check cancel
            if _check_cancel(work_dir, item_id):
                f.close()
                resp.close()
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
                    write_status(
                        work_dir,
                        item_id,
                        {
                            "status": "downloading",
                            "progress": progress,
                            "downloaded": downloaded,
                            "total_size": total_size,
                            "speed": avg_speed,
                        },
                    )
                    pct = int(progress * 100)
                    update_download_notification(
                        service, f"Downloading: {filename}", pct, 100
                    )

    return file_path


def _download_parallel(
    service,
    item_id,
    url,
    filename,
    total_size,
    work_dir,
    headers,
    cookies,
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

    # Thread safety: each worker writes only to its own index, and
    # CPython's GIL ensures sum() reads are atomic at the element level.
    progress_array = [0] * num_workers
    chunk_paths = [
        os.path.join(work_dir, f".{filename}.part{i}") for i in range(num_workers)
    ]
    chunk_failed = threading.Event()

    def worker(chunk_index):
        return _download_chunk(
            url,
            headers,
            cookies,
            chunks[chunk_index][0],
            chunks[chunk_index][1],
            chunk_paths[chunk_index],
            chunk_index,
            progress_array,
            chunk_failed,
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
                write_status(
                    work_dir,
                    item_id,
                    {
                        "status": "downloading",
                        "progress": progress,
                        "downloaded": downloaded,
                        "total_size": total_size,
                        "speed": avg_speed,
                    },
                )
                pct = int(progress * 100)
                update_download_notification(
                    service, f"Downloading: {filename}", pct, 100
                )

        # Check results
        for f in futures:
            if not f.result():
                write_status(
                    work_dir,
                    item_id,
                    {
                        "status": "failed",
                        "progress": 0.0,
                        "error": "Chunk download failed",
                    },
                )
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
        write_status(
            work_dir,
            item_id,
            {
                "status": "failed",
                "progress": 0.0,
                "error": f"Stitch failed: {str(e)[:50]}",
            },
        )
        return None

    return file_path


def _download_chunk(
    url,
    headers,
    cookies,
    start,
    end,
    chunk_path,
    chunk_index,
    progress_array,
    failed_event,
):
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
            for chunk in resp.iter_content(chunk_size=STREAM_CHUNK_SIZE):
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
            write_status(
                work_dir,
                item_id,
                {
                    "status": "cancelled",
                    "progress": 0.0,
                },
            )
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
        write_status(
            task["work_dir"],
            task["item_id"],
            {
                "status": "completed",
                "progress": 1.0,
            },
        )


def _build_download_headers(url):
    """Build browser-like headers for download servers."""
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
        ua = (
            f"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:{ff}.0)"
            f" Gecko/20100101 Firefox/{ff}.0"
        )
    else:
        sv = random.randint(0, 5)
        ua = (
            f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
            f" AppleWebKit/605.1.15"
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
        "Accept-Encoding": "identity",
        "Connection": "keep-alive",
        "Pragma": "no-cache",
        "Cache-Control": "no-cache",
        "Referer": referer,
        "sec-ch-ua": (
            f'"Not)A;Brand";v="8", "Chromium";v="{chrome_ver}",'
            f' "Google Chrome";v="{chrome_ver}"'
        ),
        "sec-ch-ua-mobile": "?0" if random.random() > 0.5 else "?1",
        "sec-ch-ua-platform": random.choice(platforms),
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": ("same-origin" if random.randint(0, 9) < 8 else "none"),
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
    }
    return headers


# p4a service entry point
if __name__ == "__main__":
    run_service()
