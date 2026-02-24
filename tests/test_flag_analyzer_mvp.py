"""MVP Flag Analyzer — Atletico Mineiro demo.

Fetches the Atletico Mineiro logo from ESPN's public API, analyzes it
spatially (dominant colors per 4x4 grid cell), matches against known WE2002
flag patterns, and outputs an ASCII visualization with the BGR555 palette
that would be written to ROM.

Run:
    python -m pytest tests/test_flag_analyzer_mvp.py -s
    # or directly:
    PYTHONPATH=src python tests/test_flag_analyzer_mvp.py
"""

import io
import struct
import sys
import os
import unicodedata
from collections import Counter
from typing import Dict, List, Tuple

import requests
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# ---------------------------------------------------------------------------
# ESPN API helpers (same base URL as espn_client.py)
# ---------------------------------------------------------------------------

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"


def _strip_accents(s: str) -> str:
    """Remove unicode accents for fuzzy name matching."""
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def fetch_team_logo(league_code: str, team_name_query: str) -> Tuple[str, str]:
    """Find a team by partial name in an ESPN league and return (name, logo_url)."""
    resp = requests.get(f"{ESPN_BASE}/{league_code}/teams", timeout=15)
    resp.raise_for_status()
    data = resp.json()
    teams_raw = (
        data.get("sports", [{}])[0]
        .get("leagues", [{}])[0]
        .get("teams", [])
    )
    query_words = _strip_accents(team_name_query.lower()).split()
    for entry in teams_raw:
        t = entry.get("team", {})
        name = t.get("displayName", "")
        haystack = _strip_accents(name.lower())
        # Match if all query words appear in the team name
        if all(w in haystack for w in query_words):
            logo_url = t.get("logos", [{}])[0].get("href", "") if t.get("logos") else ""
            return name, logo_url
    # List available teams for debugging
    available = [e.get("team", {}).get("displayName", "") for e in teams_raw]
    raise ValueError(
        f"Team matching '{team_name_query}' not found in {league_code}. "
        f"Available: {available}"
    )


def download_logo(logo_url: str) -> Image.Image:
    """Download a PNG logo and return as RGBA PIL Image."""
    resp = requests.get(logo_url, timeout=15)
    resp.raise_for_status()
    return Image.open(io.BytesIO(resp.content)).convert("RGBA")


# ---------------------------------------------------------------------------
# Color helpers (from rom_writer.py and patcher.py)
# ---------------------------------------------------------------------------


def rgb_to_bgr555(r: int, g: int, b: int) -> int:
    """Convert RGB888 to PS1 15-bit BGR555."""
    r5 = (r >> 3) & 0x1F
    g5 = (g >> 3) & 0x1F
    b5 = (b >> 3) & 0x1F
    return r5 | (g5 << 5) | (b5 << 10)


def color_distance_sq(c1: Tuple[int, ...], c2: Tuple[int, ...]) -> float:
    return sum((a - b) ** 2 for a, b in zip(c1, c2))


def nearest_color_index(color: Tuple[int, int, int], palette: List[Tuple[int, int, int]]) -> int:
    """Return index of the nearest palette color."""
    best_idx = 0
    best_dist = float("inf")
    for i, p in enumerate(palette):
        d = color_distance_sq(color, p)
        if d < best_dist:
            best_dist = d
            best_idx = i
    return best_idx


# ---------------------------------------------------------------------------
# Spatial logo analysis
# ---------------------------------------------------------------------------

GRID_SIZE = 4  # 4x4 grid of cells


def _crop_to_content(img: Image.Image) -> Image.Image:
    """Crop RGBA image to the bounding box of non-transparent pixels."""
    bbox = img.getbbox()  # uses alpha channel
    if bbox:
        return img.crop(bbox)
    return img


def _composite_on_white(img: Image.Image) -> Image.Image:
    """Composite RGBA onto a white background → RGB."""
    bg = Image.new("RGB", img.size, (255, 255, 255))
    bg.paste(img, mask=img.split()[3])  # paste using alpha as mask
    return bg


