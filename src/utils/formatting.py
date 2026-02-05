"""
Formatting utilities for Console Utilities.
Provides functions for formatting sizes and decoding filenames.
"""

import html
from urllib.parse import unquote


def format_size(size_bytes: float) -> str:
    """
    Convert bytes to human readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted string with appropriate unit (B, KB, MB, GB, TB)
    """
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def decode_filename(raw_filename: str) -> str:
    """
    Properly decode URL-encoded and HTML entity-encoded filenames.

    Handles:
    - URL encoding (e.g., %20 -> space, %5B -> [)
    - HTML entities (e.g., &gt; -> >, &amp; -> &)
    - Character encoding issues (latin1/utf-8)

    Args:
        raw_filename: The encoded filename

    Returns:
        Decoded filename
    """
    try:
        # First decode URL encoding (e.g., %20 -> space, %5B -> [)
        url_decoded = unquote(raw_filename)

        # Then decode HTML entities (e.g., &gt; -> >, &amp; -> &)
        html_decoded = html.unescape(url_decoded)

        # Handle any remaining character encoding issues
        # Try to encode as latin1 and decode as utf-8 if needed
        try:
            if html_decoded.encode("latin1").decode("utf-8") != html_decoded:
                html_decoded = html_decoded.encode("latin1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass  # Keep original if encoding conversion fails

        return html_decoded

    except Exception:
        # If all decoding fails, return the original
        return raw_filename


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate text to a maximum length, adding suffix if truncated.

    Args:
        text: The text to truncate
        max_length: Maximum allowed length
        suffix: Suffix to add if truncated (default: "...")

    Returns:
        Truncated text with suffix if needed
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename by removing or replacing invalid characters.

    Args:
        filename: The filename to sanitize

    Returns:
        Sanitized filename
    """
    # Characters not allowed in filenames on various systems
    invalid_chars = '<>:"/\\|?*'

    result = filename
    for char in invalid_chars:
        result = result.replace(char, "_")

    # Remove leading/trailing spaces and dots
    result = result.strip(" .")

    return result
