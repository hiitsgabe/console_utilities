"""Logo pattern analyzer — picks a geometric flag style + palette from a logo.

Downloads a team logo PNG, analyzes it spatially (dominant colors per 4×4 grid),
matches against known flag patterns, and returns the style byte + 16-color
RGB palette ready for ROM patching.

Requires PIL (Pillow).
"""

import io
from collections import Counter
from typing import Dict, List, Optional, Tuple

try:
    from PIL import Image
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

import requests

# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------

GRID_SIZE = 4  # 4x4 grid of cells


def _color_distance_sq(c1: Tuple[int, ...], c2: Tuple[int, ...]) -> float:
    return sum((a - b) ** 2 for a, b in zip(c1, c2))


def _nearest_color_index(
    color: Tuple[int, int, int], palette: List[Tuple[int, int, int]]
) -> int:
    best_idx = 0
    best_dist = float("inf")
    for i, p in enumerate(palette):
        d = _color_distance_sq(color, p)
        if d < best_dist:
            best_dist = d
            best_idx = i
    return best_idx


# ---------------------------------------------------------------------------
# Palette simplification
# ---------------------------------------------------------------------------


def _simplify_palette(
    colors: List[Tuple[int, int, int]],
) -> List[Tuple[int, int, int]]:
    """Simplify quantized colors: snap near-black/near-white, remove low-chroma.

    - Near-black (max channel < 60) → (0,0,0)
    - Near-white (min channel > 200) → (255,255,255)
    - Low-chroma colors (channel spread < 80) → removed.  These are grays
      from anti-aliasing AND muted tints from small decorative elements.
      Real team colors (chroma 100+) pass easily.
    - Remaining vivid colors are kept as-is
    """
    simplified = []
    for r, g, b in colors:
        if max(r, g, b) < 60:
            simplified.append((0, 0, 0))
        elif min(r, g, b) > 200:
            simplified.append((255, 255, 255))
        else:
            chroma = max(r, g, b) - min(r, g, b)
            if chroma < 80:
                continue
            simplified.append((r, g, b))
    # Deduplicate preserving order
    seen = set()
    unique = []
    for c in simplified:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    # Ensure at least 2 colors
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


# ---------------------------------------------------------------------------
# Pattern templates
# ---------------------------------------------------------------------------

# Each pattern is a 4x4 grid of zone IDs.
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

# ---------------------------------------------------------------------------
# Pattern matching
# ---------------------------------------------------------------------------


def _zone_colors(
    color_grid: List[List[Tuple[int, int, int]]],
    pattern_grid: List[List[int]],
) -> Dict[int, List[Tuple[int, int, int]]]:
    zones: Dict[int, List[Tuple[int, int, int]]] = {}
    for r in range(GRID_SIZE):
        for c in range(GRID_SIZE):
            zone = pattern_grid[r][c]
            zones.setdefault(zone, []).append(color_grid[r][c])
    return zones


def _within_zone_variance(colors: List[Tuple[int, int, int]]) -> float:
    if len(colors) <= 1:
        return 0.0
    cr = sum(c[0] for c in colors) / len(colors)
    cg = sum(c[1] for c in colors) / len(colors)
    cb = sum(c[2] for c in colors) / len(colors)
    centroid = (cr, cg, cb)
    return sum(_color_distance_sq(c, centroid) for c in colors) / len(colors)


def _between_zone_distance(
    zone_centroids: List[Tuple[float, float, float]],
) -> float:
    if len(zone_centroids) <= 1:
        return 0.0
    total = 0.0
    count = 0
    for i in range(len(zone_centroids)):
        for j in range(i + 1, len(zone_centroids)):
            total += _color_distance_sq(zone_centroids[i], zone_centroids[j]) ** 0.5
            count += 1
    return total / count if count > 0 else 0.0


def _score_pattern(
    color_grid: List[List[Tuple[int, int, int]]],
    pattern_grid: List[List[int]],
) -> float:
    """Score = between_zone_distance / (1 + sqrt(within_zone_variance))."""
    zones = _zone_colors(color_grid, pattern_grid)
    within = sum(_within_zone_variance(c) for c in zones.values()) / len(zones)
    centroids = []
    for colors in zones.values():
        cr = sum(c[0] for c in colors) / len(colors)
        cg = sum(c[1] for c in colors) / len(colors)
        cb = sum(c[2] for c in colors) / len(colors)
        centroids.append((cr, cg, cb))
    between = _between_zone_distance(centroids)
    return between / (1.0 + within ** 0.5)


def _match_best_pattern(
    color_grid: List[List[Tuple[int, int, int]]],
) -> Tuple[str, int, float]:
    best_name = "solid"
    best_style = 0
    best_score = -1.0
    for name, info in PATTERNS.items():
        s = _score_pattern(color_grid, info["grid"])
        if s > best_score:
            best_score = s
            best_name = name
            best_style = info["style"]
    return best_name, best_style, best_score


