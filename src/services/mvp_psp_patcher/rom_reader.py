"""ISO reader for MVP Baseball PSP patcher.

Reads database.big from MVP Baseball PSP ISO (ULUS-10012).
database.big contains 18 concatenated RefPack-compressed CSV sections.
Each section decompresses to CSV data with hex hash IDs linking records.

References:
  - RefPack: https://simswiki.info/wiki.php?title=DBPF_Compression
"""

import os
import struct
from typing import Optional, List, Dict, Tuple

from services.nhl07_psp_patcher.ea_tdb import refpack_decompress
from services.mvp_psp_patcher.models import (
    MVPRomInfo,
    MVPTeamSlot,
    MVP_TEAM_ORDER,
    TEAM_HASHES,
    SECTION_MAP,
    DATABASE_BIG_LBA,
    DATABASE_BIG_SIZE,
    ISO_SECTOR_SIZE,
    TEAM_COUNT,
    ATTRIB_FIRST_NAME,
    ATTRIB_LAST_NAME,
    ATTRIB_JERSEY,
    ATTRIB_BATS,
    ATTRIB_THROWS,
    ATTRIB_PRIMARY_POS,
    ATTRIB_SECONDARY_POS,
    ATTRIB_HEIGHT,
    ATTRIB_WEIGHT,
    ATTRIB_SPEED,
    ATTRIB_FIELDING,
    ATTRIB_RANGE,
    ATTRIB_THROW_STRENGTH,
    ATTRIB_THROW_ACCURACY,
    ATTRIB_DURABILITY,
    ATTRIB_PLATE_DISCIPLINE,
    ATTRIB_BUNTING,
    ATTRIB_BASERUNNING,
    ATTRIB_STEALING_AGGRESSIVE,
    ATTRIB_STARPOWER,
    ROSTER_TEAMID,
    ROSTER_PLAYERID,
    ROSTER_RH_AL_POS,
    ROSTER_RH_AL_ORDER,
)

# Reverse lookup: hash -> game abbreviation
HASH_TO_ABBREV = {v: k for k, v in TEAM_HASHES.items()}


