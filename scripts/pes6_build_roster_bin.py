#!/usr/bin/env python3
"""
Build assets/pes6_roster_map.bin from PES6 EUR CSV data + ISO player positions.

Reads team/roster CSVs (extracted from pesapi database) and player positions
from the PES6 EUR ISO's decompressed player DB.

Binary format: PES6RM magic + version(u16) + orig_size(u32) + comp_size(u32) + zlib(JSON)

Usage:
    python scripts/pes6_build_roster_bin.py <path_to_pes6_eur.iso>
"""
import csv
import json
import os
import struct
import sys
import zlib

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROSTER_CSV = os.path.join(SCRIPT_DIR, "pes6_eur_roster.csv")
TEAMS_CSV = os.path.join(SCRIPT_DIR, "pes6_eur_teams.csv")
OUTPUT_BIN = os.path.join(SCRIPT_DIR, "..", "assets", "pes6_roster_map.bin")

RECORD_SIZE = 124


def read_iso_db(iso_path):
    """Decompress the player DB from the PES6 EUR ISO."""
    sys.path.insert(0, os.path.join(SCRIPT_DIR, "..", "src"))
    import importlib.util as ilu
    import types

    # Stub dependencies for standalone execution
    for m in ["constants", "utils", "utils.logging"]:
        if m not in sys.modules:
            sys.modules[m] = types.ModuleType(m)
    sys.modules["constants"].BUILD_TARGET = "source"
    sys.modules["constants"].DEV_MODE = True
    sys.modules["utils.logging"].log_error = lambda *a: None
    sys.modules["services"] = types.ModuleType("services")
    sys.modules["services"].__path__ = [os.path.join(SCRIPT_DIR, "..", "src", "services")]
    pkg = types.ModuleType("services.pes6_ps2_patcher")
    pkg.__path__ = [os.path.join(SCRIPT_DIR, "..", "src", "services", "pes6_ps2_patcher")]
    sys.modules["services.pes6_ps2_patcher"] = pkg
    sa = types.ModuleType("services.sports_api")
    sam = types.ModuleType("services.sports_api.models")
    for cls in ["League", "Player", "PlayerStats", "Team", "TeamRoster", "LeagueData"]:
        setattr(sam, cls, type(cls, (), {}))
    sys.modules["services.sports_api"] = sa
    sys.modules["services.sports_api.models"] = sam

    mspec = ilu.spec_from_file_location(
        "services.pes6_ps2_patcher.models",
        os.path.join(SCRIPT_DIR, "..", "src", "services", "pes6_ps2_patcher", "models.py"),
    )
    mmod = ilu.module_from_spec(mspec)
    sys.modules["services.pes6_ps2_patcher.models"] = mmod
    mspec.loader.exec_module(mmod)

    rspec = ilu.spec_from_file_location(
        "services.pes6_ps2_patcher.rom_reader",
        os.path.join(SCRIPT_DIR, "..", "src", "services", "pes6_ps2_patcher", "rom_reader.py"),
    )
    rmod = ilu.module_from_spec(rspec)
    rmod.__package__ = "services.pes6_ps2_patcher"
    rspec.loader.exec_module(rmod)

    reader = rmod.RomReader(iso_path)
    rom_info = reader.validate()
    if not rom_info.is_valid:
        print(f"Invalid ISO: {iso_path}")
        sys.exit(1)

    with open(iso_path, "rb") as f:
        db = reader._decompress_wesys(f, rom_info.file35_offset, rom_info.file35_size)

    print(f"ISO: {rom_info.num_players} players, DB: {len(db)} bytes")
    return db


def get_position(db, player_id):
    """Read registered position from decompressed player DB."""
    off = player_id * RECORD_SIZE
    pos_off = off + 48 + 5  # regPos: offset 6 from byte 48, read 16-bit LE from [off-1, off]
    if pos_off + 1 >= len(db):
        return 0
    return ((db[pos_off] | (db[pos_off + 1] << 8)) >> 4) & 0x0F


def get_name(db, player_id):
    """Read player name from decompressed player DB."""
    off = player_id * RECORD_SIZE
    if off + 32 > len(db):
        return ""
    try:
        return db[off : off + 32].decode("utf-16-le").split("\x00")[0]
    except Exception:
        return ""


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <path_to_pes6_eur.iso>")
        sys.exit(1)

    iso_path = sys.argv[1]
    db = read_iso_db(iso_path)

    # Read teams CSV
    teams = {}
    with open(TEAMS_CSV) as f:
        for row in csv.DictReader(f):
            tid = int(row["team_id"])
            teams[tid] = {
                "name": row["team_name"],
                "real_name": row["team_real_name"] or row["team_name"],
                "abbr": row["team_short"],
                "league": row["league"],
                "category": row["league_category"],
            }

    # Read roster CSV — club teams only
    team_players = {}
    with open(ROSTER_CSV) as f:
        for row in csv.DictReader(f):
            if row["league_category"] != "Club":
                continue
            tid = int(row["team_id"])
            pid = int(row["player_id"])

            if tid not in team_players:
                team_players[tid] = []

            pos = get_position(db, pid)
            iso_name = get_name(db, pid)

            team_players[tid].append(
                {
                    "idx": pid,
                    "pos": pos,
                    "name": iso_name or row["player_name"],
                    "shirt": int(row["shirt_number"]) if row["shirt_number"] else 0,
                    "starter": int(row["starter"]),
                }
            )

    # Build JSON
    roster_json = {
        "meta": {
            "version": "pes6-eur",
            "game_id": "SLES-54203",
            "source": "pesapi + ISO positions",
            "total_teams": len(team_players),
            "total_players": sum(len(v) for v in team_players.values()),
        },
        "teams": {},
    }

    for tid in sorted(team_players.keys()):
        t = teams[tid]
        players = team_players[tid]
        # Sort: starters first, then by shirt number
        players.sort(key=lambda p: (-p["starter"], p["shirt"]))

        roster_json["teams"][str(tid)] = {
            "name": t["name"],
            "real_name": t["real_name"],
            "abbr": t["abbr"],
            "league": t["league"],
            "ri": tid,
            "player_count": len(players),
            "players": players,
        }

    # Compress and write binary
    json_bytes = json.dumps(roster_json, separators=(",", ":")).encode("utf-8")
    compressed = zlib.compress(json_bytes, 9)
    header = (
        b"PES6RM"
        + struct.pack("<H", 4)  # Version 4
        + struct.pack("<I", len(json_bytes))
        + struct.pack("<I", len(compressed))
    )

    with open(OUTPUT_BIN, "wb") as f:
        f.write(header + compressed)

    print(f"Teams: {len(team_players)}")
    print(f"Players: {sum(len(v) for v in team_players.values())}")
    print(f"JSON: {len(json_bytes)} bytes -> Binary: {len(header) + len(compressed)} bytes")
    print(f"Written to: {OUTPUT_BIN}")

    # Show sample
    for tid in sorted(team_players.keys())[:3]:
        t = teams[tid]
        p = team_players[tid]
        print(f"  [{tid}] {t['real_name']} ({t['abbr']}): {len(p)} players")
        for pl in p[:3]:
            s = "*" if pl["starter"] else ""
            print(f"    ID={pl['idx']:5d} pos={pl['pos']:2d} #{pl['shirt']:2d} {pl['name']} {s}")


if __name__ == "__main__":
    main()
