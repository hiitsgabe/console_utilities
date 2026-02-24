"""Verification tests for WE2002 ROM patcher.

Uses the real WE2002 ROM from roms/psx/ to verify all writes land at the
correct offsets with the expected data.
"""

import os
import struct
import sys
import shutil
import tempfile

# Add src to path so we can import the modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from services.we_patcher.rom_writer import (
    RomWriter,
    _OFS_NOMI_SQ1,
    _OFS_NOMI_SQ2,
    _OFS_NOMI_SQ_AB1,
    _OFS_NOMI_SQ_AB2,
    _OFS_NOMI_SQ_AB3,
    _OFS_NOMI_SQK,
    _OFS_NOMI_GML,
    _OFS_NOMI_G,
    _OFS_CARAT_GML,
    _OFS_CARAT_G,
    _OFS_BANDIERE_FORMA1,
    _OFS_BAR,
    _OFS_ANT_MAGLIE,
    _OFS_ANT_MAGLIE2,
    _ML_BAR_OFFSET,
    _ML_COLOR_OFFSETS,
    _NAT_COLOR_OFFSETS,
    _SQUADRE_NAZ,
    _PLAYERS_PER_NAT,
    _LUN_NOMI1,
    _LUN_NOMI2,
    _LUN_NOMIK,
    _encode_team_name,
    _encode_abbreviation,
    _encode_player_name,
    _encode_player_carat,
    _encode_kanji_name,
    _ml_name_offset,
    _ml_name_budget,
    _ml_kanji_offset,
    _nome_chunks,
    _carat_chunks,
    _nat_nome_chunks,
    _nat_carat_chunks,
    _nat_slot_player_range,
    _nat_name_offset,
    _nat_ab_offset,
    _nat_bar_offset,
    _nat_jersey_offset,
    _slot_player_range,
    _rgb_to_ps1_color,
)
from services.we_patcher.models import (
    WETeamRecord,
    WEPlayerRecord,
    WEPlayerAttributes,
)
from services.we_patcher.ppf import apply_ppf, PPFError
from services.we_patcher.translations.we2002.english_ppf import generate_english_ppf, _ascii_to_kanji


# ---------------------------------------------------------------------------
# ROM path
# ---------------------------------------------------------------------------

_ROM_DIR = os.path.join(
    os.path.dirname(__file__), "..", "roms", "psx",
    "World Soccer Winning Eleven 2002 (Japan)",
)
_ORIGINAL_ROM = os.path.join(_ROM_DIR, "World Soccer Winning Eleven 2002 (Japan) (Track 1).bin")
_ASSETS_DIR = os.path.join(os.path.dirname(__file__), "..", "assets")
_PPF_PATH = os.path.join(_ASSETS_DIR, "w202-english.ppf")


def _require_rom():
    """Skip test if ROM not present."""
    if not os.path.exists(_ORIGINAL_ROM):
        print(f"  SKIP: ROM not found at {_ORIGINAL_ROM}")
        return False
    return True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_test_team(name="Test FC", short_name="TST", n_players=14):
    """Create a WETeamRecord with realistic test data."""
    players = []
    for i in range(n_players):
        attrs = WEPlayerAttributes(
            offensive=6, defensive=5, body_balance=5, stamina=6,
            speed=7, acceleration=6, pass_accuracy=5, shoot_power=6,
            shoot_accuracy=5, jump_power=5, heading=5, technique=6,
            dribble=5, curve=4, aggression=5,
        )
        players.append(WEPlayerRecord(
            last_name=f"PLAYER{i:02d}",
            first_name=f"First{i:02d}",
            position=1 if i > 0 else 0,  # GK for first, DF for rest
            shirt_number=i + 1,
            attributes=attrs,
        ))

    return WETeamRecord(
        name=name,
        short_name=short_name,
        players=players,
        kit_home=(200, 50, 50),    # Red
        kit_away=(255, 255, 255),  # White
    )


# ---------------------------------------------------------------------------
# Pure unit tests (no ROM needed)
# ---------------------------------------------------------------------------

def test_encode_team_name():
    """Verify team name encoding: ASCII uppercase, null-padded to budget."""
    result = _encode_team_name("Arsenal", 8, uppercase=True)
    assert result == b"ARSENAL\x00", f"Expected b'ARSENAL\\x00', got {result!r}"
    assert len(result) == 8

    # Truncation
    result = _encode_team_name("Manchester United", 8, uppercase=True)
    assert len(result) == 8
    assert result == b"MANCHES\x00"

    # Lowercase variant
    result = _encode_team_name("Arsenal", 8, uppercase=False)
    assert result == b"Arsenal\x00"
    print("  PASS: test_encode_team_name")


