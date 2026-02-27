"""EA TDB / BIGF / RefPack library for NHL 07 PSP.

Handles the archive stack: ISO -> db.viv (BIGF) -> *.tdb (RefPack) -> tables.

RefPack (QFS) compression/decompression is EA's standard format used across
many EA Sports titles. BIGF is their standard archive container.

TDB is a structured database format with bit-packed fields, used for
player bios, attributes, roster assignments, and team data.

References:
  - RefPack/QFS: https://simswiki.info/wiki.php?title=DBPF_Compression
  - BIGF: EA archive format (header + file table + data)
  - TDB: Reverse-engineered from nhl2007.tdb / nhlbioatt.tdb / nhlrost.tdb
"""

import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ──────────────────────────────────────────────────────────────
# RefPack (QFS) Compression / Decompression
# ──────────────────────────────────────────────────────────────


def refpack_decompress(data: bytes) -> bytes:
    """Decompress RefPack/QFS compressed data.

    Header: 0x10 0xFB + 3-byte big-endian decompressed size.
    """
    if len(data) < 5 or data[0] != 0x10 or data[1] != 0xFB:
        raise ValueError("Not RefPack data (missing 0x10 0xFB header)")

    decompressed_size = (data[2] << 16) | (data[3] << 8) | data[4]
    out = bytearray()
    pos = 5

    while pos < len(data):
        # Control byte determines the operation
        b0 = data[pos]

        if b0 < 0x80:
            # 2-byte command: literal + copy
            if pos + 1 >= len(data):
                break
            b1 = data[pos + 1]
            pos += 2
            num_literal = b0 & 0x03
            num_copy = ((b0 & 0x1C) >> 2) + 3
            copy_offset = ((b0 & 0x60) << 3) + b1 + 1

        elif b0 < 0xC0:
            # 3-byte command
            if pos + 2 >= len(data):
                break
            b1 = data[pos + 1]
            b2 = data[pos + 2]
            pos += 3
            num_literal = ((b1 & 0xC0) >> 6) & 0x03
            num_copy = (b0 & 0x3F) + 4
            copy_offset = ((b1 & 0x3F) << 8) + b2 + 1

        elif b0 < 0xE0:
            # 4-byte command
            if pos + 3 >= len(data):
                break
            b1 = data[pos + 1]
            b2 = data[pos + 2]
            b3 = data[pos + 3]
            pos += 4
            num_literal = b0 & 0x03
            num_copy = ((b0 & 0x0C) << 6) + b3 + 5
            copy_offset = ((b0 & 0x10) << 12) + (b1 << 8) + b2 + 1

        elif b0 < 0xFC:
            # Literal-only command
            num_literal = ((b0 & 0x1F) << 2) + 4
            num_copy = 0
            copy_offset = 0
            pos += 1

        else:
            # End marker (0xFC-0xFF): 0-3 trailing literals
            num_literal = b0 & 0x03
            num_copy = 0
            copy_offset = 0
            pos += 1

        # Copy literal bytes from input
        if num_literal > 0:
            if pos + num_literal > len(data):
                num_literal = len(data) - pos
            out.extend(data[pos : pos + num_literal])
            pos += num_literal

        # Copy from output buffer (back-reference)
        if num_copy > 0:
            src = len(out) - copy_offset
            for _ in range(num_copy):
                if src >= 0 and src < len(out):
                    out.append(out[src])
                else:
                    out.append(0)
                src += 1

        if b0 >= 0xFC:
            break

    # Truncate or pad to exact size
    if len(out) > decompressed_size:
        out = out[:decompressed_size]

    return bytes(out)


def _is_encodable(length: int, offset: int) -> bool:
    """Check if a match is encodable in any RefPack command format."""
    if length <= 10 and offset <= 1024:
        return True
    if 4 <= length <= 67 and offset <= 16384:
        return True
    if 5 <= length <= 1028 and offset <= 131072:
        return True
    return False


