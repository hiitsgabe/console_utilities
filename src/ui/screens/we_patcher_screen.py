"""WE Patcher screen — WE2002 Winning Eleven 2002 step-by-step patcher."""

import os
from datetime import datetime

import pygame

from ui.theme import Theme, default_theme
from ui.templates.list_screen import ListScreenTemplate
from ui.atoms.text import Text
from services.we_patcher.translations.we2002 import LANGUAGES, LANGUAGE_CODES


class WePatcherScreen:
    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.template = ListScreenTemplate(theme)
        self.text = Text(theme)
        # Set after each render — used for click/touch hit-testing
        self.season_arrow_left: pygame.Rect = None
        self.season_arrow_right: pygame.Rect = None
        self.lang_arrow_left: pygame.Rect = None
        self.lang_arrow_right: pygame.Rect = None

    def _get_items(self, state, settings):
        """
        Build the menu items as (label, value, action) tuples.

        Order: Season → Language → Select League → Preview Rosters → ROM → Map → Patch
        """
        we = state.we_patcher
        provider = (settings or {}).get("sports_roster_provider", "espn")
        api_key = (settings or {}).get("api_football_key", "")
        needs_key = provider == "api_football" and not api_key

        # ── Season ─────────────────────────────────────────────────────────
        # For API-Football: secondary is empty — we draw it manually with buttons.
        # For ESPN: show year as plain secondary text (read-only).
        if provider == "espn":
            season_value = str(datetime.now().year)
            season_action = "locked"
        else:
            season_value = ""  # drawn manually in render()
            season_action = "change_season"

        items = [("Season", season_value, season_action)]

        # ── Language ───────────────────────────────────────────────────────
        items.append(("Language", "", "change_language"))

        # ── Select League ───────────────────────────────────────────────────
        if needs_key:
            step1_value = "API key required"
        elif we.selected_league:
            step1_value = getattr(we.selected_league, "name", str(we.selected_league))
        else:
            step1_value = "Not selected"

        items.append((
            "1. Select League",
            step1_value,
            "needs_api_key" if needs_key else "select_league",
        ))

        # ── Preview Rosters ─────────────────────────────────────────────────
        if we.league_data:
            step2_value = "Tap to preview"
        elif we.is_fetching and we.selected_league:
            step2_value = "Loading roster data..."
        elif we.selected_league:
            step2_value = "Tap to preview"
        else:
            step2_value = "Complete step 1 first"

        items.append((
            "2. Preview Rosters",
            step2_value,
            "preview_rosters" if (we.league_data or we.selected_league) else "locked",
        ))

        # ── Select ROM ──────────────────────────────────────────────────────
        if we.rom_path and we.rom_valid:
            step3_value = os.path.basename(we.rom_path)
        elif we.rom_path:
            step3_value = "Invalid ROM"
        else:
            step3_value = "Not selected"

        items.append(("3. Select ROM", step3_value, "select_rom"))

        # ── Patch ROM ───────────────────────────────────────────────────────
        if we.patch_complete:
            step4_value = "Complete"
        elif we.league_data and we.rom_valid:
            step4_value = "Ready to patch"
        else:
            step4_value = "Complete steps 1+3 first"

        items.append((
            "4. Patch ROM",
            step4_value,
            "patch_rom" if (we.league_data and we.rom_valid) else "locked",
        ))

        return items

    def render(self, screen, highlighted, state, settings=None):
        items = self._get_items(state, settings)
        display_items = [(label, value) for label, value, _ in items]

        back_rect, item_rects, scroll_offset = self.template.render(
            screen,
            title="WE2002 Patcher",
            items=display_items,
            highlighted=highlighted,
            selected=set(),
            show_back=True,
            item_height=48,
            get_label=lambda x: x[0] if isinstance(x, tuple) else x,
            get_secondary=lambda x: x[1] if isinstance(x, tuple) else None,
            item_spacing=8,
        )

        # Draw the Season row control (arrow buttons + year) for API-Football
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
                    season = state.we_patcher.selected_season or datetime.now().year - 1
                    is_hl = highlighted == season_idx
                    self._draw_arrow_control(screen, row, str(season), is_hl, "season")

        # Draw the Language row control (arrow buttons + language name)
        self.lang_arrow_left = None
        self.lang_arrow_right = None
        lang_idx = next(
            (i for i, (_, _, a) in enumerate(items) if a == "change_language"), None
        )
        if lang_idx is not None:
            visible_idx = lang_idx - scroll_offset
            if 0 <= visible_idx < len(item_rects):
                row = item_rects[visible_idx]
                lang_code = (settings or {}).get("we_patcher_language", "en")
                lang_name = LANGUAGES.get(lang_code, "English")
                is_hl = highlighted == lang_idx
                self._draw_arrow_control(screen, row, lang_name, is_hl, "lang")

        return back_rect, item_rects, scroll_offset

    def _draw_arrow_control(self, screen, row: pygame.Rect, label: str, is_highlighted: bool, target: str):
        """Draw < value > control on the right side of a row."""
        btn_w, btn_h = 32, 30
        value_w = 100 if target == "lang" else 56
        margin = 10
        gap = 6

        # Layout (right to left): margin | right_btn | gap | value | gap | left_btn
        rx = row.right - margin
        right_btn = pygame.Rect(rx - btn_w, row.centery - btn_h // 2, btn_w, btn_h)
        value_cx = right_btn.left - gap - value_w // 2
        left_btn = pygame.Rect(value_cx - value_w // 2 - gap - btn_w, row.centery - btn_h // 2, btn_w, btn_h)

        arrow_color = self.theme.primary if is_highlighted else self.theme.text_secondary
        value_color = self.theme.primary if is_highlighted else self.theme.text_primary

        # Left arrow
        self.text.render(
            screen, "<",
            (left_btn.centerx, left_btn.centery - self.theme.font_size_sm // 2),
            color=arrow_color, size=self.theme.font_size_sm, align="center",
        )

        # Value text
        self.text.render(
            screen, label,
            (value_cx, row.centery - self.theme.font_size_md // 2),
            color=value_color, size=self.theme.font_size_md, align="center",
        )

        # Right arrow
        self.text.render(
            screen, ">",
            (right_btn.centerx, right_btn.centery - self.theme.font_size_sm // 2),
            color=arrow_color, size=self.theme.font_size_sm, align="center",
        )

        if target == "season":
            self.season_arrow_left = left_btn
            self.season_arrow_right = right_btn
        else:
            self.lang_arrow_left = left_btn
            self.lang_arrow_right = right_btn

    # Keep legacy name for backwards compatibility
    _draw_season_control = _draw_arrow_control

    def get_action(self, index: int, state, settings=None) -> str:
        items = self._get_items(state, settings)
        if 0 <= index < len(items):
            return items[index][2]
        return "unknown"

    def get_count(self, state=None, settings=None) -> int:
        if state is None:
            return 6  # Season + Language + 4 steps
        return len(self._get_items(state, settings))


we_patcher_screen = WePatcherScreen()
