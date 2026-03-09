"""MVP Baseball PSP Patcher screen — roster update for PSP ISO.

Step-by-step list: Fetch Rosters -> Preview -> Select ISO -> Patch.
"""

import os
import pygame

from ui.theme import Theme, default_theme
from ui.templates.list_screen import ListScreenTemplate
from ui.atoms.text import Text


class MVPPSPPatcherScreen:
    """MVP Baseball PSP roster patcher UI."""

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.template = ListScreenTemplate(theme)
        self.text = Text(theme)

    def _get_items(self, state, settings):
        """Build the menu items as (label, value, action) tuples."""
        mvp = state.mvp_psp_patcher

        items = []

        # -- Season (display only) --
        season = mvp.selected_season
        items.append(("Season", str(season), "locked"))

        # -- 1. Fetch Rosters --
        if mvp.is_fetching:
            fetch_value = f"Fetching... {int(mvp.fetch_progress * 100)}%"
        elif mvp.rosters:
            team_count = len(mvp.rosters)
            fetch_value = f"{team_count} teams loaded"
        elif mvp.fetch_error:
            fetch_value = f"Error: {mvp.fetch_error}"
        else:
            fetch_value = "Not fetched"
        items.append(("1. Fetch Rosters", fetch_value, "fetch_rosters"))

        # -- 2. Preview Rosters --
        if mvp.league_data or mvp.rosters or mvp.is_fetching:
            preview_value = "Tap to preview"
            preview_action = "preview_rosters"
        else:
            preview_value = "Complete step 1 first"
            preview_action = "locked"
        items.append(("2. Preview Rosters", preview_value, preview_action))

        # -- 3. Select ISO --
        if mvp.rom_path and mvp.rom_valid:
            rom_value = os.path.basename(mvp.zip_path or mvp.rom_path)
        elif mvp.rom_path:
            rom_value = "Invalid ISO"
        else:
            rom_value = "Not selected"
        items.append(("3. Select ISO (.iso/.zip)", rom_value, "select_rom"))

        # -- 4. Patch ISO --
        if mvp.patch_complete:
            patch_value = "Complete"
        elif mvp.rosters and mvp.rom_valid:
            patch_value = "Ready to patch"
        else:
            patch_value = "Complete steps 1+3 first"
        items.append(
            (
                "4. Patch ISO",
                patch_value,
                "patch_rom" if (mvp.rosters and mvp.rom_valid) else "locked",
            )
        )

        return items

    def render(self, screen, highlighted, state, settings=None):
        items = self._get_items(state, settings)
        display_items = [(label, value) for label, value, _ in items]

        back_rect, item_rects, scroll_offset = self.template.render(
            screen,
            title="MVP Baseball (PSP) Patcher",
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


mvp_psp_patcher_screen = MVPPSPPatcherScreen()
