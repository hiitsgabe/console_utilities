"""
ExtractionService — p4a foreground service for ZIP/NSZ extraction.

This runs as a separate Python process on Android, launched via
startForegroundService(). It handles post-download file processing
(extraction, decompression, file moves) while the main app may be
backgrounded.

Communication with the main app is via shared JSON files (see ipc.py).

p4a service argument convention: the task JSON is passed via the
PYTHON_SERVICE_ARGUMENT environment variable (set by p4a's generated
Java service class).

Since this only runs on Android, top-level pyjnius imports are acceptable.
"""

import json
import os
import shutil
import sys
import traceback
from zipfile import ZipFile

# Add src to path (p4a service may not have it)
_service_dir = os.path.dirname(os.path.abspath(__file__))
_src_dir = os.path.dirname(_service_dir)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from droid.ipc import write_status, read_cancel, clear_cancel, IPC_FILENAMES
from droid.notification import (
    create_notification_channel,
    build_extraction_notification,
    update_notification,
    NOTIFICATION_ID,
)

from jnius import autoclass


def _move_to_roms(src_path: str, dst_path: str) -> str:
    """Move a file into the ROMs folder. Returns "" on success, error string otherwise.

    PermissionError on Android (errno 1, EPERM) means the user hasn't granted
    MANAGE_EXTERNAL_STORAGE. Surface a clear, actionable message instead of
    letting the exception bubble up as a cryptic "[Errno 1] Operation not
    permitted".
    """
    try:
        if os.path.exists(dst_path):
            if os.path.isdir(dst_path):
                shutil.rmtree(dst_path)
            else:
                os.remove(dst_path)
        shutil.move(src_path, dst_path)
        return ""
    except PermissionError:
        return (
            "Permission denied writing to ROMs folder. "
            "Grant All-files access in Settings > Storage Permission."
        )
    except OSError as e:
        return f"Move failed: {e}"

PythonService = autoclass("org.kivy.android.PythonService")
PowerManager = autoclass("android.os.PowerManager")
Context = autoclass("android.content.Context")


def run_service():
    """
    Main entry point for the extraction foreground service.

    Reads task info from PYTHON_SERVICE_ARGUMENT env var, performs extraction,
    and communicates progress via IPC.
    """
    service = PythonService.mService

    # Acquire wake lock to keep CPU active during extraction
    power_manager = service.getSystemService(Context.POWER_SERVICE)
    wake_lock = power_manager.newWakeLock(
        PowerManager.PARTIAL_WAKE_LOCK, "consoleutilities:extraction"
    )
    wake_lock.acquire()

    try:
        # Set up notification channel and start foreground (use service context)
        create_notification_channel(service)
        notification = build_extraction_notification(service, "Preparing extraction...")
        service.startForeground(NOTIFICATION_ID, notification)

        # Read task info from p4a service argument (env var)
        task_json = os.environ.get("PYTHON_SERVICE_ARGUMENT", "")
        if not task_json:
            return

        task = json.loads(task_json)
        file_path = task["file_path"]
        filename = task["filename"]
        work_dir = task["work_dir"]
        roms_folder = task["roms_folder"]
        system_data = task["system_data"]
        item_id = task["item_id"]

        _process_file(
            service, item_id, file_path, filename, work_dir, roms_folder, system_data
        )

    except Exception as e:
        try:
            # Try to report the error via IPC
            task_json = os.environ.get("PYTHON_SERVICE_ARGUMENT", "")
            if task_json:
                task = json.loads(task_json)
                write_status(
                    task["work_dir"],
                    task["item_id"],
                    {
                        "status": "failed",
                        "progress": 0.0,
                        "error": f"{type(e).__name__}: {str(e)[:100]}",
                    },
                )
        except Exception:
            pass
    finally:
        if wake_lock.isHeld():
            wake_lock.release()
        service.stopForeground(True)
        service.stopSelf()


