# PES 6 PS2 Patcher — Design Spec

## Overview

A new patcher for Pro Evolution Soccer 6 (PS2, SLES-54203) that updates team names, player rosters, kit colors, and team emblems by directly patching the ISO image. Follows the same architecture as existing patchers (NHL 05 PS2, WE2002, etc.).

Users select a soccer league from ESPN, fetch current rosters, select a PES 6 ISO, and get a patched ISO with updated data. If a league doesn't exist in the game, the user can replace any existing league's slots.

## Target Game

- **Title**: PES 6 - Pro Evolution Soccer (Europe)
- **Game ID**: SLES-54203
- **Format**: PS2 ISO 9660, ~1.54 GB
- **Volume ID**: PES6

## ISO Structure (confirmed from analysis)

| File | LBA | Size | Contents |
|------|-----|------|----------|
| `SLES_542.03` | 323 | 3.0 MB | Game executable — team names/abbreviations |
| `NTGUI2EU.ELF` | 1816 | 5.0 MB | Main game binary |
| `0_TEXT.AFS` | 14741 | 410 MB | 9,806 files — textures, kits, emblems, player DB |
| `E_TEXT.AFS` | 224414 | 24 MB | 421 files — English text/localization |
| `OVER.AFS` | 8241 | 13 MB | 37 overlay modules (MWo3 format) |

### Team Names (SLES_542.03)

**Location**: Starts at national teams around `0x2DDCE0`, clubs at `0x2DE4A8`, ends at `~0x2DF600` in `SLES_542.03`.

**Format**: Variable-length null-terminated UTF-8 strings, **8-byte aligned**. Entries alternate: team name, abbreviation, team name, abbreviation, etc. Each string is padded with nulls to the next 8-byte boundary.

**Total**: 277 string pairs (name + abbreviation), occupying ~4,400 bytes.

**Team ranges** (pair index, confirmed from ISO dump):

| Range | Count | League / Category |
|-------|-------|-------------------|
| 24-55 | 32 | National teams (Austria → Wales) |
| 56-63 | 8 | African nations (Angola → Tunisia) |
| 64-68 | 5 | CONCACAF (Costa Rica → USA) |
| 69-80 | 12 | South America + Asia (Argentina → Australia) |
| 81-88 | 8 | Classic teams (Classic England → Classic Brazil) |
| 88-108 | 20 | English Premier League (Arsenal licensed, rest fake names) |
| 108-128 | 20 | Ligue 1 (AJ Auxerre → Valenciennes FC) |
| 128-148 | 20 | Serie A (Ascoli → Udinese) |
| 148-166 | 18 | Eredivisie (ADO Den Haag → Willem II) |
| 166-186 | 20 | La Liga (Athletic Club → R. Zaragoza) |
| 186-205 | 19 | Other European clubs (Bruxelles, Copenhagen, Bayern, Juventus, etc.) |
| 205-210 | 5 | South American clubs (Patagonia, Pampas — fake names) |
| 210-228 | 18 | Custom Team A-R (ZZA → ZZR) |
| 228-245 | 17 | Extra national teams (Bosnia → Uzbekistan) |
| 245-263 | 18 | ML/zodiac teams (ML United → WE Japan) |
| 263-277 | 14 | All-Stars + shop teams |

**Write constraint**: New names must fit within the existing byte budget per entry. Names that would overflow are truncated. The total region size (4,400 bytes) is fixed — the executable cannot grow.

### AFS Archive Format

- Magic: `AFS\x00`
- Header: 4-byte magic + 4-byte file count
- File table: N entries of (4-byte offset, 4-byte size) relative to AFS start
- Files concatenated after table

Sub-files observed to use a 32-byte header + zlib payload:
- Bytes 0-3: unknown/magic
- Bytes 8-11: decompressed size (LE uint32)
- Bytes 32+: zlib stream (starts with `78 DA`)

**Note**: Not all AFS entries may follow this pattern. The reader must check for the zlib magic at offset 32 and handle uncompressed entries.

### Key AFS Entries (0_TEXT.AFS)

