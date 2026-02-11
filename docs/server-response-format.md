# Server Response Format

This document describes how your server needs to respond for Console Utilities to detect and list files from it. The app supports three server response formats: **HTML Directory Listing**, **JSON API**, and **Internet Archive**.

## HTML Directory Listing (Recommended)

This is the most common format. Your server serves an HTML page containing a table of files, and the app uses a regex pattern to extract file information from each row.

### Expected HTML Structure

The app fetches the page at the configured `url` and applies a regex pattern to extract file entries. The default regex expects an HTML table with rows containing link, size, and date columns.

Here's an example of what the HTML response should look like:

```html
<!DOCTYPE html>
<html>
<body>
  <h1>Index of /files/My-System/</h1>
  <table>
    <thead>
      <tr>
        <th>File Name</th>
        <th>File Size</th>
        <th>Date</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td class="link">
          <a href="Game%20Name%20%28USA%29.zip" title="Game Name (USA).zip">
            Game Name (USA).zip
          </a>
        </td>
        <td class="size">125.4 MiB</td>
        <td class="date">15-Jan-2025 12:00</td>
      </tr>
      <tr>
        <td class="link">
          <a href="Another%20Game%20%28USA%29.zip" title="Another Game (USA).zip">
            Another Game (USA).zip
          </a>
        </td>
        <td class="size">89.2 MiB</td>
        <td class="date">20-Feb-2025 08:30</td>
      </tr>
    </tbody>
  </table>
</body>
</html>
```

### Regex Pattern

The regex must use **named capture groups** to extract data from each row. The app recognizes the following group names:

| Group Name   | Required | Description |
|-------------|----------|-------------|
| `href`      | Yes*     | The download URL (relative or absolute path) |
| `text`      | No       | Display filename (falls back to `title` or `href`) |
| `title`     | No       | Fallback display name |
| `size`      | No       | Human-readable file size |
| `id`        | Yes*     | Unique identifier, used with `download_url` template |
| `banner_url`| No       | URL to a thumbnail/banner image for the file |

*Either `href` or `id` (with `download_url`) is required.

Here's the regex pattern that matches the HTML table structure shown above:

```regex
<tr><td class="link"><a href="(?P<href>[^"]+)" title="(?P<title>[^"]+)">(?P<text>[^<]+)</a></td><td class="size">(?P<size>[^<]+)</td><td class="date">[^<]*</td></tr>
```

### Minimal Fallback

If no custom `regex` is configured, the app falls back to a simple pattern that matches any `<a>` tag:

```regex
<a href="([^"]+)"[^>]*>([^<]+)</a>
```

This captures `(href, text)` as positional groups. It's less precise but works with any page containing file links.

### Key Requirements

1. **File links must contain the filename** (or a URL-encoded version of it) in the `href` attribute
2. **Relative URLs are supported** - the app joins them with the base `url`
3. **URL encoding** - filenames with special characters should be URL-encoded in the `href` (e.g., spaces as `%20`)
4. The `title` attribute should contain the decoded/readable filename
5. The visible link text should also be the readable filename
6. **Content-Length header** - your server should respond to `HEAD` requests with a `Content-Length` header so the app can show file sizes and download progress

### Download URL Template

For servers where the download URL differs from the listing URL, use the `download_url` field with an `<id>` placeholder:

```json
{
  "url": "https://your-server.com/api/games",
  "regex": "\"(?P<id>[A-F0-9]+)\".*?\"name\".*?\"(?P<text>[^\"]+)\"",
  "download_url": "https://your-server.com/download/<id>/file"
}
```

When the regex captures an `id` group, the app replaces `<id>` in the `download_url` template to build the final download link.

---

## JSON API

For servers that return structured JSON instead of HTML.

### Configuration

Use `list_url` instead of `url` to signal that this is a JSON API source:

```json
{
  "name": "My System",
  "list_url": "https://your-api.com/games/?limit=100000",
  "list_json_file_location": "files",
  "list_item_id": "name",
  "file_format": [".zip"],
  "roms_folder": "my_system"
}
```

### Expected JSON Response

The response must be a JSON object containing an array of file objects:

```json
{
  "files": [
    { "name": "Game One (USA).zip" },
    { "name": "Game Two (USA).zip" },
    { "name": "Game Three (Europe).zip" }
  ]
}
```

### Configuration Fields

| Field | Default | Description |
|-------|---------|-------------|
| `list_url` | *(required)* | Full URL to the JSON API endpoint |
| `list_json_file_location` | `"files"` | Key in the JSON response that contains the files array |
| `list_item_id` | `"name"` | Key within each file object that contains the filename |

### Custom Response Structure

If your API returns data in a different structure, configure the field paths accordingly:

```json
// API returns: { "data": { "games": [{ "filename": "Game.zip" }] } }
{
  "list_url": "https://api.example.com/v1/games",
  "list_json_file_location": "games",
  "list_item_id": "filename"
}
```

> **Note**: The `list_json_file_location` currently resolves a single top-level key. Nested paths are not supported.

---

## Internet Archive

For items hosted on archive.org.

### Configuration

Simply set the `url` to an `archive.org/download/` URL:

```json
{
  "name": "My Collection",
  "url": "https://archive.org/download/my-item-id",
  "file_format": [".zip", ".iso"],
  "roms_folder": "my_system"
}
```

The app automatically detects archive.org URLs and uses the Internet Archive metadata API to list files.

### Authentication

For private or restricted items, provide S3-style credentials:

```json
{
  "url": "https://archive.org/download/my-private-item",
  "auth": {
    "type": "ia_s3",
    "access_key": "your-access-key",
    "secret_key": "your-secret-key"
  }
}
```

Credentials can be obtained from the [Internet Archive S3 API](https://archive.org/account/s3.php).

---

## Authentication

All three formats support optional authentication. Add an `auth` object to your system configuration:

### Bearer Token

```json
{
  "auth": {
    "token": "your-bearer-token"
  }
}
```

Sent as: `Authorization: Bearer your-bearer-token`

### Cookie-Based

```json
{
  "auth": {
    "cookies": true,
    "cookie_name": "session_id",
    "token": "your-session-token"
  }
}
```

Sent as a cookie: `session_id=your-session-token`

### Internet Archive S3

```json
{
  "auth": {
    "type": "ia_s3",
    "access_key": "your-access-key",
    "secret_key": "your-secret-key"
  }
}
```

Sent as: `Authorization: LOW access-key:secret-key`

---

## Filtering Behavior

The app applies several filters to the parsed file list:

1. **Extension filtering** - Only files matching extensions in `file_format` are shown (case-insensitive). Can be disabled with `"ignore_extension_filtering": true`.
2. **USA filter** - When enabled in settings, filters filenames matching a regex pattern (default: `(USA)`). Configurable per-system with `usa_regex`.
3. **Non-ASCII filter** - Files starting with non-ASCII characters are skipped.
4. **Sorting** - Results are sorted alphabetically by filename.

---

## Testing Your Server

You can test if your server responds correctly by curling the URL and checking that the regex matches:

```bash
# Fetch the HTML page
curl -s "https://your-server.com/files/system/" | head -20

# Test the regex against the response
curl -s "https://your-server.com/files/system/" | \
  grep -oP '<tr><td class="link"><a href="(?P<href>[^"]+)"'
```

For JSON APIs:

```bash
curl -s "https://your-api.com/games/" | python3 -m json.tool
```
