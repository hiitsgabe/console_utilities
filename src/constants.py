"""
Global constants for Console Utilities application.
Contains path configuration, display settings, colors, and timing constants.
"""

import os

# **************************************************************** #
#                       Build Info                                     #
# **************************************************************** #
# These are overwritten at build time by CI/CD or make targets.
# See .github/workflows/release.yml and Makefile bundle targets.
APP_VERSION = "dev"
BUILD_TARGET = "source"  # source, pygame, macos, windows, android

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
    TEMP_LOG_DIR = os.path.join(SCRIPT_DIR, "..", "workdir")
    CONFIG_FILE = os.path.join(SCRIPT_DIR, "..", "workdir", "config.json")
    ADDED_SYSTEMS_FILE = os.path.join(SCRIPT_DIR, "..", "workdir", "added_systems.json")
else:
    TEMP_LOG_DIR = SCRIPT_DIR
    CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")
    ADDED_SYSTEMS_FILE = os.path.join(SCRIPT_DIR, "added_systems.json")

os.makedirs(TEMP_LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(TEMP_LOG_DIR, "error.log")

# WE Patcher cache directory
if DEV_MODE:
    WE_PATCHER_CACHE_DIR = os.path.join(SCRIPT_DIR, "..", "workdir", "we_patcher_cache")
else:
    WE_PATCHER_CACHE_DIR = os.path.join(SCRIPT_DIR, "we_patcher_cache")

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
BACKGROUND = (0, 20, 0)  # Dark green CRT phosphor glow
SURFACE = (0, 30, 0)  # Slightly lighter green for cards/panels
SURFACE_HOVER = (0, 40, 0)  # Hover state green
SURFACE_SELECTED = (0, 50, 5)  # Selected green

# Primary accent (Phosphor Green)
PRIMARY = (0, 255, 65)
PRIMARY_DARK = (0, 180, 45)
PRIMARY_LIGHT = (0, 255, 100)

# Secondary accent (Amber)
SECONDARY = (200, 200, 0)
SECONDARY_DARK = (160, 160, 0)
SECONDARY_LIGHT = (230, 230, 50)

# Text colors
TEXT_PRIMARY = (0, 255, 65)  # Bright phosphor green
TEXT_SECONDARY = (0, 180, 45)  # Dimmer green
TEXT_DISABLED = (0, 80, 20)  # Very dim green

# Status colors
WARNING = (200, 200, 0)  # Amber
ERROR = (255, 50, 30)  # Red
SUCCESS = (0, 255, 65)  # Bright green

# Effects
SHADOW_COLOR = (0, 0, 0, 80)  # Shadow color with alpha
GLOW_COLOR = (0, 255, 65, 40)  # Green glow

# Legacy aliases
WHITE = TEXT_PRIMARY
BLACK = BACKGROUND
GREEN = PRIMARY
GRAY = TEXT_SECONDARY

# **************************************************************** #
#                       UI Dimensions                                #
# **************************************************************** #
BEZEL_INSET = 26  # CRT bezel overlay thickness (22px frame + 4px bevel)
BORDER_RADIUS = 0
CARD_PADDING = 8
THUMBNAIL_BORDER_RADIUS = 0
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
WEB_COMPANION_PORT = 7655  # Port for the web companion server

SCROLL_THRESHOLD = 5  # Pixels to move before it's considered scrolling
TAP_TIME_THRESHOLD = 250  # Max ms for a tap vs scroll
SCROLL_SENSITIVITY = 0.08  # Touch scroll sensitivity (lower = more sensitive)
SCROLL_ITEM_HEIGHT = 60  # Approximate height of a scrollable item in pixels
DOUBLE_CLICK_THRESHOLD = 500  # Max ms between clicks for double-click
