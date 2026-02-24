"""ISS SNES ROM patcher orchestrator — ties together API, stat mapping, and ROM patching."""

import os
from typing import Callable, List, Optional

from .models import ISSRomInfo, ISSSlotMapping, ISSTeamRecord, TEAM_ENUM_ORDER
from .stat_mapper import ISSStatMapper
from .rom_reader import ISSRomReader
from .rom_writer import ISSRomWriter
from services.sports_api.models import LeagueData, TeamRoster


class ISSPatcher:
    def __init__(self, api_key: str, cache_dir: str, on_status=None, client=None):
        if client is not None:
            self.api = client
        else:
            from services.sports_api.api_football import ApiFootballClient
            self.api = ApiFootballClient(api_key, cache_dir, on_status=on_status)
        self.mapper = ISSStatMapper()

    def fetch_league(
        self,
        league_id: int,
        season: int,
        on_progress: Optional[Callable[[float, str], None]] = None,
        on_partial_data: Optional[Callable[[LeagueData], None]] = None,
    ) -> LeagueData:
        """Fetch all teams and rosters for a league.

        Identical flow to WePatcher — uses the shared sports API layer.
        """
        from services.sports_api.models import League, TeamRoster as TR

        if on_progress:
            on_progress(0.05, "Fetching league info...")
        leagues = self.api.get_leagues(id=league_id, season=season)
        league = next((l for l in leagues), None)
        if not league:
            raise ValueError(f"League {league_id} not found for season {season}")

        if on_progress:
            on_progress(0.1, f"Fetching teams for {league.name}...")
        teams = self.api.get_teams(league_id, season)

        team_rosters = [
            TR(team=t, players=[], player_stats={}, loading=True)
            for t in teams
        ]
        league_data = LeagueData(league=league, teams=team_rosters)
        if on_partial_data:
            on_partial_data(league_data)

        for i, team in enumerate(teams):
            progress = 0.1 + 0.8 * (i / max(len(teams), 1))
            if on_progress:
                on_progress(progress, f"Fetching squad: {team.name}...")
            try:
                players = self.api.get_squad(team.id)
                player_stats = {}
                try:
                    stats_list = self.api.get_player_stats(team.id, season)
                    player_stats = {s.player_id: s for s in stats_list}
                except Exception:
                    pass
                team_rosters[i].players = players
                team_rosters[i].player_stats = player_stats
            except Exception as e:
                from services.sports_api.api_football import RateLimitError, DailyLimitError
                if isinstance(e, DailyLimitError):
                    team_rosters[i].error = "Daily API limit reached"
                elif isinstance(e, RateLimitError):
                    team_rosters[i].error = "Rate limit reached"
                else:
                    team_rosters[i].error = f"Failed: {e}"
            finally:
                team_rosters[i].loading = False

        if on_progress:
            on_progress(1.0, "Done!")
        return league_data

    def analyze_rom(self, rom_path: str) -> ISSRomInfo:
        """Read ROM and return info including available team slots."""
        reader = ISSRomReader(rom_path)
        return reader.get_rom_info()

    def create_slot_mapping(
        self, league_data: LeagueData, rom_info: ISSRomInfo
    ) -> List[ISSSlotMapping]:
        """Map league teams to ROM slots sequentially (0-26).

        ISS has 27 team slots. Teams are mapped in order.
        """
        mappings = []
        for i, tr in enumerate(league_data.teams):
            if i >= len(TEAM_ENUM_ORDER):
                break
            slot_name = TEAM_ENUM_ORDER[i]
            mappings.append(
                ISSSlotMapping(
                    real_team=tr.team,
                    slot_index=i,
                    slot_name=slot_name,
                )
            )
        return mappings

    @staticmethod
    def _parse_hex_color(hex_str: str):
        """Parse a hex color string like '#ff0000' or 'ff0000' to RGB tuple."""
        if not hex_str:
            return None
        h = hex_str.lstrip("#")
        if len(h) == 6:
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
        return None

    def patch_rom(
        self,
        rom_path: str,
        output_path: str,
        league_data: LeagueData,
        slot_mapping: List[ISSSlotMapping],
        on_progress: Optional[Callable[[float, str], None]] = None,
    ) -> str:
        """Apply all patches and write output ROM. Returns output_path."""
        # Detect header
        reader = ISSRomReader(rom_path)
        reader.validate_rom()
        header_offset = reader.header_offset

        writer = ISSRomWriter(rom_path, output_path, header_offset)

        total = len(slot_mapping)
        team_by_id = {tr.team.id: tr for tr in league_data.teams}

        # Collect patched team names (only for teams being replaced)
        patched_names = {}

        for i, mapping in enumerate(slot_mapping):
            progress = i / max(total, 1)
            team_roster = team_by_id.get(mapping.real_team.id)
            if not team_roster:
                continue

            if on_progress:
                on_progress(progress, f"Patching {mapping.real_team.name}...")

            iss_team = self.mapper.map_team_with_league_context(
                team_roster, league_data.teams
            )

            # Parse team colors from ESPN API
            team_obj = mapping.real_team
            primary = self._parse_hex_color(team_obj.color)
            alt = self._parse_hex_color(team_obj.alternate_color)

            # Kit colors: home, away, GK
            if primary:
                iss_team.kit_home = (primary, (255, 255, 255), primary)
            if alt:
                iss_team.kit_away = (alt, (255, 255, 255), alt)
            # GK kit: green shirt, black shorts (standard default)
            iss_team.kit_gk = ((0, 128, 0), (0, 0, 0))

            # Write player names and data
            writer.write_player_names(mapping.slot_index, iss_team.players)
            writer.write_player_data(mapping.slot_index, iss_team.players)

            # Write kit colors
            writer.write_kit_colors(mapping.slot_index, iss_team)

            # Write predominant color
            if primary:
                writer.write_predominant_color(mapping.slot_index, primary)

            # Collect team name for selection screen
            patched_names[mapping.slot_index] = iss_team.name

        if on_progress:
            on_progress(0.90, "Writing team names...")

        # Write patched team names to selection screen text
        writer.write_team_name_texts(patched_names)

        if on_progress:
            on_progress(0.95, "Finalizing...")
        writer.finalize()
        if on_progress:
            on_progress(1.0, f"Done! Saved to {output_path}")
        return output_path
