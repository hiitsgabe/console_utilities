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
_nsz_log_file: str = os.path.join(TEMP_LOG_DIR, "nsz.log")

# In-memory NSZ diagnostics buffer. The nsz.log file is often unreachable on
# Android (sandboxed app storage), so every log_nsz() entry is also captured
# here for the in-app log viewer. Capped so a long session can't grow unbounded.
NSZ_LOG_BUFFER_MAX: int = 1000
_nsz_log_buffer: "deque[str]" = deque(maxlen=NSZ_LOG_BUFFER_MAX)


def get_log_file() -> str:
    """Get the current log file path."""
    return _log_file


def get_nsz_log_file() -> str:
    """Get the current NSZ log file path."""
    return _nsz_log_file


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
    Log an NSZ diagnostic message to the dedicated NSZ log file and stdout.

    Mirrors ``log_error`` but targets ``_nsz_log_file`` so NSZ decompression
    diagnostics land in their own ``nsz.log`` (sibling of ``error.log``) and
    never pollute the general error log. On a primary-write OSError it routes
    the entry through the hardened ``_write_fallback`` path.

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

    # Capture to the in-memory buffer for the in-app viewer (display-friendly,
    # no separator rule). Survives even when the file write below fails.
    entry = log_message
    if traceback_str:
        entry += f"\nTraceback:\n{traceback_str}"
    _nsz_log_buffer.append(entry)

    # Build full file entry with traceback
    file_message = log_message + "\n"
    if traceback_str:
        file_message += f"Traceback:\n{traceback_str}\n"
    file_message += "-" * 80 + "\n"

    try:
        with open(_nsz_log_file, "a") as f:
            f.write(file_message)
    except OSError as e:
        print(f"Failed to write log to {_nsz_log_file}: {e}", file=sys.stderr, flush=True)
        _write_fallback(file_message)


def get_nsz_log_buffer() -> List[str]:
    """Return a copy of the in-memory NSZ log entries (oldest first)."""
    return list(_nsz_log_buffer)


def clear_nsz_log_buffer() -> None:
    """Drop all captured in-memory NSZ log entries."""
    _nsz_log_buffer.clear()


def read_nsz_log_lines() -> List[str]:
    """Return NSZ diagnostics as display lines for the in-app viewer.

    Prefers the in-memory buffer (always available, even on Android where the
    file path is unreachable). Falls back to reading ``nsz.log`` from disk when
    the buffer is empty. Returns an empty list when neither source has content.
    """
    if _nsz_log_buffer:
        lines: List[str] = []
        for entry in _nsz_log_buffer:
            lines.extend(entry.splitlines())
        return lines

    try:
        with open(_nsz_log_file, "r") as f:
            return f.read().splitlines()
    except OSError:
        return []


def save_nsz_log_to_error_log() -> bool:
    """Append the current NSZ diagnostics into the main ``error.log``.

    The error log is the one location users can reliably retrieve, so this lets
    them force the NSZ diagnostics there for sharing. Returns True when content
    was written, False when there was nothing to save or the write failed.
    """
    lines = read_nsz_log_lines()
    if not lines:
        return False

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    block = (
        f"\n===== NSZ LOG (saved {timestamp}) =====\n"
        + "\n".join(lines)
        + "\n"
        + "=" * 80
        + "\n"
    )
    try:
        with open(_log_file, "a") as f:
            f.write(block)
        print(f"NSZ log saved to {_log_file}", flush=True)
        return True
    except OSError as e:
        print(
            f"Failed to save NSZ log to {_log_file}: {e}",
            file=sys.stderr,
            flush=True,
        )
        _write_fallback(block)
        return False


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
