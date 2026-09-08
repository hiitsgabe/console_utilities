"""Winning Eleven 2002 (PlayStation) — the app's adapter onto `retro-roster-patcher`.

The library's `WE2002Patcher` owns the ROM writer, the stat mapper, the
translation PPFs and the ESPN client; this class is only the shape `app.py`
already calls, mapped onto that. It is not the uniform adapter the other games
got: `patch_rom` returns a path and raises, rather than returning a
`PatchResult`, because that is what `app.py`'s WE2002 thread expects.

Deliberate differences from the local code this replaces:

`fetch_league` fetches from ESPN, the only roster source the app has. An
explicit `client=` is still honoured, and that is how `app.py` injects the
status-reporting `EspnClient`. The old code built an `ApiFootballClient` when no
client was passed; that provider is gone, along with the two error strings that
went with it, "Daily API limit reached" and "Rate limit reached". The library
reports every squad failure as `Failed to load squad: {exc}`, and neither limit
exists on ESPN.

`fetch_league` no longer clears `TeamRoster.loading` team by team. The old code
mutated the very rosters it had already handed to `on_partial_data`, so the UI
watched each tile resolve. The library publishes an immutable skeleton and
builds fresh rosters behind it, deliberately, so a caller can render the
skeleton without it changing underneath. The tiles therefore stay in their
loading state until `fetch_league` returns and `app.py` swaps the whole
`LeagueData` in. Progress text still advances per team.

`patch_rom` no longer writes the 63 national-team slots. The old code called
`RomWriter.write_nat_team` for every mapping with a `nat_index`; the library's
`patch` reaches only the 32 Master League slots, because its public
`SlotMapping` carries a single `slot_index` and the national table is addressable
only through `write_nat_team`. This is a regression, not a correction, and it is
the reason `create_slot_mapping` now leaves `nat_index` at `None` and labels
slots `ML n` rather than `Nat n + ML n`: a label promising a national write that
no longer happens is worse than the missing write. Restoring it belongs in the
library, not here — a second writer pass bolted on after `patch` would read its
TEX cache from the already-patched output and copy the wrong 3D jerseys.

`patch_rom` refuses a ROM under 100 MB instead of producing a 12 MB file. Every
write is an absolute seek into a 700 MB image and seeking past the end extends
the file, so the old code turned a wrong input into a plausible-looking output
holding nothing but the patch.

`patch_rom` raises on an unknown `language` rather than silently falling back to
English. `app.py` cycles `LANGUAGE_CODES`, so it cannot reach this.

Generated translation PPFs are written to `cache_dir/translations` instead of
into the repository's own `assets/translations`. The community
`w202-english.ppf` is still read from `assets/translations` if the user put one
there; the app never ships it.

`analyze_rom` goes to the library's `RomReader` rather than the library
patcher's `analyze_rom`. `app.py` reads the ROM through `RomReader` directly at
its other three sites, and the reader's `RomInfo` is the one the old code
returned: it carries `version`, `team_slots` and the 95 `slot_palettes`, where
the patcher's `analyze_rom` returns the interface-wide `RomInfo`, which has no
palettes. Both cost the same read.

`_last_verify_report` is wired up. The library's `patch` deliberately does not
call `verify_patches` — it returns prose and `PatchResult` has nowhere to put it
— but `app.py` does have somewhere: it reads the attribute after every patch,
stores it on `WePatcherState.patch_verify_report` and prints it. The report is
regenerated here from a second `RomWriter` pointed at the finished output. It
costs three file opens and roughly ten small seeks per patched slot, no full
re-read of the image, and it writes `error.log` beside the output, exactly as
the old code did. The attribute is cleared at the top of every `patch_rom`, so a
failed run cannot leave the previous run's report on the instance.
"""

import os
from pathlib import Path
from typing import Callable, List, Optional

from retro_roster_patcher.core.models import SlotMapping as _CoreSlotMapping
from retro_roster_patcher.games.we2002.csv_handler import CsvHandler
from retro_roster_patcher.games.we2002.models import LeagueData, RomInfo, SlotMapping
from retro_roster_patcher.games.we2002.patcher import MAX_ML_SLOTS
from retro_roster_patcher.games.we2002.patcher import WE2002Patcher as _LibPatcher
from retro_roster_patcher.games.we2002.rom_reader import RomReader
from retro_roster_patcher.games.we2002.rom_writer import RomWriter
from retro_roster_patcher.games.we2002.tim_generator import TimGenerator

# Read-only, and the only place the operator's own `w202-english.ppf` is looked
# for. Resolved from this file so it follows the package into a bundle. The file
# is never shipped: an absent directory just means the generated PPF is used.
_ASSETS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "assets", "translations")
)


