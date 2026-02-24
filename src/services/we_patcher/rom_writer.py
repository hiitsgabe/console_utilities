"""WE2002 ROM writer — patches player and team data into a copy of the ROM.

Offset constants and data structures sourced from:
  https://github.com/thyddralisk/WE2002-editor-2.0 (edDlg.cpp / giocatore.cpp)

The PS1 BIN file is Mode2/2352 bytes per sector.  All offsets are absolute raw
byte positions in that file (including sector sync/header/ECC overhead).  Data
regions span multiple sectors; the C++ editor re-seeks at known boundaries to
skip ECC bytes — we replicate that exact logic here.

Player attributes are encoded in a 12-byte str_carat field using the bit layout
defined in giocatore::decodifica().  Skills use a 3-bit offset-12 scheme
(storage value 0-7 = in-game values 12-19).

Team names are variable-length strings.  The per-entry byte budget is defined by
hardcoded lun_nomiN[] arrays (one per name variant).  Names are null-terminated
within their budget.  The ROM stores 95 entries: indices 0-62 are national/allstar
teams, indices 63-94 are the 32 ML teams.  Both ML and national names are patched.

Flags are parametric: 1 byte style (geometric pattern) + 16×2-byte colors.
Style is written identically at 5 FORMA offsets.  Colors are written in a
complex non-sequential order at COLORE offsets.
"""

import os
import struct
import shutil
import unicodedata
from typing import List, Tuple

from .models import WETeamRecord, WEPlayerRecord

# ---------------------------------------------------------------------------
# Absolute byte offsets in the Mode2/2352 BIN (from WE2002-editor-2.0 source)
# ---------------------------------------------------------------------------

# Master League player NAME sections (10 bytes per player)
_OFS_NOMI_GML  = 2_006_288   # ML player names, section 1: players 0–203
_OFS_NOMI_GML2 = 2_008_632   # ML player names, section 2: players 204–407 + first 8 of 408
_OFS_NOMI_GML3 = 2_010_984   # ML player names, section 3: last 2 of 408, then 409–461

# Master League player CHARACTERISTICS sections (12 bytes per player)
_OFS_CARAT_GML  = 2_204_112  # Characteristics section 1: players 0–147
_OFS_CARAT_GML1 = 2_206_200  # Characteristics section 2: last 4 of 148, then 149–318, + first 4 of 319
_OFS_CARAT_GML2 = 2_208_552  # Characteristics section 3: last 8 of 319, then 320–461

# Team NAME offsets — 6 name variants + lowercase + abbreviations + additional ML
_OFS_NOMI_SQ1   = 1_012_640   # Name variant 1
_OFS_NOMI_SQ1A  = 1_013_736   # SQ1 continuation after sector boundary (national team 40)
_OFS_NOMI_SQ2   = 1_881_968   # Name variant 2
_OFS_NOMI_SQ3   = 2_003_996   # Name variant 3
_OFS_NOMI_SQ4   = 2_830_160   # Name variant 4
_OFS_NOMI_SQ5   = 4_822_908   # Name variant 5
_OFS_NOMI_SQ5A  = 4_823_976   # SQ5 continuation after sector boundary
_OFS_NOMI_SQ6   = 5_651_448   # Name variant 6
_OFS_NOMI_SQ6A  = 5_651_880   # SQ6 sector boundary (ML team i==15)
_OFS_NOMI_SQ6B  = 5_652_364   # SQ6 national/allstar start
_OFS_NOMI_SQ_M  = 4_598_596   # Lowercase name
_OFS_NOMI_SQ_AB1 = 2_004_996  # Abbreviation variant 1 (fixed 4 bytes)
_OFS_NOMI_SQ_AB2 = 5_651_068  # Abbreviation variant 2 (fixed 4 bytes)
_OFS_NOMI_SQ_AB3 = 4_234_484  # Abbreviation variant 3 (fixed 4 bytes)

# Flag (bandiera) offsets
_OFS_BANDIERE_FORMA1  = 1_929_004  # Flag style byte × 5 copies
_OFS_BANDIERE_FORMA2  = 2_005_412
_OFS_BANDIERE_FORMA3  = 2_328_060
_OFS_BANDIERE_FORMA4  = 4_904_664
_OFS_BANDIERE_FORMA5  = 5_711_640
_OFS_BANDIERE_COLORE  = 12_549_518  # Flag colors (complex layout)
_OFS_BANDIERE_COLORE1 = 12_550_296
_OFS_BANDIERE_COLORE2 = 12_552_648
_OFS_BANDIERE_COLORE_SEN = 12_545_758

# Force bars
_OFS_BAR  = 2_328_184
_OFS_BAR1 = 2_328_504  # Continuation after sector boundary (national team 3)

# Jersey preview colors
_OFS_ANT_MAGLIE2 = 2_671_896  # ML jersey previews (32 teams × 64 bytes)

# National player NAME sections (10 bytes per player, 8 sections)
_OFS_NOMI_G  = 387_792
_OFS_NOMI_G2 = 390_456
_OFS_NOMI_G3 = 392_808
_OFS_NOMI_G4 = 395_160
_OFS_NOMI_G5 = 397_512
_OFS_NOMI_G6 = 399_864
_OFS_NOMI_G7 = 402_216
_OFS_NOMI_G8 = 404_568

# National player CHARACTERISTICS sections (12 bytes per player, 10 sections)
_OFS_CARAT_G  = 2_179_492
_OFS_CARAT_G1 = 2_180_328
_OFS_CARAT_G2 = 2_182_680
_OFS_CARAT_G3 = 2_185_032
_OFS_CARAT_G4 = 2_187_384
_OFS_CARAT_G5 = 2_189_736
_OFS_CARAT_G6 = 2_192_088
_OFS_CARAT_G7 = 2_194_440
_OFS_CARAT_G8 = 2_196_792
_OFS_CARAT_G9 = 2_199_144

# National jersey preview colors (64 bytes per team: maglia1 + maglia2)
_OFS_ANT_MAGLIE  = 2_667_256   # National + allstar jersey start
_OFS_ANT_MAGLIE1 = 2_669_544   # Continuation after sector boundary (team 30)

# Kanji (2-byte encoded) team name section
_OFS_NOMI_SQK  = 2_002_316   # Kanji names start (ML reverse, then nationals reverse)
_OFS_NOMI_SQK1 = 2_003_928   # Sector boundary continuation (national i=58 split)

# ---------------------------------------------------------------------------
# Sector boundary crossing points (from C++ switch-case indices)
# ---------------------------------------------------------------------------

_NOME_LAST_GML   = 203
_NOME_LAST_GML2  = 407
_NOME_STRADDLE   = 408
_CARAT_STRADDLE1 = 148
_CARAT_STRADDLE2 = 319

# National player name straddle points (national index, bytes_before, bytes_after)
# Index 820 is a clean break (0 before, 10 after = full seek to next section)
_NAT_NOME_STRADDLES = {
    0:    (8, 2, _OFS_NOMI_G + 312),  # special: seek +312 within same section
    205:  (6, 4, _OFS_NOMI_G2),
    410:  (4, 6, _OFS_NOMI_G3),
    615:  (2, 8, _OFS_NOMI_G4),
    820:  (0, 10, _OFS_NOMI_G5),       # clean break
    1024: (8, 2, _OFS_NOMI_G6),
    1229: (6, 4, _OFS_NOMI_G7),
    1434: (4, 6, _OFS_NOMI_G8),
}

# National characteristics straddle points (national index, bytes_before, bytes_after)
# Indices 215, 727, 1239 are clean breaks (0 before, 12 after)
_NAT_CARAT_STRADDLES = {
    44:   (4, 8, _OFS_CARAT_G1),
    215:  (0, 12, _OFS_CARAT_G2),      # clean break
    385:  (8, 4, _OFS_CARAT_G3),
    556:  (4, 8, _OFS_CARAT_G4),
    727:  (0, 12, _OFS_CARAT_G5),      # clean break
    897:  (8, 4, _OFS_CARAT_G6),
    1068: (4, 8, _OFS_CARAT_G7),
    1239: (0, 12, _OFS_CARAT_G8),      # clean break
    1409: (8, 4, _OFS_CARAT_G9),
}

# ---------------------------------------------------------------------------
# ROM constants
# ---------------------------------------------------------------------------

_SQUADRE_ML   = 32
_SQUADRE_NAZ  = 63   # National + allstar teams
_GIOCATORI_NC = 462
_PLAYERS_PER_NAT = 23
_NOME_SIZE    = 10
_CARAT_SIZE   = 12

_POS_MAP = {0: 0, 1: 1, 2: 3, 3: 6}

# ---------------------------------------------------------------------------
# Hardcoded name length tables from WE2002-editor-2.0 (edDlg.cpp lines 639-709)
#
# 95 entries each: indices 0-62 = national/allstar, indices 63-94 = 32 ML teams.
# The C++ writes ML teams in reverse: squad_ml[31-i] uses lun_nomiN[94-i].
# For our slot_index (0-31), the array index is: 63 + slot_index.
# But ROM write order is reversed: slot_index maps to lun_nomi index 94-rom_i
# where rom_i = 31-slot_index.  So: lun_index = 94 - (31 - slot_index) = 63 + slot_index.
# ---------------------------------------------------------------------------

_LUN_NOMI1 = [
    8,12,8,8,12,8,8,8,12,12,8,8,8,8,8,8,8,8,12,8,8,12,8,12,8,12,8,8,8,8,
    8,8,8,8,12,16,8,12,8,12,12,8,8,8,12,8,12,8,8,8,8,8,16,12,
    16,16,16,16,20,16,16,16,20,
    8,8,8,12,12,12,12,12,8,12,12,12,12,12,8,12,
    16,8,8,12,12,8,8,8,8,12,8,8,16,16,8,12,
]

