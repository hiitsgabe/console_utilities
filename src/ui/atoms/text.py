"""
Text atom - Basic text rendering component.
"""

import pygame
from typing import Tuple, Optional

from ui.theme import Theme, Color, default_theme


class Text:
    """
    Basic text rendering atom.

    Handles text rendering with various styles, truncation,
    and alignment options.
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self._font_cache: dict = {}

    def get_font(self, size: int) -> pygame.font.Font:
        """Get or create a font of the given size."""
        if size not in self._font_cache:
            font_path = getattr(self.theme, "font_path", None)
            self._font_cache[size] = pygame.font.Font(font_path, size)
        return self._font_cache[size]

    def render(
        self,
        screen: pygame.Surface,
        text: str,
        position: Tuple[int, int],
        color: Optional[Color] = None,
        size: Optional[int] = None,
        max_width: Optional[int] = None,
        align: str = "left",  # "left", "center", "right"
        antialias: bool = True,
    ) -> pygame.Rect:
        """
        Render text to the screen.

        Args:
            screen: Surface to render to
            text: Text to render
            position: (x, y) position
            color: Text color (default: text_primary)
            size: Font size (default: font_size_md)
            max_width: Maximum width (truncate with ellipsis if exceeded)
            align: Text alignment ("left", "center", "right")
            antialias: Use antialiasing

        Returns:
            Rect of rendered text
        """
        if color is None:
            color = self.theme.text_primary
        if size is None:
            size = self.theme.font_size_md

        font = self.get_font(size)

        # Truncate if needed
        if max_width:
            text = self._truncate(text, font, max_width)

        surface = font.render(text, antialias, color)
        rect = surface.get_rect()

        # Apply alignment
        x, y = position
        if align == "center":
            rect.centerx = x
            rect.top = y
        elif align == "right":
            rect.right = x
            rect.top = y
        else:  # left
            rect.topleft = position

        screen.blit(surface, rect)
        return rect

    def render_multiline(
        self,
        screen: pygame.Surface,
        text: str,
        position: Tuple[int, int],
        color: Optional[Color] = None,
        size: Optional[int] = None,
        max_width: Optional[int] = None,
        line_spacing: int = 4,
        align: str = "left",
    ) -> pygame.Rect:
        """
        Render multiline text.

        Args:
            screen: Surface to render to
            text: Text to render (can contain newlines)
            position: (x, y) position
            color: Text color
            size: Font size
            max_width: Maximum width per line
            line_spacing: Space between lines
            align: Text alignment

        Returns:
            Bounding rect of all rendered text
        """
        if color is None:
            color = self.theme.text_primary
        if size is None:
            size = self.theme.font_size_md

        font = self.get_font(size)
        lines = text.split("\n")

        x, y = position
        total_rect = pygame.Rect(x, y, 0, 0)

        for line in lines:
            rect = self.render(
                screen,
                line,
                (x, y),
                color=color,
                size=size,
                max_width=max_width,
                align=align,
            )
            y += rect.height + line_spacing
            total_rect = total_rect.union(rect)

        return total_rect

    def measure(self, text: str, size: Optional[int] = None) -> Tuple[int, int]:
        """
        Measure text dimensions without rendering.

        Args:
            text: Text to measure
            size: Font size

        Returns:
            (width, height) tuple
        """
        if size is None:
            size = self.theme.font_size_md

        font = self.get_font(size)
        return font.size(text)

    def render_rainbow(
        self,
        screen: pygame.Surface,
        text: str,
        position: Tuple[int, int],
        size: Optional[int] = None,
        align: str = "center",
        antialias: bool = True,
    ) -> pygame.Rect:
        """
        Render text with rainbow colors (each character a different color).

        Args:
            screen: Surface to render to
            text: Text to render
            position: (x, y) position
            size: Font size (default: font_size_md)
            align: Text alignment ("left", "center", "right")
            antialias: Use antialiasing

        Returns:
            Rect of rendered text
        """
        if size is None:
            size = self.theme.font_size_md

        # Green phosphor gradient for retro terminal look
        rainbow_colors = [
            self.theme.primary,
            self.theme.primary_light,
            self.theme.secondary,
            self.theme.primary,
            self.theme.primary_dark,
            self.theme.primary_light,
            self.theme.primary,
        ]

        font = self.get_font(size)

        # Calculate total width for alignment
        total_width, total_height = font.size(text)

        # Determine starting x position based on alignment
        x, y = position
        if align == "center":
            x = x - total_width // 2
        elif align == "right":
            x = x - total_width

        # Render each character with a different color
        current_x = x
        first_rect = None
        last_rect = None

        for i, char in enumerate(text):
            if char == " ":
                # Just advance position for spaces
                char_width = font.size(" ")[0]
                current_x += char_width
                continue

            color = rainbow_colors[i % len(rainbow_colors)]
            char_surface = font.render(char, antialias, color)
            char_rect = char_surface.get_rect(topleft=(current_x, y))
            screen.blit(char_surface, char_rect)

            if first_rect is None:
                first_rect = char_rect
            last_rect = char_rect

            current_x += char_rect.width

        # Return bounding rect
        if first_rect and last_rect:
            return pygame.Rect(
                first_rect.left,
                first_rect.top,
                last_rect.right - first_rect.left,
                total_height,
            )
        return pygame.Rect(x, y, total_width, total_height)

    def _truncate(
        self, text: str, font: pygame.font.Font, max_width: int, suffix: str = "..."
    ) -> str:
        """
        Truncate text to fit within max_width.

        Args:
            text: Text to truncate
            font: Font to use for measurement
            max_width: Maximum width in pixels
            suffix: Suffix to add when truncating

        Returns:
            Truncated text
        """
        if font.size(text)[0] <= max_width:
            return text

        suffix_width = font.size(suffix)[0]
        available_width = max_width - suffix_width

        # Binary search for optimal truncation point
        low, high = 0, len(text)
        while low < high:
            mid = (low + high + 1) // 2
            if font.size(text[:mid])[0] <= available_width:
                low = mid
            else:
                high = mid - 1

        return text[:low] + suffix


# Default instance
text = Text()
