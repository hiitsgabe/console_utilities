"""Data models for the NHL94 SNES patcher.

NHL 94 (SNES) has 28 teams (26 NHL + 2 All-Star) with ~23 players each.
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


# NHL team order in NHL 94 SNES ROM
# 28 teams: 26 NHL teams (sorted alphabetically) + 2 All-Star teams
NHL94_TEAM_ORDER = [
    "Anaheim",      # 0 - Mighty Ducks (will map to SJS for modern)
    "Boston",       # 1
    "Buffalo",      # 2
    "Calgary",      # 3
    "Chicago",      # 4
    "Dallas",       # 5
    "Detroit",      # 6
    "Edmonton",     # 7
    "Florida",      # 8
    "Hartford",     # 9 - Carolina Hurricanes (relocated)
    "Los Angeles",  # 10
    "Montreal",     # 11
    "New Jersey",   # 12
    "NY Islanders", # 13
    "NY Rangers",   # 14
    "Ottawa",       # 15
    "Philadelphia", # 16
    "Pittsburgh",   # 17
    "Quebec",       # 18 - Colorado Avalanche (relocated)
    "San Jose",     # 19
    "St. Louis",    # 20
    "Tampa Bay",    # 21
    "Toronto",      # 22
    "Vancouver",    # 23
    "Washington",   # 24
    "Winnipeg",     # 25
    "All-Star East", # 26
    "All-Star West", # 27
]

# Modern NHL team abbreviation to NHL94 slot mapping
# Includes both standard (NHL.com) and ESPN abbreviation variants.
# Excludes expansion teams not in NHL94 (CBJ, MIN, NSH, SEA, UTA, VGK).
MODERN_NHL_TO_NHL94 = {
    "ANA": 0,   # Anaheim Ducks
    "BOS": 1,   # Boston Bruins
    "BUF": 2,   # Buffalo Sabres
    "CGY": 3,   # Calgary Flames
    "CHI": 4,   # Chicago Blackhawks
    "DAL": 5,   # Dallas Stars
    "DET": 6,   # Detroit Red Wings
    "EDM": 7,   # Edmonton Oilers
    "FLA": 8,   # Florida Panthers
    "CAR": 9,   # Carolina Hurricanes (was Hartford)
    "LAK": 10,  # Los Angeles Kings
    "LA": 10,   # ESPN abbreviation
    "MTL": 11,  # Montreal Canadiens
    "NJD": 12,  # New Jersey Devils
    "NJ": 12,   # ESPN abbreviation
    "NYI": 13,  # New York Islanders
    "NYR": 14,  # New York Rangers
    "OTT": 15,  # Ottawa Senators
    "PHI": 16,  # Philadelphia Flyers
    "PIT": 17,  # Pittsburgh Penguins
    "COL": 18,  # Colorado Avalanche (was Quebec)
    "SJS": 19,  # San Jose Sharks
    "SJ": 19,   # ESPN abbreviation
    "STL": 20,  # St. Louis Blues
    "TBL": 21,  # Tampa Bay Lightning
    "TB": 21,   # ESPN abbreviation
    "TOR": 22,  # Toronto Maple Leafs
    "VAN": 23,  # Vancouver Canucks
    "WSH": 24,  # Washington Capitals
    "WPG": 25,  # Winnipeg Jets
    # 26 and 27 are All-Star teams (not mapped)
}

TEAM_COUNT = 28
MAX_PLAYERS_PER_TEAM = 25  # Typical NHL active roster


@dataclass
class NHL94PlayerAttributes:
    """NHL94 player attributes (0-6 scale).

    NHL94 uses nibble-packing for stats. Each stat is 0-6 where:
    0 = 25, 1 = 35, 2 = 45, 3 = 55, 4 = 65, 5 = 85, 6 = 100
    """

    speed: int = 3
    agility: int = 3
    shot_power: int = 3
    shot_accuracy: int = 3
    stick_handling: int = 3
    pass_accuracy: int = 3
    off_awareness: int = 3
    def_awareness: int = 3
    checking: int = 3
    endurance: int = 3
    # Hidden stats
    roughness: int = 2
    aggression: int = 2


@dataclass
class NHL94PlayerRecord:
    """Complete player record ready to write to ROM."""

    name: str                    # Plain ASCII, variable length
    jersey_number: int = 1       # 1-99, BCD format
    weight_class: int = 7        # 0-14 (140-252 lbs via 140 + class*8)
    handedness: int = 0          # 0=L (even), 1=R (odd)
    is_goalie: bool = False
    attributes: NHL94PlayerAttributes = field(default_factory=NHL94PlayerAttributes)


@dataclass
class NHL94TeamRecord:
    """Complete team record ready to write to ROM."""

    index: int                   # 0-27
    name: str                    # Team name (e.g., "Boston")
    city: str                    # City (e.g., "Boston")
    acronym: str                 # 3-letter (e.g., "BOS")
    players: List[NHL94PlayerRecord] = field(default_factory=list)


@dataclass
class NHL94TeamSlot:
    """Represents an existing team slot in the ROM."""

    index: int
    current_name: str
    display_name: str           # Name from NHL94_TEAM_ORDER


@dataclass
class NHL94RomInfo:
    """Information about a loaded NHL94 SNES ROM."""

    path: str
    size: int
    team_slots: List[NHL94TeamSlot] = field(default_factory=list)
    is_valid: bool = False
    has_header: bool = False    # SNES ROMs may have 512-byte copier header


@dataclass
class NHL94SlotMapping:
    """Maps a modern NHL team to an NHL94 ROM slot."""

    team: Team
    slot_index: int             # 0-27
    slot_name: str              # Display name for UI