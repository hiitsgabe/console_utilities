"""PES6 PS2 Patcher screen — PES6/WE10 roster update via ESPN.

Step-by-step list: Season, Select League, Fetch Rosters, Preview, Select ISO, Patch.
"""

import os
import pygame
from datetime import datetime

from ui.theme import Theme, default_theme
from ui.templates.list_screen import ListScreenTemplate
from ui.atoms.text import Text
from services.rom_finder import RomFinderConfig

ROM_FINDER_CONFIG = RomFinderConfig(
    search_terms=["Pro Evolution Soccer 6", "PES6"],
    system_folders=["ps2"],
    file_extensions=[".iso", ".zip"],
    system_type="ps2",
    preferred_region="Europe",
)


class PES6PS2PatcherScreen:
    """PES6 PS2 roster patcher UI."""

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.template = ListScreenTemplate(theme)
        self.text = Text(theme)

    def _get_items(self, state, settings):
        pes = state.pes6_ps2_patcher

        items = []

        # -- Season --
        season_value = str(pes.selected_season)
        items.append(("Season", season_value, "locked"))

        # -- 1. Select League --
        if pes.selected_league:
            league_value = pes.selected_league.name
        else:
            league_value = "Not selected"
        items.append(("1. Select League", league_value, "select_league"))

        # -- 2. Fetch Rosters --
        if pes.is_fetching:
            fetch_value = f"Fetching... {int(pes.fetch_progress * 100)}%"
        elif pes.league_data:
            team_count = len(pes.league_data.teams)
            fetch_value = f"{team_count} teams loaded"
        elif pes.fetch_error:
            fetch_value = f"Error: {pes.fetch_error[:30]}"
        else:
            fetch_value = (
                "Select league first" if not pes.selected_league else "Not fetched"
            )
        fetch_action = "fetch_rosters" if pes.selected_league else "locked"
        items.append(("2. Fetch Rosters", fetch_value, fetch_action))

        # -- 3. Preview Rosters --
        if pes.league_data or pes.is_fetching:
            preview_value = "Tap to preview"
            preview_action = "preview_rosters"
        else:
            preview_value = "Complete step 2 first"
            preview_action = "locked"
        items.append(("3. Preview Rosters", preview_value, preview_action))

        # -- 4. Select ISO --
        if pes.rom_path and pes.rom_valid:
            rom_value = os.path.basename(pes.zip_path or pes.rom_path)
        elif pes.rom_path:
            rom_value = "Invalid ISO"
        else:
            rom_value = "Not selected"
        if pes.rom_select_mode == "auto":
            if pes.auto_detect_downloading:
                rom_value = "Downloading..."
            elif not pes.rom_path:
                rom_value = "Press A to search"
            items.append(
                ("4. Auto-detect ISO \u25c0\u25b6", rom_value, "auto_detect_rom")
            )
        else:
            items.append(("4. Select ISO (.iso/.zip)", rom_value, "select_rom"))

        # -- 5. Patch ISO --
        if pes.patch_complete:
            patch_value = "Complete"
        elif pes.league_data and pes.rom_valid:
            patch_value = "Ready to patch"
        else:
            patch_value = "Complete steps 2+4 first"
        items.append(
            (
                "5. Patch ISO",
                patch_value,
                "patch_rom" if (pes.league_data and pes.rom_valid) else "locked",
            )
        )

        return items

    def render(self, screen, highlighted, state, settings=None):
        items = self._get_items(state, settings)
        display_items = [(label, value) for label, value, _ in items]

        back_rect, item_rects, scroll_offset = self.template.render(
            screen,
            title="PES 6 PS2 Patcher",
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
            return 6
        return len(self._get_items(state, settings))


pes6_ps2_patcher_screen = PES6PS2PatcherScreen()
