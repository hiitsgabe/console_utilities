"""ISS SNES ROM writer — patches player and team data into a copy of the ROM.

Offset constants sourced from:
  https://github.com/rodmguerra/issparser (ISS Studio Java editor)
  https://github.com/EstebanFuentealba/web-iss-studio (web port)

ISS (International Superstar Soccer, 1994, SNES) uses a standard .sfc ROM.
27 teams × 15 players = 405 players total.

Player names use ISS custom character encoding (not ASCII).
Player data (abilities, number, hair, special) is a 6-byte interleaved block.
Kit colors use SNES BGR555 (15-bit, little-endian).
"""

import os
import shutil
import struct
import unicodedata
from typing import List, Tuple

from .models import (
    ISSTeamRecord,
    ISSPlayerRecord,
    TEAM_ENUM_ORDER,
    TEAM_NAME_ORDER,
    PLAYERS_PER_TEAM,
    TOTAL_TEAMS,
)

# ── Absolute byte offsets (headerless .sfc) ─────────────────────────────────

# Player names: 8 bytes per player, stored in TEAM_NAME_ORDER
_OFS_PLAYER_NAMES = 0x3B62C

# Player data: 6 bytes per player, stored in TEAM_ENUM_ORDER
# Byte layout within each 6-byte record:
#   [0] speed data   [1] shooting data   [2] shooting+technique
#   [3] shirt number [4] stamina data    [5] hair_style | special_flag
_OFS_PLAYER_DATA = 0x387EC

# Uniform / kit colors
# Outfield kits: 32 bytes per team (shirt 6B + shorts 6B + socks 4B + 16B padding)
# Range 1 (19 teams): Germany, Italy, Holland, Spain, England, France, Sweden,
#   Ireland, Belgium, Romania, Bulgaria, Argentina, Brazil, Colombia, Mexico,
#   U.S.A., Nigeria, Cameroon, Super Star
# Range 2 (8 teams): Russia, Scotland, S.Korea, Wales, Norway, Switz, Denmark, Austria
_OFS_KIT1_RANGE1 = 0x2EA3B    # 1st kit, range 1 (19 teams, 32 bytes each)
_OFS_KIT1_RANGE2 = 0x2F0EB    # 1st kit, range 2 (8 teams, 32 bytes each)
_OFS_KIT2_RANGE1 = 0x2ECBB    # 2nd kit, range 1 (19 teams, 32 bytes each)
_OFS_KIT2_RANGE2 = 0x2F1EB    # 2nd kit, range 2 (8 teams, 32 bytes each)
_OFS_GK_RANGE1 = 0x2EF37      # GK kit, range 1 (18 teams, 24 bytes each)
_OFS_GK_RANGE2 = 0x2F2E7      # GK kit, range 2 (8 teams, 24 bytes each)

# Hair/skin colors sit 12 bytes before the kit data in the same blocks
_OFS_HAIR_SKIN1_RANGE1 = 0x2EA2F   # = 0x2EA3B - 12
_OFS_HAIR_SKIN1_RANGE2 = 0x2F0DF   # = 0x2F0EB - 12
_OFS_HAIR_SKIN2_RANGE1 = 0x2ECAF   # = 0x2ECBB - 12
_OFS_HAIR_SKIN2_RANGE2 = 0x2F1DF   # = 0x2F1EB - 12

# Flag colors: 10 bytes per team (4 colors × 2 bytes + 2 padding)
_OFS_FLAG_COLORS_RANGE1 = 0x2DD91  # 18 teams
_OFS_FLAG_COLORS_RANGE2 = 0x2DE4F  # 9 teams

# Predominant color byte
_OFS_PREDOMINANT_COLOR = 0x8DB2    # 1 byte per team, enum order

# Team name text: pointer table in TEAM_ENUM_ORDER, P40000 format
_OFS_TEAM_NAME_TEXT_PTRS = 0x39DAE  # 2 bytes per team, 27 teams
_MAX_NAME_TEXT_ADDR = 0x44478  # must not overwrite extra entries at 0x44478+

# ── Kit color team orderings ────────────────────────────────────────────────
_KIT_RANGE1_TEAMS = [
    "Germany", "Italy", "Holland", "Spain", "England", "France", "Sweden",
    "Ireland", "Belgium", "Romania", "Bulgaria", "Argentina", "Brazil",
    "Colombia", "Mexico", "U.S.A.", "Nigeria", "Cameroon", "Super Star",
]

