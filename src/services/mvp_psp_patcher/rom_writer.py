"""ISO writer for MVP Baseball PSP patcher.

Rebuilds modified CSV sections, recompresses with RefPack,
and writes the updated database.big back into the ISO.
"""

import os
from typing import Dict, List, Optional

from services.nhl07_psp_patcher.ea_tdb import refpack_compress
from services.mvp_psp_patcher.models import (
    SECTION_MAP,
    DATABASE_BIG_LBA,
    DATABASE_BIG_SIZE,
    ISO_SECTOR_SIZE,
)
from services.mvp_psp_patcher.rom_reader import MVPPSPRomReader


def _build_csv_record(hash_id: str, fields: Dict[int, str]) -> str:
    """Build a single CSV record line.

    Format: hash_id,fieldnum value,fieldnum value,...;
    """
    parts = [hash_id]
    for field_num in sorted(fields.keys()):
        parts.append(f"{field_num} {fields[field_num]}")
    return ",".join(parts) + ",;"


def _build_csv_section(
    header: str,
    records: Dict[str, Dict[int, str]],
    record_order: Optional[List[str]] = None,
) -> bytes:
    """Rebuild a complete CSV section from records.

    Format: header;CRLF + record1;CRLF + record2;CRLF + ...
    Uses record_order to preserve original ordering when available.
    """
    lines = [header + ";\r\n"]

    if record_order:
        # Use original order, then append any new records not in order
        ordered = list(record_order)
        seen = set(ordered)
        for h in records:
            if h not in seen:
                ordered.append(h)
        hash_list = ordered
    else:
        hash_list = sorted(records.keys())

    for hash_id in hash_list:
        if hash_id not in records:
            continue
        line = _build_csv_record(hash_id, records[hash_id])
        lines.append(line + "\r\n")
    return "".join(lines).encode("ascii", errors="replace")


class MVPPSPRomWriter:
    """Writes modified data back to MVP Baseball PSP ISO.

    Strategy (same as NHL 07 PSP patcher):
      1. Copy ISO to output path
      2. Parse database.big sections from original
      3. Modify CSV records in memory
      4. Recompress modified sections and write IN-PLACE at original offsets
      5. Write modified database.big back to ISO copy
    """

    def __init__(self, iso_path: str, output_path: str):
        self.iso_path = iso_path
        self.output_path = output_path
        self.reader = MVPPSPRomReader(iso_path)
        self.section_headers: Dict[str, str] = {}
        self._modified_tables: set = set()

    def copy_iso(self) -> bool:
        """Copy source ISO to output path."""
        try:
            output_dir = os.path.dirname(self.output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            chunk_size = 4 * 1024 * 1024
            with open(self.iso_path, "rb") as src, open(self.output_path, "wb") as dst:
                while True:
                    chunk = src.read(chunk_size)
                    if not chunk:
                        break
                    dst.write(chunk)
                dst.flush()
                os.fsync(dst.fileno())
            return True
        except Exception:
            return False

    def load(self) -> bool:
        """Load and parse database.big from the source ISO."""
        if not self.reader.load():
            return False
        if not self.reader.validate():
            return False

        self.reader.decompress_all()
        self._extract_headers()
        self.reader.parse_all()

        return True

    def _extract_headers(self):
        """Extract CSV header lines from each decompressed section."""
        for name, data in self.reader.sections.items():
            text = data.decode("ascii", errors="replace")
            # Header is the first line before the first ;\r\n
            idx = text.find(";\r\n")
            if idx >= 0:
                self.section_headers[name] = text[:idx]

    def update_records(self, table_name: str, records: Dict[str, Dict[int, str]]):
        """Replace all records in a table with new data."""
        self.reader.records[table_name] = records
        self._modified_tables.add(table_name)

    def update_player_record(
        self, table_name: str, player_hash: str, fields: Dict[int, str]
    ):
        """Update or add a single player record in a table.

        Merges new fields into any existing record, preserving
        fields not explicitly set (appearance, spray charts, etc.).
        """
        if table_name not in self.reader.records:
            self.reader.records[table_name] = {}
        existing = self.reader.records[table_name].get(player_hash, {})
        existing.update(fields)
        self.reader.records[table_name][player_hash] = existing
        self._modified_tables.add(table_name)

    def remove_player_record(self, table_name: str, player_hash: str):
        """Remove a player record from a table."""
        if table_name in self.reader.records:
            self.reader.records[table_name].pop(player_hash, None)
            self._modified_tables.add(table_name)

    def _rebuild_section(self, name: str) -> Optional[bytes]:
        """Rebuild and compress a single section."""
        if name not in self.reader.records:
            return None
        header = self.section_headers.get(name, "")
        if not header:
            return None

        order = self.reader.record_order.get(name)
        csv_data = _build_csv_section(header, self.reader.records[name], order)
        return refpack_compress(csv_data)

    def _rebuild_database_big(self) -> bytearray:
        """Rebuild database.big with modified sections IN-PLACE.

        Each section is written at its original offset, padded with
        zeros to fill the original allocation. This preserves the
        fixed offsets the game expects for each section.
        """
        original = self.reader.database_big
        if not original:
            raise ValueError("No database.big loaded")

        result = bytearray(original)

        # Build (offset, allocation_size, name) for each section
        offsets = [(off, name) for off, name in SECTION_MAP]
        modified_tables = self._modified_tables

        for i, (off, name) in enumerate(offsets):
            if i + 1 < len(offsets):
                alloc = offsets[i + 1][0] - off
            else:
                alloc = len(original) - off

            if name not in modified_tables or name not in self.section_headers:
                continue
            # Skip compact attrib — we only modify the full one
            if name == "attrib_compact":
                continue

            compressed = self._rebuild_section(name)
            if not compressed:
                continue

            if len(compressed) > alloc:
                # Recompressed section is too large — keep original
                continue

            # Write at original offset, zero-pad remainder
            result[off : off + len(compressed)] = compressed
            if len(compressed) < alloc:
                result[off + len(compressed) : off + alloc] = b"\x00" * (
                    alloc - len(compressed)
                )

        return result

    def finalize(self) -> bool:
        """Copy ISO and write modified database.big into the copy.

        Only the database.big region is rewritten — the rest of the
        ISO is an exact copy of the original.
        """
        if not self.reader.database_big:
            return False

        try:
            # Step 1: Copy ISO to output
            if not self.copy_iso():
                return False

            # Step 2: Rebuild database.big in-place
            new_db = bytes(self._rebuild_database_big())

            # Step 3: Write just the database.big region into the copy
            db_offset = DATABASE_BIG_LBA * ISO_SECTOR_SIZE
            with open(self.output_path, "r+b") as f:
                f.seek(db_offset)
                f.write(new_db)
                f.flush()
                os.fsync(f.fileno())

            return True
        except Exception:
            return False
