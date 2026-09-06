"""NBA Live 95 Genesis patcher — the app's adapter onto `retro-roster-patcher`.

Fetching, mapping and patching all live in the library now, in
`retro_roster_patcher.games.nbalive95_genesis`. This module keeps the shape
`app.py` calls, which the library deliberately does not have:

- `fetch_rosters` returns `{team code: [Player]}` and leaves the per-team leader
  stats on `self.team_stats`. The library returns one `LeagueData` carrying
  both.
- `patch_rom` returns a `PatchResult` with `success` and `error`. The library
  raises instead.

`_league_data` is the load-bearing part, and the reason is not obvious from the
call sites. `app.py` builds a *second* patcher for the patch phase —
`_start_nbalive95_roster_fetch` constructs one, `_start_nbalive95_patching`
constructs another and re-injects `patcher.team_stats = nba.team_stats` — so no
state survives on the instance between the two. The `LeagueData` the library's
`map_rosters` needs has to be rebuilt from the roster dict plus that stats dict
at patch time.

That reconstruction is lossy by design: `map_rosters` reads only `Team.code`
(to find the ROM slot), `players`, and `extra["leaders"]`, so every other `Team`
and `League` field is filler here. It is safe only because the UI never mutates
`nba.rosters` — the roster preview modal reads it, and `app.py` builds its own
separate `LeagueData` for display. A roster editor would have to write back into
what `_league_data` reads, or its edits would be dropped here in silence.

`analyze_rom` delegates to the library patcher, unlike the NHL 05 and NHL 07
shims, which bypass theirs. Those two games keep their rosters in RefPack-
compressed TDB files, so the library's deep validation costs megabytes of
pure-Python decompression on the pygame main thread at every ROM-selection tap.
Nothing of the sort happens here: a Genesis cartridge is a flat 2 MB image, and
`_looks_like_nbalive95` is 360 pointer dereferences plus a printable-ASCII count
over 24 bytes each. Measured against the synthetic 0x200000 fixture, the whole
library `analyze_rom` is 2.6 ms, of which the deep check is 0.55 ms; the old
local `analyze_rom` — the same file read plus `get_info` — was 1.7 ms. Under a
millisecond of extra work per tap does not justify reaching past the library's
own entry point, and going through it buys the stricter validity test for free.

Four behaviour differences from the old local code, all deliberate:

`team_stats` now exists from construction. The old class only created it inside
`fetch_rosters`, so reading it first raised `AttributeError`; `app.py` works
around that with `getattr(patcher, "team_stats", {})`. Initialising it is a
widening — the workaround still returns the same `{}`.

`fetch_rosters` raises `ApiError` when the provider answers with no teams, or
with no team that maps to a ROM slot, where the old code returned an empty dict
and the screen went quiet. `app.py`'s fetch thread catches it and shows the
message.

`analyze_rom` returns the library's `RomInfo` rather than `NBALive95RomInfo`.
The library *raises* `RomError` for a file it cannot read; the shim catches it
and answers with an invalid `RomInfo`, which is what the old code did. All
three call sites — the folder-browser selection handler, the ROM auto-detect
handler and `_validate_auto_detect_rom` — would have tolerated the raise, but
one of them stores the object before testing it, and every other adapter in the
family returns rather than raises. `RomInfo.slots` replaces `.team_slots`;
nothing in `src/` reads either.

`analyze_rom` is also stricter about what counts as valid. The old reader's
`validate()` checked the size band, the Genesis title and team 0's first
pointer; the library additionally requires all 360 pointers to resolve, to be
distinct, and to address records with a known position byte and a printable
name. A short-but-plausible dump that the old code called valid and would then
have patched into garbage past team 17 is now refused up front. `patch_rom` is
unaffected — the library's `patch` runs the same `validate()` the old code did,
plus a bounds check on the pointer tables.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

from retro_roster_patcher.core.errors import RetroRosterError, RomError
from retro_roster_patcher.core.models import RomInfo
from retro_roster_patcher.games.nbalive95_genesis.patcher import (
    NBALive95Patcher as _LibPatcher,
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


class NBALive95Patcher:
    """Main orchestrator for NBA Live 95 roster patching.

    ESPN only. There is no `provider` argument, and the library's is left at its
    default for the same reason: this game registers `providers=("espn",)`.
    """

    def __init__(
        self,
        cache_dir: str,
        on_status: Optional[Callable] = None,
    ):
        self.cache_dir = cache_dir
        self.on_status = on_status
        self.team_stats: Dict[str, dict] = {}
        self._patcher = _LibPatcher(cache_dir, on_status=on_status)

    def analyze_rom(self, rom_path: str) -> RomInfo:
        """Validate ROM and read team slots."""
        try:
            return self._patcher.analyze_rom(Path(rom_path))
        except RomError:
            # A file that cannot be opened at all. The old code answered with an
            # invalid `NBALive95RomInfo`; the call sites read `is_valid` and
            # nothing else, but one of them stores the object before testing it.
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
        """Fetch all NBA team rosters + stats.

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

        Sorted by team code so a patch run is reproducible:
        `MODERN_NBA_TO_NBALIVE95` collapses 34 codes onto 27 slots — GS/GSW,
        BKN/NJN, NYK/NY, SA/SAS, OKC/SEA, UTA/UTAH and WAS/WSH alias — so which
        of a colliding pair wins depends on iteration order.

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
                name="NBA",
                country="USA",
                country_code="US",
                season=0,
                teams_count=len(teams),
            ),
            teams=teams,
        )
