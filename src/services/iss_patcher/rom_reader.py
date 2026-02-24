"""ISS SNES ROM reader — validates ROM and reads existing team/player data.

Offset constants sourced from:
  https://github.com/rodmguerra/issparser (ISS Studio Java editor)
  https://github.com/EstebanFuentealba/web-iss-studio (web port)

ISS (International Superstar Soccer, 1994) uses a standard SNES .sfc ROM.
Some ROMs include a 512-byte copier header which shifts all offsets.
The expected ROM size is 2MB (2,097,152 bytes) without header, or
2,097,664 with header.
"""

import os
from typing import List

from .models import (
    ISSRomInfo,
    ISSTeamSlot,
    TEAM_ENUM_ORDER,
    TEAM_NAME_ORDER,
    PLAYERS_PER_TEAM,
    TOTAL_TEAMS,
)

# ── ROM size constants ──────────────────────────────────────────────────────
_ROM_SIZE_8MBIT = 1_048_576           # 1 MB (8 Mbit) — USA/EUR ISS
_ROM_SIZE_8MBIT_HEADER = 1_049_088    # 1 MB + 512
_ROM_SIZE_16MBIT = 2_097_152          # 2 MB (16 Mbit) — some variants
_ROM_SIZE_16MBIT_HEADER = 2_097_664   # 2 MB + 512
_HEADER_SIZE = 512
_MIN_ROM_SIZE = _ROM_SIZE_8MBIT       # Minimum valid ROM size

# ── Absolute byte offsets (headerless) ──────────────────────────────────────
# Player names: 8 bytes per player, teams in TEAM_NAME_ORDER
_OFS_PLAYER_NAMES = 0x3B62C     # 27 teams × 15 players × 8 bytes = 3240 bytes

# Player data block: 6 bytes per player, teams in TEAM_ENUM_ORDER
_OFS_PLAYER_DATA = 0x387EC

# ISS custom character encoding
_CHAR_TO_BYTE = {}
_BYTE_TO_CHAR = {}


def _init_encoding():
    """Build ISS custom character encoding tables."""
    if _CHAR_TO_BYTE:
        return
    _CHAR_TO_BYTE[" "] = 0x00
    _BYTE_TO_CHAR[0x00] = " "
    _CHAR_TO_BYTE["."] = 0x54
    _BYTE_TO_CHAR[0x54] = "."
    _CHAR_TO_BYTE["-"] = 0x53
    _BYTE_TO_CHAR[0x53] = "-"
    _CHAR_TO_BYTE['"'] = 0x56
    _BYTE_TO_CHAR[0x56] = '"'
    _CHAR_TO_BYTE["'"] = 0x5C
    _BYTE_TO_CHAR[0x5C] = "'"
    _CHAR_TO_BYTE["/"] = 0x5F
    _BYTE_TO_CHAR[0x5F] = "/"
    for i, c in enumerate("0123456789"):
        b = 0x62 + i
        _CHAR_TO_BYTE[c] = b
        _BYTE_TO_CHAR[b] = c
    for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
        b = 0x6C + i
        _CHAR_TO_BYTE[c] = b
        _BYTE_TO_CHAR[b] = c
    for i, c in enumerate("abcdefghijklmnopqrstuvwxyz"):
        b = 0x86 + i
        _CHAR_TO_BYTE[c] = b
        _BYTE_TO_CHAR[b] = c


def decode_iss_name(data: bytes) -> str:
    """Decode an 8-byte ISS player name to a string."""
    _init_encoding()
    chars = []
    for b in data:
        c = _BYTE_TO_CHAR.get(b, "")
        chars.append(c)
    return "".join(chars).strip()


class ISSRomReader:
    def __init__(self, rom_path: str):
        self.rom_path = rom_path
        self.header_offset = 0
        _init_encoding()

    def _detect_header(self, size: int) -> bool:
        """Detect if ROM has a 512-byte copier header."""
        if size in (_ROM_SIZE_8MBIT_HEADER, _ROM_SIZE_16MBIT_HEADER):
            return True
        if size in (_ROM_SIZE_8MBIT, _ROM_SIZE_16MBIT):
            return False
        # Heuristic: if size % 1024 == 512, likely has header
        return (size % 1024) == 512

    def validate_rom(self) -> bool:
        """Check if file looks like a valid ISS SNES ROM."""
        if not os.path.exists(self.rom_path):
            return False
        size = os.path.getsize(self.rom_path)
        if size < _MIN_ROM_SIZE:
            return False
        self.header_offset = _HEADER_SIZE if self._detect_header(size) else 0
        return True

    def read_player_names(self) -> List[List[str]]:
        """Read all player names. Returns list of 27 teams, each with 15 names.

        Names are stored in TEAM_NAME_ORDER.
        """
        names = []
        with open(self.rom_path, "rb") as f:
            base = _OFS_PLAYER_NAMES + self.header_offset
            for team_idx in range(TOTAL_TEAMS):
                team_names = []
                for player_idx in range(PLAYERS_PER_TEAM):
                    offset = base + (team_idx * PLAYERS_PER_TEAM + player_idx) * 8
                    f.seek(offset)
                    data = f.read(8)
                    team_names.append(decode_iss_name(data))
                names.append(team_names)
        return names

    def read_team_slots(self) -> List[ISSTeamSlot]:
        """Return 27 team slots with their current names."""
        slots = []
        for i, name in enumerate(TEAM_ENUM_ORDER):
            slots.append(ISSTeamSlot(index=i, current_name=name, enum_name=name))
        return slots

    def get_rom_info(self) -> ISSRomInfo:
        """Read ROM and return info including available team slots."""
        is_valid = self.validate_rom()
        size = os.path.getsize(self.rom_path) if os.path.exists(self.rom_path) else 0
        team_slots = self.read_team_slots() if is_valid else []
        return ISSRomInfo(
            path=self.rom_path,
            size=size,
            team_slots=team_slots,
            is_valid=is_valid,
            has_header=self.header_offset > 0,
        )
