# PES 6 / WE10 PS2 ISO Roster Research

## Research ISOs
- `Bomba_Patch_77.iso` (1.9GB) - Bomba Patch 77 Geomatrix, Brazilian mod based on PES6/WE10
- `WE10_PTBR.iso` (1.6GB) - Winning Eleven 10 PT-BR (base game)
- Source: Internet Archive

## ISO Top-Level Structure
Both ISOs use UDF filesystem with identical file layout:
```
SYSTEM.CNF          - Boot config (57 bytes)
SLPM_663.74         - PS2 ELF executable (~2.9MB)
IOP/                - I/O processor modules (.IRX files)
0_SOUND.AFS         - Sound archives
0_TEXT.AFS          - Main data archive (9315 files) ← MOST IMPORTANT
BOOT.AFS            - Boot assets (536 files)
J_SOUND.AFS         - Japanese sound
J_TEXT.AFS          - Japanese text (36 files)
MODULE.AFS          - Module data (407 files)
OVER.AFS            - Overlay modules (36 MWo3 files)
ROMLIST.DIR          - ROM listing
WE10_OP.PSS         - Opening video
```

## AFS Archive Locations in ISO
| Archive | Bomba Patch Offset | WE10 Offset | Files |
|---------|-------------------|-------------|-------|
| BOOT.AFS | 0x0035F800 | 0x00153000 | 536 |
| 0_TEXT.AFS | 0x2F1FA000 | 0x2297C800 | 9315 |
| J_TEXT.AFS | 0x61399800 (Bomba) | 0x3BFCE000 (WE10) | 36 |
| MODULE.AFS | 0x5F969800 (Bomba) | 0x5FC55000 (WE10) | 407 |

Note: OVER.AFS in both ISOs is stored as the J_TEXT.AFS entry (36 files, MWo3 format).

## 0_TEXT.AFS Key Files

### File[34] - Base Player Database
- **4848 records x 124 bytes** (zlib compressed in WESYS 0x00060000 container)
- Zlib stream starts at offset 0x70 in the container
- **IDENTICAL between WE10 and Bomba Patch** (base/default data)
- Player record format (124 bytes):
  - Bytes 0-31: Player name (UTF-16LE, max 15 chars + null)
  - Bytes 32-47: Shirt name (ASCII, 16 bytes)
  - Bytes 48-49: Call name ID (0xCDCD = default)
  - Bytes 50-123: Player attributes (bitfield encoded stats)
- WE10 has Japanese katakana names for many players

### File[35] - Editable Player Database
- **4873 records x 124 bytes** (zlib compressed, same container format as file[34])
- **DIFFERENT between WE10 and Bomba Patch** - 4742 out of 4873 records changed
- This is the PRIMARY file Bomba Patch modifies for roster updates
- Same record format as file[34]
- Contains the actual in-game player names and stats
- 25 more records than file[34] (extra player slots)

### File[36] - Extra Player Database
- Smaller player database, similar format
- Also differs between ISOs

### File[33] - Game Configuration
- 391,264 bytes decompressed (308,824 compressed)
- **IDENTICAL between WE10 and Bomba Patch**
- Contains formation data, squad configuration
- Header: 16 sections with (offset, count) pairs
- Section at offset 0x1540: 16-byte entries with team_byte, player_idx, data
  - team_byte range: 128-191 (64 national team slots)
  - Contains formation/role assignments, NOT full rosters

### File[38] - WEPLDATA
- Magic: "WEPLDATA" (8 bytes)
- 159 team IDs (u16 each) after header
- Followed by supplementary player entries with UTF-16LE names and ASCII shirt names
- Team IDs: [0, 72, 75, 77, 80, 83, 84, 85, 162, 163, ...]

### File[566] - Player Name Table
- 2607 player names, 48 bytes each (ASCII, null-padded)
- Starts at offset 0x30 in the file
- Names are alphabetically sorted (Aaron Hughes ... Zwarthoed)
- **IDENTICAL between WE10 and Bomba Patch**
- Used as a lookup table; actual in-game names come from file[35]

### Files[47-58] - Kit/Config Data
- 12 files, ~224KB-388KB each
- Use nested WESYS container format (0x00060000 magic)
- Contain kit, stadium assignment, and team configuration data
- All differ between WE10 and Bomba Patch (size differences)

## OVER.AFS (36 MWo3 Overlay Files)

