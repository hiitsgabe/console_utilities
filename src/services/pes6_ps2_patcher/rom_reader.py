"""ROM reader for PES 6 PS2 patcher.

Reads PES 6 PS2 ISO (SLES-54203) to extract team names and abbreviations
from the SLES_542.03 executable.

Team names are stored as variable-length null-terminated UTF-8 strings,
8-byte aligned, alternating: name, abbreviation, name, abbreviation.
277 team pairs total.

References:
  - SLES_542.03 at LBA 323, 3,057,568 bytes
  - ISO 9660 standard sector size 2048
  - Volume ID: PES6
"""

import os
import struct
from typing import List, Optional

from services.pes6_ps2_patcher.models import (
    ISO_SECTOR_SIZE,
    SLES_LBA,
    SLES_SIZE,
    AFS_0TEXT_LBA,
    TOTAL_TEAMS,
    PES6TeamSlot,
    PES6RomInfo,
)

# ISO 9660 Primary Volume Descriptor offset
ISO_PVD_OFFSET = 16 * ISO_SECTOR_SIZE

# Anchor string to locate team name region
ANCHOR_STRING = "Austria"


class PES6RomReader:
    """Reads and parses PES 6 PS2 ISO data."""

    def __init__(self, iso_path: str):
        self.iso_path = iso_path
        self._sles_data: Optional[bytes] = None

    def validate(self) -> bool:
        """Validate this is a PES 6 ISO.

        Checks:
        - File exists
        - ISO 9660 PVD at sector 16
        - Volume ID contains 'PES6'
        - SLES_542.03 readable at LBA 323
        """
        if not os.path.exists(self.iso_path):
            return False

        try:
            file_size = os.path.getsize(self.iso_path)
            if file_size < (SLES_LBA + 1) * ISO_SECTOR_SIZE:
                return False

            with open(self.iso_path, "rb") as f:
                # Check ISO 9660 PVD signature at sector 16
                f.seek(ISO_PVD_OFFSET)
                pvd = f.read(6)
                # PVD starts with 0x01 + "CD001"
                if pvd[0:1] != b"\x01" or pvd[1:6] != b"CD001":
                    return False

                # Volume ID is at PVD offset 40, 32 bytes, space-padded
                f.seek(ISO_PVD_OFFSET + 40)
                volume_id = f.read(32).decode("ascii", errors="replace").strip()
                if "PES6" not in volume_id:
                    return False

                # Read SLES executable
                sles_offset = SLES_LBA * ISO_SECTOR_SIZE
                f.seek(sles_offset)
                self._sles_data = f.read(SLES_SIZE)
                if len(self._sles_data) < SLES_SIZE:
                    return False

            return True

        except (IOError, OSError):
            return False

    def _ensure_sles_loaded(self):
        """Load SLES data if not already loaded."""
        if self._sles_data is None:
            if not self.validate():
                raise RuntimeError("Invalid PES 6 ISO or file not found")

    def _find_anchor(self) -> int:
        """Find the byte offset of the anchor string within SLES data."""
        anchor = ANCHOR_STRING.encode("utf-8") + b"\x00"
        pos = self._sles_data.find(anchor)
        if pos == -1:
            raise RuntimeError(
                f"Anchor string '{ANCHOR_STRING}' not found in SLES executable"
            )
        return pos

    def _parse_strings_from(self, start: int) -> List[dict]:
        """Parse null-terminated 8-byte-aligned strings from the given offset.

        Returns a list of dicts with 'text' and 'offset' keys.
        Strings are null-terminated and padded to the next 8-byte boundary.
        """
        strings = []
        pos = start
        data = self._sles_data
        data_len = len(data)
        # Parse enough strings to cover all teams (277 pairs = 554 strings)
        # plus some margin
        max_strings = TOTAL_TEAMS * 2 + 50

        while pos < data_len and len(strings) < max_strings:
            # At this point pos should be 8-byte aligned and pointing at
            # the start of a string (non-null byte)
            if data[pos] == 0:
                # Skip null padding
                while pos < data_len and data[pos] == 0:
                    pos += 1
                # Re-align to 8-byte boundary
                remainder = pos % 8
                if remainder != 0:
                    pos += 8 - remainder
                continue

            # Find null terminator
            null_pos = data.find(b"\x00", pos)
            if null_pos == -1 or null_pos == pos:
                break

            try:
                text = data[pos:null_pos].decode("utf-8")
            except UnicodeDecodeError:
                text = data[pos:null_pos].decode("latin-1")

            strings.append({"text": text, "offset": pos})

            # Move past null terminator and align to next 8-byte boundary
            pos = null_pos + 1
            remainder = pos % 8
            if remainder != 0:
                pos += 8 - remainder

        return strings

    def read_team_slots(self) -> List[PES6TeamSlot]:
        """Parse all team name/abbreviation pairs from SLES.

        Finds "Austria" anchor (first national team, start of the team name
        section), then parses forward to extract 277 team pairs.

        Returns list of PES6TeamSlot with absolute ISO offsets.
        """
        self._ensure_sles_loaded()

        anchor_pos = self._find_anchor()

        # Austria is the first team name — team data starts here.
        # Before it are IOP module names and system strings (skipped).
        strings = self._parse_strings_from(anchor_pos)

        # We need pairs of (name, abbreviation)
        # Take exactly TOTAL_TEAMS * 2 strings
        num_needed = TOTAL_TEAMS * 2
        if len(strings) < num_needed:
            raise RuntimeError(
                f"Expected at least {num_needed} strings, found {len(strings)}"
            )

        strings = strings[:num_needed]

        # Calculate absolute ISO offset for each string
        sles_base = SLES_LBA * ISO_SECTOR_SIZE

        slots = []
        for i in range(TOTAL_TEAMS):
            name_entry = strings[i * 2]
            abbr_entry = strings[i * 2 + 1]

            name_offset = sles_base + name_entry["offset"]
            abbr_offset = sles_base + abbr_entry["offset"]

            # Budget = distance to next field
            name_budget = abbr_offset - name_offset

            # Abbreviation budget = distance to next team's name
            if i + 1 < TOTAL_TEAMS:
                next_name_offset = sles_base + strings[(i + 1) * 2]["offset"]
                abbr_budget = next_name_offset - abbr_offset
            else:
                # Last team - estimate budget from string length + padding
                abbr_len = len(abbr_entry["text"].encode("utf-8")) + 1
                abbr_budget = abbr_len + (8 - abbr_len % 8) if abbr_len % 8 else abbr_len

            slot = PES6TeamSlot(
                index=i,
                name=name_entry["text"],
                abbreviation=abbr_entry["text"],
                name_offset=name_offset,
                abbr_offset=abbr_offset,
                name_budget=name_budget,
                abbr_budget=abbr_budget,
            )
            slots.append(slot)

        return slots

    def read_player_name_table(self):
        """Read all player names from 0_TEXT.AFS file 485.

        Returns list of (record_index, pointer, name) tuples sorted by pointer.
        The pointer groups players by team — consecutive pointers belong
        to the same team.
        """
        with open(self.iso_path, "rb") as f:
            f.seek(AFS_0TEXT_LBA * ISO_SECTOR_SIZE)
            afs_hdr = f.read(8)
            num_files = struct.unpack_from("<I", afs_hdr, 4)[0]
            afs_tbl = f.read(num_files * 8)

            entry_off = struct.unpack_from("<I", afs_tbl, 485 * 8)[0]
            entry_sz = struct.unpack_from("<I", afs_tbl, 485 * 8 + 4)[0]
            f.seek(AFS_0TEXT_LBA * ISO_SECTOR_SIZE + entry_off)
            data = f.read(entry_sz)

        players = []
        header_size = 0x20
        record_size = 48
        num_records = (len(data) - header_size) // record_size

        for i in range(num_records):
            rec_off = header_size + i * record_size
            ptr = struct.unpack_from("<I", data, rec_off + 8)[0]
            name_bytes = data[rec_off + 16 : rec_off + 48]
            name = name_bytes.split(b"\x00")[0].decode("ascii", errors="replace")
            if ptr and name:
                players.append((i, ptr, name))

        return players

    def find_team_player_indices(self, team_slot_index):
        """Find player record indices that belong to a specific team.

        Uses the team name table's team slot index to find the corresponding
        pointer range in the player name table. Teams are grouped by
        consecutive pointer values.

        Args:
            team_slot_index: 0-based team index from read_team_slots()

        Returns:
            List of (record_index, name) for players on this team.
        """
        all_players = self.read_player_name_table()

        # Sort by pointer
        by_ptr = sorted(all_players, key=lambda x: x[1])

        # Split into team clusters using gaps
        # A gap >= 5 between consecutive pointers indicates a team boundary
        teams = []
        team_start = 0
        for j in range(1, len(by_ptr)):
            gap = by_ptr[j][1] - by_ptr[j - 1][1]
            if gap >= 5:
                teams.append(by_ptr[team_start:j])
                team_start = j
        teams.append(by_ptr[team_start:])

        # The team clusters are ordered by pointer value.
        # We need to map our team_slot_index to a cluster.
        # This is approximate — the pointer ordering follows the game's
        # internal team ordering which may differ from the name table ordering.
        if team_slot_index < len(teams):
            return [(idx, name) for idx, _, name in teams[team_slot_index]]

        return []

    def get_rom_info(self) -> PES6RomInfo:
        """Return PES6RomInfo with validation status and team slots."""
        is_valid = self.validate()

        info = PES6RomInfo(
            path=self.iso_path,
            is_valid=is_valid,
        )

        if is_valid:
            try:
                info.size = os.path.getsize(self.iso_path)
                info.team_slots = self.read_team_slots()
            except Exception:
                info.is_valid = False

        return info
