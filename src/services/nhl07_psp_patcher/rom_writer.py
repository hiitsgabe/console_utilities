"""ROM writer for NHL 07 PSP patcher.

Modifies TDB tables in db.viv and writes modified db.viv back to ISO.

Strategy:
  1. Copy ISO to output path (or work in-place on copy)
  2. Extract db.viv from ISO
  3. Extract TDB files from BIGF, decompress, modify, recompress
  4. Rebuild BIGF with modified TDB files
  5. Write modified db.viv back to ISO at original location

References:
  - TDB tables modified: SPBT (bios), SPAI (skater attrs),
    SGAI (goalie attrs), ROST (roster assignments)
"""

import os
import struct
from typing import Optional, Dict, Callable

from services.nhl07_psp_patcher.ea_tdb import (
    bigf_replace,
    bigf_replace_inplace,
    refpack_compress,
    TDBFile,
)
from services.nhl07_psp_patcher.rom_reader import (
    NHL07PSPRomReader,
    ISO_SECTOR_SIZE,
)
from services.nhl07_psp_patcher.models import (
    NHL07PlayerRecord,
    NHL07SkaterAttributes,
    NHL07GoalieAttributes,
    POSITION_REVERSE,
)


# Line assignment flag names for ROST table
LINE_FLAGS = [
    "L1C_",
    "L2C_",
    "L3C_",
    "L4C_",
    "L1LW",
    "L2LW",
    "L3LW",
    "L4LW",
    "L1RW",
    "L2RW",
    "L3RW",
    "L4RW",
    "31LD",
    "32LD",
    "33LD",  # Note: "31LD" not "L1LD" in TDB
    "31RD",
    "32RD",
    "33RD",
    "G1__",
    "G2__",
    "H1__",
    "H2__",
    "H3__",
    "H4__",
    "H5__",
    "S1__",
    "S2__",
    "S3__",
    "S4__",
    "S5__",
]


