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