All files use MWo3 (PS2 memory card save) container format:
```
0x00: "MWo3" magic (4 bytes)
0x04: type/ID (u32)
0x08: PS2 load address (u32)
0x0C: flags (u32)
0x10-0x1F: metadata
0x20: filename (null-terminated, 16 bytes)
0x80+: MIPS R5900 code + embedded data
```

### Key Overlay Files
| File | Name | Size | Load Addr | Description |
|------|------|------|-----------|-------------|
| [0] | (flags) | 15KB | 0x008CB000 | Settings |
| [2] | defaultdataset.ovl | 631KB | 0x00904000 | **Default option file data** |
| [4] | edit.ovl | 1.27MB | 0x00B68800 | **Editable data overlay** |
| [17] | (kit data) | 693KB | 0x00AB8800 | Kit/color overlay |
| [21] | realcondition.ovl | 457KB | 0x00C9A800 | Player condition ratings |

### WE10 vs Bomba Patch Diffs in OVER.AFS
- **Only files 2, 4, 17, 21 differ** between the two ISOs
- File[2] and [4]: **475 byte diffs** = stadium/competition name changes ONLY
  - "Practice Stadium" → "Treinamento"
  - "Highbury" → "Emirates Stadium"
  - "League -France-" → "Brasileirao 2006"
  - etc.
- File[17]: **11 byte diffs** = minor kit color adjustments
- File[21]: **138 byte diffs** = player condition value tweaks

### edit.ovl Internal Structure
- 0x0080-0x08E000: MIPS code + data (~570KB) - low instruction density, mostly data
- 0x08E000-0x125000: BSS section (all zeros, ~620KB)
- 0x125000-0x135680: Trailing data (~67KB) - includes stadium/competition names

## SLPM_663.74 (PS2 Executable)

- ELF header at ISO offset: 0x00095000
- Size: 2,926,456 bytes
- Team name table at SLPM offset 0x2BEC00 (ISO offset 0x353C00)
- Format: alternating null-terminated strings (team_name, abbreviation)
- Bomba Patch team list (first 25):

| Idx | Team Name | Abbrev | Original PES6 Team |
|-----|-----------|--------|-------------------|
| 0 | Swansea | SWS | (national team slot 0) |
| 1 | Manchester City | MCR | (national team slot 1) |
| 2 | Manchester United | MAN | (national team slot 2) |
| 3 | Cristal Pallace | CRI | (national team slot 3) |
| 4 | Liverpool | LIV | (national team slot 4) |
| 5 | Vasco | VAS | (national team slot 5) |
| 6 | Atletico PR | APR | (national team slot 6) |
| **7** | **Atletico MG** | **CAM** | **(national team slot 7)** |
| 8 | Cruzeiro | CRZ | (national team slot 8) |
| 9 | Ponte Preta | APP | (national team slot 9) |
| 10 | Flamengo | FLA | (national team slot 10) |
| ... | ... | ... | ... |
| 25+ | German/European clubs | | (club team slots) |

## Player Record Stats Layout (bytes 48-123 of 124-byte record)

From PESEditor Stats.java (byte offsets relative to stats start = record byte 48):

| Stat | Offset | Shift | Mask | Description |
|------|--------|-------|------|-------------|
| callName | 1 | 0 | 0xFFFF | Call name ID |
| nameEdited | 3 | 0 | 0x1 | Name edited flag |
| regPos | 6 | 4 | 0xF | Registered position |
| attack | 7 | 0 | 0x7F | Attack |
| gk | 7 | 7 | 1 | GK position flag |
| defence | 8 | 0 | 0x7F | Defence |
| balance | 9 | 0 | 0x7F | Balance |
| stamina | 10 | 0 | 0x7F | Stamina |
| speed | 11 | 0 | 0x7F | Speed |
| accel | 12 | 0 | 0x7F | Acceleration |
| response | 13 | 0 | 0x7F | Response |
| agility | 14 | 0 | 0x7F | Agility |
| dribAcc | 15 | 0 | 0x7F | Dribble accuracy |
| dribSpe | 16 | 0 | 0x7F | Dribble speed |
| sPassAcc | 17 | 0 | 0x7F | Short pass accuracy |
| sPassSpe | 18 | 0 | 0x7F | Short pass speed |
| lPassAcc | 19 | 0 | 0x7F | Long pass accuracy |
| lPassSpe | 20 | 0 | 0x7F | Long pass speed |
| shotAcc | 21 | 0 | 0x7F | Shot accuracy |
| shotPow | 22 | 0 | 0x7F | Shot power |
| shotTec | 23 | 0 | 0x7F | Shot technique |
| fk | 24 | 0 | 0x7F | Free kick accuracy |
| curling | 25 | 0 | 0x7F | Swerve |
| heading | 26 | 0 | 0x7F | Heading |
| jump | 27 | 0 | 0x7F | Jump |
| team | 28 | 0 | 0x7F | Team work |
| tech | 29 | 0 | 0x7F | Technique |
| aggress | 30 | 0 | 0x7F | Aggression |
| mental | 31 | 0 | 0x7F | Mentality |
| gkAbil | 32 | 0 | 0x7F | GK ability |
| consistency | 33 | 0 | 0x07 | Consistency |
| condition | 33 | 8 | 0x07 | Condition |
| height | 41 | 0 | 0x3F | Height (add 148) |
| weight | 41 | 8 | 0x7F | Weight (add 148) |
| age | 65 | 9 | 0x1F | Age (add 15) |
| **nationality** | **65** | **0** | **0x7F** | **Nationality index** |

