"""League browser modal for WE Patcher."""

import pygame
from typing import List, Tuple, Optional, Any

from ui.theme import Theme, default_theme
from ui.organisms.modal_frame import ModalFrame
from ui.organisms.char_keyboard import CharKeyboard
from ui.atoms.text import Text
from ui.atoms.progress import ProgressBar


class LeagueBrowserModal:
    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.modal_frame = ModalFrame(theme)
        self.char_keyboard = CharKeyboard(theme)
        self.text = Text(theme)
        self.progress_bar = ProgressBar(theme)

    def render(
        self,
        screen: pygame.Surface,
        state,
        settings=None,
    ) -> Tuple[
        pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[Any], List[pygame.Rect]
    ]:
        """
        Render the league browser modal.

        Returns:
            Tuple of (modal_rect, content_rect, close_rect, char_rects, item_rects)
        """
        we = state.we_patcher

        margin = 30
        width = screen.get_width() - margin * 2
        height = screen.get_height() - margin * 2
        modal_rect = pygame.Rect(margin, margin, width, height)

        _, content_rect, close_rect = self.modal_frame.render(
            screen, modal_rect, title="Select League", show_close=True
        )

        char_rects = []
        item_rects = []

        if we.is_fetching and not we.available_leagues:
            self._render_loading(screen, content_rect, we)
            return modal_rect, content_rect, close_rect, char_rects, item_rects

        if we.fetch_error and not we.available_leagues:
            self._render_error(screen, content_rect, we.fetch_error)
            return modal_rect, content_rect, close_rect, char_rects, item_rects

        # Search bar area
        search_y = content_rect.top + self.theme.padding_sm
        field_rect = pygame.Rect(
            content_rect.left + self.theme.padding_sm,
            search_y,
            content_rect.width - self.theme.padding_sm * 2,
            30,
        )
        pygame.draw.rect(
            screen,
            self.theme.surface_hover,
            field_rect,
            border_radius=self.theme.radius_sm,
        )
        display_text = we.league_search_query or "Search leagues..."
        text_color = (
            self.theme.text_primary
            if we.league_search_query
            else self.theme.text_disabled
        )
        self.text.render(
            screen,
            display_text,
            (field_rect.left + 8, field_rect.centery - self.theme.font_size_sm // 2),
            color=text_color,
            size=self.theme.font_size_sm,
            max_width=field_rect.width - 16,
        )

        # Filter leagues by search query
        leagues = we.available_leagues or []
        query = we.league_search_query.lower()
        if query:
            leagues = [
                l
                for l in leagues
                if query in (l.name.lower() if hasattr(l, "name") else str(l).lower())
                or query in (l.country.lower() if hasattr(l, "country") else "")
            ]

        # League list area
        list_top = field_rect.bottom + self.theme.padding_md
        list_bottom = content_rect.bottom - self.theme.padding_sm
        item_height = 36
        y = list_top

        for i, league in enumerate(leagues):
            if y + item_height > list_bottom:
                break

            rect = pygame.Rect(
                content_rect.left + self.theme.padding_sm,
                y,
                content_rect.width - self.theme.padding_sm * 2,
                item_height,
            )

            is_highlighted = i == we.leagues_highlighted
            if is_highlighted:
                pygame.draw.rect(
                    screen,
                    self.theme.primary,
                    rect,
                    border_radius=self.theme.radius_sm,
                )

            league_name = league.name if hasattr(league, "name") else str(league)
            country = league.country if hasattr(league, "country") else ""
            label = f"{league_name} ({country})" if country else league_name

            self.text.render(
                screen,
                label,
                (rect.left + 8, rect.centery - self.theme.font_size_sm // 2),
                color=(
                    self.theme.text_primary
                    if is_highlighted
                    else self.theme.text_secondary
                ),
                size=self.theme.font_size_sm,
                max_width=rect.width - 16,
            )

            item_rects.append(rect)
            y += item_height + 2

        if not leagues and we.available_leagues:
            self.text.render(
                screen,
                "No matches",
                (content_rect.centerx, list_top + 40),
                color=self.theme.text_disabled,
                size=self.theme.font_size_md,
                align="center",
            )

        return modal_rect, content_rect, close_rect, char_rects, item_rects

    def get_filtered_leagues(self, state):
        """Return filtered leagues based on search query."""
        we = state.we_patcher
        leagues = we.available_leagues or []
        query = we.league_search_query.lower()
        if query:
            leagues = [
                l
                for l in leagues
                if query in (l.name.lower() if hasattr(l, "name") else str(l).lower())
                or query in (l.country.lower() if hasattr(l, "country") else "")
            ]
        return leagues

    def _render_loading(self, screen, content_rect, we):
        center_y = content_rect.centery - 40

        self.text.render(
            screen,
            we.fetch_status or "Loading leagues...",
            (content_rect.centerx, center_y),
            color=self.theme.text_primary,
            size=self.theme.font_size_lg,
            align="center",
        )

        if we.fetch_progress > 0:
            bar_width = min(400, content_rect.width - 80)
            bar_rect = pygame.Rect(
                content_rect.centerx - bar_width // 2,
                center_y + 40,
                bar_width,
                20,
            )
            self.progress_bar.render(screen, bar_rect, we.fetch_progress)

    def _render_error(self, screen, content_rect, error):
        self.text.render(
            screen,
            "Error",
            (content_rect.centerx, content_rect.centery - 30),
            color=self.theme.error,
            size=self.theme.font_size_xl,
            align="center",
        )
        self.text.render(
            screen,
            error,
            (content_rect.centerx, content_rect.centery + 10),
            color=self.theme.text_secondary,
            size=self.theme.font_size_md,
            align="center",
            max_width=content_rect.width - 40,
        )


league_browser_modal = LeagueBrowserModal()
