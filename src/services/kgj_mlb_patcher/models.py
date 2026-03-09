"""Data models for the KGJ MLB patcher.

Ken Griffey Jr. Presents Major League Baseball (SNES, 1994).
28 MLB teams (14 AL, 14 NL), 25 players per team (15 batters + 10 pitchers).
Player records are 32 bytes each with custom character encoding.

References:
  - https://github.com/johnz1/ken_griffey_jr_presents_major_league_baseball_tools
"""

from dataclasses import dataclass, field
from typing import List, Optional

# Re-export shared sports models
from services.sports_api.models import (  # noqa: F401
    League,
    Player,
    PlayerStats,
    Team,
    TeamRoster,
    LeagueData,
)


# Custom character encoding used for player names
CHAR_TO_BYTE = {
    " ": 0x00,
    "0": 0x01,
    "1": 0x02,
    "2": 0x03,
    "3": 0x04,
    "4": 0x05,
    "5": 0x06,
    "6": 0x07,
    "7": 0x08,
    "8": 0x09,
    "9": 0x0A,
    "A": 0x0B,
    "B": 0x0C,
    "C": 0x0D,
    "D": 0x0E,
    "E": 0x0F,
    "F": 0x10,
    "G": 0x11,
    "H": 0x12,
    "I": 0x13,
    "J": 0x14,
    "K": 0x15,
    "L": 0x16,
    "M": 0x17,
    "N": 0x18,
    "O": 0x19,
    "P": 0x1A,
    "Q": 0x1B,
    "R": 0x1C,
    "S": 0x1D,
    "T": 0x1E,
    "U": 0x1F,
    "V": 0x20,
    "W": 0x21,
    "X": 0x22,
    "Y": 0x23,
    "Z": 0x24,
    "c": 0x36,
}
BYTE_TO_CHAR = {v: k for k, v in CHAR_TO_BYTE.items()}

# Position encoding (values step by 2)
POSITION_TO_BYTE = {
    "P": 0x00,
    "C": 0x02,
    "LF": 0x04,
    "CF": 0x06,
    "RF": 0x08,
    "3B": 0x0A,
    "SS": 0x0C,
    "2B": 0x0E,
    "1B": 0x10,
    "DH": 0x12,
    "IF": 0x14,
    "OF": 0x16,
}
BYTE_TO_POSITION = {v: k for k, v in POSITION_TO_BYTE.items()}

# Batting handedness encoding
HAND_RIGHT = 0x00
HAND_LEFT = 0x11
HAND_SWITCH = 0x20

# ROM layout constants
PLAYER_LENGTH = 0x20  # 32 bytes per player
TEAM_LENGTH = 0x320  # 800 bytes per team (25 * 32)
AL_TO_NL_GAP = 0xB40  # 2880 bytes between last AL and first NL team
PLAYERS_PER_TEAM = 25  # 15 batters + 5 starters + 5 relievers
BATTERS_PER_TEAM = 15
STARTERS_PER_TEAM = 5
RELIEVERS_PER_TEAM = 5

# Marker to find first team data (14 bytes before team 0)
FIRST_TEAM_MARKER = bytes(
    [
        0x81,
        0x81,
        0x81,
        0x81,
        0x9F,
        0x9F,
        0x90,
        0x90,
        0x90,
        0x90,
        0x90,
        0x90,
        0xF0,
        0xF0,
    ]
)

# HR Derby marker (6 batters follow this)
HR_DERBY_MARKER = bytes(
    [
        0x02,
        0x2E,
        0x37,
        0x27,
        0x00,
        0x0A,
        0x23,
        0x3B,
        0x35,
        0xFF,
    ]
)

# Team order in ROM: 0-13 = AL, 14-27 = NL (1994 MLB)
TEAM_COUNT = 28
AL_TEAMS = 14
NL_TEAMS = 14

KGJ_TEAM_ORDER = [
    # American League (0-13)
    "Baltimore Orioles",  # 0
    "Boston Red Sox",  # 1
    "California Angels",  # 2
    "Chicago White Sox",  # 3
    "Cleveland Indians",  # 4
    "Detroit Tigers",  # 5
    "Kansas City Royals",  # 6
    "Milwaukee Brewers",  # 7
    "Minnesota Twins",  # 8
    "New York Yankees",  # 9
    "Oakland Athletics",  # 10
    "Seattle Mariners",  # 11
    "Texas Rangers",  # 12
    "Toronto Blue Jays",  # 13
    # National League (14-27)
    "Atlanta Braves",  # 14
    "Chicago Cubs",  # 15
    "Cincinnati Reds",  # 16
    "Houston Astros",  # 17
    "Los Angeles Dodgers",  # 18
    "Montreal Expos",  # 19
    "New York Mets",  # 20
    "Pittsburgh Pirates",  # 21
    "St. Louis Cardinals",  # 22
    "San Diego Padres",  # 23
    "San Francisco Giants",  # 24
    "Philadelphia Phillies",  # 25
    "Colorado Rockies",  # 26
    "Florida Marlins",  # 27
]

