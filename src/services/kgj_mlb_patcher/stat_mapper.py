"""Stat mapping for KGJ MLB patcher.

Maps MLB player stats from ESPN API to KGJ's 1-10 attribute scale.
Uses real season stats (AVG, HR, RBI, SB, ERA, W, SV, etc.) when available,
with position-based defaults as fallback.
"""

from typing import Optional, List, Dict

from services.sports_api.models import Player
from services.kgj_mlb_patcher.models import (
    KGJPlayerRecord,
    KGJBatterAttributes,
    KGJPitcherAttributes,
    KGJBatterAppearance,
    KGJPitcherAppearance,
    MODERN_MLB_TO_KGJ,
    HAND_RIGHT,
    HAND_LEFT,
    HAND_SWITCH,
    BATTERS_PER_TEAM,
    STARTERS_PER_TEAM,
    RELIEVERS_PER_TEAM,
)


def _clamp(val: int, lo: int = 1, hi: int = 10) -> int:
    return max(lo, min(hi, val))


def _scale(value: float, low: float, high: float) -> int:
    """Map a value within [low, high] to 1-10 scale."""
    if high <= low:
        return 5
    ratio = (value - low) / (high - low)
    return _clamp(round(ratio * 9) + 1)


# Default batter attributes by position
BATTER_DEFAULTS = {
    "C": KGJBatterAttributes(batting=5, power=5, speed=3, defense=7),
    "1B": KGJBatterAttributes(batting=6, power=7, speed=3, defense=5),
    "2B": KGJBatterAttributes(batting=5, power=3, speed=6, defense=7),
    "3B": KGJBatterAttributes(batting=5, power=5, speed=4, defense=6),
    "SS": KGJBatterAttributes(batting=5, power=3, speed=6, defense=8),
    "LF": KGJBatterAttributes(batting=6, power=5, speed=6, defense=5),
    "CF": KGJBatterAttributes(batting=5, power=4, speed=8, defense=7),
    "RF": KGJBatterAttributes(batting=6, power=6, speed=5, defense=6),
    "DH": KGJBatterAttributes(batting=7, power=7, speed=3, defense=2),
    "IF": KGJBatterAttributes(batting=4, power=3, speed=5, defense=6),
    "OF": KGJBatterAttributes(batting=5, power=4, speed=6, defense=5),
}

PITCHER_DEFAULTS = {
    "SP": KGJPitcherAttributes(speed=6, control=6, fatigue=7),
    "RP": KGJPitcherAttributes(speed=6, control=5, fatigue=3),
    "CL": KGJPitcherAttributes(speed=7, control=6, fatigue=3),
}


