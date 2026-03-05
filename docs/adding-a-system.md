# Adding a System

Console Utilities can pull game lists from different kinds of servers. This guide walks you through each supported source type and how to configure them.

---

## Quick Start: Add Systems from the App

The easiest way is the built-in discovery feature — no file editing required:

1. Go to **Settings > Add Systems**
2. Browse the list of available systems
3. Select one and choose a destination folder
4. Done — the system appears in your main list

If you want to add a system that isn't in the discovery list, or you're hosting your own files, read on.

---

## Where to Put Your Configuration

Systems are defined as JSON objects in configuration files:

- **`added_systems.json`** — Your custom systems. This is where you should add new entries.
- **`bundled_data.json`** — Ships with the app. Editing this directly is not recommended since updates may overwrite it.

| Environment | `added_systems.json` Location |
|------------|------|
| Development (`DEV_MODE=true`) | `workdir/added_systems.json` |
| Console | Same directory as the app |

The file is a JSON array. Each entry is one system:

```json
[
  { "name": "System One", "url": "...", "file_format": [".zip"], "roms_folder": "sys1" },
  { "name": "System Two", "url": "...", "file_format": [".zip"], "roms_folder": "sys2" }
]
```

---

## Source Types

Console Utilities supports three ways to fetch a game list. The app figures out which one to use based on the fields you provide:

| You provide... | The app uses... |
|----------------|-----------------|
| `url` pointing to `archive.org/download/...` | **Internet Archive** parser |
| `list_url` | **JSON API** parser |
| `url` pointing to anything else | **HTML** parser |

Each is explained below with examples.

---

## 1. HTML Directory Listing

This is the most common setup. The app fetches an HTML page from your server, scans it with a regex pattern, and extracts the list of files.

### How it works

1. The app makes a GET request to the `url`
2. It runs a regex pattern across the HTML response
3. Each regex match becomes a game entry — the pattern pulls out the filename, download link, and optionally the file size
4. Results are filtered by `file_format` and sorted alphabetically

### Basic example

If your server has a simple directory listing page with `<a>` tags linking to files, you don't even need a custom regex:

```json
{
  "name": "SNES",
  "url": "https://your-server.com/roms/snes/",
  "file_format": [".sfc", ".smc", ".zip"],
  "roms_folder": "snes",
  "should_unzip": true
}
```

Without a `regex` field, the app falls back to a simple pattern that matches any `<a href="...">` tag on the page. It then filters by `file_format` to show only relevant files.

### Custom regex

If your server uses a more structured layout (like an HTML table), you can provide a regex with **named capture groups** to extract exactly what you need:

```json
{
  "name": "SNES",
  "url": "https://your-server.com/files/SNES/",
  "regex": "<tr><td class=\"link\"><a href=\"(?P<href>[^\"]+)\" title=\"(?P<title>[^\"]+)\">(?P<text>[^<]+)</a></td><td class=\"size\">(?P<size>[^<]+)</td><td class=\"date\">[^<]*</td></tr>",
  "file_format": [".sfc", ".smc", ".zip"],
  "roms_folder": "snes",
  "should_unzip": true
}
```

The supported capture group names are:

| Group | Required | What it does |
|-------|----------|-------------|
| `href` | Yes* | The download link (relative or absolute URL) |
| `text` | No | The display filename. Falls back to `title`, then `href` |
| `title` | No | Alternative display name |
| `size` | No | Human-readable file size |
| `id` | Yes* | Unique file identifier — used with `download_url` (see below) |
| `banner_url` | No | URL to a thumbnail image for this file |

\* Either `href` or `id` (with `download_url`) is required.

### Custom download URLs

Sometimes the page you're scraping and the actual download endpoint are different. Use `download_url` with an `<id>` placeholder:

```json
{
  "name": "Custom API",
  "url": "https://api.example.com/catalog",
  "regex": "\"(?P<id>[A-F0-9]+)\".*?\"name\":\"(?P<text>[^\"]+)\"",
  "download_url": "https://api.example.com/download/<id>/file",
  "file_format": [".zip"],
  "roms_folder": "custom",
  "ignore_extension_filtering": true
}
```

When the regex captures an `id` group, the app replaces `<id>` in the `download_url` template to build the final download link.

---

## 2. Internet Archive

For files hosted on archive.org, the app automatically uses the Internet Archive metadata API to list files — no regex needed.

### How it works

1. The app detects that the `url` contains `archive.org/download/`
2. It extracts the item ID from the URL
3. It calls the IA metadata API to get the full file list with sizes
4. Results are filtered by `file_format`

### Basic example

```json
{
  "name": "My Collection",
  "url": "https://archive.org/download/my-collection-id",
  "file_format": [".zip", ".bin"],
  "roms_folder": "my_collection",
  "should_unzip": true
}
```

That's it — the app handles the rest.

### Private/restricted items

For items that require authentication, add IA S3 credentials:

```json
{
  "name": "My Private Collection",
  "url": "https://archive.org/download/my-private-item",
  "file_format": [".zip"],
  "roms_folder": "my_collection",
  "auth": {
    "type": "ia_s3",
    "access_key": "your-access-key",
    "secret_key": "your-secret-key"
  }
}
```

You can get your S3 credentials from your Internet Archive account settings.

---

## 3. JSON API

For servers that return a structured JSON response instead of HTML.

### How it works

1. The app makes a GET request to the `list_url`
2. It parses the JSON response and looks for an array of file objects
3. It extracts filenames from each object using the configured key
4. Results are filtered by `file_format`

### Basic example

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

This expects a response like:

