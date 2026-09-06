"""NHL 05 PS2 patcher — the app's adapter onto `retro-roster-patcher`.

Fetching, mapping and patching all live in the library now, in
`retro_roster_patcher.games.nhl05_ps2`. This module keeps the shape `app.py`
calls, which the library deliberately does not have:

- `fetch_rosters` returns `{team code: [Player]}` and leaves the per-team leader
  stats on `self.team_stats`. The library returns one `LeagueData` carrying
  both.
- `patch_rom` returns a `PatchResult` with `success` and `error`. The library
  raises instead.

`_league_data` is the load-bearing part, and the reason is not obvious from the
call sites. `app.py` builds a *second* patcher for the patch phase — `_fetch`
constructs one, `_patch` constructs another and re-injects
`patcher.team_stats = nhl.team_stats` — so no state survives on the instance
between the two. The `LeagueData` the library's `map_rosters` needs has to be
rebuilt from the roster dict plus that stats dict at patch time.

That reconstruction is lossy by design: `map_rosters` reads only `Team.code`
(to find the ROM slot), `players`, and `extra["leaders"]`, so every other `Team`
and `League` field is filler here. It is safe only because the UI never mutates
`nhl.rosters` — it reads `len()` and truthiness. A roster editor would have to
write back into what `_league_data` reads, or its edits would be dropped here in
silence.

`analyze_rom` goes to the library's reader rather than to the library patcher's
`analyze_rom`, which always validates deeply. Deep validation decompresses
`nhl2005.tdb` in full twice — once for a four-byte magic check, once for the
team names — and every call site here runs on the pygame main thread when the
user picks a ROM. That is a few megabytes of pure-Python RefPack per tap on a
handheld, where the shallow check is a memcmp. Keep the shallow default.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

from retro_roster_patcher.core.errors import RetroRosterError
from retro_roster_patcher.games.nhl05_ps2.models import NHL05RomInfo
from retro_roster_patcher.games.nhl05_ps2.patcher import (
    NHL05PS2Patcher as _LibPatcher,
)
from retro_roster_patcher.games.nhl05_ps2.rom_reader import NHL05PS2RomReader
from retro_roster_patcher.sports.models import League, LeagueData, Player, Team, TeamRoster


@dataclass
class PatchResult:
    """Result of a patch operation."""

    success: bool
    output_path: str = ""
    error: str = ""
    teams_patched: int = 0
    players_patched: int = 0


class NHL05PS2Patcher:
    """Main orchestrator for NHL 05 PS2 roster patching.

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

    def analyze_rom(self, iso_path: str, deep: bool = False) -> NHL05RomInfo:
        """Validate ISO and read team slots.

        Args:
            deep: If True, decompress TDB files for full validation (slow).
                  If False, just check BIGF header + use hardcoded teams (fast).
        """
        reader = NHL05PS2RomReader(str(iso_path))
        if not reader.load():
            return NHL05RomInfo(
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

        A provider that answers with no teams at all now raises `ApiError`
        rather than returning an empty dict; `app.py` catches it and shows the
        message, where before the screen just went quiet.
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

        Sorted by team code so a patch run is reproducible; `map_rosters` folds
        several modern abbreviations onto one ROM slot, and which of a colliding
        pair wins depends on iteration order.

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