_KIT_RANGE2_TEAMS = [
    "Russia", "Scotland", "S.Korea", "Wales", "Norway", "Switz",
    "Denmark", "Austria",
]

# GK range 1 is same as kit range 1 but without Super Star (18 teams)
_GK_RANGE1_TEAMS = _KIT_RANGE1_TEAMS[:18]

# Flag color team orderings
_FLAG_RANGE1_TEAMS = [
    "Germany", "England", "Italy", "Holland", "France", "Spain", "Belgium",
    "Ireland", "Colombia", "Brazil", "Argentina", "Mexico", "Nigeria",
    "Cameroon", "U.S.A.", "Bulgaria", "Romania", "Sweden",
]

_FLAG_RANGE2_TEAMS = [
    "Scotland", "S.Korea", "Super Star", "Russia", "Switz", "Denmark",
    "Austria", "Wales", "Norway",
]

# ── Team name text character widths (pixels) ──────────────────────────────
_NAME_CHAR_WIDTHS = {"I": 7, ".": 7, "M": 8, "N": 8, "T": 8, "W": 8}
_NAME_SPACE_WIDTH = 3
_NAME_DEFAULT_WIDTH = 9
_MAX_NAME_WIDTH = 70

# ── Shooting/technique value table (3-bit → odd values 1-15) ───────────────
_SHOOTING_VALUES = [1, 3, 5, 7, 9, 11, 13, 15]

# ── ISS custom character encoding ──────────────────────────────────────────
_CHAR_TO_BYTE = {}


def _init_encoding():
    if _CHAR_TO_BYTE:
        return
    _CHAR_TO_BYTE[" "] = 0x00
    _CHAR_TO_BYTE["."] = 0x54
    _CHAR_TO_BYTE["-"] = 0x53
    _CHAR_TO_BYTE['"'] = 0x56
    _CHAR_TO_BYTE["'"] = 0x5C
    _CHAR_TO_BYTE["/"] = 0x5F
    for i, c in enumerate("0123456789"):
        _CHAR_TO_BYTE[c] = 0x62 + i
    for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
        _CHAR_TO_BYTE[c] = 0x6C + i
    for i, c in enumerate("abcdefghijklmnopqrstuvwxyz"):
        _CHAR_TO_BYTE[c] = 0x86 + i


