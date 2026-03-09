"""
Syncthing REST API client for save sync configuration.
Communicates with local Syncthing instance to auto-configure shared folders.
"""

import os
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple, Any

import requests

from constants import BUILD_TARGET, DEV_MODE


# Default systems with their Knulli/Batocera save paths
SYNC_SYSTEMS = [
    "psx", "snes", "n64", "scummvm", "gba", "gb", "gbc", "nds",
    "megadrive", "nes", "psp", "dreamcast", "mame", "fba",
    "segacd", "pcengine", "atari2600", "atari7800", "atarilynx",
    "wonderswan", "neogeo", "gamegear", "mastersystem",
]

SYNCTHING_API_URL = "http://localhost:8384"


class SyncthingService:
    """Client for Syncthing REST API."""

    def __init__(self, api_key: str = "", api_url: str = SYNCTHING_API_URL):
        self.api_key = api_key
        self.api_url = api_url

    def _headers(self) -> Dict[str, str]:
        return {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }

    def is_running(self) -> bool:
        """Check if Syncthing is reachable."""
        try:
            r = requests.get(
                f"{self.api_url}/rest/system/status",
                headers=self._headers(),
                timeout=3,
            )
            # 200 = OK, 403 = running but needs API key
            return r.status_code in (200, 403)
        except Exception:
            return False

    def get_device_id(self) -> str:
        """Get this device's Syncthing Device ID."""
        try:
            r = requests.get(
                f"{self.api_url}/rest/system/status",
                headers=self._headers(),
                timeout=5,
            )
            r.raise_for_status()
            return r.json().get("myID", "")
        except Exception:
            return ""

    def get_config(self) -> Dict[str, Any]:
        """Get current Syncthing config."""
        try:
            r = requests.get(
                f"{self.api_url}/rest/config",
                headers=self._headers(),
                timeout=5,
            )
            r.raise_for_status()
            return r.json()
        except Exception:
            return {}

    def add_device(self, device_id: str, name: str = "console_utils") -> bool:
        """Add a device to Syncthing."""
        try:
            device = {
                "deviceID": device_id,
                "name": name,
                "addresses": ["dynamic"],
                "autoAcceptFolders": True,
            }
            r = requests.post(
                f"{self.api_url}/rest/config/devices",
                headers=self._headers(),
                json=device,
                timeout=5,
            )
            return r.status_code in (200, 201)
        except Exception:
            return False

    def get_existing_folder_ids(self) -> List[str]:
        """Get list of existing shared folder IDs."""
        config = self.get_config()
        return [f["id"] for f in config.get("folders", [])]

    def add_folder(
        self,
        folder_id: str,
        label: str,
        path: str,
        device_ids: List[str],
    ) -> bool:
        """Add a shared folder to Syncthing."""
        try:
            devices = [{"deviceID": did} for did in device_ids]
            folder = {
                "id": folder_id,
                "label": label,
                "path": path,
                "devices": devices,
                "type": "sendreceive",
                "versioning": {
                    "type": "simple",
                    "params": {"keep": "5"},
                },
            }
            r = requests.post(
                f"{self.api_url}/rest/config/folders",
                headers=self._headers(),
                json=folder,
                timeout=5,
            )
            return r.status_code in (200, 201)
        except Exception:
            return False

    def remove_folder(self, folder_id: str) -> bool:
        """Remove a shared folder."""
        try:
            r = requests.delete(
                f"{self.api_url}/rest/config/folders/{folder_id}",
                headers=self._headers(),
                timeout=5,
            )
            return r.status_code in (200, 204)
        except Exception:
            return False

    def get_folder_status(self, folder_id: str) -> Dict[str, Any]:
        """Get sync status for a folder."""
        try:
            r = requests.get(
                f"{self.api_url}/rest/db/status",
                headers=self._headers(),
                params={"folder": folder_id},
                timeout=5,
            )
            r.raise_for_status()
            return r.json()
        except Exception:
            return {}

    def get_connections(self) -> Dict[str, Any]:
        """Get connected devices info."""
        try:
            r = requests.get(
                f"{self.api_url}/rest/system/connections",
                headers=self._headers(),
                timeout=5,
            )
            r.raise_for_status()
            return r.json().get("connections", {})
        except Exception:
            return {}

    @staticmethod
    def detect_api_key() -> str:
        """Try to read API key from Syncthing's config.xml."""
        config_paths = [
            os.path.expanduser("~/.config/syncthing/config.xml"),
            os.path.expanduser("~/.local/state/syncthing/config.xml"),
            os.path.expanduser("~/Library/Application Support/Syncthing/config.xml"),
            "/userdata/system/.config/syncthing/config.xml",
        ]
        # Android
        if BUILD_TARGET == "android":
            config_paths.append(
                "/storage/emulated/0/Android/data/com.github.catfriend1.syncthingandroid/files/config.xml"
            )
        for path in config_paths:
            try:
                if os.path.exists(path):
                    tree = ET.parse(path)
                    root = tree.getroot()
                    gui = root.find(".//gui")
                    if gui is not None:
                        api_key_elem = gui.find("apikey")
                        if api_key_elem is not None and api_key_elem.text:
                            return api_key_elem.text
            except Exception:
                continue
        return ""

    @staticmethod
    def get_save_path(system: str) -> str:
        """Get the default save path for a system on the current platform."""
        if DEV_MODE:
            return os.path.join(os.path.expanduser("~"), "game-saves", system)
        elif BUILD_TARGET == "android":
            return ""  # User must configure on Android
        elif os.path.exists("/userdata"):
            return f"/userdata/saves/{system}"
        else:
            # Desktop/host
            return os.path.join(os.path.expanduser("~"), "game-saves", system)

    @staticmethod
    def get_folder_id(system: str) -> str:
        """Get the Syncthing folder ID for a system."""
        return f"saves-{system}"

    def configure_all_systems(
        self,
        role: str,
        device_ids: List[str],
        base_path: str = "",
        folder_overrides: Optional[Dict[str, str]] = None,
    ) -> Tuple[int, int, List[str]]:
        """
        Configure shared folders for all systems.

        Args:
            role: "host" or "console"
            device_ids: List of remote device IDs to share with
            base_path: Base path for host saves (ignored for console)
            folder_overrides: Per-system path overrides (for Android)

        Returns:
            Tuple of (success_count, skip_count, error_systems)
        """
        existing = set(self.get_existing_folder_ids())
        overrides = folder_overrides or {}
        success = 0
        skipped = 0
        errors = []

        for system in SYNC_SYSTEMS:
            folder_id = self.get_folder_id(system)

            # Skip if already configured
            if folder_id in existing:
                skipped += 1
                continue

            # Determine path
            if role == "host":
                path = os.path.join(
                    base_path or os.path.join(os.path.expanduser("~"), "game-saves"),
                    system,
                )
            elif system in overrides:
                path = overrides[system]
            else:
                path = self.get_save_path(system)

            # Skip if no path (Android without override)
            if not path:
                skipped += 1
                continue

            # Create directory
            os.makedirs(path, exist_ok=True)

            if self.add_folder(folder_id, f"{system} saves", path, device_ids):
                success += 1
            else:
                errors.append(system)

        return success, skipped, errors

    def get_system_sync_status(self) -> Dict[str, str]:
        """
        Get sync status for all configured systems.

        Returns:
            Dict mapping system name to status string
        """
        existing = set(self.get_existing_folder_ids())
        statuses = {}
        for system in SYNC_SYSTEMS:
            folder_id = self.get_folder_id(system)
            if folder_id not in existing:
                statuses[system] = "not_configured"
            else:
                status = self.get_folder_status(folder_id)
                state = status.get("state", "unknown")
                statuses[system] = state  # "idle", "syncing", "error", etc.
        return statuses
