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
import time
import traceback
from zipfile import ZipFile

# Add src to path (p4a service may not have it)
_service_dir = os.path.dirname(os.path.abspath(__file__))
_src_dir = os.path.dirname(_service_dir)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from droid import chunks
from droid.ipc import write_status, read_cancel, clear_cancel, IPC_FILENAMES
from droid.notification import (
    create_notification_channel,
    build_extraction_notification,
    update_notification,
    NOTIFICATION_ID,
)

from jnius import autoclass

PythonService = autoclass("org.kivy.android.PythonService")
PowerManager = autoclass("android.os.PowerManager")
Context = autoclass("android.content.Context")


def run_service():
    """
    Main entry point for the extraction foreground service.

    Reads task info from PYTHON_SERVICE_ARGUMENT env var, performs extraction,
    and communicates progress via IPC.
    """
    # Earliest breadcrumb — proves the ExtractionService python process ran
    # at all, regardless of what happens later. Goes to both error.log and
    # logcat (stdout is captured by Android's log buffer on p4a).
    try:
        from utils.logging import log_error as _log

        _log(f"NSZ-SVC run_service entered pid={os.getpid()}")
    except Exception as _e:
        print(f"NSZ-SVC bootstrap log_error failed: {_e}", flush=True)

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
        nsz_keys_path = task.get("nsz_keys_path", "")

        _process_file(
            service,
            item_id,
            file_path,
            filename,
            work_dir,
            roms_folder,
            system_data,
            nsz_keys_path,
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
    service,
    item_id,
    file_path,
    filename,
    work_dir,
    roms_folder,
    system_data,
    nsz_keys_path="",
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
        _decompress_nsz(
            service,
            item_id,
            file_path,
            work_dir,
            roms_folder,
            system_data,
            nsz_keys_path,
        )
        return

    # Files that need no extraction never reach this service anymore — the
    # download service writes them directly to the destination and completes.
    write_status(work_dir, item_id, {"status": "completed", "progress": 1.0})


def _extract_zip(
    service, item_id, file_path, filename, work_dir, roms_folder, system_data, formats
):
    """
    Extract selected ZIP members directly into the destination folder.

    Extracting straight to roms_folder (instead of the old extract-to-work_dir
    then move) means the extracted bytes hit the slow SD card exactly once.
    Progress is byte-based so multi-GB single-file archives don't freeze the
    UI, and cancel is honored mid-file.
    """
    update_notification(service, f"Extracting: {filename}", 0, 100)
    write_status(work_dir, item_id, {"status": "extracting", "progress": 0.0})

    extract_contents = system_data.get("extract_contents", True)
    roms_root = os.path.abspath(roms_folder)

    with ZipFile(file_path, "r") as zip_ref:
        names = chunks.select_zip_members(zip_ref.namelist(), formats, extract_contents)
        infos = [zip_ref.getinfo(n) for n in names]
        total_bytes = sum(i.file_size for i in infos) or 1
        done = 0
        last_report = 0.0

        for info in infos:
            if _check_cancel(work_dir, item_id):
                return
            dest = os.path.abspath(os.path.join(roms_folder, info.filename))
            if not dest.startswith(roms_root + os.sep):
                continue  # zip-slip: refuse members escaping the destination
            if info.is_dir():
                os.makedirs(dest, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with zip_ref.open(info) as src, open(dest, "wb") as out:
                while True:
                    buf = src.read(1024 * 1024)
                    if not buf:
                        break
                    out.write(buf)
                    done += len(buf)
                    now = time.time()
                    if now - last_report >= 0.5:
                        last_report = now
                        if _check_cancel(work_dir, item_id):
                            out.close()
                            os.remove(dest)
                            return
                        progress = done / total_bytes
                        write_status(
                            work_dir,
                            item_id,
                            {"status": "extracting", "progress": progress},
                        )
                        update_notification(
                            service,
                            f"Extracting: {filename}",
                            int(progress * 100),
                            100,
                        )

    os.remove(file_path)
    _cleanup_work_dir(work_dir)
    write_status(work_dir, item_id, {"status": "completed", "progress": 1.0})
    update_notification(service, "Extraction complete", 100, 100)


def _decompress_nsz(
    service, item_id, file_path, work_dir, roms_folder, system_data, nsz_keys_path=""
):
    """Decompress an NSZ file directly into the selected ROM folder (no move)."""
    from utils.logging import log_error as _log

    filename = os.path.basename(file_path)
    update_notification(service, f"Decompressing: {filename}", 0, 100)
    write_status(work_dir, item_id, {"status": "extracting", "progress": 0.0})

    # Diagnostic breadcrumbs — the ExtractionService runs as a separate Python
    # process; logs go to the same external app data dir but only if we get
    # past the import and basic setup. Capture everything we need to triage
    # large-file failures from one run.
    try:
        nsz_size = os.path.getsize(file_path) if os.path.exists(file_path) else -1
        st = os.statvfs(roms_folder) if os.path.isdir(roms_folder) else None
        free_bytes = st.f_bavail * st.f_frsize if st else -1
        keys_exists = bool(nsz_keys_path) and os.path.isfile(nsz_keys_path)
        _log(
            f"NSZ-SVC start: file={filename} nsz_size={nsz_size} "
            f"keys_set={bool(nsz_keys_path)} keys_exists={keys_exists} "
            f"out={roms_folder} free_bytes={free_bytes}"
        )
    except Exception as _e:
        _log(f"NSZ-SVC diag pre-check failed: {type(_e).__name__}: {_e}")

    try:
        from utils.nsz import decompress_nsz_file
    except Exception as _e:
        import traceback as _tb

        _log(f"NSZ-SVC import failed: {type(_e).__name__}: {_e}\n{_tb.format_exc()}")
        write_status(
            work_dir,
            item_id,
            {
                "status": "failed",
                "progress": 0.0,
                "error": f"NSZ library import failed: {_e}",
            },
        )
        return

    def nsz_progress(text, percent):
        write_status(
            work_dir, item_id, {"status": "extracting", "progress": percent / 100.0}
        )
        update_notification(service, f"Decompressing: {filename}", percent, 100)

    os.makedirs(roms_folder, exist_ok=True)

    try:
        success = decompress_nsz_file(
            file_path, roms_folder, nsz_keys_path, nsz_progress
        )
        last_error = "" if success else "decompress_nsz_file returned False"
    except Exception as _e:
        import traceback as _tb

        success = False
        last_error = f"{type(_e).__name__}: {_e}"
        _log(f"NSZ-SVC decompress raised: {last_error}\n{_tb.format_exc()}")

    _log(f"NSZ-SVC done: success={success} reason={last_error or '-'}")

    if success:
        if os.path.exists(file_path):
            os.remove(file_path)

        write_status(work_dir, item_id, {"status": "completed", "progress": 1.0})
        update_notification(service, "Decompression complete", 100, 100)
    else:
        write_status(
            work_dir,
            item_id,
            {
                "status": "failed",
                "progress": 0.0,
                "error": last_error or "NSZ decompression failed",
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
