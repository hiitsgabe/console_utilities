"""PES 6 PS2 Patcher screen — Pro Evolution Soccer 6 (PS2) team name update.

Mirrors the WE2002 patcher UI pattern: Season row at top, then step-by-step
list with (label, secondary_text) pairs and action-based dispatch.
"""

import os
import pygame
from datetime import datetime

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

        Order: Season → Select League → Preview Rosters → Select ISO → Patch ROM
        """
        pes = state.pes6_ps2_patcher

        items = []

        # -- Season (read-only for ESPN) --
        season_value = str(datetime.now().year)
        items.append(("Season", season_value, "locked"))

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

        # -- 2. Preview Rosters --
        if pes.league_data:
            preview_value = "Tap to preview"
        elif pes.is_fetching and pes.selected_league:
            preview_value = "Loading roster data..."
        elif pes.selected_league:
            preview_value = "Tap to preview"
        else:
            preview_value = "Complete step 1 first"
        items.append((
            "2. Preview Rosters",
            preview_value,
            (
                "preview_rosters"
                if (pes.league_data or pes.selected_league)
                else "locked"
            ),
        ))

        # -- 3. Select ISO --
        if pes.rom_path and pes.rom_valid:
            rom_value = os.path.basename(pes.zip_path or pes.rom_path)
        elif pes.rom_path:
            rom_value = "Invalid ISO"
        else:
            rom_value = "Not selected"
        items.append(("3. Select ISO (.iso/.zip)", rom_value, "select_rom"))

        # -- 4. Patch ROM --
        if pes.patch_complete:
            patch_value = "Complete"
        elif pes.league_data and pes.rom_valid:
            patch_value = "Ready to patch"
        else:
            patch_value = "Complete steps 1+3 first"
        items.append((
            "4. Patch ROM",
            patch_value,
            "patch_rom" if (pes.league_data and pes.rom_valid) else "locked",
        ))

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
