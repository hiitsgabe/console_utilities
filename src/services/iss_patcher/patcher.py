"""International Superstar Soccer (SNES) — the app's adapter onto `retro-roster-patcher`.

Unlike the seven adapters that came before it, this one keeps the app's own
five-argument surface rather than the library's: `app.py` drives ISS through
`fetch_league` / `create_slot_mapping` / `patch_rom(rom, out, league_data,
slot_mapping)` and reads no `PatchResult`, so `patch_rom` still returns the
output path and still raises on failure. Everything below the surface is the
library's.

`client` is accepted and never read, and that is provably a no-op rather than a
dropped behaviour. `app.py` passes it at exactly one site
(`_start_iss_roster_fetch`) and only on the ESPN branch, where it hands over
`services.sports_api.espn_client.EspnClient(WE_PATCHER_CACHE_DIR,
on_status=on_status)`. That name is a re-export of
`retro_roster_patcher.sports.espn.EspnClient` — `scripts/_verify_sports_api_shim.py`
asserts the identity — and the library patcher builds
`EspnClient(str(cache_dir), on_status)` from the same `cache_dir` and the same
`on_status` this constructor was handed. Same class, same arguments, so
honouring the injection would buy nothing and add a way to feed the ISS patcher
a provider it does not support.

Behaviour differences from the old local code, all of them below the surface:

**The partial callback no longer fills in.** Both versions fire
`on_partial_data` once with a skeleton `LeagueData` whose teams are all
`loading=True`, so the team tiles still appear before any squad is fetched. The
old code then mutated *those same* `TeamRoster` objects as each squad arrived,
so the modal filled in team by team; the library builds fresh rosters and
publishes them only in its return value, so the skeleton stays "Loading..."
until the whole fetch finishes and `app.py` replaces `league_data` wholesale.
Progress text and the progress bar are unaffected. This is a regression in
feedback granularity and is not fixable here — reproducing it means
reimplementing `fetch`.

**`get_squad` is now given the season.** The old call was
`get_squad(team.id)`; the library passes `season` as well. ESPN's squad endpoint
has no season in its URL, so the squad returned is unchanged — the season only
enters the cache key, which is a correction: without it every season replayed
whichever one was fetched first.

**`patch_rom` refuses two ROMs the old code patched.** `ISSRomWriter` opens its
output `r+b` and seeks absolutely, and seeking past the end extends the file, so
the old code turned a too-small input into a 297 KB file of one hole and two
flag tiles. The library gates `patch` on `reader.data_fits()`. It also raises
rather than writing a negative-budget slice when the team-name-text pointer
table points at or past its 0x44478 ceiling. Both are deliberate corrections;
`app.py` shows the message.

**A slot mapping naming a team that is not in the league data now raises.** The
old loop skipped it silently. Unreachable from `app.py`, whose only mapping
comes from `create_slot_mapping` over the same `league_data`.

**Slots are patched in ascending order rather than in slot-mapping order.**
`write_team_name_texts` breaks a tie between two equally long names by whichever
it met first, so the old output depended on the order of the list handed in. The
library sorts. `create_slot_mapping` is sequential and ascending, so the two
agree on every mapping `app.py` can produce.
"""

from pathlib import Path
from typing import Any, Callable, List, Optional

from retro_roster_patcher.core.errors import RomError
from retro_roster_patcher.core.models import RomInfo, SlotMapping
from retro_roster_patcher.games.iss_snes.patcher import ISSPatcher as _LibPatcher
from retro_roster_patcher.sports.models import LeagueData


