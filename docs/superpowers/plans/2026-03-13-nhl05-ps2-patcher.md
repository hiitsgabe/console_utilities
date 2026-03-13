# NHL 05 PS2 Roster Patcher Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add NHL 05 PS2 roster patching to console_utilities, reusing the existing ea_tdb.py BIGF/RefPack/TDB infrastructure from the NHL 07 PSP patcher.

**Architecture:** The NHL 05 PS2 patcher follows the identical architecture as `nhl07_psp_patcher/`: models → rom_reader → rom_writer → stat_mapper → patcher → screen. The key insight from research is that NHL 05 PS2 uses the exact same TDB format (DB\x00\x08 magic, bit-packed fields, RefPack compression, BIGF archives) with identical table names (SPBT, SPAI, SGAI, ROST, PLAY, STEA) and nearly identical field names. The `ea_tdb.py` library reads NHL 05 PS2 data without modification. The main differences are: (1) PS2 ISO path is `DB/DB.VIV` vs PSP's `PSP_GAME/USRDIR/DB/DB.VIV`, (2) NHL 05 has 94 teams (30 NHL + international + European leagues) vs 32, (3) master TDB filename is `nhl2005.tdb` vs `nhl2007.tdb`, (4) SPBT has extra fields (INTL, POSD, STIC, HBRA), (5) ROST has 69 line flag fields vs ~30, (6) team INDX 0-29 are identical to NHL 07, (7) NHL 05 has no separate `nhlbioatt.tdb` — all player data is in `nhl2005.tdb` and `nhlrost.tdb`.

**Tech Stack:** Python, ea_tdb.py (shared BIGF/RefPack/TDB library), ESPN/NHL API clients (shared), pygame-ce (UI)

---

## File Structure

### New files to create:
- `src/services/nhl05_ps2_patcher/__init__.py` — Module entry point
- `src/services/nhl05_ps2_patcher/models.py` — Team mappings, data models, constants
- `src/services/nhl05_ps2_patcher/rom_reader.py` — PS2 ISO reader (DB/DB.VIV path)
- `src/services/nhl05_ps2_patcher/rom_writer.py` — PS2 ISO writer
- `src/services/nhl05_ps2_patcher/stat_mapper.py` — Stats → NHL 05 attributes mapper
- `src/services/nhl05_ps2_patcher/patcher.py` — Main orchestrator
- `src/ui/screens/nhl05_ps2_patcher_screen.py` — Patcher UI screen
- `tests/test_nhl05_ps2_patcher.py` — Tests

### Files to modify:
- `src/state.py` — Add `NHL05PS2PatcherState` dataclass + state field
- `src/ui/screens/screen_manager.py` — Register new screen
- `src/ui/screens/systems_screen.py` — Add menu entry for NHL 05 PS2 patcher
- `src/app.py` — Add event handling for new patcher actions

### Shared files (no modification needed):
- `src/services/nhl07_psp_patcher/ea_tdb.py` — BIGF, RefPack, TDB library (import directly)
- `src/services/sports_api/espn_client.py` — ESPN API client
- `src/services/sports_api/nhl_api_client.py` — NHL API client
- `src/services/sports_api/models.py` — Shared Player/Team/League models

---

## Chunk 1: Core Service Layer

### Task 1: Models

**Files:**
- Create: `src/services/nhl05_ps2_patcher/models.py`
- Create: `src/services/nhl05_ps2_patcher/__init__.py`

- [ ] **Step 1: Create models.py with team mappings and data models**

NHL 05 PS2 team indices 0-29 are identical to NHL 07 PSP. The key data from ISO analysis:
- Master TDB: `nhl2005.tdb` (not `nhl2007.tdb`)
- Roster TDB: `nhlrost.tdb` (same as NHL 07)
- No separate `nhlbioatt.tdb` — all bio/attr data is in the master TDB
- 94 teams total: 0-29 NHL, 30-33 All-Stars, 34-53+95 International, 56-68+96 DEL, 70-81 SHL, 82-94 SM-liiga
- SPBT has 27 fields including extras: INTL, POSD, STIC, HBRA, STAT, ART_, DAY_
- SPAI has 26 fields including extras: PCBI, ODBI, SPBI (4-bit bias fields)
- SGAI has 23 fields including extras: POSI, PADL, STYL, FLOP, CONS
- ROST has 69 fields (vs 30 in NHL 07): includes 41LD, K1LD, L1LD, P1LD prefix variants
- POS_ field: 0=C, 1=LW, 2=RW, 3=D, 4=G (same as NHL 07)

