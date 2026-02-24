"""Data models for the ISS SNES patcher.

International Superstar Soccer (1994, SNES) has 27 teams (26 national + Super Star)
with 15 players each = 405 players total.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Tuple

# Re-export shared sports models so existing imports keep working
from services.sports_api.models import (  # noqa: F401
    League,
    Player,
    PlayerStats,
    Team,
    TeamRoster,
    LeagueData,
)

# ── 27 teams in canonical (enum) order ──────────────────────────────────────
TEAM_ENUM_ORDER = [
    "Germany", "Italy", "Holland", "Spain", "England", "Scotland", "Wales",
    "France", "Denmark", "Sweden", "Norway", "Ireland", "Belgium", "Austria",
    "Switz", "Romania", "Bulgaria", "Russia", "Argentina", "Brazil",
    "Colombia", "Mexico", "U.S.A.", "Nigeria", "Cameroon", "S.Korea",
    "Super Star",
]

# Player name data uses a DIFFERENT team order
TEAM_NAME_ORDER = [
    "Germany", "Italy", "Holland", "Spain", "England", "Wales", "France",
    "Denmark", "Sweden", "Norway", "Ireland", "Belgium", "Austria", "Switz",
    "Romania", "Bulgaria", "Russia", "Argentina", "Brazil", "Colombia",
    "Mexico", "U.S.A.", "Nigeria", "Cameroon", "Scotland", "S.Korea",
    "Super Star",
]

# Hair style ordinals
HAIR_STYLES = [
    "Short", "Curly", "Long Curly", "Long Beard", "Long Straight",
    "Dreadlocks", "Afro", "Ponytail", "Bald", "Mid Length", "Long Ribbon",
]

PLAYERS_PER_TEAM = 15
TOTAL_TEAMS = 27
TOTAL_PLAYERS = PLAYERS_PER_TEAM * TOTAL_TEAMS  # 405


@dataclass
class ISSPlayerAttributes:
    """ISS player attributes.

    ISS has a simpler attribute system than WE2002:
    - speed: encoded in byte 0 of the 6-byte block (1-16 range)
    - shooting: 3-bit value (0-7) mapped to [1,3,5,7,9,11,13,15]
    - stamina: low nibble of byte 4 + 1 (1-16 range)
    - technique: 3-bit value same encoding as shooting
    """

    speed: int = 8          # 1-16
    shooting: int = 7       # 1-15 (odd values: 1,3,5,7,9,11,13,15)
    stamina: int = 8        # 1-16
    technique: int = 7      # 1-15 (odd values)


@dataclass
class ISSPlayerRecord:
    """Complete player record ready to write to ROM."""

    name: str                    # 8 chars max, ISS custom encoding
    shirt_number: int = 1        # 1-16
    position: int = 2            # 0=GK, 1=DF, 2=MF, 3=FW (not stored in ROM, used for mapping)
    hair_style: int = 0          # 0-10 ordinal
    is_special: bool = False     # Star player (unique appearance)
    attributes: ISSPlayerAttributes = field(default_factory=ISSPlayerAttributes)


@dataclass
class ISSTeamRecord:
    """Complete team record ready to write to ROM."""

    name: str                    # Team name for display
    short_name: str              # 3-letter abbreviation
    kit_home: Tuple[Tuple[int, int, int], ...] = ()    # Home kit colors (shirt, shorts, socks) as RGB tuples
    kit_away: Tuple[Tuple[int, int, int], ...] = ()    # Away kit colors
    kit_gk: Tuple[Tuple[int, int, int], ...] = ()      # GK kit colors
    flag_colors: List[Tuple[int, int, int]] = field(default_factory=list)  # 4 flag colors as RGB
    players: List[ISSPlayerRecord] = field(default_factory=list)  # Exactly 15


@dataclass
class ISSTeamSlot:
    """Represents an existing team slot in the ROM."""

    index: int
    current_name: str
    enum_name: str           # canonical name from TEAM_ENUM_ORDER


@dataclass
class ISSSlotMapping:
    """Maps a real team to an ISS ROM slot."""

    real_team: Team
    slot_index: int          # 0-26 in enum order
    slot_name: str           # Display name for UI


@dataclass
class ISSRomInfo:
    """Information about a loaded ISS SNES ROM."""

    path: str
    size: int
    team_slots: List[ISSTeamSlot] = field(default_factory=list)
    is_valid: bool = False
    has_header: bool = False  # SNES ROMs may have 512-byte copier header
