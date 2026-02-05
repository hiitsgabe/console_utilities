"""
Global constants for Console Utilities application.
Contains path configuration, display settings, colors, and timing constants.
"""

import os

# **************************************************************** #
#                       Environment Detection                        #
# **************************************************************** #
DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"

# Detect if running from a zip bundle (e.g., .pygame file)
_raw_script_dir = os.path.dirname(os.path.abspath(__file__))
if ".pygame" in _raw_script_dir or ".zip" in _raw_script_dir:
    # Running from zip - use the directory containing the zip file
    SCRIPT_DIR = os.path.dirname(
        _raw_script_dir.split(".pygame")[0].split(".zip")[0] + ".pygame"
    )
else:
    SCRIPT_DIR = _raw_script_dir

# **************************************************************** #
#                       Path Configuration                           #
# **************************************************************** #
if DEV_MODE:
    TEMP_LOG_DIR = os.path.join(SCRIPT_DIR, "..", "py_downloads")
    CONFIG_FILE = os.path.join(SCRIPT_DIR, "..", "workdir", "config.json")
    ADDED_SYSTEMS_FILE = os.path.join(SCRIPT_DIR, "..", "workdir", "added_systems.json")
else:
    TEMP_LOG_DIR = os.path.join(SCRIPT_DIR, "py_downloads")
    CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")
    ADDED_SYSTEMS_FILE = os.path.join(SCRIPT_DIR, "added_systems.json")

os.makedirs(TEMP_LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(TEMP_LOG_DIR, "error.log")

# **************************************************************** #
#                       Display Settings                             #
# **************************************************************** #
FPS = 30
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FONT_SIZE = 28

# **************************************************************** #
#                       Color Palette                                #
# **************************************************************** #
# Base colors
BACKGROUND = (18, 20, 24)  # Dark background
SURFACE = (30, 34, 40)  # Card/surface background
SURFACE_HOVER = (40, 44, 50)  # Card hover state
SURFACE_SELECTED = (45, 50, 60)  # Card selected state

# Primary accent (blue)
PRIMARY = (66, 165, 245)
PRIMARY_DARK = (48, 123, 184)
PRIMARY_LIGHT = (100, 181, 246)

# Secondary accent (green)
SECONDARY = (102, 187, 106)
SECONDARY_DARK = (76, 140, 79)
SECONDARY_LIGHT = (129, 199, 132)

# Text colors
TEXT_PRIMARY = (255, 255, 255)  # Primary text (white)
TEXT_SECONDARY = (189, 189, 189)  # Secondary text (light gray)
TEXT_DISABLED = (117, 117, 117)  # Disabled text (darker gray)

# Status colors
WARNING = (255, 193, 7)  # Warning color (amber)
ERROR = (244, 67, 54)  # Error color (red)
SUCCESS = (76, 175, 80)  # Success color (green)

# Effects
SHADOW_COLOR = (0, 0, 0, 60)  # Shadow color with alpha
GLOW_COLOR = (66, 165, 245, 40)  # Glow color for highlights

# Legacy aliases (for backwards compatibility)
WHITE = TEXT_PRIMARY
BLACK = BACKGROUND
GREEN = SECONDARY
GRAY = TEXT_SECONDARY

# **************************************************************** #
#                       UI Dimensions                                #
# **************************************************************** #
BORDER_RADIUS = 12
CARD_PADDING = 8
THUMBNAIL_BORDER_RADIUS = 8
THUMBNAIL_SIZE = (192, 192)
HIRES_IMAGE_SIZE = (400, 400)

# **************************************************************** #
#                       Navigation Timing                            #
# **************************************************************** #
NAVIGATION_INITIAL_DELAY = 100  # ms before repeating starts
NAVIGATION_START_RATE = 400  # ms between repeats when starting (slow)
NAVIGATION_MAX_RATE = 100  # ms between repeats at maximum speed (fast)
NAVIGATION_ACCELERATION = 0.90  # Acceleration factor per repeat

# **************************************************************** #
#                       Touch/Mouse Settings                         #
# **************************************************************** #
SCROLL_THRESHOLD = 5  # Pixels to move before it's considered scrolling
TAP_TIME_THRESHOLD = 250  # Max ms for a tap vs scroll
SCROLL_SENSITIVITY = 0.08  # Touch scroll sensitivity (lower = more sensitive)
SCROLL_ITEM_HEIGHT = 60  # Approximate height of a scrollable item in pixels
DOUBLE_CLICK_THRESHOLD = 500  # Max ms between clicks for double-click
