"""Stat mapping for MVP Baseball PSP patcher.

Maps MLB player stats from ESPN API to MVP's 0-99 attribute scale.
Uses real season stats when available, with position-based defaults.
"""

from typing import Optional, List, Dict

from services.sports_api.models import Player
from services.mvp_psp_patcher.models import (
    MVPPlayerRecord,
    MODERN_MLB_TO_MVP,
    MVP_ABBREV_TO_INDEX,
    TEAM_HASHES,
    PLAYERS_PER_TEAM,
    BATTERS_PER_TEAM,
    STARTERS_PER_TEAM,
)


def _clamp(val: int, lo: int = 0, hi: int = 99) -> int:
    return max(lo, min(hi, val))


def _scale(value: float, low: float, high: float) -> int:
    """Map a value within [low, high] to 0-99 scale."""
    if high <= low:
        return 50
    ratio = (value - low) / (high - low)
    return _clamp(round(ratio * 99))


# Default attributes by position
POSITION_DEFAULTS = {
    "C":  {"speed": 35, "fielding": 60, "arm_range": 55, "throw_strength": 65,
            "throw_accuracy": 60, "contact": 55, "power": 50},
    "1B": {"speed": 30, "fielding": 50, "arm_range": 45, "throw_strength": 55,
            "throw_accuracy": 55, "contact": 60, "power": 65},
    "2B": {"speed": 55, "fielding": 65, "arm_range": 60, "throw_strength": 50,
            "throw_accuracy": 65, "contact": 55, "power": 35},
    "3B": {"speed": 40, "fielding": 55, "arm_range": 55, "throw_strength": 70,
            "throw_accuracy": 60, "contact": 55, "power": 55},
    "SS": {"speed": 55, "fielding": 70, "arm_range": 65, "throw_strength": 65,
            "throw_accuracy": 65, "contact": 55, "power": 35},
    "LF": {"speed": 55, "fielding": 50, "arm_range": 50, "throw_strength": 55,
            "throw_accuracy": 55, "contact": 60, "power": 55},
    "CF": {"speed": 65, "fielding": 60, "arm_range": 65, "throw_strength": 60,
            "throw_accuracy": 55, "contact": 55, "power": 45},
    "RF": {"speed": 50, "fielding": 55, "arm_range": 55, "throw_strength": 70,
            "throw_accuracy": 60, "contact": 60, "power": 60},
    "DH": {"speed": 30, "fielding": 30, "arm_range": 30, "throw_strength": 40,
            "throw_accuracy": 40, "contact": 65, "power": 70},
}