```python
"""Data models for the NHL 05 PS2 patcher.

NHL 05 PS2 has 30 NHL teams + All-Star + National/European teams.
Roster data is in TDB tables inside a BIGF archive (db.viv) on the ISO.

Team indices 0-29 are identical to NHL 07 PSP.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from services.sports_api.models import (  # noqa: F401
    League,
    Player,
    PlayerStats,
    Team,
    TeamRoster,
    LeagueData,
)


# STEA table INDX → team abbreviation
# 30 NHL teams in NHL 05 (2004-05 season, same slots as NHL 07)
NHL05_TEAM_INDEX = {
    0: "ANA",
    1: "ATL",
    2: "BOS",
    3: "BUF",
    4: "CGY",
    5: "CAR",
    6: "CHI",
    7: "COL",
    8: "CBJ",
    9: "DAL",
    10: "DET",
    11: "EDM",
    12: "FLA",
    13: "LA",
    14: "MIN",
    15: "MTL",
    16: "NSH",
    17: "NJ",
    18: "NYI",
    19: "NYR",
    20: "OTT",
    21: "PHI",
    22: "PHX",
    23: "PIT",
    24: "SJ",
    25: "STL",
    26: "TB",
    27: "TOR",
    28: "VAN",
    29: "WSH",
    30: "EAS",
    31: "WES",
}

# Modern NHL abbreviation → STEA INDX
# NOTE: NHL 05 swaps SJ/STL compared to NHL 07 (SJ=24, STL=25 vs STL=24, SJ=25)
MODERN_NHL_TO_NHL05 = {
    "ANA": 0,
    "ATL": 1,
    "BOS": 2,
    "BUF": 3,
    "CGY": 4,
    "CAR": 5,
    "CHI": 6,
    "COL": 7,
    "CBJ": 8,
    "DAL": 9,
    "DET": 10,
    "EDM": 11,
    "FLA": 12,
    "LAK": 13,
    "LA": 13,
    "MIN": 14,
    "MTL": 15,
    "NSH": 16,
    "NJD": 17,
    "NJ": 17,
    "NYI": 18,
    "NYR": 19,
    "OTT": 20,
    "PHI": 21,
    "PHX": 22,
    "ARI": 22,
    "UTA": 22,
    "PIT": 23,
    "SJS": 24,
    "SJ": 24,
    "STL": 25,
    "TBL": 26,
    "TB": 26,
    "TOR": 27,
    "VAN": 28,
    "WSH": 29,
    # Expansion teams
    "WPG": 1,   # → Atlanta slot
    "VGK": 31,  # → WES All-Star slot
    "SEA": 30,  # → EAS All-Star slot
}

NHL05_TEAM_NAMES = [
    "Anaheim",      # 0
    "Atlanta",       # 1
    "Boston",        # 2
    "Buffalo",       # 3
    "Calgary",       # 4
    "Carolina",      # 5
    "Chicago",       # 6
    "Colorado",      # 7
    "Columbus",      # 8
    "Dallas",        # 9
    "Detroit",       # 10
    "Edmonton",      # 11
    "Florida",       # 12
    "Los Angeles",   # 13
    "Minnesota",     # 14
    "Montreal",      # 15
    "Nashville",     # 16
    "New Jersey",    # 17
    "NY Islanders",  # 18
    "NY Rangers",    # 19
    "Ottawa",        # 20
    "Philadelphia",  # 21
    "Phoenix",       # 22
    "Pittsburgh",    # 23
    "San Jose",      # 24
    "St. Louis",     # 25
    "Tampa Bay",     # 26
    "Toronto",       # 27
    "Vancouver",     # 28
    "Washington",    # 29
    "East All-Star", # 30
    "West All-Star", # 31
]

TEAM_COUNT = 30
MAX_PLAYERS_PER_TEAM = 30

POSITION_MAP = {
    0: "C",
    1: "LW",
    2: "RW",
    3: "D",
    4: "G",
}
POSITION_REVERSE = {v: k for k, v in POSITION_MAP.items()}

TDB_MASTER = "nhl2005.tdb"
TDB_ROSTER = "nhlrost.tdb"
# NHL 05 has no separate nhlbioatt.tdb — bios/attrs are in master TDB


@dataclass
class NHL05SkaterAttributes:
    """NHL 05 skater attributes (0-63 scale, 6-bit fields)."""

    balance: int = 30
    penalty: int = 30
    shot_accuracy: int = 30
    wrist_accuracy: int = 30
    faceoffs: int = 30
    acceleration: int = 30
    speed: int = 30
    potential: int = 30
    deking: int = 30
    checking: int = 30
    toughness: int = 30
    fighting: int = 1
    puck_control: int = 30
    agility: int = 30
    hero: int = 30
    aggression: int = 30
    pressure: int = 30
    passing: int = 30
    endurance: int = 30
    injury: int = 30
    slap_power: int = 30
    wrist_power: int = 30


@dataclass
class NHL05GoalieAttributes:
    """NHL 05 goalie attributes (0-63 scale, 6-bit fields)."""

    breakaway: int = 30
    rebound_ctrl: int = 30
    shot_recovery: int = 30
    speed: int = 30
    poke_check: int = 30
    intensity: int = 30
    potential: int = 30
    toughness: int = 30
    fighting: int = 1
    agility: int = 30
    five_hole: int = 30
    passing: int = 30
    endurance: int = 30
    glove_high: int = 30
    stick_high: int = 30
    glove_low: int = 30
    stick_low: int = 30


@dataclass
class NHL05PlayerRecord:
    """Complete player record ready to write to TDB tables."""

    first_name: str = ""
    last_name: str = ""
    position: str = "C"
    jersey_number: int = 1
    handedness: int = 1
    weight: int = 190
    height: int = 16
    team_index: int = 0
    player_id: int = 0
    is_goalie: bool = False
    skater_attrs: Optional[NHL05SkaterAttributes] = None
    goalie_attrs: Optional[NHL05GoalieAttributes] = None


@dataclass
class NHL05TeamSlot:
    """An existing team slot read from the TDB."""

    index: int
    name: str
    abbreviation: str


@dataclass
class NHL05RomInfo:
    """Information about a loaded NHL 05 PS2 ISO."""

    path: str
    size: int = 0
    team_slots: List[NHL05TeamSlot] = field(default_factory=list)
    is_valid: bool = False
```

- [ ] **Step 2: Create __init__.py**

