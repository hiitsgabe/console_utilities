"""PES 6 Option File generator.

Generates a PES 6 option file (.npo format) with updated player names
from ESPN data. Uses a decrypted template from the ACTION EXTREME patch
as a base, modifies player names, re-encrypts, and wraps in nPort container.

Format:
  - NPO = 6984-byte nPort header + 1,191,936 encrypted OF data
  - OF block 4 (offset 37116): 5000 player records, 124 bytes each
  - Player name: UTF-16LE, 32 bytes at record offset 0
  - Shirt name: ASCII, 16 bytes at record offset 32
"""

import os
import struct
import unicodedata
from typing import List, Optional, Tuple

# PES6 option file block structure
OF_LENGTH = 1191936
OF_BLOCK = [12, 5144, 9544, 14288, 37116, 657956, 751472, 763804, 911144, 1170520]
OF_BLOCK_SIZE = [4844, 1268, 4730, 22816, 620000, 93501, 12320, 147328, 259364, 21032]

PLAYER_START = 37116
PLAYER_RECORD_SIZE = 124
PLAYER_COUNT = 5000
PLAYER_NAME_SIZE = 32  # UTF-16LE, 15 chars max + null
SHIRT_NAME_SIZE = 16  # ASCII

# NPO header size (nPort container with icon data)
NPO_HEADER_SIZE = 6984

# Assets directory
_ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")


def _load_key():
    """Load the PES6 encryption key."""
    key_path = os.path.join(_ASSETS_DIR, "pes6_key.py")
    ns = {}
    with open(key_path) as f:
        exec(f.read(), ns)
    return ns["PES6_KEY"]


def _load_template():
    """Load the decrypted option file template."""
    path = os.path.join(_ASSETS_DIR, "of_template_decrypted.bin")
    with open(path, "rb") as f:
        return bytearray(f.read()[:OF_LENGTH])


def _load_npo_header():
    """Load the nPort container header."""
    path = os.path.join(_ASSETS_DIR, "npo_header.bin")
    with open(path, "rb") as f:
        return f.read()


def _clean_name(name: str) -> str:
    """Strip accents and special chars for ASCII-safe text."""
    nfkd = unicodedata.normalize("NFKD", name)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _zfrs(val, n):
    """Zero-fill right shift (unsigned)."""
    return (val % 0x100000000) >> n


def encrypt_of(data: bytearray, key: list):
    """Encrypt option file data in-place."""
    for i in range(1, min(10, len(OF_BLOCK))):
        k = 0
        a = OF_BLOCK[i]
        while a + 4 <= OF_BLOCK[i] + OF_BLOCK_SIZE[i] and a + 4 <= len(data):
            p = struct.unpack_from("<I", data, a)[0]
            c = key[k] + ((p ^ 0x7AB3684C) - 0x7AB3684C)
            data[a] = c & 0xFF
            data[a + 1] = _zfrs(c, 8) & 0xFF
            data[a + 2] = _zfrs(c, 16) & 0xFF
            data[a + 3] = _zfrs(c, 24) & 0xFF
            k = (k + 1) % 446
            a += 4


def checksums(data: bytearray):
    """Recalculate block checksums."""
    for i in range(len(OF_BLOCK)):
        checksum = 0
        end = OF_BLOCK[i] + OF_BLOCK_SIZE[i] if i < len(OF_BLOCK_SIZE) else len(data)
        for a in range(OF_BLOCK[i], min(end, len(data) - 3), 4):
            checksum += struct.unpack_from("<I", data, a)[0]
        checksum &= 0xFFFFFFFF
        ck_off = OF_BLOCK[i] - 8
        if ck_off >= 0:
            data[ck_off] = checksum & 0xFF
            data[ck_off + 1] = _zfrs(checksum, 8) & 0xFF
            data[ck_off + 2] = _zfrs(checksum, 16) & 0xFF
            data[ck_off + 3] = _zfrs(checksum, 24) & 0xFF


def write_player_name(data: bytearray, player_index: int, name: str, shirt: str = ""):
    """Write a player name into the option file data.

    Args:
        data: Decrypted option file bytearray.
        player_index: 0-4999.
        name: Player display name (max 15 chars).
        shirt: Shirt name (max 15 chars ASCII). Auto-generated if empty.
    """
    if player_index < 0 or player_index >= PLAYER_COUNT:
        return

    off = PLAYER_START + player_index * PLAYER_RECORD_SIZE

    # Write name (UTF-16LE, 32 bytes)
    clean = _clean_name(name)[:15]
    name_bytes = clean.encode("utf-16-le")
    data[off : off + PLAYER_NAME_SIZE] = b"\x00" * PLAYER_NAME_SIZE
    data[off : off + min(len(name_bytes), PLAYER_NAME_SIZE - 2)] = name_bytes[
        : PLAYER_NAME_SIZE - 2
    ]

    # Write shirt name (ASCII, 16 bytes at offset +32)
    if not shirt:
        # Auto-generate: last name, uppercase
        parts = clean.split()
        shirt = (parts[-1] if parts else clean).upper()[:15]
    shirt_bytes = shirt.encode("ascii", errors="replace")[:SHIRT_NAME_SIZE - 1]
    data[off + 32 : off + 32 + SHIRT_NAME_SIZE] = b"\x00" * SHIRT_NAME_SIZE
    data[off + 32 : off + 32 + len(shirt_bytes)] = shirt_bytes

    # Mark as name-edited (byte 3 bit 0)
    data[off + 48] |= 0x01
    # Mark as shirt-edited (byte 3 bit 1)
    data[off + 48] |= 0x02


def generate_npo(
    league_data,
    on_progress=None,
) -> bytes:
    """Generate a complete NPO file with updated player names.

    Args:
        league_data: LeagueData with teams and player rosters.
        on_progress: Optional callback(progress, message).

    Returns:
        Complete NPO file as bytes, ready to write to ISO.
    """
    if on_progress:
        on_progress(0.0, "Loading template...")

    key = _load_key()
    of_data = _load_template()
    npo_header = _load_npo_header()

    if on_progress:
        on_progress(0.1, "Writing player names...")

    # Write ESPN player names into the template
    # The template already has ~5000 player slots
    # We overwrite starting from player index 1 (0 is empty)
    player_idx = 1
    total_teams = len(league_data.teams) if hasattr(league_data, "teams") else 0

    for team_idx, team_roster in enumerate(league_data.teams):
        if on_progress:
            pct = 0.1 + 0.6 * (team_idx / max(total_teams, 1))
            team_name = team_roster.team.name if hasattr(team_roster.team, "name") else ""
            on_progress(pct, f"Writing {team_name}...")

        players = team_roster.players if hasattr(team_roster, "players") else []

        for player in players:
            if player_idx >= PLAYER_COUNT:
                break

            pname = player.name if hasattr(player, "name") else str(player)
            write_player_name(of_data, player_idx, pname)
            player_idx += 1

    if on_progress:
        on_progress(0.7, "Encrypting option file...")

    # Recalculate checksums and encrypt
    checksums(of_data)
    encrypt_of(of_data, key)

    if on_progress:
        on_progress(0.9, "Building NPO file...")

    # Combine header + encrypted OF
    npo = npo_header + bytes(of_data)

    if on_progress:
        on_progress(1.0, f"Done! {player_idx - 1} players written")

    return npo
