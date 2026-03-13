"""Tests for the NHL 05 PS2 patcher module.

Tests models, stat mapping, and line flag generation without requiring
a real ISO file.
"""

import os
import sys

# Add src to path so we can import the modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from services.nhl05_ps2_patcher.models import (
    NHL05_TEAM_INDEX,
    MODERN_NHL_TO_NHL05,
    NHL05_TEAM_NAMES,
    NHL05SkaterAttributes,
    NHL05GoalieAttributes,
    NHL05PlayerRecord,
    TEAM_COUNT,
    POSITION_MAP,
    POSITION_REVERSE,
    FNME_WIDTH,
    TDB_MASTER,
    TDB_ROSTER,
)
from services.nhl05_ps2_patcher.stat_mapper import (
    NHL05StatMapper,
    SKATER_DEFAULTS,
    GOALIE_DEFAULTS,
    _clamp,
    _scale,
)
from services.nhl05_ps2_patcher.rom_writer import LINE_FLAGS
from services.sports_api.models import Player


# --- Model tests ---


def test_team_index_count():
    """NHL 05 has 30 NHL teams (indices 0-29) plus 2 All-Star."""
    nhl_teams = {k: v for k, v in NHL05_TEAM_INDEX.items() if k < 30}
    assert len(nhl_teams) == 30
    assert TEAM_COUNT == 30


def test_team_index_sj_stl_swap():
    """NHL 05 swaps SJ=24 and STL=25 vs NHL 07 (STL=24, SJ=25)."""
    assert NHL05_TEAM_INDEX[24] == "SJ"
    assert NHL05_TEAM_INDEX[25] == "STL"


def test_modern_mapping_covers_all_current_teams():
    """All 32 current NHL teams should map to an NHL 05 slot."""
    current_teams = [
        "ANA", "BOS", "BUF", "CGY", "CAR", "CHI", "COL", "CBJ",
        "DAL", "DET", "EDM", "FLA", "LAK", "MIN", "MTL", "NSH",
        "NJD", "NYI", "NYR", "OTT", "PHI", "PIT", "SJS", "STL",
        "TBL", "TOR", "VAN", "WSH", "WPG", "VGK", "SEA", "UTA",
    ]
    for code in current_teams:
        assert code in MODERN_NHL_TO_NHL05, f"{code} not in MODERN_NHL_TO_NHL05"


def test_modern_mapping_espn_variants():
    """ESPN abbreviations (LA, NJ, SJ, TB) should map correctly."""
    assert MODERN_NHL_TO_NHL05["LA"] == MODERN_NHL_TO_NHL05["LAK"]
    assert MODERN_NHL_TO_NHL05["NJ"] == MODERN_NHL_TO_NHL05["NJD"]
    assert MODERN_NHL_TO_NHL05["SJ"] == MODERN_NHL_TO_NHL05["SJS"]
    assert MODERN_NHL_TO_NHL05["TB"] == MODERN_NHL_TO_NHL05["TBL"]


def test_team_names_count():
    """Should have names for all 30 NHL teams + 2 All-Star."""
    assert len(NHL05_TEAM_NAMES) == 32


def test_position_map_roundtrip():
    """Position codes should round-trip through map and reverse map."""
    for code, name in POSITION_MAP.items():
        assert POSITION_REVERSE[name] == code


def test_fnme_width():
    """FNME field is 128 bits = 16 chars."""
    assert FNME_WIDTH == 16


def test_tdb_filenames():
    """NHL 05 TDB filenames."""
    assert TDB_MASTER == "nhl2005.tdb"
    assert TDB_ROSTER == "nhlrost.tdb"


def test_skater_attrs_defaults():
    """Default skater attributes should be in valid 0-63 range."""
    attrs = NHL05SkaterAttributes()
    for f in attrs.__dataclass_fields__:
        val = getattr(attrs, f)
        if f == "fighting":
            assert 0 <= val <= 3, f"fighting={val} out of 0-3"
        else:
            assert 0 <= val <= 63, f"{f}={val} out of 0-63"


