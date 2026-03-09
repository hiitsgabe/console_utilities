"""Data models for the MVP Baseball PSP patcher.

MVP Baseball (PSP, ULUS-10012, EA Sports 2005).
database.big contains 18 concatenated RefPack-compressed CSV tables.
852 players, 404 pitchers, 30 MLB teams + special teams.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

# Re-export shared sports models
from services.sports_api.models import (  # noqa: F401
    League,
    Player,
    PlayerStats,
    Team,
    TeamRoster,
    LeagueData,
)

# database.big location in ISO
DATABASE_BIG_LBA = 334832
DATABASE_BIG_SIZE = 386977
ISO_SECTOR_SIZE = 2048

# Section map: (offset_in_file, table_name)
# Each section is a RefPack-compressed CSV blob
SECTION_MAP = [
    (0, "attrib_compact"),
    (324, "attrib"),
    (61772, "lrattrib_rhp"),
    (101852, "lrattrib_lhp"),
    (144692, "batstat"),
    (165552, "fieldstat"),
    (188428, "lrbatstat_rhp"),
    (214440, "lrpitchstat_rhp"),
    (229676, "pitchstat"),
    (245436, "lrbatstat_lhp"),
    (274488, "lrpitchstat_lhp"),
    (290260, "pitchattrib"),
    (313720, "team"),
    (317176, "teamstat"),
    (317752, "roster"),
    (335616, "careerstats"),
    (366772, "pitchcareer"),
    (384620, "organization"),
    (385608, "manager"),
]

# Tables we need to modify for roster patching
WRITABLE_TABLES = [
    "attrib",
    "lrattrib_rhp",
    "lrattrib_lhp",
    "pitchattrib",
    "roster",
    "team",
    "teamstat",
]

# Attrib field numbers (from CSV header)
ATTRIB_FIRST_NAME = 0
ATTRIB_LAST_NAME = 1
ATTRIB_JERSEY = 2
ATTRIB_BATS = 3  # 0=R, 1=L, 2=S
ATTRIB_THROWS = 4  # 0=R, 1=L
ATTRIB_PRIMARY_POS = 5
ATTRIB_SECONDARY_POS = 6
ATTRIB_HEIGHT = 9
ATTRIB_WEIGHT = 10
ATTRIB_PLATE_DISCIPLINE = 18
ATTRIB_BUNTING = 19
ATTRIB_STEALING_AGGRESSIVE = 20
ATTRIB_BASERUNNING = 21
ATTRIB_SPEED = 22
ATTRIB_FIELDING = 23
ATTRIB_RANGE = 24
ATTRIB_THROW_STRENGTH = 25
ATTRIB_THROW_ACCURACY = 26
ATTRIB_DURABILITY = 27
ATTRIB_SALARY = 39
ATTRIB_CONTRACT_LENGTH = 40
ATTRIB_STARPOWER = 41
ATTRIB_BIRTHDAY = 43

# LR Attrib field numbers (vs RHP and vs LHP tables)
LR_CONTACT = 2  # 0-99
LR_POWER = 3  # 0-99
LR_SPRAY_UL = 4
LR_SPRAY_UM = 5
LR_SPRAY_UR = 6
LR_SPRAY_CL = 7
LR_SPRAY_CM = 8
LR_SPRAY_CR = 9
LR_SPRAY_LL = 10
LR_SPRAY_LM = 11
LR_SPRAY_LR = 12
LR_FIELD_PCT_LF = 13
LR_FIELD_PCT_CF = 14
LR_FIELD_PCT_RF = 15
LR_HR_PCT = 16
LR_FB = 17
LR_LD = 18
LR_GB = 19

# Pitch attrib field numbers
PA_STAMINA = 2
PA_PICKOFF = 3
# Pitch 1 is always fastball (no type field): movement, description, control, velocity
PA_PITCH1_MOVEMENT = 4
PA_PITCH1_DESC = 5
PA_PITCH1_CONTROL = 6
PA_PITCH1_VELOCITY = 7
# Pitches 2-5 each have: type, movement, description, control, velocity
PA_PITCH2_TYPE = 8
PA_PITCH2_MOVEMENT = 9
PA_PITCH2_DESC = 10
PA_PITCH2_CONTROL = 11
PA_PITCH2_VELOCITY = 12
PA_PITCHER_DELIVERY = 28

# Attrib position encoding (field 5)
ATTRIB_POS_PITCHER = 0  # SP
ATTRIB_POS_C = 1
ATTRIB_POS_1B = 2
ATTRIB_POS_2B = 3
ATTRIB_POS_3B = 4
ATTRIB_POS_SS = 5
ATTRIB_POS_LF = 6
ATTRIB_POS_CF = 7
ATTRIB_POS_RF = 8
ATTRIB_POS_RELIEVER = 10  # RP/CP/MR/SU/LR

# Map position string to attrib position number
POS_STRING_TO_NUM = {
    "P": 0,
    "SP": 0,
    "SP1": 0,
    "SP2": 0,
    "SP3": 0,
    "SP4": 0,
    "SP5": 0,
    "C": 1,
    "1B": 2,
    "2B": 3,
    "3B": 4,
    "SS": 5,
    "LF": 6,
    "CF": 7,
    "RF": 8,
    "OF": 7,
    "DH": 2,
    "RP": 10,
    "CP": 10,
    "CL": 10,
    "MR": 10,
    "SU": 10,
    "LR": 10,
}

# Roster field numbers
ROSTER_TEAMID = 0
ROSTER_PLAYERID = 1
ROSTER_RH_AL_POS = 2
ROSTER_RH_AL_ORDER = 3
ROSTER_RH_NL_POS = 4
ROSTER_RH_NL_ORDER = 5
ROSTER_LH_AL_POS = 6
ROSTER_LH_AL_ORDER = 7
ROSTER_LH_NL_POS = 8
ROSTER_LH_NL_ORDER = 9

# Team field numbers
TEAM_NAME = 0
TEAM_LEAGUE = 1
TEAM_DIVISION = 2
TEAM_ARTID = 3

# Positions used in roster table
POSITIONS = [
    "C",
    "1B",
    "2B",
    "SS",
    "3B",
    "LF",
    "CF",
    "RF",
    "DH",
    "SP1",
    "SP2",
    "SP3",
    "SP4",
    "SP5",
    "LR",
    "MR",
    "SU",
    "CP",
    "B",  # Bench
]

PLAYERS_PER_TEAM = 25
PITCHERS_PER_TEAM = 10  # 5 SP + 5 RP (LR, MR, SU, CP, extra)
BATTERS_PER_TEAM = 15
STARTERS_PER_TEAM = 5
TEAM_COUNT = 30  # 30 MLB teams (no specials patched)

# Team hash IDs from database.big
TEAM_HASHES = {
    "ANA": "00b87d5f5",
    "OAK": "00b880fe0",
    "SEA": "00b88215e",
    "TEX": "00b8825b6",
    "CWS": "00b87db72",
    "CLE": "00b87de39",
    "DET": "00b87e1a2",
    "KC": "000597433",
    "MIN": "00b880869",
    "BAL": "00b87d894",
    "BOS": "00b87da69",
    "NYY": "00b880a85",
    "TB": "00059755b",
    "TOR": "00b8826fa",
    "ARI": "00b87d681",
    "COL": "00b87dea3",
    "LA": "000597452",
    "SD": "00059753c",
    "SF": "00059753e",
    "CHC": "00b87dd93",
    "CIN": "00b87dddf",
    "HOU": "00b87f3f1",
    "MIL": "00b880867",
    "PIT": "00b881532",
    "STL": "00b882338",
    "ATL": "00b87d6c6",
    "FLA": "00b87eaf8",
    "WAS": "00b8831f0",
    "NYM": "00b880a79",
    "PHI": "00b881506",
}

# Game team order (indices 0-29 match ROM positions)
MVP_TEAM_ORDER = [
    "Anaheim Angels",  # 0  ANA
    "Oakland Athletics",  # 1  OAK
    "Seattle Mariners",  # 2  SEA
    "Texas Rangers",  # 3  TEX
    "Chicago White Sox",  # 4  CWS
    "Cleveland Indians",  # 5  CLE
    "Detroit Tigers",  # 6  DET
    "Kansas City Royals",  # 7  KC
    "Minnesota Twins",  # 8  MIN
    "Baltimore Orioles",  # 9  BAL
    "Boston Red Sox",  # 10 BOS
    "New York Yankees",  # 11 NYY
    "Tampa Bay Devil Rays",  # 12 TB
    "Toronto Blue Jays",  # 13 TOR
    "Arizona Diamondbacks",  # 14 ARI
    "Colorado Rockies",  # 15 COL
    "Los Angeles Dodgers",  # 16 LA
    "San Diego Padres",  # 17 SD
    "San Francisco Giants",  # 18 SF
    "Chicago Cubs",  # 19 CHC
    "Cincinnati Reds",  # 20 CIN
    "Houston Astros",  # 21 HOU
    "Milwaukee Brewers",  # 22 MIL
    "Pittsburgh Pirates",  # 23 PIT
    "St. Louis Cardinals",  # 24 STL
    "Atlanta Braves",  # 25 ATL
    "Florida Marlins",  # 26 FLA
    "Washington Nationals",  # 27 WAS
    "New York Mets",  # 28 NYM
    "Philadelphia Phillies",  # 29 PHI
]

# Map game team abbreviations to team hash IDs
TEAM_ABBREV_TO_HASH = {
    "ANA": "00b87d5f5",
    "OAK": "00b880fe0",
    "SEA": "00b88215e",
    "TEX": "00b8825b6",
    "CWS": "00b87db72",
    "CLE": "00b87de39",
    "DET": "00b87e1a2",
    "KC": "000597433",
    "MIN": "00b880869",
    "BAL": "00b87d894",
    "BOS": "00b87da69",
    "NYY": "00b880a85",
    "TB": "00059755b",
    "TOR": "00b8826fa",
    "ARI": "00b87d681",
    "COL": "00b87dea3",
    "LA": "000597452",
    "SD": "00059753c",
    "SF": "00059753e",
    "CHC": "00b87dd93",
    "CIN": "00b87dddf",
    "HOU": "00b87f3f1",
    "MIL": "00b880867",
    "PIT": "00b881532",
    "STL": "00b882338",
    "ATL": "00b87d6c6",
    "FLA": "00b87eaf8",
    "WAS": "00b8831f0",
    "NYM": "00b880a79",
    "PHI": "00b881506",
}

# Modern ESPN team abbreviation -> MVP game abbreviation
MODERN_MLB_TO_MVP = {
    "LAA": "ANA",  # Los Angeles Angels -> Anaheim Angels
    "OAK": "OAK",
    "ATH": "OAK",  # ESPN alternate for Athletics
    "SEA": "SEA",
    "TEX": "TEX",
    "CWS": "CWS",
    "CHW": "CWS",  # ESPN alternate
    "CLE": "CLE",  # Cleveland Guardians -> Indians
    "DET": "DET",
    "KC": "KC",
    "MIN": "MIN",
    "BAL": "BAL",
    "BOS": "BOS",
    "NYY": "NYY",
    "TB": "TB",  # Tampa Bay Rays -> Devil Rays
    "TOR": "TOR",
    "ARI": "ARI",
    "COL": "COL",
    "LAD": "LA",  # Dodgers
    "SD": "SD",
    "SF": "SF",
    "CHC": "CHC",
    "CIN": "CIN",
    "HOU": "HOU",
    "MIL": "MIL",
    "PIT": "PIT",
    "STL": "STL",
    "ATL": "ATL",
    "MIA": "FLA",  # Miami Marlins -> Florida Marlins
    "WSH": "WAS",  # Washington Nationals
    "NYM": "NYM",
    "PHI": "PHI",
}

# Map game abbreviation -> team index in MVP_TEAM_ORDER
MVP_ABBREV_TO_INDEX = {
    "ANA": 0,
    "OAK": 1,
    "SEA": 2,
    "TEX": 3,
    "CWS": 4,
    "CLE": 5,
    "DET": 6,
    "KC": 7,
    "MIN": 8,
    "BAL": 9,
    "BOS": 10,
    "NYY": 11,
    "TB": 12,
    "TOR": 13,
    "ARI": 14,
    "COL": 15,
    "LA": 16,
    "SD": 17,
    "SF": 18,
    "CHC": 19,
    "CIN": 20,
    "HOU": 21,
    "MIL": 22,
    "PIT": 23,
    "STL": 24,
    "ATL": 25,
    "FLA": 26,
    "WAS": 27,
    "NYM": 28,
    "PHI": 29,
}


@dataclass
class MVPPlayerRecord:
    """A player record for MVP Baseball PSP."""

    hash_id: str = ""
    first_name: str = ""
    last_name: str = ""
    jersey: int = 0
    bats: int = 0  # 0=R, 1=L, 2=S
    throws: int = 0  # 0=R, 1=L
    primary_position: str = "CF"
    secondary_position: str = ""
    height: int = 72  # inches
    weight: int = 190  # lbs

    # General attributes (0-99)
    speed: int = 50
    fielding: int = 50
    arm_range: int = 50
    throw_strength: int = 50
    throw_accuracy: int = 50
    durability: int = 50
    plate_discipline: int = 50
    bunting: int = 50
    baserunning: int = 50
    stealing: int = 50
    starpower: int = 50

    # Contact/Power vs RHP and LHP (0-99)
    contact_rhp: int = 50
    power_rhp: int = 50
    contact_lhp: int = 50
    power_lhp: int = 50

    # Pitcher attributes
    is_pitcher: bool = False
    stamina: int = 50
    pickoff: int = 50
    pitches: List[Dict] = field(default_factory=list)

    # Roster assignment
    roster_position: str = ""  # C, 1B, SP1, CP, B, etc.
    batting_order: int = -1  # -1 = not in lineup


@dataclass
class MVPTeamRecord:
    """A team record for MVP Baseball PSP."""

    index: int
    name: str
    abbrev: str
    hash_id: str
    players: List[MVPPlayerRecord] = field(default_factory=list)


@dataclass
class MVPTeamSlot:
    """Existing team slot info read from ISO."""

    index: int
    name: str
    abbrev: str
    player_count: int = 0
    first_player: str = ""


@dataclass
class MVPRomInfo:
    """Information about a loaded MVP Baseball PSP ISO."""

    path: str
    size: int
    database_big_offset: int = 0
    database_big_size: int = 0
    team_slots: List[MVPTeamSlot] = field(default_factory=list)
    is_valid: bool = False