def _process_file(
    service, item_id, file_path, filename, work_dir, roms_folder, system_data
):
    """
    Process a downloaded file: extract ZIP, decompress NSZ, or move files.

    Mirrors the logic in DownloadManager._process_downloaded_file() but
    communicates via IPC instead of direct state mutation.
    """
    formats = system_data.get("file_format", [])
    os.makedirs(work_dir, exist_ok=True)
    os.makedirs(roms_folder, exist_ok=True)

    # Android DM downloads to its own external files directory, not work_dir.
    # Move the file into work_dir first so the rest of the logic (which scans
    # work_dir via os.listdir) matches the desktop DownloadManager exactly.
    work_file_path = os.path.join(work_dir, filename)
    if os.path.abspath(file_path) != os.path.abspath(work_file_path):
        shutil.move(file_path, work_file_path)
        file_path = work_file_path

    # Handle ZIP extraction
    if filename.endswith(".zip") and system_data.get("should_unzip", False):
        _extract_zip(
            service,
            item_id,
            file_path,
            filename,
            work_dir,
            roms_folder,
            system_data,
            formats,
        )
        return

    # Handle NSZ decompression
    if filename.endswith(".nsz"):
        _decompress_nsz(service, item_id, file_path, work_dir, roms_folder, system_data)
        return

    # Simple file move
    update_notification(service, f"Moving: {filename}", 0, 100)
    write_status(work_dir, item_id, {"status": "moving", "progress": 0.0})

    # Include .zip in move filter when not extracting
    move_formats = list(formats)
    if filename.endswith(".zip") and ".zip" not in [
        ext.lower() for ext in move_formats
    ]:
        move_formats.append(".zip")

    files_to_move = [
        f
        for f in os.listdir(work_dir)
        if f not in IPC_FILENAMES
        and any(f.lower().endswith(ext.lower()) for ext in move_formats)
        and os.path.isfile(os.path.join(work_dir, f))
    ]

    for i, f in enumerate(files_to_move):
        if _check_cancel(work_dir, item_id):
            return
        src_path = os.path.join(work_dir, f)
        dst_path = os.path.join(roms_folder, f)
        err = _move_to_roms(src_path, dst_path)
        if err:
            write_status(
                work_dir,
                item_id,
                {"status": "failed", "progress": 0.0, "error": err},
            )
            update_notification(service, err, 0, 100)
            return
        progress = (i + 1) / max(len(files_to_move), 1)
        write_status(work_dir, item_id, {"status": "moving", "progress": progress})
        update_notification(service, f"Moving: {f}", int(progress * 100), 100)

    _cleanup_work_dir(work_dir)

    write_status(work_dir, item_id, {"status": "completed", "progress": 1.0})
    update_notification(service, "Extraction complete", 100, 100)


def _extract_zip(
    service, item_id, file_path, filename, work_dir, roms_folder, system_data, formats
):
    """Extract a ZIP in parallel with byte-weighted progress and speed/ETA."""
    import threading
    from utils.progress import SpeedTracker
    from utils.parallel_extract import parallel_extract_zip

    update_notification(service, f"Extracting: {filename}", 0, 100)

    extract_contents = system_data.get("extract_contents", True)

    tracker = SpeedTracker()
    cancel_event = threading.Event()
    state_lock = threading.Lock()
    last_notif_pct = [-1]

    def cancel_check():
        if cancel_event.is_set():
            return True
        if _check_cancel(work_dir, item_id):
            cancel_event.set()
            return True
        return False

    def on_progress(written, total):
        with state_lock:
            speed = tracker.update(written)
        progress = (written / total) if total else 0.0
        write_status(
            work_dir,
            item_id,
            {
                "status": "extracting",
                "progress": progress,
                "downloaded": written,
                "total_size": total,
                "speed": speed,
            },
        )
        pct = int(progress * 100)
        if pct != last_notif_pct[0]:
            last_notif_pct[0] = pct
            update_notification(
                service, f"Extracting: {filename}", pct, 100
            )

    ok = parallel_extract_zip(
        file_path,
        work_dir,
        on_progress=on_progress,
        should_cancel=cancel_check,
    )
    if not ok:
        if not cancel_event.is_set():
            # Distinguish extraction error from user cancellation
            write_status(
                work_dir,
                item_id,
                {
                    "status": "failed",
                    "progress": 0.0,
                    "error": "ZIP extraction failed",
                },
            )
        # If cancelled, _check_cancel already wrote the "cancelled" status.
        return

    os.remove(file_path)

    # Move extracted files
    write_status(work_dir, item_id, {"status": "moving", "progress": 0.0})
    update_notification(service, "Moving files...", 0, 100)

    if not extract_contents:
        # Keep folder structure
        extracted_items = [
            f
            for f in os.listdir(work_dir)
            if not f.startswith(".") and f not in IPC_FILENAMES
        ]
        items_to_move = []
        for f in extracted_items:
            src_path = os.path.join(work_dir, f)
            if os.path.isdir(src_path):
                items_to_move.append(f)
            elif any(f.lower().endswith(ext.lower()) for ext in formats):
                items_to_move.append(f)

        for i, extracted_item in enumerate(items_to_move):
            if _check_cancel(work_dir, item_id):
                return
            src_path = os.path.join(work_dir, extracted_item)
            dst_path = os.path.join(roms_folder, extracted_item)
            err = _move_to_roms(src_path, dst_path)
            if err:
                write_status(
                    work_dir,
                    item_id,
                    {"status": "failed", "progress": 0.0, "error": err},
                )
                update_notification(service, err, 0, 100)
                return
            progress = (i + 1) / max(len(items_to_move), 1)
            write_status(work_dir, item_id, {"status": "moving", "progress": progress})
    else:
        # Move matching files
        files_to_move = [
            f
            for f in os.listdir(work_dir)
            if f not in IPC_FILENAMES
            and any(f.lower().endswith(ext.lower()) for ext in formats)
            and os.path.isfile(os.path.join(work_dir, f))
        ]
        for i, f in enumerate(files_to_move):
            if _check_cancel(work_dir, item_id):
                return
            src_path = os.path.join(work_dir, f)
            dst_path = os.path.join(roms_folder, f)
            err = _move_to_roms(src_path, dst_path)
            if err:
                write_status(
                    work_dir,
                    item_id,
                    {"status": "failed", "progress": 0.0, "error": err},
                )
                update_notification(service, err, 0, 100)
                return
            progress = (i + 1) / max(len(files_to_move), 1)
            write_status(work_dir, item_id, {"status": "moving", "progress": progress})

    _cleanup_work_dir(work_dir)
    write_status(work_dir, item_id, {"status": "completed", "progress": 1.0})
    update_notification(service, "Extraction complete", 100, 100)


