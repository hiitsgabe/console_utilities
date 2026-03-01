# Sports ROM Patcher

The Sports ROM Patcher lets you update team rosters in retro sports games using real-world data from public sports APIs. It supports soccer and hockey titles across multiple console platforms.

**Important:** You must provide your own ROM or ISO file dumped from an original game copy that you legally own. This project does not provide, distribute, or link to any game files. The developers assume no responsibility for any misuse of this tool.

## Supported Platforms

| Platform | Sport | ROM Format |
|----------|-------|------------|
| PS1 | Soccer | `.bin` (Mode2/2352) |
| SNES | Soccer | `.sfc` |
| Genesis | Hockey | `.bin` |
| SNES | Hockey | `.sfc` / `.smc` |
| PSP | Hockey | `.iso` |

## How It Works

All patchers follow the same guided, step-by-step workflow:

### 1. Select Season

Choose the season year for roster data. Depending on the data provider:
- **ESPN API** — Current season only, no authentication required
- **Public Hockey API** — Historical seasons back to 1993, no authentication required
- **API-Football** — Current and historical seasons, requires a free API key (configured in Settings)

### 2. Select League (Soccer Only)

For soccer patchers, browse and search available leagues from the selected API provider. Hockey patchers fetch rosters directly for the selected season.

### 3. Fetch Rosters

The app fetches team rosters and per-player statistics from the selected API. A streaming progress indicator shows teams loading in real time.

### 4. Preview Rosters

Before any changes are made, you can review every team and its players. The preview shows:
- Player names
- Positions
- Mapped in-game attributes (derived from real-world stats)
- Jersey/shirt numbers

This step lets you verify the data looks correct before proceeding.

### 5. Set Team Colors (Soccer, API-Football Only)

An interactive color picker lets you customize primary, secondary, tertiary, and goalkeeper kit colors for each team. Colors are fetched from the API when available and can be manually adjusted.

### 6. Select ROM / ISO

A file browser lets you navigate to and select your game file. The patcher validates the file format before proceeding.

### 7. Patch

The patcher writes updated data into a **new output file**, leaving your original ROM/ISO untouched. A progress indicator shows the patching process. Depending on the platform, the patcher updates:

- Player names and jersey numbers
- Player attributes and stats (mapped to each game's internal scale)
- Team names and abbreviations
- Kit/jersey colors (home, away, goalkeeper)
- Team flag designs and colors
- Line assignments and roster ordering

## Platform-Specific Details

### PS1 Soccer Patcher

- **Team Slots**: 32 club team slots + 63 national team slots
- **Dual Write**: Each team is written to both a club slot and a national team slot simultaneously, so updated rosters appear in all game modes
- **Language Support**: Team names can be written in English, German, French, Spanish, or Japanese
- **Translation Patch**: Optionally applies a full English translation patch (PPF format) during the patching process
- **What Gets Patched**: Player names, attributes (mapped from a 1-9 scale to the game's internal 3-bit encoding), kit colors (primary/secondary/GK), team flags, team names (including abbreviations and alternate display variants), and force/strength bars

### SNES Soccer Patcher

- **Team Slots**: 27 teams (26 national + 1 all-star team)
- **Player Limit**: 15 players per team, 8-character names using a custom character encoding
- **What Gets Patched**: Player names, player data (speed, shooting, technique, stamina, hair style), home/away/GK jersey colors (BGR555 format), flag tiles and colors, predominant team color, and team name text
- **Color System**: Kit colors use 15-bit BGR little-endian encoding; flag tiles use a simple RLE compression scheme

### Genesis Hockey Patcher

- **Team Slots**: 26 teams
- **Architecture**: Motorola 68000 big-endian ROM with a pointer table at a fixed offset
- **What Gets Patched**: Player names (variable-length with length prefix), jersey numbers (BCD encoded), player attributes (14 attributes per player on a 0-6 scale, nibble-packed into 7 bytes), line assignments, and team roster headers
- **Checksum Bypass**: The patcher writes an RTS instruction to disable the game's internal ROM checksum validation, allowing the modified ROM to boot correctly
- **Budget-Aware**: Player names are truncated if necessary to fit within each team's existing byte allocation in the ROM

### SNES Hockey Patcher

- **Team Slots**: 28 teams
- **Position Splits**: Respects the original ROM's goalie/forward/defenseman player counts per team
- **What Gets Patched**: Player names, jersey numbers, player attributes, and roster ordering (players written in G/F/D ROM order)
- **Header Detection**: Automatically handles both headered and headerless SNES ROMs

### PSP Hockey Patcher

- **Team Slots**: 30 league teams + 2 all-star teams + international teams
- **Complex Archive Stack**: The game stores roster data inside a compressed archive within the ISO:
  - ISO 9660 image → EA BIGF archive (`db.viv`) → RefPack-compressed TDB database files → bit-packed table records
- **What Gets Patched**: Player bios and attributes, roster assignments, team associations — across multiple cross-referenced database tables (linked via an internal player ID index system)
- **Non-Destructive**: The patcher copies the full ISO before modifying it, so the original file is never altered
- **Patching Process**:
  1. Copies the ISO to the output path
  2. Extracts the database archive from the ISO
  3. Decompresses the TDB files using the RefPack algorithm
  4. Modifies the relevant database tables with new roster data
  5. Recompresses the TDB files
  6. Rebuilds the archive and writes it back into the ISO

## Data Sources

The patcher fetches real-world roster and statistics data from public sports APIs:

| Provider | Sports | Auth Required | Season Coverage |
|----------|--------|--------------|-----------------|
| ESPN Public API | Hockey, Soccer | No | Current season |
| Public Hockey API | Hockey | No | 1993 to present |
| API-Football | Soccer | Yes (free key) | Multiple seasons |

### Configuring API-Football

1. Sign up for a free API key at the API-Football provider
2. Open **Settings** in Console Utilities
3. Enter your API key in the API-Football configuration section
4. The soccer patchers will now offer API-Football as a data provider alongside ESPN

## Attribute Mapping

Each patcher maps real-world player statistics to the target game's internal attribute system. The mapping varies by game but generally considers:

- **Offensive stats**: Goals, assists, points → shooting, offensive awareness
- **Defensive stats**: Blocks, takeaways, defensive plays → checking, defensive awareness
- **Physical stats**: Height, weight → size, strength, aggression
- **Performance stats**: Games played, ice time/minutes → endurance, stamina
- **Skill stats**: Save percentage (goalies), pass completion → accuracy attributes

The exact mapping formula is tuned per game to produce balanced, realistic in-game ratings that reflect each player's real-world performance.

## Troubleshooting

### Common Issues

- **"No teams found"**: Check your network connection. The patcher requires internet access to fetch roster data from public APIs.
- **API rate limits**: The ESPN and public hockey APIs are free and generally generous, but excessive requests may be throttled. Wait a moment and try again.
- **ROM not recognized**: Ensure you are selecting the correct file format for the patcher (e.g., `.bin` for Genesis, `.sfc` for SNES, `.iso` for PSP).
- **Patched game doesn't boot**: Some emulators are stricter about ROM validation than others. Try a different emulator or verify your source ROM is a clean, unmodified dump.
- **Missing players**: The patcher writes as many players as the ROM format allows per team. If a real-world roster has more players than available slots, lower-ranked players may be omitted.

### Output Files

Patched files are saved to a location you choose during the patching process. The original ROM/ISO is never modified. If you need to re-patch with different data, you can always start from your original file again.

## Legal Notice

- You must provide your own ROM or ISO file from an original game copy that you legally own
- This tool does not provide, distribute, host, or link to any game files
- This project is not affiliated with any game publishers, developers, or sports leagues
- The developers and contributors assume no responsibility or liability for any misuse of this software
- Users are solely responsible for ensuring their use complies with all applicable copyright laws in their jurisdiction
- This tool is intended for personal use only with games you legally own
