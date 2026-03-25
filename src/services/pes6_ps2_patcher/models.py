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
    position: int  # 0=GK, 1=CB, 2=SB, 3=DMF, 4=CMF, 5=SMF, 6=AMF, 7=WF, 8=SS, 9=CF
    nationality: int  # 0-127 PES6 nationality code
    age: int  # 15-46 (stored as age-15)
    height: int  # 148-211 cm (stored as height-148)
    weight: int  # 148-275 (stored as weight-148, but practically 50-120 kg range)
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
