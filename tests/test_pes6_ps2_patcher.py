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
