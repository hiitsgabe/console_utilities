"""Data models for the PES 6 PS2 patcher.

PES 6 (Pro Evolution Soccer 6) stores team names in the SLES_542.03
executable as variable-length null-terminated UTF-8 strings, 8-byte
aligned, alternating name/abbreviation. 277 team pairs total.

References:
  - SLES_542.03 executable at LBA 323 in the ISO
  - AFS 0_TEXT.AFS at LBA 14741 (9806 files)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

# Re-export shared sports models
from services.sports_api.models import (  # noqa: F401
    League,
    Player,
    PlayerStats,
    Team,
    TeamRoster,
    LeagueData,
)


# ---------------------------------------------------------------------------
# ISO layout constants
# ---------------------------------------------------------------------------

ISO_SECTOR_SIZE = 2048
SLES_LBA = 323  # LBA of SLES_542.03 executable
SLES_SIZE = 3_057_568  # bytes
AFS_0TEXT_LBA = 14741  # LBA of 0_TEXT.AFS
AFS_0TEXT_FILES = 9806  # number of files inside 0_TEXT.AFS

# ---------------------------------------------------------------------------
# Team name table
# ---------------------------------------------------------------------------

TOTAL_TEAMS = 277  # total team name/abbreviation pairs in SLES

# League ranges: maps league key -> (start, end, count, label)
# start is inclusive, end is exclusive (like Python range)
LEAGUE_RANGES: Dict[str, Dict] = {
    "epl": {
        "start": 64,
        "end": 84,
        "count": 20,
        "label": "English Premier League",
    },
    "ligue1": {
        "start": 84,
        "end": 104,
        "count": 20,
        "label": "French Ligue 1",
    },
    "serie_a": {
        "start": 104,
        "end": 124,
        "count": 20,
        "label": "Italian Serie A",
    },
    "eredivisie": {
        "start": 124,
        "end": 142,
        "count": 18,
        "label": "Dutch Eredivisie",
    },
    "la_liga": {
        "start": 142,
        "end": 162,
        "count": 20,
        "label": "Spanish La Liga",
    },
    "other_european": {
        "start": 162,
        "end": 181,
        "count": 19,
        "label": "Other European Clubs",
    },
    "custom": {
        "start": 186,
        "end": 204,
        "count": 18,
        "label": "Custom Teams",
    },
    "national_europe": {
        "start": 204,
        "end": 244,
        "count": 40,
        "label": "European National Teams",
    },
    "national_africa": {
        "start": 244,
        "end": 249,
        "count": 5,
        "label": "African National Teams",
    },
    "national_americas": {
        "start": 249,
        "end": 259,
        "count": 10,
        "label": "Americas National Teams",
    },
    "national_asia": {
        "start": 259,
        "end": 268,
        "count": 9,
        "label": "Asian National Teams",
    },
    "classics": {
        "start": 268,
        "end": 277,
        "count": 9,
        "label": "Classic Teams",
    },
}

# ESPN soccer league IDs -> our league range keys
ESPN_LEAGUE_TO_RANGE: Dict[str, str] = {
    "eng.1": "epl",
    "fra.1": "ligue1",
    "ita.1": "serie_a",
    "ned.1": "eredivisie",
    "esp.1": "la_liga",
    # Leagues without a native PES 6 range — replace the first club league (EPL)
    "ger.1": "epl",
    "por.1": "epl",
    "bra.1": "epl",
    "arg.1": "epl",
    "usa.1": "epl",
    "mex.1": "epl",
    "jpn.1": "epl",
    "col.1": "epl",
    "chi.1": "epl",
}

# Fallback range for any league not in ESPN_LEAGUE_TO_RANGE
# Uses EPL slots so teams appear in the first club league in-game
DEFAULT_LEAGUE_RANGE = "epl"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class PES6TeamSlot:
    """A team slot read from the SLES executable."""

    index: int
    name: str
    abbreviation: str
    name_offset: int = 0  # byte offset within SLES
    abbr_offset: int = 0  # byte offset within SLES
    name_budget: int = 0  # max bytes available for name
    abbr_budget: int = 0  # max bytes available for abbreviation


@dataclass
class PES6RomInfo:
    """Information about a loaded PES 6 PS2 ISO."""

    path: str
    size: int = 0
    team_slots: List[PES6TeamSlot] = field(default_factory=list)
    is_valid: bool = False


@dataclass
class PES6SlotMapping:
    """Maps a modern team to a PES 6 ROM slot."""

    team: Team
    slot_index: int
    slot_name: str
