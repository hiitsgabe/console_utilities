"""Stat mapping for NHL 07 PSP patcher.

Maps NHL player stats from ESPN/NHL API to NHL 07's 0-63 attribute scale.
Uses real season stats (G, A, PTS, +/-, PIM, SV%, GAA, etc.) when available,
with position-based defaults as fallback.

Same sport and API data as NHL94 patchers but scaled to 0-63 instead of 0-6.
"""

from typing import Optional, List, Dict

from services.sports_api.models import Player
from services.nhl07_psp_patcher.models import (
    NHL07PlayerRecord,
    NHL07SkaterAttributes,
    NHL07GoalieAttributes,
    MODERN_NHL_TO_NHL07,
)


# Default attributes by position (0-63 scale)
SKATER_DEFAULTS = {
    "C": NHL07SkaterAttributes(
        balance=35,
        penalty=30,
        shot_accuracy=35,
        wrist_accuracy=35,
        faceoffs=40,
        acceleration=35,
        speed=35,
        potential=35,
        deking=35,
        checking=30,
        toughness=25,
        fighting=1,
        puck_control=35,
        agility=35,
        hero=30,
        aggression=25,
        pressure=30,
        passing=38,
        endurance=35,
        injury=35,
        slap_power=30,
        wrist_power=30,
    ),
    "LW": NHL07SkaterAttributes(
        balance=33,
        penalty=30,
        shot_accuracy=35,
        wrist_accuracy=33,
        faceoffs=20,
        acceleration=35,
        speed=35,
        potential=35,
        deking=33,
        checking=33,
        toughness=30,
        fighting=1,
        puck_control=33,
        agility=35,
        hero=30,
        aggression=30,
        pressure=30,
        passing=30,
        endurance=35,
        injury=35,
        slap_power=33,
        wrist_power=33,
    ),
    "RW": NHL07SkaterAttributes(
        balance=33,
        penalty=30,
        shot_accuracy=35,
        wrist_accuracy=33,
        faceoffs=20,
        acceleration=35,
        speed=35,
        potential=35,
        deking=33,
        checking=33,
        toughness=30,
        fighting=1,
        puck_control=33,
        agility=35,
        hero=30,
        aggression=30,
        pressure=30,
        passing=30,
        endurance=35,
        injury=35,
        slap_power=33,
        wrist_power=33,
    ),
    "D": NHL07SkaterAttributes(
        balance=38,
        penalty=30,
        shot_accuracy=25,
        wrist_accuracy=25,
        faceoffs=15,
        acceleration=30,
        speed=30,
        potential=30,
        deking=25,
        checking=40,
        toughness=35,
        fighting=1,
        puck_control=28,
        agility=30,
        hero=28,
        aggression=33,
        pressure=35,
        passing=33,
        endurance=38,
        injury=35,
        slap_power=35,
        wrist_power=25,
    ),
}

GOALIE_DEFAULTS = NHL07GoalieAttributes(
    breakaway=35,
    rebound_ctrl=35,
    shot_recovery=35,
    speed=25,
    poke_check=30,
    intensity=35,
    potential=35,
    toughness=25,
    fighting=0,
    agility=40,
    five_hole=35,
    passing=25,
    endurance=40,
    glove_high=35,
    stick_high=35,
    glove_low=35,
    stick_low=35,
)


def _clamp(val: int, lo: int = 0, hi: int = 63) -> int:
    return max(lo, min(hi, val))


def _scale(value: float, low: float, high: float) -> int:
    """Map a value within [low, high] to 0-63 scale."""
    if high <= low:
        return 32
    ratio = (value - low) / (high - low)
    return _clamp(round(ratio * 63))


