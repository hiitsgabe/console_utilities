"""
Ghost file cleaner service for Console Utilities.
Scans for and removes junk files (.DS_Store, ._ files, Thumbs.db, etc.)
that clutter ROM folders.
"""

import os
import shutil
from typing import List, Dict, Any, Tuple, Callable, Optional

# Ghost file patterns
GHOST_FILE_NAMES = {
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
}

GHOST_FOLDER_NAMES = {
    "__MACOSX",
    ".AppleDouble",
}


def is_ghost_file(filename: str) -> Optional[str]:
    """
    Check if a filename is a ghost file.

    Returns the ghost type string if it is, None otherwise.
    """
    if filename in GHOST_FILE_NAMES:
        return filename
    if filename.startswith("._"):
        return "._* (resource fork)"
    return None


def is_ghost_folder(foldername: str) -> Optional[str]:
    """
    Check if a folder name is a ghost folder.

    Returns the ghost type string if it is, None otherwise.
    """
    if foldername in GHOST_FOLDER_NAMES:
        return foldername
    return None


def scan_ghost_files(
    folder_path: str,
    recursive: bool = True,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> List[Dict[str, Any]]:
    """
    Scan a folder for ghost files and folders.

    Args:
        folder_path: Path to scan
        recursive: Whether to scan recursively
        progress_callback: Optional callback(current, total)

    Returns:
        List of ghost file dicts with: path, name, type, size, is_dir
    """
    ghost_files = []

    try:
        if recursive:
            entries = []
            for root, dirs, files in os.walk(folder_path):
                for d in dirs:
                    entries.append(os.path.join(root, d))
                for f in files:
                    entries.append(os.path.join(root, f))
        else:
            entries = [os.path.join(folder_path, e) for e in os.listdir(folder_path)]

        total = len(entries)

        for i, entry_path in enumerate(entries):
            if progress_callback:
                progress_callback(i + 1, total)

            name = os.path.basename(entry_path)

            if os.path.isdir(entry_path):
                ghost_type = is_ghost_folder(name)
                if ghost_type:
                    # Calculate folder size
                    size = _get_folder_size(entry_path)
                    ghost_files.append(
                        {
                            "path": entry_path,
                            "name": name,
                            "type": ghost_type,
                            "size": size,
                            "is_dir": True,
                        }
                    )
            else:
                ghost_type = is_ghost_file(name)
                if ghost_type:
                    try:
                        size = os.path.getsize(entry_path)
                    except OSError:
                        size = 0
                    ghost_files.append(
                        {
                            "path": entry_path,
                            "name": name,
                            "type": ghost_type,
                            "size": size,
                            "is_dir": False,
                        }
                    )

    except OSError:
        pass

    return ghost_files


def get_ghost_summary(ghost_files: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Get a summary of ghost files grouped by type.

    Returns:
        Dict mapping type name to count.
    """
    summary = {}
    for f in ghost_files:
        ghost_type = f["type"]
        summary[ghost_type] = summary.get(ghost_type, 0) + 1
    return summary


def get_total_size(ghost_files: List[Dict[str, Any]]) -> int:
    """Get total size of all ghost files in bytes."""
    return sum(f.get("size", 0) for f in ghost_files)


def clean_ghost_files(
    ghost_files: List[Dict[str, Any]],
    progress_callback: Optional[Callable[[int, int, int], None]] = None,
    base_folder: str = "",
) -> Tuple[int, int]:
    """
    Delete ghost files and folders.

    Args:
        ghost_files: List of ghost file dicts from scan_ghost_files
        progress_callback: Optional callback(current, total, bytes_freed)
        base_folder: If set, only delete files within this folder (safety check)

    Returns:
        Tuple of (files_removed, bytes_freed)
    """
    files_removed = 0
    bytes_freed = 0

    # Resolve base folder for path validation
    resolved_base = os.path.realpath(base_folder) if base_folder else ""

    # Delete folders first (they may contain files that are also in the list)
    # Sort so directories come first, deepest paths first
    sorted_files = sorted(
        ghost_files,
        key=lambda f: (not f["is_dir"], -f["path"].count(os.sep)),
    )

    for i, ghost in enumerate(sorted_files):
        path = ghost["path"]
        try:
            resolved_path = os.path.realpath(path)

            # Safety: skip paths outside the base folder
            if resolved_base and not resolved_path.startswith(resolved_base + os.sep):
                continue

            if not os.path.exists(resolved_path):
                # Already deleted (parent folder was removed)
                continue

            size = ghost.get("size", 0)
            if ghost["is_dir"]:
                shutil.rmtree(resolved_path)
            else:
                os.remove(resolved_path)

            files_removed += 1
            bytes_freed += size
        except OSError:
            pass

        if progress_callback:
            progress_callback(i + 1, len(sorted_files), bytes_freed)

    return files_removed, bytes_freed


def format_size(size_bytes: int) -> str:
    """Format size in bytes to human readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def _get_folder_size(folder_path: str) -> int:
    """Calculate total size of a folder recursively."""
    total = 0
    try:
        for root, dirs, files in os.walk(folder_path):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
    except OSError:
        pass
    return total
