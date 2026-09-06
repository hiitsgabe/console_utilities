"""MVP Baseball PSP patcher — the app's adapter onto `retro-roster-patcher`.

Fetching, mapping and patching all live in the library now, in
`retro_roster_patcher.games.mvp_psp`. This module keeps the shape `app.py`
calls, which the library deliberately does not have:

- `fetch_rosters` returns `{team code: [Player]}` and leaves the per-team leader
  stats on `self.team_stats`. The library returns one `LeagueData` carrying
  both.
- `patch_rom` returns a `PatchResult` with `success` and `error`. The library
  raises instead.

`_league_data` is the load-bearing part, and the reason is not obvious from the
call sites. `app.py` builds a *second* patcher for the patch phase — the fetch
thread constructs one and reads `patcher.team_stats` off it, the patch thread
constructs another and re-injects `patcher.team_stats = mvp.team_stats` — so no
state survives on the instance between the two. The `LeagueData` the library's
`map_rosters` needs has to be rebuilt from the roster dict plus that stats dict
at patch time.

That reconstruction is lossy by design: `map_rosters` reads only `Team.code`
(to find the ROM slot), `players`, and `extra["leaders"]`, so every other `Team`
and `League` field is filler here. It is safe only because the UI never mutates
`mvp.rosters` — it reads `len()` and truthiness, and the roster-preview modal
builds its own separate `LeagueData` rather than round-tripping this one. A
roster editor would have to write back into what `_league_data` reads, or its
edits would be dropped here in silence.

There is no `provider` argument and there must not be one. MVP Baseball is
ESPN-only: ESPN is the only source of MLB rosters in the library, and the
library's patcher is registered `providers=("espn",)`. The keyword exists on the
library class and is left unset so the library picks its own default.

`analyze_rom` goes to the library's reader rather than to the library patcher's
`analyze_rom`, and the reason here is *not* the reason it is in the two NHL
shims. Those bypass a deep validation that decompresses megabytes of RefPack the
shallow path would never touch. That saving does not exist for this game:
`MVPPSPRomReader.get_info` decompresses and parses all nineteen sections on
either path, because that is where the team slots come from, so `deep=True`
costs one extra lookup in the already-parsed `team` table. Measured on this
machine against a fabricated 387 KB `database.big` (195 KB decompressed):
shallow 0.033 s, deep 0.030 s, the library's `analyze_rom` 0.031 s — three
numbers inside each other's noise. Do not repeat the NHL shims' timing argument
here; it is not true of this game.

The reasons that do apply are behavioural, and both are about not smuggling a
change into a migration:

- `is_valid` would get narrower. The library's `analyze_rom` decides on
  `validate_deep`, which additionally requires the disc's `team` table to hold
  at least one of the thirty known MVP team hashes. `patch` does not require
  that — it checks the `database.big` extent and the shallow header — so a disc
  failing the heuristic would be refused by the UI, which gates the patch button
  on `rom_valid`, while the patch itself would have worked. The old code decided
  on the three-byte `validate`, and so does this.
- The return type and the failure mode would change. This method is annotated
  `MVPRomInfo` and the library's `analyze_rom` returns the core `RomInfo`; it
  also takes a `Path` and raises `RomError` for a file it cannot read, where the
  old code returned `MVPRomInfo(size=0)`. `app.py` reads only `.is_valid` and
  wraps every call site in `except Exception`, so none of that reaches a user —
  which is an argument for not paying for it, not an argument that it is fine.

What the shallow path gives up is that `team`-table heuristic: a file that is
some other EA PSP disc, with a RefPack stream at offset 0 and another at offset
324, is called valid here and fails later inside `patch` with the writer's
message instead of at ROM-selection time. That is what the old code did.

Four behaviour differences from the old local code, all deliberate:

`team_stats` now exists from construction. The old class only created it inside
`fetch_rosters`, so reading it first raised `AttributeError`; `app.py` works
around that with `getattr(patcher, "team_stats", {})`. Initialising it is a
widening — the workaround still returns the same `{}`.

`fetch_rosters` raises `ApiError` when the provider answers with no teams, or
with no team that maps to a ROM slot, where the old code returned an empty dict
and the screen went quiet.

The squad request now carries the season. The old code called
`get_baseball_squad(team.id)` with no season, and the ESPN client puts the
season in its *cache key* but not in the squad URL, so the first season a user
ever fetched was served back for every later one. The library passes it, so
rosters for a non-current season change — for the better.

A patch that cannot be stored now fails instead of silently succeeding. MVP's
sections sit at fixed offsets with no length word, so a rebuilt table that
compresses larger than its allocation cannot be written at all. The old writer
did `continue`: it kept the original section, dropped every edit to that table,
and still returned `success=True`. The library raises `SectionTooLargeError`,
which is a `RetroRosterError`, so it arrives here as `success=False` with a
message naming the table and the shortfall.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

from retro_roster_patcher.core.errors import RetroRosterError
from retro_roster_patcher.games.mvp_psp.models import MVPRomInfo
from retro_roster_patcher.games.mvp_psp.patcher import (
    MVPPSPPatcher as _LibPatcher,
)
from retro_roster_patcher.games.mvp_psp.rom_reader import MVPPSPRomReader
from retro_roster_patcher.sports.models import League, LeagueData, Player, Team, TeamRoster


@dataclass
class PatchResult:
    """Result of a patch operation."""

    success: bool
    output_path: str = ""
    error: str = ""
    teams_patched: int = 0
    players_patched: int = 0


class MVPPSPPatcher:
    """Main orchestrator for MVP Baseball PSP roster patching.

    One provider, unlike the NHL patchers: ESPN is the only source of MLB
    rosters in the library, so there is nothing for a user to choose and no
    `provider` argument.
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

    def analyze_rom(self, iso_path: str) -> MVPRomInfo:
        """Validate ISO and read team slots.

        The shallow three-byte check, through the library's reader rather than
        its patcher's `analyze_rom`. See the module docstring for why.
        """
        reader = MVPPSPRomReader(iso_path)
        if not reader.load():
            return MVPRomInfo(path=iso_path, size=0)
        return reader.get_info()

    def fetch_rosters(
        self,
        on_progress: Optional[Callable[[float, str], None]] = None,
        season: int = 2025,
    ) -> Dict[str, List[Player]]:
        """Fetch all MLB team rosters + stats.

        Returns dict mapping team abbreviation to player list.
        Also populates self.team_stats for use during patching.

        A provider that answers with no teams, or with no team holding a ROM
        slot, now raises `ApiError` rather than returning an empty dict;
        `app.py` catches it and shows the message, where before the screen just
        went quiet.
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

        Sorted by team code so a patch run is reproducible: `MODERN_MLB_TO_MVP`
        collapses 32 provider codes onto 30 slots — `OAK`/`ATH` and `CWS`/`CHW`
        — so which of a colliding pair wins depends on iteration order.

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
                name="MLB",
                country="USA",
                country_code="US",
                season=0,
                teams_count=len(teams),
            ),
            teams=teams,
        )
