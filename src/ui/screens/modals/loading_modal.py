"""
Loading modal - Progress display during operations.
"""

import pygame
from typing import Optional

from ui.theme import Theme, default_theme
from ui.templates.modal_template import ModalTemplate


class LoadingModal:
    """
    Loading modal.

    Displays loading/progress information during
    operations like downloads or data loading.
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.modal_template = ModalTemplate(theme)

    def render(
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
        return self.modal_template.render_loading(screen, message, progress)

    def render_download(
        self,
        screen: pygame.Surface,
        filename: str,
        progress: float,
        downloaded: int = 0,
        total_size: int = 0,
        speed: float = 0,
    ) -> pygame.Rect:
        """
        Render a download progress modal.

        Args:
            screen: Surface to render to
            filename: Name of file being downloaded
            progress: Download progress (0.0 to 1.0)
            downloaded: Bytes downloaded
            total_size: Total file size
            speed: Download speed in bytes/second

        Returns:
            Modal rect
        """
        from ui.molecules.download_progress import DownloadProgress
        from ui.organisms.modal_frame import ModalFrame

        modal_frame = ModalFrame(self.theme)
        download_progress = DownloadProgress(self.theme)

        # Modal size
        width = 400
        height = 150

        # Render modal frame
        modal_rect, content_rect, _ = modal_frame.render_centered(
            screen, width, height, title="Downloading", show_close=False
        )

        # Render progress
        download_progress.render(
            screen,
            content_rect,
            progress=progress,
            label=filename,
            downloaded=downloaded,
            total_size=total_size,
            speed=speed,
        )

        return modal_rect


# Default instance
loading_modal = LoadingModal()
