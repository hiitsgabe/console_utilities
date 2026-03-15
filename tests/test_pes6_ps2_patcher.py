"""Tests for the PES 6 PS2 patcher module.

Tests models and constants without requiring a real ISO file.
"""

import importlib
import os
import sys
import types

# Add src to path so we can import the modules
src_dir = os.path.join(os.path.dirname(__file__), "..", "src")
sys.path.insert(0, src_dir)

# Stub out the services package to avoid heavy imports (NSZ, pygame, etc.)
# We only need the pes6_ps2_patcher subpackage and sports_api.models.
if "services" not in sys.modules:
    services_pkg = types.ModuleType("services")
    services_pkg.__path__ = [os.path.join(src_dir, "services")]
    services_pkg.__package__ = "services"
    sys.modules["services"] = services_pkg

# Now import the subpackages we actually need
from services.sports_api.models import Team  # noqa: E402
from services.pes6_ps2_patcher.models import (  # noqa: E402
    TOTAL_TEAMS,
    LEAGUE_RANGES,
    ESPN_LEAGUE_TO_RANGE,
    ISO_SECTOR_SIZE,
    SLES_LBA,
    SLES_SIZE,
    AFS_0TEXT_LBA,
    AFS_0TEXT_FILES,
    PES6TeamSlot,
    PES6RomInfo,
    PES6SlotMapping,
)


# --- Constant tests ---


def test_total_teams():
    """PES 6 has 277 team name/abbreviation pairs."""
    assert TOTAL_TEAMS == 277


def test_iso_sector_size():
    """ISO sector size is 2048 bytes."""
    assert ISO_SECTOR_SIZE == 2048


def test_sles_constants():
    """SLES executable location and size are correct."""
    assert SLES_LBA == 323
    assert SLES_SIZE == 3_057_568


def test_afs_constants():
    """0_TEXT.AFS location and file count are correct."""
    assert AFS_0TEXT_LBA == 14741
    assert AFS_0TEXT_FILES == 9806


# --- League range tests ---


def test_league_ranges_defined():
    """All expected league ranges are defined."""
    expected = ["epl", "ligue1", "serie_a", "eredivisie", "la_liga"]
    for key in expected:
        assert key in LEAGUE_RANGES, f"Missing league range: {key}"


def test_epl_range():
    """EPL range is indices 64-83 (20 teams)."""
    epl = LEAGUE_RANGES["epl"]
    assert epl["start"] == 64
    assert epl["end"] == 84
    assert epl["count"] == 20
    assert epl["label"] == "English Premier League"


def test_ligue1_range():
    """Ligue 1 range has 20 teams starting at 84."""
    ligue1 = LEAGUE_RANGES["ligue1"]
    assert ligue1["start"] == 84
    assert ligue1["count"] == 20


def test_serie_a_range():
    """Serie A range has 20 teams starting at 104."""
    sa = LEAGUE_RANGES["serie_a"]
    assert sa["start"] == 104
    assert sa["count"] == 20


def test_eredivisie_range():
    """Eredivisie range has 18 teams starting at 124."""
    ere = LEAGUE_RANGES["eredivisie"]
    assert ere["start"] == 124
    assert ere["count"] == 18


def test_la_liga_range():
    """La Liga range has 20 teams starting at 142."""
    ll = LEAGUE_RANGES["la_liga"]
    assert ll["start"] == 142
    assert ll["count"] == 20


def test_custom_slots_count():
    """Custom team range has 18 slots."""
    custom = LEAGUE_RANGES["custom"]
    assert custom["count"] == 18
    assert custom["end"] - custom["start"] == 18


def test_league_range_consistency():
    """Every range's count matches end - start."""
    for key, rng in LEAGUE_RANGES.items():
        assert rng["end"] - rng["start"] == rng["count"], (
            f"Inconsistent range for {key}"
        )


# --- ESPN mapping tests ---


def test_espn_eng1_maps_to_epl():
    """ESPN eng.1 maps to the epl league range."""
    assert ESPN_LEAGUE_TO_RANGE["eng.1"] == "epl"


def test_espn_league_mappings():
    """All ESPN league mappings point to valid league ranges."""
    for espn_id, range_key in ESPN_LEAGUE_TO_RANGE.items():
        assert range_key in LEAGUE_RANGES, (
            f"ESPN {espn_id} maps to unknown range {range_key}"
        )


# --- Dataclass tests ---


def test_team_slot_defaults():
    """PES6TeamSlot has sensible defaults."""
    slot = PES6TeamSlot(index=0, name="Arsenal", abbreviation="ARS")
    assert slot.index == 0
    assert slot.name == "Arsenal"
    assert slot.abbreviation == "ARS"
    assert slot.name_offset == 0
    assert slot.name_budget == 0


