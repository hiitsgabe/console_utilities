"""Tests for _dedupe_game_list in src/services/file_listing.py (GAB-16)."""

import importlib.util
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

_src = os.path.join(os.path.dirname(__file__), "..", "src")
sys.path.insert(0, _src)
_mp = os.path.join(_src, "services", "file_listing.py")
_spec = importlib.util.spec_from_file_location("file_listing", _mp)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
dedupe = _mod._dedupe_game_list


def _chosen(result):
    """Extract the single chosen filename from a result list."""
    assert len(result) == 1
    f = result[0]
    return f.get("filename", "") if isinstance(f, dict) else str(f)


def _filenames(result):
    out = []
    for f in result:
        out.append(f.get("filename", "") if isinstance(f, dict) else str(f))
    return out


def test_merges_same_normalized_name():
    files = [
        {"filename": "Cool Game (USA).zip", "size": 10},
        {"filename": "Cool Game (Europe).zip", "size": 10},
    ]
    result = dedupe(files)
    assert len(result) == 1


def test_usa_beats_europe():
    files = [
        {"filename": "Cool Game (USA).zip", "size": 10},
        {"filename": "Cool Game (Europe).zip", "size": 10},
    ]
    result = dedupe(files)
    assert "(USA)" in _chosen(result)


def test_mixed_case_usa_beats_europe():
    # RED test: on current case-sensitive code, "(usa)" falls to region 4,
    # so the larger Europe entry wins. Passes after case-insensitive fix.
    files = [
        {"filename": "Cool Game (usa).zip", "size": 10},
        {"filename": "Cool Game (Europe).zip", "size": 20},
    ]
    result = dedupe(files)
    assert _chosen(result) == "Cool Game (usa).zip"


def test_size_tiebreak():
    files = [
        {"filename": "Cool Game (USA).zip", "size": 5},
        {"filename": "Cool Game (USA) (Rev 1).zip", "size": 50},
    ]
    result = dedupe(files)
    assert result[0].get("size") == 50


def test_world_beats_europe():
    files = [
        {"filename": "Cool Game (World).zip", "size": 10},
        {"filename": "Cool Game (Europe).zip", "size": 10},
    ]
    result = dedupe(files)
    assert "(World)" in _chosen(result)


def test_usa_europe_combo_ranking():
    # (USA, Europe) beats (Europe)
    files = [
        {"filename": "Cool Game (USA, Europe).zip", "size": 10},
        {"filename": "Cool Game (Europe).zip", "size": 10},
    ]
    result = dedupe(files)
    assert "(USA, Europe)" in _chosen(result)

    # (USA) beats (USA, Europe)
    files2 = [
        {"filename": "Other Game (USA).zip", "size": 10},
        {"filename": "Other Game (USA, Europe).zip", "size": 10},
    ]
    result2 = dedupe(files2)
    assert _chosen(result2) == "Other Game (USA).zip"


def test_malformed_entries_no_crash():
    files = [
        "barestring",
        {"filename": "X (USA).zip"},
        {"size": 5},
    ]
    result = dedupe(files)
    assert isinstance(result, list)


def test_empty_list():
    assert dedupe([]) == []


def test_distinct_games_preserved():
    files = [
        {"filename": "Game One (USA).zip", "size": 10},
        {"filename": "Game Two (USA).zip", "size": 10},
    ]
    result = dedupe(files)
    assert len(result) == 2
