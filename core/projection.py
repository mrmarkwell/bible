"""Zero-Dependency 2D Semantic Projection Engine for Scripture Embeddings.

This module provides high-performance dimensionality reduction from high-dimensional
vector embeddings (e.g. 768-dim float32/int8) into 2D canvas coordinates (x, y)
for interactive visualization in the Web UI and SVG export.

Algorithms implemented:
1. FastMap (Faloutsos & Lin, 1995): Non-linear, distance-preserving projection
   running in O(k * N) time via distant pivot pairs and the Law of Cosines.
   Sub-second execution across the entire biblical canon (~1,304 pericopes).
2. PCA (Principal Component Analysis): Deterministic power iteration on covariance
   structure finding the two top orthogonal variance eigenvectors.

Architectural invariants:
- Pure Python 3 standard library only (math, random, struct, typing, dataclasses).
- Zero external packages (no numpy, scipy, scikit-learn).
- Complies with ADR-003, ADR-051, and ADR-076.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
import random
import struct
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
)

# Canvas geometry defaults
DEFAULT_MAP_WIDTH = 1000.0
DEFAULT_MAP_HEIGHT = 700.0
DEFAULT_MAP_MARGIN = 55.0


@dataclass
class MapPoint:
    """Represents a 2D projected coordinate for a biblical pericope or verse unit."""

    entity_id: int
    human_ref: str
    title: str
    book_id: int
    book_name: str
    testament: str  # "OT" or "NT"
    genre: str
    x: float
    y: float
    tags: List[str] = field(default_factory=list)
    redemptive_summary: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert point to JSON-serializable dictionary."""
        return {
            "entity_id": self.entity_id,
            "human_ref": self.human_ref,
            "title": self.title,
            "book_id": self.book_id,
            "book_name": self.book_name,
            "testament": self.testament,
            "genre": self.genre,
            "x": round(self.x, 2),
            "y": round(self.y, 2),
            "tags": self.tags,
            "redemptive_summary": self.redemptive_summary or "",
        }


def dequantize_vector_bytes(raw_bytes: bytes, dim: Optional[int] = None) -> List[float]:
    """Dequantize packed signed int8 or float32 bytes into normalized float components."""
    if dim is None:
        # Infer from length: if multiple of 4 and not 768, float32; else int8
        if len(raw_bytes) % 4 == 0 and len(raw_bytes) != 768:
            dim = len(raw_bytes) // 4
            return list(struct.unpack(f"{dim}f", raw_bytes))
        dim = len(raw_bytes)

    if len(raw_bytes) == dim:
        # Int8 signed bytes
        unpacked = struct.unpack(f"{dim}b", raw_bytes)
        inv = 1.0 / 127.0
        vec = [b * inv for b in unpacked]
    else:
        # Float32 bytes
        float_count = len(raw_bytes) // 4
        vec = list(struct.unpack(f"{float_count}f", raw_bytes))

    # Ensure unit L2 normalization
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 1e-12:
        inv_norm = 1.0 / norm
        return [x * inv_norm for x in vec]
    return vec