def test_rom_info_defaults():
    """PES6RomInfo initialises with empty team_slots."""
    info = PES6RomInfo(path="/tmp/pes6.iso")
    assert info.path == "/tmp/pes6.iso"
    assert info.team_slots == []
    assert info.is_valid is False


def test_slot_mapping():
    """PES6SlotMapping holds team and slot info."""
    team = Team(
        id=1, name="Arsenal", short_name="Arsenal",
        code="ARS", logo_url="", country="England",
    )
    mapping = PES6SlotMapping(team=team, slot_index=64, slot_name="Arsenal")
    assert mapping.slot_index == 64
    assert mapping.team.name == "Arsenal"


# --- ROM reader tests ---

import tempfile  # noqa: E402
import pytest  # noqa: E402

from services.pes6_ps2_patcher.rom_reader import PES6RomReader  # noqa: E402

# Path to the real PES 6 ISO (relative to repo root)
_REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
_ISO_PATH = os.path.join(
    _REPO_ROOT, "roms", "ps2", "PES 6 - Pro Evolution Soccer (Europe).iso"
)
_HAS_ISO = os.path.exists(_ISO_PATH)


class TestPES6RomReaderNoISO:
    """Tests that don't require the real ISO."""

    def test_validate_missing_file(self):
        """validate() returns False for a non-existent file."""
        reader = PES6RomReader("/tmp/nonexistent_pes6.iso")
        assert reader.validate() is False

    def test_validate_fake_file(self):
        """validate() returns False for a file that isn't a valid ISO."""
        with tempfile.NamedTemporaryFile(suffix=".iso", delete=False) as f:
            f.write(b"\x00" * 4096)
            fake_path = f.name
        try:
            reader = PES6RomReader(fake_path)
            assert reader.validate() is False
        finally:
            os.unlink(fake_path)

    def test_get_rom_info_invalid(self):
        """get_rom_info() returns invalid info for non-existent ISO."""
        reader = PES6RomReader("/tmp/nonexistent_pes6.iso")
        info = reader.get_rom_info()
        assert info.is_valid is False
        assert info.team_slots == []


@pytest.mark.skipif(not _HAS_ISO, reason="PES 6 ISO not available")
class TestPES6RomReader:
    """Tests that require the real PES 6 ISO."""

    @pytest.fixture(autouse=True)
    def setup_reader(self):
        self.reader = PES6RomReader(_ISO_PATH)

    def test_validate_real_iso(self):
        """validate() returns True for the real PES 6 ISO."""
        assert self.reader.validate() is True

    def test_read_team_slots_count(self):
        """read_team_slots() returns > 200 slots."""
        self.reader.validate()
        slots = self.reader.read_team_slots()
        assert len(slots) > 200

    def test_read_team_slots_exact_count(self):
        """read_team_slots() returns exactly 277 slots."""
        self.reader.validate()
        slots = self.reader.read_team_slots()
        assert len(slots) == TOTAL_TEAMS

    def test_arsenal_in_team_names(self):
        """Arsenal appears in the team names."""
        self.reader.validate()
        slots = self.reader.read_team_slots()
        names = [s.name for s in slots]
        assert "Arsenal" in names

    def test_austria_in_team_names(self):
        """Austria (anchor team) appears in the team names."""
        self.reader.validate()
        slots = self.reader.read_team_slots()
        names = [s.name for s in slots]
        assert "Austria" in names

    def test_positive_budgets(self):
        """Each slot has positive name_budget and abbr_budget."""
        self.reader.validate()
        slots = self.reader.read_team_slots()
        for slot in slots:
            assert slot.name_budget > 0, (
                f"Slot {slot.index} ({slot.name}) has non-positive name_budget: "
                f"{slot.name_budget}"
            )
            assert slot.abbr_budget > 0, (
                f"Slot {slot.index} ({slot.name}) has non-positive abbr_budget: "
                f"{slot.abbr_budget}"
            )

    def test_offsets_are_absolute(self):
        """Offsets are absolute ISO positions (not relative to SLES)."""
        self.reader.validate()
        slots = self.reader.read_team_slots()
        sles_base = SLES_LBA * ISO_SECTOR_SIZE
        for slot in slots:
            assert slot.name_offset >= sles_base, (
                f"Slot {slot.index} name_offset {slot.name_offset} < SLES base {sles_base}"
            )
            assert slot.abbr_offset >= sles_base, (
                f"Slot {slot.index} abbr_offset {slot.abbr_offset} < SLES base {sles_base}"
            )

    def test_get_rom_info_valid(self):
        """get_rom_info() returns valid info with team slots."""
        info = self.reader.get_rom_info()
        assert info.is_valid is True
        assert info.size > 0
        assert len(info.team_slots) == TOTAL_TEAMS
        assert info.path == _ISO_PATH


