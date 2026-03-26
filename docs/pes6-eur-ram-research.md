# PES6 EUR RAM Research

## Save State
- Path: `/Users/gabe/Library/Application Support/PCSX2/sstates/SLES-54203 (7D2AF924).01.p2s`
- EE RAM: 32 MB (extracted from ZIP, eeMemory.bin)

## Team Name Table
- Location: `0x003DDCA8` (Arsenal) — first club team
- Entry size: 24 bytes (16-byte name + 8-byte abbreviation)
- National teams start earlier (~0x003DD700)
- Club teams start at Arsenal

### Sample Club Teams (Premier League, fake names)
| Offset | Name | Abbr | Real Team |
|--------|------|------|-----------|
| 0x003DDCA8 | Arsenal | ASN | Arsenal |
| 0x003DDCC0 | West Midlands Village | WMV | Aston Villa |
| 0x003DDCE0 | Lancashire | LAC | Blackburn |
| 0x003DDCF8 | Middlebrook | MID | Bolton |
| 0x003DDD10 | South East London Reds | SLR | Charlton |
| 0x003DDD28 | London FC | LDN | Chelsea |
| 0x003DDD48 | Merseyside Blue | MSB | Everton |
| 0x003DDD68 | West London White | WLW | Fulham |
| 0x003DDD88 | Merseyside Red | MSR | Liverpool |

## Player Database
- Location: `0x018415B0` (first player: "N. Jensen", Danish national team)
- Record size: 124 bytes
- Players are stored in **contiguous 32-player blocks per team**
- National teams start at DB index 1 (Denmark, England, etc.)
- Club teams start at DB index ~1338 (Arsenal is first Premier League club team)

### Key Player Indices (1-based)
- Denmark NT: starts at 1
- Arsenal: starts at 1338 (IDs 1338-1369, 32 players)
  - 1338-1353: fake-named unlicensed players (Lidoanho, Palm, etc.)
  - 1354-1369: real-named players (Lehmann, Toure, Adebayor, Lauren...)
- Aston Villa: starts at 1370
- Blackburn: starts at 1402
- ...each club has exactly 32 players

### Known Players
- Henry (France NT): index 76
- Lehmann (Arsenal): index 1354
- Campbell (England NT): index 33
- Ljungberg: index 510
- Essien (Chelsea area): index 1450
- Drogba: index 1451

## Roster Table Search Status
- Sequential flat table found at `0x018D785A` — just contiguous IDs, same as DB order
- Players per team: exactly 32
- **NEEDED**: The structure mapping team_index → starting_player_id
  - Could be a simple formula: `start_id = CLUB_BASE + team_order_index * 32`
  - Or could be a lookup table somewhere in RAM
  - The team name table at `0x003DDCA8` gives team ORDER
  - Need to verify the exact mapping between team name order and player ID blocks

## Team Name Table
- Location: `0x003DDCA8` (Arsenal) — first club team
- Entry size: 24 bytes (16-byte name + 8-byte abbreviation)
- National teams start earlier (~0x003DD700)

### Premier League Teams (PES6 fake names → real teams)
| Offset | Name | Abbr | Real Team |
|--------|------|------|-----------|
| 0x003DDCA8 | Arsenal | ASN | Arsenal |
| 0x003DDCC0 | West Midlands Village | WMV | Aston Villa |
| 0x003DDCE0 | Lancashire | LAC | Blackburn |
| 0x003DDCF8 | Middlebrook | MID | Bolton |
| 0x003DDD10 | South East London Reds | SLR | Charlton |
| 0x003DDD28 | London FC | LDN | Chelsea |
| 0x003DDD48 | Merseyside Blue | MSB | Everton |
| 0x003DDD68 | West London White | WLW | Fulham |
| 0x003DDD88 | Merseyside Red | MSR | Liverpool |
