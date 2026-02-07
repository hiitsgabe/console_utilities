"""
Rename wizard modal - Game file name cleaning wizard.
"""

import pygame
from typing import List, Dict, Any, Tuple, Optional

from ui.theme import Theme, default_theme
from ui.organisms.modal_frame import ModalFrame
from ui.molecules.action_button import ActionButton
from ui.atoms.text import Text
from ui.atoms.progress import ProgressBar


class RenameWizardModal:
    """
    Rename wizard modal.

    Multi-step wizard for cleaning game file names.
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.modal_frame = ModalFrame(theme)
        self.action_button = ActionButton(theme)
        self.text = Text(theme)
        self.progress_bar = ProgressBar(theme)

    def render(
        self,
        screen: pygame.Surface,
        step: str,
        mode: str,
        rename_items: List[Dict[str, Any]],
        current_item_index: int,
        scan_progress: float,
        process_progress: float,
        files_scanned: int,
        total_files: int,
        files_renamed: int,
        error_message: str,
        mode_highlighted: int = 0,
        input_mode: str = "keyboard",
    ) -> Tuple[
        pygame.Rect,
        pygame.Rect,
        Optional[pygame.Rect],
        List[pygame.Rect],
    ]:
        """Render the rename wizard modal."""
        margin = 30
        width = screen.get_width() - margin * 2
        height = screen.get_height() - margin * 2

        modal_rect = pygame.Rect(margin, margin, width, height)

        title = self._get_step_title(step)

        _, content_rect, close_rect = self.modal_frame.render(
            screen, modal_rect, title=title, show_close=True
        )

        item_rects = []

        if step == "mode_select":
            item_rects = self._render_mode_select(
                screen, content_rect, mode_highlighted, input_mode
            )
        elif step == "scanning":
            self._render_scanning(
                screen,
                content_rect,
                scan_progress,
                files_scanned,
                total_files,
            )
        elif step == "review":
            item_rects = self._render_review(
                screen,
                content_rect,
                mode,
                rename_items,
                current_item_index,
                input_mode,
            )
        elif step == "processing":
            self._render_processing(screen, content_rect, process_progress)
        elif step == "complete":
            self._render_complete(screen, content_rect, files_renamed)
        elif step == "error":
            self._render_error(screen, content_rect, error_message)
        elif step == "no_changes":
            self._render_no_changes(screen, content_rect)

        return modal_rect, content_rect, close_rect, item_rects

    def _get_step_title(self, step: str) -> str:
        """Get title for current step."""
        titles = {
            "mode_select": "Clean File Names - Select Mode",
            "scanning": "Clean File Names - Scanning",
            "review": "Clean File Names - Review",
            "processing": "Clean File Names - Processing",
            "complete": "Clean File Names - Complete",
            "error": "Clean File Names - Error",
            "no_changes": "Clean File Names - No Changes",
        }
        return titles.get(step, "Clean File Names")

    def _render_mode_select(
        self,
        screen: pygame.Surface,
        content_rect: pygame.Rect,
        mode_highlighted: int,
        input_mode: str,
    ) -> List[pygame.Rect]:
        """Render mode selection step."""
        item_rects = []

        y = content_rect.top + self.theme.padding_lg
        self.text.render(
            screen,
            "Select cleaning mode:",
            (content_rect.centerx, y),
            color=self.theme.text_primary,
            size=self.theme.font_size_md,
            align="center",
        )
        y += self.theme.font_size_md + self.theme.padding_lg * 2

        modes = [
            {
                "name": "Automatic",
                "desc": "Remove all parenthetical annotations",
                "desc2": "and rename files automatically.",
            },
            {
                "name": "Manual",
                "desc": "Review each rename proposal and",
                "desc2": "choose which files to rename.",
            },
        ]

        for i, mode_info in enumerate(modes):
            box_height = 80
            box_rect = pygame.Rect(
                content_rect.left + self.theme.padding_lg,
                y,
                content_rect.width - self.theme.padding_lg * 2,
                box_height,
            )
            item_rects.append(box_rect)

            if i == mode_highlighted:
                pygame.draw.rect(
                    screen,
                    self.theme.primary,
                    box_rect,
                    border_radius=8,
                )
                text_color = self.theme.text_primary
            else:
                pygame.draw.rect(
                    screen,
                    self.theme.surface,
                    box_rect,
                    border_radius=8,
                )
                text_color = self.theme.text_secondary

            self.text.render(
                screen,
                mode_info["name"],
                (
                    box_rect.left + self.theme.padding_md,
                    box_rect.top + 15,
                ),
                color=text_color,
                size=self.theme.font_size_lg,
            )

            desc_color = (
                self.theme.text_primary
                if i == mode_highlighted
                else self.theme.text_secondary
            )
            self.text.render(
                screen,
                mode_info["desc"],
                (
                    box_rect.left + self.theme.padding_md,
                    box_rect.top + 40,
                ),
                color=desc_color,
                size=self.theme.font_size_sm,
            )
            self.text.render(
                screen,
                mode_info["desc2"],
                (
                    box_rect.left + self.theme.padding_md,
                    box_rect.top + 58,
                ),
                color=desc_color,
                size=self.theme.font_size_sm,
            )

            y += box_height + self.theme.padding_md

        hint = "[A] Select" if input_mode == "gamepad" else "Press Enter to select"
        self.text.render(
            screen,
            hint,
            (content_rect.centerx, content_rect.bottom - 30),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
            align="center",
        )

        return item_rects

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
            "Scanning for game files...",
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
            f"{files_scanned} / {total_files} files",
            (content_rect.centerx, center_y + 80),
            color=self.theme.text_secondary,
            size=self.theme.font_size_md,
            align="center",
        )

    def _render_review(
        self,
        screen: pygame.Surface,
        content_rect: pygame.Rect,
        mode: str,
        rename_items: List[Dict[str, Any]],
        current_item_index: int,
        input_mode: str,
    ) -> List[pygame.Rect]:
        """Render rename review step."""
        item_rects = []

        if not rename_items:
            return item_rects

        total_items = len(rename_items)
        y = content_rect.top

        if mode == "automatic":
            # Show summary list of all renames
            self.text.render(
                screen,
                f"{total_items} files will be renamed:",
                (content_rect.centerx, y),
                color=self.theme.text_primary,
                size=self.theme.font_size_lg,
                align="center",
            )
            y += self.theme.font_size_lg + self.theme.padding_md

            # Show visible items around current index
            visible = min(6, total_items)
            start = max(
                0,
                min(
                    current_item_index - visible // 2,
                    total_items - visible,
                ),
            )
            end = min(start + visible, total_items)

            for i in range(start, end):
                item = rename_items[i]
                box_height = 42
                box_rect = pygame.Rect(
                    content_rect.left + self.theme.padding_sm,
                    y,
                    content_rect.width - self.theme.padding_sm * 2,
                    box_height,
                )
                item_rects.append(box_rect)

                if i == current_item_index:
                    pygame.draw.rect(
                        screen,
                        self.theme.primary,
                        box_rect,
                        border_radius=6,
                    )
                else:
                    pygame.draw.rect(
                        screen,
                        self.theme.surface,
                        box_rect,
                        border_radius=6,
                    )

                self.text.render(
                    screen,
                    item["original_name"],
                    (box_rect.left + 10, box_rect.top + 4),
                    color=self.theme.text_secondary,
                    size=self.theme.font_size_sm,
                    max_width=box_rect.width - 20,
                )
                self.text.render(
                    screen,
                    f"-> {item['new_name']}",
                    (box_rect.left + 10, box_rect.top + 22),
                    color=self.theme.success,
                    size=self.theme.font_size_sm,
                    max_width=box_rect.width - 20,
                )

                y += box_height + 4

            hint = "L/R: Scroll, [A] Rename all, [B] Cancel"
            self.text.render(
                screen,
                hint,
                (
                    content_rect.centerx,
                    content_rect.bottom - 30,
                ),
                color=self.theme.text_secondary,
                size=self.theme.font_size_sm,
                align="center",
            )
        else:
            # Manual mode - one file at a time
            item = rename_items[current_item_index]
            self.text.render(
                screen,
                f"File {current_item_index + 1} of" f" {total_items}",
                (content_rect.centerx, y),
                color=self.theme.text_primary,
                size=self.theme.font_size_lg,
                align="center",
            )
            y += self.theme.font_size_lg + self.theme.padding_lg * 2

            # Original name
            self.text.render(
                screen,
                "Original:",
                (content_rect.left, y),
                color=self.theme.text_secondary,
                size=self.theme.font_size_md,
            )
            y += self.theme.font_size_md + self.theme.padding_sm
            self.text.render(
                screen,
                item["original_name"],
                (content_rect.left + 10, y),
                color=self.theme.text_primary,
                size=self.theme.font_size_md,
                max_width=content_rect.width - 20,
            )
            y += self.theme.font_size_md + self.theme.padding_lg * 2

            # New name
            self.text.render(
                screen,
                "Clean name:",
                (content_rect.left, y),
                color=self.theme.text_secondary,
                size=self.theme.font_size_md,
            )
            y += self.theme.font_size_md + self.theme.padding_sm
            self.text.render(
                screen,
                item["new_name"],
                (content_rect.left + 10, y),
                color=self.theme.success,
                size=self.theme.font_size_md,
                max_width=content_rect.width - 20,
            )
            y += self.theme.font_size_md + self.theme.padding_lg * 2

            # Include/exclude status
            selected = item.get("selected", True)
            status = "INCLUDED" if selected else "EXCLUDED"
            status_color = self.theme.success if selected else self.theme.error
            self.text.render(
                screen,
                f"Status: {status}",
                (content_rect.centerx, y),
                color=status_color,
                size=self.theme.font_size_lg,
                align="center",
            )

            hint = "L/R: Prev/Next, [A] Toggle," " [B] Cancel, Start: Confirm"
            self.text.render(
                screen,
                hint,
                (
                    content_rect.centerx,
                    content_rect.bottom - 30,
                ),
                color=self.theme.text_secondary,
                size=self.theme.font_size_sm,
                align="center",
            )

        return item_rects

    def _render_processing(
        self,
        screen: pygame.Surface,
        content_rect: pygame.Rect,
        progress: float,
    ) -> None:
        """Render processing progress."""
        center_y = content_rect.centery - 20

        self.text.render(
            screen,
            "Renaming files...",
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
        files_renamed: int,
    ) -> None:
        """Render completion screen."""
        center_y = content_rect.centery - 30

        self.text.render(
            screen,
            "Renaming Complete!",
            (content_rect.centerx, center_y),
            color=self.theme.success,
            size=self.theme.font_size_xl,
            align="center",
        )

        self.text.render(
            screen,
            f"Files renamed: {files_renamed}",
            (content_rect.centerx, center_y + 50),
            color=self.theme.text_primary,
            size=self.theme.font_size_lg,
            align="center",
        )

        self.text.render(
            screen,
            "Press any button to close",
            (
                content_rect.centerx,
                content_rect.bottom - 30,
            ),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
            align="center",
        )

    def _render_no_changes(
        self,
        screen: pygame.Surface,
        content_rect: pygame.Rect,
    ) -> None:
        """Render no changes needed screen."""
        center_y = content_rect.centery - 20

        self.text.render(
            screen,
            "No files need renaming!",
            (content_rect.centerx, center_y),
            color=self.theme.success,
            size=self.theme.font_size_xl,
            align="center",
        )

        self.text.render(
            screen,
            "All file names are already clean.",
            (content_rect.centerx, center_y + 50),
            color=self.theme.text_secondary,
            size=self.theme.font_size_md,
            align="center",
        )

        self.text.render(
            screen,
            "Press any button to close",
            (
                content_rect.centerx,
                content_rect.bottom - 30,
            ),
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
            (
                content_rect.centerx,
                content_rect.bottom - 30,
            ),
            color=self.theme.text_secondary,
            size=self.theme.font_size_sm,
            align="center",
        )


rename_wizard_modal = RenameWizardModal()
