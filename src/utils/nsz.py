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


def decompress_nsz_file(
    nsz_file_path: str,
    output_dir: str,
    keys_path: str,
    progress_callback: Optional[Callable[[str, int], None]] = None
) -> bool:
    """
    Unified NSZ decompression method.

    Args:
        nsz_file_path: Path to the NSZ file to decompress
        output_dir: Directory to extract NSP file(s) to
        keys_path: Path to Nintendo Switch keys file
        progress_callback: Optional callback for progress updates (message, progress_percent)

    Returns:
        True if decompression was successful, False otherwise
    """
    filename = os.path.basename(nsz_file_path)

    log_error(f"NSZ Called for {filename}")
    log_error("NSZ Starting Checks:")

    def update_progress(message: str, progress: int):
        if progress_callback:
            progress_callback(message, progress)
        else:
            print(message)

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
            update_progress(f"Decompressing {filename} using NSZ library...", 30)

            # Check if NSZ file is valid before attempting decompression
            if not os.path.exists(nsz_file_path):
                raise FileNotFoundError(f"NSZ file not found: {nsz_file_path}")

            file_size = os.path.getsize(nsz_file_path)
            if file_size == 0:
                raise ValueError(f"NSZ file is empty: {nsz_file_path}")

            log_error(f"Attempting NSZ decompression of {filename} ({file_size} bytes)")
            local_nsz_decompress(
                Path(nsz_file_path),
                Path(output_dir),
                True,
                None,
                keys_path=keys_path
            )
            nsz_success = True
            update_progress("NSZ library decompression successful", 80)
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
        update_progress(f"Decompressing {filename}... Complete", 100)
        return True
    else:
        log_error(f"NSZ decompression failed for {filename}: All methods failed")
        update_progress(f"NSZ decompression failed for {filename}", 0)
        return False
