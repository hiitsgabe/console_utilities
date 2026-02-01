"""
Theme and design tokens for Console Utilities.
Centralizes all visual constants for consistent styling.
"""

from dataclasses import dataclass
from typing import Tuple

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
    background: Color = (18, 20, 24)
    surface: Color = (30, 34, 40)
    surface_hover: Color = (40, 44, 50)
    surface_selected: Color = (45, 50, 60)

    # ---- Primary Accent (Blue) ---- #
    primary: Color = (66, 165, 245)
    primary_dark: Color = (48, 123, 184)
    primary_light: Color = (100, 181, 246)

    # ---- Secondary Accent (Green) ---- #
    secondary: Color = (102, 187, 106)
    secondary_dark: Color = (76, 140, 79)
    secondary_light: Color = (129, 199, 132)

    # ---- Text Colors ---- #
    text_primary: Color = (255, 255, 255)
    text_secondary: Color = (189, 189, 189)
    text_disabled: Color = (117, 117, 117)

    # ---- Status Colors ---- #
    warning: Color = (255, 193, 7)
    error: Color = (244, 67, 54)
    success: Color = (76, 175, 80)

    # ---- Effects ---- #
    shadow: ColorAlpha = (0, 0, 0, 60)
    glow: ColorAlpha = (66, 165, 245, 40)

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

    # ---- Border Radius ---- #
    radius_sm: int = 4
    radius_md: int = 8
    radius_lg: int = 12
    radius_xl: int = 16

    # ---- Component Sizes ---- #
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
