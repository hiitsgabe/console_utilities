"""ROM writer for PES 6 PS2 patcher.

Writes patched team names and abbreviations into a copy of the PES 6 PS2 ISO.
Names are null-terminated UTF-8 strings written at absolute ISO offsets
determined by the rom_reader.

The writer copies the original ISO to an output path, then patches in-place
using r+b mode. Zero-fills each slot's budget region before writing to clear
old data.
"""

import shutil
from typing import BinaryIO, Optional

import struct
from services.pes6_ps2_patcher.models import PES6TeamSlot, ISO_SECTOR_SIZE


def _truncate_utf8(text: str, max_bytes: int) -> bytes:
    """Encode text as UTF-8, truncating to at most max_bytes without splitting multi-byte chars."""
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return encoded
    # Truncate and avoid splitting a multi-byte character
    truncated = encoded[:max_bytes]
    # Walk back if we landed in the middle of a multi-byte sequence
    while truncated and (truncated[-1] & 0xC0) == 0x80:
        truncated = truncated[:-1]
    # If the last byte is a multi-byte lead but we cut its continuation bytes, remove it too
    if truncated and truncated[-1] >= 0xC0:
        # Check if the lead byte expects more continuation bytes than remain
        last = truncated[-1]
        if last >= 0xF0:
            needed = 4
        elif last >= 0xE0:
            needed = 3
        elif last >= 0xC0:
            needed = 2
        else:
            needed = 1
        # Count how many bytes this char actually has in our truncated result
        char_start = len(truncated) - 1
        if len(encoded) < char_start + needed:
            truncated = truncated[:char_start]
        elif char_start + needed > len(truncated):
            truncated = truncated[:char_start]
    return truncated


