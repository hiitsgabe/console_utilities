"""PES 6 PS2 Patcher - Main orchestrator.

Coordinates fetching roster data from ESPN soccer API,
mapping teams to ROM slots, and patching team names in the ISO.
"""

from typing import Dict, List, Optional, Callable
from dataclasses import dataclass

import unicodedata

from services.sports_api.models import Team, TeamRoster, LeagueData
from services.pes6_ps2_patcher.models import (
    ISO_SECTOR_SIZE,
    PES6RomInfo,
    PES6SlotMapping,
    ESPN_LEAGUE_TO_RANGE,
    DEFAULT_LEAGUE_RANGE,
    LEAGUE_RANGES,
)

# League index in OVER.AFS that corresponds to each PES 6 league range
# Used to rename the league when patching
_RANGE_TO_LEAGUE_INDEX = {
    "epl": 1,        # "League -England-"
    "ligue1": 2,     # "League -France-"
    "serie_a": 4,    # "Serie A"
    "eredivisie": 5, # "Eredivisie"
    "la_liga": 6,    # "Liga Española"
}

# "Other" league indices for swapping displaced league names
_OTHER_LEAGUE_INDICES = [7, 8, 9, 10]  # League A, B, C, D


def _clean_name(name: str) -> str:
    """Strip accents and special chars, keeping ASCII-safe text."""
    # Normalize to decomposed form, then drop combining characters
    nfkd = unicodedata.normalize("NFKD", name)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


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
        espn_code = item["code"] if item else None
        range_key = ESPN_LEAGUE_TO_RANGE.get(espn_code, DEFAULT_LEAGUE_RANGE)

        league_range = LEAGUE_RANGES.get(range_key)
        if not league_range:
            league_range = LEAGUE_RANGES[DEFAULT_LEAGUE_RANGE]

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
        league_id: int = 0,
        league_name: str = "",
        on_progress: Optional[Callable[[float, str], None]] = None,
    ) -> PatchResult:
        """Write patched team names and league name to a copy of the ISO.

        Args:
            input_path: Path to original PES 6 ISO.
            output_path: Path for patched ISO copy.
            slot_mapping: List of team-to-slot mappings.
            rom_info: ROM info with team slot offsets/budgets.
            league_id: ESPN league ID (for league name patching).
            league_name: Display name of the league.
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
            from services.sports_api.espn_client import _ID_TO_LEAGUE

            writer = PES6RomWriter(input_path, output_path)

            # -- Rename the league in OVER.AFS --
            item = _ID_TO_LEAGUE.get(league_id)
            espn_code = item["code"] if item else None
            range_key = ESPN_LEAGUE_TO_RANGE.get(espn_code, DEFAULT_LEAGUE_RANGE)
            target_league_idx = _RANGE_TO_LEAGUE_INDEX.get(range_key)

            if target_league_idx is not None and league_name:
                clean_league = _clean_name(league_name)

                # If replacing a different native league (e.g. Brasileirao → EPL slots),
                # move the original league name to "League A" slot
                native_range = ESPN_LEAGUE_TO_RANGE.get(espn_code)
                if native_range != range_key or native_range is None:
                    original_name = self._read_league_name(
                        input_path, target_league_idx
                    )
                    if original_name:
                        for other_idx in _OTHER_LEAGUE_INDICES:
                            writer.write_league_name(other_idx, original_name)
                            break

                writer.write_league_name(target_league_idx, clean_league)
                writer.write_etext_league_name(target_league_idx, clean_league)

            # -- Patch team names --
            teams_patched = 0
            total = len(slot_mapping)

            for i, mapping in enumerate(slot_mapping):
                if on_progress:
                    pct = (i + 1) / total
                    on_progress(pct, f"Patching {mapping.team.name}...")

                slot = rom_info.team_slots[mapping.slot_index]

                new_name = _clean_name(mapping.team.name)
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

    def _read_league_name(self, iso_path: str, league_index: int) -> str:
        """Read the current league name from OVER.AFS[2]."""
        import struct

        try:
            with open(iso_path, "rb") as f:
                from services.pes6_ps2_patcher.rom_writer import PES6RomWriter

                f.seek(PES6RomWriter.OVER_AFS_LBA * ISO_SECTOR_SIZE)
                afs_header = f.read(8)
                num_files = struct.unpack_from("<I", afs_header, 4)[0]
                afs_table = f.read(num_files * 8)

                entry_off = struct.unpack_from("<I", afs_table, 2 * 8)[0]
                abs_off = (
                    PES6RomWriter.OVER_AFS_LBA * ISO_SECTOR_SIZE
                    + entry_off
                    + PES6RomWriter._OVER2_LEAGUE_OFF
                    + league_index * PES6RomWriter.LEAGUE_RECORD_SIZE
                )
                f.seek(abs_off)
                record = f.read(PES6RomWriter.LEAGUE_RECORD_SIZE)
                return record.split(b"\x00")[0].decode("utf-8", errors="replace")
        except Exception:
            return ""
