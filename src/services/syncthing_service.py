"""
Syncthing REST API client for save sync configuration.
Communicates with local Syncthing instance to auto-configure shared folders.
"""

import os
import traceback
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple, Any

import requests

from constants import BUILD_TARGET, DEV_MODE
from utils.logging import log_error


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
        except Exception as e:
            log_error("Syncthing: get_device_id failed", type(e).__name__, traceback.format_exc())
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
        except Exception as e:
            log_error("Syncthing: get_config failed", type(e).__name__, traceback.format_exc())
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
        except Exception as e:
            log_error("Syncthing: add_device failed", type(e).__name__, traceback.format_exc())
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
        except Exception as e:
            log_error("Syncthing: add_folder failed", type(e).__name__, traceback.format_exc())
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
        except Exception as e:
            log_error("Syncthing: remove_folder failed", type(e).__name__, traceback.format_exc())
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
        except Exception as e:
            log_error("Syncthing: get_folder_status failed", type(e).__name__, traceback.format_exc())
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
        except Exception as e:
            log_error("Syncthing: get_connections failed", type(e).__name__, traceback.format_exc())
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

    @staticmethod
    def sanitize_folder_id(name: str) -> str:
        """Convert a custom save name to a Syncthing folder ID.
        Example: 'Balatro Save' -> 'custom-balatro-save'
        """
        import re
        sanitized = name.lower().strip()
        sanitized = re.sub(r'[^a-z0-9\s-]', '', sanitized)
        sanitized = re.sub(r'\s+', '-', sanitized)
        sanitized = re.sub(r'-+', '-', sanitized).strip('-')
        return f"custom-{sanitized}"

    @staticmethod
    def write_sync_info(
        folder_path: str,
        name: str,
        source_device: str,
        source_path: str,
        sync_mode: str = "folder",
        sync_files: Optional[List[str]] = None,
    ) -> bool:
        """Write sync_info.json to a folder."""
        import json
        from datetime import datetime
        info = {
            "name": name,
            "source_device": source_device,
            "source_path": source_path,
            "sync_mode": sync_mode,
            "created": datetime.now().isoformat(),
        }
        if sync_mode == "files" and sync_files:
            info["sync_files"] = sync_files
        try:
            os.makedirs(folder_path, exist_ok=True)
            with open(os.path.join(folder_path, "sync_info.json"), "w") as f:
                json.dump(info, f, indent=2)
            return True
        except Exception as e:
            log_error("Syncthing: write_sync_info failed", type(e).__name__, traceback.format_exc())
            return False

    @staticmethod
    def write_stignore(folder_path: str, allowed_files: List[str]) -> bool:
        """Write .stignore that whitelists only specific files."""
        try:
            lines = ["!sync_info.json"]
            for f in allowed_files:
                lines.append(f"!{f}")
            lines.append("*")
            with open(os.path.join(folder_path, ".stignore"), "w") as fh:
                fh.write("\n".join(lines) + "\n")
            return True
        except Exception as e:
            log_error("Syncthing: write_stignore failed", type(e).__name__, traceback.format_exc())
            return False

    @staticmethod
    def read_sync_info(folder_path: str) -> Optional[Dict[str, Any]]:
        """Read sync_info.json from a folder. Returns None if not found."""
        import json
        info_path = os.path.join(folder_path, "sync_info.json")
        try:
            if os.path.exists(info_path):
                with open(info_path, "r") as f:
                    return json.load(f)
        except Exception:
            pass
        return None

    def add_custom_save(
        self,
        name: str,
        source_path: str,
        source_device: str,
        device_ids: List[str],
        sync_mode: str = "folder",
        sync_files: Optional[List[str]] = None,
    ) -> Optional[str]:
        """Create a custom save sync folder in Syncthing.
        Returns folder_id on success, None on failure.
        """
        folder_id = self.sanitize_folder_id(name)

        # Check if folder ID already exists, make unique if needed
        existing = set(self.get_existing_folder_ids())
        if folder_id in existing:
            i = 2
            while f"{folder_id}-{i}" in existing:
                i += 1
            folder_id = f"{folder_id}-{i}"

        # Write metadata
        self.write_sync_info(source_path, name, source_device, source_path, sync_mode, sync_files)

        # Write .stignore for file mode
        if sync_mode == "files" and sync_files:
            self.write_stignore(source_path, sync_files)

        # Add to Syncthing
        if self.add_folder(folder_id, name, source_path, device_ids):
            return folder_id
        return None

    def get_custom_save_statuses(self, custom_saves: List[Dict[str, str]]) -> Dict[str, str]:
        """Get sync status for custom save folders."""
        existing = set(self.get_existing_folder_ids())
        statuses = {}
        for save in custom_saves:
            fid = save.get("folder_id", "")
            if fid not in existing:
                statuses[fid] = "not_configured"
            else:
                status = self.get_folder_status(fid)
                statuses[fid] = status.get("state", "unknown")
        return statuses

    def discover_custom_saves(self, base_path: str) -> List[Dict[str, Any]]:
        """Scan custom save staging dirs for sync_info.json metadata."""
        custom_dir = os.path.join(base_path, "custom")
        saves = []
        if not os.path.isdir(custom_dir):
            return saves
        for entry in os.listdir(custom_dir):
            entry_path = os.path.join(custom_dir, entry)
            if os.path.isdir(entry_path):
                info = self.read_sync_info(entry_path)
                if info:
                    info["folder_id"] = entry
                    info["staging_path"] = entry_path
                    saves.append(info)
        return saves
