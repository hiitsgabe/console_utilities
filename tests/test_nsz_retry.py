"""Tests for retrying NSZ decompression via the python download path (GAB-58).

A failed .nsz keeps its downloaded file (decompression failure does not delete
it), so the user can re-run decompression using the desktop/python
``decompress_nsz_file`` path -- independent of the Android-native download
handler. The worker logs to error.log via log_nsz so the retry is visible.
"""

import os
import sys

import pytest

sys.argv = sys.argv[:1]
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "nsz"))

from services import download_manager as dm_mod  # noqa: E402
from services.download_manager import DownloadManager  # noqa: E402
from state import DownloadQueueState, DownloadQueueItem  # noqa: E402


def _make_manager(tmp_path):
    work = tmp_path / "work"
    roms = tmp_path / "roms"
    work.mkdir()
    roms.mkdir()
    settings = {
        "work_dir": str(work),
        "roms_dir": str(roms),
        "nsz_keys_path": "/fake/keys.txt",
    }
    return DownloadManager(settings, DownloadQueueState()), work, roms


def _make_item():
    return DownloadQueueItem(
        game={"name": "game.nsz"},
        system_data={"name": "Switch", "roms_folder": "switch"},
        system_name="Switch",
        status="failed",
        error="NSZ decompression failed",
    )


def test_retry_runs_decompress_and_marks_completed(tmp_path, monkeypatch):
    mgr, work, roms = _make_manager(tmp_path)
    (work / "game.nsz").write_bytes(b"\x00" * 1024)
    item = _make_item()

    calls = {}

    def fake_decompress(file_path, output_dir, keys_path, progress_cb=None):
        calls["args"] = (file_path, output_dir, keys_path)
        return True

    monkeypatch.setattr(dm_mod, "decompress_nsz_file", fake_decompress)

    ok = mgr._retry_decompress_worker(item)

    assert ok is True
    assert item.status == "completed"
    fp, out, keys = calls["args"]
    assert fp == str(work / "game.nsz")
    assert out == str(roms / "switch")
    assert keys == "/fake/keys.txt"
    # Successful decompression removes the source .nsz.
    assert not (work / "game.nsz").exists()


def test_retry_marks_failed_when_decompress_fails(tmp_path, monkeypatch):
    mgr, work, roms = _make_manager(tmp_path)
    (work / "game.nsz").write_bytes(b"\x00" * 1024)
    item = _make_item()

    monkeypatch.setattr(
        dm_mod, "decompress_nsz_file", lambda *a, **k: False
    )

    ok = mgr._retry_decompress_worker(item)

    assert ok is False
    assert item.status == "failed"
    # The file is kept so the user can retry again.
    assert (work / "game.nsz").exists()


def test_retry_when_file_missing_reports_clearly(tmp_path, monkeypatch):
    mgr, work, roms = _make_manager(tmp_path)
    item = _make_item()  # no file in work_dir

    called = {"n": 0}
    monkeypatch.setattr(
        dm_mod,
        "decompress_nsz_file",
        lambda *a, **k: called.__setitem__("n", called["n"] + 1) or True,
    )

    ok = mgr._retry_decompress_worker(item)

    assert ok is False
    assert item.status == "failed"
    assert "missing" in item.error.lower() or "re-download" in item.error.lower()
    assert called["n"] == 0  # decompress not attempted without a file


def test_retry_nsz_decompression_spawns_joinable_thread(tmp_path, monkeypatch):
    mgr, work, roms = _make_manager(tmp_path)
    (work / "game.nsz").write_bytes(b"\x00" * 1024)
    item = _make_item()

    monkeypatch.setattr(dm_mod, "decompress_nsz_file", lambda *a, **k: True)

    t = mgr.retry_nsz_decompression(item)
    t.join(timeout=5)

    assert not t.is_alive()
    assert item.status == "completed"
