"""
Installed games checker service for Console Utilities.
Handles lazy checking of whether games are already installed in the roms folder.
"""

import os
from difflib import SequenceMatcher
from typing import Dict, Any, List, Optional

from utils.logging import log_error


class InstalledChecker:
    """
    Checks if games are installed by comparing filenames with files in the roms folder.
    Uses lazy evaluation and caching to avoid performance issues with large lists.
    """

    def __init__(self):
        """Initialize the installed checker."""
        self._roms_folder: str = ""
        self._existing_files: List[str] = []
        self._cache: Dict[str, bool] = {}
        self._match_threshold: float = 0.9

    def set_roms_folder(self, roms_folder: str) -> None:
        """
        Set the current roms folder and load its file list.
        Clears cache when folder changes.

        Args:
            roms_folder: Path to the ROMs folder
        """
        if roms_folder == self._roms_folder:
            return

        self._roms_folder = roms_folder
        self._cache.clear()
        self._existing_files = []

        if not roms_folder:
            return

        try:
            if os.path.exists(roms_folder):
                files = os.listdir(roms_folder)
                # Store base filenames (without extension) for comparison
                self._existing_files = [self._get_base_filename(f) for f in files]
        except Exception as e:
            log_error(
                "Failed to list roms folder for install check",
                type(e).__name__,
                str(e),
            )

    def is_installed(self, game: Any) -> bool:
        """
        Check if a game is installed (lazy evaluation with caching).

        Args:
            game: Game item (string or dictionary)

        Returns:
            True if the game is installed, False otherwise
        """
        if not self._existing_files:
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

        # Compute installed status
        game_basename = self._get_base_filename(game_filename)
        is_installed = any(
            self._fuzzy_match(game_basename, existing)
            for existing in self._existing_files
        )

        # Cache the result
        self._cache[game_filename] = is_installed
        return is_installed

    def clear(self) -> None:
        """Clear the cache and reset state."""
        self._roms_folder = ""
        self._existing_files = []
        self._cache.clear()

    def refresh(self) -> None:
        """Refresh the file list for the current roms folder."""
        if self._roms_folder:
            folder = self._roms_folder
            self._roms_folder = ""  # Force reload
            self.set_roms_folder(folder)

    def _get_base_filename(self, filename: str) -> str:
        """Extract base filename without extension, lowercased."""
        base = os.path.splitext(filename)[0]
        return base.lower()

    def _fuzzy_match(self, name1: str, name2: str) -> bool:
        """Check if two filenames match with at least 90% similarity."""
        ratio = SequenceMatcher(None, name1, name2).ratio()
        return ratio >= self._match_threshold


# Default instance
installed_checker = InstalledChecker()
