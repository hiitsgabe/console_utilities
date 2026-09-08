"""ISS Patcher screen — International Superstar Soccer (SNES) step-by-step patcher."""

import os
from datetime import datetime

from ui.theme import Theme, default_theme
from ui.templates.list_screen import ListScreenTemplate
from ui.atoms.text import Text
from services.rom_finder import RomFinderConfig

ROM_FINDER_CONFIG = RomFinderConfig(
    search_terms=["International Superstar Soccer"],
    system_folders=["snes", "supernintendo", "superfamicom", "sfc"],
    file_extensions=[".sfc", ".smc", ".zip"],
    system_type="snes",
)


class ISSPatcherScreen:
    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.template = ListScreenTemplate(theme)
        self.text = Text(theme)

    def _get_items(self, state, settings):
        """Build the menu items as (label, value, action) tuples.

        Order: Season → Select League → Preview Rosters → ROM → Patch
        """
        iss = state.iss_patcher

        # ── Season ────────────────────────────────────────────────────────
        # ESPN only serves the current season, so the row is read-only.
        items = [("Season", str(datetime.now().year), "locked")]

        # ── Select League ─────────────────────────────────────────────────
        if iss.selected_league:
            step1_value = getattr(iss.selected_league, "name", str(iss.selected_league))
        else:
            step1_value = "Not selected"

        items.append(("1. Select League", step1_value, "select_league"))

        # ── Preview Rosters ───────────────────────────────────────────────
        if iss.league_data:
            step2_value = "Tap to preview"
        elif iss.is_fetching and iss.selected_league:
            step2_value = "Loading roster data..."
        elif iss.selected_league:
            step2_value = "Tap to preview"
        else:
            step2_value = "Complete step 1 first"

        items.append(
            (
                "2. Preview Rosters",
                step2_value,
                (
                    "preview_rosters"
                    if (iss.league_data or iss.selected_league)
                    else "locked"
                ),
            )
        )

        # ── Set Team Colors ───────────────────────────────────────────────
        # ESPN supplies colours, so this is an override for the ones it omits.
        from services.team_color_cache import all_teams_have_colors

        if iss.league_data and all_teams_have_colors(iss.league_data):
            colors_value = "All colors set"
        elif iss.league_data:
            colors_value = "Some colors missing"
        else:
            colors_value = "Complete step 2 first"
        items.append(
            (
                "3. Set Team Colors",
                colors_value,
                "set_colors" if iss.league_data else "locked",
            )
        )

        # ── Select ROM ────────────────────────────────────────────────────
        step_rom = "4"
        if iss.rom_path and iss.rom_valid:
            rom_value = os.path.basename(iss.zip_path or iss.rom_path)
        elif iss.rom_path:
            rom_value = "Invalid ROM"
        else:
            rom_value = "Not selected"
        if iss.rom_select_mode == "auto":
            if iss.auto_detect_downloading:
                rom_value = "Downloading..."
            elif iss.auto_detect_status == "not_found":
                rom_value = "ROM not found"
            elif not iss.rom_path:
                rom_value = "Press A to search"
            items.append(
                (
                    f"{step_rom}. Auto-detect ROM \u25c0\u25b6",
                    rom_value,
                    "auto_detect_rom",
                )
            )
        else:
            items.append(
                (f"{step_rom}. Select ROM (.sfc/.zip)", rom_value, "select_rom")
            )

        # ── Patch ROM ─────────────────────────────────────────────────────
        # Colours are not a gate: a team the picker never reached is patched
        # with whatever ESPN supplied.
        can_patch = bool(iss.league_data and iss.rom_valid)
        if iss.patch_complete:
            patch_value = "Complete"
        elif can_patch:
            patch_value = "Ready to patch"
        else:
            patch_value = f"Complete steps 1+{step_rom} first"

        items.append(
            (
                "5. Patch ROM",
                patch_value,
                "patch_rom" if can_patch else "locked",
            )
        )

        return items

    def render(self, screen, highlighted, state, settings=None):
        items = self._get_items(state, settings)
        display_items = [(label, value) for label, value, _ in items]

        back_rect, item_rects, scroll_offset = self.template.render(
            screen,
            title="ISS SNES Patcher",
            items=display_items,
            highlighted=highlighted,
            selected=set(),
            show_back=True,
            item_height=48,
            get_label=lambda x: x[0] if isinstance(x, tuple) else x,
            get_secondary=lambda x: x[1] if isinstance(x, tuple) else None,
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
            return 6  # Season + 5 steps
        return len(self._get_items(state, settings))


iss_patcher_screen = ISSPatcherScreen()
