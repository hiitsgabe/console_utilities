#!/usr/bin/env python3
"""
Build assets/pes6_roster_map.bin from PES6 EUR PCSX2 save state.

Extracts team names and player ID mappings from EE RAM. Each club team
has exactly 32 contiguous player IDs in the player DB.

Binary format: PES6RM magic + version(u16) + orig_size(u32) + comp_size(u32) + zlib(JSON)
"""
import struct
import json
import zlib
import sys
import os

# PES6 EUR RAM addresses (discovered from SLES-54203 save state analysis)
ARSENAL_NAME_ADDR = 0x003DDCA8  # "Arsenal\0" in team name table
CLUB_PLAYER_BASE_ID = 1338  # 1-based, first club team's first player in DB
DB_START = 0x018415B0  # Start of player DB in RAM
RECORD_SIZE = 124  # Bytes per player record
PLAYERS_PER_TEAM = 32


def extract_ee_ram(path):
    """Extract EE RAM from PCSX2 save state (.p2s)."""
    import zstandard

    with open(path, "rb") as f:
        data = f.read()
    pos = 0
    while pos < len(data):
        idx = data.find(b"PK\x03\x04", pos)
        if idx == -1:
            break
        comp_size = struct.unpack_from("<I", data, idx + 18)[0]
        uncomp_size = struct.unpack_from("<I", data, idx + 22)[0]
        fname_len = struct.unpack_from("<H", data, idx + 26)[0]
        extra_len = struct.unpack_from("<H", data, idx + 28)[0]
        fname = data[idx + 30 : idx + 30 + fname_len]
        data_start = idx + 30 + fname_len + extra_len
        if fname == b"eeMemory.bin":
            dctx = zstandard.ZstdDecompressor()
            return dctx.decompress(
                data[data_start : data_start + comp_size],
                max_output_size=uncomp_size,
            )
        pos = data_start + comp_size if comp_size > 0 else idx + 4
    return None