class MVPPSPStatMapper:
    """Maps MLB API player data to MVP PSP attributes."""

    def map_batter(
        self,
        player: Player,
        stats: Optional[Dict] = None,
    ) -> MVPPlayerRecord:
        """Map an MLB batter to MVP format."""
        pos = self._normalize_position(player.position, is_pitcher=False)
        defaults = POSITION_DEFAULTS.get(pos, POSITION_DEFAULTS["CF"])

        rec = MVPPlayerRecord(
            first_name=self._get_first_name(player.name),
            last_name=self._get_last_name(player.name),
            jersey=player.number or 0,
            bats=self._map_bat_hand(player.bats or player.handedness),
            throws=self._map_throw_hand(player.handedness),
            primary_position=pos,
            is_pitcher=False,
        )

        if stats:
            rec = self._apply_batter_stats(rec, stats, defaults)
        else:
            rec.speed = defaults["speed"]
            rec.fielding = defaults["fielding"]
            rec.arm_range = defaults["arm_range"]
            rec.throw_strength = defaults["throw_strength"]
            rec.throw_accuracy = defaults["throw_accuracy"]
            rec.contact_rhp = defaults["contact"]
            rec.power_rhp = defaults["power"]
            rec.contact_lhp = defaults["contact"]
            rec.power_lhp = defaults["power"]
            rec.durability = 50
            rec.plate_discipline = 50
            rec.bunting = 40
            rec.baserunning = defaults["speed"]
            rec.stealing = defaults["speed"]

        return rec

    def map_pitcher(
        self,
        player: Player,
        stats: Optional[Dict] = None,
        is_starter: bool = True,
    ) -> MVPPlayerRecord:
        """Map an MLB pitcher to MVP format."""
        rec = MVPPlayerRecord(
            first_name=self._get_first_name(player.name),
            last_name=self._get_last_name(player.name),
            jersey=player.number or 0,
            bats=self._map_bat_hand(player.bats or player.handedness),
            throws=self._map_throw_hand(player.handedness),
            primary_position="SP" if is_starter else "RP",
            is_pitcher=True,
        )

        if stats:
            rec = self._apply_pitcher_stats(rec, stats, is_starter)
        else:
            rec.stamina = 70 if is_starter else 35
            rec.pickoff = 50
            rec.speed = 35
            rec.fielding = 40
            rec.contact_rhp = 25
            rec.power_rhp = 15
            rec.contact_lhp = 25
            rec.power_lhp = 15

        # Default pitch arsenal
        rec.pitches = self._default_pitches(is_starter)

        return rec

    def _apply_batter_stats(
        self, rec: MVPPlayerRecord, stats: Dict, defaults: Dict
    ) -> MVPPlayerRecord:
        """Apply real batting stats to MVP attributes."""
        avg = float(stats.get("AVG", 0.250) or 0.250)
        hr = float(stats.get("HR", 0) or 0)
        rbi = float(stats.get("RBI", 0) or 0)
        sb = float(stats.get("SB", 0) or 0)
        ops = float(stats.get("OPS", 0.700) or 0.700)
        slg = float(stats.get("SLG", 0.400) or 0.400)
        obp = float(stats.get("OBP", 0.320) or 0.320)
        hits = float(stats.get("H", 0) or 0)
        gp = float(stats.get("GP", 0) or 0)

        # Contact: based on AVG and OBP
        contact_base = _scale(avg, 0.200, 0.330)
        obp_bonus = _scale(obp, 0.280, 0.420) // 4
        rec.contact_rhp = _clamp(contact_base + obp_bonus)
        rec.contact_lhp = _clamp(rec.contact_rhp - 5)  # Slightly lower vs same-side

        # Power: based on HR and SLG
        power_from_hr = _scale(hr, 0, 45)
        power_from_slg = _scale(slg, 0.350, 0.600)
        rec.power_rhp = _clamp((power_from_hr * 2 + power_from_slg) // 3)
        rec.power_lhp = _clamp(rec.power_rhp - 5)

        # Switch hitters: equalize splits
        if rec.bats == 2:
            avg_contact = (rec.contact_rhp + rec.contact_lhp) // 2
            rec.contact_rhp = avg_contact
            rec.contact_lhp = avg_contact
            avg_power = (rec.power_rhp + rec.power_lhp) // 2
            rec.power_rhp = avg_power
            rec.power_lhp = avg_power

        # Speed: based on stolen bases
        rec.speed = _scale(sb, 0, 40)
        triples = float(stats.get("3B", 0) or 0)
        if triples >= 5:
            rec.speed = _clamp(rec.speed + 5)

        # Baserunning and stealing tied to speed
        rec.baserunning = _clamp(rec.speed + 5)
        rec.stealing = rec.speed

        # Fielding: position default + games bonus
        rec.fielding = defaults["fielding"]
        if gp > 120:
            rec.fielding = _clamp(rec.fielding + 5)
        rec.arm_range = defaults["arm_range"]
        rec.throw_strength = defaults["throw_strength"]
        rec.throw_accuracy = defaults["throw_accuracy"]

        # Plate discipline: based on OBP relative to AVG (walk rate proxy)
        walk_proxy = obp - avg
        rec.plate_discipline = _scale(walk_proxy, 0.040, 0.120)

        # Durability: based on games played
        rec.durability = _scale(gp, 60, 155)

        # Bunting: modest for most, higher for speedsters
        rec.bunting = 30 if rec.speed < 50 else _clamp(rec.speed - 10)

        # Starpower: based on hits + HR + RBI composite
        composite = hits * 0.3 + hr * 2 + rbi * 0.5
        rec.starpower = _scale(composite, 20, 200)

        return rec

    def _apply_pitcher_stats(
        self, rec: MVPPlayerRecord, stats: Dict, is_starter: bool
    ) -> MVPPlayerRecord:
        """Apply real pitching stats to MVP attributes."""
        era = float(stats.get("ERA", 4.00) or 4.00)
        k = float(stats.get("K", 0) or 0)
        whip = float(stats.get("WHIP", 1.30) or 1.30)
        w = float(stats.get("W", 0) or 0)
        sv = float(stats.get("SV", 0) or 0)
        qs = float(stats.get("QS", 0) or 0)

        # Stamina: starters high, relievers low
        if is_starter:
            rec.stamina = _scale(qs, 5, 25)
            if w >= 15:
                rec.stamina = _clamp(rec.stamina + 5)
            rec.stamina = _clamp(rec.stamina, 40, 99)
        else:
            rec.stamina = _clamp(25 + (5 if sv > 20 else 0))

        # Pickoff: moderate for all
        rec.pickoff = 50

        # Velocity proxy from K total
        if is_starter:
            vel = _scale(k, 60, 250)
        else:
            vel = _scale(k, 20, 90)

        # Control from WHIP and ERA
        con_whip = _scale(1.60 - whip, 0.0, 0.70)
        con_era = _scale(6.0 - era, 0.0, 4.0)
        control = (con_whip + con_era) // 2

        # Store velocity/control into pitches
        rec.pitches = self._default_pitches(is_starter, vel, control)

        # Batting ability for pitchers (minimal)
        rec.contact_rhp = 20
        rec.power_rhp = 10
        rec.contact_lhp = 20
        rec.power_lhp = 10
        rec.speed = 30
        rec.fielding = 40

        # Starpower for pitchers
        if is_starter:
            composite = w * 3 + k * 0.1 + (6.0 - era) * 10
        else:
            composite = sv * 3 + k * 0.1 + (4.0 - era) * 5
        rec.starpower = _scale(composite, 10, 80)

        return rec

    def _default_pitches(
        self, is_starter: bool, velocity: int = 50, control: int = 50
    ) -> List[Dict]:
        """Generate default pitch arsenal.

        Each pitch: {type, movement, control, velocity}
        Types: 1=Fastball, 2=Curve, 3=Slider, 4=Changeup, 5=Sinker, etc.
        """
        pitches = [
            {"type": 1, "movement": velocity // 2, "control": control,
             "velocity": _clamp(velocity + 10)},
        ]
        if is_starter:
            # Starters get 3-4 pitches
            pitches.append(
                {"type": 3, "movement": _clamp(velocity // 2 + 5),
                 "control": _clamp(control - 5),
                 "velocity": _clamp(velocity - 5)}
            )
            pitches.append(
                {"type": 4, "movement": _clamp(velocity // 3),
                 "control": control,
                 "velocity": _clamp(velocity - 15)}
            )
        else:
            # Relievers get 2 pitches
            pitches.append(
                {"type": 3, "movement": _clamp(velocity // 2),
                 "control": _clamp(control - 5),
                 "velocity": _clamp(velocity - 5)}
            )
        return pitches

    def select_roster(
        self, players: List[Player], stats: Optional[Dict] = None
    ) -> List[Player]:
        """Build MVP roster with proper slot ordering.

        Returns 25 players ordered:
          [0-14]  = batters (C, 1B, 2B, 3B, SS, LF, CF, RF, DH + bench)
          [15-19] = starting pitchers
          [20-24] = relief pitchers (closer first, then setup)
        """
        stats = stats or {}

        pitchers = [p for p in players if self._is_pitcher(p)]
        batters = [p for p in players if not self._is_pitcher(p)]

        def batter_sort(p: Player) -> float:
            ps = stats.get(str(p.id), {})
            ops = float(ps.get("OPS", 0) or 0)
            hits = float(ps.get("H", 0) or 0)
            return ops * 1000 + hits

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

        starters = [p for p in pitchers if (p.position or "").upper() == "SP"]
        relievers = [p for p in pitchers if (p.position or "").upper() != "SP"]

        starters.sort(key=starter_sort, reverse=True)
        relievers.sort(key=reliever_sort, reverse=True)

        selected_starters = starters[:STARTERS_PER_TEAM]
        selected_relievers = relievers[:5]

        remaining = starters[STARTERS_PER_TEAM:] + relievers[5:]
        while len(selected_starters) < STARTERS_PER_TEAM and remaining:
            selected_starters.append(remaining.pop(0))
        while len(selected_relievers) < 5 and remaining:
            selected_relievers.append(remaining.pop(0))

        batters.sort(key=batter_sort, reverse=True)
        selected_batters = self._select_position_players(batters)

        return selected_batters + selected_starters + selected_relievers

    def _select_position_players(self, batters: List[Player]) -> List[Player]:
        """Select 15 batters filling required positions."""
        by_pos: Dict[str, List[Player]] = {}
        for p in batters:
            pos = self._normalize_position(p.position, is_pitcher=False)
            by_pos.setdefault(pos, []).append(p)

        lineup_order = ["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "DH"]
        selected = []
        used = set()

        for pos in lineup_order:
            candidates = by_pos.get(pos, [])
            for c in candidates:
                if id(c) not in used:
                    selected.append(c)
                    used.add(id(c))
                    break

        for p in batters:
            if len(selected) >= BATTERS_PER_TEAM:
                break
            if id(p) not in used:
                selected.append(p)
                used.add(id(p))

        return selected[:BATTERS_PER_TEAM]

    def _is_pitcher(self, player: Player) -> bool:
        pos = (player.position or "").upper()
        return pos in ("P", "SP", "RP", "CL", "CP")

    def _normalize_position(self, position: str, is_pitcher: bool) -> str:
        pos = (position or "").upper()
        if is_pitcher:
            return "SP"
        pos_map = {
            "C": "C", "1B": "1B", "2B": "2B", "3B": "3B", "SS": "SS",
            "LF": "LF", "CF": "CF", "RF": "RF", "DH": "DH",
            "OF": "CF", "IF": "SS",
        }
        return pos_map.get(pos, "CF")

    def _map_bat_hand(self, handedness: Optional[str]) -> int:
        """Map batting handedness: 0=R, 1=L, 2=S."""
        if not handedness:
            return 0
        h = handedness.upper()
        if h == "L":
            return 1
        if h in ("S", "B"):
            return 2
        return 0

    def _map_throw_hand(self, handedness: Optional[str]) -> int:
        """Map throwing handedness: 0=R, 1=L."""
        if not handedness:
            return 0
        return 1 if handedness.upper() == "L" else 0

    def _get_first_name(self, full_name: str) -> str:
        parts = full_name.strip().split()
        if not parts:
            return "Player"
        return parts[0]

    def _get_last_name(self, full_name: str) -> str:
        parts = full_name.strip().split()
        if len(parts) <= 1:
            return parts[0] if parts else "Player"
        # Skip suffixes
        last_parts = []
        for p in parts[1:]:
            if p.rstrip(".").upper() in ("JR", "SR", "II", "III", "IV"):
                continue
            last_parts.append(p)
        return " ".join(last_parts) if last_parts else parts[-1]

    def get_team_slot(self, team_abbrev: str) -> Optional[int]:
        """Get MVP ROM slot index for a modern MLB team."""
        mvp_abbrev = MODERN_MLB_TO_MVP.get(team_abbrev.upper())
        if mvp_abbrev:
            return MVP_ABBREV_TO_INDEX.get(mvp_abbrev)
        return None

    def get_mvp_abbrev(self, team_abbrev: str) -> Optional[str]:
        """Get MVP game abbreviation for a modern MLB team."""
        return MODERN_MLB_TO_MVP.get(team_abbrev.upper())