class WePatcher:
    """Fetch, map and patch WE2002 rosters."""

    def __init__(self, cache_dir: str, on_status=None, client=None):
        self._patcher = _LibPatcher(
            cache_dir,
            on_status=on_status,
            assets_dir=_ASSETS_DIR,
        )
        if client is not None:
            # `app.py` injects an `EspnClient` built with its own status
            # callback. The library's `fetch` only ever calls `get_leagues`,
            # `get_teams`, `get_squad` and `get_player_stats` on it.
            self._patcher.api = client
        self.api = self._patcher.api
        self.mapper = self._patcher.mapper
        self.csv = CsvHandler()
        self.tim = TimGenerator()
        # Truthful from construction: `app.py` reads this with `getattr` after
        # every patch, and an absent attribute and a stale one look the same.
        self._last_verify_report = ""

    def fetch_league(
        self,
        league_id: int,
        season: int,
        on_progress: Optional[Callable[[float, str], None]] = None,
        on_partial_data: Optional[Callable[["LeagueData"], None]] = None,
    ) -> LeagueData:
        """Fetch every team and squad in a league.

        `on_partial_data` fires once, with a `LeagueData` whose teams are all
        `loading=True`, as soon as the team list is known — the library's
        `on_partial` hook, which is a constructor argument there and a per-call
        argument here, so it is rebound for the duration of the call.
        """
        previous = self._patcher.on_partial
        self._patcher.on_partial = on_partial_data
        try:
            return self._patcher.fetch(
                season=season,
                league_id=league_id,
                on_progress=on_progress,
            )
        finally:
            self._patcher.on_partial = previous

    def generate_csv(self, league_data: LeagueData, output_dir: str) -> str:
        """Export league data to CSV. Returns the CSV file path."""
        os.makedirs(output_dir, exist_ok=True)
        safe_name = league_data.league.name.replace(" ", "_").replace("/", "-")
        path = os.path.join(output_dir, f"{safe_name}_{league_data.league.season}.csv")

        we_records = []
        for team_roster in league_data.teams:
            we_team = self.mapper.map_team_with_league_context(
                team_roster, league_data.teams
            )
            we_records.append((team_roster.team.name, we_team.players))

        self.csv.export_league(league_data.league.name, we_records, path)
        return path

    def analyze_rom(self, rom_path: str) -> RomInfo:
        """Read the ROM and return its info, including the 32 team slots."""
        return RomReader(rom_path).get_rom_info()

    def create_slot_mapping(
        self, league_data: LeagueData, rom_info: RomInfo
    ) -> List[SlotMapping]:
        """Map league teams to Master League slots sequentially.

        Team 0 to slot 0, team 1 to slot 1, and so on, so teams appear in league
        order on the selection screen. Teams past the 32nd get `slot_index=32`,
        a sentinel `patch_rom` drops; the ROM has nowhere to put them.

        `rom_info` is unused and stays in the signature because `app.py` passes
        it: the slot layout is a property of the game, not of the image, and
        `RomReader.read_team_slots` returns the same 32 placeholders for every
        ROM.

        Returns the ROM-facing `SlotMapping`, the one carrying `real_team` and
        `slot_name`, because `slot_mapping_modal` renders both. `patch_rom`
        converts to the library's JSON-serialisable mapping on the way in.
        """
        mappings = []
        for i, tr in enumerate(league_data.teams):
            if i < MAX_ML_SLOTS:
                mappings.append(
                    SlotMapping(
                        real_team=tr.team,
                        slot_index=i,
                        slot_name=f"ML {i}",
                        nat_index=None,
                    )
                )
            else:
                mappings.append(
                    SlotMapping(
                        real_team=tr.team,
                        slot_index=MAX_ML_SLOTS,
                        slot_name=f"Team {i}",
                        nat_index=None,
                    )
                )
        return mappings

    def patch_rom(
        self,
        rom_path: str,
        output_path: str,
        league_data: LeagueData,
        slot_mapping: List[SlotMapping],
        on_progress: Optional[Callable[[float, str], None]] = None,
        language: str = "en",
    ) -> str:
        """Apply the translation and every roster patch. Returns `output_path`.

        Raises `RetroRosterError` — `RomError`, `MappingError` or
        `CapabilityError` — on failure; `app.py` catches it and shows the text.

        The translation PPF goes on first, then the ROM writer overwrites the 32
        Master League slots with the fetched team names, so the translation only
        survives where the roster patch does not reach.
        """
        # Never let a previous run's report survive a failure below.
        self._last_verify_report = ""

        known = {roster.team.id for roster in league_data.teams}
        # Kept in step: `entries` is what the library maps, `usable` the
        # matching ROM-facing mappings that the verification report describes.
        entries, usable = [], []
        for mapping in slot_mapping:
            # The old code skipped both of these silently rather than failing a
            # whole patch over one unplaceable team, and `create_slot_mapping`
            # produces the sentinel deliberately. `map_rosters` would raise.
            if not 0 <= mapping.slot_index < MAX_ML_SLOTS:
                continue
            if mapping.real_team.id not in known:
                continue
            entries.append(
                _CoreSlotMapping(
                    slot_index=mapping.slot_index,
                    team_id=mapping.real_team.id,
                    team_name=mapping.real_team.name,
                )
            )
            usable.append(mapping)

        rosters = self._patcher.map_rosters(league_data, entries)
        result = self._patcher.patch(
            rom_path=Path(rom_path),
            output_path=Path(output_path),
            rosters=rosters,
            on_progress=on_progress,
            language=language,
        )

        if on_progress:
            on_progress(0.95, "Verifying patches...")
        self._last_verify_report = self._verify(
            rom_path, result.output_path, usable, rosters.teams
        )
        if on_progress:
            on_progress(1.0, f"Done! Saved to {result.output_path}")
        return result.output_path

    @staticmethod
    def _verify(rom_path: str, output_path: str, slot_mapping, we_teams) -> str:
        """Re-derive the human-readable verification report for a finished patch.

        `verify_patches` is an instance method on the writer, and the library's
        `patch` builds and drops its own, so a writer has to be rebuilt over the
        finished output. Constructing it with `output_path` as both arguments is
        what keeps `RomWriter.__init__` from copying anything over the file that
        was just written.

        That constructor sets `_in_place`, whose only other use is to skip the
        original-versus-patched diff — the most useful phase of the report, and
        skipping it here would be an artefact of how this writer was built
        rather than something the caller asked for. Clearing it restores the
        method's own `original == output` test, which still skips the diff for a
        genuine in-place re-patch, which is exactly the old behaviour.
        """
        writer = RomWriter(output_path, output_path)
        writer._in_place = False
        return writer.verify_patches(rom_path, slot_mapping, we_teams)
