"""ROM writer for KGJ MLB patcher.

Writes player data to Ken Griffey Jr. Presents MLB (SNES) ROM.
Each player is exactly 32 bytes at fixed offsets — no variable-length records.

References:
  - https://github.com/johnz1/ken_griffey_jr_presents_major_league_baseball_tools
"""

import os
from typing import List, Optional

from services.kgj_mlb_patcher.models import (
    KGJPlayerRecord,
    CHAR_TO_BYTE,
    POSITION_TO_BYTE,
    PLAYER_LENGTH,
    TEAM_COUNT,
    PLAYERS_PER_TEAM,
    BATTERS_PER_TEAM,
    STARTERS_PER_TEAM,
)
from services.kgj_mlb_patcher.rom_reader import KGJRomReader


def _encode_char(ch: str) -> int:
    """Encode a single character to ROM byte."""
    return CHAR_TO_BYTE.get(ch, CHAR_TO_BYTE.get(ch.upper(), 0x00))


def _encode_name(name: str, length: int) -> List[int]:
    """Encode a name string to ROM bytes, padded to length."""
    result = []
    for ch in name[:length]:
        result.append(_encode_char(ch))
    while len(result) < length:
        result.append(0x00)  # Space padding
    return result


def _encode_stat_pair(high: int, low: int) -> int:
    """Encode two ratings (1-10) into high/low nibbles.

    ROM stores (rating - 1), so 1-10 maps to 0x0-0x9.
    """
    h = max(0, min(9, high - 1))
    l = max(0, min(9, low - 1))
    return (h << 4) | l


def _encode_bcd_stat(value: int) -> tuple:
    """Encode a BCD stat value (batting avg * 1000, or ERA * 100).

    Returns (low_byte, high_nibble).
    For example, .325 = 325:
      hex(325) = 0x145 -> low_byte=0x45, high_nibble=0x1
    """
    value = max(0, min(999, value))
    low_byte = value & 0xFF
    high_nibble = (value >> 8) & 0x0F
    return low_byte, high_nibble


