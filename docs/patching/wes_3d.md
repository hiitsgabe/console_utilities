# WE2002 3D Jersey Color Patching

## Problem

When patching WE2002 team data, the 2D jersey previews in menus change correctly (via the maglia palette), but the 3D in-game jerseys keep the original team's colors. This is because the maglia palette only controls:

- **2D menu preview** (team selection screen)
- **3D shorts**

The **3D shirt body** is controlled by separate TEX files stored on the CD.

## What Controls What

| Visual Element     | Data Source                        | Editable Via       |
|--------------------|------------------------------------|--------------------|
| 2D menu preview    | Maglia palette (SELECT2.BIN)       | ROM byte offsets   |
| 3D shorts          | Maglia palette entries 10-14       | ROM byte offsets   |
| 3D shirt body      | TEX file CLUT at VRAM Y=486       | CD file system     |
| Skin/face          | TEX file CLUT at VRAM Y=488       | CD file system     |
| Boots/accessories  | TEX file CLUT at VRAM Y=480       | CD file system     |
| Numbers/details    | Baked into TEX bitmap pixel data   | CD file system     |

## TEX File Layout

Each team has a TEX file (`BIN/TEX_XX.BIN`) containing everything needed to render players in 3D:

- **TEX_00 to TEX_62** = 63 national teams
- **TEX_63 to TEX_94** = 32 Master League teams (`TEX index = 63 + ml_slot_index`)

### CD Location Formula

```
LBA = 8400 + file_number * 20
```

Each file is allocated 20 sectors (40,960 bytes max). Actual sizes vary ~26-34KB.

### Internal Structure

```
[0x00-0x2F]  48-byte pointer table: 12 PSX RAM pointers (0x800Fxxxx)
[sections]   Mix of 0x000A (GPU texture) and 0xFF09 (CLUT palette) sections
```

**Section types:**

| Type   | Purpose                    | Contains                              |
|--------|----------------------------|---------------------------------------|
| 0x000A | GPU texture transfer       | 8bpp pixel data (jersey fabric/folds) |
| 0xFF09 | CLUT palette upload        | 256 BGR555 color entries              |

**CLUTs per TEX file (5 total):**

| #  | VRAM Y | Purpose              |
|----|--------|----------------------|
| 1  | 486    | Home jersey colors   |
| 2  | 488    | Home skin/face       |
| 3  | 486    | Away jersey colors   |
| 4  | 488    | Away skin/face       |
| 5  | 480    | Boots (shared)       |

## Solution: Copy Whole TEX Files by Color Match

### Why Other Approaches Fail

1. **Generating CLUTs from scratch** - Breaks the bitmap-to-CLUT pairing. The 8bpp bitmap pixels are indices into the 256-entry CLUT. Replacing the CLUT with generated gradients produces wrong colors and UI glitches because the pixel indices were authored for the original palette distribution.

2. **Swapping only CLUTs between TEX files** - Does NOT change the visible jersey color. Each TEX file's bitmap pixels use specific index distributions paired with its own CLUT. Swapping only the CLUT puts the wrong color mapping on pixel indices that expect different values.

3. **Copying whole TEX without EDC fix** - Game crashes (black screen when starting a match). PS1 CD-ROM Mode 2 Form 1 sectors contain EDC checksums that must be recalculated after modifying sector data.

### Working Approach

Copy the **entire TEX file** (bitmaps + CLUTs together) from a color-matched source team into the target slot, then recalculate EDC checksums on all modified sectors.

**Constraints:**
- Source TEX file size must be **<= target slot's ISO9660 file size** (the game reads the size from the CD directory and will truncate larger files, cutting off sections and causing crashes)
- Pad remaining bytes with zeros
- Recalculate EDC on every modified sector

### Implementation

#### 1. Reading a TEX file from CD sectors

PS1 CD-ROM Mode 2 sectors: 2352 bytes total, 24-byte header, 2048 bytes user data.

```python
def read_cd_file(rom_data, lba, size):
    result = bytearray()
    current_lba = lba
    remaining = size
    while remaining > 0:
        sector_offset = current_lba * 2352 + 24
        chunk = min(remaining, 2048)
        result.extend(rom_data[sector_offset:sector_offset + chunk])
        remaining -= chunk
        current_lba += 1
    return bytes(result)
```

#### 2. Writing with EDC recalculation

```python
def edc_compute(data):
    """CRC-32 with CD-ROM polynomial 0xD8018001."""
    edc_table = []
    for i in range(256):
        edc = i
        for _ in range(8):
            if edc & 1:
                edc = (edc >> 1) ^ 0xD8018001
            else:
                edc >>= 1
        edc_table.append(edc)
    crc = 0
    for b in data:
        crc = edc_table[(crc ^ b) & 0xFF] ^ (crc >> 8)
    return crc


def write_cd_file_with_edc(rom, lba, file_data):
    """Write file data to CD sectors, recalculating EDC checksums."""
    current_lba = lba
    offset = 0
    while offset < len(file_data):
        sector_off = current_lba * 2352
        user_off = sector_off + 24
        chunk = min(len(file_data) - offset, 2048)

        # Write user data
        rom[user_off:user_off + chunk] = file_data[offset:offset + chunk]

        # Recalculate EDC over bytes 16..2071 (subheader + user data)
        new_edc = edc_compute(rom[sector_off + 16:sector_off + 2072])
        struct.pack_into("<I", rom, sector_off + 2072, new_edc)

        offset += chunk
        current_lba += 1
```