**IMPORTANT**: nationality (byte 112 in record, offset 65-1=64 from stats area) is the player's COUNTRY, not their team assignment. Value 50 = Brazil.

## Atletico MG 2017 Roster (from ESPN + file[35] matching)

| Pos | Player ID | Name in file[35] | Shirt Name |
|-----|-----------|------------------|------------|
| GK | 2329 | Victor | VICTOR |
| GK | 4439 | Giovanni | GIOVANNI |
| DF | 4723 | Marcos Rocha | MARCOS ROCHA |
| DF | 440 | Leo Silva | LEO SILVA |
| DF | 1060 | Erazo | ERAZO |
| DF | 4364 | Adilson | ADILSON |
| DF | 2451 | Mansur | MANSUR |
| DF | 2805 | F. Santana | F. SANTANA |
| MF | 2218 | Lucas Candido | LUCAS CANDIDO |
| MF | 1996 | Elias | ELIAS |
| MF | 2100 | Cazares | CAZARES |
| MF | 745 | Otero | OTERO |
| MF | 4086 | Carlos César | CARLOS CESAR |
| MF | 2115 | Capixaba | CAPIXABA |
| MF | 2030 | Yago | YAGO |
| MF | 1983 | Luan | LUAN |
| MF | 4224 | Marquinhos | MARQUINHOS |
| MF | 4000 | Marlone | MARLONE |
| FW | 1470 | Robinho | ROBINHO |
| FW | 1170 | Fred | FRED |
| FW | 2294 | Rafael Moura | RAFAEL MOURA |
| FW | 2711 | Roger Guedes | ROGER GUEDES |

Player IDs are scattered: min=440, max=4723. NOT contiguous.

## Unsolved: Team-Player Mapping

The critical piece we haven't cracked: **where does the ISO store "player X belongs to team Y"?**

### What we ruled out:
1. **u16 player ID arrays in the ISO** - Full 1.9GB scan found zero clusters of known ATL MG player IDs
2. **Byte field in player records** - No byte in the 124-byte record encodes team membership (byte 112 = nationality, not team)
3. **PESEditor option file offsets** - The PS2 version uses completely different structure than PC exports
4. **OVER.AFS as flat option file** - The overlays are PS2 MIPS executables, not raw data files
5. **Contiguous player index ranges** - ATL MG players are scattered across indices 440-4723
6. **File[33] squad tables** - Contains formation/role data for original national teams, not full rosters

### Leading hypothesis:
The `defaultdataset.ovl` (631KB) and/or `edit.ovl` (1.27MB) contain the squad assignment tables embedded within the MIPS code/data sections in a custom compressed or encoded format. The near-zero diff between WE10 and Bomba Patch overlays suggests the squad assignments may be the SAME and Bomba Patch only changes player data at existing slots, or the roster is reconstructed from player nationality + other fields at runtime.

### Next steps:
1. **PCSX2 emulation**: Boot the ISO, dump PS2 RAM after roster initialization, search for player ID arrays in the memory dump
2. **MIPS disassembly**: Trace the `defaultdataset.ovl` code to find where it writes squad slot data
3. **Community research**: Find Bomba Patch modding tutorials or tools that explain their specific workflow

## Tools & References
- **PESEditor** (PC): `PESEditor/` - Java source, handles PC option files
- **PES-EDITOR-PS2**: `PES-EDITOR-PS2/` - Java source, handles PS2 save files (.xps/.psu)
- **Capstone**: Python MIPS disassembler (`pip install capstone`)
- **7z/bsdtar**: For ISO and AFS extraction
- **Python zlib**: For decompressing WESYS container data