```json
{
  "files": [
    { "name": "Game One (USA).zip" },
    { "name": "Game Two (USA).zip" }
  ]
}
```

### Configuration fields

| Field | Default | Description |
|-------|---------|-------------|
| `list_url` | *(required)* | Full URL to the JSON endpoint |
| `list_json_file_location` | `"files"` | Top-level key in the response that holds the files array |
| `list_item_id` | `"name"` | Key within each file object that contains the filename |

> **Note**: `list_json_file_location` resolves a single top-level key. Nested paths (like `data.games`) are not supported.

---

## Multi-Part Collections

Some collections are split across multiple URLs. You can use an array of URLs in the `url` field — the app fetches each one and merges the results into a single alphabetical list:

```json
{
  "name": "My Large System",
  "url": [
    "https://archive.org/download/my-collection-part1/",
    "https://archive.org/download/my-collection-part2/",
    "https://archive.org/download/my-collection-part3/"
  ],
  "file_format": [".zip"],
  "roms_folder": "my_system",
  "should_unzip": true
}
```

This works with both Internet Archive URLs and HTML directory URLs. You can even mix them in the same array — the app picks the right parser for each URL automatically.

---

## Common Fields Reference

### Required

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Display name shown in the systems list |
| `roms_folder` | string | Target directory for downloads. Can be a folder name (relative to your ROMs dir) or an absolute path. |
| `file_format` | array | Accepted file extensions, e.g. `[".zip", ".sfc"]` |

Plus a source — either `url` (for HTML or IA) or `list_url` (for JSON API).

### Optional

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `regex` | string | Simple `<a>` matcher | Custom regex for HTML parsing. See [Source Type 1](#1-html-directory-listing). |
| `boxarts` | string | *(none)* | Base URL for thumbnails. The app appends `filename.png` to build the full URL. |
| `should_unzip` | boolean | `false` | Auto-extract ZIP files after download |
| `extract_contents` | boolean | `true` | When unzipping, extract contents only (not the folder wrapper) |
| `should_filter_usa` | boolean | `true` | Whether the USA-only filter can apply to this system |
| `usa_regex` | string | `"(USA)"` | Custom regex for region filtering |
| `should_decompress_nsz` | boolean | `false` | Auto-decompress NSZ files after download |
| `ignore_extension_filtering` | boolean | `false` | Show all regex matches regardless of `file_format` |
| `download_url` | string | *(none)* | Download URL template with `<id>` placeholder |
| `auth` | object | *(none)* | Authentication config (see [Authentication](#authentication)) |

---

## Authentication

All source types support optional authentication:

### Bearer Token

```json
{ "auth": { "token": "your-bearer-token" } }
```

Sent as `Authorization: Bearer your-bearer-token` on every request.

### Cookie-Based

```json
{ "auth": { "cookies": true, "cookie_name": "session_id", "token": "your-session-token" } }
```

Sent as a cookie: `session_id=your-session-token`.

### Internet Archive S3

```json
{ "auth": { "type": "ia_s3", "access_key": "your-access-key", "secret_key": "your-secret-key" } }
```

Sent as `Authorization: LOW access-key:secret-key`.

---

## Boxart / Thumbnails

The `boxarts` field sets a base URL for game cover art. The app builds thumbnail URLs by appending the game filename (with `.png` extension) to this base:

```json
"boxarts": "https://thumbnails.example.com/SNES/"
```

A game named `"Cool Game (USA).zip"` would look for a thumbnail at:
```
https://thumbnails.example.com/SNES/Cool Game (USA).png
```

---

## Per-System Settings

After adding a system, you can tweak settings from within the app:

- **Custom ROM folder** — Override `roms_folder` with any path
- **Hide/Show** — Toggle visibility without removing the system

These are stored in `config.json` under `system_settings`.

---

## System Discovery (Advanced)

If you're hosting your own server and want to let users browse and add systems from within the app, you can configure a discovery endpoint.

Add an entry with `"list_systems": true` to your config:

```json
{
  "name": "Available Systems",
  "list_systems": true,
  "url": "https://your-server.com/files/systems/",
  "regex": "<tr><td class=\"link\"><a href=\"(?P<href>[^\"]+)\" title=\"(?P<title>[^\"]+)\">(?P<text>[^<]+)</a></td><td class=\"size\">(?P<size>[^<]+)</td><td class=\"date\">[^<]*</td></tr>",
  "file_format": [".zip"],
  "should_unzip": true,
  "boxarts": "https://thumbnails.example.com/"
}
```

The URL should serve an HTML directory listing where each sub-directory is a system. When a user picks one from **Settings > Add Systems**, the app creates a new system entry that inherits all the parent's settings (regex, file_format, boxarts, auth, etc.) and uses the sub-directory's URL.

Key details:
- Only the **first** `"list_systems": true` entry is used
- The discovery entry itself never appears in the main systems list
- Sub-directories must use the same HTML structure as the parent
- The user picks a destination folder; everything else is inherited

---

## Troubleshooting

**System shows no games:**
- Open the `url` in a browser to verify it's accessible
- If using a custom `regex`, test it against the page HTML to make sure it matches
- Check that `file_format` extensions match the actual files on the server
- Look at `error.log` for detailed error messages

**Games download to wrong folder:**
- Double-check `roms_folder` matches what your emulator expects
- Check if a custom folder override is set in per-system settings

**Thumbnails not loading:**
- Verify the `boxarts` base URL is correct
- Thumbnail filenames must match game filenames (minus extension, plus `.png`)
- Make sure the thumbnail server is reachable
