"""GAB-55: Cancel/close (X) in folder/file selection must not leave a blank page.

The X-close path routes through `_go_back()`. Its folder_browser branch did an
inline reset that (a) omitted `scroll_offset`/`button_index` and (b) only
restored the parent wizard for 3 of ~30 selection types, leaving all other
types with the browser hidden but the parent wizard stuck in a sub-step the
screen manager cannot render -> blank page.

These tests pin the fix: the X-close path must converge on the authoritative
`_reset_folder_browser_state()` reset (full field clear) for every selection
type, while still restoring the parent wizard for the 3 special types.

Pure state / code-path assertions; no rendering, headless-safe.
"""

import importlib.util
import os
import sys
from types import SimpleNamespace

import pytest

# Drop pytest's argv tail so nsz/ParseArguments.py (run at import time on the
# chain app -> services -> utils.nsz -> nsz) doesn't crash on unknown args.
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
AppState = _state_mod.AppState
FolderBrowserState = _state_mod.FolderBrowserState


def _go_back_stub(selection_type, scraper=False):
    """Build a stub `self` whose `_go_back()` reaches the folder_browser branch.

    A real AppState gives every modal `show=False` by default, so the only
    truthy dismiss target is the folder_browser we configure here. That puts us
    on the folder_browser branch of `_go_back()` regardless of which earlier
    `elif self.state.X.show` guards exist.
    """
    state = AppState()

    fb = FolderBrowserState()
    fb.show = True
    fb.items = [{"name": "x", "type": "folder"}]
    fb.current_path = "/x"
    fb.highlighted = 5
    fb.scroll_offset = 10
    fb.focus_area = "buttons"
    fb.button_index = 1
    fb.selected_system_to_add = {"type": selection_type}
    state.folder_browser = fb

    # steam_shortcut guard precedes the folder_browser branch -> keep it falsy.
    state.steam_shortcut.show = False

    stub = SimpleNamespace(state=state, settings={"work_dir": "/work"})
    if scraper:
        from app import ConsoleUtilitiesApp

        stub.screen_manager = SimpleNamespace(
            scraper_wizard_modal=SimpleNamespace(clear_thumbs=lambda: None)
        )
        # The scraper special-case calls the real _close_scraper_wizard.
        stub._close_scraper_wizard = lambda: ConsoleUtilitiesApp._close_scraper_wizard(
            stub
        )
    return stub


# Types that previously fell through `_go_back()` with NO parent restoration.
PREVIOUSLY_BROKEN_TYPES = [
    "work_dir",
    "dedupe_folder",
    "we_patcher_rom",
    "retroarch_thumbnails",
]


@pytest.mark.parametrize("selection_type", PREVIOUSLY_BROKEN_TYPES)
def test_x_close_generic_type_fully_resets(selection_type):
    """X-close on a generic picker must run the full authoritative reset.

    The inline reset omitted scroll_offset and button_index; these assertions
    fail against the buggy code and pass once `_go_back()` calls
    `_reset_folder_browser_state()`.
    """
    from app import ConsoleUtilitiesApp

    stub = _go_back_stub(selection_type)
    ConsoleUtilitiesApp._go_back(stub)

    fb = stub.state.folder_browser
    assert fb.show is False
    assert fb.items == []
    assert fb.current_path == "/work"
    assert fb.highlighted == 0
    assert fb.scroll_offset == 0
    assert fb.button_index == 0
    assert fb.focus_area == "list"
    # No special-case wizard should have been mutated for a generic type.
    assert stub.state.ia_collection_wizard.step == "url"


def test_x_close_ia_collection_resets_and_restores_parent():
    """X-close on the IA-collection folder picker resets AND restores the wizard."""
    from app import ConsoleUtilitiesApp

    stub = _go_back_stub("ia_collection_folder")
    ConsoleUtilitiesApp._go_back(stub)

    fb = stub.state.folder_browser
    assert fb.show is False
    assert fb.scroll_offset == 0
    assert fb.button_index == 0
    assert stub.state.ia_collection_wizard.step == "name"
    assert stub.state.ia_collection_wizard.cursor_position == 0


def test_x_close_scraper_batch_resets_and_closes_wizard():
    """X-close on the scraper folder picker resets AND tears down the scraper wizard."""
    from app import ConsoleUtilitiesApp

    stub = _go_back_stub("scraper_batch_folder", scraper=True)
    ConsoleUtilitiesApp._go_back(stub)

    fb = stub.state.folder_browser
    assert fb.show is False
    assert fb.scroll_offset == 0
    assert fb.button_index == 0
    assert stub.state.scraper_wizard.show is False
    assert stub.state.scraper_wizard.step == "rom_select"


def test_x_close_steam_shortcut_resets_and_restores_results():
    """X-close on the steam folder picker resets AND returns the wizard to results."""
    from app import ConsoleUtilitiesApp

    stub = _go_back_stub("steam_shortcut")
    ConsoleUtilitiesApp._go_back(stub)

    fb = stub.state.folder_browser
    assert fb.show is False
    assert fb.scroll_offset == 0
    assert fb.button_index == 0
    assert stub.state.steam_shortcut.step == "results"