class NHL07PSPRomWriter:
    """Writes player data to NHL 07 PSP ISO."""

    def __init__(self, iso_path: str, output_path: str):
        self.iso_path = iso_path
        self.output_path = output_path
        self.reader: Optional[NHL07PSPRomReader] = None
        self._db_viv: Optional[bytes] = None

    def copy_iso(self, on_progress: Optional[Callable[[float, str], None]] = None) -> bool:
        """Copy source ISO to output path with progress reporting."""
        try:
            src_size = os.path.getsize(self.iso_path)
            output_dir = os.path.dirname(self.output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

            chunk_size = 4 * 1024 * 1024  # 4MB chunks
            copied = 0
            with open(self.iso_path, "rb") as src, open(self.output_path, "wb") as dst:
                while True:
                    chunk = src.read(chunk_size)
                    if not chunk:
                        break
                    dst.write(chunk)
                    copied += len(chunk)
                    if on_progress and src_size > 0:
                        on_progress(
                            copied / src_size * 0.3,  # Copy is 30% of total
                            f"Copying ISO... {copied // (1024 * 1024)}MB",
                        )
            return True
        except Exception:
            return False

    def load(self) -> bool:
        """Load the output ISO for modification."""
        self.reader = NHL07PSPRomReader(self.output_path)
        if not self.reader.load():
            return False
        self._db_viv = self.reader.get_db_viv()
        return self._db_viv is not None

    def write_player_bio(self, tdb: TDBFile, record_idx: int, player: NHL07PlayerRecord):
        """Update a SPBT record with player bio data."""
        spbt = tdb.get_table("SPBT")
        if not spbt or record_idx >= spbt.capacity:
            return

        values = {
            "FNME": player.first_name[:19],
            "LNME": player.last_name[:19],
            "JERS": player.jersey_number,
            "HAND": player.handedness,
            "TEAM": player.team_index,
            "POS_": POSITION_REVERSE.get(player.position, 0),
        }
        # Only write weight/height if we have them
        if player.weight > 0:
            values["WEIG"] = player.weight
        if player.height > 0:
            values["HEIG"] = player.height

        spbt.write_record(record_idx, values)

    def write_skater_attrs(
        self,
        tdb: TDBFile,
        record_idx: int,
        attrs: NHL07SkaterAttributes,
        player_id: int = 0,
    ):
        """Update a SPAI record with skater attributes."""
        spai = tdb.get_table("SPAI")
        if not spai or record_idx >= spai.capacity:
            return

        values = {
            "BALA": attrs.balance,
            "PENA": attrs.penalty,
            "SACC": attrs.shot_accuracy,
            "WACC": attrs.wrist_accuracy,
            "FACE": attrs.faceoffs,
            "ACCE": attrs.acceleration,
            "SPEE": attrs.speed,
            "POTE": attrs.potential,
            "DEKG": attrs.deking,
            "CHKG": attrs.checking,
            "TOUG": attrs.toughness,
            "FIGH": attrs.fighting,
            "PUCK": attrs.puck_control,
            "AGIL": attrs.agility,
            "HERO": attrs.hero,
            "AGGR": attrs.aggression,
            "PRES": attrs.pressure,
            "PASS": attrs.passing,
            "ENDU": attrs.endurance,
            "INJU": attrs.injury,
            "SPOW": attrs.slap_power,
            "WPOW": attrs.wrist_power,
        }
        if player_id > 0:
            values["INDX"] = player_id
        spai.write_record(record_idx, values)

    def write_goalie_attrs(
        self,
        tdb: TDBFile,
        record_idx: int,
        attrs: NHL07GoalieAttributes,
        player_id: int = 0,
    ):
        """Update a SGAI record with goalie attributes."""
        sgai = tdb.get_table("SGAI")
        if not sgai or record_idx >= sgai.capacity:
            return

        values = {
            "BRKA": attrs.breakaway,
            "REBC": attrs.rebound_ctrl,
            "SREC": attrs.shot_recovery,
            "SPEE": attrs.speed,
            "POKE": attrs.poke_check,
            "INTE": attrs.intensity,
            "POTE": attrs.potential,
            "TOUG": attrs.toughness,
            "FIGH": attrs.fighting,
            "AGIL": attrs.agility,
            "5HOL": attrs.five_hole,
            "PASS": attrs.passing,
            "ENDU": attrs.endurance,
            "GSH_": attrs.glove_high,
            "SSH_": attrs.stick_high,
            "GSL_": attrs.glove_low,
            "SSL_": attrs.stick_low,
        }
        if player_id > 0:
            values["INDX"] = player_id
        sgai.write_record(record_idx, values)

    def write_roster_entry(
        self,
        tdb: TDBFile,
        record_idx: int,
        team_index: int,
        jersey: int,
        player_id: int,
        captain: int = 0,
        dressed: int = 1,
        line_flags: Optional[Dict[str, int]] = None,
    ):
        """Update a ROST record."""
        rost = tdb.get_table("ROST")
        if not rost or record_idx >= rost.capacity:
            return

        values = {
            "TEAM": team_index,
            "JERS": jersey,
            "INDX": player_id,
            "CAPT": captain,
            "DRES": dressed,
        }

        # Clear all line flags first
        for flag in LINE_FLAGS:
            values[flag] = 0

        # Set specified line flags
        if line_flags:
            for flag, val in line_flags.items():
                if flag in LINE_FLAGS:
                    values[flag] = val

        rost.write_record(record_idx, values)

    def rebuild_and_write(
        self,
        modified_tdbs: Dict[str, TDBFile],
        on_progress: Optional[Callable[[float, str], None]] = None,
    ) -> bool:
        """Recompress modified TDB files, rebuild BIGF, write to ISO.

        Args:
            modified_tdbs: dict mapping TDB filename → modified TDBFile
            on_progress: progress callback
        """
        if not self._db_viv or not self.reader:
            return False

        try:
            # In-place replacement: write modified TDB data at original
            # offsets within the BIGF, preserving all file positions.
            # This avoids shifting file offsets which crashes the game.
            new_viv = bytearray(self._db_viv)
            total = len(modified_tdbs)

            for i, (tdb_name, tdb_file) in enumerate(modified_tdbs.items()):
                if on_progress:
                    on_progress(
                        0.3 + (i / max(total, 1)) * 0.4,
                        f"Compressing {tdb_name}...",
                    )

                serialized = tdb_file.serialize()
                compressed = refpack_compress(serialized)

                # Try in-place: write at original offset, pad if smaller.
                # If compressed data is larger than the original allocation,
                # skip this file — the master TDB has all tables so split
                # TDBs (nhlbioatt.tdb, nhlrost.tdb) can stay unchanged.
                bigf_replace_inplace(new_viv, tdb_name, compressed)

            if on_progress:
                on_progress(0.7, "Writing db.viv to ISO...")

            # Find db.viv location in ISO and write back
            reader_for_loc = NHL07PSPRomReader(self.output_path)
            reader_for_loc.load()
            db_lba, db_orig_size, db_max_size = (
                reader_for_loc.find_db_viv_location()
            )
            if db_lba == 0:
                return False

            new_viv_bytes = bytes(new_viv)

            # Check if new data fits in available ISO space
            if len(new_viv_bytes) > db_max_size:
                self._last_error = (
                    f"New db.viv ({len(new_viv_bytes)} bytes) exceeds "
                    f"ISO allocation ({db_max_size} bytes)"
                )
                return False

            # Write to ISO at original location (same size = no ISO changes)
            with open(self.output_path, "r+b") as f:
                f.seek(db_lba * ISO_SECTOR_SIZE)
                f.write(new_viv_bytes)
                # Zero-fill remaining space to original size
                remaining = db_orig_size - len(new_viv_bytes)
                if remaining > 0:
                    f.write(b"\x00" * remaining)

            # Update ISO 9660 directory entry size if db.viv size changed
            new_size = len(new_viv_bytes)
            if new_size != db_orig_size:
                dir_entry_offset = reader_for_loc.find_db_viv_dir_entry_offset()
                if dir_entry_offset > 0:
                    with open(self.output_path, "r+b") as f:
                        # Size (LE) at record offset +10
                        f.seek(dir_entry_offset + 10)
                        f.write(struct.pack("<I", new_size))
                        # Size (BE) at record offset +14
                        f.seek(dir_entry_offset + 14)
                        f.write(struct.pack(">I", new_size))

            if on_progress:
                on_progress(1.0, "Complete")

            return True

        except Exception as e:
            self._last_error = str(e)
            import traceback

            self._last_traceback = traceback.format_exc()
            return False
