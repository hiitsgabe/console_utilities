"""NHL94 Genesis Patcher screen — NHL Hockey '94 (Genesis) roster update.

Mirrors the NHL94 SNES patcher UI pattern: step-by-step list with
(label, secondary_text) pairs and action-based dispatch.
"""

import os
import pygame
from datetime import datetime

from ui.theme import Theme, default_theme
from ui.templates.list_screen import ListScreenTemplate
from ui.atoms.text import Text


class NHL94GenesisPatcherScreen:
    """NHL94 Genesis roster patcher UI."""

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.template = ListScreenTemplate(theme)
        self.text = Text(theme)
        self.season_arrow_left: pygame.Rect = None
        self.season_arrow_right: pygame.Rect = None

    def _get_items(self, state, settings):
        """Build the menu items as (label, value, action) tuples.

        Order: Season -> Fetch Rosters -> Preview Rosters -> Select ROM -> Patch ROM
        """
        nhl = state.nhl94_gen_patcher
        provider = (settings or {}).get("nhl94_gen_provider", "espn")

        items = []

        # -- Season --
        if provider == "espn":
            now = datetime.now()
            start = now.year if now.month >= 10 else now.year - 1
            season_value = f"{start}-{start + 1}"
            season_action = "locked"
        else:
            season_value = ""  # Drawn by _draw_arrow_control
            season_action = "change_season"
        items.append(("Season", season_value, season_action))

        # -- 1. Fetch Rosters --
        if nhl.is_fetching:
            fetch_value = f"Fetching... {int(nhl.fetch_progress * 100)}%"
        elif nhl.rosters:
            team_count = len(nhl.rosters)
            fetch_value = f"{team_count} teams loaded"
        elif nhl.fetch_error:
            fetch_value = f"Error: {nhl.fetch_error}"
        else:
            fetch_value = "Not fetched"
        items.append(("1. Fetch Rosters", fetch_value, "fetch_rosters"))

        # -- 2. Preview Rosters --
        if nhl.league_data or nhl.rosters or nhl.is_fetching:
            preview_value = "Tap to preview"
            preview_action = "preview_rosters"
        else:
            preview_value = "Complete step 1 first"
            preview_action = "locked"
        items.append(("2. Preview Rosters", preview_value, preview_action))

        # -- 3. Select ROM --
        if nhl.rom_path and nhl.rom_valid:
            rom_value = os.path.basename(nhl.rom_path)
        elif nhl.rom_path:
            rom_value = "Invalid ROM"
        else:
            rom_value = "Not selected"
        items.append(("3. Select ROM (.bin)", rom_value, "select_rom"))

        # -- 4. Patch ROM --
        if nhl.patch_complete:
            patch_value = "Complete"
        elif nhl.rosters and nhl.rom_valid:
            patch_value = "Ready to patch"
        else:
            patch_value = "Complete steps 1+3 first"
        items.append((
            "4. Patch ROM",
            patch_value,
            "patch_rom" if (nhl.rosters and nhl.rom_valid) else "locked",
        ))

        return items

    def render(self, screen, highlighted, state, settings=None):
        items = self._get_items(state, settings)
        display_items = [(label, value) for label, value, _ in items]

        back_rect, item_rects, scroll_offset = self.template.render(
            screen,
            title="NHL 94 (Genesis) Patcher",
            items=display_items,
            highlighted=highlighted,
            selected=set(),
            show_back=True,
            item_height=48,
            get_label=lambda x: x[0] if isinstance(x, tuple) else x,
            get_secondary=lambda x: (
                x[1] if isinstance(x, tuple) else None
            ),
            item_spacing=8,
        )

        # Draw the Season row arrow control for NHL API provider
        self.season_arrow_left = None
        self.season_arrow_right = None

        provider = (settings or {}).get("nhl94_gen_provider", "espn")
        if provider == "nhl":
            season_idx = next(
                (i for i, (_, _, a) in enumerate(items)
                 if a == "change_season"), None
            )
            if season_idx is not None:
                visible_idx = season_idx - scroll_offset
                if 0 <= visible_idx < len(item_rects):
                    row = item_rects[visible_idx]
                    season = state.nhl94_gen_patcher.selected_season
                    is_hl = highlighted == season_idx
                    self._draw_arrow_control(
                        screen, row, str(season), is_hl
                    )

        return back_rect, item_rects, scroll_offset

    def _draw_arrow_control(
        self, screen, row: pygame.Rect, label: str, is_highlighted: bool
    ):
        """Draw < value > control on the right side of a row."""
        btn_w, btn_h = 32, 30
        value_w = 56
        margin = 10
        gap = 6

        rx = row.right - margin
        right_btn = pygame.Rect(
            rx - btn_w, row.centery - btn_h // 2, btn_w, btn_h
        )
        value_cx = right_btn.left - gap - value_w // 2
        left_btn = pygame.Rect(
            value_cx - value_w // 2 - gap - btn_w,
            row.centery - btn_h // 2, btn_w, btn_h,
        )

        arrow_color = (
            self.theme.primary if is_highlighted
            else self.theme.text_secondary
        )
        value_color = (
            self.theme.primary if is_highlighted
            else self.theme.text_primary
        )

        self.text.render(
            screen, "<",
            (left_btn.centerx,
             left_btn.centery - self.theme.font_size_sm // 2),
            color=arrow_color, size=self.theme.font_size_sm, align="center",
        )
        self.text.render(
            screen, label,
            (value_cx, row.centery - self.theme.font_size_md // 2),
            color=value_color, size=self.theme.font_size_md, align="center",
        )
        self.text.render(
            screen, ">",
            (right_btn.centerx,
             right_btn.centery - self.theme.font_size_sm // 2),
            color=arrow_color, size=self.theme.font_size_sm, align="center",
        )

        self.season_arrow_left = left_btn
        self.season_arrow_right = right_btn

    def get_action(self, index: int, state, settings=None) -> str:
        items = self._get_items(state, settings)
        if 0 <= index < len(items):
            return items[index][2]
        return "unknown"

    def get_count(self, state=None, settings=None) -> int:
        if state is None:
            return 5
        return len(self._get_items(state, settings))


nhl94_genesis_patcher_screen = NHL94GenesisPatcherScreen()
