"""Prove the sports_api shims resolve into the library, not into local copies.

Not a pytest file on purpose: it runs the app's real import path, and importing
`src/nsz` under pytest's argv kills collection. Run it as

    .venv/bin/python scripts/_verify_sports_api_shim.py

Two things are checked, and the second is the one that matters. Identity of the
re-exported names proves nothing on its own -- a stale duplicate class would
still be *a* class. So every consumer that touches these types is imported too,
and each is asserted to have landed on the library's module, by
`__module__`/`__file__` and not by name.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import retro_roster_patcher.sports.espn as lib_espn  # noqa: E402
import retro_roster_patcher.sports.models as lib_models  # noqa: E402
import retro_roster_patcher.sports.nhl as lib_nhl  # noqa: E402

from services.sports_api import espn_client, models, nhl_api_client  # noqa: E402

failures = []


def same(label, got, want):
    if got is not want:
        failures.append(f"{label}: {got!r} is not {want!r}")


for name in ("League", "LeagueData", "Player", "PlayerStats", "Team", "TeamRoster"):
    same(f"models.{name}", getattr(models, name), getattr(lib_models, name))

same("espn_client.EspnClient", espn_client.EspnClient, lib_espn.EspnClient)
same("espn_client._ID_TO_LEAGUE", espn_client._ID_TO_LEAGUE, lib_espn._ID_TO_LEAGUE)
same("nhl_api_client.NhlApiClient", nhl_api_client.NhlApiClient, lib_nhl.NhlApiClient)

# The consumers. Each entry is (module path, attribute, expected library module).
CONSUMERS = [
    ("services.we_patcher.espn_client", "EspnClient", lib_espn),
    ("services.pes6_ps2_patcher.patcher", "EspnClient", lib_espn),
    ("services.iss_patcher.stat_mapper", "Player", lib_models),
    # Every migrated game has dropped out of this list, and that is the point:
    # its stat_mapper is gone, folded into the library, so there is no local
    # copy left to have drifted. Gone so far: nhl05_ps2, nhl07_psp, nhl94_snes,
    # nhl94_genesis, nbalive95, kgj_mlb, mvp_psp. What remains is we2002 and
    # iss_snes, not yet migrated, plus pes6_ps2, which has no library game.
]

for module_path, attribute, expected in CONSUMERS:
    __import__(module_path)
    obj = getattr(sys.modules[module_path], attribute)
    same(f"{module_path}.{attribute}", obj, getattr(expected, attribute))

if failures:
    print("FAIL")
    for line in failures:
        print("  " + line)
    sys.exit(1)

print(f"OK: {6 + 3 + len(CONSUMERS)} names all resolve into retro_roster_patcher")
print("  models   ->", lib_models.__file__)
print("  espn     ->", lib_espn.__file__)
print("  nhl      ->", lib_nhl.__file__)