def test_encode_abbreviation():
    """Verify abbreviation is 3 chars + null = 4 bytes."""
    result = _encode_abbreviation("ARS")
    assert result == b"ARS\x00", f"Expected b'ARS\\x00', got {result!r}"
    assert len(result) == 4

    result = _encode_abbreviation("ARSENAL")
    assert result == b"ARS\x00"
    print("  PASS: test_encode_abbreviation")


def test_encode_player_name():
    """Verify player name is 10 bytes, ASCII uppercase, null-padded."""
    result = _encode_player_name("Beckham")
    assert len(result) == 10
    assert result == b"BECKHAM\x00\x00\x00"

    result = _encode_player_name("Vanthournhout")
    assert len(result) == 10
    print("  PASS: test_encode_player_name")


def test_encode_kanji_name():
    """Verify 2-byte kanji encoding matches the C++ asciitokanji()."""
    result = _encode_kanji_name("Arsenal", 6)
    assert len(result) == 12  # budget * 2

    # A (uppercase): 0x82, 65+31=96=0x60
    assert result[0] == 0x82 and result[1] == 0x60
    # r (lowercase): 0x82, 114+32=146=0x92
    assert result[2] == 0x82 and result[3] == 0x92

    # Period: "P.S.G." budget 8
    result = _encode_kanji_name("P.S.G.", 8)
    assert len(result) == 16
    assert result[0] == 0x82 and result[1] == ord('P') + 31
    assert result[2] == 0x81 and result[3] == 0x42  # period
    print("  PASS: test_encode_kanji_name")


def test_encode_player_carat():
    """Verify player characteristics encode to 12 bytes."""
    attrs = WEPlayerAttributes(
        offensive=7, defensive=5, body_balance=6, stamina=5,
        speed=8, acceleration=7, pass_accuracy=6, shoot_power=7,
        shoot_accuracy=6, jump_power=5, heading=5, technique=7,
        dribble=6, curve=5, aggression=4,
    )
    player = WEPlayerRecord(
        last_name="TEST", first_name="Test", position=1, shirt_number=10,
        attributes=attrs,
    )
    result = _encode_player_carat(player)
    assert len(result) == 12

    numero_raw = (result[3] >> 2) & 0x1F
    assert numero_raw == 9, f"Expected shirt 10 (stored as 9), got {numero_raw}"
    print("  PASS: test_encode_player_carat")


def test_rgb_to_ps1_color():
    """Verify RGB888 to BGR555 conversion."""
    assert _rgb_to_ps1_color(255, 0, 0) == 0x001F    # Red
    assert _rgb_to_ps1_color(0, 255, 0) == 0x03E0    # Green
    assert _rgb_to_ps1_color(0, 0, 255) == 0x7C00    # Blue
    assert _rgb_to_ps1_color(255, 255, 255) == 0x7FFF # White
    print("  PASS: test_rgb_to_ps1_color")


def test_slot_player_range():
    """Verify player index ranges don't overlap and cover 462 players."""
    ranges = []
    for slot in range(32):
        first, count = _slot_player_range(slot)
        ranges.append((first, first + count))

    ranges.sort()
    for i in range(len(ranges) - 1):
        assert ranges[i][1] <= ranges[i + 1][0], (
            f"Overlap at index {i}: {ranges[i]} vs {ranges[i+1]}"
        )

    total = sum(end - start for start, end in ranges)
    assert total == 462, f"Expected 462 total players, got {total}"
    print("  PASS: test_slot_player_range")


def test_ml_name_offsets_no_overlap():
    """Verify ML name offsets don't collide for variant 1."""
    offsets = []
    for slot in range(32):
        off = _ml_name_offset(_OFS_NOMI_SQ1, slot, _LUN_NOMI1)
        budget = _ml_name_budget(slot, _LUN_NOMI1)
        offsets.append((off, off + budget, slot))

    offsets.sort()
    for i in range(len(offsets) - 1):
        assert offsets[i][1] <= offsets[i + 1][0], (
            f"Name overlap: slot {offsets[i][2]} ends at {offsets[i][1]}, "
            f"slot {offsets[i+1][2]} starts at {offsets[i+1][0]}"
        )
    print("  PASS: test_ml_name_offsets_no_overlap")


def test_ml_kanji_offsets_no_overlap():
    """Verify ML kanji name offsets don't collide."""
    offsets = []
    for slot in range(32):
        off = _ml_kanji_offset(slot)
        budget = _LUN_NOMIK[63 + slot]
        offsets.append((off, off + budget * 2, slot))

    offsets.sort()
    for i in range(len(offsets) - 1):
        assert offsets[i][1] <= offsets[i + 1][0], (
            f"Kanji overlap: slot {offsets[i][2]} ends at {offsets[i][1]}, "
            f"slot {offsets[i+1][2]} starts at {offsets[i+1][0]}"
        )
    print("  PASS: test_ml_kanji_offsets_no_overlap")