```python
"""NHL 05 PS2 Patcher service.

Fetches NHL roster data and patches NHL 05 (PS2) ISOs with updated
player names, stats, jersey numbers, and roster assignments.
"""

from services.nhl05_ps2_patcher.patcher import NHL05PS2Patcher

__all__ = ["NHL05PS2Patcher"]
```

- [ ] **Step 3: Commit**

```bash
git add src/services/nhl05_ps2_patcher/__init__.py src/services/nhl05_ps2_patcher/models.py
git commit -m "feat(nhl05-ps2): add data models and team mappings"
```

---

### Task 2: ROM Reader

**Files:**
- Create: `src/services/nhl05_ps2_patcher/rom_reader.py`

The PS2 ISO uses standard ISO 9660. The DB.VIV path is `DB/DB.VIV` (flat, not nested under PSP_GAME). The reader can reuse the ISO 9660 traversal from `nhl07_psp_patcher/rom_reader.py` with a shorter path.

- [ ] **Step 1: Create rom_reader.py**

Key differences from NHL 07 PSP reader:
- `DB_VIV_PATH = "DB/DB.VIV"` (only 1 directory to traverse, not 3)
- `TDB_MASTER = "nhl2005.tdb"` (no separate `nhlbioatt.tdb`)
- Team reading uses different field names (NHL 05 STEA has `CONF` field, not just `LEAG`)
- Import ea_tdb from the nhl07_psp_patcher package (shared library)

