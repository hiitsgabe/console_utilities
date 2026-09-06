"""NHL 94 SNES patcher — the app's adapter onto `retro-roster-patcher`.

Same adapter as `services.nhl05_ps2_patcher.patcher` and
`services.nhl07_psp_patcher.patcher`, and for the same reason: `app.py` builds
one patcher for the fetch and a second one for the patch, keeping the result as
a `{team code: [Player]}` dict plus a separate `team_stats` dict, so the
`LeagueData` the library's `map_rosters` wants has to be rebuilt from those two
dicts at patch time. See `nhl05_ps2` for the full argument about what that
rebuild drops.

Two differences from the old local code, the same two the other two hockey
adapters have:

`team_stats` now exists from construction. The old class only created it inside
`fetch_rosters`, so reading it first raised `AttributeError`; `app.py` works
around that with `getattr(patcher, "team_stats", {})`. Initialising it is a
widening — the workaround still returns the same `{}`.

`fetch_rosters` raises `ApiError` when the provider answers with no teams, or
when no team it answered with has an NHL94 ROM slot, where the old code returned
an empty dict and the screen went quiet.

One difference specific to this game, and it is a library correction rather than
an adapter choice. The old code wrote the team header from the forward and
defenceman counts it read out of the ROM, whatever the writer had actually
managed to fit into the team's region. The library clamps them to the records
that reached the image (`rom_writer.header_counts`), because the line table
indexes players by absolute position and a header claiming more forwards than
were written names records that are not there. The two agree byte for byte
whenever the whole selection fits, which is the case for any ROM whose existing
records are at least as long as the ones being written.

`analyze_rom` delegates to the library's `analyze_rom` rather than dropping to
the reader, which is where the NHL 05 and NHL 07 adapters had to go. Those two
bypass it because the library validates deeply there, and deep validation means
decompressing megabytes of RefPack on the pygame main thread at every ROM
selection tap. Nothing of the sort exists here: a SNES image is 1 MB, has no
compression, and the library's extra work over the old code is 28 pointer
dereferences plus 28 single-byte reads. Measured on this machine over the
synthetic 1 MB fixture, 0.66 ms for the old path against 0.70 ms for the
library's — the cost is dominated by reading the file, which both do. So the
stricter check is worth having: the old `is_valid` was a file-size test alone
and would greenlight an image with no bank $9C in it at all, which then fails at
patch time. `RomError` is caught and turned back into `is_valid=False` because
the app-facing contract is a result object, not an exception; `app.py` swallows
it either way, but the return type stays what every call site expects.

The app-facing signature keeps its single argument. The library's `analyze_rom`
has no `deep` flag for this game and neither did the old local one.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

from retro_roster_patcher.core.errors import RetroRosterError, RomError
from retro_roster_patcher.core.models import RomInfo
from retro_roster_patcher.games.nhl94_snes.models import TEAM_COUNT
from retro_roster_patcher.games.nhl94_snes.patcher import (
    NHL94SNESPatcher as _LibPatcher,
)
from retro_roster_patcher.games.nhl94_snes.rom_reader import NHL94SNESRomReader
from retro_roster_patcher.sports.models import League, LeagueData, Player, Team, TeamRoster


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
        self.team_stats: Dict[str, dict] = {}
        self._patcher = _LibPatcher(
            cache_dir,
            provider=provider,
            on_status=on_status,
        )

    def analyze_rom(self, rom_path: str) -> RomInfo:
        """Validate ROM and read team slots."""
        try:
            return self._patcher.analyze_rom(Path(rom_path))
        except RomError:
            # A file that cannot be opened at all. The old code answered with an
            # invalid `NHL94RomInfo`; the call sites read `is_valid` and nothing
            # else, but one of them stores the object before testing it.
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
        options = {}
        counts = self._roster_counts(rom_path)
        if counts is not None:
            options["roster_counts"] = counts

        try:
            mapped = self._patcher.map_rosters(self._league_data(rosters), **options)
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

    def _roster_counts(self, rom_path: str) -> Optional[List[List[int]]]:
        """The (goalies, forwards, defencemen) triple each ROM slot is cut to.

        This game is the one hockey adapter that has to hand `map_rosters`
        something beyond the league data, and getting it wrong is silent:
        without it the library falls back to `(2, 14, 7)` for all 28 slots,
        which is a different roster for every team the ROM composes differently,
        and a header byte to match. Byte 17 of a team block packs the forward
        count in its high nibble and the defenceman count in its low one;
        goalies are never encoded and are always 2.

        Read straight from the library's reader rather than from `analyze_rom`'s
        `extra["roster_counts"]`, because `analyze_rom` publishes them only for
        an image that also passes its structural check, while `patch`
        deliberately does not apply that check. Routing them through it would
        quietly downgrade a patchable-but-unusual image to the defaults.

        `None` means the file could not be read, and then the argument is left
        off entirely so the library applies its own documented default rather
        than this module keeping a second copy of it. Nothing is lost: `patch`
        re-opens the same file a moment later and raises `RomError`.
        """
        reader = NHL94SNESRomReader(str(rom_path))
        if not reader.load():
            return None
        return [list(reader.read_team_player_counts(i)) for i in range(TEAM_COUNT)]

    def _league_data(self, rosters: Dict[str, List[Player]]) -> LeagueData:
        """Rebuild the library's `LeagueData` from the app's two state fields.

        Sorted by team code so a patch run is reproducible: `MODERN_NHL_TO_NHL94`
        collapses 30 codes onto 26 slots — LAK/LA, NJD/NJ, SJS/SJ and TBL/TB
        alias — so which of a colliding pair wins depends on iteration order.

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
