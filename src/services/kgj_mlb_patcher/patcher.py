"""KGJ MLB Patcher - Main orchestrator.

Coordinates fetching MLB roster data from ESPN, mapping stats,
and patching Ken Griffey Jr. Presents MLB (SNES) ROM.
"""

from typing import Dict, List, Optional, Callable
from dataclasses import dataclass

from services.sports_api.models import Player
from services.kgj_mlb_patcher.models import (
    KGJTeamRecord,
    KGJRomInfo,
    TEAM_COUNT,
    KGJ_TEAM_ORDER,
)
from services.kgj_mlb_patcher.stat_mapper import KGJStatMapper
from services.kgj_mlb_patcher.rom_reader import KGJRomReader
from services.kgj_mlb_patcher.rom_writer import KGJRomWriter


@dataclass
class PatchResult:
    """Result of a patch operation."""

    success: bool
    output_path: str = ""
    error: str = ""
    teams_patched: int = 0
    players_patched: int = 0


class KGJMLBPatcher:
    """Main orchestrator for KGJ MLB roster patching."""

    def __init__(
        self,
        cache_dir: str,
        on_status: Optional[Callable] = None,
    ):
        self.cache_dir = cache_dir
        self.on_status = on_status
        self.mapper = KGJStatMapper()

        from services.sports_api.espn_client import EspnClient

        self.api = EspnClient(cache_dir, on_status)

    def analyze_rom(self, rom_path: str) -> KGJRomInfo:
        """Validate ROM and read team slots."""
        reader = KGJRomReader(rom_path)
        if not reader.load():
            return KGJRomInfo(path=rom_path, size=0)
        return reader.get_info()

    def fetch_rosters(
        self,
        on_progress: Optional[Callable[[float, str], None]] = None,
        season: int = 2025,
    ) -> Dict[str, List[Player]]:
        """Fetch all MLB team rosters + stats.

        Returns dict mapping team abbreviation to player list.
        Also populates self.team_stats for use during patching.
        """
        rosters: Dict[str, List[Player]] = {}
        self.team_stats: Dict[str, dict] = {}

        if self.on_status:
            self.on_status("Fetching MLB teams...")
        mlb_teams = self.api.get_mlb_teams()

        if not mlb_teams:
            if self.on_status:
                self.on_status("No MLB teams found")
            return rosters

        # Filter to teams with KGJ ROM slots
        mapped = [t for t in mlb_teams if self.mapper.get_team_slot(t.code) is not None]
        total = len(mapped)

        for i, team in enumerate(mapped):
            if on_progress:
                on_progress(i / total, f"Fetching {team.name}...")

            players = self.api.get_baseball_squad(team.id)
            stats = self.api.get_baseball_team_leaders(team.id, season)

            if players:
                rosters[team.code] = players
            if stats:
                self.team_stats[team.code] = stats

        if on_progress:
            on_progress(1.0, "Complete")

        return rosters

    def map_rosters_to_kgj(
        self,
        rosters: Dict[str, List[Player]],
    ) -> List[KGJTeamRecord]:
        """Map fetched rosters to KGJ team records.

        Returns list of 28 KGJTeamRecord (one per ROM slot).
        """
        teams: List[KGJTeamRecord] = []
        team_stats = getattr(self, "team_stats", {})

        for i in range(TEAM_COUNT):
            teams.append(
                KGJTeamRecord(
                    index=i,
                    name=KGJ_TEAM_ORDER[i],
                    players=[],
                )
            )

        for team_code, players in rosters.items():
            slot = self.mapper.get_team_slot(team_code)
            if slot is None or slot >= TEAM_COUNT:
                continue

            stats = team_stats.get(team_code, {})

            # Select 25 players ordered for ROM slots
            selected = self.mapper.select_roster(players, stats)

            # Map to KGJ format
            kgj_players = []
            for idx, player in enumerate(selected):
                pid = str(player.id)
                pstats = stats.get(pid, {})
                is_pitcher = self.mapper._is_pitcher(player)
                is_starter = idx < 20  # slots 15-19 are starters

                if is_pitcher:
                    record = self.mapper.map_pitcher(
                        player,
                        pstats,
                        is_starter=is_starter,
                    )
                else:
                    record = self.mapper.map_batter(player, pstats)

                kgj_players.append(record)

            teams[slot].players = kgj_players

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
        reader = KGJRomReader(rom_path)
        if not reader.load() or not reader.validate():
            return PatchResult(
                success=False,
                error="Invalid KGJ MLB ROM file",
            )

        if self.on_status:
            self.on_status("Mapping rosters...")
        kgj_teams = self.map_rosters_to_kgj(rosters)

        if self.on_status:
            self.on_status("Initializing ROM writer...")
        writer = KGJRomWriter(rom_path, output_path)
        if not writer.load():
            return PatchResult(
                success=False,
                error="Failed to load ROM for writing",
            )

        teams_patched = 0
        players_patched = 0

        for i, team in enumerate(kgj_teams):
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

        writer.update_snes_checksum()

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