def _decompress_nsz(service, item_id, file_path, work_dir, roms_folder, system_data):
    """Decompress an NSZ file with real-time progress, speed, and ETA."""
    from utils.nsz import decompress_nsz_file
    from utils.progress import SpeedTracker

    filename = os.path.basename(file_path)
    update_notification(service, f"Decompressing: {filename}", 0, 100)
    write_status(
        work_dir,
        item_id,
        {
            "status": "extracting",
            "progress": 0.0,
            "downloaded": 0,
            "total_size": 0,
            "speed": 0.0,
        },
    )

    tracker = SpeedTracker()
    last_notif_pct = [-1]

    def nsz_progress(step, processed, total):
        speed = tracker.update(processed)
        progress = (processed / total) if total > 0 else 0.0
        write_status(
            work_dir,
            item_id,
            {
                "status": "extracting",
                "progress": progress,
                "downloaded": processed,
                "total_size": total,
                "speed": speed,
            },
        )
        pct = int(progress * 100)
        if pct != last_notif_pct[0]:
            last_notif_pct[0] = pct
            update_notification(service, f"Decompressing: {filename}", pct, 100)

    keys_path = system_data.get("nsz_keys_path", "")
    # Decompress straight into roms_folder so the resulting multi-GB NSP
    # never has to be copied across the app-private / shared-storage mount
    # boundary on Android — that cross-mount copy was the slow / often-failing
    # step. Falls back to work_dir if the direct write fails (no permission).
    nsz_output_dir = roms_folder
    try:
        os.makedirs(roms_folder, exist_ok=True)
        # Probe write access cheaply before committing the library to the path
        with open(os.path.join(roms_folder, ".write_probe"), "wb") as _f:
            _f.write(b"")
        os.remove(os.path.join(roms_folder, ".write_probe"))
    except (OSError, PermissionError):
        nsz_output_dir = work_dir

    success = decompress_nsz_file(file_path, nsz_output_dir, keys_path, nsz_progress)

    if success:
        # If we wrote to roms_folder directly, no move is needed — common case.
        if nsz_output_dir != roms_folder:
            write_status(work_dir, item_id, {"status": "moving", "progress": 0.0})
            update_notification(service, "Moving files...", 0, 100)

            for f in os.listdir(nsz_output_dir):
                if f.endswith(".nsp"):
                    src_path = os.path.join(nsz_output_dir, f)
                    dst_path = os.path.join(roms_folder, f)
                    err = _move_to_roms(src_path, dst_path)
                    if err:
                        write_status(
                            work_dir,
                            item_id,
                            {"status": "failed", "progress": 0.0, "error": err},
                        )
                        update_notification(service, err, 0, 100)
                        return

        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass

        write_status(work_dir, item_id, {"status": "completed", "progress": 1.0})
        update_notification(service, "Decompression complete", 100, 100)
    else:
        write_status(
            work_dir,
            item_id,
            {
                "status": "failed",
                "progress": 0.0,
                "error": "NSZ decompression failed",
            },
        )


def _check_cancel(work_dir, item_id):
    """
    Check for a cancel signal. Returns True if this item should stop.
    """
    cancel = read_cancel(work_dir)
    if cancel:
        cancel_type = cancel.get("type", "")
        if cancel_type in ("current", "all"):
            clear_cancel(work_dir)
            write_status(work_dir, item_id, {"status": "cancelled", "progress": 0.0})
            return True
    return False


def _cleanup_work_dir(work_dir):
    """Remove leftover files in the work directory (preserving IPC files)."""
    for f in os.listdir(work_dir):
        if f in IPC_FILENAMES:
            continue
        file_to_remove = os.path.join(work_dir, f)
        if os.path.isfile(file_to_remove):
            try:
                os.remove(file_to_remove)
            except Exception:
                pass


# p4a service entry point
if __name__ == "__main__":
    run_service()
