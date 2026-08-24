"""
Pure logic for the single-write parallel download path (no jnius imports).

Workers write byte ranges directly at offsets into one preallocated hidden
file at its final destination, so there is no stitch pass and no
cross-filesystem move afterwards. A sidecar meta file records fsync-committed
progress per worker so a SIGKILLed download resumes instead of restarting.
"""

import json
import os

# fsync cadence: keeps the dirty page cache small (large bursts of dirty
# pages are what provoked the lmkd kill observed on device) and bounds how
# much work a resume repeats.
FSYNC_INTERVAL = 64 * 1024 * 1024

_META_SUFFIX = ".dlmeta"


def needs_extraction(filename, system_data):
    """True when the file requires a post-download processing pass."""
    if filename.endswith(".nsz"):
        return True
    return filename.endswith(".zip") and system_data.get("should_unzip", False)


def download_paths(filename, work_dir, roms_folder, system_data):
    """
    Return (tmp_path, final_path) for a download.

    Files needing extraction land in work_dir (internal storage, fast) for the
    extraction service to consume. Everything else downloads straight into the
    destination folder under a hidden temp name, so completion is a same-
    filesystem rename instead of a full copy.
    """
    dest = work_dir if needs_extraction(filename, system_data) else roms_folder
    return os.path.join(dest, "." + filename + ".dl"), os.path.join(dest, filename)


def meta_path(tmp_path):
    return tmp_path + _META_SUFFIX


def compute_ranges(total_size, num_workers):
    """Split total_size into num_workers inclusive (start, end) byte ranges."""
    chunk_size = total_size // num_workers
    ranges = []
    for i in range(num_workers):
        start = i * chunk_size
        end = (total_size - 1) if i == num_workers - 1 else ((i + 1) * chunk_size - 1)
        ranges.append((start, end))
    return ranges


def save_committed(path, total_size, committed):
    """Atomically persist fsync-committed byte counts per worker."""
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"total_size": total_size, "committed": list(committed)}, f)
    os.replace(tmp, path)


def load_committed(path, total_size, num_workers):
    """
    Return committed byte counts from a prior attempt, or None if absent,
    corrupt, or not matching this download's size/worker layout.
    """
    try:
        with open(path, "r") as f:
            data = json.load(f)
        committed = data["committed"]
        if data["total_size"] != total_size or len(committed) != num_workers:
            return None
        return [int(c) for c in committed]
    except (OSError, ValueError, KeyError, TypeError):
        return None


def write_stream_at(
    path,
    offset,
    chunk_iter,
    on_bytes=None,
    on_committed=None,
    fsync_every=FSYNC_INTERVAL,
):
    """
    Write an iterable of byte chunks into an existing file starting at offset.

    on_bytes(n) fires after each chunk (progress display). on_committed(total)
    fires only after fsync — data up to that count is guaranteed on disk, so
    it is safe to record for resume. Returns total bytes written.
    """
    written = 0
    since_sync = 0
    with open(path, "r+b") as f:
        f.seek(offset)
        for chunk in chunk_iter:
            if not chunk:
                continue
            f.write(chunk)
            written += len(chunk)
            since_sync += len(chunk)
            if on_bytes:
                on_bytes(len(chunk))
            if since_sync >= fsync_every:
                f.flush()
                os.fsync(f.fileno())
                since_sync = 0
                if on_committed:
                    on_committed(written)
        f.flush()
        os.fsync(f.fileno())
    if on_committed:
        on_committed(written)
    return written


def select_zip_members(names, formats, extract_contents):
    """
    Choose which zip members to extract into the destination.

    extract_contents=False keeps the archive's structure: everything.
    extract_contents=True mirrors the old extract-then-move behavior:
    top-level files matching the system's formats.
    """
    if not extract_contents:
        return list(names)
    return [
        n
        for n in names
        if "/" not in n and any(n.lower().endswith(ext.lower()) for ext in formats)
    ]
