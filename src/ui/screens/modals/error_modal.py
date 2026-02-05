"""
Error modal - Error message display.
"""

import pygame
from typing import List, Tuple, Optional

from ui.theme import Theme, default_theme
from ui.templates.modal_template import ModalTemplate


class ErrorModal:
    """
    Error modal.

    Displays error messages with optional dismiss button.
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.modal_template = ModalTemplate(theme)

    def render(
        self,
        screen: pygame.Surface,
        title: str,
        error_lines: List[str],
        show_ok_button: bool = True,
    ) -> Tuple[pygame.Rect, Optional[pygame.Rect], List[pygame.Rect]]:
        """
        Render an error modal.

        Args:
            screen: Surface to render to
            title: Error title
            error_lines: Error message lines
            show_ok_button: Show OK button

        Returns:
            Tuple of (modal_rect, close_button_rect, button_rects)
        """
        buttons = [("OK", "primary")] if show_ok_button else None
        return self.modal_template.render_error(screen, title, error_lines, buttons)

    def render_simple(self, screen: pygame.Surface, message: str) -> pygame.Rect:
        """
        Render a simple error message.

        Args:
            screen: Surface to render to
            message: Error message

        Returns:
            Modal rect
        """
        modal_rect, _, _ = self.modal_template.render_error(
            screen, "Error", [message], [("OK", "primary")]
        )
        return modal_rect


# Default instance
error_modal = ErrorModal()
