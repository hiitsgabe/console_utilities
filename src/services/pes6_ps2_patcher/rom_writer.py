"""Write updated player data and team names to PES6 PS2 ISO."""

import os
import shutil
import struct
import zlib
from typing import List

from .models import (
    PES6PlayerRecord,
    PES6PlayerAttributes,
    RomInfo,
    ATTR_OFFSETS,
    SMALL_FIELD_OFFSETS,
    IDENTITY_OFFSETS,
    FLAG_OFFSETS,
)


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
            team_names: List of (index, name, abbreviation) tuples.
                        index is the position within the club name table.
        """
        if self._file is None:
            raise RuntimeError("Call begin() first")

        club_start = self._find_club_name_table()
        if club_start is None:
            return

        entries = self._scan_name_entries(club_start, max_entries=200)

        for entry_index, new_name, new_abbrev in team_names:
            if entry_index >= len(entries):
                continue
            offset, name_size, abbrev_offset = entries[entry_index]

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

    def _write_stat_field(
        self,
        data: bytearray,
        record_start: int,
        offset: int,
        shift: int,
        mask: int,
        value: int,
    ):
        """Write a bit-packed value into the player record.

        All offsets are relative to byte 48 of the record.
        Reads 16-bit LE from [abs_off-1, abs_off], modifies field, writes back.
        """
        abs_off = record_start + 48 + offset
        # Read 16-bit LE
        lo = data[abs_off - 1] if abs_off > 0 else 0
        hi = data[abs_off] if abs_off < len(data) else 0
        existing = lo | (hi << 8)
        # Clear field bits, set new value
        existing = (existing & ~(mask << shift)) | ((value & mask) << shift)
        # Write back
        if abs_off > 0:
            data[abs_off - 1] = existing & 0xFF
        if abs_off < len(data):
            data[abs_off] = (existing >> 8) & 0xFF

    def _write_record(self, data: bytearray, offset: int, player: PES6PlayerRecord):
        """Write a complete player record including all attributes."""
        # Bytes 0-31: Name (UTF-16LE, 16 chars max including null)
        name_encoded = player.name[:15].encode("utf-16-le")
        name_field = name_encoded + b"\x00" * (32 - len(name_encoded))
        data[offset : offset + 32] = name_field

        # Bytes 32-47: Shirt name (ASCII, 16 bytes)
        shirt_encoded = player.shirt_name[:15].encode("ascii", errors="replace")
        shirt_field = shirt_encoded + b"\x00" * (16 - len(shirt_encoded))
        data[offset + 32 : offset + 48] = shirt_field

        # Registered position
        pos_off, pos_shift, pos_mask = IDENTITY_OFFSETS["regPos"]
        self._write_stat_field(
            data, offset, pos_off, pos_shift, pos_mask, player.position
        )

        # Nationality
        nat_off, nat_shift, nat_mask = IDENTITY_OFFSETS["nationality"]
        self._write_stat_field(
            data, offset, nat_off, nat_shift, nat_mask, player.nationality
        )

        # Age (stored as age - 15)
        age_off, age_shift, age_mask = IDENTITY_OFFSETS["age"]
        age_stored = max(0, min(31, player.age - 15))
        self._write_stat_field(data, offset, age_off, age_shift, age_mask, age_stored)

        # Height (stored as height - 148)
        h_off, h_shift, h_mask = IDENTITY_OFFSETS["height"]
        h_stored = max(0, min(63, player.height - 148))
        self._write_stat_field(data, offset, h_off, h_shift, h_mask, h_stored)

        # Weight (raw kg)
        w_off, w_shift, w_mask = IDENTITY_OFFSETS["weight"]
        self._write_stat_field(
            data, offset, w_off, w_shift, w_mask, min(127, player.weight)
        )

        # All 26 core attributes (7-bit, 1-99)
        if player.attributes:
            for attr_name, (a_off, a_shift, a_mask) in ATTR_OFFSETS.items():
                value = getattr(player.attributes, attr_name, 50)
                value = max(1, min(99, value))
                self._write_stat_field(data, offset, a_off, a_shift, a_mask, value)

            # Small fields: consistency, condition
            c_off, c_shift, c_mask = SMALL_FIELD_OFFSETS["consistency"]
            self._write_stat_field(
                data,
                offset,
                c_off,
                c_shift,
                c_mask,
                max(0, min(7, player.attributes.consistency)),
            )
            cond_off, cond_shift, cond_mask = SMALL_FIELD_OFFSETS["condition"]
            self._write_stat_field(
                data,
                offset,
                cond_off,
                cond_shift,
                cond_mask,
                max(0, min(7, player.attributes.condition)),
            )

        # Flags written last so they are not clobbered by attribute bit-writes:
        # nameEdited, shirtEdited, abilityEdited
        for flag_name, (f_off, f_shift) in FLAG_OFFSETS.items():
            abs_off = offset + 48 + f_off
            data[abs_off] = data[abs_off] | (1 << f_shift)

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