def test_goalie_attrs_defaults():
    """Default goalie attributes should be in valid 0-63 range."""
    attrs = NHL05GoalieAttributes()
    for f in attrs.__dataclass_fields__:
        val = getattr(attrs, f)
        if f == "fighting":
            assert 0 <= val <= 3, f"fighting={val} out of 0-3"
        else:
            assert 0 <= val <= 63, f"{f}={val} out of 0-63"


def test_player_record_defaults():
    """NHL05PlayerRecord should have sensible defaults."""
    rec = NHL05PlayerRecord()
    assert rec.first_name == ""
    assert rec.last_name == ""
    assert rec.position == "C"
    assert rec.jersey_number == 1
    assert rec.is_goalie is False


# --- Stat mapper tests ---


def _make_player(name="Test Player", pos="C", number=97, **kwargs):
    """Helper to create a Player with required fields."""
    parts = name.split(" ", 1)
    return Player(
        id=kwargs.get("id", 1),
        name=name,
        first_name=parts[0],
        last_name=parts[1] if len(parts) > 1 else "",
        position=pos,
        number=number,
        age=kwargs.get("age", 25),
        nationality=kwargs.get("nationality", "CAN"),
        photo_url="",
        weight=kwargs.get("weight", 190),
        handedness=kwargs.get("handedness", "R"),
    )


def test_mapper_skater_no_stats():
    """Mapper should produce valid record with no stats."""
    mapper = NHL05StatMapper()
    player = _make_player("Connor McDavid", "C", 97)
    rec = mapper.map_player(player, "EDM")
    assert rec.first_name == "Connor"
    assert rec.last_name == "McDavid"
    assert rec.position == "C"
    assert rec.jersey_number == 97
    assert rec.team_index == 11  # EDM
    assert rec.is_goalie is False
    assert rec.skater_attrs is not None
    assert rec.goalie_attrs is None


def test_mapper_goalie_no_stats():
    """Mapper should produce goalie record with goalie attrs."""
    mapper = NHL05StatMapper()
    player = _make_player("Stuart Skinner", "G", 74)
    rec = mapper.map_player(player, "EDM")
    assert rec.is_goalie is True
    assert rec.goalie_attrs is not None
    assert rec.skater_attrs is None


def test_mapper_skater_with_stats():
    """Mapper should scale stats to 0-63 range."""
    mapper = NHL05StatMapper()
    player = _make_player("Connor McDavid", "C", 97)
    stats = {"G": "40", "A": "60", "PTS": "100", "+/-": "+25", "PIM": "20", "SOG": "300", "FO%": "52"}
    rec = mapper.map_player(player, "EDM", stats)
    attrs = rec.skater_attrs
    # High-producing player should have elevated offensive stats
    assert attrs.shot_accuracy > 30
    assert attrs.puck_control > 40
    assert attrs.potential > 40


def test_mapper_goalie_with_stats():
    """Mapper should scale goalie stats properly."""
    mapper = NHL05StatMapper()
    player = _make_player("Connor Hellebuyck", "G", 37)
    stats = {"SV%": "0.921", "GAA": "2.35", "W": "35"}
    rec = mapper.map_player(player, "WPG", stats)
    attrs = rec.goalie_attrs
    # Elite goalie should have high save-related attrs
    assert attrs.rebound_ctrl > 40
    assert attrs.glove_high > 40
    assert attrs.five_hole > 40


def test_mapper_name_truncation():
    """Names longer than 15 chars should be truncated."""
    mapper = NHL05StatMapper()
    player = _make_player("Alexanderrrrrrr VeryLongLastNameHere", "C", 1)
    rec = mapper.map_player(player, "EDM")
    assert len(rec.first_name) <= 15
    assert len(rec.last_name) <= 15


def test_mapper_handedness():
    """Handedness should map L=0, R=1."""
    mapper = NHL05StatMapper()
    lefty = _make_player("Left Player", "C", 1, handedness="L")
    righty = _make_player("Right Player", "C", 2, handedness="R")
    assert mapper.map_player(lefty, "EDM").handedness == 0
    assert mapper.map_player(righty, "EDM").handedness == 1


