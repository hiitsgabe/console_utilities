"""Integration test: NSZ log modal button navigation + activation.

Drives the real ConsoleUtilitiesApp._move_highlight / _select_item against a
lightweight fake `self` (so we exercise the actual routing without the heavy
app __init__). Verifies left/right move focus between Refresh/Close, up/down
scroll, and select activates the focused button.
"""

import os
import sys
from types import SimpleNamespace

import pytest

sys.argv = sys.argv[:1]
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("DEV_MODE", "true")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "nsz"))

import app as app_mod  # noqa: E402
from state import AppState  # noqa: E402
from ui.screens.modals.nsz_log_modal import NszLogModal  # noqa: E402

App = app_mod.ConsoleUtilitiesApp


def _make_app():
    fake = SimpleNamespace()
    fake.state = AppState()
    fake.screen_manager = SimpleNamespace(nsz_log_modal=NszLogModal())
    fake._android_text_modal_active = lambda: False
    # Bind the real methods under test to the fake instance.
    for name in (
        "_move_highlight",
        "_select_item",
        "_handle_nsz_log_modal_select",
        "_refresh_nsz_log_modal",
        "_open_nsz_log_modal",
    ):
        setattr(fake, name, getattr(App, name).__get__(fake))
    return fake


def test_left_right_toggle_button_focus():
    a = _make_app()
    a.state.nsz_log_modal.show = True
    a.state.nsz_log_modal.button_index = 0

    a._move_highlight("right")
    assert a.state.nsz_log_modal.button_index == 1  # moved to Close

    a._move_highlight("left")
    assert a.state.nsz_log_modal.button_index == 0  # back to Refresh


def test_up_down_scroll_log():
    a = _make_app()
    a.state.nsz_log_modal.show = True
    a.state.nsz_log_modal.lines = [f"line-{i}" for i in range(500)]
    a.state.nsz_log_modal.scroll_offset = 0

    a._move_highlight("down")
    assert a.state.nsz_log_modal.scroll_offset == 1

    a._move_highlight("up")
    assert a.state.nsz_log_modal.scroll_offset == 0


def test_select_close_button_closes_modal():
    a = _make_app()
    a.state.nsz_log_modal.show = True
    a.state.nsz_log_modal.button_index = 1  # Close focused

    a._select_item()
    assert a.state.nsz_log_modal.show is False


def test_select_refresh_button_keeps_modal_open():
    a = _make_app()
    a.state.nsz_log_modal.show = True
    a.state.nsz_log_modal.button_index = 0  # Refresh focused

    a._select_item()
    assert a.state.nsz_log_modal.show is True  # refresh must not close
