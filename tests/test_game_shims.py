"""The game adapters onto `retro-roster-patcher`.

The library's own suite covers the fetching, mapping and ROM writing. What is
untested by it, and what this file is for, is the translation the app forces:
`app.py` stores the fetch result as a `{code: [Player]}` dict plus a separate
`team_stats` dict, throws the patcher away, and builds a second one for the
patch phase. The `LeagueData` the library needs therefore has to be rebuilt
from those two dicts, and a field lost in that rebuild is lost silently — the
patch still succeeds, just against the wrong data.

So the library patcher is stubbed here and the tests assert on what it was
handed. End-to-end checks against fabricated ROMs live outside the repo; this
is the part that is this repo's code.

Every adapter in `GAMES` is the same adapter, so every test runs against all of
them. That is the point of parameterising rather than copying the file per
game: if one of them drifts, the shared behaviour stops being shared and a test
says so. A game is only added here once its old-vs-new byte differential has
passed with a passing negative control.
"""

import importlib
import os
import sys
from dataclasses import dataclass

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from retro_roster_patcher.core.errors import ApiError, RomError  # noqa: E402
from retro_roster_patcher.core.models import PatchResult as LibPatchResult  # noqa: E402
from retro_roster_patcher.sports.models import (  # noqa: E402
    League,
    LeagueData,
    Player,
    Team,
    TeamRoster,
)


@dataclass(frozen=True)
class Game:
    """One adapter, plus whether it takes a `provider`.

    Only the NHL games have two providers to choose between — the library
    registers `providers=("espn", "nhl")` for them and `("espn",)` for the
    others, so the MLB and NBA adapters deliberately have no such argument and
    `app.py` must not pass one. The tests split on this field rather than
    tolerating both shapes, so that a provider appearing on an ESPN-only game,
    or vanishing from an NHL one, fails here.
    """

    module: str
    cls: str
    provider: bool = True

    def __str__(self):
        return self.module.split(".")[1]


GAMES = [
    Game("services.nhl05_ps2_patcher.patcher", "NHL05PS2Patcher"),
    Game("services.nhl07_psp_patcher.patcher", "NHL07PSPPatcher"),
    Game("services.nhl94_snes_patcher.patcher", "NHL94SNESPatcher"),
    Game("services.nhl94_genesis_patcher.patcher", "NHL94GenesisPatcher"),
    Game("services.nbalive95_patcher.patcher", "NBALive95Patcher", provider=False),
    Game("services.kgj_mlb_patcher.patcher", "KGJMLBPatcher", provider=False),
]


@pytest.fixture(params=GAMES, ids=str)
def game(request):
    return request.param


@pytest.fixture(params=[g for g in GAMES if g.provider], ids=str)
def provider_game(request):
    return request.param


@pytest.fixture(params=[g for g in GAMES if not g.provider], ids=str)
def espn_only_game(request):
    return request.param


def patcher_class(game):
    return getattr(importlib.import_module(game.module), game.cls)


def player(pid, name="Some One", position="C"):
    return Player(id=pid, name=name, position=position)


def roster(code, players, leaders=None):
    return TeamRoster(
        team=Team(id=0, name=code, code=code),
        players=players,
        extra={"leaders": leaders or {}},
    )


def league_data(rosters):
    return LeagueData(league=League(id=0, name="NHL", season=2025), teams=rosters)


class StubLibPatcher:
    """Stands in for the library patcher and records what it was handed."""

    def __init__(self, cache_dir, *, provider=None, on_status=None, **_):
        self.cache_dir = cache_dir
        self.provider = provider
        self.on_status = on_status
        self.fetch_calls = []
        self.mapped = []
        self.patch_calls = []
        self.fetch_result = league_data([])
        self.patch_result = LibPatchResult(
            output_path="/out.iso", teams_patched=0, players_patched=0
        )
        self.fetch_raises = None
        self.map_raises = None
        self.patch_raises = None

    def fetch(self, *, season, league_id=None, on_progress=None):
        self.fetch_calls.append({"season": season, "on_progress": on_progress})
        if self.fetch_raises:
            raise self.fetch_raises
        return self.fetch_result

    def map_rosters(self, data, slot_mapping=None):
        self.mapped.append(data)
        if self.map_raises:
            raise self.map_raises
        return data

    def patch(self, *, rom_path, output_path, rosters, on_progress=None, **options):
        self.patch_calls.append(
            {"rom_path": rom_path, "output_path": output_path, "rosters": rosters}
        )
        if self.patch_raises:
            raise self.patch_raises
        return self.patch_result