## WESYS Container Format (0x00060000)
Used by files 34, 35, 36, 47-58 in 0_TEXT.AFS:
```
0x00: u32 magic = 0x00000600 (LE)
0x04: u32 total_compressed_size
0x08-0x1F: zeros (padding)
0x20: u32 num_sections
0x24: u32 section_entry_size (usually 8)
0x28: u32 data_start_offset
0x2C+: section offset table (num_sections * 4 bytes)
... padding/metadata ...
0x50+: block table (for multi-block files)
0x70: zlib compressed data stream (starts with 0x78DA)
```
Decompressed data contains the actual game data (player records, config, etc.)

## Roster Table Investigation (CORRECTED)

**Location**: edit.ovl (OVER.AFS file[4]) at offset **0x12DB70**

### Roster Table Structure

The roster is stored as a flat array of u32 entries in the edit.ovl overlay file, in the trailing data section (after the BSS zero region):

```
edit.ovl layout:
  0x0080 - 0x08E000  : MIPS code + embedded data (~570KB)
  0x08E000 - 0x125000 : BSS section (all zeros, ~620KB)
  0x125000 - 0x12DB70 : Stadium/competition names + other data
  0x12DB70 - 0x12F2EC : Formation/shirt number data (u32 entries)
  0x12F2EC - 0x134xxx : Formation position data (u32, 23 per team) - NOT squad roster
  ... to 0x135680     : End of file
```

#### Tables Found (Formation Data - NOT Squad Roster)
These tables use **u32 (4 bytes, little-endian)** entries:
- `0x0000PPPP` — player index reference
- `0xFFFFFFFF` — empty slot

**WARNING**: These contain **duplicate player IDs** within the same team and only ~12 players per team. They define formation positions (where players stand on the pitch), NOT who is on the team.

### How Bomba Patch Handles Rosters

**Confirmed**: OVER.AFS overlays are nearly identical between WE10 and Bomba Patch (475 bytes diff = stadium names only). Bomba Patch modifies:
1. **SLPM executable**: Team names renamed (e.g., team 7 → "Atletico MG")
2. **0_TEXT.AFS file[35]**: 4742 out of 4873 player records replaced with updated names/stats
3. **0_TEXT.AFS files[47-58]**: Kit/config data updated
4. **OVER.AFS files[2,4,17,21]**: Stadium/competition names, minor kit color changes

**UNSOLVED**: How the game knows "player index X belongs to team Y". The team-player assignment mechanism has NOT been found in the ISO binary data. Leading theories:
- The MIPS code in the overlay generates rosters programmatically
- The roster is in a compressed/encoded format we haven't decoded
- The game uses a combination of nationality field + other heuristics

### Next Steps for Cracking the Roster

1. **PCSX2 emulation** (requires GUI machine): Boot the ISO, dump PS2 RAM after menus load, search for player ID arrays in the memory dump. This will show the RUNTIME roster structure.
2. **MIPS disassembly deep dive**: Trace the overlay code functions that reference the formation tables to find where squad rosters are constructed.
3. **Community research**: Find Bomba Patch modding tutorials, tools (like "GGS Studio" or "DKZ Studio" mentioned in forums), or contact the Bomba Patch Geomatrix team.
4. **Option file analysis**: Obtain a Bomba Patch 77 PS2 memory card save file (.psu/.xps) and parse it with PES-EDITOR-PS2 to extract the default roster.

### What We CAN Do Now

Even without the roster mapping, we can:
1. **Modify player data** (names, stats, appearance) in file[35]
2. **Change team names** in the SLPM executable
3. **Read formation/position data** from the overlay tables
4. **Modify stadium/competition names** in OVER.AFS

### Implication for Building a Roster Patcher

**Step 1** (BLOCKED): Find team-player assignment table via PCSX2 RAM dump

**Step 2**: Read the roster table and map player indices to teams

**Step 3**: Prepare player data for each team
- Create 124-byte player records (name UTF-16LE + shirt ASCII + stats)
- Write to correct file[35] indices

**Step 4**: Modify team names in SLPM executable (offset 0x2BEC00)

**Step 5**: Modify roster table to assign players to teams (if writable)

**Step 6**: Repack the ISO
- Recompress file[35] with zlib, update WESYS container
- Update AFS entry offsets/sizes
- Write modified files back to ISO