_LUN_NOMI2 = [
    8,12,8,12,12,8,8,8,8,8,8,8,8,8,8,12,12,12,8,8,8,8,8,12,8,12,8,
    8,8,8,8,8,8,12,8,8,8,8,8,8,8,8,8,4,12,8,12,8,8,8,8,8,12,12,
    16,16,16,12,16,12,12,16,16,
    8,8,8,12,8,8,16,8,8,12,12,12,12,12,8,12,
    12,8,8,8,12,8,8,8,12,12,8,8,12,16,8,12,
]

_LUN_NOMI3 = [
    8,12,8,8,12,8,8,8,12,12,8,8,8,8,8,8,8,8,12,8,8,12,8,12,8,12,
    8,8,8,8,8,8,8,8,12,16,8,12,8,12,12,8,8,8,12,8,12,8,8,8,8,8,16,12,
    16,16,16,16,20,16,16,16,20,
    8,8,8,12,12,12,12,12,8,12,12,12,12,12,8,12,
    16,8,8,12,12,8,8,8,8,12,8,8,16,16,8,12,
]

_LUN_NOMI4 = [
    8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,
    8,8,8,8,8,8,8,8,8,8,8,8,8,4,8,8,8,8,4,4,4,8,8,8,8,8,16,12,12,
    12,12,12,16,8,8,8,8,8,8,12,8,8,8,8,8,8,8,8,8,12,8,4,8,8,8,8,
    8,8,12,8,4,8,12,8,8,
]

_LUN_NOMI5 = [
    8,12,8,12,8,8,8,8,8,4,8,4,8,8,8,8,8,8,8,8,8,8,8,12,8,8,8,4,
    8,4,8,8,8,8,8,8,8,8,8,8,8,8,8,4,8,8,8,8,8,8,8,4,12,8,
    12,16,12,12,12,12,12,12,12,
    8,8,8,8,8,8,12,8,8,8,8,12,12,8,8,8,
    12,8,4,8,12,8,8,8,8,12,8,4,12,12,8,8,
]

_LUN_NOMI6 = [
    8,12,8,12,8,8,8,8,8,4,8,4,8,8,8,8,8,8,8,8,8,8,8,12,8,8,8,
    4,8,4,8,8,8,8,8,8,8,8,8,8,8,8,8,4,8,8,8,8,8,8,8,4,
    12,8,12,16,16,12,12,12,12,16,16,8,8,8,8,8,8,12,8,8,8,8,12,12,8,8,
    8,12,8,4,8,12,8,8,8,8,12,8,4,12,12,8,8,
]

_LUN_NOMI_MIN = [
    8,12,8,12,8,8,8,8,8,4,8,4,8,8,8,8,8,8,8,8,8,8,8,12,8,8,8,4,8,4,8,
    8,8,8,8,8,8,8,8,8,8,8,8,4,8,8,8,8,8,8,8,4,12,8,12,16,
    16,12,12,12,12,16,16,8,8,8,8,8,8,12,8,8,8,8,12,12,8,
    8,8,12,8,4,8,12,8,8,8,8,12,8,4,12,12,8,8,
]


_LUN_NOMIK = [
    8,8,6,8,6,6,6,6,6,6,6,6,6,6,6,8,8,6,6,8,6,6,6,8,6,6,6,6,6,6,
    6,6,6,8,6,6,6,6,6,6,6,6,6,6,6,6,8,6,6,6,6,6,8,8,
    12,12,14,12,12,12,10,12,14,
    6,6,6,8,8,6,10,8,6,8,8,8,8,8,6,8,
    10,6,6,6,8,6,6,6,8,10,6,6,8,10,6,6,
]


def _ml_name_budget(slot_index: int, lun_table: list) -> int:
    """Return the byte budget for ML slot_index (0-31) from a lun_nomi table."""
    return lun_table[63 + slot_index]


# ---------------------------------------------------------------------------
# Encoding helpers
# ---------------------------------------------------------------------------

def _we_val(attr: int) -> int:
    """Map 1-9 WE attribute to 0-7 ROM storage value (offset-12 scheme)."""
    return min(7, max(0, attr - 1))


def _encode_player_carat(player: WEPlayerRecord) -> bytes:
    """Encode WEPlayerRecord attributes into the 12-byte str_carat format.

    Bit layout (from giocatore::decodifica() in WE2002-editor-2.0):
      Byte  0: posizione[2:0], stile_capelli_low4[7:4]
      Byte  1: stile_capelli_bit4[0], col_capelli[3:1], stile_barba[7:5]
      Byte  2: col_barba[3:1], altezza_low4[7:4]
      Byte  3: altezza_high2[1:0], (numero-1)[6:2], fuori_ruolo[7]
      Byte  4: col_pelle[1:0], corporatura[4:2], eta_low3[7:5]
      Byte  5: eta_high2[1:0], riflessi[4:2], forza_low2[7:6]
      Byte  6: forza_high1[0], resistenza[3:1], dribbling[6:4], velocita_low1[7]
      Byte  7: velocita_high2[1:0], accel[4:2], attacco[7:5]
      Byte  8: difesa[2:0], pot_tiro[5:3], prec_tiro_low2[7:6]
      Byte  9: prec_tiro_high1[0], passaggio[3:1], tecnica[6:4], testa_low1[7]
      Byte 10: testa_high2[1:0], salto[4:2], effetto[7:5]
      Byte 11: aggress[2:0], scarpe[5:3], piede[7:6]
    """
    a = player.attributes

    posizione      = _POS_MAP.get(player.position, 1)
    stile_capelli  = 0;  col_capelli = 0;  stile_barba = 0;  col_barba = 0
    col_pelle      = 0;  corporatura = 2
    altezza        = 178
    eta            = 25
    scarpe         = 0;  piede = 0;  fuori_ruolo = 0
    numero         = max(1, min(32, player.shirt_number or 1))

    attacco    = _we_val(a.offensive)
    difesa     = _we_val(a.defensive)
    forza      = _we_val(a.body_balance)
    resistenza = _we_val(a.stamina)
    velocita   = _we_val(a.speed)
    accel      = _we_val(a.acceleration)
    passaggio  = _we_val(a.pass_accuracy)
    pot_tiro   = _we_val(a.shoot_power)
    prec_tiro  = _we_val(a.shoot_accuracy)
    salto      = _we_val(a.jump_power)
    testa      = _we_val(a.heading)
    tecnica    = _we_val(a.technique)
    dribbling  = _we_val(a.dribble)
    effetto    = _we_val(a.curve)
    aggress    = _we_val(a.aggression)
    riflessi   = _we_val(a.defensive)

    h = altezza - 148
    e = eta - 15

    c = bytearray(12)
    c[0]  = (posizione & 0x07) | ((stile_capelli & 0x0F) << 4)
    c[1]  = ((stile_capelli >> 4) & 0x01) | ((col_capelli & 0x07) << 1) | ((stile_barba & 0x07) << 5)
    c[2]  = ((col_barba & 0x07) << 1) | ((h & 0x0F) << 4)
    c[3]  = ((h >> 4) & 0x03) | (((numero - 1) & 0x1F) << 2) | ((fuori_ruolo & 0x01) << 7)
    c[4]  = (col_pelle & 0x03) | ((corporatura & 0x07) << 2) | ((e & 0x07) << 5)
    c[5]  = ((e >> 3) & 0x03) | ((riflessi & 0x07) << 2) | ((forza & 0x03) << 6)
    c[6]  = ((forza >> 2) & 0x01) | ((resistenza & 0x07) << 1) | ((dribbling & 0x07) << 4) | ((velocita & 0x01) << 7)
    c[7]  = ((velocita >> 1) & 0x03) | ((accel & 0x07) << 2) | ((attacco & 0x07) << 5)
    c[8]  = (difesa & 0x07) | ((pot_tiro & 0x07) << 3) | ((prec_tiro & 0x03) << 6)
    c[9]  = ((prec_tiro >> 2) & 0x01) | ((passaggio & 0x07) << 1) | ((tecnica & 0x07) << 4) | ((testa & 0x01) << 7)
    c[10] = ((testa >> 1) & 0x03) | ((salto & 0x07) << 2) | ((effetto & 0x07) << 5)
    c[11] = (aggress & 0x07) | ((scarpe & 0x07) << 3) | ((piede & 0x03) << 6)
    return bytes(c)


def _to_ascii(text: str) -> str:
    """Convert Unicode text to plain ASCII by stripping diacritics.

    Handles accented Latin characters (é→e, ñ→n, ê→e, ü→u, etc.)
    and special ligatures/letters that don't decompose via NFKD.
    """
    _SPECIAL = {
        "ø": "o", "Ø": "O", "ß": "ss", "đ": "d", "Đ": "D",
        "ł": "l", "Ł": "L", "æ": "ae", "Æ": "AE",
        "œ": "oe", "Œ": "OE", "þ": "th", "Þ": "TH",
    }
    for src, dst in _SPECIAL.items():
        text = text.replace(src, dst)
    normalized = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in normalized if not unicodedata.combining(c))
    return stripped.encode("ascii", errors="ignore").decode("ascii")


def _encode_player_name(name: str) -> bytes:
    """Encode a name string to 10-byte ROM format: ASCII uppercase, null-padded.

    The game only displays the first 8 characters; bytes 9-10 must be null.
    """
    ascii_bytes = _to_ascii(name.upper()).encode("ascii")[:8]
    return ascii_bytes.ljust(_NOME_SIZE, b"\x00")


def _encode_team_name(name: str, budget: int, uppercase: bool = True) -> bytes:
    """Encode a team name to fit within the ROM byte budget, null-terminated."""
    text = name.upper() if uppercase else name
    ascii_bytes = _to_ascii(text).encode("ascii")
    max_len = max(0, budget - 1)
    return ascii_bytes[:max_len].ljust(budget, b"\x00")