class MVPPSPRomReader:
    """Reads and parses MVP Baseball PSP ISO data."""

    def __init__(self, iso_path: str):
        self.iso_path = iso_path
        self.database_big: Optional[bytes] = None
        self.database_big_offset: int = 0
        self.sections: Dict[str, bytes] = {}  # table_name -> decompressed CSV
        self.records: Dict[str, Dict[str, Dict[int, str]]] = {}  # table -> {hash -> {field -> value}}
        self.record_order: Dict[str, List[str]] = {}  # table -> [hash_ids in original order]

    def load(self) -> bool:
        """Load database.big from the ISO."""
        if not os.path.exists(self.iso_path):
            return False
        try:
            offset = DATABASE_BIG_LBA * ISO_SECTOR_SIZE
            with open(self.iso_path, "rb") as f:
                f.seek(offset)
                data = f.read(DATABASE_BIG_SIZE)
            if len(data) < DATABASE_BIG_SIZE:
                return False
            self.database_big = data
            self.database_big_offset = offset
            return True
        except Exception:
            return False

    def validate(self) -> bool:
        """Validate the database.big has valid RefPack sections."""
        if not self.database_big:
            return False
        # Check first section has RefPack-like header
        if len(self.database_big) < 5:
            return False
        # First section uses 0xC0 flags, second uses 0x10 0xFB
        b0 = self.database_big[0]
        if b0 not in (0x10, 0xC0):
            return False
        # Verify second section at offset 324
        if len(self.database_big) > 326:
            if self.database_big[324] == 0x10 and self.database_big[325] == 0xFB:
                return True
        return False

    def decompress_section(self, offset: int) -> Optional[bytes]:
        """Decompress a single RefPack section at the given offset."""
        if not self.database_big:
            return None
        if offset >= len(self.database_big):
            return None

        raw = self.database_big[offset:]

        # First section (offset 0) has flags=0xC0 instead of 0x10
        if offset == 0 and raw[0] == 0xC0:
            # Convert to standard 0x10 0xFB header
            fake_header = bytes([0x10, 0xFB]) + raw[2:5]
            compatible = fake_header + raw[5:]
            return refpack_decompress(compatible)
        elif raw[0] == 0x10 and raw[1] == 0xFB:
            return refpack_decompress(raw)
        else:
            return None

    def decompress_all(self):
        """Decompress all known sections."""
        for offset, name in SECTION_MAP:
            try:
                data = self.decompress_section(offset)
                if data:
                    self.sections[name] = data
            except Exception:
                pass

    def parse_csv_section(self, name: str) -> Dict[str, Dict[int, str]]:
        """Parse a decompressed CSV section into records.

        Returns dict: hash_id -> {field_number -> value}
        Also stores record_order[name] = list of hash_ids in original order.
        """
        if name not in self.sections:
            return {}

        data = self.sections[name]
        text = data.decode("ascii", errors="replace")
        records: Dict[str, Dict[int, str]] = {}
        order: List[str] = []

        # Split on CRLF-terminated records (each ends with ;\r\n)
        lines = text.split(";\r\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Skip header line (starts with field definitions)
            if "," not in line:
                continue

            parts = line.split(",")
            if not parts:
                continue

            hash_id = parts[0].strip()
            if not hash_id or len(hash_id) < 5:
                continue
            # Skip header lines — real hash IDs are hex-only with no spaces
            if " " in hash_id or not all(
                c in "0123456789abcdef" for c in hash_id
            ):
                continue

            fields: Dict[int, str] = {}
            for part in parts[1:]:
                if not part.strip():
                    continue
                # Format: "FieldNum Value" (space-separated)
                # Note: value may be empty (e.g. "0 ") — don't strip before finding space
                space_idx = part.find(" ")
                if space_idx < 0:
                    continue
                try:
                    field_num = int(part[:space_idx])
                    value = part[space_idx + 1:]
                    fields[field_num] = value
                except ValueError:
                    continue

            if fields:
                records[hash_id] = fields
                order.append(hash_id)

        self.record_order[name] = order
        return records

    def parse_all(self):
        """Parse all decompressed sections into records."""
        for _, name in SECTION_MAP:
            if name in self.sections:
                self.records[name] = self.parse_csv_section(name)

    def get_info(self) -> MVPRomInfo:
        """Get ISO information and team slots."""
        if not self.database_big:
            return MVPRomInfo(path=self.iso_path, size=0)

        is_valid = self.validate()
        team_slots = []

        if is_valid:
            # Decompress and parse what we need for info
            if not self.sections:
                self.decompress_all()
            if not self.records:
                self.parse_all()

            team_slots = self._read_team_slots()

        iso_size = 0
        try:
            iso_size = os.path.getsize(self.iso_path)
        except Exception:
            pass

        return MVPRomInfo(
            path=self.iso_path,
            size=iso_size,
            database_big_offset=self.database_big_offset,
            database_big_size=len(self.database_big),
            team_slots=team_slots,
            is_valid=is_valid,
        )

    def _read_team_slots(self) -> List[MVPTeamSlot]:
        """Read team slot info from parsed data."""
        slots = []
        roster_records = self.records.get("roster", {})
        attrib_records = self.records.get("attrib", {})

        # Build team hash -> abbrev mapping
        hash_to_abbrev = {v: k for k, v in TEAM_HASHES.items()}

        # Count players per team
        team_players: Dict[str, List[str]] = {}  # team_hash -> [player_hashes]
        for _rec_id, fields in roster_records.items():
            team_hash = fields.get(ROSTER_TEAMID, "")
            player_hash = fields.get(ROSTER_PLAYERID, "")
            if team_hash and player_hash:
                team_players.setdefault(team_hash, []).append(player_hash)

        for i in range(TEAM_COUNT):
            name = MVP_TEAM_ORDER[i]
            abbrev = list(TEAM_HASHES.keys())[i]
            team_hash = TEAM_HASHES.get(abbrev, "")
            players = team_players.get(team_hash, [])

            first_player = ""
            if players and attrib_records:
                p_hash = players[0]
                p_fields = attrib_records.get(p_hash, {})
                fname = p_fields.get(ATTRIB_FIRST_NAME, "")
                lname = p_fields.get(ATTRIB_LAST_NAME, "")
                if fname or lname:
                    first_player = f"{fname} {lname}".strip()

            slots.append(MVPTeamSlot(
                index=i,
                name=name,
                abbrev=abbrev,
                player_count=len(players),
                first_player=first_player,
            ))

        return slots

    def get_team_roster(self, team_abbrev: str) -> List[Tuple[str, Dict[int, str]]]:
        """Get roster records for a team.

        Returns list of (player_hash, roster_fields) tuples.
        """
        team_hash = TEAM_HASHES.get(team_abbrev, "")
        if not team_hash:
            return []

        roster_records = self.records.get("roster", {})
        result = []
        for _rec_id, fields in roster_records.items():
            if fields.get(ROSTER_TEAMID, "") == team_hash:
                player_hash = fields.get(ROSTER_PLAYERID, "")
                if player_hash:
                    result.append((player_hash, fields))
        return result

    def get_player_attribs(self, player_hash: str) -> Dict[int, str]:
        """Get attrib record for a player."""
        return self.records.get("attrib", {}).get(player_hash, {})

    def get_player_lr_attribs(
        self, player_hash: str, vs: str = "rhp"
    ) -> Dict[int, str]:
        """Get LR attrib record (vs RHP or LHP)."""
        table = "lrattrib_rhp" if vs == "rhp" else "lrattrib_lhp"
        return self.records.get(table, {}).get(player_hash, {})

    def get_pitch_attribs(self, player_hash: str) -> Dict[int, str]:
        """Get pitching attributes for a player."""
        return self.records.get("pitchattrib", {}).get(player_hash, {})

    def get_existing_player_hashes(self) -> List[str]:
        """Get all player hash IDs from the attrib table."""
        return list(self.records.get("attrib", {}).keys())

    def get_existing_team_hashes(self) -> List[str]:
        """Get all team hash IDs from the team table."""
        return list(self.records.get("team", {}).keys())
