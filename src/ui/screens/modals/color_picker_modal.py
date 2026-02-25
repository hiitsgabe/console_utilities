"""Color picker modal for assigning team colors (API-Football only)."""

import pygame
from typing import List, Tuple, Optional, Dict

from ui.theme import Theme, default_theme
from ui.organisms.modal_frame import ModalFrame
from ui.atoms.text import Text
from services.team_color_cache import COLOR_PALETTE, COLOR_PALETTE_RGB


class ColorPickerModal:
    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.modal_frame = ModalFrame(theme)
        self.text = Text(theme)

    def render(
        self,
        screen: pygame.Surface,
        state,
    ) -> Dict:
        """Render the color picker modal.

        Returns a dict with keys:
            modal_rect, content_rect, close_rect,
            team_rects     – list of (rect, team_index) for the left panel,
            primary_rects  – list of (rect, color_index) for primary swatches,
            secondary_rects – list of (rect, color_index) for secondary swatches.
        """
        patcher = state.active_patcher
        league_data = patcher.league_data
        cp = patcher.color_picker

        margin = 30
        width = screen.get_width() - margin * 2
        height = screen.get_height() - margin * 2
        modal_rect = pygame.Rect(margin, margin, width, height)

        _, content_rect, close_rect = self.modal_frame.render(
            screen, modal_rect, title="Set Team Colors", show_close=True
        )

        result = {
            "modal_rect": modal_rect,
            "content_rect": content_rect,
            "close_rect": close_rect,
            "team_rects": [],
            "primary_rects": [],
            "secondary_rects": [],
        }

        if not league_data or not hasattr(league_data, "teams"):
            self.text.render(
                screen, "No league data loaded",
                (content_rect.centerx, content_rect.centery),
                color=self.theme.text_disabled,
                size=self.theme.font_size_lg, align="center",
            )
            return result

        teams = league_data.teams
        team_idx = cp.team_index

        # Layout: left panel = team list, right panel = color palette
        divider_x = content_rect.left + content_rect.width // 2
        team_panel = pygame.Rect(
            content_rect.left, content_rect.top,
            divider_x - content_rect.left - 4, content_rect.height,
        )
        color_panel = pygame.Rect(
            divider_x + 4, content_rect.top,
            content_rect.right - divider_x - 4, content_rect.height,
        )

        # Divider line
        pygame.draw.line(
            screen, self.theme.primary,
            (divider_x, content_rect.top), (divider_x, content_rect.bottom), 1,
        )

        # ── Left panel: team list ──────────────────────────────────
        self.text.render(
            screen, "Teams",
            (team_panel.left, team_panel.top),
            color=self.theme.text_primary, size=self.theme.font_size_md,
        )

        item_height = 28
        list_top = team_panel.top + self.theme.font_size_md + self.theme.padding_sm
        visible = max(1, (team_panel.bottom - list_top) // (item_height + 1))
        scroll = max(0, team_idx - visible + 1)

        y = list_top
        for i, tr in enumerate(teams):
            if i < scroll:
                continue
            if y + item_height > team_panel.bottom:
                break

            rect = pygame.Rect(team_panel.left, y, team_panel.width, item_height)
            is_sel = i == team_idx

            if is_sel:
                pygame.draw.rect(
                    screen, self.theme.primary, rect,
                    border_radius=self.theme.radius_sm,
                )

            team = tr.team
            name = team.name if hasattr(team, "name") else str(tr)
            has_colors = bool(team.color and team.alternate_color)

            if is_sel:
                name_color = self.theme.background
            elif has_colors:
                name_color = self.theme.text_secondary
            else:
                name_color = self.theme.error

            # Color dots next to name
            dot_x = rect.right - 36
            if team.color:
                h = team.color.lstrip("#")
                if len(h) == 6:
                    rgb = (int(h[:2], 16), int(h[2:4], 16), int(h[4:6], 16))
                    pygame.draw.circle(screen, rgb, (dot_x, rect.centery), 5)
            if team.alternate_color:
                h = team.alternate_color.lstrip("#")
                if len(h) == 6:
                    rgb = (int(h[:2], 16), int(h[2:4], 16), int(h[4:6], 16))
                    pygame.draw.circle(screen, rgb, (dot_x + 14, rect.centery), 5)

            self.text.render(
                screen, name,
                (rect.left + 6, rect.centery - self.theme.font_size_sm // 2),
                color=name_color, size=self.theme.font_size_sm,
                max_width=rect.width - 50,
            )

            result["team_rects"].append((rect, i))
            y += item_height + 1

        # ── Right panel: color palette ─────────────────────────────
        if 0 <= team_idx < len(teams):
            team = teams[team_idx].team
            team_name = team.name if hasattr(team, "name") else "Team"

            self.text.render(
                screen, team_name,
                (color_panel.left, color_panel.top),
                color=self.theme.text_primary, size=self.theme.font_size_md,
                max_width=color_panel.width,
            )

            py = color_panel.top + self.theme.font_size_md + self.theme.padding_md

            # "Primary" label
            self.text.render(
                screen, "Primary color:",
                (color_panel.left, py),
                color=self.theme.text_secondary, size=self.theme.font_size_sm,
            )
            py += self.theme.font_size_sm + 6

            swatch_size = 24
            gap = 6
            swatches_per_row = min(
                len(COLOR_PALETTE),
                max(1, (color_panel.width - 4) // (swatch_size + gap)),
            )

            # Primary color swatches
            for ci, (cname, chex) in enumerate(COLOR_PALETTE):
                col = ci % swatches_per_row
                row = ci // swatches_per_row
                sx = color_panel.left + col * (swatch_size + gap)
                sy = py + row * (swatch_size + gap)
                swatch_rect = pygame.Rect(sx, sy, swatch_size, swatch_size)

                rgb = COLOR_PALETTE_RGB[ci]
                pygame.draw.rect(screen, rgb, swatch_rect, border_radius=3)

                # Highlight if this is the picking target
                is_current = team.color and team.color.lstrip("#").upper() == chex.upper()
                is_picker_sel = (
                    cp.picking == "primary" and cp.color_index == ci
                )
                if is_current:
                    pygame.draw.rect(
                        screen, self.theme.text_primary, swatch_rect,
                        width=2, border_radius=3,
                    )
                if is_picker_sel:
                    pygame.draw.rect(
                        screen, self.theme.primary, swatch_rect.inflate(4, 4),
                        width=2, border_radius=4,
                    )

                result["primary_rects"].append((swatch_rect, ci))

            # Calculate rows used by primary swatches
            primary_rows = (len(COLOR_PALETTE) + swatches_per_row - 1) // swatches_per_row
            py += primary_rows * (swatch_size + gap) + self.theme.padding_md

            # "Secondary" label
            self.text.render(
                screen, "Secondary color:",
                (color_panel.left, py),
                color=self.theme.text_secondary, size=self.theme.font_size_sm,
            )
            py += self.theme.font_size_sm + 6

            # Secondary color swatches
            for ci, (cname, chex) in enumerate(COLOR_PALETTE):
                col = ci % swatches_per_row
                row = ci // swatches_per_row
                sx = color_panel.left + col * (swatch_size + gap)
                sy = py + row * (swatch_size + gap)
                swatch_rect = pygame.Rect(sx, sy, swatch_size, swatch_size)

                rgb = COLOR_PALETTE_RGB[ci]
                pygame.draw.rect(screen, rgb, swatch_rect, border_radius=3)

                is_current = (
                    team.alternate_color
                    and team.alternate_color.lstrip("#").upper() == chex.upper()
                )
                is_picker_sel = (
                    cp.picking == "secondary" and cp.color_index == ci
                )
                if is_current:
                    pygame.draw.rect(
                        screen, self.theme.text_primary, swatch_rect,
                        width=2, border_radius=3,
                    )
                if is_picker_sel:
                    pygame.draw.rect(
                        screen, self.theme.primary, swatch_rect.inflate(4, 4),
                        width=2, border_radius=4,
                    )

                result["secondary_rects"].append((swatch_rect, ci))

            # Hint text
            sec_rows = (len(COLOR_PALETTE) + swatches_per_row - 1) // swatches_per_row
            hint_y = py + sec_rows * (swatch_size + gap) + self.theme.padding_md
            if hint_y + 20 < color_panel.bottom:
                picking_label = "primary" if cp.picking == "primary" else "secondary"
                self.text.render(
                    screen,
                    f"Picking {picking_label} - press select to confirm",
                    (color_panel.left, hint_y),
                    color=self.theme.text_disabled, size=self.theme.font_size_sm,
                    max_width=color_panel.width,
                )

        return result


color_picker_modal = ColorPickerModal()
