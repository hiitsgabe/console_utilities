"""Tests for the NSZ log viewer data layer (GAB-58).

NSZ diagnostics are written into the main error.log (tagged [NSZ]) so they
persist across the app being killed/restarted mid-extraction on Android. The
viewer reads error.log (source of truth), falling back to an in-memory buffer
only when the file is unavailable.
"""

import importlib.util
import os
import sys

import pytest

sys.argv = sys.argv[:1]
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

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


L = _load_module("cu_logging", "utils/logging.py")


@pytest.fixture(autouse=True)
def isolate_logs(tmp_path):
    L._log_file = str(tmp_path / "error.log")
    L.clear_nsz_log_buffer()
    yield


def test_log_nsz_writes_to_error_log_tagged():
    L.log_nsz("decompress started", error_type="INFO")
    with open(L._log_file) as f:
        text = f.read()
    assert "decompress started" in text
    assert "[NSZ]" in text
    assert "INFO" in text


def test_log_nsz_does_not_create_separate_nsz_log(tmp_path):
    L.log_nsz("something")
    assert not (tmp_path / "nsz.log").exists()


def test_log_nsz_captures_entry_to_buffer():
    L.log_nsz("buffer-alpha")
    buf = L.get_nsz_log_buffer()
    assert len(buf) == 1
    assert "buffer-alpha" in buf[0]


def test_buffer_is_capped_dropping_oldest():
    cap = L.NSZ_LOG_BUFFER_MAX
    for i in range(cap + 25):
        L.log_nsz(f"entry-{i}")
    buf = L.get_nsz_log_buffer()
    joined = "\n".join(buf)
    assert len(buf) == cap
    assert "entry-0" not in joined
    assert f"entry-{cap + 24}" in joined


def test_clear_buffer_empties_it():
    L.log_nsz("something")
    L.clear_nsz_log_buffer()
    assert L.get_nsz_log_buffer() == []


def test_read_lines_reads_error_log():
    L.log_nsz("persisted-line")
    L.clear_nsz_log_buffer()  # force reading from the file, not the buffer
    lines = L.read_nsz_log_lines()
    assert any("persisted-line" in line for line in lines)


def test_read_lines_returns_recent_tail():
    total = L.NSZ_VIEW_MAX_LINES + 50
    for i in range(total):
        L.log_nsz(f"line-{i}")
    L.clear_nsz_log_buffer()
    lines = L.read_nsz_log_lines()
    assert len(lines) <= L.NSZ_VIEW_MAX_LINES
    joined = "\n".join(lines)
    assert f"line-{total - 1}" in joined  # newest kept
    assert "line-0" not in joined  # oldest dropped from the tail


def test_read_lines_falls_back_to_buffer_when_file_unreadable():
    L.log_nsz("in-buffer-only")
    # Point the file at an unreadable path so the primary read fails.
    L._log_file = str(os.path.join(os.path.dirname(L._log_file), "nope", "error.log"))
    lines = L.read_nsz_log_lines()
    assert any("in-buffer-only" in line for line in lines)


def test_read_lines_empty_when_no_file_and_no_buffer():
    L.clear_nsz_log_buffer()
    L._log_file = str(os.path.join(os.path.dirname(L._log_file), "nope", "error.log"))
    assert L.read_nsz_log_lines() == []
