# ISS Deluxe (SNES) Roster Patcher — Implementation Plan

## Overview

A patcher for **International Superstar Soccer Deluxe** (SNES) under the Sports Game Patcher feature. Fetches real-world team and player data via the API-Football API and patches an ISS Deluxe ROM with accurate player names, stats, positions, kit colors, **team names** (both selection screen tile graphics and in-game scoreboard text), and flag colors.

**Target ROM**: International Superstar Soccer Deluxe (USA) — MD5: `345ddedcd63412b9373dabb67c11fc05`

> **API & Settings**: The API-Football integration, caching, settings UI, and main menu structure are covered by the [Sports Game Roster Patcher plan](we_patcher_implementation.md) (Sections 1–2). This document only covers ISS Deluxe-specific ROM format, data mapping, and patching logic.

---

## Table of Contents

1. [ROM Format Reference](#1-rom-format-reference)
2. [Architecture](#2-architecture)
3. [Service Layer](#3-service-layer)
4. [Stat Mapping Algorithm](#4-stat-mapping-algorithm)
5. [Graphics & Team Name Patching](#5-graphics--team-name-patching)
6. [UI Screen](#6-ui-screen)
7. [State Management](#7-state-management)
8. [Implementation Phases](#8-implementation-phases)
9. [Testing Strategy](#9-testing-strategy)
10. [Known Limitations](#10-known-limitations)
11. [References & Resources](#11-references--resources)

---

## 1. ROM Format Reference

### Source of Truth

Three open-source references provide complete ROM offset data:

| Resource | Language | License | What It Covers |
|---|---|---|---|
| [ISSD-SNES-ROM-Web-Editor](https://github.com/EstebanFuentealba/ISSD-SNES-ROM-Web-Editor) | JavaScript | MIT | Player names, stats, menu text offsets, character encoding |
| [Web ISS Studio](https://github.com/EstebanFuentealba/web-iss-studio) | JS + C++ (WASM) | — | Flag colors, team name tiles, Konami compression |
| [ISS Deluxe Disassembly](https://github.com/Yoshifanatic1/International-Superstar-Soccer-Deluxe-SNES-Disassembly) | ASM | GPL-3.0 | Full ROM/RAM map, complete game logic |

### ROM Specifications

| Property | Value |
|---|---|
| Internal name | `SUPERSTAR SOCCER 2` |
| Layout | LoROM FastROM |
| Size | 2 MB |
| Region | USA |
| Maker | Konami (code "A4") |
| Game code | "AWJE" |
| SRAM | None |

### Team & Player Layout

| Constraint | Value |
|---|---|
| Standard teams | 36 |
| Secret/all-star teams | 6 |
| Total teams | **42** |
| Players per team | **20** (fixed) |
| Player name length | **8 characters** (fixed width, padded with `0x00`) |

### Player Name Data

- **Offset**: `0x3830E` (decimal: 230286)
- **Size**: 8 bytes per player × 20 players × 36 teams = 5,760 bytes
- **Encoding**: Custom character table (not ASCII)

#### Character Encoding Table

| Hex | Char | Hex | Char | Hex | Char | Hex | Char |
|-----|------|-----|------|-----|------|-----|------|
| 00 | _(pad)_ | 68 | A | 82 | a | 6A | C |
| 69 | B | 6B | D | 6C | E | 6D | F |
| 6E | G | 6F | H | 70 | I | 71 | J |
| 72 | K | 73 | L | 74 | M | 75 | N |
| 76 | O | 77 | P | 78 | Q | 79 | R |
| 7A | S | 7B | T | 7C | U | 7D | V |
| 7E | W | 7F | X | 80 | Y | 81 | Z |
| 83 | b | 84 | c | 85 | d | 86 | e |
| 87 | f | 88 | g | 89 | h | 8A | i |
| 8B | j | 8C | k | 8D | l | 8E | m |
| 8F | n | 90 | o | 91 | p | 92 | q |
| 93 | r | 94 | s | 95 | t | 96 | u |
| 97 | v | 98 | w | 99 | x | 9A | y |
| 9B | z | | | | | | |

**Note**: No numbers, accents, or special characters available in names. Only A-Z, a-z, and period.

### Player Attribute Data

- **Offset**: `0x50200` (decimal: 328192)
- **Size**: 7 bytes per player (14 hex nibbles)
- **Layout**: Nibble-packed — each attribute is a single hex nibble (0–9)

| Nibble | Attribute | Raw Range | Display Range |
|--------|-----------|-----------|---------------|
| 0 | Acceleration | 0–9 | 1–10 |
| 1 | Speed | 0–9 | 1–10 |
| 2 | Shot Power | 0–9 | 1–10 |
| 3 | Curl Skill | 0–9 | 1–10 |
| 4 | Balance | 0–9 | 1–10 |
| 5 | Intelligence | 0–9 | 1–10 |
| 6 | Dribbling | 0–9 | 1–10 |
| 7 | Jump | 0–9 | 1–10 |
| 8 | Position | 1–6 | See below |
| 9 | Energy | 0–9 | 1–10 |
| 10–11 | Jersey Number | 00–13 | 1–20 |
| 12 | Skin Type | 0–1 | Light/Dark |
| 13 | Hair Style | 0–D | 0–13 (14 styles) |

### Position Codes

| Value | Position |
|-------|----------|
| 1 | Goalkeeper (GK) |
| 2 | Defender (DEF) |
| 3 | Defensive Mid (DMF) |
| 4 | Midfielder (MF) |
| 5 | Attacking Mid (AMF) |
| 6 | Forward (FWD) |

### Kit / Uniform Color Data

- **Primary shirt offset**: `0x4854E` (decimal: 296398)
- **Size**: 2 bytes per color (SNES BGR555 format)

#### SNES BGR555 Color Format

```
Bit: 15    14-10    9-5    4-0
     0     Blue     Green  Red
           (5)      (5)    (5)
```

### Flag Color Data

- **Offset range 1**: `0x2DDA5`
- **Offset range 2**: `0x2ECBB`
- **Size**: 4 colors per flag, 2 bytes per color = 10 bytes per team

### Team Name Data

Team names appear in **two different formats** in different parts of the game:

#### A. Team Selection Screen — Compressed Tile Bitmaps

The team name displayed next to the flag on the **team selection screen** is a pre-rendered **8×32 pixel bitmap** (2bpp, 4-color palette), stored as Konami-compressed tile data.

- **Pointer table**: starts at `0x93CD`, 2-byte pointer steps per team
- **Tile data region**: `0x17680` to `0x17FFF` (relocated by editors; originally compressed elsewhere)
- **Compression**: Konami proprietary SNES compression (LZ + RLE variants)
- **Palette**: 4 colors — transparent, light (#f7fff7), blue (#84a6ef), dark blue (#0051f7)
- **To edit**: decompress → modify 8×32 pixel grid → recompress → update pointer table

#### B. In-Game Scoreboard/HUD — Structured Text

The team name shown on the **scoreboard during gameplay** (and results screens) uses an uncompressed structured text format.

- **Offset range**: `0x43ED5` to `0x44486`
- **Pointer table**: starts at `0x39DAE`, 2-byte steps per team
- **Format**: Length-prefixed, 4 bytes per character part
- **Character set**: A–Z, 0–9, period, space
- **Max display width**: 70 pixels (text condensed if exceeding)
- **Character rendering**: Each letter is composed of a "top half" and "bottom half" tile reference with a pixel position
- **Variable-width characters**: Most = 9 units; I, M, N, T, W = 8 units

This format is **editable without Konami compression** — it's structured but uncompressed.

#### C. Flag Design Tiles — Compressed

- **Offset**: `0x48000` to `0x48A7F` (Konami-compressed)
- **To edit**: Same Konami decompression pipeline as team name tiles

### Konami SNES Compression Format

Used for team name tiles (selection screen) and flag design tiles. The algorithm from web-iss-studio (`cpp/web-iss-studio.cpp`) supports:

| Mode | Description |
|---|---|
| LZ | Sliding window (0x400 byte window) |
| RLE A0 | Interleaved zero-fill |
| RLE C0 | Repeat byte |
| RLE E0 | Zero-fill (extended length via 0xFF prefix) |
| RAW | Direct byte copy |

The C++ implementation by Vladimir Protopopov ("proton") handles both compression and decompression. This will be compiled as a Python extension or called via subprocess.

---

## 2. Architecture

### File Structure

```
src/services/iss_patcher/
├── __init__.py              # Public API exports
├── models.py                # Data classes (ISSPlayerRecord, ISSTeamRecord, etc.)
├── encoding.py              # ISS Deluxe custom character encoding table
├── stat_mapper.py           # API-Football stats → ISS Deluxe 0-9 scale
├── rom_reader.py            # Read and parse ISS Deluxe ROM data
├── rom_writer.py            # Write patched data back to ROM
├── konami_compression.py    # Konami SNES compression/decompression (port or C wrapper)
├── team_name_tiles.py       # Team selection screen tile graphic generation
├── team_name_text.py        # In-game scoreboard structured text read/write
└── patcher.py               # Orchestrator

src/ui/screens/
├── iss_patcher_screen.py    # ISS Deluxe patcher screen (step-by-step)
```

### Integration Points

The ISS Deluxe patcher reuses:
- `ApiFootballClient` from `src/services/we_patcher/api_football.py` (shared API client)
- `CsvHandler` pattern (export/import CSV for manual editing)
- `sports_patcher_screen.py` (adds "ISS Deluxe - Int'l Superstar Soccer Deluxe (SNES)" to game list)

```
src/services/we_patcher/api_football.py   ← Shared (rename to src/services/sports_api/)
src/services/iss_patcher/                 ← New ISS-specific module
```

---

## 3. Service Layer

### 3.1 `encoding.py` — Character Table

```python
# Bidirectional mapping: char ↔ hex byte
CHAR_TO_HEX: dict[str, int] = {
    "A": 0x68, "B": 0x69, "C": 0x6A, "D": 0x6B, "E": 0x6C,
    "F": 0x6D, "G": 0x6E, "H": 0x6F, "I": 0x70, "J": 0x71,
    "K": 0x72, "L": 0x73, "M": 0x74, "N": 0x75, "O": 0x76,
    "P": 0x77, "Q": 0x78, "R": 0x79, "S": 0x7A, "T": 0x7B,
    "U": 0x7C, "V": 0x7D, "W": 0x7E, "X": 0x7F, "Y": 0x80,
    "Z": 0x81, "a": 0x82, "b": 0x83, "c": 0x84, "d": 0x85,
    "e": 0x86, "f": 0x87, "g": 0x88, "h": 0x89, "i": 0x8A,
    "j": 0x8B, "k": 0x8C, "l": 0x8D, "m": 0x8E, "n": 0x8F,
    "o": 0x90, "p": 0x91, "q": 0x92, "r": 0x93, "s": 0x94,
    "t": 0x95, "u": 0x96, "v": 0x97, "w": 0x98, "x": 0x99,
    "y": 0x9A, "z": 0x9B, ".": 0x9C,
}
HEX_TO_CHAR: dict[int, str] = {v: k for k, v in CHAR_TO_HEX.items()}
PADDING_BYTE = 0x00

def encode_name(name: str, max_len: int = 8) -> bytes: ...
def decode_name(data: bytes) -> str: ...
```

### 3.2 `rom_reader.py` — ROM Analysis

```python
class ISSRomReader:
    PLAYER_NAMES_OFFSET = 0x3830E
    PLAYER_ATTRS_OFFSET = 0x50200
    PLAYER_NAME_SIZE = 8
    PLAYERS_PER_TEAM = 20
    TOTAL_TEAMS = 36
    ATTR_BYTES_PER_PLAYER = 7

    def __init__(self, rom_path: str): ...
    def validate_rom(self) -> bool: ...
    def read_team_players(self, team_index: int) -> list[ISSPlayerRecord]: ...
    def read_all_teams(self) -> list[ISSTeamRecord]: ...
    def read_kit_colors(self, team_index: int) -> ISSKitColors: ...
    def read_flag_colors(self, team_index: int) -> list[int]: ...
```

### 3.3 `rom_writer.py` — ROM Patching

```python
class ISSRomWriter:
    def __init__(self, rom_path: str, output_path: str): ...
    def write_player_name(self, team_index: int, player_index: int, name: str): ...
    def write_player_attrs(self, team_index: int, player_index: int, attrs: ISSPlayerAttributes): ...
    def write_team_players(self, team_index: int, players: list[ISSPlayerRecord]): ...
    def write_kit_colors(self, team_index: int, colors: ISSKitColors): ...
    def write_flag_colors(self, team_index: int, colors: list[int]): ...
    def finalize(self): ...
```

### 3.4 `stat_mapper.py` — Attribute Mapping

```python
class ISSStatMapper:
    def map_player(self, player: Player, stats: PlayerStats | None) -> ISSPlayerAttributes: ...
    def _select_best_20(self, squad: list[Player]) -> list[Player]: ...
    def _truncate_name(self, name: str) -> str: ...
    def _map_position(self, api_position: str) -> int: ...
```

### 3.5 `patcher.py` — Orchestrator

```python
class ISSPatcher:
    def __init__(self, api_client: ApiFootballClient): ...
    def analyze_rom(self, rom_path: str) -> ISSRomInfo: ...
    def create_slot_mapping(self, league_data: LeagueData, rom_info: ISSRomInfo) -> list[SlotMapping]: ...
    def patch_rom(self, rom_path: str, output_path: str, league_data: LeagueData,
                  slot_mapping: list[SlotMapping], on_progress: Callable) -> str: ...
```

### 3.6 `team_name_text.py` — In-Game Scoreboard Names

```python
class TeamNameTextHandler:
    POINTER_TABLE_OFFSET = 0x39DAE
    DATA_START = 0x43ED5
    DATA_END = 0x44486
    MAX_DISPLAY_WIDTH = 70

    # Character → (top_bytes, bottom_bytes, width) mapping
    CHAR_PARTS: dict[str, tuple[bytes, bytes, int]] = { ... }

    def read_team_name(self, rom: bytes, team_index: int) -> str: ...
    def write_team_name(self, rom: bytearray, team_index: int, name: str): ...
    def _normalize_name(self, name: str) -> str:
        """Strip accents, uppercase, replace non-alphanumeric with space."""
        ...
```

### 3.7 `team_name_tiles.py` — Selection Screen Name Graphics

```python
class TeamNameTileHandler:
    POINTER_TABLE_OFFSET = 0x93CD
    POINTER_STEP = 2
    TILE_WIDTH = 32   # pixels
    TILE_HEIGHT = 8   # pixels
    BPP = 2           # 2 bits per pixel, 4-color palette

    PALETTE = {
        0b00: None,                      # Transparent
        0b01: (0xF7, 0xFF, 0xF7),        # Light
        0b10: (0x84, 0xA6, 0xEF),        # Blue
        0b11: (0x00, 0x51, 0xF7),        # Dark blue
    }

    def __init__(self, compressor: KonamiCompressor): ...
    def read_team_name_tile(self, rom: bytes, team_index: int) -> list[list[int]]: ...
    def write_team_name_tile(self, rom: bytearray, team_index: int,
                             pixel_data: list[list[int]]): ...
    def render_text_to_tile(self, name: str) -> list[list[int]]:
        """Render a team name string into an 8x32 2bpp pixel grid.
        Uses a built-in pixel font to draw A-Z characters into the tile."""
        ...
```

### 3.8 `konami_compression.py` — Compression Engine

```python
class KonamiCompressor:
    """Konami SNES tile compression/decompression.

    Ported from web-iss-studio (cpp/web-iss-studio.cpp) by Vladimir Protopopov.
    """

    WINDOW_SIZE = 0x400  # LZ sliding window

    def decompress(self, data: bytes, offset: int) -> tuple[bytes, int]:
        """Decompress Konami-compressed data starting at offset.
        Returns (decompressed_data, bytes_consumed)."""
        ...

    def compress(self, data: bytes) -> bytes:
        """Compress data using Konami SNES format.
        Selects optimal mix of LZ, RLE, and RAW modes."""
        ...

    def _lz_match(self, data: bytes, pos: int, window: bytes) -> tuple[int, int] | None: ...
    def _rle_match(self, data: bytes, pos: int) -> tuple[int, int] | None: ...
```

**Implementation strategy**: Pure Python port first. If performance is insufficient, compile the existing C++ as a Python extension via ctypes or cffi.

---

## 4. Stat Mapping Algorithm

### API-Football → ISS Deluxe Attribute Mapping

ISS Deluxe has **8 player stats** (0–9 scale, displayed as 1–10) plus position, energy, jersey number, skin, and hair.

| ISS Attribute | API-Football Stats Used |
|---|---|
| Acceleration | Position heuristic + age curve |
| Speed | Position heuristic + age curve |
| Shot Power | shots.total, goals (long range if available) |
| Curl Skill | Position heuristic (wingers/playmakers higher) |
| Balance | duels.won / duels.total, fouls.drawn |
| Intelligence | passes.accuracy, key_passes, assists |
| Dribbling | dribbles.success / dribbles.attempts |
| Jump | Position + height (if available) |
| Energy | games.minutes (avg), substitutes.in frequency |

### Position Mapping

| API-Football Position | ISS Deluxe Code |
|---|---|
| Goalkeeper | 1 (GK) |
| Defender | 2 (DEF) |
| Midfielder (defensive) | 3 (DMF) |
| Midfielder | 4 (MF) |
| Midfielder (attacking) | 5 (AMF) |
| Attacker | 6 (FWD) |

API-Football only provides 4 positions (Goalkeeper, Defender, Midfielder, Attacker). Sub-positions (DMF/AMF) are estimated from stats: high tackles → DMF, high assists/key passes → AMF.

### Percentile → Rating (0–9)

Same percentile-based approach as WE2002 (see [Sports Game Roster Patcher plan, Section 9](we_patcher_implementation.md#9-stat-mapping-algorithm)), but mapped to 0–9 instead of 1–9.

| Percentile Range | ISS Rating | Description |
|---|---|---|
| 95–100% | 9 | World class |
| 85–95% | 8 | Excellent |
| 70–85% | 7 | Very good |
| 50–70% | 6 | Good |
| 35–50% | 5 | Average |
| 20–35% | 4 | Below average |
| 10–20% | 3 | Weak |
| 3–10% | 2 | Very weak |
| 0–3% | 1 | Poor |
| — | 0 | Unused (reserve for extreme cases) |

### Fallback (No Detailed Stats)

```
Position-based defaults (0-9 scale):
  GK:  Acl=3 Spd=3 Sht=2 Cur=2 Bal=6 Int=5 Dri=2 Jmp=7 Eng=6
  DEF: Acl=4 Spd=4 Sht=3 Cur=2 Bal=6 Int=5 Dri=3 Jmp=5 Eng=6
  DMF: Acl=5 Spd=5 Sht=4 Cur=4 Bal=5 Int=6 Dri=5 Jmp=4 Eng=7
  MF:  Acl=5 Spd=5 Sht=5 Cur=5 Bal=5 Int=7 Dri=6 Jmp=4 Eng=7
  AMF: Acl=6 Spd=6 Sht=6 Cur=6 Bal=4 Int=7 Dri=7 Jmp=4 Eng=6
  FWD: Acl=6 Spd=6 Sht=7 Cur=5 Bal=5 Int=5 Dri=6 Jmp=5 Eng=5

Age modifiers (same as WE2002):
  < 23: Speed +1, Acceleration +1, Energy +1
  23-30: No adjustment (prime)
  31-33: Speed -1, Acceleration -1, Energy -1
  > 33: Speed -2, Energy -2
```

---

## 5. Graphics & Team Name Patching

Team names must be patched in **three places** for a complete rename:

| Location | Format | Difficulty |
|---|---|---|
| In-game scoreboard/HUD | Structured text (uncompressed) | Medium — documented 4-byte-per-char format |
| Team selection screen | Compressed tile bitmap (8×32px) | Hard — requires Konami compression |
| Flag design tiles | Compressed tile bitmap | Hard — requires Konami compression |

### 5.1 `team_name_text.py` — In-Game Scoreboard Names

Handles the structured text at `0x43ED5`–`0x44486`. Each team name is:
- Length-prefixed (first byte = length in 4-byte units)
- Each character = 4 bytes: position marker + top tile ref + bottom tile ref
- Characters are variable-width (most 9px, some 8px)
- Max display width: 70px (condensed if over)

```python
class TeamNameTextHandler:
    POINTER_TABLE_OFFSET = 0x39DAE
    DATA_START = 0x43ED5
    DATA_END = 0x44486
    MAX_DISPLAY_WIDTH = 70

    # Character → (top_bytes, bottom_bytes, width) mapping
    CHAR_PARTS: dict[str, tuple[bytes, bytes, int]] = { ... }

    def read_team_name(self, rom: bytes, team_index: int) -> str: ...
    def write_team_name(self, rom: bytearray, team_index: int, name: str): ...
    def _normalize_name(self, name: str) -> str:
        """Strip accents, uppercase, replace non-alphanumeric with space."""
        ...
```

### 5.2 `team_name_tiles.py` — Selection Screen Name Graphics

Handles the compressed 8×32 pixel bitmaps on the team selection screen.

```python
class TeamNameTileHandler:
    POINTER_TABLE_OFFSET = 0x93CD
    POINTER_STEP = 2
    TILE_WIDTH = 32  # pixels
    TILE_HEIGHT = 8  # pixels
    BPP = 2          # 2 bits per pixel, 4-color palette

    PALETTE = {
        0b00: None,       # Transparent
        0b01: (0xF7, 0xFF, 0xF7),  # Light
        0b10: (0x84, 0xA6, 0xEF),  # Blue
        0b11: (0x00, 0x51, 0xF7),  # Dark blue
    }

    def __init__(self, compressor: KonamiCompressor): ...

    def read_team_name_tile(self, rom: bytes, team_index: int) -> list[list[int]]:
        """Decompress and decode tile to 8x32 pixel matrix."""
        ...

    def write_team_name_tile(self, rom: bytearray, team_index: int,
                             pixel_data: list[list[int]]):
        """Encode pixel matrix, compress, and write to ROM."""
        ...

    def render_text_to_tile(self, name: str) -> list[list[int]]:
        """Render a team name string into an 8x32 2bpp pixel grid.
        Uses a built-in pixel font to draw A-Z characters into the tile."""
        ...
```

### 5.3 `konami_compression.py` — Compression Engine

Port of the Konami SNES compression/decompression from web-iss-studio's C++ code.

```python
class KonamiCompressor:
    """Konami SNES tile compression/decompression.

    Ported from web-iss-studio (cpp/web-iss-studio.cpp) by Vladimir Protopopov.
    """

    WINDOW_SIZE = 0x400  # LZ sliding window

    def decompress(self, data: bytes, offset: int) -> tuple[bytes, int]:
        """Decompress Konami-compressed data starting at offset.
        Returns (decompressed_data, bytes_consumed)."""
        ...

    def compress(self, data: bytes) -> bytes:
        """Compress data using Konami SNES format.
        Selects optimal mix of LZ, RLE, and RAW modes."""
        ...

    def _lz_match(self, data: bytes, pos: int, window: bytes) -> tuple[int, int] | None:
        """Find best LZ match in sliding window."""
        ...

    def _rle_match(self, data: bytes, pos: int) -> tuple[int, int] | None:
        """Find RLE run at position."""
        ...
```

**Implementation strategy**: Pure Python port first. If performance is insufficient for real-time use, compile the existing C++ as a Python extension via ctypes or cffi.

### 5.4 Kit & Flag Colors

Simple byte writes, no compression involved:

- **Kit colors**: 2 bytes per color at `0x4854E`, BGR555 format
- **Flag colors**: 4 colors × 2 bytes = 10 bytes per team at `0x2DDA5` / `0x2ECBB`

### 5.5 Flag Design Tiles

Flag tile graphics at `0x48000`–`0x48A7F` use the same Konami compression. For club league patching, team crests can be generated from API-Football logo URLs:

```
API logo PNG → resize to flag tile dimensions → quantize to 4 colors → encode as 2bpp tile → Konami compress → write to ROM
```

This uses the same `KonamiCompressor` and a similar pipeline to `team_name_tiles.py`.

---

## 6. UI Screen

### `iss_patcher_screen.py` — ISS Deluxe Patcher Screen

Same step-by-step pattern as the WE2002 patcher:

```
ISS Deluxe Patcher
─────────────────────
[1] Select League    → League Browser Modal (shared)
[2] Preview Rosters  → Roster Preview Modal (shared, 20 players, 8 stats)
[3] Select ROM       → File picker (SFC/SMC)
[4] Map Team Slots   → Slot Mapping Modal (36 team slots)
[5] Patch ROM        → Patch Progress Modal
```

Shared modals from WE2002 are reused with game-specific config (player count, stat count, file extensions).

### Sports Patcher Sub-Menu Update

```
Sports Game Patcher
─────────────────────
▶ WE2002 - Winning Eleven 2002 (PS1)
▶ ISS Deluxe - Int'l Superstar Soccer Deluxe (SNES)
```

---

## 7. State Management

```python
@dataclass
class ISSPatcherState:
    """State for the ISS Deluxe patcher."""

    # NOTE: API key is stored in Settings (api_football_key), not here.

    # League selection
    selected_league: League | None = None
    selected_season: int = 2025
    available_leagues: list[League] = field(default_factory=list)
    league_search_query: str = ""

    # Fetched data
    league_data: LeagueData | None = None
    fetch_progress: float = 0.0
    fetch_status: str = ""
    is_fetching: bool = False

    # ROM
    rom_path: str = ""
    rom_info: ISSRomInfo | None = None
    rom_valid: bool = False

    # Slot mapping
    slot_mapping: list[SlotMapping] = field(default_factory=list)

    # Patching
    patch_progress: float = 0.0
    patch_status: str = ""
    is_patching: bool = False
    patch_output_path: str = ""
    patch_complete: bool = False

    # UI navigation
    selected_menu_index: int = 0
    active_modal: str | None = None
```

Add `iss_patcher: ISSPatcherState` field to the main `AppState` dataclass.

---

## 8. Implementation Phases

### Phase 1: ROM Reader/Writer (Core)
- [ ] Create `src/services/iss_patcher/` module structure
- [ ] Implement `encoding.py` — custom character encoding table
- [ ] Implement `models.py` — `ISSPlayerRecord`, `ISSPlayerAttributes`, `ISSTeamRecord`, `ISSRomInfo`
- [ ] Implement `rom_reader.py` — read player names, stats, positions from ROM
- [ ] Implement `rom_writer.py` — write player names, stats, positions to ROM
- [ ] Test: read a team from ROM, modify one player name, write back, verify in emulator

### Phase 2: Stat Mapping
- [ ] Implement `stat_mapper.py` — API-Football stats → ISS 0–9 scale
- [ ] Implement position sub-classification (DMF/AMF heuristic)
- [ ] Implement `_select_best_20()` — pick 20 from full squad
- [ ] Implement `_truncate_name()` — 8-char limit, ISS charset only
- [ ] Test: map a full league, verify stat distribution

### Phase 3: Kit & Flag Colors
- [ ] Implement kit color read/write (BGR555 at known offsets)
- [ ] Implement flag color read/write (4 colors per team)
- [ ] Test: change one team's colors, verify in emulator

### Phase 4: Konami Compression & Team Name Tiles
- [ ] Port Konami decompression from web-iss-studio C++ (`konami_compression.py`)
- [ ] Implement Konami compression (LZ + RLE A0/C0/E0 + RAW modes)
- [ ] Test: decompress known tile data, recompress, verify byte-level round-trip
- [ ] Implement `team_name_tiles.py` — read/write 8×32px team name bitmaps on selection screen
- [ ] Implement built-in pixel font for `render_text_to_tile()` (A-Z, 0-9 at minimum)
- [ ] Test: render a team name, compress, write to ROM, verify in emulator selection screen

### Phase 5: In-Game Team Name Text
- [ ] Implement `team_name_text.py` — read/write structured scoreboard text
- [ ] Build full CHAR_PARTS mapping (top/bottom tile refs + width for A-Z, 0-9, space, period)
- [ ] Implement `_normalize_name()` — strip accents, uppercase, fit within 70px display width
- [ ] Test: write a team name, verify on in-game scoreboard in emulator

### Phase 6: Flag Design Tiles
- [ ] Implement flag tile decompression/recompression using `KonamiCompressor`
- [ ] Pipeline: API-Football team logo → resize → quantize to 4 colors → encode 2bpp → compress → write
- [ ] Test: replace one flag, verify in emulator

### Phase 7: Orchestrator + UI
- [ ] Implement `patcher.py` — full pipeline (players + stats + colors + team names + flags)
- [ ] Add `ISSPatcherState` to `state.py`
- [ ] Implement `iss_patcher_screen.py`
- [ ] Add ISS Deluxe to `sports_patcher_screen.py` game list
- [ ] Reuse shared modals (league browser, roster preview, slot mapping, progress)

### Phase 8: Polish
- [ ] Handle malformed/unsupported ROM variants (Europe vs USA)
- [ ] Handle characters not in ISS charset (strip accents, transliterate)
- [ ] CSV export/import for ISS Deluxe format
- [ ] Verify compressed tile data fits within ROM free space (track pointer table updates)

---

## 9. Testing Strategy

### Unit Tests
- `test_encoding.py`: Round-trip encode/decode for all characters
- `test_stat_mapper.py`: Verify 0–9 mapping, position classification
- `test_rom_reader.py`: Parse known ROM and verify team/player names match expected
- `test_rom_writer.py`: Write and re-read player data, verify round-trip
- `test_konami_compression.py`: Decompress known data → recompress → verify identical output; test all modes (LZ, RLE A0/C0/E0, RAW)
- `test_team_name_text.py`: Read existing scoreboard name → write new name → re-read → verify round-trip; test normalization (accents, length overflow)
- `test_team_name_tiles.py`: `render_text_to_tile()` produces correct 8×32 pixel grid; compress/decompress round-trip matches

### Integration Tests
- Read a known ISS Deluxe ROM dump, verify all 36 team rosters parse correctly
- Write a patched ROM and binary-diff against expected output
- Full pipeline: patch all 36 teams (players + stats + colors + team names + flags), verify patched ROM loads without errors
- Compressed tile data fits within available ROM free space after all teams are written

### Manual Testing
- Load patched ROM in bsnes, Snes9x, or RetroArch (bsnes core)
- Verify: player names display correctly in team selection
- Verify: player stats are correct in match
- Verify: kit colors render properly
- Verify: **team names on selection screen** render correctly (no garbled tiles)
- Verify: **team names on in-game scoreboard** display correctly (no overflow, correct characters)
- Verify: **flag tiles** render correctly on selection screen
- Verify: game plays without crashes

---

## 10. Known Limitations

| Limitation | Mitigation |
|---|---|
| 20 players per team (fixed) | Selection algorithm picks best 20 from full squad |
| 8-character name limit | Smart abbreviation + truncation |
| No numbers/accents in names | Strip accents (é→e), transliterate where possible |
| Stats are 0–9 only (coarse) | Percentile-based mapping maximizes differentiation |
| Only 36 team slots | Map leagues with ≤36 teams, or pick top 36 |
| Compressed tile space is finite | Track total compressed size; warn if tiles exceed available ROM region |
| No SRAM (no saves) | Not a patching concern — game uses passwords |
| Secret teams (6) not patchable | Only standard 36 slots targeted |

---

## 11. References & Resources

### Open-Source Tools
- [ISSD-SNES-ROM-Web-Editor](https://github.com/EstebanFuentealba/ISSD-SNES-ROM-Web-Editor) (MIT) — Player name/stat offsets, character encoding
- [Web ISS Studio](https://github.com/EstebanFuentealba/web-iss-studio) — Flag colors, team name tiles, Konami compression
- [ISS Deluxe Full Disassembly](https://github.com/Yoshifanatic1/International-Superstar-Soccer-Deluxe-SNES-Disassembly) (GPL-3.0) — Complete ROM/RAM map

### Community Tools
- [FECIC Abilities](https://www.romhacking.net/utilities/1578/) — Player ability/name editor (Windows)
- [FECIC Colors](https://www.romhacking.net/utilities/) — Uniform/kit color editor (Windows)
- [FECIC Goalkeepers](https://www.romhacking.net/utilities/) — GK palette editor (Windows)

### ROM Hacks (Reference)
- [ISS Deluxe 30 Years](https://www.romhacking.net/hacks/8949/) (2025) — Extended name length hack
- [ISS Deluxe Plus](https://www.romhacking.net/hacks/7898/) — 54 countries hack

### Community
- [Romhacking.net — ISS Deluxe](https://www.romhacking.net/games/2527/)
- [SNES ISS 4chan Cup Wiki](https://implyingrigged.info/wiki/SNES_ISS_4chan_Cup) — Community tournament using FECIC
- [ISS Deluxe Team Data Guide (GameFAQs)](https://gamefaqs.gamespot.com/snes/588391-international-superstar-soccer-deluxe/faqs/52919)

### Shared Dependencies
- API-Football client: `src/services/we_patcher/api_football.py` (see [main plan](we_patcher_implementation.md))
- Flag tile pipeline may need Pillow for API logo → 4-color quantization; otherwise pure byte manipulation
