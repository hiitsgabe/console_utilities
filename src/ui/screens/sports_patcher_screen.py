"""Sports Game Patcher screen - game selection sub-menu."""

import pygame
from typing import Optional, Dict, Any, Tuple, List

from ui.theme import Theme, default_theme
from ui.templates.list_screen import ListScreenTemplate


class SportsPatcherScreen:
    GAMES = [
        ("WE2002 - Winning Eleven 2002 (PS1)", "we_patcher"),
        ("ISS - Int. Superstar Soccer (SNES)", "iss_patcher"),
        ("NHL 94 - NHL Hockey '94 (SNES)", "nhl94_patcher"),
        ("NHL 94 - NHL Hockey '94 (Genesis)", "nhl94_gen_patcher"),
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
        api_key = (settings or {}).get("api_football_key", "")
        hint = None if api_key else "Set your API-Football key in Settings → Sports Roster"
        return self.template.render(
            screen,
            title="Sports Game Updater",
            items=items,
            highlighted=highlighted,
            selected=set(),
            show_back=True,
            item_height=40,
            get_label=lambda x: x,
            item_spacing=8,
            subtitle=hint,
        )

    def get_action(self, index: int) -> str:
        if 0 <= index < len(self.GAMES):
            return self.GAMES[index][1]
        return "unknown"

    def get_count(self) -> int:
        return len(self.GAMES)


sports_patcher_screen = SportsPatcherScreen()
