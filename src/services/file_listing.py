"""
File listing services for Console Utilities.
Handles fetching file lists from various sources and filtering.
"""

import hashlib
import json
import os
import re
import traceback
from typing import List, Dict, Any, Optional, Callable
import requests

from utils.logging import log_error
from utils.formatting import decode_filename
from constants import SYSTEMS_CACHE_DIR


def _get_listing_cache_path(url: str) -> str:
    """Return disk cache path for a file listing URL."""
    url_hash = hashlib.md5(url.encode()).hexdigest()
    return os.path.join(SYSTEMS_CACHE_DIR, "listings", f"{url_hash}.json")


def _load_cached_listing(url: str) -> Optional[List[Dict[str, Any]]]:
    """Load a cached file listing from disk, or None if not cached."""
    path = _get_listing_cache_path(url)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def _save_listing_cache(url: str, files_list: List[Dict[str, Any]]):
    """Save a file listing to disk cache."""
    path = _get_listing_cache_path(url)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(files_list, f, ensure_ascii=False)
    except Exception:
        pass


def _dedupe_game_list(files: List[Any]) -> List[Any]:
    """
    Deduplicate game list by normalized name, preferring USA titles.

    Groups files by base game name (stripping region/version tags),
    then picks the best representative: USA > World > Europe > largest file.
    """

    def _get_filename(f):
        return f.get("filename", "") if isinstance(f, dict) else str(f)

    # Group by normalized name
    groups: Dict[str, List[Any]] = {}
    for f in files:
        filename = _get_filename(f)
        # Strip extension, remove all parenthetical/bracket content, normalize
        name = re.sub(r"\.[^.]+$", "", filename)
        norm = re.sub(r"\(.*?\)", "", name)
        norm = re.sub(r"\[.*?\]", "", norm)
        norm = norm.strip().lower()
        norm = re.sub(r"\s+", " ", norm)
        if norm not in groups:
            groups[norm] = []
        groups[norm].append(f)

    # Pick best from each group
    def _priority(f):
        name = _get_filename(f)
        # Lower score = higher priority
        if "(USA)" in name:
            region = 0
        elif "(World)" in name:
            region = 1
        elif "(USA, Europe)" in name or "(Europe, USA)" in name:
            region = 2
        elif "(Europe)" in name:
            region = 3
        else:
            region = 4
        size = f.get("size", 0) if isinstance(f, dict) else 0
        try:
            size = int(size)
        except (ValueError, TypeError):
            size = 0
        return (region, -size)

    result = []
    for group in groups.values():
        best = min(group, key=_priority)
        result.append(best)
    return result


def _normalize_urls(url):
    """Normalize url field to a list of strings.

    Returns [url] if string, url if list, [] if empty/missing.
    """
    if isinstance(url, list):
        return url
    if isinstance(url, str) and url:
        return [url]
    return []


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
    system_data: Dict[str, Any], formats: List[str], url: str = ""
) -> List[Dict[str, Any]]:
    """
    List files from Internet Archive using metadata API.

    Args:
        system_data: System configuration
        formats: Allowed file formats
        url: Specific URL to list (defaults to system_data["url"] for backwards compat)

    Returns:
        List of file dictionaries
    """
    from services.internet_archive import list_ia_files, get_ia_download_url

    if not url:
        raw = system_data["url"]
        url = raw[0] if isinstance(raw, list) else raw
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
        system_name = system_data.get("name", "Unknown")

        if progress_callback:
            progress_callback(f"Loading games for {system_name}...")

        formats = list(system_data.get("file_format", []))
        # Archives serve .zip files; include in listing when should_unzip is set
        per_sys = settings.get("system_settings", {}).get(system_name, {})
        should_unzip = per_sys.get("should_unzip", system_data.get("should_unzip", False))
        if should_unzip:
            if ".zip" not in [f.lower() for f in formats]:
                formats.append(".zip")

        # Check if this is the JSON API format
        if "list_url" in system_data:
            return _list_files_json_api(system_data, settings, formats)

        urls = _normalize_urls(system_data.get("url"))
        if not urls:
            return []

        all_files = []
        for i, url in enumerate(urls):
            if len(urls) > 1 and progress_callback:
                progress_callback(f"Loading {system_name} ({i + 1}/{len(urls)})...")

            # Check disk cache first
            cached = _load_cached_listing(url)
            if cached is not None:
                all_files.extend(cached)
                continue

            if _is_archive_org_url(url):
                files = _list_files_archive_org(system_data, formats, url)
            else:
                files = _list_files_html_single(system_data, settings, formats, url)
                # Tag HTML results with their base URL for download resolution
                for f in files:
                    f["_base_url"] = url

            if files:
                _save_listing_cache(url, files)
            all_files.extend(files)

        # Apply USA filter if enabled (top-level for all sources)
        if settings.get("usa_only", False) and system_data.get(
            "should_filter_usa", True
        ):
            usa_regex = system_data.get("usa_regex", r"\(USA")
            all_files = [
                f
                for f in all_files
                if re.search(
                    usa_regex,
                    f.get("filename", "") if isinstance(f, dict) else f,
                )
            ]

        # Deduplicate game list (prefer USA, then largest file)
        if settings.get("dedupe_game_list", False) and all_files:
            all_files = _dedupe_game_list(all_files)

        # Sort combined list by filename
        if all_files and isinstance(all_files[0], dict):
            all_files.sort(key=lambda x: x.get("filename", ""))
        else:
            all_files.sort()

        return all_files

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

    try:
        r = requests.get(list_url, timeout=(10, 30), headers=headers, cookies=cookies)
    except (requests.exceptions.SSLError, requests.exceptions.ConnectionError):
        r = requests.get(
            list_url, timeout=(10, 30), headers=headers, cookies=cookies, verify=False
        )
    response = r.json()

    if isinstance(response, dict) and "files" in response:
        files = response[array_path]
        if isinstance(files, list):
            filtered_files = [
                f[file_id]
                for f in files
                if any(f[file_id].lower().endswith(ext.lower()) for ext in formats)
            ]

            return filtered_files

    return []


