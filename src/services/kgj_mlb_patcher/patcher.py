"""Ken Griffey Jr. MLB (SNES) patcher — the app's adapter onto `retro-roster-patcher`.

Same adapter as `services.nhl05_ps2_patcher.patcher` and
`services.nhl07_psp_patcher.patcher`, and for the same reason: `app.py` builds
one patcher for the fetch and a second one for the patch, keeping the result as
a `{team code: [Player]}` dict plus a separate `team_stats` dict, so the
`LeagueData` the library's `map_rosters` wants has to be rebuilt from those two
dicts at patch time. See `services.nhl05_ps2_patcher.patcher` for the full
argument.

This game is ESPN-only, so there is no `provider` argument here and none is
passed on. The library patcher declares `providers=("espn",)` and defaults to
it; forwarding `provider="espn"` would buy nothing and add one more way for a
typo in `app.py` to raise `CapabilityError`.

`analyze_rom` delegates to the library patcher, unlike the two NHL shims, which
deliberately bypass it. Those bypass because the library's deep validation
decompresses megabytes of RefPack on the pygame main thread at every ROM
selection. Nothing of the kind exists here: the ROM is 2 MB and uncompressed,
and the library's `analyze_rom` is the same `KGJRomReader.load` + `get_info` the
old code ran plus `_team_data_fits`, which is one comparison. Measured on this
machine against the synthetic fixture, 1.3 ms for the library call and 1.3 ms
for the bare reader — both of them the 2 MB `f.read()`. With nothing to save,
delegating is the better choice, because it keeps the ROM-validity rule in one
place rather than two.

Three behaviour differences from the old local code:

`team_stats` now exists from construction. The old class only created it inside
`fetch_rosters`, so reading it first raised `AttributeError`; `app.py` works
around that with `getattr(patcher, "team_stats", {})`. Initialising it is a
widening — the workaround still returns the same `{}`.

`fetch_rosters` raises `ApiError` when ESPN answers with no teams, or with no
team that maps to a 1994 ROM slot, where the old code returned an empty dict and
the screen went quiet. `app.py` catches it and shows the message.

`analyze_rom` rejects one ROM the old code accepted, and that is the library's
deliberate correction rather than a regression. `KGJRomReader.validate` bounds
neither where the 14-byte team marker may match nor how much file follows it, so
an image matching it within 25 280 bytes of the end used to report
`is_valid=True` — and the patch then "succeeded" having written nothing, because
every `write_player` past the end of the file answers False in silence. The
library folds `_team_data_fits` into `is_valid`, and its `patch` raises
`RomError` for the same image.

`analyze_rom` otherwise keeps the old signature and the old missing-file answer.
The library raises `RomError` for a file it cannot read, because its CLI probes
every registered patcher against one ROM and needs to tell "not this game" from
"not a file". `app.py` has no use for that distinction — two call sites per game
run this on the pygame main thread when a ROM is picked, and both read only
`is_valid` — so the error is turned back into the invalid `RomInfo` the old code
returned.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

from retro_roster_patcher.core.errors import RetroRosterError, RomError
from retro_roster_patcher.core.models import RomInfo
from retro_roster_patcher.games.kgj_mlb_snes.patcher import (
    KGJMLBPatcher as _LibPatcher,
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


class KGJMLBPatcher:
    """Main orchestrator for KGJ MLB roster patching.

    ESPN only; the game has no historical provider. The ROM's 28 slots are the
    1994 league, so Arizona and Tampa Bay have nowhere to go and are dropped
    before any request is made.
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
            # An unreadable file is not a distinction `app.py` can act on: it
            # reads `is_valid` and nothing else. Answer as the old code did.
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
        """Fetch all MLB team rosters + stats.

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

        Sorted by team code so a patch run is reproducible: `MODERN_MLB_TO_KGJ`
        folds 30 abbreviations onto 28 slots — CWS and CHW both name slot 3, OAK
        and ATH both name slot 10 — so which of a colliding pair wins depends on
        iteration order.

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
