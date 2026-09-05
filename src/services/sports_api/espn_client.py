"""ESPN's public API — no key, no rate limits.

The implementation now lives in the `retro-roster-patcher` library; this module
stays as the app's import path.

`_ID_TO_LEAGUE` is re-exported deliberately: `services/pes6_ps2_patcher` has no
library equivalent, stays local, and resolves a league code through it.

One signature widened in a way that could bite silently. The soccer squad call
used to be `get_squad(team_id, league_code=None)` and is now
`get_squad(team_id, season=None, league_code=None)`, so a second *positional*
argument is read as a season and the league code goes missing — which returns an
empty squad rather than raising. Every call site in this repo already passes
`league_code=` by keyword; keep it that way.
"""

from retro_roster_patcher.sports.espn import (  # noqa: F401
    ESPN_LEAGUES,
    NHL_TEAM_MAP,
    EspnClient,
    _ID_TO_LEAGUE,
)
