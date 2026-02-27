"""ROM reader for NHL 07 PSP patcher.

Reads NHL 07 PSP ISO to extract and parse TDB tables from db.viv.

ISO structure:
  Standard ISO 9660 → PSP_GAME/USRDIR/db/db.viv (BIGF archive)
  → nhl2007.tdb, nhlbioatt.tdb, nhlrost.tdb (RefPack compressed TDB files)

References:
  - Game ID: ULUS10131
  - ISO 9660: standard sector size 2048
"""

import os
import struct
from typing import Optional, List, Dict, Tuple

from services.nhl07_psp_patcher.ea_tdb import (
    bigf_extract,
    refpack_decompress,
    TDBFile,
)
from services.nhl07_psp_patcher.models import (
    NHL07RomInfo,
    NHL07TeamSlot,
    NHL07_TEAM_NAMES,
    NHL07_TEAM_INDEX,
    TEAM_COUNT,
    TDB_MASTER,
    TDB_BIOATT,
    TDB_ROSTER,
)


# ISO 9660 constants
ISO_SECTOR_SIZE = 2048
ISO_PVD_OFFSET = 16 * ISO_SECTOR_SIZE  # Primary Volume Descriptor at sector 16

# db.viv path inside ISO
DB_VIV_PATH = "PSP_GAME/USRDIR/DB/DB.VIV"


