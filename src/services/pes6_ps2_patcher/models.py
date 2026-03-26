"""Data models for the PES6 PS2 patcher."""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple

from services.sports_api.models import (  # noqa: F401
    League,
    Player,
    PlayerStats,
    Team,
    TeamRoster,
    LeagueData,
)


# Attribute byte layout within 124-byte player record.
# All offsets are relative to byte 48 (start of stat data area).
# Source: lazanet/PES-Editor-6 Stats.java
# Read pattern: val = ((data[48+off-1] | data[48+off]<<8) >> shift) & mask
ATTR_OFFSETS = {
    "attack": (7, 0, 0x7F),
    "defence": (8, 0, 0x7F),
    "balance": (9, 0, 0x7F),
    "stamina": (10, 0, 0x7F),
    "speed": (11, 0, 0x7F),
    "acceleration": (12, 0, 0x7F),
    "response": (13, 0, 0x7F),
    "agility": (14, 0, 0x7F),
    "dribble_accuracy": (15, 0, 0x7F),
    "dribble_speed": (16, 0, 0x7F),
    "short_pass_accuracy": (17, 0, 0x7F),
    "short_pass_speed": (18, 0, 0x7F),
    "long_pass_accuracy": (19, 0, 0x7F),
    "long_pass_speed": (20, 0, 0x7F),
    "shot_accuracy": (21, 0, 0x7F),
    "shot_power": (22, 0, 0x7F),
    "shot_technique": (23, 0, 0x7F),
    "free_kick": (24, 0, 0x7F),
    "curling": (25, 0, 0x7F),
    "heading": (26, 0, 0x7F),
    "jump": (27, 0, 0x7F),
    "teamwork": (28, 0, 0x7F),
    "technique": (29, 0, 0x7F),
    "aggression": (30, 0, 0x7F),
    "mentality": (31, 0, 0x7F),
    "gk_ability": (32, 0, 0x7F),
}

# Small fields packed in byte 48+33 (16-bit LE read from bytes 80-81)
SMALL_FIELD_OFFSETS = {
    "consistency": (33, 0, 0x07),
    "weak_foot_freq": (33, 3, 0x07),
    "injury_tolerance": (33, 6, 0x03),
    "condition": (33, 8, 0x07),
    "weak_foot_acc": (33, 11, 0x07),
    "favoured_side": (33, 14, 0x03),
}

# Identity field offsets (relative to byte 48)
IDENTITY_OFFSETS = {
    "regPos": (6, 4, 0x0F),
    "foot": (5, 0, 0x01),
    "nationality": (65, 0, 0x7F),
    "age": (65, 9, 0x1F),
    "height": (41, 0, 0x3F),
    "weight": (41, 8, 0x7F),
}

# Flag offsets (relative to byte 48)
FLAG_OFFSETS = {
    "nameEdited": (3, 0),
    "shirtEdited": (3, 1),
    "abilityEdited": (40, 4),
}

# PES6 EUR position codes (12-value system)
EUR_POSITION_CODES = {
    "GK": 0, "CWP": 1, "CBT": 2, "SB": 3,
    "DMF": 4, "WB": 5, "CMF": 6, "SMF": 7,
    "AMF": 8, "WG": 9, "SS": 10, "CF": 11,
}

