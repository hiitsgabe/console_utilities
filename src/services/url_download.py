"""Pure helpers for direct URL downloads (GAB-14).

No pygame/service imports so this module is safe to load in isolation.
"""

import os
import re
from urllib.parse import urlparse


def is_valid_download_url(url):
    """Return True only for non-empty http(s) URLs with a network location."""
    if not url or not url.strip():
        return False
    parse = urlparse(url.strip())
    return parse.scheme in ("http", "https") and bool(parse.netloc)


def derive_download_filename(url):
    """Derive a safe filename from a URL, falling back to "download"."""
    parse = urlparse(url.strip())
    base = os.path.basename(parse.path)
    # urlparse already separates query/fragment, but strip defensively.
    base = base.split("?", 1)[0].split("#", 1)[0]
    result = re.sub(r'[<>:"/\\|?*]', "_", base)
    if not result or not result.strip("_ \t"):
        return "download"
    return result
