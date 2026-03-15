# PES 6 PS2 Patcher — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Patch PES 6 PS2 ISO team names and abbreviations from ESPN soccer league data, with league browser UI.

**Architecture:** New patcher service at `src/services/pes6_ps2_patcher/` following the NHL 05 PS2 pattern. Reads team name table from SLES executable in the ISO, maps ESPN teams to ROM slots by league range, writes new names in-place. UI reuses the league browser modal and list screen template from existing patchers.

**Tech Stack:** Python 3, pygame, ESPN soccer API (existing `espn_client.py`), ISO 9660 sector I/O.

**Spec:** `docs/superpowers/specs/2026-03-14-pes6-ps2-patcher-design.md`

---

## File Structure

### New files to create:
- `src/services/pes6_ps2_patcher/__init__.py` — Package exports
- `src/services/pes6_ps2_patcher/models.py` — Team slot mapping, ROM constants, data structures
- `src/services/pes6_ps2_patcher/rom_reader.py` — Read team names from ISO, validate PES 6 ISO
- `src/services/pes6_ps2_patcher/rom_writer.py` — Write patched team names to ISO copy
- `src/services/pes6_ps2_patcher/patcher.py` — Orchestrator: fetch + map + patch
- `src/ui/screens/pes6_ps2_patcher_screen.py` — Step-by-step UI screen
- `tests/test_pes6_ps2_patcher.py` — Unit tests for models, reader, writer

### Existing files to modify:
- `src/state.py` — Add `PES6PS2PatcherState` dataclass + field on `AppState`
- `src/ui/screens/sports_patcher_screen.py` — Add PES 6 to GAMES list
- `src/ui/screens/screen_manager.py` — Add PES 6 screen rendering + modal checks
- `src/app.py` — Add navigation, selection, back handlers, folder browser, patching thread

---

## Chunk 1: Models + ROM Reader

### Task 1: Create models.py with team slot constants

**Files:**
- Create: `src/services/pes6_ps2_patcher/__init__.py`
- Create: `src/services/pes6_ps2_patcher/models.py`
- Test: `tests/test_pes6_ps2_patcher.py`

- [ ] **Step 1: Write tests for team slot mapping**

```python
# tests/test_pes6_ps2_patcher.py
"""Tests for PES 6 PS2 patcher models and utilities."""

import pytest


class TestPES6Models:
    """Test team slot constants and mappings."""

    def test_league_ranges_defined(self):
        from services.pes6_ps2_patcher.models import LEAGUE_RANGES

        assert "epl" in LEAGUE_RANGES
        assert "ligue1" in LEAGUE_RANGES
        assert "serie_a" in LEAGUE_RANGES
        assert "eredivisie" in LEAGUE_RANGES
        assert "la_liga" in LEAGUE_RANGES

    def test_epl_range(self):
        from services.pes6_ps2_patcher.models import LEAGUE_RANGES

        epl = LEAGUE_RANGES["epl"]
        assert epl["start"] == 88
        assert epl["end"] == 108
        assert epl["count"] == 20

    def test_total_team_count(self):
        from services.pes6_ps2_patcher.models import TOTAL_TEAMS

        assert TOTAL_TEAMS == 277

    def test_sles_team_offset(self):
        from services.pes6_ps2_patcher.models import SLES_TEAM_NAMES_START

        # National teams start around this offset
        assert SLES_TEAM_NAMES_START > 0x2DD000

    def test_custom_slots_available(self):
        from services.pes6_ps2_patcher.models import LEAGUE_RANGES

        custom = LEAGUE_RANGES["custom"]
        assert custom["count"] == 18  # Team A-R
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd src && python -m pytest ../tests/test_pes6_ps2_patcher.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Create __init__.py and models.py**

```python
# src/services/pes6_ps2_patcher/__init__.py
"""PES 6 PS2 Patcher — Pro Evolution Soccer 6 (PS2) roster update."""

