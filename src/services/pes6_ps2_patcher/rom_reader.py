"""Read and validate PES6 PS2 ISOs, extract player database."""

import os
import struct
import zlib
from typing import Dict, List, Optional, Tuple

from .models import RomInfo


class RomReader:
    """Reads PES6/WE10 PS2 ISO files."""

    # Known 0_TEXT.AFS offsets: Bomba Patch, WE10 Japan, PES6 Europe
    AFS_CANDIDATES = [0x2F1FA000, 0x2297C800, 0x01CCA800]
    SLPM_TEAM_NAME_OFFSET = 0x2BEC00
    WESYS_MAGICS = {0x00000600, 0x00010000}
    RECORD_SIZE = 124
    # Editable player DB file index varies by version
    # WE10/Bomba: file[35], PES6 EUR: file[55]
    # Base (read-only) DB: WE10 file[34], PES6 EUR file[54]
    PLAYER_DB_CANDIDATES = [35, 55]
    BASE_DB_CANDIDATES = [34, 54]

    def __init__(self, iso_path: str):
        self.iso_path = iso_path

    def validate(self) -> RomInfo:
        """Validate ISO and return ROM info."""
        info = RomInfo(path=self.iso_path, size=0)

        if not os.path.exists(self.iso_path):
            return info

        info.size = os.path.getsize(self.iso_path)
        if info.size < 100_000_000:
            return info

        with open(self.iso_path, "rb") as f:
            slpm_off = self._find_slpm(f)
            if slpm_off is None:
                return info
            info.slpm_offset = slpm_off

            f.seek(0x8028)
            vol = f.read(32)
            if b"BOMBA" in vol.upper():
                info.version = "bomba_patch"
            elif b"WE10" in vol.upper() or b"WE 10" in vol.upper():
                info.version = "we10"
            else:
                info.version = "pes6_compatible"

            afs_off = self._find_afs(f)
            if afs_off is None:
                return info
            info.afs_offset = afs_off

            # Find the base (read-only) player DB
            for fi in self.BASE_DB_CANDIDATES:
                fb_off, fb_size = self._get_afs_entry(f, afs_off, fi)
                if fb_off == 0 or fb_size == 0:
                    continue
                try:
                    decompressed = self._decompress_wesys(f, fb_off, fb_size)
                    num = len(decompressed) // self.RECORD_SIZE
                    if 4000 <= num <= 5000:
                        info.base_db_offset = fb_off
                        info.base_db_size = fb_size
                        break
                except Exception:
                    continue

            # Find the editable player DB
            for fi in self.PLAYER_DB_CANDIDATES:
                f35_off, f35_size = self._get_afs_entry(f, afs_off, fi)
                if f35_off == 0 or f35_size == 0:
                    continue
                try:
                    decompressed = self._decompress_wesys(f, f35_off, f35_size)
                    num = len(decompressed) // self.RECORD_SIZE
                    if 4000 <= num <= 5000:
                        info.file35_offset = f35_off
                        info.file35_size = f35_size
                        info.num_players = num
                        break
                except Exception:
                    continue

            info.is_valid = True

        return info

    def read_players(self) -> List[Tuple[int, str, str, int]]:
        """Read all player records. Returns list of (index, name, shirt, position)."""
        info = self.validate()
        if not info.is_valid:
            return []

        with open(self.iso_path, "rb") as f:
            data = self._decompress_wesys(f, info.file35_offset, info.file35_size)

        players = []
        for i in range(len(data) // self.RECORD_SIZE):
            rec = data[i * self.RECORD_SIZE : (i + 1) * self.RECORD_SIZE]
            try:
                name = rec[0:32].decode("utf-16-le").rstrip("\x00")
            except Exception:
                name = ""
            try:
                shirt = rec[32:48].decode("ascii").rstrip("\x00")
            except Exception:
                shirt = ""
            reg_pos = (rec[54] >> 4) & 0xF
            players.append((i + 1, name, shirt, reg_pos))

        return players

    def read_team_names(self, rom_info: RomInfo = None) -> Dict[int, str]:
        """Read team names from the SLPM executable.

        Dynamically finds the team name table by searching for known anchors.
        Returns dict mapping entry index to team name.
        """
        if rom_info is None:
            rom_info = self.validate()
        if not rom_info.is_valid:
            return {}

        with open(self.iso_path, "rb") as f:
            f.seek(rom_info.slpm_offset)
            slpm = f.read(4_000_000)

        # Find the team name table start by searching for known anchors
        table_start = self._find_team_name_table_start(slpm)
        if table_start is None:
            return {}

        raw = slpm[table_start:]

        # Extract all non-null ASCII strings with positions
        strings = []
        i = 0
        while i < min(len(raw), 0x8000):
            if raw[i] != 0:
                end = raw.find(b"\x00", i)
                if end == -1:
                    break
                try:
                    s = raw[i:end].decode("ascii")
                except UnicodeDecodeError:
                    i = end + 1
                    continue
                if all(32 <= ord(c) < 127 for c in s):
                    strings.append((i, s))
                i = end + 1
            else:
                i += 1

        # Pair strings: team name followed by abbreviation (short uppercase)
        teams = {}
        idx = 0
        entry_num = 0
        max_entries = 200
        while idx < len(strings) - 1 and entry_num < max_entries:
            _, name = strings[idx]
            _, maybe_abbrev = strings[idx + 1]

            if (
                len(name) > 3
                and len(maybe_abbrev) <= 4
                and maybe_abbrev == maybe_abbrev.upper()
            ):
                teams[entry_num] = name
                idx += 2
            elif len(name) <= 3 and name == name.upper():
                idx += 1
                continue
            else:
                teams[entry_num] = name
                idx += 1
            entry_num += 1

        return teams

    @staticmethod
    def _find_team_name_table_start(slpm: bytes) -> Optional[int]:
        """Find where the team name table starts in SLPM data.

        Searches for the first national team entry (Austria) which is
        always present as the first alphabetical team in PES6 variants.
        Falls back to Arsenal or Brazilian team names for modded ISOs.
        """
        # National teams start with Austria (alphabetically first)
        # This is followed by its 3-char abbreviation "AUT"
        austria = slpm.find(b"Austria\x00")
        if austria != -1:
            # Verify it's a team entry (followed by AUT abbreviation nearby)
            after = slpm[austria + 8 : austria + 24]
            if b"AUT" in after:
                return austria

        # Bomba Patch: search for first Brazilian team
        for name in [b"Swansea\x00", b"Flamengo\x00", b"Vasco\x00"]:
            idx = slpm.find(name)
            if idx != -1:
                return idx

        # Last resort: Arsenal
        arsenal = slpm.find(b"Arsenal\x00")
        if arsenal != -1:
            return arsenal

        return None

    def read_raw_file35(self) -> bytes:
        """Read and decompress file[35] returning raw player data."""
        info = self.validate()
        if not info.is_valid:
            return b""
        with open(self.iso_path, "rb") as f:
            return self._decompress_wesys(f, info.file35_offset, info.file35_size)

    def _find_slpm(self, f) -> Optional[int]:
        """Find SLPM ELF executable in ISO."""
        for offset in [0x95000]:
            f.seek(offset)
            if f.read(4) == b"\x7fELF":
                return offset
        f.seek(0)
        chunk_size = 1024 * 1024
        offset = 0
        file_size = f.seek(0, 2)
        while offset < min(file_size, 10_000_000):
            f.seek(offset)
            chunk = f.read(chunk_size)
            idx = chunk.find(b"\x7fELF")
            if idx != -1:
                return offset + idx
            offset += chunk_size - 4
        return None

    def _find_afs(self, f) -> Optional[int]:
        """Find 0_TEXT.AFS (9315 files) in ISO."""
        file_size = f.seek(0, 2)
        for candidate in self.AFS_CANDIDATES:
            if candidate + 8 > file_size:
                continue
            f.seek(candidate)
            if f.read(4) == b"AFS\x00":
                num_files = struct.unpack("<I", f.read(4))[0]
                if num_files in (9315, 9806):  # Bomba/WE10=9315, PES6 EUR=9806
                    return candidate
        return None

    def _get_afs_entry(self, f, afs_offset: int, file_index: int) -> Tuple[int, int]:
        """Get (offset, size) for a file in AFS archive."""
        f.seek(afs_offset + 8 + file_index * 8)
        rel_off = struct.unpack("<I", f.read(4))[0]
        size = struct.unpack("<I", f.read(4))[0]
        return afs_offset + rel_off, size

    def _decompress_wesys(self, f, offset: int, size: int) -> bytes:
        """Read and decompress WESYS container."""
        f.seek(offset)
        container = f.read(size)

        magic = struct.unpack("<I", container[:4])[0]
        if magic not in self.WESYS_MAGICS:
            raise ValueError(f"Not a WESYS container: magic=0x{magic:08X}")

        for start in range(0x20, min(0x100, len(container))):
            if container[start] == 0x78 and container[start + 1] in (
                0x01,
                0x5E,
                0x9C,
                0xDA,
            ):
                try:
                    return zlib.decompress(container[start:])
                except zlib.error:
                    continue

        raise ValueError("Could not find zlib stream in WESYS container")
