"""Slot mapping modal for WE Patcher."""

import pygame
from typing import List, Tuple, Optional

from ui.theme import Theme, default_theme
from ui.organisms.modal_frame import ModalFrame
from ui.atoms.text import Text


class SlotMappingModal:
    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.modal_frame = ModalFrame(theme)
        self.text = Text(theme)
        self.scroll_offset = 0  # Read by screen_manager after render

    def render(
        self,
        screen: pygame.Surface,
        state,
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[pygame.Rect]]:
        we = state.we_patcher

        margin = 30
        width = screen.get_width() - margin * 2
        height = screen.get_height() - margin * 2
        modal_rect = pygame.Rect(margin, margin, width, height)

        _, content_rect, close_rect = self.modal_frame.render(
            screen, modal_rect, title="Map Team Slots", show_close=True
        )

        item_rects = []

        if not we.slot_mapping:
            self.text.render(
                screen,
                "No slot mapping available",
                (content_rect.centerx, content_rect.centery),
                color=self.theme.text_disabled,
                size=self.theme.font_size_lg,
                align="center",
            )
            self.text.render(
                screen,
                "Press any button to auto-map",
                (content_rect.centerx, content_rect.centery + 40),
                color=self.theme.text_secondary,
                size=self.theme.font_size_md,
                align="center",
            )
            return modal_rect, content_rect, close_rect, item_rects

        # Column layout
        col_left = content_rect.left + self.theme.padding_sm
        col_mid = content_rect.centerx
        col_right = content_rect.right - self.theme.padding_sm

        # Header row
        header_y = content_rect.top + self.theme.padding_sm
        self.text.render(screen, "Real Team", (col_left, header_y),
                         color=self.theme.text_disabled, size=self.theme.font_size_sm)
        self.text.render(screen, "->", (col_mid - 10, header_y),
                         color=self.theme.text_disabled, size=self.theme.font_size_sm)
        self.text.render(screen, "ROM Slot", (col_mid + 20, header_y),
                         color=self.theme.text_disabled, size=self.theme.font_size_sm)

        divider_y = header_y + self.theme.font_size_sm + self.theme.padding_sm
        pygame.draw.line(screen, self.theme.primary,
                         (content_rect.left, divider_y), (content_rect.right, divider_y), 1)

        # Footer hint
        hint = "Up/Down: navigate   Left/Right: change slot   OK: confirm"
        footer_y = content_rect.bottom - self.theme.font_size_sm - self.theme.padding_sm
        self.text.render(screen, hint, (content_rect.centerx, footer_y),
                         color=self.theme.text_secondary, size=self.theme.font_size_sm,
                         align="center")

        # List area bounds
        list_top = divider_y + 4
        list_bottom = footer_y - self.theme.padding_sm

        item_height = 32
        item_spacing = 1
        total_item_h = item_height + item_spacing
        visible_count = max(1, (list_bottom - list_top) // total_item_h)

        # Scroll offset: keep highlighted item visible
        hl = we.slot_mapping_highlighted
        total = len(we.slot_mapping)
        max_scroll = max(0, total - visible_count)
        context = 2
        min_scroll = max(0, hl - visible_count + context + 1)
        ideal_scroll = max(0, hl - context)
        scroll = max(0, min(max(min_scroll, ideal_scroll), max_scroll))
        self.scroll_offset = scroll

        # Render visible items
        y = list_top
        for i in range(scroll, min(scroll + visible_count + 1, total)):
            if y + item_height > list_bottom:
                break

            mapping = we.slot_mapping[i]
            rect = pygame.Rect(content_rect.left + 4, y, content_rect.width - 8, item_height)
            is_hl = i == hl

            if is_hl:
                pygame.draw.rect(screen, self.theme.primary, rect,
                                 border_radius=self.theme.radius_sm)

            # Highlighted: dark text on bright bg. Normal: dim text on dark bg.
            text_color = self.theme.background if is_hl else self.theme.text_secondary
            arrow_color = self.theme.background if is_hl else self.theme.text_disabled

            real_name = (
                mapping.real_team.name
                if hasattr(mapping, "real_team") and hasattr(mapping.real_team, "name")
                else str(mapping)
            )
            slot_name = mapping.slot_name if hasattr(mapping, "slot_name") else ""

            text_y = rect.centery - self.theme.font_size_sm // 2
            self.text.render(screen, real_name, (col_left, text_y),
                             color=text_color, size=self.theme.font_size_sm,
                             max_width=col_mid - col_left - 20)
            self.text.render(screen, "->", (col_mid - 10, text_y),
                             color=arrow_color, size=self.theme.font_size_sm)
            self.text.render(screen, slot_name, (col_mid + 20, text_y),
                             color=text_color, size=self.theme.font_size_sm,
                             max_width=col_right - col_mid - 30)

            item_rects.append(rect)
            y += total_item_h

        # Scroll indicators
        ind_x = content_rect.right - 8
        if scroll > 0:
            pygame.draw.polygon(screen, self.theme.text_secondary, [
                (ind_x - 4, list_top + 8), (ind_x, list_top + 2), (ind_x + 4, list_top + 8),
            ])
        if scroll + visible_count < total:
            pygame.draw.polygon(screen, self.theme.text_secondary, [
                (ind_x - 4, list_bottom - 8), (ind_x, list_bottom - 2), (ind_x + 4, list_bottom - 8),
            ])

        return modal_rect, content_rect, close_rect, item_rects


slot_mapping_modal = SlotMappingModal()