# PES6 EUR nationality codes (0-108)
# Unmapped nationalities default to 0 (Austria) at runtime
EUR_NATIONALITY_MAP = {
    "Austria": 0, "Belgium": 1, "Bulgaria": 2, "Croatia": 3,
    "Czech Republic": 4, "Denmark": 5, "England": 6, "Finland": 7,
    "France": 8, "Germany": 9, "Greece": 10, "Hungary": 11,
    "Ireland": 12, "Italy": 13, "Latvia": 14, "Netherlands": 15,
    "Northern Ireland": 16, "Norway": 17, "Poland": 18, "Portugal": 19,
    "Romania": 20, "Russia": 21, "Scotland": 22,
    "Serbia and Montenegro": 23, "Serbia": 23,
    "Slovakia": 24, "Slovenia": 25, "Spain": 26, "Sweden": 27,
    "Switzerland": 28, "Turkey": 29, "Ukraine": 30, "Wales": 31,
    "Angola": 32, "Cameroon": 33, "Cote d'Ivoire": 34, "Ivory Coast": 34,
    "Ghana": 35, "Nigeria": 36, "South Africa": 37, "Togo": 38,
    "Tunisia": 39, "Costa Rica": 40, "Mexico": 41,
    "Trinidad and Tobago": 42, "United States": 43, "USA": 43,
    "Argentina": 44, "Brazil": 45, "Chile": 46, "Colombia": 47,
    "Ecuador": 48, "Paraguay": 49, "Peru": 50, "Uruguay": 51,
    "Iran": 52, "Japan": 53, "Saudi Arabia": 54, "South Korea": 55,
    "Australia": 56,
}


@dataclass
class PES6PlayerAttributes:
    """PES6 player attributes on 0-99 scale (stored as 0-127 in ROM)."""

    attack: int = 50
    defence: int = 50
    balance: int = 50
    stamina: int = 50
    speed: int = 50
    acceleration: int = 50
    response: int = 50
    agility: int = 50
    dribble_accuracy: int = 50
    dribble_speed: int = 50
    short_pass_accuracy: int = 50
    short_pass_speed: int = 50
    long_pass_accuracy: int = 50
    long_pass_speed: int = 50
    shot_accuracy: int = 50
    shot_power: int = 50
    shot_technique: int = 50
    free_kick: int = 50
    curling: int = 50
    heading: int = 50
    jump: int = 50
    teamwork: int = 50
    technique: int = 50
    aggression: int = 50
    mentality: int = 50
    gk_ability: int = 50
    consistency: int = 4  # 0-7
    condition: int = 4  # 0-7


@dataclass
class PES6PlayerRecord:
    """Complete player record ready to write to ISO."""

    name: str  # UTF-16LE, max 15 chars
    shirt_name: str  # ASCII, max 15 chars
    position: int  # 0=GK,1=CWP,2=CBT,3=SB,4=DMF,5=WB,6=CMF,7=SMF,8=AMF,9=WG,10=SS,11=CF
    nationality: int  # 0-127 PES6 nationality code
    age: int  # 15-46 (stored as age-15)
    height: int  # 148-211 cm (stored as height-148)
    weight: int = 75  # Raw kg value (0-127)
    attributes: PES6PlayerAttributes = field(default_factory=PES6PlayerAttributes)
    file35_index: int = 0  # 1-based index in file[35]


@dataclass
class PES6TeamRecord:
    """Complete team record for patching."""

    name: str  # Team display name (max 23 chars)
    abbreviation: str  # 3-4 char code (max 7 chars)
    ram_index: int  # RAM table index (7-199)
    slpm_index: int  # SLPM team name index (ram_index - SLPM_OFFSET)
    player_ids: List[int] = field(default_factory=list)  # file[35] indices
    players: List[PES6PlayerRecord] = field(default_factory=list)


@dataclass
class RomInfo:
    """ROM metadata returned by RomReader."""

    path: str
    size: int
    is_valid: bool = False
    version: str = ""  # Detected ISO variant
    num_players: int = 0
    afs_offset: int = 0  # 0_TEXT.AFS position in ISO
    file35_offset: int = 0  # file[35] position within AFS
    file35_size: int = 0
    base_db_offset: int = 0  # file[34/54] base player DB position
    base_db_size: int = 0
    slpm_offset: int = 0  # SLPM_663.74 position in ISO


@dataclass
class SlotMapping:
    """Maps an ESPN team to a PES6 roster slot."""

    espn_team: Team
    ram_index: int
    slpm_index: int
    slot_name: str  # Current team name in ISO
    player_ids: List[int] = field(default_factory=list)
