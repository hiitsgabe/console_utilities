"""
Theme and design tokens for Console Utilities.
Centralizes all visual constants for consistent styling.
"""

import os
from dataclasses import dataclass
from typing import Tuple, Optional

from constants import BUILD_TARGET, SCRIPT_DIR

# Type alias for colors
Color = Tuple[int, int, int]
ColorAlpha = Tuple[int, int, int, int]


@dataclass(frozen=True)
class Theme:
    """
    Design tokens for the application UI.

    All visual constants are defined here for consistent theming.
    This class is immutable to prevent accidental modifications.
    """

    # ---- Base Colors ---- #
    background: Color = (0, 20, 0)  # Dark green CRT phosphor
    surface: Color = (0, 30, 0)
    surface_hover: Color = (0, 40, 0)
    surface_selected: Color = (0, 50, 5)

    # ---- Primary Accent (Phosphor Green) ---- #
    primary: Color = (0, 255, 65)
    primary_dark: Color = (0, 180, 45)
    primary_light: Color = (0, 255, 100)

    # ---- Secondary Accent (Amber) ---- #
    secondary: Color = (200, 200, 0)
    secondary_dark: Color = (160, 160, 0)
    secondary_light: Color = (230, 230, 50)

    # ---- Text Colors ---- #
    text_primary: Color = (0, 255, 65)
    text_secondary: Color = (0, 180, 45)
    text_disabled: Color = (0, 80, 20)

    # ---- Status Colors ---- #
    warning: Color = (200, 200, 0)
    error: Color = (255, 50, 30)
    success: Color = (0, 255, 65)

    # ---- Effects ---- #
    shadow: ColorAlpha = (0, 0, 0, 80)
    glow: ColorAlpha = (0, 255, 65, 40)

    # ---- Spacing ---- #
    padding_xs: int = 4
    padding_sm: int = 8
    padding_md: int = 16
    padding_lg: int = 24
    padding_xl: int = 32

    # ---- Typography ---- #
    font_size_xs: int = 16
    font_size_sm: int = 20
    font_size_md: int = 28
    font_size_lg: int = 36
    font_size_xl: int = 48
    font_path: Optional[str] = (
        os.path.join(SCRIPT_DIR, "assets", "fonts", "VT323-Regular.ttf")
        if os.path.exists(os.path.join(SCRIPT_DIR, "assets", "fonts", "VT323-Regular.ttf"))
        else os.path.normpath(os.path.join(SCRIPT_DIR, "..", "assets", "fonts", "VT323-Regular.ttf"))
    )

    # ---- Border Radius ---- #
    radius_sm: int = 0
    radius_md: int = 0
    radius_lg: int = 0
    radius_xl: int = 0

    # ---- Component Sizes ---- #
    header_height: int = 60
    button_height: int = 40
    menu_item_height: int = 50
    thumbnail_size: Tuple[int, int] = (96, 96)
    hires_image_size: Tuple[int, int] = (400, 400)
    grid_columns: int = 4
    char_button_size: int = 40

    # ---- Animation Timing ---- #
    transition_fast: int = 100  # ms
    transition_normal: int = 200  # ms
    transition_slow: int = 300  # ms
    cursor_blink_rate: int = 500  # ms

    # ---- Retro Theme Features ---- #
    crt_scanlines: bool = True
    menu_cursor: str = "> "

    @property
    def thumbnail_border_radius(self) -> int:
        """Border radius for thumbnails."""
        return self.radius_md

    @property
    def card_padding(self) -> int:
        """Default card padding."""
        return self.padding_sm

    @property
    def border_radius(self) -> int:
        """Default border radius."""
        return self.radius_lg


# Default theme instance
default_theme = Theme()


def create_scaled_theme(screen_w: int, screen_h: int) -> Theme:
    """Create a theme with font/spacing scaled to screen size (Android only).

    Uses the shorter screen dimension relative to 800x600 baseline so that
    portrait mode doesn't over-scale. On non-Android targets, returns default.
    """
    if BUILD_TARGET != "android":
        return Theme()

    short_side = min(screen_w, screen_h)
    scale = max(1.0, short_side / 480.0)

    def s(base: int) -> int:
        return round(base * scale)

    is_portrait = screen_h > screen_w

    return Theme(
        font_size_xs=s(16),
        font_size_sm=s(20),
        font_size_md=s(28),
        font_size_lg=s(36),
        font_size_xl=s(48),
        padding_xs=s(4),
        padding_sm=s(8),
        padding_md=s(16),
        padding_lg=s(24),
        padding_xl=s(32),
        header_height=s(60),
        button_height=s(40),
        menu_item_height=s(50),
        thumbnail_size=(s(96), s(96)),
        hires_image_size=(s(400), s(400)),
        char_button_size=s(40),
        grid_columns=3 if is_portrait else 4,
    )
