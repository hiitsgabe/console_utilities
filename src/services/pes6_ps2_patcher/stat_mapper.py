"""Map ESPN soccer player data to PES6 player attributes."""

from typing import List
from services.sports_api.models import Player, TeamRoster
from .models import PES6PlayerAttributes, PES6PlayerRecord


POSITION_MAP = {
    "Goalkeeper": 0,
    "Defender": 1,
    "Midfielder": 4,
    "Forward": 9,
}

NATIONALITY_MAP = {
    "Brazil": 50,
    "Argentina": 28,
    "Colombia": 33,
    "Uruguay": 29,
    "Chile": 31,
    "Paraguay": 30,
    "Ecuador": 34,
    "Peru": 32,
    "Venezuela": 35,
    "Bolivia": 36,
    "Mexico": 40,
    "USA": 42,
    "England": 2,
    "Spain": 24,
    "France": 1,
    "Germany": 19,
    "Italy": 18,
    "Portugal": 13,
    "Netherlands": 6,
    "Belgium": 7,
    "Croatia": 52,
    "Serbia": 53,
    "Japan": 55,
    "South Korea": 56,
    "Nigeria": 62,
    "Cameroon": 63,
    "Ghana": 64,
    "Senegal": 65,
    "Ivory Coast": 66,
    "Egypt": 59,
}


class StatMapper:
    """Maps ESPN soccer roster data to PES6 player records."""

    def map_team(
        self,
        espn_roster: TeamRoster,
        player_ids: List[int],
    ) -> List[PES6PlayerRecord]:
        """Map ESPN team roster to PES6 player records at given file[35] indices."""
        espn_players = self._select_best_players(espn_roster.players, len(player_ids))

        records = []
        for pid, espn_player in zip(player_ids, espn_players):
            record = self._map_player(espn_player)
            record.file35_index = pid
            records.append(record)

        return records

    def _map_player(self, player: Player) -> PES6PlayerRecord:
        pos_code = POSITION_MAP.get(player.position, 4)
        nationality = self._get_nationality(player)
        attrs = self._compute_attributes(player, pos_code)

        name = self._sanitize(player.name[:14]) if player.name else "Unknown"
        shirt = self._make_shirt_name(player)

        return PES6PlayerRecord(
            name=name,
            shirt_name=shirt,
            position=pos_code,
            nationality=nationality,
            age=max(15, min(46, player.age)) if player.age else 25,
            height=175,
            weight=75,
            attributes=attrs,
            file35_index=0,
        )

    def _compute_attributes(
        self, player: Player, pos_code: int
    ) -> PES6PlayerAttributes:
        defaults = self._position_defaults(pos_code)
        age = player.age if player.age else 25

        if age < 22:
            age_factor = 0.80
        elif age < 25:
            age_factor = 0.90
        elif age <= 30:
            age_factor = 1.0
        elif age <= 33:
            age_factor = 0.95
        else:
            age_factor = 0.85

        attrs = PES6PlayerAttributes()
        for field_name, base_val in defaults.items():
            adjusted = int(base_val * age_factor)
            setattr(attrs, field_name, max(1, min(99, adjusted)))

        return attrs

    def _position_defaults(self, pos_code: int) -> dict:
        base = {
            "attack": 55,
            "defence": 55,
            "balance": 60,
            "stamina": 65,
            "speed": 60,
            "acceleration": 60,
            "response": 60,
            "agility": 60,
            "dribble_accuracy": 55,
            "dribble_speed": 55,
            "short_pass_accuracy": 60,
            "short_pass_speed": 55,
            "long_pass_accuracy": 50,
            "long_pass_speed": 50,
            "shot_accuracy": 50,
            "shot_power": 55,
            "shot_technique": 50,
            "free_kick": 45,
            "curling": 45,
            "heading": 55,
            "jump": 55,
            "teamwork": 65,
            "technique": 55,
            "aggression": 55,
            "mentality": 60,
            "gk_ability": 25,
            "consistency": 5,
            "condition": 5,
        }

        if pos_code == 0:  # GK
            base.update(
                {
                    "gk_ability": 75,
                    "defence": 65,
                    "attack": 25,
                    "response": 75,
                    "jump": 70,
                    "balance": 65,
                }
            )
        elif pos_code in (1, 2):  # CB/SB
            base.update(
                {
                    "defence": 75,
                    "attack": 35,
                    "heading": 70,
                    "balance": 70,
                    "aggression": 65,
                    "jump": 65,
                }
            )
        elif pos_code in (3, 4, 5):  # DMF/CMF/SMF
            base.update(
                {
                    "short_pass_accuracy": 70,
                    "stamina": 75,
                    "technique": 65,
                    "teamwork": 70,
                }
            )
        elif pos_code in (6, 7):  # AMF/WF
            base.update(
                {
                    "attack": 70,
                    "dribble_accuracy": 70,
                    "technique": 70,
                    "shot_accuracy": 65,
                    "speed": 70,
                }
            )
        elif pos_code in (8, 9):  # SS/CF
            base.update(
                {
                    "attack": 80,
                    "shot_accuracy": 75,
                    "shot_power": 70,
                    "heading": 65,
                    "speed": 65,
                    "dribble_accuracy": 65,
                }
            )

        return base

    def _get_nationality(self, player: Player) -> int:
        nat = getattr(player, "nationality", None) or getattr(
            player, "citizenship", None
        )
        if nat and nat in NATIONALITY_MAP:
            return NATIONALITY_MAP[nat]
        return 0  # Default unknown

    @staticmethod
    def _sanitize(name: str) -> str:
        import unicodedata

        nfkd = unicodedata.normalize("NFKD", name)
        return "".join(c for c in nfkd if not unicodedata.combining(c))

    def _make_shirt_name(self, player: Player) -> str:
        name = player.name or "UNKNOWN"
        parts = name.split()
        if len(parts) == 1:
            shirt = parts[0].upper()
        else:
            shirt = parts[-1].upper()
        return self._sanitize(shirt)[:15]

    def _select_best_players(
        self, players: List[Player], max_count: int
    ) -> List[Player]:
        pos_order = {"Goalkeeper": 0, "Defender": 1, "Midfielder": 2, "Forward": 3}
        sorted_players = sorted(players, key=lambda p: pos_order.get(p.position, 4))
        return sorted_players[:max_count]