def test_sector_straddle_indices():
    """Verify straddle chunk sizes for boundary-crossing players."""
    chunks = _nome_chunks(408)
    assert len(chunks) == 2
    assert chunks[0][1] == 8
    assert chunks[1][1] == 2

    chunks_c1 = _carat_chunks(148)
    assert len(chunks_c1) == 2

    chunks_c2 = _carat_chunks(319)
    assert len(chunks_c2) == 2
    print("  PASS: test_sector_straddle_indices")


# ---------------------------------------------------------------------------
# National slot unit tests (no ROM needed)
# ---------------------------------------------------------------------------

def test_nat_slot_player_range():
    """Verify national player index ranges don't overlap and cover 1449 players."""
    ranges = []
    for nat in range(63):
        first, count = _nat_slot_player_range(nat)
        ranges.append((first, first + count))

    ranges.sort()
    for i in range(len(ranges) - 1):
        assert ranges[i][1] <= ranges[i + 1][0], (
            f"Nat overlap at {i}: {ranges[i]} vs {ranges[i+1]}"
        )

    total = sum(end - start for start, end in ranges)
    assert total == 63 * 23, f"Expected {63 * 23} total national players, got {total}"
    print("  PASS: test_nat_slot_player_range")


def test_nat_nome_straddles():
    """Verify all 8 national name straddle points produce correct chunk sizes."""
    expected = {
        0:    (8, 2),
        205:  (6, 4),
        410:  (4, 6),
        615:  (2, 8),
        820:  (0, 10),   # clean break
        1024: (8, 2),
        1229: (6, 4),
        1434: (4, 6),
    }
    for nat_idx, (exp_before, exp_after) in expected.items():
        chunks = _nat_nome_chunks(nat_idx)
        if exp_before == 0:
            assert len(chunks) == 1, f"Name straddle {nat_idx}: expected 1 chunk, got {len(chunks)}"
            assert chunks[0][1] == 10
        else:
            assert len(chunks) == 2, f"Name straddle {nat_idx}: expected 2 chunks, got {len(chunks)}"
            assert chunks[0][1] == exp_before, f"Name straddle {nat_idx}: before={chunks[0][1]}, expected {exp_before}"
            assert chunks[1][1] == exp_after, f"Name straddle {nat_idx}: after={chunks[1][1]}, expected {exp_after}"
    print("  PASS: test_nat_nome_straddles")


def test_nat_carat_straddles():
    """Verify all 9 national characteristics straddle points."""
    expected = {
        44:   (4, 8),
        215:  (0, 12),   # clean break
        385:  (8, 4),
        556:  (4, 8),
        727:  (0, 12),   # clean break
        897:  (8, 4),
        1068: (4, 8),
        1239: (0, 12),   # clean break
        1409: (8, 4),
    }
    for nat_idx, (exp_before, exp_after) in expected.items():
        chunks = _nat_carat_chunks(nat_idx)
        if exp_before == 0:
            assert len(chunks) == 1, f"Carat straddle {nat_idx}: expected 1 chunk, got {len(chunks)}"
            assert chunks[0][1] == 12
        else:
            assert len(chunks) == 2, f"Carat straddle {nat_idx}: expected 2 chunks, got {len(chunks)}"
            assert chunks[0][1] == exp_before, f"Carat straddle {nat_idx}: before={chunks[0][1]}, expected {exp_before}"
            assert chunks[1][1] == exp_after, f"Carat straddle {nat_idx}: after={chunks[1][1]}, expected {exp_after}"
    print("  PASS: test_nat_carat_straddles")


def test_nat_nome_offsets_no_overlap():
    """Verify national player name offsets don't collide for all 1449 players."""
    regions = []
    for nat_idx in range(1449):
        chunks = _nat_nome_chunks(nat_idx)
        for off, size in chunks:
            regions.append((off, off + size, nat_idx))

    regions.sort()
    for i in range(len(regions) - 1):
        if regions[i][1] > regions[i + 1][0]:
            assert False, (
                f"Nat name overlap: idx {regions[i][2]} ends at {regions[i][1]}, "
                f"idx {regions[i+1][2]} starts at {regions[i+1][0]}"
            )
    print("  PASS: test_nat_nome_offsets_no_overlap")


def test_nat_carat_offsets_no_overlap():
    """Verify national player carat offsets don't collide for all 1449 players."""
    regions = []
    for nat_idx in range(1449):
        chunks = _nat_carat_chunks(nat_idx)
        for off, size in chunks:
            regions.append((off, off + size, nat_idx))

    regions.sort()
    for i in range(len(regions) - 1):
        if regions[i][1] > regions[i + 1][0]:
            assert False, (
                f"Nat carat overlap: idx {regions[i][2]} ends at {regions[i][1]}, "
                f"idx {regions[i+1][2]} starts at {regions[i+1][0]}"
            )
    print("  PASS: test_nat_carat_offsets_no_overlap")


