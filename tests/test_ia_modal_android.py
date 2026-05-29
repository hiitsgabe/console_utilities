"""GAB-53: Internet Archive modals must anchor to the top on Android.

Bug: ia_collection_modal.render() and ia_download_modal.render() clobber
input_mode == "android" -> "keyboard" before any step routing. The android
path is never reachable, so text-input steps render centered (top ~210) and
the Android soft keyboard covers the modal. After the fix, text-input steps
must use render_top_aligned(), placing the modal at BEZEL_INSET + 10 == 36px
from the top, while non-input steps (confirm, file_select) stay centered.

These tests assert the chosen code path via the returned modal_rect.top and
the exported touch-target rects (ok_rect / cancel_rect / backspace_rect).
"""

import importlib.util
import os
import sys

import pytest

# Drop pytest's argv tail so nsz import-time arg parsing doesn't crash.
sys.argv = sys.argv[:1]

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

_SRC = os.path.join(os.path.dirname(__file__), "..", "src")
sys.path.insert(0, _SRC)

import pygame  # noqa: E402


def _load_module(name, relpath):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(_SRC, relpath)
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_collection_mod = _load_module(
    "ia_collection_modal", "ui/screens/modals/ia_collection_modal.py"
)
_download_mod = _load_module(
    "ia_download_modal", "ui/screens/modals/ia_download_modal.py"
)

IACollectionModal = _collection_mod.IACollectionModal
IADownloadModal = _download_mod.IADownloadModal

# BEZEL_INSET (26) + 10 == 36; the y that render_top_aligned places modals at.
TOP_ALIGNED_Y = 36


@pytest.fixture(scope="module", autouse=True)
def _pygame_init():
    pygame.init()
    pygame.font.init()
    yield
    pygame.quit()


@pytest.fixture
def screen():
    return pygame.Surface((800, 600))


def _render_collection(modal, screen, step):
    return modal.render(
        screen,
        step=step,
        url="testid",
        item_id="testid",
        collection_name="My Collection",
        folder_name="my_collection",
        available_formats=[],
        selected_formats=set(),
        format_highlighted=0,
        should_unzip=False,
        cursor_position=0,
        error_message="",
        input_mode="android",
    )


def _render_download(modal, screen, step):
    return modal.render(
        screen,
        step=step,
        url="testid",
        item_id="testid",
        files_list=[],
        selected_file_index=0,
        output_folder="",
        should_extract=False,
        cursor_position=0,
        error_message="",
        input_mode="android",
    )


class TestTextInputStepsTopAligned:
    """Criteria 1-4: text-input steps anchor to the top on Android."""

    def test_collection_url_step_top_aligned(self, screen):
        modal = IACollectionModal()
        result = _render_collection(modal, screen, "url")
        assert result[0].top == TOP_ALIGNED_Y

    def test_collection_name_step_top_aligned(self, screen):
        modal = IACollectionModal()
        result = _render_collection(modal, screen, "name")
        assert result[0].top == TOP_ALIGNED_Y

    def test_collection_folder_step_top_aligned(self, screen):
        modal = IACollectionModal()
        result = _render_collection(modal, screen, "folder")
        assert result[0].top == TOP_ALIGNED_Y

    def test_download_url_step_top_aligned(self, screen):
        modal = IADownloadModal()
        result = _render_download(modal, screen, "url")
        assert result[0].top == TOP_ALIGNED_Y


class TestNonInputStepsStayCentered:
    """Criteria 5-6: list/confirm steps must NOT be top-aligned."""

    def test_collection_confirm_step_centered(self, screen):
        modal = IACollectionModal()
        result = _render_collection(modal, screen, "confirm")
        assert result[0].top != TOP_ALIGNED_Y

    def test_download_file_select_step_centered(self, screen):
        modal = IADownloadModal()
        result = _render_download(modal, screen, "file_select")
        assert result[0].top != TOP_ALIGNED_Y


class TestTouchRectExport:
    """Criteria 7-8: touch rects exported on input steps, reset otherwise."""

    def test_collection_input_step_exports_rects(self, screen):
        modal = IACollectionModal()
        _render_collection(modal, screen, "url")
        assert modal.ok_rect is not None
        assert modal.cancel_rect is not None
        assert modal.backspace_rect is not None

    def test_download_input_step_exports_rects(self, screen):
        modal = IADownloadModal()
        _render_download(modal, screen, "url")
        assert modal.ok_rect is not None
        assert modal.cancel_rect is not None
        assert modal.backspace_rect is not None

    def test_collection_non_input_step_resets_rects(self, screen):
        modal = IACollectionModal()
        # Prior input-step render populates rects...
        _render_collection(modal, screen, "url")
        # ...then a non-input step must clear them (no stale touch targets).
        _render_collection(modal, screen, "confirm")
        assert modal.ok_rect is None