def test_mapper_team_slot():
    """get_team_slot should return correct NHL 05 index."""
    mapper = NHL05StatMapper()
    assert mapper.get_team_slot("EDM") == 11
    assert mapper.get_team_slot("SJ") == 24
    assert mapper.get_team_slot("STL") == 25
    assert mapper.get_team_slot("WPG") == 1  # → Atlanta slot
    assert mapper.get_team_slot("INVALID") is None


def test_clamp():
    """_clamp should constrain values to [lo, hi]."""
    assert _clamp(-5) == 0
    assert _clamp(100) == 63
    assert _clamp(30) == 30
    assert _clamp(5, 10, 20) == 10


def test_scale():
    """_scale should map value ranges to 0-63."""
    assert _scale(0, 0, 100) == 0
    assert _scale(100, 0, 100) == 63
    assert _scale(50, 0, 100) == 32  # midpoint


# --- Line flags tests ---


def test_line_flags_count():
    """LINE_FLAGS should have entries for all ROST line fields."""
    assert len(LINE_FLAGS) == 64


def test_generate_team_line_flags_basic():
    """Generate line flags for a full team."""
    mapper = NHL05StatMapper()
    players = []
    # 2 goalies, 12 forwards (4C, 4LW, 4RW), 6 defense = 20 players
    for i in range(2):
        p = NHL05PlayerRecord(is_goalie=True, position="G")
        players.append(p)
    for pos in ["C", "LW", "RW"] * 4:
        p = NHL05PlayerRecord(position=pos)
        players.append(p)
    for i in range(6):
        p = NHL05PlayerRecord(position="D")
        players.append(p)

    flags = mapper.generate_team_line_flags(players)
    assert len(flags) == len(players)

    # Goalies should have G1__ and G2__
    assert flags[0].get("G1__") == 1
    assert flags[1].get("G2__") == 1

    # First center after goalies should be on L1C_
    assert flags[2].get("L1C_") == 1


def test_generate_team_line_flags_pp_pk():
    """PP and PK units should be assigned."""
    mapper = NHL05StatMapper()
    players = []
    for i in range(2):
        p = NHL05PlayerRecord(is_goalie=True, position="G")
        players.append(p)
    for pos in ["C", "LW", "RW"] * 4:
        p = NHL05PlayerRecord(position=pos)
        players.append(p)
    for i in range(6):
        p = NHL05PlayerRecord(position="D")
        players.append(p)

    flags = mapper.generate_team_line_flags(players)

    # PP (H1-H5) should be assigned to some players
    pp_assigned = sum(1 for f in flags for k, v in f.items() if k.startswith("H") and v == 1)
    assert pp_assigned == 5

    # PK (S1-S5) should be assigned to some players
    pk_assigned = sum(1 for f in flags for k, v in f.items() if k.startswith("S") and v == 1)
    assert pk_assigned >= 3  # May have fewer if not enough line 2 fwds + D3/D4


# --- Roster selection tests ---


def test_select_roster_order():
    """select_roster should put goalies first, then forwards, then defense."""
    mapper = NHL05StatMapper()
    players = [
        _make_player("Def One", "D", 1, id=1),
        _make_player("Goalie One", "G", 30, id=2),
        _make_player("Center One", "C", 10, id=3),
        _make_player("LW One", "LW", 15, id=4),
        _make_player("RW One", "RW", 20, id=5),
    ]
    selected = mapper.select_roster(players, max_players=5)
    # Goalie should be first
    assert selected[0].position == "G"
    # Defense should be last
    assert selected[-1].position == "D"


def test_select_roster_max_players():
    """select_roster should respect max_players limit."""
    mapper = NHL05StatMapper()
    players = [_make_player(f"Player {i}", "C", i, id=i) for i in range(40)]
    selected = mapper.select_roster(players, max_players=25)
    assert len(selected) == 25


# --- Skater defaults per position ---


def test_skater_defaults_all_positions():
    """Each position should have default attributes."""
    for pos in ["C", "LW", "RW", "D"]:
        assert pos in SKATER_DEFAULTS
        attrs = SKATER_DEFAULTS[pos]
        assert isinstance(attrs, NHL05SkaterAttributes)


def test_defenseman_defaults_higher_checking():
    """Defensemen should have higher checking than centers."""
    assert SKATER_DEFAULTS["D"].checking > SKATER_DEFAULTS["C"].checking


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