```python
"""ROM reader for NHL 05 PS2 patcher.

Reads NHL 05 PS2 ISO to extract and parse TDB tables from db.viv.

ISO structure:
  Standard ISO 9660 → DB/db.viv (BIGF archive)
  → nhl2005.tdb, nhlrost.tdb (RefPack compressed TDB files)
"""

import os
import struct
from typing import Optional, List, Dict, Tuple

from services.nhl07_psp_patcher.ea_tdb import (
    bigf_extract,
    bigf_parse,
    refpack_decompress,
    TDBFile,
)
from services.nhl05_ps2_patcher.models import (
    NHL05RomInfo,
    NHL05TeamSlot,
    NHL05_TEAM_NAMES,
    NHL05_TEAM_INDEX,
    TEAM_COUNT,
    TDB_MASTER,
    TDB_ROSTER,
)

ISO_SECTOR_SIZE = 2048
ISO_PVD_OFFSET = 16 * ISO_SECTOR_SIZE


class NHL05PS2RomReader:
    """Reads and parses NHL 05 PS2 ISO data."""

    def __init__(self, iso_path: str):
        self.iso_path = iso_path
        self._iso_size = 0
        self._db_viv_data: Optional[bytes] = None
        self._tdb_files: Dict[str, TDBFile] = {}

    def load(self) -> bool:
        """Validate ISO and extract db.viv."""
        if not os.path.exists(self.iso_path):
            return False
        try:
            self._iso_size = os.path.getsize(self.iso_path)
            if self._iso_size < ISO_SECTOR_SIZE * 20:
                return False
            self._db_viv_data = self._extract_db_viv()
            return self._db_viv_data is not None
        except Exception:
            return False

    def validate(self, deep: bool = True) -> bool:
        """Validate that this is an NHL 05 PS2 ISO."""
        if not self._db_viv_data:
            return False
        if self._db_viv_data[:4] != b"BIGF":
            return False
        if not deep:
            return True
        try:
            raw = bigf_extract(self._db_viv_data, TDB_MASTER)
            if raw and len(raw) > 2 and raw[0] == 0x10 and raw[1] == 0xFB:
                decompressed = refpack_decompress(raw)
                if decompressed[:4] == b"DB\x00\x08":
                    return True
            if raw and raw[:4] == b"DB\x00\x08":
                return True
        except Exception:
            pass
        return False

    def get_info(self, deep: bool = True) -> NHL05RomInfo:
        """Get ROM information and team slots."""
        if not self._db_viv_data:
            return NHL05RomInfo(path=self.iso_path, size=0, is_valid=False)
        is_valid = self.validate(deep=deep)
        if is_valid and deep:
            team_slots = self._read_team_slots()
        elif is_valid:
            team_slots = [
                NHL05TeamSlot(
                    index=i,
                    name=NHL05_TEAM_NAMES[i],
                    abbreviation=NHL05_TEAM_INDEX.get(i, f"T{i}"),
                )
                for i in range(TEAM_COUNT)
            ]
        else:
            team_slots = []
        return NHL05RomInfo(
            path=self.iso_path,
            size=self._iso_size,
            team_slots=team_slots,
            is_valid=is_valid,
        )

    def get_tdb(self, filename: str) -> Optional[TDBFile]:
        """Get a parsed TDB file from db.viv (with caching)."""
        if filename in self._tdb_files:
            return self._tdb_files[filename]
        if not self._db_viv_data:
            return None
        raw = bigf_extract(self._db_viv_data, filename)
        if raw is None:
            return None
        if len(raw) > 2 and raw[0] == 0x10 and raw[1] == 0xFB:
            decompressed = refpack_decompress(raw)
        else:
            decompressed = raw
        tdb = TDBFile.parse(decompressed)
        self._tdb_files[filename] = tdb
        return tdb

    def get_db_viv(self) -> Optional[bytes]:
        """Get the raw db.viv data."""
        return self._db_viv_data

    def read_teams(self) -> List[NHL05TeamSlot]:
        """Read team information from STEA table."""
        return self._read_team_slots()

    def read_players(self) -> Dict[int, dict]:
        """Read player bios from SPBT table."""
        tdb = self.get_tdb(TDB_MASTER)
        if not tdb:
            return {}
        spbt = tdb.get_table("SPBT")
        if not spbt:
            return {}
        players = {}
        for i in range(spbt.num_records):
            try:
                rec = spbt.read_record(i)
                idx = rec.get("INDX", 0)
                if idx > 0:
                    players[idx] = rec
            except Exception:
                continue
        return players

    def read_roster(self) -> Dict[int, List[dict]]:
        """Read roster assignments from ROST table."""
        tdb = self.get_tdb(TDB_ROSTER)
        if not tdb:
            tdb = self.get_tdb(TDB_MASTER)
        if not tdb:
            return {}
        rost = tdb.get_table("ROST")
        if not rost:
            return {}
        rosters: Dict[int, List[dict]] = {}
        for i in range(rost.num_records):
            try:
                rec = rost.read_record(i)
                team = rec.get("TEAM", 127)
                if team < 64:
                    rosters.setdefault(team, []).append(rec)
            except Exception:
                continue
        return rosters

    def _extract_db_viv(self) -> Optional[bytes]:
        """Extract db.viv from the PS2 ISO.

        PS2 path: DB/DB.VIV (one directory deep, vs PSP's 3-deep path).
        """
        try:
            with open(self.iso_path, "rb") as f:
                f.seek(ISO_PVD_OFFSET)
                pvd = f.read(ISO_SECTOR_SIZE)
                if len(pvd) < ISO_SECTOR_SIZE or pvd[0] != 1:
                    return None
                root_rec = pvd[156:156 + 34]
                root_lba = struct.unpack_from("<I", root_rec, 2)[0]
                root_size = struct.unpack_from("<I", root_rec, 10)[0]

                # Navigate: root → DB
                result = self._find_dir_entry(f, root_lba, root_size, "DB")
                if result is None:
                    return None
                db_lba, db_size, is_dir = result
                if not is_dir:
                    return None

                # Find DB.VIV
                result = self._find_dir_entry(f, db_lba, db_size, "DB.VIV")
                if result is None:
                    return None
                file_lba, file_size, is_dir = result
                if is_dir:
                    return None

                f.seek(file_lba * ISO_SECTOR_SIZE)
                return f.read(file_size)
        except Exception:
            return None

    def _find_dir_entry(
        self, f, dir_lba: int, dir_size: int, name: str
    ) -> Optional[Tuple[int, int, bool]]:
        """Find a named entry in an ISO 9660 directory."""
        f.seek(dir_lba * ISO_SECTOR_SIZE)
        dir_data = f.read(dir_size)
        pos = 0
        name_upper = name.upper()
        while pos < len(dir_data):
            rec_len = dir_data[pos]
            if rec_len == 0:
                next_sector = ((pos // ISO_SECTOR_SIZE) + 1) * ISO_SECTOR_SIZE
                if next_sector >= len(dir_data):
                    break
                pos = next_sector
                continue
            if pos + rec_len > len(dir_data):
                break
            name_len = dir_data[pos + 32]
            if name_len > 0 and pos + 33 + name_len <= len(dir_data):
                entry_name = dir_data[pos + 33:pos + 33 + name_len].decode(
                    "ascii", errors="replace"
                )
                entry_name_clean = entry_name.split(";")[0].upper()
                if entry_name_clean == name_upper:
                    entry_lba = struct.unpack_from("<I", dir_data, pos + 2)[0]
                    entry_size = struct.unpack_from("<I", dir_data, pos + 10)[0]
                    is_dir = bool(dir_data[pos + 25] & 0x02)
                    return entry_lba, entry_size, is_dir
            pos += rec_len
        return None

    def _read_team_slots(self) -> List[NHL05TeamSlot]:
        """Read team slots from STEA table or use defaults."""
        slots = []
        tdb = self.get_tdb(TDB_MASTER)
        stea = tdb.get_table("STEA") if tdb else None

        if stea:
            for i in range(min(stea.num_records, 94)):
                try:
                    rec = stea.read_record(i)
                    indx = rec.get("INDX", i)
                    # Only include NHL teams (index 0-29)
                    if indx >= TEAM_COUNT:
                        continue
                    name = rec.get("FNME", "") or rec.get("SNME", "")
                    abbr = rec.get("ABBR", NHL05_TEAM_INDEX.get(indx, f"T{indx}"))
                    if not name:
                        name = (
                            NHL05_TEAM_NAMES[indx]
                            if indx < len(NHL05_TEAM_NAMES)
                            else f"Team {indx}"
                        )
                    slots.append(NHL05TeamSlot(index=indx, name=name, abbreviation=abbr))
                except Exception:
                    continue
            # Sort by index and fill gaps
            slots.sort(key=lambda s: s.index)
        else:
            for i in range(TEAM_COUNT):
                slots.append(
                    NHL05TeamSlot(
                        index=i,
                        name=NHL05_TEAM_NAMES[i],
                        abbreviation=NHL05_TEAM_INDEX.get(i, f"T{i}"),
                    )
                )
        return slots

    def find_db_viv_location(self) -> Tuple[int, int, int]:
        """Find the LBA, size, and available space for db.viv in the ISO."""
        try:
            with open(self.iso_path, "rb") as f:
                f.seek(ISO_PVD_OFFSET)
                pvd = f.read(ISO_SECTOR_SIZE)
                root_rec = pvd[156:156 + 34]
                root_lba = struct.unpack_from("<I", root_rec, 2)[0]
                root_size = struct.unpack_from("<I", root_rec, 10)[0]

                result = self._find_dir_entry(f, root_lba, root_size, "DB")
                if result is None:
                    return 0, 0, 0
                db_lba, db_size, _ = result

                db_lba2, db_size2, next_lba = self._find_entry_with_gap(
                    f, db_lba, db_size, "DB.VIV"
                )
                if db_lba2 == 0:
                    return 0, 0, 0
                if next_lba > db_lba2:
                    max_size = (next_lba - db_lba2) * ISO_SECTOR_SIZE
                else:
                    max_size = (
                        (db_size2 + ISO_SECTOR_SIZE - 1)
                        // ISO_SECTOR_SIZE
                        * ISO_SECTOR_SIZE
                    )
                return db_lba2, db_size2, max_size
        except Exception:
            return 0, 0, 0

    def find_db_viv_dir_entry_offset(self) -> int:
        """Find the absolute ISO byte offset of DB.VIV's directory record."""
        try:
            with open(self.iso_path, "rb") as f:
                f.seek(ISO_PVD_OFFSET)
                pvd = f.read(ISO_SECTOR_SIZE)
                root_rec = pvd[156:156 + 34]
                root_lba = struct.unpack_from("<I", root_rec, 2)[0]
                root_size = struct.unpack_from("<I", root_rec, 10)[0]

                result = self._find_dir_entry(f, root_lba, root_size, "DB")
                if result is None:
                    return 0
                db_lba, db_size, _ = result
                return self._find_dir_entry_abs_offset(f, db_lba, db_size, "DB.VIV")
        except Exception:
            return 0

    def _find_dir_entry_abs_offset(
        self, f, dir_lba: int, dir_size: int, name: str
    ) -> int:
        """Find the absolute ISO byte offset of a directory entry record."""
        f.seek(dir_lba * ISO_SECTOR_SIZE)
        dir_data = f.read(dir_size)
        pos = 0
        name_upper = name.upper()
        while pos < len(dir_data):
            rec_len = dir_data[pos]
            if rec_len == 0:
                next_sector = ((pos // ISO_SECTOR_SIZE) + 1) * ISO_SECTOR_SIZE
                if next_sector >= len(dir_data):
                    break
                pos = next_sector
                continue
            if pos + rec_len > len(dir_data):
                break
            name_len = dir_data[pos + 32]
            if name_len > 0 and pos + 33 + name_len <= len(dir_data):
                entry_name = dir_data[pos + 33:pos + 33 + name_len].decode(
                    "ascii", errors="replace"
                )
                entry_name_clean = entry_name.split(";")[0].upper()
                if entry_name_clean == name_upper:
                    return dir_lba * ISO_SECTOR_SIZE + pos
            pos += rec_len
        return 0

    def _find_entry_with_gap(
        self, f, dir_lba: int, dir_size: int, name: str
    ) -> Tuple[int, int, int]:
        """Find a file entry and the next file's LBA in the same directory."""
        f.seek(dir_lba * ISO_SECTOR_SIZE)
        dir_data = f.read(dir_size)
        pos = 0
        name_upper = name.upper()
        all_entries: List[Tuple[str, int, int]] = []
        while pos < len(dir_data):
            rec_len = dir_data[pos]
            if rec_len == 0:
                next_sector = ((pos // ISO_SECTOR_SIZE) + 1) * ISO_SECTOR_SIZE
                if next_sector >= len(dir_data):
                    break
                pos = next_sector
                continue
            if pos + rec_len > len(dir_data):
                break
            name_len = dir_data[pos + 32]
            if name_len > 1 and pos + 33 + name_len <= len(dir_data):
                entry_name = dir_data[pos + 33:pos + 33 + name_len].decode(
                    "ascii", errors="replace"
                )
                entry_name_clean = entry_name.split(";")[0].upper()
                entry_lba = struct.unpack_from("<I", dir_data, pos + 2)[0]
                entry_size = struct.unpack_from("<I", dir_data, pos + 10)[0]
                all_entries.append((entry_name_clean, entry_lba, entry_size))
            pos += rec_len
        all_entries.sort(key=lambda x: x[1])
        for i, (ename, elba, esize) in enumerate(all_entries):
            if ename == name_upper:
                next_lba = 0
                if i + 1 < len(all_entries):
                    next_lba = all_entries[i + 1][1]
                return elba, esize, next_lba
        return 0, 0, 0
```

