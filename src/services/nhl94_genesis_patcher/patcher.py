"""NHL 94 Genesis patcher — the app's adapter onto `retro-roster-patcher`.

Same adapter as `services.nhl05_ps2_patcher.patcher`, and for the same reasons:
`app.py` builds one patcher for the fetch and a second for the patch, keeping
the result as a `{team code: [Player]}` dict plus a separate `team_stats` dict,
so the `LeagueData` the library's `map_rosters` wants has to be rebuilt from
those two dicts at patch time. See that module for the full argument.

`analyze_rom` delegates to the library patcher here, unlike the NHL 05 and
NHL 07 shims, which bypass it and drive the library's `RomReader` themselves.
Those two games pay for a deep validation that decompresses megabytes of
RefPack on the pygame main thread at every ROM selection. This game has nothing
of the kind: the library's `analyze_rom` reads the 1 MB cartridge once and walks
26 four-byte pointers and one length-prefixed string per team. There is no
cheaper mode to opt into and no work worth skipping, so delegating costs
nothing and keeps the library's guard against a truncated image, where a
pointer near the end of the file makes the string read run off the end.

The one thing that does not carry over is the failure mode. The library reports
an unreadable path by raising `RomError`; this shim's callers need a falsy
`RomInfo` instead, so the error is translated back into one. That is not
defensive padding: the app builds a patcher and calls `analyze_rom` the moment
a file is highlighted in the browser, including on paths that have just been
deleted or unmounted, and "not a ROM" is the answer it wants for those.

Two differences from the old local code:

`team_stats` now exists from construction. The old class only created it inside
`fetch_rosters`, so reading it first raised `AttributeError`; `app.py` works
around that with `getattr(patcher, "team_stats", {})`. Initialising it is a
widening — the workaround still returns the same `{}`.

`fetch_rosters` raises `ApiError` when the provider answers with no teams, or
when no returned team maps to a 1994 ROM slot, where the old code returned an
empty dict and the screen went quiet.

`analyze_rom` returns the library's `RomInfo` rather than `NHL94GenRomInfo`.
The fields overlap on everything the app touches — it stores the object and
reads only `.is_valid` — but `team_slots` is now `slots`, so a future roster
editor reading the ROM's existing team names has to follow the rename.

One library correction rides along in `map_rosters`. `MODERN_NHL_TO_NHL94_GEN`
folds 30 codes onto 26 slots — LAK/LA, NJD/NJ, SJS/SJ and TBL/TB alias — and
the old `map_rosters_to_nhl94` let whichever code came last win, so an empty
roster arriving second wiped a populated one. The library keeps the populated
roster instead. `_league_data` sorts by code so which of a colliding pair is
seen first is at least reproducible.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

from retro_roster_patcher.core.errors import RetroRosterError, RomError
from retro_roster_patcher.core.models import RomInfo
from retro_roster_patcher.games.nhl94_genesis.patcher import (
    NHL94GenesisPatcher as _LibPatcher,
)
from retro_roster_patcher.sports.models import League, LeagueData, Player, Team, TeamRoster


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
        self.team_stats: Dict[str, dict] = {}
        self._patcher = _LibPatcher(
            cache_dir,
            provider=provider,
            on_status=on_status,
        )

    def analyze_rom(self, rom_path: str) -> RomInfo:
        """Validate ROM and read team slots.

        A file that cannot be opened is reported as an invalid ROM, not raised:
        see the module docstring.
        """
        try:
            return self._patcher.analyze_rom(Path(rom_path))
        except RomError:
            return RomInfo(
                path=str(rom_path),
                size=0,
                game_id=self._patcher.game_id,
                is_valid=False,
            )

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
        rom_path: str,
        output_path: str,
        rosters: Dict[str, List[Player]],
        on_progress: Optional[Callable[[float, str], None]] = None,
    ) -> PatchResult:
        """Apply roster patches to ROM."""
        try:
            mapped = self._patcher.map_rosters(self._league_data(rosters))
            result = self._patcher.patch(
                rom_path=Path(rom_path),
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

        Sorted by team code so a patch run is reproducible: four modern
        abbreviations alias onto slots another code already claims, so which of
        a colliding pair wins depends on iteration order.

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
