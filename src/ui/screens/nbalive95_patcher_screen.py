"""NBA Live 95 Patcher screen — NBA Live 95 (Genesis) roster update.

Step-by-step list: Fetch Rosters -> Preview -> Select ROM -> Patch.
"""

import os
import pygame

from ui.theme import Theme, default_theme
from ui.templates.list_screen import ListScreenTemplate
from ui.atoms.text import Text
from services.rom_finder import RomFinderConfig

ROM_FINDER_CONFIG = RomFinderConfig(
    search_terms=["NBA Live 95"],
    system_folders=["genesis", "megadrive", "md", "segagenesis"],
    file_extensions=[".bin", ".md", ".gen", ".zip"],
    system_type="genesis",
)


class NBALive95PatcherScreen:
    """NBA Live 95 roster patcher UI."""

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.template = ListScreenTemplate(theme)
        self.text = Text(theme)

    def _get_items(self, state, settings):
        """Build the menu items as (label, value, action) tuples."""
        nba = state.nbalive95_patcher

        items = []

        # -- Season (display only, ESPN current data) --
        season = nba.selected_season
        items.append(("Season", f"{season}-{str(season + 1)[-2:]}", "locked"))

        # -- 1. Fetch Rosters --
        if nba.is_fetching:
            fetch_value = f"Fetching... {int(nba.fetch_progress * 100)}%"
        elif nba.rosters:
            team_count = len(nba.rosters)
            fetch_value = f"{team_count} teams loaded"
        elif nba.fetch_error:
            fetch_value = f"Error: {nba.fetch_error}"
        else:
            fetch_value = "Not fetched"
        items.append(("1. Fetch Rosters", fetch_value, "fetch_rosters"))

        # -- 2. Preview Rosters --
        if nba.league_data or nba.rosters or nba.is_fetching:
            preview_value = "Tap to preview"
            preview_action = "preview_rosters"
        else:
            preview_value = "Complete step 1 first"
            preview_action = "locked"
        items.append(("2. Preview Rosters", preview_value, preview_action))

        # -- 3. Select ROM --
        if nba.rom_path and nba.rom_valid:
            rom_value = os.path.basename(nba.zip_path or nba.rom_path)
        elif nba.rom_path:
            rom_value = "Invalid ROM"
        else:
            rom_value = "Not selected"
        if nba.rom_select_mode == "auto":
            if nba.auto_detect_downloading:
                rom_value = "Downloading..."
            elif nba.auto_detect_status == "not_found":
                rom_value = "ROM not found"
            elif not nba.rom_path:
                rom_value = "Press A to search"
            items.append(("3. Auto-detect ROM \u25c0\u25b6", rom_value, "auto_detect_rom"))
        else:
            items.append(("3. Select ROM (.md/.zip)", rom_value, "select_rom"))

        # -- 4. Patch ROM --
        if nba.patch_complete:
            patch_value = "Complete"
        elif nba.rosters and nba.rom_valid:
            patch_value = "Ready to patch"
        else:
            patch_value = "Complete steps 1+3 first"
        items.append(
            (
                "4. Patch ROM",
                patch_value,
                "patch_rom" if (nba.rosters and nba.rom_valid) else "locked",
            )
        )

        return items

    def render(self, screen, highlighted, state, settings=None):
        items = self._get_items(state, settings)
        display_items = [(label, value) for label, value, _ in items]

        back_rect, item_rects, scroll_offset = self.template.render(
            screen,
            title="NBA Live 95 (Genesis) Patcher",
            items=display_items,
            highlighted=highlighted,
            selected=set(),
            show_back=True,
            item_height=48,
            get_label=lambda x: x[0] if isinstance(x, tuple) else x,
            get_secondary=lambda x: (x[1] if isinstance(x, tuple) else None),
            item_spacing=8,
        )

        return back_rect, item_rects, scroll_offset

    def get_action(self, index: int, state, settings=None) -> str:
        items = self._get_items(state, settings)
        if 0 <= index < len(items):
            return items[index][2]
        return "unknown"

    def get_count(self, state=None, settings=None) -> int:
        if state is None:
            return 5
        return len(self._get_items(state, settings))


nbalive95_patcher_screen = NBALive95PatcherScreen()