def _encode_abbreviation(code: str) -> bytes:
    """Encode a 3-letter abbreviation to fixed 4-byte ROM format."""
    ascii_bytes = _to_ascii(code.upper()).encode("ascii")[:3]
    return ascii_bytes.ljust(4, b"\x00")


def _encode_kanji_name(name: str, budget: int) -> bytes:
    """Encode a team name to the 2-byte Kanji format for the SQK section.

    budget is lun_nomik[idx] (character count); output is budget * 2 bytes.
    Name is titlecased (first char upper, rest lower) per C++ editor convention.
    """
    # Titlecase: first char uppercase, rest lowercase
    if len(name) > 1:
        text = name[0].upper() + name[1:].lower()
    elif name:
        text = name.upper()
    else:
        text = ""

    max_chars = budget - 1  # last position is null terminator
    text = text[:max_chars]

    buf = bytearray(budget * 2)
    for i, ch in enumerate(text):
        c = ord(ch)
        if 65 <= c <= 90:       # A-Z
            buf[i * 2] = 0x82
            buf[i * 2 + 1] = c + 31
        elif 97 <= c <= 122:    # a-z
            buf[i * 2] = 0x82
            buf[i * 2 + 1] = c + 32
        elif 48 <= c <= 57:     # 0-9
            buf[i * 2] = 0x82
            buf[i * 2 + 1] = c + 31
        elif c == 46:           # period '.'
            buf[i * 2] = 0x81
            buf[i * 2 + 1] = 0x42
        else:                   # space / default
            buf[i * 2] = 0x82
            buf[i * 2 + 1] = 0x80

    # Null terminator
    term = len(text)
    buf[term * 2] = 0x00
    buf[term * 2 + 1] = 0x00
    return bytes(buf)


def _ml_kanji_offset(slot_index: int) -> int:
    """Calculate the absolute file offset for an ML team's kanji name.

    ML kanji names are written at OFS_NOMI_SQK in reverse order:
    rom_i=0 is squad_ml[31], rom_i=31 is squad_ml[0].
    """
    rom_i = 31 - slot_index
    off = _OFS_NOMI_SQK
    for j in range(rom_i):
        off += _LUN_NOMIK[94 - j] * 2
    return off


def _nat_kanji_base() -> int:
    """Starting offset for national kanji names (after all 32 ML teams)."""
    base = _OFS_NOMI_SQK
    for j in range(32):
        base += _LUN_NOMIK[94 - j] * 2
    return base


_NAT_KANJI_BASE = _nat_kanji_base()

# National kanji sector boundary: writing in reverse (62, 61, ..., 0),
# nat_index=4 straddles the sector 851/852 boundary.
# Sector 851 data area ends at byte 2_003_623; sector 852 data starts at SQK1.
_NAT_KANJI_STRADDLE_IDX = 4
_NAT_KANJI_SECTOR_END   = 2_003_623  # last byte of sector 851 data area


def _nat_kanji_chunks(nat_index: int) -> List[Tuple[int, int]]:
    """Return [(offset, nbytes)] chunks for a national team's kanji name.

    National kanji names are written in reverse order (62, 61, ..., 0) after
    the 32 ML kanji names.  A sector boundary splits nat_index=4: 4 bytes
    before the boundary, then 8 bytes at _OFS_NOMI_SQK1.
    """
    budget = _LUN_NOMIK[nat_index]
    total_bytes = budget * 2

    if nat_index > _NAT_KANJI_STRADDLE_IDX:
        # Before the boundary in write order — simple linear offset
        off = _NAT_KANJI_BASE
        for rev_idx in range(62, nat_index, -1):
            off += _LUN_NOMIK[rev_idx] * 2
        return [(off, total_bytes)]

    elif nat_index == _NAT_KANJI_STRADDLE_IDX:
        # Straddle: compute linear offset, split across sector boundary
        off = _NAT_KANJI_BASE
        for rev_idx in range(62, nat_index, -1):
            off += _LUN_NOMIK[rev_idx] * 2
        before = _NAT_KANJI_SECTOR_END - off + 1  # bytes that fit in sector 851
        after = total_bytes - before
        return [(off, before), (_OFS_NOMI_SQK1, after)]

    else:
        # After the boundary — recalculate from _OFS_NOMI_SQK1 + straddle tail
        straddle_off = _NAT_KANJI_BASE
        for rev_idx in range(62, _NAT_KANJI_STRADDLE_IDX, -1):
            straddle_off += _LUN_NOMIK[rev_idx] * 2
        straddle_before = _NAT_KANJI_SECTOR_END - straddle_off + 1
        straddle_tail = _LUN_NOMIK[_NAT_KANJI_STRADDLE_IDX] * 2 - straddle_before

        off = _OFS_NOMI_SQK1 + straddle_tail
        for rev_idx in range(_NAT_KANJI_STRADDLE_IDX - 1, nat_index, -1):
            off += _LUN_NOMIK[rev_idx] * 2
        return [(off, total_bytes)]


def _rgb_to_ps1_color(r: int, g: int, b: int) -> int:
    """Convert RGB888 to PS1 15-bit BGR555 (unsigned short).

    PS1 format: 0bbbbbgggggrrrrr (bit 15 = STP/semi-transparency, set to 0).
    """
    r5 = (r >> 3) & 0x1F
    g5 = (g >> 3) & 0x1F
    b5 = (b >> 3) & 0x1F
    return r5 | (g5 << 5) | (b5 << 10)


def _build_flag_data(team: "WETeamRecord") -> Tuple[int, bytes]:
    """Build (style_byte, color_data_32bytes) for a team's flag.

    If team.flag_style / team.flag_palette are set, uses those directly.
    Otherwise falls back to style 4 (vertical halves) with 8×primary +
    8×secondary from ESPN colors.
    """
    if team.flag_style is not None and team.flag_palette and len(team.flag_palette) == 16:
        style = team.flag_style
        palette = [_rgb_to_ps1_color(*c) for c in team.flag_palette]
    else:
        style = 4  # vertical halves: left = primary, right = secondary
        primary = _rgb_to_ps1_color(*team.kit_home)
        secondary = _rgb_to_ps1_color(*team.kit_away)
        palette = [primary] * 8 + [secondary] * 8
    color_data = struct.pack("<" + "H" * 16, *palette)
    return style, color_data


# ---------------------------------------------------------------------------
# Sector-boundary-aware offset calculation
# ---------------------------------------------------------------------------

def _nome_chunks(player_idx: int) -> List[Tuple[int, int]]:
    """Return [(file_offset, byte_count)] to write the 10-byte player name."""
    if player_idx <= _NOME_LAST_GML:
        return [(_OFS_NOMI_GML + player_idx * _NOME_SIZE, _NOME_SIZE)]

    if player_idx <= _NOME_LAST_GML2:
        offset = _OFS_NOMI_GML2 + (player_idx - (_NOME_LAST_GML + 1)) * _NOME_SIZE
        return [(offset, _NOME_SIZE)]

    if player_idx == _NOME_STRADDLE:
        off1 = _OFS_NOMI_GML2 + (player_idx - (_NOME_LAST_GML + 1)) * _NOME_SIZE
        return [(off1, 8), (_OFS_NOMI_GML3, 2)]

    off = _OFS_NOMI_GML3 + 2 + (player_idx - (_NOME_STRADDLE + 1)) * _NOME_SIZE
    return [(off, _NOME_SIZE)]


def _carat_chunks(player_idx: int) -> List[Tuple[int, int]]:
    """Return [(file_offset, byte_count)] to write the 12-byte characteristics."""
    if player_idx < _CARAT_STRADDLE1:
        return [(_OFS_CARAT_GML + player_idx * _CARAT_SIZE, _CARAT_SIZE)]

    if player_idx == _CARAT_STRADDLE1:
        off1 = _OFS_CARAT_GML + _CARAT_STRADDLE1 * _CARAT_SIZE
        return [(off1, 8), (_OFS_CARAT_GML1, 4)]

    if player_idx < _CARAT_STRADDLE2:
        off = _OFS_CARAT_GML1 + 4 + (player_idx - (_CARAT_STRADDLE1 + 1)) * _CARAT_SIZE
        return [(off, _CARAT_SIZE)]

    if player_idx == _CARAT_STRADDLE2:
        off1 = _OFS_CARAT_GML1 + 4 + (player_idx - (_CARAT_STRADDLE1 + 1)) * _CARAT_SIZE
        return [(off1, 4), (_OFS_CARAT_GML2, 8)]

    off = _OFS_CARAT_GML2 + 8 + (player_idx - (_CARAT_STRADDLE2 + 1)) * _CARAT_SIZE
    return [(off, _CARAT_SIZE)]


# ---------------------------------------------------------------------------
# National player sector-boundary-aware offset calculation
# ---------------------------------------------------------------------------

# Contiguous sections for national player names.  Each tuple is
# (first_nat_idx_inclusive, first_nat_idx_exclusive, base_offset).
# Straddle indices are the LAST element of their section; their linear
# offset is computed normally, then _nat_nome_chunks splits the write.
_NAT_NOME_SECTIONS = [
    (0,    206,  _OFS_NOMI_G),              # index 0 straddles (8+2 at G+312)
    (206,  411,  _OFS_NOMI_G2 + 4),         # after straddle 205 tail
    (411,  616,  _OFS_NOMI_G3 + 6),         # after straddle 410 tail
    (616,  821,  _OFS_NOMI_G4 + 8),         # after straddle 615 tail
    (821,  1025, _OFS_NOMI_G5 + 10),        # after straddle 820 (full 10)
    (1025, 1230, _OFS_NOMI_G6 + 2),         # after straddle 1024 tail
    (1230, 1435, _OFS_NOMI_G7 + 4),         # after straddle 1229 tail
    (1435, 1449, _OFS_NOMI_G8 + 6),         # after straddle 1434 tail
]