from .patcher import PES6PS2Patcher  # noqa: F401
```

```python
# src/services/pes6_ps2_patcher/models.py
"""Data models for the PES 6 PS2 patcher.

PES 6 (PS2, SLES-54203) stores team names as variable-length
null-terminated UTF-8 strings in the SLES_542.03 executable.
Strings are 8-byte aligned, alternating: name, abbreviation.

References:
  - PES 6 AFS Map documentation
  - PeterC10/PESEditor (option file format)
  - ISO analysis of PES 6 - Pro Evolution Soccer (Europe)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# Re-export shared sports models
from services.sports_api.models import (  # noqa: F401
    League,
    Player,
    PlayerStats,
    Team,
    TeamRoster,
    LeagueData,
)


# ---------------------------------------------------------------------------
# ISO layout constants (confirmed from PES 6 EUR SLES-54203)
# ---------------------------------------------------------------------------

ISO_SECTOR_SIZE = 2048
SLES_LBA = 323
SLES_SIZE = 3_057_568
NTGUI_LBA = 1816
AFS_0TEXT_LBA = 14741
AFS_0TEXT_FILES = 9806

# Team name string table in SLES_542.03
# Strings start with national teams and end with All-Stars/shop teams.
# Each string is null-terminated, padded to 8-byte boundary.
# Format: name\0[pad] abbr\0[pad] name\0[pad] abbr\0[pad] ...
# The first valid team pair (Austria/AUT) is at pair index 24 in the
# sequential string list; indices 0-23 are non-team data (IOP modules etc.).
SLES_TEAM_NAMES_START = 0x2DDE10  # Offset of "Austria" in SLES
SLES_TEAM_NAMES_END = 0x2DF610  # Approximate end of team data
FIRST_TEAM_PAIR_INDEX = 24  # First team in the sequential string list

TOTAL_TEAMS = 277  # Total name+abbreviation pairs (indices 0-276)

# League slot ranges (pair index in team list, 0-based from first team)
# These are relative to the team list (subtract FIRST_TEAM_PAIR_INDEX
# from the absolute string pair index).
LEAGUE_RANGES: Dict[str, Dict] = {
    "national_europe": {"start": 0, "end": 32, "count": 32, "label": "National (Europe)"},
    "national_africa": {"start": 32, "end": 40, "count": 8, "label": "National (Africa)"},
    "national_concacaf": {"start": 40, "end": 45, "count": 5, "label": "National (CONCACAF)"},
    "national_south_america_asia": {"start": 45, "end": 57, "count": 12, "label": "National (S.Am/Asia)"},
    "classic": {"start": 57, "end": 65, "count": 8, "label": "Classic Teams"},
    "epl": {"start": 64, "end": 84, "count": 20, "label": "English Premier League"},
    "ligue1": {"start": 84, "end": 104, "count": 20, "label": "Ligue 1"},
    "serie_a": {"start": 104, "end": 124, "count": 20, "label": "Serie A"},
    "eredivisie": {"start": 124, "end": 142, "count": 18, "label": "Eredivisie"},
    "la_liga": {"start": 142, "end": 162, "count": 20, "label": "La Liga"},
    "other_european": {"start": 162, "end": 181, "count": 19, "label": "Other European"},
    "south_american_clubs": {"start": 181, "end": 186, "count": 5, "label": "S. American Clubs"},
    "custom": {"start": 186, "end": 204, "count": 18, "label": "Custom (Team A-R)"},
    "extra_national": {"start": 204, "end": 221, "count": 17, "label": "Extra National"},
    "ml_zodiac": {"start": 221, "end": 239, "count": 18, "label": "ML/Zodiac"},
    "allstars": {"start": 239, "end": 253, "count": 14, "label": "All-Stars/Shop"},
}

# ESPN league ID → PES 6 slot range key
ESPN_LEAGUE_TO_RANGE: Dict[str, str] = {
    "eng.1": "epl",
    "fra.1": "ligue1",
    "ita.1": "serie_a",
    "ned.1": "eredivisie",
    "esp.1": "la_liga",
}


@dataclass
class PES6TeamSlot:
    """A team slot read from the ROM."""

    index: int  # 0-based team index (relative to first team)
    name: str
    abbreviation: str
    name_offset: int  # Absolute byte offset of name in SLES
    abbr_offset: int  # Absolute byte offset of abbreviation in SLES
    name_budget: int  # Max bytes available for name (including null + padding)
    abbr_budget: int  # Max bytes available for abbreviation


@dataclass
class PES6RomInfo:
    """Information about a loaded PES 6 PS2 ISO."""

    path: str
    size: int = 0
    team_slots: List[PES6TeamSlot] = field(default_factory=list)
    is_valid: bool = False


@dataclass
class PES6SlotMapping:
    """Maps an ESPN team to a PES 6 ROM slot."""

    team: Team
    slot_index: int
    slot_name: str  # Original ROM name for this slot
```

Note: The exact `SLES_TEAM_NAMES_START` offset and league range indices need to be verified by running `rom_reader.py` against the real ISO. The values above are from the ISO dump but may need fine-tuning once the reader parses the actual string table.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd src && python -m pytest ../tests/test_pes6_ps2_patcher.py -v`
Expected: PASS (may need to adjust constants after verifying with real ISO)

- [ ] **Step 5: Commit**

```bash
git add src/services/pes6_ps2_patcher/__init__.py src/services/pes6_ps2_patcher/models.py tests/test_pes6_ps2_patcher.py
git commit -m "feat(pes6): add models with team slot constants and league ranges"
```

---

### Task 2: Create rom_reader.py — ISO validation + team name parsing

**Files:**
- Create: `src/services/pes6_ps2_patcher/rom_reader.py`
- Test: `tests/test_pes6_ps2_patcher.py` (add tests)

- [ ] **Step 1: Write tests for ROM reader**

Add to `tests/test_pes6_ps2_patcher.py`:

```python
import os
import struct


PES6_ISO = os.path.join(
    os.path.dirname(__file__),
    "..", "roms", "ps2",
    "PES 6 - Pro Evolution Soccer (Europe).iso",
)


@pytest.mark.skipif(not os.path.exists(PES6_ISO), reason="PES 6 ISO not available")
class TestPES6RomReader:
    """Tests that require the actual PES 6 ISO."""

    def test_validate_valid_iso(self):
        from services.pes6_ps2_patcher.rom_reader import PES6RomReader

        reader = PES6RomReader(PES6_ISO)
        assert reader.validate() is True

    def test_validate_invalid_file(self, tmp_path):
        from services.pes6_ps2_patcher.rom_reader import PES6RomReader

        fake = tmp_path / "fake.iso"
        fake.write_bytes(b"\x00" * 1000)
        reader = PES6RomReader(str(fake))
        assert reader.validate() is False

    def test_read_team_slots(self):
        from services.pes6_ps2_patcher.rom_reader import PES6RomReader

        reader = PES6RomReader(PES6_ISO)
        assert reader.validate()
        slots = reader.read_team_slots()
        assert len(slots) > 200  # Should be ~253 teams
        # Check Arsenal is in there (first EPL team, licensed)
        names = [s.name for s in slots]
        assert "Arsenal" in names

    def test_team_slot_has_byte_budget(self):
        from services.pes6_ps2_patcher.rom_reader import PES6RomReader

        reader = PES6RomReader(PES6_ISO)
        reader.validate()
        slots = reader.read_team_slots()
        for slot in slots:
            assert slot.name_budget > 0
            assert slot.abbr_budget > 0
            # Name must fit in budget
            assert len(slot.name.encode("utf-8")) < slot.name_budget

    def test_rom_info(self):
        from services.pes6_ps2_patcher.rom_reader import PES6RomReader

        reader = PES6RomReader(PES6_ISO)
        info = reader.get_rom_info()
        assert info.is_valid
        assert len(info.team_slots) > 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd src && python -m pytest ../tests/test_pes6_ps2_patcher.py::TestPES6RomReader -v`
Expected: FAIL — rom_reader module not found

- [ ] **Step 3: Implement rom_reader.py**

```python
# src/services/pes6_ps2_patcher/rom_reader.py
"""ROM reader for PES 6 PS2 patcher.