def _simplify_palette(colors: List[Tuple[int, int, int]]) -> List[Tuple[int, int, int]]:
    """Simplify quantized colors: snap near-black/near-white, remove low-chroma.

    - Near-black (max channel < 60) → (0,0,0)
    - Near-white (min channel > 200) → (255,255,255)
    - Low-chroma colors (channel spread < 80) → removed.  These are grays
      from anti-aliasing AND muted tints from small decorative elements
      (e.g. a tiny gold star on a black/white badge).  Real team colors
      like Boca's gold (chroma 201), Flamengo's red, etc. pass easily.
    - Remaining vivid colors are kept as-is (actual team colors)
    """
    simplified = []
    for r, g, b in colors:
        if max(r, g, b) < 60:
            simplified.append((0, 0, 0))
        elif min(r, g, b) > 200:
            simplified.append((255, 255, 255))
        else:
            mx, mn = max(r, g, b), min(r, g, b)
            chroma = mx - mn
            if chroma < 80:
                # Low-chroma: gray edges or muted decorative elements — skip
                continue
            simplified.append((r, g, b))
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for c in simplified:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    # Ensure at least 2 colors (the top two from input if everything was gray)
    if len(unique) < 2:
        for r, g, b in colors:
            c = (r, g, b)
            if max(r, g, b) < 60:
                c = (0, 0, 0)
            elif min(r, g, b) > 200:
                c = (255, 255, 255)
            if c not in unique:
                unique.append(c)
            if len(unique) >= 2:
                break
    return unique


