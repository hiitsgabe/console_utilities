"""Tests for the IA wizard keyboard-need predicate (GAB-13).

`ia_wizard_needs_keyboard` is a pure function deciding whether the on-screen
keyboard must be shown for the Internet Archive download / collection wizard,
based on which wizard is visible and which step it is on.
"""

import os
import sys

# Defensive SDL dummy env (module is dependency-free, but keep parity with the
# rest of the suite which may import pygame transitively).
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ui.keyboard_state import ia_wizard_needs_keyboard


def test_download_url_step_true():
    assert ia_wizard_needs_keyboard(True, "url", False, "", False) is True


def test_download_non_url_steps_false():
    for step in ["validating", "file_select", "options", "downloading"]:
        assert ia_wizard_needs_keyboard(True, step, False, "", False) is False


def test_download_hidden_url_false():
    assert ia_wizard_needs_keyboard(False, "url", False, "", False) is False


def test_collection_url_true():
    assert ia_wizard_needs_keyboard(False, "", True, "url", False) is True


def test_collection_name_true():
    assert ia_wizard_needs_keyboard(False, "", True, "name", False) is True


def test_collection_formats_true_when_adding_custom():
    assert ia_wizard_needs_keyboard(False, "", True, "formats", True) is True


def test_collection_formats_false_without_custom():
    assert ia_wizard_needs_keyboard(False, "", True, "formats", False) is False


def test_collection_folder_false():
    assert ia_wizard_needs_keyboard(False, "", True, "folder", False) is False


def test_collection_hidden_false():
    assert ia_wizard_needs_keyboard(False, "", False, "url", False) is False


def test_both_hidden_false():
    assert ia_wizard_needs_keyboard(False, "", False, "", False) is False
