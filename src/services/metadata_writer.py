"""
Metadata writer service - Updates frontend metadata files with scraped game info.

Handles updating gamelist.xml (EmulationStation), metadata.pegasus.txt (Pegasus),
and other frontend-specific metadata formats.
"""

import os
import re
import traceback
from datetime import datetime
from typing import Dict, Any, List, Optional
from xml.etree import ElementTree as ET
from xml.dom import minidom


class MetadataWriter:
    """
    Service for updating frontend metadata files.

    Supports:
    - EmulationStation Base: gamelist.xml in ROM folder
    - ES-DE Android: gamelist.xml in separate gamelists folder
    - Pegasus: metadata.pegasus.txt in ROM folder
    - RetroArch: No metadata update needed (uses filename matching)
    """

    def __init__(self, settings: Dict[str, Any]):
        """
        Initialize metadata writer.

        Args:
            settings: Application settings dictionary
        """
        self.settings = settings

    def update_metadata(
        self,
        rom_path: str,
        game_info: Dict[str, Any],
        image_paths: List[str],
    ) -> tuple[bool, str]:
        """
        Update metadata for a ROM based on frontend configuration.

        Args:
            rom_path: Path to the ROM file
            game_info: Game information from scraper (name, description, etc.)
            image_paths: List of downloaded image paths

        Returns:
            Tuple of (success, error message)
        """
        frontend = self.settings.get("scraper_frontend", "emulationstation_base")

        try:
            if frontend == "emulationstation_base":
                return self._update_gamelist_xml(rom_path, game_info, image_paths)
            elif frontend == "esde_android":
                return self._update_esde_gamelist(rom_path, game_info, image_paths)
            elif frontend == "pegasus":
                return self._update_pegasus_metadata(rom_path, game_info, image_paths)
            elif frontend == "retroarch":
                # RetroArch doesn't need metadata updates - it matches by filename
                return True, ""
            else:
                return False, f"Unknown frontend: {frontend}"

        except Exception as e:
            traceback.print_exc()
            return False, f"Error updating metadata: {str(e)}"

    def _update_gamelist_xml(
        self,
        rom_path: str,
        game_info: Dict[str, Any],
        image_paths: List[str],
    ) -> tuple[bool, str]:
        """
        Update EmulationStation gamelist.xml in ROM folder.

        Args:
            rom_path: Path to the ROM file
            game_info: Game information
            image_paths: Downloaded image paths

        Returns:
            Tuple of (success, error message)
        """
        rom_dir = os.path.dirname(rom_path)
        gamelist_path = os.path.join(rom_dir, "gamelist.xml")

        # Load existing or create new
        if os.path.exists(gamelist_path):
            try:
                tree = ET.parse(gamelist_path)
                root = tree.getroot()
            except ET.ParseError:
                root = ET.Element("gameList")
        else:
            root = ET.Element("gameList")

        # Get ROM filename for path matching
        rom_filename = os.path.basename(rom_path)
        rom_relative = f"./{rom_filename}"

        # Find existing game entry or create new
        game_elem = None
        for game in root.findall("game"):
            path_elem = game.find("path")
            if path_elem is not None and path_elem.text == rom_relative:
                game_elem = game
                break

        if game_elem is None:
            game_elem = ET.SubElement(root, "game")

        # Update game elements
        self._set_xml_element(game_elem, "path", rom_relative)
        self._set_xml_element(game_elem, "name", game_info.get("name", ""))

        if game_info.get("description"):
            self._set_xml_element(game_elem, "desc", game_info["description"])

        if game_info.get("release_date"):
            # Convert to ES format (YYYYMMDDTHHMMSS)
            date_str = self._format_es_date(game_info["release_date"])
            if date_str:
                self._set_xml_element(game_elem, "releasedate", date_str)

        # Set image paths (relative to ROM folder)
        for img_path in image_paths:
            img_relative = os.path.relpath(img_path, rom_dir)
            img_type = self._get_es_image_type(img_path)
            if img_type:
                self._set_xml_element(game_elem, img_type, f"./{img_relative}")

        # Write the file
        self._write_pretty_xml(root, gamelist_path)
        return True, ""

    def _update_esde_gamelist(
        self,
        rom_path: str,
        game_info: Dict[str, Any],
        image_paths: List[str],
    ) -> tuple[bool, str]:
        """
        Update ES-DE Android gamelist.xml in separate gamelists folder.

        ES-DE Android stores gamelists in:
        /sdcard/ES-DE/gamelists/<platform>/gamelist.xml

        Args:
            rom_path: Path to the ROM file
            game_info: Game information
            image_paths: Downloaded image paths

        Returns:
            Tuple of (success, error message)
        """
        gamelists_base = self.settings.get("esde_gamelists_path", "")
        if not gamelists_base:
            return False, "ES-DE gamelists path not configured"

        # Get platform from ROM directory
        platform = os.path.basename(os.path.dirname(rom_path))
        gamelist_dir = os.path.join(gamelists_base, platform)
        gamelist_path = os.path.join(gamelist_dir, "gamelist.xml")

        os.makedirs(gamelist_dir, exist_ok=True)

        # Load existing or create new
        if os.path.exists(gamelist_path):
            try:
                tree = ET.parse(gamelist_path)
                root = tree.getroot()
            except ET.ParseError:
                root = ET.Element("gameList")
        else:
            root = ET.Element("gameList")

        # ES-DE uses full ROM path
        rom_filename = os.path.basename(rom_path)

        # Find existing or create
        game_elem = None
        for game in root.findall("game"):
            path_elem = game.find("path")
            if (
                path_elem is not None
                and os.path.basename(path_elem.text or "") == rom_filename
            ):
                game_elem = game
                break

        if game_elem is None:
            game_elem = ET.SubElement(root, "game")

        # Update elements
        self._set_xml_element(game_elem, "path", rom_path)
        self._set_xml_element(game_elem, "name", game_info.get("name", ""))

        if game_info.get("description"):
            self._set_xml_element(game_elem, "desc", game_info["description"])

        if game_info.get("release_date"):
            date_str = self._format_es_date(game_info["release_date"])
            if date_str:
                self._set_xml_element(game_elem, "releasedate", date_str)

        # Set image paths (ES-DE uses full paths)
        for img_path in image_paths:
            img_type = self._get_es_image_type(img_path)
            if img_type:
                self._set_xml_element(game_elem, img_type, img_path)

        self._write_pretty_xml(root, gamelist_path)
        return True, ""

    def _update_pegasus_metadata(
        self,
        rom_path: str,
        game_info: Dict[str, Any],
        image_paths: List[str],
    ) -> tuple[bool, str]:
        """
        Update Pegasus metadata.pegasus.txt in ROM folder.

        Args:
            rom_path: Path to the ROM file
            game_info: Game information
            image_paths: Downloaded image paths

        Returns:
            Tuple of (success, error message)
        """
        rom_dir = os.path.dirname(rom_path)
        metadata_path = os.path.join(rom_dir, "metadata.pegasus.txt")
        rom_filename = os.path.basename(rom_path)

        # Load existing entries
        entries = {}
        if os.path.exists(metadata_path):
            entries = self._parse_pegasus_metadata(metadata_path)

        # Update or create entry for this ROM
        entry = entries.get(rom_filename, {})
        entry["file"] = rom_filename
        entry["name"] = game_info.get("name", os.path.splitext(rom_filename)[0])

        if game_info.get("description"):
            entry["description"] = game_info["description"]

        if game_info.get("release_date"):
            # Pegasus uses YYYY-MM-DD format
            date_str = self._format_pegasus_date(game_info["release_date"])
            if date_str:
                entry["release"] = date_str

        # Add assets
        assets = entry.get("assets", {})
        for img_path in image_paths:
            asset_type = self._get_pegasus_asset_type(img_path)
            if asset_type:
                # Pegasus uses relative paths
                rel_path = os.path.relpath(img_path, rom_dir)
                assets[asset_type] = rel_path
        entry["assets"] = assets

        entries[rom_filename] = entry

        # Write the file
        self._write_pegasus_metadata(entries, metadata_path)
        return True, ""

    def _set_xml_element(self, parent: ET.Element, tag: str, text: str):
        """Set or create an XML element with text content."""
        elem = parent.find(tag)
        if elem is None:
            elem = ET.SubElement(parent, tag)
        elem.text = text

    def _write_pretty_xml(self, root: ET.Element, path: str):
        """Write XML with nice formatting."""
        xml_str = ET.tostring(root, encoding="unicode")
        dom = minidom.parseString(xml_str)
        pretty_xml = dom.toprettyxml(indent="  ")

        # Remove extra blank lines
        lines = [line for line in pretty_xml.split("\n") if line.strip()]
        # Skip xml declaration if it's the first line
        if lines and lines[0].startswith("<?xml"):
            lines = lines[1:]
        final_xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + "\n".join(lines)

        with open(path, "w", encoding="utf-8") as f:
            f.write(final_xml)

    def _format_es_date(self, date_str: str) -> str:
        """Convert date string to EmulationStation format (YYYYMMDDTHHMMSS)."""
        try:
            # Try common formats
            for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y", "%Y"]:
                try:
                    dt = datetime.strptime(date_str.strip(), fmt)
                    return dt.strftime("%Y%m%dT000000")
                except ValueError:
                    continue
            return ""
        except Exception:
            return ""

    def _format_pegasus_date(self, date_str: str) -> str:
        """Convert date string to Pegasus format (YYYY-MM-DD)."""
        try:
            for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y", "%Y"]:
                try:
                    dt = datetime.strptime(date_str.strip(), fmt)
                    return dt.strftime("%Y-%m-%d")
                except ValueError:
                    continue
            return ""
        except Exception:
            return ""

    def _get_es_image_type(self, img_path: str) -> Optional[str]:
        """Get EmulationStation XML tag for an image path."""
        path_lower = img_path.lower()
        if "screenshot" in path_lower or "/snaps/" in path_lower:
            return "image"
        elif (
            "cover" in path_lower or "boxart" in path_lower or "/images/" in path_lower
        ):
            return "image"
        elif "marquee" in path_lower or "wheel" in path_lower:
            return "marquee"
        elif "fanart" in path_lower:
            return "fanart"
        elif "video" in path_lower:
            return "video"
        elif "thumbnail" in path_lower:
            return "thumbnail"
        return "image"

    def _get_pegasus_asset_type(self, img_path: str) -> Optional[str]:
        """Get Pegasus asset type for an image path."""
        path_lower = img_path.lower()
        if "boxfront" in path_lower or "cover" in path_lower:
            return "box_front"
        elif "screenshot" in path_lower:
            return "screenshot"
        elif "logo" in path_lower or "wheel" in path_lower:
            return "logo"
        elif "background" in path_lower or "fanart" in path_lower:
            return "background"
        elif "titlescreen" in path_lower:
            return "titlescreen"
        elif "marquee" in path_lower:
            return "marquee"
        return "box_front"

    def _parse_pegasus_metadata(self, path: str) -> Dict[str, Dict]:
        """Parse existing Pegasus metadata file."""
        entries = {}
        current_entry = None
        current_key = None
        multiline_value = []

        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.rstrip("\n")

                    # Check for continuation of multiline value
                    if line.startswith("  ") and current_key:
                        multiline_value.append(line.strip())
                        continue
                    elif multiline_value and current_entry and current_key:
                        current_entry[current_key] = "\n".join(multiline_value)
                        multiline_value = []
                        current_key = None

                    # Skip empty lines and comments
                    if not line.strip() or line.startswith("#"):
                        continue

                    # Parse key: value
                    if ":" in line:
                        key, _, value = line.partition(":")
                        key = key.strip()
                        value = value.strip()

                        if key == "file":
                            # New entry
                            if current_entry and current_entry.get("file"):
                                entries[current_entry["file"]] = current_entry
                            current_entry = {"file": value}
                        elif current_entry:
                            if key == "assets":
                                current_entry["assets"] = {}
                            elif key.startswith("  "):
                                # Asset entry
                                asset_key = key.strip()
                                if "assets" in current_entry:
                                    current_entry["assets"][asset_key] = value
                            else:
                                current_entry[key] = value
                                if not value:
                                    current_key = key
                                    multiline_value = []

                # Save last entry
                if current_entry and current_entry.get("file"):
                    entries[current_entry["file"]] = current_entry

        except Exception:
            pass

        return entries

    def _write_pegasus_metadata(self, entries: Dict[str, Dict], path: str):
        """Write Pegasus metadata file."""
        with open(path, "w", encoding="utf-8") as f:
            for filename, entry in entries.items():
                f.write(f"file: {entry.get('file', filename)}\n")
                f.write(f"name: {entry.get('name', '')}\n")

                if entry.get("description"):
                    desc = entry["description"].replace("\n", "\n  ")
                    f.write(f"description:\n  {desc}\n")

                if entry.get("release"):
                    f.write(f"release: {entry['release']}\n")

                assets = entry.get("assets", {})
                if assets:
                    f.write("assets:\n")
                    for asset_type, asset_path in assets.items():
                        f.write(f"  {asset_type}: {asset_path}\n")

                f.write("\n")


# Singleton instance
_metadata_writer: Optional[MetadataWriter] = None


def get_metadata_writer(settings: Dict[str, Any]) -> MetadataWriter:
    """
    Get or create the metadata writer instance.

    Args:
        settings: Application settings

    Returns:
        MetadataWriter instance
    """
    global _metadata_writer
    if _metadata_writer is None:
        _metadata_writer = MetadataWriter(settings)
    else:
        _metadata_writer.settings = settings
    return _metadata_writer
