"""
NSZ decompression utilities for Console Utilities.
Handles decompression of NSZ files to NSP format.
"""

import os
import sys
from pathlib import Path
from typing import Callable, Optional

from .logging import log_nsz

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


# Characters forbidden in FAT/exFAT filenames. Handheld ROM SD cards are almost
# always exFAT, and creating a file whose name contains one of these fails with
# EPERM on the FUSE mount -- that is why a title like "Cities: Skylines" (colon)
# silently fails to extract while a legal-named title on the SAME folder works.
_EXFAT_ILLEGAL = set('<>:"/\\|?*')


def sanitize_for_fat(name: str) -> str:
    """Return ``name`` with FAT/exFAT-illegal characters made safe.

    Illegal and control chars become spaces; runs of whitespace collapse; a
    trailing dot/space (also illegal on FAT) is stripped. The file extension is
    preserved because '.' is legal. Never returns empty.
    """
    cleaned = "".join(
        " " if (c in _EXFAT_ILLEGAL or ord(c) < 0x20) else c for c in name
    )
    cleaned = " ".join(cleaned.split()).rstrip(". ")
    return cleaned or "output"


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

    log_nsz(f"NSZ start: file={filename} path={nsz_file_path}")
    log_nsz(f"NSZ keys_path={keys_path!r}")
    if os.path.exists(nsz_file_path):
        log_nsz(f"NSZ file_size={os.path.getsize(nsz_file_path)}")
    else:
        log_nsz("NSZ file_size=unknown (path does not exist)")

    def update_progress(message: str, progress: int):
        if progress_callback:
            progress_callback(message, progress)
        else:
            print(message)

    # Check if NSZ library is available
    local_nsz_decompress = _nsz_decompress
    log_nsz(f"NSZ exists? : {local_nsz_decompress is not None}")

    if local_nsz_decompress is None:
        try:
            from nsz import decompress as local_nsz_decompress

            log_nsz("IMPORTED NSZ AGAIN")
        except (ImportError, AttributeError) as e:
            log_nsz(f"NSZ IMPORT ERROR: {str(e)}")
            local_nsz_decompress = None

    nsz_success = False

    if not keys_path:
        log_nsz("NSZ skipped: keys_path not set")
    elif local_nsz_decompress is None:
        log_nsz("NSZ skipped: nsz library unavailable")
    else:
        try:
            update_progress(f"Decompressing {filename}...", 0)

            # Check if NSZ file is valid before attempting decompression
            if not os.path.exists(nsz_file_path):
                raise FileNotFoundError(f"NSZ file not found: {nsz_file_path}")

            file_size = os.path.getsize(nsz_file_path)
            if file_size == 0:
                raise ValueError(f"NSZ file is empty: {nsz_file_path}")

            log_nsz(f"Attempting NSZ decompression of {filename} ({file_size} bytes)")

            # Pre-flight capacity check: decompressed NSP roughly doubles the
            # NSZ size. Block before extraction when the target can't hold it
            # (FAT32 4 GB limit or insufficient free space) so we fail loudly
            # rather than silently truncating a multi-GiB extraction.
            est_output = file_size * 2
            ok, reason = check_output_capacity(output_dir, est_output)
            if not ok:
                log_nsz(f"Capacity check failed for {filename}: {reason}")
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

            # The nsz library derives the output .nsp name from the input .nsz
            # basename. If that name has FAT-illegal chars, writing to an exFAT
            # SD target fails with EPERM. Stage the source under a safe name in a
            # unique temp dir (on the same internal, char-tolerant fs) so the
            # library writes a legal .nsp straight to the SD -- no full copy. The
            # temp dir keeps colliding sanitized names (e.g. "A:B" and "A?B" both
            # -> "A B") from overwriting each other. The source is always moved
            # back to its original path so the caller's post-success cleanup and
            # the GAB-58 retry-by-path both find it.
            work_path = nsz_file_path
            staged_dir = None
            safe_name = sanitize_for_fat(filename)
            if safe_name != filename:
                import tempfile

                staged_dir = tempfile.mkdtemp(dir=os.path.dirname(nsz_file_path))
                work_path = os.path.join(staged_dir, safe_name)
                os.rename(nsz_file_path, work_path)
                log_nsz(f"NSZ sanitized name for FAT target: {filename!r} -> {safe_name!r}")

            try:
                local_nsz_decompress(
                    Path(work_path),
                    Path(output_dir),
                    True,
                    None,
                    keys_path=keys_path,
                    progress_callback=_on_progress,
                )
                nsz_success = True
            finally:
                # Restore the source to its original path on BOTH outcomes.
                if staged_dir:
                    try:
                        if os.path.exists(work_path):
                            os.replace(work_path, nsz_file_path)
                    except OSError as e:
                        log_nsz(f"NSZ source restore failed for {filename}: {e}")
                    finally:
                        try:
                            os.rmdir(staged_dir)
                        except OSError:
                            pass
            log_nsz("NSZ decompression successful using nsz library")

        except Exception as e:
            import traceback

            error_msg = f"NSZ library decompression failed: {e}"
            print(error_msg)
            log_nsz(
                f"NSZ library method failed for {filename}: {e}",
                traceback_str=traceback.format_exc(),
            )
            log_nsz(f"NSZ file path: {nsz_file_path}")
            log_nsz(f"Output directory: {output_dir}")
            log_nsz(f"Keys path: {keys_path}")

            # Check if it's a corrupted file issue
            if "read returned empty" in str(e):
                log_nsz("NSZ file appears to be corrupted or incomplete")

    if nsz_success:
        log_nsz(f"NSZ completion: success file={filename}")
        update_progress(f"Decompressing {filename}... Complete", 100)
        return True
    else:
        log_nsz(f"NSZ failure: file={filename} all methods failed")
        update_progress(f"NSZ decompression failed for {filename}", 0)
        return False
