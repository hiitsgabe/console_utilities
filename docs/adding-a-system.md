# Adding a System

This document explains how to add a custom gaming system to Console Utilities, either through the in-app discovery feature or by manually editing configuration files.

## System Discovery (`list_systems`)

The app supports a special entry type that acts as a **system discovery endpoint**. When the user goes to **Settings > Add Systems**, the app fetches a directory listing from this entry, parses it to discover sub-directories (each representing a system), and lets the user select which ones to add.

### How It Works

1. The app finds the entry with `"list_systems": true` in the configuration
2. It fetches the HTML page at that entry's `url`
3. It parses the page using the entry's `regex` to extract sub-directory names and URLs
4. Each sub-directory is presented as a discoverable system
5. When the user selects one, the app creates a new system entry that **inherits configuration from the parent `list_systems` entry** (regex, file_format, auth, boxarts, etc.) and uses the sub-directory's URL

### JSON Configuration

The `list_systems` entry in your configuration looks like this:

```json
{
  "name": "Other Systems",
  "list_systems": true,
  "url": "https://your-server.com/files/systems/",
  "regex": "<tr><td class=\"link\"><a href=\"(?P<href>[^\"]+)\" title=\"(?P<title>[^\"]+)\">(?P<text>[^<]+)</a></td><td class=\"size\">(?P<size>[^<]+)</td><td class=\"date\">[^<]*</td></tr>",
  "file_format": [".zip"],
  "should_unzip": true,
  "boxarts": "https://thumbnails.example.com/",
  "auth": { }
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Display name (e.g., "Other Systems"). Not shown in the main systems list. |
| `list_systems` | Yes | Must be `true`. Marks this entry as a discovery endpoint. |
| `url` | Yes | URL to an HTML page listing sub-directories (one per system). |
| `regex` | Yes | Regex with named capture groups to parse the directory listing. Must capture at least `href` and `text`. |

All other fields on this entry (`file_format`, `should_unzip`, `extract_contents`, `boxarts`, `auth`, `regex`, `download_url`, `ignore_extension_filtering`, `should_filter_usa`, `should_decompress_nsz`, `usa_regex`) are **inherited by every system the user adds from this listing**.

### How the Server Must Respond

The `url` must serve an HTML page where each sub-directory is a row that the `regex` can match. The server response should look like a standard directory listing with one entry per system:

```html
<table>
  <tbody>
    <tr>
      <td class="link">
        <a href="Nintendo%20-%20Game%20Boy/" title="Nintendo - Game Boy">
          Nintendo - Game Boy/
        </a>
      </td>
      <td class="size">-</td>
      <td class="date">01-Jan-2025 00:00</td>
    </tr>
    <tr>
      <td class="link">
        <a href="Nintendo%20-%20Game%20Boy%20Advance/" title="Nintendo - Game Boy Advance">
          Nintendo - Game Boy Advance/
        </a>
      </td>
      <td class="size">-</td>
      <td class="date">01-Jan-2025 00:00</td>
    </tr>
    <tr>
      <td class="link">
        <a href="Sega%20-%20Genesis/" title="Sega - Genesis">
          Sega - Genesis/
        </a>
      </td>
      <td class="size">-</td>
      <td class="date">01-Jan-2025 00:00</td>
    </tr>
  </tbody>
