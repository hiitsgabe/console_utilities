"""
Data loading services for Console Utilities.
Handles loading system configurations, added systems, and available systems.
"""

import json
import os
import re
import traceback
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin

import requests

from constants import ADDED_SYSTEMS_FILE, SCRIPT_DIR, DEV_MODE
from utils.logging import log_error

# Module-level variable for JSON file path
_json_file: Optional[str] = None

# Path to bundled JSON file in assets folder
BUNDLED_JSON_FILE = os.path.join(SCRIPT_DIR, "assets", "bundled_data.json")


def get_json_file() -> Optional[str]:
    """Get the current JSON file path."""
    return _json_file


def set_json_file(path: str) -> None:
    """Set the JSON file path."""
    global _json_file
    _json_file = path


def get_bundled_json_path() -> Optional[str]:
    """
    Get the path to bundled JSON data if it exists.

    Returns:
        Path to bundled JSON file or None if not found
    """
    if os.path.exists(BUNDLED_JSON_FILE):
        return BUNDLED_JSON_FILE
    return None


def update_json_file_path(settings: Dict[str, Any]) -> None:
    """
    Update the JSON file path based on settings.
    Falls back to bundled JSON if no user-specified path.

    Args:
        settings: Application settings dictionary
    """
    global _json_file
    archive_path = settings.get("archive_json_path", "")
    if archive_path and os.path.exists(archive_path):
        _json_file = archive_path
    elif get_bundled_json_path():
        # Use bundled JSON as fallback
        _json_file = get_bundled_json_path()


