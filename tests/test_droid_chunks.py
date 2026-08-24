"""TDD tests for droid.chunks: pure logic behind the single-write download path.

Motivation (Odin 2 field failure, 2026-08-24): the parallel downloader wrote
4 x 2GB .partN files, then a stitch pass rewrote all 8GB, then the extraction
service copied 8GB again to the SD card. The service process was SIGKILLed
(lmkd) mid-stitch, leaving 15GB of junk and a UI frozen at 99%.

New design: workers write byte ranges directly at offsets into one
preallocated hidden file at the final destination, fsync periodically, and
record committed progress in a sidecar meta file so a killed download resumes
instead of restarting.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from droid import chunks  # noqa: E402


# ---- compute_ranges ----


def test_compute_ranges_covers_total_without_gaps():
    ranges = chunks.compute_ranges(1000, 4)
    assert len(ranges) == 4
    assert ranges[0][0] == 0
    assert ranges[-1][1] == 999
    for (_, prev_end), (next_start, _) in zip(ranges, ranges[1:]):
        assert next_start == prev_end + 1


def test_compute_ranges_single_worker():
    assert chunks.compute_ranges(500, 1) == [(0, 499)]


# ---- needs_extraction ----


def test_needs_extraction_zip_with_should_unzip():
    assert chunks.needs_extraction("game.zip", {"should_unzip": True})


def test_needs_extraction_zip_without_should_unzip():
    assert not chunks.needs_extraction("game.zip", {"should_unzip": False})
    assert not chunks.needs_extraction("game.zip", {})


def test_needs_extraction_nsz():
    assert chunks.needs_extraction("game.nsz", {})


def test_needs_extraction_plain_file():
    assert not chunks.needs_extraction("game.iso", {"should_unzip": True})


# ---- download_paths ----


def test_download_paths_direct_to_dest_when_no_extraction():
    tmp, final = chunks.download_paths(
        "game.zip", "/work", "/sd/roms", {"should_unzip": False}
    )
    assert final == "/sd/roms/game.zip"
    assert os.path.dirname(tmp) == "/sd/roms"
    assert os.path.basename(tmp).startswith(".")
    assert tmp != final


def test_download_paths_workdir_when_extraction_needed():
    tmp, final = chunks.download_paths(
        "game.zip", "/work", "/sd/roms", {"should_unzip": True}
    )
    assert final == "/work/game.zip"
    assert os.path.dirname(tmp) == "/work"
    assert tmp != final


# ---- resume metadata ----


def test_committed_roundtrip(tmp_path):
    meta = str(tmp_path / "meta.json")
    chunks.save_committed(meta, 8000, [1, 2, 3, 4])
    assert chunks.load_committed(meta, 8000, 4) == [1, 2, 3, 4]


def test_committed_total_size_mismatch_returns_none(tmp_path):
    meta = str(tmp_path / "meta.json")
    chunks.save_committed(meta, 8000, [1, 2, 3, 4])
    assert chunks.load_committed(meta, 9000, 4) is None


def test_committed_worker_count_mismatch_returns_none(tmp_path):
    meta = str(tmp_path / "meta.json")
    chunks.save_committed(meta, 8000, [1, 2])
    assert chunks.load_committed(meta, 8000, 4) is None


def test_committed_missing_file_returns_none(tmp_path):
    assert chunks.load_committed(str(tmp_path / "nope.json"), 8000, 4) is None


def test_committed_corrupt_file_returns_none(tmp_path):
    meta = tmp_path / "meta.json"
    meta.write_text("{not json")
    assert chunks.load_committed(str(meta), 8000, 4) is None


# ---- write_stream_at ----


def _prealloc(tmp_path, size):
    path = str(tmp_path / "out.bin")
    with open(path, "wb") as f:
        f.truncate(size)
    return path


def test_write_stream_at_writes_at_offset(tmp_path):
    path = _prealloc(tmp_path, 10)
    written = chunks.write_stream_at(path, 4, [b"ab", b"cd"])
    assert written == 4
    with open(path, "rb") as f:
        data = f.read()
    assert data == b"\x00\x00\x00\x00abcd\x00\x00"


def test_write_stream_at_reports_bytes_per_chunk(tmp_path):
    path = _prealloc(tmp_path, 10)
    seen = []
    chunks.write_stream_at(path, 0, [b"ab", b"c"], on_bytes=seen.append)
    assert seen == [2, 1]


def test_write_stream_at_commits_on_fsync_interval_and_at_end(tmp_path):
    path = _prealloc(tmp_path, 10)
    committed = []
    chunks.write_stream_at(
        path,
        0,
        [b"ab", b"cd", b"e"],
        on_committed=committed.append,
        fsync_every=3,
    )
    # First commit once >=3 bytes written (after 2nd chunk), final commit at end
    assert committed == [4, 5]


def test_write_stream_at_resume_completes_file(tmp_path):
    path = _prealloc(tmp_path, 8)
    # First attempt wrote 3 bytes of the range starting at offset 2
    chunks.write_stream_at(path, 2, [b"abc"])
    # Resume: continue at offset 2+3 with the rest
    chunks.write_stream_at(path, 5, [b"def"])
    with open(path, "rb") as f:
        assert f.read() == b"\x00\x00abcdef"


# ---- select_zip_members ----


def test_select_zip_members_filters_top_level_by_format():
    names = ["game.iso", "readme.txt", "nested/other.iso"]
    got = chunks.select_zip_members(names, [".iso"], extract_contents=True)
    assert got == ["game.iso"]


def test_select_zip_members_all_when_keeping_structure():
    names = ["folder/", "folder/game.bin", "info.txt"]
    got = chunks.select_zip_members(names, [".bin"], extract_contents=False)
    assert got == names


def test_select_zip_members_case_insensitive():
    got = chunks.select_zip_members(["GAME.ISO"], [".iso"], extract_contents=True)
    assert got == ["GAME.ISO"]
