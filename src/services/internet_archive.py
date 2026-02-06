"""
Internet Archive API service for Console Utilities.
Handles authentication, item validation, and file listing for archive.org downloads.
"""

import base64
import re
import traceback
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urlparse, quote

import requests

from utils.logging import log_error

# Internet Archive API endpoints
IA_S3_AUTH_URL = "https://archive.org/services/xauthn/?op=login"
IA_METADATA_URL = "https://archive.org/metadata/{item_id}"
IA_DOWNLOAD_BASE = "https://archive.org/download/{item_id}/{filename}"


def encode_password(password: str) -> str:
    """
    Encode password with base64 for storage.
    This is minimal obfuscation, not encryption.

    Args:
        password: Plain text password

    Returns:
        Base64 encoded password
    """
    return base64.b64encode(password.encode("utf-8")).decode("utf-8")


def decode_password(encoded: str) -> str:
    """
    Decode base64 encoded password.

    Args:
        encoded: Base64 encoded password

    Returns:
        Plain text password
    """
    try:
        return base64.b64decode(encoded.encode("utf-8")).decode("utf-8")
    except Exception:
        return ""


def get_ia_s3_credentials(
    email: str, password: str
) -> Tuple[bool, Optional[str], Optional[str], str]:
    """
    Get Internet Archive S3 credentials from login.

    Args:
        email: IA account email
        password: IA account password

    Returns:
        Tuple of (success, access_key, secret_key, error_message)
    """
    try:
        response = requests.post(
            IA_S3_AUTH_URL,
            data={"email": email, "password": password},
            timeout=30,
        )

        if response.status_code != 200:
            return False, None, None, f"Login failed (HTTP {response.status_code})"

        data = response.json()

        if not data.get("success"):
            error = data.get("values", {}).get("reason", "Unknown error")
            return False, None, None, error

        values = data.get("values", {})
        s3 = values.get("s3", {})
        access_key = s3.get("access")
        secret_key = s3.get("secret")

        if not access_key or not secret_key:
            return False, None, None, "No S3 credentials returned"

        return True, access_key, secret_key, ""

    except requests.exceptions.Timeout:
        return False, None, None, "Connection timed out"
    except requests.exceptions.ConnectionError:
        return False, None, None, "Connection failed"
    except Exception as e:
        log_error(f"IA login error: {e}", type(e).__name__, traceback.format_exc())
        return False, None, None, str(e)


def test_ia_credentials(access_key: str, secret_key: str) -> Tuple[bool, str]:
    """
    Test if stored IA S3 credentials are valid.

    Args:
        access_key: S3 access key
        secret_key: S3 secret key

    Returns:
        Tuple of (valid, error_message)
    """
    try:
        # Test by accessing the user's account info
        response = requests.get(
            "https://s3.us.archive.org",
            headers={"authorization": f"LOW {access_key}:{secret_key}"},
            timeout=10,
        )

        # A 403 with specific message means bad credentials
        # A successful connection means credentials work
        if response.status_code in (200, 204):
            return True, ""
        elif response.status_code == 403:
            return False, "Invalid credentials"
        else:
            return False, f"HTTP {response.status_code}"

    except requests.exceptions.Timeout:
        return False, "Connection timed out"
    except requests.exceptions.ConnectionError:
        return False, "Connection failed"
    except Exception as e:
        return False, str(e)


def validate_ia_url(url: str) -> Tuple[bool, Optional[str], str]:
    """
    Validate and parse an archive.org item ID or download URL.

    Accepts formats:
    - ITEM_ID (just the item identifier)
    - https://archive.org/download/ITEM_ID
    - https://archive.org/download/ITEM_ID/
    - https://archive.org/download/ITEM_ID/filename
    - https://archive.org/details/ITEM_ID

    Args:
        url: Item ID or URL to validate

    Returns:
        Tuple of (valid, item_id, error_message)
    """
    if not url:
        return False, None, "Item ID is empty"

    # Strip whitespace
    url = url.strip()

    # Check if it's just an item ID (no slashes, no protocol)
    if not "/" in url and not url.startswith("http"):
        # Validate item ID format (alphanumeric, dashes, underscores, dots)
        if re.match(r"^[\w\-\.]+$", url):
            return True, url, ""
        else:
            return False, None, "Invalid item ID format"

    try:
        parsed = urlparse(url)

        # Check domain
        if parsed.netloc not in ("archive.org", "www.archive.org"):
            return False, None, "Not an archive.org URL"

        # Parse path
        path_parts = [p for p in parsed.path.split("/") if p]

        if len(path_parts) < 2:
            return False, None, "Invalid archive.org URL format"

        # Check for /download/ or /details/ path
        if path_parts[0] not in ("download", "details"):
            return False, None, "URL must be archive.org/download/... or /details/..."

        item_id = path_parts[1]

        if not item_id:
            return False, None, "No item ID found in URL"

        # Basic validation of item ID (alphanumeric, dashes, underscores)
        if not re.match(r"^[\w\-\.]+$", item_id):
            return False, None, "Invalid item ID format"

        return True, item_id, ""

    except Exception as e:
        return False, None, f"URL parsing error: {e}"


