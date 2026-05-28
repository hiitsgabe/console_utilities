"""Tests for scraper orchestration (GAB-18).

The module under test is dependency-free (typing only), imported by file
path to avoid services/__init__.py side effects. A lazy loader keeps test
collection clean before the module file exists.
"""

import importlib.util
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

_mod_path = os.path.join(
    os.path.dirname(__file__),
    "..",
    "src",
    "services",
    "scraper_orchestration.py",
)


def _load():
    """Lazily import the module by file path inside each test."""
    spec = importlib.util.spec_from_file_location(
        "scraper_orchestration", _mod_path
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeProvider:
    def __init__(self, configured=True, results=None, error="", record=None):
        self._configured = configured
        self._results = results
        self._error = error
        self._record = record

    def is_configured(self):
        return self._configured

    def search_game(self, name, system_id=""):
        if self._record is not None:
            self._record.append((name, system_id))
        return (bool(self._results), self._results or [], self._error)


def make_factory(mapping):
    """mapping: name -> provider. The name "boom" raises."""

    def factory(name, settings):
        if name == "boom":
            raise RuntimeError("x")
        return mapping[name]

    return factory


# --- ordered_configured_providers ---------------------------------------


def test_ordering_primary_first():
    mod = _load()
    mapping = {
        "a": FakeProvider(),
        "b": FakeProvider(),
        "c": FakeProvider(),
    }
    out = mod.ordered_configured_providers(
        "a", True, ["b", "c"], {}, make_factory(mapping)
    )
    assert [name for name, _ in out] == ["a", "b", "c"]


def test_fallback_disabled_primary_only():
    mod = _load()
    mapping = {"a": FakeProvider(), "b": FakeProvider()}
    out = mod.ordered_configured_providers(
        "a", False, ["b", "c"], {}, make_factory(mapping)
    )
    assert [name for name, _ in out] == ["a"]


def test_unconfigured_filtered_out():
    mod = _load()
    mapping = {
        "a": FakeProvider(configured=True),
        "b": FakeProvider(configured=False),
        "c": FakeProvider(configured=True),
    }
    out = mod.ordered_configured_providers(
        "a", True, ["b", "c"], {}, make_factory(mapping)
    )
    assert [name for name, _ in out] == ["a", "c"]


def test_factory_exception_skipped():
    mod = _load()
    mapping = {"a": FakeProvider(), "c": FakeProvider()}
    out = mod.ordered_configured_providers(
        "a", True, ["boom", "c"], {}, make_factory(mapping)
    )
    assert [name for name, _ in out] == ["a", "c"]


def test_dedup_primary_in_chain():
    mod = _load()
    mapping = {"a": FakeProvider(), "b": FakeProvider()}
    out = mod.ordered_configured_providers(
        "a", True, ["a", "b"], {}, make_factory(mapping)
    )
    assert [name for name, _ in out] == ["a", "b"]


# --- search_game_with_fallback -------------------------------------------


def test_search_returns_first_non_empty():
    mod = _load()
    p = FakeProvider(results=["hit"])
    success, result, error, name = mod.search_game_with_fallback(
        "game", "sys", [("a", p)]
    )
    assert success is True
    assert result == "hit"
    assert error == ""
    assert name == "a"


def test_auth_error_skips_and_continues():
    mod = _load()
    bad = FakeProvider(error="API key invalid")
    good = FakeProvider(results=["hit"])
    success, result, error, name = mod.search_game_with_fallback(
        "game", "sys", [("a", bad), ("b", good)]
    )
    assert success is True
    assert result == "hit"
    assert name == "b"


def test_all_empty_returns_false():
    mod = _load()
    p1 = FakeProvider(results=[])
    p2 = FakeProvider(results=[])
    success, result, error, name = mod.search_game_with_fallback(
        "game", "sys", [("a", p1), ("b", p2)]
    )
    assert success is False
    assert result is None
    assert isinstance(error, str) and error
    assert name is None


def test_non_auth_error_tracked_as_last_error():
    mod = _load()
    p = FakeProvider(results=[], error="network down")
    success, result, error, name = mod.search_game_with_fallback(
        "game", "sys", [("a", p)]
    )
    assert success is False
    assert "network down" in error
    assert name is None


def test_name_adapter_applied():
    mod = _load()
    record = []
    p = FakeProvider(results=["hit"], record=record)
    mod.search_game_with_fallback(
        "game", "sys", [("a", p)], name_adapter=lambda n, prov: n.upper()
    )
    assert record == [("GAME", "sys")]


# --- search_same_platform_then_expand ------------------------------------


def test_same_platform_hit_on_primary():
    mod = _load()
    record = []
    p = FakeProvider(results=["hit"], record=record)
    success, result, error, name = mod.search_same_platform_then_expand(
        "game", "primary", [("a", p)], other_system_ids=["x", "y"]
    )
    assert success is True
    assert record == [("game", "primary")]


def test_expands_to_other_platform_when_primary_empty():
    mod = _load()

    class SnesOnly:
        def is_configured(self):
            return True

        def search_game(self, name, system_id=""):
            if system_id == "snes":
                return (True, ["hit"], "")
            return (False, [], "")

    p = SnesOnly()
    success, result, error, name = mod.search_same_platform_then_expand(
        "game", "primary", [("a", p)], other_system_ids=["snes"]
    )
    assert success is True
    assert result == "hit"


def test_expand_returns_provider_name():
    mod = _load()
    p = FakeProvider(results=["hit"])
    success, result, error, name = mod.search_same_platform_then_expand(
        "game", "primary", [("zebra", p)], other_system_ids=["x"]
    )
    assert success is True
    assert name == "zebra"
