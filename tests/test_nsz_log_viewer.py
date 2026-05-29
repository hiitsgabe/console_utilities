"""Tests for the NSZ in-app log viewer data layer (GAB-58 follow-up).

The dedicated nsz.log file is unreachable on Android, so log_nsz() must also
capture entries to an in-memory ring buffer that an in-app modal can display,
with a fallback to reading nsz.log from disk, plus a "force save to error.log"
action so the diagnostics land in the one log the user can actually retrieve.
"""

import importlib.util
import os
import sys

import pytest

# Keep nsz/ParseArguments import-time argv parsing from choking on pytest args.
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


# Load utils/logging.py under a non-stdlib name so we never shadow `logging`.
L = _load_module("cu_logging", "utils/logging.py")


@pytest.fixture(autouse=True)
def isolate_logs(tmp_path):
    """Redirect both log files to tmp and start with an empty buffer."""
    L._nsz_log_file = str(tmp_path / "nsz.log")
    L._log_file = str(tmp_path / "error.log")
    L.clear_nsz_log_buffer()
    yield


def test_log_nsz_captures_entry_to_buffer():
    L.log_nsz("decompress started", error_type="INFO")
    buf = L.get_nsz_log_buffer()
    assert len(buf) == 1
    assert "decompress started" in buf[0]
    assert "INFO" in buf[0]


def test_buffer_is_capped_dropping_oldest():
    cap = L.NSZ_LOG_BUFFER_MAX
    for i in range(cap + 25):
        L.log_nsz(f"entry-{i}")
    buf = L.get_nsz_log_buffer()
    joined = "\n".join(buf)
    assert len(buf) == cap
    assert "entry-0" not in joined  # oldest dropped
    assert f"entry-{cap + 24}" in joined  # newest kept


def test_clear_buffer_empties_it():
    L.log_nsz("something")
    L.clear_nsz_log_buffer()
    assert L.get_nsz_log_buffer() == []


def test_read_lines_prefers_in_memory_buffer():
    L.log_nsz("buffer-alpha")
    lines = L.read_nsz_log_lines()
    assert any("buffer-alpha" in line for line in lines)


def test_read_lines_falls_back_to_file_when_buffer_empty(tmp_path):
    L.clear_nsz_log_buffer()
    with open(L._nsz_log_file, "w") as f:
        f.write("file-line-1\nfile-line-2\n")
    lines = L.read_nsz_log_lines()
    assert "file-line-1" in lines
    assert "file-line-2" in lines


def test_read_lines_empty_when_no_buffer_and_no_file():
    L.clear_nsz_log_buffer()
    L._nsz_log_file = str(os.path.join(os.path.dirname(L._nsz_log_file), "missing.log"))
    assert L.read_nsz_log_lines() == []


def test_save_to_error_log_appends_buffer_content():
    L.log_nsz("save-me-token")
    ok = L.save_nsz_log_to_error_log()
    assert ok is True
    with open(L._log_file) as f:
        content = f.read()
    assert "save-me-token" in content
    assert "NSZ LOG" in content  # a header marks the appended section


def test_save_returns_false_when_nothing_to_save():
    L.clear_nsz_log_buffer()
    L._nsz_log_file = str(os.path.join(os.path.dirname(L._nsz_log_file), "missing.log"))
    assert L.save_nsz_log_to_error_log() is False
