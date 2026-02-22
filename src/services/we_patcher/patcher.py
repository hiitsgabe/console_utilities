"""WE2002 ROM patcher orchestrator — ties together API, stat mapping, and ROM patching."""

import os
from typing import Callable, List, Optional

from .models import LeagueData, RomInfo, SlotMapping, WETeamRecord
from .api_football import ApiFootballClient
from .stat_mapper import StatMapper
from .csv_handler import CsvHandler
from .tim_generator import TimGenerator
from .rom_reader import RomReader
from .rom_writer import RomWriter


class WePatcher:
    def __init__(self, api_key: str, cache_dir: str):
        self.api = ApiFootballClient(api_key, cache_dir)
        self.mapper = StatMapper()
        self.csv = CsvHandler()
        self.tim = TimGenerator()

    def fetch_league(
        self,
        league_id: int,
        season: int,
        on_progress: Optional[Callable[[float, str], None]] = None,
    ) -> LeagueData:
        """Fetch all teams and rosters for a league from API-Football."""
        from .models import League, TeamRoster

        if on_progress:
            on_progress(0.05, "Fetching league info...")
        leagues = self.api.get_leagues(season=season)
        league = next((l for l in leagues if l.id == league_id), None)
        if not league:
            raise ValueError(f"League {league_id} not found for season {season}")

        if on_progress:
            on_progress(0.1, f"Fetching teams for {league.name}...")
        teams = self.api.get_teams(league_id, season)

        team_rosters = []
        for i, team in enumerate(teams):
            progress = 0.1 + 0.8 * (i / max(len(teams), 1))
            if on_progress:
                on_progress(progress, f"Fetching squad: {team.name}...")
            players = self.api.get_squad(team.id)
            player_stats = {}
            try:
                stats_list = self.api.get_player_stats(team.id, season)
                player_stats = {s.player_id: s for s in stats_list}
            except Exception:
                pass  # Stats are optional
            team_rosters.append(
                TeamRoster(team=team, players=players, player_stats=player_stats)
            )

        if on_progress:
            on_progress(1.0, "Done!")
        return LeagueData(league=league, teams=team_rosters)

    def generate_csv(self, league_data: LeagueData, output_dir: str) -> str:
        """Export league data to CSV. Returns the CSV file path."""
        os.makedirs(output_dir, exist_ok=True)
        safe_name = league_data.league.name.replace(" ", "_").replace("/", "-")
        path = os.path.join(output_dir, f"{safe_name}_{league_data.league.season}.csv")

        # Map to WE records first
        we_records = []
        for team_roster in league_data.teams:
            we_team = self.mapper.map_team_with_league_context(
                team_roster, league_data.teams
            )
            we_records.append((team_roster.team.name, we_team.players))

        self.csv.export_league(league_data.league.name, we_records, path)
        return path

    def analyze_rom(self, rom_path: str) -> RomInfo:
        """Read ROM and return info including available team slots."""
        reader = RomReader(rom_path)
        return reader.get_rom_info()

    def create_slot_mapping(
        self, league_data: LeagueData, rom_info: RomInfo
    ) -> List[SlotMapping]:
        """Auto-map league teams to ROM slots sequentially."""
        mappings = []
        slots = rom_info.team_slots
        for i, team_roster in enumerate(league_data.teams):
            if i >= len(slots):
                break
            slot = slots[i]
            mappings.append(
                SlotMapping(
                    real_team=team_roster.team,
                    slot_index=slot.index,
                    slot_name=slot.current_name,
                )
            )
        return mappings

    def patch_rom(
        self,
        rom_path: str,
        output_path: str,
        league_data: LeagueData,
        slot_mapping: List[SlotMapping],
        on_progress: Optional[Callable[[float, str], None]] = None,
    ) -> str:
        """Apply all patches and write output ROM. Returns output_path."""
        writer = RomWriter(rom_path, output_path)
        total = len(slot_mapping)

        # Build team lookup
        team_by_id = {tr.team.id: tr for tr in league_data.teams}

        for i, mapping in enumerate(slot_mapping):
            progress = i / max(total, 1)
            team_roster = team_by_id.get(mapping.real_team.id)
            if not team_roster:
                continue

            if on_progress:
                on_progress(progress, f"Patching {mapping.real_team.name}...")

            we_team = self.mapper.map_team_with_league_context(
                team_roster, league_data.teams
            )

            writer.write_team(mapping.slot_index, we_team)
            writer.write_players(mapping.slot_index, we_team.players)

            # Try to download and write flag (best effort)
            try:
                logo_url = self.api.get_team_logo_url(mapping.real_team.id)
                if logo_url:
                    tim_data = self.tim.download_and_convert(logo_url, (32, 32))
                    writer.write_flag(mapping.slot_index, tim_data)
            except Exception:
                pass  # Flag generation is best-effort

        if on_progress:
            on_progress(0.95, "Finalizing ROM checksums...")
        writer.finalize()
        if on_progress:
            on_progress(1.0, f"Done! Saved to {output_path}")
        return output_path
