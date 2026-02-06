"""
Dedupe wizard modal - Game deduplication wizard.
"""

import pygame
from typing import List, Dict, Any, Tuple, Optional

from ui.theme import Theme, default_theme
from ui.organisms.modal_frame import ModalFrame
from ui.molecules.action_button import ActionButton
from ui.atoms.text import Text
from ui.atoms.progress import ProgressBar
from services.dedupe_service import format_size


class DedupeWizardModal:
    """
    Dedupe wizard modal.

    Multi-step wizard for deduplicating game files in a folder.
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
        folder_path: str,
        folder_items: List[Dict[str, Any]],
        folder_highlighted: int,
        duplicate_groups: List[List[Dict[str, Any]]],
        current_group_index: int,
        selected_to_keep: int,
        scan_progress: float,
        process_progress: float,
        files_scanned: int,
        total_files: int,
        files_removed: int,
        space_freed: int,
        error_message: str,
        mode_highlighted: int = 0,
        input_mode: str = "keyboard",
    ) -> Tuple[pygame.Rect, pygame.Rect, Optional[pygame.Rect], List[pygame.Rect]]:
        """
        Render the dedupe wizard modal.

        Returns:
            Tuple of (modal_rect, content_rect, close_rect, item_rects)
        """
        # Modal size
        margin = 30
        width = screen.get_width() - margin * 2
        height = screen.get_height() - margin * 2

        modal_rect = pygame.Rect(margin, margin, width, height)

        # Get title based on step
        title = self._get_step_title(step)

        # Render modal frame
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
                screen, content_rect, scan_progress, files_scanned, total_files
            )
        elif step == "review":
            item_rects = self._render_review(
                screen,
                content_rect,
                mode,
                duplicate_groups,
                current_group_index,
                selected_to_keep,
                input_mode,
            )
        elif step == "processing":
            self._render_processing(screen, content_rect, process_progress)
        elif step == "complete":
            self._render_complete(screen, content_rect, files_removed, space_freed)
        elif step == "error":
            self._render_error(screen, content_rect, error_message)
        elif step == "no_duplicates":
            self._render_no_duplicates(screen, content_rect)

        return modal_rect, content_rect, close_rect, item_rects

    def _get_step_title(self, step: str) -> str:
        """Get title for current step."""
        titles = {
            "mode_select": "Dedupe Games - Select Mode",
            "folder_select": "Dedupe Games - Select Folder",
            "scanning": "Dedupe Games - Scanning",
            "review": "Dedupe Games - Review Duplicates",
            "processing": "Dedupe Games - Processing",
            "complete": "Dedupe Games - Complete",
            "error": "Dedupe Games - Error",
            "no_duplicates": "Dedupe Games - No Duplicates",
        }
        return titles.get(step, "Dedupe Games")

    def _render_mode_select(
        self,
        screen: pygame.Surface,
        content_rect: pygame.Rect,
        mode_highlighted: int,
        input_mode: str,
    ) -> List[pygame.Rect]:
        """Render mode selection step."""
        item_rects = []

        # Instructions
        y = content_rect.top + self.theme.padding_lg
        self.text.render(
            screen,
            "Select deduplication mode:",
            (content_rect.centerx, y),
            color=self.theme.text_primary,
            size=self.theme.font_size_md,
            align="center",
        )
        y += self.theme.font_size_md + self.theme.padding_lg * 2

        # Mode options
        modes = [
            {
                "name": "Safe Mode (Automatic)",
                "description": "Normalizes names by removing region codes, versions,",
                "description2": "disc numbers, etc. Automatically keeps larger files.",
            },
            {
                "name": "Manual Mode (90% Match)",
                "description": "Uses fuzzy matching to find similar names.",
                "description2": "You choose which file to keep for each duplicate.",
            },
        ]

        for i, mode_info in enumerate(modes):
            # Draw option box
            box_height = 80
            box_rect = pygame.Rect(
                content_rect.left + self.theme.padding_lg,
                y,
                content_rect.width - self.theme.padding_lg * 2,
                box_height,
            )
            item_rects.append(box_rect)

            # Highlight if selected
            if i == mode_highlighted:
                pygame.draw.rect(screen, self.theme.primary, box_rect, border_radius=8)
                text_color = self.theme.text_primary
            else:
                pygame.draw.rect(screen, self.theme.surface, box_rect, border_radius=8)
                text_color = self.theme.text_secondary

            # Mode name
            self.text.render(
                screen,
                mode_info["name"],
                (box_rect.left + self.theme.padding_md, box_rect.top + 15),
                color=text_color,
                size=self.theme.font_size_lg,
            )

            # Description lines
            self.text.render(
                screen,
                mode_info["description"],
                (box_rect.left + self.theme.padding_md, box_rect.top + 40),
                color=(
                    self.theme.text_secondary
                    if i != mode_highlighted
                    else self.theme.text_primary
                ),
                size=self.theme.font_size_sm,
            )
            self.text.render(
                screen,
                mode_info["description2"],
                (box_rect.left + self.theme.padding_md, box_rect.top + 58),
                color=(
                    self.theme.text_secondary
                    if i != mode_highlighted
                    else self.theme.text_primary
                ),
                size=self.theme.font_size_sm,
            )

            y += box_height + self.theme.padding_md

        # Hint
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

        # Message
        self.text.render(
            screen,
            "Scanning for game files...",
            (content_rect.centerx, center_y),
            color=self.theme.text_primary,
            size=self.theme.font_size_lg,
            align="center",
        )

        # Progress bar
        bar_width = min(400, content_rect.width - 80)
        bar_rect = pygame.Rect(
            content_rect.centerx - bar_width // 2,
            center_y + 40,
            bar_width,
            20,
        )
        self.progress_bar.render(screen, bar_rect, progress)

        # File count
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
        duplicate_groups: List[List[Dict[str, Any]]],
        current_group_index: int,
        selected_to_keep: int,
        input_mode: str,
    ) -> List[pygame.Rect]:
        """Render duplicate review step."""
        item_rects = []

        if not duplicate_groups:
            return item_rects

        total_groups = len(duplicate_groups)
        current_group = duplicate_groups[current_group_index]

        # Header with count
        y = content_rect.top
        self.text.render(
            screen,
            f"Duplicate Group {current_group_index + 1} of {total_groups}",
            (content_rect.centerx, y),
            color=self.theme.text_primary,
            size=self.theme.font_size_lg,
            align="center",
        )
        y += self.theme.font_size_lg + self.theme.padding_md

        if mode == "safe":
            # Safe mode - show auto selection
            self.text.render(
                screen,
                "Will keep (largest file):",
                (content_rect.left, y),
                color=self.theme.success,
                size=self.theme.font_size_md,
            )
            y += self.theme.font_size_md + self.theme.padding_sm

            # Show file to keep
            keep_file = current_group[0]
            self.text.render(
                screen,
                f"  {keep_file['name']}",
                (content_rect.left, y),
                color=self.theme.text_primary,
                size=self.theme.font_size_sm,
                max_width=content_rect.width - 20,
            )
            y += self.theme.font_size_sm + 4
            self.text.render(
                screen,
                f"  Size: {format_size(keep_file['size'])}",
                (content_rect.left, y),
                color=self.theme.text_secondary,
                size=self.theme.font_size_sm,
            )
            y += self.theme.font_size_sm + self.theme.padding_lg

            # Files to remove
            self.text.render(
                screen,
                "Will remove:",
                (content_rect.left, y),
                color=self.theme.error,
                size=self.theme.font_size_md,
            )
            y += self.theme.font_size_md + self.theme.padding_sm

            for file in current_group[1:]:
                self.text.render(
                    screen,
                    f"  {file['name']}",
                    (content_rect.left, y),
                    color=self.theme.text_secondary,
                    size=self.theme.font_size_sm,
                    max_width=content_rect.width - 20,
                )
                y += self.theme.font_size_sm + 4
                self.text.render(
                    screen,
                    f"  Size: {format_size(file['size'])}",
                    (content_rect.left, y),
                    color=self.theme.text_secondary,
                    size=self.theme.font_size_sm,
                )
                y += self.theme.font_size_sm + self.theme.padding_sm
        else:
            # Manual mode - user selects which to keep
            self.text.render(
                screen,
                "Select which file to KEEP:",
                (content_rect.left, y),
                color=self.theme.text_primary,
                size=self.theme.font_size_md,
            )
            y += self.theme.font_size_md + self.theme.padding_md

            for i, file in enumerate(current_group):
                box_height = 50
                box_rect = pygame.Rect(
                    content_rect.left + self.theme.padding_sm,
                    y,
                    content_rect.width - self.theme.padding_sm * 2,
                    box_height,
                )
                item_rects.append(box_rect)

                # Highlight selected
                if i == selected_to_keep:
                    pygame.draw.rect(
                        screen, self.theme.success, box_rect, border_radius=6
                    )
                    label = "[KEEP] "
                else:
                    pygame.draw.rect(
                        screen, self.theme.surface, box_rect, border_radius=6
                    )
                    label = ""

                # File name
                self.text.render(
                    screen,
                    f"{label}{file['name']}",
                    (box_rect.left + 10, box_rect.top + 10),
                    color=self.theme.text_primary,
                    size=self.theme.font_size_sm,
                    max_width=box_rect.width - 20,
                )
                # Size
                self.text.render(
                    screen,
                    f"Size: {format_size(file['size'])}",
                    (box_rect.left + 10, box_rect.top + 30),
                    color=self.theme.text_secondary,
                    size=self.theme.font_size_sm,
                )

                y += box_height + self.theme.padding_sm

        # Navigation hints
        if mode == "safe":
            hint = "L/R: Prev/Next group, [A] Process all, [B] Cancel"
        else:
            hint = "Up/Down: Select, L/R: Prev/Next, [A] Confirm, [B] Cancel"

        self.text.render(
            screen,
            hint,
            (content_rect.centerx, content_rect.bottom - 30),
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
            "Removing duplicate files...",
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
            "Deduplication Complete!",
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

    def _render_no_duplicates(
        self,
        screen: pygame.Surface,
        content_rect: pygame.Rect,
    ) -> None:
        """Render no duplicates found screen."""
        center_y = content_rect.centery - 20

        self.text.render(
            screen,
            "No duplicates found!",
            (content_rect.centerx, center_y),
            color=self.theme.success,
            size=self.theme.font_size_xl,
            align="center",
        )

        self.text.render(
            screen,
            "This folder contains no duplicate game files.",
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
dedupe_wizard_modal = DedupeWizardModal()
