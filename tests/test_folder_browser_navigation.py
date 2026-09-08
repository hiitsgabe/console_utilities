"""Tests for FolderBrowserModal gamepad navigation between list and Select/Cancel buttons.

Regression: the Steam shortcut folder picker rendered Select/Cancel buttons but the
D-pad navigation refused to focus them because a duplicated `is_folder_selection`
predicate in `_navigate_folder_browser` was missing several selection types,
steam_shortcut among them.
"""

import importlib.util
import os
import sys
from types import SimpleNamespace

import pytest

# Drop pytest's argv tail so nsz/ParseArguments.py (run at import time on the
# chain app → services → utils.nsz → nsz) doesn't crash on unknown args.
sys.argv = sys.argv[:1]

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

_SRC = os.path.join(os.path.dirname(__file__), "..", "src")
sys.path.insert(0, _SRC)


def _load_module(name, relpath):
    """Load a module by file path, bypassing package __init__ side effects."""
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(_SRC, relpath)
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_state_mod = _load_module("state", "state.py")
_modal_mod = _load_module(
    "folder_browser_modal", "ui/screens/modals/folder_browser_modal.py"
)

FolderBrowserState = _state_mod.FolderBrowserState
is_folder_selection_type = _modal_mod.is_folder_selection_type


def _navigate(selection_type, direction, initial_focus="list", items=("a", "b")):
    """Drive `_navigate_folder_browser` against a minimal state stub.

    Imports the method late and binds it to a stub `self` so we don't pull in
    pygame, services, or the rest of ConsoleUtilitiesApp.
    """
    from app import ConsoleUtilitiesApp

    fb = FolderBrowserState()
    fb.show = True
    fb.items = [{"name": n, "type": "folder"} for n in items]
    fb.highlighted = 0
    fb.focus_area = initial_focus
    fb.button_index = 0
    fb.selected_system_to_add = {"type": selection_type}

    stub = SimpleNamespace(state=SimpleNamespace(folder_browser=fb))
    ConsoleUtilitiesApp._navigate_folder_browser(stub, direction)
    return fb


FOLDER_SELECTION_TYPES = [
    "steam_shortcut",
    "work_dir",
    "roms_dir",
    "custom_folder",
    "add_system_folder",
    "ia_collection_folder",
    "dedupe_folder",
    "rename_folder",
    "ghost_cleaner_folder",
    "ia_download_folder",
    "folder",
]

FILE_SELECTION_TYPES = [
    "archive_json",
    "nsz_keys",
    "extract_zip",
    "extract_rar",
    "extract_7z",
    "nsz_converter",
    "we_patcher_rom",
    "iss_patcher_rom",
    "nhl94_patcher_rom",
    "kgj_mlb_patcher_rom",
    "nbalive95_patcher_rom",
    "nhl94_gen_patcher_rom",
    "nhl05_patcher_rom",
    "pes6_ps2_patcher_rom",
    "nhl07_patcher_rom",
    "mvp_psp_patcher_rom",
]


@pytest.mark.parametrize("selection_type", FOLDER_SELECTION_TYPES)
def test_right_from_list_focuses_select_button(selection_type):
    """D-pad right on a folder picker moves focus to the Select button."""
    fb = _navigate(selection_type, "right")
    assert fb.focus_area == "buttons"
    assert fb.button_index == 0  # Select


@pytest.mark.parametrize("selection_type", FOLDER_SELECTION_TYPES)
def test_left_from_list_focuses_cancel_button(selection_type):
    """D-pad left on a folder picker moves focus to the Cancel button."""
    fb = _navigate(selection_type, "left")
    assert fb.focus_area == "buttons"
    assert fb.button_index == 1  # Cancel


@pytest.mark.parametrize("selection_type", FILE_SELECTION_TYPES)
def test_file_picker_left_right_do_not_focus_buttons(selection_type):
    """File pickers render no Select/Cancel buttons, so left/right must not move focus."""
    fb_right = _navigate(selection_type, "right")
    assert fb_right.focus_area == "list"
    fb_left = _navigate(selection_type, "left")
    assert fb_left.focus_area == "list"


def test_render_and_navigation_agree_on_folder_selection():
    """Render and navigation must consult the same predicate (no duplicated drift).

    This guards against the original bug class: the modal drawing Select/Cancel
    buttons while the navigation handler refuses to focus them.
    """
    for st in FOLDER_SELECTION_TYPES:
        assert is_folder_selection_type(st), f"{st} should be a folder selection"
    for st in FILE_SELECTION_TYPES:
        assert not is_folder_selection_type(st), f"{st} should be a file selection"


def _fb_stub(button_index=1):
    fb = FolderBrowserState()
    fb.show = True
    fb.items = [{"name": "x", "type": "folder"}]
    fb.current_path = "/x"
    fb.highlighted = 5
    fb.scroll_offset = 10
    fb.focus_area = "buttons"
    fb.button_index = button_index
    return SimpleNamespace(
        state=SimpleNamespace(folder_browser=fb), settings={"work_dir": "/work"}
    )


def test_reset_folder_browser_state_clears_fields():
    """GAB-17: resetting the folder browser clears all transient nav state."""
    from app import ConsoleUtilitiesApp

    stub = _fb_stub()
    ConsoleUtilitiesApp._reset_folder_browser_state(stub)

    fb = stub.state.folder_browser
    assert fb.show is False
    assert fb.focus_area == "list"
    assert fb.current_path == "/work"
    assert fb.items == []
    assert fb.highlighted == 0
    assert fb.scroll_offset == 0
    assert fb.button_index == 0


def test_button_cancel_resets_state():
    """GAB-17: choosing Cancel must reset the browser, not just hide it."""
    from app import ConsoleUtilitiesApp

    s = _fb_stub(button_index=1)
    ConsoleUtilitiesApp._handle_folder_browser_button_selection(s)

    fb = s.state.folder_browser
    assert fb.items == []
    assert fb.current_path == "/work"
    assert fb.show is False