class PES6RomWriter:
    """Writes patched data into a copy of the PES 6 PS2 ISO."""

    def __init__(self, input_path: str, output_path: str):
        """Copy ISO to output path and open for patching.

        Args:
            input_path: Path to the original PES 6 ISO.
            output_path: Path where the patched copy will be written.
        """
        shutil.copy2(input_path, output_path)
        self._output_path = output_path
        self._fh: Optional[BinaryIO] = open(output_path, "r+b")

    def write_team_name(self, slot: PES6TeamSlot, new_name: str, new_abbr: str):
        """Write new name and abbreviation to a team slot.

        1. Encode name as UTF-8
        2. Truncate at valid UTF-8 boundary if too long for budget
        3. Zero-fill the slot's name region
        4. Write the name bytes
        5. Same for abbreviation

        Args:
            slot: The team slot (with offsets/budgets from rom_reader).
            new_name: New team name string.
            new_abbr: New team abbreviation string.
        """
        if self._fh is None:
            raise RuntimeError("Writer already finalized")

        # Write name
        name_bytes = _truncate_utf8(new_name, slot.name_budget - 1)
        self._fh.seek(slot.name_offset)
        self._fh.write(b"\x00" * slot.name_budget)
        self._fh.seek(slot.name_offset)
        self._fh.write(name_bytes)

        # Write abbreviation
        abbr_bytes = _truncate_utf8(new_abbr, slot.abbr_budget - 1)
        self._fh.seek(slot.abbr_offset)
        self._fh.write(b"\x00" * slot.abbr_budget)
        self._fh.seek(slot.abbr_offset)
        self._fh.write(abbr_bytes)

    # -----------------------------------------------------------------------
    # Player name patching in 0_TEXT.AFS file 485
    # -----------------------------------------------------------------------
    # File 485 is uncompressed, 48-byte records, 6339 players.
    # Record layout: 16B metadata + 32B ASCII name (null-padded).
    # Players are alphabetically sorted by name.
    # The metadata bytes 8-11 contain a pointer/ID that links to attributes.
    # Players are grouped by team via these pointer values.
    AFS_0TEXT_LBA = 14741
    # All language variants of the name table (485-488, 490-492)
    # Patch all of them since we don't know which one the game reads
    NAME_TABLE_ENTRIES = [485, 486, 487, 488, 490, 491, 492]
    NAME_RECORD_SIZE = 48
    NAME_OFFSET_IN_RECORD = 16
    NAME_MAX_BYTES = 32
    NAME_TABLE_HEADER = 0x20  # 32-byte file header before records

    def write_player_names(self, player_names, record_indices):
        """Write player names to specific records in the name table.

        Args:
            player_names: List of new player name strings.
            record_indices: List of record indices (0-based) to write to.
                Must be same length as player_names.
        """
        if self._fh is None:
            raise RuntimeError("Writer already finalized")

        # Read AFS table
        self._fh.seek(self.AFS_0TEXT_LBA * ISO_SECTOR_SIZE)
        afs_header = self._fh.read(8)
        num_files = struct.unpack_from("<I", afs_header, 4)[0]
        afs_table = self._fh.read(num_files * 8)

        # Write to ALL language variants of the name table
        for entry_idx in self.NAME_TABLE_ENTRIES:
            if entry_idx >= num_files:
                continue

            entry_off = struct.unpack_from(
                "<I", afs_table, entry_idx * 8
            )[0]
            file_base = self.AFS_0TEXT_LBA * ISO_SECTOR_SIZE + entry_off

            for name, rec_idx in zip(player_names, record_indices):
                rec_off = (
                    file_base
                    + self.NAME_TABLE_HEADER
                    + rec_idx * self.NAME_RECORD_SIZE
                    + self.NAME_OFFSET_IN_RECORD
                )
                name_bytes = _truncate_utf8(name, self.NAME_MAX_BYTES - 1)

                self._fh.seek(rec_off)
                self._fh.write(b"\x00" * self.NAME_MAX_BYTES)
                self._fh.seek(rec_off)
                self._fh.write(name_bytes)

    # -----------------------------------------------------------------------
    # League name patching in OVER.AFS
    # -----------------------------------------------------------------------
    # League names are in OVER.AFS entries [2] and [4] as 84-byte records:
    #   - Two copies of the name (display + short), null-padded
    #   - Records: 0=International, 1=England, 2=France, 3=Germany,
    #              4=Serie A, 5=Eredivisie, 6=Liga Española,
    #              7=League A, 8=League B, 9=League C, 10=League D
    OVER_AFS_LBA = 8241
    LEAGUE_RECORD_SIZE = 84
    # Each record fits two name copies + nulls + padding within 84 bytes
    # Max name length = (84 - 2) // 2 = 41 bytes per copy
    LEAGUE_NAME_MAX = 41

    # Internal offsets of league[0] within each OVER entry
    _OVER2_LEAGUE_OFF = 0x099C80
    _OVER4_LEAGUE_OFF = 0x123C90

    def write_league_name(self, league_index: int, new_name: str):
        """Write a league name to both OVER.AFS copies.

        Args:
            league_index: 0-10 (0=International, 1=England, 2=France, etc.)
            new_name: New league name (ASCII-safe, special chars stripped).
        """
        if self._fh is None:
            raise RuntimeError("Writer already finalized")

        # Read OVER.AFS header to get entry offsets
        self._fh.seek(self.OVER_AFS_LBA * ISO_SECTOR_SIZE)
        afs_header = self._fh.read(8)
        import struct

        num_files = struct.unpack_from("<I", afs_header, 4)[0]
        afs_table = self._fh.read(num_files * 8)

        name_bytes = _truncate_utf8(new_name, self.LEAGUE_NAME_MAX - 1)

        for entry_idx, base_off in [
            (2, self._OVER2_LEAGUE_OFF),
            (4, self._OVER4_LEAGUE_OFF),
        ]:
            entry_off = struct.unpack_from("<I", afs_table, entry_idx * 8)[0]
            abs_base = self.OVER_AFS_LBA * ISO_SECTOR_SIZE + entry_off + base_off
            record_off = abs_base + league_index * self.LEAGUE_RECORD_SIZE

            # First read original record to preserve any trailing data
            self._fh.seek(record_off)
            original = self._fh.read(self.LEAGUE_RECORD_SIZE)

            # Build new record: name\0 + name\0 + padding
            new_record = bytearray(self.LEAGUE_RECORD_SIZE)
            # First copy at byte 0
            new_record[: len(name_bytes)] = name_bytes
            # null at len(name_bytes) is already 0
            # Second copy right after first null
            second_start = len(name_bytes) + 1
            new_record[second_start : second_start + len(name_bytes)] = name_bytes
            # Rest stays zero-padded

            self._fh.seek(record_off)
            self._fh.write(bytes(new_record))

    # -----------------------------------------------------------------------
    # E_TEXT.AFS league name patching (compressed .str files)
    # -----------------------------------------------------------------------
    E_TEXT_AFS_LBA = 224414

    # E_TEXT entries that contain league name strings
    _ETEXT_LEAGUE_ENTRIES = [2, 191]

    # Original league names → will be replaced in-place (same byte length)
    _LEAGUE_NAME_MAP = {
        1: b"England League",  # 14 bytes
        2: b"Ligue 1",  # 7 bytes (can't fit much)
        3: b"German League",  # 13 bytes
        4: b"Serie A",  # 7 bytes
        5: b"Eredivisie",  # 10 bytes
    }

    def write_etext_league_name(self, league_index: int, new_name: str):
        """Replace a league name in E_TEXT.AFS compressed string files.

        The new name is truncated/padded to match the original's exact byte
        length, since the strings are packed (no room to grow).
        """
        if self._fh is None:
            raise RuntimeError("Writer already finalized")

        original = self._LEAGUE_NAME_MAP.get(league_index)
        if not original:
            return

        import struct
        import zlib

        new_bytes = _truncate_utf8(new_name, len(original))
        # Pad with spaces to exact original length if shorter
        if len(new_bytes) < len(original):
            new_bytes = new_bytes + b" " * (len(original) - len(new_bytes))

        # Read E_TEXT AFS table
        self._fh.seek(self.E_TEXT_AFS_LBA * ISO_SECTOR_SIZE)
        afs_header = self._fh.read(8)
        num_files = struct.unpack_from("<I", afs_header, 4)[0]
        afs_table = self._fh.read(num_files * 8)

        for entry_idx in self._ETEXT_LEAGUE_ENTRIES:
            if entry_idx >= num_files:
                continue

            entry_off, entry_sz = struct.unpack_from(
                "<II", afs_table, entry_idx * 8
            )
            abs_entry = self.E_TEXT_AFS_LBA * ISO_SECTOR_SIZE + entry_off

            # Read compressed entry
            self._fh.seek(abs_entry)
            raw = self._fh.read(entry_sz)

            if len(raw) < 34 or raw[32:34] != b"\x78\xda":
                continue  # Not compressed in expected format

            # Decompress
            try:
                decompressed = bytearray(zlib.decompress(raw[32:]))
            except zlib.error:
                continue

            # Replace all occurrences of the original name
            pos = 0
            replaced = False
            while True:
                pos = decompressed.find(original, pos)
                if pos < 0:
                    break
                decompressed[pos : pos + len(original)] = new_bytes
                pos += len(new_bytes)
                replaced = True

            if not replaced:
                continue

            # Recompress
            recompressed = zlib.compress(bytes(decompressed), 9)

            # Build new entry: 32-byte header + recompressed data
            new_entry = bytearray(raw[:32])
            # Update decompressed size in header (should be same)
            struct.pack_into("<I", new_entry, 8, len(decompressed))
            new_entry.extend(recompressed)

            # Check allocated space: gap to next entry
            if entry_idx + 1 < num_files:
                next_off = struct.unpack_from(
                    "<I", afs_table, (entry_idx + 1) * 8
                )[0]
                allocated = next_off - entry_off
            else:
                allocated = entry_sz  # Last entry, use exact size

            if len(new_entry) <= allocated:
                self._fh.seek(abs_entry)
                self._fh.write(bytes(new_entry))
                # Zero-pad remainder of allocated space
                remaining = allocated - len(new_entry)
                if remaining > 0:
                    self._fh.write(b"\x00" * remaining)
                # Update entry size in AFS table
                afs_table_off = (
                    self.E_TEXT_AFS_LBA * ISO_SECTOR_SIZE
                    + 8
                    + entry_idx * 8
                    + 4
                )
                self._fh.seek(afs_table_off)
                self._fh.write(struct.pack("<I", len(new_entry)))

    # -----------------------------------------------------------------------
    # Player roster patching in 0_TEXT.AFS file 55
    # -----------------------------------------------------------------------
    # File 55 = 32B file header + 80B data header + zlib(decrypted OF data)
    # Player names are UTF-16LE within the decompressed data.
    # We decompress, replace names, recompress, and write back.
    FILE55_INDEX = 55
    FILE55_HEADER_SIZE = 32
    FILE55_DATA_HEADER_SIZE = 80

    def write_player_roster(self, league_data, on_progress=None):
        """Replace player names in file 55 for all teams in league_data.

        File 55 contains zlib-compressed player records (124 bytes each).
        Uses raw deflate recompression with manual Adler-32 to produce
        output compatible with the game's custom decompressor.
        """
        if self._fh is None:
            raise RuntimeError("Writer already finalized")

        import zlib
        import unicodedata

        def clean(name):
            nfkd = unicodedata.normalize("NFKD", name)
            return "".join(c for c in nfkd if not unicodedata.combining(c))

        # Read AFS table
        self._fh.seek(self.AFS_0TEXT_LBA * ISO_SECTOR_SIZE)
        afs_header = self._fh.read(8)
        num_files = struct.unpack_from("<I", afs_header, 4)[0]
        afs_table = self._fh.read(num_files * 8)

        entry_off = struct.unpack_from(
            "<I", afs_table, self.FILE55_INDEX * 8
        )[0]
        entry_sz = struct.unpack_from(
            "<I", afs_table, self.FILE55_INDEX * 8 + 4
        )[0]
        if self.FILE55_INDEX + 1 < num_files:
            next_off = struct.unpack_from(
                "<I", afs_table, (self.FILE55_INDEX + 1) * 8
            )[0]
            allocated = next_off - entry_off
        else:
            allocated = entry_sz

        abs_entry = self.AFS_0TEXT_LBA * ISO_SECTOR_SIZE + entry_off

        # Read file 55
        self._fh.seek(abs_entry)
        raw55 = bytearray(self._fh.read(entry_sz))

        # Decompress using raw deflate to find exact stream boundaries
        skip = self.FILE55_HEADER_SIZE + self.FILE55_DATA_HEADER_SIZE
        comp_data = raw55[skip:]

        try:
            dobj = zlib.decompressobj(-15)  # Raw deflate
            dec_data = bytearray(dobj.decompress(comp_data[2:]))  # Skip 78 DA
            unused = dobj.unused_data
        except zlib.error:
            return

        deflate_size = len(comp_data) - 2 - len(unused)
        # Tail = everything after zlib header(2) + deflate + adler32(4)
        tail_data = comp_data[2 + deflate_size + 4:]

        if on_progress:
            on_progress(0.1, "Preparing players...")

        # Collect all ESPN player names
        espn_players = []
        for tr in league_data.teams:
            players = tr.players if hasattr(tr, "players") else []
            for p in players:
                pname = p.name if hasattr(p, "name") else str(p)
                espn_players.append(clean(pname))

        # Write ESPN players to the correct club team record slots.
        # Club teams start at record 1472 (after 64 national teams × 23).
        # Each club team has 32 record slots.
        # ESPN team 0 → club slot 0 (records 1472-1503)
        # ESPN team 1 → club slot 1 (records 1504-1535), etc.
        RECORD_SIZE = 124
        NAME_SIZE = 32
        CLUB_START_REC = 1472  # 64 national teams × 23 players
        CLUB_TEAM_SIZE = 32

        replaced = 0
        for team_idx, tr in enumerate(league_data.teams):
            players = tr.players if hasattr(tr, "players") else []
            base_rec = CLUB_START_REC + team_idx * CLUB_TEAM_SIZE

            for j, player in enumerate(players[:CLUB_TEAM_SIZE]):
                rec = base_rec + j
                rec_off = rec * RECORD_SIZE
                if rec_off + NAME_SIZE > len(dec_data):
                    break

                pname = player.name if hasattr(player, "name") else str(player)
                full = clean(pname)
                # Use last name to keep compressed size small
                parts = full.split()
                last = (parts[-1] if parts else full)[:15]
                new_bytes = last.encode("utf-16-le")

                dec_data[rec_off:rec_off + NAME_SIZE] = b"\x00" * NAME_SIZE
                wlen = min(len(new_bytes), NAME_SIZE - 2)
                dec_data[rec_off:rec_off + wlen] = new_bytes[:wlen]
                replaced += 1

        if on_progress:
            on_progress(0.7, f"Replaced {replaced} names, compressing...")

        # Recompress using raw deflate + manual Adler-32
        cobj = zlib.compressobj(9, zlib.DEFLATED, -15)
        new_deflate = cobj.compress(bytes(dec_data)) + cobj.flush()
        new_adler = struct.pack(
            ">I", zlib.adler32(bytes(dec_data)) & 0xFFFFFFFF
        )

        # Build new main stream: header(2) + deflate + adler(4)
        new_main = b"\x78\xda" + new_deflate + new_adler

        # The compressed data has sections AFTER the main stream
        # (squad assignments, team config, etc.) at fixed offsets.
        # We MUST pad the main stream to its original size so these
        # sections stay at their original positions.
        comp_size = struct.unpack_from("<I", raw55, 32 + 52)[0]

        if len(new_main) <= comp_size:
            # Pad to exact original compressed size
            padded_main = new_main + b"\x00" * (comp_size - len(new_main))

            # Replace ONLY the main stream, keep all sections intact
            raw55[skip : skip + comp_size] = padded_main

            # Update comp_size field to actual new size
            struct.pack_into("<I", raw55, 32 + 52, len(new_main))

            # Write back — NO other header changes needed
            self._fh.seek(abs_entry)
            self._fh.write(bytes(raw55))

            if on_progress:
                on_progress(1.0, f"Done! {replaced} players patched")
        else:
            if on_progress:
                on_progress(
                    1.0,
                    f"Warning: compressed data too large "
                    f"({len(new_main):,} > {comp_size:,})",
                )

    def finalize(self):
        """Flush and close the output file."""
        if self._fh is not None:
            self._fh.flush()
            self._fh.close()
            self._fh = None
