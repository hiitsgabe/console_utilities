"""Language names for the WE2002 translation, re-exported from the library.

The PPF generators that used to live here are gone: `retro-roster-patcher` owns
them, and `WePatcher` reaches them through the library patcher rather than
through this package. What survives is the pair of names the UI reads —
`app.py`, `ui/screens/we_patcher_screen.py` and
`web_companion/state_serializer.py` all drive the language picker from them — so
the import path stays and the values now come from the same module that decides
which languages `patch_rom` will actually accept. Keeping a second copy here was
how the picker could come to offer a language the patcher would reject.

`ensure_ppf` is deliberately not re-exported. The library's signature is
`(cache_dir, lang, assets_dir)` where this package's was `(assets_dir, lang)`,
so a positional call written against the old one would quietly pass an assets
directory as the cache directory and generate the PPF into the wrong place.
Nothing in the app ever called it — the library patcher does it internally — so
the name is dropped rather than re-exported with a changed meaning.
"""

from retro_roster_patcher.games.we2002.translations.we2002 import (  # noqa: F401
    LANGUAGE_CODES,
    LANGUAGES,
)
