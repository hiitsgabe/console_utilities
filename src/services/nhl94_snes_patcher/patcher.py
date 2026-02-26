"""NHL94 SNES Patcher - Main orchestrator.

Coordinates fetching roster data, mapping stats, and patching the ROM.
Supports ESPN (current season) and NHL official API (historical).
"""

from typing import Dict, List, Optional, Callable
from dataclasses import dataclass

from services.sports_api.models import Player
from services.nhl94_snes_patcher.models import (
    NHL94TeamRecord,
    NHL94RomInfo,
    TEAM_COUNT,
    NHL94_TEAM_ORDER,
)
from services.nhl94_snes_patcher.stat_mapper import NHL94StatMapper
from services.nhl94_snes_patcher.rom_reader import NHL94SNESRomReader
from services.nhl94_snes_patcher.rom_writer import NHL94SNESRomWriter


@dataclass
class PatchResult:
    """Result of a patch operation."""

    success: bool
    output_path: str = ""
    error: str = ""
    teams_patched: int = 0
    players_patched: int = 0


class NHL94SNESPatcher:
    """Main orchestrator for NHL94 SNES roster patching.

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
        self.mapper = NHL94StatMapper()

        if provider == "nhl":
            from services.sports_api.nhl_api_client import (
                NhlApiClient,
            )
            self.api = NhlApiClient(cache_dir, on_status)
        else:
            from services.sports_api.espn_client import EspnClient
            self.api = EspnClient(cache_dir, on_status)

    def analyze_rom(self, rom_path: str) -> NHL94RomInfo:
        """Validate ROM and read team slots."""
        reader = NHL94SNESRomReader(rom_path)
        if not reader.load():
            return NHL94RomInfo(
                path=rom_path,
                size=0,
                team_slots=[],
                is_valid=False,
                has_header=False,
            )
        return reader.get_info()

    def fetch_rosters(
        self,
        on_progress: Optional[Callable[[float, str], None]] = None,
        season: int = 2025,
    ) -> Dict[str, List[Player]]:
        """Fetch all NHL team rosters + stats.

        Args:
            on_progress: Callback (progress_0_to_1, message)
            season: Start year of season (2024 = 2024-25).
                    ESPN ignores this (always current).

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

        # Filter to teams with NHL94 ROM slots
        mapped = [
            t for t in nhl_teams
            if self.mapper.get_team_slot(t.code) is not None
        ]
        total = len(mapped)

        for i, team in enumerate(mapped):
            if on_progress:
                on_progress(i / total, f"Fetching {team.name}...")

            if self.provider == "nhl":
                # NHL API: use team abbreviation + season
                players = self.api.get_hockey_squad(
                    team.code, season
                )
                stats = self.api.get_hockey_team_leaders(
                    team.code, season
                )
            else:
                # ESPN: use team ESPN ID (no season support)
                players = self.api.get_hockey_squad(team.id)
                stats = self.api.get_hockey_team_leaders(
                    team.id
                )

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
        team_counts: Optional[Dict[int, tuple]] = None,
    ) -> List[NHL94TeamRecord]:
        """Map fetched rosters to NHL94 team records.

        Returns list of 28 NHL94TeamRecord (one per ROM slot).
        Uses self.team_stats (populated by fetch_rosters) for
        player ranking and attribute mapping.

        Args:
            rosters: Dict of team abbreviation -> players
            team_counts: Dict of slot_index -> (G, F, D) counts
                         from the ROM header's player count byte.
        """
        teams: List[NHL94TeamRecord] = []
        team_stats = getattr(self, "team_stats", {})
        team_counts = team_counts or {}

        # Initialize empty teams for all 28 slots
        for i in range(TEAM_COUNT):
            teams.append(NHL94TeamRecord(
                index=i,
                name=NHL94_TEAM_ORDER[i],
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
            counts = team_counts.get(slot, (2, 14, 7))
            num_g, num_f, num_d = counts

            # Select players in ROM order: G, F, D
            selected = self.mapper.select_roster(
                players, stats,
                num_goalies=num_g,
                num_forwards=num_f,
                num_defensemen=num_d,
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
        """Apply roster patches to ROM.

        Args:
            rom_path: Path to source NHL94 ROM
            output_path: Path for patched ROM
            rosters: Dict of team abbreviation -> players
            on_progress: Callback for progress updates

        Returns:
            PatchResult with success status and details
        """
        # Validate ROM
        if self.on_status:
            self.on_status("Validating ROM...")
        reader = NHL94SNESRomReader(rom_path)
        if not reader.load() or not reader.validate():
            return PatchResult(
                success=False,
                error="Invalid NHL94 ROM file",
            )

        # Read original G/F/D counts from ROM header
        team_counts = {}
        for i in range(TEAM_COUNT):
            team_counts[i] = reader.read_team_player_counts(i)

        # Map rosters to NHL94 format (G+F+D order)
        if self.on_status:
            self.on_status("Mapping rosters...")
        nhl94_teams = self.map_rosters_to_nhl94(
            rosters, team_counts
        )

        # Initialize writer
        if self.on_status:
            self.on_status("Initializing ROM writer...")
        writer = NHL94SNESRomWriter(rom_path, output_path)
        if not writer.load():
            return PatchResult(
                success=False,
                error="Failed to load ROM for writing",
            )

        # Write each team
        total_teams = TEAM_COUNT
        teams_patched = 0
        players_patched = 0

        for i, team in enumerate(nhl94_teams):
            if on_progress:
                on_progress(
                    i / total_teams,
                    f"Writing {team.name} ({len(team.players)} players)...",
                )

            if team.players:
                success = writer.write_team_roster(i, team.players)
                if success:
                    # Also update header: player count + lines
                    counts = team_counts.get(i, (2, 14, 7))
                    _, nf, nd = counts
                    writer.write_team_header(i, nf, nd)
                    teams_patched += 1
                    players_patched += len(team.players)

        if on_progress:
            on_progress(1.0, "Saving patched ROM...")

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