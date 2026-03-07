"""ZIP ROM handling utilities for sport patchers.

Handles extracting ROMs from ZIP files and re-zipping patched output.
"""

import os
import re
import shutil
import tempfile
import zipfile


def is_zip(path):
    """Check if path is a ZIP file."""
    return path.lower().endswith(".zip")


def _find_psx_data_track(bin_files):
    """Find the PSX data track from a list of .bin files.

    Priority:
      1. Track 1 / Track 01 in filename (the data track)
      2. A .bin without any track number (standalone data image)
      3. Largest .bin as fallback
    """
    track_pattern = re.compile(r"[(\s\-]track\s*0*1[)\s.\-]", re.IGNORECASE)
    any_track_pattern = re.compile(r"[(\s\-]track\s*\d+", re.IGNORECASE)

    # Look for explicit "Track 1"
    for f in bin_files:
        if track_pattern.search(os.path.basename(f)):
            return f

    # Look for a .bin with no track number at all (standalone data image)
    no_track = [f for f in bin_files if not any_track_pattern.search(os.path.basename(f))]
    if len(no_track) == 1:
        return no_track[0]

    # Fallback: largest file (data track is usually the biggest)
    return max(bin_files, key=lambda f: os.path.getsize(f))


def extract_rom_from_zip(zip_path, rom_extensions):
    """Extract ZIP and find ROM file matching extensions.

    For PSX (.cue/.bin), prefers .cue files so the caller can resolve
    the data track via its existing cue-parsing logic.  If no .cue is
    found, uses track-number heuristics to pick the data track .bin.

    Args:
        zip_path: Path to the ZIP file.
        rom_extensions: List of lowercase extensions to look for
                        (e.g. [".sfc", ".smc"]).

    Returns:
        (rom_path, temp_dir) tuple.

    Raises:
        ValueError: If no matching ROM file is found inside the ZIP.
    """
    temp_dir = tempfile.mkdtemp(prefix="patcher_zip_")

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(temp_dir)

    cue_files = []
    bin_files = []
    rom_files = []

    is_psx = ".cue" in rom_extensions

    for root, _dirs, files in os.walk(temp_dir):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            full = os.path.join(root, f)
            if ext == ".cue" and is_psx:
                cue_files.append(full)
            elif ext == ".bin" and is_psx:
                bin_files.append(full)
            elif ext in rom_extensions:
                rom_files.append(full)

    # PSX: prefer .cue so caller can resolve data track
    if cue_files:
        return cue_files[0], temp_dir

    # PSX without .cue: use track-number heuristics
    if bin_files:
        return _find_psx_data_track(bin_files), temp_dir

    if rom_files:
        return rom_files[0], temp_dir

    cleanup_temp_dir(temp_dir)
    raise ValueError("No ROM file found inside ZIP")


def create_output_zip(output_files, output_zip_path):
    """Create a ZIP containing the given output files.

    Args:
        output_files: List of absolute file paths to include.
        output_zip_path: Path for the output ZIP file.
    """
    with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for fpath in output_files:
            zf.write(fpath, os.path.basename(fpath))


def cleanup_temp_dir(temp_dir):
    """Remove temp directory created by extract_rom_from_zip."""
    if temp_dir and os.path.isdir(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)
