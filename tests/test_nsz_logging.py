"""Tests for GAB-58: NSZ debug logging routed into the main error.log.

The dedicated nsz.log proved unreliable/invisible on Android, so NSZ
diagnostics now go straight into ``error.log`` (the file that is created at
startup and reliably persists / is retrievable), tagged with ``[NSZ]``.

Pinned behavior:
    - utils.logging.log_nsz writes to ``_log_file`` (error.log), tagged [NSZ];
      it does NOT write a separate nsz.log.
    - decompress_nsz_file routes ALL of its log calls through log_nsz, emits a
      pre-call integer ``file_size=`` diagnostic, distinguishes the two silent
      failure modes (``keys_path not set`` vs ``nsz library unavailable``), and
      records a multi-line traceback (with the exception class name) on raise.
    - log_nsz reuses the hardened _write_fallback path on a primary OSError.
"""

import os
import sys

import pytest

# Keep nsz/ParseArguments out of pytest's argv when the nsz package imports.
sys.argv = sys.argv[:1]

# src (and src/nsz) on path so `utils` and the top-level `nsz` package resolve.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "nsz"))

from utils import nsz as nsz_mod  # noqa: E402
from utils import logging as L  # noqa: E402
from utils.nsz import decompress_nsz_file  # noqa: E402


def test_writes_to_error_log_tagged_with_filename(tmp_path, monkeypatch):
    """A decompress must write the basename to error.log, tagged [NSZ]."""
    err_log = tmp_path / "error.log"
    monkeypatch.setattr(L, "_log_file", str(err_log), raising=False)

    monkeypatch.setattr(
        nsz_mod, "check_output_capacity", lambda d, n: (True, None), raising=False
    )
    monkeypatch.setattr(
        nsz_mod, "_nsz_decompress", lambda *a, **k: None, raising=False
    )

    nsz_file = tmp_path / "game.nsz"
    nsz_file.write_bytes(b"\x00" * 1024)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    decompress_nsz_file(str(nsz_file), str(out_dir), "/fake/keys.txt")

    assert err_log.exists(), "error.log was not written"
    text = err_log.read_text()
    assert "game.nsz" in text
    assert "[NSZ]" in text


def test_no_separate_nsz_log_file_is_created(tmp_path, monkeypatch):
    """NSZ logging must not create a separate nsz.log sibling file."""
    err_log = tmp_path / "error.log"
    monkeypatch.setattr(L, "_log_file", str(err_log), raising=False)

    L.log_nsz("hello")

    assert not (tmp_path / "nsz.log").exists()
    assert "hello" in err_log.read_text()


def test_multiline_traceback_on_raise(tmp_path, monkeypatch):
    """An exception during decompression yields a multi-line entry with the
    exception class name and a Traceback block, in error.log."""
    err_log = tmp_path / "error.log"
    monkeypatch.setattr(L, "_log_file", str(err_log), raising=False)

    monkeypatch.setattr(
        nsz_mod, "check_output_capacity", lambda d, n: (True, None), raising=False
    )

    def boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(nsz_mod, "_nsz_decompress", boom, raising=False)

    nsz_file = tmp_path / "game.nsz"
    nsz_file.write_bytes(b"\x00" * 1024)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    decompress_nsz_file(str(nsz_file), str(out_dir), "/fake/keys.txt")

    text = err_log.read_text()
    assert "RuntimeError" in text
    assert "boom" in text
    assert "Traceback:" in text
    assert "\n" in text


def test_keys_path_not_set_distinct_token(tmp_path, monkeypatch):
    """keys_path="" logs 'keys_path not set' and NOT 'nsz library unavailable'."""
    err_log = tmp_path / "error.log"
    monkeypatch.setattr(L, "_log_file", str(err_log), raising=False)

    nsz_file = tmp_path / "game.nsz"
    nsz_file.write_bytes(b"\x00" * 1024)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    result = decompress_nsz_file(str(nsz_file), str(out_dir), "")

    assert result is False
    text = err_log.read_text()
    assert "keys_path not set" in text
    assert "nsz library unavailable" not in text


def test_library_unavailable_distinct_token(tmp_path, monkeypatch):
    """When the nsz library genuinely cannot load (even after the re-import
    branch), the path logs 'nsz library unavailable'."""
    err_log = tmp_path / "error.log"
    monkeypatch.setattr(L, "_log_file", str(err_log), raising=False)

    monkeypatch.setattr(nsz_mod, "_nsz_decompress", None, raising=False)

    # Block the re-import resurrection: the real nsz package IS importable in
    # CI, so intercept __import__ for "nsz" to force the unavailable branch.
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "nsz":
            raise ImportError("nsz blocked for test")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    nsz_file = tmp_path / "game.nsz"
    nsz_file.write_bytes(b"\x00" * 1024)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    # keys_path truthy so branch ordering reaches the library check.
    result = decompress_nsz_file(str(nsz_file), str(out_dir), "/fake/keys.txt")

    assert result is False
    assert "nsz library unavailable" in err_log.read_text()


def test_integer_file_size_logged_before_library_call(tmp_path, monkeypatch):
    """An integer 'file_size=' diagnostic is logged before invoking the lib."""
    err_log = tmp_path / "error.log"
    monkeypatch.setattr(L, "_log_file", str(err_log), raising=False)

    monkeypatch.setattr(
        nsz_mod, "check_output_capacity", lambda d, n: (True, None), raising=False
    )
    monkeypatch.setattr(
        nsz_mod, "_nsz_decompress", lambda *a, **k: None, raising=False
    )

    nsz_file = tmp_path / "game.nsz"
    nsz_file.write_bytes(b"\x00" * 4096)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    decompress_nsz_file(str(nsz_file), str(out_dir), "/fake/keys.txt")

    import re

    text = err_log.read_text()
    assert re.search(r"file_size=\d+", text), "no integer file_size= diagnostic logged"


def test_fallback_on_primary_oserror(tmp_path, monkeypatch):
    """A primary-write OSError routes the entry through _write_fallback."""
    import builtins

    real_open = builtins.open
    primary = str(tmp_path / "primary" / "error.log")
    monkeypatch.setattr(L, "_log_file", primary, raising=False)

    def fake_open(path, *args, **kwargs):
        if str(path) == primary:
            raise OSError("read-only filesystem")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", fake_open)

    fallback_dir = tmp_path / "fallback"
    fallback_dir.mkdir()
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(fallback_dir))

    L.log_nsz("nsz-boom")

    contents = [f.read_text() for f in fallback_dir.iterdir() if f.is_file()]
    assert any("nsz-boom" in c for c in contents), "no fallback log written"