class KGJStatMapper:
    """Maps MLB API player data to KGJ ROM attributes."""

    def map_batter(
        self,
        player: Player,
        stats: Optional[Dict] = None,
    ) -> KGJPlayerRecord:
        """Map an MLB batter to a KGJ player record."""
        pos = self._normalize_position(player.position, is_pitcher=False)
        hand = self._map_bat_hand(player.bats or player.handedness)

        if stats:
            attrs = self._map_batter_stats(stats, pos)
            avg = int(float(stats.get("AVG", 0.250) or 0.250) * 1000)
            hr = int(float(stats.get("HR", 0) or 0))
            rbi = int(float(stats.get("RBI", 0) or 0))
        else:
            attrs = BATTER_DEFAULTS.get(pos, BATTER_DEFAULTS["CF"])
            avg = 250
            hr = 0
            rbi = 0

        first, last = self._split_name(player.name)

        return KGJPlayerRecord(
            first_initial=first,
            last_name=last,
            position=pos,
            jersey_number=player.number or 0,
            is_pitcher=False,
            bat_hand=hand,
            batter_attrs=attrs,
            batter_appearance=self._default_batter_appearance(),
            batting_avg=avg,
            home_runs=hr,
            rbi=rbi,
        )

    def map_pitcher(
        self,
        player: Player,
        stats: Optional[Dict] = None,
        is_starter: bool = True,
    ) -> KGJPlayerRecord:
        """Map an MLB pitcher to a KGJ player record."""
        hand = self._map_bat_hand(player.bats or player.handedness)
        pitch_hand = 1 if player.handedness == "L" else 0

        if stats:
            attrs = self._map_pitcher_stats(stats, is_starter)
            wins = int(float(stats.get("W", 0) or 0))
            losses = int(float(stats.get("L", 0) or 0))
            era_val = float(stats.get("ERA", 4.00) or 4.00)
            era = int(era_val * 100)
            saves = int(float(stats.get("SV", 0) or 0))
        else:
            default_key = "SP" if is_starter else "RP"
            attrs = PITCHER_DEFAULTS[default_key]
            wins = 0
            losses = 0
            era = 400
            saves = 0

        first, last = self._split_name(player.name)

        return KGJPlayerRecord(
            first_initial=first,
            last_name=last,
            position="P",
            jersey_number=player.number or 0,
            is_pitcher=True,
            bat_hand=hand,
            pitcher_attrs=attrs,
            pitcher_appearance=self._default_pitcher_appearance(),
            pitch_hand=pitch_hand,
            wins=wins,
            losses=losses,
            era=era,
            saves=saves,
        )

    def _map_batter_stats(
        self, stats: Dict, pos: str
    ) -> KGJBatterAttributes:
        """Map real batting stats to 1-10 ratings.

        Stat ranges for scaling (per-season):
          AVG: .200-.330, HR: 0-45, RBI: 0-130, SB: 0-50
          OPS: .600-1.000, H: 0-200
        """
        avg = float(stats.get("AVG", 0.250) or 0.250)
        hr = float(stats.get("HR", 0) or 0)
        rbi = float(stats.get("RBI", 0) or 0)
        sb = float(stats.get("SB", 0) or 0)
        ops = float(stats.get("OPS", 0.700) or 0.700)
        hits = float(stats.get("H", 0) or 0)

        # BAT: based on batting average and OPS
        bat = _scale((avg * 0.6 + ops * 0.4 / 3), 0.200, 0.330)

        # POW: based on home runs and slugging
        slg = float(stats.get("SLG", 0.400) or 0.400)
        pow_r = _scale((hr / 45 * 0.7 + slg * 0.3), 0.0, 1.0)

        # SPD: based on stolen bases
        spd = _scale(sb, 0, 40)
        # Boost if many triples
        triples = float(stats.get("3B", 0) or 0)
        if triples >= 5:
            spd = _clamp(spd + 1)

        # DEF: use position default + small adjustment for experience
        base_def = BATTER_DEFAULTS.get(pos, BATTER_DEFAULTS["CF"]).defense
        games = float(stats.get("GP", 0) or 0)
        def_bonus = 1 if games > 120 else 0
        def_r = _clamp(base_def + def_bonus)

        return KGJBatterAttributes(
            batting=bat, power=pow_r, speed=spd, defense=def_r,
        )

    def _map_pitcher_stats(
        self, stats: Dict, is_starter: bool
    ) -> KGJPitcherAttributes:
        """Map real pitching stats to 1-10 ratings.

        ESPN leaders provides: ERA, W, K, SV, WHIP, QS, OBA, HLD.
        Does NOT provide K/9, BB/9, IP, GS.
        """
        era = float(stats.get("ERA", 4.00) or 4.00)
        k = float(stats.get("K", 0) or 0)
        whip = float(stats.get("WHIP", 1.30) or 1.30)
        w = float(stats.get("W", 0) or 0)
        qs = float(stats.get("QS", 0) or 0)

        # SPD: strikeout total as proxy for velocity/dominance
        if is_starter:
            spd = _scale(k, 60, 250)
        else:
            spd = _scale(k, 20, 90)

        # CON: based on WHIP (lower = better control) and ERA
        con_from_whip = _scale(1.60 - whip, 0.0, 0.70)
        con_from_era = _scale(6.0 - era, 0.0, 4.0)
        con = _clamp((con_from_whip + con_from_era) // 2)

        # FAT: based on quality starts (starters) or wins+saves (relievers)
        if is_starter:
            fat = _scale(qs, 5, 25)
            # Boost for high-win starters
            if w >= 15:
                fat = _clamp(fat + 1)
        else:
            # Relievers have low fatigue
            sv = float(stats.get("SV", 0) or 0)
            fat = _clamp(3 + (1 if sv > 20 else 0))

        return KGJPitcherAttributes(speed=spd, control=con, fatigue=fat)

    def select_roster(
        self,
        players: List[Player],
        stats: Optional[Dict] = None,
    ) -> List[Player]:
        """Build KGJ roster with proper slot ordering.

        Returns 25 players ordered:
          [0-14]  = batters (C, 1B, 2B, 3B, SS, LF, CF, RF, DH + bench)
          [15-19] = starting pitchers (sorted by wins)
          [20-24] = relief pitchers (closer first, then setup)
        """
        stats = stats or {}

        pitchers = [p for p in players if self._is_pitcher(p)]
        batters = [p for p in players if not self._is_pitcher(p)]

        # Sort batters by OPS or hits
        def batter_sort(p: Player) -> float:
            ps = stats.get(str(p.id), {})
            ops = float(ps.get("OPS", 0) or 0)
            hits = float(ps.get("H", 0) or 0)
            return ops * 1000 + hits

        # Sort pitchers
        def starter_sort(p: Player) -> float:
            ps = stats.get(str(p.id), {})
            w = float(ps.get("W", 0) or 0)
            ip = float(ps.get("IP", 0) or 0)
            return w * 100 + ip

        def reliever_sort(p: Player) -> float:
            ps = stats.get(str(p.id), {})
            sv = float(ps.get("SV", 0) or 0)
            era = float(ps.get("ERA", 9.0) or 9.0)
            return sv * 100 + (10 - era)

        # Separate starters from relievers using position abbreviation
        # ESPN roster gives SP vs RP; stats (GS/IP) aren't in leaders endpoint
        starters = []
        relievers = []
        for p in pitchers:
            pos = (p.position or "").upper()
            if pos == "SP":
                starters.append(p)
            else:
                relievers.append(p)

        starters.sort(key=starter_sort, reverse=True)
        relievers.sort(key=reliever_sort, reverse=True)

        # Take top 5 starters, 5 relievers
        selected_starters = starters[:STARTERS_PER_TEAM]
        selected_relievers = relievers[:RELIEVERS_PER_TEAM]

        # Fill if we don't have enough
        remaining_pitchers = [
            p for p in starters[STARTERS_PER_TEAM:] + relievers[RELIEVERS_PER_TEAM:]
        ]
        while len(selected_starters) < STARTERS_PER_TEAM and remaining_pitchers:
            selected_starters.append(remaining_pitchers.pop(0))
        while len(selected_relievers) < RELIEVERS_PER_TEAM and remaining_pitchers:
            selected_relievers.append(remaining_pitchers.pop(0))

        # Select batters by position
        batters.sort(key=batter_sort, reverse=True)
        selected_batters = self._select_position_players(batters)

        return selected_batters + selected_starters + selected_relievers

    def _select_position_players(
        self, batters: List[Player]
    ) -> List[Player]:
        """Select 15 batters filling required positions.

        Order: C, 1B, 2B, 3B, SS, LF, CF, RF, DH, then bench.
        """
        by_pos: Dict[str, List[Player]] = {}
        for p in batters:
            pos = self._normalize_position(p.position, is_pitcher=False)
            by_pos.setdefault(pos, []).append(p)

        lineup_order = ["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "DH"]
        selected = []
        used = set()

        # Fill each position with the best available
        for pos in lineup_order:
            candidates = by_pos.get(pos, [])
            for c in candidates:
                if id(c) not in used:
                    selected.append(c)
                    used.add(id(c))
                    break
            else:
                # No player at this position — will fill from bench later
                pass

        # Fill remaining slots with best unused batters
        for p in batters:
            if len(selected) >= BATTERS_PER_TEAM:
                break
            if id(p) not in used:
                selected.append(p)
                used.add(id(p))

        return selected[:BATTERS_PER_TEAM]

    def _is_pitcher(self, player: Player) -> bool:
        """Check if a player is a pitcher."""
        pos = (player.position or "").upper()
        return pos in ("P", "SP", "RP", "CL", "CP")

    def _normalize_position(self, position: str, is_pitcher: bool) -> str:
        """Normalize ESPN position strings to KGJ positions."""
        pos = (position or "").upper()
        if is_pitcher:
            return "P"

        pos_map = {
            "C": "C", "1B": "1B", "2B": "2B", "3B": "3B", "SS": "SS",
            "LF": "LF", "CF": "CF", "RF": "RF", "DH": "DH",
            "OF": "OF", "IF": "IF",
            # ESPN sometimes uses these
            "SP": "P", "RP": "P", "CL": "P", "CP": "P", "P": "P",
        }
        return pos_map.get(pos, "OF")

    def _map_bat_hand(self, handedness: Optional[str]) -> int:
        """Map batting handedness string to ROM value."""
        if not handedness:
            return HAND_RIGHT
        h = handedness.upper()
        if h == "L":
            return HAND_LEFT
        if h in ("S", "B"):
            return HAND_SWITCH
        return HAND_RIGHT

    def _split_name(self, full_name: str) -> tuple:
        """Split 'First Last' into (initial, last_name).

        Handles names like 'J.D. Martinez' -> ('J', 'MARTINEZ')
        and 'Ken Griffey Jr.' -> ('K', 'GRIFFEY')
        """
        parts = full_name.strip().split()
        if not parts:
            return "A", "PLAYER"

        first_initial = parts[0][0].upper()

        if len(parts) == 1:
            last = parts[0].upper()[:8]
        else:
            # Use last meaningful part (skip Jr., Sr., III, etc.)
            last_parts = []
            for p in parts[1:]:
                if p.rstrip(".").upper() in ("JR", "SR", "II", "III", "IV"):
                    continue
                last_parts.append(p)
            if last_parts:
                last = last_parts[-1].upper()[:8]
            else:
                last = parts[-1].upper()[:8]

        # Handle Mc/Mac names — use lowercase c
        if last.startswith("MC") and len(last) > 2:
            last = "M" + "c" + last[2:]

        return first_initial, last

    def _default_batter_appearance(self) -> KGJBatterAppearance:
        return KGJBatterAppearance()

    def _default_pitcher_appearance(self) -> KGJPitcherAppearance:
        return KGJPitcherAppearance()

    def get_team_slot(self, team_abbrev: str) -> Optional[int]:
        """Get KGJ ROM slot for a modern MLB team."""
        return MODERN_MLB_TO_KGJ.get(team_abbrev.upper())