def install_stub(monkeypatch, game):
    """Swap the adapter's `_LibPatcher` for the stub. Returns the created list.

    The uniform alias is what makes this work for every game, and is why the
    shims import the library class under one name rather than a per-game one.
    """
    module = importlib.import_module(game.module)
    created = []

    def factory(*args, **kwargs):
        created.append(StubLibPatcher(*args, **kwargs))
        return created[-1]

    monkeypatch.setattr(module, "_LibPatcher", factory)
    return created


@pytest.fixture
def stubbed(monkeypatch, game):
    """An adapter whose library patcher is a stub, exposed as `.stub`."""
    created = install_stub(monkeypatch, game)
    shim = patcher_class(game)("/cache")
    shim.stub = created[0]
    return shim


# ---------------------------------------------------------------- construction


def test_cache_dir_and_status_reach_the_library(monkeypatch, game):
    created = install_stub(monkeypatch, game)

    def on_status(msg):
        pass

    shim = patcher_class(game)("/cache", on_status=on_status)

    assert created[0].cache_dir == "/cache"
    assert created[0].on_status is on_status
    # The app reads this back off the shim itself.
    assert shim.cache_dir == "/cache"


def test_provider_reaches_the_library(monkeypatch, provider_game):
    created = install_stub(monkeypatch, provider_game)

    shim = patcher_class(provider_game)("/cache", provider="nhl")

    assert created[0].provider == "nhl"
    # `app.py` reads it back off the shim to label the fetch.
    assert shim.provider == "nhl"


def test_an_espn_only_game_refuses_a_provider(espn_only_game):
    """Not a courtesy check. The library registers one provider for these two,
    so a `provider=` that the shim quietly swallowed would read as a working
    choice at the call site while changing nothing."""
    with pytest.raises(TypeError):
        patcher_class(espn_only_game)("/cache", provider="nhl")


def test_team_stats_exists_before_any_fetch(stubbed):
    """The old classes only created it inside `fetch_rosters`, so `app.py` reads
    it through `getattr(patcher, "team_stats", {})`. Same answer, no raise."""
    assert stubbed.team_stats == {}


# ------------------------------------------------------------------- fetching


def test_fetch_flattens_to_code_keyed_players(stubbed):
    a, b = player(1), player(2)
    stubbed.stub.fetch_result = league_data([roster("ANA", [a]), roster("BOS", [b])])

    result = stubbed.fetch_rosters(season=2024)

    assert result == {"ANA": [a], "BOS": [b]}
    assert stubbed.stub.fetch_calls[0]["season"] == 2024


def test_fetch_lifts_leaders_onto_team_stats(stubbed):
    leaders = {"1": {"PTS": 40}}
    stubbed.stub.fetch_result = league_data([roster("ANA", [player(1)], leaders)])

    stubbed.fetch_rosters()

    assert stubbed.team_stats == {"ANA": leaders}


def test_fetch_drops_a_team_with_no_players(stubbed):
    """The old behaviour: no key at all, rather than a key mapping to []."""
    stubbed.stub.fetch_result = league_data([roster("ANA", []), roster("BOS", [player(2)])])

    assert list(stubbed.fetch_rosters()) == ["BOS"]


def test_fetch_drops_a_team_with_no_leaders(stubbed):
    stubbed.stub.fetch_result = league_data(
        [roster("ANA", [player(1)]), roster("BOS", [player(2)], {"2": {"PTS": 1}})]
    )

    stubbed.fetch_rosters()

    assert list(stubbed.team_stats) == ["BOS"]


def test_fetch_replaces_team_stats_rather_than_accumulating(stubbed):
    stubbed.stub.fetch_result = league_data([roster("ANA", [player(1)], {"1": {"PTS": 1}})])
    stubbed.fetch_rosters()
    stubbed.stub.fetch_result = league_data([roster("BOS", [player(2)], {"2": {"PTS": 2}})])
    stubbed.fetch_rosters()

    assert list(stubbed.team_stats) == ["BOS"]


def test_fetch_forwards_the_progress_callback(stubbed):
    def on_progress(fraction, message):
        pass

    stubbed.fetch_rosters(on_progress=on_progress)

    assert stubbed.stub.fetch_calls[0]["on_progress"] is on_progress


def test_fetch_propagates_an_api_error(stubbed):
    """`app.py` catches it and shows the text; the old code went quiet instead."""
    stubbed.stub.fetch_raises = ApiError("provider returned no teams")

    with pytest.raises(ApiError):
        stubbed.fetch_rosters()


# ------------------------------------------------------- rebuilding LeagueData