| Index | Compressed | Decompressed | Purpose |
|-------|-----------|--------------|---------|
| 32 | 2,001 B | 4,576 B | Player database header |
| 33 | 20,677 B | 66,688 B | Player database (format TBD) |
| 34 | 2,101 B | TBD | Fake player database header |
| 35 | 29,697 B | TBD | Fake player database |
| 535 | 94,400 B | TBD | Flags & emblems (texture container) |
| 536 | 201,216 B | TBD | Flags & emblems (texture container) |
| 5473-6831 | ~125 KB each | TBD | Team kits |

## Architecture

### Service Layer (`src/services/pes6_ps2_patcher/`)

| File | Responsibility |
|------|---------------|
| `models.py` | PES6 team/player data structures, 277-slot team index mapping, re-exports shared sports models |
| `patcher.py` | Orchestrator: fetch rosters → map stats → patch ISO |
| `rom_reader.py` | Parse ISO 9660, extract AFS entries via seek (no full load), decompress zlib, read team/player data from SLES |
| `rom_writer.py` | Write patched team names to SLES in-place within ISO, recompress/replace AFS entries, emblem injection |
| `stat_mapper.py` | Map API-Football stats to PES 6 attributes (0-99 scale) — Phase 2b only |
| `afs_handler.py` | AFS archive seek-based read/write (no full 410 MB load — read entries on demand via offset table) |

`ps2_texture.py` placed in `src/utils/` for reuse across PS2 patchers (NHL 05, future PS2 games).

### State (`src/state.py`)

```python
@dataclass
class PES6PS2PatcherState:
    selected_season: int = field(
        default_factory=lambda: datetime.now().year
    )
    selected_league: Any = None

    # Fetched data
    rosters: Any = None  # Dict[str, List[Player]]
    team_stats: Any = None
    league_data: Any = None  # LeagueData (for roster preview modal)
    fetch_progress: float = 0.0
    fetch_status: str = ""
    is_fetching: bool = False
    fetch_error: str = ""

    # ROM
    rom_path: str = ""
    rom_info: Any = None
    rom_valid: bool = False
    zip_path: str = ""
    zip_temp_dir: str = ""

    # Patching
    patch_progress: float = 0.0
    patch_status: str = ""
    is_patching: bool = False
    patch_output_path: str = ""
    patch_complete: bool = False
    patch_error: str = ""

    # Roster preview
    roster_preview_team_index: int = 0
    roster_preview_player_index: int = 0

    # UI
    active_modal: Optional[str] = None  # "league_browser", "roster_preview", "patch_progress"
    leagues_highlighted: int = 0
    roster_teams_highlighted: int = 0
    roster_players_highlighted: int = 0
    league_search_query: str = ""
```

### UI (`src/ui/screens/pes6_ps2_patcher_screen.py`)

Step-by-step list screen (same pattern as NHL 05, WE2002):

1. **Select League** — opens league browser modal (reuse `LeagueBrowserModal`)
2. **Fetch Rosters** — fetches from ESPN soccer API
3. **Preview Rosters** — shows teams/players in roster preview modal
4. **Select ISO** — folder browser filtered to .iso/.zip
5. **Patch ROM** — writes patched ISO

### Data Source

**ESPN** for squad rosters (names, positions, jersey numbers, team logos, team colors). Same `espn_client.py` soccer endpoints used by WE2002 patcher.

**ESPN does not provide player stats** for soccer. For Phase 2b (player database with attributes), `ApiFootballClient` (api-football.io, requires API key) would be needed, same as WE2002 patcher. Phase 1 and 2a do not require stats.

### ISO Write-Back

SLES_542.03 is modified **in-place within the ISO** at its known LBA (323). The file size does not change. This is the same approach used by the NHL 05 PS2 patcher (`rom_writer.py` writes directly to the output ISO copy at sector offsets).

For AFS entries, the writer seeks to `AFS_LBA * 2048 + entry_offset` in the ISO and writes the modified data. No ISO filesystem rebuild is needed as long as file sizes don't grow.

### AFS Handler — Memory Strategy

`0_TEXT.AFS` is 410 MB — cannot be loaded into memory on handheld consoles. The AFS handler will:

1. Read only the AFS header + file table (offset/size pairs) into memory (~80 KB for 9,806 entries)
2. Read individual entries on demand via `seek()` to `AFS_LBA * 2048 + entry_offset`
3. Write modified entries back at the same position, updating size in the file table
4. Only the file table and modified entries are kept in memory

## Patching Strategy

### Phase 1: Team Names (MVP)

