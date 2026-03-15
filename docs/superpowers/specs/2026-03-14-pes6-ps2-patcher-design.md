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
| `SLES_542.03` | 323 | 3.0 MB | Game executable — team names at `0x2DE4A8` |
| `NTGUI2EU.ELF` | 1816 | 5.0 MB | Main game binary |
| `0_TEXT.AFS` | 14741 | 410 MB | 9,806 files — textures, kits, emblems, player DB |
| `E_TEXT.AFS` | 224414 | 24 MB | 421 files — English text/localization |
| `OVER.AFS` | 8241 | 13 MB | 37 overlay modules (MWo3 format) |

### Team Names (SLES_542.03)

- Located at offset `0x2DE4A8` in the executable
- ~178 teams: English Premier League (fake names), Ligue 1, Serie A, Eredivisie, La Liga, plus licensed clubs, national teams, and ML/custom teams
- Format: null-terminated UTF-8 string (16-byte aligned) + null-terminated abbreviation (8-byte aligned)
- Names must fit within existing byte budget (no executable growth)

### AFS Archive Format

- Magic: `AFS\x00`
- Header: 4-byte magic + 4-byte file count
- File table: N entries of (4-byte offset, 4-byte size) relative to AFS start
- Files are concatenated after the table
- Sub-files use a 32-byte header + zlib-compressed payload:
  - Bytes 0-3: unknown/magic
  - Bytes 4-7: unknown
  - Bytes 8-11: decompressed size (LE uint32)
  - Bytes 12-31: padding/zeros
  - Bytes 32+: zlib stream (starts with `78 DA`)

### Key AFS Entries (0_TEXT.AFS)

| Index | Decompressed Size | Purpose |
|-------|-------------------|---------|
| 32 | 4,576 B | Player database header |
| 33 | 66,688 B | Player database (format TBD) |
| 34 | ~4 KB | Fake player database header |
| 35 | ~30 KB | Fake player database |
| 535 | 92 KB | Flags & emblems (texture container) |
| 536 | 196 KB | Flags & emblems (texture container) |
| 5473-6831 | ~125 KB each | Team kits |

## Architecture

### Service Layer (`src/services/pes6_ps2_patcher/`)

| File | Responsibility |
|------|---------------|
| `models.py` | PES6 team/player data structures, team index mappings (178 slots), re-exports shared sports models |
| `patcher.py` | Orchestrator: fetch rosters → map stats → patch ISO |
| `rom_reader.py` | Parse ISO 9660, extract AFS entries, decompress zlib, read team/player data |
| `rom_writer.py` | Write patched team names to SLES, recompress/replace AFS entries, emblem injection |
| `stat_mapper.py` | Map ESPN soccer stats to PES 6 attributes (0-99 scale, 26 stats + 23 specials) |
| `afs_handler.py` | AFS archive read/write/repack |
| `ps2_texture.py` | PS2 texture: swizzle/unswizzle, TXS parsing, PNG→PS2 conversion |

### State (`src/state.py`)

```python
@dataclass
class PES6PS2PatcherState:
    selected_season: int  # current season
    selected_league: Any  # league from ESPN browser
    league_data: Any  # LeagueData for preview
    rosters: Any  # Dict[str, List[Player]]
    team_stats: Any
    fetch_progress: float
    fetch_status: str
    is_fetching: bool
    fetch_error: str

    rom_path: str
    rom_info: Any
    rom_valid: bool
    zip_path: str
    zip_temp_dir: str

    patch_progress: float
    patch_status: str
    is_patching: bool
    patch_output_path: str
    patch_complete: bool
    patch_error: str

    roster_preview_team_index: int
    roster_preview_player_index: int
    active_modal: Optional[str]  # "league_browser", "roster_preview", "patch_progress"

    # League browser (reuse WE2002 pattern)
    league_search_query: str
    league_browser_highlighted: int
    league_browser_leagues: Any
    leagues_highlighted: int
    roster_teams_highlighted: int
    roster_players_highlighted: int
```

### UI (`src/ui/screens/pes6_ps2_patcher_screen.py`)

Step-by-step list screen (same as NHL 05, WE2002):

1. **Select League** — opens league browser modal (reuse `LeagueBrowserModal`)
2. **Fetch Rosters** — fetches from ESPN soccer API
3. **Preview Rosters** — shows teams/players in roster preview modal
4. **Select ISO** — folder browser filtered to .iso/.zip
5. **Patch ROM** — writes patched ISO

### ESPN Integration

