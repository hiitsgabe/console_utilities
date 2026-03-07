"""
Steam search modal - Search and select Steam games for shortcut creation.
"""

import pygame
from typing import List, Dict, Any, Tuple, Optional, Callable

from constants import BEZEL_INSET
from ui.theme import Theme, default_theme
from ui.organisms.modal_frame import ModalFrame
from ui.organisms.grid import Grid
from ui.molecules.action_button import ActionButton
from ui.atoms.text import Text


class SteamSearchModal:
    """Modal for displaying Steam game search results in a grid."""

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.modal_frame = ModalFrame(theme)
        self.grid = Grid(theme)
        self.action_button = ActionButton(theme)
        self.text = Text(theme)

    def render_results(
        self,
        screen: pygame.Surface,
        results: List[Dict[str, Any]],
        highlighted: int,
        query: str,
        get_image: Optional[Callable[[Any], Optional[pygame.Surface]]] = None,
        loading_more: bool = False,
    ) -> Tuple[pygame.Rect, List[pygame.Rect], Optional[pygame.Rect], int]:
        """Render the search results as a grid with images."""
        modal_rect, content_rect, close_rect = self.modal_frame.render_fullscreen(
            screen, margin=max(30, BEZEL_INSET), title=f"Steam: \"{query}\"", show_close=True
        )

        if not results:
            self.text.render(
                screen,
                "No games found. Try a different search.",
                (content_rect.centerx, content_rect.centery),
                color=self.theme.text_secondary,
                size=self.theme.font_size_md,
                align="center",
            )
            return modal_rect, [], close_rect, 0

        # Calculate cell size for Steam banner aspect ratio (460x215 ≈ 2.14:1)
        columns = 3
        padding = self.theme.padding_sm
        available_width = content_rect.width - padding * 2
        cell_width = (available_width - padding * (columns - 1)) // columns
        cell_height = int(cell_width / 2.14) + 30  # banner height + label
        cell_size = (cell_width, cell_height)

        # Clip grid rendering to content area to prevent overflow onto bezels
        old_clip = screen.get_clip()
        screen.set_clip(content_rect)

        item_rects, scroll_offset = self.grid.render(
            screen,
            content_rect,
            results,
            highlighted,
            set(),
            columns=columns,
            cell_size=cell_size,
            get_label=lambda item: item.get("name", ""),
            get_image=get_image,
            fill_image=True,
        )

        screen.set_clip(old_clip)

        if loading_more:
            self.text.render(
                screen,
                "Loading more...",
                (content_rect.centerx, content_rect.bottom - self.theme.font_size_sm),
                color=self.theme.text_secondary,
                size=self.theme.font_size_sm,
                align="center",
            )

        return modal_rect, item_rects, close_rect, scroll_offset

    def render_complete(
        self,
        screen: pygame.Surface,
        game_name: str,
        file_path: str,
    ) -> Tuple[pygame.Rect, Optional[pygame.Rect], Optional[pygame.Rect]]:
        """Render the completion message."""
        width = min(500, screen.get_width() - 40)
        height = 200

        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height, title="Shortcut Created", show_close=True
        )

        y = content_rect.top + self.theme.padding_md
        self.text.render(
            screen, f"{game_name}.steam",
            (content_rect.centerx, y),
            color=self.theme.primary,
            size=self.theme.font_size_md,
            align="center",
            max_width=content_rect.width - self.theme.padding_md * 2,
        )

        y += self.theme.font_size_md + self.theme.padding_sm
        self.text.render(
            screen, f"Saved to: {file_path}",
            (content_rect.centerx, y),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
            align="center",
            max_width=content_rect.width - self.theme.padding_md * 2,
        )

        # OK button
        button_width = 120
        button_height = 44
        ok_rect = pygame.Rect(
            content_rect.centerx - button_width // 2,
            content_rect.bottom - button_height - self.theme.padding_sm,
            button_width, button_height,
        )
        self.action_button.render(screen, ok_rect, "OK", hover=True)

        return modal_rect, close_rect, ok_rect


steam_search_modal = SteamSearchModal()
