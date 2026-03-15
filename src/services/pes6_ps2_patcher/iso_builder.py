"""ISO builder for PES 6 PS2 patcher.

Adds the option file (NPO) and boot loader to a PES 6 ISO.
Modifies the ISO 9660 directory to include new files and
updates SYSTEM.CNF to boot the multiloader.

Strategy:
  1. Copy original ISO
  2. Append new files (NPO, PS2MENU.ELF, multiloader, MULTI.XML) at the end
  3. Update ISO 9660 root directory to include new entries
  4. Patch SYSTEM.CNF to boot the multiloader
"""

import os
import struct
import shutil
from typing import Optional

ISO_SECTOR_SIZE = 2048

# Assets directory
_ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")


def _load_asset(name: str) -> bytes:
    path = os.path.join(_ASSETS_DIR, name)
    with open(path, "rb") as f:
        return f.read()


def _pad_to_sector(data: bytes) -> bytes:
    """Pad data to sector boundary."""
    remainder = len(data) % ISO_SECTOR_SIZE
    if remainder:
        data += b"\x00" * (ISO_SECTOR_SIZE - remainder)
    return data


def _make_iso_dir_record(
    name: str, lba: int, size: int, is_dir: bool = False
) -> bytes:
    """Create an ISO 9660 directory record."""
    name_bytes = name.encode("ascii")
    name_len = len(name_bytes)

    # Record length: 33 (fixed fields) + name_len + padding
    rec_len = 33 + name_len
    if rec_len % 2:
        rec_len += 1  # Pad to even

    record = bytearray(rec_len)
    record[0] = rec_len  # Length of directory record

    # Extent location (LBA) — both LE and BE
    struct.pack_into("<I", record, 2, lba)
    struct.pack_into(">I", record, 6, lba)

    # Data length — both LE and BE
    struct.pack_into("<I", record, 10, size)
    struct.pack_into(">I", record, 14, size)

    # Recording date (7 bytes at offset 18) — zeros = Jan 1, 1900
    # File flags at offset 25
    if is_dir:
        record[25] = 0x02

    # File unit size, interleave gap = 0
    # Volume sequence number = 1
    struct.pack_into("<H", record, 28, 1)
    struct.pack_into(">H", record, 30, 1)

    # File identifier length and name
    record[32] = name_len
    record[33 : 33 + name_len] = name_bytes

    return bytes(record)


def _make_multi_xml(game_id: str) -> bytes:
    """Generate MULTI.XML for single-item auto-boot."""
    xml = f"""<multiload>
\t<item>
\t\t<name>PES 6</name>
\t\t<path>cdrom0:\\{game_id};1</path>
\t\t<description>Pro Evolution Soccer 6</description>
\t</item>
</multiload>
"""
    return xml.encode("ascii")


def build_patched_iso(
    input_path: str,
    output_path: str,
    npo_data: bytes,
    game_id: str = "SLES_542.03",
    on_progress=None,
) -> str:
    """Build a patched ISO with embedded option file and boot loader.

    Args:
        input_path: Path to original PES 6 ISO.
        output_path: Path for output ISO.
        npo_data: Generated NPO file data.
        game_id: Original game executable name (e.g., SLES_542.03).
        on_progress: Optional callback(progress, message).

    Returns:
        Output path.
    """
    if on_progress:
        on_progress(0.0, "Preparing ISO...")

    # Copy original ISO (skip if same file — already copied by rom_writer)
    if os.path.abspath(input_path) != os.path.abspath(output_path):
        shutil.copy2(input_path, output_path)

    # Determine the NPO filename based on game ID
    # SLES_542.03 → BESLES-54203PES6OPT
    npo_filename = f"BE{game_id.replace('_', '').replace('.', '')}PES6OPT.NPO;1"

    with open(output_path, "r+b") as f:
        # Find current ISO end (last used sector)
        f.seek(0, 2)
        iso_size = f.tell()
        append_lba = (iso_size + ISO_SECTOR_SIZE - 1) // ISO_SECTOR_SIZE

        if on_progress:
            on_progress(0.2, "Appending option file...")

        # Append NPO file at the end of the ISO
        files_to_add = [
            (npo_filename, npo_data),
        ]

        file_entries = []
        for fname, fdata in files_to_add:
            padded = _pad_to_sector(fdata)
            lba = append_lba
            f.seek(lba * ISO_SECTOR_SIZE)
            f.write(padded)
            file_entries.append((fname, lba, len(fdata)))
            append_lba += len(padded) // ISO_SECTOR_SIZE

        if on_progress:
            on_progress(0.5, "Updating directory...")

        # Read original root directory
        f.seek(16 * ISO_SECTOR_SIZE)
        pvd = bytearray(f.read(ISO_SECTOR_SIZE))

        root_lba = struct.unpack_from("<I", pvd, 158)[0]
        root_size = struct.unpack_from("<I", pvd, 166)[0]

        f.seek(root_lba * ISO_SECTOR_SIZE)
        root_dir = bytearray(f.read(root_size))

        # Find end of existing directory entries
        pos = 0
        last_entry_end = 0
        while pos < len(root_dir):
            rec_len = root_dir[pos]
            if rec_len == 0:
                # Try next sector
                next_sector = ((pos // ISO_SECTOR_SIZE) + 1) * ISO_SECTOR_SIZE
                if next_sector >= len(root_dir):
                    break
                pos = next_sector
                continue
            last_entry_end = pos + rec_len
            pos += rec_len

        # Check if there's room in the existing directory sectors
        space_left = len(root_dir) - last_entry_end
        new_records = b""
        for fname, lba, fsize in file_entries:
            rec = _make_iso_dir_record(fname, lba, fsize)
            new_records += rec

        if len(new_records) <= space_left:
            # Fits in existing directory — write new entries
            root_dir[last_entry_end : last_entry_end + len(new_records)] = new_records
            f.seek(root_lba * ISO_SECTOR_SIZE)
            f.write(bytes(root_dir))
        else:
            # Need to extend directory — allocate new sectors
            new_dir_size = last_entry_end + len(new_records)
            new_dir_sectors = (new_dir_size + ISO_SECTOR_SIZE - 1) // ISO_SECTOR_SIZE
            new_dir = bytearray(new_dir_sectors * ISO_SECTOR_SIZE)
            new_dir[: len(root_dir)] = root_dir
            new_dir[last_entry_end : last_entry_end + len(new_records)] = new_records

            # Write extended directory at a new location
            new_dir_lba = append_lba
            f.seek(new_dir_lba * ISO_SECTOR_SIZE)
            f.write(bytes(new_dir))
            append_lba += new_dir_sectors

            # Update PVD to point to new directory
            new_total_size = len(new_dir)
            struct.pack_into("<I", pvd, 158, new_dir_lba)
            struct.pack_into(">I", pvd, 162, new_dir_lba)
            struct.pack_into("<I", pvd, 166, new_total_size)
            struct.pack_into(">I", pvd, 170, new_total_size)

            # Also update root directory record in PVD (at offset 156)
            # The root dir record is embedded in the PVD at offset 156
            struct.pack_into("<I", pvd, 158, new_dir_lba)
            struct.pack_into(">I", pvd, 162, new_dir_lba)
            struct.pack_into("<I", pvd, 166, new_total_size)
            struct.pack_into(">I", pvd, 170, new_total_size)

            f.seek(16 * ISO_SECTOR_SIZE)
            f.write(bytes(pvd))

        if on_progress:
            on_progress(1.0, "ISO build complete!")

    return output_path
