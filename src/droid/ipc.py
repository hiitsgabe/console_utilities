"""
Shared file IPC helpers for Android download/extraction communication.

Pure Python module — no Android or pyjnius dependencies.
Used by both the main app (reader) and the extraction service (writer).
"""

import json
import os
import time


_STATUS_FILENAME = "extraction_status.json"
_CANCEL_FILENAME = "extraction_cancel.json"
_DOWNLOAD_TASK_FILENAME = "download_task.json"

# Exported for service.py to skip during work_dir cleanup
IPC_FILENAMES = frozenset(
    {
        _STATUS_FILENAME,
        _CANCEL_FILENAME,
        _STATUS_FILENAME + ".tmp",
        _DOWNLOAD_TASK_FILENAME,
        _DOWNLOAD_TASK_FILENAME + ".tmp",
    }
)


def write_status(work_dir, item_id, status_dict):
    """
    Write extraction progress for a specific item.

    Called by the extraction service to report progress.

    Args:
        work_dir: Working directory for IPC files
        item_id: Unique identifier for the download/extraction item
        status_dict: Dict with keys like 'status', 'progress', 'error'
    """
    path = os.path.join(work_dir, _STATUS_FILENAME)
    # Read existing statuses
    all_statuses = _read_json(path) or {}
    all_statuses[str(item_id)] = status_dict
    all_statuses[str(item_id)]["updated_at"] = time.time()
    _write_json(path, all_statuses)


def read_status(work_dir):
    """
    Read all extraction statuses.

    Called by the main app to poll extraction progress.

    Returns:
        Dict mapping item_id to status dicts, or empty dict.
    """
    path = os.path.join(work_dir, _STATUS_FILENAME)
    return _read_json(path) or {}


def clear_status(work_dir, item_id):
    """
    Clear status for a specific item after the main app has processed it.

    Args:
        work_dir: Working directory for IPC files
        item_id: Item to clear
    """
    path = os.path.join(work_dir, _STATUS_FILENAME)
    all_statuses = _read_json(path) or {}
    all_statuses.pop(str(item_id), None)
    if all_statuses:
        _write_json(path, all_statuses)
    elif os.path.exists(path):
        os.remove(path)


def write_cancel(work_dir, cancel_type):
    """
    Write a cancel signal for the extraction service.

    Args:
        work_dir: Working directory for IPC files
        cancel_type: "current" to cancel current extraction, "all" to cancel all
    """
    path = os.path.join(work_dir, _CANCEL_FILENAME)
    _write_json(path, {"type": cancel_type, "timestamp": time.time()})


def read_cancel(work_dir):
    """
    Read cancel signal. Called by the extraction service between steps.

    Returns:
        Cancel dict with 'type' key, or None if no cancel pending.
    """
    path = os.path.join(work_dir, _CANCEL_FILENAME)
    return _read_json(path)


def clear_cancel(work_dir):
    """
    Clear cancel signal after the service has processed it.
    """
    path = os.path.join(work_dir, _CANCEL_FILENAME)
    if os.path.exists(path):
        os.remove(path)


def write_download_task(work_dir, task_dict):
    """
    Write a download task for the download service to pick up.

    Args:
        work_dir: Working directory for IPC files
        task_dict: Dict with url, filename, auth_headers, cookies, etc.
    """
    path = os.path.join(work_dir, _DOWNLOAD_TASK_FILENAME)
    _write_json(path, task_dict)


def read_download_task(work_dir):
    """
    Read the current download task. Called by the download service.

    Returns:
        Task dict or None if no task pending.
    """
    path = os.path.join(work_dir, _DOWNLOAD_TASK_FILENAME)
    return _read_json(path)


def clear_download_task(work_dir):
    """
    Clear the download task after the service has picked it up.
    """
    path = os.path.join(work_dir, _DOWNLOAD_TASK_FILENAME)
    if os.path.exists(path):
        os.remove(path)


def _read_json(path):
    """Read a JSON file, returning None on any error."""
    try:
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError, OSError):
        pass
    return None


def _write_json(path, data):
    """Atomically write a JSON file (write to temp then rename)."""
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "w") as f:
            json.dump(data, f)
        os.replace(tmp_path, path)
    except (IOError, OSError):
        # Best-effort cleanup
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