# Modern MLB team abbreviation -> KGJ ROM slot index.
# Maps current 30 teams to the 28 ROM slots.
# Arizona (ARI) and Tampa Bay (TB) didn't exist in 1994 — no ROM slot.
# Montreal Expos became Washington Nationals, California Angels became
# Los Angeles Angels, Florida Marlins became Miami Marlins.
MODERN_MLB_TO_KGJ = {
    "BAL": 0,  # Baltimore Orioles
    "BOS": 1,  # Boston Red Sox
    "LAA": 2,  # Los Angeles Angels (was California Angels)
    "CWS": 3,  # Chicago White Sox
    "CHW": 3,  # ESPN alternate
    "CLE": 4,  # Cleveland Guardians (was Indians)
    "DET": 5,  # Detroit Tigers
    "KC": 6,  # Kansas City Royals
    "MIL": 7,  # Milwaukee Brewers
    "MIN": 8,  # Minnesota Twins
    "NYY": 9,  # New York Yankees
    "OAK": 10,  # Oakland Athletics
    "ATH": 10,  # ESPN abbreviation (Athletics)
    "SEA": 11,  # Seattle Mariners
    "TEX": 12,  # Texas Rangers
    "TOR": 13,  # Toronto Blue Jays
    "ATL": 14,  # Atlanta Braves
    "CHC": 15,  # Chicago Cubs
    "CIN": 16,  # Cincinnati Reds
    "HOU": 17,  # Houston Astros
    "LAD": 18,  # Los Angeles Dodgers
    "WSH": 19,  # Washington Nationals (was Montreal Expos)
    "NYM": 20,  # New York Mets
    "PIT": 21,  # Pittsburgh Pirates
    "STL": 22,  # St. Louis Cardinals
    "SD": 23,  # San Diego Padres
    "SF": 24,  # San Francisco Giants
    "PHI": 25,  # Philadelphia Phillies
    "COL": 26,  # Colorado Rockies
    "MIA": 27,  # Miami Marlins (was Florida Marlins)
}


@dataclass
class KGJBatterAttributes:
    """Batter ratings (1-10 scale)."""

    batting: int = 5  # BAT — contact/hitting ability
    power: int = 5  # POW — home run power
    speed: int = 5  # SPD — baserunning speed
    defense: int = 5  # DEF — fielding ability


@dataclass
class KGJPitcherAttributes:
    """Pitcher ratings (1-10 scale)."""

    speed: int = 5  # SPD — fastball velocity
    control: int = 5  # CON — pitch accuracy
    fatigue: int = 5  # FAT — stamina


@dataclass
class KGJBatterAppearance:
    """Visual appearance for a batter at the plate."""

    skin: int = 0  # 0-5: White, Tan, Very Tan, Light Black, Black, Dark Black
    head: int = 0  # 0-7: hair/facial hair combos
    hair_color: int = 4  # 0-5: Blonde/Brown, Red, Brown, Bald, Black, Blonde
    body: int = 1  # 0-7: build/stance
    legs_size: int = 0  # 0-1: Average, Small
    legs_stance: int = 0  # 0-4: various stances
    arms_stance: int = 0  # 0-2: bat position


@dataclass
class KGJPitcherAppearance:
    """Visual appearance for a pitcher on the mound."""

    skin: int = 0  # 0-5: same as batter
    head: int = 0  # 0-4: hair/facial hair combos
    hair_color: int = 4  # 0-4: Blonde, Red, Blonde/Brown, Brown, Black
    body: int = 0  # 0-2: Average, Fat, Tall
    throwing_style: int = 0  # 0=Overhand, 1=Sidearm


@dataclass
class KGJPlayerRecord:
    """Complete player record ready to write to ROM (32 bytes)."""

    first_initial: str = "A"
    last_name: str = "PLAYER"
    position: str = "CF"
    jersey_number: int = 1
    is_pitcher: bool = False
    bat_hand: int = HAND_RIGHT  # Batting handedness

    # Batter fields
    batter_attrs: KGJBatterAttributes = field(default_factory=KGJBatterAttributes)
    batter_appearance: KGJBatterAppearance = field(default_factory=KGJBatterAppearance)
    batting_avg: int = 250  # e.g. 250 = .250
    home_runs: int = 0
    rbi: int = 0

    # Pitcher fields
    pitcher_attrs: KGJPitcherAttributes = field(default_factory=KGJPitcherAttributes)
    pitcher_appearance: KGJPitcherAppearance = field(
        default_factory=KGJPitcherAppearance
    )
    pitch_hand: int = 0  # 0=Right, 1=Left
    wins: int = 0
    losses: int = 0
    era: int = 400  # e.g. 400 = 4.00 ERA
    saves: int = 0

    # Roster type (set during write based on slot position)
    roster_type: int = 0x30  # 0x30=batter, 0x10=starter, 0x00=reliever


@dataclass
class KGJTeamRecord:
    """Complete team record."""

    index: int
    name: str
    players: List[KGJPlayerRecord] = field(default_factory=list)


@dataclass
class KGJTeamSlot:
    """An existing team slot read from the ROM."""

    index: int
    name: str  # From KGJ_TEAM_ORDER
    first_player: str  # First player name for verification


@dataclass
class KGJRomInfo:
    """Information about a loaded KGJ ROM."""

    path: str
    size: int
    first_team_offset: int = 0
    team_slots: List[KGJTeamSlot] = field(default_factory=list)
    is_valid: bool = False
    has_header: bool = False


@dataclass
class KGJSlotMapping:
    """Maps a modern MLB team to a KGJ ROM slot."""

    team: Team
    slot_index: int
    slot_name: str