def _emit_copy(out: bytearray, nl: int, lit_bytes: bytes, length: int, offset: int):
    """Emit a RefPack copy command with 0-3 attached literals."""
    if length <= 10 and offset <= 1024:
        # 2-byte command: length 3-10, offset 1-1024, 0-3 literals
        b0 = (nl & 0x03) | (((length - 3) & 0x07) << 2) | (((offset - 1) >> 3) & 0x60)
        b1 = (offset - 1) & 0xFF
        out.extend([b0, b1])
    elif length >= 4 and length <= 67 and offset <= 16384:
        # 3-byte command: length 4-67, offset 1-16384, 0-3 literals
        b0 = 0x80 | ((length - 4) & 0x3F)
        b1 = ((nl & 0x03) << 6) | (((offset - 1) >> 8) & 0x3F)
        b2 = (offset - 1) & 0xFF
        out.extend([b0, b1, b2])
    else:
        # 4-byte command: length 5-1028, offset 1-131072, 0-3 literals
        b0 = (
            0xC0
            | (nl & 0x03)
            | (((length - 5) >> 6) & 0x0C)
            | (((offset - 1) >> 12) & 0x10)
        )
        b1 = ((offset - 1) >> 8) & 0xFF
        b2 = (offset - 1) & 0xFF
        b3 = (length - 5) & 0xFF
        out.extend([b0, b1, b2, b3])

    out.extend(lit_bytes)


