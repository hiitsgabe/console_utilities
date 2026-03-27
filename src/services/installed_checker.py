"""
Installed games checker service for Console Utilities.
Handles lazy checking of whether games are already installed in the roms folder.
"""

import os
import re
from typing import Dict, Any, List, Set

from utils.logging import log_error


def _normalize_name(filename: str) -> str:
    """Normalize a filename for matching: strip extension, tags, whitespace, lowercase."""
    base = os.path.splitext(filename)[0]
    # Remove parenthetical and bracket tags like (USA), [!], (Rev 1)
    base = re.sub(r"\(.*?\)", "", base)
    base = re.sub(r"\[.*?\]", "", base)
    # Collapse whitespace and strip
    base = re.sub(r"\s+", " ", base).strip()
    return base.lower()


class InstalledChecker:
    """
    Checks if games are installed by comparing filenames with files in the roms folder.
    Uses O(1) set lookups with normalized names for fast matching on low-power devices.
    """

    def __init__(self):
        """Initialize the installed checker."""
        self._roms_folder: str = ""
        self._existing_exact: Set[str] = set()  # base filenames (no ext, lowered)
        self._existing_normalized: Set[str] = set()  # stripped of tags too
        self._cache: Dict[str, bool] = {}

    def set_roms_folder(self, roms_folder: str) -> None:
        """
        Set the current roms folder and load its file list.
        Clears cache when folder changes.
        """
        if roms_folder == self._roms_folder:
            return

        self._roms_folder = roms_folder
        self._cache.clear()
        self._existing_exact = set()
        self._existing_normalized = set()

        if not roms_folder:
            return

        try:
            if os.path.exists(roms_folder):
                for f in os.listdir(roms_folder):
                    base = os.path.splitext(f)[0].lower()
                    self._existing_exact.add(base)
                    self._existing_normalized.add(_normalize_name(f))
        except Exception as e:
            log_error(
                "Failed to list roms folder for install check",
                type(e).__name__,
                str(e),
            )

    def is_installed(self, game: Any) -> bool:
        """
        Check if a game is installed (lazy evaluation with caching).
        Uses fast O(1) set lookups instead of fuzzy matching.
        """
        if not self._existing_exact:
            return False

        # Get game filename
        if isinstance(game, dict):
            game_filename = game.get("filename", game.get("name", ""))
        else:
            game_filename = str(game)

        if not game_filename:
            return False

        # Check cache first
        if game_filename in self._cache:
            return self._cache[game_filename]

        # Try exact base name match (fast, covers most cases)
        game_base = os.path.splitext(game_filename)[0].lower()
        if game_base in self._existing_exact:
            self._cache[game_filename] = True
            return True

        # Try normalized match (strips region/version tags)
        game_norm = _normalize_name(game_filename)
        result = game_norm in self._existing_normalized
        self._cache[game_filename] = result
        return result

    def clear(self) -> None:
        """Clear the cache and reset state."""
        self._roms_folder = ""
        self._existing_exact = set()
        self._existing_normalized = set()
        self._cache.clear()

    def refresh(self) -> None:
        """Refresh the file list for the current roms folder."""
        if self._roms_folder:
            folder = self._roms_folder
            self._roms_folder = ""  # Force reload
            self.set_roms_folder(folder)


# Default instance
installed_checker = InstalledChecker()
