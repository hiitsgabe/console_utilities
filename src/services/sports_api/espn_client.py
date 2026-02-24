"""ESPN public API client for soccer roster data — no API key required."""

import os
import json
import requests
from typing import Optional, List

from services.sports_api.models import League, Team, Player, PlayerStats


# Maps our internal league IDs to ESPN league codes.
# IDs start at 2000 to avoid clashing with API-Football IDs.
ESPN_LEAGUES = [
    {"id": 2001, "code": "eng.1",               "name": "Premier League",        "country": "England"},
    {"id": 2002, "code": "esp.1",               "name": "La Liga",               "country": "Spain"},
    {"id": 2003, "code": "ger.1",               "name": "Bundesliga",            "country": "Germany"},
    {"id": 2004, "code": "ita.1",               "name": "Serie A",               "country": "Italy"},
    {"id": 2005, "code": "fra.1",               "name": "Ligue 1",               "country": "France"},
    {"id": 2006, "code": "bra.1",               "name": "Brasileirao Serie A",   "country": "Brazil"},
    {"id": 2007, "code": "usa.1",               "name": "MLS",                   "country": "USA"},
    {"id": 2008, "code": "UEFA.CHAMPIONS",      "name": "UEFA Champions League", "country": "World"},
    {"id": 2009, "code": "conmebol.libertadores","name": "Copa Libertadores",     "country": "South America"},
    {"id": 2010, "code": "arg.1",               "name": "Liga Profesional",      "country": "Argentina"},
    {"id": 2011, "code": "mex.1",               "name": "Liga BBVA MX",          "country": "Mexico"},
    {"id": 2012, "code": "por.1",               "name": "Primeira Liga",         "country": "Portugal"},
    {"id": 2013, "code": "ned.1",               "name": "Eredivisie",            "country": "Netherlands"},
    {"id": 2014, "code": "jpn.1",               "name": "J.League",              "country": "Japan"},
    {"id": 2015, "code": "col.1",               "name": "Primera A",             "country": "Colombia"},
    {"id": 2016, "code": "chi.1",               "name": "Primera División",      "country": "Chile"},
]

_ID_TO_LEAGUE = {item["id"]: item for item in ESPN_LEAGUES}
_CODE_TO_LEAGUE = {item["code"]: item for item in ESPN_LEAGUES}

BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer"


