"""Regression test for the web companion's Sports Game Updater screen.

`SportsPatcherScreen` used to expose a flat `GAMES` list. It was reorganised
into `SECTIONS` (Soccer, Basketball, Hockey, Baseball) with a divider row per
section, and the pygame screen was updated, but the web companion serializer
kept reading the attribute that no longer exists. Opening the screen in a
browser raised `AttributeError` and the companion showed nothing.

These tests pin the serializer to the sectioned list: every game reachable on
the console must be reachable in the browser, and the section headers must be
marked `is_divider` so the client renders them as headers rather than as
selectable rows.
"""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from state import AppState  # noqa: E402
from ui.screens import sports_patcher_screen as screen  # noqa: E402
from web_companion.state_serializer import serialize_web_state  # noqa: E402


def _serialize():
    state = AppState()
    state.mode = "sports_patcher"
    return serialize_web_state(state, {}, [])


def test_sports_patcher_screen_serializes():
    payload = _serialize()

    assert payload["screen_type"] == "list"
    assert payload["title"] == "Sports Game Updater"


def test_every_row_matches_the_pygame_screen():
    """The browser list and the console list must agree row for row."""
    names = [item["name"] for item in _serialize()["items"]]

    assert names == [label for label, _ in screen.sports_patcher_screen._items]


def test_section_headers_are_marked_as_dividers():
    items = _serialize()["items"]
    dividers = screen.sports_patcher_screen.get_divider_indices()

    assert dividers, "screen should have section headers"
    for index, item in enumerate(items):
        marked = item.get("is_divider", False)
        assert marked is (index in dividers), item["name"]


def test_headers_are_not_selectable_and_games_are():
    """A divider has no action; other rows route to a patcher screen."""
    items = _serialize()["items"]

    for index, item in enumerate(items):
        action = screen.sports_patcher_screen.get_action(index)
        if item.get("is_divider"):
            assert action == "divider", item["name"]
        else:
            assert action.endswith("_patcher"), (item["name"], action)
