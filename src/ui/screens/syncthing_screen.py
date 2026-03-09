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
            "--- STATUS ---",
            "Syncthing is not running",
            "",
            "--- INSTRUCTIONS ---",
            "Install Syncthing on this device",
            "and make sure it is running.",
            "",
            "Retry Connection",
        ]
        divider_indices = {0, 3}
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
        role = settings.get("syncthing_role", "")
        items = []
        divider_indices = set()

        # Status header
        divider_indices.add(len(items))
        items.append("--- STATUS ---")
        role_label = "Host" if role == "host" else "Console"
        items.append(("Role", role_label))

        if role == "host":
            # Show device ID for copying
            short_id = device_id[:20] + "..." if len(device_id) > 20 else device_id
            items.append(("Device ID", short_id))
        else:
            host_id = settings.get("syncthing_host_device_id", "")
            short_id = host_id[:20] + "..." if len(host_id) > 20 else host_id
            items.append(("Host", short_id or "Not set"))

        if status_message:
            items.append(("Status", status_message))

        # Actions
        divider_indices.add(len(items))
        items.append("--- ACTIONS ---")
        items.append("Sync All Systems")

        if role == "host":
            items.append("Change Base Path")

        # System list
        divider_indices.add(len(items))
        items.append("--- SYSTEMS ---")
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
            items.append((system.upper(), label))

        # Reset
        divider_indices.add(len(items))
        items.append("--- SETTINGS ---")
        items.append("Reconfigure")

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
        # "Retry Connection" is at index 7
        if index == 7:
            return "retry"
        return "none"

    def get_role_select_action(self, index: int) -> str:
        """Get action for role select screen."""
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
    ) -> str:
        """Get action for configured screen."""
        role = settings.get("syncthing_role", "")
        status_message = ""  # We don't have access to status_message here

        # Build a flat action list matching the items
        actions = []
        actions.append("divider")  # --- STATUS ---
        actions.append("none")  # Role
        actions.append("copy_device_id" if role == "host" else "none")  # Device ID / Host

        # Note: status_message item is optional, but we can't know if it's present
        # from here. The caller should account for this. For now we skip it.

        actions.append("divider")  # --- ACTIONS ---
        actions.append("sync_all")  # Sync All Systems

        if role == "host":
            actions.append("change_base_path")  # Change Base Path

        actions.append("divider")  # --- SYSTEMS ---
        for system in SYNC_SYSTEMS:
            status = system_statuses.get(system, "not_configured")
            if BUILD_TARGET == "android" and status == "not_configured":
                actions.append(f"configure_{system}")
            else:
                actions.append(f"system_{system}")

        actions.append("divider")  # --- SETTINGS ---
        actions.append("reconfigure")  # Reconfigure

        if index < len(actions):
            return actions[index]
        return "none"

    def get_configured_item_count(
        self,
        settings: Dict[str, Any],
    ) -> int:
        """Get total item count for configured screen."""
        role = settings.get("syncthing_role", "")
        # STATUS: divider + role + device_id = 3
        # ACTIONS: divider + sync_all + (change_base_path if host) = 2 or 3
        # SYSTEMS: divider + len(SYNC_SYSTEMS)
        # SETTINGS: divider + reconfigure = 2
        count = 3 + 2 + 1 + len(SYNC_SYSTEMS) + 2
        if role == "host":
            count += 1
        return count


# Default instance
syncthing_screen = SyncthingScreen()
