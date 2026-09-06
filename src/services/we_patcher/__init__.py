"""WE2002 patcher package — now a thin surface over `retro-roster-patcher`.

Everything except `WePatcher` and the two API clients is re-exported straight
from the library, so the names `app.py` imports from this package resolve to the
same classes the library's own patcher uses. `ApiFootballClient` has no library
equivalent and keeps coming from `services.sports_api`; `app.py` still imports
both clients from here.
"""

from retro_roster_patcher.games.we2002.afs_handler import AfsHandler  # noqa: F401
from retro_roster_patcher.games.we2002.csv_handler import CsvHandler  # noqa: F401
from retro_roster_patcher.games.we2002.models import (  # noqa: F401
    AfsEntry,
    League,
    LeagueData,
    Player,
    PlayerStats,
    RomInfo,
    SlotMapping,
    SlotPalette,
    Team,
    TeamRoster,
    WEPlayerAttributes,
    WEPlayerRecord,
    WETeamRecord,
    WETeamSlot,
)
from retro_roster_patcher.games.we2002.rom_reader import RomReader  # noqa: F401
from retro_roster_patcher.games.we2002.rom_writer import RomWriter  # noqa: F401
from retro_roster_patcher.games.we2002.stat_mapper import StatMapper  # noqa: F401
from retro_roster_patcher.games.we2002.tim_generator import TimGenerator  # noqa: F401

from .api_football import ApiFootballClient  # noqa: F401
from .espn_client import EspnClient  # noqa: F401
from .patcher import WePatcher  # noqa: F401
