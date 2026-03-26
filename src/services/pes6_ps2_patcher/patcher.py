"""PES6 PS2 patcher orchestrator."""

import os
import unicodedata
from typing import Callable, Dict, List, Optional

from services.sports_api.espn_client import EspnClient
from .models import LeagueData, RomInfo, SlotMapping
from .roster_map import RosterMap, SLPM_OFFSET
from .rom_reader import RomReader
from .rom_writer import RomWriter
from .stat_mapper import StatMapper


class PES6Patcher:
    """Orchestrates fetching rosters and patching PES6 PS2 ISOs.

    League-agnostic: works with any ESPN league. Teams are assigned
    to ROM slots sequentially within a configurable slot range.
    """

    def __init__(self, cache_dir: str, on_status=None):
        self.cache_dir = cache_dir
        self.on_status = on_status
        self.api = EspnClient(cache_dir, on_status=on_status)
        self.mapper = StatMapper()
        self.roster_map = RosterMap()

    def fetch_league(
        self,
        league_id: int,
        season: int,
        on_progress: Optional[Callable[[float, str], None]] = None,
        on_partial_data: Optional[Callable] = None,
    ) -> LeagueData:
        """Fetch rosters for any ESPN league."""
        from services.sports_api.models import TeamRoster

        if on_progress:
            on_progress(0.05, "Fetching league info...")

        leagues = self.api.get_leagues(id=league_id)
        league = leagues[0] if leagues else None
        if not league:
            raise ValueError(f"League {league_id} not found on ESPN")

        from services.sports_api.espn_client import _ID_TO_LEAGUE

        item = _ID_TO_LEAGUE.get(league_id)
        code = item["code"] if item else None

        if on_progress:
            on_progress(0.1, f"Fetching teams for {league.name}...")
        teams = self.api.get_teams(league_id, season)

        team_rosters = [
            TeamRoster(team=t, players=[], player_stats={}, loading=True) for t in teams
        ]
        league_data = LeagueData(league=league, teams=team_rosters)
        if on_partial_data:
            on_partial_data(league_data)

        for i, team in enumerate(teams):
            progress = 0.1 + 0.8 * (i / max(len(teams), 1))
            if on_progress:
                on_progress(progress, f"Fetching: {team.name}...")
            try:
                players = self.api.get_squad(team.id, league_code=code)
                team_rosters[i].players = players
                team_rosters[i].loading = False
            except Exception as e:
                team_rosters[i].error = str(e)
                team_rosters[i].loading = False

        if on_progress:
            on_progress(1.0, f"Loaded {len(teams)} teams")

        return league_data

    def analyze_rom(self, iso_path: str) -> RomInfo:
        """Validate and analyze a PES6 PS2 ISO."""
        reader = RomReader(iso_path)
        return reader.validate()

    def create_slot_mapping(
        self,
        league_data: LeagueData,
        rom_info: RomInfo = None,
        slot_start: int = 7,
        slot_end: int = 200,
    ) -> List[SlotMapping]:
        """Map ESPN teams to ROM slots by matching team names.

        Reads team names from the ISO's SLPM section and matches each ESPN
        team to the best-matching ROM team. Only matched teams are patched,
        ensuring player data goes to the correct roster slots.
        """
        mappings = []

        teams_with_players = [
            tr for tr in league_data.teams if tr.players and not tr.error
        ]

        # Build name → ram_index map from roster map
        roster_map = RosterMap()
        available_slots = roster_map.get_slot_range(slot_start, slot_end)
        iso_team_names = {}
        for ram_idx in available_slots:
            name = roster_map.get_team_name(ram_idx)
            if name:
                iso_team_names[name] = ram_idx

        # Name-based matching: only explicitly matched teams are patched
        for team_roster in teams_with_players:
            espn_name = team_roster.team.name
            roster_idx = self._match_team_name(espn_name, iso_team_names)

            if roster_idx is None:
                continue

            player_ids = self.roster_map.get_team_player_ids(roster_idx)
            if not player_ids:
                continue

            # Reverse-lookup the iso name from the roster map
            iso_name = roster_map.get_team_name(roster_idx) or f"Club {roster_idx}"
            mappings.append(
                SlotMapping(
                    espn_team=team_roster.team,
                    ram_index=roster_idx,
                    slpm_index=roster_idx,
                    slot_name=iso_name,
                    player_ids=player_ids,
                )
            )

        return mappings

    def _match_team_name(
        self, espn_name: str, iso_teams: Dict[str, int]
    ) -> Optional[int]:
        """Find the best matching ROM team for an ESPN team name.

        Uses normalized comparison (strip accents, lowercase) with known
        aliases for common mismatches between ESPN and EUR ROM names.
        iso_teams maps team name → ram_index.
        """
        ALIASES = {
            "atletico-madrid": ["atletico de madrid", "at. madrid"],
            "wolverhampton-wanderers": ["wolverhampton", "wolves"],
            "inter-milan": ["internazionale", "inter"],
            "paris-saint-germain": ["paris sg"],
            "borussia-dortmund": ["bor. dortmund"],
            "bayern-munich": ["bayern munchen", "fc bayern"],
            "rb-leipzig": ["rasenballsport leipzig"],
            "tottenham-hotspur": ["tottenham", "spurs"],
            "manchester-united": ["man united", "manchester utd"],
            "manchester-city": ["man city", "manchester c"],
            "newcastle-united": ["newcastle utd", "newcastle"],
            "west-ham-united": ["west ham", "west ham utd"],
            "athletic-club": ["athletic bilbao", "ath. bilbao"],
            "deportivo-la-coruna": ["deportivo", "rc deportivo"],
            "real-sociedad": ["r. sociedad"],
            "real-betis": ["r. betis"],
        }

        def normalize(s):
            nfkd = unicodedata.normalize("NFKD", s)
            out = (
                "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()
            )
            return out.replace("-", " ")

        norm_espn = normalize(espn_name)

        # Direct match
        for iso_name, ram_idx in iso_teams.items():
            if normalize(iso_name) == norm_espn:
                return ram_idx

        # Alias match (normalize alias keys to handle hyphens)
        for alias_key, variants in ALIASES.items():
            if normalize(alias_key) == norm_espn:
                for variant in variants:
                    for iso_name, ram_idx in iso_teams.items():
                        if normalize(iso_name) == normalize(variant):
                            return ram_idx
                break

        # Word-level match: check if all words of one name appear in the other
        espn_words = set(norm_espn.split())
        for iso_name, ram_idx in iso_teams.items():
            norm_iso = normalize(iso_name)
            iso_words = set(norm_iso.split())
            # ISO name's words all found in ESPN name, or vice versa
            if iso_words and iso_words.issubset(espn_words):
                return ram_idx
            if espn_words and espn_words.issubset(iso_words):
                return ram_idx

        return None

    @staticmethod
    def _sanitize_name(name: str) -> str:
        """Strip accents and non-ASCII chars for PES6 display."""
        import unicodedata

        nfkd = unicodedata.normalize("NFKD", name)
        ascii_name = "".join(c for c in nfkd if not unicodedata.combining(c))
        ascii_name = ascii_name.replace("-", " ")
        ascii_name = "".join(c if 32 <= ord(c) < 127 else "" for c in ascii_name)
        return ascii_name

    def patch_rom(
        self,
        rom_info: RomInfo,
        output_path: str,
        league_data: LeagueData,
        slot_mapping: List[SlotMapping],
        on_progress: Optional[Callable[[float, str], None]] = None,
    ) -> str:
        """Apply roster patches to the ISO."""
        writer = RomWriter(rom_info, output_path)
        writer.begin()

        try:
            all_records = []
            for i, mapping in enumerate(slot_mapping):
                progress = 0.7 * (i / max(len(slot_mapping), 1))
                if on_progress:
                    on_progress(progress, f"Mapping: {mapping.espn_team.name}...")

                team_roster = next(
                    (
                        tr
                        for tr in league_data.teams
                        if tr.team.id == mapping.espn_team.id
                    ),
                    None,
                )
                if team_roster and team_roster.players:
                    records = self.mapper.map_team(team_roster, mapping.player_ids)
                    all_records.extend(records)

            if on_progress:
                on_progress(0.7, f"Writing {len(all_records)} players to ISO...")

            writer.write_players_batch(all_records)

            if on_progress:
                on_progress(0.9, "Writing team names...")

            # Write team names to SLPM at correct club table positions
            # ram_index maps to club table entry (same numbering as roster)
            team_names = []
            for mapping in slot_mapping:
                name = self._sanitize_name(mapping.espn_team.name)[:23]
                code = (
                    mapping.espn_team.short_name[:7]
                    if mapping.espn_team.short_name
                    else name[:3].upper()
                )
                code = self._sanitize_name(code)
                # ram_index is the club table entry index
                team_names.append((mapping.ram_index, name, code))
            writer.write_team_names(team_names)

            if on_progress:
                on_progress(1.0, "Patch complete!")

        finally:
            writer.finalize()

        return output_path