# Special: index 0 has an internal 312-byte gap (8 bytes at G, then skip to G+312
# for the remaining 2 bytes).  Indices 1+ within section 0 start after that tail.
_NAT_NOME_SEC0_GAP = 312 + 2  # bytes from _OFS_NOMI_G to first byte of index 1


def _nat_nome_chunks(nat_idx: int) -> List[Tuple[int, int]]:
    """Return [(file_offset, byte_count)] to write a 10-byte national player name.

    nat_idx is the national player index (0-based, relative to GIOCATORI_NC).
    """
    if nat_idx in _NAT_NOME_STRADDLES:
        before, after, next_off = _NAT_NOME_STRADDLES[nat_idx]
        if before == 0:
            return [(next_off, _NOME_SIZE)]
        before_off = _nat_nome_linear_offset(nat_idx)
        return [(before_off, before), (next_off, after)]
    return [(_nat_nome_linear_offset(nat_idx), _NOME_SIZE)]


def _nat_nome_linear_offset(nat_idx: int) -> int:
    """Compute the file offset for a national player name."""
    if nat_idx == 0:
        return _OFS_NOMI_G
    # Section 0 indices 1-205: after the index-0 straddle gap
    if 1 <= nat_idx < 206:
        return _OFS_NOMI_G + _NAT_NOME_SEC0_GAP + (nat_idx - 1) * _NOME_SIZE
    for start, end, base in _NAT_NOME_SECTIONS[1:]:
        if start <= nat_idx < end:
            return base + (nat_idx - start) * _NOME_SIZE
    return _NAT_NOME_SECTIONS[-1][2] + (nat_idx - _NAT_NOME_SECTIONS[-1][0]) * _NOME_SIZE


# Contiguous sections for national player characteristics.
_NAT_CARAT_SECTIONS = [
    (0,    45,   _OFS_CARAT_G),             # indices 0..44 (straddle 44 at end)
    (45,   216,  _OFS_CARAT_G1 + 8),        # after straddle 44 tail
    (216,  386,  _OFS_CARAT_G2 + 12),       # after clean break 215
    (386,  557,  _OFS_CARAT_G3 + 4),        # after straddle 385 tail
    (557,  728,  _OFS_CARAT_G4 + 8),        # after straddle 556 tail
    (728,  898,  _OFS_CARAT_G5 + 12),       # after clean break 727
    (898,  1069, _OFS_CARAT_G6 + 4),        # after straddle 897 tail
    (1069, 1240, _OFS_CARAT_G7 + 8),        # after straddle 1068 tail
    (1240, 1410, _OFS_CARAT_G8 + 12),       # after clean break 1239
    (1410, 1449, _OFS_CARAT_G9 + 4),        # after straddle 1409 tail
]


def _nat_carat_chunks(nat_idx: int) -> List[Tuple[int, int]]:
    """Return [(file_offset, byte_count)] to write 12-byte national player characteristics."""
    if nat_idx in _NAT_CARAT_STRADDLES:
        before, after, next_off = _NAT_CARAT_STRADDLES[nat_idx]
        if before == 0:
            return [(next_off, _CARAT_SIZE)]
        before_off = _nat_carat_linear_offset(nat_idx)
        return [(before_off, before), (next_off, after)]
    return [(_nat_carat_linear_offset(nat_idx), _CARAT_SIZE)]


def _nat_carat_linear_offset(nat_idx: int) -> int:
    """Compute the file offset for national player characteristics."""
    for start, end, base in _NAT_CARAT_SECTIONS:
        if start <= nat_idx < end:
            return base + (nat_idx - start) * _CARAT_SIZE
    return _NAT_CARAT_SECTIONS[-1][2] + (nat_idx - _NAT_CARAT_SECTIONS[-1][0]) * _CARAT_SIZE


def _nat_slot_player_range(nat_index: int) -> Tuple[int, int]:
    """Return (first_nat_player_index, player_count) for a national team slot.

    nat_index: 0-62 (national + allstar team index).
    Returns indices relative to GIOCATORI_NC (national player base).
    """
    return nat_index * _PLAYERS_PER_NAT, _PLAYERS_PER_NAT


# ---------------------------------------------------------------------------
# Team-to-player index mapping
# ---------------------------------------------------------------------------

def _slot_player_range(slot_index: int) -> Tuple[int, int]:
    """Return (first_global_player_index, player_count) for a ML slot.

    WE2002 stores squad_ml[31] first in the ROM, squad_ml[0] last.  Player
    indices 0-461 correspond to teams in that order.  Distribution assumption:
      - Slots 18-31 (ROM positions 0-13):  15 players each  → indices 0-209
      - Slots  0-17 (ROM positions 14-31): 14 players each  → indices 210-461
    """
    if slot_index >= 18:
        rom_pos = 31 - slot_index
        return rom_pos * 15, 15
    else:
        rom_pos = 31 - slot_index
        first   = 14 * 15 + (rom_pos - 14) * 14
        return first, 14


def _write_chunks(f, data: bytes, chunks: List[Tuple[int, int]]) -> None:
    """Write data bytes in pieces according to (offset, size) chunk list."""
    pos = 0
    for offset, size in chunks:
        f.seek(offset)
        f.write(data[pos: pos + size])
        pos += size


# ---------------------------------------------------------------------------
# Team name offset calculation
#
# The C++ writes names sequentially: 32 ML teams (reversed) then 63 national.
# We only patch ML teams.  For a given name variant offset base, the ML team
# at slot_index is written at:
#   base + sum(lun_nomiN[94 - j] for j in range(rom_position))
# where rom_position = the team's write index (0 = squad_ml[31], 31 = squad_ml[0]).
# ---------------------------------------------------------------------------

def _ml_name_offset(base_offset: int, slot_index: int, lun_table: list) -> int:
    """Calculate the absolute file offset for an ML team name.

    ML teams are written in reverse ROM order: rom_i=0 is squad_ml[31],
    rom_i=31 is squad_ml[0].  slot_index maps to rom_i = 31 - slot_index.
    """
    rom_i = 31 - slot_index
    off = base_offset
    for j in range(rom_i):
        # j-th ML team written uses lun_table index: 94 - j
        off += lun_table[94 - j]
    return off


# ---------------------------------------------------------------------------
# National team name offset calculation
#
# The C++ writes team names sequentially: 32 ML teams (reversed) then 63 national.
# For nationals, the array index is simply nat_index (0-62).
# The offset is: base + sum of all 32 ML budgets + sum of nat budgets 0..nat_index-1.
# Sector boundaries within national ranges must be handled per variant.
# ---------------------------------------------------------------------------

def _nat_name_offset(base_offset: int, nat_index: int, lun_table: list) -> int:
    """Calculate the absolute file offset for a national team name.

    The write order is: 32 ML teams (reversed) then 63 national teams sequential.
    National team at nat_index uses lun_table[nat_index].
    """
    off = base_offset
    # Skip all 32 ML teams (written first in reverse)
    for j in range(32):
        off += lun_table[94 - j]
    # Skip preceding national teams
    for j in range(nat_index):
        off += lun_table[j]
    return off


def _nat_name_offset_sq1(nat_index: int) -> int:
    """SQ1 has a sector boundary at national team 40 → OFS_NOMI_SQ1A."""
    off = _nat_name_offset(_OFS_NOMI_SQ1, nat_index, _LUN_NOMI1)
    if nat_index >= 40:
        # Recalculate from SQ1A base for teams at and after the boundary
        off = _OFS_NOMI_SQ1A
        for j in range(40, nat_index):
            off += _LUN_NOMI1[j]
    return off


def _nat_name_offset_sq5(nat_index: int) -> int:
    """SQ5 has a sector boundary → OFS_NOMI_SQ5A in the national range."""
    # Compute the sequential offset; the C++ seeks to SQ5A at a certain point.
    # SQ5A is at 4_823_976.  We compute the transition point by summing budgets.
    off = _nat_name_offset(_OFS_NOMI_SQ5, nat_index, _LUN_NOMI5)
    # Find where SQ5A kicks in: sum ML + nationals until we cross SQ5A
    running = _OFS_NOMI_SQ5
    for j in range(32):
        running += _LUN_NOMI5[94 - j]
    for j in range(63):
        if running >= _OFS_NOMI_SQ5A and j <= nat_index:
            # Boundary crossed at national team j
            off = _OFS_NOMI_SQ5A
            for k in range(j, nat_index):
                off += _LUN_NOMI5[k]
            return off
        running += _LUN_NOMI5[j]
    return off


def _nat_name_offset_sq6(nat_index: int) -> int:
    """SQ6 has a sector boundary at OFS_NOMI_SQ6B for nationals."""
    # Nationals start writing at SQ6B (after ML's SQ6/SQ6A region)
    off = _OFS_NOMI_SQ6B
    for j in range(nat_index):
        off += _LUN_NOMI6[j]
    return off


# National abbreviation offset: after 32 ML abbreviations (written in reverse)
def _nat_ab_offset(base_offset: int, nat_index: int) -> int:
    """National abbreviation offset: 32 ML (reversed) then 63 national sequential."""
    return base_offset + 32 * 4 + nat_index * 4


# ---------------------------------------------------------------------------
# National force bar offset calculation
# ---------------------------------------------------------------------------

def _nat_bar_offset(nat_index: int) -> Tuple[List[Tuple[int, int]], None]:
    """Return [(offset, nbytes)] chunks for a national team's 5 force bar bytes.

    National teams 0-62 are written first at OFS_BAR, with a sector boundary
    at team 3 (1 byte before boundary, then seek to OFS_BAR1 for 4 bytes).
    """
    if nat_index < 3:
        off = _OFS_BAR + nat_index * 5
        return [(off, 5)]
    elif nat_index == 3:
        # Straddle: 1 byte (bar_attacco) then seek to OFS_BAR1 for 4 bytes
        return [(_OFS_BAR + 15, 1), (_OFS_BAR1, 4)]
    else:
        # Teams 4-62: contiguous after OFS_BAR1 + 4
        off = _OFS_BAR1 + 4 + (nat_index - 4) * 5
        return [(off, 5)]