class ISSPatcher:
    """Orchestrator for International Superstar Soccer (SNES) roster patching.

    ESPN only; league ids are ESPN's. The ROM's 27 slots are national teams and
    the data source is a club league, so the slot assignment is arbitrary by
    construction — `create_slot_mapping` offers the sequential one the app has
    always used.
    """

    def __init__(
        self,
        cache_dir: str,
        on_status: Optional[Callable] = None,
        client: Any = None,
    ):
        # `client` is dead; see the module docstring for why it is still in the
        # signature and why ignoring it drops no behaviour.
        self.cache_dir = cache_dir
        self.on_status = on_status
        # Set for the duration of one `fetch_league` call and read by the
        # trampoline below. The library takes `on_partial` at construction,
        # `app.py` supplies it per call.
        self._on_partial_data: Optional[Callable[[LeagueData], None]] = None
        self._patcher = _LibPatcher(
            cache_dir,
            on_status=on_status,
            on_partial=self._emit_partial,
        )

    def _emit_partial(self, data: LeagueData) -> None:
        """Forward the library's one partial publication to this call's callback."""
        if self._on_partial_data is not None:
            self._on_partial_data(data)

    def fetch_league(
        self,
        league_id: int,
        season: int,
        on_progress: Optional[Callable[[float, str], None]] = None,
        on_partial_data: Optional[Callable[[LeagueData], None]] = None,
    ) -> LeagueData:
        """Fetch every team and squad in one league.

        `on_partial_data` fires once, with the teams known but no squads, so the
        caller can render tiles before the squad requests start.
        """
        self._on_partial_data = on_partial_data
        try:
            return self._patcher.fetch(
                season=season,
                league_id=league_id,
                on_progress=on_progress,
            )
        finally:
            # Cleared so a later fetch cannot publish into a stale callback.
            self._on_partial_data = None

    def analyze_rom(self, rom_path: str) -> RomInfo:
        """Validate a ROM and read its 27 team slots.

        `app.py` does not call this for ISS — both ROM-selection paths and the
        auto-detect path go straight to `ISSRomReader` — but it is part of the
        patcher surface, so it stays and answers the way the other shims do.
        """
        try:
            return self._patcher.analyze_rom(Path(rom_path))
        except RomError:
            # An unreadable file is not a distinction a caller here can act on:
            # the old code answered with an invalid `ISSRomInfo` rather than
            # raising, so answer with an invalid `RomInfo`.
            return RomInfo(
                path=str(rom_path),
                size=0,
                game_id=self._patcher.game_id,
                is_valid=False,
            )

    def create_slot_mapping(
        self, league_data: LeagueData, rom_info: Any
    ) -> List[SlotMapping]:
        """Map league teams to ROM slots sequentially: team *i* to slot *i*.

        Teams past the 27th are dropped. `rom_info` is unused and was unused by
        the old implementation too — every ISS ROM has the same 27 slots in the
        same order, so there is nothing in it to consult.

        These are the library's `SlotMapping`, not the old `ISSSlotMapping`. The
        two carry different fields, and nothing outside this package read the
        old ones: `slot_mapping_modal` renders `state.we_patcher.slot_mapping`
        and needs a `slot_mapping_highlighted` that `ISSPatcherState` does not
        have, and `real_team` / `slot_name` appear only under
        `services/we_patcher` and `services/pes6_ps2_patcher`. The app stores
        this list in `state.iss_patcher.slot_mapping` and hands it back to
        `patch_rom`, which is the only thing that reads it.
        """
        return self._patcher.default_slot_mapping(league_data)

    def patch_rom(
        self,
        rom_path: str,
        output_path: str,
        league_data: LeagueData,
        slot_mapping: List[SlotMapping],
        on_progress: Optional[Callable[[float, str], None]] = None,
    ) -> str:
        """Apply every patch and write the output ROM. Returns `output_path`.

        Raises on failure rather than returning a result object: that is the
        contract `app.py`'s ISS patch thread is written against, and it is the
        one place this game's surface differs from the other seven.
        """
        mapped = self._patcher.map_rosters(league_data, slot_mapping)
        result = self._patcher.patch(
            rom_path=Path(rom_path),
            output_path=Path(output_path),
            rosters=mapped,
            on_progress=on_progress,
        )
        return result.output_path
