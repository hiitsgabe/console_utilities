"""
NSZ decompression utilities for Console Utilities.
Handles decompression of NSZ files to NSP format.
"""

import os
import sys
from pathlib import Path
from typing import Callable, Optional

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


def is_nsz_available() -> bool:
    """Check if NSZ decompression is available."""
    return NSZ_AVAILABLE


class _ProgressReport:
    """List-like proxy for nsz's statusReport that fires a callback on updates.

    The nsz library writes ``statusReport[id] = [processed, verified, total, step]``
    after every decompressed chunk. We intercept those writes and translate
    them into ``progress_callback(step, processed, total)`` calls so the UI can
    show real-time progress, speed, and ETA instead of a hard-coded 30 → 80
    waypoint.
    """

    def __init__(self, callback, slot_id=0):
        self._slots = {}
        self._callback = callback
        self._slot_id = slot_id

    def __setitem__(self, key, value):
        self._slots[key] = value
        if key != self._slot_id or self._callback is None:
            return
        try:
            processed, _verified, total, step = value
        except (ValueError, TypeError):
            return
        try:
            self._callback(str(step), int(processed), int(total))
        except Exception:
            pass

    def __getitem__(self, key):
        return self._slots[key]


def decompress_nsz_file(
    nsz_file_path: str,
    output_dir: str,
    keys_path: str,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
) -> bool:
    """
    Unified NSZ decompression method.

    Args:
        nsz_file_path: Path to the NSZ file to decompress
        output_dir: Directory to extract NSP file(s) to
        keys_path: Path to Nintendo Switch keys file
        progress_callback: Optional callback ``(step, bytes_processed, bytes_total)``
            invoked continuously during decompression.

    Returns:
        True if decompression was successful, False otherwise
    """
    filename = os.path.basename(nsz_file_path)

    log_error(f"NSZ Called for {filename}")
    log_error(f"NSZ Key Path: {keys_path}")

    # Check if NSZ library is available
    local_nsz_decompress = _nsz_decompress
    log_error(f"NSZ exists? : {local_nsz_decompress is not None}")

    if local_nsz_decompress is None:
        try:
            from nsz import decompress as local_nsz_decompress

            log_error("IMPORTED NSZ AGAIN")
        except (ImportError, AttributeError) as e:
            log_error(f"NSZ IMPORT ERROR: {str(e)}")
            local_nsz_decompress = None

    nsz_success = False

    if keys_path and local_nsz_decompress:
        try:
            # Check if NSZ file is valid before attempting decompression
            if not os.path.exists(nsz_file_path):
                raise FileNotFoundError(f"NSZ file not found: {nsz_file_path}")

            file_size = os.path.getsize(nsz_file_path)
            if file_size == 0:
                raise ValueError(f"NSZ file is empty: {nsz_file_path}")

            if progress_callback:
                progress_callback("Decompressing", 0, file_size)

            log_error(f"Attempting NSZ decompression of {filename} ({file_size} bytes)")
            report = _ProgressReport(progress_callback)
            local_nsz_decompress(
                Path(nsz_file_path),
                Path(output_dir),
                True,
                (report, 0),
                keys_path=keys_path,
            )
            nsz_success = True
            log_error("NSZ decompression successful using nsz library")

        except Exception as e:
            error_msg = f"NSZ library decompression failed: {e}"
            print(error_msg)
            log_error(f"NSZ library method failed for {filename}: {str(e)}")
            log_error(f"NSZ file path: {nsz_file_path}")
            log_error(f"Output directory: {output_dir}")
            log_error(f"Keys path: {keys_path}")

            # Check if it's a corrupted file issue
            if "read returned empty" in str(e):
                log_error("NSZ file appears to be corrupted or incomplete")

    if nsz_success:
        if progress_callback:
            try:
                final_size = os.path.getsize(nsz_file_path)
            except OSError:
                final_size = 1
            progress_callback("Decompressing", final_size, final_size)
        return True
    else:
        log_error(f"NSZ decompression failed for {filename}: All methods failed")
        if progress_callback:
            progress_callback("Failed", 0, 1)
        return False
