"""
Logging utilities for Console Utilities.
Provides logging with timestamps, file output, and stdout mirroring.
"""

import os
import sys
import tempfile
from collections import deque
from datetime import datetime
from typing import List, Optional

from constants import TEMP_LOG_DIR

# Module-level log file path
_log_file: str = os.path.join(TEMP_LOG_DIR, "error.log")

# NSZ diagnostics are written into the main error.log, tagged so they are easy
# to spot among other entries. A separate nsz.log proved unreliable/invisible
# on Android, and error.log is the file that reliably persists and is
# retrievable there.
NSZ_LOG_TAG: str = "[NSZ]"

# Number of trailing error.log lines the in-app viewer shows.
NSZ_VIEW_MAX_LINES: int = 500

# In-memory NSZ diagnostics buffer, used as a fallback source for the in-app
# viewer when error.log cannot be read. Capped so a long session stays bounded.
NSZ_LOG_BUFFER_MAX: int = 1000
_nsz_log_buffer: "deque[str]" = deque(maxlen=NSZ_LOG_BUFFER_MAX)


def get_log_file() -> str:
    """Get the current log file path."""
    return _log_file


def _write_fallback(text: str) -> None:
    """Best-effort write of a log entry to a fallback location.

    Tries the system temp dir first, then the current directory. Never raises;
    surfaces failures to stderr and stops after the first success.
    """
    candidates = [
        os.path.join(tempfile.gettempdir(), "console_utilities_error.log"),
        os.path.join(".", "error.log"),
    ]
    for path in candidates:
        try:
            with open(path, "a") as f:
                f.write(text)
            return
        except OSError as e:
            print(f"Failed to write fallback log to {path}: {e}", file=sys.stderr, flush=True)


def log_error(
    error_msg: str,
    error_type: Optional[str] = None,
    traceback_str: Optional[str] = None,
) -> None:
    """
    Log a message to the log file and stdout.

    Writes to both the log file and stdout so that the web companion's
    log capture can pick it up in real time.

    Args:
        error_msg: The message to log
        error_type: Optional error type/class name
        traceback_str: Optional traceback string
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{timestamp}] {error_msg}"

    if error_type:
        log_message += f" | {error_type}"

    # Always print to stdout (captured by web companion's _LogCapture)
    print(log_message, flush=True)

    # Build full file entry with traceback
    file_message = log_message + "\n"
    if traceback_str:
        file_message += f"Traceback:\n{traceback_str}\n"
    file_message += "-" * 80 + "\n"

    try:
        with open(_log_file, "a") as f:
            f.write(file_message)
    except OSError as e:
        print(f"Failed to write log to {_log_file}: {e}", file=sys.stderr, flush=True)
        _write_fallback(file_message)


def log_nsz(
    error_msg: str,
    error_type: Optional[str] = None,
    traceback_str: Optional[str] = None,
) -> None:
    """
    Log an NSZ diagnostic message into the main ``error.log`` and stdout.

    NSZ diagnostics go straight into ``error.log`` (tagged ``[NSZ]``) rather than
    a separate file: error.log is created at startup and reliably persists / is
    retrievable on Android, so entries survive even when a large-file extraction
    crashes or the app is restarted mid-decompression. Each entry is also kept in
    a small in-memory buffer as a fallback source for the in-app viewer when the
    file cannot be read.

    Args:
        error_msg: The message to log
        error_type: Optional error type/class name
        traceback_str: Optional traceback string
    """
    tagged = f"{NSZ_LOG_TAG} {error_msg}"

    # Capture to the in-memory buffer (display-friendly, no separator rule).
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] {tagged}"
    if error_type:
        entry += f" | {error_type}"
    if traceback_str:
        entry += f"\nTraceback:\n{traceback_str}"
    _nsz_log_buffer.append(entry)

    # Persist through the shared error.log writer (stdout mirror + hardened
    # fallback on OSError are handled there).
    log_error(tagged, error_type, traceback_str)


def get_nsz_log_buffer() -> List[str]:
    """Return a copy of the in-memory NSZ log entries (oldest first)."""
    return list(_nsz_log_buffer)


def clear_nsz_log_buffer() -> None:
    """Drop all captured in-memory NSZ log entries."""
    _nsz_log_buffer.clear()


def read_nsz_log_lines() -> List[str]:
    """Return recent log lines for the in-app viewer.

    Reads the tail of ``error.log`` (the source of truth, which persists across
    restarts/crashes) so the user sees NSZ diagnostics *and* the surrounding
    download/processing errors for a failed item. Falls back to the in-memory
    buffer only when the file cannot be read. Returns ``[]`` when neither source
    has content.
    """
    try:
        with open(_log_file, "r") as f:
            lines = f.read().splitlines()
        if lines:
            return lines[-NSZ_VIEW_MAX_LINES:]
    except OSError:
        pass

    if _nsz_log_buffer:
        out: List[str] = []
        for entry in _nsz_log_buffer:
            out.extend(entry.splitlines())
        return out

    return []


def init_log_file() -> bool:
    """
    Initialize the log file with system information.

    Returns:
        True if successful, False otherwise
    """
    try:
        log_dir = os.path.dirname(_log_file) if os.path.dirname(_log_file) else "."
        os.makedirs(log_dir, exist_ok=True)

        with open(_log_file, "w") as f:
            f.write(
                f"Log - Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            )
            f.write(f"Python version: {sys.version}\n")
            f.write(f"Platform: {sys.platform}\n")
            f.write(f"Log file: {_log_file}\n")
            f.write("-" * 80 + "\n")

        print(f"Log file initialized: {_log_file}")
        return True

    except Exception as e:
        print(f"Failed to initialize log file: {e}")
        print(f"Failed to initialize log file: {e}", file=sys.stderr, flush=True)
        return False
