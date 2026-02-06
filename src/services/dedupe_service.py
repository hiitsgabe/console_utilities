"""
Dedupe service - Handles game deduplication logic.
"""

import os
import re
from typing import List, Dict, Any, Tuple, Callable, Optional
from difflib import SequenceMatcher

# Common patterns to remove for normalization (from Myrient/Redump naming conventions)
REGION_PATTERNS = [
    r"\(USA\)",
    r"\(Europe\)",
    r"\(Japan\)",
    r"\(France\)",
    r"\(Germany\)",
    r"\(Spain\)",
    r"\(Italy\)",
    r"\(UK\)",
    r"\(Australia\)",
    r"\(Canada\)",
    r"\(Korea\)",
    r"\(Netherlands\)",
    r"\(Sweden\)",
    r"\(Portugal\)",
    r"\(Brazil\)",
    r"\(Asia\)",
    r"\(World\)",
    r"\(En,.*?\)",  # Language combinations like (En,Fr,De)
    r"\(Ja,.*?\)",
]

RELEASE_TYPE_PATTERNS = [
    r"\(Demo\)",
    r"\(Beta\)",
    r"\(Proto\)",
    r"\(Prototype\)",
    r"\(Trade Demo\)",
    r"\(Unl\)",
    r"\(Sample\)",
    r"\(Promo\)",
    r"\(Preview\)",
    r"\(Kiosk\)",
    r"\(Kiosk Demo\)",
]

DISC_PATTERNS = [
    r"\(Disc\s*\d+\)",
    r"\(Disc\s*\d+\s*of\s*\d+\)",
    r"\(CD\s*\d+\)",
    r"\(DVD\s*\d+\)",
]

VERSION_PATTERNS = [
    r"\(Rev\s*\d+\)",
    r"\(Revision\s*\d+\)",
    r"\(v\d+\.?\d*\)",
    r"\(V\d+\.?\d*\)",
    r"\(Version\s*\d+\.?\d*\)",
]

EDITION_PATTERNS = [
    r"\(Rerelease\)",
    r"\(PlayStation the Best\)",
    r"\(PSone Books\)",
    r"\(Special Pack\)",
    r"\(Premium Box\)",
    r"\(Gentei Set\)",
    r"\(Fukkokuban\)",
    r"\(Shokai Genteiban\)",
    r"\(Artdink Best Choice\)",
    r"\(Major Wave\)",
    r"\(Platinum\)",
    r"\(Greatest Hits\)",
    r"\(Budget\)",
    r"\(Classic\)",
    r"\(Classics\)",
    r"\(Essentials\)",
    r"\(Hits\)",
    r"\(Collection\)",
    r"\(Midway Classics\)",
]

OTHER_PATTERNS = [
    r"\(EDC\)",  # Error correction variant
    r"\(\d{4}-\d{2}-\d{2}\)",  # Date patterns like (1996-11-21)
    r"\[.*?\]",  # Remove anything in brackets
]

# Compile all patterns
ALL_PATTERNS = (
    REGION_PATTERNS
    + RELEASE_TYPE_PATTERNS
    + DISC_PATTERNS
    + VERSION_PATTERNS
    + EDITION_PATTERNS
    + OTHER_PATTERNS
)

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in ALL_PATTERNS]


def normalize_game_name(filename: str) -> str:
    """
    Normalize a game filename for comparison.

    Removes common patterns like regions, versions, disc numbers, etc.
    Converts to lowercase and removes special characters.

    Args:
        filename: The original filename

    Returns:
        Normalized name for comparison
    """
    # Remove file extension
    name = os.path.splitext(filename)[0]

    # Apply all pattern removals
    for pattern in COMPILED_PATTERNS:
        name = pattern.sub("", name)

    # Convert to lowercase
    name = name.lower()

    # Remove special characters (keep only alphanumeric and spaces)
    name = re.sub(r"[^a-z0-9\s]", "", name)

    # Normalize whitespace
    name = " ".join(name.split())

    return name.strip()


def get_similarity_ratio(name1: str, name2: str) -> float:
    """
    Get similarity ratio between two strings.

    Args:
        name1: First name
        name2: Second name

    Returns:
        Similarity ratio between 0.0 and 1.0
    """
    return SequenceMatcher(None, name1, name2).ratio()