# ---------------------------------------------------------------------------
# Palette builder
# ---------------------------------------------------------------------------


def _build_flag_palette(
    color_grid: List[List[Tuple[int, int, int]]],
    pattern_grid: List[List[int]],
) -> List[Tuple[int, int, int]]:
    """Build a 16-color palette with distinct colors per zone."""
    zones = _zone_colors(color_grid, pattern_grid)
    n_zones = len(zones)
    sorted_zones = sorted(zones.keys())

    # Rank colors per zone by frequency
    zone_ranked: Dict[int, List[Tuple[int, int, int]]] = {}
    for z in sorted_zones:
        freq = Counter(zones[z]).most_common()
        zone_ranked[z] = [color for color, _ in freq]

    # Assign colors greedily, avoiding duplicates where possible
    used: set = set()
    zone_color: Dict[int, Tuple[int, int, int]] = {}
    for z in sorted_zones:
        assigned = False
        for color in zone_ranked[z]:
            if color not in used:
                zone_color[z] = color
                used.add(color)
                assigned = True
                break
        if not assigned:
            zone_color[z] = zone_ranked[z][0]

    # Distribute 16 slots proportionally
    slots_per_zone = {}
    remaining = 16
    for i, z in enumerate(sorted_zones):
        if i == n_zones - 1:
            slots_per_zone[z] = remaining
        else:
            n = max(1, 16 // n_zones)
            slots_per_zone[z] = n
            remaining -= n

    palette = []
    for z in sorted_zones:
        palette.extend([zone_color[z]] * slots_per_zone[z])
    while len(palette) < 16:
        palette.append(palette[-1])
    return palette[:16]


# ---------------------------------------------------------------------------
# Logo analysis — spatial grid
# ---------------------------------------------------------------------------


def _crop_to_content(img: "Image.Image") -> "Image.Image":
    bbox = img.getbbox()
    return img.crop(bbox) if bbox else img


def _analyze_logo_grid(img: "Image.Image") -> Tuple[
    List[List[Tuple[int, int, int]]],
    List[Tuple[int, int, int]],
]:
    """Crop, quantize opaque pixels, build 4×4 color grid.

    Returns (color_grid, canonical_colors).
    """
    IMG_SIZE = 64
    ALPHA_THRESHOLD = 128
    COVERAGE_MIN = 0.25

    img = _crop_to_content(img)
    img = img.resize((IMG_SIZE, IMG_SIZE), Image.LANCZOS)

    px_data = list(img.getdata())
    opaque_pixels = [(r, g, b) for r, g, b, a in px_data if a > ALPHA_THRESHOLD]

    if not opaque_pixels:
        default = [(128, 128, 128)] * 2
        return [[(128, 128, 128)] * GRID_SIZE for _ in range(GRID_SIZE)], default

    # Quantize to 8 colors then simplify
    q_img = Image.new("RGB", (len(opaque_pixels), 1))
    q_img.putdata(opaque_pixels)
    quantized = q_img.quantize(colors=8, method=Image.Quantize.MEDIANCUT)
    raw_pal = quantized.getpalette()
    raw_colors = [
        (raw_pal[i * 3], raw_pal[i * 3 + 1], raw_pal[i * 3 + 2])
        for i in range(min(8, len(raw_pal) // 3))
    ]
    canonical = _simplify_palette(raw_colors)

    # Snap helper
    def snap(r, g, b):
        if max(r, g, b) < 60:
            return _nearest_color_index((0, 0, 0), canonical)
        if min(r, g, b) > 200:
            return _nearest_color_index((255, 255, 255), canonical)
        return _nearest_color_index((r, g, b), canonical)

    # Build grid: for each cell, pick best canonical color among opaque pixels.
    # If the secondary color has >30% presence, prefer it over the dominant.
    # This reveals interior fill colors hidden by surrounding outlines.
    cell_size = IMG_SIZE // GRID_SIZE
    pixels_per_cell = cell_size * cell_size
    color_grid: List[List[Optional[Tuple[int, int, int]]]] = []
    for row in range(GRID_SIZE):
        grid_row: List[Optional[Tuple[int, int, int]]] = []
        for col in range(GRID_SIZE):
            cell_indices = []
            for py in range(cell_size):
                for px in range(cell_size):
                    r, g, b, a = px_data[
                        (row * cell_size + py) * IMG_SIZE + (col * cell_size + px)
                    ]
                    if a > ALPHA_THRESHOLD:
                        cell_indices.append(snap(r, g, b))
            if len(cell_indices) >= pixels_per_cell * COVERAGE_MIN:
                counts = Counter(cell_indices)
                ranked = counts.most_common()
                if len(ranked) > 1 and ranked[1][1] / len(cell_indices) > 0.30:
                    grid_row.append(canonical[ranked[1][0]])
                else:
                    grid_row.append(canonical[ranked[0][0]])
            else:
                grid_row.append(None)
        color_grid.append(grid_row)

    # Fill background cells from nearest populated neighbor
    populated = [
        (r, c)
        for r in range(GRID_SIZE)
        for c in range(GRID_SIZE)
        if color_grid[r][c] is not None
    ]
    if not populated:
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                color_grid[r][c] = canonical[0]
    else:
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                if color_grid[r][c] is None:
                    best_dist = float("inf")
                    best_color = canonical[0]
                    for pr, pc in populated:
                        d = abs(r - pr) + abs(c - pc)
                        if d < best_dist:
                            best_dist = d
                            best_color = color_grid[pr][pc]
                    color_grid[r][c] = best_color

    return color_grid, canonical


# ---------------------------------------------------------------------------
# Shared image loading
# ---------------------------------------------------------------------------


def _download_logo(logo_url: str) -> Optional["Image.Image"]:
    """Download a logo PNG and return as RGBA PIL Image, or None on failure."""
    if not _PIL_AVAILABLE or not logo_url:
        return None
    try:
        resp = requests.get(logo_url, timeout=10)
        resp.raise_for_status()
        return Image.open(io.BytesIO(resp.content)).convert("RGBA")
    except Exception:
        return None


def _extract_canonical_colors(
    logo_url: str,
) -> Optional[Tuple["Image.Image", List[Tuple[int, int, int]]]]:
    """Download logo → crop → quantize → simplify.  Returns (img, canonical) or None."""
    img = _download_logo(logo_url)
    if img is None:
        return None
    cropped = _crop_to_content(img)
    resized = cropped.resize((64, 64), Image.LANCZOS)
    opaque = [(r, g, b) for r, g, b, a in resized.getdata() if a > 128]
    if not opaque:
        return None
    q_img = Image.new("RGB", (len(opaque), 1))
    q_img.putdata(opaque)
    quantized = q_img.quantize(colors=8, method=Image.Quantize.MEDIANCUT)
    raw_pal = quantized.getpalette()
    raw_colors = [
        (raw_pal[i * 3], raw_pal[i * 3 + 1], raw_pal[i * 3 + 2])
        for i in range(min(8, len(raw_pal) // 3))
    ]
    canonical = _simplify_palette(raw_colors)
    return img, canonical


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_logo_colors(
    logo_url: str,
) -> Tuple[Tuple[int, int, int], Tuple[int, int, int], Tuple[int, int, int]]:
    """Download a team logo and extract 3 dominant colors (primary, secondary, tertiary).

    Uses the same pipeline as flag analysis: crop to content, quantize to 8
    colors, simplify (merge near-blacks, snap near-whites, filter low-chroma
    anti-aliasing/decorative artifacts).

    Returns 3 RGB tuples.  Falls back to (white, black, gray) on error.
    """
    default = ((255, 255, 255), (0, 0, 0), (128, 128, 128))
    result = _extract_canonical_colors(logo_url)
    if result is None:
        return default
    _, canonical = result
    # Pad to 3 if needed
    while len(canonical) < 3:
        canonical.append(canonical[-1])
    return canonical[0], canonical[1], canonical[2]


def analyze_flag(
    logo_url: str,
) -> Optional[Tuple[int, List[Tuple[int, int, int]]]]:
    """Download a team logo and compute the best flag style + 16-color palette.

    Returns (style_byte, palette_16_rgb) or None if analysis fails.
    The palette is a list of 16 RGB tuples ready for BGR555 conversion.
    """
    result = _extract_canonical_colors(logo_url)
    if result is None:
        return None
    img, _ = result
    color_grid, canonical = _analyze_logo_grid(img)
    pattern_name, style, score = _match_best_pattern(color_grid)
    pattern_grid = PATTERNS[pattern_name]["grid"]
    palette = _build_flag_palette(color_grid, pattern_grid)
    return style, palette


def analyze_logo(
    logo_url: str,
) -> Optional[Tuple[
    Tuple[int, int, int],
    Tuple[int, int, int],
    Tuple[int, int, int],
    int,
    List[Tuple[int, int, int]],
]]:
    """Download a logo ONCE and return both jersey colors and flag data.

    Returns (primary, secondary, tertiary, flag_style, flag_palette_16)
    or None on failure.  This avoids downloading the logo twice.
    """
    result = _extract_canonical_colors(logo_url)
    if result is None:
        return None
    img, canonical = result

    # Jersey colors: top 3 canonical
    colors = list(canonical)
    while len(colors) < 3:
        colors.append(colors[-1])
    primary, secondary, tertiary = colors[0], colors[1], colors[2]

    # Flag analysis
    color_grid, _ = _analyze_logo_grid(img)
    pattern_name, style, score = _match_best_pattern(color_grid)
    pattern_grid = PATTERNS[pattern_name]["grid"]
    flag_palette = _build_flag_palette(color_grid, pattern_grid)

    return primary, secondary, tertiary, style, flag_palette
