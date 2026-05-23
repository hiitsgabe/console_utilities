"""
NSZ decompression utilities for Console Utilities.
Handles decompression of NSZ files to NSP format.
"""

import os
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Optional, Union

from .logging import log_error

# Try to import NSZ module
try:
    nsz_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "nsz")
    if nsz_path not in sys.path:
        sys.path.insert(0, nsz_path)
    from nsz import decompress as _nsz_decompress

    NSZ_AVAILABLE = True
except (ImportError, AttributeError, FileNotFoundError, ModuleNotFoundError) as e:
    NSZ_AVAILABLE = False
    _nsz_decompress = None


# Typical NSZ compression ratio: output (.nsp) is ~1.7x the input (.nsz)
_NSZ_OUTPUT_RATIO = 1.7


# Progress callback can be either the legacy 2-arg form (text, percent) or the
# extended 5-arg form (text, percent, bytes_done, total_bytes, speed).
ProgressCallback = Union[
    Callable[[str, int], None],
    Callable[[str, int, int, int, float], None],
]


def is_nsz_available() -> bool:
    """Check if NSZ decompression is available."""
    return NSZ_AVAILABLE


def _invoke_progress(
    callback: Optional[ProgressCallback],
    text: str,
    percent: int,
    bytes_done: int = 0,
    total_bytes: int = 0,
    speed: float = 0.0,
):
    """Call progress callback, falling back to the 2-arg form if needed."""
    if callback is None:
        return
    try:
        callback(text, percent, bytes_done, total_bytes, speed)
    except TypeError:
        callback(text, percent)


def _expected_output_path(nsz_file_path: str, output_dir: str) -> str:
    """Predict the NSP path the NSZ library will write."""
    stem = Path(nsz_file_path).stem
    return os.path.join(output_dir, stem + ".nsp")


def _poll_output(
    output_path: str,
    estimated_total: int,
    callback: Optional[ProgressCallback],
    label: str,
    stop_event: threading.Event,
):
    """Background thread: watch the output .nsp file grow and report progress."""
    start_time = time.time()
    samples = []  # rolling [(t, bytes_written)]
    last_emit = 0.0

    while not stop_event.wait(0.5):
        try:
            size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
        except OSError:
            size = 0

        now = time.time()
        samples.append((now, size))
        # Keep ~10 seconds of samples for smoother speed
        cutoff = now - 10.0
        while len(samples) > 1 and samples[0][0] < cutoff:
            samples.pop(0)

        speed = 0.0
        if len(samples) >= 2:
            dt = samples[-1][0] - samples[0][0]
            db = samples[-1][1] - samples[0][1]
            if dt > 0 and db > 0:
                speed = db / dt

        # Adjust estimated_total upward if output already exceeds estimate
        total = max(estimated_total, size)
        # Map raw progress to 5..95% window so we leave room for finalize step
        if total > 0:
            raw = size / total
        else:
            raw = 0.0
        percent = 5 + int(min(0.95, raw) * 90)

        # Throttle callback emits to ~2 Hz
        if now - last_emit >= 0.5:
            _invoke_progress(callback, label, percent, size, total, speed)
            last_emit = now


def decompress_nsz_file(
    nsz_file_path: str,
    output_dir: str,
    keys_path: str,
    progress_callback: Optional[ProgressCallback] = None,
) -> bool:
    """
    Unified NSZ decompression method with real-time progress reporting.

    The progress callback receives (text, percent, bytes_done, total_bytes, speed).
    Legacy 2-arg callbacks (text, percent) are also supported.

    Args:
        nsz_file_path: Path to the NSZ file to decompress
        output_dir: Directory to extract NSP file(s) to
        keys_path: Path to Nintendo Switch keys file
        progress_callback: Optional progress callback

    Returns:
        True if decompression was successful, False otherwise
    """
    filename = os.path.basename(nsz_file_path)
    label = f"Decompressing {filename}"

    log_error(f"NSZ Called for {filename}")
    log_error(f"NSZ Key Path: {keys_path}")

    # Check if NSZ library is available
    local_nsz_decompress = _nsz_decompress
    if local_nsz_decompress is None:
        try:
            from nsz import decompress as local_nsz_decompress
        except (ImportError, AttributeError) as e:
            log_error(f"NSZ IMPORT ERROR: {str(e)}")
            local_nsz_decompress = None

    if not (keys_path and local_nsz_decompress):
        _invoke_progress(progress_callback, f"NSZ decompression unavailable", 0)
        return False

    if not os.path.exists(nsz_file_path):
        log_error(f"NSZ file not found: {nsz_file_path}")
        _invoke_progress(progress_callback, "NSZ file not found", 0)
        return False

    nsz_size = os.path.getsize(nsz_file_path)
    if nsz_size == 0:
        log_error(f"NSZ file is empty: {nsz_file_path}")
        _invoke_progress(progress_callback, "NSZ file is empty", 0)
        return False

    estimated_total = int(nsz_size * _NSZ_OUTPUT_RATIO)
    output_path = _expected_output_path(nsz_file_path, output_dir)

    _invoke_progress(progress_callback, label, 0, 0, estimated_total, 0.0)

    # Background polling thread tracks the output file's growth so the UI
    # gets real progress + speed/ETA instead of a single jump from 30% to 100%.
    stop_event = threading.Event()
    poll_thread = threading.Thread(
        target=_poll_output,
        args=(output_path, estimated_total, progress_callback, label, stop_event),
        daemon=True,
    )

    try:
        os.makedirs(output_dir, exist_ok=True)
        log_error(f"Attempting NSZ decompression of {filename} ({nsz_size} bytes)")
        poll_thread.start()

        local_nsz_decompress(
            Path(nsz_file_path), Path(output_dir), True, None, keys_path=keys_path
        )

        stop_event.set()
        poll_thread.join(timeout=2.0)

        # Emit a final 100% with the actual output size as the total
        final_size = (
            os.path.getsize(output_path) if os.path.exists(output_path) else 0
        )
        _invoke_progress(progress_callback, label, 100, final_size, final_size, 0.0)
        log_error("NSZ decompression successful using nsz library")
        return True

    except Exception as e:
        stop_event.set()
        poll_thread.join(timeout=2.0)
        log_error(f"NSZ library method failed for {filename}: {str(e)}")
        log_error(f"NSZ file path: {nsz_file_path}")
        log_error(f"Output directory: {output_dir}")
        log_error(f"Keys path: {keys_path}")
        if "read returned empty" in str(e):
            log_error("NSZ file appears to be corrupted or incomplete")
        _invoke_progress(progress_callback, f"NSZ decompression failed", 0)
        return False
