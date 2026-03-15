"""PES 6 PS2 Patcher - Main orchestrator.

Coordinates fetching roster data from ESPN soccer API,
mapping teams to ROM slots, and patching team names in the ISO.
"""

from typing import Dict, List, Optional, Callable
from dataclasses import dataclass

from services.sports_api.models import Team, TeamRoster, LeagueData
from services.pes6_ps2_patcher.models import (
    PES6RomInfo,
    PES6SlotMapping,
    ESPN_LEAGUE_TO_RANGE,
    LEAGUE_RANGES,
)


@dataclass
class PatchResult:
    """Result of a patch operation."""

    success: bool
    output_path: str = ""
    error: str = ""
    teams_patched: int = 0


class PES6PS2Patcher:
    """Main orchestrator for PES 6 PS2 team name patching.

    Uses ESPN public soccer API to fetch current team names for a league,
    then maps them to the corresponding ROM slots and patches the ISO.
    """

    def __init__(
        self,
        cache_dir: str,
        on_status: Optional[Callable] = None,
    ):
        self.cache_dir = cache_dir
        self.on_status = on_status

        from services.sports_api.espn_client import EspnClient

        self.api = EspnClient(cache_dir, on_status)

    def analyze_rom(self, iso_path: str) -> PES6RomInfo:
        """Validate ISO and read team slots."""
        from services.pes6_ps2_patcher.rom_reader import PES6RomReader

        reader = PES6RomReader(iso_path)
        return reader.get_rom_info()

    def fetch_rosters(
        self,
        league_id: int,
        season: int = 2026,
        on_progress: Optional[Callable[[float, str], None]] = None,
    ) -> LeagueData:
        """Fetch all teams and squads for a league.

        Args:
            league_id: ESPN league ID (e.g. 2001 for Premier League).
            season: Season year.
            on_progress: Callback (progress_0_to_1, status_message).

        Returns:
            LeagueData with teams and rosters.
        """
        if on_progress:
            on_progress(0.0, "Fetching teams...")

        teams = self.api.get_teams(league_id, season)
        if not teams:
            raise RuntimeError(f"No teams found for league {league_id}")

        # Look up the ESPN league code for squad fetching
        from services.sports_api.espn_client import _ID_TO_LEAGUE

        item = _ID_TO_LEAGUE.get(league_id)
        league_code = item["code"] if item else None

        team_rosters = []
        for i, team in enumerate(teams):
            if on_progress:
                pct = (i + 1) / len(teams)
                on_progress(pct, f"Fetching {team.name}...")

            players = self.api.get_squad(team.id, league_code=league_code)

            team_rosters.append(
                TeamRoster(
                    team=team,
                    players=players,
                    player_stats={},
                )
            )

        from services.sports_api.models import League

        league_info = League(
            id=league_id,
            name=item["name"] if item else f"League {league_id}",
            country=item.get("country", "") if item else "",
            country_code="",
            logo_url="",
            season=season,
            teams_count=len(team_rosters),
        )

        return LeagueData(league=league_info, teams=team_rosters)

    def build_slot_mapping(
        self,
        rom_info: PES6RomInfo,
        teams: List[Team],
        league_id: int,
    ) -> List[PES6SlotMapping]:
        """Map ESPN teams to ROM slots for the given league.

        Uses ESPN_LEAGUE_TO_RANGE to find the correct slot range,
        then assigns teams sequentially.

        Args:
            rom_info: Parsed ROM info with team_slots.
            teams: List of ESPN Team objects.
            league_id: ESPN league ID.

        Returns:
            List of PES6SlotMapping.
        """
        from services.sports_api.espn_client import _ID_TO_LEAGUE

        item = _ID_TO_LEAGUE.get(league_id)
        if not item:
            return []

        espn_code = item["code"]
        range_key = ESPN_LEAGUE_TO_RANGE.get(espn_code)
        if not range_key:
            return []

        league_range = LEAGUE_RANGES.get(range_key)
        if not league_range:
            return []

        start = league_range["start"]
        end = league_range["end"]
        count = league_range["count"]

        mappings = []
        for i, team in enumerate(teams):
            if i >= count:
                break
            slot_index = start + i
            if slot_index >= end or slot_index >= len(rom_info.team_slots):
                break

            slot = rom_info.team_slots[slot_index]
            mappings.append(
                PES6SlotMapping(
                    team=team,
                    slot_index=slot_index,
                    slot_name=slot.name,
                )
            )

        return mappings

    def patch_rom(
        self,
        input_path: str,
        output_path: str,
        slot_mapping: List[PES6SlotMapping],
        rom_info: PES6RomInfo,
        on_progress: Optional[Callable[[float, str], None]] = None,
    ) -> PatchResult:
        """Write patched team names to a copy of the ISO.

        Args:
            input_path: Path to original PES 6 ISO.
            output_path: Path for patched ISO copy.
            slot_mapping: List of team-to-slot mappings.
            rom_info: ROM info with team slot offsets/budgets.
            on_progress: Callback (progress_0_to_1, status_message).

        Returns:
            PatchResult.
        """
        if not slot_mapping:
            return PatchResult(success=False, error="No teams to patch")

        if on_progress:
            on_progress(0.0, "Copying ISO...")

        try:
            from services.pes6_ps2_patcher.rom_writer import PES6RomWriter

            writer = PES6RomWriter(input_path, output_path)

            teams_patched = 0
            total = len(slot_mapping)

            for i, mapping in enumerate(slot_mapping):
                if on_progress:
                    pct = (i + 1) / total
                    on_progress(pct, f"Patching {mapping.team.name}...")

                slot = rom_info.team_slots[mapping.slot_index]

                # Use full team name and short_name as abbreviation
                new_name = mapping.team.name
                new_abbr = mapping.team.code or mapping.team.short_name[:3]

                writer.write_team_name(slot, new_name, new_abbr)
                teams_patched += 1

            writer.finalize()

            return PatchResult(
                success=True,
                output_path=output_path,
                teams_patched=teams_patched,
            )
        except Exception as e:
            return PatchResult(success=False, error=str(e))
