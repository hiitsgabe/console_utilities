"""TDD (red) tests for GAB-10: output capacity / filesystem pre-flight checks.

NSZ decompression on Android silently fails when the extracted NSP would
exceed the free space available or the 4 GiB single-file limit of a FAT32
target. These tests pin the NOT-YET-IMPLEMENTED API:

    utils.nsz.check_output_capacity(output_dir, required_bytes) -> (ok, reason)
    utils.nsz._detect_fs_type(path) -> str   (e.g. "vfat", "exfat", "ext4")
    decompress_nsz_file must short-circuit (return False, never call the
    underlying nsz decompressor) when check_output_capacity says no.

The module imports cleanly today, so collection succeeds; the new symbols
are accessed via the module object so the failures surface as AttributeError
("feature not implemented yet"), not ImportError.
"""

import os
import sys
from types import SimpleNamespace

import pytest

# Keep nsz/ParseArguments out of pytest's argv when the nsz package imports.
sys.argv = sys.argv[:1]

# src on path so `utils` and the top-level `nsz` package resolve.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "nsz"))

from utils import nsz as nsz_mod  # noqa: E402
from utils.nsz import decompress_nsz_file  # noqa: E402

GB = 1024 ** 3


def _fake_statvfs(free_bytes, frsize=4096):
    """Build an object shaped like os.statvfs_result with a given free size."""
    bavail = free_bytes // frsize
    return SimpleNamespace(
        f_frsize=frsize,
        f_bsize=frsize,
        f_bavail=bavail,
        f_bfree=bavail,
        f_blocks=bavail,
    )


def test_capacity_ok_when_space_available(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "statvfs", lambda p: _fake_statvfs(50 * GB))
    ok, reason = nsz_mod.check_output_capacity(str(tmp_path), 4 * GB)
    assert ok is True
    assert reason is None


def test_capacity_fails_when_insufficient_space(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "statvfs", lambda p: _fake_statvfs(1 * GB))
    ok, reason = nsz_mod.check_output_capacity(str(tmp_path), 4 * GB)
    assert ok is False
    assert reason is not None
    assert "space" in reason.lower()


def test_fat32_over_4gb_blocked(tmp_path, monkeypatch):
    monkeypatch.setattr(nsz_mod, "_detect_fs_type", lambda p: "vfat", raising=False)
    monkeypatch.setattr(os, "statvfs", lambda p: _fake_statvfs(50 * GB))
    ok, reason = nsz_mod.check_output_capacity(str(tmp_path), 5 * GB)
    assert ok is False
    assert reason is not None
    assert "fat32" in reason.lower()


def test_fat32_under_4gb_allowed(tmp_path, monkeypatch):
    monkeypatch.setattr(nsz_mod, "_detect_fs_type", lambda p: "vfat", raising=False)
    monkeypatch.setattr(os, "statvfs", lambda p: _fake_statvfs(500 * GB))
    ok, reason = nsz_mod.check_output_capacity(str(tmp_path), 3 * GB)
    assert ok is True
    assert reason is None


def test_exfat_over_4gb_allowed(tmp_path, monkeypatch):
    monkeypatch.setattr(nsz_mod, "_detect_fs_type", lambda p: "exfat", raising=False)
    monkeypatch.setattr(os, "statvfs", lambda p: _fake_statvfs(500 * GB))
    ok, reason = nsz_mod.check_output_capacity(str(tmp_path), 6 * GB)
    assert ok is True
    assert reason is None


def test_capacity_fail_open_when_statvfs_raises(tmp_path, monkeypatch):
    def boom(p):
        raise OSError("statvfs unavailable")

    monkeypatch.setattr(os, "statvfs", boom)
    # Fail open: an unknowable filesystem must not block decompression.
    ok, reason = nsz_mod.check_output_capacity(str(tmp_path), 4 * GB)
    assert ok is True
    assert reason is None


def test_detect_fs_type_parses_proc_mounts(monkeypatch):
    import builtins

    real_open = builtins.open
    mounts = "/dev/x /mnt/sd vfat rw 0 0\n/dev/y / ext4 rw 0 0\n"

    def fake_open(path, *args, **kwargs):
        if str(path) == "/proc/mounts":
            import io

            return io.StringIO(mounts)
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", fake_open)

    # Longest-prefix match: /mnt/sd is more specific than /.
    assert nsz_mod._detect_fs_type("/mnt/sd/foo") == "vfat"
    assert nsz_mod._detect_fs_type("/other") == "ext4"


def test_decompress_short_circuits_on_capacity_fail(tmp_path, monkeypatch):
    # Capacity check denies the operation.
    monkeypatch.setattr(
        nsz_mod,
        "check_output_capacity",
        lambda out_dir, required: (False, "FAT32 cannot hold a file this large"),
        raising=False,
    )

    called = {"hit": False}

    def must_not_run(*args, **kwargs):
        called["hit"] = True
        raise AssertionError("nsz decompressor must not be invoked")

    # The internal decompress callable captured in utils/nsz.py.
    monkeypatch.setattr(nsz_mod, "_nsz_decompress", must_not_run, raising=False)

    nsz_file = tmp_path / "big.nsz"
    nsz_file.write_bytes(b"\x00" * 1024)  # nonzero size so the size guard passes
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    result = decompress_nsz_file(str(nsz_file), str(out_dir), "/fake/keys.txt")

    assert result is False
    assert called["hit"] is False
