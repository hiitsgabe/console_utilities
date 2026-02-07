"""
Ghost cleaner wizard modal - Ghost file cleanup wizard.
"""

import pygame
from typing import List, Dict, Any, Tuple, Optional

from ui.theme import Theme, default_theme
from ui.organisms.modal_frame import ModalFrame
from ui.atoms.text import Text
from ui.atoms.progress import ProgressBar
from services.ghost_cleaner import format_size, get_ghost_summary, get_total_size


class GhostCleanerModal:
    """
    Ghost cleaner wizard modal.

    Multi-step wizard for finding and deleting ghost files.
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.modal_frame = ModalFrame(theme)
        self.text = Text(theme)
        self.progress_bar = ProgressBar(theme)

    def render(
        self,
        screen: pygame.Surface,
        step: str,
        folder_path: str,
        ghost_files: List[Dict[str, Any]],
        scan_progress: float,
        clean_progress: float,
        files_scanned: int,
        total_files: int,
        files_removed: int,
        space_freed: int,
        error_message: str,
        input_mode: str = "keyboard",
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[pygame.Rect]]:
        """
        Render the ghost cleaner wizard modal.

        Returns:
            Tuple of (modal_rect, content_rect, close_rect, item_rects)
        """
        margin = 30
        width = screen.get_width() - margin * 2
        height = screen.get_height() - margin * 2

        modal_rect = pygame.Rect(margin, margin, width, height)

        title = self._get_step_title(step)

        _, content_rect, close_rect = self.modal_frame.render(
            screen, modal_rect, title=title, show_close=True
        )

        item_rects = []

        if step == "scanning":
            self._render_scanning(
                screen, content_rect, scan_progress, files_scanned, total_files
            )
        elif step == "review":
            self._render_review(screen, content_rect, ghost_files, input_mode)
        elif step == "cleaning":
            self._render_cleaning(screen, content_rect, clean_progress)
        elif step == "complete":
            self._render_complete(screen, content_rect, files_removed, space_freed)
        elif step == "no_ghosts":
            self._render_no_ghosts(screen, content_rect)
        elif step == "error":
            self._render_error(screen, content_rect, error_message)

        return modal_rect, content_rect, close_rect, item_rects

    def _get_step_title(self, step: str) -> str:
        """Get title for current step."""
        titles = {
            "scanning": "Ghost Cleaner - Scanning",
            "review": "Ghost Cleaner - Review",
            "cleaning": "Ghost Cleaner - Cleaning",
            "complete": "Ghost Cleaner - Complete",
            "no_ghosts": "Ghost Cleaner - Clean",
            "error": "Ghost Cleaner - Error",
        }
        return titles.get(step, "Ghost File Cleaner")

    def _render_scanning(
        self,
        screen: pygame.Surface,
        content_rect: pygame.Rect,
        progress: float,
        files_scanned: int,
        total_files: int,
    ) -> None:
        """Render scanning progress."""
        center_y = content_rect.centery - 40

        self.text.render(
            screen,
            "Scanning for ghost files...",
            (content_rect.centerx, center_y),
            color=self.theme.text_primary,
            size=self.theme.font_size_lg,
            align="center",
        )

        bar_width = min(400, content_rect.width - 80)
        bar_rect = pygame.Rect(
            content_rect.centerx - bar_width // 2,
            center_y + 40,
            bar_width,
            20,
        )
        self.progress_bar.render(screen, bar_rect, progress)

        self.text.render(
            screen,
            f"{files_scanned} / {total_files} entries",
            (content_rect.centerx, center_y + 80),
            color=self.theme.text_secondary,
            size=self.theme.font_size_md,
            align="center",
        )

    def _render_review(
        self,
        screen: pygame.Surface,
        content_rect: pygame.Rect,
        ghost_files: List[Dict[str, Any]],
        input_mode: str,
    ) -> None:
        """Render review step showing ghost files found."""
        y = content_rect.top + self.theme.padding_lg

        total_count = len(ghost_files)
        total_size = get_total_size(ghost_files)
        summary = get_ghost_summary(ghost_files)

        # Header
        self.text.render(
            screen,
            f"Found {total_count} ghost files ({format_size(total_size)})",
            (content_rect.centerx, y),
            color=self.theme.text_primary,
            size=self.theme.font_size_lg,
            align="center",
        )
        y += self.theme.font_size_lg + self.theme.padding_lg * 2

        # Summary by type
        for ghost_type, count in sorted(summary.items()):
            self.text.render(
                screen,
                f"  {ghost_type}: {count}",
                (content_rect.left + self.theme.padding_lg, y),
                color=self.theme.text_secondary,
                size=self.theme.font_size_md,
            )
            y += self.theme.font_size_md + self.theme.padding_sm

        # Hint
        y = content_rect.bottom - 60
        self.text.render(
            screen,
            "Delete all ghost files?",
            (content_rect.centerx, y),
            color=self.theme.text_primary,
            size=self.theme.font_size_md,
            align="center",
        )

        hint = (
            "[A] Delete all  [B] Cancel"
            if input_mode == "gamepad"
            else "Enter: Delete all  Esc: Cancel"
        )
        self.text.render(
            screen,
            hint,
            (content_rect.centerx, content_rect.bottom - 30),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
            align="center",
        )

    def _render_cleaning(
        self,
        screen: pygame.Surface,
        content_rect: pygame.Rect,
        progress: float,
    ) -> None:
        """Render cleaning progress."""
        center_y = content_rect.centery - 20

        self.text.render(
            screen,
            "Removing ghost files...",
            (content_rect.centerx, center_y),
            color=self.theme.text_primary,
            size=self.theme.font_size_lg,
            align="center",
        )

        bar_width = min(400, content_rect.width - 80)
        bar_rect = pygame.Rect(
            content_rect.centerx - bar_width // 2,
            center_y + 40,
            bar_width,
            20,
        )
        self.progress_bar.render(screen, bar_rect, progress)

    def _render_complete(
        self,
        screen: pygame.Surface,
        content_rect: pygame.Rect,
        files_removed: int,
        space_freed: int,
    ) -> None:
        """Render completion screen."""
        center_y = content_rect.centery - 40

        self.text.render(
            screen,
            "Cleanup Complete!",
            (content_rect.centerx, center_y),
            color=self.theme.success,
            size=self.theme.font_size_xl,
            align="center",
        )

        self.text.render(
            screen,
            f"Files removed: {files_removed}",
            (content_rect.centerx, center_y + 50),
            color=self.theme.text_primary,
            size=self.theme.font_size_lg,
            align="center",
        )

        self.text.render(
            screen,
            f"Space freed: {format_size(space_freed)}",
            (content_rect.centerx, center_y + 85),
            color=self.theme.text_primary,
            size=self.theme.font_size_lg,
            align="center",
        )

        self.text.render(
            screen,
            "Press any button to close",
            (content_rect.centerx, content_rect.bottom - 30),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
            align="center",
        )

    def _render_no_ghosts(
        self,
        screen: pygame.Surface,
        content_rect: pygame.Rect,
    ) -> None:
        """Render no ghost files found screen."""
        center_y = content_rect.centery - 20

        self.text.render(
            screen,
            "No ghost files found!",
            (content_rect.centerx, center_y),
            color=self.theme.success,
            size=self.theme.font_size_xl,
            align="center",
        )

        self.text.render(
            screen,
            "This folder is clean.",
            (content_rect.centerx, center_y + 50),
            color=self.theme.text_secondary,
            size=self.theme.font_size_md,
            align="center",
        )

        self.text.render(
            screen,
            "Press any button to close",
            (content_rect.centerx, content_rect.bottom - 30),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
            align="center",
        )

    def _render_error(
        self,
        screen: pygame.Surface,
        content_rect: pygame.Rect,
        error_message: str,
    ) -> None:
        """Render error screen."""
        center_y = content_rect.centery - 30

        self.text.render(
            screen,
            "Error",
            (content_rect.centerx, center_y),
            color=self.theme.error,
            size=self.theme.font_size_xl,
            align="center",
        )

        self.text.render(
            screen,
            error_message,
            (content_rect.centerx, center_y + 50),
            color=self.theme.text_secondary,
            size=self.theme.font_size_md,
            align="center",
            max_width=content_rect.width - 40,
        )

        self.text.render(
            screen,
            "Press any button to close",
            (content_rect.centerx, content_rect.bottom - 30),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
            align="center",
        )


# Default instance
ghost_cleaner_modal = GhostCleanerModal()