- [ ] **Step 2: Commit**

```bash
git add src/services/nhl05_ps2_patcher/rom_reader.py
git commit -m "feat(nhl05-ps2): add PS2 ISO reader for DB.VIV extraction"
```

---

### Task 3: ROM Writer

**Files:**
- Create: `src/services/nhl05_ps2_patcher/rom_writer.py`

Nearly identical to NHL 07 PSP writer. Key differences:
- Imports from `nhl05_ps2_patcher.models` and `nhl05_ps2_patcher.rom_reader`
- NHL 05 ROST has 69 line flags (vs 30 in NHL 07)
- No `nhlbioatt.tdb` to update

- [ ] **Step 1: Create rom_writer.py**

```python
"""ROM writer for NHL 05 PS2 patcher.

Modifies TDB tables in db.viv and writes modified db.viv back to ISO.
"""

import os
import struct
from typing import Optional, Dict, Callable

from services.nhl07_psp_patcher.ea_tdb import (
    bigf_replace_inplace,
    refpack_compress,
    TDBFile,
)
from services.nhl05_ps2_patcher.rom_reader import (
    NHL05PS2RomReader,
    ISO_SECTOR_SIZE,
)
from services.nhl05_ps2_patcher.models import (
    NHL05PlayerRecord,
    NHL05SkaterAttributes,
    NHL05GoalieAttributes,
    POSITION_REVERSE,
)


# NHL 05 ROST line flag names (69 total — much more than NHL 07's 30)
LINE_FLAGS = [
    "31LD", "41LD", "K1LD", "L1LD", "P1LD",
    "32LD", "42LD", "K2LD", "L2LD", "P2LD", "L3LD",
    "31RD", "41RD", "K1RD", "L1RD", "P1RD",
    "32RD", "42RD", "K2RD", "L2RD", "P2RD", "L3RD",
    "41LW", "K1LW", "L1LW", "P1LW",
    "42LW", "K2LW", "L2LW", "P2LW", "L3LW", "L4LW",
    "L1RW", "P1RW", "L2RW", "P2RW", "L3RW", "L4RW",
    "31C_", "41C_", "K1C_", "L1C_", "P1C_",
    "32C_", "42C_", "K2C_", "L2C_", "P2C_", "L3C_", "L4C_",
    "G1__", "H1__", "S1__", "X1__",
    "G2__", "H2__", "S2__", "X2__",
    "H3__", "S3__", "H4__", "S4__", "H5__", "S5__",
]


class NHL05PS2RomWriter:
    """Writes player data to NHL 05 PS2 ISO."""

    def __init__(self, iso_path: str, output_path: str):
        self.iso_path = iso_path
        self.output_path = output_path
        self.reader: Optional[NHL05PS2RomReader] = None
        self._db_viv: Optional[bytes] = None
        self._last_error: str = ""
        self._last_traceback: str = ""

    def copy_iso(
        self, on_progress: Optional[Callable[[float, str], None]] = None
    ) -> bool:
        """Copy source ISO to output path with progress reporting."""
        try:
            src_size = os.path.getsize(self.iso_path)
            output_dir = os.path.dirname(self.output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            chunk_size = 4 * 1024 * 1024
            copied = 0
            with open(self.iso_path, "rb") as src, open(self.output_path, "wb") as dst:
                while True:
                    chunk = src.read(chunk_size)
                    if not chunk:
                        break
                    dst.write(chunk)
                    copied += len(chunk)
                    if on_progress and src_size > 0:
                        on_progress(
                            copied / src_size * 0.3,
                            f"Copying ISO... {copied // (1024 * 1024)}MB",
                        )
            return True
        except Exception:
            return False

    def load(self) -> bool:
        """Load the output ISO for modification."""
        self.reader = NHL05PS2RomReader(self.output_path)
        if not self.reader.load():
            return False
        self._db_viv = self.reader.get_db_viv()
        return self._db_viv is not None

    def write_player_bio(
        self, tdb: TDBFile, record_idx: int, player: NHL05PlayerRecord
    ):
        """Update a SPBT record with player bio data."""
        spbt = tdb.get_table("SPBT")
        if not spbt or record_idx >= spbt.capacity:
            return
        values = {
            "FNME": player.first_name[:15],
            "LNME": player.last_name[:15],
            "JERS": player.jersey_number,
            "HAND": player.handedness,
            "TEAM": player.team_index,
            "POS_": POSITION_REVERSE.get(player.position, 0),
        }
        if player.weight > 0:
            values["WEIG"] = player.weight
        if player.height > 0:
            values["HEIG"] = player.height
        spbt.write_record(record_idx, values)

    def write_skater_attrs(
        self, tdb: TDBFile, record_idx: int,
        attrs: NHL05SkaterAttributes, player_id: int = 0,
    ):
        """Update a SPAI record with skater attributes."""
        spai = tdb.get_table("SPAI")
        if not spai or record_idx >= spai.capacity:
            return
        values = {
            "BALA": attrs.balance, "PENA": attrs.penalty,
            "SACC": attrs.shot_accuracy, "WACC": attrs.wrist_accuracy,
            "FACE": attrs.faceoffs, "ACCE": attrs.acceleration,
            "SPEE": attrs.speed, "POTE": attrs.potential,
            "DEKG": attrs.deking, "CHKG": attrs.checking,
            "TOUG": attrs.toughness, "FIGH": attrs.fighting,
            "PUCK": attrs.puck_control, "AGIL": attrs.agility,
            "HERO": attrs.hero, "AGGR": attrs.aggression,
            "PRES": attrs.pressure, "PASS": attrs.passing,
            "ENDU": attrs.endurance, "INJU": attrs.injury,
            "SPOW": attrs.slap_power, "WPOW": attrs.wrist_power,
        }
        if player_id > 0:
            values["INDX"] = player_id
        spai.write_record(record_idx, values)

    def write_goalie_attrs(
        self, tdb: TDBFile, record_idx: int,
        attrs: NHL05GoalieAttributes, player_id: int = 0,
    ):
        """Update a SGAI record with goalie attributes."""
        sgai = tdb.get_table("SGAI")
        if not sgai or record_idx >= sgai.capacity:
            return
        values = {
            "BRKA": attrs.breakaway, "REBC": attrs.rebound_ctrl,
            "SREC": attrs.shot_recovery, "SPEE": attrs.speed,
            "POKE": attrs.poke_check, "INTE": attrs.intensity,
            "POTE": attrs.potential, "TOUG": attrs.toughness,
            "FIGH": attrs.fighting, "AGIL": attrs.agility,
            "5HOL": attrs.five_hole, "PASS": attrs.passing,
            "ENDU": attrs.endurance, "GSH_": attrs.glove_high,
            "SSH_": attrs.stick_high, "GSL_": attrs.glove_low,
            "SSL_": attrs.stick_low,
        }
        if player_id > 0:
            values["INDX"] = player_id
        sgai.write_record(record_idx, values)

    def write_roster_entry(
        self, tdb: TDBFile, record_idx: int,
        team_index: int, jersey: int, player_id: int,
        captain: int = 0, dressed: int = 1,
        line_flags: Optional[Dict[str, int]] = None,
    ):
        """Update a ROST record."""
        rost = tdb.get_table("ROST")
        if not rost or record_idx >= rost.capacity:
            return
        values = {
            "TEAM": team_index, "JERS": jersey,
            "INDX": player_id, "CAPT": captain, "DRES": dressed,
        }
        for flag in LINE_FLAGS:
            values[flag] = 0
        if line_flags:
            for flag, val in line_flags.items():
                if flag in LINE_FLAGS:
                    values[flag] = val
        rost.write_record(record_idx, values)

    def rebuild_and_write(
        self, modified_tdbs: Dict[str, TDBFile],
        on_progress: Optional[Callable[[float, str], None]] = None,
    ) -> bool:
        """Recompress modified TDB files, rebuild BIGF, write to ISO."""
        if not self._db_viv or not self.reader:
            return False
        try:
            new_viv = bytearray(self._db_viv)
            total = len(modified_tdbs)
            for i, (tdb_name, tdb_file) in enumerate(modified_tdbs.items()):
                if on_progress:
                    on_progress(0.3 + (i / max(total, 1)) * 0.4, f"Compressing {tdb_name}...")
                serialized = tdb_file.serialize()
                compressed = refpack_compress(serialized)
                bigf_replace_inplace(new_viv, tdb_name, compressed)

            if on_progress:
                on_progress(0.7, "Writing db.viv to ISO...")

            reader_for_loc = NHL05PS2RomReader(self.output_path)
            reader_for_loc.load()
            db_lba, db_orig_size, db_max_size = reader_for_loc.find_db_viv_location()
            if db_lba == 0:
                return False

            new_viv_bytes = bytes(new_viv)
            if len(new_viv_bytes) > db_max_size:
                self._last_error = (
                    f"New db.viv ({len(new_viv_bytes)} bytes) exceeds "
                    f"ISO allocation ({db_max_size} bytes)"
                )
                return False

            with open(self.output_path, "r+b") as f:
                f.seek(db_lba * ISO_SECTOR_SIZE)
                f.write(new_viv_bytes)
                remaining = db_orig_size - len(new_viv_bytes)
                if remaining > 0:
                    f.write(b"\x00" * remaining)

            new_size = len(new_viv_bytes)
            if new_size != db_orig_size:
                dir_entry_offset = reader_for_loc.find_db_viv_dir_entry_offset()
                if dir_entry_offset > 0:
                    with open(self.output_path, "r+b") as f:
                        f.seek(dir_entry_offset + 10)
                        f.write(struct.pack("<I", new_size))
                        f.seek(dir_entry_offset + 14)
                        f.write(struct.pack(">I", new_size))

            if on_progress:
                on_progress(1.0, "Complete")
            return True
        except Exception as e:
            self._last_error = str(e)
            import traceback
            self._last_traceback = traceback.format_exc()
            return False
```

