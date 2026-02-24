"""Maps real-world player stats to ISS's attribute scales.

ISS has a simpler attribute system than WE2002:
- Speed: 1-16 (stored as complex byte encoding)
- Shooting: 1-15 (odd values only, 3-bit encoding)
- Stamina: 1-16 (stored as nibble + 1)
- Technique: 1-15 (odd values only, 3-bit encoding)

Players are mapped from ESPN/API-Football data using percentile ranking.
"""

from typing import List, Dict, Optional

from .models import (
    ISSPlayerAttributes,
    ISSPlayerRecord,
    ISSTeamRecord,
    PLAYERS_PER_TEAM,
)
from services.sports_api.models import (
    Player,
    PlayerStats,
    TeamRoster,
)
from .rom_writer import _to_ascii


class ISSStatMapper:
    """Maps real-world player stats to ISS attribute scales."""

    # Map percentile → ISS shooting/technique (odd 1-15 scale)
    SHOOTING_TABLE = [
        (95, 15),
        (85, 13),
        (70, 11),
        (50, 9),
        (35, 7),
        (20, 5),
        (10, 3),
        (0, 1),
    ]

    # Map percentile → ISS speed/stamina (1-16 scale)
    SPEED_TABLE = [
        (95, 16),
        (88, 14),
        (75, 12),
        (60, 10),
        (45, 8),
        (30, 6),
        (15, 4),
        (5, 2),
        (0, 1),
    ]

    FALLBACK_ATTRS = {
        "Goalkeeper": dict(speed=6, shooting=3, stamina=8, technique=5),
        "Defender": dict(speed=8, shooting=5, stamina=9, technique=5),
        "Midfielder": dict(speed=8, shooting=7, stamina=10, technique=9),
        "Attacker": dict(speed=10, shooting=11, stamina=7, technique=9),
    }

    POSITION_CODES = {
        "Goalkeeper": 0,
        "Defender": 1,
        "Midfielder": 2,
        "Attacker": 3,
    }

    HAIR_BY_POSITION = {
        "Goalkeeper": 0,   # Short
        "Defender": 0,     # Short
        "Midfielder": 9,   # Mid length
        "Attacker": 4,     # Long straight
    }

    def map_team_with_league_context(
        self,
        team_roster: TeamRoster,
        all_rosters: List[TeamRoster],
    ) -> ISSTeamRecord:
        """Map team using league-wide percentile normalization."""
        all_stats = {}
        for roster in all_rosters:
            for pid, ps in roster.player_stats.items():
                all_stats[pid] = ps

        percentiles = self._compute_percentiles(all_stats)

        # Select best 15 players
        best_15 = self._select_best_15(
            team_roster.players, team_roster.player_stats
        )

        iss_players = []
        for player in best_15:
            stats = team_roster.player_stats.get(player.id)
            attrs = self.map_player(player, stats, percentiles)
            rom_name = self._format_player_name(player)
            hair = self.HAIR_BY_POSITION.get(player.position, 0)
            iss_players.append(
                ISSPlayerRecord(
                    name=rom_name,
                    shirt_number=player.number or 1,
                    position=self.POSITION_CODES.get(player.position, 2),
                    hair_style=hair,
                    is_special=self._is_star_player(player, stats),
                    attributes=attrs,
                )
            )

        return ISSTeamRecord(
            name=self._truncate_name(team_roster.team.name, 12),
            short_name=_to_ascii(
                team_roster.team.code[:3]
                if team_roster.team.code
                else team_roster.team.name[:3].upper()
            ),
            players=iss_players,
        )

    def map_player(
        self,
        player: Player,
        stats: Optional[PlayerStats],
        percentiles: Dict[str, Dict[int, float]],
    ) -> ISSPlayerAttributes:
        """Convert a real player's stats to ISS format."""
        if not stats or stats.appearances == 0:
            return self._fallback_attributes(player)

        pid = stats.player_id
        return ISSPlayerAttributes(
            speed=self._percentile_to_speed(
                percentiles.get("speed", {}).get(pid, 50)
            ),
            shooting=self._percentile_to_shooting(
                percentiles.get("shooting", {}).get(pid, 50)
            ),
            stamina=self._percentile_to_speed(
                percentiles.get("stamina", {}).get(pid, 50)
            ),
            technique=self._percentile_to_shooting(
                percentiles.get("technique", {}).get(pid, 50)
            ),
        )

    def _compute_percentiles(
        self, all_stats: Dict[int, PlayerStats]
    ) -> Dict[str, Dict[int, float]]:
        """Compute league-wide percentiles for each stat category."""
        if not all_stats:
            return {}

        categories = {
            "speed": lambda s: s.minutes / max(s.appearances, 1),  # Proxy: endurance
            "shooting": lambda s: s.goals + s.shots_on * 0.3 if s.shots_on else s.goals,
            "stamina": lambda s: s.minutes / max(s.appearances, 1),
            "technique": lambda s: (
                (s.dribbles_success / max(s.dribbles_attempts, 1)) * 100
                + s.passes_accuracy
            ) / 2,
        }

        percentiles = {}
        for cat_name, extract_fn in categories.items():
            raw_values = {}
            for pid, stats in all_stats.items():
                raw_values[pid] = extract_fn(stats)

            sorted_values = sorted(raw_values.values())
            n = len(sorted_values)
            if n == 0:
                percentiles[cat_name] = {}
                continue

            cat_percentiles = {}
            for pid, value in raw_values.items():
                below = sum(1 for v in sorted_values if v < value)
                cat_percentiles[pid] = (below / n) * 100
            percentiles[cat_name] = cat_percentiles

        return percentiles

    def _percentile_to_shooting(self, percentile: float) -> int:
        """Map percentile to ISS shooting/technique scale (odd 1-15)."""
        for threshold, rating in self.SHOOTING_TABLE:
            if percentile >= threshold:
                return rating
        return 1

    def _percentile_to_speed(self, percentile: float) -> int:
        """Map percentile to ISS speed/stamina scale (1-16)."""
        for threshold, rating in self.SPEED_TABLE:
            if percentile >= threshold:
                return rating
        return 1

    def _fallback_attributes(self, player: Player) -> ISSPlayerAttributes:
        """Generate attributes from position when no stats available."""
        defaults = self.FALLBACK_ATTRS.get(
            player.position, self.FALLBACK_ATTRS["Midfielder"]
        )
        attrs = ISSPlayerAttributes(**defaults)

        age = player.age
        if age and age < 23:
            attrs.speed = min(16, attrs.speed + 2)
            attrs.stamina = min(16, attrs.stamina + 1)
        elif age and age > 32:
            attrs.speed = max(1, attrs.speed - 2)
            attrs.stamina = max(1, attrs.stamina - 2)
            attrs.technique = min(15, attrs.technique + 2)

        return attrs

    def _is_star_player(self, player: Player, stats: Optional[PlayerStats]) -> bool:
        """Determine if a player should be marked as 'special' (star player)."""
        if not stats:
            return False
        # Top performers: high goals or assists relative to appearances
        if stats.appearances < 5:
            return False
        goals_per_game = stats.goals / max(stats.appearances, 1)
        assists_per_game = stats.assists / max(stats.appearances, 1)
        return goals_per_game >= 0.5 or assists_per_game >= 0.4

    def _select_best_15(
        self,
        players: List[Player],
        player_stats: Optional[Dict[int, PlayerStats]] = None,
    ) -> List[Player]:
        """Select best 15 players ordered for ISS starting lineup.

        ISS uses the first 11 as starters, last 4 as subs.
        Starting 11 (4-4-2): 1 GK, 4 DF, 4 MF, 2 FW.
        Subs: 1 GK + best remaining (typically 1 MF, 2 FW).
        """
        stats = player_stats or {}

        def _sort_key(p: Player) -> tuple:
            s = stats.get(p.id)
            if s:
                return (-s.lineups, -s.appearances, -s.minutes)
            return (0, 0, 0)

        by_position = {}
        for p in players:
            by_position.setdefault(p.position, []).append(p)
        for pos in by_position:
            by_position[pos].sort(key=_sort_key)

        gks = by_position.get("Goalkeeper", [])
        dfs = by_position.get("Defender", [])
        mfs = by_position.get("Midfielder", [])
        fws = by_position.get("Attacker", [])

        # Starting 11: 1 GK + 4 DF + 4 MF + 2 FW
        starters = []
        starters.extend(gks[:1])          # 1 GK
        starters.extend(dfs[:4])          # 4 DF
        starters.extend(mfs[:4])          # 4 MF
        starters.extend(fws[:2])          # 2 FW

        # Subs: backup GK first, then best remaining outfield
        subs = []
        subs.extend(gks[1:2])             # backup GK

        remaining = (
            dfs[4:] + mfs[4:] + fws[2:]
            + gks[2:]
            + [p for p in players if p.position not in by_position or p not in
               gks + dfs + mfs + fws]
        )
        remaining.sort(key=_sort_key)
        subs.extend(remaining)

        squad = starters + subs

        # Fill any gaps if not enough players in certain positions
        used = set(id(p) for p in squad)
        extras = [p for p in players if id(p) not in used]
        extras.sort(key=_sort_key)
        squad.extend(extras)

        return squad[:PLAYERS_PER_TEAM]

    def _format_player_name(self, player: Player) -> str:
        """Build ROM-friendly 8-char name from a Player.

        ISS names are 8 characters max with ISS custom encoding.
        """
        display = _to_ascii(player.name) if player.name else ""
        if not display:
            last = _to_ascii(player.last_name) if player.last_name else ""
            return (last or "PLAYER")[:8]

        words = display.split()
        if len(words) == 1:
            return display[:8]

        # Use surname, capitalize
        surname = words[-1]
        return surname[:8]

    def _truncate_name(self, name: str, max_len: int) -> str:
        """Smart truncation for team names."""
        if not name:
            return ""
        ascii_name = _to_ascii(name)
        if len(ascii_name) <= max_len:
            return ascii_name
        return ascii_name[:max_len]