# National jersey preview offset calculation
def _nat_jersey_offset(nat_index: int) -> int:
    """Return the file offset for a national team's jersey preview (64 bytes).

    Sector boundary at team 30: seeks to OFS_ANT_MAGLIE1.
    """
    if nat_index < 30:
        return _OFS_ANT_MAGLIE + nat_index * 64
    else:
        # Teams 30-62 continue from OFS_ANT_MAGLIE1
        return _OFS_ANT_MAGLIE1 + (nat_index - 30) * 64


# ---------------------------------------------------------------------------
# National flag color offset computation
#
# The C++ OnWriteCD() writes national colors (i=0..55) then ML colors.
# We trace the file pointer to compute each national team's color offset.
# ---------------------------------------------------------------------------

def _compute_nat_color_offsets() -> dict:
    """Compute {nat_index: [(offset, nbytes)]} for national team flag colors.

    Traces the C++ OnWriteCD national color write loop (lines 5989-6015):
      - i=13: straddle (26 bytes + seek to COLORE1 + 6 bytes)
      - i=36, 39, 47: skipped
      - i=1, 40, 52: seek +32 (skip old slot) then write 32
      - default: write 32
    """
    result = {}
    pos = _OFS_BANDIERE_COLORE

    for i in range(56):
        if i == 13:
            result[i] = [(pos, 26), (_OFS_BANDIERE_COLORE1, 6)]
            pos += 26
            pos = _OFS_BANDIERE_COLORE1 + 6
        elif i in (36, 39, 47):
            pass  # skipped entirely — no write, no advance
        elif i in (1, 40, 52):
            pos += 32  # skip old slot
            result[i] = [(pos, 32)]
            pos += 32
        else:
            result[i] = [(pos, 32)]
            pos += 32

    # Teams 56-62 are allstar teams — they are in the ML color region
    # (handled by _compute_ml_color_offsets).  We don't write them here.

    return result


_NAT_COLOR_OFFSETS = _compute_nat_color_offsets()


# ---------------------------------------------------------------------------
# Flag color write order
#
# The C++ OnWriteCD() writes ML flag colors in this exact non-sequential order,
# with relative seeks interspersed.  We replicate the absolute offsets by
# tracking file position as the C++ code does.
# ---------------------------------------------------------------------------

def _build_ml_color_write_plan() -> List[Tuple[int, int]]:
    """Build (ml_squad_index, relative_position) pairs for color writes.

    Returns a list of (squad_ml_index, absolute_offset_from_COLORE) entries.
    We simulate the C++ file pointer to compute absolute positions.
    """
    # The C++ first writes 56 national team colors, then does relative seeks
    # for ML teams.  We need to figure out the file position after all the
    # national writes, then trace the ML writes.
    #
    # Rather than simulate the full national write (which has its own skips),
    # we compute the ML color offsets by tracking the file pointer from known
    # absolute positions.  The ML color section starts after national teams.
    #
    # From the C++ (OnWriteCD lines 5987-6055):
    #   After writing 56 national colors with skips, the file pointer is at
    #   some position.  Then:
    #     Seek(64, current)      → skip 2 empty slots
    #     Write ml[0..4]         → 5 × 32 bytes
    #     Write ml[10]           → 32 bytes
    #     Write ml[7..9]         → 3 × 32 bytes
    #     Write ml[11..12]       → 2 × 32 bytes
    #     Write ml[15]           → 32 bytes
    #     Write ml[18..21]       → 4 × 32 bytes
    #     Seek(32, current)      → skip 1 slot
    #     Write ml[14]           → 32 bytes
    #     Write ml[24]           → 32 bytes
    #     Write ml[25]           → 32 bytes
    #     Write ml[26] partial   → 26 bytes (straddles to COLORE2)
    #     --- Seek to COLORE2 ---
    #     Write ml[26] tail      → 6 bytes
    #     Write ml[27]           → 32 bytes
    #     Write ml[16..17]       → 2 × 32 bytes
    #     Seek(64, current)      → skip 2 slots
    #     Write ml[13]           → 32 bytes
    #     Seek(288, current)     → skip 9 slots
    #     Write nazall[39]       → 32 bytes (national team, skip)
    #     Seek(64, current)      → skip 2 slots
    #     Write nazall[47]       → 32 bytes (national team, skip)
    #     Write ml[6]            → 32 bytes
    #     Write ml[23]           → 32 bytes
    #     Write ml[28..31]       → 4 × 32 bytes
    #
    # We don't need absolute offsets for every position — instead we compute
    # them relative to OFS_BANDIERE_COLORE2 for the second segment,
    # and use a tracking approach for the first segment.
    #
    # Actually, the simplest correct approach: we know the file position after
    # writing nationals.  Let's compute it.
    #
    # National color write (lines 5989-6015):
    #   56 teams with special cases:
    #   - i=13: write 26, seek to COLORE1, write 6 (straddle)
    #   - i=36,39,47: skip (no write)
    #   - i=1,40,52: seek +32 before write (skip old team slot)
    #   - default: write 32
    #
    # After COLORE1 seek at i=13, file position is OFS_BANDIERE_COLORE1 + 6.
    # Then normal 32-byte writes continue for i=14..55 (minus skips).
    # Actually this is getting complex — let me just hardcode the ML offsets
    # by doing the math once.

    # I'll trace the file pointer through the entire national+ML write sequence.
    # Start at OFS_BANDIERE_COLORE.
    return []  # placeholder — actual computation below


# Instead of the complex tracing, compute the ML color offsets directly.
# The ML color region starts at a known position that we can derive.

def _compute_ml_color_offsets() -> dict:
    """Compute {ml_index: (offset, size)} for each ML team's color data.

    For teams that straddle a sector boundary (ml[26]), returns two entries
    that must be written separately.

    Returns dict mapping ml_index to list of (offset, nbytes) chunks.
    """
    # Trace the C++ file pointer through OnWriteCD lines 5989-6055.
    pos = _OFS_BANDIERE_COLORE

    # --- National teams (i=0..55) ---
    for i in range(56):
        if i == 13:
            # Write 26 bytes, then seek to COLORE1, write 6 bytes
            pos += 26
            pos = _OFS_BANDIERE_COLORE1 + 6  # after writing the 6-byte tail
        elif i in (36, 39, 47):
            pass  # skipped entirely
        elif i in (1, 40, 52):
            pos += 32  # skip an old slot
            pos += 32  # then write 32
        else:
            pos += 32

    # Now pos is after all national color writes.

    result = {}

    # Seek(64, current) — skip 2 empty slots
    pos += 64

    # ml[0..4]: 5 × 32
    for idx in range(5):
        result[idx] = [(pos, 32)]
        pos += 32

    # ml[10]: 32
    result[10] = [(pos, 32)]
    pos += 32

    # ml[7..9]: 3 × 32
    for idx in range(7, 10):
        result[idx] = [(pos, 32)]
        pos += 32

    # ml[11..12]: 2 × 32
    for idx in range(11, 13):
        result[idx] = [(pos, 32)]
        pos += 32

    # ml[15]: 32
    result[15] = [(pos, 32)]
    pos += 32

    # ml[18..21]: 4 × 32
    for idx in range(18, 22):
        result[idx] = [(pos, 32)]
        pos += 32

    # Seek(32, current) — skip 1 slot
    pos += 32

    # ml[14]: 32
    result[14] = [(pos, 32)]
    pos += 32

    # ml[24]: 32
    result[24] = [(pos, 32)]
    pos += 32

    # ml[25]: 32
    result[25] = [(pos, 32)]
    pos += 32

    # ml[26]: straddle — 26 bytes here, then 6 bytes at COLORE2
    result[26] = [(pos, 26), (_OFS_BANDIERE_COLORE2, 6)]
    pos += 26
    pos = _OFS_BANDIERE_COLORE2 + 6  # after writing tail at COLORE2

    # ml[27]: 32
    result[27] = [(pos, 32)]
    pos += 32

    # ml[16..17]: 2 × 32
    for idx in range(16, 18):
        result[idx] = [(pos, 32)]
        pos += 32

    # Seek(64, current) — skip 2 slots
    pos += 64

    # ml[13]: 32
    result[13] = [(pos, 32)]
    pos += 32

    # Seek(288, current) — skip 9 slots
    pos += 288

    # nazall[39]: 32 (national team — we skip it)
    pos += 32

    # Seek(64, current) — skip 2 slots
    pos += 64

    # nazall[47]: 32 (national team — we skip it)
    pos += 32

    # ml[6]: 32
    result[6] = [(pos, 32)]
    pos += 32

    # ml[23]: 32
    result[23] = [(pos, 32)]
    pos += 32

    # ml[28..31]: 4 × 32
    for idx in range(28, 32):
        result[idx] = [(pos, 32)]
        pos += 32

    # ml[22] is missing from the C++ write sequence — it may share a slot
    # with one of the national teams or be at a position we haven't found.
    # Leave it unpatched to avoid corruption.

    return result


# Pre-compute once at import time
_ML_COLOR_OFFSETS = _compute_ml_color_offsets()

# ---------------------------------------------------------------------------
# Force bar offset calculation
#
# Force bars: 5 bytes per team.  National teams (0-62) first at OFS_BAR,
# with a sector boundary at national team index 3 (seeks to OFS_BAR1 after
# writing bar_attacco, before bar_difesa).  Then ML teams (0-31) sequentially.
# ML bars follow directly after the last national team bar.
# ---------------------------------------------------------------------------