- Parse the team name string table from SLES executable (277 entries, ~4,400 bytes)
- Map ESPN teams to PES 6 ROM slots by matching league → slot range
- Derive mapping at runtime by reading existing team names from ROM and matching to ESPN names
- Write new team names and abbreviations, null-padded, within each entry's existing byte budget
- For leagues not in PES 6 (e.g., Bundesliga beyond Bayern), user selects which slot range to replace
- For promoted/relegated teams: if an ESPN team has no matching slot, assign it to the closest available slot in the league's range (or an unused custom Team A-R slot)

### Phase 2a: Kit Colors

- Extract ESPN `color`/`alternateColor` hex values
- Convert to PS2 palette format
- Write to kit data entries in 0_TEXT.AFS (files 5473-6831)
- Independent of player database — can ship separately

### Phase 2b: Player Database

- Reverse engineer the on-disc player format in `0_TEXT.AFS[32-33]`
- File 33 decompresses to 66,688 bytes — does not match 124-byte option file records
- PESEditor source documents the option file format (124B/player, 26 stats, 23 specials)
- Need to determine how on-disc format differs
- Requires API-Football for player stats (ESPN provides no soccer stats)
- Fallback: generate option file and embed as save data alongside ISO

### Phase 3: Emblems

- Download ESPN team logo PNGs
- Resize to match existing emblem dimensions (64×64 or 128×128, to be confirmed from AFS 535-536)
- Quantize to palette (16 or 256 colors)
- Swizzle pixel data to PS2 memory layout (4-bit unswizzle algorithm available)
- Replace in AFS files 535-536 (TXS texture containers, zlib-compressed)
- TXS format: zlib-compressed archive with named sub-files and file table

## Team Slot Mapping Strategy

At runtime, `rom_reader.py` parses all 277 team name/abbreviation pairs from the SLES executable. The patcher then:

1. Groups slots by league range (known from the fixed slot layout above)
2. When user selects an ESPN league, matches ESPN team names to existing ROM team names in the corresponding range
3. For exact matches (e.g., "Barcelona" → "F.C. Barcelona"), maps directly
4. For close matches, uses fuzzy string matching
5. For no match (promoted team), assigns to first unused custom slot (Team A-R range, indices 210-228)
6. User can override any mapping in the preview step

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| On-disc player format unknown | Can't patch rosters in Phase 2b | Investigate files 32-35; fallback to option file embed |
| AFS entry grows after recompression | Corrupts ISO | In-place-only writes; reject if new compressed size > original |
| PS2 texture swizzle wrong | Garbled emblems | Roundtrip verify: unswizzle existing → re-swizzle → compare |
| SLES executable checksum | Game crashes | PS2 games rarely verify; test on PCSX2 first |
| Team name overflow | Truncated names | Measure each entry's byte budget from ROM; truncate with warning |
| 410 MB AFS memory | OOM on handhelds | Seek-based AFS handler, no full load |
| ESPN has no soccer stats | Can't set player attributes | Phase 2b uses API-Football (requires API key); Phase 1 doesn't need stats |
| Promoted/relegated teams | No matching ROM slot | Use custom Team A-R slots (18 available); user override in preview |

## Open Source References

- [PeterC10/PESEditor](https://github.com/PeterC10/PESEditor) — PES 6 option file format, 124-byte player records
- [nthachus/pes-editor](https://github.com/nthachus/pes-editor) — comprehensive stat definitions, multi-version support
- [lazanet/PES6-AFS-Tools](https://github.com/lazanet/PES6-AFS-Tools) — AFS/TXS format parsing (Java)
- [MaikelChan/AFSPacker](https://github.com/MaikelChan/AFSPacker) — AFS extract/repack
- [PS2 4-bit texture unswizzle](https://gist.github.com/Fireboyd78/1546f5c86ebce52ce05e7837c697dc72) — swizzle algorithm (C#)
- [PES 6 AFS Map](https://pdfcoffee.com/pes-6-afs-map-pdf-free.html) — file index documentation

## Phasing

1. **Phase 1 (MVP)**: Team names + abbreviations in SLES executable + league browser + ESPN integration + roster preview
2. **Phase 2a**: Kit colors (ESPN team colors → AFS kit palette entries)
3. **Phase 2b**: Player database (pending format reverse engineering, requires API-Football)
4. **Phase 3**: Emblem/logo injection (PS2 texture conversion + swizzle)
