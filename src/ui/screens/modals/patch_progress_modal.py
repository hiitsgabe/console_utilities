"""Patch progress modal for WE Patcher."""

import pygame
from typing import Tuple, Optional, List

from ui.theme import Theme, default_theme
from ui.organisms.modal_frame import ModalFrame
from ui.atoms.text import Text
from ui.atoms.progress import ProgressBar


class PatchProgressModal:
    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.modal_frame = ModalFrame(theme)
        self.text = Text(theme)
        self.progress_bar = ProgressBar(theme)

    def render(
        self,
        screen: pygame.Surface,
        state,
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[pygame.Rect]]:
        """
        Render the patch progress modal.

        Returns:
            Tuple of (modal_rect, content_rect, close_rect, item_rects)
        """
        we = state.active_patcher

        width = 500
        height = 260

        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height, title="Patching ROM", show_close=not we.is_patching
        )

        item_rects = []

        if we.patch_complete:
            self._render_complete(screen, content_rect, we)
        elif we.patch_error:
            self._render_error(screen, content_rect, we.patch_error)
        else:
            self._render_progress(screen, content_rect, we)

        return modal_rect, content_rect, close_rect, item_rects

    def _render_progress(self, screen, content_rect, we):
        center_y = content_rect.centery - 20

        status = we.patch_status or "Patching..."
        self.text.render(
            screen,
            status,
            (content_rect.centerx, center_y),
            color=self.theme.text_primary,
            size=self.theme.font_size_md,
            align="center",
            max_width=content_rect.width - 40,
        )

        bar_width = min(350, content_rect.width - 60)
        bar_rect = pygame.Rect(
            content_rect.centerx - bar_width // 2,
            center_y + 35,
            bar_width,
            20,
        )
        self.progress_bar.render(screen, bar_rect, we.patch_progress)

        pct = int(we.patch_progress * 100)
        self.text.render(
            screen,
            f"{pct}%",
            (content_rect.centerx, center_y + 65),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
            align="center",
        )

    def _render_complete(self, screen, content_rect, we):
        center_y = content_rect.centery - 40

        self.text.render(
            screen,
            "Patching Complete!",
            (content_rect.centerx, center_y),
            color=self.theme.success,
            size=self.theme.font_size_xl,
            align="center",
        )

        y = center_y + 35
        if we.patch_output_path:
            import os

            filename = os.path.basename(we.patch_output_path)
            self.text.render(
                screen,
                f"Saved: {filename}",
                (content_rect.centerx, y),
                color=self.theme.text_primary,
                size=self.theme.font_size_md,
                align="center",
                max_width=content_rect.width - 40,
            )
            y += 25

        # Show verification summary
        report = getattr(we, "patch_verify_report", "")
        if report:
            # Extract the summary line
            for line in report.split("\n"):
                if "Regions changed:" in line:
                    self.text.render(
                        screen,
                        line.strip(),
                        (content_rect.centerx, y),
                        color=self.theme.text_secondary,
                        size=self.theme.font_size_sm,
                        align="center",
                    )
                    y += 18
                elif "NO DATA CHANGED" in line:
                    self.text.render(
                        screen,
                        "WARNING: No bytes changed! Check console log.",
                        (content_rect.centerx, y),
                        color=self.theme.error,
                        size=self.theme.font_size_sm,
                        align="center",
                    )
                    y += 18
                elif "WRONG FORMAT" in line:
                    self.text.render(
                        screen,
                        "WARNING: ROM not Mode2/2352 format!",
                        (content_rect.centerx, y),
                        color=self.theme.error,
                        size=self.theme.font_size_sm,
                        align="center",
                    )
                    y += 18

        self.text.render(
            screen,
            "Press any button to close  (full report in console)",
            (content_rect.centerx, content_rect.bottom - 20),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
            align="center",
        )

    def _render_error(self, screen, content_rect, error):
        center_y = content_rect.centery - 30

        self.text.render(
            screen,
            "Patching Failed",
            (content_rect.centerx, center_y),
            color=self.theme.error,
            size=self.theme.font_size_xl,
            align="center",
        )

        self.text.render(
            screen,
            error,
            (content_rect.centerx, center_y + 40),
            color=self.theme.text_secondary,
            size=self.theme.font_size_md,
            align="center",
            max_width=content_rect.width - 40,
        )

        self.text.render(
            screen,
            "Press any button to close",
            (content_rect.centerx, content_rect.bottom - 20),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
            align="center",
        )


patch_progress_modal = PatchProgressModal()
