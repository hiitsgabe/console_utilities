"""
Logging utilities for Console Utilities.
Provides logging with timestamps, file output, and stdout mirroring.
"""

import os
import sys
from datetime import datetime
from typing import Optional

from constants import TEMP_LOG_DIR

# Module-level log file path
_log_file: str = os.path.join(TEMP_LOG_DIR, "error.log")


def get_log_file() -> str:
    """Get the current log file path."""
    return _log_file


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
    except Exception:
        pass


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
        return False
