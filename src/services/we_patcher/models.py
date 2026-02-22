"""Data models for the WE2002 patcher."""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple


@dataclass
class League:
    id: int
    name: str
    country: str
    country_code: str
    logo_url: str
    season: int
    teams_count: int


@dataclass
class Player:
    id: int
    name: str
    first_name: str
    last_name: str
    age: int
    nationality: str
    position: str  # "Goalkeeper", "Defender", "Midfielder", "Attacker"
    number: Optional[int]
    photo_url: str


@dataclass
class PlayerStats:
    """Detailed per-season stats from API-Football."""

    player_id: int
    appearances: int
    minutes: int
    goals: int
    assists: int
    shots_total: int
    shots_on: int
    passes_total: int
    passes_accuracy: float  # percentage
    tackles_total: int
    interceptions: int
    blocks: int
    duels_total: int
    duels_won: int
    dribbles_attempts: int
    dribbles_success: int
    fouls_committed: int
    fouls_drawn: int
    cards_yellow: int
    cards_red: int
    rating: Optional[float]  # API-Football average rating


@dataclass
class Team:
    id: int
    name: str
    short_name: str
    code: str  # 3-letter abbreviation
    logo_url: str
    country: str


@dataclass
class TeamRoster:
    team: Team
    players: List[Player]
    player_stats: Dict[int, PlayerStats]  # player_id -> stats


@dataclass
class LeagueData:
    league: League
    teams: List[TeamRoster]


@dataclass
class WEPlayerAttributes:
    """WE2002 player attributes on 1-9 scale."""

    offensive: int = 5
    defensive: int = 5
    body_balance: int = 5
    stamina: int = 5
    speed: int = 5
    acceleration: int = 5
    pass_accuracy: int = 5
    shoot_power: int = 5
    shoot_accuracy: int = 5
    jump_power: int = 5
    heading: int = 5
    technique: int = 5
    dribble: int = 5
    curve: int = 5
    aggression: int = 5


@dataclass
class WEPlayerRecord:
    """Complete player record ready to write to ROM."""

    last_name: str  # Truncated to max ROM length
    first_name: str  # Truncated to max ROM length
    position: int  # 0=GK, 1=DF, 2=MF, 3=FW
    shirt_number: int
    attributes: WEPlayerAttributes = field(default_factory=WEPlayerAttributes)


@dataclass
class WETeamRecord:
    """Complete team record ready to write to ROM."""

    name: str
    short_name: str
    kit_home: Tuple[int, int, int] = (255, 255, 255)  # RGB
    kit_away: Tuple[int, int, int] = (0, 0, 0)  # RGB
    kit_gk: Tuple[int, int, int] = (0, 128, 0)  # RGB
    players: List[WEPlayerRecord] = field(default_factory=list)  # Exactly 22
    flag_tim: Optional[bytes] = None  # TIM graphic data


@dataclass
class WETeamSlot:
    """Represents an existing team slot in the ROM."""

    index: int
    current_name: str
    league_group: str  # "League A", "League B", etc.


@dataclass
class SlotMapping:
    """Maps a real team to a WE2002 ROM slot."""

    real_team: Team
    slot_index: int
    slot_name: str


@dataclass
class RomInfo:
    """Information about a loaded WE2002 ROM."""

    path: str
    size: int
    version: str  # Detected WE2002 variant
    team_slots: List[WETeamSlot] = field(default_factory=list)
    is_valid: bool = False


@dataclass
class AfsEntry:
    index: int
    offset: int
    size: int