def refpack_compress(data: bytes) -> bytes:
    """Compress data using RefPack/QFS algorithm.

    Uses hash-chain LZ77 with lazy match evaluation for better
    compression ratio. Lazy matching checks if the next position has a
    longer match before committing, which typically saves 2-5%.
    """
    size = len(data)
    out = bytearray()

    # Header: 0x10 0xFB + 3-byte big-endian decompressed size
    out.extend(b"\x10\xFB")
    out.append((size >> 16) & 0xFF)
    out.append((size >> 8) & 0xFF)
    out.append(size & 0xFF)

    if size == 0:
        out.append(0xFC)
        return bytes(out)

    # Hash chain for 3-byte match finding
    HASH_BITS = 16
    HASH_MASK = (1 << HASH_BITS) - 1
    MAX_CHAIN = 128  # Deeper chain search for better matches
    MAX_OFFSET = 131072  # 0x20000
    MAX_MATCH = 1028

    head = [-1] * (HASH_MASK + 1)  # hash → most recent position
    chain = [-1] * size  # position → previous position with same hash
    inserted = bytearray(size)  # Track which positions were inserted

    def calc_hash(p: int) -> int:
        return ((data[p] << 8) ^ (data[p + 1] << 4) ^ data[p + 2]) & HASH_MASK

    def insert(p: int):
        if p + 2 >= size or inserted[p]:
            return
        inserted[p] = 1
        h = calc_hash(p)
        chain[p] = head[h]
        head[h] = p

    def find_match(p: int) -> Tuple[int, int]:
        """Find best (longest) match at position p. Returns (offset, length)."""
        if p + 2 >= size:
            return 0, 0
        h = calc_hash(p)
        cand = head[h]
        best_len = 2  # minimum useful = 3
        best_off = 0
        depth = 0
        d0, d1, d2 = data[p], data[p + 1], data[p + 2]

        while cand >= 0 and depth < MAX_CHAIN:
            off = p - cand
            if off > MAX_OFFSET:
                break
            if off >= 1 and data[cand] == d0 and data[cand + 1] == d1 and data[cand + 2] == d2:
                ml = 3
                limit = min(MAX_MATCH, size - p, size - cand)
                while ml < limit and data[cand + ml] == data[p + ml]:
                    ml += 1
                if ml > best_len:
                    best_len = ml
                    best_off = off
                    if ml >= MAX_MATCH:
                        break
            cand = chain[cand]
            depth += 1

        if best_len < 3:
            return 0, 0
        return best_off, best_len

    def flush_literals(out: bytearray, lit_start: int, pos: int) -> int:
        """Flush bulk pending literals (keeping 0-3 for the copy command)."""
        while pos - lit_start > 3:
            chunk = min(pos - lit_start, 112)
            chunk = (chunk // 4) * 4
            if chunk < 4:
                break
            out.append(0xE0 + ((chunk - 4) >> 2))
            out.extend(data[lit_start : lit_start + chunk])
            lit_start += chunk
        return lit_start

    pos = 0
    lit_start = 0  # Start of unprocessed literals in input

    while pos < size:
        offset, length = find_match(pos)

        if length < 3 or not _is_encodable(length, offset):
            insert(pos)
            pos += 1
            continue

        # Lazy matching: check if pos+1 has a strictly better match.
        # If so, emit pos as a literal and let the main loop pick up
        # the better match on the next iteration.
        if length < MAX_MATCH and pos + 1 < size - 2:
            insert(pos)
            next_offset, next_length = find_match(pos + 1)
            if (
                next_length > length + 1
                and _is_encodable(next_length, next_offset)
            ):
                # Better match at pos+1 — skip current as literal
                pos += 1
                continue

        # Flush bulk pending literals
        lit_start = flush_literals(out, lit_start, pos)

        # Emit copy command with 0-3 attached literals
        nl = pos - lit_start
        lit_bytes = data[lit_start:pos]
        _emit_copy(out, nl, lit_bytes, length, offset)

        # Insert matched positions into hash chain
        for i in range(pos, min(pos + length, size - 2)):
            insert(i)
        pos += length
        lit_start = pos

    # Flush remaining literals
    while size - lit_start >= 4:
        chunk = min(size - lit_start, 112)
        chunk = (chunk // 4) * 4
        if chunk < 4:
            break
        out.append(0xE0 + ((chunk - 4) >> 2))
        out.extend(data[lit_start : lit_start + chunk])
        lit_start += chunk

    # End marker with 0-3 trailing literals
    trail = size - lit_start
    out.append(0xFC + trail)
    if trail > 0:
        out.extend(data[lit_start:size])

    return bytes(out)


# ──────────────────────────────────────────────────────────────
# BIGF Archive
# ──────────────────────────────────────────────────────────────


@dataclass
class BigfEntry:
    """A file entry in a BIGF archive."""

    name: str
    offset: int
    size: int


def bigf_parse(archive: bytes) -> List[BigfEntry]:
    """Parse BIGF archive and return list of file entries."""
    if len(archive) < 16 or archive[:4] != b"BIGF":
        raise ValueError("Not a BIGF archive")

    _total_size = struct.unpack(">I", archive[4:8])[0]  # noqa: F841
    num_files = struct.unpack(">I", archive[8:12])[0]
    # header_size at archive[12:16] — not always reliable

    entries = []
    pos = 16
    for _ in range(num_files):
        if pos + 8 > len(archive):
            break
        file_offset = struct.unpack(">I", archive[pos : pos + 4])[0]
        file_size = struct.unpack(">I", archive[pos + 4 : pos + 8])[0]
        pos += 8
        # Read null-terminated filename
        name_start = pos
        while pos < len(archive) and archive[pos] != 0:
            pos += 1
        name = archive[name_start:pos].decode("ascii", errors="replace")
        pos += 1  # Skip null terminator
        entries.append(BigfEntry(name=name, offset=file_offset, size=file_size))

    return entries


def bigf_extract(archive: bytes, filename: str) -> Optional[bytes]:
    """Extract a single file from a BIGF archive by name (case-insensitive)."""
    entries = bigf_parse(archive)
    filename_lower = filename.lower()
    for entry in entries:
        if entry.name.lower() == filename_lower:
            return archive[entry.offset : entry.offset + entry.size]
    return None


def bigf_replace(archive: bytes, filename: str, new_data: bytes) -> bytes:
    """Replace a file in a BIGF archive, returning new archive bytes.

    Rebuilds the entire archive with the replaced file data.
    All other files are preserved byte-for-byte.
    """
    entries = bigf_parse(archive)
    filename_lower = filename.lower()
    file_contents = {}
    for entry in entries:
        if entry.name.lower() == filename_lower:
            file_contents[entry.name] = new_data
        else:
            file_contents[entry.name] = archive[entry.offset : entry.offset + entry.size]

    if filename not in file_contents:
        raise ValueError(f"File '{filename}' not found in BIGF archive")

    return bigf_build(entries, file_contents)


def bigf_replace_inplace(
    archive: bytearray, filename: str, new_data: bytes
) -> bool:
    """Replace a file's data in-place within the BIGF archive.

    Writes new_data at the file's ORIGINAL offset, preserving all other
    file offsets. If new_data is smaller, pads with zeros. Updates the
    file size in the BIGF directory entry.

    Returns True on success, False if new_data is too large to fit.
    """
    entries = bigf_parse(bytes(archive))
    filename_lower = filename.lower()

    # Find the target entry and its directory position
    target_entry = None
    target_dir_pos = -1
    pos = 16  # After BIGF header
    for entry in entries:
        if entry.name.lower() == filename_lower:
            target_entry = entry
            target_dir_pos = pos
        pos += 8 + len(entry.name) + 1  # offset(4) + size(4) + name + null

    if target_entry is None:
        return False

    # Check if new data fits in the original space
    if len(new_data) > target_entry.size:
        return False

    # Write new data at original offset
    archive[target_entry.offset : target_entry.offset + len(new_data)] = new_data
    # Zero-pad remaining space
    remaining = target_entry.size - len(new_data)
    if remaining > 0:
        archive[
            target_entry.offset + len(new_data) :
            target_entry.offset + target_entry.size
        ] = b"\x00" * remaining

    # Update file size in directory entry (keep original offset)
    # Directory entry layout: 4B offset (BE) + 4B size (BE) + name + null
    # We keep the original size in the directory so the game reads the
    # full allocation. RefPack stops at its end marker, ignoring padding.
    # (No size update needed — original size is preserved.)

    return True


def bigf_build(entries: List[BigfEntry], file_contents: Dict[str, bytes]) -> bytes:
    """Build a BIGF archive from entries and file data."""
    num_files = len(entries)

    # Calculate header size: 16 (main header) + entries
    header_size = 16
    for entry in entries:
        header_size += 8 + len(entry.name) + 1  # offset + size + name + null

    # Build file table and data
    out = bytearray()
    # Placeholder header
    out.extend(b"BIGF")
    out.extend(b"\x00" * 12)

    # Write file entries (placeholder offsets)
    entry_positions = []
    for entry in entries:
        entry_positions.append(len(out))
        out.extend(b"\x00\x00\x00\x00")  # offset placeholder
        data = file_contents.get(entry.name, b"")
        out.extend(struct.pack(">I", len(data)))
        out.extend(entry.name.encode("ascii"))
        out.append(0)

    # Write file data and fix offsets (128-byte aligned, matching EA's format)
    # Pad header area to 128-byte boundary before first file
    pad_to_128 = (128 - (len(out) % 128)) % 128
    out.extend(b"\x00" * pad_to_128)

    for i, entry in enumerate(entries):
        data = file_contents.get(entry.name, b"")
        file_offset = len(out)
        out.extend(data)
        # Fix offset in entry
        struct.pack_into(">I", out, entry_positions[i], file_offset)
        # Pad to next 128-byte boundary (except after last file)
        if i < num_files - 1:
            pad = (128 - (len(out) % 128)) % 128
            out.extend(b"\x00" * pad)

    # Fix header
    # Note: EA's BIGF stores total_size as LE, but num_files/header_size as BE
    total_size = len(out)
    struct.pack_into("<I", out, 4, total_size)
    struct.pack_into(">I", out, 8, num_files)
    struct.pack_into(">I", out, 12, header_size)

    return bytes(out)


# ──────────────────────────────────────────────────────────────
# TDB Database Format
# ──────────────────────────────────────────────────────────────

# Field types
TDB_TYPE_STRING = 0
TDB_TYPE_BINARY = 1
TDB_TYPE_SINT = 2
TDB_TYPE_UINT = 3
TDB_TYPE_FLOAT = 4

TDB_MAGIC = b"DB\x00\x08"


@dataclass
class TDBField:
    """A field definition in a TDB table."""

    name: str
    field_type: int  # 0=string, 3=int, etc.
    bit_offset: int
    bit_width: int
    name_hash: int = 0

    @property
    def is_string(self) -> bool:
        return self.field_type == TDB_TYPE_STRING

    @property
    def is_int(self) -> bool:
        return self.field_type in (TDB_TYPE_SINT, TDB_TYPE_UINT)


@dataclass
class TDBTable:
    """A single table in a TDB file.

    Records are bit-packed arrays of fields. String fields are byte-aligned
    within each record; integer fields are bit-packed.

    TDB header layout at each table (matches madden-file-tools):
      offset 20: maxRecords (2B LE) — allocated capacity
      offset 22: currentRecords (2B LE) — actual valid record count
    The game reads only currentRecords; maxRecords is the buffer size.
    """

    name: str
    name_hash: int
    fields: List[TDBField] = field(default_factory=list)
    record_size: int = 0  # bytes per record
    capacity: int = 0  # maxRecords — allocated capacity
    num_records: int = 0  # currentRecords — actual valid count
    data_offset: int = 0  # offset into raw TDB data where records start
    _raw_data: bytes = b""  # raw record data (capacity * record_size bytes)
    _header_crc: int = 0
    _header_unk: int = 0
    _padding: int = 0

    def allocate_record(self) -> int:
        """Allocate a new record slot, incrementing currentRecords.

        Returns the new record index, or -1 if at capacity.
        """
        if self.num_records >= self.capacity:
            return -1
        idx = self.num_records
        self.num_records += 1
        return idx

    def read_record(self, index: int) -> Dict[str, object]:
        """Read a single record by index, returning field name→value dict."""
        if index < 0 or index >= self.capacity:
            raise IndexError(f"Record {index} out of range (0-{self.capacity - 1})")

        rec_start = index * self.record_size
        rec_data = self._raw_data[rec_start : rec_start + self.record_size]

        result = {}
        for f in self.fields:
            if f.is_string:
                # String fields: byte-aligned, bit_offset and bit_width in bits
                byte_off = f.bit_offset // 8
                byte_len = f.bit_width // 8
                raw = rec_data[byte_off : byte_off + byte_len]
                # Null-terminate
                null_idx = raw.find(b"\x00")
                if null_idx >= 0:
                    raw = raw[:null_idx]
                result[f.name] = raw.decode("ascii", errors="replace")
            else:
                # Integer: extract bits
                result[f.name] = self._read_bits(rec_data, f.bit_offset, f.bit_width)
        return result

    def write_record(self, index: int, values: Dict[str, object]):
        """Write values to a record. Only specified fields are updated."""
        if index < 0 or index >= self.capacity:
            raise IndexError(f"Record {index} out of range (capacity={self.capacity})")

        rec_start = index * self.record_size
        # Convert to mutable if needed
        if not isinstance(self._raw_data, bytearray):
            self._raw_data = bytearray(self._raw_data)

        for f in self.fields:
            if f.name not in values:
                continue
            val = values[f.name]

            if f.is_string:
                byte_off = f.bit_offset // 8
                byte_len = f.bit_width // 8
                if isinstance(val, str):
                    encoded = val.encode("ascii", errors="replace")
                else:
                    encoded = bytes(val)
                # Pad/truncate to field width, null-terminate
                padded = encoded[:byte_len]
                padded = padded + b"\x00" * (byte_len - len(padded))
                for i, b in enumerate(padded):
                    self._raw_data[rec_start + byte_off + i] = b
            else:
                # Integer: write bits
                self._write_bits(rec_start, f.bit_offset, f.bit_width, int(val))

    def _read_bits(self, rec_data: bytes, bit_offset: int, bit_width: int) -> int:
        """Read an unsigned integer from bit-packed record data (LSB first)."""
        value = 0
        for i in range(bit_width):
            bit_pos = bit_offset + i
            byte_idx = bit_pos // 8
            bit_idx = bit_pos % 8  # LSB first within byte
            if byte_idx < len(rec_data):
                if rec_data[byte_idx] & (1 << bit_idx):
                    value |= 1 << i
        return value

    def _write_bits(self, rec_start: int, bit_offset: int, bit_width: int, value: int):
        """Write an unsigned integer to bit-packed record data (LSB first)."""
        max_val = (1 << bit_width) - 1
        value = max(0, min(max_val, value))

        for i in range(bit_width):
            bit_pos = bit_offset + i
            byte_idx = rec_start + bit_pos // 8
            bit_idx = bit_pos % 8  # LSB first within byte
            if byte_idx < len(self._raw_data):
                if value & (1 << i):
                    self._raw_data[byte_idx] |= 1 << bit_idx
                else:
                    self._raw_data[byte_idx] &= ~(1 << bit_idx)

    def find_record(self, field_name: str, value: object) -> int:
        """Find first record index where field == value.

        Only searches within currentRecords (the valid range).
        Returns -1 if not found.
        """
        for i in range(self.num_records):
            rec = self.read_record(i)
            if rec.get(field_name) == value:
                return i
        return -1

    def find_records(self, field_name: str, value: object) -> List[int]:
        """Find all record indices where field == value.

        Only searches within currentRecords (the valid range).
        """
        results = []
        for i in range(self.num_records):
            rec = self.read_record(i)
            if rec.get(field_name) == value:
                results.append(i)
        return results


class TDBFile:
    """Parser/serializer for EA TDB database files.

    TDB layout:
      [4B magic: DB\\x00\\x08]
      [4B file_size LE]
      [4B num_tables]
      [table directory: N × (4B hash + 4B name + 4B offset)]
      [per-table data blocks]
    """

    def __init__(self):
        self.tables: Dict[str, TDBTable] = {}
        self._raw: bytearray = bytearray()
        self._table_order: List[str] = []

    @classmethod
    def parse(cls, data: bytes) -> "TDBFile":
        """Parse a TDB file from raw bytes.

        TDB header layout (20 bytes):
          [4B magic: DB\\x00\\x08]
          [4B zeros]
          [4B data_size LE]
          [4B zeros]
          [4B num_tables LE]
        Then:
          [4B directory hash]
          [8B per table entry: 4B name ASCII + 4B offset LE]
        """
        tdb = cls()
        tdb._raw = bytearray(data)

        if len(data) < 20 or data[:4] != TDB_MAGIC:
            raise ValueError(f"Not a TDB file (magic: {data[:4]!r})")

        num_tables = struct.unpack_from("<I", data, 16)[0]

        # Skip 4-byte directory hash after header
        dir_start = 24  # 20 (header) + 4 (dir hash)
        dir_end = dir_start + num_tables * 8  # Each entry is 8 bytes

        table_entries = []
        pos = dir_start
        for _ in range(num_tables):
            if pos + 8 > len(data):
                break
            t_name_raw = data[pos : pos + 4]
            t_rel_offset = struct.unpack_from("<I", data, pos + 4)[0]
            t_name = t_name_raw.decode("ascii", errors="replace").strip("\x00")
            # Offsets are relative to end of directory
            t_abs_offset = dir_end + t_rel_offset
            table_entries.append((t_name, t_abs_offset))
            pos += 8

        # Parse each table
        for t_name, t_offset in table_entries:
            table = cls._parse_table(data, t_offset, t_name)
            if table:
                tdb.tables[t_name] = table
                tdb._table_order.append(t_name)

        return tdb

    @classmethod
    def _parse_table(
        cls, data: bytes, offset: int, name: str
    ) -> Optional[TDBTable]:
        """Parse a single table at the given offset."""
        if offset + 20 > len(data):
            return None

        # Table header (20 bytes)
        header_crc = struct.unpack_from("<I", data, offset)[0]
        header_unk = struct.unpack_from("<I", data, offset + 4)[0]
        rec_size = struct.unpack_from("<I", data, offset + 8)[0]
        max_recs = struct.unpack_from("<I", data, offset + 12)[0]
        padding = struct.unpack_from("<I", data, offset + 16)[0]

        pos = offset + 20

        # Record info (16 bytes)
        # Layout matches madden-file-tools:
        #   offset+0: maxRecords (2B LE) — allocated capacity
        #   offset+2: currentRecords (2B LE) — valid record count
        #   offset+4: marker (4B)
        #   offset+8: numFields (4B LE, but really 1B + 1B idx_count + 2B pad)
        #   offset+12: padding (4B)
        if pos + 16 > len(data):
            return None
        max_records = struct.unpack_from("<H", data, pos)[0]
        current_records = struct.unpack_from("<H", data, pos + 2)[0]
        _rec_marker = struct.unpack_from("<I", data, pos + 4)[0]  # noqa: F841
        num_fields = struct.unpack_from("<I", data, pos + 8)[0]
        _rec_pad = struct.unpack_from("<I", data, pos + 12)[0]  # noqa: F841
        pos += 16

        # Field name hash (4 bytes)
        if pos + 4 > len(data):
            return None
        _field_hash = struct.unpack_from("<I", data, pos)[0]  # noqa: F841
        pos += 4

        # Field definitions (16 bytes each)
        fields = []
        for _ in range(num_fields):
            if pos + 16 > len(data):
                break
            f_type = struct.unpack_from("<I", data, pos)[0]
            f_bit_offset = struct.unpack_from("<I", data, pos + 4)[0]
            f_name_raw = data[pos + 8 : pos + 12]
            f_bit_width = struct.unpack_from("<I", data, pos + 12)[0]
            f_name = f_name_raw.decode("ascii", errors="replace").strip("\x00")
            fields.append(
                TDBField(
                    name=f_name,
                    field_type=f_type,
                    bit_offset=f_bit_offset,
                    bit_width=f_bit_width,
                    name_hash=0,
                )
            )
            pos += 16

        # Record data follows — read the full allocated capacity
        data_offset = pos
        raw_data = data[data_offset : data_offset + max_records * rec_size]

        table = TDBTable(
            name=name,
            name_hash=0,
            fields=fields,
            record_size=rec_size,
            capacity=max_records,
            num_records=current_records,
            data_offset=data_offset,
            _raw_data=bytearray(raw_data),
            _header_crc=header_crc,
            _header_unk=header_unk,
            _padding=padding,
        )
        return table

    def get_table(self, name: str) -> Optional[TDBTable]:
        """Get a table by name (e.g., 'SPBT', 'SPAI', 'ROST')."""
        return self.tables.get(name)

    def serialize(self) -> bytes:
        """Serialize TDB file back to bytes.

        Writes modified record data back into the raw buffer.
        Updates both maxRecords (capacity) and currentRecords (num_records)
        in the table header.
        """
        out = bytearray(self._raw)

        for table in self.tables.values():
            # Write full record data back at original offset (capacity * record_size)
            rec_end = table.data_offset + table.capacity * table.record_size
            if rec_end <= len(out):
                out[table.data_offset : rec_end] = table._raw_data[
                    : table.capacity * table.record_size
                ]
            # Update record counts in table header
            # Layout: header(20) + rec_info(16) + field_hash(4) + fields(N*16)
            #   header_offset + 20 = maxRecords (2B LE)
            #   header_offset + 22 = currentRecords (2B LE)
            header_offset = (
                table.data_offset
                - 4  # field_hash
                - len(table.fields) * 16  # field defs
                - 16  # rec_info
                - 20  # table header
            )
            if header_offset >= 0:
                struct.pack_into("<H", out, header_offset + 20, table.capacity)
                struct.pack_into("<H", out, header_offset + 22, table.num_records)

        return bytes(out)