# --- ROM writer tests ---

from services.pes6_ps2_patcher.rom_writer import PES6RomWriter, _truncate_utf8  # noqa: E402


class TestTruncateUtf8:
    """Unit tests for UTF-8 truncation (no ISO needed)."""

    def test_short_string_unchanged(self):
        """A string that fits is returned as-is."""
        result = _truncate_utf8("Hello", 10)
        assert result == b"Hello"

    def test_exact_fit(self):
        """A string that exactly fills the budget is kept."""
        result = _truncate_utf8("Hello", 5)
        assert result == b"Hello"

    def test_truncate_ascii(self):
        """ASCII string truncated to max_bytes."""
        result = _truncate_utf8("Hello World", 5)
        assert result == b"Hello"

    def test_no_split_multibyte(self):
        """Multi-byte UTF-8 chars are not split."""
        # Each char is 3 bytes in UTF-8
        result = _truncate_utf8("\u00e9\u00e9\u00e9", 4)
        # Should keep only 2 bytes (one \u00e9 = 2 bytes in UTF-8)
        assert len(result) <= 4
        # Verify it decodes cleanly
        result.decode("utf-8")

    def test_empty_string(self):
        result = _truncate_utf8("", 10)
        assert result == b""


@pytest.mark.skipif(not _HAS_ISO, reason="PES 6 ISO not available")
class TestPES6RomWriter:
    """Tests that require the real PES 6 ISO."""

    def test_write_team_name(self, tmp_path):
        """Write 'Test FC'/'TST' to Arsenal slot, read back, verify."""
        reader = PES6RomReader(_ISO_PATH)
        reader.validate()
        slots = reader.read_team_slots()
        arsenal = next(s for s in slots if s.name == "Arsenal")

        output = str(tmp_path / "patched.iso")
        writer = PES6RomWriter(_ISO_PATH, output)
        writer.write_team_name(arsenal, "Test FC", "TST")
        writer.finalize()

        reader2 = PES6RomReader(output)
        reader2.validate()
        slots2 = reader2.read_team_slots()
        updated = next(s for s in slots2 if s.index == arsenal.index)
        assert updated.name == "Test FC"
        assert updated.abbreviation == "TST"

    def test_name_truncation(self, tmp_path):
        """Write a very long name, verify it's truncated to fit within budget."""
        reader = PES6RomReader(_ISO_PATH)
        reader.validate()
        slots = reader.read_team_slots()
        arsenal = next(s for s in slots if s.name == "Arsenal")

        long_name = "A" * 100
        output = str(tmp_path / "patched.iso")
        writer = PES6RomWriter(_ISO_PATH, output)
        writer.write_team_name(arsenal, long_name, "TST")
        writer.finalize()

        reader2 = PES6RomReader(output)
        reader2.validate()
        slots2 = reader2.read_team_slots()
        updated = next(s for s in slots2 if s.index == arsenal.index)
        # Name should be truncated but non-empty
        assert len(updated.name) > 0
        assert len(updated.name.encode("utf-8")) < arsenal.name_budget

    def test_roundtrip_preserves_other_slots(self, tmp_path):
        """Write to one slot, verify other slots are unchanged."""
        reader = PES6RomReader(_ISO_PATH)
        reader.validate()
        slots = reader.read_team_slots()
        arsenal = next(s for s in slots if s.name == "Arsenal")

        output = str(tmp_path / "patched.iso")
        writer = PES6RomWriter(_ISO_PATH, output)
        writer.write_team_name(arsenal, "Test FC", "TST")
        writer.finalize()

        reader2 = PES6RomReader(output)
        reader2.validate()
        slots2 = reader2.read_team_slots()

        # Build lookup by index
        original_by_idx = {s.index: s for s in slots}
        patched_by_idx = {s.index: s for s in slots2}

        for idx, orig in original_by_idx.items():
            if idx == arsenal.index:
                continue
            patched = patched_by_idx[idx]
            assert patched.name == orig.name, (
                f"Slot {idx} name changed: {orig.name!r} -> {patched.name!r}"
            )
            assert patched.abbreviation == orig.abbreviation, (
                f"Slot {idx} abbr changed: {orig.abbreviation!r} -> {patched.abbreviation!r}"
            )
