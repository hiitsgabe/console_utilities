"""
Parallel ZIP extraction helper.

Spawns a small pool of worker threads, each owning its own ``ZipFile``
handle, so the underlying zlib decompressors (which release the GIL) can
run concurrently on multi-core devices. Falls back to single-threaded
extraction when there is only one member, only one worker, or the
archive is too small to benefit.
"""

import os
import queue
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional
from zipfile import ZipFile, BadZipFile


# Archives smaller than this run serially — the thread-pool setup cost
# outweighs the parallel-decompress win on tiny inputs.
_PARALLEL_MIN_BYTES = 8 * 1024 * 1024


def parallel_extract_zip(
    zip_path: str,
    dest_dir: str,
    on_progress: Optional[Callable[[int, int], None]] = None,
    should_cancel: Optional[Callable[[], bool]] = None,
    max_workers: int = 4,
) -> bool:
    """Extract a ZIP file using a pool of ``ZipFile`` handles in parallel.

    Args:
        zip_path: Path to the ZIP file.
        dest_dir: Output directory (created if missing).
        on_progress: Optional ``(bytes_written, bytes_total)`` callback.
            Called from worker threads as each member finishes.
        should_cancel: Optional ``() -> bool`` polled per member.
            When it returns True the extraction aborts.
        max_workers: Maximum worker threads. Capped to the number of
            members so we don't spin idle threads.

    Returns:
        True on success, False if cancelled or on unrecoverable error.
    """
    os.makedirs(dest_dir, exist_ok=True)

    try:
        with ZipFile(zip_path, "r") as zf:
            members = zf.infolist()
    except BadZipFile:
        return False

    total_bytes = sum(m.file_size for m in members) or 1

    workers = max(1, min(max_workers, len(members)))
    if total_bytes < _PARALLEL_MIN_BYTES or workers == 1:
        return _serial_extract(zip_path, dest_dir, members, total_bytes, on_progress, should_cancel)

    handle_pool: "queue.Queue[ZipFile]" = queue.Queue()
    handles = []
    try:
        for _ in range(workers):
            zh = ZipFile(zip_path, "r")
            handles.append(zh)
            handle_pool.put(zh)
    except Exception:
        for h in handles:
            try:
                h.close()
            except Exception:
                pass
        return False

    written_lock = threading.Lock()
    written = [0]
    cancel_event = threading.Event()
    error_event = threading.Event()

    def worker(member):
        if cancel_event.is_set() or error_event.is_set():
            return
        if should_cancel and should_cancel():
            cancel_event.set()
            return
        zh = handle_pool.get()
        try:
            zh.extract(member, dest_dir)
            with written_lock:
                written[0] += member.file_size
                if on_progress:
                    on_progress(written[0], total_bytes)
        except Exception:
            error_event.set()
        finally:
            handle_pool.put(zh)

    try:
        # Largest first keeps the workers saturated past the tail.
        ordered = sorted(members, key=lambda m: m.file_size, reverse=True)
        executor = ThreadPoolExecutor(max_workers=workers)
        try:
            futures = [executor.submit(worker, m) for m in ordered]
            for _ in as_completed(futures):
                if cancel_event.is_set() or error_event.is_set():
                    break
        finally:
            executor.shutdown(wait=True, cancel_futures=True)
    finally:
        for h in handles:
            try:
                h.close()
            except Exception:
                pass

    if cancel_event.is_set() or error_event.is_set():
        return False
    return True


def _serial_extract(
    zip_path: str,
    dest_dir: str,
    members,
    total_bytes: int,
    on_progress,
    should_cancel,
) -> bool:
    """Single-threaded fallback when parallelism isn't worth the overhead."""
    with ZipFile(zip_path, "r") as zf:
        written = 0
        for m in members:
            if should_cancel and should_cancel():
                return False
            zf.extract(m, dest_dir)
            written += m.file_size
            if on_progress:
                on_progress(written, total_bytes)
    return True
