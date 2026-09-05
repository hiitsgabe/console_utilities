"""NHL official API client (api-web.nhle.com) — no API key required.

The implementation now lives in the `retro-roster-patcher` library; this module
stays as the app's import path.

Provides historical rosters and per-player stats back to 1993-94, as the
alternative to ESPN for the four NHL patchers.
"""

from retro_roster_patcher.sports.nhl import BASE_URL, NhlApiClient  # noqa: F401
