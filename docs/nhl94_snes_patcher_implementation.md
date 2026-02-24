# NHL 94 (SNES) Roster Patcher — Implementation Plan

## Overview

A patcher for **NHL 94** (SNES) under the Sports Game Patcher feature. Fetches real-world NHL player data via the free NHL API and patches an NHL 94 SNES ROM with current rosters — player names, stats, jersey numbers, positions, handedness, and weight. Teams and flags remain unchanged (all 26 NHL teams + 2 All-Star teams stay as-is).

**Target ROM**: NHL 94 (USA) — `.sfc` (headerless) or `.smc` (512-byte copier header)

> **Settings & Menu**: The sports patcher menu structure and settings toggle are covered by the [Sports Game Roster Patcher plan](we_patcher_implementation.md) (Sections 1–2). This document covers NHL 94 SNES-specific ROM format, NHL API integration, data mapping, and patching logic.

> **No API key required**: Unlike API-Football, the NHL API is free and public — no authentication needed. The `api_football_key` setting does not apply here.

---

## Table of Contents

1. [ROM Format Reference](#1-rom-format-reference)
2. [NHL API Integration](#2-nhl-api-integration)
3. [Architecture](#3-architecture)
4. [Service Layer](#4-service-layer)
5. [Stat Mapping Algorithm](#5-stat-mapping-algorithm)
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
| [nhl94e](https://github.com/clandrew/nhl94e) | C++/CLI | — | Player names, stats, ROM expansion, pointer tables |
| [SNES 94 Roster Tool](https://forum.nhl94.com/index.php?/topic/16918-tool-snes-94-roster-tool/) | — | — | CSV import/export of full rosters |
| [NHL 94 SNESVault](https://forum.nhl94.com/) | ASM | — | Full disassembly (DiztinGUIsh), complete ROM/RAM map |

### ROM Specifications

| Property | Value |
|---|---|
| Platform | SNES (Super Nintendo) |
| Layout | LoROM |
| Size | ~634 KB (expandable for name changes) |
| Region | USA |
| Maker | EA Sports |
| Format | `.sfc` (headerless) or `.smc` (+512-byte copier header) |

### Team & Player Layout

| Constraint | Value |
|---|---|
| NHL teams | 26 |
| All-Star teams | 2 (East, West) |
| Total teams | **28** |
| Players per team | ~**23–25** (variable, typically 14F + 9D + 2G) |
| Max goalies per team | 4 |
| Player name encoding | **Plain ASCII** (no custom table needed) |

### Team Pointer Table

- **Offset**: `0x9CA5E7` (headerless ROM)
- **Size**: 28 entries × 4 bytes = 112 bytes
- **Format**: `[low_byte][high_byte][dead][dead]` — game hardcodes bank `$9C`
- **Team IDs**: `0x00` (Anaheim) through `0x19` (Winnipeg), `0x1A` (All-Stars East), `0x1B` (All-Stars West)

### Per-Team Data Block Structure

Each team pointer references a block containing:

1. **Header**: 2-byte little-endian length + header data
2. **Player records**: Sequential until two `0x00` bytes terminate the list
3. **Team metadata** (after players):
   - City/location string (2-byte length + ASCII)
   - Location acronym (2-byte length + ASCII)
   - Team name (2-byte length + ASCII)
   - Venue name (2-byte length + ASCII)

### Player Record Structure

| Offset | Size | Field | Details |
|--------|------|-------|---------|
| 0–1 | 2 bytes | Name length | Little-endian; includes the 2-byte header itself |
| 2+ | Variable | Name string | Plain ASCII |
| +0 | 1 byte | Jersey number | BCD format (high nibble=tens, low nibble=ones) |
| +1 | 1 byte | Weight / Agility | High nibble: weight class (0–14); Low nibble: agility (0–6) |
| +2 | 1 byte | Speed / Off. Awareness | High nibble: speed (0–6); Low nibble: off. awareness (0–6) |
| +3 | 1 byte | Def. Awareness / Shot Power | High nibble: def. awareness (0–6); Low nibble: shot power (0–6) |
| +4 | 1 byte | Checking / Handedness | High nibble: checking (0–6); Low nibble: hand (even=L, odd=R) |
| +5 | 1 byte | Stick Handling / Shot Accuracy | High nibble: stick handling (0–6); Low nibble: shot accuracy (0–6) |
| +6 | 1 byte | Endurance / Roughness | High nibble: endurance (0–6); Low nibble: roughness (0–6, hidden) |
| +7 | 1 byte | Pass Accuracy / Aggression | High nibble: pass accuracy (0–6); Low nibble: aggression (0–6) |

**Total**: 8 stat bytes per player (14 attributes via nibble-packing) + variable-length name.

**Record stride**: name length + 8 bytes.

### Goalie Record Structure

Goalies use a different stat layout (12 nibbles / 6 bytes instead of 14 / 7 for skaters):
- Weight, Agility, Speed, (reserved), Def. Awareness, Puck Control, (reserved), Handedness, (reserved), (reserved), Stick R/L, Glove R/L

### Stat Value Scale

| Raw Value | Displayed Rating |
|-----------|-----------------|
| 0 | 25 |
| 1 | 35 |
| 2 | 45 |
| 3 | 55 |
| 4 | 65 |
| 5 | 85 |
| 6 | 100 |

### Weight Conversion

`pounds = 140 + (weight_class * 8)` where weight_class ranges 0–14, giving 140–252 lbs.

### Name Length Encoding

The 2-byte length field includes itself:

| Length Code | Actual Characters |
|-------------|-------------------|
| `0x0A` | 6–7 |
| `0x0C` | 8–9 |
| `0x0E` | 10–11 |
| `0x10` | 12–13 |
| `0x12` | 14–15 |

### Line Configuration

Each team defines 7 line combos (stored after goalie count):
- Scoring Line 1 (SC1), Scoring Line 2 (SC2), Checking Line (CHK)
- Power Play 1 (PP1), Power Play 2 (PP2)
- Penalty Kill 1 (PK1), Penalty Kill 2 (PK2)

Each line: G, LD, RD, LW, C, RW, Extra Attacker (by player index).

### Team Advantage Ratings

3-byte sequences encoding Offense/Defense, Home/Away, PP/PK on a 0–7 scale. `70 30 30` = best, `07 03 03` = worst.

### ROM Expansion for Name Changes

Changing player name lengths requires the **nhl94e detour technique**:
- Patch `LookupPlayerName()` at `$9F/C732` with a `JMP` to expanded ROM space at `$A08100`
- Write alternate pointer table at `0xA8D000`
- This is a 55-byte 65816 assembly patch documented in nhl94e's source

---

## 2. NHL API Integration

### API Overview

The NHL provides a **free, public API** — no API key or authentication required.

| Property | Value |
|---|---|
| Base URL | `https://api-web.nhle.com` |
| Auth | None (public) |
| Rate limit | Undocumented (generous for reasonable use) |
| Python wrapper | `nhl-api-py` on PyPI |
| Format | JSON |

### Key Endpoints

#### Current Roster
```
GET /v1/roster/{team-abbrev}/current
```
Returns `forwards`, `defensemen`, `goalies` arrays. Each player:
- `firstName`, `lastName`, `sweaterNumber`, `positionCode`
- `shootsCatches` (L/R), `heightInInches`, `weightInPounds`
- `birthDate`, `birthCountry`
- `id` (player ID for detailed stats)

#### Player Stats
```
GET /v1/player/{player-id}/landing
```
Returns career and season stats:
- Goals, assists, points, plus/minus, PIM, shots, shooting %
- Power play / shorthanded stats, game-winning goals
- TOI (time on ice), games played
- For goalies: wins, losses, GAA, save %, shutouts

#### Standings
```
GET /v1/standings/now
```
Returns current league standings (useful for team advantage ratings).

#### Team Abbreviations
```
ANA, BOS, BUF, CAR, CBJ, CGY, CHI, COL, DAL, DET, EDM, FLA,
LAK, MIN, MTL, NJD, NSH, NYI, NYR, OTT, PHI, PIT, SEA, SJE,
STL, TBL, TOR, UTA, VAN, VGK, WPG, WSH
```

### Caching Strategy

Same approach as the soccer patchers — cache API responses as JSON files in `workdir/nhl_cache/`:
- `rosters/{team_abbrev}.json` — team roster (refresh daily)
- `players/{player_id}.json` — player stats (refresh daily)
- `standings.json` — league standings (refresh daily)

### Team Mapping: Modern NHL → NHL 94 Slots

Modern NHL has **32 teams**, the game has **26 + 2 All-Star = 28 slots**. Since the user wants to keep the same teams, we map based on franchise continuity:

| NHL 94 Slot | Modern Equivalent | Notes |
|---|---|---|
| Anaheim (Mighty Ducks) | Anaheim Ducks | Same franchise |
| Boston | Boston Bruins | — |
| Buffalo | Buffalo Sabres | — |
| Calgary | Calgary Flames | — |
| Chicago | Chicago Blackhawks | — |
| Dallas | Dallas Stars | — |
| Detroit | Detroit Red Wings | — |
| Edmonton | Edmonton Oilers | — |
| Florida | Florida Panthers | — |
| Hartford | Carolina Hurricanes | Relocated 1997 |
| Los Angeles | Los Angeles Kings | — |
| Montreal | Montreal Canadiens | — |
| New Jersey | New Jersey Devils | — |
| NY Islanders | New York Islanders | — |
| NY Rangers | New York Rangers | — |
| Ottawa | Ottawa Senators | — |
| Philadelphia | Philadelphia Flyers | — |
| Pittsburgh | Pittsburgh Penguins | — |
| Quebec | Colorado Avalanche | Relocated 1995 |
| San Jose | San Jose Sharks | — |
| St. Louis | St. Louis Blues | — |
| Tampa Bay | Tampa Bay Lightning | — |
| Toronto | Toronto Maple Leafs | — |
| Vancouver | Vancouver Canucks | — |
| Washington | Washington Capitals | — |
| Winnipeg | Winnipeg Jets | Current Jets (relocated 2011) |
| All-Stars East | Eastern All-Stars | Best players from East |
| All-Stars West | Western All-Stars | Best players from West |

**6 modern teams without slots**: CBJ, MIN, NSH, SEA, UTA, VGK. These are excluded (or user could optionally map them to All-Star slots).

---

## 3. Architecture

### File Structure

```
src/services/nhl94_snes_patcher/
├── __init__.py              # Public API exports
├── models.py                # Data classes (NHLPlayerRecord, NHLTeamRecord, etc.)
├── rom_reader.py            # Read and parse NHL 94 SNES ROM data
├── rom_writer.py            # Write patched data back to ROM
├── rom_expander.py          # Name expansion detour (nhl94e technique)
├── stat_mapper.py           # NHL API stats → 0-6 scale
├── nhl_api.py               # NHL API client (rosters, player stats)
└── patcher.py               # Orchestrator

src/ui/screens/
├── nhl94_snes_patcher_screen.py  # NHL 94 SNES patcher screen
```

### Integration Points

- `sports_patcher_screen.py` — adds "NHL 94 - NHL Hockey (SNES)" to game list
- Shared caching pattern from soccer patchers (but different API)
- Shared UI modals: roster preview, progress

---

## 4. Service Layer

### 4.1 `nhl_api.py` — NHL API Client

```python
class NHLApiClient:
    BASE_URL = "https://api-web.nhle.com"
    CACHE_DIR = "nhl_cache"
    CACHE_TTL = 86400  # 24 hours

    def get_roster(self, team_abbrev: str) -> list[NHLPlayer]: ...
    def get_player_stats(self, player_id: int, season: str) -> NHLPlayerStats | None: ...
    def get_standings(self) -> list[NHLTeamStanding]: ...
    def get_all_rosters(self, on_progress: Callable) -> dict[str, list[NHLPlayer]]: ...
```

### 4.2 `models.py` — Data Classes

```python
@dataclass
class NHLPlayer:
    id: int
    first_name: str
    last_name: str
    position: str          # C, LW, RW, D, G
    jersey_number: int
    shoots_catches: str    # L or R
    height_inches: int
    weight_pounds: int
    birth_date: str

@dataclass
class NHLPlayerStats:
    games_played: int
    goals: int
    assists: int
    points: int
    plus_minus: int
    pim: int
    shots: int
    toi_per_game: float    # minutes
    hits: int
    blocked_shots: int
    # Goalie-specific
    wins: int | None = None
    gaa: float | None = None
    save_pct: float | None = None

@dataclass
class NHL94PlayerRecord:
    name: str              # ASCII, variable length
    jersey_number: int     # 1-99
    weight_class: int      # 0-14
    handedness: int        # even=L, odd=R
    agility: int           # 0-6
    speed: int             # 0-6
    off_awareness: int     # 0-6
    def_awareness: int     # 0-6
    shot_power: int        # 0-6
    checking: int          # 0-6
    stick_handling: int    # 0-6
    shot_accuracy: int     # 0-6
    endurance: int         # 0-6
    roughness: int         # 0-6
    pass_accuracy: int     # 0-6
    aggression: int        # 0-6
    is_goalie: bool = False

@dataclass
class NHL94TeamRecord:
    team_id: int
    city: str
    acronym: str
    name: str
    venue: str
    players: list[NHL94PlayerRecord]
    line_config: dict      # Line assignments by player index

@dataclass
class NHL94RomInfo:
    path: str
    has_header: bool       # 512-byte SMC header
    header_offset: int     # 0 or 0x200
    teams: list[NHL94TeamRecord]
    valid: bool
```

### 4.3 `rom_reader.py` — ROM Analysis

```python
class NHL94SNESRomReader:
    POINTER_TABLE_OFFSET = 0x9CA5E7  # headerless
    TEAM_COUNT = 28
    POINTER_SIZE = 4
    BANK = 0x9C

    def __init__(self, rom_path: str): ...
    def detect_header(self) -> bool:
        """Detect 512-byte SMC copier header."""
        ...
    def validate_rom(self) -> bool: ...
    def read_team(self, team_index: int) -> NHL94TeamRecord: ...
    def read_all_teams(self) -> list[NHL94TeamRecord]: ...
    def _parse_player_record(self, data: bytes, offset: int) -> tuple[NHL94PlayerRecord, int]:
        """Parse one player record, return (record, bytes_consumed)."""
        ...
    def _parse_goalie_record(self, data: bytes, offset: int) -> tuple[NHL94PlayerRecord, int]: ...
```

### 4.4 `rom_writer.py` — ROM Patching

```python
class NHL94SNESRomWriter:
    def __init__(self, rom_path: str, output_path: str): ...
    def write_player_stats(self, team_index: int, player_index: int,
                           record: NHL94PlayerRecord): ...
    def write_team_roster(self, team_index: int, players: list[NHL94PlayerRecord]): ...
    def finalize(self): ...
```

### 4.5 `rom_expander.py` — Name Length Expansion

```python
class NHL94RomExpander:
    """Handles ROM expansion for name length changes.

    Implements the nhl94e detour technique:
    - Patches LookupPlayerName() at $9F/C732 with JMP to $A08100
    - Writes alternate pointer table at 0xA8D000
    - Expands ROM to fit new name data
    """

    LOOKUP_FUNC_ADDR = 0x9FC732
    DETOUR_ADDR = 0xA08100
    ALT_POINTER_TABLE = 0xA8D000
    DETOUR_SIZE = 55  # bytes of 65816 assembly

    def needs_expansion(self, original: list[NHL94TeamRecord],
                        patched: list[NHL94TeamRecord]) -> bool: ...
    def expand_rom(self, rom: bytearray, patched_teams: list[NHL94TeamRecord]) -> bytearray: ...
    def _write_detour_code(self, rom: bytearray): ...
    def _write_alt_pointer_table(self, rom: bytearray, teams: list[NHL94TeamRecord]): ...
```

### 4.6 `stat_mapper.py` — Attribute Mapping

```python
class NHL94StatMapper:
    # Modern NHL → NHL 94 slot mapping
    TEAM_MAP: dict[str, int] = {
        "ANA": 0, "BOS": 1, "BUF": 2, "CGY": 3, "CHI": 4,
        "DAL": 5, "DET": 6, "EDM": 7, "FLA": 8, "CAR": 9,  # Hartford→Carolina
        "LAK": 10, "MTL": 11, "NJD": 12, "NYI": 13, "NYR": 14,
        "OTT": 15, "PHI": 16, "PIT": 17, "COL": 18,  # Quebec→Colorado
        "SJS": 19, "STL": 20, "TBL": 21, "TOR": 22, "VAN": 23,
        "WSH": 24, "WPG": 25,
    }

    def map_player(self, player: NHLPlayer, stats: NHLPlayerStats | None) -> NHL94PlayerRecord: ...
    def map_weight(self, weight_pounds: int) -> int:
        """Map real weight to 0-14 class: (weight - 140) / 8, clamped."""
        ...
    def _map_handedness(self, shoots_catches: str) -> int: ...
    def _select_roster(self, players: list[NHLPlayer]) -> list[NHLPlayer]:
        """Select ~23 players (14F + 7D + 2G) from full roster."""
        ...
```

### 4.7 `patcher.py` — Orchestrator

```python
class NHL94SNESPatcher:
    def __init__(self, api_client: NHLApiClient): ...
    def analyze_rom(self, rom_path: str) -> NHL94RomInfo: ...
    def fetch_current_rosters(self, season: str, on_progress: Callable) -> dict[str, list[NHLPlayer]]: ...
    def patch_rom(self, rom_path: str, output_path: str, season: str,
                  on_progress: Callable) -> str: ...
```

---

## 5. Stat Mapping Algorithm

### NHL API → NHL 94 Attribute Mapping

NHL 94 has **10 skater stats** (0–6 scale) plus weight, handedness, endurance, roughness, pass accuracy, and aggression.

| NHL 94 Attribute | NHL API Stats Used |
|---|---|
| Speed | Skating metrics, position heuristic, age |
| Agility | Position heuristic (smaller players higher), age |
| Shot Power | Shot distance data, goals, position |
| Shot Accuracy | Shooting %, goals per shot |
| Stick Handling | Points, assists, TOI context |
| Pass Accuracy | Assists, assists/game |
| Off. Awareness | Points, power play points, +/- |
| Def. Awareness | +/-, blocked shots, hits, PK time |
| Checking | Hits, PIM, position (defensemen higher) |
| Endurance | TOI per game, games played |
| Roughness | PIM, fighting majors (hidden stat) |
| Aggression | PIM, hits |

### Rating Scale (0–6)

| Percentile Range | NHL 94 Rating | Displayed |
|---|---|---|
| 95–100% | 6 | 100 |
| 80–95% | 5 | 85 |
| 60–80% | 4 | 65 |
| 40–60% | 3 | 55 |
| 20–40% | 2 | 45 |
| 5–20% | 1 | 35 |
| 0–5% | 0 | 25 |

### Weight Mapping

```
weight_class = clamp((weight_pounds - 140) / 8, 0, 14)
```

### Goalie Stat Mapping

| NHL 94 Attribute | NHL API Stats Used |
|---|---|
| Puck Control | Save %, goals against average |
| Def. Awareness | Save %, games played |
| Agility | Age, size heuristic |
| Speed | Age heuristic |

### Fallback (No Detailed Stats — Rookies)

```
Position-based defaults (0-6 scale):
  C:  Spd=3 Agi=3 ShP=3 ShA=3 StH=3 Pas=3 OfA=3 DfA=2 Chk=2 End=3 Rou=2 Agg=2
  LW: Spd=3 Agi=3 ShP=3 ShA=3 StH=3 Pas=2 OfA=3 DfA=2 Chk=3 End=3 Rou=3 Agg=3
  RW: Spd=3 Agi=3 ShP=3 ShA=3 StH=3 Pas=2 OfA=3 DfA=2 Chk=3 End=3 Rou=3 Agg=3
  D:  Spd=2 Agi=2 ShP=2 ShA=2 StH=2 Pas=3 OfA=2 DfA=4 Chk=4 End=3 Rou=3 Agg=3
  G:  Spd=2 Agi=4 PkC=3 DfA=3 End=4
```

### Reference Implementation

The [EA-NHL-Tools Roster-Generator](https://github.com/abdulahmad/EA-NHL-Tools) provides a working stat-mapping algorithm from the NHL API to retro EA NHL attributes. Use this as a reference/starting point.

---

## 6. UI Screen

### `nhl94_snes_patcher_screen.py`

Simpler flow than soccer patchers — no league selection or slot mapping needed:

```
NHL 94 (SNES) Roster Patcher
─────────────────────────────
[1] Select Season     → Season picker (default: current)
[2] Fetch Rosters     → Fetch all 26 teams from NHL API
[3] Preview Rosters   → Roster Preview Modal (per-team player list)
[4] Select ROM        → File picker (SFC/SMC)
[5] Patch ROM         → Patch Progress Modal
```

### Sports Patcher Sub-Menu Update

```
Sports Game Patcher
─────────────────────
▶ WE2002 - Winning Eleven 2002 (PS1)
▶ ISS Deluxe - Int'l Superstar Soccer Deluxe (SNES)
▶ NHL 94 - NHL Hockey '94 (SNES)
▶ NHL 94 - NHL Hockey '94 (Genesis)
```

---

## 7. State Management

```python
@dataclass
class NHL94SNESPatcherState:
    """State for the NHL 94 SNES patcher."""

    # Season
    selected_season: str = "2025-2026"

    # Fetched data
    rosters: dict[str, list[NHLPlayer]] | None = None
    fetch_progress: float = 0.0
    fetch_status: str = ""
    is_fetching: bool = False

    # ROM
    rom_path: str = ""
    rom_info: NHL94RomInfo | None = None
    rom_valid: bool = False

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

Add `nhl94_snes_patcher: NHL94SNESPatcherState` field to the main `AppState` dataclass.

---

## 8. Implementation Phases

### Phase 1: NHL API Client
- [ ] Implement `nhl_api.py` — fetch rosters, player stats, standings
- [ ] Implement JSON caching with TTL
- [ ] Implement `models.py` — `NHLPlayer`, `NHLPlayerStats`, `NHL94PlayerRecord`, etc.
- [ ] Test: fetch current Bruins roster, verify data completeness

### Phase 2: ROM Reader/Writer (Core)
- [ ] Implement `rom_reader.py` — detect header, parse pointer table, read teams/players
- [ ] Implement `rom_writer.py` — write player stats back to ROM (in-place)
- [ ] Test: read all 28 teams, modify one player's stats, write back, verify in emulator

### Phase 3: ROM Expansion
- [ ] Implement `rom_expander.py` — nhl94e detour technique for name length changes
- [ ] Write the 55-byte 65816 assembly detour patch
- [ ] Implement alternate pointer table generation
- [ ] Test: change a player's name to a longer name, verify game loads correctly

### Phase 4: Stat Mapping
- [ ] Implement `stat_mapper.py` — NHL API stats → 0-6 scale
- [ ] Implement weight mapping, handedness mapping
- [ ] Implement roster selection (pick ~23 from full roster)
- [ ] Reference EA-NHL-Tools Roster-Generator for mapping formulas
- [ ] Test: map all teams, verify stat distribution looks reasonable

### Phase 5: Orchestrator + UI
- [ ] Implement `patcher.py` — full pipeline
- [ ] Add `NHL94SNESPatcherState` to `state.py`
- [ ] Implement `nhl94_snes_patcher_screen.py`
- [ ] Add NHL 94 SNES to `sports_patcher_screen.py` game list
- [ ] Reuse shared modals (roster preview, progress)

### Phase 6: Polish
- [ ] Handle headered vs headerless ROM detection
- [ ] CSV export/import for manual roster editing
- [ ] Team advantage rating recalculation based on standings
- [ ] Line configuration generation from real-world line combos

---

## 9. Testing Strategy

### Unit Tests
- `test_nhl_api.py`: Verify roster fetch, player stats parsing, caching
- `test_rom_reader.py`: Parse known ROM, verify all 28 teams and player counts
- `test_rom_writer.py`: Write stats, re-read, verify round-trip
- `test_rom_expander.py`: Expand ROM with new names, verify detour patch and pointer table
- `test_stat_mapper.py`: Verify 0-6 mapping, weight conversion, roster selection

### Integration Tests
- Read a known NHL 94 SNES ROM, verify all team rosters parse correctly
- Full pipeline: fetch rosters → map stats → patch ROM → verify binary output
- ROM expansion: patch with longer player names, verify game loads

### Manual Testing
- Load patched ROM in bsnes, Snes9x, or RetroArch (bsnes core)
- Verify: player names display correctly on roster screen
- Verify: player stats are reasonable in-game
- Verify: jersey numbers are correct
- Verify: line configurations make sense
- Verify: game plays without crashes through full period

---

## 10. Known Limitations

| Limitation | Mitigation |
|---|---|
| 26 team slots (modern NHL has 32) | 6 expansion teams excluded; could map to All-Star slots |
| ~23–25 players per team | Matches real NHL active roster size |
| Name changes require ROM expansion | Automated via nhl94e detour technique |
| Stats are 0–6 only (very coarse) | Percentile-based mapping maximizes differentiation |
| No portrait/face updates | Player card images stay as original |
| Line combos are manual | Could auto-generate from real NHL line data |
| Hartford/Quebec are relocated teams | Map to Carolina/Colorado rosters |
| NHL API has no auth but may change | Cache aggressively; fallback to cached data |

---

## 11. References & Resources

### Open-Source Tools
- [nhl94e](https://github.com/clandrew/nhl94e) — C++ SNES editor with ROM expansion
- [SNES 94 Roster Tool](https://forum.nhl94.com/index.php?/topic/16918-tool-snes-94-roster-tool/) — CSV import/export
- [NHL 94 SNESVault](https://forum.nhl94.com/) — Full SNES disassembly
- [EA-NHL-Tools](https://github.com/abdulahmad/EA-NHL-Tools) — Roster-Generator with NHL API stat mapping
- [Statto's Editor v0.8.1](https://forum.nhl94.com/index.php?/topic/11993-editor-v081/) — VB6 team/player editor

### NHL API
- [NHL API Reference](https://github.com/Zmalski/NHL-API-Reference) — Community-maintained endpoint docs
- [nhl-api-py](https://pypi.org/project/nhl-api-py/) — Python wrapper for NHL API

### Community
- [forum.nhl94.com](https://forum.nhl94.com/) — Central hub for NHL 94 modding
- [nhl94.com](https://nhl94.com/) — ROM hacking guides and community tools
- [Names and Stats in NHL 94](https://cml-a.com/content/2020/11/23/names-and-stats-in-nhl-94/) — Technical blog post on ROM internals

### Technical References
- [SNES ROM Header Reference](https://snes.nesdev.org/wiki/ROM_header)
- [nhl94e Player Names Documentation](https://github.com/clandrew/nhl94e/blob/main/docs/PlayerNames.txt)
