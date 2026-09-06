"""International Superstar Soccer (SNES) patcher — the app's import path.

The implementation now lives in `retro_roster_patcher.games.iss_snes`; this
package is the adapter plus the re-exports `app.py` imports by name.

`ISSRomReader` is the library's reader, re-exported rather than wrapped:
`app.py` bypasses the patcher at three sites — two ROM-selection paths and the
auto-detect validator — and calls `reader.get_rom_info()` and
`reader.validate_rom()` directly.

`validate_rom` is unchanged, so the `rom_valid` flag every ISS screen gates on
answers exactly as before. `get_rom_info` is stricter: the library's `is_valid`
also requires `data_fits()` and `signature_ok()`, and its `ISSTeamSlot` carries
`name` and the slot's `first_player` where the old one carried `current_name`
and `enum_name`. Neither reaches a user: `app.py` stores the result in
`state.iss_patcher.rom_info` and the only thing that reads it is a truthiness
test before `create_slot_mapping`, which a dataclass instance passes either way.

The old models, stat mapper and ROM writer are gone; nothing outside this
package imported them.
"""

from retro_roster_patcher.games.iss_snes.rom_reader import ISSRomReader  # noqa: F401

from .patcher import ISSPatcher  # noqa: F401

__all__ = ["ISSPatcher", "ISSRomReader"]
