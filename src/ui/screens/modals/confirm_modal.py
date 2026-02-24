"""
Confirm modal - Confirmation dialog with OK/Cancel buttons.
"""

import pygame
from typing import Tuple, Optional, List

from ui.theme import Theme, default_theme
from ui.organisms.modal_frame import ModalFrame
from ui.molecules.action_button import ActionButton
from ui.atoms.text import Text


class ConfirmModal:
    """
    Confirmation modal.

    Displays a message with OK and Cancel buttons.
    Used for confirming actions like "Download All".
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.modal_frame = ModalFrame(theme)
        self.action_button = ActionButton(theme)
        self.text = Text(theme)

    def render(
        self,
        screen: pygame.Surface,
        title: str,
        message_lines: List[str],
        ok_label: str = "OK",
        cancel_label: str = "Cancel",
        button_index: int = 0,  # 0 = OK, 1 = Cancel
    ) -> Tuple[
        pygame.Rect, Optional[pygame.Rect], Optional[pygame.Rect], Optional[pygame.Rect]
    ]:
        """
        Render the confirmation modal.

        Args:
            screen: Surface to render to
            title: Modal title
            message_lines: List of message lines to display
            ok_label: Label for OK button
            cancel_label: Label for Cancel button
            button_index: Currently focused button (0=OK, 1=Cancel)

        Returns:
            Tuple of (modal_rect, ok_button_rect, cancel_button_rect, close_rect)
        """
        # Calculate modal size based on content
        width = min(450, screen.get_width() - 40)
        font = self.text.get_font(self.theme.font_size_md)
        line_height = font.get_linesize() + 4
        text_height = len(message_lines) * line_height
        button_height = 44
        button_footer = button_height + self.theme.padding_lg * 2  # gap above + button
        content_height = text_height + self.theme.padding_sm + button_footer
        height = min(
            content_height + 120, screen.get_height() - 60
        )  # 120 for title + padding

        # Render modal frame
        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height, title=title, show_close=True
        )

        # Anchor buttons to bottom of content area
        button_y = content_rect.bottom - button_height - self.theme.padding_sm
        button_width = 120
        button_spacing = self.theme.padding_lg

        # Draw message lines (in area above buttons)
        y = content_rect.top + self.theme.padding_sm
        text_area_bottom = button_y - self.theme.padding_lg
        for line in message_lines:
            if y + line_height > text_area_bottom:
                break
            self.text.render(
                screen,
                line,
                (content_rect.centerx, y),
                color=self.theme.text_primary,
                size=self.theme.font_size_md,
                align="center",
                max_width=content_rect.width - self.theme.padding_md * 2,
            )
            y += line_height

        has_cancel = bool(cancel_label)

        if has_cancel:
            # Two buttons side by side
            ok_rect = pygame.Rect(
                content_rect.centerx - button_width - button_spacing // 2,
                button_y,
                button_width,
                button_height,
            )
            cancel_rect = pygame.Rect(
                content_rect.centerx + button_spacing // 2,
                button_y,
                button_width,
                button_height,
            )
        else:
            # Single centered OK button
            ok_rect = pygame.Rect(
                content_rect.centerx - button_width // 2,
                button_y,
                button_width,
                button_height,
            )
            cancel_rect = pygame.Rect(0, 0, 0, 0)

        ok_focused = button_index == 0
        self.action_button.render(screen, ok_rect, ok_label, hover=ok_focused)

        if has_cancel:
            cancel_focused = button_index == 1
            self.action_button.render_secondary(
                screen,
                cancel_rect,
                cancel_label,
                hover=cancel_focused,
            )

        return modal_rect, ok_rect, cancel_rect, close_rect


# Default instance
confirm_modal = ConfirmModal()
