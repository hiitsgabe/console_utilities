"""WE2002 ROM patcher orchestrator — ties together API, stat mapping, and ROM patching."""

import os
from typing import Callable, List, Optional, Tuple

from .models import LeagueData, RomInfo, SlotMapping, WETeamRecord
from .api_football import ApiFootballClient
from .stat_mapper import StatMapper
from .csv_handler import CsvHandler
from .tim_generator import TimGenerator
from .rom_reader import RomReader
from .rom_writer import RomWriter
from .ppf import apply_ppf, get_ppf_info, PPFError


class WePatcher:
    def __init__(self, api_key: str, cache_dir: str, on_status=None, client=None):
        if client is not None:
            self.api = client
        else:
            self.api = ApiFootballClient(api_key, cache_dir, on_status=on_status)
        self.mapper = StatMapper()
        self.csv = CsvHandler()
        self.tim = TimGenerator()

    def fetch_league(
        self,
        league_id: int,
        season: int,
        on_progress: Optional[Callable[[float, str], None]] = None,
        on_partial_data: Optional[Callable[["LeagueData"], None]] = None,
    ) -> LeagueData:
        """Fetch all teams and rosters for a league from API-Football.

        Calls on_partial_data once the team list is known so the UI can show
        teams immediately (with loading=True) while squads are still fetching.
        """
        from .models import League, TeamRoster

        if on_progress:
            on_progress(0.05, "Fetching league info...")
        leagues = self.api.get_leagues(id=league_id, season=season)
        league = next((l for l in leagues), None)
        if not league:
            raise ValueError(f"League {league_id} not found for season {season}")

        if on_progress:
            on_progress(0.1, f"Fetching teams for {league.name}...")
        teams = self.api.get_teams(league_id, season)

        # Build skeleton immediately so the UI can render the team list right away
        team_rosters = [
            TeamRoster(team=t, players=[], player_stats={}, loading=True)
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
                    pass  # Stats are optional
                team_rosters[i].players = players
                team_rosters[i].player_stats = player_stats
            except Exception as e:
                from .api_football import RateLimitError, DailyLimitError
                if isinstance(e, DailyLimitError):
                    team_rosters[i].error = "Daily API limit reached — upgrade your plan"
                elif isinstance(e, RateLimitError):
                    team_rosters[i].error = "Rate limit reached — squad unavailable"
                else:
                    team_rosters[i].error = f"Failed to load squad: {e}"
            finally:
                # Update the roster entry in-place; render loop picks up changes automatically
                team_rosters[i].loading = False

        if on_progress:
            on_progress(1.0, "Done!")
        return league_data

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
        """Map league teams to ROM slots sequentially.

        Both national and ML slots are sequential (team 0 → slot 0,
        team 1 → slot 1, ...) so teams appear in order on the
        selection screen.  ESPN colors are written directly into the
        CLUT which controls both menu previews and 3D jerseys.
        Teams beyond 32 get slot_index=32 (sentinel; ML skipped).
        """
        mappings = []
        for i, tr in enumerate(league_data.teams):
            nat_slot = i if i < 63 else None
            ml_slot = i if i < 32 else None
            slot_index = ml_slot if ml_slot is not None else 32

            if ml_slot is not None and nat_slot is not None:
                label = f"Nat {nat_slot} + ML {ml_slot}"
            elif nat_slot is not None:
                label = f"Nat {nat_slot}"
            else:
                label = f"Team {i}"

            mappings.append(
                SlotMapping(
                    real_team=tr.team,
                    slot_index=slot_index,
                    slot_name=label,
                    nat_index=nat_slot,
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
        language: str = "en",
    ) -> str:
        """Apply all patches and write output ROM. Returns output_path.

        Automatically applies a translation PPF (for the chosen language)
        before writing roster/team patches.  The PPF translates kanji team
        names; the ROM writer then overwrites ML slots with actual API
        team names.
        """
        from .translations.we2002 import LANGUAGES, ensure_ppf as ensure_translation_ppf

        lang_name = LANGUAGES.get(language, "English")
        writer = RomWriter(rom_path, output_path)

        # Apply translation PPF first
        if on_progress:
            on_progress(0.02, f"Applying {lang_name} translation...")
        try:
            assets_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "assets")
            translations_dir = os.path.abspath(os.path.join(assets_dir, "translations"))
            # For English, try the community full-translation PPF first
            if language == "en":
                ppf_path = os.path.join(translations_dir, "w202-english.ppf")
                if os.path.exists(ppf_path):
                    desc = apply_ppf(output_path, ppf_path, skip_validation=True)
                    if on_progress:
                        on_progress(0.05, f"{lang_name} translation applied")
                else:
                    fallback_ppf = ensure_translation_ppf(translations_dir, language)
                    desc = apply_ppf(output_path, fallback_ppf)
                    if on_progress:
                        on_progress(0.05, f"{lang_name} team names applied")
            else:
                fallback_ppf = ensure_translation_ppf(translations_dir, language)
                desc = apply_ppf(output_path, fallback_ppf)
                if on_progress:
                    on_progress(0.05, f"{lang_name} translation applied")
        except Exception as e:
            if on_progress:
                on_progress(0.05, f"{lang_name} translation failed: {e}")

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

            # Kit colors from ESPN API (shirt primary, shorts secondary)
            team_obj = mapping.real_team
            if team_obj.color:
                h = team_obj.color.lstrip("#")
                if len(h) == 6:
                    we_team.kit_home = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
            if team_obj.alternate_color:
                h = team_obj.alternate_color.lstrip("#")
                if len(h) == 6:
                    we_team.kit_away = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
            we_team.kit_third = we_team.kit_home  # accent = shirt color

            # ML slot writes (0-31)
            if mapping.slot_index < 32:
                writer.write_team(mapping.slot_index, we_team)
                writer.write_players(mapping.slot_index, we_team.players)
                writer.write_flag(mapping.slot_index, we_team)

            # National slot writes (0-62)
            if mapping.nat_index is not None:
                writer.write_nat_team(mapping.nat_index, we_team)
                writer.write_nat_players(mapping.nat_index, we_team.players)
                writer.write_nat_flag(mapping.nat_index, we_team)

        if on_progress:
            on_progress(0.90, "Verifying patches...")

        # Collect the WE team records for verification (ML slots only)
        we_teams_map = {}
        for mapping in slot_mapping:
            if mapping.slot_index >= 32:
                continue
            team_roster = team_by_id.get(mapping.real_team.id)
            if team_roster:
                we_team = self.mapper.map_team_with_league_context(
                    team_roster, league_data.teams
                )
                we_teams_map[mapping.slot_index] = we_team

        report = writer.verify_patches(rom_path, slot_mapping, we_teams_map)
        self._last_verify_report = report

        if on_progress:
            on_progress(0.95, "Finalizing...")
        writer.finalize()
        if on_progress:
            on_progress(1.0, f"Done! Saved to {output_path}")
        return output_path
