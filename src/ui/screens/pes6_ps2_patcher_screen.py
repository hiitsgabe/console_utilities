"""PES 6 PS2 Patcher screen — Pro Evolution Soccer 6 (PS2) team name update.

Mirrors the NHL 05 PS2 patcher UI pattern: step-by-step list with
(label, secondary_text) pairs and action-based dispatch.
"""

import os
import pygame

from ui.theme import Theme, default_theme
from ui.templates.list_screen import ListScreenTemplate
from ui.atoms.text import Text


class PES6PS2PatcherScreen:
    """PES 6 PS2 team name patcher UI."""

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.template = ListScreenTemplate(theme)
        self.text = Text(theme)

    def _get_items(self, state, settings):
        """Build the menu items as (label, value, action) tuples.

        Order: Select League -> Fetch Rosters -> Preview Rosters -> Select ISO -> Patch ROM
        """
        pes = state.pes6_ps2_patcher

        items = []

        # -- 1. Select League --
        if pes.selected_league:
            league_name = (
                pes.selected_league.name
                if hasattr(pes.selected_league, "name")
                else str(pes.selected_league)
            )
            league_value = league_name
        else:
            league_value = "Not selected"
        items.append(("1. Select League", league_value, "select_league"))

        # -- 2. Fetch Rosters --
        if pes.is_fetching:
            fetch_value = f"Fetching... {int(pes.fetch_progress * 100)}%"
            fetch_action = "locked"
        elif pes.league_data:
            team_count = (
                len(pes.league_data.teams)
                if hasattr(pes.league_data, "teams")
                else 0
            )
            fetch_value = f"{team_count} teams loaded"
            fetch_action = "fetch_rosters"
        elif pes.fetch_error:
            fetch_value = f"Error: {pes.fetch_error}"
            fetch_action = "fetch_rosters" if pes.selected_league else "locked"
        elif pes.selected_league:
            fetch_value = "Not fetched"
            fetch_action = "fetch_rosters"
        else:
            fetch_value = "Select a league first"
            fetch_action = "locked"
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
        items.append(("4. Select ISO (.iso/.zip)", rom_value, "select_rom"))

        # -- 5. Patch ROM --
        if pes.patch_complete:
            patch_value = "Complete"
        elif pes.league_data and pes.rom_valid:
            patch_value = "Ready to patch"
        else:
            patch_value = "Complete steps 2+4 first"
        items.append(
            (
                "5. Patch ROM",
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
            title="PES 6 (PS2) Patcher",
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


pes6_ps2_patcher_screen = PES6PS2PatcherScreen()