def check_ia_item_accessible(
    item_id: str, access_key: Optional[str] = None, secret_key: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Check if an Internet Archive item exists and is accessible.

    Args:
        item_id: The IA item identifier
        access_key: Optional S3 access key for private items
        secret_key: Optional S3 secret key for private items

    Returns:
        Tuple of (accessible, error_message)
    """
    try:
        headers = {}
        if access_key and secret_key:
            headers["authorization"] = f"LOW {access_key}:{secret_key}"

        url = IA_METADATA_URL.format(item_id=item_id)
        response = requests.get(url, headers=headers, timeout=15)

        if response.status_code == 200:
            data = response.json()
            # Check if item exists (has files)
            if data.get("files"):
                return True, ""
            else:
                return False, "Item has no files"
        elif response.status_code == 404:
            return False, "Item not found"
        elif response.status_code == 403:
            return False, "Item is private or requires login"
        else:
            return False, f"HTTP {response.status_code}"

    except requests.exceptions.Timeout:
        return False, "Connection timed out"
    except requests.exceptions.ConnectionError:
        return False, "Connection failed"
    except Exception as e:
        return False, str(e)


def list_ia_files(
    item_id: str,
    access_key: Optional[str] = None,
    secret_key: Optional[str] = None,
    file_formats: Optional[List[str]] = None,
) -> Tuple[bool, List[Dict[str, Any]], str]:
    """
    List files in an Internet Archive item.

    Args:
        item_id: The IA item identifier
        access_key: Optional S3 access key for private items
        secret_key: Optional S3 secret key for private items
        file_formats: Optional list of extensions to filter (e.g., [".zip", ".7z"])

    Returns:
        Tuple of (success, files_list, error_message)
        files_list contains dicts with: name, size, format, mtime
    """
    try:
        headers = {}
        if access_key and secret_key:
            headers["authorization"] = f"LOW {access_key}:{secret_key}"

        url = IA_METADATA_URL.format(item_id=item_id)
        response = requests.get(url, headers=headers, timeout=30)

        if response.status_code != 200:
            if response.status_code == 404:
                return False, [], "Item not found"
            elif response.status_code == 403:
                return False, [], "Access denied"
            else:
                return False, [], f"HTTP {response.status_code}"

        data = response.json()
        raw_files = data.get("files", [])

        files = []
        for f in raw_files:
            name = f.get("name", "")
            if not name:
                continue

            # Skip derivative files (thumbnails, metadata, etc.)
            source = f.get("source", "")
            if source == "derivative":
                continue

            # Apply format filter if specified
            if file_formats:
                ext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
                if ext not in [fmt.lower() for fmt in file_formats]:
                    continue

            size = f.get("size")
            try:
                size = int(size) if size else 0
            except (ValueError, TypeError):
                size = 0

            files.append(
                {
                    "name": name,
                    "size": size,
                    "format": f.get("format", ""),
                    "mtime": f.get("mtime", ""),
                }
            )

        # Sort by name
        files.sort(key=lambda x: x["name"].lower())

        return True, files, ""

    except requests.exceptions.Timeout:
        return False, [], "Connection timed out"
    except requests.exceptions.ConnectionError:
        return False, [], "Connection failed"
    except Exception as e:
        log_error(f"IA list files error: {e}", type(e).__name__, traceback.format_exc())
        return False, [], str(e)


def get_ia_download_url(item_id: str, filename: str) -> str:
    """
    Build the download URL for an Internet Archive file.

    Args:
        item_id: The IA item identifier
        filename: The filename within the item

    Returns:
        Full download URL
    """
    # URL-encode the filename to handle special characters
    encoded_filename = quote(filename, safe="")
    return IA_DOWNLOAD_BASE.format(item_id=item_id, filename=encoded_filename)


def get_available_formats(
    item_id: str,
    access_key: Optional[str] = None,
    secret_key: Optional[str] = None,
) -> Tuple[bool, List[str], str]:
    """
    Get list of unique file extensions available in an IA item.
    Useful for auto-detecting formats when adding a collection.

    Args:
        item_id: The IA item identifier
        access_key: Optional S3 access key for private items
        secret_key: Optional S3 secret key for private items

    Returns:
        Tuple of (success, formats_list, error_message)
    """
    success, files, error = list_ia_files(item_id, access_key, secret_key)
    if not success:
        return False, [], error

    formats = set()
    for f in files:
        name = f.get("name", "")
        if "." in name:
            ext = "." + name.rsplit(".", 1)[-1].lower()
            formats.add(ext)

    # Sort with common gaming formats first
    priority_formats = [".zip", ".7z", ".rar", ".iso", ".chd", ".cue", ".bin", ".nsp"]
    sorted_formats = []

    for fmt in priority_formats:
        if fmt in formats:
            sorted_formats.append(fmt)
            formats.discard(fmt)

    # Add remaining formats alphabetically
    sorted_formats.extend(sorted(formats))

    return True, sorted_formats, ""


def get_ia_item_metadata(item_id: str) -> Tuple[bool, Dict[str, Any], str]:
    """
    Get metadata for an Internet Archive item.

    Args:
        item_id: The IA item identifier

    Returns:
        Tuple of (success, metadata_dict, error_message)
    """
    try:
        url = IA_METADATA_URL.format(item_id=item_id)
        response = requests.get(url, timeout=15)

        if response.status_code != 200:
            if response.status_code == 404:
                return False, {}, "Item not found"
            return False, {}, f"HTTP {response.status_code}"

        data = response.json()
        metadata = data.get("metadata", {})

        return True, metadata, ""

    except Exception as e:
        return False, {}, str(e)