class KGJRomWriter:
    """Writes player data to KGJ MLB ROM.

    Fixed-size 32-byte records at known offsets — no space management needed.
    """

    def __init__(self, rom_path: str, output_path: str):
        self.rom_path = rom_path
        self.output_path = output_path
        self.data: Optional[bytearray] = None
        self.reader = KGJRomReader(rom_path)

    def load(self) -> bool:
        """Load ROM data for writing."""
        if not self.reader.load():
            return False
        if not self.reader.validate():
            return False
        if self.reader.data:
            self.data = bytearray(self.reader.data)
            return True
        return False

    def write_player(
        self, team_index: int, player_slot: int, player: KGJPlayerRecord
    ) -> bool:
        """Write a single player record (32 bytes) to ROM."""
        if not self.data or team_index >= TEAM_COUNT:
            return False
        if player_slot >= PLAYERS_PER_TEAM:
            return False

        off = self.reader.get_player_offset(team_index, player_slot)
        if off + PLAYER_LENGTH > len(self.data):
            return False

        d = self.data

        # Byte 0x00: First initial
        d[off] = _encode_char(player.first_initial)

        # Bytes 0x01-0x08: Last name (8 chars, padded)
        name_bytes = _encode_name(player.last_name, 8)
        for i, b in enumerate(name_bytes):
            d[off + 1 + i] = b

        # Byte 0x09: Position
        d[off + 0x09] = POSITION_TO_BYTE.get(player.position, 0x06)

        # Byte 0x0A: Jersey number
        d[off + 0x0A] = max(0, min(99, player.jersey_number))

        if player.is_pitcher:
            self._write_pitcher(off, player)
        else:
            self._write_batter(off, player)

        return True

    def _write_batter(self, off: int, player: KGJPlayerRecord):
        """Write batter-specific fields."""
        d = self.data
        attrs = player.batter_attrs
        app = player.batter_appearance

        # Byte 0x0B: BAT (high) | POW (low)
        d[off + 0x0B] = _encode_stat_pair(attrs.batting, attrs.power)

        # Byte 0x0C: SPD (high) | DEF (low)
        d[off + 0x0C] = _encode_stat_pair(attrs.speed, attrs.defense)

        # Byte 0x0D: Batting handedness
        d[off + 0x0D] = player.bat_hand

        # Byte 0x0E: Skin (high) | Head (low)
        d[off + 0x0E] = ((app.skin & 0xF) << 4) | (app.head & 0xF)

        # Byte 0x0F: Hair color (high) | Body (low)
        d[off + 0x0F] = ((app.hair_color & 0xF) << 4) | (app.body & 0xF)

        # Byte 0x10: Legs size (high) | Legs stance (low)
        d[off + 0x10] = ((app.legs_size & 0xF) << 4) | (app.legs_stance & 0xF)

        # Byte 0x11: preserve high nibble, Arms stance (low)
        d[off + 0x11] = (d[off + 0x11] & 0xF0) | (app.arms_stance & 0xF)

        # Bytes 0x15-0x17: zero for batters
        d[off + 0x15] = 0x00
        d[off + 0x16] = 0x00
        d[off + 0x17] = 0x00

        # Byte 0x18-0x19: Batting average (BCD)
        avg_low, avg_high = _encode_bcd_stat(player.batting_avg)
        d[off + 0x18] = avg_low
        # Byte 0x19: roster type (high) | avg hundreds (low)
        d[off + 0x19] = (player.roster_type & 0xF0) | (avg_high & 0x0F)

        # Byte 0x1A: Home runs
        d[off + 0x1A] = max(0, min(255, player.home_runs))

        # Byte 0x1B: always 0
        d[off + 0x1B] = 0x00

        # Byte 0x1C: RBI
        d[off + 0x1C] = max(0, min(255, player.rbi))

        # Byte 0x1D: 0x10 (batter flag)
        d[off + 0x1D] = 0x10

        # Byte 0x1E: unused for batters
        d[off + 0x1E] = 0x00

    def _write_pitcher(self, off: int, player: KGJPlayerRecord):
        """Write pitcher-specific fields."""
        d = self.data
        attrs = player.pitcher_attrs
        app = player.pitcher_appearance

        # Byte 0x0B: SPD (high) | CON (low)
        d[off + 0x0B] = _encode_stat_pair(attrs.speed, attrs.control)

        # Byte 0x0C: 0 (high) | FAT (low)
        d[off + 0x0C] = max(0, min(9, attrs.fatigue - 1)) & 0x0F

        # Byte 0x0D: Batting handedness (pitchers bat too)
        d[off + 0x0D] = player.bat_hand

        # Bytes 0x0E-0x11: batter appearance (pitchers also bat)
        bapp = player.batter_appearance
        d[off + 0x0E] = ((bapp.skin & 0xF) << 4) | (bapp.head & 0xF)
        d[off + 0x0F] = ((bapp.hair_color & 0xF) << 4) | (bapp.body & 0xF)
        d[off + 0x10] = ((bapp.legs_size & 0xF) << 4) | (bapp.legs_stance & 0xF)
        d[off + 0x11] = (d[off + 0x11] & 0xF0) | (bapp.arms_stance & 0xF)

        # Byte 0x15: Pitch hand (high) | Pitch skin (low)
        d[off + 0x15] = ((player.pitch_hand & 0xF) << 4) | (app.skin & 0xF)

        # Byte 0x16: Pitch head (high) | Pitch hair color (low)
        d[off + 0x16] = ((app.head & 0xF) << 4) | (app.hair_color & 0xF)

        # Byte 0x17: Pitch body (high) | Throwing style (low)
        d[off + 0x17] = ((app.body & 0xF) << 4) | (app.throwing_style & 0xF)

        # Byte 0x18: Wins
        d[off + 0x18] = max(0, min(255, player.wins))

        # Byte 0x19: roster type (high) | 0 (low)
        d[off + 0x19] = player.roster_type & 0xF0

        # Byte 0x1A: Losses
        d[off + 0x1A] = max(0, min(255, player.losses))

        # Byte 0x1B: always 0
        d[off + 0x1B] = 0x00

        # Byte 0x1C-0x1D: ERA (BCD)
        era_low, era_high = _encode_bcd_stat(player.era)
        d[off + 0x1C] = era_low

        # Byte 0x1D: pitcher flag 0x2 (high) | ERA hundreds (low)
        d[off + 0x1D] = 0x20 | (era_high & 0x0F)

        # Byte 0x1E: Saves
        d[off + 0x1E] = max(0, min(255, player.saves))

    def write_team_roster(
        self, team_index: int, players: List[KGJPlayerRecord]
    ) -> int:
        """Write all players for a team.

        Players list should be ordered:
          [0-14]  = batters (15)
          [15-19] = starting pitchers (5)
          [20-24] = relief pitchers (5)

        Sets roster_type flags automatically based on slot position.
        Returns number of players written.
        """
        if not self.data or team_index >= TEAM_COUNT:
            return -1

        written = 0
        for slot, player in enumerate(players[:PLAYERS_PER_TEAM]):
            # Set roster type based on slot
            if slot < BATTERS_PER_TEAM:
                player.roster_type = 0x30  # Batter
            elif slot < BATTERS_PER_TEAM + STARTERS_PER_TEAM:
                player.roster_type = 0x10  # Starting pitcher
            else:
                player.roster_type = 0x00  # Relief pitcher

            if self.write_player(team_index, slot, player):
                written += 1

        return written

    def update_snes_checksum(self):
        """Recalculate the SNES internal checksum.

        The checksum at 0x7FDE is the 16-bit sum of all ROM bytes.
        The complement at 0x7FDC = 0xFFFF - checksum.
        Not strictly required (emulators don't verify) but nice to have.
        """
        if not self.data or len(self.data) < 0x8000:
            return

        # Determine checksum location (headerless vs headered)
        if len(self.data) == ROM_SIZE_EXPECTED + 512:
            cksum_off = 0x7FDE + 512
            comp_off = 0x7FDC + 512
        else:
            cksum_off = 0x7FDE
            comp_off = 0x7FDC

        # Zero out existing checksum fields before calculation
        self.data[cksum_off] = 0x00
        self.data[cksum_off + 1] = 0x00
        self.data[comp_off] = 0xFF
        self.data[comp_off + 1] = 0xFF

        # Calculate sum of all bytes
        total = sum(self.data) & 0xFFFF

        # Write checksum and complement
        self.data[cksum_off] = total & 0xFF
        self.data[cksum_off + 1] = (total >> 8) & 0xFF
        complement = (0xFFFF - total) & 0xFFFF
        self.data[comp_off] = complement & 0xFF
        self.data[comp_off + 1] = (complement >> 8) & 0xFF

    def finalize(self) -> bool:
        """Write the modified ROM to output path."""
        if not self.data:
            return False
        try:
            output_dir = os.path.dirname(self.output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            with open(self.output_path, "wb") as f:
                f.write(self.data)
            return True
        except Exception:
            return False


# Import constant used in update_snes_checksum
from services.kgj_mlb_patcher.rom_reader import ROM_SIZE_EXPECTED  # noqa: E402
