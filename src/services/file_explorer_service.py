import os
import shutil
import subprocess
import zipfile
from typing import List, Optional, Tuple


def list_directory(path: str) -> Tuple[List[dict], str]:
    """Lists directory contents, folders first, alpha-sorted, hidden files excluded, symlinks followed."""
    try:
        entries = []
        for name in os.listdir(path):
            if name.startswith("."):
                continue
            full_path = os.path.join(path, name)
            try:
                stat = os.stat(full_path)
                is_dir = os.path.isdir(full_path)
                entries.append(
                    {
                        "name": name,
                        "is_dir": is_dir,
                        "size": None if is_dir else stat.st_size,
                        "modified": stat.st_mtime,
                    }
                )
            except (PermissionError, OSError):
                continue
        entries.sort(key=lambda e: (not e["is_dir"], e["name"].lower()))
        return entries, ""
    except PermissionError as exc:
        return [], str(exc)
    except OSError as exc:
        return [], str(exc)


def _resolve_conflict(dest_dir: str, basename: str) -> str:
    """Appends ' (N)' suffix to basename if a file with that name already exists in dest_dir."""
    candidate = os.path.join(dest_dir, basename)
    if not os.path.exists(candidate):
        return basename
    name, _, ext = basename.rpartition(".")
    if not name:
        name = ext
        ext = ""
    else:
        ext = "." + ext
    counter = 2
    while True:
        new_name = f"{name} ({counter}){ext}"
        if not os.path.exists(os.path.join(dest_dir, new_name)):
            return new_name
        counter += 1


def copy_files(sources: List[str], dest_dir: str) -> Tuple[bool, str]:
    """Copies files/folders to dest_dir, auto-resolving name conflicts with ' (N)' suffix."""
    try:
        for src in sources:
            basename = os.path.basename(src.rstrip(os.sep))
            resolved = _resolve_conflict(dest_dir, basename)
            dest = os.path.join(dest_dir, resolved)
            if os.path.isdir(src):
                shutil.copytree(src, dest)
            else:
                shutil.copy2(src, dest)
        return True, ""
    except PermissionError as exc:
        return False, str(exc)
    except OSError as exc:
        return False, str(exc)


def move_files(sources: List[str], dest_dir: str) -> Tuple[bool, str]:
    """Moves files/folders to dest_dir, auto-resolving name conflicts with ' (N)' suffix."""
    try:
        for src in sources:
            basename = os.path.basename(src.rstrip(os.sep))
            resolved = _resolve_conflict(dest_dir, basename)
            dest = os.path.join(dest_dir, resolved)
            shutil.move(src, dest)
        return True, ""
    except PermissionError as exc:
        return False, str(exc)
    except OSError as exc:
        return False, str(exc)


def delete_paths(paths: List[str]) -> Tuple[bool, str]:
    """Deletes files and folders (recursive)."""
    try:
        for path in paths:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
        return True, ""
    except PermissionError as exc:
        return False, str(exc)
    except OSError as exc:
        return False, str(exc)


def rename_path(path: str, new_name: str) -> Tuple[bool, str]:
    """Renames a file or folder. Validates that new_name contains no path separators."""
    if "/" in new_name or "\\" in new_name:
        return False, "Name must not contain path separators"
    if not new_name:
        return False, "Name must not be empty"
    try:
        parent = os.path.dirname(path)
        dest = os.path.join(parent, new_name)
        os.rename(path, dest)
        return True, ""
    except PermissionError as exc:
        return False, str(exc)
    except OSError as exc:
        return False, str(exc)


def create_folder(parent: str, name: str) -> Tuple[bool, str]:
    """Creates a new directory named name inside parent."""
    try:
        os.makedirs(os.path.join(parent, name), exist_ok=True)
        return True, ""
    except PermissionError as exc:
        return False, str(exc)
    except OSError as exc:
        return False, str(exc)


def read_text_file(path: str, max_lines: int = 5000) -> Tuple[List[str], bool, str]:
    """Reads a text file, returning (lines, was_truncated, error).

    Detects binary files via null-byte check in first 1024 bytes.
    """
    try:
        with open(path, "rb") as f:
            header = f.read(1024)
        if b"\x00" in header:
            return [], False, "File appears to be binary"
        with open(path, "r", errors="replace") as f:
            lines = []
            truncated = False
            for i, line in enumerate(f):
                if i >= max_lines:
                    truncated = True
                    break
                lines.append(line.rstrip("\n"))
        return lines, truncated, ""
    except PermissionError as exc:
        return [], False, str(exc)
    except OSError as exc:
        return [], False, str(exc)


def extract_archive(path: str, to_subfolder: bool) -> Tuple[bool, str]:
    """Extracts a .zip or .rar archive.

    If to_subfolder is True, extracts into a folder named after the archive (without extension).
    """
    try:
        parent = os.path.dirname(path)
        basename = os.path.basename(path)
        name_no_ext, ext = os.path.splitext(basename)
        ext_lower = ext.lower()

        if to_subfolder:
            dest = os.path.join(parent, name_no_ext)
            os.makedirs(dest, exist_ok=True)
        else:
            dest = parent

        if ext_lower == ".zip":
            with zipfile.ZipFile(path, "r") as zf:
                zf.extractall(dest)
            return True, ""
        elif ext_lower == ".rar":
            if not is_unrar_available():
                return False, "unrar command not found"
            result = subprocess.run(
                ["unrar", "x", "-y", path, dest + os.sep],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                return False, result.stderr.strip() or "unrar failed"
            return True, ""
        else:
            return False, f"Unsupported archive format: {ext}"
    except PermissionError as exc:
        return False, str(exc)
    except OSError as exc:
        return False, str(exc)


def is_unrar_available() -> bool:
    """Returns True if the unrar command is available on PATH."""
    return shutil.which("unrar") is not None


def format_size(size_bytes: Optional[int]) -> str:
    """Formats a file size in bytes to a human-readable string (B, KB, MB, GB)."""
    if size_bytes is None:
        return ""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


_TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".cfg",
    ".conf",
    ".ini",
    ".json",
    ".xml",
    ".yaml",
    ".yml",
    ".log",
    ".csv",
    ".py",
    ".sh",
    ".bat",
    ".lua",
    ".js",
    ".html",
    ".css",
    ".toml",
    ".rst",
    ".nfo",
    ".readme",
}

_ARCHIVE_EXTENSIONS = {".zip", ".rar"}


def get_file_icon(name: str, is_dir: bool) -> str:
    """Returns a single character icon for a file entry.

    D = directory, Z = archive (.zip/.rar), T = text file, F = other.
    """
    if is_dir:
        return "D"
    _, ext = os.path.splitext(name)
    ext_lower = ext.lower()
    if ext_lower in _ARCHIVE_EXTENSIONS:
        return "Z"
    if ext_lower in _TEXT_EXTENSIONS:
        return "T"
    return "F"
