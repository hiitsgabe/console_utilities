"""
Update service for Console Utilities.
Checks GitHub releases for new versions and handles platform-specific updates.
"""

import os
import shutil
import threading
import traceback
from typing import Dict, Any, Optional, Tuple
from zipfile import ZipFile

import requests

from constants import APP_VERSION, BUILD_TARGET, SCRIPT_DIR
from utils.logging import log_error


GITHUB_OWNER = "hiitsgabe"
GITHUB_REPO = "console_utilities"
RELEASES_API = (
    f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
)

# Map BUILD_TARGET to the expected asset filename in GitHub releases
TARGET_ASSET_MAP = {
    "pygame": "pygame.zip",
    "macos": "macos.zip",
    "windows": "windows.zip",
    "android": "android.zip",
}


def check_for_update() -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """
    Check GitHub releases for a newer version.

    Returns:
        Tuple of (update_available, release_info, error_message)
        - update_available: True if a newer version exists
        - release_info: Dict with 'tag', 'name', 'body', 'asset_url', 'asset_size'
                        or None if no update / error
        - error_message: Empty string on success, error description on failure
    """
    if APP_VERSION == "dev":
        return False, None, "Cannot check updates in dev mode"

    try:
        response = requests.get(
            RELEASES_API,
            headers={"Accept": "application/vnd.github.v3+json"},
            timeout=10,
        )

        if response.status_code == 403:
            return False, None, "GitHub API rate limit exceeded. Try again later."
        if response.status_code == 404:
            return False, None, "No releases found."
        if response.status_code != 200:
            return False, None, f"GitHub API error (HTTP {response.status_code})"

        data = response.json()
        latest_tag = data.get("tag_name", "")

        if not latest_tag:
            return False, None, "Could not determine latest version"

        if not _is_newer_version(APP_VERSION, latest_tag):
            return False, None, ""

        # Find the asset for our platform
        asset_url = None
        asset_size = 0
        asset_name = TARGET_ASSET_MAP.get(BUILD_TARGET)

        if asset_name:
            for asset in data.get("assets", []):
                if asset.get("name") == asset_name:
                    asset_url = asset.get("browser_download_url")
                    asset_size = asset.get("size", 0)
                    break

        release_info = {
            "tag": latest_tag,
            "name": data.get("name", latest_tag),
            "body": data.get("body", ""),
            "asset_url": asset_url,
            "asset_size": asset_size,
        }

        return True, release_info, ""

    except requests.exceptions.ConnectionError:
        return False, None, "No internet connection"
    except requests.exceptions.Timeout:
        return False, None, "Connection timed out"
    except Exception as e:
        log_error("Update check failed", type(e).__name__, traceback.format_exc())
        return False, None, f"Update check failed: {type(e).__name__}"


def apply_pygame_update(
    asset_url: str, on_progress=None, on_complete=None, on_error=None
):
    """
    Download and apply a pygame bundle update.

    Replaces the .pygame file and assets folder with the new version.

    Args:
        asset_url: URL to download the pygame.zip asset
        on_progress: Callback(progress_float, status_str) for progress updates
        on_complete: Callback() when update is complete
        on_error: Callback(error_str) on failure
    """

    def _do_update():
        try:
            if on_progress:
                on_progress(0.0, "Downloading update...")

            # Download to temp location
            tmp_dir = os.path.join(SCRIPT_DIR, ".update_tmp")
            os.makedirs(tmp_dir, exist_ok=True)
            tmp_zip = os.path.join(tmp_dir, "update.zip")

            # Stream download with progress
            response = requests.get(asset_url, stream=True, timeout=60)
            response.raise_for_status()
            total = int(response.headers.get("content-length", 0))
            downloaded = 0

            with open(tmp_zip, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0 and on_progress:
                        on_progress(downloaded / total * 0.7, "Downloading update...")

            if on_progress:
                on_progress(0.7, "Extracting update...")

            # Extract the zip
            extract_dir = os.path.join(tmp_dir, "extracted")
            with ZipFile(tmp_zip, "r") as zip_ref:
                zip_ref.extractall(extract_dir)

            if on_progress:
                on_progress(0.85, "Applying update...")

            # Find and replace the .pygame file
            new_pygame = None
            for f in os.listdir(extract_dir):
                if f.endswith(".pygame"):
                    new_pygame = os.path.join(extract_dir, f)
                    break

            if new_pygame:
                # Find current .pygame file location
                current_pygame = _find_current_pygame()
                if current_pygame:
                    shutil.copy2(new_pygame, current_pygame)

            # Replace assets folder
            new_assets = os.path.join(extract_dir, "assets")
            if os.path.isdir(new_assets):
                current_assets = os.path.join(SCRIPT_DIR, "assets")
                if os.path.isdir(current_assets):
                    shutil.rmtree(current_assets)
                shutil.copytree(new_assets, current_assets)

            if on_progress:
                on_progress(1.0, "Update complete!")

            # Clean up
            shutil.rmtree(tmp_dir, ignore_errors=True)

            if on_complete:
                on_complete()

        except Exception as e:
            log_error("Update failed", type(e).__name__, traceback.format_exc())
            # Clean up on failure
            tmp_dir = os.path.join(SCRIPT_DIR, ".update_tmp")
            shutil.rmtree(tmp_dir, ignore_errors=True)
            if on_error:
                on_error(str(e))

    thread = threading.Thread(target=_do_update, daemon=True)
    thread.start()
    return thread


def _find_current_pygame() -> Optional[str]:
    """Find the current .pygame file path."""
    for f in os.listdir(SCRIPT_DIR):
        if f.endswith(".pygame"):
            return os.path.join(SCRIPT_DIR, f)
    return None


def _is_newer_version(current: str, latest: str) -> bool:
    """
    Compare version strings. Returns True if latest is newer than current.

    Handles versions like "v1.2.3" or "1.2.3".
    """
    try:
        current_parts = _parse_version(current)
        latest_parts = _parse_version(latest)
        return latest_parts > current_parts
    except (ValueError, IndexError):
        # If we can't parse, do string comparison
        return current != latest


def _parse_version(version: str) -> Tuple[int, ...]:
    """Parse a version string like 'v1.2.3' into a tuple of ints."""
    v = version.lstrip("v")
    return tuple(int(x) for x in v.split("."))
