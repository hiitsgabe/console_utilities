"""
GAB-61 regression guard: low_end_device_mode must sort the concatenated
multi-source game list EXACTLY ONCE.

This closes the gap the architect spec flagged in test_list_files_perf.py:
the existing TestNoDoubleSort falls back to correctness-only because the
internal `all_files` accumulator is a plain list a network-mock TrackingList
never becomes, and `list.sort` itself cannot be monkey-patched (immutable
built-in type). Correctness (output == sorted(output)) cannot distinguish one
sort from two -- a list sorted twice is still sorted.

Vector that reaches the in-function accumulator without touching production
code: the file items are dicts, and BOTH sort sites use the key
`lambda x: x.get("filename", ...)`. CPython's list.sort computes the sort key
exactly once per element per sort pass. So if we fill the accumulator with
dicts that count `.get("filename")` calls, one sort over N items yields N key
extractions and a redundant double sort yields 2N. We assert key extractions
== N (single pass) in low_end_device_mode.
"""

import importlib.util
import os
import sys
import unittest
from unittest.mock import patch

# Must be set before any import to prevent NSZ arg-parser from consuming pytest argv
sys.argv = [sys.argv[0]]
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

_src = os.path.join(os.path.dirname(__file__), "..", "src")
sys.path.insert(0, _src)

_fl_spec = importlib.util.spec_from_file_location(
    "file_listing_gab61",
    os.path.join(_src, "services", "file_listing.py"),
)
_fl_mod = importlib.util.module_from_spec(_fl_spec)
_fl_spec.loader.exec_module(_fl_mod)
list_files = _fl_mod.list_files


# Shared counter for filename-key extractions across all items in a run.
_KEY_READS = {"n": 0}


class CountingDict(dict):
    """A file dict that counts `.get('filename', ...)` accesses.

    Both sort sites in list_files use key=lambda x: x.get("filename", ...).
    CPython computes the sort key once per element per sort pass, so counting
    these reads measures how many times the accumulator was sorted.
    """

    def get(self, key, default=None):
        if key == "filename":
            _KEY_READS["n"] += 1
        return super().get(key, default)


def _make_system_data():
    return {"name": "TestSys", "url": ["http://example.com/roms/"]}


def _make_settings(low_end=False, dedupe=False):
    return {
        "dedupe_game_list": dedupe,
        "low_end_device_mode": low_end,
        "filter_region": "none",
    }


class TestSingleSortInLowEndMode(unittest.TestCase):
    N = 30

    def _run(self, low_end, dedupe):
        _KEY_READS["n"] = 0

        def fake_html_single(system_data, settings, formats, url):
            return [
                CountingDict({"filename": f"Game {self.N - i:04d} (USA).zip", "size": i})
                for i in range(self.N)
            ]

        with patch.object(
            _fl_mod, "_list_files_html_single", side_effect=fake_html_single
        ), patch.object(
            _fl_mod, "_load_cached_listing", side_effect=lambda url: None
        ), patch.object(
            _fl_mod, "_save_listing_cache", side_effect=lambda url, data: None
        ):
            result = list_files(
                _make_system_data(),
                _make_settings(low_end=low_end, dedupe=dedupe),
            )
        return result, _KEY_READS["n"]

    def test_low_end_mode_sorts_game_list_exactly_once(self):
        result, key_reads = self._run(low_end=True, dedupe=True)

        names = [f["filename"] for f in result]
        self.assertEqual(names, sorted(names), "low_end output must be sorted")

        # The only `.get("filename")` consumers in low_end mode are the sort
        # key lambdas. One sort over N items reads the key N times; a redundant
        # second sort reads 2*N. Assert single pass.
        self.assertEqual(
            key_reads,
            self.N,
            "low_end_device_mode must sort the concatenated game list exactly "
            f"once. Expected {self.N} filename-key reads (single sort) but got "
            f"{key_reads} (~{key_reads / self.N:.0f} sort passes); the "
            "unconditional final sort must be skipped via the already_sorted flag",
        )


if __name__ == "__main__":
    unittest.main()
