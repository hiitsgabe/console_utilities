"""
Syncthing Sync screen - Configure save sync between devices.
"""

import pygame
from typing import List, Dict, Any, Tuple, Optional, Set

from ui.theme import Theme, default_theme
from ui.templates.list_screen import ListScreenTemplate
from constants import BUILD_TARGET
from services.syncthing_service import SYNC_SYSTEMS


class SyncthingScreen:
    """
    Syncthing sync configuration screen.

    Shows different views based on setup step:
    - Checking: "Checking Syncthing..."
    - Not found: "Syncthing not running" message
    - Role select: Host vs Console choice
    - Device ID input: Enter host device ID (console mode)
    - Configured: System list with sync status
    """

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.template = ListScreenTemplate(theme)

    def render_checking(
        self, screen: pygame.Surface
    ) -> Tuple[Optional[pygame.Rect], List[pygame.Rect], int]:
        """Render checking state."""
        return self.template.render(
            screen,
            title="Syncthing Sync",
            items=["Checking Syncthing connection..."],
            highlighted=0,
            selected=set(),
            show_back=True,
            item_height=40,
        )

    def render_not_found(
        self, screen: pygame.Surface, highlighted: int
    ) -> Tuple[Optional[pygame.Rect], List[pygame.Rect], int]:
        """Render not found state."""
        items = [
            "--- Syncthing not found ---",
            "--- Install Syncthing and ---",
            "--- make sure it is running ---",
            "Retry Connection",
        ]
        divider_indices = {0, 1, 2}
        return self.template.render(
            screen,
            title="Syncthing Sync",
            items=items,
            highlighted=highlighted,
            selected=set(),
            show_back=True,
            item_height=40,
            item_spacing=8,
            divider_indices=divider_indices,
        )

    def get_not_found_max_items(self) -> int:
        """Get max items for not found screen."""
        return 4

    def render_role_select(
        self, screen: pygame.Surface, highlighted: int
    ) -> Tuple[Optional[pygame.Rect], List[pygame.Rect], int]:
        """Render role selection."""
        items = [
            "--- SELECT ROLE ---",
            "Host (Computer)",
            "Console (Knulli/Android)",
        ]
        divider_indices = {0}
        return self.template.render(
            screen,
            title="Syncthing Sync",
            items=items,
            highlighted=highlighted,
            selected=set(),
            show_back=True,
            item_height=40,
            item_spacing=8,
            divider_indices=divider_indices,
        )

    def _build_configured_items(
        self,
        settings: Dict[str, Any],
        device_id: str,
        system_statuses: Dict[str, str],
        status_message: str = "",
    ) -> Tuple[List[Any], List[str], Set[int]]:
        """
        Build items, actions, and divider indices for the configured screen.
        Single source of truth used by render, action lookup, and item count.

        Returns:
            Tuple of (display_items, action_list, divider_indices)
        """
        role = settings.get("syncthing_role", "")
        items = []
        actions = []
        divider_indices = set()

        def _add_divider(label: str):
            divider_indices.add(len(items))
            items.append(label)
            actions.append("divider")

        def _add_item(display, action: str):
            items.append(display)
            actions.append(action)

        # Status header — all info rows are dividers (non-interactive)
        _add_divider("--- STATUS ---")
        role_label = "Host" if role == "host" else "Console"
        _add_divider(f"--- Role: {role_label} ---")

        if role == "host":
            short_id = device_id[:20] + "..." if len(device_id) > 20 else device_id
            _add_divider(f"--- ID: {short_id} ---")
        else:
            host_id = settings.get("syncthing_host_device_id", "")
            short_id = host_id[:20] + "..." if len(host_id) > 20 else host_id
            _add_divider(f"--- Host: {short_id or 'Not set'} ---")

        if status_message:
            _add_divider(f"--- {status_message} ---")

        # Actions
        _add_divider("--- ACTIONS ---")
        _add_item("Sync All Systems", "sync_all")

        if role == "host":
            _add_item("Change Base Path", "change_base_path")

        # System list
        _add_divider("--- SYSTEMS ---")
        for system in SYNC_SYSTEMS:
            status = system_statuses.get(system, "not_configured")
            status_labels = {
                "not_configured": "-",
                "idle": "Synced",
                "syncing": "Syncing...",
                "scanning": "Scanning...",
                "error": "Error",
                "unknown": "?",
            }
            label = status_labels.get(status, status)
            if BUILD_TARGET == "android":
                # Android: always allow folder selection
                _add_item((system.upper(), label), f"configure_{system}")
            else:
                _add_item((system.upper(), label), f"system_{system}")

        # Reset
        _add_divider("--- SETTINGS ---")
        _add_item("Reconfigure", "reconfigure")

        return items, actions, divider_indices

    def render_configured(
        self,
        screen: pygame.Surface,
        highlighted: int,
        settings: Dict[str, Any],
        device_id: str,
        system_statuses: Dict[str, str],
        status_message: str = "",
    ) -> Tuple[Optional[pygame.Rect], List[pygame.Rect], int]:
        """Render configured state with system list."""
        items, _, divider_indices = self._build_configured_items(
            settings, device_id, system_statuses, status_message
        )

        return self.template.render(
            screen,
            title="Syncthing Sync",
            items=items,
            highlighted=highlighted,
            selected=set(),
            show_back=True,
            item_height=40,
            get_label=lambda x: x[0] if isinstance(x, tuple) else x,
            get_secondary=lambda x: x[1] if isinstance(x, tuple) else None,
            item_spacing=8,
            divider_indices=divider_indices,
        )

    def get_not_found_action(self, index: int) -> str:
        """Get action for not found screen."""
        # items: [divider, divider, divider, "Retry Connection"]
        if index == 3:
            return "retry"
        return "none"

    def get_role_select_action(self, index: int) -> str:
        """Get action for role select screen."""
        # items: [divider, "Host (Computer)", "Console (Knulli/Android)"]
        if index == 1:
            return "select_host"
        elif index == 2:
            return "select_console"
        return "none"

    def get_configured_action(
        self,
        index: int,
        settings: Dict[str, Any],
        system_statuses: Dict[str, str],
        status_message: str = "",
    ) -> str:
        """Get action for configured screen."""
        _, actions, _ = self._build_configured_items(
            settings, "", system_statuses, status_message
        )
        if index < len(actions):
            return actions[index]
        return "none"

    def get_configured_item_count(
        self,
        settings: Dict[str, Any],
        status_message: str = "",
    ) -> int:
        """Get total item count for configured screen."""
        items, _, _ = self._build_configured_items(
            settings, "", {}, status_message
        )
        return len(items)


# Default instance
syncthing_screen = SyncthingScreen()
