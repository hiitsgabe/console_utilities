# Sports Game Roster Patcher — Implementation Plan

## Overview

A new **Sports Roster** feature for Console Utilities that allows users to patch sports game ROMs with real-world team and player data. The feature is gated behind a **Sports Roster** toggle in Settings. When enabled, a **"Sports Game Patcher"** option appears on the main menu, leading to a sub-menu of supported games.

### Supported Games

| Game | Platform | Status |
|---|---|---|
| **World Soccer Winning Eleven 2002** | PSX | First implementation |
| *(Future titles)* | — | Extensible architecture |

The first (and currently only) patcher targets **WE2002 (SLPM-87056)** — the most actively modded PSX Winning Eleven title, with existing open-source tooling as reference. The architecture is designed so additional sports game patchers can be added as sub-menu items in the future.

---

## Table of Contents

1. [Settings & Main Menu Integration](#1-settings--main-menu-integration)
2. [API Setup (API-Football)](#2-api-setup-api-football)
3. [WE2002 ROM Format Reference](#3-we2002-rom-format-reference)
4. [Architecture](#4-architecture)
5. [Service Layer](#5-service-layer)
6. [UI Screens & Flow](#6-ui-screens--flow)
7. [State Management](#7-state-management)
8. [Data Models](#8-data-models)
9. [Stat Mapping Algorithm](#9-stat-mapping-algorithm)
10. [TIM Graphics Generation](#10-tim-graphics-generation)
11. [AFS Archive Handling](#11-afs-archive-handling)
12. [ROM Binary Patching](#12-rom-binary-patching)
13. [Implementation Phases](#13-implementation-phases)
14. [Testing Strategy](#14-testing-strategy)
15. [Known Limitations](#15-known-limitations)
16. [References & Resources](#16-references--resources)

---

## 1. Settings & Main Menu Integration

### Settings Screen — Sports Roster Section

A new **"Sports Roster"** section in the Settings screen, following the same pattern as PortMaster/Internet Archive toggles:

```
--- SPORTS ROSTER ---
Enable Sports Roster     ON / OFF
API-Football Key          ••••••abc    (masked, tap to edit)
```

#### `settings.py` Additions

```python
# Settings dataclass additions
sports_roster_enabled: bool = False
api_football_key: str = ""
```

- **`sports_roster_enabled`**: Gates the "Sports Game Patcher" main menu item (same pattern as `portmaster_enabled`)
- **`api_football_key`**: User's API-Football key, stored in `config.json` alongside other credentials (e.g., ScreenScraper)

#### `settings_screen.py` Additions

```python
SPORTS_ROSTER_SECTION = [
    "--- SPORTS ROSTER ---",
    "Enable Sports Roster",
    "API-Football Key",
]
```

- Toggle action: `"Enable Sports Roster": "toggle_sports_roster_enabled"`
- API key action: `"API-Football Key": "edit_api_football_key"` — opens the existing `char_keyboard` organism for text entry
- The API key item is only shown when `sports_roster_enabled` is `True` (same conditional pattern as IA Login)
- API key display: masked with `••••••` + last 3 chars, or `"Not set"` if empty

### Main Menu — Sports Game Patcher

#### `systems_screen.py` Additions

Add to `_ALL_ROOT_ENTRIES`:

```python
("Sports Game Patcher", "sports_patcher"),
```

Conditional visibility in `_build_root_menu()`:

```python
if action == "sports_patcher":
    if not settings.get("sports_roster_enabled", False):
        continue
```

### Sports Game Patcher Sub-Menu

When the user selects "Sports Game Patcher" from the main menu, they see a list of supported games:

```
Sports Game Patcher
─────────────────────
▶ WE2002 - Winning Eleven 2002 (PS1)
  (future titles here)
```

Selecting **WE2002** enters the WE Patcher screen described in [Section 6](#6-ui-screens--flow).

This sub-menu is a simple list screen (`sports_patcher_screen.py`) that routes to game-specific patcher screens. As more games are supported, they are added here.

---

## 2. API Setup (API-Football)

### Getting an API Key (Free Tier)

1. Go to [https://www.api-football.com](https://www.api-football.com)
2. Click **"Get Free API Key"** — no credit card required
3. Sign up with email
4. Your API key will be displayed on the dashboard
5. Free tier: **100 requests/day**, all endpoints unlocked, 1,200+ leagues

Alternative: Register via [RapidAPI](https://rapidapi.com/api-sports/api/api-football) (same backend).

### Key Endpoints

| Endpoint | Purpose | Example |
|---|---|---|
| `GET /leagues` | List all available leagues | `?country=England&season=2025` |
| `GET /teams` | Get teams in a league | `?league=39&season=2025` (39 = Premier League) |
| `GET /players/squads` | Get current squad for a team | `?team=33` (Manchester United) |
| `GET /players` | Get detailed player stats | `?team=33&season=2025` |

### Rate Limiting Strategy

With 100 requests/day on the free tier, we need to be efficient:

- **1 request**: Fetch leagues list (cache indefinitely)
- **1 request**: Fetch teams for selected league (~20 teams)
- **20 requests**: Fetch squad for each team (1 per team)
- **20 requests**: Fetch detailed player stats per team (optional, for better stat mapping)
- **Total per league**: ~22-42 requests (well within 100/day)

All responses must be cached locally as JSON files to avoid repeat fetches.

### API Authentication

```
Headers:
  x-apisports-key: YOUR_API_KEY
  # OR via RapidAPI:
  x-rapidapi-key: YOUR_API_KEY
  x-rapidapi-host: api-football-v1.p.rapidapi.com
```

The API key is stored in `config.json` as `api_football_key`, configured via the Sports Roster section in Settings (see [Section 1](#1-settings--main-menu-integration)).

---

## 3. WE2002 ROM Format Reference

### Source of Truth

The primary reference for binary offsets is the open-source **WE2002 Team Editor v0.99** by Obocaman:
- **Repository**: [github.com/thyddralisk/WE2002-editor-2.0](https://github.com/thyddralisk/WE2002-editor-2.0)
- **Language**: C++ (read the source to extract byte offsets, field sizes, encoding)

### ROM Structure Overview

```
WE2002 BIN/ISO (Mode 2/2352)
├── SLPM_870.56          # Main executable (team/player data embedded)
├── 0TEXT.AFS            # Text assets archive
├── J_TEXT.AFS           # Japanese text archive
├── 0_SOUND.AFS          # Sound archive (callnames as VAG in RA containers)
├── [graphic archives]   # Kit textures, flags, stadiums (TIM/TIM2 format)
└── [other game data]
```

### Player Record Structure

Each player record contains (approximate — verify against WE2002 editor source):

| Field | Size | Description |
|---|---|---|
| Last Name | 8-12 bytes | Fixed-length, ASCII or custom charset |
| First Name | 8 bytes | Fixed-length |
| Position | 1 byte | GK=0, DF=1, MF=2, FW=3 (verify values) |
| Shirt Number | 1 byte | 1-99 |
| Nationality | 1 byte | Country code index |
| Age / DOB | 1-2 bytes | Age or birth year offset |
| **Attributes** (15 total, 1 byte each on 1-9 scale): |
| Offensive | 1 byte | 1-9 |
| Defensive | 1 byte | 1-9 |
| Body Balance | 1 byte | 1-9 |
| Stamina | 1 byte | 1-9 |
| Speed | 1 byte | 1-9 |
| Acceleration | 1 byte | 1-9 |
| Pass Accuracy | 1 byte | 1-9 |
| Shoot Power | 1 byte | 1-9 |
| Shoot Accuracy | 1 byte | 1-9 |
| Jump Power | 1 byte | 1-9 |
| Heading | 1 byte | 1-9 |
| Technique | 1 byte | 1-9 |
| Dribble | 1 byte | 1-9 |
| Curve | 1 byte | 1-9 |
| Aggression | 1 byte | 1-9 |
| Special Traits | 1-2 bytes | Binary flags (e.g., dribbler, dead ball specialist) |

### Team Record Structure

| Field | Size | Description |
|---|---|---|
| Team Name | 16-24 bytes | Appears in multiple locations (menu, match, etc.) |
| Short Name | 3-4 bytes | Abbreviation |
| Kit Colors (Home) | 6 bytes | RGB for shirt, shorts, socks |
| Kit Colors (Away) | 6 bytes | RGB for shirt, shorts, socks |
| Kit Colors (GK) | 6 bytes | RGB for GK kit |
| Flag/Emblem Pointer | 2-4 bytes | Offset to TIM graphic in archive |
| Formation | Variable | Default tactical formation data |
| Player Records | 22 × player_size | Fixed 22 players per team |

### Constraints

| Constraint | Value |
|---|---|
| Players per squad | **22** (fixed, cannot be changed) |
| Club team slots | ~24 per league mode (verify in editor source) |
| National team slots | ~56 |
| Stat range | **1-9** per attribute |
| Name encoding | ASCII-compatible (Western versions), Shift-JIS (Japanese) |
| Player name max length | ~8-12 characters (last name), ~8 characters (first name) |
| Total teams | Hardcoded — cannot add new slots, only overwrite existing |

---

## 4. Architecture

### File Structure

```
src/services/we_patcher/
├── __init__.py              # Public API exports
├── models.py                # Data classes (League, Team, Player, WERecord, etc.)
├── api_football.py          # API-Football client with caching
├── stat_mapper.py           # Real stats → WE2002 1-9 scale algorithm
├── csv_handler.py           # CSV export/import of roster data
├── rom_reader.py            # Read and parse WE2002 ROM binary data
├── rom_writer.py            # Write patched data back to ROM binary
├── tim_generator.py         # Convert images → PSX TIM format
├── afs_handler.py           # Read/write Konami AFS archive files
└── patcher.py               # Orchestrator: ties all steps together

src/ui/screens/
├── sports_patcher_screen.py # Sports Game Patcher sub-menu (game list)
├── we_patcher_screen.py     # WE2002-specific patcher screen

src/ui/screens/modals/
├── league_browser_modal.py  # Browse/search leagues
├── roster_preview_modal.py  # Preview team rosters before patching
├── slot_mapping_modal.py    # Map real teams → WE2002 team slots
└── patch_progress_modal.py  # Patching progress with per-team status
```

### Integration Points

```
app.py
├── state.py              ← Add WePatcherState
├── screen_manager.py     ← Register sports_patcher_screen + we_patcher_screen
├── settings.py           ← Add sports_roster_enabled + api_football_key
└── constants.py          ← Add WE patcher cache paths
```

---

## 5. Service Layer

### 5.1 `api_football.py` — API Client

```python
class ApiFootballClient:
    """Client for API-Football with local JSON caching."""

    BASE_URL = "https://v3.football.api-sports.io"

    def __init__(self, api_key: str, cache_dir: str):
        ...

    def get_leagues(self, country: str = None, season: int = None) -> list[League]:
        """Fetch available leagues, optionally filtered by country/season."""
        # GET /leagues
        # Cache: leagues_{country}_{season}.json
        ...

    def get_teams(self, league_id: int, season: int) -> list[Team]:
        """Fetch all teams in a league for a given season."""
        # GET /teams?league={id}&season={season}
        # Cache: teams_{league_id}_{season}.json
        ...

    def get_squad(self, team_id: int) -> list[Player]:
        """Fetch current squad/roster for a team."""
        # GET /players/squads?team={team_id}
        # Cache: squad_{team_id}.json
        ...

    def get_player_stats(self, team_id: int, season: int) -> list[PlayerStats]:
        """Fetch detailed player statistics (optional, for better stat mapping)."""
        # GET /players?team={team_id}&season={season}
        # Cache: players_{team_id}_{season}.json
        ...

    def get_team_logo_url(self, team_id: int) -> str:
        """Get team logo image URL from API."""
        ...

    def _request(self, endpoint: str, params: dict) -> dict:
        """Make authenticated request with rate limiting."""
        ...

    def _load_cache(self, cache_key: str) -> dict | None:
        """Load cached API response if fresh enough."""
        ...

    def _save_cache(self, cache_key: str, data: dict):
        """Save API response to local cache."""
        ...
```

### 5.2 `stat_mapper.py` — Attribute Mapping

```python
class StatMapper:
    """Maps real-world player stats to WE2002's 1-9 attribute scale."""

    def map_player(self, player: Player, stats: PlayerStats | None) -> WEPlayerAttributes:
        """Convert a real player's stats to WE2002 format."""
        ...

    def _map_offensive(self, stats: PlayerStats) -> int:
        """Map goals, assists, key passes → Offensive (1-9)."""
        ...

    def _map_defensive(self, stats: PlayerStats) -> int:
        """Map tackles, interceptions, blocks → Defensive (1-9)."""
        ...

    def _map_speed(self, player: Player) -> int:
        """Estimate speed from position and age heuristics."""
        ...

    def _select_best_22(self, squad: list[Player]) -> list[Player]:
        """Select the best 22 players from a full squad."""
        # Priority: 3 GK, 7 DF, 6 MF, 6 FW (adjustable)
        ...

    def _truncate_name(self, name: str, max_bytes: int) -> str:
        """Smart name truncation: abbreviate first, then truncate."""
        ...
```

#### Stat Mapping Strategy

The API-Football `/players` endpoint provides per-season stats. The mapping algorithm:

1. **Collect league-wide stats** for normalization (e.g., max goals, max tackles across all players)
2. **Percentile ranking**: Rank each player within the league for each stat category
3. **Map percentile → 1-9**:
   - Top 5% → 9
   - Top 15% → 8
   - Top 30% → 7
   - Top 50% → 6
   - Top 65% → 5
   - Top 80% → 4
   - Top 90% → 3
   - Top 97% → 2
   - Bottom 3% → 1
4. **Position-based adjustments**: Goalkeepers get defensive/jump bonuses; strikers get offensive/shooting bonuses
5. **Fallback heuristics**: If detailed stats unavailable (free tier limit), use position + age to estimate attributes

| WE2002 Attribute | API-Football Stats Used |
|---|---|
| Offensive | goals, assists, key_passes, shots.on |
| Defensive | tackles.total, interceptions, blocks |
| Body Balance | duels.won / duels.total, fouls.drawn |
| Stamina | games.minutes (avg), substitutes.in frequency |
| Speed | Position heuristic + age curve |
| Acceleration | Position heuristic + age curve |
| Pass Accuracy | passes.accuracy, passes.total |
| Shoot Power | shots.total, goals (long range if available) |
| Shoot Accuracy | goals / shots.total |
| Jump Power | Position + height (if available) |
| Heading | Position + aerial duels (if available) |
| Technique | dribbles.success / dribbles.attempts |
| Dribble | dribbles.success, dribbles.attempts |
| Curve | Position heuristic (wingers/playmakers higher) |
| Aggression | fouls.committed, cards.yellow, cards.red |

### 5.3 `csv_handler.py` — CSV Export/Import

```python
class CsvHandler:
    """Export/import roster data as CSV for manual editing."""

    def export_league(self, league: League, teams: list[TeamRoster], path: str):
        """Export full league data to CSV."""
        # Columns: team_name, player_name, position, number, off, def, bod,
        #          sta, spe, acl, pas, spw, sac, jmp, hea, tec, dri, cur, agg
        ...

    def import_league(self, path: str) -> list[TeamRoster]:
        """Import league data from CSV (allows manual stat tweaks)."""
        ...
```

CSV acts as an intermediate format: users can fetch from API, export CSV, manually tweak stats if desired, then import and patch.

### 5.4 `rom_reader.py` — ROM Analysis

```python
class RomReader:
    """Reads and parses WE2002 ROM binary data."""

    def __init__(self, rom_path: str):
        ...

    def validate_rom(self) -> bool:
        """Check if the ROM is a valid WE2002 image (magic bytes, size check)."""
        ...

    def read_teams(self) -> list[WETeamRecord]:
        """Read all team records from the ROM."""
        ...

    def read_players(self, team_index: int) -> list[WEPlayerRecord]:
        """Read all 22 player records for a team."""
        ...

    def read_team_slots(self) -> list[WETeamSlot]:
        """List all available team slots with current names."""
        # Used for the slot mapping UI
        ...

    def extract_flag(self, team_index: int) -> bytes:
        """Extract a team's flag/emblem graphic data."""
        ...
```

### 5.5 `rom_writer.py` — ROM Patching

```python
class RomWriter:
    """Writes patched data to WE2002 ROM binary."""

    def __init__(self, rom_path: str, output_path: str):
        # Always writes to a NEW file (never overwrites original)
        ...

    def write_team(self, slot_index: int, team: WETeamRecord):
        """Write team name, abbreviation, kit colors to a slot."""
        ...

    def write_players(self, slot_index: int, players: list[WEPlayerRecord]):
        """Write all 22 player records for a team slot."""
        ...

    def write_flag(self, slot_index: int, tim_data: bytes):
        """Write team flag/emblem TIM graphic."""
        ...

    def finalize(self):
        """Regenerate EDC/ECC checksums for the patched BIN."""
        # Critical: PSX requires valid checksums or the disc won't boot
        ...
```

### 5.6 `tim_generator.py` — PSX Graphics

```python
class TimGenerator:
    """Converts images to PSX TIM format for team flags/emblems."""

    def png_to_tim(self, png_path: str, width: int, height: int,
                   bpp: int = 4) -> bytes:
        """Convert a PNG image to PSX TIM format."""
        # 1. Load PNG with PIL/Pillow
        # 2. Quantize to 16 colors (4bpp) or 256 colors (8bpp)
        # 3. Build CLUT (Color Look-Up Table) in 5-5-5 BGR format
        # 4. Pack pixel data
        # 5. Assemble TIM header + CLUT + pixel data
        ...

    def download_and_convert_flag(self, logo_url: str, output_size: tuple[int, int]) -> bytes:
        """Download team logo from API and convert to TIM."""
        ...

    def _quantize_image(self, img, num_colors: int):
        """Reduce image to N colors using median cut."""
        ...

    def _rgb_to_bgr555(self, r: int, g: int, b: int) -> int:
        """Convert 8-bit RGB to 15-bit BGR (PSX color format)."""
        # B(5) | G(5) | R(5) | STP(1)
        return ((b >> 3) << 10) | ((g >> 3) << 5) | (r >> 3)

    def _build_tim_header(self, bpp: int, has_clut: bool) -> bytes:
        """Build the 8-byte TIM file header."""
        # Magic: 0x10, 0x00, 0x00, 0x00
        # Flags: bpp mode + CLUT flag
        ...
```

#### TIM Format Specification

```
TIM File Layout:
┌──────────────────────┐
│ Header (8 bytes)     │  Magic (4B) + Flags (4B)
├──────────────────────┤
│ CLUT Block           │  Length (4B) + X,Y (4B) + W,H (4B) + Color Data
├──────────────────────┤
│ Pixel Block          │  Length (4B) + X,Y (4B) + W,H (4B) + Pixel Data
└──────────────────────┘

Color Format (15-bit BGR):
Bit: 15    14-10    9-5    4-0
     STP   Blue     Green  Red
     (1)   (5)      (5)    (5)
```

### 5.7 `afs_handler.py` — AFS Archives

```python
class AfsHandler:
    """Read/write Konami AFS archive files used in WE2002."""

    def __init__(self, afs_path: str):
        ...

    def list_entries(self) -> list[AfsEntry]:
        """List all files in the AFS archive with offsets and sizes."""
        ...

    def extract_entry(self, index: int) -> bytes:
        """Extract a single file from the archive."""
        ...

    def replace_entry(self, index: int, data: bytes):
        """Replace a file in the archive (must not exceed original size)."""
        ...

    def rebuild(self, output_path: str):
        """Rebuild entire AFS archive (allows size changes)."""
        ...
```

#### AFS Archive Format

```
AFS Header:
┌──────────────────────┐
│ "AFS\0" (4 bytes)    │  Magic identifier
├──────────────────────┤
│ File Count (4 bytes)  │  Little-endian uint32
├──────────────────────┤
│ TOC Entry 0          │  Offset (4B) + Size (4B)
│ TOC Entry 1          │  Offset (4B) + Size (4B)
│ ...                  │
│ TOC Entry N          │  Offset (4B) + Size (4B)
├──────────────────────┤
│ File Data 0          │  Raw file data (padded to 2048-byte boundary)
│ File Data 1          │
│ ...                  │
└──────────────────────┘
```

### 5.8 `patcher.py` — Orchestrator

```python
class WePatcher:
    """Orchestrates the full patching pipeline."""

    def __init__(self, api_key: str, cache_dir: str):
        self.api = ApiFootballClient(api_key, cache_dir)
        self.mapper = StatMapper()
        self.csv = CsvHandler()
        self.tim = TimGenerator()
        ...

    def fetch_league(self, league_id: int, season: int,
                     on_progress: Callable) -> LeagueData:
        """Step 1: Fetch all teams and rosters from API."""
        ...

    def generate_csv(self, league_data: LeagueData, output_dir: str) -> str:
        """Step 2: Export fetched data as CSV."""
        ...

    def analyze_rom(self, rom_path: str) -> RomInfo:
        """Step 3: Read ROM and list available team slots."""
        ...

    def create_slot_mapping(self, league_data: LeagueData,
                            rom_info: RomInfo) -> list[SlotMapping]:
        """Step 4: Auto-map league teams to ROM slots (user can override)."""
        ...

    def patch_rom(self, rom_path: str, output_path: str,
                  league_data: LeagueData, slot_mapping: list[SlotMapping],
                  on_progress: Callable) -> str:
        """Step 5: Apply all patches and write output ROM."""
        # 1. Copy original ROM to output path
        # 2. For each team mapping:
        #    a. Write team name/abbreviation
        #    b. Write 22 player records (names, stats, positions)
        #    c. Write kit colors
        #    d. Generate and write flag TIM
        # 3. Regenerate EDC/ECC checksums
        # 4. Return output path
        ...
```

---

## 6. UI Screens & Flow

### Navigation Flow

```
Main Menu (Systems Screen)
  └── "Sports Game Patcher" (shown when sports_roster_enabled = true)
        └── Sports Patcher Screen (game list)
              └── "WE2002 - Winning Eleven 2002 (PS1)"
                    └── WE Patcher Screen
                          ├── [1] Select League    → League Browser Modal
                          │     └── Search/browse 1200+ leagues
                          │     └── Select season
                          │     └── Fetches teams + squads (with progress)
                          ├── [2] Preview Rosters  → Roster Preview Modal
                          │     └── List of teams
                          │     └── Tap team → see 22 players with mapped stats
                          │     └── Option to export CSV
                          ├── [3] Select ROM       → File picker (BIN/ISO)
                          ├── [4] Map Team Slots   → Slot Mapping Modal
                          │     └── Left: Real teams | Right: WE2002 slots
                          │     └── Auto-mapping with manual override
                          └── [5] Patch ROM        → Patch Progress Modal
                                └── Per-team progress bars
                                └── "Done! ROM saved to: /path/to/patched.bin"
```

### Screen Descriptions

#### `sports_patcher_screen.py` — Game Selection (List View)

A simple list screen showing all supported sports game patchers:
- Currently one item: "WE2002 - Winning Eleven 2002 (PS1)"
- Future games are added here as new list items
- If API key is not set, show a warning hint at the bottom: "Set your API-Football key in Settings"

#### `we_patcher_screen.py` — WE2002 Patcher Screen (List View)

A step-by-step list menu matching the app's existing style:
- 5 menu items as listed above (API key is now managed in Settings, not here)
- Status indicators showing completion state (checkmark when step is done)
- Steps must be completed in order (1 requires API key in settings, 2 requires 1, etc.)
- If API key is missing, step 1 is disabled with hint to configure in Settings

#### `league_browser_modal.py` — League Selection

- Search bar at top (reuse existing `char_keyboard` organism)
- List of leagues grouped by country
- Each item shows: league name, country flag, number of teams
- On select: choose season (default: current), then auto-fetch teams/squads

#### `roster_preview_modal.py` — Team/Player Preview

- Grid or list of teams in the selected league
- Tap a team → see 22 players with:
  - Name, position, jersey number
  - Mapped stats (all 15 attributes on 1-9 scale)
  - Visual stat bars
- "Export CSV" button at the bottom

#### `slot_mapping_modal.py` — Team Slot Assignment

- Two-column layout:
  - Left: Real teams from selected league
  - Right: Available WE2002 team slots (showing current names)
- Auto-map button: match by name similarity or sequential assignment
- Manual override: select a real team, then select a WE2002 slot
- Unmapped teams shown in red

#### `patch_progress_modal.py` — Patching Progress

- Overall progress bar at top
- Per-team status list:
  - Team name → "Patching players..." / "Writing flag..." / "Done"
- Final summary: output file path, teams patched, total players

---

## 7. State Management

Add to `state.py`:

```python
@dataclass
class WePatcherState:
    """State for the WE Patcher feature."""

    # NOTE: API key is stored in Settings (api_football_key), not here.

    # League selection
    selected_league: League | None = None
    selected_season: int = 2025
    available_leagues: list[League] = field(default_factory=list)
    league_search_query: str = ""

    # Fetched data
    league_data: LeagueData | None = None
    fetch_progress: float = 0.0  # 0.0 - 1.0
    fetch_status: str = ""       # "Fetching Manchester United squad..."
    is_fetching: bool = False

    # ROM
    rom_path: str = ""
    rom_info: RomInfo | None = None
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
    active_modal: str | None = None  # "league_browser", "roster_preview", etc.
```

Add `we_patcher: WePatcherState` field to the main `AppState` dataclass.

---

## 8. Data Models

```python
# src/services/we_patcher/models.py

@dataclass
class League:
    id: int
    name: str
    country: str
    country_code: str
    logo_url: str
    season: int
    teams_count: int

@dataclass
class Player:
    id: int
    name: str
    first_name: str
    last_name: str
    age: int
    nationality: str
    position: str        # "Goalkeeper", "Defender", "Midfielder", "Attacker"
    number: int | None
    photo_url: str

@dataclass
class PlayerStats:
    """Detailed per-season stats from API-Football."""
    player_id: int
    appearances: int
    minutes: int
    goals: int
    assists: int
    shots_total: int
    shots_on: int
    passes_total: int
    passes_accuracy: float  # percentage
    tackles_total: int
    interceptions: int
    blocks: int
    duels_total: int
    duels_won: int
    dribbles_attempts: int
    dribbles_success: int
    fouls_committed: int
    fouls_drawn: int
    cards_yellow: int
    cards_red: int
    rating: float | None  # API-Football average rating

@dataclass
class Team:
    id: int
    name: str
    short_name: str
    code: str           # 3-letter abbreviation
    logo_url: str
    country: str

@dataclass
class TeamRoster:
    team: Team
    players: list[Player]
    player_stats: dict[int, PlayerStats]  # player_id → stats

@dataclass
class LeagueData:
    league: League
    teams: list[TeamRoster]

@dataclass
class WEPlayerAttributes:
    """WE2002 player attributes on 1-9 scale."""
    offensive: int
    defensive: int
    body_balance: int
    stamina: int
    speed: int
    acceleration: int
    pass_accuracy: int
    shoot_power: int
    shoot_accuracy: int
    jump_power: int
    heading: int
    technique: int
    dribble: int
    curve: int
    aggression: int

@dataclass
class WEPlayerRecord:
    """Complete player record ready to write to ROM."""
    last_name: str       # Truncated to max ROM length
    first_name: str      # Truncated to max ROM length
    position: int        # 0=GK, 1=DF, 2=MF, 3=FW
    shirt_number: int
    attributes: WEPlayerAttributes

@dataclass
class WETeamRecord:
    """Complete team record ready to write to ROM."""
    name: str
    short_name: str
    kit_home: tuple[int, int, int]    # RGB
    kit_away: tuple[int, int, int]    # RGB
    kit_gk: tuple[int, int, int]      # RGB
    players: list[WEPlayerRecord]     # Exactly 22
    flag_tim: bytes | None            # TIM graphic data

@dataclass
class WETeamSlot:
    """Represents an existing team slot in the ROM."""
    index: int
    current_name: str
    league_group: str  # "League A", "League B", etc.

@dataclass
class SlotMapping:
    """Maps a real team to a WE2002 ROM slot."""
    real_team: Team
    slot_index: int
    slot_name: str

@dataclass
class RomInfo:
    """Information about a loaded WE2002 ROM."""
    path: str
    size: int
    version: str          # Detected WE2002 variant
    team_slots: list[WETeamSlot]
    is_valid: bool
```

---

## 9. Stat Mapping Algorithm

### Overview

The stat mapper converts real-world API-Football statistics to WE2002's 15 attributes, each on a 1-9 scale. The approach uses **league-wide percentile ranking** for fairness.

### Algorithm

```
1. Collect all player stats for the entire league
2. For each stat category, compute league-wide percentiles
3. Map each player's percentile to 1-9 using thresholds
4. Apply position-based adjustments
5. Clamp all values to [1, 9]
```

### Percentile → Rating Mapping

| Percentile Range | WE2002 Rating | Description |
|---|---|---|
| 95-100% | 9 | World class |
| 85-95% | 8 | Excellent |
| 70-85% | 7 | Very good |
| 50-70% | 6 | Good |
| 35-50% | 5 | Average |
| 20-35% | 4 | Below average |
| 10-20% | 3 | Weak |
| 3-10% | 2 | Very weak |
| 0-3% | 1 | Poor |

### Position-Based Adjustments

Since some stats are not meaningful for certain positions:

- **Goalkeepers**: Defensive base +2, Jump +2, Offensive max 4, Shooting max 3
- **Center Backs**: Defensive +1, Heading +1, Speed -1 (unless fast)
- **Full Backs**: Speed +1, Stamina +1
- **Midfielders**: Pass Accuracy +1, Technique +1, Stamina +1
- **Wingers**: Speed +1, Dribble +1, Acceleration +1
- **Strikers**: Offensive +1, Shoot Accuracy +1, Shoot Power +1

### Fallback (No Detailed Stats)

When the `/players` endpoint isn't used (to save API calls), use heuristics:

```
Position-based defaults:
  GK: Off=2, Def=7, Bal=6, Sta=6, Spe=4, Acl=4, Pas=5, SPw=3, SAc=2, Jmp=7, Hea=5, Tec=4, Dri=3, Cur=3, Agg=4
  DF: Off=3, Def=7, Bal=6, Sta=6, Spe=5, Acl=5, Pas=5, SPw=4, SAc=3, Jmp=6, Hea=6, Tec=4, Dri=3, Cur=3, Agg=6
  MF: Off=5, Def=5, Bal=5, Sta=7, Spe=5, Acl=5, Pas=7, SPw=5, SAc=5, Jmp=5, Hea=5, Tec=6, Dri=6, Cur=5, Agg=5
  FW: Off=7, Def=3, Bal=5, Sta=5, Spe=6, Acl=6, Pas=5, SPw=7, SAc=7, Jmp=5, Hea=5, Tec=6, Dri=6, Cur=5, Agg=5

Age modifiers:
  < 23: Speed +1, Acceleration +1, Stamina +1, Technique -1
  23-30: No adjustment (prime)
  31-33: Speed -1, Acceleration -1, Stamina -1, Technique +1
  > 33: Speed -2, Stamina -2, Technique +1
```

---

## 10. TIM Graphics Generation

### Pipeline

```
Team Logo URL (API-Football)
    ↓
Download PNG (via requests)
    ↓
Resize to target dimensions (e.g., 32x32 or 64x64)
    ↓
Quantize to 16 colors (4bpp TIM)
    ↓
Build CLUT (16 × 2 bytes = 32 bytes)
    ↓
Pack pixel data (2 pixels per byte for 4bpp)
    ↓
Assemble TIM file (header + CLUT block + pixel block)
    ↓
bytes ready to write to ROM
```

### Dependencies

- **Pillow (PIL)**: Image loading, resizing, and color quantization
  - Add `Pillow>=9.0.0` to `pyproject.toml` dependencies

### Flag Dimensions

The exact flag/emblem dimensions in WE2002 need to be verified from the ROM data. Typical PSX game flags are:
- 32×32 pixels (4bpp = 512 bytes pixel data + 32 bytes CLUT)
- 64×64 pixels (4bpp = 2048 bytes pixel data + 32 bytes CLUT)

The WE2002 editor source code will reveal the exact size.

---

## 11. AFS Archive Handling

### Read Process

1. Read 4-byte magic "AFS\0"
2. Read 4-byte file count (uint32 LE)
3. Read TOC: `file_count` entries of (offset: uint32, size: uint32)
4. For each entry, seek to offset and read `size` bytes

### Write Process (Replace Entry)

1. Read existing AFS structure
2. Verify replacement data size <= original entry size
3. Seek to entry offset, write new data
4. If smaller, pad with zeros to original size
5. If larger, need full archive rebuild (recompute all offsets)

### Full Rebuild (When Sizes Change)

1. Recompute all offsets based on new sizes
2. Pad each entry to 2048-byte boundary (CD sector alignment)
3. Write new header + TOC + all entries sequentially
4. Update the AFS file in the ROM image

---

## 12. ROM Binary Patching

### Workflow

```
1. COPY original ROM to output path (never modify original)
2. Open output ROM in binary read/write mode
3. For each team slot to patch:
   a. Seek to team name offset → write new name
   b. Seek to player records offset → write 22 player records
   c. Seek to kit color offset → write RGB values
4. For graphics:
   a. Extract AFS archive containing flags
   b. Replace flag entries with new TIM data
   c. If sizes match: in-place replace in BIN
   d. If sizes differ: rebuild AFS, then replace in BIN
5. Regenerate EDC/ECC checksums
6. Verify patched ROM loads in emulator (manual step)
```

### EDC/ECC Regeneration

PSX BIN files use Mode 2/Form 1 sectors (2352 bytes each) which include Error Detection Code (EDC) and Error Correction Code (ECC). After modifying any data:

- Use the Python equivalent of the `edcre` tool
- Or call `edcre` as a subprocess if installed
- Or implement EDC/ECC calculation in Python (the algorithm is well-documented)

Without valid checksums, the game will crash on real hardware (emulators are more forgiving).

---

## 13. Implementation Phases

### Phase 1: Settings & Menu Integration
- [ ] Add `sports_roster_enabled` and `api_football_key` to `Settings` dataclass
- [ ] Add "Sports Roster" section to `settings_screen.py` with toggle + API key entry
- [ ] Add "Sports Game Patcher" to `_ALL_ROOT_ENTRIES` with conditional visibility
- [ ] Implement `sports_patcher_screen.py` (game list sub-menu)
- [ ] Register screens in `screen_manager.py`
- [ ] Test: toggle setting on/off, verify main menu item appears/disappears

### Phase 2: Foundation (API + Data Models)
- [ ] Create `src/services/we_patcher/` module structure
- [ ] Implement `models.py` with all data classes
- [ ] Implement `api_football.py` with caching
- [ ] Add cache directory to `constants.py`
- [ ] Test: fetch leagues, teams, squads from API

### Phase 3: Stat Mapping + CSV
- [ ] Implement `stat_mapper.py` with percentile-based mapping
- [ ] Implement position-based adjustments and fallback heuristics
- [ ] Implement `csv_handler.py` for export/import
- [ ] Implement `_select_best_22()` squad selection
- [ ] Implement `_truncate_name()` smart name truncation
- [ ] Test: map a full Premier League season, verify stat distribution

### Phase 4: ROM Format Reverse Engineering
- [ ] Clone and study [WE2002-editor-2.0](https://github.com/thyddralisk/WE2002-editor-2.0) source
- [ ] Document all byte offsets for team names, player records, kit colors
- [ ] Implement `rom_reader.py` — read and parse existing ROM data
- [ ] Implement `rom_writer.py` — write team and player data
- [ ] Test: read a team from ROM, modify one player name, write back, verify in emulator

### Phase 5: Graphics (TIM + AFS)
- [ ] Add `Pillow` dependency
- [ ] Implement `tim_generator.py` — PNG to TIM conversion
- [ ] Implement `afs_handler.py` — AFS archive read/write
- [ ] Determine exact flag dimensions from ROM analysis
- [ ] Test: replace one team flag, verify in emulator

### Phase 6: Orchestrator + Patcher
- [ ] Implement `patcher.py` — full pipeline orchestration
- [ ] Implement EDC/ECC regeneration (Python or subprocess)
- [ ] Implement slot auto-mapping logic
- [ ] Test: patch entire league (20 teams), verify in emulator

### Phase 7: UI Integration
- [ ] Add `WePatcherState` to `state.py`
- [ ] Implement `we_patcher_screen.py` (WE2002 patcher steps)
- [ ] Implement `league_browser_modal.py`
- [ ] Implement `roster_preview_modal.py`
- [ ] Implement `slot_mapping_modal.py`
- [ ] Implement `patch_progress_modal.py`

### Phase 8: Polish & Edge Cases
- [ ] Handle API rate limit errors gracefully
- [ ] Handle malformed/unsupported ROM variants
- [ ] Add option to import custom CSV (skip API entirely)
- [ ] Add preset stat profiles for popular leagues
- [ ] Add undo/reset for patched ROMs

---

## 14. Testing Strategy

### Unit Tests
- `test_stat_mapper.py`: Verify percentile mapping produces valid 1-9 values
- `test_csv_handler.py`: Round-trip export/import preserves data
- `test_tim_generator.py`: Generated TIM files have correct header, CLUT, pixel layout
- `test_afs_handler.py`: AFS read/write preserves archive structure
- `test_name_truncation.py`: Names are truncated intelligently

### Integration Tests
- Fetch real league data from API (with cached responses)
- Read a known WE2002 ROM dump and verify parsed team names match expected
- Write a patched ROM and binary-diff against expected output

### Manual Testing
- Load patched ROM in ePSXe, DuckStation, or RetroArch (Beetle PSX)
- Verify: team names display correctly in menus
- Verify: player names and stats are correct in match
- Verify: kit colors render properly
- Verify: team flags display correctly
- Verify: game plays without crashes

---

## 15. Known Limitations

| Limitation | Mitigation |
|---|---|
| 22 players per team (fixed) | Smart selection algorithm picks best 22 from full squad |
| ~24 team slots per league mode | Can only patch teams that fit in available slots |
| Player name length limit (~8-12 chars) | Smart abbreviation: "Fernandez" → "Fernandez", "Lewandowski" → "Lewandwski" |
| Stats are 1-9 only (coarse) | Percentile-based mapping maximizes differentiation |
| API free tier: 100 req/day | Cache all responses; one league per day is sufficient |
| No new team slots can be added | Work within existing ROM structure |
| Callname audio won't match | Out of scope — would require VAG audio generation |
| Some flag palette pairs are linked | May need to avoid certain slot combinations |
| EDC/ECC required for real hardware | Implement or use subprocess; emulators work without it |

---

## 16. References & Resources

### APIs
- [API-Football Documentation](https://www.api-football.com/documentation-v3)
- [API-Football Players/Squads Endpoint](https://www.api-football.com/news/post/football-players-squads)
- [API-Football Getting Teams from a League](https://www.api-football.com/news/post/how-to-get-all-teams-and-players-from-a-league-id)

### WE2002 Modding Tools
- [WE2002 Team Editor 2.0 (C++ source)](https://github.com/thyddralisk/WE2002-editor-2.0) — **Primary byte offset reference**
- [Winning Eleven Memcard Editor (Python)](https://github.com/Diego-Pino/Winning-Eleven-Memcard-Editor)
- [WE2002 Tools Page](https://winningeleven-games.com)

### PSX Technical
- [PSX TIM Format Spec](https://qhimm-modding.fandom.com/wiki/PSX/TIM_file)
- [psximager (disc image tools)](https://github.com/cebix/psximager)
- [mkpsxiso (ISO builder)](https://github.com/Lameguy64/mkpsxiso)
- [EDCRE (checksum regenerator)](https://github.com/alex-free/edcre)
- [PSX CD-ROM XA format](https://romhackplaza.org/tutorials/the-playstation-translation-doc/)

### Community
- [ZonaWE Forum](https://zonawe.forosactivos.net) — Primary WE modding community
- [Evo-Web Retro PES Corner](https://evoweb.uk/forums/playstation-1-2-classic-games.348/)
- [Soccer Gaming Forums](https://soccergaming.com/forums/forums/pes-winning-eleven-forum.30/)
- [Internet Archive: WE PS1 Hacks](https://archive.org/details/winningeleven-ps1)

### Dependencies to Add
```toml
# pyproject.toml additions
dependencies = [
    ...
    "Pillow>=9.0.0",   # Image processing for TIM generation
]
```