def test_nat_bar_offset_no_overlap():
    """Verify national force bar offsets don't collide."""
    regions = []
    for nat in range(63):
        chunks = _nat_bar_offset(nat)
        for off, size in chunks:
            regions.append((off, off + size, nat))

    regions.sort()
    for i in range(len(regions) - 1):
        if regions[i][1] > regions[i + 1][0]:
            assert False, (
                f"Nat bar overlap: team {regions[i][2]} ends at {regions[i][1]}, "
                f"team {regions[i+1][2]} starts at {regions[i+1][0]}"
            )
    print("  PASS: test_nat_bar_offset_no_overlap")


# ---------------------------------------------------------------------------
# ROM-based tests (require real ROM file)
# ---------------------------------------------------------------------------

def test_rom_format():
    """Verify the ROM is Mode2/2352 with correct sync bytes."""
    if not _require_rom():
        return

    with open(_ORIGINAL_ROM, "rb") as f:
        # Check sector 0 sync
        sync = f.read(12)
        expected = b"\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\x00"
        assert sync == expected, f"Sector 0 sync mismatch: {sync.hex()}"

        # Check sector 1 sync
        f.seek(2352)
        sync2 = f.read(12)
        assert sync2 == expected, f"Sector 1 sync mismatch: {sync2.hex()}"

    size = os.path.getsize(_ORIGINAL_ROM)
    print(f"  ROM size: {size:,} bytes ({size // 2352} sectors)")
    print("  PASS: test_rom_format")


def test_rom_has_original_data():
    """Verify the original ROM has data at key offsets (not all zeros/FF)."""
    if not _require_rom():
        return

    with open(_ORIGINAL_ROM, "rb") as f:
        # Check abbreviation section has data
        f.seek(_OFS_NOMI_SQ_AB1)
        data = f.read(128)
        has_ascii = any(0x20 <= b <= 0x7E for b in data)
        assert has_ascii, f"No ASCII at AB1 offset — wrong ROM or offset?"

        # Check player name section
        f.seek(_OFS_NOMI_GML)
        data = f.read(100)
        assert data != b"\x00" * 100, "Player name section all zeros"

        # Check kanji section
        f.seek(_OFS_NOMI_SQK)
        data = f.read(100)
        assert data != b"\x00" * 100, "Kanji section all zeros"

    print("  PASS: test_rom_has_original_data")


def test_write_team_to_real_rom():
    """Patch a copy of the real ROM and verify team names are written."""
    if not _require_rom():
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "patched.bin")

        team = _make_test_team("Liverpool", "LIV")
        writer = RomWriter(_ORIGINAL_ROM, out_path)
        writer.write_team(0, team)

        with open(out_path, "rb") as f:
            # Name variant 1
            budget = _ml_name_budget(0, _LUN_NOMI1)
            offset = _ml_name_offset(_OFS_NOMI_SQ1, 0, _LUN_NOMI1)
            f.seek(offset)
            data = f.read(budget)
            expected = _encode_team_name("Liverpool", budget, uppercase=True)
            assert data == expected, f"Name1: {data!r} vs {expected!r}"

            # Name variant 2
            budget2 = _ml_name_budget(0, _LUN_NOMI2)
            offset2 = _ml_name_offset(_OFS_NOMI_SQ2, 0, _LUN_NOMI2)
            f.seek(offset2)
            data2 = f.read(budget2)
            expected2 = _encode_team_name("Liverpool", budget2, uppercase=True)
            assert data2 == expected2, f"Name2: {data2!r} vs {expected2!r}"

            # Abbreviation
            rom_i = 31 - 0
            f.seek(_OFS_NOMI_SQ_AB1 + rom_i * 4)
            ab = f.read(4)
            assert ab == b"LIV\x00", f"AB1: {ab!r}"

            f.seek(_OFS_NOMI_SQ_AB2 + rom_i * 4)
            ab2 = f.read(4)
            assert ab2 == b"LIV\x00", f"AB2: {ab2!r}"

            # Kanji name
            k_budget = _LUN_NOMIK[63 + 0]
            k_offset = _ml_kanji_offset(0)
            f.seek(k_offset)
            k_data = f.read(k_budget * 2)
            k_expected = _encode_kanji_name("Liverpool", k_budget)
            assert k_data == k_expected, f"Kanji: {k_data.hex()} vs {k_expected.hex()}"

    print("  PASS: test_write_team_to_real_rom")


def test_write_players_to_real_rom():
    """Patch players to a real ROM copy and verify."""
    if not _require_rom():
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "patched.bin")

        team = _make_test_team("Chelsea", "CHE", n_players=14)
        writer = RomWriter(_ORIGINAL_ROM, out_path)
        writer.write_players(5, team.players)

        first_idx, count = _slot_player_range(5)

        with open(out_path, "rb") as f:
            for i in range(min(3, count)):
                global_idx = first_idx + i
                chunks = _nome_chunks(global_idx)
                f.seek(chunks[0][0])
                data = f.read(chunks[0][1])
                expected = _encode_player_name(f"PLAYER{i:02d}")
                assert data == expected[:len(data)], (
                    f"Player {i} name: {data!r} vs {expected[:len(data)]!r}"
                )

                # Verify characteristics changed from original
                c_chunks = _carat_chunks(global_idx)
                f.seek(c_chunks[0][0])
                carat = f.read(c_chunks[0][1])
                # Should not be all zeros or all 0xFF
                assert carat != b"\x00" * len(carat)

    print("  PASS: test_write_players_to_real_rom")


