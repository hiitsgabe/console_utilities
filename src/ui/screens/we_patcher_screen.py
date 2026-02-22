"""WE Patcher screen — WE2002 Winning Eleven 2002 step-by-step patcher."""

import os

from ui.theme import Theme, default_theme
from ui.templates.list_screen import ListScreenTemplate


class WePatcherScreen:
    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.template = ListScreenTemplate(theme)

    def _get_items(self, state, settings):
        """Build the 5-step menu items with status values."""
        we = state.we_patcher
        api_key = (settings or {}).get("api_football_key", "")

        # Step 1: Select League
        if not api_key:
            step1_value = "API key required"
        elif we.selected_league:
            league_name = (
                we.selected_league.name
                if hasattr(we.selected_league, "name")
                else str(we.selected_league)
            )
            step1_value = f"{league_name} {we.selected_season}"
        else:
            step1_value = "Not selected"

        # Step 2: Preview Rosters (requires step 1)
        step2_value = "Tap to preview" if we.league_data else "Complete step 1 first"

        # Step 3: Select ROM (always available)
        if we.rom_path and we.rom_valid:
            step3_value = os.path.basename(we.rom_path)
        elif we.rom_path:
            step3_value = "Invalid ROM"
        else:
            step3_value = "Not selected"

        # Step 4: Map Team Slots (requires steps 1+3)
        if we.slot_mapping:
            step4_value = f"{len(we.slot_mapping)} teams mapped"
        elif we.league_data and we.rom_valid:
            step4_value = "Tap to map"
        else:
            step4_value = "Complete steps 1+3 first"

        # Step 5: Patch ROM (requires steps 1+3+4)
        if we.patch_complete:
            step5_value = "Complete"
        elif we.league_data and we.rom_valid and we.slot_mapping:
            step5_value = "Ready to patch"
        else:
            step5_value = "Complete steps 1+3+4 first"

        return [
            ("1. Select League", step1_value),
            ("2. Preview Rosters", step2_value),
            ("3. Select ROM", step3_value),
            ("4. Map Team Slots", step4_value),
            ("5. Patch ROM", step5_value),
        ]

    def render(self, screen, highlighted, state, settings=None):
        items = self._get_items(state, settings)
        return self.template.render(
            screen,
            title="WE2002 Patcher",
            items=items,
            highlighted=highlighted,
            selected=set(),
            show_back=True,
            item_height=48,
            get_label=lambda x: x[0] if isinstance(x, tuple) else x,
            get_secondary=lambda x: x[1] if isinstance(x, tuple) else None,
            item_spacing=8,
        )

    def get_action(self, index: int, state, settings=None) -> str:
        we = state.we_patcher
        api_key = (settings or {}).get("api_football_key", "")
        actions = {
            0: "select_league" if api_key else "needs_api_key",
            1: "preview_rosters" if we.league_data else "locked",
            2: "select_rom",
            3: "map_slots" if (we.league_data and we.rom_valid) else "locked",
            4: (
                "patch_rom"
                if (we.league_data and we.rom_valid and we.slot_mapping)
                else "locked"
            ),
        }
        return actions.get(index, "unknown")

    def get_count(self) -> int:
        return 5


we_patcher_screen = WePatcherScreen()
