"""ROM writer for NHL94 Genesis patcher.

Writes player names and stats back to NHL94 Genesis ROM.
Does in-place patching — names are truncated to fit the original
record's space. Team header, strings, palettes, and structure are preserved.

Also disables the ROM checksum so edited ROMs boot correctly.

References:
  - https://forum.nhl94.com/index.php?/topic/26353-how-to-manually-edit-the-team-player-data-nhl-94/
  - https://nhl94.com/html/editing/edit_bin.php
"""

import os
from typing import List, Optional

from services.nhl94_genesis_patcher.models import (
    NHL94GenPlayerRecord,
    TEAM_COUNT,
)
from services.nhl94_genesis_patcher.rom_reader import (
    NHL94GenesisRomReader,
    STATS_SIZE,
    CHECKSUM_BYPASS_OFFSET,
)


def encode_nibble(high: int, low: int) -> int:
    """Encode two nibbles (0-6) into a byte."""
    high = max(0, min(6, high))
    low = max(0, min(6, low))
    return (high << 4) | low


def encode_weight_nibble(weight_class: int, low_stat: int) -> int:
    """Encode weight class (0-14) in high nibble + stat (0-6) in low nibble."""
    weight_class = max(0, min(14, weight_class))
    low_stat = max(0, min(6, low_stat))
    return (weight_class << 4) | low_stat


class NHL94GenesisRomWriter:
    """Writes player data to NHL94 Genesis ROM.

    Strategy: in-place patching. For each team, read the existing player
    region to know how much space is available, then write new records
    that fit within that space. Names are truncated if needed.
    """

    def __init__(self, rom_path: str, output_path: str):
        self.rom_path = rom_path
        self.output_path = output_path
        self.data: Optional[bytearray] = None
        self.reader = NHL94GenesisRomReader(rom_path)

    def load(self) -> bool:
        """Load ROM data for writing."""
        if not self.reader.load():
            return False
        if self.reader.data:
            self.data = bytearray(self.reader.data)
            return True
        return False

    def _write_u16_be(self, offset: int, value: int):
        """Write a big-endian 16-bit value."""
        self.data[offset] = (value >> 8) & 0xFF
        self.data[offset + 1] = value & 0xFF

    def disable_checksum(self):
        """Disable ROM checksum by writing RTS (0x4E75) at bypass offset.

        This makes the checksum routine return immediately so edited ROMs boot.
        """
        if not self.data:
            return
        if CHECKSUM_BYPASS_OFFSET + 2 <= len(self.data):
            self.data[CHECKSUM_BYPASS_OFFSET] = 0x4E
            self.data[CHECKSUM_BYPASS_OFFSET + 1] = 0x75

    def update_header_checksum(self):
        """Recalculate the Genesis ROM header checksum at 0x18E.

        The checksum is the sum of all 16-bit big-endian words from
        offset 0x200 to end of ROM, stored as a 16-bit value at 0x18E.
        """
        if not self.data or len(self.data) < 0x200:
            return
        checksum = 0
        for i in range(0x200, len(self.data), 2):
            if i + 1 < len(self.data):
                word = (self.data[i] << 8) | self.data[i + 1]
            else:
                word = self.data[i] << 8
            checksum = (checksum + word) & 0xFFFF
        self.data[0x18E] = (checksum >> 8) & 0xFF
        self.data[0x18F] = checksum & 0xFF

    def write_team_roster(
        self,
        team_index: int,
        players: List[NHL94GenPlayerRecord],
    ) -> bool:
        """Write player records for a team, fitting within existing space.

        Names are truncated if they don't fit. Excess space is zero-filled.
        """
        if not self.data or team_index >= TEAM_COUNT:
            return False

        start, region_size = self.reader.get_team_player_region(team_index)
        if region_size == 0:
            return False

        offset = start
        end = start + region_size

        for player in players:
            # Space needed: 2 (length) + name_len + 8 (stats) + 2 (sentinel)
            max_name_len = (end - offset) - 2 - STATS_SIZE - 2
            if max_name_len < 1:
                break  # No room for more players

            # Truncate name to fit
            name = player.name[:max_name_len]
            name_bytes = name.encode("ascii", errors="replace")
            name_len = len(name_bytes)

            # Write 2-byte BE length (includes the 2 length bytes)
            total_len = name_len + 2
            self._write_u16_be(offset, total_len)
            offset += 2

            # Write name bytes
            for i, b in enumerate(name_bytes):
                self.data[offset + i] = b
            offset += name_len

            # Write 8 stat bytes
            offset = self._write_player_stats(player, offset)

        # Write end-of-roster sentinel (0x0000)
        if offset + 2 <= end:
            self.data[offset] = 0x00
            self.data[offset + 1] = 0x00
            offset += 2

        # Zero-fill remaining space
        while offset < end:
            self.data[offset] = 0x00
            offset += 1

        return True

    def _write_player_stats(
        self, player: NHL94GenPlayerRecord, offset: int
    ) -> int:
        """Write 8 stat bytes for a player. Returns new offset.

        Byte layout (14 nibbles packed into 8 bytes):
          Byte 0: Jersey number (BCD)
          Byte 1: Weight (0-14) | Agility (0-6)
          Byte 2: Speed (0-6) | Off. Awareness (0-6)
          Byte 3: Def. Awareness (0-6) | Shot Power (0-6)
          Byte 4: Checking (0-6) | Handedness (0=L, 1=R)
          Byte 5: Stick Handling (0-6) | Shot Accuracy (0-6)
          Byte 6: Endurance (0-6) | Roughness (0-6)
          Byte 7: Pass Accuracy (0-6) | Aggression (0-6)
        """
        if not self.data or offset + STATS_SIZE > len(self.data):
            return offset

        attrs = player.attributes

        # Byte 0: Jersey number (BCD)
        jersey = max(1, min(99, player.jersey_number))
        self.data[offset] = ((jersey // 10) << 4) | (jersey % 10)
        offset += 1

        # Byte 1: Weight class | Agility
        self.data[offset] = encode_weight_nibble(
            player.weight_class, attrs.agility
        )
        offset += 1

        # Byte 2: Speed | Off. Awareness
        self.data[offset] = encode_nibble(attrs.speed, attrs.off_awareness)
        offset += 1

        # Byte 3: Def. Awareness | Shot Power
        self.data[offset] = encode_nibble(
            attrs.def_awareness, attrs.shot_power
        )
        offset += 1

        # Byte 4: Checking | Handedness
        self.data[offset] = encode_nibble(attrs.checking, player.handedness)
        offset += 1

        # Byte 5: Stick Handling | Shot Accuracy
        self.data[offset] = encode_nibble(
            attrs.stick_handling, attrs.shot_accuracy
        )
        offset += 1

        # Byte 6: Endurance | Roughness
        self.data[offset] = encode_nibble(attrs.endurance, attrs.roughness)
        offset += 1

        # Byte 7: Pass Accuracy | Aggression
        self.data[offset] = encode_nibble(
            attrs.pass_accuracy, attrs.aggression
        )
        offset += 1

        return offset

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
