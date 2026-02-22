"""Slot mapping modal for WE Patcher."""

import pygame
from typing import List, Tuple, Optional, Any

from ui.theme import Theme, default_theme
from ui.organisms.modal_frame import ModalFrame
from ui.atoms.text import Text


class SlotMappingModal:
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
        Render the slot mapping modal.

        Returns:
            Tuple of (modal_rect, content_rect, close_rect, item_rects)
        """
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

        # Column headers
        col_left = content_rect.left + self.theme.padding_sm
        col_mid = content_rect.centerx
        col_right = content_rect.right - self.theme.padding_sm

        y = content_rect.top + self.theme.padding_sm

        # Headers
        self.text.render(
            screen,
            "Real Team",
            (col_left, y),
            color=self.theme.text_disabled,
            size=self.theme.font_size_sm,
        )
        self.text.render(
            screen,
            "->",
            (col_mid - 10, y),
            color=self.theme.text_disabled,
            size=self.theme.font_size_sm,
        )
        self.text.render(
            screen,
            "ROM Slot",
            (col_mid + 20, y),
            color=self.theme.text_disabled,
            size=self.theme.font_size_sm,
        )

        y += self.theme.font_size_sm + self.theme.padding_md

        # Draw divider line
        pygame.draw.line(
            screen,
            self.theme.primary,
            (content_rect.left, y - 4),
            (content_rect.right, y - 4),
            1,
        )

        item_height = 32

        for i, mapping in enumerate(we.slot_mapping):
            if y + item_height > content_rect.bottom - 30:
                break

            rect = pygame.Rect(
                content_rect.left + 4, y, content_rect.width - 8, item_height
            )
            is_highlighted = i == we.slot_mapping_highlighted

            if is_highlighted:
                pygame.draw.rect(
                    screen,
                    self.theme.primary,
                    rect,
                    border_radius=self.theme.radius_sm,
                )

            real_name = (
                mapping.real_team.name
                if hasattr(mapping, "real_team") and hasattr(mapping.real_team, "name")
                else str(mapping)
            )
            slot_name = mapping.slot_name if hasattr(mapping, "slot_name") else ""

            text_color = (
                self.theme.text_primary if is_highlighted else self.theme.text_secondary
            )

            self.text.render(
                screen,
                real_name,
                (col_left, rect.centery - self.theme.font_size_sm // 2),
                color=text_color,
                size=self.theme.font_size_sm,
                max_width=col_mid - col_left - 20,
            )
            self.text.render(
                screen,
                "->",
                (col_mid - 10, rect.centery - self.theme.font_size_sm // 2),
                color=self.theme.text_disabled,
                size=self.theme.font_size_sm,
            )
            self.text.render(
                screen,
                slot_name,
                (col_mid + 20, rect.centery - self.theme.font_size_sm // 2),
                color=text_color,
                size=self.theme.font_size_sm,
                max_width=col_right - col_mid - 30,
            )

            item_rects.append(rect)
            y += item_height + 1

        # Footer hint
        self.text.render(
            screen,
            "Press B to confirm mapping",
            (content_rect.centerx, content_rect.bottom - 20),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
            align="center",
        )

        return modal_rect, content_rect, close_rect, item_rects


slot_mapping_modal = SlotMappingModal()
