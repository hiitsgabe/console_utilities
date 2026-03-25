"""Write updated player data and team names to PES6 PS2 ISO."""

import os
import shutil
import struct
import zlib
from typing import List

from .models import PES6PlayerRecord, PES6PlayerAttributes, RomInfo


class RomWriter:
    """Writes player records and team names to a PES6 PS2 ISO."""

    RECORD_SIZE = 124
    WESYS_MAGIC = 0x00000600
    SLPM_TEAM_NAME_OFFSET = 0x2BEC00

    def __init__(self, rom_info: RomInfo, output_path: str):
        self.rom_info = rom_info
        self.output_path = output_path
        self._file = None

    def begin(self):
        """Copy source ISO to output path and open for writing."""
        if self.rom_info.path != self.output_path:
            shutil.copy2(self.rom_info.path, self.output_path)
        self._file = open(self.output_path, "r+b")

    def write_players_batch(self, players: List[PES6PlayerRecord]):
        """Write multiple players to BOTH base and editable player DBs."""
        if self._file is None:
            raise RuntimeError("Call begin() first")

        # Write to BOTH base and editable DBs
        self._write_to_db(
            players, self.rom_info.file35_offset, self.rom_info.file35_size
        )
        if self.rom_info.base_db_offset and self.rom_info.base_db_size:
            self._write_to_db(
                players, self.rom_info.base_db_offset, self.rom_info.base_db_size
            )

    def _write_to_db(
        self, players: List[PES6PlayerRecord], db_offset: int, db_size: int
    ):
        """Write player records into a DB file, preserving multi-section structure.

        WESYS containers have a main zlib stream followed by additional sub-streams.
        We only modify the main stream and preserve everything after it byte-for-byte.
        """
        self._file.seek(db_offset)
        container = bytearray(self._file.read(db_size))
        zlib_start = self._find_zlib_start(container)

        # Read the original compressed stream size from header at 0x54
        orig_comp_size = struct.unpack_from("<I", container, 0x54)[0]

        # Decompress only the main stream (orig_comp_size bytes from zlib_start)
        main_stream = bytes(container[zlib_start : zlib_start + orig_comp_size])
        decompressed = bytearray(zlib.decompress(main_stream))

        for player in players:
            rec_offset = player.file35_index * self.RECORD_SIZE
            if 0 <= rec_offset and rec_offset + self.RECORD_SIZE <= len(decompressed):
                self._write_record(decompressed, rec_offset, player)

        # Recompress with max compression + memLevel to fit within original space
        obj = zlib.compressobj(level=9, method=zlib.DEFLATED, wbits=15, memLevel=9)
        compressed = obj.compress(bytes(decompressed)) + obj.flush()

        # Find the next sub-stream to know max available space
        max_space = orig_comp_size
        for probe in range(
            zlib_start + orig_comp_size,
            min(zlib_start + orig_comp_size + 256, db_size - 1),
        ):
            if container[probe] == 0x78 and container[probe + 1] in (
                0xDA,
                0x9C,
                0x5E,
                0x01,
            ):
                max_space = probe - zlib_start
                break

        if len(compressed) > max_space:
            # Try truncating names further to fit
            for max_name_len in [10, 8, 6]:
                for player in players:
                    rec_offset = player.file35_index * self.RECORD_SIZE
                    if 0 <= rec_offset and rec_offset + self.RECORD_SIZE <= len(
                        decompressed
                    ):
                        name = player.name[:max_name_len].encode("utf-16-le")
                        name_field = name + b"\x00" * (32 - len(name))
                        decompressed[rec_offset : rec_offset + 32] = name_field
                obj2 = zlib.compressobj(
                    level=9, method=zlib.DEFLATED, wbits=15, memLevel=9
                )
                compressed = obj2.compress(bytes(decompressed)) + obj2.flush()
                if len(compressed) <= max_space:
                    break
            else:
                raise ValueError(
                    f"Recompressed stream too large ({len(compressed)} > {max_space})"
                )

        # Write recompressed main stream, pad to fill original space
        container[zlib_start : zlib_start + orig_comp_size] = (
            compressed + b"\x00" * (orig_comp_size - len(compressed))
            if len(compressed) <= orig_comp_size
            else compressed[:orig_comp_size]
        )
        # If we overflowed into padding area, write the overflow
        if len(compressed) > orig_comp_size:
            overflow = len(compressed) - orig_comp_size
            container[
                zlib_start + orig_comp_size : zlib_start + orig_comp_size + overflow
            ] = compressed[orig_comp_size:]

        # Update compressed size at 0x54
        struct.pack_into("<I", container, 0x54, len(compressed))

        self._file.seek(db_offset)
        self._file.write(bytes(container))

    def write_team_names(self, team_names: list):
        """Write team names to club team slots in the SLPM executable.

        Args:
            team_names: List of (name, abbreviation) tuples in order.
        """
        if self._file is None:
            raise RuntimeError("Call begin() first")

        club_start = self._find_club_name_table()
        if club_start is None:
            return

        entries = self._scan_name_entries(club_start, max_entries=130)

        for i, (new_name, new_abbrev) in enumerate(team_names):
            if i >= len(entries):
                break
            offset, name_size, abbrev_offset = entries[i]

            max_name_len = name_size - 1
            name_bytes = new_name[:max_name_len].encode("ascii", errors="replace")
            name_field = name_bytes + b"\x00" * (name_size - len(name_bytes))
            self._file.seek(offset)
            self._file.write(name_field)

            abbrev_bytes = new_abbrev[:7].encode("ascii", errors="replace")
            abbrev_field = abbrev_bytes + b"\x00" * (8 - len(abbrev_bytes))
            self._file.seek(abbrev_offset)
            self._file.write(abbrev_field)

    def _find_club_name_table(self) -> int:
        """Find the start of club team names in the SLPM."""
        self._file.seek(self.rom_info.slpm_offset)
        slpm_data = self._file.read(4_000_000)
        idx = slpm_data.find(b"Arsenal\x00")
        if idx != -1:
            return self.rom_info.slpm_offset + idx
        return None

    def _scan_name_entries(self, start: int, max_entries: int = 130):
        """Scan variable-width name entries: (offset, name_field_size, abbrev_offset)."""
        self._file.seek(start)
        raw = self._file.read(32 * max_entries * 2)
        entries = []
        pos = 0

        for _ in range(max_entries):
            if pos + 24 > len(raw):
                break
            null_pos = raw.find(b"\x00", pos)
            if null_pos == -1 or null_pos - pos > 30:
                break
            name_len = null_pos - pos
            name_field_size = max(16, ((name_len + 8) // 8) * 8)
            abbrev_pos = pos + name_field_size
            if abbrev_pos + 8 > len(raw):
                break
            entries.append((start + pos, name_field_size, start + abbrev_pos))
            pos = abbrev_pos + 8

        return entries

    def finalize(self):
        """Flush and close the output file."""
        if self._file:
            self._file.flush()
            os.fsync(self._file.fileno())
            self._file.close()
            self._file = None

    def _write_record(self, data: bytearray, offset: int, player: PES6PlayerRecord):
        """Write player name and position into a 124-byte record.

        Modifies: name, shirt name, nameEdited flag, registered position.
        Stats, shirt number, and other fields are preserved from original.
        """
        # Bytes 0-31: Name (UTF-16LE, 16 chars max including null)
        name_encoded = player.name[:15].encode("utf-16-le")
        name_field = name_encoded + b"\x00" * (32 - len(name_encoded))
        data[offset : offset + 32] = name_field

        # Bytes 32-47: Shirt name (ASCII, 16 bytes)
        shirt_encoded = player.shirt_name[:15].encode("ascii", errors="replace")
        shirt_field = shirt_encoded + b"\x00" * (16 - len(shirt_encoded))
        data[offset + 32 : offset + 48] = shirt_field

        # Byte 51 (stats offset 3, bit 0): nameEdited flag — MUST be 1
        data[offset + 51] = data[offset + 51] | 0x01

        # Byte 54 (stats offset 6): registered position in bits 4-7
        data[offset + 54] = (data[offset + 54] & 0x0F) | ((player.position & 0xF) << 4)

    def _find_zlib_start(self, container: bytearray) -> int:
        """Find zlib stream start in WESYS container."""
        for start in range(0x20, min(0x100, len(container))):
            if container[start] == 0x78 and container[start + 1] in (
                0x01,
                0x5E,
                0x9C,
                0xDA,
            ):
                return start
        raise ValueError("Could not find zlib stream in WESYS container")
