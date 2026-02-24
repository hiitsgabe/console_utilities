"""
Port details modal - Shows port information and download option.
"""

import pygame
from typing import Dict, Any, Tuple, Optional

from ui.theme import Theme, default_theme
from ui.organisms.modal_frame import ModalFrame
from ui.molecules.thumbnail import Thumbnail
from ui.molecules.action_button import ActionButton
from ui.atoms.text import Text
from utils.button_hints import get_game_details_hints


class PortDetailsModal:
    """
    Port details modal.

    Displays detailed information about a PortMaster port
    with screenshot, description, and download option.

    Vertical layout:
    - Port title
    - Screenshot image
    - Description
    - Genres, RTR badge, file size, porter
    - Download button
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.modal_frame = ModalFrame(theme)
        self.thumbnail = Thumbnail(theme)
        self.action_button = ActionButton(theme)
        self.text = Text(theme)

    def render(
        self,
        screen: pygame.Surface,
        port: Dict[str, Any],
        hires_image: Optional[pygame.Surface] = None,
        button_focused: bool = True,
        input_mode: str = "keyboard",
        text_scroll_offset: int = 0,
    ) -> Tuple[pygame.Rect, Optional[pygame.Rect], Optional[pygame.Rect]]:
        """
        Render the port details modal.

        Args:
            screen: Surface to render to
            port: Port data dictionary
            hires_image: Optional screenshot image
            button_focused: Whether download button is focused
            input_mode: Current input mode
            text_scroll_offset: Horizontal text scroll offset

        Returns:
            Tuple of (modal_rect, download_button_rect, close_button_rect)
        """
        screen_width, screen_height = screen.get_size()

        # Make modal bigger - use most of the screen
        width = min(500, screen_width - 40)
        height = min(screen_height - 60, 600)

        # Render modal frame
        show_close = input_mode == "touch"
        modal_rect, content_rect, close_rect = self.modal_frame.render_centered(
            screen, width, height, title="Port Details", show_close=show_close
        )

        # Vertical layout - centered
        center_x = content_rect.centerx
        y = content_rect.top

        # Port title at top
        port_title = port.get("title", "Unknown Port")
        name_max_width = content_rect.width - self.theme.padding_md * 2
        if text_scroll_offset > 0:
            self.text.render_scrolled(
                screen,
                port_title,
                (content_rect.left + self.theme.padding_md, y),
                max_width=name_max_width,
                scroll_offset=text_scroll_offset,
                color=self.theme.text_primary,
                size=self.theme.font_size_lg,
            )
        else:
            self.text.render(
                screen,
                port_title,
                (center_x, y),
                color=self.theme.text_primary,
                size=self.theme.font_size_lg,
                max_width=name_max_width,
                align="center",
            )
        y += self.theme.font_size_lg + self.theme.padding_sm

        # Calculate space for image
        reserved_height = (
            self.theme.font_size_sm * 4  # desc, genres, size, porter
            + self.theme.padding_sm * 5
            + 50  # button height
            + self.theme.padding_md
        )

        available_for_image = content_rect.bottom - y - reserved_height
        image_size = min(
            available_for_image,
            content_rect.width - self.theme.padding_md * 2,
            250,
        )
        image_size = max(image_size, 80)

        # Screenshot image (centered)
        image_rect = pygame.Rect(center_x - image_size // 2, y, image_size, image_size)
        placeholder = self.thumbnail.get_placeholder_initials(port_title)
        self.thumbnail.render(
            screen, image_rect, image=hires_image, placeholder_text=placeholder
        )
        y += image_size + self.theme.padding_sm

        # Description (centered, truncated)
        desc = port.get("desc", "")
        if desc:
            # Truncate long descriptions
            if len(desc) > 120:
                desc = desc[:117] + "..."
            self.text.render(
                screen,
                desc,
                (center_x, y),
                color=self.theme.text_secondary,
                size=self.theme.font_size_sm,
                max_width=content_rect.width - self.theme.padding_sm * 2,
                align="center",
            )
            y += self.theme.font_size_sm + self.theme.padding_sm

        # Genres + RTR badge
        genres = port.get("genres", [])
        rtr = port.get("rtr", False)
        info_parts = []
        if genres:
            info_parts.append(", ".join(genres))
        if rtr:
            info_parts.append("Ready to Run")
        if info_parts:
            self.text.render(
                screen,
                " | ".join(info_parts),
                (center_x, y),
                color=self.theme.primary if rtr else self.theme.text_secondary,
                size=self.theme.font_size_sm,
                max_width=content_rect.width - self.theme.padding_sm * 2,
                align="center",
            )
            y += self.theme.font_size_sm + self.theme.padding_sm

        # File size
        size_str = self._format_bytes(port.get("download_size", 0))
        if size_str:
            self.text.render(
                screen,
                f"Size: {size_str}",
                (center_x, y),
                color=self.theme.text_secondary,
                size=self.theme.font_size_sm,
                align="center",
            )
            y += self.theme.font_size_sm + self.theme.padding_sm

        # Porter credit
        porter = port.get("porter", [])
        if porter:
            self.text.render(
                screen,
                f"Porter: {', '.join(porter)}",
                (center_x, y),
                color=self.theme.text_secondary,
                size=self.theme.font_size_sm,
                align="center",
            )

        # Bottom section - button or hints
        download_rect = None

        if input_mode == "touch":
            button_width = 150
            button_height = 45
            download_rect = pygame.Rect(
                center_x - button_width // 2,
                content_rect.bottom - button_height - self.theme.padding_sm,
                button_width,
                button_height,
            )
            self.action_button.render(
                screen, download_rect, "Download", hover=button_focused
            )
        else:
            hints = get_game_details_hints(input_mode)
            self.text.render(
                screen,
                hints,
                (center_x, content_rect.bottom - self.theme.padding_md),
                color=self.theme.text_secondary,
                size=self.theme.font_size_sm,
                align="center",
            )

        return modal_rect, download_rect, close_rect

    def _format_bytes(self, size: int) -> str:
        """Format bytes to human readable string."""
        if not size:
            return ""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0:
                return (
                    f"{size:.1f} {unit}" if size != int(size) else f"{int(size)} {unit}"
                )
            size /= 1024.0
        return f"{size:.1f} PB"


# Default instance
port_details_modal = PortDetailsModal()
