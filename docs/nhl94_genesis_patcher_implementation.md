# NHL 94 (Genesis) Roster Patcher — Implementation Plan

## Overview

A patcher for **NHL 94** (Sega Genesis / Mega Drive) under the Sports Game Patcher feature. This is the **gold standard** for retro hockey modding — the most well-documented and actively modded hockey game ever. Fetches real-world NHL player data via the free NHL API and patches an NHL 94 Genesis ROM with current rosters — player names, stats, jersey numbers, positions, handedness, and weight. Teams and flags remain unchanged.

**Target ROM**: NHL 94 (USA, Europe) — `.bin` or `.md` format

> **Settings & Menu**: The sports patcher menu structure and settings toggle are covered by the [Sports Game Roster Patcher plan](we_patcher_implementation.md) (Sections 1–2). This document covers NHL 94 Genesis-specific ROM format and patching logic.

> **NHL API**: Same API integration as the [NHL 94 SNES patcher](nhl94_snes_patcher_implementation.md) (Section 2). The `NHLApiClient` class is shared between both patchers.

> **No API key required**: The NHL API is free and public — no authentication needed.

---

## Table of Contents

1. [ROM Format Reference](#1-rom-format-reference)
2. [Architecture](#2-architecture)
3. [Service Layer](#3-service-layer)
4. [Stat Mapping Algorithm](#4-stat-mapping-algorithm)
5. [UI Screen](#5-ui-screen)
6. [State Management](#6-state-management)
7. [Implementation Phases](#7-implementation-phases)
8. [Testing Strategy](#8-testing-strategy)
9. [Known Limitations](#9-known-limitations)
10. [References & Resources](#10-references--resources)

---

## 1. ROM Format Reference

### Source of Truth

| Resource | Language | License | What It Covers |
|---|---|---|---|
| [NOSE (NHL Old Skool Editor)](https://www.romhacking.net/utilities/290/) | — | — | Complete GUI editor for Genesis NHL series; de facto standard |
| [EA-NHL-Tools](https://github.com/abdulahmad/EA-NHL-Tools) | Python/JS | — | 20+ tools including Roster-Generator with NHL API integration |
| [nhl94.com Editing Guides](https://nhl94.com/html/editing/edit_bin.php) | — | — | Complete hex offset documentation |

### ROM Specifications

| Property | Value |
|---|---|
| Platform | Sega Genesis / Mega Drive |
| CPU | Motorola 68000 |
| Size | ~1 MB (BIN) or ~640 KB (ISO/stripped) |
| Region | USA / Europe |
| Format | `.bin` (raw binary) or `.md` (Mega Drive) |
| Checksum | At `0x000FFACB` — must fix after editing (change `BOFC` to `4E75`) |

### Team & Player Layout

| Constraint | Value |
|---|---|
| NHL teams | 26 |
| All-Star teams | 2 (East, West) |
| Total teams | **28** |
| Players per team | ~**23–25** (variable) |
| Player name encoding | **ASCII** with length prefix |

### Player Record Structure

Same conceptual layout as SNES version, but at different offsets and with 68000 byte ordering:

| Field | Size | Details |
|-------|------|---------|
| Name length | 1 byte | Character count code (`0x0A`=6-7, `0x0C`=8-9, etc.) |
| Name | Variable | ASCII string |
| Jersey number | 1 byte | BCD format |
| Weight / Agility | 1 byte | High nibble: weight (0–F); Low nibble: agility (0–6) |
| Speed / Off. Awareness | 1 byte | High nibble: speed (0–6); Low nibble: off. awareness (0–6) |
| Def. Awareness / Shot Power | 1 byte | High nibble: def. awareness (0–6); Low nibble: shot power (0–6) |
| Checking / Handedness | 1 byte | High nibble: checking (0–6); Low nibble: even=L, odd=R |
| Stick Handling / Shot Accuracy | 1 byte | High nibble: stick handling (0–6); Low nibble: shot accuracy (0–6) |
| Endurance / Roughness | 1 byte | High nibble: endurance (0–6); Low nibble: roughness (0–6, hidden) |
| Pass Accuracy / Aggression | 1 byte | High nibble: pass accuracy (0–6); Low nibble: aggression (0–6) |

**Stats**: Same 0–6 scale as SNES, same display formula: `core_value * 18 + random(-9, +8)`, clamped 25–99.

### Key Offsets (BIN Format)

| Address | Content |
|---------|---------|
| `0x000FE18E` | Team ratings area |
| `0x000FFACB` | Checksum (fix: change `BOFC` → `4E75`) |

> **Note**: The Genesis version's offset tables are comprehensively documented at [nhl94.com/html/editing/edit_bin.php](https://nhl94.com/html/editing/edit_bin.php) and in the NOSE editor's source. Rather than duplicate all offsets here, the implementation should reference NOSE and the EA-NHL-Tools source code.

### Line Configuration

Same structure as SNES: 7 lines (SC1, SC2, CHK, PP1, PP2, PK1, PK2), 5 positions each (LD, RD, LW, C, RW) indexed by player number.

### Team Advantage Ratings

Same 0–7 scale for Offense/Defense, Home/Away, PP/PK.

### Checksum Fix

After any ROM modification, the internal checksum must be fixed:
- **Offset**: `0x000FFACB`
- **Fix**: Replace `BOFC` with `4E75` (NOP the checksum routine)
- This is a one-time patch — once applied, the game no longer validates the checksum

---

## 2. Architecture

### File Structure

```
src/services/nhl94_genesis_patcher/
├── __init__.py              # Public API exports
├── models.py                # Data classes (reuses NHL94 models where possible)
├── rom_reader.py            # Read and parse Genesis ROM data
├── rom_writer.py            # Write patched data + fix checksum
├── stat_mapper.py           # NHL API stats → 0-6 (shared logic with SNES)
└── patcher.py               # Orchestrator

src/ui/screens/
├── nhl94_genesis_patcher_screen.py  # Genesis patcher screen
```

### Shared Code with SNES Version

```
src/services/nhl_api/
├── __init__.py
├── client.py               # NHLApiClient (shared between SNES + Genesis)
├── models.py               # NHLPlayer, NHLPlayerStats (shared)
└── cache.py                # JSON caching logic (shared)
```

The NHL API client and data models are shared. Only ROM read/write differs between SNES and Genesis.

### Integration Points

- `sports_patcher_screen.py` — adds "NHL 94 - NHL Hockey '94 (Genesis)" to game list
- Shared `NHLApiClient` from `src/services/nhl_api/`
- Shared UI modals (roster preview, progress)

---

## 3. Service Layer

### 3.1 `rom_reader.py` — ROM Analysis

```python
class NHL94GenesisRomReader:
    CHECKSUM_OFFSET = 0x000FFACB

    def __init__(self, rom_path: str): ...
    def validate_rom(self) -> bool:
        """Verify this is an NHL 94 Genesis ROM."""
        ...
    def read_team(self, team_index: int) -> NHL94TeamRecord: ...
    def read_all_teams(self) -> list[NHL94TeamRecord]: ...
    def _parse_player_record(self, data: bytes, offset: int) -> tuple[NHL94PlayerRecord, int]: ...
```

### 3.2 `rom_writer.py` — ROM Patching

```python
class NHL94GenesisRomWriter:
    CHECKSUM_OFFSET = 0x000FFACB
    CHECKSUM_FIX = b'\x4E\x75'  # NOP the checksum routine

    def __init__(self, rom_path: str, output_path: str): ...
    def write_player_stats(self, team_index: int, player_index: int,
                           record: NHL94PlayerRecord): ...
    def write_team_roster(self, team_index: int, players: list[NHL94PlayerRecord]): ...
    def fix_checksum(self): ...
    def finalize(self): ...
```

### 3.3 `stat_mapper.py` — Attribute Mapping

```python
class NHL94GenesisStatMapper:
    """Same mapping logic as SNES version.

    Can inherit from or delegate to a shared base mapper.
    """
    TEAM_MAP: dict[str, int] = { ... }  # Same as SNES

    def map_player(self, player: NHLPlayer, stats: NHLPlayerStats | None) -> NHL94PlayerRecord: ...
    def map_weight(self, weight_pounds: int) -> int: ...
    def _select_roster(self, players: list[NHLPlayer]) -> list[NHLPlayer]: ...
```

### 3.4 `patcher.py` — Orchestrator

```python
class NHL94GenesisPatcher:
    def __init__(self, api_client: NHLApiClient): ...
    def analyze_rom(self, rom_path: str) -> NHL94RomInfo: ...
    def patch_rom(self, rom_path: str, output_path: str, season: str,
                  on_progress: Callable) -> str: ...
```

---

## 4. Stat Mapping Algorithm

Same algorithm as the [NHL 94 SNES patcher](nhl94_snes_patcher_implementation.md#5-stat-mapping-algorithm). Both versions use identical 0–6 stat scales, weight classes, and attribute definitions.

The [EA-NHL-Tools Roster-Generator](https://github.com/abdulahmad/EA-NHL-Tools) already implements a working mapping from the NHL API to Genesis NHL 94 attributes — this should be the primary reference for the implementation.

---

## 5. UI Screen

### `nhl94_genesis_patcher_screen.py`

Same simplified flow as SNES version — no league selection or slot mapping:

```
NHL 94 (Genesis) Roster Patcher
─────────────────────────────────
[1] Select Season     → Season picker (default: current)
[2] Fetch Rosters     → Fetch all 26 teams from NHL API
[3] Preview Rosters   → Roster Preview Modal (per-team player list)
[4] Select ROM        → File picker (BIN/MD)
[5] Patch ROM         → Patch Progress Modal
```

---

## 6. State Management

```python
@dataclass
class NHL94GenesisPatcherState:
    """State for the NHL 94 Genesis patcher."""

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

Add `nhl94_genesis_patcher: NHL94GenesisPatcherState` field to the main `AppState` dataclass.

---

## 7. Implementation Phases

### Phase 1: Shared NHL API Client
- [ ] Create `src/services/nhl_api/` shared module
- [ ] Implement `client.py` — fetch rosters, player stats, standings
- [ ] Implement `cache.py` — JSON caching with TTL
- [ ] Implement shared `models.py` — `NHLPlayer`, `NHLPlayerStats`
- [ ] Test: fetch all 32 current NHL rosters

### Phase 2: ROM Reader/Writer
- [ ] Implement `rom_reader.py` — parse Genesis ROM, read teams/players
- [ ] Implement `rom_writer.py` — write player stats, fix checksum
- [ ] Reference NOSE source and nhl94.com offset docs for all addresses
- [ ] Test: read all 28 teams, modify one player, write back, verify in emulator

### Phase 3: Stat Mapping
- [ ] Implement `stat_mapper.py` — NHL API stats → 0-6 scale
- [ ] Reference EA-NHL-Tools Roster-Generator mapping formulas
- [ ] Implement weight mapping, handedness, roster selection
- [ ] Test: map all teams, verify stat distribution

### Phase 4: Orchestrator + UI
- [ ] Implement `patcher.py` — full pipeline
- [ ] Add `NHL94GenesisPatcherState` to `state.py`
- [ ] Implement `nhl94_genesis_patcher_screen.py`
- [ ] Add NHL 94 Genesis to `sports_patcher_screen.py` game list

### Phase 5: Polish
- [ ] CSV export/import for manual editing
- [ ] Team advantage rating recalculation from standings
- [ ] Line configuration from real-world line combos

---

## 8. Testing Strategy

### Unit Tests
- `test_rom_reader.py`: Parse known ROM, verify all 28 teams
- `test_rom_writer.py`: Write stats + checksum fix, re-read, verify round-trip
- `test_stat_mapper.py`: Verify 0-6 mapping, weight conversion

### Integration Tests
- Full pipeline: fetch rosters → map stats → patch ROM → verify binary
- Compare output against a NOSE-edited ROM for sanity

### Manual Testing
- Load patched ROM in Kega Fusion, BlastEm, or RetroArch (Genesis Plus GX core)
- Verify: player names, stats, jersey numbers in roster screen
- Verify: gameplay with updated rosters
- Verify: no crashes through full game

---

## 9. Known Limitations

| Limitation | Mitigation |
|---|---|
| 26 team slots (modern NHL has 32) | 6 expansion teams excluded |
| Stats are 0–6 (very coarse) | Percentile-based mapping + EA-NHL-Tools reference |
| No portrait updates | Player photos stay as original |
| Checksum must be fixed | Automated one-time patch (NOP the routine) |
| Name length changes may need padding | Pad shorter names, truncate longer ones |
| Line combos are manual | Could auto-generate from real NHL data |

---

## 10. References & Resources

### Open-Source Tools
- [NOSE (NHL Old Skool Editor)](https://www.romhacking.net/utilities/290/) — Definitive Genesis NHL 94 editor
- [EA-NHL-Tools](https://github.com/abdulahmad/EA-NHL-Tools) — Roster-Generator with NHL API stat mapping (Python)
- [nhl94.com Editing Guides](https://nhl94.com/html/editing/edit_bin.php) — Complete hex offset documentation

### NHL API
- [NHL API Reference](https://github.com/Zmalski/NHL-API-Reference) — Community endpoint docs
- [nhl-api-py](https://pypi.org/project/nhl-api-py/) — Python wrapper

### Community
- [forum.nhl94.com](https://forum.nhl94.com/) — Central hub, annual roster updates
- [nhl94.com](https://nhl94.com/) — Guides, tools, online play
- [NHL 94: 2025 Edition](https://www.romhacking.net/hacks/8872/) — Latest annual update (reference for stat ratings)

### Annual Roster Hacks (Reference)
- NHL 94: 2025 Edition by Adam Catalyst — 800+ players rated
- These community-made annual editions serve as ground truth for validating our automated stat mapping
