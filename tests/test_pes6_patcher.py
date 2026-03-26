"""Tests for PES6 EUR patcher."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import importlib.util as _ilu

_spec = _ilu.spec_from_file_location(
    "models",
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "src",
        "services",
        "pes6_ps2_patcher",
        "models.py",
    ),
)
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


def test_attr_offsets_has_all_26_attributes():
    """ATTR_OFFSETS contains all 26 core attributes."""
    offsets = _mod.ATTR_OFFSETS
    assert len(offsets) >= 26
    for attr in [
        "attack", "defence", "balance", "stamina", "speed",
        "acceleration", "response", "agility", "dribble_accuracy",
        "dribble_speed", "short_pass_accuracy", "short_pass_speed",
        "long_pass_accuracy", "long_pass_speed", "shot_accuracy",
        "shot_power", "shot_technique", "free_kick", "curling",
        "heading", "jump", "teamwork", "technique", "aggression",
        "mentality", "gk_ability",
    ]:
        assert attr in offsets, f"Missing attribute: {attr}"


def test_attr_offset_values():
    """Each offset entry has (offset, shift, mask) tuple."""
    offsets = _mod.ATTR_OFFSETS
    for name, (off, shift, mask) in offsets.items():
        assert 0 <= off <= 75, f"{name} offset {off} out of range"
        assert 0 <= shift <= 15, f"{name} shift {shift} out of range"
        assert mask > 0, f"{name} mask must be positive"


def test_eur_nationality_map():
    """EUR nationality map uses PES6 EUR codes."""
    nat_map = _mod.EUR_NATIONALITY_MAP
    assert nat_map["England"] == 6
    assert nat_map["Brazil"] == 45
    assert nat_map["Spain"] == 26
    assert nat_map["Germany"] == 9
    assert nat_map["France"] == 8
    assert nat_map["Italy"] == 13


def test_position_codes_12_values():
    """Position codes cover all 12 PES6 EUR positions."""
    codes = _mod.EUR_POSITION_CODES
    assert codes["GK"] == 0
    assert codes["CF"] == 11
    assert len(codes) == 12


def _load_roster_map_module():
    """Load roster_map module via importlib."""
    rm_spec = _ilu.spec_from_file_location(
        "roster_map",
        os.path.join(
            os.path.dirname(__file__),
            "..", "src", "services", "pes6_ps2_patcher", "roster_map.py",
        ),
    )
    rm_mod = _ilu.module_from_spec(rm_spec)
    rm_mod.__spec__ = rm_spec
    rm_spec.loader.exec_module(rm_mod)
    return rm_mod


def _make_mock_roster_map(rm_mod, teams):
    """Create a RosterMap with injected team data."""
    rm = rm_mod.RosterMap.__new__(rm_mod.RosterMap)
    rm._teams = teams
    rm._meta = {"version": "pes6-eur", "total_players_in_db": 100, "slpm_offset": 21}
    return rm


def test_roster_map_get_team_players():
    """get_team_players returns list of {idx, pos} dicts."""
    rm_mod = _load_roster_map_module()
    teams = {
        "7": {
            "name": "Arsenal", "ri": 7, "si": 28,
            "player_count": 2,
            "players": [{"idx": 100, "pos": 11}, {"idx": 101, "pos": 2}],
        }
    }
    rm = _make_mock_roster_map(rm_mod, teams)
    players = rm.get_team_players(7)
    assert len(players) == 2
    assert players[0] == {"idx": 100, "pos": 11}
    assert players[1] == {"idx": 101, "pos": 2}


def test_roster_map_get_team_player_ids_new_format():
    """get_team_player_ids extracts idx from new {idx, pos} format."""
    rm_mod = _load_roster_map_module()
    teams = {
        "7": {
            "name": "Arsenal", "ri": 7, "si": 28,
            "player_count": 2,
            "players": [{"idx": 100, "pos": 11}, {"idx": 101, "pos": 2}],
        }
    }
    rm = _make_mock_roster_map(rm_mod, teams)
    ids = rm.get_team_player_ids(7)
    assert ids == [100, 101]


def test_roster_map_get_team_player_ids_old_format():
    """get_team_player_ids still works with old pi format."""
    rm_mod = _load_roster_map_module()
    teams = {
        "7": {"ri": 7, "si": 28, "pi": [200, 201, 202]}
    }
    rm = _make_mock_roster_map(rm_mod, teams)
    ids = rm.get_team_player_ids(7)
    assert ids == [200, 201, 202]


def test_roster_map_get_team_name():
    """get_team_name returns team name string."""
    rm_mod = _load_roster_map_module()
    teams = {
        "7": {"name": "Arsenal", "ri": 7, "si": 28, "player_count": 23, "players": []},
    }
    rm = _make_mock_roster_map(rm_mod, teams)
    assert rm.get_team_name(7) == "Arsenal"
    assert rm.get_team_name(999) == ""


def test_roster_map_get_team_player_count():
    """get_team_player_count returns player_count field."""
    rm_mod = _load_roster_map_module()
    teams = {
        "7": {
            "name": "Arsenal", "ri": 7, "si": 28,
            "player_count": 23,
            "players": [{"idx": i, "pos": 0} for i in range(23)],
        }
    }
    rm = _make_mock_roster_map(rm_mod, teams)
    assert rm.get_team_player_count(7) == 23
    assert rm.get_team_player_count(999) == 0


def _ensure_pes6_package():
    """Set up package hierarchy so relative imports work in pes6_ps2_patcher."""
    import types

    pkg_dir = os.path.join(
        os.path.dirname(__file__), "..", "src", "services", "pes6_ps2_patcher",
    )
    if "services" not in sys.modules:
        sp = types.ModuleType("services")
        sp.__path__ = [os.path.join(os.path.dirname(__file__), "..", "src", "services")]
        sys.modules["services"] = sp
    if "services.pes6_ps2_patcher" not in sys.modules:
        pp = types.ModuleType("services.pes6_ps2_patcher")
        pp.__path__ = [pkg_dir]
        sys.modules["services.pes6_ps2_patcher"] = pp
    if "services.pes6_ps2_patcher.models" not in sys.modules:
        ms = _ilu.spec_from_file_location(
            "services.pes6_ps2_patcher.models",
            os.path.join(pkg_dir, "models.py"),
        )
        mm = _ilu.module_from_spec(ms)
        sys.modules["services.pes6_ps2_patcher.models"] = mm
        ms.loader.exec_module(mm)
    return pkg_dir


def _load_rom_writer_module():
    """Load rom_writer module via importlib with package context for relative imports."""
    pkg_dir = _ensure_pes6_package()
    rw_spec = _ilu.spec_from_file_location(
        "services.pes6_ps2_patcher.rom_writer",
        os.path.join(pkg_dir, "rom_writer.py"),
    )
    rw_mod = _ilu.module_from_spec(rw_spec)
    rw_mod.__package__ = "services.pes6_ps2_patcher"
    rw_spec.loader.exec_module(rw_mod)
    return rw_mod


def test_write_stat_field_basic():
    """_write_stat_field writes a 7-bit value at correct offset."""
    rw_mod = _load_rom_writer_module()
    writer = rw_mod.RomWriter.__new__(rw_mod.RomWriter)

    data = bytearray(124)
    # Write attack=85 at offset 7, shift 0, mask 0x7F
    writer._write_stat_field(data, 0, 7, 0, 0x7F, 85)

    # Read back: 16-bit LE from bytes [48+7-1, 48+7] = [54, 55]
    val = (data[54] | (data[55] << 8)) & 0x7F
    assert val == 85


def test_write_stat_field_preserves_other_bits():
    """Writing a stat preserves adjacent bits."""
    rw_mod = _load_rom_writer_module()
    writer = rw_mod.RomWriter.__new__(rw_mod.RomWriter)

    data = bytearray(124)
    # Set bit 7 of byte 54 (e.g., a position flag)
    data[54] = 0x80

    # Write attack=50 at offset 7
    writer._write_stat_field(data, 0, 7, 0, 0x7F, 50)

    val = (data[54] | (data[55] << 8)) & 0x7F
    assert val == 50
    # Upper bit preserved
    assert data[54] & 0x80 == 0x80


def test_write_stat_field_with_shift():
    """Fields with non-zero shift write to correct bit position."""
    rw_mod = _load_rom_writer_module()
    writer = rw_mod.RomWriter.__new__(rw_mod.RomWriter)

    data = bytearray(124)
    # Write regPos=11 (CF) at offset 6, shift 4, mask 0x0F
    writer._write_stat_field(data, 0, 6, 4, 0x0F, 11)

    # Read back
    val = ((data[53] | (data[54] << 8)) >> 4) & 0x0F
    assert val == 11


def test_write_record_writes_name_and_attributes():
    """_write_record writes name, shirt, position, nationality, and stats."""
    rw_mod = _load_rom_writer_module()
    writer = rw_mod.RomWriter.__new__(rw_mod.RomWriter)

    data = bytearray(124)
    attrs = _mod.PES6PlayerAttributes(
        attack=85, defence=70, balance=65, stamina=80,
        speed=75, acceleration=78, response=72, agility=68,
        dribble_accuracy=80, dribble_speed=74,
        short_pass_accuracy=82, short_pass_speed=76,
        long_pass_accuracy=70, long_pass_speed=68,
        shot_accuracy=85, shot_power=82, shot_technique=78,
        free_kick=65, curling=60, heading=72, jump=70,
        teamwork=75, technique=80, aggression=65, mentality=78,
        gk_ability=20, consistency=6, condition=5,
    )
    player = _mod.PES6PlayerRecord(
        name="Test Player",
        shirt_name="PLAYER",
        position=11,  # CF
        nationality=6,  # England
        age=27,
        height=180,
        weight=75,
        attributes=attrs,
        file35_index=1,
    )

    writer._write_record(data, 0, player)

    # Check name
    assert b"T\x00e\x00s\x00t\x00" in data[0:32]

    # Check attack (offset 7 from byte 48, bytes 54-55)
    val = (data[54] | (data[55] << 8)) & 0x7F
    assert val == 85

    # Check defence (offset 8 from byte 48, bytes 55-56)
    val = (data[55] | (data[56] << 8)) & 0x7F
    assert val == 70

    # Check nationality (offset 65 from byte 48, bytes 112-113)
    nat_val = (data[112] | (data[113] << 8)) & 0x7F
    assert nat_val == 6

    # Check age (offset 65, shift 9, mask 0x1F — stored as age-15=12)
    age_val = ((data[112] | (data[113] << 8)) >> 9) & 0x1F
    assert age_val == 12  # 27 - 15

    # Check abilityEdited flag (offset 40, bit 4)
    assert data[48 + 40] & (1 << 4) != 0
