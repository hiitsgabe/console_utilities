"""
System settings screen - Individual system settings.
"""

import pygame
from typing import List, Dict, Any, Tuple, Optional, Set

from ui.theme import Theme, default_theme
from ui.templates.list_screen import ListScreenTemplate


def _get_source_label(system: Dict[str, Any]) -> str:
    """Derive a human-readable source label from the system URL."""
    url = system.get("url", "")
    if isinstance(url, list):
        url = url[0] if url else ""
    if not url:
        return "Unknown"
    if "archive.org" in url:
        return "Internet Archive"
    if "myrient" in url:
        return "Myrient"
    # Use the domain name
    try:
        from urllib.parse import urlparse

        host = urlparse(url).hostname or ""
        # Strip www. prefix
        if host.startswith("www."):
            host = host[4:]
        return host if host else "Custom URL"
    except Exception:
        return "Custom URL"


def _has_api_auth(system: Dict[str, Any]) -> bool:
    """Check if system uses API-based authentication (editable credentials)."""
    auth = system.get("auth", {})
    if not auth:
        return False
    auth_type = auth.get("type", "")
    # ia_s3 has its own keys managed via IA login, not editable here
    if auth_type == "ia_s3":
        return False
    # Token-based auth (bearer or cookie) is editable
    if "token" in auth or auth.get("auth_message"):
        return True
    return False


class SystemSettingsScreen:
    """
    Individual system settings screen.

    Displays settings for a single system:
    - Source info
    - Hide/Show system
    - Set custom folder
    - Edit auth token (if applicable)
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.template = ListScreenTemplate(theme)

    def _get_items(
        self,
        system: Dict[str, Any],
        is_hidden: bool,
        system_settings: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[Any], Set[int]]:
        """Build items list dynamically based on system config."""
        items = []
        divider_indices = set()
        sys_s = system_settings or {}

        # Source info section
        divider_indices.add(len(items))
        items.append("--- SOURCE ---")
        source_label = _get_source_label(system)
        items.append(("Source", source_label))

        # Settings section
        divider_indices.add(len(items))
        items.append("--- SETTINGS ---")
        items.append(("Hide System", "ON" if is_hidden else "OFF"))
        custom_folder = sys_s.get("custom_folder", "")
        folder_value = self._shorten_path(custom_folder) if custom_folder else "Default"
        items.append(("Set Custom Folder", folder_value))
        should_unzip = sys_s.get("should_unzip", system.get("should_unzip", False))
        items.append(("Auto-extract ZIPs", "ON" if should_unzip else "OFF"))

        # Auth section (only for token-based auth)
        if _has_api_auth(system):
            divider_indices.add(len(items))
            items.append("--- AUTHENTICATION ---")
            auth = system.get("auth", {})
            token = auth.get("token", "")
            if token:
                # Show masked token
                if len(token) > 6:
                    display = token[:3] + "..." + token[-3:]
                else:
                    display = "Set"
            else:
                display = "Not set"
            items.append(("Edit Auth Token", display))

        return items, divider_indices

    def render(
        self,
        screen: pygame.Surface,
        highlighted: int,
        system: Dict[str, Any],
        is_hidden: bool = False,
        system_settings: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[pygame.Rect], List[pygame.Rect], int]:
        """
        Render the system settings screen.

        Args:
            screen: Surface to render to
            highlighted: Currently highlighted index
            system: System configuration dict
            is_hidden: Whether the system is currently hidden
            system_settings: Per-system settings from config

        Returns:
            Tuple of (back_button_rect, item_rects, scroll_offset)
        """
        system_name = system.get("name", "Unknown System")
        items, divider_indices = self._get_items(system, is_hidden, system_settings)

        return self.template.render(
            screen,
            title=f"{system_name} Settings",
            items=items,
            highlighted=highlighted,
            selected=set(),
            show_back=True,
            item_height=40,
            get_label=lambda x: x[0] if isinstance(x, tuple) else x,
            get_secondary=lambda x: x[1] if isinstance(x, tuple) else None,
            divider_indices=divider_indices,
            item_spacing=8,
        )

    def _shorten_path(self, path: str, max_length: int = 25) -> str:
        """Shorten a path for display."""
        if not path:
            return ""
        if len(path) <= max_length:
            return path

        # Show last parts of path
        parts = path.replace("\\", "/").split("/")
        result = ""
        for part in reversed(parts):
            if len(result) + len(part) + 1 <= max_length - 3:
                result = "/" + part + result if result else part
            else:
                break

        return "..." + result if result else "..." + path[-max_length + 3 :]

    def get_setting_action(
        self,
        index: int,
        system: Dict[str, Any],
        is_hidden: bool = False,
        system_settings: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Get the action for a settings item.

        Args:
            index: Selected index
            system: System configuration dict
            is_hidden: Whether the system is currently hidden
            system_settings: Per-system settings from config

        Returns:
            Action string
        """
        items, divider_indices = self._get_items(system, is_hidden, system_settings)

        if index in divider_indices:
            return "divider"

        if index < len(items):
            item = items[index]
            label = item[0] if isinstance(item, tuple) else item
            actions = {
                "Source": "noop",
                "Hide System": "toggle_hide_system",
                "Set Custom Folder": "set_custom_folder",
                "Auto-extract ZIPs": "toggle_should_unzip",
                "Edit Auth Token": "edit_auth_token",
            }
            return actions.get(label, "unknown")

        return "unknown"

    def get_max_items(
        self,
        system: Dict[str, Any],
        is_hidden: bool = False,
        system_settings: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Get total number of items."""
        items, _ = self._get_items(system, is_hidden, system_settings)
        return len(items)


# Default instance
system_settings_screen = SystemSettingsScreen()
