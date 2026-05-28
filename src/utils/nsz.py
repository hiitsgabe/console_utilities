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


def _detect_fs_type(path: str) -> Optional[str]:
    """Detect the filesystem type backing ``path`` by parsing /proc/mounts.

    Returns the lowercase fstype of the longest mountpoint that is a prefix of
    the absolute path, or None on any failure (file unreadable / non-Linux).
    """
    try:
        abspath = os.path.abspath(path)
        best_mount = ""
        best_fstype = None
        with open("/proc/mounts", "r") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 3:
                    continue
                mountpoint, fstype = parts[1], parts[2]
                if abspath == mountpoint or abspath.startswith(
                    mountpoint.rstrip("/") + "/"
                ) or mountpoint == "/":
                    if len(mountpoint) >= len(best_mount):
                        best_mount = mountpoint
                        best_fstype = fstype
        return best_fstype.lower() if best_fstype is not None else None
    except Exception:
        return None


def check_output_capacity(output_dir: str, required_bytes: int):
    """Pre-flight check that ``output_dir`` can hold ``required_bytes``.

    Returns (ok, reason). ``reason`` is None when ok. Fails open (returns True)
    when free space cannot be determined.
    """
    try:
        st = os.statvfs(output_dir)
        free = st.f_frsize * st.f_bavail
    except OSError:
        return (True, None)  # fail-open: can't tell, don't block

    fs = _detect_fs_type(output_dir)
    if fs in {"vfat", "msdos", "fat", "fat32"} and required_bytes >= 4 * 1024 ** 3 - 1:
        return (
            False,
            "Target drive is FAT32, which cannot store a single file of 4 GB "
            "or larger. Reformat the drive as exFAT and try again.",
        )

    if required_bytes > free:
        need_gb = required_bytes / (1024 ** 3)
        have_gb = free / (1024 ** 3)
        return (
            False,
            f"Not enough free space: need ~{need_gb:.1f} GB but only "
            f"{have_gb:.1f} GB available.",
        )

    return (True, None)


def decompress_nsz_file(
    nsz_file_path: str,
    output_dir: str,
    keys_path: str,
    progress_callback: Optional[Callable[[str, int], None]] = None,
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
            update_progress(f"Decompressing {filename}...", 0)

            # Check if NSZ file is valid before attempting decompression
            if not os.path.exists(nsz_file_path):
                raise FileNotFoundError(f"NSZ file not found: {nsz_file_path}")

            file_size = os.path.getsize(nsz_file_path)
            if file_size == 0:
                raise ValueError(f"NSZ file is empty: {nsz_file_path}")

            log_error(f"Attempting NSZ decompression of {filename} ({file_size} bytes)")

            # Pre-flight capacity check: decompressed NSP roughly doubles the
            # NSZ size. Block before extraction when the target can't hold it
            # (FAT32 4 GB limit or insufficient free space) so we fail loudly
            # rather than silently truncating a multi-GiB extraction.
            est_output = file_size * 2
            ok, reason = check_output_capacity(output_dir, est_output)
            if not ok:
                log_error(f"Capacity check failed for {filename}: {reason}")
                update_progress(reason, 0)
                return False

            # Translate library's (done_bytes, total_bytes) into our (message, percent).
            # Throttle by integer-percent change so we don't flood IPC writes.
            last_pct = [-1]

            def _on_progress(done, total):
                if total <= 0:
                    return
                pct = int(done * 100 / total)
                if pct > 99:
                    pct = 99  # reserve 100 for completion path below
                if pct == last_pct[0]:
                    return
                last_pct[0] = pct
                update_progress(f"Decompressing {filename}... {pct}%", pct)

            local_nsz_decompress(
                Path(nsz_file_path),
                Path(output_dir),
                True,
                None,
                keys_path=keys_path,
                progress_callback=_on_progress,
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
        update_progress(f"Decompressing {filename}... Complete", 100)
        return True
    else:
        log_error(f"NSZ decompression failed for {filename}: All methods failed")
        update_progress(f"NSZ decompression failed for {filename}", 0)
        return False