def cosine_distance(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
    """Compute Euclidean chord distance on the unit hypersphere: sqrt(2 * (1 - cos_sim))."""
    dot = 0.0
    for a, b in zip(vec_a, vec_b):
        dot += a * b
    cos_sim = max(-1.0, min(1.0, dot))
    return math.sqrt(max(0.0, 2.0 * (1.0 - cos_sim)))


def normalize_coordinates(
    raw_coords: Sequence[Tuple[float, float]],
    width: float = DEFAULT_MAP_WIDTH,
    height: float = DEFAULT_MAP_HEIGHT,
    margin: float = DEFAULT_MAP_MARGIN,
) -> List[Tuple[float, float]]:
    """Normalize raw 2D coordinates into a target rectangular viewport [margin, width-margin]."""
    if not raw_coords:
        return []

    xs = [c[0] for c in raw_coords]
    ys = [c[1] for c in raw_coords]

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    range_x = max_x - min_x
    range_y = max_y - min_y

    avail_w = max(10.0, width - 2 * margin)
    avail_h = max(10.0, height - 2 * margin)

    normalized: List[Tuple[float, float]] = []
    for x, y in raw_coords:
        norm_x = margin + (0.5 * avail_w if range_x < 1e-9 else ((x - min_x) / range_x) * avail_w)
        norm_y = margin + (0.5 * avail_h if range_y < 1e-9 else ((y - min_y) / range_y) * avail_h)
        normalized.append((norm_x, norm_y))

    return normalized


# ==============================================================================
# FastMap Projector (Faloutsos & Lin, 1995)
# ==============================================================================

class FastMapProjector:
    """Projects high-dimensional vectors to 2D coordinates using FastMap.

    FastMap maps arbitrary metric spaces into Euclidean R^k in linear time.
    For k=2, it finds distant pivot points along 2 orthogonal hyperplanes
    and uses the Law of Cosines to calculate projection coordinates.
    """

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed

    def project(
        self,
        vectors: Sequence[Sequence[float]],
        width: float = DEFAULT_MAP_WIDTH,
        height: float = DEFAULT_MAP_HEIGHT,
        margin: float = DEFAULT_MAP_MARGIN,
    ) -> List[Tuple[float, float]]:
        """Project vectors to 2D (x, y) coordinates scaled to [width, height]."""
        n = len(vectors)
        if n == 0:
            return []
        if n == 1:
            return [(width / 2.0, height / 2.0)]
        if n == 2:
            return [(margin, height / 2.0), (width - margin, height / 2.0)]

        # Find 1st dimension pivots (p_a, p_b) using 3-hop furthest heuristic
        p_a = 0
        p_b = 1
        for _ in range(3):
            p_b = max(range(n), key=lambda i: cosine_distance(vectors[p_a], vectors[i]))
            p_a = max(range(n), key=lambda i: cosine_distance(vectors[p_b], vectors[i]))

        d_ab = cosine_distance(vectors[p_a], vectors[p_b])
        if d_ab < 1e-9:
            d_ab = 1e-6

        # Calculate 1st coordinate (x)
        d_ab_sq = d_ab * d_ab
        x_coords = [0.0] * n
        for i in range(n):
            d_ai = cosine_distance(vectors[p_a], vectors[i])
            d_bi = cosine_distance(vectors[p_b], vectors[i])
            x_coords[i] = (d_ai * d_ai + d_ab_sq - d_bi * d_bi) / (2.0 * d_ab)

        # Distance function on orthogonal hyperplane for 2nd dimension
        def dist_ortho(i: int, j: int) -> float:
            d_orig = cosine_distance(vectors[i], vectors[j])
            dx = x_coords[i] - x_coords[j]
            diff = d_orig * d_orig - dx * dx
            return math.sqrt(max(0.0, diff))

        # Find 2nd dimension pivots (p_c, p_d) on orthogonal hyperplane
        p_c = 0
        p_d = 1
        for _ in range(3):
            p_d = max(range(n), key=lambda i: dist_ortho(p_c, i))
            p_c = max(range(n), key=lambda i: dist_ortho(p_d, i))

        d_cd = dist_ortho(p_c, p_d)
        if d_cd < 1e-9:
            d_cd = 1e-6

        # Calculate 2nd coordinate (y)
        d_cd_sq = d_cd * d_cd
        y_coords = [0.0] * n
        for i in range(n):
            d_ci = dist_ortho(p_c, i)
            d_di = dist_ortho(p_d, i)
            y_coords[i] = (d_ci * d_ci + d_cd_sq - d_di * d_di) / (2.0 * d_cd)

        raw = list(zip(x_coords, y_coords))
        return normalize_coordinates(raw, width=width, height=height, margin=margin)


# ==============================================================================
# PCA Projector (Power Iteration)
# ==============================================================================

class PCAProjector:
    """Projects high-dimensional vectors to 2D coordinates using Power Iteration PCA."""

    def __init__(self, max_iter: int = 25, seed: int = 42) -> None:
        self.max_iter = max_iter
        self.seed = seed

    def project(
        self,
        vectors: Sequence[Sequence[float]],
        width: float = DEFAULT_MAP_WIDTH,
        height: float = DEFAULT_MAP_HEIGHT,
        margin: float = DEFAULT_MAP_MARGIN,
    ) -> List[Tuple[float, float]]:
        """Project vectors using top 2 principal components."""
        n = len(vectors)
        if n == 0:
            return []
        if n == 1:
            return [(width / 2.0, height / 2.0)]

        dim = len(vectors[0])
        # Mean center
        means = [sum(vectors[i][j] for i in range(n)) / n for j in range(dim)]
        z = [[vectors[i][j] - means[j] for j in range(dim)] for i in range(n)]

        # Helper: w = Z^T (Z v)
        def power_step(mat: List[List[float]], v: List[float]) -> List[float]:
            p = [sum(mat[i][j] * v[j] for j in range(dim)) for i in range(n)]
            w = [0.0] * dim
            for i in range(n):
                pi = p[i]
                if pi == 0.0:
                    continue
                row = mat[i]
                for j in range(dim):
                    w[j] += row[j] * pi
            return w

        rng = random.Random(self.seed)

        # 1st Principal Component
        v1 = [rng.gauss(0, 1) for _ in range(dim)]
        norm1 = math.sqrt(sum(x * x for x in v1))
        v1 = [x / norm1 for x in v1]

        for _ in range(self.max_iter):
            w = power_step(z, v1)
            norm = math.sqrt(sum(x * x for x in w))
            if norm < 1e-12:
                break
            v1 = [x / norm for x in w]

        # Projection onto 1st component
        p1 = [sum(z[i][j] * v1[j] for j in range(dim)) for i in range(n)]

        # Deflate matrix for 2nd component: Z2 = Z - p1 v1^T
        z2 = [[z[i][j] - p1[i] * v1[j] for j in range(dim)] for i in range(n)]

        v2 = [rng.gauss(0, 1) for _ in range(dim)]
        norm2 = math.sqrt(sum(x * x for x in v2))
        v2 = [x / norm2 for x in v2]

        for _ in range(self.max_iter):
            w = power_step(z2, v2)
            norm = math.sqrt(sum(x * x for x in w))
            if norm < 1e-12:
                break
            v2 = [x / norm for x in w]

        p2 = [sum(z2[i][j] * v2[j] for j in range(dim)) for i in range(n)]

        raw = list(zip(p1, p2))
        return normalize_coordinates(raw, width=width, height=height, margin=margin)


# ==============================================================================
# High-Level Projection API
# ==============================================================================

def project_embeddings(
    embeddings: Sequence[Union[Sequence[float], bytes]],
    method: str = "fastmap",
    width: float = DEFAULT_MAP_WIDTH,
    height: float = DEFAULT_MAP_HEIGHT,
    margin: float = DEFAULT_MAP_MARGIN,
    seed: int = 42,
) -> List[Tuple[float, float]]:
    """Project a sequence of float vectors or int8 bytes to 2D coordinates."""
    if not embeddings:
        return []

    # Unpack / dequantize if raw bytes
    parsed_vectors: List[List[float]] = []
    for item in embeddings:
        if isinstance(item, (bytes, bytearray)):
            parsed_vectors.append(dequantize_vector_bytes(bytes(item)))
        else:
            # Normalize float sequence
            norm = math.sqrt(sum(x * x for x in item))
            if norm > 1e-12:
                inv = 1.0 / norm
                parsed_vectors.append([x * inv for x in item])
            else:
                parsed_vectors.append(list(item))

    method_clean = method.strip().lower()
    if method_clean == "pca":
        projector = PCAProjector(seed=seed)
    else:
        projector = FastMapProjector(seed=seed)

    return projector.project(parsed_vectors, width=width, height=height, margin=margin)


# ==============================================================================
# Pure SVG Scatter Map Renderer
# ==============================================================================

GENRE_COLORS: Dict[str, str] = {
    "Law": "#4ECDC4",
    "History": "#45B7D1",
    "Wisdom": "#96CEB4",
    "Prophecy": "#FFEEAD",
    "Gospel": "#D4AF37",
    "Epistle": "#FF6B6B",
    "Apocalyptic": "#DDA0DD",
    "Other": "#A0AAB2",
}

TESTAMENT_COLORS: Dict[str, str] = {
    "OT": "#D4AF37",  # Sacred gold
    "NT": "#4ECDC4",  # Illuminated cyan
}


def get_genre_color(genre: str) -> str:
    """Return theme color for a literary genre."""
    for key, color in GENRE_COLORS.items():
        if key.lower() in genre.lower():
            return color
    return GENRE_COLORS["Other"]


def render_scatter_map_svg(
    points: Sequence[MapPoint],
    width: int = int(DEFAULT_MAP_WIDTH),
    height: int = int(DEFAULT_MAP_HEIGHT),
    title: str = "Scripture Semantic Scatter Map",
    color_mode: str = "testament",  # "testament" or "genre"
) -> str:
    """Render 2D semantic scatter points into a self-contained, Sacred-Modern vector SVG."""
    bg_color = "#0D0E11"
    grid_color = "#1E222B"
    text_color = "#E0E6ED"
    muted_color = "#7A889B"

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">',
        '  <defs>',
        '    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">',
        '      <feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="#000000" flood-opacity="0.6"/>',
        '    </filter>',
        '  </defs>',
        f'  <rect width="{width}" height="{height}" fill="{bg_color}"/>',
    ]

    # Grid background lines
    grid_step = 100
    for gx in range(50, width - 50, grid_step):
        lines.append(f'  <line x1="{gx}" y1="50" x2="{gx}" y2="{height - 50}" stroke="{grid_color}" stroke-dasharray="3,3" stroke-width="0.8"/>')
    for gy in range(50, height - 50, grid_step):
        lines.append(f'  <line x1="50" y1="{gy}" x2="{width - 50}" y2="{gy}" stroke="{grid_color}" stroke-dasharray="3,3" stroke-width="0.8"/>')

    # Title & Subtitle
    lines.append(f'  <text x="50" y="32" fill="{text_color}" font-family="system-ui, sans-serif" font-size="16" font-weight="bold">{title}</text>')
    lines.append(f'  <text x="{width - 50}" y="32" fill="{muted_color}" font-family="system-ui, sans-serif" font-size="12" text-anchor="end">{len(points)} Pericopes Arranged by Embedding Proximity</text>')

    # Render points
    for pt in points:
        color = TESTAMENT_COLORS.get(pt.testament, "#D4AF37") if color_mode == "testament" else get_genre_color(pt.genre)
        tip = f"{pt.human_ref}: {pt.title} ({pt.genre})"
        lines.append(
            f'  <circle cx="{pt.x:.1f}" cy="{pt.y:.1f}" r="4.0" fill="{color}" fill-opacity="0.85" stroke="#000000" stroke-width="0.5">'
            f'<title>{tip}</title></circle>'
        )

    # Legend at bottom right
    legend_y = height - 25
    if color_mode == "testament":
        lines.append(f'  <circle cx="{width - 250}" cy="{legend_y}" r="5" fill="{TESTAMENT_COLORS["OT"]}"/>')
        lines.append(f'  <text x="{width - 240}" y="{legend_y + 4}" fill="{muted_color}" font-family="system-ui, sans-serif" font-size="11">Old Testament</text>')
        lines.append(f'  <circle cx="{width - 140}" cy="{legend_y}" r="5" fill="{TESTAMENT_COLORS["NT"]}"/>')
        lines.append(f'  <text x="{width - 130}" y="{legend_y + 4}" fill="{muted_color}" font-family="system-ui, sans-serif" font-size="11">New Testament</text>')
    else:
        lx = width - 400
        for g_name, g_color in list(GENRE_COLORS.items())[:5]:
            lines.append(f'  <circle cx="{lx}" cy="{legend_y}" r="4" fill="{g_color}"/>')
            lines.append(f'  <text x="{lx + 8}" y="{legend_y + 3}" fill="{muted_color}" font-family="system-ui, sans-serif" font-size="10">{g_name}</text>')
            lx += 75

    lines.append('</svg>')
    return "\n".join(lines)
