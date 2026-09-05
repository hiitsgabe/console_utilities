"""ROM auto-detect service for sport patchers.

The implementation now lives in the `retro-roster-patcher` library; this module
stays as the app's import path so the ten patcher screens keep working
unchanged.

The private helpers are re-exported deliberately: `app.py` imports
`_resolve_cue_track1` directly, and `tests/test_rom_finder.py` loads this file by
path and reaches for `_fuzzy_score` and `_normalize`.
"""

from retro_roster_patcher.rom_finder import (  # noqa: F401
    RomFinder,
    RomFinderConfig,
    RomFinderResult,
    _fuzzy_score,
    _normalize,
    _resolve_cue_track1,
    _tiebreak_sort_key,
)