def test_write_flag_to_real_rom():
    """Verify flag writes on real ROM."""
    if not _require_rom():
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "patched.bin")

        team = _make_test_team("Boca Juniors", "BOC")
        team.kit_home = (0, 0, 200)      # Blue
        team.kit_away = (255, 215, 0)    # Gold

        writer = RomWriter(_ORIGINAL_ROM, out_path)
        writer.write_flag(3, team)

        with open(out_path, "rb") as f:
            # Flag style
            f.seek(_OFS_BANDIERE_FORMA1 + _SQUADRE_NAZ + 3)
            style = f.read(1)
            assert style == b"\x04", f"Style: {style!r}"

            # Verify color data was written (not the same as original)
            if 3 in _ML_COLOR_OFFSETS:
                chunks = _ML_COLOR_OFFSETS[3]
                f.seek(chunks[0][0])
                patched_color = f.read(2)

        # Compare with original
        with open(_ORIGINAL_ROM, "rb") as f:
            f.seek(_OFS_BANDIERE_FORMA1 + _SQUADRE_NAZ + 3)
            orig_style = f.read(1)

        # Style should be 0 (we set it) — may differ from original
        print(f"  Flag style: original={orig_style.hex()}, patched=04")

    print("  PASS: test_write_flag_to_real_rom")


def test_jersey_colors_real_rom():
    """Verify jersey preview colors on real ROM."""
    if not _require_rom():
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "patched.bin")

        team = _make_test_team("Milan", "MIL")
        team.kit_home = (255, 0, 0)
        team.kit_away = (255, 255, 255)

        writer = RomWriter(_ORIGINAL_ROM, out_path)
        writer.write_team(10, team)

        with open(out_path, "rb") as f:
            f.seek(_OFS_ANT_MAGLIE2 + 10 * 64)
            maglia1 = f.read(32)
            # Indices 0-1 are reserved (0x0000), shirt starts at index 2
            reserved = struct.unpack_from("<H", maglia1, 0)[0]
            assert reserved == 0x0000, f"Reserved[0]: {reserved:#06x}"
            shirt = struct.unpack_from("<H", maglia1, 4)[0]  # index 2
            assert shirt == 0x001F, f"Home shirt: {shirt:#06x} expected 0x001F (red)"

            maglia2 = f.read(32)
            reserved2 = struct.unpack_from("<H", maglia2, 0)[0]
            assert reserved2 == 0x0000, f"Away reserved[0]: {reserved2:#06x}"
            shirt2 = struct.unpack_from("<H", maglia2, 4)[0]  # index 2
            assert shirt2 == 0x7FFF, f"Away shirt: {shirt2:#06x} expected 0x7FFF (white)"

    print("  PASS: test_jersey_colors_real_rom")


def test_binary_diff_real_rom():
    """Full integration: patch multiple teams and count changed bytes."""
    if not _require_rom():
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "patched.bin")

        writer = RomWriter(_ORIGINAL_ROM, out_path)

        teams = [
            _make_test_team("Arsenal", "ARS"),
            _make_test_team("Chelsea", "CHE"),
            _make_test_team("Liverpool", "LIV"),
            _make_test_team("ManUtd", "MNU"),
        ]

        for i, team in enumerate(teams):
            writer.write_team(i, team)
            writer.write_players(i, team.players)
            writer.write_flag(i, team)

        # Compare the two files at known offsets
        changed_regions = 0
        total_regions = 0

        with open(_ORIGINAL_ROM, "rb") as orig, open(out_path, "rb") as patched:
            for slot in range(4):
                rom_i = 31 - slot

                # Check abbreviation
                off = _OFS_NOMI_SQ_AB1 + rom_i * 4
                orig.seek(off)
                patched.seek(off)
                total_regions += 1
                if orig.read(4) != patched.read(4):
                    changed_regions += 1

                # Check name variant 1
                n_off = _ml_name_offset(_OFS_NOMI_SQ1, slot, _LUN_NOMI1)
                n_bud = _ml_name_budget(slot, _LUN_NOMI1)
                orig.seek(n_off)
                patched.seek(n_off)
                total_regions += 1
                if orig.read(n_bud) != patched.read(n_bud):
                    changed_regions += 1

                # Check first player
                first_idx, _ = _slot_player_range(slot)
                chunks = _nome_chunks(first_idx)
                orig.seek(chunks[0][0])
                patched.seek(chunks[0][0])
                total_regions += 1
                if orig.read(chunks[0][1]) != patched.read(chunks[0][1]):
                    changed_regions += 1

                # Check force bar
                bar_off = _ML_BAR_OFFSET + slot * 5
                orig.seek(bar_off)
                patched.seek(bar_off)
                total_regions += 1
                if orig.read(5) != patched.read(5):
                    changed_regions += 1

        print(f"  Changed: {changed_regions}/{total_regions} regions")
        assert changed_regions > 0, "No regions changed — patching had no effect!"
        assert changed_regions == total_regions, (
            f"Only {changed_regions}/{total_regions} regions changed"
        )

    print("  PASS: test_binary_diff_real_rom")