def load_main_systems_data(
    settings: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Load main systems data including added systems.

    Args:
        settings: Optional settings dictionary to get JSON path from

    Returns:
        List of system configuration dictionaries
    """
    try:
        main_data = []

        # Update JSON file path if settings provided
        if settings:
            update_json_file_path(settings)

        json_file = _json_file

        if json_file and os.path.exists(json_file):
            with open(json_file) as f:
                main_data = json.load(f)
        else:
            print(f"Info: {json_file} not found, starting with empty main systems")
            main_data = []

        added_systems = load_added_systems()
        combined_data = main_data + added_systems

        return combined_data

    except Exception as e:
        log_error(
            "Failed to load main systems data", type(e).__name__, traceback.format_exc()
        )
        return []


def load_added_systems() -> List[Dict[str, Any]]:
    """
    Load added systems from file.

    Returns:
        List of added system dictionaries
    """
    try:
        if os.path.exists(ADDED_SYSTEMS_FILE):
            with open(ADDED_SYSTEMS_FILE, "r") as f:
                return json.load(f)
        return []
    except Exception as e:
        log_error(
            "Failed to load added systems", type(e).__name__, traceback.format_exc()
        )
        return []


def save_added_systems(added_systems_list: List[Dict[str, Any]]) -> bool:
    """
    Save added systems to file.

    Args:
        added_systems_list: List of system dictionaries to save

    Returns:
        True if successful, False otherwise
    """
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(ADDED_SYSTEMS_FILE), exist_ok=True)

        with open(ADDED_SYSTEMS_FILE, "w") as f:
            json.dump(added_systems_list, f, indent=2)
        return True
    except Exception as e:
        log_error(
            "Failed to save added systems", type(e).__name__, traceback.format_exc()
        )
        return False


def add_system_to_added_systems(
    system_name: str,
    rom_folder: str,
    system_url: str,
    boxarts_url: str = "",
    file_formats: Optional[List[str]] = None,
    should_unzip: bool = True,
    extract_contents: bool = True,
    auth: Optional[Dict[str, Any]] = None,
    extra_fields: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Add a new system to the added systems list.

    Args:
        system_name: Name of the system
        rom_folder: ROM folder path
        system_url: URL for file listing
        boxarts_url: Optional boxart URL base
        file_formats: Optional list of file formats
        should_unzip: Whether to auto-extract ZIP files
        extract_contents: Whether to extract only contents (True) or keep folder structure (False)
        auth: Optional authentication config (e.g., {"type": "ia_s3", "access_key": ..., "secret_key": ...})
        extra_fields: Optional dict of additional fields to include (e.g., download_url, regex,
            ignore_extension_filtering, should_decompress_nsz, etc.)

    Returns:
        True if successful, False otherwise
    """
    try:
        added_systems = load_added_systems()

        new_system = {
            "name": system_name,
            "roms_folder": rom_folder,
            "url": system_url,
            "file_format": file_formats or [".zip"],
            "should_unzip": should_unzip,
            "extract_contents": extract_contents,
            "added": True,
        }

        if boxarts_url:
            new_system["boxarts"] = boxarts_url

        if auth:
            new_system["auth"] = auth

        if extra_fields:
            new_system.update(extra_fields)

        # Check if system already exists
        existing_idx = next(
            (i for i, s in enumerate(added_systems) if s["name"] == system_name), None
        )

        if existing_idx is not None:
            # Update existing system
            added_systems[existing_idx] = new_system
        else:
            # Add new system
            added_systems.append(new_system)

        return save_added_systems(added_systems)

    except Exception as e:
        log_error(
            "Failed to add system to added systems",
            type(e).__name__,
            traceback.format_exc(),
        )
        return False


def load_available_systems(
    data: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Load available systems from a list_systems entry.

    Finds entries with list_systems: true in data, fetches their URL,
    parses the HTML with the entry's regex to discover sub-systems.

    Args:
        data: Full list of system configuration dictionaries

    Returns:
        List of available system dictionaries with name, href, url, size
    """
    from services.file_listing import _get_request_headers_cookies

    try:
        # Find the first list_systems entry
        list_entry = next((d for d in data if d.get("list_systems") is True), None)
        if not list_entry:
            return []

        url = list_entry.get("url", "")
        regex_pattern = list_entry.get(
            "regex", '<a href="(?P<href>[^"]+)"[^>]*>(?P<title>[^<]+)</a>'
        )

        if not url:
            return []

        headers, cookies = _get_request_headers_cookies(list_entry)
        r = requests.get(url, timeout=15, headers=headers, cookies=cookies)
        r.raise_for_status()
        html = r.text

        systems = []
        skip_names = {".", "..", "Parent Directory", "Parent directory"}

        for match in re.finditer(regex_pattern, html):
            groups = match.groupdict()
            href = groups.get("href", "")
            title = groups.get("title", "")
            text = groups.get("text", title)
            size = groups.get("size", "")

            name = (text or title or href).strip()

            # Skip navigation entries
            if not name or name in skip_names or href in ("../", "./", "/"):
                continue

            # Clean up trailing slash from name
            display_name = name.rstrip("/")
            if not display_name:
                continue

            full_url = urljoin(url, href)

            systems.append(
                {
                    "name": display_name,
                    "href": href,
                    "url": full_url,
                    "size": size.strip() if size else "",
                }
            )

        return systems

    except Exception as e:
        log_error(
            "Failed to load available systems",
            type(e).__name__,
            traceback.format_exc(),
        )
        return []


def fix_added_systems_roms_folder(roms_dir: str) -> None:
    """
    Fix added systems that have incorrect ROM folder paths.

    Args:
        roms_dir: The base ROMs directory
    """
    try:
        added_systems = load_added_systems()
        modified = False

        for system in added_systems:
            # Check if roms_folder needs fixing
            current_folder = system.get("roms_folder", "")
            if current_folder and not os.path.isabs(current_folder):
                # Convert relative path to absolute based on roms_dir
                new_folder = os.path.join(roms_dir, current_folder)
                system["roms_folder"] = new_folder
                modified = True

        if modified:
            save_added_systems(added_systems)

    except Exception as e:
        log_error(
            "Failed to fix added systems roms_folder",
            type(e).__name__,
            traceback.format_exc(),
        )


def get_visible_systems(
    data: List[Dict[str, Any]], settings: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Get list of systems that are not hidden and not list_systems.

    Also filters out NSZ systems if NSZ is disabled.

    Args:
        data: Full list of system data
        settings: Application settings

    Returns:
        Filtered list of visible systems
    """
    system_settings = settings.get("system_settings", {})
    nsz_enabled = settings.get("nsz_enabled", False)

    def is_nsz_system(system: Dict[str, Any]) -> bool:
        """Check if system uses NSZ file format."""
        file_format = system.get("file_format", [])
        if isinstance(file_format, list):
            return any(".nsz" in fmt.lower() for fmt in file_format)
        return ".nsz" in str(file_format).lower()

    visible_systems = [
        d
        for d in data
        if not d.get("list_systems", False)
        and not system_settings.get(d["name"], {}).get("hidden", False)
        and (nsz_enabled or not is_nsz_system(d))
    ]
    return visible_systems


def get_system_index_by_name(data: List[Dict[str, Any]], system_name: str) -> int:
    """
    Get the original data array index for a system by name.

    Args:
        data: Full list of system data
        system_name: Name of system to find

    Returns:
        Index of system or -1 if not found
    """
    try:
        return next(i for i, d in enumerate(data) if d["name"] == system_name)
    except StopIteration:
        return -1