def scan_folder_for_games(
    folder_path: str, progress_callback: Optional[Callable[[int, int], None]] = None
) -> List[Dict[str, Any]]:
    """
    Scan a folder for game files.

    Args:
        folder_path: Path to scan
        progress_callback: Optional callback(current, total) for progress updates

    Returns:
        List of game file dictionaries with path, name, size, normalized_name
    """
    # Common game file extensions
    game_extensions = {
        ".zip",
        ".7z",
        ".rar",
        ".iso",
        ".bin",
        ".cue",
        ".chd",
        ".nsp",
        ".nsz",
        ".xci",
        ".cia",
        ".3ds",
        ".nds",
        ".gba",
        ".gbc",
        ".gb",
        ".nes",
        ".sfc",
        ".smc",
        ".md",
        ".gen",
        ".smd",
        ".gg",
        ".sms",
        ".pce",
        ".n64",
        ".z64",
        ".v64",
        ".gcm",
        ".wbfs",
        ".wad",
        ".pbp",
        ".cso",
        ".pkg",
    }

    games = []

    try:
        all_files = os.listdir(folder_path)
        total = len(all_files)

        for i, filename in enumerate(all_files):
            if progress_callback:
                progress_callback(i + 1, total)

            filepath = os.path.join(folder_path, filename)

            # Skip directories
            if os.path.isdir(filepath):
                continue

            # Check extension
            ext = os.path.splitext(filename)[1].lower()
            if ext not in game_extensions:
                continue

            try:
                size = os.path.getsize(filepath)
            except OSError:
                size = 0

            games.append(
                {
                    "path": filepath,
                    "name": filename,
                    "size": size,
                    "normalized_name": normalize_game_name(filename),
                }
            )

    except OSError:
        pass

    return games


def find_duplicates_safe(
    games: List[Dict[str, Any]],
) -> List[List[Dict[str, Any]]]:
    """
    Find duplicates using safe mode (exact normalized name match).

    Automatically selects the larger file to keep.

    Args:
        games: List of game dictionaries from scan_folder_for_games

    Returns:
        List of duplicate groups, each sorted by size descending (first = keep)
    """
    # Group by normalized name
    name_groups: Dict[str, List[Dict[str, Any]]] = {}

    for game in games:
        norm_name = game["normalized_name"]
        if norm_name not in name_groups:
            name_groups[norm_name] = []
        name_groups[norm_name].append(game)

    # Filter to only groups with duplicates, sort each by size (largest first)
    duplicates = []
    for norm_name, group in name_groups.items():
        if len(group) > 1:
            # Sort by size descending (keep largest)
            sorted_group = sorted(group, key=lambda x: x["size"], reverse=True)
            duplicates.append(sorted_group)

    return duplicates


def find_duplicates_manual(
    games: List[Dict[str, Any]], threshold: float = 0.9
) -> List[List[Dict[str, Any]]]:
    """
    Find duplicates using manual mode (fuzzy matching).

    Uses 90% similarity threshold by default.

    Args:
        games: List of game dictionaries from scan_folder_for_games
        threshold: Similarity threshold (0.0 to 1.0)

    Returns:
        List of duplicate groups (user must confirm which to keep)
    """
    # Track which games are already in a group
    grouped = set()
    duplicates = []

    for i, game1 in enumerate(games):
        if i in grouped:
            continue

        group = [game1]
        grouped.add(i)

        for j, game2 in enumerate(games[i + 1 :], start=i + 1):
            if j in grouped:
                continue

            similarity = get_similarity_ratio(
                game1["normalized_name"], game2["normalized_name"]
            )

            if similarity >= threshold:
                group.append(game2)
                grouped.add(j)

        if len(group) > 1:
            # Sort by size descending as a suggestion
            sorted_group = sorted(group, key=lambda x: x["size"], reverse=True)
            duplicates.append(sorted_group)

    return duplicates


def delete_files(
    files_to_delete: List[str],
    progress_callback: Optional[Callable[[int, int, int], None]] = None,
) -> Tuple[int, int]:
    """
    Delete the specified files.

    Args:
        files_to_delete: List of file paths to delete
        progress_callback: Optional callback(current, total, bytes_freed) for progress

    Returns:
        Tuple of (files_deleted, bytes_freed)
    """
    files_deleted = 0
    bytes_freed = 0

    for i, filepath in enumerate(files_to_delete):
        try:
            size = os.path.getsize(filepath)
            os.remove(filepath)
            files_deleted += 1
            bytes_freed += size
        except OSError:
            pass

        if progress_callback:
            progress_callback(i + 1, len(files_to_delete), bytes_freed)

    return files_deleted, bytes_freed


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