def parse_team_name_entry(ram, offset):
    """Parse a variable-length team name entry.

    Format: name (padded to 8-byte boundary, null-terminated) + abbreviation (8 bytes).
    Returns (name, abbreviation, total_entry_size) or None if invalid.
    """
    # Read name (scan for null, then round up to 8-byte boundary)
    name_end = ram.find(b"\x00", offset, offset + 48)
    if name_end == -1:
        return None
    name = ram[offset:name_end].decode("ascii", errors="replace")
    if not name or not name[0].isalpha():
        return None

    # Name field: padded to 8-byte boundary
    name_field_size = ((len(name) + 9) // 8) * 8

    # Abbreviation follows: 8 bytes
    abbr_offset = offset + name_field_size
    abbr = ram[abbr_offset : abbr_offset + 8].split(b"\x00")[0].decode("ascii", errors="replace")

    entry_size = name_field_size + 8
    return name, abbr, entry_size


def get_player_name(ram, idx_1based):
    """Read player name from DB by 1-based index."""
    off = DB_START + (idx_1based - 1) * RECORD_SIZE
    if off < 0 or off + 32 > len(ram):
        return ""
    try:
        return ram[off : off + 32].decode("utf-16-le").split("\x00")[0]
    except Exception:
        return ""


def get_player_position(ram, idx_1based):
    """Read player's registered position from DB (byte 48+6, bits 4-7)."""
    off = DB_START + (idx_1based - 1) * RECORD_SIZE
    abs_pos = off + 48 + 6  # regPos offset relative to byte 48
    if abs_pos < 0 or abs_pos >= len(ram):
        return 0
    # 16-bit LE read from [abs_pos-1, abs_pos], shift 4, mask 0x0F
    lo = ram[abs_pos - 1]
    hi = ram[abs_pos]
    val = (lo | (hi << 8)) >> 4
    return val & 0x0F


def find_club_teams(ram):
    """Parse club team names starting from Arsenal.

    Returns list of (name, abbreviation, team_index) tuples.
    """
    teams = []
    offset = ARSENAL_NAME_ADDR
    team_idx = 0

    consecutive_nulls = 0
    while offset < len(ram) - 32:
        result = parse_team_name_entry(ram, offset)
        if result is None:
            # Skip 8-byte null padding blocks
            if ram[offset : offset + 8] == b"\x00" * 8:
                offset += 8
                consecutive_nulls += 1
                if consecutive_nulls > 4:  # Too many gaps = end of table
                    break
                continue
            break
        consecutive_nulls = 0

        name, abbr, entry_size = result
        teams.append((name, abbr, team_idx))
        offset += entry_size
        team_idx += 1

        # Safety limit
        if team_idx > 300:
            break

    return teams


def find_national_teams(ram):
    """Parse national team names by scanning backwards from Arsenal.

    Returns list of (name, abbreviation, team_index) in reverse order.
    """
    # Scan backwards from Arsenal to find national teams
    teams = []
    offset = ARSENAL_NAME_ADDR

    # Go back one entry at a time
    # We need to find entry boundaries going backwards, which is tricky
    # with variable-length entries. Use a heuristic: scan back for abbreviation
    # patterns (3 uppercase letters followed by nulls at 8-byte boundaries)
    # For now, just report that we found the club teams and national teams
    # need a separate approach.
    return teams


def main():
    ss_path = (
        sys.argv[1]
        if len(sys.argv) > 1
        else os.path.expanduser(
            "~/Library/Application Support/PCSX2/sstates/SLES-54203 (7D2AF924).01.p2s"
        )
    )

    print(f"Reading save state: {ss_path}")
    ram = extract_ee_ram(ss_path)
    if ram is None:
        print("Failed to extract EE RAM")
        sys.exit(1)
    print(f"EE RAM: {len(ram)} bytes ({len(ram) / 1024 / 1024:.1f} MB)")

    # Parse club teams from name table
    club_teams = find_club_teams(ram)
    print(f"Found {len(club_teams)} club teams")

    # Build roster map
    teams_json = {}
    total_players = 0

    for name, abbr, team_idx in club_teams:
        start_id = CLUB_PLAYER_BASE_ID + team_idx * PLAYERS_PER_TEAM
        players = []

        for slot in range(PLAYERS_PER_TEAM):
            pid = start_id + slot
            pos = get_player_position(ram, pid)
            player_name = get_player_name(ram, pid)
            if player_name:  # Only include players with names
                players.append({"idx": pid, "pos": pos, "name": player_name})

        teams_json[str(team_idx)] = {
            "name": name,
            "abbr": abbr,
            "ri": team_idx,
            "player_count": len(players),
            "players": players,
        }
        total_players += len(players)

        # Show first team as verification
        if team_idx < 3:
            first_names = [get_player_name(ram, p["idx"]) for p in players[:3]]
            print(f"  [{team_idx}] {name} ({abbr}): {len(players)} players, first: {first_names}")

    compact = {
        "meta": {
            "version": "pes6-eur",
            "game_id": "SLES-54203",
            "arsenal_name_addr": f"0x{ARSENAL_NAME_ADDR:08X}",
            "club_player_base_id": CLUB_PLAYER_BASE_ID,
            "players_per_team": PLAYERS_PER_TEAM,
            "total_players": total_players,
            "total_teams": len(teams_json),
        },
        "teams": teams_json,
    }

    # Serialize and compress
    json_bytes = json.dumps(compact, separators=(",", ":")).encode("utf-8")
    compressed = zlib.compress(json_bytes, 9)

    # Write binary
    magic = b"PES6RM"
    version = struct.pack("<H", 3)  # Version 3 = PES6 EUR format
    header = (
        magic
        + version
        + struct.pack("<I", len(json_bytes))
        + struct.pack("<I", len(compressed))
    )
    output = header + compressed

    out_path = os.path.join(os.path.dirname(__file__), "..", "assets", "pes6_roster_map.bin")
    with open(out_path, "wb") as f:
        f.write(output)

    print(f"\nTeams: {len(teams_json)}")
    print(f"Total players: {total_players}")
    print(f"JSON: {len(json_bytes)} bytes -> Binary: {len(output)} bytes")
    print(f"Written to: {out_path}")


if __name__ == "__main__":
    main()