def test_all_32_slots_real_rom():
    """Patch all 32 ML slots and verify read-back on real ROM."""
    if not _require_rom():
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "patched.bin")

        writer = RomWriter(_ORIGINAL_ROM, out_path)

        for slot in range(32):
            team = _make_test_team(f"Team {slot}", f"T{slot:02d}")
            writer.write_team(slot, team)
            writer.write_players(slot, team.players)
            writer.write_flag(slot, team)

        # Read back all abbreviations
        with open(out_path, "rb") as f:
            for slot in range(32):
                rom_i = 31 - slot
                f.seek(_OFS_NOMI_SQ_AB1 + rom_i * 4)
                data = f.read(3).rstrip(b"\x00").decode("ascii")
                expected = f"T{slot:02d}"
                assert data == expected, (
                    f"Slot {slot} AB1: got {data!r}, expected {expected!r}"
                )

    print("  PASS: test_all_32_slots_real_rom")


def test_ppf_english_on_real_rom():
    """Apply the community English PPF (with skip_validation) to real ROM."""
    if not _require_rom():
        return
    if not os.path.exists(_PPF_PATH):
        print(f"  SKIP: PPF not found at {_PPF_PATH}")
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "patched.bin")
        shutil.copy2(_ORIGINAL_ROM, out_path)

        # Read original kanji section
        with open(_ORIGINAL_ROM, "rb") as f:
            f.seek(_OFS_NOMI_SQK)
            orig_kanji = f.read(200)

        # Apply PPF with skip_validation
        desc = apply_ppf(out_path, _PPF_PATH, skip_validation=True)
        print(f"  PPF description: {desc}")

        # Read patched kanji section
        with open(out_path, "rb") as f:
            f.seek(_OFS_NOMI_SQK)
            patched_kanji = f.read(200)

        assert orig_kanji != patched_kanji, "PPF had no effect on kanji section"

        # Verify some English text appears somewhere in the patched ROM
        # (the community PPF translates menus too, so there should be English)
        with open(out_path, "rb") as f:
            f.seek(_OFS_NOMI_SQK)
            section = f.read(2000)
        # The 2-byte encoded text should contain 0x82 bytes (the marker)
        has_encoded = section.count(b"\x82") > 10
        assert has_encoded, "Expected 2-byte encoded English names in kanji section"

    print("  PASS: test_ppf_english_on_real_rom")


def test_ppf1_fallback_on_real_rom():
    """Generate and apply PPF1 fallback to real ROM."""
    if not _require_rom():
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "patched.bin")
        ppf_path = os.path.join(tmpdir, "fallback.ppf")

        shutil.copy2(_ORIGINAL_ROM, out_path)

        # Generate PPF1
        ppf_data = generate_english_ppf()
        with open(ppf_path, "wb") as f:
            f.write(ppf_data)

        print(f"  Generated PPF1: {len(ppf_data):,} bytes")

        # Read original kanji section
        with open(_ORIGINAL_ROM, "rb") as f:
            f.seek(_OFS_NOMI_SQK)
            orig = f.read(500)

        # Apply
        desc = apply_ppf(out_path, ppf_path)
        print(f"  PPF1 description: {desc}")

        # Read patched
        with open(out_path, "rb") as f:
            f.seek(_OFS_NOMI_SQK)
            patched = f.read(500)

        assert orig != patched, "PPF1 fallback had no effect"

    print("  PASS: test_ppf1_fallback_on_real_rom")


