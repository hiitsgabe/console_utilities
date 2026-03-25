"""Sports Game Patcher screen - game selection sub-menu."""

import pygame
from typing import Optional, Dict, Any, Tuple, List, Set

from ui.theme import Theme, default_theme
from ui.templates.list_screen import ListScreenTemplate


class SportsPatcherScreen:
    SECTIONS = [
        (
            "Soccer",
            [
                ("WE2002 - Winning Eleven 2002 (PS1)", "we_patcher"),
                ("ISS - Int. Superstar Soccer (SNES)", "iss_patcher"),
                ("WIP - PES 6 (PS2) - V0", "pes6_ps2_patcher"),
            ],
        ),
        (
            "Basketball",
            [
                ("NBA Live 95 (Genesis)", "nbalive95_patcher"),
            ],
        ),
        (
            "Hockey",
            [
                ("NHL 94 - NHL Hockey '94 (Genesis)", "nhl94_gen_patcher"),
                ("NHL 05 - NHL 05 (PS2)", "nhl05_patcher"),
                ("NHL 07 - NHL 07 (PSP)", "nhl07_patcher"),
            ],
        ),
        (
            "Baseball",
            [
                ("KGJ MLB - Ken Griffey Jr. MLB (SNES)", "kgj_mlb_patcher"),
                ("MVP Baseball (PSP)", "mvp_psp_patcher"),
            ],
        ),
    ]

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.template = ListScreenTemplate(theme)
        self._items, self._divider_indices = self._build_items()

    def _build_items(self) -> Tuple[List[Tuple[str, str]], Set[int]]:
        items = []
        divider_indices = set()
        for section_label, games in self.SECTIONS:
            divider_indices.add(len(items))
            items.append((section_label, "divider"))
            items.extend(games)
        return items, divider_indices

    def render(
        self,
        screen: pygame.Surface,
        highlighted: int,
        settings: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[pygame.Rect], List[pygame.Rect], int]:
        items = [label for label, _ in self._items]
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
            divider_indices=self._divider_indices,
        )

    def get_action(self, index: int) -> str:
        if 0 <= index < len(self._items):
            return self._items[index][1]
        return "unknown"

    def get_count(self) -> int:
        return len(self._items)

    def get_divider_indices(self) -> Set[int]:
        return self._divider_indices


sports_patcher_screen = SportsPatcherScreen()
