"""Shared data models for sports API clients.

The implementation now lives in the `retro-roster-patcher` library; this module
stays as the app's import path so the patcher screens and the not-yet-migrated
local patchers keep working unchanged.

Re-exported rather than duplicated, and that is the point: `app.py` builds a
`LeagueData` for the roster-preview modal out of `Player` objects a library
patcher fetched. Two structurally identical dataclasses declared in two modules
are still different classes, so `isinstance` and `==` would quietly disagree.

The library's definitions are a strict widening of the ones that used to live
here. Every field kept its name, type and position; the library only added
defaults, plus `TeamRoster.extra` and `PlayerStats.unsupplied`. Keyword and
positional construction both still work.
"""

from retro_roster_patcher.sports.models import (  # noqa: F401
    League,
    LeagueData,
    Player,
    PlayerStats,
    Team,
    TeamRoster,
)
