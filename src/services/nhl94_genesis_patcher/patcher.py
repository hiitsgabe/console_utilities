"""NHL94 Genesis Patcher - Main orchestrator.

Coordinates fetching roster data, mapping stats, and patching the ROM.
Supports ESPN (current season) and NHL official API (historical).
"""

from typing import Dict, List, Optional, Callable
from dataclasses import dataclass

from services.sports_api.models import Player
from services.nhl94_genesis_patcher.models import (
    NHL94GenTeamRecord,
    NHL94GenRomInfo,
    TEAM_COUNT,
    NHL94_GEN_TEAM_ORDER,
)
from services.nhl94_genesis_patcher.stat_mapper import NHL94GenStatMapper
from services.nhl94_genesis_patcher.rom_reader import NHL94GenesisRomReader
from services.nhl94_genesis_patcher.rom_writer import NHL94GenesisRomWriter


@dataclass
class PatchResult:
    """Result of a patch operation."""

    success: bool
    output_path: str = ""
    error: str = ""
    teams_patched: int = 0
    players_patched: int = 0


class NHL94GenesisPatcher:
    """Main orchestrator for NHL94 Genesis roster patching.

    Supports two providers:
      - "espn": ESPN public API (current season only)
      - "nhl": NHL official API (historical back to 1993)
    """

    def __init__(
        self,
        cache_dir: str,
        on_status: Optional[Callable] = None,
        provider: str = "espn",
    ):
        self.cache_dir = cache_dir
        self.on_status = on_status
        self.provider = provider
        self.mapper = NHL94GenStatMapper()

        if provider == "nhl":
            from services.sports_api.nhl_api_client import NhlApiClient
            self.api = NhlApiClient(cache_dir, on_status)
        else:
            from services.sports_api.espn_client import EspnClient
            self.api = EspnClient(cache_dir, on_status)

    def analyze_rom(self, rom_path: str) -> NHL94GenRomInfo:
        """Validate ROM and read team slots."""
        reader = NHL94GenesisRomReader(rom_path)
        if not reader.load():
            return NHL94GenRomInfo(
                path=rom_path, size=0,
                team_slots=[], is_valid=False,
            )
        return reader.get_info()

    def fetch_rosters(
        self,
        on_progress: Optional[Callable[[float, str], None]] = None,
        season: int = 2025,
    ) -> Dict[str, List[Player]]:
        """Fetch all NHL team rosters + stats.

        Returns dict mapping team abbreviation to player list.
        Also populates self.team_stats for use during patching.
        """
        rosters: Dict[str, List[Player]] = {}
        self.team_stats: Dict[str, dict] = {}

        if self.on_status:
            self.on_status("Fetching NHL teams...")
        nhl_teams = self.api.get_nhl_teams()

        if not nhl_teams:
            if self.on_status:
                self.on_status("No NHL teams found")
            return rosters

        # Filter to teams with NHL94 Genesis ROM slots
        mapped = [
            t for t in nhl_teams
            if self.mapper.get_team_slot(t.code) is not None
        ]
        total = len(mapped)

        for i, team in enumerate(mapped):
            if on_progress:
                on_progress(i / total, f"Fetching {team.name}...")

            if self.provider == "nhl":
                players = self.api.get_hockey_squad(team.code, season)
                stats = self.api.get_hockey_team_leaders(
                    team.code, season
                )
            else:
                players = self.api.get_hockey_squad(team.id)
                stats = self.api.get_hockey_team_leaders(team.id)

            if players:
                rosters[team.code] = players
            if stats:
                self.team_stats[team.code] = stats

        if on_progress:
            on_progress(1.0, "Complete")

        return rosters

    def map_rosters_to_nhl94(
        self,
        rosters: Dict[str, List[Player]],
    ) -> List[NHL94GenTeamRecord]:
        """Map fetched rosters to NHL94 Genesis team records.

        Returns list of 26 NHL94GenTeamRecord (one per ROM slot).
        """
        teams: List[NHL94GenTeamRecord] = []
        team_stats = getattr(self, "team_stats", {})

        # Initialize empty teams for all 26 slots
        for i in range(TEAM_COUNT):
            teams.append(NHL94GenTeamRecord(
                index=i,
                name=NHL94_GEN_TEAM_ORDER[i],
                city="",
                acronym="",
                players=[],
            ))

        # Fill in rosters for mapped teams
        for team_code, players in rosters.items():
            slot = self.mapper.get_team_slot(team_code)
            if slot is None or slot >= TEAM_COUNT:
                continue

            stats = team_stats.get(team_code, {})

            # Select ~23 players, ordered for proper lines
            selected = self.mapper.select_roster(
                players, stats, max_players=23,
            )

            # Map to NHL94 format with real stats
            nhl94_players = []
            for player in selected:
                pid = str(player.id)
                pstats = stats.get(pid, {})
                record = self.mapper.map_player(
                    player, team_code, pstats,
                )
                nhl94_players.append(record)

            teams[slot].players = nhl94_players

        return teams

    def patch_rom(
        self,
        rom_path: str,
        output_path: str,
        rosters: Dict[str, List[Player]],
        on_progress: Optional[Callable[[float, str], None]] = None,
    ) -> PatchResult:
        """Apply roster patches to ROM."""
        # Validate ROM
        if self.on_status:
            self.on_status("Validating ROM...")
        reader = NHL94GenesisRomReader(rom_path)
        if not reader.load() or not reader.validate():
            return PatchResult(
                success=False,
                error="Invalid NHL94 Genesis ROM file",
            )

        # Map rosters to NHL94 format
        if self.on_status:
            self.on_status("Mapping rosters...")
        nhl94_teams = self.map_rosters_to_nhl94(rosters)

        # Initialize writer
        if self.on_status:
            self.on_status("Initializing ROM writer...")
        writer = NHL94GenesisRomWriter(rom_path, output_path)
        if not writer.load():
            return PatchResult(
                success=False,
                error="Failed to load ROM for writing",
            )

        # Disable checksum so the edited ROM boots
        writer.disable_checksum()

        # Write each team
        teams_patched = 0
        players_patched = 0

        for i, team in enumerate(nhl94_teams):
            if on_progress:
                on_progress(
                    i / TEAM_COUNT,
                    f"Writing {team.name} ({len(team.players)} players)...",
                )

            if team.players:
                written = writer.write_team_roster(i, team.players)
                if written > 0:
                    writer.write_team_header(
                        i, team.players, actual_count=written,
                    )
                    teams_patched += 1
                    players_patched += written

        if on_progress:
            on_progress(1.0, "Saving patched ROM...")

        # Recalculate ROM header checksum
        writer.update_header_checksum()

        # Save patched ROM
        if self.on_status:
            self.on_status("Saving patched ROM...")
        if not writer.finalize():
            return PatchResult(
                success=False,
                error="Failed to save patched ROM",
            )

        return PatchResult(
            success=True,
            output_path=output_path,
            teams_patched=teams_patched,
            players_patched=players_patched,
        )
