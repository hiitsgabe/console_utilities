# Bundled Data Sources

Console Utilities ships with a `bundled_data.json` file in the `assets/` directory that contains pre-configured game system sources. These provide out-of-the-box access to popular ROM data sources.

## Current Bundled Sources

### Myrient (HTML Directory Listing)

Myrient is a popular ROM hosting service that provides No-Intro and Redump verified ROM sets. The bundled data includes:

| System | ROMs Folder | Formats | Auto-Extract |
|--------|-------------|---------|--------------|
| Sony PlayStation (PSX) | `psx` | .zip, .cue, .bin, .iso | No |
| Super Nintendo (SNES) | `snes` | .sfc, .smc, .zip | Yes |
| Nintendo 64 (N64) | `n64` | .zip, .n64, .v64 | Yes |
| Game Boy Advance (GBA) | `gba` | .zip, .gba | Yes |
| Sega Genesis | `genesis` | .zip, .bin, .md, .gen | Yes |
| GameCube | `gc` | .zip, .iso, .gcm | Yes |
| Nintendo DS | `nds` | .zip, .nds | Yes |
| PlayStation Portable (PSP) | `psp` | .zip, .iso, .cso | No |

All Myrient sources use Libretro thumbnails for box art.

### Minerva API

Minerva is a JSON-based API source type that provides game metadata and ROM data. It supports:

- **API Key Authentication**: Uses `X-Minerva-API-Key` header
- **Flexible Response Parsing**: Configure `list_json_file_location` and `list_item_id`
- **File Filtering**: Filter by format extensions
- **Custom Download URLs**: Use `download_url` template with `<id>` placeholder

#### Minerva API Configuration

```json
{
  "name": "My Minerva Collection",
  "list_url": "https://api.minerva-project.org/games",
  "list_json_file_location": "games",
  "list_item_id": "filename",
  "list_item_size": "size",
  "download_url": "https://api.minerva-project.org/download/<id>",
  "file_format": [".zip", ".7z"],
  "roms_folder": "minerva_roms",
  "source_type": "minerva_api",
  "auth": {
    "type": "minerva_api_key",
    "api_key": "your-api-key-here"
  }
}
```

## Adding Custom Sources

### Via the App

1. Go to **Settings > Add Systems**
2. Browse available systems or add a custom source
3. For Internet Archive: Use the IA Collection wizard
4. For custom URLs: Use the folder browser to configure

### Via JSON Configuration

Edit `added_systems.json` (in `workdir/` for development, or app directory for console):

```json
[
  {
    "name": "Custom System",
    "url": "https://your-server.com/roms/",
    "file_format": [".zip"],
    "roms_folder": "custom",
    "should_unzip": true
  }
]
```

## Source Types

| Type | Configuration | Description |
|------|---------------|-------------|
| HTML | `url` field | Directory listing with optional regex |
| Internet Archive | `url` with `archive.org/download/` | IA metadata API |
| JSON API | `list_url` field | Structured JSON response |
| NPS TSV | `source_type: nps_tsv` | Nintendo PSX TSV format |
| Minerva API | `source_type: minerva_api` | Custom JSON API with auth |

## Best Game Data Sources

### ROM Sources

1. **Myrient** - No-Intro and Redump sets, clean filenames, reliable
2. **Internet Archive** - Various ROM collections, often with metadata
3. **Custom Servers** - Your own hosted ROMs

### Metadata Sources

1. **Libretro Thumbnails** - Box art, screenshots, titles, logos
2. **ScreenScraper** - Detailed metadata and artwork (requires credentials)
3. **TheGamesDB** - Game metadata and box art
4. **RAWG** - Large game database with artwork

### API Sources

For programmatic access to game data, consider:

1. **Minerva API** - If you have an API key for a Minerva-based service
2. **Custom JSON APIs** - Any API returning structured JSON can be integrated
3. **Internet Archive API** - Direct metadata access for IA collections

## Updating Bundled Sources

The `bundled_data.json` file in `assets/` is overwritten on app updates. For persistent customizations:

1. Add systems to `added_systems.json` instead
2. Or set `archive_json_path` in settings to a custom JSON file
3. Use the IA collection wizard for one-off additions

## Authentication

| Auth Type | Configuration | Header/Cookie |
|-----------|---------------|---------------|
| Bearer Token | `{"token": "..."}` | `Authorization: Bearer ...` |
| Cookie | `{"cookies": true, "token": "...", "cookie_name": "..."}` | Cookie header |
| IA S3 | `{"type": "ia_s3", "access_key": "...", "secret_key": "..."}` | `Authorization: LOW ...` |
| Minerva API Key | `{"type": "minerva_api_key", "api_key": "..."}` | `X-Minerva-API-Key: ...` |