class NHL07PSPRomReader:
    """Reads and parses NHL 07 PSP ISO data."""

    def __init__(self, iso_path: str):
        self.iso_path = iso_path
        self._iso_size = 0
        self._db_viv_data: Optional[bytes] = None
        self._tdb_files: Dict[str, TDBFile] = {}

    def load(self) -> bool:
        """Validate ISO and extract db.viv."""
        if not os.path.exists(self.iso_path):
            return False
        try:
            self._iso_size = os.path.getsize(self.iso_path)
            if self._iso_size < ISO_SECTOR_SIZE * 20:
                return False
            # Extract db.viv from ISO
            self._db_viv_data = self._extract_db_viv()
            return self._db_viv_data is not None
        except Exception:
            return False

    def validate(self, deep: bool = True) -> bool:
        """Validate that this is an NHL 07 PSP ISO.

        Args:
            deep: If True, decompress and parse a TDB file to verify.
                  If False, only check BIGF header (fast).
        """
        if not self._db_viv_data:
            return False
        # Check that db.viv is a BIGF archive
        if self._db_viv_data[:4] != b"BIGF":
            return False
        if not deep:
            return True
        # Try to extract and parse a TDB file
        try:
            raw = bigf_extract(self._db_viv_data, TDB_BIOATT)
            if raw is None:
                # Try lowercase
                raw = bigf_extract(self._db_viv_data, TDB_BIOATT.lower())
            if raw and len(raw) > 5 and raw[0] == 0x10 and raw[1] == 0xFB:
                decompressed = refpack_decompress(raw)
                if decompressed[:4] == b"DB\x00\x08":
                    return True
            # Maybe not compressed
            if raw and raw[:4] == b"DB\x00\x08":
                return True
        except Exception:
            pass
        return False

    def get_info(self, deep: bool = True) -> NHL07RomInfo:
        """Get ROM information and team slots.

        Args:
            deep: If True, decompress TDB to verify and read team names from ROM.
                  If False, only check BIGF header and use hardcoded team names (fast).
        """
        if not self._db_viv_data:
            return NHL07RomInfo(path=self.iso_path, size=0, is_valid=False)

        is_valid = self.validate(deep=deep)
        if is_valid and deep:
            team_slots = self._read_team_slots()
        elif is_valid:
            # Fast path: use hardcoded team names
            team_slots = [
                NHL07TeamSlot(
                    index=i,
                    name=NHL07_TEAM_NAMES[i],
                    abbreviation=NHL07_TEAM_INDEX.get(i, f"T{i}"),
                )
                for i in range(TEAM_COUNT)
            ]
        else:
            team_slots = []
        return NHL07RomInfo(
            path=self.iso_path,
            size=self._iso_size,
            team_slots=team_slots,
            is_valid=is_valid,
        )

    def get_tdb(self, filename: str) -> Optional[TDBFile]:
        """Get a parsed TDB file from db.viv (with caching)."""
        if filename in self._tdb_files:
            return self._tdb_files[filename]

        if not self._db_viv_data:
            return None

        raw = bigf_extract(self._db_viv_data, filename)
        if raw is None:
            return None

        # Decompress if RefPack compressed
        if len(raw) > 2 and raw[0] == 0x10 and raw[1] == 0xFB:
            decompressed = refpack_decompress(raw)
        else:
            decompressed = raw

        tdb = TDBFile.parse(decompressed)
        self._tdb_files[filename] = tdb
        return tdb

    def get_db_viv(self) -> Optional[bytes]:
        """Get the raw db.viv data."""
        return self._db_viv_data

    def read_teams(self) -> List[NHL07TeamSlot]:
        """Read team information from STEA table."""
        return self._read_team_slots()

    def read_players(self) -> Dict[int, dict]:
        """Read player bios from SPBT table.

        Returns dict mapping player INDX to bio dict.
        """
        tdb = self.get_tdb(TDB_BIOATT)
        if not tdb:
            tdb = self.get_tdb(TDB_MASTER)
        if not tdb:
            return {}

        spbt = tdb.get_table("SPBT")
        if not spbt:
            return {}

        players = {}
        for i in range(spbt.num_records):
            try:
                rec = spbt.read_record(i)
                idx = rec.get("INDX", 0)
                if idx > 0:
                    players[idx] = rec
            except Exception:
                continue
        return players

    def read_roster(self) -> Dict[int, List[dict]]:
        """Read roster assignments from ROST table.

        Returns dict mapping team index to list of roster entries.
        """
        tdb = self.get_tdb(TDB_ROSTER)
        if not tdb:
            tdb = self.get_tdb(TDB_MASTER)
        if not tdb:
            return {}

        rost = tdb.get_table("ROST")
        if not rost:
            return {}

        rosters: Dict[int, List[dict]] = {}
        for i in range(rost.num_records):
            try:
                rec = rost.read_record(i)
                team = rec.get("TEAM", 127)
                if team < 64:  # Valid team index
                    rosters.setdefault(team, []).append(rec)
            except Exception:
                continue
        return rosters

    def _extract_db_viv(self) -> Optional[bytes]:
        """Extract db.viv from the ISO using ISO 9660 directory traversal."""
        try:
            with open(self.iso_path, "rb") as f:
                # Read Primary Volume Descriptor
                f.seek(ISO_PVD_OFFSET)
                pvd = f.read(ISO_SECTOR_SIZE)
                if len(pvd) < ISO_SECTOR_SIZE or pvd[0] != 1:
                    return None

                # Root directory record is at offset 156 in PVD (34 bytes)
                root_rec = pvd[156 : 156 + 34]
                root_lba = struct.unpack_from("<I", root_rec, 2)[0]
                root_size = struct.unpack_from("<I", root_rec, 10)[0]

                # Navigate path: PSP_GAME → USRDIR → DB → DB.VIV
                path_parts = ["PSP_GAME", "USRDIR", "DB"]
                current_lba = root_lba
                current_size = root_size

                for part in path_parts:
                    result = self._find_dir_entry(f, current_lba, current_size, part)
                    if result is None:
                        return None
                    current_lba, current_size, is_dir = result
                    if not is_dir:
                        return None

                # Find DB.VIV file
                result = self._find_dir_entry(f, current_lba, current_size, "DB.VIV")
                if result is None:
                    return None
                file_lba, file_size, is_dir = result
                if is_dir:
                    return None

                # Read the file
                f.seek(file_lba * ISO_SECTOR_SIZE)
                return f.read(file_size)

        except Exception:
            return None

    def _find_dir_entry(
        self, f, dir_lba: int, dir_size: int, name: str
    ) -> Optional[Tuple[int, int, bool]]:
        """Find a named entry in an ISO 9660 directory.

        Returns (lba, size, is_directory) or None.
        """
        f.seek(dir_lba * ISO_SECTOR_SIZE)
        dir_data = f.read(dir_size)
        pos = 0
        name_upper = name.upper()

        while pos < len(dir_data):
            rec_len = dir_data[pos]
            if rec_len == 0:
                # Skip to next sector boundary
                next_sector = ((pos // ISO_SECTOR_SIZE) + 1) * ISO_SECTOR_SIZE
                if next_sector >= len(dir_data):
                    break
                pos = next_sector
                continue

            if pos + rec_len > len(dir_data):
                break

            name_len = dir_data[pos + 32]
            if name_len > 0 and pos + 33 + name_len <= len(dir_data):
                entry_name = dir_data[pos + 33 : pos + 33 + name_len].decode(
                    "ascii", errors="replace"
                )
                # ISO 9660 names may have ";1" version suffix
                entry_name_clean = entry_name.split(";")[0].upper()

                if entry_name_clean == name_upper:
                    entry_lba = struct.unpack_from("<I", dir_data, pos + 2)[0]
                    entry_size = struct.unpack_from("<I", dir_data, pos + 10)[0]
                    is_dir = bool(dir_data[pos + 25] & 0x02)
                    return entry_lba, entry_size, is_dir

            pos += rec_len

        return None

    def _read_team_slots(self) -> List[NHL07TeamSlot]:
        """Read team slots from STEA table or use defaults."""
        slots = []

        # Try reading from STEA table in master TDB
        tdb = self.get_tdb(TDB_MASTER)
        stea = tdb.get_table("STEA") if tdb else None

        if stea:
            for i in range(min(stea.num_records, len(NHL07_TEAM_NAMES))):
                try:
                    rec = stea.read_record(i)
                    name = rec.get("NAME", "") or rec.get("CITY", "")
                    idx = rec.get("INDX", i)
                    abbr = NHL07_TEAM_INDEX.get(idx, f"T{idx}")
                    if not name:
                        name = NHL07_TEAM_NAMES[i] if i < len(NHL07_TEAM_NAMES) else f"Team {i}"
                    slots.append(
                        NHL07TeamSlot(
                            index=idx,
                            name=name,
                            abbreviation=abbr,
                        )
                    )
                except Exception:
                    slots.append(
                        NHL07TeamSlot(
                            index=i,
                            name=NHL07_TEAM_NAMES[i] if i < len(NHL07_TEAM_NAMES) else f"Team {i}",
                            abbreviation=NHL07_TEAM_INDEX.get(i, f"T{i}"),
                        )
                    )
        else:
            # Fallback to hardcoded names
            for i in range(TEAM_COUNT):
                slots.append(
                    NHL07TeamSlot(
                        index=i,
                        name=NHL07_TEAM_NAMES[i],
                        abbreviation=NHL07_TEAM_INDEX.get(i, f"T{i}"),
                    )
                )

        return slots

    def find_db_viv_location(self) -> Tuple[int, int, int]:
        """Find the LBA, size, and available space for db.viv in the ISO.

        Returns (lba, size, max_size) where max_size is the usable byte
        budget before the next file on the ISO (sector-aligned).
        """
        try:
            with open(self.iso_path, "rb") as f:
                f.seek(ISO_PVD_OFFSET)
                pvd = f.read(ISO_SECTOR_SIZE)
                root_rec = pvd[156 : 156 + 34]
                root_lba = struct.unpack_from("<I", root_rec, 2)[0]
                root_size = struct.unpack_from("<I", root_rec, 10)[0]

                current_lba = root_lba
                current_size = root_size

                for part in ["PSP_GAME", "USRDIR", "DB"]:
                    result = self._find_dir_entry(f, current_lba, current_size, part)
                    if result is None:
                        return 0, 0, 0
                    current_lba, current_size, _ = result

                # Find db.viv and the next file to determine available space
                db_lba, db_size, next_lba = self._find_entry_with_gap(
                    f, current_lba, current_size, "DB.VIV"
                )
                if db_lba == 0:
                    return 0, 0, 0

                # Available space = sectors from db.viv LBA to next file's LBA
                if next_lba > db_lba:
                    max_size = (next_lba - db_lba) * ISO_SECTOR_SIZE
                else:
                    # Fallback: just sector-align the original size
                    max_size = (
                        (db_size + ISO_SECTOR_SIZE - 1)
                        // ISO_SECTOR_SIZE
                        * ISO_SECTOR_SIZE
                    )
                return db_lba, db_size, max_size
        except Exception:
            return 0, 0, 0

    def find_db_viv_dir_entry_offset(self) -> int:
        """Find the absolute ISO byte offset of DB.VIV's directory record.

        This is needed to update the ISO 9660 file size fields when the
        rebuilt db.viv is a different size than the original.

        Returns the absolute byte offset of the directory record, or 0 on failure.
        The size fields are at record_offset+10 (LE) and record_offset+14 (BE).
        """
        try:
            with open(self.iso_path, "rb") as f:
                f.seek(ISO_PVD_OFFSET)
                pvd = f.read(ISO_SECTOR_SIZE)
                root_rec = pvd[156:156 + 34]
                root_lba = struct.unpack_from("<I", root_rec, 2)[0]
                root_size = struct.unpack_from("<I", root_rec, 10)[0]

                current_lba = root_lba
                current_size = root_size

                for part in ["PSP_GAME", "USRDIR", "DB"]:
                    result = self._find_dir_entry(
                        f, current_lba, current_size, part
                    )
                    if result is None:
                        return 0
                    current_lba, current_size, _ = result

                # Find DB.VIV's record offset within the DB directory
                return self._find_dir_entry_abs_offset(
                    f, current_lba, current_size, "DB.VIV"
                )
        except Exception:
            return 0

    def _find_dir_entry_abs_offset(
        self, f, dir_lba: int, dir_size: int, name: str
    ) -> int:
        """Find the absolute ISO byte offset of a directory entry record.

        Returns the absolute byte offset of the record start, or 0 on failure.
        """
        f.seek(dir_lba * ISO_SECTOR_SIZE)
        dir_data = f.read(dir_size)
        pos = 0
        name_upper = name.upper()

        while pos < len(dir_data):
            rec_len = dir_data[pos]
            if rec_len == 0:
                next_sector = ((pos // ISO_SECTOR_SIZE) + 1) * ISO_SECTOR_SIZE
                if next_sector >= len(dir_data):
                    break
                pos = next_sector
                continue
            if pos + rec_len > len(dir_data):
                break

            name_len = dir_data[pos + 32]
            if name_len > 0 and pos + 33 + name_len <= len(dir_data):
                entry_name = dir_data[pos + 33:pos + 33 + name_len].decode(
                    "ascii", errors="replace"
                )
                entry_name_clean = entry_name.split(";")[0].upper()
                if entry_name_clean == name_upper:
                    return dir_lba * ISO_SECTOR_SIZE + pos

            pos += rec_len

        return 0

    def _find_entry_with_gap(
        self, f, dir_lba: int, dir_size: int, name: str
    ) -> Tuple[int, int, int]:
        """Find a file entry and the next file's LBA in the same directory.

        Returns (lba, size, next_lba). next_lba is the LBA of the file
        that starts immediately after this one on the ISO.
        """
        f.seek(dir_lba * ISO_SECTOR_SIZE)
        dir_data = f.read(dir_size)
        pos = 0
        name_upper = name.upper()

        # Collect all file entries
        all_entries: List[Tuple[str, int, int]] = []
        while pos < len(dir_data):
            rec_len = dir_data[pos]
            if rec_len == 0:
                next_sector = ((pos // ISO_SECTOR_SIZE) + 1) * ISO_SECTOR_SIZE
                if next_sector >= len(dir_data):
                    break
                pos = next_sector
                continue
            if pos + rec_len > len(dir_data):
                break
            name_len = dir_data[pos + 32]
            if name_len > 1 and pos + 33 + name_len <= len(dir_data):
                entry_name = dir_data[pos + 33 : pos + 33 + name_len].decode(
                    "ascii", errors="replace"
                )
                entry_name_clean = entry_name.split(";")[0].upper()
                entry_lba = struct.unpack_from("<I", dir_data, pos + 2)[0]
                entry_size = struct.unpack_from("<I", dir_data, pos + 10)[0]
                all_entries.append((entry_name_clean, entry_lba, entry_size))
            pos += rec_len

        # Sort by LBA to find the next file after our target
        all_entries.sort(key=lambda x: x[1])
        for i, (ename, elba, esize) in enumerate(all_entries):
            if ename == name_upper:
                next_lba = 0
                if i + 1 < len(all_entries):
                    next_lba = all_entries[i + 1][1]
                return elba, esize, next_lba

        return 0, 0, 0
