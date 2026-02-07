"""
Settings management for Console Utilities.
Handles loading, saving, and managing application settings.
"""

import json
import os
import traceback
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List

from constants import CONFIG_FILE, SCRIPT_DIR, DEV_MODE


@dataclass
class Settings:
    """Application settings with default values."""

    enable_boxart: bool = True
    view_type: str = "grid"  # "grid" or "list"
    usa_only: bool = False
    show_download_all: bool = False  # Show "Download All" button in game lists
    work_dir: str = ""
    roms_dir: str = ""
    nsz_keys_path: str = ""
    archive_json_path: str = ""
    archive_json_url: str = ""
    cache_enabled: bool = True
    system_settings: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # Internet Archive settings
    ia_enabled: bool = False
    ia_email: str = ""
    ia_access_key: str = ""  # S3 access key from IA
    ia_secret_key: str = ""  # S3 secret key (base64 encoded for minimal obfuscation)
    # Scraper settings
    scraper_frontend: str = (
        "emulationstation_base"  # emulationstation_base, esde_android, retroarch, pegasus
    )
    scraper_provider: str = "libretro"  # libretro, screenscraper, thegamesdb
    scraper_fallback_enabled: bool = True
    screenscraper_username: str = ""
    screenscraper_password: str = ""  # base64 encoded
    thegamesdb_api_key: str = ""
    # Frontend-specific paths
    esde_media_path: str = ""
    esde_gamelists_path: str = ""
    retroarch_thumbnails_path: str = ""

    def __post_init__(self):
        """Set default paths if not specified."""
        if not self.work_dir:
            self.work_dir = _get_default_work_dir()
        if not self.roms_dir:
            self.roms_dir = _get_default_roms_dir()

    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Settings":
        """Create Settings from dictionary."""
        # Filter out unknown keys
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered_data)


def _get_default_work_dir() -> str:
    """Get the default work directory based on environment."""
    if DEV_MODE:
        return os.path.join(SCRIPT_DIR, "..", "downloads")
    elif os.path.exists("/userdata") and os.access("/userdata", os.W_OK):
        return "/userdata/downloads"
    else:
        return os.path.join(SCRIPT_DIR, "downloads")


def _get_default_roms_dir() -> str:
    """Get the default ROMs directory based on environment."""
    if DEV_MODE:
        return os.path.join(SCRIPT_DIR, "..", "roms")
    elif os.path.exists("/userdata") and os.access("/userdata", os.W_OK):
        return "/userdata/roms"
    else:
        return os.path.join(SCRIPT_DIR, "roms")


def get_default_settings() -> Dict[str, Any]:
    """Get default settings as a dictionary."""
    return Settings().to_dict()


def load_settings() -> Dict[str, Any]:
    """
    Load settings from config file.

    Returns:
        Dictionary of settings with defaults for missing values
    """
    default_settings = get_default_settings()

    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                loaded_settings = json.load(f)
                # Merge with defaults to handle new settings
                default_settings.update(loaded_settings)
        else:
            # Create config file with defaults
            save_settings(default_settings)
    except Exception as e:
        from utils.logging import log_error

        log_error(
            "Failed to load settings, using defaults",
            type(e).__name__,
            traceback.format_exc(),
        )

    return default_settings


def save_settings(settings_to_save: Dict[str, Any]) -> bool:
    """
    Save settings to config file.

    Args:
        settings_to_save: Dictionary of settings to save

    Returns:
        True if successful, False otherwise
    """
    try:
        # Create directory if it doesn't exist
        config_dir = os.path.dirname(CONFIG_FILE)
        if config_dir:
            os.makedirs(config_dir, exist_ok=True)

        with open(CONFIG_FILE, "w") as f:
            json.dump(settings_to_save, f, indent=2)
        return True
    except Exception as e:
        from utils.logging import log_error

        log_error("Failed to save settings", type(e).__name__, traceback.format_exc())
        return False


# ---- Controller Mapping ---- #

_controller_mapping: Dict[str, Any] = {}


def get_controller_mapping() -> Dict[str, Any]:
    """Get the current controller mapping."""
    return _controller_mapping


def load_controller_mapping() -> bool:
    """
    Load controller mapping from file.

    Returns:
        True if mapping was loaded, False otherwise
    """
    global _controller_mapping

    mapping_file = os.path.join(os.path.dirname(CONFIG_FILE), "controller_mapping.json")

    try:
        if os.path.exists(mapping_file):
            with open(mapping_file, "r") as f:
                _controller_mapping = json.load(f)
                print("Controller mapping loaded from file")
                return True
        else:
            print("No controller mapping found, will need to create new mapping")
            _controller_mapping = {}
            return False
    except Exception as e:
        from utils.logging import log_error

        log_error(
            "Failed to load controller mapping",
            type(e).__name__,
            traceback.format_exc(),
        )
        _controller_mapping = {}
        return False


def save_controller_mapping(mapping: Optional[Dict[str, Any]] = None) -> bool:
    """
    Save controller mapping to file.

    Args:
        mapping: Controller mapping to save. If None, saves current mapping.

    Returns:
        True if successful, False otherwise
    """
    global _controller_mapping

    if mapping is not None:
        _controller_mapping = mapping

    mapping_file = os.path.join(os.path.dirname(CONFIG_FILE), "controller_mapping.json")

    try:
        os.makedirs(os.path.dirname(mapping_file), exist_ok=True)
        with open(mapping_file, "w") as f:
            json.dump(_controller_mapping, f, indent=2)
        print("Controller mapping saved")
        return True
    except Exception as e:
        from utils.logging import log_error

        log_error(
            "Failed to save controller mapping",
            type(e).__name__,
            traceback.format_exc(),
        )
        return False


def needs_controller_mapping() -> bool:
    """
    Check if we need to collect controller mapping.

    Returns:
        True if mapping is needed, False otherwise
    """
    try:
        if _controller_mapping and _controller_mapping.get("touchscreen_mode"):
            return False

        essential_buttons = [
            "select",
            "back",
            "start",
            "detail",
            "search",
            "up",
            "down",
            "left",
            "right",
        ]
        return not _controller_mapping or not all(
            button in _controller_mapping for button in essential_buttons
        )
    except Exception as e:
        from utils.logging import log_error

        log_error(
            "Failed to check controller mapping",
            type(e).__name__,
            traceback.format_exc(),
        )
        return True


def get_controller_button(action: str) -> Optional[Any]:
    """
    Get the button mapping for an action.

    Args:
        action: The action name (e.g., "select", "back", "up")

    Returns:
        Button identifier or None if not mapped
    """
    return _controller_mapping.get(action)


def set_controller_button(action: str, button: Any) -> None:
    """
    Set the button mapping for an action.

    Args:
        action: The action name
        button: The button identifier
    """
    _controller_mapping[action] = button