- [ ] **Step 2: Commit**

```bash
git add src/services/nhl05_ps2_patcher/rom_writer.py
git commit -m "feat(nhl05-ps2): add PS2 ISO writer for db.viv patching"
```

---

### Task 4: Stat Mapper

**Files:**
- Create: `src/services/nhl05_ps2_patcher/stat_mapper.py`

Identical logic to NHL 07 PSP stat mapper — same 0-63 attribute scale, same stat sources. Uses NHL 05 model classes and team mappings.

- [ ] **Step 1: Create stat_mapper.py**

Copy the logic from `nhl07_psp_patcher/stat_mapper.py`, replacing:
- `NHL07SkaterAttributes` → `NHL05SkaterAttributes`
- `NHL07GoalieAttributes` → `NHL05GoalieAttributes`
- `NHL07PlayerRecord` → `NHL05PlayerRecord`
- `MODERN_NHL_TO_NHL07` → `MODERN_NHL_TO_NHL05`

The stat mapping formulas, defaults, and roster selection logic are identical since both games use the same 0-63 scale.

- [ ] **Step 2: Commit**

```bash
git add src/services/nhl05_ps2_patcher/stat_mapper.py
git commit -m "feat(nhl05-ps2): add stat mapper for NHL 05 attributes"
```

---

