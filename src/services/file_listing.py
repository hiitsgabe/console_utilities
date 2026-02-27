"""
File listing services for Console Utilities.
Handles fetching file lists from various sources and filtering.
"""

import os
import re
import traceback
from typing import List, Dict, Any, Optional, Callable
import requests

from utils.logging import log_error
from utils.formatting import decode_filename


def get_roms_folder_for_system(
    system_data: Dict[str, Any], settings: Dict[str, Any]
) -> str:
    """
    Get the target ROMs folder for a system.

    Args:
        system_data: System configuration dictionary
        settings: Application settings

    Returns:
        Absolute path to the ROMs folder for this system
    """
    system_name = system_data.get("name", "")
    system_settings = settings.get("system_settings", {})
    custom_folder = system_settings.get(system_name, {}).get("custom_folder")

    if custom_folder and os.path.exists(custom_folder):
        return custom_folder
    else:
        roms_folder = system_data.get("roms_folder", "")
        # If roms_folder is an absolute path (e.g., from IA collection), use it directly
        if roms_folder and os.path.isabs(roms_folder):
            return roms_folder
        roms_dir = settings.get("roms_dir", "")
        return os.path.join(roms_dir, roms_folder)


def _is_archive_org_url(url: str) -> bool:
    """Check if URL is an archive.org download URL."""
    return "archive.org/download/" in url


def _extract_ia_item_id(url: str) -> Optional[str]:
    """Extract item ID from archive.org URL."""
    # URL format: https://archive.org/download/ITEM_ID/...
    match = re.search(r"archive\.org/download/([^/]+)", url)
    return match.group(1) if match else None


def _list_files_archive_org(
    system_data: Dict[str, Any], formats: List[str]
) -> List[Dict[str, Any]]:
    """
    List files from Internet Archive using metadata API.

    Args:
        system_data: System configuration
        formats: Allowed file formats

    Returns:
        List of file dictionaries
    """
    from services.internet_archive import list_ia_files, get_ia_download_url

    url = system_data["url"]
    item_id = _extract_ia_item_id(url)

    if not item_id:
        return []

    # Get auth credentials if available (only pass if both are set)
    access_key = None
    secret_key = None
    if "auth" in system_data:
        auth_config = system_data["auth"]
        if auth_config.get("type") == "ia_s3":
            access_key = auth_config.get("access_key") or None
            secret_key = auth_config.get("secret_key") or None

    # Only pass credentials if both are set
    success, files, error = list_ia_files(
        item_id,
        access_key if access_key and secret_key else None,
        secret_key if access_key and secret_key else None,
        formats if formats else None,
    )

    if not success:
        log_error(f"IA file listing failed: {error}", "IAListError", "")
        return []

    # Convert to the format expected by the rest of the app
    result = []
    for f in files:
        filename = f["name"]
        # Build the download URL (properly URL-encoded)
        href = get_ia_download_url(item_id, filename)
        result.append(
            {
                "filename": filename,
                "href": href,
                "size": f.get("size", 0),
            }
        )

    return result


def list_files(
    system_data: Dict[str, Any],
    settings: Dict[str, Any],
    progress_callback: Optional[Callable[[str], None]] = None,
    page: int = 0,
) -> List[Any]:
    """
    List files for a given system.

    Args:
        system_data: System configuration dictionary
        settings: Application settings
        progress_callback: Optional callback for progress updates
        page: Page number (for pagination)

    Returns:
        List of files (strings or dictionaries depending on source)
    """
    try:
        if progress_callback:
            progress_callback(
                f"Loading games for {system_data.get('name', 'Unknown')}..."
            )

        formats = system_data.get("file_format", [])

        # Check if this is the JSON API format
        if "list_url" in system_data:
            return _list_files_json_api(system_data, settings, formats)

        # Check if this is an archive.org URL - use metadata API
        elif "url" in system_data and _is_archive_org_url(system_data["url"]):
            return _list_files_archive_org(system_data, formats)

        # Check if this is HTML directory format
        elif "url" in system_data:
            return _list_files_html(system_data, settings, formats)

        return []

    except Exception as e:
        log_error(
            f"Failed to fetch list for system {system_data.get('name', 'Unknown')}",
            type(e).__name__,
            traceback.format_exc(),
        )
        return []