Reuse existing `src/services/sports_api/espn_client.py` soccer endpoints. Same league browser as WE2002 patcher — user picks from available ESPN soccer leagues (Premier League, La Liga, Serie A, Bundesliga, Ligue 1, Brasileirão, etc.).

## Patching Strategy

### Phase 1: Team Names (MVP)

- Read team name table from SLES executable at `0x2DE4A8`
- Map ESPN teams to PES 6 ROM slots (by league → team matching)
- Write new team names and abbreviations, null-padded within existing byte budget
- If a league doesn't exist in PES 6, user selects which existing league slots to replace

### Phase 2: Player Database

- Reverse engineer the on-disc player format in `0_TEXT.AFS[32-33]`
- The 66,688-byte decompressed file does not match the 124-byte option file record format
- PESEditor source (PeterC10/PESEditor, nthachus/pes-editor) documents the option file format:
  - 124 bytes per player, UTF-16LE names (32 bytes), shirt name (16 bytes)
  - 26 ability stats (0-99, 7-bit), 23 special abilities (1-bit)
  - 12 position slots, physical attributes, nationality
- Need to determine how this maps to the on-disc format
- Fallback: generate option file and embed as save data

### Phase 3: Emblems

- Download ESPN team logo PNGs
- Resize to match existing emblem dimensions (64×64 or 128×128)
- Quantize to palette (16 or 256 colors)
- Swizzle pixel data to PS2 memory layout (4-bit unswizzle algorithm available)
- Replace in AFS files 535-536 (TXS texture containers)
- TXS format: zlib-compressed archive with named sub-files and a file table

### Kit Colors

- Extract ESPN `color`/`alternateColor` hex values
- Convert to PS2 palette format
- Write to kit data entries in 0_TEXT.AFS (files 5473-6831)

### AFS Repacking

- Measure slack space between consecutive AFS entries
- If new compressed data ≤ original size: write in-place, update size in AFS table
- If larger: investigate relocation or truncation strategies
- Update AFS file table offsets/sizes after any modifications

## Team Slot Mapping

178 slots identified in SLES executable at `0x2DE4A8`:

- **English clubs** (0-22): Fake names (Arsenal is licensed, rest are "West Midlands Village", "Lancashire", etc.)
- **French clubs** (23-46): Ligue 1 (AJ Auxerre, Bordeaux, Lyon, PSG, etc.)
- **Italian clubs** (47-63): Serie A (Ascoli, Atalanta, AC Milan, Juventus, etc.)
- **Dutch clubs** (64-82): Eredivisie (Ajax, PSV, Feyenoord, etc.)
- **Spanish clubs** (83-107): La Liga (Barcelona, Real Madrid, Valencia, etc.)
- **Other European clubs** (108-127): Belgian, Czech, Danish, German, Greek, Portuguese, Scottish, Swedish, Turkish, Ukrainian
- **South American** (128-131): Patagonia, Pampas (fake names)
- **Custom/ML teams** (132-177): Team A-R, zodiac teams, national teams, etc.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| On-disc player format unknown | Can't patch rosters in Phase 2 | Investigate files 32-35; fallback to option file embed |
| AFS entry grows after recompression | Corrupts ISO | Measure slack; in-place-only writes with size check |
| PS2 texture swizzle wrong | Garbled emblems | Test with existing textures first (roundtrip verify) |
| Team slot mapping incomplete | Wrong teams patched | Full 178-slot map from SLES dump confirmed |
| SLES executable checksum | Game crashes | PS2 games rarely verify ELF checksums; test on PCSX2 |

## Open Source References

- [PeterC10/PESEditor](https://github.com/PeterC10/PESEditor) — PES 6 option file format, 124-byte player records
- [nthachus/pes-editor](https://github.com/nthachus/pes-editor) — comprehensive stat definitions, multi-version support
- [lazanet/PES6-AFS-Tools](https://github.com/lazanet/PES6-AFS-Tools) — AFS/TXS format parsing (Java)
- [MaikelChan/AFSPacker](https://github.com/MaikelChan/AFSPacker) — AFS extract/repack
- [PS2 4-bit texture unswizzle](https://gist.github.com/Fireboyd78/1546f5c86ebce52ce05e7837c697dc72) — swizzle algorithm (C#)
- [PES 6 AFS Map](https://pdfcoffee.com/pes-6-afs-map-pdf-free.html) — file index documentation

## Phasing

1. **Phase 1 (MVP)**: Team names + abbreviations + league browser + ESPN integration
2. **Phase 2**: Player database (pending format reverse engineering) + kit colors
3. **Phase 3**: Emblem/logo injection (PS2 texture conversion)
