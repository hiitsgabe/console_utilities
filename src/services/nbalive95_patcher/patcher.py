"""NBA Live 95 Patcher - Main orchestrator.

Coordinates fetching NBA roster data from ESPN, mapping stats,
and patching NBA Live 95 (Sega Genesis) ROM.
"""

from typing import Dict, List, Optional, Callable
from dataclasses import dataclass

from services.sports_api.models import Player
from services.nbalive95_patcher.models import (
    NBALive95TeamRecord,
    NBALive95RomInfo,
    TEAM_COUNT,
    NBA_TEAM_COUNT,
    NBALIVE95_TEAM_ORDER,
)
from services.nbalive95_patcher.stat_mapper import NBALive95StatMapper
from services.nbalive95_patcher.rom_reader import NBALive95RomReader
from services.nbalive95_patcher.rom_writer import NBALive95RomWriter


@dataclass
class PatchResult:
    """Result of a patch operation."""

    success: bool
    output_path: str = ""
    error: str = ""
    teams_patched: int = 0
    players_patched: int = 0


class NBALive95Patcher:
    """Main orchestrator for NBA Live 95 roster patching."""

    def __init__(
        self,
        cache_dir: str,
        on_status: Optional[Callable] = None,
    ):
        self.cache_dir = cache_dir
        self.on_status = on_status
        self.mapper = NBALive95StatMapper()

        from services.sports_api.espn_client import EspnClient
        self.api = EspnClient(cache_dir, on_status)

    def analyze_rom(self, rom_path: str) -> NBALive95RomInfo:
        """Validate ROM and read team slots."""
        reader = NBALive95RomReader(rom_path)
        if not reader.load():
            return NBALive95RomInfo(path=rom_path, size=0)
        return reader.get_info()

    def fetch_rosters(
        self,
        on_progress: Optional[Callable[[float, str], None]] = None,
        season: int = 2025,
    ) -> Dict[str, List[Player]]:
        """Fetch all NBA team rosters + stats.

        Returns dict mapping team abbreviation to player list.
        Also populates self.team_stats for use during patching.
        """
        rosters: Dict[str, List[Player]] = {}
        self.team_stats: Dict[str, dict] = {}

        if self.on_status:
            self.on_status("Fetching NBA teams...")
        nba_teams = self.api.get_nba_teams()

        if not nba_teams:
            if self.on_status:
                self.on_status("No NBA teams found")
            return rosters

        # Filter to teams with ROM slots
        mapped = [
            t for t in nba_teams
            if self.mapper.get_team_slot(t.code) is not None
        ]
        total = len(mapped)

        for i, team in enumerate(mapped):
            if on_progress:
                on_progress(i / total, f"Fetching {team.name}...")

            players = self.api.get_basketball_squad(team.id)
            stats = self.api.get_basketball_team_leaders(team.id, season)

            if players:
                rosters[team.code] = players
            if stats:
                self.team_stats[team.code] = stats

        if on_progress:
            on_progress(1.0, "Complete")

        return rosters

    def map_rosters(
        self,
        rosters: Dict[str, List[Player]],
    ) -> List[NBALive95TeamRecord]:
        """Map fetched rosters to NBA Live 95 team records.

        Returns list of 30 NBALive95TeamRecord (one per ROM slot).
        Only NBA team slots (0-26) get populated with real data.
        """
        teams: List[NBALive95TeamRecord] = []
        team_stats = getattr(self, "team_stats", {})

        for i in range(TEAM_COUNT):
            teams.append(NBALive95TeamRecord(
                index=i,
                name=NBALIVE95_TEAM_ORDER[i],
                players=[],
            ))

        for team_code, players in rosters.items():
            slot = self.mapper.get_team_slot(team_code)
            if slot is None or slot >= NBA_TEAM_COUNT:
                continue

            stats = team_stats.get(team_code, {})

            # Select 12 players ordered for ROM slots
            selected = self.mapper.select_roster(players, stats)

            # Map to NBA Live 95 format
            nba_players = []
            for player in selected:
                pid = str(player.id)
                pstats = stats.get(pid, {})
                record = self.mapper.map_player(player, pstats)
                nba_players.append(record)

            teams[slot].players = nba_players

        return teams

    def patch_rom(
        self,
        rom_path: str,
        output_path: str,
        rosters: Dict[str, List[Player]],
        on_progress: Optional[Callable[[float, str], None]] = None,
    ) -> PatchResult:
        """Apply roster patches to ROM."""
        if self.on_status:
            self.on_status("Validating ROM...")
        reader = NBALive95RomReader(rom_path)
        if not reader.load() or not reader.validate():
            return PatchResult(
                success=False,
                error="Invalid NBA Live 95 ROM file",
            )

        if self.on_status:
            self.on_status("Mapping rosters...")
        nba_teams = self.map_rosters(rosters)

        if self.on_status:
            self.on_status("Initializing ROM writer...")
        writer = NBALive95RomWriter(rom_path, output_path)
        if not writer.load():
            return PatchResult(
                success=False,
                error="Failed to load ROM for writing",
            )

        # Bypass game's internal checksum verification
        writer.apply_patches()

        teams_patched = 0
        players_patched = 0

        for i, team in enumerate(nba_teams):
            if on_progress:
                on_progress(
                    i / TEAM_COUNT,
                    f"Writing {team.name} ({len(team.players)} players)...",
                )

            if team.players:
                written = writer.write_team_roster(i, team.players)
                if written > 0:
                    teams_patched += 1
                    players_patched += written

        if on_progress:
            on_progress(1.0, "Saving patched ROM...")

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
