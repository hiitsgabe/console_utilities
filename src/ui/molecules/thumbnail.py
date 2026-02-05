"""
Thumbnail molecule - Image with placeholder and border.
"""

import pygame
from typing import Tuple, Optional

from ui.theme import Theme, Color, default_theme
from ui.atoms.text import Text


class Thumbnail:
    """
    Thumbnail molecule.

    Displays an image with a placeholder when no image
    is available, and optional selection border.
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.text = Text(theme)

    def render(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        image: Optional[pygame.Surface] = None,
        placeholder_text: str = "?",
        selected: bool = False,
        highlighted: bool = False,
        border_radius: Optional[int] = None,
    ) -> pygame.Rect:
        """
        Render a thumbnail.

        Args:
            screen: Surface to render to
            rect: Thumbnail rectangle
            image: Image surface to display
            placeholder_text: Text when no image (initials, etc)
            selected: Show selection border
            highlighted: Show highlight border
            border_radius: Corner radius

        Returns:
            Thumbnail rect
        """
        if border_radius is None:
            border_radius = self.theme.thumbnail_border_radius

        # Draw background/placeholder
        bg_color = self.theme.surface_hover if highlighted else self.theme.surface
        pygame.draw.rect(screen, bg_color, rect, border_radius=border_radius)

        if image and isinstance(image, pygame.Surface):
            # Scale image to fit
            img_size = min(rect.width, rect.height)
            scaled_img = pygame.transform.smoothscale(image, (img_size, img_size))

            # Center image in rect
            img_rect = scaled_img.get_rect(center=rect.center)
            screen.blit(scaled_img, img_rect)
        else:
            # Draw placeholder text
            self.text.render(
                screen,
                placeholder_text,
                rect.center,
                color=self.theme.text_disabled,
                size=self.theme.font_size_lg,
                align="center",
            )

        # Draw selection/highlight border
        if selected:
            pygame.draw.rect(
                screen, self.theme.primary, rect, width=3, border_radius=border_radius
            )
        elif highlighted:
            pygame.draw.rect(
                screen,
                self.theme.primary_light,
                rect,
                width=2,
                border_radius=border_radius,
            )

        return rect

    def render_with_label(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        label: str,
        image: Optional[pygame.Surface] = None,
        placeholder_text: str = "?",
        selected: bool = False,
        highlighted: bool = False,
    ) -> pygame.Rect:
        """
        Render a thumbnail with a label below.

        Args:
            screen: Surface to render to
            rect: Total area including label
            label: Label text
            image: Image surface
            placeholder_text: Placeholder when no image
            selected: Selection state
            highlighted: Highlight state

        Returns:
            Total rect
        """
        # Calculate thumbnail and label areas
        label_height = self.theme.font_size_sm + self.theme.padding_xs
        thumb_rect = pygame.Rect(
            rect.left, rect.top, rect.width, rect.height - label_height
        )

        # Render thumbnail
        self.render(
            screen,
            thumb_rect,
            image=image,
            placeholder_text=placeholder_text,
            selected=selected,
            highlighted=highlighted,
        )

        # Render label
        label_y = thumb_rect.bottom + self.theme.padding_xs
        self.text.render(
            screen,
            label,
            (rect.centerx, label_y),
            color=self.theme.text_primary if selected else self.theme.text_secondary,
            size=self.theme.font_size_sm,
            max_width=rect.width,
            align="center",
        )

        return rect

    def get_placeholder_initials(self, name: str, max_chars: int = 2) -> str:
        """
        Get initials from a name for placeholder.

        Args:
            name: Full name
            max_chars: Maximum initials to return

        Returns:
            Initials string (only alphanumeric characters)
        """
        if not name:
            return "?"

        # Remove file extension
        if "." in name:
            name = name.rsplit(".", 1)[0]

        # Replace common separators with spaces
        clean_name = name.replace("_", " ").replace("-", " ")

        # Remove region tags and special content in parentheses/brackets
        import re

        clean_name = re.sub(r"\([^)]*\)", "", clean_name)
        clean_name = re.sub(r"\[[^\]]*\]", "", clean_name)

        # Split into words and get initials from alphanumeric words only
        words = clean_name.split()
        initials = ""

        for word in words:
            # Find first alphanumeric character in word (letters and digits only)
            for char in word:
                if char.isalnum():
                    initials += char.upper()
                    break
            if len(initials) >= max_chars:
                break

        # Fallback if no valid initials found
        if not initials:
            # Try to get any alphanumeric character from original name
            for char in name:
                if char.isalnum():
                    initials += char.upper()
                    if len(initials) >= max_chars:
                        break

        return initials if initials else "?"


# Default instance
thumbnail = Thumbnail()