def _to_ascii(text: str) -> str:
    """Strip diacritics and non-ASCII chars."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c) and ord(c) < 128)


def _encode_iss_name(name: str, max_len: int = 8) -> bytes:
    """Encode a player name to ISS custom encoding, padded with spaces (0x00)."""
    _init_encoding()
    ascii_name = _to_ascii(name)
    encoded = bytearray(max_len)  # filled with 0x00 = space
    for i, c in enumerate(ascii_name[:max_len]):
        encoded[i] = _CHAR_TO_BYTE.get(c, 0x00)
    return bytes(encoded)


def _rgb_to_bgr555(r: int, g: int, b: int) -> int:
    """Convert RGB888 to SNES BGR555 (15-bit)."""
    r5 = min(31, r * 31 // 255)
    g5 = min(31, g * 31 // 255)
    b5 = min(31, b * 31 // 255)
    return r5 | (g5 << 5) | (b5 << 10)


def _bgr555_to_rgb(value: int) -> Tuple[int, int, int]:
    """Convert SNES BGR555 to RGB888."""
    r5 = value & 0x1F
    g5 = (value >> 5) & 0x1F
    b5 = (value >> 10) & 0x1F
    return (r5 * 255 // 31, g5 * 255 // 31, b5 * 255 // 31)


def _shooting_to_rom(value: int) -> int:
    """Map a shooting/technique value (1-15) to the 3-bit ROM index (0-7)."""
    # Find closest value in the table
    best_idx = 0
    best_dist = abs(_SHOOTING_VALUES[0] - value)
    for i, sv in enumerate(_SHOOTING_VALUES):
        d = abs(sv - value)
        if d < best_dist:
            best_dist = d
            best_idx = i
    return best_idx


def _speed_to_rom(value: int) -> int:
    """Encode speed value (1-16) to the ROM byte format.

    From SkillData.java:
      if (b % 0x20 == 0) return b / 0x20 + 1;
      return ((int) b + 1) / 0x20 + 8;

    We need the inverse. Values 1-7 → multiples of 0x20 (0x00, 0x20, ..., 0xC0).
    Values 8-16 → non-multiples: approximate as (value - 8) * 0x20 + some offset.
    Simplified: clamp to 0x00-0xE0 range in 0x20 steps.
    """
    clamped = max(1, min(16, value))
    # Simple linear mapping: value 1→0x00, 8→0xE0, 16→0xE0
    # Based on the decoder, multiples of 0x20 decode to b/0x20+1
    # So value V → (V-1)*0x20 for V in 1..7
    if clamped <= 7:
        return (clamped - 1) * 0x20
    # For 8-16, use non-multiples: ((V-8)*0x20) + some offset
    # decoder: ((b+1)/0x20) + 8 = V → b = (V-8)*0x20 - 1
    return max(0, (clamped - 8) * 0x20 - 1) & 0xFF


def _char_top_tile(c: str):
    """Get the top-half tile ID for a character, or None if no top half."""
    if "A" <= c <= "P":
        return 0xC0 + (ord(c) - ord("A"))
    if "Q" <= c <= "Z":
        return 0xE0 + (ord(c) - ord("Q"))
    if "0" <= c <= "9":
        return 0xA0 + (ord(c) - ord("0"))
    return None


def _char_bottom_tile(c: str):
    """Get the bottom-half tile ID for a character, or None if no bottom half."""
    if "A" <= c <= "P":
        return 0xD0 + (ord(c) - ord("A"))
    if "Q" <= c <= "Z":
        return 0xF0 + (ord(c) - ord("Q"))
    if "0" <= c <= "9":
        return 0xB0 + (ord(c) - ord("0"))
    if c == ".":
        return 0xFA
    return None


def _encode_team_name_text(name: str) -> bytes:
    """Encode a team name into ISS team-name-text format.

    Returns: [count_byte] [entry0_4bytes] [entry1_4bytes] ...
    Each visible character produces bottom+top entries (4 bytes each).
    Period only has a bottom-half tile.

    Original ROM ordering: characters right-to-left, F9 (bottom) before F1 (top).
    """
    clean = _to_ascii(name).upper()
    # Build (char, x_position) list
    chars = []
    x = 0
    for c in clean:
        if c == " ":
            x += _NAME_SPACE_WIDTH
            continue
        top = _char_top_tile(c)
        bot = _char_bottom_tile(c)
        if top is None and bot is None:
            continue
        w = _NAME_CHAR_WIDTHS.get(c, _NAME_DEFAULT_WIDTH)
        chars.append((c, x, top, bot))
        x += w

    total_width = x
    # Compress if too wide
    if total_width > _MAX_NAME_WIDTH and total_width > 0:
        scale = _MAX_NAME_WIDTH / total_width
        chars = [(c, int(xp * scale), t, b) for c, xp, t, b in chars]
        total_width = _MAX_NAME_WIDTH

    # Center: shift all x positions
    half = total_width // 2
    entries = []
    # Characters in reverse order (right-to-left), bottom (F9) before top (F1)
    for c, xp, top, bot in reversed(chars):
        x_centered = xp - half
        x_byte = x_centered & 0xFF  # signed to unsigned byte
        if bot is not None:
            entries.append(bytes([0xF9, x_byte, bot, 0x06]))
        if top is not None:
            entries.append(bytes([0xF1, x_byte, top, 0x06]))

    count = len(entries)
    result = bytearray([count])
    for e in entries:
        result.extend(e)
    return bytes(result)


def _decode_p40000(b1: int, b2: int) -> int:
    """Decode P40000 pointer bytes to ROM file offset."""
    return 0x40000 | ((b2 - 0x80) << 8) | b1


def _encode_p40000(address: int) -> bytes:
    """Encode ROM file offset as P40000 pointer bytes [low, high]."""
    raw = address - 0x40000
    b1 = raw & 0xFF
    b2 = ((raw >> 8) & 0xFF) + 0x80
    return bytes([b1, b2])



def _make_shades(r: int, g: int, b: int, count: int) -> list:
    """Generate BGR555 shades (dark→light) from a single RGB color.

    For bright colors (near white): base is lightest shade, darker shades generated below.
    For dark/medium colors: base is darkest shade, lighter shades blend toward white.
    Spread is ~50% of the available range per channel.
    """
    r5 = min(31, r * 31 // 255)
    g5 = min(31, g * 31 // 255)
    b5 = min(31, b * 31 // 255)

    brightness = (r5 + g5 + b5) / 3.0

    shades = []
    if brightness > 22:
        # Bright color: base is lightest, darken for shadow shades
        for i in range(count):
            t = (count - 1 - i) / (count - 1) * 0.5 if count > 1 else 0
            rv = max(0, round(r5 * (1.0 - t)))
            gv = max(0, round(g5 * (1.0 - t)))
            bv = max(0, round(b5 * (1.0 - t)))
            shades.append(rv | (gv << 5) | (bv << 10))
    else:
        # Dark/medium: base is darkest, lighter shades blend toward white
        for i in range(count):
            t = i / (count - 1) * 0.5 if count > 1 else 0
            rv = min(31, round(r5 + t * (31 - r5)))
            gv = min(31, round(g5 + t * (31 - g5)))
            bv = min(31, round(b5 + t * (31 - b5)))
            shades.append(rv | (gv << 5) | (bv << 10))
    return shades


def _rgb_to_predominant(r: int, g: int, b: int) -> int:
    """Map RGB to ISS predominant color (0=White,1=Blue,2=Red,3=Yellow,4=Green)."""
    max_c = max(r, g, b)
    min_c = min(r, g, b)
    if max_c > 200 and (max_c - min_c) < 50:
        return 0  # White
    if r >= g and r >= b:
        if g > 150 and g > b:
            return 3  # Yellow
        return 2  # Red
    if g >= r and g >= b:
        return 4  # Green
    return 1  # Blue


class ISSRomWriter:
    def __init__(self, rom_path: str, output_path: str, header_offset: int = 0):
        _init_encoding()
        self.output_path = output_path
        self.header_offset = header_offset

        # Copy ROM to output
        shutil.copy2(rom_path, output_path)
        self._f = open(output_path, "r+b")

    def _seek(self, offset: int):
        """Seek to a ROM offset, accounting for copier header."""
        self._f.seek(offset + self.header_offset)

    def write_player_names(self, enum_index: int, players: List[ISSPlayerRecord]):
        """Write player names for a team.

        Names are stored in TEAM_NAME_ORDER, so we need to convert from
        enum_index to the name storage index.
        """
        enum_name = TEAM_ENUM_ORDER[enum_index]
        try:
            name_index = TEAM_NAME_ORDER.index(enum_name)
        except ValueError:
            return  # Team not in name order (shouldn't happen)

        base = _OFS_PLAYER_NAMES + name_index * PLAYERS_PER_TEAM * 8
        for i, player in enumerate(players[:PLAYERS_PER_TEAM]):
            self._seek(base + i * 8)
            self._f.write(_encode_iss_name(player.name, 8))

    def write_player_data(self, enum_index: int, players: List[ISSPlayerRecord]):
        """Write player abilities, shirt numbers, hair, and special flag.

        Player data is stored in TEAM_ENUM_ORDER.
        6 bytes per player:
          [0] speed   [1] shooting (high nibble)
          [2] shooting(low) + technique(high)  [3] shirt_number
          [4] stamina [5] hair_style | special_flag
        """
        base = _OFS_PLAYER_DATA + enum_index * PLAYERS_PER_TEAM * 6
        for i, player in enumerate(players[:PLAYERS_PER_TEAM]):
            self._seek(base + i * 6)
            existing = bytearray(self._f.read(6))
            self._seek(base + i * 6)

            attrs = player.attributes

            # Byte 0: speed
            existing[0] = _speed_to_rom(attrs.speed)

            # Bytes 1-2: shooting + technique
            # Shooting is stored as a 3-bit value in the data
            shoot_idx = _shooting_to_rom(attrs.shooting)
            tech_idx = _shooting_to_rom(attrs.technique)
            # Preserve non-ability bits, write ability bits
            existing[1] = (existing[1] & 0xF8) | (shoot_idx & 0x07)
            existing[2] = (existing[2] & 0xF8) | (tech_idx & 0x07)

            # Byte 3: shirt number (low nibble = number - 1, preserve high nibble)
            number = max(1, min(16, player.shirt_number))
            existing[3] = (existing[3] & 0xF0) | ((number - 1) & 0x0F)

            # Byte 4: stamina (low nibble = stamina - 1)
            stamina = max(1, min(16, attrs.stamina))
            existing[4] = (existing[4] & 0xF0) | ((stamina - 1) & 0x0F)

            # Byte 5: hair_style (low nibble) | special (bit 6)
            hair = max(0, min(10, player.hair_style))
            special_bit = 0x40 if player.is_special else 0x00
            existing[5] = (existing[5] & 0xB0) | special_bit | (hair & 0x0F)

            self._f.write(bytes(existing))

    def write_kit_colors(self, enum_index: int, team: ISSTeamRecord):
        """Write kit colors (home, away, GK) for a team.

        Outfield kits are 32 bytes: 6B shirt + 6B shorts + 4B socks + 16B extra
        GK kits are 24 bytes: 10B shirt + 2B shorts + 12B extra
        Colors are BGR555 little-endian.
        """
        enum_name = TEAM_ENUM_ORDER[enum_index]

        # Determine which range and position
        if enum_name in _KIT_RANGE1_TEAMS:
            kit1_base = _OFS_KIT1_RANGE1
            kit2_base = _OFS_KIT2_RANGE1
            pos = _KIT_RANGE1_TEAMS.index(enum_name)
        elif enum_name in _KIT_RANGE2_TEAMS:
            kit1_base = _OFS_KIT1_RANGE2
            kit2_base = _OFS_KIT2_RANGE2
            pos = _KIT_RANGE2_TEAMS.index(enum_name)
        else:
            return

        # Write home kit (1st kit)
        if team.kit_home:
            self._write_outfield_kit(kit1_base + pos * 32, team.kit_home)

        # Write away kit (2nd kit)
        if team.kit_away:
            self._write_outfield_kit(kit2_base + pos * 32, team.kit_away)

        # Write GK kit
        if team.kit_gk:
            if enum_name in _GK_RANGE1_TEAMS:
                gk_base = _OFS_GK_RANGE1
                gk_pos = _GK_RANGE1_TEAMS.index(enum_name)
            elif enum_name in _KIT_RANGE2_TEAMS:
                gk_base = _OFS_GK_RANGE2
                gk_pos = _KIT_RANGE2_TEAMS.index(enum_name)
            else:
                return
            self._write_gk_kit(gk_base + gk_pos * 24, team.kit_gk)

    def _write_outfield_kit(self, offset: int, colors: Tuple[Tuple[int, int, int], ...]):
        """Write shirt/shorts/socks with proper shade gradients (dark→light).

        32-byte block: words 0-2 shirt, words 3-5 shorts, words 6-7 socks,
        words 8-15 hair/skin (untouched).
        """
        if not colors:
            return
        self._seek(offset)
        existing = bytearray(self._f.read(16))
        self._seek(offset)

        shirt_color = colors[0] if len(colors) > 0 else (255, 255, 255)
        shorts_color = colors[1] if len(colors) > 1 else shirt_color
        socks_color = colors[2] if len(colors) > 2 else shirt_color

        # Shirt: 3 shades (bytes 0-5)
        for i, shade in enumerate(_make_shades(*shirt_color, 3)):
            struct.pack_into("<H", existing, i * 2, shade)

        # Shorts: 3 shades (bytes 6-11)
        for i, shade in enumerate(_make_shades(*shorts_color, 3)):
            struct.pack_into("<H", existing, 6 + i * 2, shade)

        # Socks: 2 shades (bytes 12-15)
        for i, shade in enumerate(_make_shades(*socks_color, 2)):
            struct.pack_into("<H", existing, 12 + i * 2, shade)

        self._f.write(bytes(existing))

    def _write_gk_kit(self, offset: int, colors: Tuple[Tuple[int, int, int], ...]):
        """Write GK kit with proper shade gradients.

        24-byte block: word 0 specular (always near-white), words 1-4 shirt
        (4 shades dark→light), word 5 shorts, words 6-11 hair/skin (untouched).
        """
        if not colors:
            return
        self._seek(offset)
        existing = bytearray(self._f.read(12))
        self._seek(offset)

        shirt_color = colors[0] if len(colors) > 0 else (0, 128, 0)
        shorts_color = colors[1] if len(colors) > 1 else shirt_color

        # Word 0: specular highlight (always near-white)
        struct.pack_into("<H", existing, 0, 0x7FFE)

        # Words 1-4: 4 shirt shades (bytes 2-9)
        for i, shade in enumerate(_make_shades(*shirt_color, 4)):
            struct.pack_into("<H", existing, 2 + i * 2, shade)

        # Word 5: shorts (single color, bytes 10-11)
        struct.pack_into("<H", existing, 10, _rgb_to_bgr555(*shorts_color))

        self._f.write(bytes(existing))

    def write_flag_colors(self, enum_index: int, team: ISSTeamRecord):
        """Write flag colors for a team.

        4 colors per flag, 10 bytes per team (4 × 2 bytes + 2 padding).
        """
        if not team.flag_colors:
            return

        enum_name = TEAM_ENUM_ORDER[enum_index]

        if enum_name in _FLAG_RANGE1_TEAMS:
            base = _OFS_FLAG_COLORS_RANGE1
            pos = _FLAG_RANGE1_TEAMS.index(enum_name)
        elif enum_name in _FLAG_RANGE2_TEAMS:
            base = _OFS_FLAG_COLORS_RANGE2
            pos = _FLAG_RANGE2_TEAMS.index(enum_name)
        else:
            return

        self._seek(base + pos * 10)
        data = bytearray(10)
        for i, color in enumerate(team.flag_colors[:4]):
            c = _rgb_to_bgr555(*color)
            struct.pack_into("<H", data, i * 2, c)
        self._f.write(bytes(data))

    def write_team_name_texts(self, patched_names: dict):
        """Write team names to the selection-screen text data.

        Preserves original ROM data for unpatched teams to avoid overflow
        (original uses combined-character encoding we don't replicate).
        Truncates long patched names if total would exceed available space.

        patched_names: dict of {slot_index: new_name_str} for teams to update.
        """
        # Read existing pointer table and data
        self._seek(_OFS_TEAM_NAME_TEXT_PTRS)
        raw_ptrs = self._f.read(TOTAL_TEAMS * 2)

        orig_addrs = []
        orig_data = []
        for i in range(TOTAL_TEAMS):
            b1 = raw_ptrs[i * 2]
            b2 = raw_ptrs[i * 2 + 1]
            addr = _decode_p40000(b1, b2)
            orig_addrs.append(addr)
            self._seek(addr)
            count = self._f.read(1)[0]
            size = 1 + count * 4
            self._seek(addr)
            orig_data.append(self._f.read(size))

        min_addr = min(orig_addrs)
        budget = _MAX_NAME_TEXT_ADDR - min_addr

        # Build team data blobs — patched teams get new encoding, others keep original
        names_copy = dict(patched_names)
        team_blobs = []
        for i in range(TOTAL_TEAMS):
            if i in names_copy:
                team_blobs.append(_encode_team_name_text(names_copy[i]))
            else:
                team_blobs.append(orig_data[i])

        # Progressively truncate longest patched names until data fits
        while sum(len(b) for b in team_blobs) > budget:
            # Find the longest patched name we can still shorten
            longest_idx = -1
            longest_len = 0
            for idx in names_copy:
                if len(names_copy[idx]) > 3 and len(team_blobs[idx]) > longest_len:
                    longest_len = len(team_blobs[idx])
                    longest_idx = idx
            if longest_idx < 0:
                break  # Can't shrink further
            names_copy[longest_idx] = names_copy[longest_idx][:-1]
            team_blobs[longest_idx] = _encode_team_name_text(names_copy[longest_idx])

        # Build final data with pointers
        current_addr = min_addr
        new_pointers = []
        all_data = bytearray()
        for blob in team_blobs:
            new_pointers.append(_encode_p40000(current_addr))
            all_data.extend(blob)
            current_addr += len(blob)

        # Write pointer table
        self._seek(_OFS_TEAM_NAME_TEXT_PTRS)
        for ptr in new_pointers:
            self._f.write(ptr)

        # Write name data (capped at budget for safety)
        self._seek(min_addr)
        self._f.write(bytes(all_data[:budget]))

    def write_predominant_color(self, enum_index: int, rgb: Tuple[int, int, int]):
        """Write the predominant color byte for a team.

        0=White, 1=Blue, 2=Red, 3=Yellow, 4=Green
        """
        color = _rgb_to_predominant(*rgb)
        self._seek(_OFS_PREDOMINANT_COLOR + enum_index)
        self._f.write(bytes([color]))

    def finalize(self):
        """Close the output file."""
        if self._f:
            self._f.close()
            self._f = None