Reads team names from the SLES_542.03 executable embedded in the ISO.
Team names are variable-length null-terminated UTF-8 strings, 8-byte aligned,
alternating: name, abbreviation, name, abbreviation...

ISO structure:
  Standard ISO 9660 → SLES_542.03 at LBA 323
"""

import os
import struct
from typing import List, Optional

from services.pes6_ps2_patcher.models import (
    PES6RomInfo,
    PES6TeamSlot,
    ISO_SECTOR_SIZE,
    SLES_LBA,
    SLES_SIZE,
)


# Volume ID to validate this is a PES 6 ISO
EXPECTED_VOLUME_ID = "PES6"


class PES6RomReader:
    """Reads and parses PES 6 PS2 ISO data."""

    def __init__(self, iso_path: str):
        self.iso_path = iso_path
        self._iso_size = 0
        self._sles_data: Optional[bytes] = None

    def validate(self) -> bool:
        """Validate this is a PES 6 PS2 ISO."""
        if not os.path.exists(self.iso_path):
            return False

        self._iso_size = os.path.getsize(self.iso_path)
        if self._iso_size < (SLES_LBA + 1) * ISO_SECTOR_SIZE:
            return False

        try:
            with open(self.iso_path, "rb") as f:
                # Check ISO 9660 PVD at sector 16
                f.seek(16 * ISO_SECTOR_SIZE)
                pvd = f.read(ISO_SECTOR_SIZE)
                if pvd[0] != 1:  # PVD type
                    return False

                volume_id = pvd[40:72].decode("ascii", errors="replace").strip()
                if EXPECTED_VOLUME_ID not in volume_id:
                    return False

                # Read SLES executable
                f.seek(SLES_LBA * ISO_SECTOR_SIZE)
                self._sles_data = f.read(SLES_SIZE)
                if len(self._sles_data) < SLES_SIZE:
                    return False

            return True
        except Exception:
            return False

    def read_team_slots(self) -> List[PES6TeamSlot]:
        """Parse all team name/abbreviation pairs from SLES executable.

        Scans the known team name region for 8-byte-aligned null-terminated
        strings, pairing them as (name, abbreviation).
        """
        if self._sles_data is None:
            return []

        # Find team names by scanning for known anchor: "Austria"
        anchor = b"Austria"
        anchor_pos = self._sles_data.find(anchor)
        if anchor_pos < 0:
            return []

        # Collect all 8-byte-aligned strings from anchor backwards and forwards
        # First, find the start of the team region by going back
        # to find the first team name before Austria
        strings = self._parse_string_table(anchor_pos)
        if len(strings) < 4:
            return []

        # Pair strings as (name, abbreviation)
        slots = []
        i = 0
        team_idx = 0
        while i + 1 < len(strings):
            name_offset, name_str = strings[i]
            abbr_offset, abbr_str = strings[i + 1]

            # Calculate byte budget: distance to next string
            if i + 2 < len(strings):
                name_budget = abbr_offset - name_offset
            else:
                name_budget = 16  # default
            if i + 3 < len(strings):
                abbr_budget = strings[i + 2][0] - abbr_offset
            else:
                abbr_budget = 8  # default

            slots.append(
                PES6TeamSlot(
                    index=team_idx,
                    name=name_str,
                    abbreviation=abbr_str,
                    name_offset=SLES_LBA * ISO_SECTOR_SIZE + name_offset,
                    abbr_offset=SLES_LBA * ISO_SECTOR_SIZE + abbr_offset,
                    name_budget=name_budget,
                    abbr_budget=abbr_budget,
                )
            )
            team_idx += 1
            i += 2

        return slots

    def _parse_string_table(self, anchor_pos: int) -> list:
        """Parse the string table around the anchor position.

        Returns list of (sles_offset, string) tuples.
        """
        data = self._sles_data

        # Scan backwards from anchor to find the start of the team section
        # Look for a gap of 16+ null bytes (section boundary)
        scan_pos = anchor_pos - 8
        region_start = anchor_pos
        while scan_pos > max(0, anchor_pos - 4000):
            block = data[scan_pos : scan_pos + 8]
            if block == b"\x00" * 8:
                # Check if this is a real gap (previous block also null)
                prev = data[scan_pos - 8 : scan_pos]
                if prev == b"\x00" * 8:
                    region_start = scan_pos + 8
                    break
            scan_pos -= 8

        # Skip any leading nulls
        while region_start < len(data) and data[region_start] == 0:
            region_start += 1
        # Align to 8
        region_start = (region_start // 8) * 8

        # Scan forward from anchor to find the end
        # Look for another section boundary or end of reasonable range
        region_end = min(anchor_pos + 6000, len(data))

        # Parse all strings in the region
        strings = []
        pos = region_start
        while pos < region_end:
            if data[pos] == 0:
                pos += 1
                continue

            # Found start of a string
            end = data.index(b"\x00", pos)
            try:
                s = data[pos:end].decode("utf-8")
            except UnicodeDecodeError:
                # Not a valid UTF-8 string — we've left the team region
                break
            strings.append((pos, s))

            # Advance to next 8-byte boundary
            pos = ((end + 8) // 8) * 8

        return strings

    def get_rom_info(self) -> PES6RomInfo:
        """Return PES6RomInfo for this ISO."""
        valid = self.validate()
        slots = self.read_team_slots() if valid else []
        return PES6RomInfo(
            path=self.iso_path,
            size=self._iso_size,
            team_slots=slots,
            is_valid=valid,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd src && python -m pytest ../tests/test_pes6_ps2_patcher.py -v`
Expected: PASS (ISO-dependent tests skip if ISO not present)

- [ ] **Step 5: Commit**

```bash
git add src/services/pes6_ps2_patcher/rom_reader.py tests/test_pes6_ps2_patcher.py
git commit -m "feat(pes6): add ROM reader with team name parsing from SLES executable"
```

---

### Task 3: Create rom_writer.py — write team names to ISO copy

**Files:**
- Create: `src/services/pes6_ps2_patcher/rom_writer.py`
- Test: `tests/test_pes6_ps2_patcher.py` (add tests)

- [ ] **Step 1: Write tests for ROM writer**

Add to `tests/test_pes6_ps2_patcher.py`:

```python
@pytest.mark.skipif(not os.path.exists(PES6_ISO), reason="PES 6 ISO not available")
class TestPES6RomWriter:
    """Tests for writing team names back to ISO."""

    def test_write_team_name(self, tmp_path):
        from services.pes6_ps2_patcher.rom_reader import PES6RomReader
        from services.pes6_ps2_patcher.rom_writer import PES6RomWriter

        output = str(tmp_path / "patched.iso")
        writer = PES6RomWriter(PES6_ISO, output)

        # Read original slots
        reader = PES6RomReader(PES6_ISO)
        reader.validate()
        slots = reader.read_team_slots()

        # Find Arsenal slot
        arsenal = next(s for s in slots if s.name == "Arsenal")

        # Write a new name
        writer.write_team_name(arsenal, "Test FC", "TST")
        writer.finalize()

        # Verify by reading back
        reader2 = PES6RomReader(output)
        reader2.validate()
        slots2 = reader2.read_team_slots()
        updated = next(s for s in slots2 if s.index == arsenal.index)
        assert updated.name == "Test FC"
        assert updated.abbreviation == "TST"

    def test_name_truncation(self, tmp_path):
        from services.pes6_ps2_patcher.rom_reader import PES6RomReader
        from services.pes6_ps2_patcher.rom_writer import PES6RomWriter

        output = str(tmp_path / "patched.iso")
        writer = PES6RomWriter(PES6_ISO, output)

        reader = PES6RomReader(PES6_ISO)
        reader.validate()
        slots = reader.read_team_slots()
        slot = slots[0]

        # Try writing a name that's too long — should truncate
        long_name = "A" * 100
        writer.write_team_name(slot, long_name, "XX")
        writer.finalize()

        reader2 = PES6RomReader(output)
        reader2.validate()
        slots2 = reader2.read_team_slots()
        assert len(slots2[0].name.encode("utf-8")) < slot.name_budget
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd src && python -m pytest ../tests/test_pes6_ps2_patcher.py::TestPES6RomWriter -v`
Expected: FAIL — rom_writer module not found

- [ ] **Step 3: Implement rom_writer.py**

```python
# src/services/pes6_ps2_patcher/rom_writer.py
"""ROM writer for PES 6 PS2 patcher.