def analyze_logo_grid(img: Image.Image) -> Tuple[
    List[List[Tuple[int, int, int]]],
    List[Tuple[int, int, int]],
]:
    """Analyze logo: crop, quantize opaque pixels, build 4×4 color grid.

    Steps:
      1. Crop to opaque bounding box (removes surrounding transparency).
      2. Resize to 64×64 for detail preservation.
      3. Quantize opaque pixels to a small palette (4 colors), then merge
         near-blacks into pure black to avoid splitting badge outlines into
         many useless dark variants.  This yields the 2–4 actual team colors.
      4. Build a canonical palette from those merged colors, padded to 16.
      5. For each 4×4 grid cell, snap opaque pixels to the canonical palette
         and pick the most common.  Cells with <25% opaque coverage inherit
         from the nearest populated neighbor (background, not badge content).

    Returns:
        color_grid: 4x4 list of dominant RGB colors per cell
        palette_16: 16-color quantized palette (RGB tuples)
    """
    IMG_SIZE = 64
    ALPHA_THRESHOLD = 128
    COVERAGE_MIN = 0.25

    # Crop to content and resize (keep RGBA)
    img = _crop_to_content(img)
    img = img.resize((IMG_SIZE, IMG_SIZE), Image.LANCZOS)

    # Collect opaque pixels
    px_data = list(img.getdata())  # (r, g, b, a)
    opaque_pixels = [(r, g, b) for r, g, b, a in px_data if a > ALPHA_THRESHOLD]

    if not opaque_pixels:
        flat = [(128, 128, 128)] * 16
        return [[flat[0]] * GRID_SIZE for _ in range(GRID_SIZE)], flat

    # Step 1: quantize to 8 colors to capture the full range
    q_img = Image.new("RGB", (len(opaque_pixels), 1))
    q_img.putdata(opaque_pixels)
    quantized = q_img.quantize(colors=8, method=Image.Quantize.MEDIANCUT)
    raw_pal = quantized.getpalette()
    raw_colors = [
        (raw_pal[i * 3], raw_pal[i * 3 + 1], raw_pal[i * 3 + 2])
        for i in range(min(8, len(raw_pal) // 3))
    ]

    # Step 2: simplify palette — snap near-black/white, remove gray edges
    canonical = _simplify_palette(raw_colors)

    # Step 3: build 16-slot palette, distributing slots evenly
    palette_16 = []
    slots_each = max(1, 16 // len(canonical))
    for c in canonical:
        palette_16.extend([c] * slots_each)
    while len(palette_16) < 16:
        palette_16.append(canonical[-1])
    palette_16 = palette_16[:16]

    # Helper: snap a raw pixel to canonical palette
    def snap(r, g, b):
        if max(r, g, b) < 60:
            return nearest_color_index((0, 0, 0), canonical)
        if min(r, g, b) > 200:
            return nearest_color_index((255, 255, 255), canonical)
        return nearest_color_index((r, g, b), canonical)

    # Step 4: for each grid cell, snap opaque pixels and pick the best color.
    # Use a weighted approach: if a cell has >30% secondary color presence,
    # pick the secondary color. This reveals interior fill colors that would
    # otherwise be hidden by surrounding outlines in every cell.
    cell_size = IMG_SIZE // GRID_SIZE
    pixels_per_cell = cell_size * cell_size
    color_grid: List[List[Tuple[int, int, int] | None]] = []
    for row in range(GRID_SIZE):
        grid_row: List[Tuple[int, int, int] | None] = []
        for col in range(GRID_SIZE):
            cell_indices = []
            for py in range(cell_size):
                for px in range(cell_size):
                    r, g, b, a = px_data[(row * cell_size + py) * IMG_SIZE + (col * cell_size + px)]
                    if a > ALPHA_THRESHOLD:
                        cell_indices.append(snap(r, g, b))
            if len(cell_indices) >= pixels_per_cell * COVERAGE_MIN:
                counts = Counter(cell_indices)
                ranked = counts.most_common()
                # If the top color has a rival with >30% presence, use the rival.
                # This helps with badge-style logos where outlines bleed into every
                # cell but interior regions have meaningful secondary presence.
                if len(ranked) > 1 and ranked[1][1] / len(cell_indices) > 0.30:
                    grid_row.append(canonical[ranked[1][0]])
                else:
                    grid_row.append(canonical[ranked[0][0]])
            else:
                grid_row.append(None)  # background
        color_grid.append(grid_row)

    # Fill background cells from nearest populated neighbor
    _fill_background_cells(color_grid, canonical)

    return color_grid, palette_16


def _fill_background_cells(
    grid: List[List[Tuple[int, int, int] | None]],
    canonical: List[Tuple[int, int, int]],
):
    """Replace None cells with the nearest populated neighbor's color."""
    populated = []
    for r in range(GRID_SIZE):
        for c in range(GRID_SIZE):
            if grid[r][c] is not None:
                populated.append((r, c))

    if not populated:
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                grid[r][c] = canonical[0]
        return

    for r in range(GRID_SIZE):
        for c in range(GRID_SIZE):
            if grid[r][c] is None:
                best_dist = float("inf")
                best_color = canonical[0]
                for pr, pc in populated:
                    d = abs(r - pr) + abs(c - pc)
                    if d < best_dist:
                        best_dist = d
                        best_color = grid[pr][pc]
                grid[r][c] = best_color


# ---------------------------------------------------------------------------
# Pattern templates and matching
# ---------------------------------------------------------------------------

# Each pattern is a 4x4 grid of zone IDs. Cells in the same zone should share
# a color; different zones should differ.
PATTERNS = {
    "solid": {
        "style": 0,
        "grid": [
            [0, 0, 0, 0],
            [0, 0, 0, 0],
            [0, 0, 0, 0],
            [0, 0, 0, 0],
        ],
    },
    "vertical_halves": {
        "style": 4,
        "grid": [
            [0, 0, 1, 1],
            [0, 0, 1, 1],
            [0, 0, 1, 1],
            [0, 0, 1, 1],
        ],
    },
    "horizontal_halves": {
        "style": 3,
        "grid": [
            [0, 0, 0, 0],
            [0, 0, 0, 0],
            [1, 1, 1, 1],
            [1, 1, 1, 1],
        ],
    },
    "vertical_thirds": {
        "style": 6,
        "grid": [
            [0, 0, 1, 2],
            [0, 0, 1, 2],
            [0, 0, 1, 2],
            [0, 0, 1, 2],
        ],
    },
    "horizontal_thirds": {
        "style": 5,
        "grid": [
            [0, 0, 0, 0],
            [1, 1, 1, 1],
            [1, 1, 1, 1],
            [2, 2, 2, 2],
        ],
    },
    "diagonal": {
        "style": 9,
        "grid": [
            [0, 0, 0, 1],
            [0, 0, 1, 1],
            [0, 1, 1, 1],
            [1, 1, 1, 1],
        ],
    },
    "quadrants": {
        "style": 7,
        "grid": [
            [0, 0, 1, 1],
            [0, 0, 1, 1],
            [2, 2, 3, 3],
            [2, 2, 3, 3],
        ],
    },
    "vertical_stripes": {
        "style": 10,
        "grid": [
            [0, 1, 0, 1],
            [0, 1, 0, 1],
            [0, 1, 0, 1],
            [0, 1, 0, 1],
        ],
    },
}


def _zone_colors(
    color_grid: List[List[Tuple[int, int, int]]],
    pattern_grid: List[List[int]],
) -> Dict[int, List[Tuple[int, int, int]]]:
    """Group grid colors by zone ID."""
    zones: Dict[int, List[Tuple[int, int, int]]] = {}
    for r in range(GRID_SIZE):
        for c in range(GRID_SIZE):
            zone = pattern_grid[r][c]
            zones.setdefault(zone, []).append(color_grid[r][c])
    return zones


def _within_zone_variance(colors: List[Tuple[int, int, int]]) -> float:
    """Average squared distance of colors from their centroid."""
    if len(colors) <= 1:
        return 0.0
    cr = sum(c[0] for c in colors) / len(colors)
    cg = sum(c[1] for c in colors) / len(colors)
    cb = sum(c[2] for c in colors) / len(colors)
    centroid = (cr, cg, cb)
    return sum(color_distance_sq(c, centroid) for c in colors) / len(colors)


def _between_zone_distance(zone_centroids: List[Tuple[float, float, float]]) -> float:
    """Average pairwise distance between zone centroids."""
    if len(zone_centroids) <= 1:
        return 0.0
    total = 0.0
    count = 0
    for i in range(len(zone_centroids)):
        for j in range(i + 1, len(zone_centroids)):
            total += color_distance_sq(zone_centroids[i], zone_centroids[j]) ** 0.5
            count += 1
    return total / count if count > 0 else 0.0


def score_pattern(
    color_grid: List[List[Tuple[int, int, int]]],
    pattern_grid: List[List[int]],
) -> float:
    """Score how well the color grid matches a pattern template.

    Higher is better. Score = between_zone_distance / (1 + within_zone_variance).
    This rewards patterns where zones are internally consistent but differ from
    each other.
    """
    zones = _zone_colors(color_grid, pattern_grid)

    # Compute within-zone variance (average across zones)
    within = sum(_within_zone_variance(colors) for colors in zones.values()) / len(zones)

    # Compute zone centroids
    centroids = []
    for colors in zones.values():
        cr = sum(c[0] for c in colors) / len(colors)
        cg = sum(c[1] for c in colors) / len(colors)
        cb = sum(c[2] for c in colors) / len(colors)
        centroids.append((cr, cg, cb))

    between = _between_zone_distance(centroids)

    # Normalize: max possible distance is ~441 (sqrt(255^2*3))
    return between / (1.0 + within ** 0.5)


def match_best_pattern(
    color_grid: List[List[Tuple[int, int, int]]],
) -> Tuple[str, int, float]:
    """Find the best-matching pattern for a color grid.

    Returns (pattern_name, style_byte, score).
    """
    best_name = "solid"
    best_style = 0
    best_score = -1.0

    for name, info in PATTERNS.items():
        s = score_pattern(color_grid, info["grid"])
        if s > best_score:
            best_score = s
            best_name = name
            best_style = info["style"]

    return best_name, best_style, best_score


# ---------------------------------------------------------------------------
# Palette builder — assign palette slots per zone
# ---------------------------------------------------------------------------


def build_flag_palette(
    color_grid: List[List[Tuple[int, int, int]]],
    pattern_grid: List[List[int]],
    palette_16: List[Tuple[int, int, int]],
) -> List[Tuple[int, int, int]]:
    """Build the 16-color flag palette, distributing slots across zones.

    For each zone, picks the most common color among its grid cells.  If two
    zones would get the same color, the second zone falls back to the next
    most common color — ensuring visual distinction between zones.
    """
    zones = _zone_colors(color_grid, pattern_grid)
    n_zones = len(zones)
    sorted_zones = sorted(zones.keys())

    # For each zone, rank its colors by frequency
    zone_ranked: Dict[int, List[Tuple[int, int, int]]] = {}
    for z in sorted_zones:
        freq = Counter(zones[z]).most_common()
        zone_ranked[z] = [color for color, _ in freq]

    # Assign colors greedily, avoiding duplicates where possible
    used_colors: set = set()
    zone_palette_color: Dict[int, Tuple[int, int, int]] = {}
    for z in sorted_zones:
        assigned = False
        for color in zone_ranked[z]:
            if color not in used_colors:
                zone_palette_color[z] = color
                used_colors.add(color)
                assigned = True
                break
        if not assigned:
            # All colors already used — pick the most common anyway
            zone_palette_color[z] = zone_ranked[z][0]

    # Distribute 16 slots proportionally among zones
    slots_per_zone = {}
    remaining = 16
    for i, z in enumerate(sorted_zones):
        if i == n_zones - 1:
            slots_per_zone[z] = remaining
        else:
            n = max(1, 16 // n_zones)
            slots_per_zone[z] = n
            remaining -= n

    # Build final 16-color palette
    flag_palette = []
    for z in sorted_zones:
        for _ in range(slots_per_zone[z]):
            flag_palette.append(zone_palette_color[z])
    while len(flag_palette) < 16:
        flag_palette.append(flag_palette[-1])
    flag_palette = flag_palette[:16]

    return flag_palette


# ---------------------------------------------------------------------------
# ASCII visualization
# ---------------------------------------------------------------------------

# ANSI 24-bit color escape
def _ansi_bg(r, g, b):
    return f"\033[48;2;{r};{g};{b}m"


ANSI_RESET = "\033[0m"


def _color_name_hint(r, g, b) -> str:
    """Simple heuristic color name for readability."""
    brightness = r * 0.299 + g * 0.587 + b * 0.114
    if brightness < 40:
        return "black"
    if brightness > 220 and max(r, g, b) - min(r, g, b) < 30:
        return "white"
    if r > 180 and g < 80 and b < 80:
        return "red"
    if r < 80 and g > 120 and b < 80:
        return "green"
    if r < 80 and g < 80 and b > 150:
        return "blue"
    if r > 180 and g > 160 and b < 60:
        return "yellow/gold"
    if r > 180 and g > 100 and b < 60:
        return "orange"
    if r > 100 and g < 60 and b > 100:
        return "purple"
    if r < 80 and g > 150 and b > 180:
        return "cyan/light blue"
    if max(r, g, b) - min(r, g, b) < 30:
        return "gray"
    return ""


def print_analysis(
    team_name: str,
    color_grid: List[List[Tuple[int, int, int]]],
    palette_16: List[Tuple[int, int, int]],
    pattern_name: str,
    style: int,
    score: float,
    flag_palette: List[Tuple[int, int, int]],
):
    """Print the full ASCII analysis to stdout."""
    print(f"\n{team_name} — Logo Flag Analysis")
    print("=" * 50)

    # Dominant colors from grid (unique, by frequency)
    all_colors = [color_grid[r][c] for r in range(GRID_SIZE) for c in range(GRID_SIZE)]
    freq = Counter(all_colors).most_common()
    labels = ["Primary", "Secondary", "Tertiary"]
    print("\nLogo dominant colors:")
    for i, (color, count) in enumerate(freq[:3]):
        r, g, b = color
        hint = _color_name_hint(r, g, b)
        swatch = f"{_ansi_bg(r, g, b)}  {ANSI_RESET}"
        label = labels[i] if i < len(labels) else f"Color {i+1}"
        print(f"  {label:12s}: {swatch} ({r}, {g}, {b}) {hint}")

    # Color grid visualization
    print(f"\n4x4 color grid:")
    for row in color_grid:
        line = "  "
        for r, g, b in row:
            line += f"{_ansi_bg(r, g, b)}    {ANSI_RESET}"
        print(line)

    # Pattern match
    print(f"\nBest pattern match: \"{pattern_name}\" (style={style}, score={score:.2f})")

    # Pattern template visualization
    pattern_grid = PATTERNS[pattern_name]["grid"]
    zone_ids = set()
    for row in pattern_grid:
        zone_ids.update(row)
    zone_colors_map = {}
    zones = _zone_colors(color_grid, pattern_grid)
    for z, colors in zones.items():
        cr = sum(c[0] for c in colors) // len(colors)
        cg = sum(c[1] for c in colors) // len(colors)
        cb = sum(c[2] for c in colors) // len(colors)
        zone_colors_map[z] = (cr, cg, cb)

    print(f"\nPattern template ({pattern_name}):")
    for row in pattern_grid:
        line = "  "
        for z in row:
            c = zone_colors_map.get(z, (128, 128, 128))
            line += f"{_ansi_bg(*c)}  {z} {ANSI_RESET}"
        print(line)

    # BGR555 palette
    print(f"\nGenerated 16-color BGR555 palette:")
    # Identify which zone each slot belongs to
    sorted_zones = sorted(zones.keys())
    n_zones = len(sorted_zones)
    slots_per_zone = {}
    remaining = 16
    for i, z in enumerate(sorted_zones):
        if i == n_zones - 1:
            slots_per_zone[z] = remaining
        else:
            n = max(1, 16 // n_zones)
            slots_per_zone[z] = n
            remaining -= n

    slot_idx = 0
    for z in sorted_zones:
        for j in range(slots_per_zone[z]):
            r, g, b = flag_palette[slot_idx]
            bgr = rgb_to_bgr555(r, g, b)
            swatch = f"{_ansi_bg(r, g, b)}  {ANSI_RESET}"
            hint = _color_name_hint(r, g, b)
            zone_label = f"zone {z}" if j == 0 else ""
            print(f"  [{slot_idx:2d}] 0x{bgr:04X} ({r:3d},{g:3d},{b:3d}) {swatch} {hint:14s} {zone_label}")
            slot_idx += 1

    # Raw ROM bytes
    print(f"\nROM bytes that would be written:")
    print(f"  Style: 0x{style:02X}")
    bgr_values = [rgb_to_bgr555(*c) for c in flag_palette]
    color_bytes = struct.pack("<" + "H" * 16, *bgr_values)
    hex_str = " ".join(f"{b:02X}" for b in color_bytes)
    print(f"  Colors: {hex_str}")


# ---------------------------------------------------------------------------
# Pixel art preview
# ---------------------------------------------------------------------------


def generate_preview(
    pattern_name: str,
    flag_palette: List[Tuple[int, int, int]],
    output_path: str,
):
    """Generate a 64x64 pixel art preview of the flag."""
    pattern_grid = PATTERNS[pattern_name]["grid"]

    # Figure out zone → color mapping
    zones = sorted(set(z for row in pattern_grid for z in row))
    n_zones = len(zones)
    slots_per_zone = {}
    remaining = 16
    for i, z in enumerate(zones):
        if i == n_zones - 1:
            slots_per_zone[z] = remaining
        else:
            n = max(1, 16 // n_zones)
            slots_per_zone[z] = n
            remaining -= n
    # Zone color is the first palette slot assigned to that zone
    zone_color = {}
    slot_idx = 0
    for z in zones:
        zone_color[z] = flag_palette[slot_idx]
        slot_idx += slots_per_zone[z]

    preview = Image.new("RGB", (64, 64))
    cell_w = 64 // GRID_SIZE  # 16 pixels per cell
    for r in range(GRID_SIZE):
        for c in range(GRID_SIZE):
            zone_id = pattern_grid[r][c]
            color = zone_color[zone_id]
            for py in range(cell_w):
                for px in range(cell_w):
                    preview.putpixel((c * cell_w + px, r * cell_w + py), color)

    preview.save(output_path)
    print(f"\nPreview saved to: {output_path}")


# ---------------------------------------------------------------------------
# Main test
# ---------------------------------------------------------------------------


def _run_flag_analysis(league_code: str, team_query: str, preview_filename: str):
    """Shared helper: fetch logo, analyze, match pattern, visualize, assert."""
    team_name, logo_url = fetch_team_logo(league_code, team_query)
    print(f"\nFetched: {team_name}")
    print(f"Logo URL: {logo_url}")
    img = download_logo(logo_url)

    color_grid, palette_16 = analyze_logo_grid(img)
    pattern_name, style, score = match_best_pattern(color_grid)
    pattern_grid = PATTERNS[pattern_name]["grid"]
    flag_palette = build_flag_palette(color_grid, pattern_grid, palette_16)

    print_analysis(team_name, color_grid, palette_16, pattern_name, style, score, flag_palette)

    preview_path = f"/tmp/{preview_filename}"
    generate_preview(pattern_name, flag_palette, preview_path)

    assert pattern_name in PATTERNS
    assert 0 <= style <= 255
    assert len(flag_palette) == 16
    assert all(len(c) == 3 for c in flag_palette)
    assert os.path.exists(preview_path)

    return pattern_name, style, flag_palette


def test_atletico_mineiro_flag():
    """MVP: Atletico Mineiro — black shield with white/gold interior."""
    _run_flag_analysis("bra.1", "atletico mg", "atletico_flag_preview.png")


def test_flamengo_flag():
    """Flamengo — red/black horizontal stripes, should get stripes or halves."""
    _run_flag_analysis("bra.1", "flamengo", "flamengo_flag_preview.png")


def test_boca_juniors_flag():
    """Boca Juniors — blue with yellow horizontal stripe."""
    _run_flag_analysis("arg.1", "boca", "boca_flag_preview.png")


# Allow running directly: PYTHONPATH=src python tests/test_flag_analyzer_mvp.py
if __name__ == "__main__":
    test_atletico_mineiro_flag()
    test_flamengo_flag()
    test_boca_juniors_flag()
