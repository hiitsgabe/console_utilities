"""TDD (red) tests for GAB-10: hardened logging.

When the primary log file is unwritable (Android external storage permission
quirks), log_error today silently swallows the failure (`except: pass`), so the
breadcrumb trail that would explain a failed >3 GiB extraction is lost.

Pinned NOT-YET-IMPLEMENTED behavior in utils.logging:
    - On primary write failure, fall back to a file under tempfile.gettempdir().
    - If the fallback also fails, surface the failure to stderr (never raise).

Regression preserved:
    - log_error always prints the message to stdout.
    - init_log_file returns False (not raise) on failure.
"""

import os
import sys

import pytest

sys.argv = sys.argv[:1]

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from utils import logging as L  # noqa: E402


def test_log_error_writes_to_configured_file(tmp_path, monkeypatch):
    log_path = tmp_path / "error.log"
    monkeypatch.setattr(L, "_log_file", str(log_path))

    L.log_error("hi")

    assert log_path.exists()
    assert "hi" in log_path.read_text()


def test_log_error_falls_back_on_unwritable_primary(tmp_path, monkeypatch):
    import builtins

    real_open = builtins.open
    primary = str(tmp_path / "primary" / "error.log")
    monkeypatch.setattr(L, "_log_file", primary)

    def fake_open(path, *args, **kwargs):
        if str(path) == primary:
            raise OSError("read-only filesystem")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", fake_open)

    fallback_dir = tmp_path / "fallback"
    fallback_dir.mkdir()
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(fallback_dir))

    L.log_error("boom")

    contents = [
        f.read_text()
        for f in fallback_dir.iterdir()
        if f.is_file()
    ]
    assert any("boom" in c for c in contents), "no fallback log written"


def test_log_error_surfaces_to_stderr_on_failure(tmp_path, monkeypatch, capsys):
    import builtins

    def always_fail_open(path, *args, **kwargs):
        raise OSError("everything is unwritable")

    monkeypatch.setattr(builtins, "open", always_fail_open)
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))

    # Must not raise even though primary AND fallback fail.
    L.log_error("xyz")

    captured = capsys.readouterr()
    assert "fail" in captured.err.lower()


def test_log_error_still_prints_stdout(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(L, "_log_file", str(tmp_path / "error.log"))

    L.log_error("stdout-message")

    captured = capsys.readouterr()
    assert "stdout-message" in captured.out


def test_init_log_file_returns_false_on_failure_without_raising(monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("cannot create dir")

    monkeypatch.setattr(os, "makedirs", boom)

    assert L.init_log_file() is False