def test_patch_rebuilds_players_under_the_right_code(stubbed):
    a, b = player(1), player(2)

    stubbed.patch_rom("/in.iso", "/out.iso", {"ANA": [a], "BOS": [b]})

    rebuilt = {r.team.code: r.players for r in stubbed.stub.mapped[0].teams}
    assert rebuilt == {"ANA": [a], "BOS": [b]}


def test_patch_puts_team_stats_back_into_extra_leaders(stubbed):
    """The one field `map_rosters` reads besides `code` and `players`."""
    leaders = {"1": {"PTS": 40, "G": 12}}
    stubbed.team_stats = {"ANA": leaders}

    stubbed.patch_rom("/in.iso", "/out.iso", {"ANA": [player(1)]})

    assert stubbed.stub.mapped[0].teams[0].extra["leaders"] == leaders


def test_patch_gives_a_team_with_no_stats_an_empty_leaders_dict(stubbed):
    """Not a missing key: every `map_rosters` does `extra.get("leaders") or {}`,
    but the ROM slot lookup happens first and a KeyError here would abort it."""
    stubbed.patch_rom("/in.iso", "/out.iso", {"ANA": [player(1)]})

    assert stubbed.stub.mapped[0].teams[0].extra["leaders"] == {}


def test_patch_orders_teams_by_code(stubbed):
    """Several modern abbreviations fold onto one ROM slot, so which of a
    colliding pair wins depends on iteration order. Pin it."""
    stubbed.patch_rom(
        "/in.iso", "/out.iso", {"WSH": [player(3)], "ANA": [player(1)], "BOS": [player(2)]}
    )

    assert [r.team.code for r in stubbed.stub.mapped[0].teams] == ["ANA", "BOS", "WSH"]


def test_patch_does_not_alias_the_callers_player_lists(stubbed):
    """The app keeps its `rosters` dict alive across repeated patch attempts."""
    players = [player(1)]

    stubbed.patch_rom("/in.iso", "/out.iso", {"ANA": players})

    assert stubbed.stub.mapped[0].teams[0].players is not players


def test_patch_forwards_paths_and_progress(stubbed):
    def on_progress(fraction, message):
        pass

    stubbed.patch_rom("/in.iso", "/out.iso", {"ANA": [player(1)]}, on_progress=on_progress)

    call = stubbed.stub.patch_calls[0]
    assert str(call["rom_path"]) == "/in.iso"
    assert str(call["output_path"]) == "/out.iso"
    assert call["rosters"] is stubbed.stub.mapped[0]


# -------------------------------------------------------------- patch results


def test_patch_reports_success_with_the_libraries_counts(stubbed):
    stubbed.stub.patch_result = LibPatchResult(
        output_path="/out.iso", teams_patched=30, players_patched=750
    )

    result = stubbed.patch_rom("/in.iso", "/out.iso", {"ANA": [player(1)]})

    assert (result.success, result.output_path) == (True, "/out.iso")
    assert (result.teams_patched, result.players_patched) == (30, 750)
    assert result.error == ""


def test_patch_turns_a_library_error_into_a_failed_result(stubbed):
    stubbed.stub.patch_raises = RomError("the archive is truncated")

    result = stubbed.patch_rom("/in.iso", "/out.iso", {"ANA": [player(1)]})

    assert result.success is False
    assert "truncated" in result.error
    assert result.output_path == ""


def test_a_mapping_failure_is_also_a_failed_result(stubbed):
    stubbed.stub.map_raises = RomError("no slot matched")

    assert stubbed.patch_rom("/in.iso", "/out.iso", {"ANA": [player(1)]}).success is False


def test_a_non_library_exception_still_propagates(stubbed):
    """A bug must not be laundered into a tidy error message on screen."""
    stubbed.stub.patch_raises = ZeroDivisionError("bug")

    with pytest.raises(ZeroDivisionError):
        stubbed.patch_rom("/in.iso", "/out.iso", {"ANA": [player(1)]})


# ------------------------------------------------------------------- analysis


def test_analyze_rom_of_a_missing_file_is_invalid_rather_than_raising(tmp_path, game):
    """Two call sites per game run this on the pygame main thread when a ROM is
    picked, and `app.py` only ever reads `is_valid`.

    Unstubbed, so it is also the one check that the real library constructor
    accepts the arguments the shim passes. It needs a writable cache dir: the
    library's API clients create it eagerly.
    """
    info = patcher_class(game)(str(tmp_path)).analyze_rom("/does/not/exist.iso")

    assert info.is_valid is False
    assert info.size == 0