#### 3. Patching a team's 3D jersey

```python
def patch_3d_jersey(rom, target_team_index, source_team_index, tex_sizes):
    """Copy source team's TEX file into target slot."""
    src_lba = 8400 + source_team_index * 20
    dst_lba = 8400 + target_team_index * 20

    src_size = tex_sizes[source_team_index]
    dst_size = tex_sizes[target_team_index]

    assert src_size <= dst_size, (
        f"Source TEX ({src_size}b) exceeds target slot ({dst_size}b)"
    )

    src_data = read_cd_file(rom, src_lba, src_size)

    # Pad to target size
    padded = bytearray(src_data) + bytearray(dst_size - src_size)

    write_cd_file_with_edc(rom, dst_lba, bytes(padded))
```

#### 4. Color matching

To find the best source TEX for a target color, extract the dominant jersey color from each TEX file's home CLUT (Y=486) and find the closest match by Euclidean distance in RGB space.

```python
def get_tex_dominant_color(tex_data):
    """Extract dominant jersey color from TEX file's home CLUT."""
    base = 0x800F0000
    ptrs = set()
    for i in range(0, 48, 4):
        val = struct.unpack_from("<I", tex_data, i)[0]
        if base <= val < base + 0x10000:
            ptrs.add(val - base)

    for off in sorted(ptrs):
        if off >= len(tex_data) - 2:
            continue
        if struct.unpack_from("<H", tex_data, off)[0] != 0xFF09:
            continue
        if struct.unpack_from("<H", tex_data, off + 4)[0] != 486:
            continue

        # Sample CLUT entries 2-20 for dominant color
        clut_start = off + 32
        colors = struct.unpack_from("<256H", tex_data, clut_start)
        rs, gs, bs = [], [], []
        for ci in range(2, 20):
            r, g, b = bgr555_to_rgb(colors[ci])
            rs.append(r); gs.append(g); bs.append(b)
        return (sum(rs)//len(rs), sum(gs)//len(gs), sum(bs)//len(bs))

    return (128, 128, 128)  # fallback gray


def find_best_tex_match(target_rgb, tex_catalog, max_size):
    """Find TEX index with closest color that fits in max_size."""
    best_idx = None
    best_dist = float('inf')
    for idx, (color, size) in tex_catalog.items():
        if size > max_size:
            continue
        dist = sum((a - b) ** 2 for a, b in zip(target_rgb, color))
        if dist < best_dist:
            best_dist = dist
            best_idx = idx
    return best_idx
```

## BGR555 Color Format

```
Bit layout: 0 BBBBB GGGGG RRRRR
            15 14-10  9-5   4-0

To RGB888:
  r5 = val & 0x1F
  g5 = (val >> 5) & 0x1F
  b5 = (val >> 10) & 0x1F
  R = (r5 << 3) | (r5 >> 2)
  G = (g5 << 3) | (g5 >> 2)
  B = (b5 << 3) | (b5 >> 2)
```

## TEX File Sizes (from ISO9660 directory)

```python
TEX_SIZES = {
    0:29944, 1:30676, 2:30956, 3:29964, 4:30428, 5:31652, 6:29044, 7:30016,
    8:29656, 9:31056, 10:29312, 11:31860, 12:30848, 13:30372, 14:31188,
    15:31412, 16:31680, 17:30340, 18:30264, 19:32380, 20:31116, 21:31596,
    22:30772, 23:31492, 24:31072, 25:30808, 26:31936, 27:31048, 28:30812,
    29:30404, 30:31168, 31:30532, 32:30912, 33:30424, 34:31464, 35:29540,
    36:30444, 37:32000, 38:27296, 39:31116, 40:31196, 41:27572, 42:27196,
    43:26664, 44:28076, 45:28420, 46:27020, 47:30712, 48:30368, 49:27424,
    50:28724, 51:28304, 52:25948, 53:27412, 54:32168, 55:32376, 56:29108,
    57:29032, 58:29088, 59:29384, 60:28980, 61:29936, 62:29928, 63:30516,
    64:30748, 65:29664, 66:29300, 67:29612, 68:31888, 69:31056, 70:29900,
    71:27328, 72:28280, 73:30464, 74:31248, 75:31520, 76:26456, 77:31872,
    78:28496, 79:28372, 80:26156, 81:27272, 82:26844, 83:32244, 84:27928,
    85:26492, 86:28456, 87:27588, 88:28648, 89:33284, 90:26720, 91:28208,
    92:26656, 93:26560, 94:26648,
}
```

## Integration Notes

- `rom_writer.py:1268` comment "CLUT controls BOTH 2D and 3D" is **wrong** -- maglia only controls 2D + shorts
- `patcher.py:120` has a similar incorrect comment about ESPN colors controlling 3D
- After writing maglia (2D preview), also call `patch_3d_jersey()` to update the TEX file
- Build TEX color catalog once at ROM load time, then reuse for all team patches

