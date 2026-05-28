"""Pure JSON-API listing parser (GAB-15).

Dependency-free module: parses a JSON payload from a generic JSON-API ROM
source into either a plain list of filenames (default/back-compat mode) or a
list of enriched dicts (when a download URL template or a size field is
configured). No network, pygame, or services imports — safe to import anywhere.
"""

from typing import Any, Dict, List, Optional, Union


def parse_json_api_listing(
    data: Any,
    *,
    items_path: str = "files",
    id_field: str = "name",
    size_field: Optional[str] = None,
    download_url_template: Optional[str] = None,
    file_format: Optional[List[str]] = None,
) -> Union[List[str], List[Dict[str, Any]]]:
    """Parse a JSON-API listing payload.

    Args:
        data: Decoded JSON payload (expected to be a dict).
        items_path: Key under which the array of items lives.
        id_field: Key within each item holding the filename/id.
        size_field: Optional key holding the file size (enables enriched mode).
        download_url_template: Optional URL template with ``<id>`` placeholder
            (enables enriched mode).
        file_format: Optional list of allowed file extensions.

    Returns:
        list[str] in default mode, or list[dict] (filename/href/size) in
        enriched mode.
    """
    items = data.get(items_path) if isinstance(data, dict) else None
    if not isinstance(items, list):
        return []

    enriched = download_url_template is not None or size_field is not None

    def matches(name: Any) -> bool:
        if not file_format:
            return True
        return any(
            str(name).lower().endswith(ext.lower()) for ext in file_format
        )

    result: List[Any] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get(id_field)
        if not name:
            continue
        if not matches(name):
            continue

        if enriched:
            if download_url_template:
                href = download_url_template.replace("<id>", str(name))
            else:
                href = item.get("url", "")
            size = item.get(size_field, 0) if size_field else 0
            result.append({"filename": str(name), "href": href, "size": size})
        else:
            result.append(str(name))

    return result
