"""ROM reader for KGJ MLB patcher.

Reads Ken Griffey Jr. Presents MLB (SNES) ROM data.
Supports both headerless (.sfc) and headered (.smc) ROMs by
searching for a marker sequence to locate team data.

References:
  - https://github.com/johnz1/ken_griffey_jr_presents_major_league_baseball_tools
"""

import os
from typing import Optional, List, Tuple

from services.kgj_mlb_patcher.models import (
    KGJRomInfo,
    KGJTeamSlot,
    KGJ_TEAM_ORDER,
    FIRST_TEAM_MARKER,
    TEAM_COUNT,
    AL_TEAMS,
    PLAYER_LENGTH,
    TEAM_LENGTH,
    AL_TO_NL_GAP,
    PLAYERS_PER_TEAM,
    BYTE_TO_CHAR,
    BYTE_TO_POSITION,
)


# Expected ROM size (2 MB = 16 Mbit, headerless)
ROM_SIZE_EXPECTED = 2097152
# SMC header size
SMC_HEADER_SIZE = 512


class KGJRomReader:
    """Reads and parses KGJ MLB SNES ROM data."""

    def __init__(self, rom_path: str):
        self.rom_path = rom_path
        self.data: Optional[bytearray] = None
        self.first_team_offset: int = 0

    def load(self) -> bool:
        """Load ROM file into memory."""
        if not os.path.exists(self.rom_path):
            return False
        try:
            with open(self.rom_path, "rb") as f:
                self.data = bytearray(f.read())
            return True
        except Exception:
            return False

    def validate(self) -> bool:
        """Validate that this is a KGJ MLB ROM."""
        if not self.data:
            return False
        size = len(self.data)
        # Accept headerless (2MB) or headered (2MB + 512)
        if size != ROM_SIZE_EXPECTED and size != ROM_SIZE_EXPECTED + SMC_HEADER_SIZE:
            return False
        # Find team data marker
        pos = self.data.find(FIRST_TEAM_MARKER)
        if pos < 0:
            return False
        self.first_team_offset = pos + len(FIRST_TEAM_MARKER)
        return True

    def get_info(self) -> KGJRomInfo:
        """Get ROM information and team slots."""
        if not self.data:
            return KGJRomInfo(path=self.rom_path, size=0)
        is_valid = self.validate()
        has_header = len(self.data) == ROM_SIZE_EXPECTED + SMC_HEADER_SIZE
        team_slots = self._read_team_slots() if is_valid else []
        return KGJRomInfo(
            path=self.rom_path,
            size=len(self.data),
            first_team_offset=self.first_team_offset,
            team_slots=team_slots,
            is_valid=is_valid,
            has_header=has_header,
        )

    def get_team_offset(self, team_index: int) -> int:
        """Get absolute file offset for a team's player data."""
        if team_index < AL_TEAMS:
            return self.first_team_offset + team_index * TEAM_LENGTH
        else:
            nl_index = team_index - AL_TEAMS
            return (
                self.first_team_offset
                + AL_TEAMS * TEAM_LENGTH
                + AL_TO_NL_GAP
                + nl_index * TEAM_LENGTH
            )

    def get_player_offset(self, team_index: int, player_slot: int) -> int:
        """Get absolute file offset for a specific player."""
        return self.get_team_offset(team_index) + player_slot * PLAYER_LENGTH

    def _decode_name(self, data_bytes: bytes) -> str:
        """Decode custom-encoded name bytes to string."""
        return "".join(
            BYTE_TO_CHAR.get(b, "?") for b in data_bytes
        ).strip()

    def read_player(
        self, team_index: int, player_slot: int
    ) -> dict:
        """Read a single player record from ROM.

        Returns dict with all parsed fields.
        """
        if not self.data:
            return {}
        off = self.get_player_offset(team_index, player_slot)
        if off + PLAYER_LENGTH > len(self.data):
            return {}

        d = self.data
        # Use roster type (0x19 high nibble) to detect batter vs pitcher:
        # 3 = batter, 1 = starting pitcher, 0 = relief pitcher
        roster_type = (d[off + 0x19] >> 4) & 0xF
        is_pitcher = roster_type != 3

        result = {
            "first_initial": BYTE_TO_CHAR.get(d[off], "?"),
            "last_name": self._decode_name(d[off + 1:off + 9]),
            "position": BYTE_TO_POSITION.get(d[off + 9], "?"),
            "jersey": d[off + 0x0A],
            "is_pitcher": is_pitcher,
            "roster_type": roster_type,
            "bat_hand": d[off + 0x0D],
        }

        if is_pitcher:
            spd_con = d[off + 0x0B]
            fat = d[off + 0x0C]
            result["p_speed"] = ((spd_con >> 4) & 0xF) + 1
            result["p_control"] = (spd_con & 0xF) + 1
            result["p_fatigue"] = (fat & 0xF) + 1
            result["pitch_hand"] = (d[off + 0x15] >> 4) & 0xF
            result["wins"] = d[off + 0x18]
            result["losses"] = d[off + 0x1A]
            era_low = d[off + 0x1C]
            era_high = d[off + 0x1D] & 0x0F
            result["era"] = (era_high * 256) + era_low
            result["saves"] = d[off + 0x1E]
        else:
            bat_pow = d[off + 0x0B]
            spd_def = d[off + 0x0C]
            result["batting"] = ((bat_pow >> 4) & 0xF) + 1
            result["power"] = (bat_pow & 0xF) + 1
            result["speed"] = ((spd_def >> 4) & 0xF) + 1
            result["defense"] = (spd_def & 0xF) + 1
            avg_low = d[off + 0x18]
            avg_high = d[off + 0x19] & 0x0F
            result["batting_avg"] = (avg_high * 256) + avg_low
            result["home_runs"] = d[off + 0x1A]
            result["rbi"] = d[off + 0x1C]

        return result

    def read_team_roster(
        self, team_index: int
    ) -> Tuple[List[str], List[dict]]:
        """Read all players for a team.

        Returns: (player_names, player_dicts)
        """
        if not self.data or team_index >= TEAM_COUNT:
            return [], []

        names = []
        players = []
        for slot in range(PLAYERS_PER_TEAM):
            p = self.read_player(team_index, slot)
            if not p:
                break
            name = f"{p['first_initial']}. {p['last_name']}"
            names.append(name)
            players.append(p)

        return names, players

    def _read_team_slots(self) -> List[KGJTeamSlot]:
        """Read team slots for ROM info display."""
        slots = []
        for i in range(TEAM_COUNT):
            first_player = ""
            p = self.read_player(i, 0)
            if p:
                first_player = f"{p['first_initial']}. {p['last_name']}"
            slots.append(KGJTeamSlot(
                index=i,
                name=KGJ_TEAM_ORDER[i] if i < len(KGJ_TEAM_ORDER) else f"Team {i}",
                first_player=first_player,
            ))
        return slots
