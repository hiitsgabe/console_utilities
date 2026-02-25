"""ISS Patcher screen — International Superstar Soccer (SNES) step-by-step patcher."""

import os
from datetime import datetime

import pygame

from ui.theme import Theme, default_theme
from ui.templates.list_screen import ListScreenTemplate
from ui.atoms.text import Text


class ISSPatcherScreen:
    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.template = ListScreenTemplate(theme)
        self.text = Text(theme)
        self.season_arrow_left: pygame.Rect = None
        self.season_arrow_right: pygame.Rect = None

    def _get_items(self, state, settings):
        """Build the menu items as (label, value, action) tuples.

        Order: Season → Select League → Preview Rosters → ROM → Patch
        """
        iss = state.iss_patcher
        provider = (settings or {}).get("sports_roster_provider", "espn")
        api_key = (settings or {}).get("api_football_key", "")
        needs_key = provider == "api_football" and not api_key

        # ── Season ────────────────────────────────────────────────────────
        if provider == "espn":
            season_value = str(datetime.now().year)
            season_action = "locked"
        else:
            season_value = ""
            season_action = "change_season"

        items = [("Season", season_value, season_action)]

        # ── Select League ─────────────────────────────────────────────────
        if needs_key:
            step1_value = "API key required"
        elif iss.selected_league:
            step1_value = getattr(iss.selected_league, "name", str(iss.selected_league))
        else:
            step1_value = "Not selected"

        items.append((
            "1. Select League",
            step1_value,
            "needs_api_key" if needs_key else "select_league",
        ))

        # ── Preview Rosters ───────────────────────────────────────────────
        if iss.league_data:
            step2_value = "Tap to preview"
        elif iss.is_fetching and iss.selected_league:
            step2_value = "Loading roster data..."
        elif iss.selected_league:
            step2_value = "Tap to preview"
        else:
            step2_value = "Complete step 1 first"

        items.append((
            "2. Preview Rosters",
            step2_value,
            "preview_rosters" if (iss.league_data or iss.selected_league) else "locked",
        ))

        # ── Set Team Colors (API-Football only) ──────────────────────────
        if provider == "api_football":
            from services.team_color_cache import all_teams_have_colors
            if iss.league_data and all_teams_have_colors(iss.league_data):
                colors_value = "All colors set"
            elif iss.league_data:
                colors_value = "Colors required"
            else:
                colors_value = "Complete step 2 first"
            items.append((
                "3. Set Team Colors",
                colors_value,
                "set_colors" if iss.league_data else "locked",
            ))

        # ── Select ROM ────────────────────────────────────────────────────
        step_rom = "4" if provider == "api_football" else "3"
        if iss.rom_path and iss.rom_valid:
            rom_value = os.path.basename(iss.rom_path)
        elif iss.rom_path:
            rom_value = "Invalid ROM"
        else:
            rom_value = "Not selected"
        items.append((f"{step_rom}. Select ROM (.sfc)", rom_value, "select_rom"))

        # ── Patch ROM ─────────────────────────────────────────────────────
        step_patch = "5" if provider == "api_football" else "4"
        if provider == "api_football":
            from services.team_color_cache import all_teams_have_colors as _athc
            colors_ok = iss.league_data and _athc(iss.league_data)
        else:
            colors_ok = True

        if iss.patch_complete:
            patch_value = "Complete"
        elif iss.league_data and iss.rom_valid and colors_ok:
            patch_value = "Ready to patch"
        else:
            patch_value = f"Complete steps 1+{step_rom} first"

        items.append((
            f"{step_patch}. Patch ROM",
            patch_value,
            "patch_rom" if (iss.league_data and iss.rom_valid and colors_ok) else "locked",
        ))

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

        # Draw the Season row control for API-Football
        self.season_arrow_left = None
        self.season_arrow_right = None

        provider = (settings or {}).get("sports_roster_provider", "espn")
        if provider == "api_football":
            season_idx = next(
                (i for i, (_, _, a) in enumerate(items) if a == "change_season"), None
            )
            if season_idx is not None:
                visible_idx = season_idx - scroll_offset
                if 0 <= visible_idx < len(item_rects):
                    row = item_rects[visible_idx]
                    season = state.iss_patcher.selected_season or datetime.now().year - 1
                    is_hl = highlighted == season_idx
                    self._draw_arrow_control(screen, row, str(season), is_hl)

        return back_rect, item_rects, scroll_offset

    def _draw_arrow_control(self, screen, row: pygame.Rect, label: str, is_highlighted: bool):
        """Draw < value > control on the right side of a row."""
        btn_w, btn_h = 32, 30
        value_w = 56
        margin = 10
        gap = 6

        rx = row.right - margin
        right_btn = pygame.Rect(rx - btn_w, row.centery - btn_h // 2, btn_w, btn_h)
        value_cx = right_btn.left - gap - value_w // 2
        left_btn = pygame.Rect(value_cx - value_w // 2 - gap - btn_w, row.centery - btn_h // 2, btn_w, btn_h)

        arrow_color = self.theme.primary if is_highlighted else self.theme.text_secondary
        value_color = self.theme.primary if is_highlighted else self.theme.text_primary

        self.text.render(
            screen, "<",
            (left_btn.centerx, left_btn.centery - self.theme.font_size_sm // 2),
            color=arrow_color, size=self.theme.font_size_sm, align="center",
        )
        self.text.render(
            screen, label,
            (value_cx, row.centery - self.theme.font_size_md // 2),
            color=value_color, size=self.theme.font_size_md, align="center",
        )
        self.text.render(
            screen, ">",
            (right_btn.centerx, right_btn.centery - self.theme.font_size_sm // 2),
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
            return 5  # Season + 4 steps
        return len(self._get_items(state, settings))


iss_patcher_screen = ISSPatcherScreen()
