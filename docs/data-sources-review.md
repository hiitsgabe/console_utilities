# Data Sources Review (GAB-15)

Console Utilities can populate a system's game list from several remote source
types. This document reviews them, gives guidance on the most reliable options,
and records the feasibility of integrating a MiNERVA-style source.

## Source Types

### 1. HTML directory listing
- **Config:** `url` (string or array of strings) + optional `regex`.
- **How it works:** Fetches an HTML directory index and scrapes anchor hrefs.
  An optional custom `regex` overrides the default link parser for non-standard
  layouts. Arrays of URLs allow multi-part / multi-mirror collections.
- **Best for:** Classic Apache/nginx autoindex ROM mirrors.

### 2. Internet Archive
- **Config:** `url` pointing at an `archive.org` item/details/download page.
- **Auth:** optional `auth.type == "ia_s3"` with `access_key` / `secret_key`,
  sent as an `authorization: LOW <key>:<secret>` header.
- **Best for:** Large, stable, publicly-mirrored collections.

### 3. Generic JSON API
- **Config:** `list_url` plus:
  - `list_json_file_location` — key holding the items array (default `files`).
  - `list_item_id` — key within each item holding the filename (default `name`).
  - `list_size_field` *(optional)* — key holding the file size.
  - `download_url_template` *(optional)* — URL template containing the literal
    placeholder `<id>`, substituted with each item's id to build a direct
    download href.
- **Auth (optional `auth` block):**
  - `type == "ia_s3"` — Internet Archive S3 keys.
  - `type == "header"` with `header_name` + `token` — sets an arbitrary custom
    header (e.g. `X-Api-Key: <token>`).
  - `cookies: true` + `token` (+ optional `cookie_name`) — cookie auth.
  - `token` only — `Authorization: Bearer <token>`.
- **Parsing:** delegated to the dependency-free `parse_json_api_listing`
  helper (`src/services/json_api_listing.py`).
  - **Default mode** (no `download_url_template`, no `list_size_field`):
    returns a plain `list[str]` of filenames — identical to the legacy
    behaviour, so existing configs are unaffected.
  - **Enriched mode** (template and/or size field present): returns
    `list[dict]` of `{filename, href, size}`, where `href` comes from the
    template (or each item's `url`) and `size` from the configured size field.
- **Best for:** Structured / self-hosted catalogs exposing a JSON endpoint.

### 4. NPS TSV
- **Config:** `list_url` to a tab-separated manifest (NoPayStation-style).
- **How it works:** Parses each row into `{filename, href, size, title_id,
  region}` and flags entries with `_nps_manifest` for downstream handling.
- **Best for:** PSV/PSP/PS3 NoPayStation-format catalogs.

## Best Options Guidance
- **Reliability first:** prefer HTTP mirrors (HTML directory listings) and
  `archive.org` items — they are widely mirrored, resumable, and require no
  bespoke auth.
- **Structured / self-hosted:** use the generic JSON API when you control the
  catalog or it already exposes JSON. The enhanced handler (custom header auth,
  `download_url_template`, size field) makes it suitable for authenticated,
  programmatically-generated catalogs.
- **Format-specific:** use the NPS TSV handler only for NoPayStation-format
  manifests.

## MiNERVA Feasibility
The public **MiNERVA Archive** (`minerva-archive.org`) distributes its content
**torrent-only**: it exposes no public HTTP file index and no public JSON API.
As a result it **cannot** be added as a direct-HTTP bundled source — the app
downloads over HTTP(S) and has no torrent client.

However, a **self-hosted Minerva-style JSON endpoint is fully supported** via
the enhanced generic JSON-API handler: point `list_url` at the endpoint, use
`auth.type == "header"` for an API key, set `download_url_template` (with
`<id>`) for direct-download links, and `list_size_field` for sizes. No bundled
MiNERVA URLs are added by this change.
