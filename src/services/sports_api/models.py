"""Shared data models for sports API clients (API-Football, ESPN, etc.)."""

from dataclasses import dataclass, field
from typing import Optional, List, Dict


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
    lineups: int = 0  # Times in starting XI


@dataclass
class Team:
    id: int
    name: str
    short_name: str
    code: str  # 3-letter abbreviation
    logo_url: str
    country: str
    color: str = ""  # Primary hex color (e.g. "C60000")
    alternate_color: str = ""  # Secondary hex color


@dataclass
class TeamRoster:
    team: Team
    players: List[Player]
    player_stats: Dict[int, PlayerStats]  # player_id -> stats
    loading: bool = False  # True while squad is still being fetched
    error: str = ""  # Non-empty if squad fetch failed (e.g. rate limit)


@dataclass
class LeagueData:
    league: League
    teams: List[TeamRoster]