def _list_files_html(
    system_data: Dict[str, Any], settings: Dict[str, Any], formats: List[str]
) -> List[Dict[str, Any]]:
    """List files from HTML directory listing (backwards compat wrapper)."""
    raw = system_data["url"]
    url = raw[0] if isinstance(raw, list) else raw
    return _list_files_html_single(system_data, settings, formats, url)


def _list_files_html_single(
    system_data: Dict[str, Any],
    settings: Dict[str, Any],
    formats: List[str],
    url: str,
) -> List[Dict[str, Any]]:
    """
    List files from a single HTML directory listing URL.

    Args:
        system_data: System configuration
        settings: Application settings
        formats: Allowed file formats
        url: URL to fetch the HTML listing from

    Returns:
        List of file dictionaries with filename, href, and optional banner_url
    """
    regex_pattern = system_data.get("regex", '<a href="([^"]+)"[^>]*>([^<]+)</a>')

    headers, cookies = _get_request_headers_cookies(system_data)

    try:
        r = requests.get(url, timeout=(15, 60), headers=headers, cookies=cookies)
        r.raise_for_status()
    except (requests.exceptions.SSLError, requests.exceptions.ConnectionError):
        r = requests.get(
            url, timeout=(15, 60), headers=headers, cookies=cookies, verify=False
        )
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


def get_android_storage_volumes() -> List[Dict[str, Any]]:
    """
    Get available storage volumes on Android (internal + SD card).

    Returns:
        List of storage volume dicts with name, type, and path.
        Empty list on non-Android platforms.
    """
    from constants import BUILD_TARGET

    if BUILD_TARGET != "android":
        return []

    volumes = []
    try:
        # Internal shared storage
        internal = "/storage/emulated/0"
        if os.path.isdir(internal) and os.access(internal, os.R_OK):
            volumes.append(
                {"name": "Internal Storage", "type": "storage_volume", "path": internal}
            )

        # App's external files dir (always writable)
        try:
            from jnius import autoclass

            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            context = PythonActivity.mActivity.getApplicationContext()
            ext_dir = context.getExternalFilesDir(None)
            if ext_dir:
                app_path = ext_dir.getAbsolutePath()
                if os.path.isdir(app_path):
                    volumes.append(
                        {"name": "App Storage", "type": "storage_volume", "path": app_path}
                    )

            # External SD card volumes via getExternalFilesDirs (plural)
            ext_dirs = context.getExternalFilesDirs(None)
            if ext_dirs:
                for i in range(ext_dirs.length):
                    d = ext_dirs[i]
                    if d is None:
                        continue
                    sd_app_path = d.getAbsolutePath()
                    # Skip internal (already added)
                    if "emulated" in sd_app_path:
                        continue
                    # Navigate up to the SD card root for browsing
                    # Path is like /storage/XXXX-XXXX/Android/data/<pkg>/files
                    sd_root = sd_app_path
                    android_idx = sd_app_path.find("/Android/")
                    if android_idx > 0:
                        sd_root = sd_app_path[:android_idx]
                    label = os.path.basename(sd_root) if sd_root != "/" else "SD Card"
                    volumes.append(
                        {"name": f"SD Card ({label})", "type": "storage_volume", "path": sd_root}
                    )
                    # Also add the writable app dir on SD card
                    if os.path.isdir(sd_app_path):
                        volumes.append(
                            {"name": f"SD App Storage ({label})", "type": "storage_volume", "path": sd_app_path}
                        )
        except Exception:
            pass

        # Fallback: scan /storage for any mount points we missed
        if os.path.isdir("/storage"):
            try:
                for entry in os.listdir("/storage"):
                    if entry == "emulated" or entry == "self":
                        continue
                    full = os.path.join("/storage", entry)
                    if os.path.isdir(full) and os.access(full, os.R_OK):
                        # Check if already added
                        existing_paths = {v["path"] for v in volumes}
                        if full not in existing_paths:
                            volumes.append(
                                {"name": f"SD Card ({entry})", "type": "storage_volume", "path": full}
                            )
            except Exception:
                pass
    except Exception:
        pass

    return volumes


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

        # On Android, add storage volume shortcuts for quick navigation
        from constants import BUILD_TARGET
        if BUILD_TARGET == "android":
            volumes = get_android_storage_volumes()
            for vol in volumes:
                # Skip if we're already at this exact path
                if vol["path"] != path:
                    items.append(vol)

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
            # Use per-game base URL (from multi-URL listing) or first URL
            base_url = game.get("_base_url") if isinstance(game, dict) else None
            if not base_url:
                urls = _normalize_urls(system_data["url"])
                base_url = urls[0] if urls else ""
            if "href" in game:
                url = urljoin(base_url, game["href"])
            else:
                url = urljoin(base_url, filename)
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
