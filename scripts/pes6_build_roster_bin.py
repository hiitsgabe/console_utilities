#!/usr/bin/env python3
"""
Build assets/pes6_roster_map.bin from PCSX2 save state + ISO.
Binary format: PES6RM magic + version(u16) + orig_size(u32) + comp_size(u32) + zlib(JSON)
"""
import struct
import json
import zlib
import zstandard
import mmap
import sys
import os


def extract_ee_ram(path):
    with open(path, 'rb') as f:
        data = f.read()
    pos = 0
    while pos < len(data):
        idx = data.find(b'PK\x03\x04', pos)
        if idx == -1:
            break
        comp_method = struct.unpack_from('<H', data, idx + 8)[0]
        comp_size = struct.unpack_from('<I', data, idx + 18)[0]
        uncomp_size = struct.unpack_from('<I', data, idx + 22)[0]
        fname_len = struct.unpack_from('<H', data, idx + 26)[0]
        extra_len = struct.unpack_from('<H', data, idx + 28)[0]
        fname = data[idx + 30:idx + 30 + fname_len]
        data_start = idx + 30 + fname_len + extra_len
        if fname == b'eeMemory.bin':
            dctx = zstandard.ZstdDecompressor()
            return dctx.decompress(data[data_start:data_start + comp_size],
                                   max_output_size=uncomp_size)
        pos = data_start + comp_size if comp_size > 0 else idx + 4
    return None




def main():
    ss_path = sys.argv[1] if len(sys.argv) > 1 else \
        os.path.expanduser("~/Library/Application Support/PCSX2/sstates/SLPM-66374 (DF7C80A6).01.p2s")

    ram = extract_ee_ram(ss_path)
    if ram is None:
        print("Failed to extract RAM")
        sys.exit(1)

    TABLE_START = 0x018D7ADA  # PES6 EUR (SLES-54203)
    TEAM_SIZE = 32
    STRIDE = 64

    compact = {
        "meta": {
            "table_start": f"0x{TABLE_START:08X}",
            "team_size": TEAM_SIZE,
            "stride": STRIDE,
            "slpm_offset": 0,
            "total_players_in_db": 4784,
        },
        "teams": {},
        "aliases": {},  # espn_name_pattern -> ram_index
    }

    for ram_idx in range(0, 200):
        addr = TABLE_START + ram_idx * STRIDE
        if addr + STRIDE > len(ram):
            break

        roster_slots = []
        for i in range(TEAM_SIZE):
            v = struct.unpack_from('<H', ram, addr + i * 2)[0]
            roster_slots.append(v)

        player_ids = [p for p in roster_slots if 1 <= p <= 4848]
        if not player_ids:
            continue

        compact["teams"][str(ram_idx)] = {
            "ri": ram_idx,
            "si": ram_idx - 21,
            "rs": roster_slots,
            "pi": player_ids,
        }

    json_bytes = json.dumps(compact, separators=(',', ':')).encode('utf-8')
    compressed = zlib.compress(json_bytes, 9)
    magic = b'PES6RM'
    version = struct.pack('<H', 2)
    header = magic + version + struct.pack('<I', len(json_bytes)) + struct.pack('<I', len(compressed))
    output = header + compressed

    out_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'pes6_roster_map.bin')
    with open(out_path, 'wb') as f:
        f.write(output)

    print(f'Teams: {len(compact["teams"])}')
    print(f'Aliases: {len(compact["aliases"])}')
    print(f'JSON: {len(json_bytes)} bytes -> Binary: {len(output)} bytes')


if __name__ == '__main__':
    main()