def _compute_ml_bar_offset() -> int:
    """Compute the file offset where ML force bars begin.

    National teams: 63 teams × 5 bytes each, with sector boundary at team 3.
    The boundary is after writing team 3's bar_attacco (1 byte into team 3's
    5-byte block).  So:
      - Teams 0-2: 3 × 5 = 15 bytes at OFS_BAR
      - Team 3: 1 byte (bar_attacco) at OFS_BAR + 15
      - Then seek to OFS_BAR1, write remaining 4 bytes of team 3
      - Teams 4-62: 59 × 5 = 295 bytes continuing from OFS_BAR1 + 4
    Total national bytes after OFS_BAR1: 4 + 59×5 = 299
    ML starts at: OFS_BAR1 + 299
    """
    return _OFS_BAR1 + 4 + 59 * 5


_ML_BAR_OFFSET = _compute_ml_bar_offset()

# ---------------------------------------------------------------------------
# Public writer class
# ---------------------------------------------------------------------------

_DUMMY_NAME  = b"PLAYER\x00\x00\x00\x00"
_DUMMY_CARAT = bytes(12)


class RomWriter:
    def __init__(self, rom_path: str, output_path: str):
        """Copy the ROM to output_path for patching. The original is never modified."""
        if os.path.exists(rom_path):
            shutil.copy2(rom_path, output_path)
        self.output_path = output_path

    def write_team(self, slot_index: int, team: WETeamRecord):
        """Write team names, abbreviations, and force bars for a ROM slot.

        Team names are variable-length: each variant has a fixed byte budget
        from the lun_nomiN[] tables.  Names are null-terminated within their
        budget.  All 6 name variants + lowercase + 3 abbreviations are written.
        """
        if not os.path.exists(self.output_path):
            return
        if slot_index < 0 or slot_index >= _SQUADRE_ML:
            return

        with open(self.output_path, "r+b") as f:
            self._write_team_names(f, slot_index, team)
            self._write_kanji_name(f, slot_index, team)
            self._write_abbreviations(f, slot_index, team)
            self._write_force_bars(f, slot_index, team)
            self._write_jersey_colors(f, slot_index, team)

    def _write_team_names(self, f, slot_index: int, team: WETeamRecord):
        """Write all 6 name variants + lowercase for an ML team slot.

        The ROM has 6 name variants (nomi[0..5]) and a lowercase name (nome_m).
        Each has its own offset base and length table.  We write the team name
        to all of them — uppercase for variants 1-6, mixed case for lowercase.
        """
        name = team.name

        # Name variant 1 — uses lun_nomi1, offset base OFS_NOMI_SQ1
        # Special case: SQ1 has a sector boundary at national team i==40
        # (OFS_NOMI_SQ1A), but that's in the national section (after ML).
        # ML teams are written first (indices 0-31), so no boundary for ML.
        budget = _ml_name_budget(slot_index, _LUN_NOMI1)
        offset = _ml_name_offset(_OFS_NOMI_SQ1, slot_index, _LUN_NOMI1)
        f.seek(offset)
        f.write(_encode_team_name(name, budget, uppercase=True))

        # Name variant 2
        budget = _ml_name_budget(slot_index, _LUN_NOMI2)
        offset = _ml_name_offset(_OFS_NOMI_SQ2, slot_index, _LUN_NOMI2)
        f.seek(offset)
        f.write(_encode_team_name(name, budget, uppercase=True))

        # Name variant 3
        budget = _ml_name_budget(slot_index, _LUN_NOMI3)
        offset = _ml_name_offset(_OFS_NOMI_SQ3, slot_index, _LUN_NOMI3)
        f.seek(offset)
        f.write(_encode_team_name(name, budget, uppercase=True))

        # Name variant 4
        budget = _ml_name_budget(slot_index, _LUN_NOMI4)
        offset = _ml_name_offset(_OFS_NOMI_SQ4, slot_index, _LUN_NOMI4)
        f.seek(offset)
        f.write(_encode_team_name(name, budget, uppercase=True))

        # Name variant 5
        budget = _ml_name_budget(slot_index, _LUN_NOMI5)
        offset = _ml_name_offset(_OFS_NOMI_SQ5, slot_index, _LUN_NOMI5)
        f.seek(offset)
        f.write(_encode_team_name(name, budget, uppercase=True))

        # Name variant 6 — has sector boundary at ML i==15 (OFS_NOMI_SQ6A)
        budget = _ml_name_budget(slot_index, _LUN_NOMI6)
        offset = self._sq6_ml_offset(slot_index)
        f.seek(offset)
        f.write(_encode_team_name(name, budget, uppercase=True))

        # Lowercase name
        budget = _ml_name_budget(slot_index, _LUN_NOMI_MIN)
        offset = _ml_name_offset(_OFS_NOMI_SQ_M, slot_index, _LUN_NOMI_MIN)
        f.seek(offset)
        f.write(_encode_team_name(name, budget, uppercase=False))

    def _write_kanji_name(self, f, slot_index: int, team: WETeamRecord):
        """Write the 2-byte encoded (kanji) name for an ML team.

        This overwrites the kanji section (OFS_NOMI_SQK) which the built-in
        PPF sets to default English names.  After this, the kanji section
        shows the actual API team name instead of the original ML team name.
        """
        budget = _LUN_NOMIK[63 + slot_index]
        offset = _ml_kanji_offset(slot_index)
        f.seek(offset)
        f.write(_encode_kanji_name(team.name, budget))

    def _sq6_ml_offset(self, slot_index: int) -> int:
        """Compute offset for name variant 6 (SQ6), which has a sector boundary.

        The C++ seeks to OFS_NOMI_SQ6A when i==15 (rom write index 15,
        which is squad_ml[16] = slot_index 16).  ML teams before rom_i=15
        are at OFS_NOMI_SQ6, teams at and after rom_i=15 are at OFS_NOMI_SQ6A.
        """
        rom_i = 31 - slot_index
        if rom_i < 15:
            # Before the boundary
            off = _OFS_NOMI_SQ6
            for j in range(rom_i):
                off += _LUN_NOMI6[94 - j]
            return off
        else:
            # At or after the boundary — base is OFS_NOMI_SQ6A
            off = _OFS_NOMI_SQ6A
            for j in range(15, rom_i):
                off += _LUN_NOMI6[94 - j]
            return off

    def _write_abbreviations(self, f, slot_index: int, team: WETeamRecord):
        """Write 3 abbreviation variants (fixed 4 bytes each)."""
        code = team.short_name or team.name[:3]
        abbrev = _encode_abbreviation(code)

        # Abbreviations are written: 32 ML (reversed) then 63 national, sequential.
        rom_i = 31 - slot_index

        # AB1
        off = _OFS_NOMI_SQ_AB1 + rom_i * 4
        f.seek(off)
        f.write(abbrev)

        # AB2
        off = _OFS_NOMI_SQ_AB2 + rom_i * 4
        f.seek(off)
        f.write(abbrev)

        # AB3
        off = _OFS_NOMI_SQ_AB3 + rom_i * 4
        f.seek(off)
        f.write(abbrev)

    def _write_force_bars(self, f, slot_index: int, team: WETeamRecord):
        """Write 5 force bar bytes for an ML team.

        Force bars are written: 63 national first, then 32 ML sequential
        (squad_ml[0] first, not reversed).  Each team = 5 bytes:
        attack, defense, power, speed, technique.
        """
        # Compute overall team ratings from roster
        att, defe, power, speed, tech = self._compute_force_bars(team)

        off = _ML_BAR_OFFSET + slot_index * 5
        f.seek(off)
        f.write(bytes([att, defe, power, speed, tech]))

    def _compute_force_bars(self, team: WETeamRecord) -> Tuple[int, int, int, int, int]:
        """Derive 5 force bar values (each 1-8) from team roster attributes."""
        if not team.players:
            return (4, 4, 4, 4, 4)

        # Average across all players for each bar category
        n = len(team.players)
        tot_att = sum(p.attributes.offensive for p in team.players)
        tot_def = sum(p.attributes.defensive for p in team.players)
        tot_pow = sum(p.attributes.body_balance + p.attributes.shoot_power
                      for p in team.players)
        tot_spd = sum(p.attributes.speed + p.attributes.acceleration
                      for p in team.players)
        tot_tec = sum(p.attributes.technique + p.attributes.pass_accuracy
                      for p in team.players)

        def bar(total, divisor):
            avg = total / divisor
            return max(1, min(8, round(avg)))

        return (
            bar(tot_att, n),
            bar(tot_def, n),
            bar(tot_pow, n * 2),
            bar(tot_spd, n * 2),
            bar(tot_tec, n * 2),
        )

    def _write_jersey_colors(self, f, slot_index: int, team: WETeamRecord):
        """Write jersey CLUT (maglia1 + maglia2) for an ML team.

        The CLUT controls BOTH the menu preview AND the in-game 3D
        jerseys (the PS1 GPU palette-swaps the same texture).
        Indices 0-1 are reserved, 2-9 = shirt, 10-15 = shorts.
        """
        if team.jersey_data and len(team.jersey_data) == 64:
            off = _OFS_ANT_MAGLIE2 + slot_index * 64
            f.seek(off)
            f.write(team.jersey_data)
            return

        primary = _rgb_to_ps1_color(*team.kit_home)
        secondary = _rgb_to_ps1_color(*team.kit_away)

        home_palette = [0, 0] + [primary] * 8 + [secondary] * 6
        away_palette = [0, 0] + [secondary] * 8 + [primary] * 6

        maglia1 = struct.pack("<" + "H" * 16, *home_palette)
        maglia2 = struct.pack("<" + "H" * 16, *away_palette)

        off = _OFS_ANT_MAGLIE2 + slot_index * 64
        f.seek(off)
        f.write(maglia1)
        f.write(maglia2)

    def write_players(self, slot_index: int, players: List[WEPlayerRecord]):
        """Write player names + characteristics for a team slot."""
        if not os.path.exists(self.output_path):
            return

        first_idx, count = _slot_player_range(slot_index)

        with open(self.output_path, "r+b") as f:
            for i in range(count):
                global_idx = first_idx + i

                if i < len(players):
                    p = players[i]
                    name_bytes  = _encode_player_name(p.last_name)
                    carat_bytes = _encode_player_carat(p)
                else:
                    name_bytes  = _DUMMY_NAME
                    carat_bytes = _DUMMY_CARAT

                _write_chunks(f, name_bytes,  _nome_chunks(global_idx))
                _write_chunks(f, carat_bytes, _carat_chunks(global_idx))

    def write_flag(self, slot_index: int, team: WETeamRecord):
        """Write team flag (style byte + 16 colors) for an ML team slot.

        Style: 1 byte written identically at 5 FORMA offsets.  All 95 entries
        (63 national + 32 ML) are sequential at each FORMA offset.

        Colors: 16 × unsigned short (32 bytes) written at the pre-computed
        offset from _ML_COLOR_OFFSETS.  The color layout is non-sequential
        in the ROM due to historical PS1 CD sector constraints.

        If team.flag_style and team.flag_palette are set (from flag_analyzer),
        uses those directly.  Otherwise falls back to style 0 (solid) with
        the 3 kit colors distributed as 8x primary + 5x secondary + 3x tertiary.
        """
        if not os.path.exists(self.output_path):
            return
        if slot_index < 0 or slot_index >= _SQUADRE_ML:
            return

        style, color_data = _build_flag_data(team)

        with open(self.output_path, "r+b") as f:
            # Write style byte at all 5 FORMA offsets
            for forma_base in [
                _OFS_BANDIERE_FORMA1, _OFS_BANDIERE_FORMA2,
                _OFS_BANDIERE_FORMA3, _OFS_BANDIERE_FORMA4,
                _OFS_BANDIERE_FORMA5,
            ]:
                # 63 national teams first, then 32 ML teams sequential
                off = forma_base + _SQUADRE_NAZ + slot_index
                f.seek(off)
                f.write(bytes([style]))

            # Write color data at the pre-computed offset
            if slot_index in _ML_COLOR_OFFSETS:
                chunks = _ML_COLOR_OFFSETS[slot_index]
                _write_chunks(f, color_data, chunks)

    # ------------------------------------------------------------------
    # National team writers
    # ------------------------------------------------------------------

    def write_nat_team(self, nat_index: int, team: WETeamRecord):
        """Write team names, abbreviations, force bars, and jerseys for a national slot."""
        if not os.path.exists(self.output_path):
            return
        if nat_index < 0 or nat_index >= _SQUADRE_NAZ:
            return

        with open(self.output_path, "r+b") as f:
            self._write_nat_team_names(f, nat_index, team)
            self._write_nat_kanji_name(f, nat_index, team)
            self._write_nat_abbreviations(f, nat_index, team)
            self._write_nat_force_bars(f, nat_index, team)
            self._write_nat_jersey_colors(f, nat_index, team)

    def _write_nat_team_names(self, f, nat_index: int, team: WETeamRecord):
        """Write all name variants for a national team slot."""
        name = team.name

        # Name variant 1 (SQ1) — sector boundary at national team 40
        budget = _LUN_NOMI1[nat_index]
        offset = _nat_name_offset_sq1(nat_index)
        f.seek(offset)
        f.write(_encode_team_name(name, budget, uppercase=True))

        # Name variant 2 (SQ2) — no national boundary
        budget = _LUN_NOMI2[nat_index]
        offset = _nat_name_offset(_OFS_NOMI_SQ2, nat_index, _LUN_NOMI2)
        f.seek(offset)
        f.write(_encode_team_name(name, budget, uppercase=True))

        # Name variant 3 (SQ3) — no national boundary
        budget = _LUN_NOMI3[nat_index]
        offset = _nat_name_offset(_OFS_NOMI_SQ3, nat_index, _LUN_NOMI3)
        f.seek(offset)
        f.write(_encode_team_name(name, budget, uppercase=True))

        # Name variant 4 (SQ4) — no national boundary
        budget = _LUN_NOMI4[nat_index]
        offset = _nat_name_offset(_OFS_NOMI_SQ4, nat_index, _LUN_NOMI4)
        f.seek(offset)
        f.write(_encode_team_name(name, budget, uppercase=True))

        # Name variant 5 (SQ5) — has sector boundary in national range
        budget = _LUN_NOMI5[nat_index]
        offset = _nat_name_offset_sq5(nat_index)
        f.seek(offset)
        f.write(_encode_team_name(name, budget, uppercase=True))

        # Name variant 6 (SQ6) — nationals start at SQ6B
        budget = _LUN_NOMI6[nat_index]
        offset = _nat_name_offset_sq6(nat_index)
        f.seek(offset)
        f.write(_encode_team_name(name, budget, uppercase=True))

        # Lowercase name
        budget = _LUN_NOMI_MIN[nat_index]
        offset = _nat_name_offset(_OFS_NOMI_SQ_M, nat_index, _LUN_NOMI_MIN)
        f.seek(offset)
        f.write(_encode_team_name(name, budget, uppercase=False))

    def _write_nat_kanji_name(self, f, nat_index: int, team: WETeamRecord):
        """Write the 2-byte encoded (kanji) name for a national team.

        National kanji names are stored after ML kanji names in reverse order
        (62, 61, ..., 0) with a sector boundary straddling nat_index=4.
        """
        budget = _LUN_NOMIK[nat_index]
        encoded = _encode_kanji_name(team.name, budget)
        chunks = _nat_kanji_chunks(nat_index)
        _write_chunks(f, encoded, chunks)

    def _write_nat_abbreviations(self, f, nat_index: int, team: WETeamRecord):
        """Write 3 abbreviation variants for a national team slot."""
        code = team.short_name or team.name[:3]
        abbrev = _encode_abbreviation(code)

        f.seek(_nat_ab_offset(_OFS_NOMI_SQ_AB1, nat_index))
        f.write(abbrev)
        f.seek(_nat_ab_offset(_OFS_NOMI_SQ_AB2, nat_index))
        f.write(abbrev)
        f.seek(_nat_ab_offset(_OFS_NOMI_SQ_AB3, nat_index))
        f.write(abbrev)

    def _write_nat_force_bars(self, f, nat_index: int, team: WETeamRecord):
        """Write 5 force bar bytes for a national team slot."""
        att, defe, power, speed, tech = self._compute_force_bars(team)
        bar_data = bytes([att, defe, power, speed, tech])
        chunks = _nat_bar_offset(nat_index)
        _write_chunks(f, bar_data, chunks)

    def _write_nat_jersey_colors(self, f, nat_index: int, team: WETeamRecord):
        """Write jersey CLUT (maglia1 + maglia2) for a national team slot.

        The CLUT controls BOTH the menu preview AND the in-game 3D
        jerseys.  Indices 0-1 reserved, 2-9 = shirt, 10-15 = shorts.
        """
        if team.jersey_data and len(team.jersey_data) == 64:
            off = _nat_jersey_offset(nat_index)
            f.seek(off)
            f.write(team.jersey_data)
            return

        primary = _rgb_to_ps1_color(*team.kit_home)
        secondary = _rgb_to_ps1_color(*team.kit_away)

        home_palette = [0, 0] + [primary] * 8 + [secondary] * 6
        away_palette = [0, 0] + [secondary] * 8 + [primary] * 6

        maglia1 = struct.pack("<" + "H" * 16, *home_palette)
        maglia2 = struct.pack("<" + "H" * 16, *away_palette)

        off = _nat_jersey_offset(nat_index)
        f.seek(off)
        f.write(maglia1)
        f.write(maglia2)

    def write_nat_players(self, nat_index: int, players: List[WEPlayerRecord]):
        """Write player names + characteristics for a national team slot.

        Writes up to 23 players; pads with dummies if fewer are provided.
        """
        if not os.path.exists(self.output_path):
            return
        if nat_index < 0 or nat_index >= _SQUADRE_NAZ:
            return

        first_nat_idx, count = _nat_slot_player_range(nat_index)

        with open(self.output_path, "r+b") as f:
            for i in range(count):
                nat_player_idx = first_nat_idx + i

                if i < len(players):
                    p = players[i]
                    name_bytes = _encode_player_name(p.last_name)
                    carat_bytes = _encode_player_carat(p)
                else:
                    name_bytes = _DUMMY_NAME
                    carat_bytes = _DUMMY_CARAT

                _write_chunks(f, name_bytes, _nat_nome_chunks(nat_player_idx))
                _write_chunks(f, carat_bytes, _nat_carat_chunks(nat_player_idx))

    def write_nat_flag(self, nat_index: int, team: WETeamRecord):
        """Write flag (style byte + 16 colors) for a national team slot."""
        if not os.path.exists(self.output_path):
            return
        if nat_index < 0 or nat_index >= _SQUADRE_NAZ:
            return

        style, color_data = _build_flag_data(team)

        with open(self.output_path, "r+b") as f:
            # Write style byte at all 5 FORMA offsets
            for forma_base in [
                _OFS_BANDIERE_FORMA1, _OFS_BANDIERE_FORMA2,
                _OFS_BANDIERE_FORMA3, _OFS_BANDIERE_FORMA4,
                _OFS_BANDIERE_FORMA5,
            ]:
                off = forma_base + nat_index
                f.seek(off)
                f.write(bytes([style]))

            # Write color data at the pre-computed national offset
            if nat_index in _NAT_COLOR_OFFSETS:
                chunks = _NAT_COLOR_OFFSETS[nat_index]
                _write_chunks(f, color_data, chunks)

    def verify_patches(self, original_path: str, slot_mapping, we_teams) -> str:
        """Compare original vs patched ROM AND read-back the output to confirm.

        Three-phase check:
          1. ROM format validation (Mode2/2352 sync bytes)
          2. Binary diff: original vs patched at every written offset
          3. Read-back: re-read what we wrote and confirm it matches intent

        The report is written to an error.log file next to the output ROM.

        Args:
            original_path: Path to the unmodified source ROM.
            slot_mapping: List of SlotMapping used during patching.
            we_teams: Dict mapping slot_index → WETeamRecord that was written.

        Returns:
            Multi-line human-readable verification report string.
        """
        if not os.path.exists(original_path) or not os.path.exists(self.output_path):
            return "ERROR: Cannot verify — original or patched file missing."

        lines = []
        lines.append("=" * 60)
        lines.append("WE2002 PATCH VERIFICATION REPORT")
        lines.append("=" * 60)

        orig_size = os.path.getsize(original_path)
        patch_size = os.path.getsize(self.output_path)
        lines.append(f"Original ROM: {original_path}")
        lines.append(f"  Size: {orig_size:,} bytes")
        lines.append(f"Patched ROM:  {self.output_path}")
        lines.append(f"  Size: {patch_size:,} bytes")
        if orig_size != patch_size:
            lines.append(f"  *** SIZE MISMATCH — copy may have failed ***")
        lines.append("")

        # --- Phase 1: ROM format check ---
        lines.append("--- PHASE 1: ROM FORMAT CHECK ---")
        with open(original_path, "rb") as f:
            sync = f.read(12)
            is_mode2 = (sync == b"\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\x00")
            lines.append(f"Sector 0 sync: {sync.hex()}")
            lines.append(f"Mode2/2352: {'YES' if is_mode2 else 'NO  *** WRONG FORMAT ***'}")
            if not is_mode2:
                lines.append("!!! ROM is NOT a raw Mode2/2352 BIN dump.")
                lines.append("!!! All offsets are calibrated for Mode2/2352.")
                lines.append("!!! This is likely why the patch had no effect.")

            f.seek(2352)
            sync2 = f.read(12)
            sector1_ok = (sync2 == b"\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\x00")
            lines.append(f"Sector 1 sync: {sync2.hex()} ({'OK' if sector1_ok else 'MISMATCH'})")

            # Probe known data offsets for sanity
            f.seek(_OFS_NOMI_SQ_AB1)
            sample = f.read(32)
            has_ascii = any(0x20 <= b <= 0x7E for b in sample)
            lines.append(f"Probe @AB1 ({_OFS_NOMI_SQ_AB1}): {sample[:16].hex()}")
            lines.append(f"  Printable ASCII present: {'YES' if has_ascii else 'NO (wrong offset?)'}")

            f.seek(_OFS_NOMI_GML)
            sample2 = f.read(40)
            has_names = any(0x41 <= b <= 0x5A for b in sample2)  # uppercase A-Z
            lines.append(f"Probe @GML ({_OFS_NOMI_GML}): {sample2[:20].hex()}")
            lines.append(f"  Uppercase letters present: {'YES' if has_names else 'NO (wrong offset?)'}")
        lines.append("")

        # --- Phase 2: Binary diff original vs patched ---
        lines.append("--- PHASE 2: ORIGINAL vs PATCHED DIFF ---")
        total_changed = 0
        total_checked = 0

        with open(original_path, "rb") as orig, open(self.output_path, "rb") as patched:
            for mapping in slot_mapping:
                si = mapping.slot_index
                team_name = mapping.real_team.name if hasattr(mapping, "real_team") else f"slot {si}"
                we_team = we_teams.get(si)
                lines.append(f"\n  Slot {si}: {team_name}")

                checks = self._get_check_points(si)
                for label, offset, size in checks:
                    orig.seek(offset)
                    orig_data = orig.read(size)
                    patched.seek(offset)
                    patch_data = patched.read(size)
                    changed = orig_data != patch_data
                    total_checked += 1
                    if changed:
                        total_changed += 1
                    # Show readable representation
                    orig_repr = self._format_bytes(orig_data)
                    patch_repr = self._format_bytes(patch_data)
                    lines.append(f"    {label} @{offset}: {orig_repr} -> {patch_repr} {'CHANGED' if changed else 'SAME'}")

        lines.append("")
        lines.append(f"  Diff totals: {total_changed}/{total_checked} regions changed")
        lines.append("")

        # --- Phase 3: Read-back verification on output file ---
        lines.append("--- PHASE 3: OUTPUT READ-BACK CHECK ---")
        readback_ok = 0
        readback_fail = 0

        with open(self.output_path, "rb") as f:
            for mapping in slot_mapping:
                si = mapping.slot_index
                we_team = we_teams.get(si)
                if not we_team:
                    continue

                team_name = mapping.real_team.name if hasattr(mapping, "real_team") else f"slot {si}"

                # Verify abbreviation matches what we intended to write
                code = we_team.short_name or we_team.name[:3]
                expected_ab = _encode_abbreviation(code)
                rom_i = 31 - si
                ab_off = _OFS_NOMI_SQ_AB1 + rom_i * 4
                f.seek(ab_off)
                actual_ab = f.read(4)
                if actual_ab == expected_ab:
                    readback_ok += 1
                else:
                    readback_fail += 1
                    lines.append(f"  FAIL slot {si} AB1: expected {expected_ab} got {actual_ab}")

                # Verify name variant 1
                budget = _ml_name_budget(si, _LUN_NOMI1)
                expected_name = _encode_team_name(we_team.name, budget, uppercase=True)
                n1_off = _ml_name_offset(_OFS_NOMI_SQ1, si, _LUN_NOMI1)
                f.seek(n1_off)
                actual_name = f.read(budget)
                if actual_name == expected_name:
                    readback_ok += 1
                else:
                    readback_fail += 1
                    lines.append(f"  FAIL slot {si} Name1: expected {expected_name} got {actual_name}")

                # Verify first player name
                if we_team.players:
                    expected_pn = _encode_player_name(we_team.players[0].last_name)
                    first_idx, _ = _slot_player_range(si)
                    pn_chunks = _nome_chunks(first_idx)
                    f.seek(pn_chunks[0][0])
                    actual_pn = f.read(pn_chunks[0][1])
                    # For straddle cases, only check the first chunk
                    if actual_pn == expected_pn[:len(actual_pn)]:
                        readback_ok += 1
                    else:
                        readback_fail += 1
                        lines.append(f"  FAIL slot {si} Player0: expected {expected_pn[:len(actual_pn)]} got {actual_pn}")

        if readback_fail == 0:
            lines.append(f"  All {readback_ok} read-back checks PASSED")
        else:
            lines.append(f"  {readback_fail} FAILED, {readback_ok} passed")
        lines.append("")

        # --- Summary ---
        lines.append("--- SUMMARY ---")
        lines.append(f"ROM format: {'Mode2/2352 OK' if is_mode2 else 'WRONG FORMAT'}")
        lines.append(f"Diff: {total_changed}/{total_checked} regions changed")
        lines.append(f"Read-back: {readback_ok} OK, {readback_fail} FAIL")
        if total_changed == 0:
            lines.append("")
            lines.append("*** NO DATA CHANGED AT ALL ***")
            lines.append("Possible causes:")
            lines.append("  1. ROM is not Mode2/2352 BIN (check format above)")
            lines.append("  2. Emulator loading original file, not patched copy")
            lines.append("  3. shutil.copy2 failed (check disk space)")
        lines.append("=" * 60)

        report = "\n".join(lines)

        # Write to error.log next to the output ROM
        log_path = os.path.join(os.path.dirname(self.output_path), "error.log")
        try:
            with open(log_path, "w") as f:
                f.write(report)
        except Exception:
            pass

        return report

    @staticmethod
    def _get_check_points(slot_index):
        """Return list of (label, offset, size) to check for a given slot."""
        rom_i = 31 - slot_index
        checks = []

        # Abbreviation AB1
        checks.append(("AB1", _OFS_NOMI_SQ_AB1 + rom_i * 4, 4))

        # Name variant 1
        n1_off = _ml_name_offset(_OFS_NOMI_SQ1, slot_index, _LUN_NOMI1)
        n1_budget = _ml_name_budget(slot_index, _LUN_NOMI1)
        checks.append(("Name1", n1_off, n1_budget))

        # First player name
        first_idx, _ = _slot_player_range(slot_index)
        pn_chunks = _nome_chunks(first_idx)
        checks.append(("Player0", pn_chunks[0][0], pn_chunks[0][1]))

        # First player characteristics
        pc_chunks = _carat_chunks(first_idx)
        checks.append(("Carat0", pc_chunks[0][0], pc_chunks[0][1]))

        # Force bar
        checks.append(("ForceBar", _ML_BAR_OFFSET + slot_index * 5, 5))

        # Flag style
        checks.append(("FlagStyle", _OFS_BANDIERE_FORMA1 + _SQUADRE_NAZ + slot_index, 1))

        return checks

    @staticmethod
    def _format_bytes(data: bytes) -> str:
        """Format bytes for display — show as ASCII if printable, else hex."""
        try:
            text = data.rstrip(b"\x00").decode("ascii")
            if text and all(0x20 <= ord(c) <= 0x7E for c in text):
                return repr(data)
        except (UnicodeDecodeError, ValueError):
            pass
        if len(data) <= 5:
            return str(list(data))
        return data.hex()[:24] + "..."

    def finalize(self):
        """Post-processing after all patches are written.

        EDC/ECC regeneration is not implemented — most emulators (DuckStation,
        ePSXe, PCSX-R, Mednafen) skip ECC verification and run patched ROMs
        as-is.  Hardware play may require a separate edcre pass.
        """
        pass
