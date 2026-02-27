"""Data models for the NHL 07 PSP patcher.

NHL 07 PSP has 30 NHL teams + All-Star + National/European teams.
Roster data is in TDB tables inside a BIGF archive (db.viv) on the ISO.

References:
  - Game ID: ULUS10131
  - TDB tables: STEA (teams), SPBT (bios), SPAI (skater attrs),
    SGAI (goalie attrs), ROST (roster assignments)
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


# STEA table INDX → modern team abbreviation
# 30 NHL teams in NHL 07 (2006-07 season)
NHL07_TEAM_INDEX = {
    0: "ANA",
    1: "ATL",
    2: "BOS",
    3: "BUF",
    4: "CGY",
    5: "CAR",
    6: "CHI",
    7: "COL",
    8: "CBJ",
    9: "DAL",
    10: "DET",
    11: "EDM",
    12: "FLA",
    13: "LA",
    14: "MIN",
    15: "MTL",
    16: "NSH",
    17: "NJ",
    18: "NYI",
    19: "NYR",
    20: "OTT",
    21: "PHI",
    22: "PHX",
    23: "PIT",
    24: "STL",
    25: "SJ",
    26: "TB",
    27: "TOR",
    28: "VAN",
    29: "WSH",
    30: "EAS",
    31: "WES",  # All-Star
}

# Modern NHL abbreviation → STEA INDX (for matching fetched rosters to ROM slots)
# Includes common abbreviation variants from ESPN and NHL APIs
MODERN_NHL_TO_NHL07 = {
    "ANA": 0,  # Anaheim Ducks
    "ATL": 1,  # Atlanta Thrashers (now WPG)
    "BOS": 2,  # Boston Bruins
    "BUF": 3,  # Buffalo Sabres
    "CGY": 4,  # Calgary Flames
    "CAR": 5,  # Carolina Hurricanes
    "CHI": 6,  # Chicago Blackhawks
    "COL": 7,  # Colorado Avalanche
    "CBJ": 8,  # Columbus Blue Jackets
    "DAL": 9,  # Dallas Stars
    "DET": 10,  # Detroit Red Wings
    "EDM": 11,  # Edmonton Oilers
    "FLA": 12,  # Florida Panthers
    "LAK": 13,  # Los Angeles Kings
    "LA": 13,  # ESPN abbreviation
    "MIN": 14,  # Minnesota Wild
    "MTL": 15,  # Montreal Canadiens
    "NSH": 16,  # Nashville Predators
    "NJD": 17,  # New Jersey Devils
    "NJ": 17,  # ESPN abbreviation
    "NYI": 18,  # New York Islanders
    "NYR": 19,  # New York Rangers
    "OTT": 20,  # Ottawa Senators
    "PHI": 21,  # Philadelphia Flyers
    "PHX": 22,  # Phoenix Coyotes (now UTA)
    "ARI": 22,  # Arizona Coyotes (became UTA)
    "UTA": 22,  # Utah Hockey Club → use Phoenix slot
    "PIT": 23,  # Pittsburgh Penguins
    "STL": 24,  # St. Louis Blues
    "SJS": 25,  # San Jose Sharks
    "SJ": 25,  # ESPN abbreviation
    "TBL": 26,  # Tampa Bay Lightning
    "TB": 26,  # ESPN abbreviation
    "TOR": 27,  # Toronto Maple Leafs
    "VAN": 28,  # Vancouver Canucks
    "WSH": 29,  # Washington Capitals
    # Expansion teams not in NHL 07 — map to closest slot
    "WPG": 1,  # Winnipeg Jets → use Atlanta slot
    "VGK": 31,  # Vegas → use WES All-Star slot
    "SEA": 30,  # Seattle → use EAS All-Star slot
}

# Display names for each team index (0-29 = NHL, 30-31 = All-Star)
NHL07_TEAM_NAMES = [
    "Anaheim",  # 0
    "Atlanta",  # 1
    "Boston",  # 2
    "Buffalo",  # 3
    "Calgary",  # 4
    "Carolina",  # 5
    "Chicago",  # 6
    "Colorado",  # 7
    "Columbus",  # 8
    "Dallas",  # 9
    "Detroit",  # 10
    "Edmonton",  # 11
    "Florida",  # 12
    "Los Angeles",  # 13
    "Minnesota",  # 14
    "Montreal",  # 15
    "Nashville",  # 16
    "New Jersey",  # 17
    "NY Islanders",  # 18
    "NY Rangers",  # 19
    "Ottawa",  # 20
    "Philadelphia",  # 21
    "Phoenix",  # 22
    "Pittsburgh",  # 23
    "St. Louis",  # 24
    "San Jose",  # 25
    "Tampa Bay",  # 26
    "Toronto",  # 27
    "Vancouver",  # 28
    "Washington",  # 29
    "East All-Star",  # 30
    "West All-Star",  # 31
]

TEAM_COUNT = 30  # Only NHL teams (not All-Star)
MAX_PLAYERS_PER_TEAM = 30

# Position codes from TDB POS_ field
POSITION_MAP = {
    0: "C",
    1: "LW",
    2: "RW",
    3: "D",
    4: "G",
}
POSITION_REVERSE = {v: k for k, v in POSITION_MAP.items()}

# PSP ISO game ID
GAME_ID = "ULUS10131"

# Known TDB filenames inside db.viv
TDB_MASTER = "nhl2007.tdb"
TDB_BIOATT = "nhlbioatt.tdb"
TDB_ROSTER = "nhlrost.tdb"


@dataclass
class NHL07SkaterAttributes:
    """NHL 07 skater attributes (0-63 scale, 6-bit fields)."""

    balance: int = 30  # BALA
    penalty: int = 30  # PENA
    shot_accuracy: int = 30  # SACC
    wrist_accuracy: int = 30  # WACC
    faceoffs: int = 30  # FACE
    acceleration: int = 30  # ACCE
    speed: int = 30  # SPEE
    potential: int = 30  # POTE
    deking: int = 30  # DEKG
    checking: int = 30  # CHKG
    toughness: int = 30  # TOUG
    fighting: int = 1  # FIGH (2-bit: 0-3)
    puck_control: int = 30  # PUCK
    agility: int = 30  # AGIL
    hero: int = 30  # HERO
    aggression: int = 30  # AGGR
    pressure: int = 30  # PRES
    passing: int = 30  # PASS
    endurance: int = 30  # ENDU
    injury: int = 30  # INJU
    slap_power: int = 30  # SPOW
    wrist_power: int = 30  # WPOW


@dataclass
class NHL07GoalieAttributes:
    """NHL 07 goalie attributes (0-63 scale, 6-bit fields)."""

    breakaway: int = 30  # BRKA
    rebound_ctrl: int = 30  # REBC
    shot_recovery: int = 30  # SREC
    speed: int = 30  # SPEE
    poke_check: int = 30  # POKE
    intensity: int = 30  # INTE
    potential: int = 30  # POTE
    toughness: int = 30  # TOUG
    fighting: int = 1  # FIGH (2-bit)
    agility: int = 30  # AGIL
    five_hole: int = 30  # 5HOL
    passing: int = 30  # PASS
    endurance: int = 30  # ENDU
    glove_high: int = 30  # GSH_
    stick_high: int = 30  # SSH_
    glove_low: int = 30  # GSL_
    stick_low: int = 30  # SSL_


@dataclass
class NHL07PlayerRecord:
    """Complete player record ready to write to TDB tables."""

    first_name: str = ""
    last_name: str = ""
    position: str = "C"
    jersey_number: int = 1
    handedness: int = 1  # 0=L, 1=R
    weight: int = 190  # encoded weight
    height: int = 16  # encoded height (5-bit)
    team_index: int = 0
    player_id: int = 0
    is_goalie: bool = False
    skater_attrs: Optional[NHL07SkaterAttributes] = None
    goalie_attrs: Optional[NHL07GoalieAttributes] = None


@dataclass
class NHL07RosterEntry:
    """A roster slot assigning a player to a team with line positions."""

    team_index: int = 0
    jersey: int = 1
    player_id: int = 0
    captain: int = 0  # 0=none, 1=A, 2=C
    dressed: int = 1  # 0=scratched, 1-3=dressed levels
    # Line assignment flags (single bits)
    line_flags: Dict = field(default_factory=dict)


@dataclass
class NHL07TeamSlot:
    """An existing team slot read from the TDB."""

    index: int
    name: str
    abbreviation: str


@dataclass
class NHL07RomInfo:
    """Information about a loaded NHL 07 PSP ISO."""

    path: str
    size: int = 0
    team_slots: List[NHL07TeamSlot] = field(default_factory=list)
    is_valid: bool = False


@dataclass
class NHL07SlotMapping:
    """Maps a modern NHL team to an NHL 07 ROM slot."""

    team: Team
    slot_index: int
    slot_name: str
