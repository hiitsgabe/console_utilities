"""
Logging utilities for Console Utilities.
Provides error logging with timestamps and traceback support.
"""

import os
from datetime import datetime
from typing import Optional

from constants import TEMP_LOG_DIR

# Module-level log file path
_log_file: str = os.path.join(TEMP_LOG_DIR, "error.log")


def get_log_file() -> str:
    """Get the current log file path."""
    return _log_file


def update_log_file_path(work_dir: str) -> None:
    """
    Update LOG_FILE path to use the configured work directory.

    Creates a py_downloads subdirectory within the work directory.

    Args:
        work_dir: The work directory path
    """
    global _log_file
    py_downloads_dir = os.path.join(work_dir, "py_downloads")
    os.makedirs(py_downloads_dir, exist_ok=True)
    _log_file = os.path.join(py_downloads_dir, "error.log")


def log_error(
    error_msg: str,
    error_type: Optional[str] = None,
    traceback_str: Optional[str] = None,
) -> None:
    """
    Log an error message to the log file.

    Args:
        error_msg: The error message to log
        error_type: Optional error type/class name
        traceback_str: Optional traceback string
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{timestamp}] ERROR: {error_msg}\n"

    if error_type:
        log_message += f"Type: {error_type}\n"

    if traceback_str:
        log_message += f"Traceback:\n{traceback_str}\n"

    log_message += "-" * 80 + "\n"

    try:
        with open(_log_file, "a") as f:
            f.write(log_message)
    except Exception as e:
        # If logging fails, print to console as fallback
        print(f"Failed to write to log file: {e}")
        print(log_message)


def init_log_file() -> bool:
    """
    Initialize the log file with system information.

    Returns:
        True if successful, False otherwise
    """
    import sys

    try:
        log_dir = os.path.dirname(_log_file) if os.path.dirname(_log_file) else "."
        os.makedirs(log_dir, exist_ok=True)

        with open(_log_file, "w") as f:
            f.write(
                f"Error Log - Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            )
            f.write(f"Python version: {sys.version}\n")
            f.write(f"Platform: {sys.platform}\n")
            f.write("-" * 80 + "\n")

        print(f"Log file initialized: {_log_file}")
        return True

    except Exception as e:
        print(f"Failed to initialize log file: {e}")
        return False