class EspnClient:
    """Client for ESPN's public soccer API — no key, no rate limits."""

    def __init__(self, cache_dir: str, on_status=None):
        self.cache_dir = cache_dir
        self.on_status = on_status
        os.makedirs(cache_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Public interface (mirrors ApiFootballClient)
    # ------------------------------------------------------------------

    def get_featured_leagues(self) -> List[League]:
        """Return featured leagues from the ESPN league list."""
        featured_ids = [2008, 2009, 2006, 2007]  # CL, Libertadores, Brasileirao, MLS
        result = []
        for league_id in featured_ids:
            item = _ID_TO_LEAGUE.get(league_id)
            if item:
                result.append(self._league_from_item(item))
        return result

    def get_leagues(self, country: str = None, season: int = None, id: int = None) -> List[League]:
        """Return ESPN leagues, optionally filtered by id."""
        if id is not None:
            item = _ID_TO_LEAGUE.get(id)
            return [self._league_from_item(item)] if item else []
        leagues = [self._league_from_item(item) for item in ESPN_LEAGUES]
        if country:
            leagues = [l for l in leagues if l.country.lower() == country.lower()]
        return leagues

    def get_teams(self, league_id: int, season: int = None) -> List[Team]:
        """Fetch all teams in a league."""
        item = _ID_TO_LEAGUE.get(league_id)
        if not item:
            return []
        code = item["code"]
        cache_key = f"espn_teams_{league_id}"
        cached = self._load_cache(cache_key)
        if cached:
            return self._parse_teams(cached)
        data = self._request(f"/{code}/teams")
        if data:
            self._save_cache(cache_key, data)
        return self._parse_teams(data)

    def get_squad(self, team_id: int, league_code: str = None) -> List[Player]:
        """Fetch current squad for a team."""
        cache_key = f"espn_squad_{team_id}"
        cached = self._load_cache(cache_key)
        if cached:
            return self._parse_squad(cached)
        # ESPN roster endpoint requires the league code; find it via team detail if unknown
        code = league_code or self._find_league_code_for_team(team_id)
        if not code:
            return []
        data = self._request(f"/{code}/teams/{team_id}/roster")
        if data:
            self._save_cache(cache_key, data)
        return self._parse_squad(data)

    def get_player_stats(self, team_id: int, season: int) -> List[PlayerStats]:
        """ESPN doesn't provide historical stats — return empty list."""
        return []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _league_from_item(self, item: dict) -> League:
        from datetime import datetime
        return League(
            id=item["id"],
            name=item["name"],
            country=item["country"],
            country_code="",
            logo_url="",
            season=datetime.now().year,
            teams_count=0,
        )

    def _request(self, path: str) -> dict:
        try:
            if self.on_status:
                self.on_status(f"Fetching{path}...")
            response = requests.get(BASE_URL + path, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception:
            return {}

    def _load_cache(self, cache_key: str) -> Optional[dict]:
        path = os.path.join(self.cache_dir, f"{cache_key}.json")
        if os.path.exists(path):
            try:
                with open(path) as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
        return None

    def _save_cache(self, cache_key: str, data: dict):
        path = os.path.join(self.cache_dir, f"{cache_key}.json")
        with open(path, "w") as f:
            json.dump(data, f)

    def _find_league_code_for_team(self, team_id: int) -> Optional[str]:
        """Find which league a team belongs to by checking cached team lists."""
        for item in ESPN_LEAGUES:
            cache_key = f"espn_teams_{item['id']}"
            cached = self._load_cache(cache_key)
            if cached:
                teams = self._parse_teams(cached)
                if any(t.id == team_id for t in teams):
                    return item["code"]
        return None

    def _parse_teams(self, data: dict) -> List[Team]:
        if not isinstance(data, dict):
            return []
        teams_raw = (
            data.get("sports", [{}])[0]
            .get("leagues", [{}])[0]
            .get("teams", [])
        )
        teams = []
        for entry in teams_raw:
            t = entry.get("team", {})
            teams.append(Team(
                id=int(t.get("id", 0)),
                name=t.get("displayName", t.get("name", "")),
                short_name=t.get("shortDisplayName", t.get("name", ""))[:12],
                code=(t.get("abbreviation", "") or "")[:3],
                logo_url=t.get("logos", [{}])[0].get("href", "") if t.get("logos") else "",
                country="",
                color=t.get("color", ""),
                alternate_color=t.get("alternateColor", ""),
            ))
        return teams

    def _parse_squad(self, data: dict) -> List[Player]:
        if not isinstance(data, dict):
            return []
        players = []
        for athlete in data.get("athletes", []):
            pos_info = athlete.get("position", {})
            pos_name = pos_info.get("name", "Midfielder") if isinstance(pos_info, dict) else "Midfielder"
            if "Goalkeeper" in pos_name:
                position = "Goalkeeper"
            elif "Defender" in pos_name or "Back" in pos_name:
                position = "Defender"
            elif "Forward" in pos_name or "Striker" in pos_name or "Winger" in pos_name:
                position = "Attacker"
            else:
                position = "Midfielder"

            jersey = athlete.get("jersey")
            number = int(jersey) if jersey and str(jersey).isdigit() else None

            display_name = athlete.get("displayName", athlete.get("fullName", ""))
            first_name = athlete.get("firstName", "")
            last_name = athlete.get("lastName", "")

            # ESPN often leaves lastName empty for mononym players (Hulk,
            # Paulinho) and compound-name players (Carlos Miguel, Felipe
            # Anderson).  Split displayName so last_name gets the surname
            # and first_name gets the given name.
            if not last_name and display_name:
                parts = display_name.split()
                if len(parts) == 1:
                    last_name = parts[0]
                    first_name = ""
                else:
                    last_name = parts[-1]
                    first_name = " ".join(parts[:-1])

            players.append(Player(
                id=int(athlete.get("id", 0)),
                name=display_name,
                first_name=first_name,
                last_name=last_name,
                age=athlete.get("age", 25) or 25,
                nationality=athlete.get("citizenship", ""),
                position=position,
                number=number,
                photo_url="",
            ))
        return players
