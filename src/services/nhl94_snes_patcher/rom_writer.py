"""ROM writer for NHL94 SNES patcher.

Writes player names and stats back to NHL94 SNES ROM.
Does in-place patching — names are truncated to fit the original
record's space. Team header, strings, and structure are preserved.

References:
  - https://github.com/clandrew/nhl94e
  - https://cml-a.com/content/2020/11/23/names-and-stats-in-nhl-94/
"""

import os
from typing import List, Optional, Tuple

from services.nhl94_snes_patcher.models import (
    NHL94PlayerRecord,
    TEAM_COUNT,
)
from services.nhl94_snes_patcher.rom_reader import (
    NHL94SNESRomReader,
    STATS_SIZE,
)


def encode_nibble(high: int, low: int) -> int:
    """Encode two nibbles (0-6) into a byte."""
    high = max(0, min(6, high))
    low = max(0, min(6, low))
    return (high << 4) | low


def encode_weight_nibble(weight_class: int, low_stat: int) -> int:
    """Encode weight class (0-14) in high nibble + stat (0-6) in low nibble.

    Weight class uses the full 4-bit range (0-15), not the 0-6 stat range.
    """
    weight_class = max(0, min(14, weight_class))
    low_stat = max(0, min(6, low_stat))
    return (weight_class << 4) | low_stat


class NHL94SNESRomWriter:
    """Writes player data to NHL94 SNES ROM.

    Strategy: in-place patching. For each team, we read the existing
    player records to know how much space is available, then write
    new records that fit within that space. Names are truncated if needed.
    """

    def __init__(self, rom_path: str, output_path: str):
        self.rom_path = rom_path
        self.output_path = output_path
        self.data: Optional[bytearray] = None
        self.reader = NHL94SNESRomReader(rom_path)

    def load(self) -> bool:
        """Load ROM data for writing."""
        if not self.reader.load():
            return False

        # Make a writable copy
        if self.reader.data:
            self.data = bytearray(self.reader.data)
            return True
        return False

    def _get_team_player_region(self, team_index: int) -> Tuple[int, int]:
        """Get the file offset and total byte size of a team's player region.

        Returns (start_offset, total_bytes) where start_offset is the
        first byte of the first player record and total_bytes includes
        all player records + the 2-byte terminator.
        """
        file_off = self.reader._read_team_pointer(team_index)
        if file_off is None or not self.data:
            return 0, 0

        # Skip header
        start = self.reader._skip_team_header(file_off)
        offset = start

        while offset < len(self.data) - 1:
            length = self.data[offset] | (self.data[offset + 1] << 8)
            if length < 3:  # Terminator
                offset += 2  # Include terminator in region
                break
            offset += length + STATS_SIZE

        return start, offset - start

    def write_team_roster(
        self,
        team_index: int,
        players: List[NHL94PlayerRecord],
    ) -> bool:
        """Write player records for a team, fitting within existing space.

        Names are truncated if they don't fit. Excess space is zero-filled.
        """
        if not self.data or team_index >= TEAM_COUNT:
            return False

        start, region_size = self._get_team_player_region(team_index)
        if region_size == 0:
            return False

        offset = start
        end = start + region_size

        for player in players:
            # Calculate space needed: 2 (length) + name_len + 8 (stats)
            # Plus we need at least 2 bytes left for the terminator
            max_name_for_record = (end - offset) - 2 - STATS_SIZE - 2
            if max_name_for_record < 1:
                break  # No room for more players

            # Truncate name to fit
            name = player.name[:max_name_for_record]
            name_bytes = name.encode("ascii", errors="replace")
            name_len = len(name_bytes)

            # Write 2-byte LE length (includes the 2 length bytes)
            total_len = name_len + 2
            self.data[offset] = total_len & 0xFF
            self.data[offset + 1] = (total_len >> 8) & 0xFF
            offset += 2

            # Write name
            for i, b in enumerate(name_bytes):
                self.data[offset + i] = b
            offset += name_len

            # Write 8 stat bytes
            offset = self._write_player_stats(player, offset)

        # Write terminator (0x02 0x00 = empty string)
        if offset + 2 <= end:
            self.data[offset] = 0x02
            self.data[offset + 1] = 0x00
            offset += 2

        # Zero-fill any remaining space in the region
        while offset < end:
            self.data[offset] = 0x00
            offset += 1

        return True

    def _write_player_stats(self, player: NHL94PlayerRecord, offset: int) -> int:
        """Write 8 stat bytes for a player. Returns new offset."""
        if not self.data or offset + STATS_SIZE > len(self.data):
            return offset

        attrs = player.attributes

        # Byte 0: Jersey number (BCD)
        jersey = max(1, min(99, player.jersey_number))
        self.data[offset] = ((jersey // 10) << 4) | (jersey % 10)
        offset += 1

        # Byte 1: Weight class (0-14) | Agility (0-6)
        self.data[offset] = encode_weight_nibble(player.weight_class, attrs.agility)
        offset += 1

        # Byte 2: Speed (0-6) | Off. Awareness (0-6)
        self.data[offset] = encode_nibble(attrs.speed, attrs.off_awareness)
        offset += 1

        # Byte 3: Def. Awareness (0-6) | Shot Power (0-6)
        self.data[offset] = encode_nibble(attrs.def_awareness, attrs.shot_power)
        offset += 1

        # Byte 4: Checking (0-6) | Handedness (0=L, 1=R)
        self.data[offset] = encode_nibble(attrs.checking, player.handedness)
        offset += 1

        # Byte 5: Stick Handling (0-6) | Shot Accuracy (0-6)
        self.data[offset] = encode_nibble(attrs.stick_handling, attrs.shot_accuracy)
        offset += 1

        # Byte 6: Endurance (0-6) | Roughness (0-6)
        self.data[offset] = encode_nibble(attrs.endurance, attrs.roughness)
        offset += 1

        # Byte 7: Pass Accuracy (0-6) | Aggression (0-6)
        self.data[offset] = encode_nibble(attrs.pass_accuracy, attrs.aggression)
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