### Task 5: Patcher Orchestrator

**Files:**
- Create: `src/services/nhl05_ps2_patcher/patcher.py`

Same orchestration flow as NHL 07 PSP patcher. Key differences:
- No `nhlbioatt.tdb` — only write to master TDB and `nhlrost.tdb`
- Use NHL 05 model classes and team mappings
- NHL 05 ROST uses NHL 05's extended line flag set

- [ ] **Step 1: Create patcher.py**

Follow the same structure as `nhl07_psp_patcher/patcher.py`:
1. `analyze_rom()` — validate ISO + read team slots
2. `fetch_rosters()` — fetch from ESPN/NHL API
3. `map_rosters_to_nhl05()` — map API data to NHL 05 records
4. `patch_rom()` — copy ISO, extract db.viv, modify TDBs, write back

Key difference in `patch_rom()`: only two TDB files to modify (master + roster), no bioatt split.

- [ ] **Step 2: Commit**

```bash
git add src/services/nhl05_ps2_patcher/patcher.py
git commit -m "feat(nhl05-ps2): add patcher orchestrator"
```

---

## Chunk 2: UI Integration

### Task 6: State

**Files:**
- Modify: `src/state.py`

- [ ] **Step 1: Add NHL05PS2PatcherState dataclass**

Add after the `NHL07PSPPatcherState` class (around line 526). Same fields as NHL07PSPPatcherState but for NHL 05 PS2.

