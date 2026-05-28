"""Tests for auto-scrape gating and new-completion detection (GAB-19)."""

import importlib.util
import os
import sys

# Run headless so importing anything pygame-adjacent never opens a window/audio.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

# Make src/ importable for parity with the rest of the suite, though we load
# the module by file path to avoid services/__init__.py side effects.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

_MOD_PATH = os.path.join(
    os.path.dirname(__file__), "..", "src", "services", "auto_scrape.py"
)


def _load():
    """Lazily load auto_scrape by file path.

    Loading lazily (inside each test) keeps pytest collection clean: the import
    error surfaces as a test failure rather than a collection error while
    src/services/auto_scrape.py does not yet exist.
    """
    spec = importlib.util.spec_from_file_location("auto_scrape", _MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Stubs for new_completions.
_id_of = lambda d: d["id"]
_status_of = lambda d: d["status"]


class TestShouldAutoScrape:
    def test_all_true(self):
        should_auto_scrape = _load().should_auto_scrape
        assert (
            should_auto_scrape(
                {
                    "auto_scrape_after_download": True,
                    "scraper_enabled": True,
                    "scraper_provider": "libretro",
                }
            )
            is True
        )

    def test_auto_flag_false(self):
        should_auto_scrape = _load().should_auto_scrape
        assert (
            should_auto_scrape(
                {
                    "auto_scrape_after_download": False,
                    "scraper_enabled": True,
                    "scraper_provider": "libretro",
                }
            )
            is False
        )

    def test_scraper_disabled(self):
        should_auto_scrape = _load().should_auto_scrape
        assert (
            should_auto_scrape(
                {
                    "auto_scrape_after_download": True,
                    "scraper_enabled": False,
                    "scraper_provider": "libretro",
                }
            )
            is False
        )

    def test_provider_empty(self):
        should_auto_scrape = _load().should_auto_scrape
        assert (
            should_auto_scrape(
                {
                    "auto_scrape_after_download": True,
                    "scraper_enabled": True,
                    "scraper_provider": "",
                }
            )
            is False
        )

    def test_provider_none(self):
        should_auto_scrape = _load().should_auto_scrape
        assert (
            should_auto_scrape(
                {
                    "auto_scrape_after_download": True,
                    "scraper_enabled": True,
                    "scraper_provider": None,
                }
            )
            is False
        )

    def test_missing_keys_default_false(self):
        should_auto_scrape = _load().should_auto_scrape
        assert should_auto_scrape({}) is False


class TestNewCompletions:
    def test_detects_transition_to_completed(self):
        new_completions = _load().new_completions
        prev = {1: "downloading"}
        items = [{"id": 1, "status": "completed"}]
        assert new_completions(prev, items, _id_of, _status_of) == [1]

    def test_ignores_already_completed(self):
        new_completions = _load().new_completions
        prev = {1: "completed"}
        items = [{"id": 1, "status": "completed"}]
        assert new_completions(prev, items, _id_of, _status_of) == []

    def test_ignores_non_completed(self):
        new_completions = _load().new_completions
        prev = {}
        items = [{"id": 1, "status": "downloading"}]
        assert new_completions(prev, items, _id_of, _status_of) == []

    def test_multiple_items_mixed(self):
        new_completions = _load().new_completions
        prev = {1: "completed", 2: "downloading"}
        items = [
            {"id": 1, "status": "completed"},
            {"id": 2, "status": "completed"},
            {"id": 3, "status": "downloading"},
        ]
        assert new_completions(prev, items, _id_of, _status_of) == [2]

    def test_empty_prev_completed_is_new(self):
        new_completions = _load().new_completions
        prev = {}
        items = [{"id": 5, "status": "completed"}]
        assert new_completions(prev, items, _id_of, _status_of) == [5]
