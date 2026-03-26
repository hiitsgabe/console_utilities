"""Load and query the PES6 roster map from compressed binary asset."""

import json
import os
import struct
import zlib
from typing import Dict, List, Tuple


MAGIC = b"PES6RM"
SLPM_OFFSET = 21  # ram_index - slpm_offset = slpm_index


class RosterMap:
    """Team-to-player-index mappings from compressed binary asset.

    The binary contains only structural data: which file[35] player indices
    belong to which RAM team slot. No team names or league-specific data.
    """

    def __init__(self, bin_path: str = None):
        if bin_path is None:
            bin_path = os.path.join(
                os.path.dirname(__file__),
                "..",
                "..",
                "..",
                "assets",
                "pes6_roster_map.bin",
            )
        with open(bin_path, "rb") as f:
            raw = f.read()

        magic = raw[:6]
        if magic != MAGIC:
            raise ValueError(f"Invalid roster map: expected {MAGIC!r}, got {magic!r}")
        comp_size = struct.unpack_from("<I", raw, 12)[0]
        compressed = raw[16 : 16 + comp_size]

        json_bytes = zlib.decompress(compressed)
        data = json.loads(json_bytes)

        self._teams = data.get("teams", {})
        self._meta = data.get("meta", {})

    def get_team_player_ids(self, ram_index: int) -> List[int]:
        """Get flat list of player indices for a team."""
        team = self._teams.get(str(ram_index), {})
        # New format: players = [{idx, pos}, ...]
        players = team.get("players")
        if players and len(players) > 0 and isinstance(players[0], dict):
            return [p["idx"] for p in players]
        # Old format: pi = [int, ...]
        return team.get("pi", [])

    def get_team_players(self, ram_index: int) -> List[Dict[str, int]]:
        """Get list of player entries with idx and pos."""
        team = self._teams.get(str(ram_index), {})
        return team.get("players", [])

    def get_team_name(self, ram_index: int) -> str:
        """Get team name from roster map."""
        team = self._teams.get(str(ram_index), {})
        return team.get("name", "")

    def get_team_player_count(self, ram_index: int) -> int:
        """Get number of valid players for a team."""
        team = self._teams.get(str(ram_index), {})
        players = team.get("players", [])
        return team.get("player_count", len(players))

    def get_team_roster_slots(self, ram_index: int) -> List[int]:
        """Return all 32 roster slots (including zeros for empty)."""
        team = self._teams.get(str(ram_index), {})
        return team.get("rs", [])

    @property
    def slpm_offset(self) -> int:
        return self._meta.get("slpm_offset", SLPM_OFFSET)

    def get_slot_range(self, start: int = 7, end: int = 200) -> List[int]:
        """Return RAM indices with teams in given range."""
        return [int(k) for k in self._teams.keys() if start <= int(k) < end]

    def get_all_team_indices(self) -> List[int]:
        """Return all RAM indices that have teams."""
        return sorted(int(k) for k in self._teams.keys())

    @property
    def total_players(self) -> int:
        return self._meta.get("total_players_in_db", 4873)