</table>
```

The regex extracts:
- **`href`** - The relative URL to the sub-directory (e.g., `Nintendo%20-%20Game%20Boy/`). This gets joined with the parent `url` to build the full URL for the new system.
- **`text`** - The display name (e.g., `Nintendo - Game Boy/`). Trailing slashes are stripped for display.

The app skips navigation entries (`.`, `..`, `Parent Directory`) automatically.

### What Gets Created

When a user selects "Nintendo - Game Boy" from the discovery list, the app creates this entry in `added_systems.json`:

```json
{
  "name": "Nintendo - Game Boy",
  "url": "https://your-server.com/files/systems/Nintendo%20-%20Game%20Boy/",
  "roms_folder": "/path/user/selected/",
  "file_format": [".zip"],
  "regex": "<tr>...(inherited from parent)...</tr>",
  "should_unzip": true,
  "boxarts": "https://thumbnails.example.com/",
  "added": true
}
```

The user is prompted to pick a destination folder for the ROM files. Everything else is inherited from the `list_systems` parent entry.

### Key Points

- Only the **first** entry with `"list_systems": true` is used
- The `list_systems` entry itself is **never shown** in the main systems list
- Each sub-directory URL must serve file listings in the same format as the parent (same regex, same HTML structure)
- This means your server must use a **consistent HTML structure** across the parent directory and all sub-directories

---

## Manual Configuration

Systems are defined as JSON objects in configuration files. You can add systems to:

- **`bundled_data.json`** - Main system configuration (not recommended to edit directly)
- **`added_systems.json`** - User-added systems that persist across updates

### File Location

| Environment | Path |
|------------|------|
| Development (`DEV_MODE=true`) | `workdir/added_systems.json` |
| Console (Batocera/Knulli) | Same directory as the app (`added_systems.json`) |

### System Configuration Schema

```json
{
  "name": "System Display Name",
  "url": "https://your-server.com/files/system/",
  "regex": "<your regex pattern>",
  "file_format": [".zip", ".iso"],
  "roms_folder": "target_folder",
  "boxarts": "https://thumbnails.example.com/system/",
  "should_unzip": true,
  "should_filter_usa": true,
  "usa_regex": "(USA)"
}
```

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Display name shown in the systems list |
| `roms_folder` | string | Target directory within your ROMs folder (e.g., `"psx"`, `"gba"`). Can be a relative name or absolute path. |
| `file_format` | array | List of accepted file extensions (e.g., `[".zip", ".iso", ".bin"]`) |

Plus one of the following source configurations:

**For HTML directory listing:**
| Field | Type | Description |
|-------|------|-------------|
| `url` | string | URL to the HTML directory page |

**For JSON API:**
| Field | Type | Description |
|-------|------|-------------|
| `list_url` | string | URL to the JSON API endpoint |

**For Internet Archive:**
| Field | Type | Description |
|-------|------|-------------|
| `url` | string | Must be an `archive.org/download/` URL |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `regex` | string | Simple `<a>` matcher | Regex pattern with named capture groups for parsing HTML responses. See [Server Response Format](server-response-format.md) for details. |
| `boxarts` | string | *(none)* | Base URL for game thumbnail images. The app appends the game filename (with `.png` extension) to build the full thumbnail URL. |
| `should_unzip` | boolean | `false` | Automatically extract ZIP files after download |
| `extract_contents` | boolean | `true` | When unzipping, extract only the contents (not the folder itself) |
| `should_filter_usa` | boolean | `true` | Whether the USA-only filter applies to this system |
| `usa_regex` | string | `"(USA)"` | Custom regex for region filtering |
| `should_decompress_nsz` | boolean | `false` | Auto-decompress Nintendo Switch NSZ files after download |
| `ignore_extension_filtering` | boolean | `false` | Skip file extension checks (useful when regex already filters) |
| `download_url` | string | *(none)* | Template URL for downloads with `<id>` placeholder. Used when the download link differs from the listing link. |
| `auth` | object | *(none)* | Authentication configuration. See [Server Response Format](server-response-format.md#authentication). |

### JSON API-Specific Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `list_url` | string | *(required)* | JSON API endpoint URL |
| `list_json_file_location` | string | `"files"` | Key in JSON response containing the files array |
| `list_item_id` | string | `"name"` | Key within each file object for the filename |

---

## Examples

### Basic HTML Directory System

The simplest configuration for a server that serves an HTML directory listing:

```json
{
  "name": "Game Boy",
  "url": "https://your-server.com/files/Nintendo%20-%20Game%20Boy/",
  "regex": "<tr><td class=\"link\"><a href=\"(?P<href>[^\"]+)\" title=\"(?P<title>[^\"]+)\">(?P<text>[^<]+)</a></td><td class=\"size\">(?P<size>[^<]+)</td><td class=\"date\">[^<]*</td></tr>",
  "file_format": [".gb", ".zip"],
  "roms_folder": "gb",
  "boxarts": "https://thumbnails.libretro.com/Nintendo%20-%20Game%20Boy/Named_Boxarts/",
  "should_unzip": true
}
```

### JSON API System

```json
{
  "name": "My Game Library",
  "list_url": "https://api.example.com/games/?limit=100000",
  "list_json_file_location": "files",
  "list_item_id": "name",
  "file_format": [".zip"],
  "roms_folder": "my_library",
  "should_unzip": true
}
```

### Internet Archive Collection

```json
{
  "name": "Homebrew Collection",
  "url": "https://archive.org/download/homebrew-collection",
  "file_format": [".zip", ".bin"],
  "roms_folder": "homebrew",
  "should_unzip": true
}
```

### System with Custom Download URLs

For servers where the file listing and download endpoints are different:

```json
{
  "name": "Custom API",
  "url": "https://api.example.com/catalog",
  "regex": "\"(?P<id>[A-F0-9]+)\".*?\"name\":\"(?P<text>[^\"]+)\".*?\"icon\":\"(?P<banner_url>[^\"]+)\"",
  "download_url": "https://api.example.com/download/<id>/file",
  "file_format": [".zip"],
  "roms_folder": "custom",
  "ignore_extension_filtering": true,
  "should_unzip": true
}
```

### Minimal System (No Regex)

If you don't provide a `regex`, the app uses a simple default that matches any `<a href>` on the page:

```json
{
  "name": "Simple Server",
  "url": "https://your-server.com/roms/snes/",
  "file_format": [".sfc", ".smc", ".zip"],
  "roms_folder": "snes",
  "should_unzip": true
}
```

---

## Adding Multiple Systems at Once

The `added_systems.json` file is a JSON array. Add multiple systems by adding entries to the array:

```json
[
  {
    "name": "System One",
    "url": "https://server.com/system-one/",
    "file_format": [".zip"],
    "roms_folder": "system_one"
  },
  {
    "name": "System Two",
    "url": "https://server.com/system-two/",
    "file_format": [".iso"],
    "roms_folder": "system_two"
  }
]
```

---

## Boxart / Thumbnails

The `boxarts` field sets a base URL for game cover art. The app constructs thumbnail URLs by appending the game filename (with `.png` extension) to this base URL.

For example, with:
```json
"boxarts": "https://thumbnails.libretro.com/Nintendo%20-%20Game%20Boy/Named_Boxarts/"
```

A game named `"Pokemon Red (USA).zip"` would look for a thumbnail at:
```
https://thumbnails.libretro.com/Nintendo%20-%20Game%20Boy/Named_Boxarts/Pokemon Red (USA).png
```

[Libretro thumbnails](https://thumbnails.libretro.com/) are a good source for standard system cover art.

---

## Per-System Settings

After adding a system, you can configure additional per-system settings from within the app:

- **Custom ROM folder** - Override the default `roms_folder` with a custom path
- **Hide/Show** - Toggle visibility in the systems list without removing the system
- These settings are stored in `config.json` under `system_settings`

---

## Troubleshooting

**System shows no games:**
- Verify the `url` is accessible (try opening it in a browser)
- Check that your `regex` pattern matches the HTML structure of the page
- Ensure `file_format` extensions match the actual files on the server
- Check `error.log` for detailed error messages

**Games download to wrong folder:**
- Verify `roms_folder` matches the folder name expected by your emulator
- Check if a custom folder has been set in per-system settings

**Thumbnails not loading:**
- Verify the `boxarts` URL base is correct
- Check that thumbnail filenames match game filenames (minus extension, plus `.png`)
- Ensure the thumbnail server is accessible
