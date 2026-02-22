"""Roster preview modal for WE Patcher."""

import pygame
from typing import List, Tuple, Optional, Any

from ui.theme import Theme, default_theme
from ui.organisms.modal_frame import ModalFrame
from ui.atoms.text import Text


class RosterPreviewModal:
    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.modal_frame = ModalFrame(theme)
        self.text = Text(theme)

    def render(
        self,
        screen: pygame.Surface,
        state,
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[pygame.Rect]]:
        """
        Render the roster preview modal.

        Returns:
            Tuple of (modal_rect, content_rect, close_rect, item_rects)
        """
        we = state.we_patcher
        league_data = we.league_data

        margin = 30
        width = screen.get_width() - margin * 2
        height = screen.get_height() - margin * 2
        modal_rect = pygame.Rect(margin, margin, width, height)

        title = "Roster Preview"
        if league_data and hasattr(league_data, "league"):
            title = f"Roster Preview - {league_data.league.name}"

        _, content_rect, close_rect = self.modal_frame.render(
            screen, modal_rect, title=title, show_close=True
        )

        item_rects = []

        if not league_data or not hasattr(league_data, "teams"):
            self.text.render(
                screen,
                "No league data loaded",
                (content_rect.centerx, content_rect.centery),
                color=self.theme.text_disabled,
                size=self.theme.font_size_lg,
                align="center",
            )
            return modal_rect, content_rect, close_rect, item_rects

        teams = league_data.teams
        team_idx = we.roster_preview_team_index
        player_idx = we.roster_preview_player_index

        # Left panel: team list
        panel_width = content_rect.width // 3
        team_panel = pygame.Rect(
            content_rect.left,
            content_rect.top,
            panel_width - self.theme.padding_sm,
            content_rect.height,
        )

        # Right panel: player list
        player_panel = pygame.Rect(
            content_rect.left + panel_width,
            content_rect.top,
            content_rect.width - panel_width,
            content_rect.height,
        )

        # Draw divider
        pygame.draw.line(
            screen,
            self.theme.primary,
            (player_panel.left - 4, content_rect.top),
            (player_panel.left - 4, content_rect.bottom),
            1,
        )

        # Render teams
        self.text.render(
            screen,
            "Teams",
            (team_panel.left, team_panel.top),
            color=self.theme.text_primary,
            size=self.theme.font_size_md,
        )

        y = team_panel.top + self.theme.font_size_md + self.theme.padding_sm
        item_height = 28

        for i, team_roster in enumerate(teams):
            if y + item_height > team_panel.bottom:
                break

            rect = pygame.Rect(team_panel.left, y, team_panel.width, item_height)
            is_selected = i == team_idx

            if is_selected:
                pygame.draw.rect(
                    screen,
                    self.theme.primary,
                    rect,
                    border_radius=self.theme.radius_sm,
                )

            team_name = (
                team_roster.team.name
                if hasattr(team_roster, "team")
                else str(team_roster)
            )
            self.text.render(
                screen,
                team_name,
                (rect.left + 6, rect.centery - self.theme.font_size_sm // 2),
                color=(
                    self.theme.text_primary
                    if is_selected
                    else self.theme.text_secondary
                ),
                size=self.theme.font_size_sm,
                max_width=rect.width - 12,
            )

            item_rects.append(rect)
            y += item_height + 1

        # Render players for selected team
        if 0 <= team_idx < len(teams):
            team_roster = teams[team_idx]
            players = team_roster.players if hasattr(team_roster, "players") else []

            self.text.render(
                screen,
                f"Players ({len(players)})",
                (player_panel.left + self.theme.padding_sm, player_panel.top),
                color=self.theme.text_primary,
                size=self.theme.font_size_md,
            )

            py = player_panel.top + self.theme.font_size_md + self.theme.padding_sm

            # Column headers
            col_name_x = player_panel.left + self.theme.padding_sm
            col_pos_x = player_panel.right - 80
            col_num_x = player_panel.right - 30

            self.text.render(
                screen,
                "Name",
                (col_name_x, py),
                color=self.theme.text_disabled,
                size=self.theme.font_size_sm,
            )
            self.text.render(
                screen,
                "Pos",
                (col_pos_x, py),
                color=self.theme.text_disabled,
                size=self.theme.font_size_sm,
            )
            self.text.render(
                screen,
                "#",
                (col_num_x, py),
                color=self.theme.text_disabled,
                size=self.theme.font_size_sm,
            )

            py += self.theme.font_size_sm + 4
            row_height = 22

            for j, player in enumerate(players):
                if py + row_height > player_panel.bottom:
                    break

                is_hl = j == player_idx
                row_rect = pygame.Rect(
                    player_panel.left + 4, py, player_panel.width - 8, row_height
                )

                if is_hl:
                    pygame.draw.rect(
                        screen,
                        self.theme.surface_hover,
                        row_rect,
                        border_radius=2,
                    )

                p_name = player.name if hasattr(player, "name") else str(player)
                p_pos = player.position if hasattr(player, "position") else ""
                p_num = (
                    str(player.number)
                    if hasattr(player, "number") and player.number
                    else ""
                )

                name_color = (
                    self.theme.text_primary if is_hl else self.theme.text_secondary
                )
                self.text.render(
                    screen,
                    p_name,
                    (col_name_x, py + 2),
                    color=name_color,
                    size=self.theme.font_size_sm,
                    max_width=col_pos_x - col_name_x - 8,
                )
                self.text.render(
                    screen,
                    p_pos[:3] if p_pos else "",
                    (col_pos_x, py + 2),
                    color=self.theme.text_disabled,
                    size=self.theme.font_size_sm,
                )
                self.text.render(
                    screen,
                    p_num,
                    (col_num_x, py + 2),
                    color=self.theme.text_disabled,
                    size=self.theme.font_size_sm,
                )

                py += row_height

        return modal_rect, content_rect, close_rect, item_rects


roster_preview_modal = RosterPreviewModal()