Writes patched team names back to a copy of the PES 6 ISO.
Names are written in-place at each slot's known offset within SLES_542.03.
"""

import os
import shutil

from services.pes6_ps2_patcher.models import PES6TeamSlot


class PES6RomWriter:
    """Writes patched data to a copy of the PES 6 ISO."""

    def __init__(self, input_path: str, output_path: str):
        """Copy ISO to output path for patching."""
        if os.path.exists(input_path):
            shutil.copy2(input_path, output_path)
        self.output_path = output_path
        self._rom = None

    def _ensure_open(self):
        if self._rom is None:
            self._rom = open(self.output_path, "r+b")

    def write_team_name(
        self, slot: PES6TeamSlot, new_name: str, new_abbr: str
    ):
        """Write a new team name and abbreviation to a slot.

        Names are truncated if they exceed the slot's byte budget.
        The slot region is zero-filled first, then the new string is written.
        """
        self._ensure_open()

        # Write name
        name_bytes = new_name.encode("utf-8")
        max_name = slot.name_budget - 1  # Leave room for null terminator
        if len(name_bytes) > max_name:
            # Truncate at valid UTF-8 boundary
            name_bytes = name_bytes[:max_name]
            while name_bytes and (name_bytes[-1] & 0xC0) == 0x80:
                name_bytes = name_bytes[:-1]

        self._rom.seek(slot.name_offset)
        self._rom.write(b"\x00" * slot.name_budget)  # Clear region
        self._rom.seek(slot.name_offset)
        self._rom.write(name_bytes)

        # Write abbreviation
        abbr_bytes = new_abbr.encode("utf-8")
        max_abbr = slot.abbr_budget - 1
        if len(abbr_bytes) > max_abbr:
            abbr_bytes = abbr_bytes[:max_abbr]

        self._rom.seek(slot.abbr_offset)
        self._rom.write(b"\x00" * slot.abbr_budget)
        self._rom.seek(slot.abbr_offset)
        self._rom.write(abbr_bytes)

    def finalize(self):
        """Flush and close the output file."""
        if self._rom:
            self._rom.flush()
            self._rom.close()
            self._rom = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd src && python -m pytest ../tests/test_pes6_ps2_patcher.py::TestPES6RomWriter -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/pes6_ps2_patcher/rom_writer.py tests/test_pes6_ps2_patcher.py
git commit -m "feat(pes6): add ROM writer for team name patching"
```

---

## Chunk 2: Patcher Orchestrator + State + UI Wiring

### Task 4: Create patcher.py — orchestrator

**Files:**
- Create: `src/services/pes6_ps2_patcher/patcher.py`

- [ ] **Step 1: Implement patcher orchestrator**

```python
# src/services/pes6_ps2_patcher/patcher.py
"""PES 6 PS2 patcher orchestrator.

