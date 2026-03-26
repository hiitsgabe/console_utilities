"""
Syncthing REST API client for save sync configuration.
Communicates with local Syncthing instance to auto-configure shared folders.
"""

import os
import socket
import struct
import threading
import traceback
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple, Any

import requests

from constants import BUILD_TARGET, DEV_MODE
from utils.logging import log_error


# Default systems with their Knulli/Batocera save paths
SYNC_SYSTEMS = [
    "psx",
    "snes",
    "n64",
    "scummvm",
    "gba",
    "gb",
    "gbc",
    "nds",
    "megadrive",
    "nes",
    "psp",
    "dreamcast",
    "mame",
    "fba",
    "segacd",
    "pcengine",
    "atari2600",
    "atari7800",
    "atarilynx",
    "wonderswan",
    "neogeo",
    "gamegear",
    "mastersystem",
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

    LDP_MAGIC = 0x2EA7D90B

    @staticmethod
    def _decode_varint(data: bytes, offset: int) -> Tuple[int, int]:
        """Decode a protobuf varint. Returns (value, bytes_consumed)."""
        result = 0
        shift = 0
        consumed = 0
        while offset < len(data):
            byte = data[offset]
            result |= (byte & 0x7F) << shift
            offset += 1
            consumed += 1
            if not (byte & 0x80):
                break
            shift += 7
        return result, consumed

    @staticmethod
    def decode_ldp_announce(data: bytes) -> Optional[Tuple[bytes, List[str]]]:
        """
        Decode a Syncthing Local Discovery Protocol v4 announcement.
        Returns (device_id_bytes, addresses) or None if invalid.
        """
        if len(data) < 4:
            return None

        magic = struct.unpack(">I", data[:4])[0]
        if magic != SyncthingService.LDP_MAGIC:
            return None

        # Parse protobuf fields manually
        device_id = b""
        addresses = []
        offset = 4

        while offset < len(data):
            tag_val, consumed = SyncthingService._decode_varint(data, offset)
            offset += consumed
            field_number = tag_val >> 3
            wire_type = tag_val & 0x07

            if wire_type == 0:  # Varint
                _, consumed = SyncthingService._decode_varint(data, offset)
                offset += consumed
            elif wire_type == 1:  # 64-bit fixed
                offset += 8
            elif wire_type == 5:  # 32-bit fixed
                offset += 4
            elif wire_type == 2:  # Length-delimited
                length, consumed = SyncthingService._decode_varint(data, offset)
                offset += consumed
                field_data = data[offset : offset + length]
                offset += length

                if field_number == 1:
                    device_id = field_data
                elif field_number == 2:
                    try:
                        addresses.append(field_data.decode("utf-8"))
                    except UnicodeDecodeError:
                        pass
            else:
                # Unknown wire type — can't determine size, bail
                break

        if not device_id:
            return None

        return device_id, addresses

    @staticmethod
    def _luhn_base32_check(s: str) -> str:
        """Calculate Luhn check character for a base32 string."""
        # Syncthing uses a custom Luhn mod 32 algorithm
        # Reference: syncthing/lib/protocol/deviceid.go
        LUHN_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
        factor = 1
        sum_val = 0
        n = len(LUHN_ALPHABET)

        for char in s:
            code_point = LUHN_ALPHABET.index(char)
            addend = factor * code_point
            factor = 1 if factor == 2 else 2
            addend = (addend // n) + (addend % n)
            sum_val += addend

        remainder = sum_val % n
        check_code_point = (n - remainder) % n
        return LUHN_ALPHABET[check_code_point]

    @staticmethod
    def decode_device_id(raw_bytes: bytes) -> str:
        """
        Convert 32 raw bytes to Syncthing's display format.
        Format: XXXXXXX-XXXXXXX-XXXXXXX-XXXXXXX-XXXXXXX-XXXXXXX-XXXXXXX-XXXXXXX

        Algorithm (from syncthing/lib/protocol/deviceid.go):
        1. Base32 encode 32 bytes -> 52 chars
        2. Split into 4 groups of 13 chars
        3. Append Luhn check char to each 13-char group -> 56 chars total
        4. Split into 8 groups of 7, joined by dashes
        """
        import base64

        b32 = base64.b32encode(raw_bytes).decode("ascii").rstrip("=")

        # Insert Luhn check after every 13 chars
        luhnified = ""
        for i in range(0, len(b32), 13):
            chunk = b32[i : i + 13]
            luhnified += chunk + SyncthingService._luhn_base32_check(chunk)

        # Split into groups of 7 with dashes
        return "-".join(luhnified[i : i + 7] for i in range(0, len(luhnified), 7))

    @staticmethod
    def _extract_ip(addresses: List[str]) -> str:
        """Extract first usable IPv4 address from Syncthing address list.
        Addresses are like 'tcp://192.168.1.50:22000'. Skips IPv6 and 0.0.0.0."""
        import re

        for addr in addresses:
            # Match tcp:// or quic:// followed by IPv4:port
            m = re.match(r"(?:tcp|quic)://(\d+\.\d+\.\d+\.\d+):\d+", addr)
            if m:
                ip = m.group(1)
                if ip != "0.0.0.0":
                    return ip
        return ""

    @staticmethod
    def _discover_via_rest_api(
        own_device_id: str = "",
        on_device_found: Optional[Any] = None,
    ) -> List[Dict[str, str]]:
        """Discover devices using the local Syncthing REST API.
        Fallback when UDP port 21027 is unavailable (held by local Syncthing)."""
        api_key = SyncthingService.detect_api_key()
        if not api_key:
            return []

        try:
            r = requests.get(
                f"{SYNCTHING_API_URL}/rest/system/discovery",
                headers={"X-API-Key": api_key},
                verify=False,
                timeout=5,
            )
            if r.status_code != 200:
                return []
            data = r.json()
        except Exception:
            return []

        results = []
        for device_id, info in data.items():
            if device_id == own_device_id:
                continue
            addresses = info.get("addresses", [])
            ip = SyncthingService._extract_ip(addresses)
            if not ip:
                continue
            device = {
                "device_id": device_id,
                "name": device_id[:7],
                "ip": ip,
            }
            results.append(device)
            if on_device_found:
                on_device_found(device)

        return results

    @staticmethod
    def discover_local_devices(
        timeout: int = 31,
        own_device_id: str = "",
        stop_event: Optional["threading.Event"] = None,
        on_device_found: Optional[Any] = None,
        on_tick: Optional[Any] = None,
    ) -> List[Dict[str, str]]:
        """
        Discover Syncthing devices on the local network.

        First tries UDP LDP broadcasts on port 21027. If the port is
        unavailable (e.g. local Syncthing holds it), falls back to
        querying the local Syncthing REST API for already-discovered devices.

        Args:
            timeout: How long to listen in seconds (default 31, covers one full broadcast cycle)
            own_device_id: This device's ID to filter out
            stop_event: Threading event to signal early stop (e.g., Back button)
            on_device_found: Callback(device_dict) called when a new device is found
            on_tick: Callback(seconds_left) called each second for countdown

        Returns:
            List of dicts with keys: device_id, name, ip
        """
        import time

        results = {}  # device_id -> {device_id, name, ip}

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # Try SO_REUSEPORT first (needed on Linux when Syncthing holds the port)
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except (AttributeError, OSError):
                pass
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.settimeout(1.0)  # 1-second recv timeout for responsive stop/tick
            sock.bind(("", 21027))
        except OSError:
            # Can't bind — local Syncthing holds the port; use REST API instead
            return SyncthingService._discover_via_rest_api(
                own_device_id, on_device_found
            )

        start = time.monotonic()
        try:
            while True:
                elapsed = time.monotonic() - start
                if elapsed >= timeout:
                    break

                remaining = max(0, int(timeout - elapsed))

                if stop_event and stop_event.is_set():
                    break

                if on_tick:
                    on_tick(remaining)

                try:
                    data, addr = sock.recvfrom(4096)
                except socket.timeout:
                    continue
                except OSError:
                    break  # Socket closed (stop_event)

                result = SyncthingService.decode_ldp_announce(data)
                if result is None:
                    continue

                raw_id, addresses = result
                device_id = SyncthingService.decode_device_id(raw_id)

                if device_id == own_device_id:
                    continue
                if device_id in results:
                    continue

                ip = SyncthingService._extract_ip(addresses)
                if not ip:
                    continue

                # Short ID as fallback name
                short_id = device_id[:7]
                device = {
                    "device_id": device_id,
                    "name": short_id,
                    "ip": ip,
                }
                results[device_id] = device

                if on_device_found:
                    on_device_found(device)
        finally:
            sock.close()

        return list(results.values())

    def resolve_device_names(
        self, devices: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """
        Resolve device names from local Syncthing config.
        Updates the 'name' field for any device whose ID is known locally.
        Returns the same list with names updated in-place.
        """
        try:
            config = self.get_config()
            known = {}
            for d in config.get("devices", []):
                did = d.get("deviceID", "")
                dname = d.get("name", "")
                if did and dname:
                    known[did] = dname

            for device in devices:
                did = device.get("device_id", "")
                if did in known:
                    device["name"] = known[did]
        except Exception:
            pass  # Best-effort — keep short ID fallback

        return devices

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
            log_error(
                "Syncthing: get_device_id failed",
                type(e).__name__,
                traceback.format_exc(),
            )
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
            log_error(
                "Syncthing: get_config failed", type(e).__name__, traceback.format_exc()
            )
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
            log_error(
                "Syncthing: add_device failed", type(e).__name__, traceback.format_exc()
            )
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
            log_error(
                "Syncthing: add_folder failed", type(e).__name__, traceback.format_exc()
            )
            return False

    def get_pending_devices(self) -> Dict[str, Any]:
        """Get pending device requests (devices wanting to connect).
        Returns dict keyed by device ID with name/address/time."""
        try:
            r = requests.get(
                f"{self.api_url}/rest/cluster/pending/devices",
                headers=self._headers(),
                timeout=5,
            )
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return {}

    def get_pending_folders(self) -> Dict[str, Any]:
        """Get pending folder requests (folders offered by remote devices).
        Returns dict keyed by folder ID with offeredBy info."""
        try:
            r = requests.get(
                f"{self.api_url}/rest/cluster/pending/folders",
                headers=self._headers(),
                timeout=5,
            )
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return {}

    def accept_pending_devices_and_folders(
        self,
        base_path: str = "",
    ) -> Tuple[int, int]:
        """Accept all pending devices and folders.

        Adds pending devices with autoAcceptFolders=True, then accepts
        pending folders with appropriate paths.

        Args:
            base_path: Base path for save folders (host mode)

        Returns:
            Tuple of (devices_accepted, folders_accepted)
        """
        devices_accepted = 0
        folders_accepted = 0

        # Accept pending devices
        pending_devices = self.get_pending_devices()
        for device_id, info in pending_devices.items():
            name = info.get("name", device_id[:7])
            if self.add_device(device_id, name):
                devices_accepted += 1

        # Accept pending folders
        pending_folders = self.get_pending_folders()
        existing = set(self.get_existing_folder_ids())

        for folder_id, info in pending_folders.items():
            if folder_id in existing:
                continue

            # Determine label and offering device IDs
            offered_by = info.get("offeredBy", {})
            device_ids = list(offered_by.keys())
            if not device_ids:
                continue

            # Use first offerer's label, fall back to folder_id
            first_offer = next(iter(offered_by.values()), {})
            label = first_offer.get("label", folder_id)

            # Derive path: if folder_id matches our saves-{system} pattern,
            # use the standard host path; otherwise use base_path + folder_id
            system = None
            if folder_id.startswith("saves-"):
                system = folder_id[len("saves-"):]

            if system and system in SYNC_SYSTEMS:
                path = os.path.join(
                    base_path
                    or os.path.join(os.path.expanduser("~"), "game-saves"),
                    system,
                )
            else:
                path = os.path.join(
                    base_path
                    or os.path.join(os.path.expanduser("~"), "game-saves"),
                    folder_id,
                )

            try:
                os.makedirs(path, exist_ok=True)
            except OSError:
                continue

            if self.add_folder(folder_id, label, path, device_ids):
                folders_accepted += 1

        return devices_accepted, folders_accepted

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
            log_error(
                "Syncthing: remove_folder failed",
                type(e).__name__,
                traceback.format_exc(),
            )
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
            log_error(
                "Syncthing: get_folder_status failed",
                type(e).__name__,
                traceback.format_exc(),
            )
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
            log_error(
                "Syncthing: get_connections failed",
                type(e).__name__,
                traceback.format_exc(),
            )
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
            try:
                os.makedirs(path, exist_ok=True)
            except OSError as e:
                log_error(
                    f"Syncthing: cannot create {path}",
                    type(e).__name__,
                    str(e),
                )
                errors.append(system)
                continue

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
        sanitized = re.sub(r"[^a-z0-9\s-]", "", sanitized)
        sanitized = re.sub(r"\s+", "-", sanitized)
        sanitized = re.sub(r"-+", "-", sanitized).strip("-")
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
            log_error(
                "Syncthing: write_sync_info failed",
                type(e).__name__,
                traceback.format_exc(),
            )
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
            log_error(
                "Syncthing: write_stignore failed",
                type(e).__name__,
                traceback.format_exc(),
            )
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
        self.write_sync_info(
            source_path, name, source_device, source_path, sync_mode, sync_files
        )

        # Write .stignore for file mode
        if sync_mode == "files" and sync_files:
            self.write_stignore(source_path, sync_files)

        # Add to Syncthing
        if self.add_folder(folder_id, name, source_path, device_ids):
            return folder_id
        return None

    def get_custom_save_statuses(
        self, custom_saves: List[Dict[str, str]]
    ) -> Dict[str, str]:
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
