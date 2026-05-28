"""TDD (red) tests for GAB-10: durable Pfs0 writes on Android.

Multi-GiB extractions on Android external storage (exFAT/FUSE) get lost when
the page cache is never flushed and a large pre-allocating truncate is issued.
bfd1b05 already gates truncate above 2 GiB; this layer adds periodic + on-close
fsync so written bytes actually hit disk.

Pinned NOT-YET-IMPLEMENTED API on Pfs0Stream:
    - self._FSYNC_INTERVAL: byte threshold between periodic fsyncs
    - periodic os.fsync during write() once threshold is crossed
    - os.fsync on close()
    - self._sync(): swallows OSError, never propagates

Regression preserved:
    - updateHashHeader() truncates for final_size <= 2 GiB, never above it.
"""

import os
import sys

import pytest

sys.argv = sys.argv[:1]

# Pfs0 does `from nsz.nut import ...`, so src/nsz must be importable too.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "nsz"))

from nsz.Fs.Pfs0 import Pfs0Stream  # noqa: E402

HEADER = 0x100


def _new_stream(tmp_path, name="game.nsp"):
    path = tmp_path / "out" / name
    return Pfs0Stream(HEADER, None, str(path)), path


def test_periodic_fsync_called_on_large_write(tmp_path, monkeypatch):
    stream, _ = _new_stream(tmp_path)
    # Small interval so a modest write crosses it.
    stream._FSYNC_INTERVAL = 1024

    calls = []
    monkeypatch.setattr(os, "fsync", lambda fd: calls.append(fd))

    for _ in range(30):
        stream.write(b"x" * 100)  # 3000 bytes total, well past 1024

    assert len(calls) >= 1
    stream.close()


def test_no_fsync_for_small_writes(tmp_path, monkeypatch):
    stream, _ = _new_stream(tmp_path)

    calls = []
    monkeypatch.setattr(os, "fsync", lambda fd: calls.append(fd))

    stream.write(b"x" * 1024)  # tiny, under the default interval

    assert len(calls) == 0
    stream.close()


def test_sync_on_close(tmp_path, monkeypatch):
    stream, path = _new_stream(tmp_path)
    content = b"HELLO-WORLD" * 8
    stream.add("test.nca", len(content))
    stream.write(content)

    calls = []
    monkeypatch.setattr(os, "fsync", lambda fd: calls.append(fd))

    stream.close()

    assert len(calls) >= 1
    assert path.exists()
    # File must be readable and start with a valid PFS0 header.
    assert path.read_bytes()[:4] == b"PFS0"


def test_sync_swallows_oserror(tmp_path, monkeypatch):
    stream, path = _new_stream(tmp_path)

    def raising_fsync(fd):
        raise OSError("fsync not supported on this fs")

    monkeypatch.setattr(os, "fsync", raising_fsync)

    content = b"y" * 4096
    stream.write(content)

    # Triggering a sync must NOT propagate the OSError.
    stream._sync()

    stream.close()
    assert path.exists()


def test_truncate_still_used_for_small_files(tmp_path):
    # Preserve bfd1b05: prealloc truncate for <=2GiB, skipped above it.
    class FakeFile:
        def __init__(self):
            self.truncate_calls = []
            self._pos = 0

        def tell(self):
            return self._pos

        def seek(self, n, whence=0):
            self._pos = n

        def truncate(self, n):
            self.truncate_calls.append(n)

        def flush(self):
            pass

        def close(self):
            pass

    stream, _ = _new_stream(tmp_path)
    real = stream.f  # the real file handle opened by the constructor

    # --- small final size: truncate IS used ---
    fake = FakeFile()
    stream.f = fake
    stream.offset = 0
    stream.addpos = 1000
    stream.updateHashHeader()
    assert fake.truncate_calls == [1000]

    # --- >2 GiB final size: truncate is NOT used ---
    fake_big = FakeFile()
    stream.f = fake_big
    stream.addpos = 3 * 1024 * 1024 * 1024  # 3 GiB
    stream.updateHashHeader()
    assert fake_big.truncate_calls == []

    # Cleanup: close the real handle, detach so __del__ is a no-op.
    real.close()
    stream.f = None