Coordinates fetching ESPN soccer rosters, mapping teams to ROM slots,
and writing patched team names to the ISO.
"""

import os
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from services.pes6_ps2_patcher.models import (
    PES6RomInfo,
    PES6SlotMapping,
    ESPN_LEAGUE_TO_RANGE,
    LEAGUE_RANGES,
)
from services.pes6_ps2_patcher.rom_reader import PES6RomReader
from services.pes6_ps2_patcher.rom_writer import PES6RomWriter
from services.sports_api.models import Team, TeamRoster


@dataclass
class PatchResult:
    success: bool
    output_path: str = ""
    error: str = ""
    teams_patched: int = 0


class PES6PS2Patcher:
    """PES 6 PS2 roster patcher."""

    def __init__(
        self,
        cache_dir: str,
        on_status: Optional[Callable] = None,
    ):
        self.cache_dir = cache_dir
        self.on_status = on_status
        os.makedirs(cache_dir, exist_ok=True)

    def _status(self, msg: str):
        if self.on_status:
            self.on_status(msg)

    def fetch_rosters(
        self,
        league_id: str,
        season: int,
        on_progress: Optional[Callable] = None,
    ) -> Dict[str, list]:
        """Fetch rosters from ESPN soccer API.

        Returns dict of team_code -> list of Player objects.
        """
        from services.sports_api.espn_client import ESPNClient

        client = ESPNClient()
        self._status("Fetching teams...")

        if on_progress:
            on_progress(0.1, "Fetching teams...")

        teams_data = client.get_soccer_teams(league_id, season)
        rosters = {}
        total = len(teams_data) if teams_data else 0

        for i, team_data in enumerate(teams_data or []):
            team_code = team_data.code or team_data.short_name
            if on_progress:
                on_progress(
                    0.1 + 0.8 * (i / max(total, 1)),
                    f"Fetching {team_data.name}...",
                )

            players = client.get_soccer_squad(team_data.id, league_id)
            rosters[team_code] = players

        if on_progress:
            on_progress(1.0, f"Loaded {total} teams")

        return rosters

    def analyze_rom(self, iso_path: str) -> PES6RomInfo:
        """Analyze a PES 6 ISO and return ROM info."""
        reader = PES6RomReader(iso_path)
        return reader.get_rom_info()

    def build_slot_mapping(
        self,
        rom_info: PES6RomInfo,
        teams: List[Team],
        league_id: str,
    ) -> List[PES6SlotMapping]:
        """Map ESPN teams to PES 6 ROM slots.

        Uses the league ID to determine which slot range to target,
        then matches teams by name similarity.
        """
        range_key = ESPN_LEAGUE_TO_RANGE.get(league_id)
        if not range_key or range_key not in LEAGUE_RANGES:
            # Unknown league — use custom slots
            range_key = "custom"

        lr = LEAGUE_RANGES[range_key]
        start, end = lr["start"], lr["end"]

        # Get available slots in this range
        available = [
            s for s in rom_info.team_slots if start <= s.index < end
        ]

        mapping = []
        for i, team in enumerate(teams):
            if i < len(available):
                slot = available[i]
                mapping.append(
                    PES6SlotMapping(
                        team=team,
                        slot_index=slot.index,
                        slot_name=slot.name,
                    )
                )

        return mapping

    def patch_rom(
        self,
        input_path: str,
        output_path: str,
        slot_mapping: List[PES6SlotMapping],
        rom_info: PES6RomInfo,
        on_progress: Optional[Callable] = None,
    ) -> PatchResult:
        """Write patched team names to the ISO."""
        try:
            writer = PES6RomWriter(input_path, output_path)
            total = len(slot_mapping)

            for i, mapping in enumerate(slot_mapping):
                if on_progress:
                    on_progress(
                        i / max(total, 1),
                        f"Patching {mapping.team.name}...",
                    )

                # Find the slot in rom_info
                slot = next(
                    (s for s in rom_info.team_slots if s.index == mapping.slot_index),
                    None,
                )
                if slot is None:
                    continue

                # Write team name and abbreviation
                name = mapping.team.name
                abbr = mapping.team.code or mapping.team.short_name or name[:3].upper()
                writer.write_team_name(slot, name, abbr)

            writer.finalize()

            if on_progress:
                on_progress(1.0, "Done!")

            return PatchResult(
                success=True,
                output_path=output_path,
                teams_patched=total,
            )
        except Exception as e:
            return PatchResult(success=False, error=str(e))
```

Note: The `fetch_rosters` method calls `get_soccer_teams` and `get_soccer_squad` on `ESPNClient`. These methods may need to be verified/added in the existing `espn_client.py` — check if they exist or if the WE2002 patcher uses a different API path for soccer. If the methods don't exist yet, add thin wrappers that call the appropriate ESPN soccer endpoint (`/sports/soccer/{league_id}/teams`).

- [ ] **Step 2: Commit**

```bash
git add src/services/pes6_ps2_patcher/patcher.py
git commit -m "feat(pes6): add patcher orchestrator with ESPN fetch and team mapping"
```

---

### Task 5: Add PES6PS2PatcherState to state.py + active_patcher

**Files:**
- Modify: `src/state.py`

- [ ] **Step 1: Add state dataclass**

Add after the existing `NHL05PS2PatcherState` class in `src/state.py`:

```python
@dataclass
class PES6PS2PatcherState:
    """State for the PES 6 PS2 Patcher feature."""

    selected_season: int = field(
        default_factory=lambda: datetime.now().year
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
    league_search_query: str = ""
```

Add field to `AppState.__init__`:

```python
self.pes6_ps2_patcher = PES6PS2PatcherState()
```

Add to `active_patcher` property:

```python
if self.mode == "pes6_patcher":
    return self.pes6_ps2_patcher
```

- [ ] **Step 2: Commit**

```bash
git add src/state.py
git commit -m "feat(pes6): add PES6PS2PatcherState to AppState"
```

---

### Task 6: Create UI screen

**Files:**
- Create: `src/ui/screens/pes6_ps2_patcher_screen.py`

- [ ] **Step 1: Implement screen**

Follow the exact pattern from `nhl05_ps2_patcher_screen.py` but with a "Select League" step instead of "Season". Steps:

1. Select League (opens league browser modal)
2. Fetch Rosters
3. Preview Rosters
4. Select ISO
5. Patch ROM

```python
# src/ui/screens/pes6_ps2_patcher_screen.py
"""PES 6 PS2 Patcher screen — PES 6 (PS2) roster update.

