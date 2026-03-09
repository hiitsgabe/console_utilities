# Android Parallel Chunk Download Service

## Problem

Android's system `DownloadManager` does not support HTTP range requests or parallel chunk downloads. Large ROM files download at single-stream speed. The desktop `DownloadManager` already splits files >5MB into 4 parallel range-request workers for significant speed gains.

## Solution

Replace Android's system `DownloadManager` with a custom Python foreground service (`DownloadService`) that performs HTTP downloads using `requests` + `ThreadPoolExecutor`, with a notification progress bar — the same UX as Chrome or any download app.

## Architecture

```
Main App (AndroidDownloadManager)       DownloadService (foreground)
─────────────────────────────────       ────────────────────────────
add_to_queue()
  → writes task JSON to IPC file ──►    reads task JSON
  → starts DownloadService              acquires wake lock
                                        shows notification with progress bar
                                        HEAD → check Content-Length + Accept-Ranges
                                        if >5MB + ranges: 4 parallel chunk workers
                                        else: single-stream requests.get(stream=True)
poll_loop() ◄── reads IPC status ──     writes progress JSON (downloaded, speed, %)
                                        on complete → starts ExtractionService
                                        releases wake lock, stops self
```

## Files

### New
- `src/droid/download_service.py` — foreground service entry point (like `service.py`)

### Modified
- `src/droid/download_manager.py` — replace system DM with IPC to download service
- `src/droid/ipc.py` — add download task queue IPC (write task, read task)
- `src/droid/notification.py` — add download notification builder
- `buildozer.spec` — register `downloadservice` as a p4a service

## Download Service Internals

Reuses the proven desktop parallel chunk logic:

- `_download_file_parallel()` — splits file into 4 range-request workers via `ThreadPoolExecutor`
- `_download_chunk()` — each worker downloads byte range to `.partN` temp file
- Stitches chunks into final file via `shutil.copyfileobj`
- Falls back to single-stream for files <5MB or servers without range support
- Constants: `PARALLEL_WORKERS = 4`, `PARALLEL_MIN_SIZE = 5 * 1024 * 1024`

## IPC Protocol

### Task Queue (main app → service)
File: `download_task.json` in work_dir
```json
{
  "item_id": "3",
  "url": "https://...",
  "filename": "game.zip",
  "work_dir": "/path/to/downloads",
  "roms_folder": "/path/to/roms/snes",
  "system_data": { ... },
  "auth_headers": { ... },
  "cookies": { ... }
}
```

### Status (service → main app)
Existing IPC pattern. File: `status_{item_id}.json`
```json
{
  "status": "downloading",
  "progress": 0.65,
  "downloaded": 34000000,
  "total_size": 52000000,
  "speed": 4500000
}
```

### Cancel (main app → service)
Existing `write_cancel()` / `read_cancel()` pattern.

## What Gets Removed

- All `android.app.DownloadManager` Java API calls (enqueue, query, cursor)
- `BroadcastReceiver` for `ACTION_DOWNLOAD_COMPLETE` (droid/receiver.py usage)
- `_download_ids` mapping (no more Android download IDs)
- IA redirect resolution in download_manager.py (service handles directly)
- `_poll_download_progress()` JNI polling (replaced by file-based IPC polling)

## What Stays

- Queue management (add/remove/cancel) in `AndroidDownloadManager`
- Poll thread reading IPC status files (`_poll_extraction_status` pattern)
- `ExtractionService` triggered after download completes
- Auth header construction (moved into task JSON for the service)
- Pause/resume lifecycle (service has own wake lock; main app pause/resume for IPC)

## Cancellation

Main app calls `write_cancel()`. Download service checks between chunks and sets `threading.Event` to abort workers — same as desktop's `chunk_failed` event. Partial `.partN` files are cleaned up.

## Notification

Uses existing `notification.py` helpers with a new channel/builder for downloads (separate from extraction). Shows:
- Title: "Downloading: filename.zip"
- Progress bar with percentage
- Description: "Console Utilities - System Name"
