"""Render-contract tests for the NSZ log viewer modal (GAB-58 follow-up)."""

import importlib.util
import os
import sys

import pytest

sys.argv = sys.argv[:1]
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

_SRC = os.path.join(os.path.dirname(__file__), "..", "src")
sys.path.insert(0, _SRC)


def _load_module(name, relpath):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(_SRC, relpath)
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_modal_mod = _load_module("nsz_log_modal", "ui/screens/modals/nsz_log_modal.py")
NszLogModal = _modal_mod.NszLogModal


@pytest.fixture(scope="module", autouse=True)
def _pygame_ctx():
    pygame.init()
    yield
    pygame.quit()


@pytest.fixture
def screen():
    return pygame.Surface((800, 600))


def test_render_returns_modal_save_and_close_rects(screen):
    modal = NszLogModal()
    modal_rect, save_rect, close_rect = modal.render(
        screen, ["line one", "line two"], scroll_offset=0, button_index=0
    )
    assert isinstance(modal_rect, pygame.Rect)
    assert isinstance(save_rect, pygame.Rect)
    assert isinstance(close_rect, pygame.Rect)
    assert save_rect != close_rect


def test_render_handles_many_lines_and_scroll(screen):
    modal = NszLogModal()
    lines = [f"log line {i}" for i in range(500)]
    # Deep scroll and out-of-range scroll must not raise.
    modal.render(screen, lines, scroll_offset=480, button_index=1)
    modal.render(screen, lines, scroll_offset=99999, button_index=0)


def test_render_handles_empty_lines(screen):
    modal = NszLogModal()
    modal_rect, save_rect, close_rect = modal.render(
        screen, [], scroll_offset=0, button_index=1
    )
    assert isinstance(modal_rect, pygame.Rect)


def test_max_scroll_offset_is_non_negative_and_bounded(screen):
    modal = NszLogModal()
    # Few lines: nothing to scroll.
    assert modal.max_scroll_offset(["a", "b"]) == 0
    # Many lines: positive and less than total.
    many = [f"l{i}" for i in range(500)]
    ms = modal.max_scroll_offset(many)
    assert 0 < ms < len(many)