class NHL07StatMapper:
    """Maps NHL API player data to NHL 07 PSP ROM attributes."""

    def map_player(
        self,
        player: Player,
        team_abbrev: str,
        stats: Optional[Dict] = None,
    ) -> NHL07PlayerRecord:
        """Map an ESPN/NHL API Player to NHL 07 player record."""
        pos = player.position.upper() if player.position else "C"
        is_goalie = pos == "G"

        # Split name
        parts = (player.name or "").split(" ", 1)
        first_name = parts[0] if parts else ""
        last_name = parts[1] if len(parts) > 1 else ""

        jersey = player.number or 1

        # Handedness: 0=L, 1=R
        hand = 1
        if player.handedness == "L":
            hand = 0

        # Weight encoding for NHL 07: raw pounds value (stored as 8-bit)
        weight = int(player.weight) if player.weight > 0 else 190

        # Height encoding: 5-bit field. Approximate: (inches - 66) clamped 0-31
        height = 16  # ~5'10" default
        player_height = getattr(player, "height", 0) or 0
        if player_height > 0:
            inches = int(player_height)
            height = max(0, min(31, inches - 66))

        # Get team index
        team_index = MODERN_NHL_TO_NHL07.get(team_abbrev.upper(), 0)

        record = NHL07PlayerRecord(
            first_name=first_name[:19],
            last_name=last_name[:19],
            position=pos,
            jersey_number=jersey,
            handedness=hand,
            weight=weight,
            height=height,
            team_index=team_index,
            player_id=player.id if player.id else 0,
            is_goalie=is_goalie,
        )

        if is_goalie:
            if stats:
                record.goalie_attrs = self._map_goalie_stats(stats)
            else:
                record.goalie_attrs = NHL07GoalieAttributes(
                    **{
                        f.name: getattr(GOALIE_DEFAULTS, f.name)
                        for f in GOALIE_DEFAULTS.__dataclass_fields__.values()
                    }
                )
        else:
            if stats:
                record.skater_attrs = self._map_skater_stats(stats, pos)
            else:
                base = SKATER_DEFAULTS.get(pos, SKATER_DEFAULTS["C"])
                record.skater_attrs = NHL07SkaterAttributes(
                    **{f.name: getattr(base, f.name) for f in base.__dataclass_fields__.values()}
                )

        return record

    def _map_skater_stats(self, stats: Dict, pos: str) -> NHL07SkaterAttributes:
        """Map real NHL stats to NHL 07 skater attributes (0-63 scale).

        Stat ranges for scaling (per-season):
          G: 0-50, A: 0-70, PTS: 0-120, +/-: -30..+40
          PIM: 0-120, Shots: 0-350, FO%: 30-65
        """
        g = float(stats.get("G", 0) or 0)
        a = float(stats.get("A", 0) or 0)
        pts = float(stats.get("PTS", 0) or 0)
        pm = float(stats.get("+/-", 0) or 0)
        pim = float(stats.get("PIM", 0) or 0)
        shots = float(stats.get("SOG", 0) or stats.get("Shots", 0) or 0)
        fop = float(stats.get("FO%", 0) or stats.get("FOW%", 0) or 0)

        base = SKATER_DEFAULTS.get(pos, SKATER_DEFAULTS["C"])

        # Offensive metrics
        off_rating = _scale(pts, 0, 90)
        goal_rating = _scale(g, 0, 40)
        assist_rating = _scale(a, 0, 55)

        # Shooting accuracy from goal-to-shot ratio
        shoot_pct = (g / max(shots, 1)) * 100 if shots > 0 else 10
        accuracy_rating = _scale(shoot_pct, 5, 20)

        # Defensive / physical
        def_rating = _scale(pm + 30, 0, 70)
        tough_rating = _scale(pim, 0, 80)

        # Speed/agility boost for high-point players
        speed_boost = 5 if pts > 50 else (3 if pts > 30 else 0)

        return NHL07SkaterAttributes(
            balance=_clamp(base.balance + (3 if pos == "D" else 0)),
            penalty=_clamp(base.penalty),
            shot_accuracy=_clamp(max(goal_rating, accuracy_rating)),
            wrist_accuracy=_clamp(max(goal_rating - 2, accuracy_rating)),
            faceoffs=_clamp(_scale(fop, 30, 60) if fop > 0 else base.faceoffs),
            acceleration=_clamp(base.acceleration + speed_boost),
            speed=_clamp(base.speed + speed_boost),
            potential=_clamp(off_rating + 5),
            deking=off_rating,
            checking=_clamp(def_rating if pos == "D" else base.checking),
            toughness=tough_rating,
            fighting=min(3, max(0, int(pim / 40))),
            puck_control=off_rating,
            agility=_clamp(base.agility + speed_boost),
            hero=_clamp(off_rating),
            aggression=tough_rating,
            pressure=_clamp(def_rating),
            passing=assist_rating,
            endurance=_clamp(base.endurance + (3 if pts > 40 else 0)),
            injury=_clamp(base.injury),
            slap_power=goal_rating,
            wrist_power=_clamp(goal_rating - 3),
        )

    def _map_goalie_stats(self, stats: Dict) -> NHL07GoalieAttributes:
        """Map real NHL goalie stats to NHL 07 attributes (0-63 scale).

        Key stats: SV% (0.880-0.930), GAA (2.0-3.5), Wins
        """
        svp = float(stats.get("SV%", 0) or 0)
        gaa = float(stats.get("GAA", 3.0) or 3.0)
        wins = float(stats.get("W", 0) or stats.get("Wins", 0) or 0)

        # Core save ability (SV% is the strongest indicator)
        save_rating = _scale(svp, 0.880, 0.930)

        # Goals against (inverse — lower is better)
        gaa_rating = _scale(3.5 - gaa, 0, 1.5)

        # Experience/wins factor
        win_bonus = min(10, int(wins / 4))

        return NHL07GoalieAttributes(
            breakaway=_clamp(gaa_rating + win_bonus),
            rebound_ctrl=save_rating,
            shot_recovery=_clamp(save_rating - 3),
            speed=_clamp(25 + win_bonus),
            poke_check=_clamp(gaa_rating),
            intensity=_clamp(save_rating - 5 + win_bonus),
            potential=_clamp(save_rating + win_bonus),
            toughness=25,
            fighting=0,
            agility=save_rating,
            five_hole=save_rating,
            passing=25,
            endurance=_clamp(35 + win_bonus),
            glove_high=save_rating,
            stick_high=_clamp(save_rating - 2),
            glove_low=save_rating,
            stick_low=_clamp(save_rating - 2),
        )

    def select_roster(
        self,
        players: List[Player],
        stats: Optional[Dict] = None,
        max_players: int = 25,
    ) -> List[Player]:
        """Build NHL 07 roster with proper line structure.

        NHL 07 roster order:
          G1, G2 (goalies)
          C1-LW1-RW1 (Line 1) through C4-LW4-RW4 (Line 4)
          D1-D2 (Pair 1) through D3-D4 (Pair 3), D5-D6-D7 (extras)
        """
        stats = stats or {}

        def sort_key(p: Player) -> float:
            ps = stats.get(str(p.id), {})
            if p.position == "G":
                svp = float(ps.get("SV%", 0) or 0)
                return svp * 1000
            return float(ps.get("PTS", 0) or 0)

        centers = sorted(
            [p for p in players if p.position == "C"],
            key=sort_key,
            reverse=True,
        )
        left_wings = sorted(
            [p for p in players if p.position == "LW"],
            key=sort_key,
            reverse=True,
        )
        right_wings = sorted(
            [p for p in players if p.position == "RW"],
            key=sort_key,
            reverse=True,
        )
        defensemen = sorted(
            [p for p in players if p.position == "D"],
            key=sort_key,
            reverse=True,
        )
        goalies = sorted(
            [p for p in players if p.position == "G"],
            key=sort_key,
            reverse=True,
        )

        # Build 4 forward lines: C, LW, RW per line
        forwards = []
        for i in range(4):
            c = centers[i] if i < len(centers) else None
            lw = left_wings[i] if i < len(left_wings) else None
            rw = right_wings[i] if i < len(right_wings) else None
            for p in (c, lw, rw):
                if p is not None:
                    forwards.append(p)

        # Fill remaining forward slots
        used = set(id(p) for p in forwards)
        extras = sorted(
            [p for p in centers + left_wings + right_wings if id(p) not in used],
            key=sort_key,
            reverse=True,
        )
        forwards.extend(extras)
        forwards = forwards[:14]

        # Defense: sorted by points, take 7
        defense = defensemen[:7]

        # Goalies: sorted by SV%, take 2
        goalies = goalies[:2]

        # NHL 07 order: goalies first, then forwards, then defense
        selected = goalies + forwards + defense

        # Fill remaining slots
        all_used = set(id(p) for p in selected)
        leftover = sorted(
            [p for p in players if id(p) not in all_used],
            key=sort_key,
            reverse=True,
        )
        remaining = max_players - len(selected)
        if remaining > 0:
            selected.extend(leftover[:remaining])

        return selected[:max_players]

    def get_team_slot(self, team_abbrev: str) -> Optional[int]:
        """Get NHL 07 ROM slot for a modern NHL team."""
        return MODERN_NHL_TO_NHL07.get(team_abbrev.upper())

    def generate_team_line_flags(
        self,
        players: list,
    ) -> List[Dict[str, int]]:
        """Generate line flags for an entire team, position-aware.

        Returns a list of flag dicts, one per player (same order as input).
        Builds complete lines by assigning players to their natural
        position first, then filling gaps with excess centers on wing.

        Flags set: G1/G2, L1-L4 (C/LW/RW), 31-33 (LD/RD),
                   H1-H5 (PP unit), S1-S5 (PK unit).
        """
        result = [{} for _ in players]

        # Separate by position, keeping original index
        goalies = [(i, p) for i, p in enumerate(players) if p.is_goalie]
        centers = [(i, p) for i, p in enumerate(players) if p.position == "C"]
        left_w = [(i, p) for i, p in enumerate(players) if p.position == "LW"]
        right_w = [(i, p) for i, p in enumerate(players) if p.position == "RW"]
        defense = [(i, p) for i, p in enumerate(players) if p.position == "D"]

        # Goalies
        for gi, (idx, _) in enumerate(goalies[:2]):
            result[idx][f"G{gi + 1}__"] = 1

        # Build 4 forward lines: C, LW, RW per line
        # When LW/RW run out, use excess centers on wing
        c_pool = list(centers)
        lw_pool = list(left_w)
        rw_pool = list(right_w)

        fwd_line_indices = []  # track indices assigned to fwd lines

        for line in range(4):
            line_num = line + 1

            # Center
            if c_pool:
                idx, _ = c_pool.pop(0)
                result[idx][f"L{line_num}C_"] = 1
                fwd_line_indices.append(idx)

            # Left wing — use natural LW first, then spare centers
            if lw_pool:
                idx, _ = lw_pool.pop(0)
                result[idx][f"L{line_num}LW"] = 1
                fwd_line_indices.append(idx)
            elif c_pool:
                idx, _ = c_pool.pop(0)
                result[idx][f"L{line_num}LW"] = 1
                fwd_line_indices.append(idx)

            # Right wing — use natural RW first, then spare centers
            if rw_pool:
                idx, _ = rw_pool.pop(0)
                result[idx][f"L{line_num}RW"] = 1
                fwd_line_indices.append(idx)
            elif c_pool:
                idx, _ = c_pool.pop(0)
                result[idx][f"L{line_num}RW"] = 1
                fwd_line_indices.append(idx)

        # Defense: 3 pairs, alternating LD/RD
        d_line_indices = []
        for di, (idx, _) in enumerate(defense[:6]):
            pair = di // 2 + 1
            side = "LD" if di % 2 == 0 else "RD"
            result[idx][f"3{pair}{side}"] = 1
            d_line_indices.append(idx)

        # PP unit (H1-H5): Line 1 forwards + top 2 defensemen
        pp_candidates = fwd_line_indices[:3] + d_line_indices[:2]
        for hi, idx in enumerate(pp_candidates[:5]):
            result[idx][f"H{hi + 1}__"] = 1

        # PK unit (S1-S5): Line 2 forwards + next 2 defensemen
        pk_candidates = fwd_line_indices[3:6] + d_line_indices[2:4]
        for si, idx in enumerate(pk_candidates[:5]):
            result[idx][f"S{si + 1}__"] = 1

        return result
