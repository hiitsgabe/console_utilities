"""
Modal template - Layout for modal dialogs.
"""

import pygame
from typing import Tuple, Optional, List

from ui.theme import Theme, default_theme
from ui.organisms.modal_frame import ModalFrame
from ui.molecules.action_button import ActionButton


class ModalTemplate:
    """
    Modal template.

    Provides common modal dialog layouts with
    optional action buttons.
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.modal_frame = ModalFrame(theme)
        self.action_button = ActionButton(theme)

    def render(
        self,
        screen: pygame.Surface,
        width: int,
        height: int,
        title: Optional[str] = None,
        show_close: bool = True,
        buttons: Optional[List[Tuple[str, str]]] = None,  # [(label, style), ...]
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[pygame.Rect]]:
        """
        Render a modal dialog.

        Args:
            screen: Surface to render to
            width: Modal width
            height: Modal height
            title: Optional title
            show_close: Show close button
            buttons: Optional list of (label, style) tuples
                    style can be: "primary", "secondary", "success", "danger"

        Returns:
            Tuple of (modal_rect, content_rect, close_button_rect, button_rects)
        """
        # Calculate button area height
        button_height = 40 if buttons else 0
        button_area_height = button_height + self.theme.padding_md * 2 if buttons else 0

        # Adjust modal height to include buttons
        total_height = height + button_area_height

        # Render modal frame
        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, total_height, title, show_close
        )

        # Adjust content rect to exclude button area
        if buttons:
            content_rect.height -= button_area_height

        # Render buttons
        button_rects = []
        if buttons:
            button_width = 100
            total_buttons_width = (
                len(buttons) * button_width + (len(buttons) - 1) * self.theme.padding_sm
            )
            start_x = modal_rect.centerx - total_buttons_width // 2
            button_y = modal_rect.bottom - button_area_height + self.theme.padding_md

            for i, (label, style) in enumerate(buttons):
                button_rect = pygame.Rect(
                    start_x + i * (button_width + self.theme.padding_sm),
                    button_y,
                    button_width,
                    button_height,
                )

                # Choose style
                if style == "success":
                    self.action_button.render_success(screen, button_rect, label)
                elif style == "danger":
                    self.action_button.render_danger(screen, button_rect, label)
                elif style == "secondary":
                    self.action_button.render_secondary(screen, button_rect, label)
                else:
                    self.action_button.render(screen, button_rect, label)

                button_rects.append(button_rect)

        return modal_rect, content_rect, close_rect, button_rects

    def render_message(
        self,
        screen: pygame.Surface,
        title: str,
        message: str,
        buttons: Optional[List[Tuple[str, str]]] = None,
    ) -> Tuple[pygame.Rect, Optional[pygame.Rect], List[pygame.Rect]]:
        """
        Render a simple message modal.

        Args:
            screen: Surface to render to
            title: Modal title
            message: Message text
            buttons: Optional buttons

        Returns:
            Tuple of (modal_rect, close_button_rect, button_rects)
        """
        from ui.atoms.text import Text

        text = Text(self.theme)

        # Calculate size based on message
        width = 400
        height = 200

        modal_rect, content_rect, close_rect, button_rects = self.render(
            screen, width, height, title, show_close=(buttons is None), buttons=buttons
        )

        # Draw message
        text.render_multiline(
            screen,
            message,
            (content_rect.left, content_rect.top),
            color=self.theme.text_primary,
            size=self.theme.font_size_md,
            max_width=content_rect.width,
        )

        return modal_rect, close_rect, button_rects

    def render_loading(
        self, screen: pygame.Surface, message: str, progress: Optional[float] = None
    ) -> pygame.Rect:
        """
        Render a loading modal.

        Args:
            screen: Surface to render to
            message: Loading message
            progress: Optional progress (0.0 to 1.0)

        Returns:
            Modal rect
        """
        from ui.atoms.text import Text
        from ui.atoms.progress import ProgressBar
        from ui.atoms.spinner import Spinner

        text = Text(self.theme)
        progress_bar = ProgressBar(self.theme)
        spinner = Spinner(self.theme)

        width = 350
        height = 140

        modal_rect, content_rect, _, _ = self.render(
            screen, width, height, show_close=False
        )

        if progress is not None:
            # Show message at top
            text.render(
                screen,
                message,
                (content_rect.centerx, content_rect.top + 10),
                color=self.theme.text_primary,
                size=self.theme.font_size_md,
                align="center",
            )

            # Draw progress bar
            bar_rect = pygame.Rect(
                content_rect.left + 20,
                content_rect.bottom - 30,
                content_rect.width - 40,
                20,
            )
            progress_bar.render(screen, bar_rect, progress, show_glow=True)
        else:
            # Show spinner in center
            spinner_y = content_rect.top + 35
            spinner.render_simple(
                screen,
                (content_rect.centerx, spinner_y),
                size=50,
                color=self.theme.primary,
            )

            # Show message below spinner
            text.render(
                screen,
                message,
                (content_rect.centerx, spinner_y + 45),
                color=self.theme.text_primary,
                size=self.theme.font_size_md,
                align="center",
            )

        return modal_rect

    def render_error(
        self,
        screen: pygame.Surface,
        title: str,
        error_lines: List[str],
        buttons: Optional[List[Tuple[str, str]]] = None,
    ) -> Tuple[pygame.Rect, Optional[pygame.Rect], List[pygame.Rect]]:
        """
        Render an error modal.

        Args:
            screen: Surface to render to
            title: Error title
            error_lines: Error message lines
            buttons: Optional buttons

        Returns:
            Tuple of (modal_rect, close_button_rect, button_rects)
        """
        from ui.atoms.text import Text

        text = Text(self.theme)

        # Calculate size based on error lines
        width = 500
        height = 100 + len(error_lines) * 25

        if buttons is None:
            buttons = [("OK", "primary")]

        modal_rect, content_rect, close_rect, button_rects = self.render(
            screen, width, height, title, show_close=False, buttons=buttons
        )

        # Draw error icon
        icon_size = 30
        pygame.draw.circle(
            screen,
            self.theme.error,
            (content_rect.left + icon_size, content_rect.top + icon_size),
            icon_size // 2,
        )

        # Draw error lines
        y = content_rect.top
        for line in error_lines:
            text.render(
                screen,
                line,
                (content_rect.left + icon_size * 2, y),
                color=self.theme.text_primary,
                size=self.theme.font_size_sm,
                max_width=content_rect.width - icon_size * 2,
            )
            y += 25

        return modal_rect, close_rect, button_rects


# Default instance
modal_template = ModalTemplate()