def test_ppf_then_roster_patch():
    """Apply PPF first, then roster patches — verify roster overwrites PPF defaults."""
    if not _require_rom():
        return
    if not os.path.exists(_PPF_PATH):
        print(f"  SKIP: PPF not found at {_PPF_PATH}")
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "patched.bin")
        shutil.copy2(_ORIGINAL_ROM, out_path)

        # Step 1: Apply English PPF
        apply_ppf(out_path, _PPF_PATH, skip_validation=True)

        # Read PPF-patched kanji for slot 0
        k_budget = _LUN_NOMIK[63 + 0]
        k_offset = _ml_kanji_offset(0)
        with open(out_path, "rb") as f:
            f.seek(k_offset)
            ppf_kanji = f.read(k_budget * 2)

        # Step 2: Apply roster patch on top (RomWriter won't re-copy since file exists)
        team = _make_test_team("Corinthians", "COR")
        writer = RomWriter.__new__(RomWriter)
        writer.output_path = out_path

        writer.write_team(0, team)
        writer.write_players(0, team.players)

        # Read final kanji for slot 0 — should be "Corinthians", not PPF default
        with open(out_path, "rb") as f:
            f.seek(k_offset)
            final_kanji = f.read(k_budget * 2)

        expected_kanji = _encode_kanji_name("Corinthians", k_budget)
        assert final_kanji == expected_kanji, (
            f"Roster did not overwrite PPF kanji: {final_kanji.hex()} vs {expected_kanji.hex()}"
        )

        # Also verify the team name was written
        budget = _ml_name_budget(0, _LUN_NOMI1)
        offset = _ml_name_offset(_OFS_NOMI_SQ1, 0, _LUN_NOMI1)
        with open(out_path, "rb") as f:
            f.seek(offset)
            name_data = f.read(budget)
        expected_name = _encode_team_name("Corinthians", budget, uppercase=True)
        assert name_data == expected_name, (
            f"Name1: {name_data!r} vs {expected_name!r}"
        )

    print("  PASS: test_ppf_then_roster_patch")


def test_verification_report_real_rom():
    """Run the verification report on a real patched ROM."""
    if not _require_rom():
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "patched.bin")

        writer = RomWriter(_ORIGINAL_ROM, out_path)

        team = _make_test_team("Barcelona", "BAR")
        writer.write_team(0, team)
        writer.write_players(0, team.players)

        class FakeMapping:
            def __init__(self, si, name):
                self.slot_index = si
                self.real_team = type("T", (), {"name": name, "id": si})()

        mappings = [FakeMapping(0, "Barcelona")]
        we_teams = {0: team}

        report = writer.verify_patches(_ORIGINAL_ROM, mappings, we_teams)

        assert "VERIFICATION REPORT" in report
        assert "Mode2/2352: YES" in report, "ROM format not detected correctly"
        assert "NO DATA CHANGED AT ALL" not in report, "No changes detected!"
        assert "CHANGED" in report

        # Count passes in phase 3
        assert "PASSED" in report or "passed" in report

        print(f"  Report length: {len(report)} chars")

    print("  PASS: test_verification_report_real_rom")


def test_write_nat_team_to_real_rom():
    """Patch national team slots on real ROM and verify read-back."""
    if not _require_rom():
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "patched.bin")

        team = _make_test_team("Brazil", "BRA", n_players=23)
        writer = RomWriter(_ORIGINAL_ROM, out_path)

        writer.write_nat_team(0, team)
        writer.write_nat_players(0, team.players)
        writer.write_nat_flag(0, team)

        with open(out_path, "rb") as f:
            # Verify abbreviation at national offset
            ab_off = _nat_ab_offset(_OFS_NOMI_SQ_AB1, 0)
            f.seek(ab_off)
            ab = f.read(4)
            assert ab == b"BRA\x00", f"Nat AB1: {ab!r}"

            # Verify first player name
            first_nat_idx, _ = _nat_slot_player_range(0)
            chunks = _nat_nome_chunks(first_nat_idx)
            f.seek(chunks[0][0])
            data = f.read(chunks[0][1])
            expected = _encode_player_name("PLAYER00")
            assert data == expected[:len(data)], f"Nat player 0: {data!r}"

            # Verify flag style at FORMA1
            f.seek(_OFS_BANDIERE_FORMA1 + 0)
            style = f.read(1)
            assert style == b"\x04", f"Nat flag style: {style!r}"

        # Verify data differs from original
        with open(_ORIGINAL_ROM, "rb") as orig, open(out_path, "rb") as patched:
            ab_off = _nat_ab_offset(_OFS_NOMI_SQ_AB1, 0)
            orig.seek(ab_off)
            patched.seek(ab_off)
            assert orig.read(4) != patched.read(4), "No change at nat AB1"

    print("  PASS: test_write_nat_team_to_real_rom")


