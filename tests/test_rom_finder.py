"""Tests for ROM auto-detect fuzzy matching."""

import hashlib
import importlib.util
import json
import os
import sys

# Import rom_finder directly to avoid services/__init__.py (which pulls in
# download_manager → nsz → argparse and crashes under pytest).
_mod_path = os.path.join(
    os.path.dirname(__file__), "..", "src", "services", "rom_finder.py"
)
_spec = importlib.util.spec_from_file_location("rom_finder", _mod_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

_normalize = _mod._normalize
_fuzzy_score = _mod._fuzzy_score
_resolve_cue_track1 = _mod._resolve_cue_track1
RomFinderConfig = _mod.RomFinderConfig
RomFinder = _mod.RomFinder


class TestNormalize:
    def test_strips_region_tags(self):
        assert _normalize("NHL '94 (USA).zip") == "nhl 94"

    def test_strips_multiple_region_tags(self):
        assert _normalize("Game (USA, Europe).bin") == "game"

    def test_removes_punctuation(self):
        assert _normalize("NHL '94") == "nhl 94"

    def test_removes_extension(self):
        assert _normalize("game.sfc") == "game"

    def test_lowercases(self):
        assert _normalize("NHL Hockey") == "nhl hockey"

    def test_strips_extra_whitespace(self):
        assert _normalize("  NHL   94  ") == "nhl 94"


class TestFuzzyScore:
    def test_exact_match_scores_100(self):
        assert _fuzzy_score("NHL 94", "NHL '94 (USA).zip") == 100

    def test_containment_scores_80(self):
        assert _fuzzy_score("NHL 94", "Some NHL 94 Collection (USA).zip") == 80

    def test_no_match_scores_low(self):
        assert _fuzzy_score("NHL 94", "FIFA 2002 (USA).zip") < 50

    def test_partial_overlap(self):
        score = _fuzzy_score("International Superstar Soccer",
                             "International Superstar Soccer Deluxe (USA).zip")
        assert score >= 50

    def test_winning_eleven(self):
        score = _fuzzy_score("World Soccer Winning Eleven 2002",
                             "World Soccer Winning Eleven 2002 (Japan).zip")
        assert score == 100

    def test_mvp_baseball_ambiguity(self):
        score = _fuzzy_score("MVP Baseball", "MVP Baseball (Japan) (En).zip")
        assert score >= 80


class TestScanLocal:
    def _make_config(self, **overrides):
        defaults = dict(
            search_terms=["NHL 94"],
            system_folders=["snes", "supernintendo"],
            file_extensions=[".sfc", ".smc", ".zip"],
            system_type="snes",
        )
        defaults.update(overrides)
        return RomFinderConfig(**defaults)

    def test_finds_rom_in_system_folder(self, tmp_path):
        snes_dir = tmp_path / "snes"
        snes_dir.mkdir()
        rom = snes_dir / "NHL '94 (USA).sfc"
        rom.write_bytes(b"\x00" * 100)
        finder = RomFinder()
        result = finder._scan_local(self._make_config(), str(tmp_path))
        assert result is not None
        assert result == str(rom)

    def test_finds_rom_in_alternate_folder(self, tmp_path):
        alt_dir = tmp_path / "supernintendo"
        alt_dir.mkdir()
        rom = alt_dir / "NHL '94 (USA).sfc"
        rom.write_bytes(b"\x00" * 100)
        finder = RomFinder()
        result = finder._scan_local(self._make_config(), str(tmp_path))
        assert result is not None
        assert "supernintendo" in result

    def test_returns_none_when_no_match(self, tmp_path):
        snes_dir = tmp_path / "snes"
        snes_dir.mkdir()
        (snes_dir / "FIFA 2002 (USA).sfc").write_bytes(b"\x00" * 100)
        finder = RomFinder()
        result = finder._scan_local(self._make_config(), str(tmp_path))
        assert result is None

    def test_prefers_usa_region(self, tmp_path):
        snes_dir = tmp_path / "snes"
        snes_dir.mkdir()
        (snes_dir / "NHL '94 (Europe).sfc").write_bytes(b"\x00" * 100)
        (snes_dir / "NHL '94 (USA).sfc").write_bytes(b"\x00" * 100)
        finder = RomFinder()
        result = finder._scan_local(self._make_config(), str(tmp_path))
        assert "(USA)" in result

    def test_ignores_wrong_extension(self, tmp_path):
        snes_dir = tmp_path / "snes"
        snes_dir.mkdir()
        (snes_dir / "NHL '94 (USA).txt").write_bytes(b"\x00" * 100)
        finder = RomFinder()
        result = finder._scan_local(self._make_config(), str(tmp_path))
        assert result is None

    def test_skips_missing_folder(self, tmp_path):
        finder = RomFinder()
        result = finder._scan_local(self._make_config(), str(tmp_path))
        assert result is None


class TestSearchCache:
    def _make_config(self, **overrides):
        defaults = dict(
            search_terms=["NHL 94"],
            system_folders=["snes"],
            file_extensions=[".sfc", ".zip"],
            system_type="snes",
        )
        defaults.update(overrides)
        return RomFinderConfig(**defaults)

    def _setup_cache(self, tmp_path, url, entries):
        listings_dir = tmp_path / "listings"
        listings_dir.mkdir(parents=True, exist_ok=True)
        url_hash = hashlib.md5(url.encode()).hexdigest()
        cache_file = listings_dir / f"{url_hash}.json"
        cache_file.write_text(json.dumps(entries))
        return str(tmp_path)

    def test_finds_game_in_cache(self, tmp_path):
        url = "https://example.com/snes/"
        entries = [
            {"filename": "NHL '94 (USA).zip", "href": "https://example.com/nhl94.zip", "size": 1000},
            {"filename": "FIFA (USA).zip", "href": "https://example.com/fifa.zip", "size": 2000},
        ]
        cache_dir = self._setup_cache(tmp_path, url, entries)
        systems_data = [{"name": "SNES Backups", "url": url, "roms_folder": "snes"}]
        finder = RomFinder()
        entry, system = finder._search_cache(self._make_config(), systems_data, cache_dir)
        assert entry is not None
        assert entry["filename"] == "NHL '94 (USA).zip"
        assert system["name"] == "SNES Backups"

    def test_returns_none_when_no_cache(self, tmp_path):
        systems_data = [{"name": "SNES", "url": "https://missing.com/", "roms_folder": "snes"}]
        finder = RomFinder()
        entry, system = finder._search_cache(self._make_config(), systems_data, str(tmp_path))
        assert entry is None
        assert system is None

    def test_handles_multi_url_system(self, tmp_path):
        url1 = "https://example.com/snes1/"
        url2 = "https://example.com/snes2/"
        self._setup_cache(tmp_path, url1, [{"filename": "Mario.zip", "href": "x", "size": 1}])
        self._setup_cache(tmp_path, url2, [
            {"filename": "NHL '94 (USA).zip", "href": "https://example.com/nhl94.zip", "size": 1000}
        ])
        cache_dir = str(tmp_path)
        systems_data = [{"name": "SNES", "url": [url1, url2], "roms_folder": "snes"}]
        finder = RomFinder()
        entry, system = finder._search_cache(self._make_config(), systems_data, cache_dir)
        assert entry is not None
        assert entry["filename"] == "NHL '94 (USA).zip"

    def test_skips_non_matching_system_type(self, tmp_path):
        url = "https://example.com/genesis/"
        entries = [{"filename": "NHL '94 (USA).bin", "href": "x", "size": 1}]
        self._setup_cache(tmp_path, url, entries)
        systems_data = [{"name": "Genesis", "url": url, "roms_folder": "genesis"}]
        finder = RomFinder()
        entry, system = finder._search_cache(self._make_config(), systems_data, str(tmp_path))
        assert entry is None


class TestResolveCueTrack1:
    def test_resolves_single_track(self, tmp_path):
        cue = tmp_path / "game.cue"
        bin_file = tmp_path / "game.bin"
        bin_file.write_bytes(b"\x00" * 100)
        cue.write_text('FILE "game.bin" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n')
        result = _resolve_cue_track1(str(cue))
        assert result == str(bin_file)

    def test_resolves_multi_track(self, tmp_path):
        cue = tmp_path / "game.cue"
        track1 = tmp_path / "game (Track 1).bin"
        track2 = tmp_path / "game (Track 2).bin"
        track1.write_bytes(b"\x00" * 100)
        track2.write_bytes(b"\x00" * 100)
        cue.write_text(
            'FILE "game (Track 1).bin" BINARY\n  TRACK 01 MODE2/2352\n'
            'FILE "game (Track 2).bin" BINARY\n  TRACK 02 AUDIO\n'
        )
        result = _resolve_cue_track1(str(cue))
        assert result == str(track1)

    def test_returns_none_if_bin_missing(self, tmp_path):
        cue = tmp_path / "game.cue"
        cue.write_text('FILE "missing.bin" BINARY\n  TRACK 01 MODE2/2352\n')
        result = _resolve_cue_track1(str(cue))
        assert result is None

    def test_returns_none_for_invalid_cue(self, tmp_path):
        cue = tmp_path / "game.cue"
        cue.write_text("not a valid cue file")
        result = _resolve_cue_track1(str(cue))
        assert result is None