```python
@dataclass
class NHL05PS2PatcherState:
    """State for the NHL 05 PS2 Patcher feature."""

    selected_season: int = field(
        default_factory=lambda: (
            datetime.now().year
            if datetime.now().month >= 10
            else datetime.now().year - 1
        )
    )
    selected_league: Any = None

    rosters: Any = None
    team_stats: Any = None
    league_data: Any = None
    fetch_progress: float = 0.0
    fetch_status: str = ""
    is_fetching: bool = False
    fetch_error: str = ""

    rom_path: str = ""
    rom_info: Any = None
    rom_valid: bool = False
    zip_path: str = ""
    zip_temp_dir: str = ""

    patch_progress: float = 0.0
    patch_status: str = ""
    is_patching: bool = False
    patch_output_path: str = ""
    patch_complete: bool = False
    patch_error: str = ""

    roster_preview_team_index: int = 0
    roster_preview_player_index: int = 0
    active_modal: Optional[str] = None
    leagues_highlighted: int = 0
    roster_teams_highlighted: int = 0
    roster_players_highlighted: int = 0
```

Add field to `AppState.__init__` after `self.nhl07_psp_patcher`:

```python
self.nhl05_ps2_patcher = NHL05PS2PatcherState()
```

Add case to `get_patcher_state()`:

```python
if self.mode == "nhl05_patcher":
    return self.nhl05_ps2_patcher
```

- [ ] **Step 2: Commit**

```bash
git add src/state.py
git commit -m "feat(nhl05-ps2): add patcher state to AppState"
```

---

### Task 7: Patcher Screen

**Files:**
- Create: `src/ui/screens/nhl05_ps2_patcher_screen.py`

Follow the exact same pattern as `nhl07_psp_patcher_screen.py`. Change:
- Title: "NHL 05 (PS2) Patcher"
- State field: `state.nhl05_ps2_patcher`
- ISO extension filter: `.iso` (PS2 ISOs, same as PSP)

- [ ] **Step 1: Create the screen file**

Copy from `nhl07_psp_patcher_screen.py`, replacing all `nhl07_psp_patcher` references with `nhl05_ps2_patcher` and updating the title string.

- [ ] **Step 2: Commit**

```bash
git add src/ui/screens/nhl05_ps2_patcher_screen.py
git commit -m "feat(nhl05-ps2): add patcher screen UI"
```

---

### Task 8: Screen Manager + Systems Screen + App Integration

**Files:**
- Modify: `src/ui/screens/screen_manager.py` — Register new screen
- Modify: `src/ui/screens/systems_screen.py` — Add menu entry
- Modify: `src/app.py` — Add event handling

- [ ] **Step 1: Register screen in screen_manager.py**

Add import and registration following the NHL 07 PSP pattern. Look for where `nhl07_psp_patcher_screen` is registered and add the NHL 05 PS2 patcher screen below it. The mode key should be `"nhl05_patcher"`.

- [ ] **Step 2: Add menu entry in systems_screen.py**

Add a "NHL 05 (PS2)" entry in the systems/patchers list, near the NHL 07 PSP entry. The action should navigate to mode `"nhl05_patcher"`.

- [ ] **Step 3: Add event handling in app.py**

Search for `nhl07_patcher` or `nhl07_psp` handling blocks in `app.py` and replicate them for `nhl05_patcher`/`nhl05_ps2_patcher`. This includes:
- Fetch rosters action
- Select ROM action
- Patch ROM action
- Season change action
- Preview rosters action

- [ ] **Step 4: Commit**

```bash
git add src/ui/screens/screen_manager.py src/ui/screens/systems_screen.py src/app.py
git commit -m "feat(nhl05-ps2): integrate patcher into menu system and app"
```

---

### Task 9: Tests

**Files:**
- Create: `tests/test_nhl05_ps2_patcher.py`

- [ ] **Step 1: Write tests for models**

```python
def test_team_mapping():
    from services.nhl05_ps2_patcher.models import MODERN_NHL_TO_NHL05
    assert MODERN_NHL_TO_NHL05["BOS"] == 2
    assert MODERN_NHL_TO_NHL05["SJ"] == 24
    assert MODERN_NHL_TO_NHL05["STL"] == 25
    assert MODERN_NHL_TO_NHL05["WPG"] == 1  # → Atlanta slot
```

- [ ] **Step 2: Write tests for stat mapper**

```python
def test_stat_mapper_skater():
    from services.nhl05_ps2_patcher.stat_mapper import NHL05StatMapper
    from services.sports_api.models import Player
    mapper = NHL05StatMapper()
    player = Player(id=1, name="Test Player", position="C", number=97)
    record = mapper.map_player(player, "EDM")
    assert record.first_name == "Test"
    assert record.last_name == "Player"
    assert record.team_index == 11
    assert record.skater_attrs is not None
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/test_nhl05_ps2_patcher.py -v
```

- [ ] **Step 4: Commit**

```bash
git add tests/test_nhl05_ps2_patcher.py
git commit -m "test(nhl05-ps2): add unit tests"
```