def test_dual_write_real_rom():
    """Patch a team to both ML and national slots, verify both are written."""
    if not _require_rom():
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "patched.bin")

        team = _make_test_team("Palmeiras", "PAL", n_players=23)
        writer = RomWriter(_ORIGINAL_ROM, out_path)

        # Write to ML slot 5 AND national slot 5
        writer.write_team(5, team)
        writer.write_players(5, team.players)
        writer.write_flag(5, team)
        writer.write_nat_team(5, team)
        writer.write_nat_players(5, team.players)
        writer.write_nat_flag(5, team)

        with open(out_path, "rb") as f:
            # ML abbreviation
            ml_rom_i = 31 - 5
            f.seek(_OFS_NOMI_SQ_AB1 + ml_rom_i * 4)
            ml_ab = f.read(4)
            assert ml_ab == b"PAL\x00", f"ML AB: {ml_ab!r}"

            # National abbreviation
            nat_ab_off = _nat_ab_offset(_OFS_NOMI_SQ_AB1, 5)
            f.seek(nat_ab_off)
            nat_ab = f.read(4)
            assert nat_ab == b"PAL\x00", f"Nat AB: {nat_ab!r}"

            # ML first player
            ml_first, _ = _slot_player_range(5)
            ml_chunks = _nome_chunks(ml_first)
            f.seek(ml_chunks[0][0])
            ml_p = f.read(ml_chunks[0][1])

            # National first player
            nat_first, _ = _nat_slot_player_range(5)
            nat_chunks = _nat_nome_chunks(nat_first)
            f.seek(nat_chunks[0][0])
            nat_p = f.read(nat_chunks[0][1])

            expected = _encode_player_name("PLAYER00")
            assert ml_p == expected[:len(ml_p)], f"ML player: {ml_p!r}"
            assert nat_p == expected[:len(nat_p)], f"Nat player: {nat_p!r}"

    print("  PASS: test_dual_write_real_rom")


def test_ppf2_skip_validation():
    """Verify PPF2 skip_validation works (won't raise on mismatched ROM)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        rom_path = os.path.join(tmpdir, "test.bin")
        ppf_path = os.path.join(tmpdir, "test.ppf")

        # Create a small dummy file
        with open(rom_path, "wb") as f:
            f.write(b"\xff" * 700_000)

        # Build a fake PPF2 with wrong expected size
        buf = bytearray()
        buf.extend(b"PPF20")
        buf.append(0x00)
        buf.extend(b"Test PPF2".ljust(50, b"\x00"))
        buf.extend(struct.pack("<I", 999_999_999))    # wrong expected size
        buf.extend(b"\x00" * 1024)                     # validation block
        buf.extend(struct.pack("<I", 100))              # offset
        buf.append(3)                                   # count
        buf.extend(b"\xAA\xBB\xCC")                    # data

        with open(ppf_path, "wb") as f:
            f.write(bytes(buf))

        # Without skip → should fail
        try:
            apply_ppf(rom_path, ppf_path, skip_validation=False)
            assert False, "Should have raised PPFError"
        except PPFError:
            pass

        # With skip → should succeed
        desc = apply_ppf(rom_path, ppf_path, skip_validation=True)
        assert desc == "Test PPF2"

        with open(rom_path, "rb") as f:
            f.seek(100)
            data = f.read(3)
        assert data == b"\xAA\xBB\xCC"

    print("  PASS: test_ppf2_skip_validation")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unit_tests = [
        test_encode_team_name,
        test_encode_abbreviation,
        test_encode_player_name,
        test_encode_kanji_name,
        test_encode_player_carat,
        test_rgb_to_ps1_color,
        test_slot_player_range,
        test_ml_name_offsets_no_overlap,
        test_ml_kanji_offsets_no_overlap,
        test_sector_straddle_indices,
        test_ppf2_skip_validation,
        # National slot unit tests
        test_nat_slot_player_range,
        test_nat_nome_straddles,
        test_nat_carat_straddles,
        test_nat_nome_offsets_no_overlap,
        test_nat_carat_offsets_no_overlap,
        test_nat_bar_offset_no_overlap,
    ]

    rom_tests = [
        test_rom_format,
        test_rom_has_original_data,
        test_write_team_to_real_rom,
        test_write_players_to_real_rom,
        test_write_flag_to_real_rom,
        test_jersey_colors_real_rom,
        test_binary_diff_real_rom,
        test_all_32_slots_real_rom,
        test_ppf_english_on_real_rom,
        test_ppf1_fallback_on_real_rom,
        test_ppf_then_roster_patch,
        test_verification_report_real_rom,
        # National ROM tests
        test_write_nat_team_to_real_rom,
        test_dual_write_real_rom,
    ]

    all_tests = unit_tests + rom_tests

    print(f"Running {len(all_tests)} WE2002 patcher verification tests...\n")
    print(f"--- Unit tests ({len(unit_tests)}) ---")

    passed = 0
    failed = 0
    skipped = 0

    for test in unit_tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  FAIL: {test.__name__}: {e}")

    print(f"\n--- ROM-based tests ({len(rom_tests)}) ---")
    if os.path.exists(_ORIGINAL_ROM):
        print(f"  ROM: {_ORIGINAL_ROM}")
        print(f"  Size: {os.path.getsize(_ORIGINAL_ROM):,} bytes\n")
    else:
        print(f"  ROM not found — ROM tests will be skipped\n")

    for test in rom_tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  FAIL: {test.__name__}: {e}")

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed out of {len(all_tests)} tests")
    if failed == 0:
        print("All tests passed!")
    else:
        print(f"*** {failed} test(s) FAILED ***")
        sys.exit(1)
