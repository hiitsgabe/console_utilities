"""Tests for reap_stale_statuses (startup recovery of orphaned statuses).

A killed session leaves extraction_status.json entries stuck in a transient
state (downloading/extracting/moving/waiting). On restart those must be removed
so the UI shows no phantom "in progress" item and a reused item id cannot
consume a stale record. Terminal states are kept as the last visible outcome.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from droid import ipc  # noqa: E402


def _write(tmp_path, data):
    p = os.path.join(tmp_path, "extraction_status.json")
    with open(p, "w") as f:
        json.dump(data, f)
    return p


def test_removes_every_transient_state_keeps_terminal(tmp_path):
    tmp = str(tmp_path)
    path = _write(
        tmp,
        {
            "0": {"status": "downloading", "progress": 0.5},
            "1": {"status": "extracting", "progress": 0.1},
            "2": {"status": "moving", "progress": 0.9},
            "3": {"status": "waiting", "progress": 0.0},
            "4": {"status": "completed", "progress": 1.0},
            "5": {"status": "failed", "error": "boom"},
            "6": {"status": "cancelled", "progress": 0.0},
        },
    )

    reaped = ipc.reap_stale_statuses(tmp)

    assert reaped == 4
    remaining = json.load(open(path))
    assert set(remaining) == {"4", "5", "6"}
    assert remaining["5"]["error"] == "boom"  # terminal entries untouched


def test_ignores_malformed_entries(tmp_path):
    tmp = str(tmp_path)
    path = _write(tmp, {"0": "not-a-dict", "1": {"status": "downloading"}})

    assert ipc.reap_stale_statuses(tmp) == 1
    remaining = json.load(open(path))
    assert remaining == {"0": "not-a-dict"}


def test_removes_file_when_all_reaped(tmp_path):
    tmp = str(tmp_path)
    path = _write(tmp, {"0": {"status": "downloading"}})

    assert ipc.reap_stale_statuses(tmp) == 1
    assert not os.path.exists(path)  # empty -> file removed


def test_no_write_and_zero_when_nothing_stale(tmp_path):
    tmp = str(tmp_path)
    path = _write(tmp, {"0": {"status": "completed"}})
    mtime_before = os.path.getmtime(path)

    assert ipc.reap_stale_statuses(tmp) == 0
    assert os.path.getmtime(path) == mtime_before  # untouched, no rewrite


def test_missing_file_is_noop(tmp_path):
    assert ipc.reap_stale_statuses(str(tmp_path)) == 0
