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
