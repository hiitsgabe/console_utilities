"""NHL 07 PSP patcher — the app's adapter onto `retro-roster-patcher`.

Same adapter as `services.nhl05_ps2_patcher.patcher`, and for the same reasons:
`app.py` builds one patcher for the fetch and a second for the patch, keeping
the result as a `{team code: [Player]}` dict plus a separate `team_stats` dict,
so the `LeagueData` the library's `map_rosters` wants has to be rebuilt from
those two dicts at patch time. See that module for the full argument.

Two differences from the old local code, both deliberate:

`team_stats` now exists from construction. The old class only created it inside
`fetch_rosters`, so reading it first raised `AttributeError`; `app.py` works
around that with `getattr(patcher, "team_stats", {})`. Initialising it is a
widening — the workaround still returns the same `{}`.

`fetch_rosters` raises `ApiError` when the provider answers with no teams,
where the old code returned an empty dict and the screen went quiet.

`analyze_rom` goes to the library's reader rather than the library patcher's
`analyze_rom`, which always validates deeply — it decompresses `nhlbioatt.tdb`
in full to check a four-byte magic. Every call site runs on the pygame main
thread when the user picks a ROM. Measured at 8.2 MB/s of pure-Python RefPack
on this machine, that is a visible stall per tap on a handheld. Going to the
reader also skips the library's compressed-image (CSO) detection and its
`db.viv` extent check, which is what the old code did too: `app.py` reads only
`is_valid` and swallows the exception, so the better message never reached a
user anyway.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

from retro_roster_patcher.core.errors import RetroRosterError
from retro_roster_patcher.games.nhl07_psp.models import NHL07RomInfo
from retro_roster_patcher.games.nhl07_psp.patcher import (
    NHL07PSPPatcher as _LibPatcher,
)
from retro_roster_patcher.games.nhl07_psp.rom_reader import NHL07PSPRomReader
from retro_roster_patcher.sports.models import League, LeagueData, Player, Team, TeamRoster


@dataclass
class PatchResult:
    """Result of a patch operation."""

    success: bool
    output_path: str = ""
    error: str = ""
    teams_patched: int = 0
    players_patched: int = 0


class NHL07PSPPatcher:
    """Main orchestrator for NHL 07 PSP roster patching.

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
        self.team_stats: Dict[str, dict] = {}
        self._patcher = _LibPatcher(
            cache_dir,
            provider=provider,
            on_status=on_status,
        )

    def analyze_rom(self, iso_path: str, deep: bool = False) -> NHL07RomInfo:
        """Validate ISO and read team slots.

        Args:
            deep: If True, decompress TDB files for full validation (slow).
                  If False, just check BIGF header + use hardcoded teams (fast).
        """
        reader = NHL07PSPRomReader(str(iso_path))
        if not reader.load():
            return NHL07RomInfo(
                path=str(iso_path),
                size=0,
                team_slots=[],
                is_valid=False,
            )
        return reader.get_info(deep=deep)

    def fetch_rosters(
        self,
        on_progress: Optional[Callable[[float, str], None]] = None,
        season: int = 2025,
    ) -> Dict[str, List[Player]]:
        """Fetch all NHL team rosters + stats.

        Returns dict mapping team abbreviation to player list.
        Also populates self.team_stats for use during patching.
        """
        data = self._patcher.fetch(season=season, on_progress=on_progress)

        rosters: Dict[str, List[Player]] = {}
        self.team_stats = {}
        for roster in data.teams:
            # Both guards are the old behaviour: a team with no players does not
            # get a key, and neither does a team with no leader stats.
            if roster.players:
                rosters[roster.team.code] = roster.players
            leaders = roster.extra.get("leaders") or {}
            if leaders:
                self.team_stats[roster.team.code] = leaders
        return rosters

    def patch_rom(
        self,
        iso_path: str,
        output_path: str,
        rosters: Dict[str, List[Player]],
        on_progress: Optional[Callable[[float, str], None]] = None,
    ) -> PatchResult:
        """Apply roster patches to ISO."""
        try:
            mapped = self._patcher.map_rosters(self._league_data(rosters))
            result = self._patcher.patch(
                rom_path=Path(iso_path),
                output_path=Path(output_path),
                rosters=mapped,
                on_progress=on_progress,
            )
        except RetroRosterError as exc:
            # This library's own errors are the ones the old code returned as a
            # failed `PatchResult`. Anything else is a bug and keeps propagating
            # to `app.py`'s handler, which shows the exception text.
            return PatchResult(success=False, error=str(exc))

        return PatchResult(
            success=True,
            output_path=result.output_path,
            teams_patched=result.teams_patched,
            players_patched=result.players_patched,
        )

    def _league_data(self, rosters: Dict[str, List[Player]]) -> LeagueData:
        """Rebuild the library's `LeagueData` from the app's two state fields.

        Sorted by team code so a patch run is reproducible: `MODERN_NHL_TO_NHL07`
        collapses 39 codes onto 32 slots, so which of a colliding pair wins
        depends on iteration order.

        `League.season` is 0 and not the fetched season: nothing downstream of
        `map_rosters` reads it, and the patch phase has no season to hand.
        """
        teams = [
            TeamRoster(
                team=Team(id=0, name=code, short_name=code, code=code),
                players=list(players),
                extra={"leaders": self.team_stats.get(code, {})},
            )
            for code, players in sorted(rosters.items())
        ]
        return LeagueData(
            league=League(
                id=0,
                name="NHL",
                country="USA",
                country_code="US",
                season=0,
                teams_count=len(teams),
            ),
            teams=teams,
        )
