"""Sports Game Patcher screen - game selection sub-menu."""

import pygame
from typing import Optional, Dict, Any, Tuple, List

from ui.theme import Theme, default_theme
from ui.templates.list_screen import ListScreenTemplate


class SportsPatcherScreen:
    GAMES = [
        ("WE2002 - Winning Eleven 2002 (PS1)", "we_patcher"),
    ]

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.template = ListScreenTemplate(theme)

    def render(
        self,
        screen: pygame.Surface,
        highlighted: int,
        settings: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[pygame.Rect], List[pygame.Rect], int]:
        items = [label for label, _ in self.GAMES]
        return self.template.render(
            screen,
            title="Sports Game Patcher",
            items=items,
            highlighted=highlighted,
            selected=set(),
            show_back=True,
            item_height=40,
            get_label=lambda x: x,
            item_spacing=8,
        )

    def get_action(self, index: int) -> str:
        if 0 <= index < len(self.GAMES):
            return self.GAMES[index][1]
        return "unknown"

    def get_count(self) -> int:
        return len(self.GAMES)


sports_patcher_screen = SportsPatcherScreen()
