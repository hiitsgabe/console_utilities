"""API-Football client with local JSON caching."""

import os
import json
import requests
from typing import Optional, List

from .models import League, Team, Player, PlayerStats


class ApiFootballClient:
    """Client for API-Football with local JSON caching."""

    BASE_URL = "https://v3.football.api-sports.io"

    # Featured leagues shown immediately without an API call
    FEATURED_LEAGUES = [
        {"id": 2,   "name": "UEFA Champions League", "country": "World",         "season": 2024},
        {"id": 13,  "name": "Copa Libertadores",      "country": "South America", "season": 2024},
        {"id": 71,  "name": "Brasileirao Serie A",    "country": "Brazil",        "season": 2024},
        {"id": 253, "name": "MLS",                    "country": "USA",           "season": 2024},
    ]

    def __init__(self, api_key: str, cache_dir: str):
        self.api_key = api_key
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def get_featured_leagues(self) -> List[League]:
        """Return hardcoded featured leagues — no API request needed."""
        return [
            League(
                id=item["id"],
                name=item["name"],
                country=item["country"],
                country_code="",
                logo_url="",
                season=item["season"],
                teams_count=0,
            )
            for item in self.FEATURED_LEAGUES
        ]

    def get_leagues(self, country: str = None, season: int = None) -> List[League]:
        """Fetch available leagues, optionally filtered by country/season."""
        params = {}
        if country:
            params["country"] = country
        if season:
            params["season"] = season
        cache_key = f"leagues_{country or 'all'}_{season or 'all'}"
        cached = self._load_cache(cache_key)
        data = cached or self._request("/leagues", params)
        if not cached and data:
            self._save_cache(cache_key, data)
        return self._parse_leagues(data, season)

    def get_teams(self, league_id: int, season: int) -> List[Team]:
        """Fetch all teams in a league for a given season."""
        params = {"league": league_id, "season": season}
        cache_key = f"teams_{league_id}_{season}"
        cached = self._load_cache(cache_key)
        data = cached or self._request("/teams", params)
        if not cached and data:
            self._save_cache(cache_key, data)
        return self._parse_teams(data)

    def get_squad(self, team_id: int) -> List[Player]:
        """Fetch current squad/roster for a team."""
        params = {"team": team_id}
        cache_key = f"squad_{team_id}"
        cached = self._load_cache(cache_key)
        data = cached or self._request("/players/squads", params)
        if not cached and data:
            self._save_cache(cache_key, data)
        return self._parse_squad(data)

    def get_player_stats(self, team_id: int, season: int) -> List[PlayerStats]:
        """Fetch detailed player statistics for a team in a season."""
        params = {"team": team_id, "season": season}
        cache_key = f"players_{team_id}_{season}"
        cached = self._load_cache(cache_key)
        data = cached or self._request("/players", params)
        if not cached and data:
            self._save_cache(cache_key, data)
        return self._parse_player_stats(data)

    def get_team_logo_url(self, team_id: int) -> str:
        """Get team logo image URL from API."""
        return f"https://media.api-sports.io/football/teams/{team_id}.png"

    def _request(self, endpoint: str, params: dict) -> dict:
        """Make authenticated request with rate limiting."""
        try:
            response = requests.get(
                self.BASE_URL + endpoint,
                params=params,
                headers={"x-apisports-key": self.api_key},
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except Exception:
            return {}

    def _load_cache(self, cache_key: str) -> Optional[dict]:
        """Load cached API response if available."""
        path = os.path.join(self.cache_dir, f"{cache_key}.json")
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
        return None

    def _save_cache(self, cache_key: str, data: dict):
        """Save API response to local cache."""
        path = os.path.join(self.cache_dir, f"{cache_key}.json")
        with open(path, "w") as f:
            json.dump(data, f)

    def _parse_leagues(self, data: dict, season: int = None) -> List[League]:
        """Parse API response into League objects."""
        leagues = []
        for item in data.get("response", []):
            league_info = item.get("league", {})
            country_info = item.get("country", {})
            seasons = item.get("seasons", [])
            # Determine teams count from the season data if available
            teams_count = 0
            used_season = season or 0
            for s in seasons:
                if season and s.get("year") == season:
                    teams_count = (
                        s.get("statistics", {}).get("teams", 0)
                        if isinstance(s.get("statistics"), dict)
                        else 0
                    )
                    used_season = season
                    break
            if not used_season and seasons:
                used_season = seasons[-1].get("year", 0)
            leagues.append(
                League(
                    id=league_info.get("id", 0),
                    name=league_info.get("name", ""),
                    country=country_info.get("name", ""),
                    country_code=country_info.get("code", ""),
                    logo_url=league_info.get("logo", ""),
                    season=used_season,
                    teams_count=teams_count,
                )
            )
        return leagues

    def _parse_teams(self, data: dict) -> List[Team]:
        """Parse API response into Team objects."""
        teams = []
        for item in data.get("response", []):
            team_info = item.get("team", {})
            venue_info = item.get("venue", {})
            teams.append(
                Team(
                    id=team_info.get("id", 0),
                    name=team_info.get("name", ""),
                    short_name=team_info.get("name", "")[:12],
                    code=team_info.get("code", "")[:3] if team_info.get("code") else "",
                    logo_url=team_info.get("logo", ""),
                    country=venue_info.get("city", ""),
                )
            )
        return teams

    def _parse_squad(self, data: dict) -> List[Player]:
        """Parse squad API response into Player objects."""
        players = []
        for item in data.get("response", []):
            for p in item.get("players", []):
                pos = p.get("position", "Midfielder")
                # Normalize position names
                if pos == "Goalkeeper":
                    position = "Goalkeeper"
                elif pos == "Defender":
                    position = "Defender"
                elif pos == "Midfielder":
                    position = "Midfielder"
                else:
                    position = "Attacker"
                players.append(
                    Player(
                        id=p.get("id", 0),
                        name=p.get("name", ""),
                        first_name=p.get("firstname", "") or "",
                        last_name=p.get("lastname", "") or "",
                        age=p.get("age", 25),
                        nationality=p.get("nationality", ""),
                        position=position,
                        number=p.get("number"),
                        photo_url=p.get("photo", ""),
                    )
                )
        return players

    def _parse_player_stats(self, data: dict) -> List[PlayerStats]:
        """Parse player stats API response into PlayerStats objects."""
        stats_list = []
        for item in data.get("response", []):
            player_info = item.get("player", {})
            statistics = item.get("statistics", [])
            if not statistics:
                continue
            # Use the first statistics entry (primary league)
            s = statistics[0]
            games = s.get("games", {})
            shots = s.get("shots", {})
            goals_data = s.get("goals", {})
            passes = s.get("passes", {})
            tackles = s.get("tackles", {})
            duels = s.get("duels", {})
            dribbles = s.get("dribbles", {})
            fouls = s.get("fouls", {})
            cards = s.get("cards", {})
            stats_list.append(
                PlayerStats(
                    player_id=player_info.get("id", 0),
                    appearances=games.get("appearences", 0) or 0,
                    minutes=games.get("minutes", 0) or 0,
                    goals=goals_data.get("total", 0) or 0,
                    assists=goals_data.get("assists", 0) or 0,
                    shots_total=shots.get("total", 0) or 0,
                    shots_on=shots.get("on", 0) or 0,
                    passes_total=passes.get("total", 0) or 0,
                    passes_accuracy=float(passes.get("accuracy", 0) or 0),
                    tackles_total=tackles.get("total", 0) or 0,
                    interceptions=tackles.get("interceptions", 0) or 0,
                    blocks=tackles.get("blocks", 0) or 0,
                    duels_total=duels.get("total", 0) or 0,
                    duels_won=duels.get("won", 0) or 0,
                    dribbles_attempts=dribbles.get("attempts", 0) or 0,
                    dribbles_success=dribbles.get("success", 0) or 0,
                    fouls_committed=fouls.get("committed", 0) or 0,
                    fouls_drawn=fouls.get("drawn", 0) or 0,
                    cards_yellow=cards.get("yellow", 0) or 0,
                    cards_red=cards.get("red", 0) or 0,
                    rating=float(games.get("rating", 0) or 0) or None,
                )
            )
        return stats_list
