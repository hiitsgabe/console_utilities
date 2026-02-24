"""
PortMaster loader and installer service.

Handles fetching the port catalog, and installing ports following
the same process as the real PortMaster/harbourmaster:
  1. Download zip + verify MD5
  2. Extract with proper file routing (.sh scripts vs data dirs)
  3. Write port.json with status "Installed"
  4. Inject PM signature into .sh files
  5. Fix permissions (chmod) on Linux
  6. Download runtime .squashfs dependencies
  7. Update gamelist.xml for EmulationStation
"""

import hashlib
import json
import os
import platform
import shutil
import subprocess
import time
import traceback
from typing import List, Dict, Any, Tuple, Optional, Callable
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import requests

from utils.logging import log_error

# Files that are allowed at the zip root but should be moved into the
# port data subdirectory during extraction (matching harbourmaster).
_NON_SCRIPT_TOP_LEVEL = {
    "cover.jpg",
    "cover.png",
    "gameinfo.xml",
    "port.json",
    "readme.md",
    "screenshot.png",
    "screenshot.jpg",
}


class PortMasterLoader:
    """
    Loads port data from the PortMaster GitHub repository.

    Uses two data sources:
    - PortMaster-Info/ports.json for the port catalog (stable, no rate limits)
    - PortMaster-New release ports.json for runtime/utils data (has utils section)
    """

    PORTS_JSON_URL = (
        "https://raw.githubusercontent.com/PortsMaster/PortMaster-Info/main/ports.json"
    )
    RUNTIMES_JSON_URL = "https://github.com/PortsMaster/PortMaster-New/releases/latest/download/ports.json"
    CACHE_TTL = 3600  # 1 hour

    def __init__(self, settings: Dict[str, Any]):
        self.settings = settings
        self._ports_cache = None
        self._runtimes_cache: Dict[str, Dict] = {}
        self._cache_time = 0

    def fetch_ports(
        self, force_refresh=False
    ) -> Tuple[bool, List[Dict[str, Any]], str]:
        """
        Fetch port catalog and runtime data, return flat list of port dicts.

        Returns:
            Tuple of (success, ports_list, error_message)
        """
        if (
            not force_refresh
            and self._ports_cache
            and (time.time() - self._cache_time < self.CACHE_TTL)
        ):
            return True, self._ports_cache, ""

        try:
            resp = requests.get(self.PORTS_JSON_URL, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            # Fetch runtime data from the release ports.json (has utils section)
            self._fetch_runtimes()

            ports = []
            for key, port_data in data.get("ports", {}).items():
                attr = port_data.get("attr", {})
                source = port_data.get("source", {})
                portname = key.replace(".zip", "")
                image_info = attr.get("image", {})
                screenshot = image_info.get("screenshot", "")
                if screenshot:
                    banner_url = f"https://raw.githubusercontent.com/PortsMaster/PortMaster-New/main/ports/{portname}/{screenshot}"
                else:
                    banner_url = ""
                ports.append(
                    {
                        "name": key,
                        "title": attr.get("title", portname),
                        "desc": attr.get("desc", ""),
                        "inst": attr.get("inst", ""),
                        "genres": attr.get("genres", []),
                        "rtr": attr.get("rtr", False),
                        "porter": attr.get("porter", []),
                        "download_url": source.get("url", ""),
                        "download_size": source.get("size", 0),
                        "md5": source.get("md5", ""),
                        "date_added": source.get("date_added", ""),
                        "date_updated": source.get("date_updated", ""),
                        "runtime": attr.get("runtime", []),
                        "availability": attr.get("availability", "unknown"),
                        "banner_url": banner_url,
                        # Keep raw items list for the installer
                        "items": port_data.get("items", []),
                        "items_opt": port_data.get("items_opt"),
                        "arch": attr.get("arch", []),
                        "reqs": attr.get("reqs", []),
                    }
                )
            ports.sort(key=lambda p: p["title"].lower())
            self._ports_cache = ports
            self._cache_time = time.time()
            return True, ports, ""
        except Exception as e:
            return False, [], str(e)

    def _fetch_runtimes(self):
        """
        Fetch runtime data from the PortMaster-New release ports.json.

        The PortMaster-Info ports.json only has 'ports' and 'ratings'.
        Runtime download info (urls, md5, sizes) lives in the 'utils'
        section of the release ports.json from PortMaster-New.

        Builds a cache keyed by runtime filename (e.g. 'mono-6.12.0.122-aarch64.squashfs').
        Architecture variants (e.g. 'ags_3.6.x86_64.squashfs') are stored
        under both their actual key and their runtime_name for lookup.
        """
        try:
            resp = requests.get(self.RUNTIMES_JSON_URL, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            self._runtimes_cache = {}
            for key, util_data in data.get("utils", {}).items():
                if not key.endswith(".squashfs"):
                    continue
                # Store under the actual filename key
                self._runtimes_cache[key] = util_data
                # Also store under runtime_name if different (for arch variants)
                runtime_name = util_data.get("runtime_name", "")
                if runtime_name and runtime_name != key:
                    # Only overwrite if we don't already have the base name
                    # (prefer the default/aarch64 variant)
                    if runtime_name not in self._runtimes_cache:
                        self._runtimes_cache[runtime_name] = util_data

        except Exception as e:
            log_error(f"Failed to fetch runtime data: {e}")
            # Non-fatal: ports will still work, just without runtime downloads

    def get_genres(self, ports: List[Dict[str, Any]]) -> List[str]:
        """Extract unique sorted genre list with 'All' prepended."""
        genres = set()
        for p in ports:
            for g in p.get("genres", []):
                genres.add(g)
        return ["All"] + sorted(genres)

    def filter_ports(
        self,
        ports: List[Dict[str, Any]],
        genre: str = "",
        query: str = "",
    ) -> List[Dict[str, Any]]:
        """Filter ports by genre and/or search query."""
        result = ports
        if genre and genre != "All":
            result = [p for p in result if genre in p.get("genres", [])]
        if query:
            q = query.lower()
            result = [p for p in result if q in p.get("title", "").lower()]
        return result

    def get_runtime_info(self, runtime_name: str) -> Optional[Dict]:
        """Look up a runtime's download info from the cached utils data.

        Handles cases where ports reference runtimes without the .squashfs
        suffix (e.g. 'weston_pkg_0.2' instead of 'weston_pkg_0.2.squashfs').
        """
        info = self._runtimes_cache.get(runtime_name)
        if info:
            return info
        # Try with .squashfs suffix appended
        if not runtime_name.endswith(".squashfs"):
            return self._runtimes_cache.get(runtime_name + ".squashfs")
        return None


class PortMasterInstaller:
    """
    Installs a PortMaster port following the harbourmaster pipeline.

    The install flow:
      1. Download zip to work_dir, verify MD5
      2. Extract zip with proper routing:
         - Root-level .sh scripts  -> ports_dir  (roms/ports/)
         - Root-level non-script   -> ports_dir/portname/
         - Everything else         -> ports_dir/
      3. Write port.json with status "Installed"
      4. Inject PM signature into .sh files
      5. Fix file permissions
      6. Download required runtime .squashfs files to libs_dir
      7. Update gamelist.xml with gameinfo.xml entries
    """

    INSTALL_SCRIPT_URL = "https://github.com/PortsMaster/PortMaster-GUI/releases/latest/download/Install.PortMaster.sh"

    def __init__(
        self,
        settings: Dict[str, Any],
        loader: PortMasterLoader,
    ):
        self.settings = settings
        self.loader = loader

    @property
    def work_dir(self) -> str:
        from constants import SCRIPT_DIR

        return self.settings.get("work_dir", os.path.join(SCRIPT_DIR, "downloads"))

    @property
    def roms_dir(self) -> str:
        from constants import SCRIPT_DIR

        return self.settings.get("roms_dir", os.path.join(SCRIPT_DIR, "roms"))

    @property
    def ports_dir(self) -> str:
        """Where port scripts and data live: roms/ports/"""
        return os.path.join(self.roms_dir, "ports")

    # ------------------------------------------------------------------
    # Base package detection & install
    # ------------------------------------------------------------------

    # Candidate PortMaster directories in priority order (matching the
    # same paths that port .sh scripts check for ``$controlfolder``).
    _PM_DIR_CANDIDATES = [
        "/opt/system/Tools/PortMaster",
        "/opt/tools/PortMaster",
    ]

    def get_portmaster_dir(self) -> Optional[str]:
        """Return the detected PortMaster install directory, or None.

        Checks known system paths first, then XDG_DATA_HOME, then the
        fallback inside roms/ports/.
        """
        for d in self._PM_DIR_CANDIDATES:
            if os.path.isfile(os.path.join(d, "control.txt")):
                return d

        xdg = os.path.join(
            os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share")),
            "PortMaster",
        )
        if os.path.isfile(os.path.join(xdg, "control.txt")):
            return xdg

        fallback = os.path.join(self.ports_dir, "PortMaster")
        if os.path.isfile(os.path.join(fallback, "control.txt")):
            return fallback

        return None

    def is_base_installed(self) -> bool:
        """Check if the PortMaster base package is installed."""
        return self.get_portmaster_dir() is not None

    @property
    def libs_dir(self) -> str:
        """Where runtime .squashfs files live.

        Uses the detected PortMaster directory so runtimes end up next
        to the rest of the PortMaster install.  Falls back to
        roms/ports/PortMaster/libs/ if the base hasn't been installed yet.
        """
        pm_dir = self.get_portmaster_dir()
        if pm_dir:
            return os.path.join(pm_dir, "libs")
        return os.path.join(self.ports_dir, "PortMaster", "libs")

    def install_base_package(
        self,
        progress_cb: Optional[Callable[[str, float], None]] = None,
    ) -> Tuple[bool, str]:
        """Download and run the official Install.PortMaster.sh installer.

        Args:
            progress_cb: Optional callback ``(status_text, progress_0_to_1)``

        Returns:
            (success, error_message)
        """
        os.makedirs(self.ports_dir, exist_ok=True)
        script_path = os.path.join(self.ports_dir, "Install.PortMaster.sh")

        try:
            # Download
            if progress_cb:
                progress_cb("Downloading PortMaster installer...", 0.0)

            resp = requests.get(self.INSTALL_SCRIPT_URL, stream=True, timeout=60)
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            downloaded = 0
            last_update = time.time()

            with open(script_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        now = time.time()
                        if progress_cb and total > 0 and now - last_update >= 0.3:
                            progress_cb(
                                "Downloading PortMaster installer...",
                                downloaded / total * 0.5,
                            )
                            last_update = now

            # Make executable and run
            if progress_cb:
                progress_cb("Running installer...", 0.6)

            os.chmod(script_path, 0o755)

            result = subprocess.run(
                ["bash", script_path],
                cwd=self.ports_dir,
                capture_output=True,
                timeout=120,
            )

            if result.returncode != 0:
                stderr = result.stderr.decode("utf-8", errors="replace")[:200]
                return (
                    False,
                    f"Installer exited with code {result.returncode}: {stderr}",
                )

            if progress_cb:
                progress_cb("PortMaster installed!", 1.0)

            return True, ""

        except subprocess.TimeoutExpired:
            return False, "Installer timed out after 120 seconds"
        except Exception as e:
            return False, str(e)
        finally:
            # Clean up install script
            if os.path.exists(script_path):
                try:
                    os.remove(script_path)
                except OSError:
                    pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def install_port(
        self,
        port: Dict[str, Any],
        progress_cb: Optional[Callable[[str, float], None]] = None,
    ) -> Tuple[bool, str]:
        """
        Install a port end-to-end.

        Args:
            port: Port dict from PortMasterLoader.fetch_ports()
            progress_cb: Optional callback ``(status_text, progress_0_to_1)``

        Returns:
            (success, error_message)
        """
        portname = port["name"].replace(".zip", "")
        undo_files: List[str] = []

        try:
            # --- 1. Download ---
            if progress_cb:
                progress_cb("Downloading...", 0.0)

            zip_path = self._download_zip(port, progress_cb)
            if zip_path is None:
                return False, "Download failed"

            # --- 2. Verify MD5 ---
            if progress_cb:
                progress_cb("Verifying checksum...", 0.0)

            expected_md5 = port.get("md5", "")
            if expected_md5:
                actual_md5 = self._compute_md5(zip_path)
                if actual_md5 != expected_md5:
                    os.remove(zip_path)
                    return False, f"MD5 mismatch: expected {expected_md5[:8]}..."

            # --- 3. Extract ---
            if progress_cb:
                progress_cb("Installing...", 0.0)

            gameinfo_xml_path = self._extract_port(
                zip_path, portname, undo_files, progress_cb
            )

            # Remove the downloaded zip
            if os.path.exists(zip_path):
                os.remove(zip_path)

            # --- 4. Write port.json ---
            if progress_cb:
                progress_cb("Writing metadata...", 0.8)

            self._write_port_json(port, portname)

            # --- 5. Inject PM signature ---
            self._inject_pm_signatures(port, portname)

            # --- 6. Fix permissions ---
            self._fix_permissions(portname, port)

            # --- 7. Download runtimes ---
            runtimes = port.get("runtime", [])
            if runtimes:
                if progress_cb:
                    progress_cb("Downloading runtimes...", 0.0)
                rt_ok, rt_err = self._install_runtimes(runtimes, progress_cb)
                if not rt_ok:
                    # Runtime failure is a warning, not a hard failure
                    log_error(f"Runtime install warning for {portname}: {rt_err}")

            # --- 8. Update gamelist.xml ---
            if gameinfo_xml_path and os.path.exists(gameinfo_xml_path):
                if progress_cb:
                    progress_cb("Updating game list...", 0.95)
                self._update_gamelist(gameinfo_xml_path)

            if progress_cb:
                progress_cb("Complete!", 1.0)

            return True, ""

        except Exception as e:
            log_error(
                f"Port install error ({portname}): {e}",
                type(e).__name__,
                traceback.format_exc(),
            )
            # Rollback: remove newly created files in reverse order
            for path in reversed(undo_files):
                try:
                    if os.path.isdir(path):
                        shutil.rmtree(path)
                    elif os.path.exists(path):
                        os.remove(path)
                except Exception:
                    pass
            return False, str(e)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _download_zip(
        self,
        port: Dict[str, Any],
        progress_cb: Optional[Callable] = None,
    ) -> Optional[str]:
        """Download the port zip to work_dir. Returns file path or None."""
        url = port.get("download_url", "")
        if not url:
            return None

        filename = port["name"]  # e.g. "2048.zip"
        os.makedirs(self.work_dir, exist_ok=True)
        file_path = os.path.join(self.work_dir, filename)

        try:
            resp = requests.get(url, stream=True, timeout=30)
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            downloaded = 0
            last_update = time.time()

            with open(file_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        now = time.time()
                        if progress_cb and total > 0 and now - last_update >= 0.3:
                            progress_cb("Downloading...", downloaded / total * 0.5)
                            last_update = now

            return file_path
        except Exception as e:
            log_error(f"Port download failed: {e}")
            if os.path.exists(file_path):
                os.remove(file_path)
            return None

    def _compute_md5(self, file_path: str) -> str:
        """Compute MD5 hash of a file."""
        h = hashlib.md5()
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(1024 * 1024 * 10)  # 10 MB chunks
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()

    def _extract_port(
        self,
        zip_path: str,
        portname: str,
        undo_files: List[str],
        progress_cb: Optional[Callable] = None,
    ) -> Optional[str]:
        """
        Extract port zip with proper file routing.

        - Root-level .sh scripts  -> ports_dir/
        - Root-level non-script files in _NON_SCRIPT_TOP_LEVEL -> ports_dir/portname/
        - Everything else         -> ports_dir/

        Returns the path to gameinfo.xml if found, else None.
        """
        os.makedirs(self.ports_dir, exist_ok=True)
        gameinfo_path = None

        with ZipFile(zip_path, "r") as zf:
            entries = zf.infolist()
            total = len(entries)

            for i, entry in enumerate(entries):
                if entry.is_dir():
                    # Create directory in ports_dir
                    dir_path = os.path.join(self.ports_dir, entry.filename)
                    os.makedirs(dir_path, exist_ok=True)
                    if not any(dir_path.startswith(u) for u in undo_files):
                        undo_files.append(dir_path)
                    continue

                name = entry.filename
                basename = os.path.basename(name)
                is_top_level = "/" not in name

                if is_top_level:
                    if name.lower().endswith(".sh"):
                        # .sh scripts go directly to ports_dir
                        dest = os.path.join(self.ports_dir, name)
                    elif basename.lower() in _NON_SCRIPT_TOP_LEVEL:
                        # Non-script top-level files go into portname subdir
                        dest_dir = os.path.join(self.ports_dir, portname)
                        os.makedirs(dest_dir, exist_ok=True)
                        dest = os.path.join(dest_dir, basename)
                    else:
                        # Other top-level files go to ports_dir
                        dest = os.path.join(self.ports_dir, name)
                else:
                    # Nested files go to ports_dir preserving structure
                    dest = os.path.join(self.ports_dir, name)

                # Security: reject path traversal
                real_dest = os.path.realpath(dest)
                real_ports = os.path.realpath(self.ports_dir)
                if not real_dest.startswith(real_ports):
                    continue

                os.makedirs(os.path.dirname(dest), exist_ok=True)

                # Extract
                with zf.open(entry) as src, open(dest, "wb") as dst:
                    shutil.copyfileobj(src, dst)

                undo_files.append(dest)

                # Track gameinfo.xml
                if basename.lower() == "gameinfo.xml":
                    gameinfo_path = dest

                if progress_cb and i % 20 == 0:
                    progress_cb("Installing...", 0.5 + (i / total) * 0.3)

        return gameinfo_path

    def _write_port_json(self, port: Dict[str, Any], portname: str):
        """Write or update port.json inside the port data directory."""
        port_dir = os.path.join(self.ports_dir, portname)
        os.makedirs(port_dir, exist_ok=True)
        port_json_path = os.path.join(port_dir, "port.json")

        port_info = {
            "version": 2,
            "name": port["name"],
            "items": port.get("items", []),
            "items_opt": port.get("items_opt"),
            "attr": {
                "title": port.get("title", ""),
                "desc": port.get("desc", ""),
                "inst": port.get("inst", ""),
                "genres": port.get("genres", []),
                "rtr": port.get("rtr", False),
                "porter": port.get("porter", []),
                "runtime": port.get("runtime", []),
                "reqs": port.get("reqs", []),
                "arch": port.get("arch", []),
            },
            "status": {
                "source": "ConsoleUtilities",
                "md5": port.get("md5", ""),
                "status": "Installed",
            },
        }

        with open(port_json_path, "w") as f:
            json.dump(port_info, f, indent=4)

    def _inject_pm_signatures(self, port: Dict[str, Any], portname: str):
        """
        Inject PortMaster signature comment into .sh launch scripts.

        Adds ``# PORTMASTER: portname.zip, ScriptName.sh`` as line 2
        so PortMaster can track ownership.
        """
        items = port.get("items", [])
        zip_name = port["name"]

        for item in items:
            if not item.lower().endswith(".sh"):
                continue
            script_path = os.path.join(self.ports_dir, item)
            if not os.path.isfile(script_path):
                continue

            try:
                with open(script_path, "r") as f:
                    lines = f.readlines()

                signature = f"# PORTMASTER: {zip_name}, {item}\n"

                # Check if signature already exists
                if len(lines) >= 2 and lines[1].startswith("# PORTMASTER:"):
                    lines[1] = signature
                elif lines:
                    lines.insert(1, signature)
                else:
                    lines = ["#!/bin/bash\n", signature]

                with open(script_path, "w") as f:
                    f.writelines(lines)
            except Exception as e:
                log_error(f"Failed to inject PM signature into {item}: {e}")

    def _fix_permissions(self, portname: str, port: Dict[str, Any]):
        """Make .sh scripts executable and fix port directory permissions."""
        if platform.system() != "Linux":
            return

        items = port.get("items", [])
        for item in items:
            item_path = os.path.join(self.ports_dir, item)
            if item.lower().endswith(".sh") and os.path.isfile(item_path):
                try:
                    os.chmod(item_path, 0o755)
                except Exception:
                    pass

        port_dir = os.path.join(self.ports_dir, portname)
        if os.path.isdir(port_dir):
            try:
                subprocess.run(
                    ["chmod", "-R", "755", port_dir],
                    capture_output=True,
                    timeout=10,
                )
            except Exception:
                pass

    def _install_runtimes(
        self,
        runtimes: List[str],
        progress_cb: Optional[Callable] = None,
    ) -> Tuple[bool, str]:
        """
        Download runtime .squashfs files that the port needs.

        Runtimes are saved to libs_dir (roms/ports/PortMaster/libs/).
        """
        os.makedirs(self.libs_dir, exist_ok=True)

        for i, runtime_name in enumerate(runtimes):
            if not runtime_name.endswith(".squashfs"):
                runtime_name += ".squashfs"

            runtime_path = os.path.join(self.libs_dir, runtime_name)

            # Skip if already installed
            if os.path.exists(runtime_path):
                runtime_info = self.loader.get_runtime_info(runtime_name)
                if runtime_info:
                    expected_md5 = runtime_info.get("md5", "")
                    if expected_md5:
                        actual_md5 = self._compute_md5(runtime_path)
                        if actual_md5 == expected_md5:
                            continue  # Already installed and verified

            # Look up download info
            runtime_info = self.loader.get_runtime_info(runtime_name)
            if not runtime_info:
                log_error(f"Runtime not found in catalog: {runtime_name}")
                continue

            url = runtime_info.get("url", "")
            if not url:
                log_error(f"No download URL for runtime: {runtime_name}")
                continue

            if progress_cb:
                label = f"Runtime: {runtime_name}"
                progress_cb(label, i / len(runtimes))

            try:
                resp = requests.get(url, stream=True, timeout=60)
                resp.raise_for_status()
                total = int(resp.headers.get("content-length", 0))
                downloaded = 0

                tmp_path = runtime_path + ".tmp"
                with open(tmp_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)

                # Verify MD5
                expected_md5 = runtime_info.get("md5", "")
                if expected_md5:
                    actual_md5 = self._compute_md5(tmp_path)
                    if actual_md5 != expected_md5:
                        os.remove(tmp_path)
                        log_error(f"Runtime MD5 mismatch for {runtime_name}")
                        continue

                os.rename(tmp_path, runtime_path)

            except Exception as e:
                log_error(f"Failed to download runtime {runtime_name}: {e}")
                if os.path.exists(runtime_path + ".tmp"):
                    os.remove(runtime_path + ".tmp")
                continue

        return True, ""

    def _update_gamelist(self, gameinfo_path: str):
        """
        Merge a port's gameinfo.xml entries into the main gamelist.xml.

        The gamelist.xml lives in ports_dir (roms/ports/gamelist.xml).
        """
        gamelist_path = os.path.join(self.ports_dir, "gamelist.xml")

        try:
            # Parse the port's gameinfo.xml
            game_tree = ET.parse(gameinfo_path)
            game_root = game_tree.getroot()
            new_games = game_root.findall("game")
            if not new_games:
                return

            # Parse or create the main gamelist.xml
            if os.path.exists(gamelist_path):
                try:
                    main_tree = ET.parse(gamelist_path)
                    main_root = main_tree.getroot()
                except ET.ParseError:
                    main_root = ET.Element("gameList")
                    main_tree = ET.ElementTree(main_root)
            else:
                main_root = ET.Element("gameList")
                main_tree = ET.ElementTree(main_root)

            # Build index of existing entries by path
            existing = {}
            for game_el in main_root.findall("game"):
                path_el = game_el.find("path")
                if path_el is not None and path_el.text:
                    existing[path_el.text] = game_el

            # Merge new entries
            merge_tags = [
                "path",
                "name",
                "image",
                "desc",
                "releasedate",
                "developer",
                "publisher",
                "players",
                "genre",
            ]

            for new_game in new_games:
                path_el = new_game.find("path")
                if path_el is None or not path_el.text:
                    continue
                game_path = path_el.text

                if game_path in existing:
                    # Update existing entry
                    target = existing[game_path]
                else:
                    # Add new entry
                    target = ET.SubElement(main_root, "game")
                    existing[game_path] = target

                for tag in merge_tags:
                    src = new_game.find(tag)
                    if src is not None and src.text:
                        dst = target.find(tag)
                        if dst is None:
                            dst = ET.SubElement(target, tag)
                        dst.text = src.text

            # Write back
            ET.indent(main_tree, space="  ")
            main_tree.write(gamelist_path, encoding="utf-8", xml_declaration=True)

        except Exception as e:
            log_error(f"Failed to update gamelist.xml: {e}")
