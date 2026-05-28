"""Tests for search outcome classification (GAB-12)."""

import importlib.util
import os

# Be safe: ensure headless SDL before any pygame-touching import. The target
# module is pure and should not import pygame, but set this defensively.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


def _load():
    """Load scraper_outcome directly by file path.

    Avoids services/__init__.py (which pulls in heavy deps that crash under
    pytest). The target module has no relative imports, so loading it by path
    is clean. Loaded lazily inside each test so collection stays clean and
    failures point at the missing module/function (the right reason).
    """
    mod_path = os.path.join(
        os.path.dirname(__file__), "..", "src", "services", "scraper_outcome.py"
    )
    spec = importlib.util.spec_from_file_location("scraper_outcome", mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestClassifySearchOutcome:
    def test_success_with_results(self):
        mod = _load()
        assert mod.classify_search_outcome(True, [object()], "") == "success"

    def test_success_empty_results_is_no_match(self):
        mod = _load()
        assert mod.classify_search_outcome(True, [], "") == "no_match"

    def test_failure_is_error(self):
        mod = _load()
        assert mod.classify_search_outcome(False, [], "boom") == "error"

    def test_failure_with_empty_error_still_error(self):
        mod = _load()
        assert mod.classify_search_outcome(False, [], "") == "error"

    def test_no_match_independent_of_error_text(self):
        mod = _load()
        assert mod.classify_search_outcome(True, [], "ignored") == "no_match"

    def test_failure_takes_precedence_over_results(self):
        mod = _load()
        assert mod.classify_search_outcome(False, [object()], "x") == "error"