Mirrors the WE2002/NHL05 patcher UI pattern: step-by-step list with
(label, secondary_text) pairs and action-based dispatch.
"""

import os
import pygame

from ui.theme import Theme, default_theme
from ui.templates.list_screen import ListScreenTemplate
from ui.atoms.text import Text


class PES6PS2PatcherScreen:
    """PES 6 PS2 roster patcher UI."""

    def __init__(self, theme: Theme = default_theme):
        self.theme = theme
        self.template = ListScreenTemplate(theme)
        self.text = Text(theme)

    def _get_items(self, state, settings):
        """Build the menu items as (label, value, action) tuples."""
        pes = state.pes6_ps2_patcher

        items = []

        # -- 1. Select League --
        if pes.selected_league:
            league_name = (
                pes.selected_league.name
                if hasattr(pes.selected_league, "name")
                else str(pes.selected_league)
            )
            league_value = league_name
        else:
            league_value = "Not selected"
        items.append(("1. Select League", league_value, "select_league"))

        # -- 2. Fetch Rosters --
        if pes.is_fetching:
            fetch_value = f"Fetching... {int(pes.fetch_progress * 100)}%"
        elif pes.rosters:
            team_count = len(pes.rosters)
            fetch_value = f"{team_count} teams loaded"
        elif pes.fetch_error:
            fetch_value = f"Error: {pes.fetch_error}"
        else:
            fetch_value = "Not fetched"
        can_fetch = pes.selected_league is not None
        items.append((
            "2. Fetch Rosters",
            fetch_value,
            "fetch_rosters" if can_fetch else "locked",
        ))

        # -- 3. Preview Rosters --
        if pes.league_data or pes.rosters or pes.is_fetching:
            preview_value = "Tap to preview"
            preview_action = "preview_rosters"
        else:
            preview_value = "Complete step 2 first"
            preview_action = "locked"
        items.append(("3. Preview Rosters", preview_value, preview_action))

        # -- 4. Select ISO --
        if pes.rom_path and pes.rom_valid:
            rom_value = os.path.basename(pes.zip_path or pes.rom_path)
        elif pes.rom_path:
            rom_value = "Invalid ISO"
        else:
            rom_value = "Not selected"
        items.append(("4. Select ISO (.iso/.zip)", rom_value, "select_rom"))

        # -- 5. Patch ROM --
        if pes.patch_complete:
            patch_value = "Complete"
        elif pes.rosters and pes.rom_valid:
            patch_value = "Ready to patch"
        else:
            patch_value = "Complete steps 2+4 first"
        items.append((
            "5. Patch ROM",
            patch_value,
            "patch_rom" if (pes.rosters and pes.rom_valid) else "locked",
        ))

        return items

    def render(self, screen, highlighted, state, settings=None):
        items = self._get_items(state, settings)
        display_items = [(label, value) for label, value, _ in items]

        back_rect, item_rects, scroll_offset = self.template.render(
            screen,
            title="PES 6 (PS2) Patcher",
            items=display_items,
            highlighted=highlighted,
            selected=set(),
            show_back=True,
            item_height=48,
            get_label=lambda x: x[0] if isinstance(x, tuple) else x,
            get_secondary=lambda x: (x[1] if isinstance(x, tuple) else None),
            item_spacing=8,
        )

        return back_rect, item_rects, scroll_offset

    def get_action(self, index: int, state, settings=None) -> str:
        items = self._get_items(state, settings)
        if 0 <= index < len(items):
            return items[index][2]
        return "unknown"

    def get_count(self, state=None, settings=None) -> int:
        if state is None:
            return 5
        return len(self._get_items(state, settings))


pes6_ps2_patcher_screen = PES6PS2PatcherScreen()
```

- [ ] **Step 2: Commit**

```bash
git add src/ui/screens/pes6_ps2_patcher_screen.py
git commit -m "feat(pes6): add PES 6 PS2 patcher UI screen"
```

---

### Task 7: Wire into sports_patcher_screen.py and screen_manager.py

**Files:**
- Modify: `src/ui/screens/sports_patcher_screen.py`
- Modify: `src/ui/screens/screen_manager.py`

- [ ] **Step 1: Add PES 6 to GAMES list**

In `src/ui/screens/sports_patcher_screen.py`, add to the `GAMES` list:

```python
("PES 6 - Pro Evolution Soccer 6 (PS2)", "pes6_patcher"),
```

- [ ] **Step 2: Add screen and modal rendering to screen_manager.py**

In `src/ui/screens/screen_manager.py`:

1. Add import: `from .pes6_ps2_patcher_screen import PES6PS2PatcherScreen`
2. Add to `__init__`: `self.pes6_ps2_patcher_screen = PES6PS2PatcherScreen(theme)`
3. Add rendering block in the mode dispatch (after NHL 05 block):

```python
elif state.mode == "pes6_patcher":
    back_rect, item_rects, scroll_offset = self.pes6_ps2_patcher_screen.render(
        screen, state.highlighted, state, settings
    )
    rects["back"] = back_rect
    rects["item_rects"] = item_rects
    rects["scroll_offset"] = scroll_offset
```

4. Add modal rendering blocks (after NHL 05 modal blocks):

```python
# PES 6 PS2 Patcher modals
if state.pes6_ps2_patcher.active_modal == "league_browser":
    modal_rect, content_rect, close_rect, char_rects, item_rects = (
        self.league_browser_modal.render(screen, state, settings)
    )
    rects["modal"] = modal_rect
    rects["close"] = close_rect
    rects["char_rects"] = char_rects
    rects["item_rects"] = item_rects
    return rects

if state.pes6_ps2_patcher.active_modal == "roster_preview":
    modal_rect, content_rect, close_rect, item_rects = (
        self.roster_preview_modal.render(screen, state)
    )
    rects["modal"] = modal_rect
    rects["close"] = close_rect
    rects["item_rects"] = item_rects
    return rects

if state.pes6_ps2_patcher.active_modal == "patch_progress":
    modal_rect, content_rect, close_rect, item_rects = (
        self.patch_progress_modal.render(screen, state)
    )
    rects["modal"] = modal_rect
    rects["close"] = close_rect
    rects["item_rects"] = item_rects
    return rects
```

- [ ] **Step 3: Commit**

```bash
git add src/ui/screens/sports_patcher_screen.py src/ui/screens/screen_manager.py
git commit -m "feat(pes6): register PES 6 in sports patcher menu and screen manager"
```

---

### Task 8: Wire into app.py — navigation, selection, back, ROM picker, patching

**Files:**
- Modify: `src/app.py`

This is the largest wiring task. Follow the exact pattern from the NHL 05 PS2 patcher handlers. The key additions to `app.py`:

- [ ] **Step 1: Add mode dispatch for navigation**

In `_handle_navigation` (around line 1461), add:

```python
elif self.state.mode == "pes6_patcher":
    self._handle_pes6_patcher_navigation(direction)
```

- [ ] **Step 2: Add mode dispatch for selection (A button)**

In `_handle_selection` (around line 3484), add:

```python
elif self.state.mode == "pes6_patcher":
    self._handle_pes6_patcher_selection()
```

- [ ] **Step 3: Add sports patcher menu action**

In the sports patcher action handler (around line 3453), add:

```python
elif action == "pes6_patcher":
    self.state.mode = "pes6_patcher"
    self.state.highlighted = 0
```

- [ ] **Step 4: Add back handler**

In `_go_back` (around line 3159), add:

```python
elif self.state.mode == "pes6_patcher":
    if self.state.pes6_ps2_patcher.active_modal:
        self.state.pes6_ps2_patcher.active_modal = None
    else:
        from state import PES6PS2PatcherState
        self.state.pes6_ps2_patcher = PES6PS2PatcherState()
        self.state.mode = "sports_patcher"
        self.state.highlighted = 0
```

- [ ] **Step 5: Add ROM file picker routing**

In `_open_folder_browser` initial path section, add:

```python
elif selection_type == "pes6_patcher_rom":
    path = self.settings.get("roms_dir", SCRIPT_DIR)
```

In the loader section, add:

```python
elif selection_type == "pes6_patcher_rom":
    from services.file_listing import load_psp_iso_folder_contents
    loader = load_psp_iso_folder_contents
```

In `is_psp_context`, add `"pes6_patcher_rom"`.

In `_complete_folder_browser_selection`, add the PES 6 ROM handling block (same pattern as NHL 05).

- [ ] **Step 6: Add navigation handler method**

```python
def _handle_pes6_patcher_navigation(self, direction):
    """Handle D-pad navigation for pes6_patcher mode."""
    pes = self.state.pes6_ps2_patcher

    if pes.active_modal == "roster_preview":
        # Same pattern as NHL 05 roster preview navigation
        league_data = pes.league_data
        if not league_data or not hasattr(league_data, "teams"):
            return
        teams = league_data.teams
        if direction == "left":
            pes.roster_preview_team_index = (
                pes.roster_preview_team_index - 1
            ) % max(len(teams), 1)
            pes.roster_preview_player_index = 0
        elif direction == "right":
            pes.roster_preview_team_index = (
                pes.roster_preview_team_index + 1
            ) % max(len(teams), 1)
            pes.roster_preview_player_index = 0
        elif direction == "up":
            pes.roster_preview_player_index = max(
                0, pes.roster_preview_player_index - 1
            )
        elif direction == "down":
            team_idx = pes.roster_preview_team_index
            if 0 <= team_idx < len(teams):
                players = (
                    teams[team_idx].players
                    if hasattr(teams[team_idx], "players")
                    else []
                )
                pes.roster_preview_player_index = min(
                    pes.roster_preview_player_index + 1,
                    max(len(players) - 1, 0),
                )

    elif pes.active_modal is None:
        from ui.screens.pes6_ps2_patcher_screen import pes6_ps2_patcher_screen
        max_items = pes6_ps2_patcher_screen.get_count(self.state, self.settings)
        if direction in ("up", "left"):
            self.state.highlighted = (self.state.highlighted - 1) % max_items
        elif direction in ("down", "right"):
            self.state.highlighted = (self.state.highlighted + 1) % max_items
```

- [ ] **Step 7: Add selection handler method**

```python
def _handle_pes6_patcher_selection(self):
    """Handle item selection on the pes6_patcher main menu."""
    pes = self.state.pes6_ps2_patcher

    if pes.active_modal == "roster_preview":
        return
    if pes.active_modal == "patch_progress":
        if pes.patch_complete or pes.patch_error:
            pes.active_modal = None
        return
    if pes.active_modal == "league_browser":
        self._handle_pes6_league_browser_selection()
        return

    from ui.screens.pes6_ps2_patcher_screen import pes6_ps2_patcher_screen

    action = pes6_ps2_patcher_screen.get_action(
        self.state.highlighted, self.state, self.settings
    )

    if action == "select_league":
        pes.active_modal = "league_browser"
        # Load available leagues from ESPN
        self._load_pes6_leagues()
    elif action == "fetch_rosters":
        self._start_pes6_roster_fetch()
    elif action == "preview_rosters":
        pes.active_modal = "roster_preview"
        pes.roster_preview_team_index = 0
        pes.roster_preview_player_index = 0
        if not pes.rosters and not pes.is_fetching:
            self._start_pes6_roster_fetch()
    elif action == "select_rom":
        self._open_folder_browser("pes6_patcher_rom")
    elif action == "patch_rom":
        pes.active_modal = "patch_progress"
        self._start_pes6_patching()
```

- [ ] **Step 8: Add roster fetch and patching thread methods**

Follow the exact pattern from `_start_nhl05_roster_fetch` and `_start_nhl05_patching`, adapted for PES 6 with league-based fetching instead of provider-based.

- [ ] **Step 9: Commit**

```bash
git add src/app.py
git commit -m "feat(pes6): wire PES 6 patcher into app.py event handling"
```

---

## Chunk 3: ESPN Soccer Integration + Testing

### Task 9: Verify ESPN soccer API methods exist

**Files:**
- Read: `src/services/sports_api/espn_client.py`

- [ ] **Step 1: Check existing ESPN soccer methods**

The WE2002 patcher uses ESPN soccer endpoints. Verify these methods exist:
- `get_soccer_teams(league_id, season)` — returns list of Team objects
- `get_soccer_squad(team_id, league_id)` — returns list of Player objects
- `get_available_soccer_leagues()` — returns list of leagues for the browser

If they don't exist with these exact names, find the equivalent methods and update `patcher.py` to use the correct names.

- [ ] **Step 2: Commit any fixes**

```bash
git add src/services/pes6_ps2_patcher/patcher.py
git commit -m "fix(pes6): align ESPN API method names with existing client"
```

---

### Task 10: End-to-end smoke test

- [ ] **Step 1: Run the app and test the full flow**

```bash
make run
```

1. Navigate to Sports Patcher menu
2. Select "PES 6 - Pro Evolution Soccer 6 (PS2)"
3. Select a league (e.g., "English Premier League")
4. Fetch rosters
5. Preview rosters
6. Select the PES 6 ISO from `roms/ps2/`
7. Patch ROM
8. Verify the output ISO has updated team names by opening it with the ROM reader

- [ ] **Step 2: Fix any issues found during smoke test**

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat(pes6): PES 6 PS2 patcher Phase 1 complete — team name patching"
```
