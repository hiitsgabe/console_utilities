"""Local cache for user-assigned team colors.

The user picks primary and secondary colors from a palette; the choices are
persisted to a JSON file keyed by team ID so they don't need to be re-picked
each session.

The implementation now lives in `retro_roster_patcher.sports.team_colors`. This
module stays as the app's import path for the colour picker modal, the two
patcher screens and the web companion.
"""

from retro_roster_patcher.sports.team_colors import (  # noqa: F401
    COLOR_PALETTE,
    COLOR_PALETTE_RGB,
    all_teams_have_colors,
    apply_cached_colors,
    get_team_color,
    load_color_cache,
    save_color_cache,
    set_team_color,
)
