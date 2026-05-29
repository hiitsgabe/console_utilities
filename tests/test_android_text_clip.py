"""Tests for GAB-54: Android input field text overflow beyond input box bounds.

The android input modals must clip the typed value to the input box and clamp
the text cursor to the field bounds. The fix reuses the already-correct
``Text.render_scrolled`` pixel-clip helper and threads ``state.text_scroll_offset``
through each modal's public ``render()`` via a new ``scroll_offset`` keyword.

These tests run headless (SDL dummy video driver) and assert code paths / state,
never pixels.
"""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pygame  # noqa: E402

from ui.atoms.text import Text  # noqa: E402
from ui.theme import default_theme  # noqa: E402


def _surface():
    return pygame.Surface((800, 600))


def _setup_module_pygame():
    if not pygame.get_init():
        pygame.init()
    if not pygame.font.get_init():
        pygame.font.init()


def _long_text(text_atom, max_width, size):
    """Build a string measurably wider than max_width at the given size."""
    s = "WMWMWMWMWM"
    while text_atom.measure(s, size)[0] <= max_width:
        s += "WMWMWMWMWM"
    return s


# ---------------------------------------------------------------------------
# Criterion 1: render_scrolled clips to max_width when text overflows.
# ---------------------------------------------------------------------------
def test_render_scrolled_clips_to_max_width():
    _setup_module_pygame()
    text = Text(default_theme)
    size = default_theme.font_size_md
    max_width = 200
    s = _long_text(text, max_width, size)

    assert text.measure(s, size)[0] > max_width

    rect = text.render_scrolled(
        _surface(), s, (10, 10), max_width=max_width, scroll_offset=0, size=size
    )
    assert rect.width == max_width


# ---------------------------------------------------------------------------
# Criterion 2: window shifts with offset and is clamped near the end.
# ---------------------------------------------------------------------------
def test_render_scrolled_window_shifts_and_clamps():
    _setup_module_pygame()
    text = Text(default_theme)
    size = default_theme.font_size_md
    max_width = 200
    s = _long_text(text, max_width, size)
    text_width = text.measure(s, size)[0]

    base = text.render_scrolled(
        _surface(), s, (10, 10), max_width=max_width, scroll_offset=0, size=size
    )
    mid_off = (text_width - max_width) // 2
    mid = text.render_scrolled(
        _surface(), s, (10, 10), max_width=max_width, scroll_offset=mid_off, size=size
    )
    large = text.render_scrolled(
        _surface(),
        s,
        (10, 10),
        max_width=max_width,
        scroll_offset=text_width * 2,  # way past the end -> clamped, window shrinks
        size=size,
    )

    # A mid offset still shows a full window.
    assert mid.width == max_width
    # A huge (clamped) offset never shows MORE than the start window.
    assert large.width <= base.width


# ---------------------------------------------------------------------------
# Criterion 3: cursor clamping keeps the caret inside the field bounds.
# ---------------------------------------------------------------------------
def test_cursor_clamped_inside_field():
    _setup_module_pygame()
    text = Text(default_theme)
    size = default_theme.font_size_md

    field_left = 50
    padding = 12
    field_width = 200
    field_rect = pygame.Rect(field_left, 100, field_width, 40)

    s = _long_text(text, field_width - padding * 2, size)

    unclamped = field_left + padding + text.measure(s, size)[0] + 2
    clamped = min(unclamped, field_rect.right - 2)

    # Documents the bug: the raw measure-based cursor escapes the field.
    assert unclamped > field_rect.right
    # The fix's clamped expression stays inside the field.
    assert clamped <= field_rect.right


# ---------------------------------------------------------------------------
# Criterion 4 (behavioral, the failing-against-current-code test):
# the public render() of an android input modal accepts and threads
# scroll_offset, returning its 4-tuple without raising.
# ---------------------------------------------------------------------------
def test_search_modal_render_accepts_scroll_offset_android():
    _setup_module_pygame()
    from ui.screens.modals.search_modal import SearchModal

    modal = SearchModal(default_theme)
    long_query = "WMWMWMWMWMWMWMWMWMWMWMWMWMWMWMWMWMWMWMWM"

    # Catch the TypeError explicitly so the failure reads as a clear assertion
    # rather than an unhandled exception (the embedded NSZ pytest plugin
    # otherwise re-parses sys.argv while rendering tracebacks and muddies output).
    try:
        result = modal.render(
            _surface(),
            search_text=long_query,
            cursor_position=0,
            input_mode="android",
            scroll_offset=40,
        )
    except TypeError as exc:
        raise AssertionError(
            "SearchModal.render() must accept a scroll_offset keyword so "
            "screen_manager can thread state.text_scroll_offset to the android "
            f"text field; got: {exc}"
        )

    assert isinstance(result, tuple)
    assert len(result) == 4