def _get_request_headers_cookies(system_data: Dict[str, Any]) -> tuple:
    """
    Get request headers and cookies for a system.

    Args:
        system_data: System configuration dictionary

    Returns:
        Tuple of (headers dict, cookies dict)
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    cookies = {}

    # Check if authentication is configured for this system
    if "auth" in system_data:
        auth_config = system_data["auth"]
        if auth_config.get("type") == "ia_s3":
            # Internet Archive S3 authentication (only if both keys are set)
            access_key = auth_config.get("access_key") or None
            secret_key = auth_config.get("secret_key") or None
            if access_key and secret_key:
                headers["authorization"] = f"LOW {access_key}:{secret_key}"
        elif auth_config.get("cookies", False) and "token" in auth_config:
            # Use cookie-based authentication
            cookie_name = auth_config.get("cookie_name", "auth_token")
            cookies[cookie_name] = auth_config["token"]
        elif "token" in auth_config:
            # Use header-based authentication (Bearer token)
            headers["Authorization"] = f"Bearer {auth_config['token']}"

    return headers, cookies


def _list_files_json_api(
    system_data: Dict[str, Any], settings: Dict[str, Any], formats: List[str]
) -> List[str]:
    """
    List files from JSON API source.

    Args:
        system_data: System configuration
        settings: Application settings
        formats: Allowed file formats

    Returns:
        List of filenames
    """
    list_url = system_data["list_url"]
    array_path = system_data.get("list_json_file_location", "files")
    file_id = system_data.get("list_item_id", "name")

    headers, cookies = _get_request_headers_cookies(system_data)

    r = requests.get(list_url, timeout=10, headers=headers, cookies=cookies)
    response = r.json()

    if isinstance(response, dict) and "files" in response:
        files = response[array_path]
        if isinstance(files, list):
            filtered_files = [
                f[file_id]
                for f in files
                if any(f[file_id].lower().endswith(ext.lower()) for ext in formats)
            ]

            # Apply USA filter if enabled
            if settings.get("usa_only", False) and system_data.get(
                "should_filter_usa", True
            ):
                usa_regex = system_data.get("usa_regex", "(USA)")
                filtered_files = [f for f in filtered_files if re.search(usa_regex, f)]

            return filtered_files

    return []


def _list_files_html(
    system_data: Dict[str, Any], settings: Dict[str, Any], formats: List[str]
) -> List[Dict[str, Any]]:
    """
    List files from HTML directory listing.

    Args:
        system_data: System configuration
        settings: Application settings
        formats: Allowed file formats

    Returns:
        List of file dictionaries with filename, href, and optional banner_url
    """
    url = system_data["url"]
    regex_pattern = system_data.get("regex", '<a href="([^"]+)"[^>]*>([^<]+)</a>')

    headers, cookies = _get_request_headers_cookies(system_data)

    r = requests.get(url, timeout=10, headers=headers, cookies=cookies)
    r.raise_for_status()
    html_content = r.text

    files = []

    if "regex" in system_data:
        # Use the provided named capture group regex
        matches = re.finditer(regex_pattern, html_content, re.DOTALL)

        for match in matches:
            try:
                href = None
                filename = None
                banner_url = None

                # Try to get values from named groups
                if "id" in match.groupdict():
                    id_value = match.groupdict().get("id")
                    if "download_url" in system_data:
                        download_url = system_data["download_url"]
                        if "<id>" in download_url:
                            href = download_url.replace("<id>", id_value)
                        else:
                            href = id_value
                    else:
                        href = id_value
                elif "href" in match.groupdict():
                    href = match.groupdict().get("href")

                if "text" in match.groupdict():
                    filename = decode_filename(match.groupdict().get("text"))
                else:
                    filename = decode_filename(match.group(1))

                if "banner_url" in match.groupdict():
                    banner_url = match.groupdict().get("banner_url")

                if href and not filename:
                    filename = decode_filename(href)

                # Filter out filenames that start with non-ASCII characters
                if filename and not filename[0].isascii():
                    continue

                # Filter by file format
                if any(filename.lower().endswith(ext.lower()) for ext in formats):
                    files.append(
                        {"filename": filename, "href": href, "banner_url": banner_url}
                    )
                elif system_data.get("ignore_extension_filtering"):
                    files.append(
                        {"filename": filename, "href": href, "banner_url": banner_url}
                    )

            except Exception:
                continue
    else:
        # Simple regex for href links
        matches = re.findall(regex_pattern, html_content)

        for href, text in matches:
            filename = decode_filename(text or href)

            # Filter out filenames that start with non-ASCII characters
            if filename and not filename[0].isascii():
                continue

            if any(filename.lower().endswith(ext.lower()) for ext in formats):
                files.append({"filename": filename, "href": href})

    # Apply USA filter if enabled
    if settings.get("usa_only", False) and system_data.get("should_filter_usa", True):
        usa_regex = system_data.get("usa_regex", "(USA)")
        files = [f for f in files if re.search(usa_regex, f["filename"])]

    return sorted(files, key=lambda x: x["filename"])


def filter_games_by_search(games: List[Any], query: str) -> List[Any]:
    """
    Filter games list by search query.

    Args:
        games: List of games (strings or dictionaries)
        query: Search query string

    Returns:
        Filtered list of games
    """
    if not query:
        return games

    query_lower = query.lower()
    filtered = []

    for game in games:
        if isinstance(game, dict):
            name = game.get("filename", game.get("name", ""))
        else:
            name = str(game)

        if query_lower in name.lower():
            filtered.append(game)

    return filtered


def load_psx_rom_folder_contents(path: str) -> List[Dict[str, Any]]:
    """
    Load folder contents for PSX ROM selection.

    Groups multi-bin/cue sets into a single entry per game.
    Only shows folders, .cue files, and .bin files not covered by a .cue.
    """
    path = os.path.abspath(path)
    items = []

    if path != "/" and path != os.path.dirname(path):
        items.append({"name": "..", "type": "parent", "path": os.path.dirname(path)})

    try:
        entries = os.listdir(path)
    except PermissionError:
        return items

    dirs = []
    cue_map = {}  # base_name -> full_path
    bin_map = {}  # base_name -> full_path

    for entry in sorted(entries):
        if entry.startswith("."):
            continue
        full_path = os.path.join(path, entry)
        if os.path.isdir(full_path):
            dirs.append({"name": entry, "type": "folder", "path": full_path})
        else:
            ext = os.path.splitext(entry)[1].lower()
            base = os.path.splitext(entry)[0]
            if ext == ".cue":
                cue_map[base] = full_path
            elif ext == ".bin":
                bin_map[base] = full_path

    # Build game entries: .cue files as primary entries
    games = {}
    for base, cue_path in cue_map.items():
        games[base.lower()] = {"name": base, "type": "psx_rom", "path": cue_path}

    # Include .bin files not covered by any .cue (i.e. no .cue base is a prefix)
    cue_bases = list(cue_map.keys())
    for base, bin_path in bin_map.items():
        covered = any(base.lower().startswith(cb.lower()) for cb in cue_bases)
        if not covered and base.lower() not in games:
            games[base.lower()] = {"name": base, "type": "psx_rom", "path": bin_path}

    dirs.sort(key=lambda x: x["name"].lower())
    game_list = sorted(games.values(), key=lambda x: x["name"].lower())

    items.extend(dirs)
    items.extend(game_list)
    return items


def load_snes_rom_folder_contents(path: str) -> List[Dict[str, Any]]:
    """
    Load folder contents for SNES ROM selection.

    Shows folders and .sfc/.smc ROM files.
    """
    path = os.path.abspath(path)
    items = []

    if path != "/" and path != os.path.dirname(path):
        items.append({"name": "..", "type": "parent", "path": os.path.dirname(path)})

    try:
        entries = os.listdir(path)
    except PermissionError:
        return items

    dirs = []
    roms = []

    for entry in sorted(entries):
        if entry.startswith("."):
            continue
        full_path = os.path.join(path, entry)
        if os.path.isdir(full_path):
            dirs.append({"name": entry, "type": "folder", "path": full_path})
        else:
            ext = os.path.splitext(entry)[1].lower()
            if ext in (".sfc", ".smc"):
                roms.append({"name": entry, "type": "snes_rom", "path": full_path})

    dirs.sort(key=lambda x: x["name"].lower())
    roms.sort(key=lambda x: x["name"].lower())

    items.extend(dirs)
    items.extend(roms)
    return items


def load_genesis_rom_folder_contents(path: str) -> List[Dict[str, Any]]:
    """
    Load folder contents for Genesis ROM selection.

    Shows folders and .bin/.md/.gen ROM files.
    """
    path = os.path.abspath(path)
    items = []

    if path != "/" and path != os.path.dirname(path):
        items.append({"name": "..", "type": "parent", "path": os.path.dirname(path)})

    try:
        entries = os.listdir(path)
    except PermissionError:
        return items

    dirs = []
    roms = []

    for entry in sorted(entries):
        if entry.startswith("."):
            continue
        full_path = os.path.join(path, entry)
        if os.path.isdir(full_path):
            dirs.append({"name": entry, "type": "folder", "path": full_path})
        else:
            ext = os.path.splitext(entry)[1].lower()
            if ext in (".bin", ".md", ".gen"):
                roms.append({"name": entry, "type": "genesis_rom", "path": full_path})

    dirs.sort(key=lambda x: x["name"].lower())
    roms.sort(key=lambda x: x["name"].lower())

    items.extend(dirs)
    items.extend(roms)
    return items


def load_psp_iso_folder_contents(path: str) -> List[Dict[str, Any]]:
    """
    Load folder contents for PSP ISO selection.

    Shows folders and .iso/.cso PSP image files.
    """
    path = os.path.abspath(path)
    items = []

    if path != "/" and path != os.path.dirname(path):
        items.append({"name": "..", "type": "parent", "path": os.path.dirname(path)})

    try:
        entries = os.listdir(path)
    except PermissionError:
        return items

    dirs = []
    isos = []

    for entry in sorted(entries):
        if entry.startswith("."):
            continue
        full_path = os.path.join(path, entry)
        if os.path.isdir(full_path):
            dirs.append({"name": entry, "type": "folder", "path": full_path})
        else:
            ext = os.path.splitext(entry)[1].lower()
            if ext in (".iso", ".cso"):
                isos.append({"name": entry, "type": "psp_iso", "path": full_path})

    dirs.sort(key=lambda x: x["name"].lower())
    isos.sort(key=lambda x: x["name"].lower())

    items.extend(dirs)
    items.extend(isos)
    return items


def load_folder_contents(path: str) -> List[Dict[str, Any]]:
    """
    Load folder contents for browser.

    Args:
        path: Directory path to list

    Returns:
        List of item dictionaries with name, type, and path
    """
    try:
        # Normalize path
        path = os.path.abspath(path)
        items = []

        # Add parent directory option unless we're at root
        if path != "/" and path != os.path.dirname(path):
            items.append(
                {"name": "..", "type": "parent", "path": os.path.dirname(path)}
            )

        # Add "Create New Folder" option
        items.append(
            {"name": "[Create New Folder]", "type": "create_folder", "path": path}
        )

        # List directory contents
        try:
            entries = os.listdir(path)
        except PermissionError:
            return items

        # Sort entries (directories first, then alphabetically)
        dirs = []
        files = []

        for entry in entries:
            # Skip hidden files
            if entry.startswith("."):
                continue

            full_path = os.path.join(path, entry)

            if os.path.isdir(full_path):
                dirs.append({"name": entry, "type": "folder", "path": full_path})
            else:
                # Determine file type
                ext = os.path.splitext(entry)[1].lower()

                if ext == ".keys":
                    file_type = "keys_file"
                elif ext == ".json":
                    file_type = "json_file"
                elif ext == ".nsz":
                    file_type = "nsz_file"
                elif ext == ".zip":
                    file_type = "zip_file"
                elif ext == ".rar":
                    file_type = "rar_file"
                elif ext == ".7z":
                    file_type = "7z_file"
                elif ext == ".cue":
                    file_type = "cue_file"
                else:
                    file_type = "file"

                files.append({"name": entry, "type": file_type, "path": full_path})

        # Sort and combine
        dirs.sort(key=lambda x: x["name"].lower())
        files.sort(key=lambda x: x["name"].lower())

        items.extend(dirs)
        items.extend(files)

        return items

    except Exception as e:
        log_error(
            "Failed to load folder contents", type(e).__name__, traceback.format_exc()
        )
        return []


def find_next_letter_index(items: List[Any], current_index: int, direction: int) -> int:
    """
    Find the next item that starts with a different letter.

    Args:
        items: List of items (strings or dictionaries)
        current_index: Current position in list
        direction: 1 for forward, -1 for backward

    Returns:
        Index of next item with different starting letter
    """
    if not items:
        return current_index

    def get_name(item: Any) -> str:
        """Extract display name from item."""
        if isinstance(item, dict):
            if "name" in item:
                return item.get("name", "")
            elif "filename" in item:
                return os.path.splitext(item.get("filename", ""))[0]
            else:
                return str(item)
        return str(item)

    current_name = get_name(items[current_index])
    if not current_name:
        return current_index

    current_letter = current_name[0].upper()

    if direction > 0:  # Moving forward
        for i in range(current_index + 1, len(items)):
            item_name = get_name(items[i])
            if item_name and item_name[0].upper() > current_letter:
                return i
    else:  # Moving backward
        for i in range(current_index - 1, -1, -1):
            item_name = get_name(items[i])
            if item_name and item_name[0].upper() < current_letter:
                return i

    return current_index


def get_file_size(system_data: Dict[str, Any], game: Dict[str, Any]) -> Optional[int]:
    """
    Get file size for a game via HEAD request.

    Args:
        system_data: System configuration dictionary
        game: Game data dictionary

    Returns:
        File size in bytes or None if unavailable
    """
    try:
        from urllib.parse import urljoin

        # Build download URL
        filename = game.get("filename", game.get("name", ""))
        if not filename:
            return None

        if "download_url" in system_data:
            url = game.get("href")
        elif "url" in system_data:
            if "href" in game:
                url = urljoin(system_data["url"], game["href"])
            else:
                url = urljoin(system_data["url"], filename)
        else:
            return None

        if not url:
            return None

        # Get headers/cookies for auth
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        cookies = {}

        if "auth" in system_data:
            auth_config = system_data["auth"]
            if auth_config.get("cookies", False) and "token" in auth_config:
                cookie_name = auth_config.get("cookie_name", "auth_token")
                cookies[cookie_name] = auth_config["token"]
            elif "token" in auth_config:
                headers["Authorization"] = f"Bearer {auth_config['token']}"

        # HEAD request to get Content-Length
        response = requests.head(
            url, timeout=5, headers=headers, cookies=cookies, allow_redirects=True
        )

        if response.status_code == 200:
            content_length = response.headers.get("content-length")
            if content_length:
                return int(content_length)

        return None

    except Exception as e:
        log_error("Failed to get file size", type(e).__name__, str(e))
        return None
