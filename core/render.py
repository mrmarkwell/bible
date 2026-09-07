"""Visual Verse Slide Rendering Engine Abstraction (Dual-Backend).

Supports pure Python SVG vector rendering and system ImageMagick (magick/convert)
raster rendering (PNG/JPEG) for TV screensavers, presentations, and digital displays.
Strictly adheres to ADR-003 (Zero External Dependencies) and ADR-005 (TV Screensaver Slide Architecture).
"""

from __future__ import annotations

import dataclasses
import html
import math
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union


class RenderError(Exception):
    """Base exception for slide rendering errors."""
    pass


class ImageMagickNotFoundError(RenderError):
    """Raised when ImageMagick ('magick' or 'convert') binary is not found on system."""
    pass


# ---------------------------------------------------------------------------
# Slide Themes & Sacred-Modern Visual Palettes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SlideTheme:
    """Color palette and typographic styling for slide generation."""
    name: str
    background_color: str
    text_color: str
    citation_color: str
    accent_color: str
    pericope_color: str
    page_indicator_color: str
    font_family: str = "Georgia, 'Liberation Serif', 'DejaVu Serif', 'Times New Roman', serif"
    tag_pill_bg: str = "#222222"
    tag_pill_color: str = "#AAAAAA"
    description: str = ""


STANDARD_THEMES: Dict[str, SlideTheme] = {
    "oled_black": SlideTheme(
        name="oled_black",
        background_color="#000000",
        text_color="#FFFFFF",
        citation_color="#D4AF37",  # Illuminated Gold
        accent_color="#443818",
        pericope_color="#9E9E9E",
        page_indicator_color="#616161",
        tag_pill_bg="#1A1812",
        tag_pill_color="#D4AF37",
        description="Pure #000000 black for zero-power OLED displays, crisp white text, and illuminated gold citation",
    ),
    "charcoal": SlideTheme(
        name="charcoal",
        background_color="#121212",
        text_color="#EDEDED",
        citation_color="#C5A059",
        accent_color="#2C2C2C",
        pericope_color="#8E8E8E",
        page_indicator_color="#555555",
        tag_pill_bg="#1E1E1E",
        tag_pill_color="#C5A059",
        description="Refined warm dark mode (#121212) with muted gold citation (#C5A059) for reduced eye strain",
    ),
    "obsidian": SlideTheme(
        name="obsidian",
        background_color="#0D0E11",
        text_color="#F8F9FA",
        citation_color="#D4AF37",
        accent_color="#242731",
        pericope_color="#9CA3AF",
        page_indicator_color="#4B5563",
        tag_pill_bg="#171A21",
        tag_pill_color="#E2B170",
        description="Sacred-Modern abyssal obsidian (#0D0E11) with radiant Byzantine gold accents",
    ),
    "monastery": SlideTheme(
        name="monastery",
        background_color="#1A1715",
        text_color="#F5EFEB",
        citation_color="#E2B170",
        accent_color="#36302C",
        pericope_color="#A89F91",
        page_indicator_color="#635B52",
        tag_pill_bg="#26221E",
        tag_pill_color="#E2B170",
        description="Antique scriptorium dark bronze (#1A1715) with sepia-gold typography",
    ),
    "inverted": SlideTheme(
        name="inverted",
        background_color="#FFFFFF",
        text_color="#111111",
        citation_color="#7A5800",
        accent_color="#E5E5E5",
        pericope_color="#666666",
        page_indicator_color="#888888",
        tag_pill_bg="#F3F3F3",
        tag_pill_color="#7A5800",
        description="High-contrast clean white background (#FFFFFF) with dark charcoal text for daytime reading or printing",
    ),
    "parchment": SlideTheme(
        name="parchment",
        background_color="#FDFBF7",
        text_color="#2A2421",
        citation_color="#8C6226",
        accent_color="#E8E0D5",
        pericope_color="#6B5D55",
        page_indicator_color="#8C7D73",
        tag_pill_bg="#EFE8DD",
        tag_pill_color="#8C6226",
        description="Illuminated manuscript warm parchment (#FDFBF7) with antique ink typography",
    ),
}

# Aliases for CLI ergonomics
THEME_ALIASES: Dict[str, str] = {
    "black": "oled_black",
    "oled": "oled_black",
    "dark": "charcoal",
    "light": "inverted",
    "white": "inverted",
    "sepia": "parchment",
    "gold": "obsidian",
}


def get_theme(name_or_theme: Union[str, SlideTheme]) -> SlideTheme:
    """Resolve a theme name or return the theme instance."""
    if isinstance(name_or_theme, SlideTheme):
        return name_or_theme
    raw = str(name_or_theme).lower().strip().replace("-", "_")
    resolved_key = THEME_ALIASES.get(raw, raw)
    if resolved_key in STANDARD_THEMES:
        return STANDARD_THEMES[resolved_key]
    return STANDARD_THEMES["oled_black"]


# ---------------------------------------------------------------------------
# Resolutions & Dimensions
# ---------------------------------------------------------------------------

RESOLUTION_PRESETS: Dict[str, Tuple[int, int]] = {
    "4k": (3840, 2160),
    "uhd": (3840, 2160),
    "1080p": (1920, 1080),
    "fhd": (1920, 1080),
    "720p": (1280, 720),
    "hd": (1280, 720),
    "square_4k": (2160, 2160),
    "square": (1080, 1080),
    "instagram": (1080, 1080),
    "portrait_1080p": (1080, 1920),
}


def parse_resolution(resolution: Union[str, Tuple[int, int]]) -> Tuple[int, int]:
    """Parse resolution string (e.g. '4k', '1080p', '3840x2160') into (width, height)."""
    if isinstance(resolution, (tuple, list)) and len(resolution) == 2:
        return int(resolution[0]), int(resolution[1])
    raw = str(resolution).lower().strip()
    if raw in RESOLUTION_PRESETS:
        return RESOLUTION_PRESETS[raw]
    m = re.match(r"^(\d+)\s*[xX:,]\s*(\d+)$", raw)
    if m:
        return int(m.group(1)), int(m.group(2))
    return RESOLUTION_PRESETS["4k"]


def list_themes() -> List[SlideTheme]:
    """Return all standard slide theme configurations."""
    return list(STANDARD_THEMES.values())


# Preset metadata for listing and self-documentation: (width, height, aspect_ratio, description)
RESOLUTION_METADATA: Dict[str, Tuple[int, int, str, str]] = {
    "4k": (3840, 2160, "16:9", "Ultra High Definition (4K TV screensavers & displays, default)"),
    "1080p": (1920, 1080, "16:9", "Full High Definition (standard TVs, monitors, slides)"),
    "720p": (1280, 720, "16:9", "Standard HD (compact displays, smaller file sizes)"),
    "square": (1080, 1080, "1:1", "Standard square format (social media, album covers)"),
    "square_4k": (2160, 2160, "1:1", "Ultra high-res square format (high-DPI printing & art)"),
    "portrait_1080p": (1080, 1920, "9:16", "Vertical portrait format (smartphones, vertical TVs)"),
}


def list_resolutions() -> List[Tuple[str, int, int, str, str]]:
    """Return list of standard resolution presets: (preset_name, width, height, aspect, description)."""
    return [
        (name, w, h, aspect, desc)
        for name, (w, h, aspect, desc) in RESOLUTION_METADATA.items()
    ]


COLOR_NAMES: Dict[str, str] = {
    "gold": "#D4AF37",
    "byzantine_gold": "#D4AF37",
    "amber": "#F39C12",
    "yellow": "#FFD700",
    "white": "#FFFFFF",
    "black": "#000000",
    "charcoal": "#121212",
    "red": "#E74C3C",
    "crimson": "#E74C3C",
    "blue": "#4A90E2",
    "sapphire": "#4A90E2",
    "green": "#2ECC71",
    "emerald": "#2ECC71",
    "purple": "#9B51E0",
    "silver": "#A0AEC0",
    "gray": "#888888",
    "grey": "#888888",
    "bronze": "#CD7F32",
    "sepia": "#704214",
}


def normalize_color(color: Optional[str]) -> Optional[str]:
    """Normalize a hex, named, or CSS color string (e.g. 'gold' -> '#D4AF37', 'D4AF37' -> '#D4AF37')."""
    if not color:
        return None
    raw = str(color).strip()
    if not raw:
        return None

    # Check named colors
    lower_raw = raw.lower().replace("-", "_").replace(" ", "_")
    if lower_raw in COLOR_NAMES:
        return COLOR_NAMES[lower_raw]

    # Bare hex without '#'
    if re.match(r"^[0-9a-fA-F]{3}$", raw) or re.match(r"^[0-9a-fA-F]{6}$", raw) or re.match(r"^[0-9a-fA-F]{8}$", raw):
        return f"#{raw.upper()}"

    # Hex with '#'
    if re.match(r"^#[0-9a-fA-F]{3,8}$", raw):
        return raw

    # CSS color functions like rgb(...), rgba(...), hsl(...)
    return raw


def format_theme_table(styling: bool = True) -> str:
    """Format an aligned table of all available slide color themes."""
    headers = ("Theme", "Background", "Text Color", "Citation", "Description")
    rows = [
        (t.name, t.background_color, t.text_color, t.citation_color, t.description)
        for t in list_themes()
    ]

    col_widths = [len(h) for h in headers]
    for r in rows:
        for i in range(4):
            col_widths[i] = max(col_widths[i], len(r[i]))
    col_widths[4] = 60

    divider = "─" * (sum(col_widths[:4]) + col_widths[4] + 8)
    lines: List[str] = []

    header_str = (
        f"{headers[0]:<{col_widths[0]}}  "
        f"{headers[1]:<{col_widths[1]}}  "
        f"{headers[2]:<{col_widths[2]}}  "
        f"{headers[3]:<{col_widths[3]}}  "
        f"{headers[4]}"
    )

    if styling:
        lines.append(f"\033[1;33m{header_str}\033[0m")
        lines.append(f"\033[2m{divider}\033[0m")
        for r in rows:
            line = (
                f"\033[1;37m{r[0]:<{col_widths[0]}}\033[0m  "
                f"\033[36m{r[1]:<{col_widths[1]}}\033[0m  "
                f"\033[37m{r[2]:<{col_widths[2]}}\033[0m  "
                f"\033[33m{r[3]:<{col_widths[3]}}\033[0m  "
                f"{r[4]}"
            )
            lines.append(line)
    else:
        lines.append(header_str)
        lines.append(divider)
        for r in rows:
            line = (
                f"{r[0]:<{col_widths[0]}}  "
                f"{r[1]:<{col_widths[1]}}  "
                f"{r[2]:<{col_widths[2]}}  "
                f"{r[3]:<{col_widths[3]}}  "
                f"{r[4]}"
            )
            lines.append(line)

    return "\n".join(lines)


def format_resolution_table(styling: bool = True) -> str:
    """Format an aligned table of all standard slide display resolutions."""
    headers = ("Preset", "Dimensions", "Aspect", "Description & Target Display")
    rows = [
        (name, f"{w}x{h}", aspect, desc)
        for name, w, h, aspect, desc in list_resolutions()
    ]

    col_widths = [len(h) for h in headers]
    for r in rows:
        for i in range(3):
            col_widths[i] = max(col_widths[i], len(r[i]))
    col_widths[3] = 60

    divider = "─" * (sum(col_widths[:3]) + col_widths[3] + 6)
    lines: List[str] = []

    header_str = (
        f"{headers[0]:<{col_widths[0]}}  "
        f"{headers[1]:<{col_widths[1]}}  "
        f"{headers[2]:<{col_widths[2]}}  "
        f"{headers[3]}"
    )

    if styling:
        lines.append(f"\033[1;33m{header_str}\033[0m")
        lines.append(f"\033[2m{divider}\033[0m")
        for r in rows:
            line = (
                f"\033[1;37m{r[0]:<{col_widths[0]}}\033[0m  "
                f"\033[36m{r[1]:<{col_widths[1]}}\033[0m  "
                f"\033[33m{r[2]:<{col_widths[2]}}\033[0m  "
                f"{r[3]}"
            )
            lines.append(line)
        lines.append(f"\033[2mCustom resolution: pass 'WIDTHxHEIGHT' (e.g. 2560x1440, 1600x900)\033[0m")
    else:
        lines.append(header_str)
        lines.append(divider)
        for r in rows:
            line = (
                f"{r[0]:<{col_widths[0]}}  "
                f"{r[1]:<{col_widths[1]}}  "
                f"{r[2]:<{col_widths[2]}}  "
                f"{r[3]}"
            )
            lines.append(line)
        lines.append("Custom resolution: pass 'WIDTHxHEIGHT' (e.g. 2560x1440, 1600x900)")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Content & Configuration Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class SlideContent:
    """The theological content to be presented on the verse slide."""
    text: str
    citation: str = ""
    translation: str = "WEB"
    pericope_title: Optional[str] = None
    page_indicator: Optional[str] = None  # e.g., "1 / 3"
    tags: List[str] = field(default_factory=list)


@dataclass
class RenderConfig:
    """Slide rendering parameters, typography, layout, and output formats."""
    width: int = 3840
    height: int = 2160
    theme: Union[str, SlideTheme] = "oled_black"
    safe_area_pct: float = 0.15  # 15% TV safe area margin
    font_family: Optional[str] = None
    font_size: Optional[float] = None  # None = auto-calculate
    min_font_size: Optional[float] = None  # None = auto-derive from resolution
    max_font_size: Optional[float] = None  # None = auto-derive from resolution
    line_spacing: float = 1.5
    text_align: str = "center"  # "center", "left", "right"
    citation_style: str = "below"  # "below", "smallcaps", "none"
    citation_color: Optional[str] = None  # Custom override for citation text color
    accent_color: Optional[str] = None  # Custom override for accent divider rule color
    optical_center_pct: float = 0.45  # 45% baseline for human optical vertical center
    balance_lines: bool = True  # Balanced word wrapping to eliminate orphan words / minimize line length variance
    show_accent_rule: bool = True
    show_tags: bool = False
    backend: str = "auto"  # "auto", "imagemagick", "svg"
    output_format: str = "png"  # "png", "jpg", "jpeg", "svg"
    jpeg_quality: int = 95
    dpi: int = 300

    def resolved_theme(self) -> SlideTheme:
        return get_theme(self.theme)


@dataclass
class RenderResult:
    """The output of a slide rendering operation."""
    data: bytes
    mime_type: str
    format: str
    width: int
    height: int
    backend: str
    file_path: Optional[str] = None

    def save(self, destination: Union[str, Path]) -> Path:
        """Write the rendered bytes to a local file path."""
        p = Path(destination)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(self.data)
        self.file_path = str(p)
        return p


@dataclass
class PaginationConfig:
    """Configuration parameters for multi-slide passage pagination and readability thresholds."""
    enabled: bool = True
    mode: str = "auto"  # "auto", "verses", "chars", "lines", "always", "disabled"
    max_lines_per_slide: Optional[int] = None  # maximum wrapped lines before splitting (default: 8)
    max_chars_per_slide: Optional[int] = None  # maximum characters before splitting (default: 420)
    max_verses_per_slide: Optional[int] = None  # maximum verses before splitting
    min_readability_font_size: Optional[float] = None  # in pt; if auto font size would drop below this, paginate
    indicator_format: str = "{page} / {total}"  # format string for multi-slide indicator (e.g. "1 / 3")
    show_indicator: bool = True  # whether to display indicator (e.g. "1 / 3") when total > 1
    sub_citations: bool = True  # whether to generate specific sub-verse citations per slide (e.g. "Romans 8:28-30")
    keep_parent_citation: bool = False  # preserve parent passage citation across all slides
    repeat_pericope_title: bool = False  # repeat pericope title on every slide (default: first slide only)


# ---------------------------------------------------------------------------
# Layout & Typography Calculations
# ---------------------------------------------------------------------------

@dataclass
class LayoutBox:
    """Calculated layout geometry for text blocks within the slide canvas."""
    safe_x: float
    safe_y: float
    safe_w: float
    safe_h: float
    font_size: float
    line_height: float
    wrapped_lines: List[str]
    body_height: float
    citation_font_size: float
    pericope_font_size: float
    total_content_height: float
    start_y: float


def estimate_char_width(char: str, font_size: float) -> float:
    """Estimate character advance width for typical serif fonts (Georgia/Times)."""
    if char in "ijlI|':;.,! ":
        return font_size * 0.30
    elif char in "mwMW_@#%":
        return font_size * 0.85
    elif char.isupper():
        return font_size * 0.65
    return font_size * 0.48


def wrap_text_to_width(text: str, max_width: float, font_size: float) -> List[str]:
    """Wrap text to fit within max_width using greedy first-fit word boundaries."""
    paragraphs = text.replace("\r\n", "\n").split("\n")
    all_lines: List[str] = []

    for para in paragraphs:
        words = para.split()
        if not words:
            all_lines.append("")
            continue

        current_line: List[str] = []
        current_w = 0.0

        for word in words:
            word_w = sum(estimate_char_width(c, font_size) for c in word)
            space_w = estimate_char_width(" ", font_size)

            if not current_line:
                current_line.append(word)
                current_w = word_w
            elif current_w + space_w + word_w <= max_width:
                current_line.append(word)
                current_w += space_w + word_w
            else:
                all_lines.append(" ".join(current_line))
                current_line = [word]
                current_w = word_w

        if current_line:
            all_lines.append(" ".join(current_line))

    return all_lines


def wrap_text_balanced(text: str, max_width: float, font_size: float) -> List[str]:
    """Wrap text with balanced line lengths (raggedness & orphan/widow minimization).

    Uses dynamic programming cost minimization (similar to Knuth-Plass line breaking)
    to balance line widths, preventing single-word orphan trailing lines and jarring
    raggedness on wide landscape presentation canvases.
    """
    paragraphs = text.replace("\r\n", "\n").split("\n")
    all_lines: List[str] = []
    space_w = estimate_char_width(" ", font_size)

    for para in paragraphs:
        words = para.split()
        if not words:
            all_lines.append("")
            continue

        n = len(words)
        word_widths = [sum(estimate_char_width(c, font_size) for c in w) for w in words]

        # Quick check: does the entire paragraph fit on a single line?
        total_single_line_w = sum(word_widths) + (n - 1) * space_w
        if total_single_line_w <= max_width:
            all_lines.append(" ".join(words))
            continue

        # If any single word exceeds max_width, fall back to standard wrap
        if any(w_w > max_width for w_w in word_widths):
            all_lines.extend(wrap_text_to_width(para, max_width, font_size))
            continue

        # Dynamic programming table for optimal line breaking:
        # dp[i] = minimum cost to break words[i:]
        # best_split[i] = index j where the line words[i:j] breaks
        inf = float("inf")
        dp = [inf] * (n + 1)
        best_split = [n] * (n + 1)
        dp[n] = 0.0

        for i in range(n - 1, -1, -1):
            line_w = 0.0
            for j in range(i + 1, n + 1):
                word_idx = j - 1
                if j == i + 1:
                    line_w = word_widths[word_idx]
                else:
                    line_w += space_w + word_widths[word_idx]

                if line_w > max_width:
                    break

                slack = max_width - line_w

                if j == n:
                    # Last line penalty:
                    # Penalize orphan single-word last line if paragraph had multiple lines
                    if i > 0 and (j - i) == 1:
                        cost = (slack * 0.2) ** 2 + (max_width * 0.8) ** 2
                    else:
                        # Moderate slack on last line is normal, but still discourage excessive slack
                        cost = (slack * 0.35) ** 2
                else:
                    # Internal lines: square of slack to heavily penalize short lines
                    cost = slack ** 2
                    # Additional penalty for single-word internal lines
                    if (j - i) == 1:
                        cost += (max_width * 1.5) ** 2

                total_cost = cost + dp[j]
                if total_cost < dp[i]:
                    dp[i] = total_cost
                    best_split[i] = j

        # If no valid DP path was found (e.g. extreme constraints), fallback
        if dp[0] == inf:
            all_lines.extend(wrap_text_to_width(para, max_width, font_size))
            continue

        # Reconstruct lines from best_split
        idx = 0
        while idx < n:
            next_idx = best_split[idx]
            if next_idx <= idx:
                next_idx = idx + 1
            all_lines.append(" ".join(words[idx:next_idx]))
            idx = next_idx

    return all_lines


def calculate_slide_layout(content: SlideContent, config: RenderConfig) -> LayoutBox:
    """Calculate geometric bounding boxes, optimal font sizes, and vertical centering.

    Auto-computes font scaling via binary search clamping between min and max bounds,
    balances line lengths, and positions text relative to the human optical vertical center (~45%).
    """
    w = config.width
    h = config.height
    safe_pct = max(0.05, min(0.35, config.safe_area_pct))

    safe_x = w * safe_pct
    safe_y = h * safe_pct
    safe_w = w * (1.0 - 2.0 * safe_pct)
    safe_h = h * (1.0 - 2.0 * safe_pct)

    scale_factor = w / 3840.0
    default_min_pt = max(16.0, 32.0 * scale_factor)
    default_max_pt = max(28.0, 112.0 * scale_factor)

    min_font_size = config.min_font_size if config.min_font_size is not None else default_min_pt
    max_font_size = config.max_font_size if config.max_font_size is not None else default_max_pt
    if min_font_size > max_font_size:
        min_font_size, max_font_size = max_font_size, min_font_size

    def wrap_fn(txt: str, pt: float) -> List[str]:
        if config.balance_lines:
            return wrap_text_balanced(txt, safe_w, pt)
        return wrap_text_to_width(txt, safe_w, pt)

    def total_height_at_font_size(pt: float) -> Tuple[float, List[str]]:
        lines = wrap_fn(content.text.strip(), pt)
        line_spacing = config.line_spacing if config.line_spacing > 0 else 1.5
        line_h = pt * line_spacing
        b_height = len(lines) * line_h

        cit_pt = max(24.0 * scale_factor, pt * 0.48)
        peri_pt = max(20.0 * scale_factor, pt * 0.40)

        accent_spacing = 40.0 * scale_factor if config.show_accent_rule else 20.0 * scale_factor
        cit_block_h = (cit_pt * 1.5) + accent_spacing if (content.citation or content.translation) else 0.0
        peri_block_h = (peri_pt * 1.6) + (24.0 * scale_factor) if content.pericope_title else 0.0

        return b_height + cit_block_h + peri_block_h, lines

    if config.font_size is not None and config.font_size > 0:
        font_size = config.font_size
        total_h, wrapped = total_height_at_font_size(font_size)
    else:
        # Binary search for optimal font size fitting within safe_h
        clean_text = content.text.strip()
        total_chars = len(clean_text)

        # Establish heuristic maximum target based on text volume to maintain editorial elegance
        if total_chars < 60:
            target_pt = 96.0 * scale_factor
        elif total_chars < 140:
            target_pt = 76.0 * scale_factor
        elif total_chars < 260:
            target_pt = 62.0 * scale_factor
        elif total_chars < 450:
            target_pt = 50.0 * scale_factor
        elif total_chars < 750:
            target_pt = 42.0 * scale_factor
        else:
            target_pt = min_font_size

        upper_bound = min(max_font_size, max(min_font_size, target_pt))

        # Check if upper bound fits comfortably
        h_upper, lines_upper = total_height_at_font_size(upper_bound)
        if h_upper <= safe_h:
            # Upper bound fits within safe area
            font_size = round(upper_bound, 2)
            total_h = h_upper
            wrapped = lines_upper
        else:
            # Upper bound exceeds safe_h; binary search down towards min_font_size
            low = min_font_size
            high = upper_bound
            best_pt = min_font_size
            best_h, best_lines = total_height_at_font_size(min_font_size)

            for _ in range(12):
                if (high - low) < 0.5:
                    break
                mid = (low + high) / 2.0
                cand_h, cand_lines = total_height_at_font_size(mid)
                if cand_h <= safe_h:
                    best_pt = mid
                    best_lines = cand_lines
                    best_h = cand_h
                    low = mid
                else:
                    high = mid

            font_size = round(best_pt, 2)
            total_h = best_h
            wrapped = best_lines

    line_spacing = config.line_spacing if config.line_spacing > 0 else 1.5
    line_h = font_size * line_spacing
    body_h = len(wrapped) * line_h

    citation_pt = max(24.0 * scale_factor, font_size * 0.48)
    pericope_pt = max(20.0 * scale_factor, font_size * 0.40)

    # Optical vertical centering (~45% baseline)
    optical_pct = config.optical_center_pct
    if optical_pct <= 0.0 or optical_pct >= 1.0:
        optical_pct = 0.45

    optical_y = h * optical_pct
    start_y = optical_y - (total_h / 2.0)

    # Constrain within safe boundaries
    if start_y < safe_y:
        start_y = safe_y
    elif start_y + total_h > safe_y + safe_h:
        start_y = max(safe_y, safe_y + safe_h - total_h)

    return LayoutBox(
        safe_x=safe_x,
        safe_y=safe_y,
        safe_w=safe_w,
        safe_h=safe_h,
        font_size=font_size,
        line_height=line_h,
        wrapped_lines=wrapped,
        body_height=body_h,
        citation_font_size=citation_pt,
        pericope_font_size=pericope_pt,
        total_content_height=total_h,
        start_y=start_y,
    )


# ---------------------------------------------------------------------------
# ImageMagick Binary Detection & Subprocess Wrapper
# ---------------------------------------------------------------------------

_CACHED_IMAGEMAGICK_BIN: Optional[str] = None
_IMAGEMAGICK_CHECKED: bool = False


def find_imagemagick_binary() -> Optional[str]:
    """Locate ImageMagick binary ('magick' or legacy 'convert') on system PATH."""
    global _CACHED_IMAGEMAGICK_BIN, _IMAGEMAGICK_CHECKED
    if _IMAGEMAGICK_CHECKED:
        return _CACHED_IMAGEMAGICK_BIN

    bin_path = shutil.which("magick") or shutil.which("convert")
    _CACHED_IMAGEMAGICK_BIN = bin_path
    _IMAGEMAGICK_CHECKED = True
    return bin_path


def is_imagemagick_available() -> bool:
    """Return True if ImageMagick is installed and executable."""
    return find_imagemagick_binary() is not None


def detect_imagemagick() -> Tuple[bool, Optional[str]]:
    """Return tuple of (is_available, binary_path)."""
    p = find_imagemagick_binary()
    return (p is not None, p)


def get_available_backends() -> List[str]:
    """Return list of supported rendering backends on current machine."""
    backends = ["svg"]
    if is_imagemagick_available():
        backends.insert(0, "imagemagick")
    return backends


# ---------------------------------------------------------------------------
# Pure Python SVG Slide Generator (Vector Backend)
# ---------------------------------------------------------------------------

class SvgSlideRenderer:
    """Generates standalone pure vector SVG verse slides (Zero External Dependencies)."""

    def render_svg_markup(self, content: SlideContent, config: RenderConfig) -> str:
        """Construct well-formed, valid SVG markup for the slide."""
        theme = config.resolved_theme()
        layout = calculate_slide_layout(content, config)

        w = config.width
        h = config.height
        font_family = config.font_family or theme.font_family

        if config.text_align == "left":
            text_x = layout.safe_x
            anchor = "start"
            rule_x1 = layout.safe_x
            rule_x2 = layout.safe_x + (layout.safe_w * 0.35)
        elif config.text_align == "right":
            text_x = layout.safe_x + layout.safe_w
            anchor = "end"
            rule_x1 = (layout.safe_x + layout.safe_w) - (layout.safe_w * 0.35)
            rule_x2 = layout.safe_x + layout.safe_w
        else:  # center
            text_x = w / 2.0
            anchor = "middle"
            rule_half = layout.safe_w * 0.18
            rule_x1 = (w / 2.0) - rule_half
            rule_x2 = (w / 2.0) + rule_half

        cit_color = normalize_color(config.citation_color) or theme.citation_color
        acc_color = normalize_color(config.accent_color) or theme.accent_color

        lines: List[str] = [
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
            "  <defs>",
            '    <style type="text/css">',
            f'      .verse-text {{ font-family: {font_family}; font-size: {layout.font_size:.2f}px; '
            f'fill: {theme.text_color}; text-anchor: {anchor}; }}',
            f'      .citation-text {{ font-family: {font_family}; font-size: {layout.citation_font_size:.2f}px; '
            f'fill: {cit_color}; text-anchor: {anchor}; font-weight: 600; letter-spacing: 0.08em; '
            f'{"font-variant: all-small-caps; text-transform: uppercase;" if config.citation_style == "smallcaps" else ""} }}',
            f'      .pericope-text {{ font-family: {font_family}; font-size: {layout.pericope_font_size:.2f}px; '
            f'fill: {theme.pericope_color}; text-anchor: {anchor}; text-transform: uppercase; letter-spacing: 0.12em; }}',
            f'      .indicator-text {{ font-family: {font_family}; font-size: {layout.pericope_font_size * 0.85:.2f}px; '
            f'fill: {theme.page_indicator_color}; text-anchor: middle; }}',
            f'      .accent-rule {{ stroke: {acc_color}; stroke-width: {max(1.5, w / 1920.0):.1f}; stroke-linecap: round; }}',
            "    </style>",
            "  </defs>",
            f'  <!-- Canvas Background -->',
            f'  <rect width="{w}" height="{h}" fill="{theme.background_color}" />',
        ]

        current_y = layout.start_y

        # 1. Pericope Section Header (if present)
        if content.pericope_title:
            current_y += layout.pericope_font_size
            escaped_pericope = html.escape(content.pericope_title.upper())
            lines.append(f'  <text class="pericope-text" x="{text_x:.2f}" y="{current_y:.2f}">{escaped_pericope}</text>')
            current_y += layout.pericope_font_size * 1.5

        # 2. Scripture Passage Body Lines
        lines.append('  <!-- Scripture Passage Body -->')
        lines.append('  <g class="verse-text">')
        for line in layout.wrapped_lines:
            current_y += layout.font_size
            escaped_line = html.escape(line)
            lines.append(f'    <text x="{text_x:.2f}" y="{current_y:.2f}">{escaped_line}</text>')
            current_y += layout.line_height - layout.font_size
        lines.append('  </g>')

        # 3. Decorative Accent Divider Rule (if enabled)
        if config.show_accent_rule and (content.citation or content.translation):
            rule_y = current_y + (layout.citation_font_size * 0.75)
            lines.append(f'  <!-- Accent Rule -->')
            lines.append(f'  <line class="accent-rule" x1="{rule_x1:.2f}" y1="{rule_y:.2f}" x2="{rule_x2:.2f}" y2="{rule_y:.2f}" />')
            current_y = rule_y + (layout.citation_font_size * 0.75)
        else:
            current_y += layout.citation_font_size * 0.5

        # 4. Scripture Citation & Translation
        citation_str = content.citation.strip()
        if content.translation and content.translation != "NONE":
            if citation_str:
                citation_str = f"{citation_str}  ({content.translation})"
            else:
                citation_str = f"({content.translation})"

        if citation_str and config.citation_style != "none":
            current_y += layout.citation_font_size
            escaped_citation = html.escape(citation_str)
            lines.append(f'  <!-- Canonical Citation -->')
            lines.append(f'  <text class="citation-text" x="{text_x:.2f}" y="{current_y:.2f}">{escaped_citation}</text>')

        # 5. Multi-Slide Page Indicator (e.g. "1 / 3")
        if content.page_indicator:
            ind_y = h - (h * (config.safe_area_pct * 0.60))
            escaped_ind = html.escape(content.page_indicator)
            lines.append(f'  <!-- Multi-Slide Page Indicator -->')
            lines.append(f'  <text class="indicator-text" x="{w / 2.0:.2f}" y="{ind_y:.2f}">{escaped_ind}</text>')

        # 6. Semantic Tags (if enabled)
        if config.show_tags and content.tags:
            tag_y = h - (h * (config.safe_area_pct * 0.85))
            tag_str = " · ".join(content.tags)
            escaped_tags = html.escape(tag_str)
            lines.append(f'  <!-- Semantic Tags -->')
            lines.append(f'  <text class="indicator-text" x="{w / 2.0:.2f}" y="{tag_y:.2f}">{escaped_tags}</text>')

        lines.append("</svg>")
        return "\n".join(lines)

    def render(self, content: SlideContent, config: RenderConfig) -> RenderResult:
        """Render SVG markup and return RenderResult."""
        markup = self.render_svg_markup(content, config)
        data = markup.encode("utf-8")
        return RenderResult(
            data=data,
            mime_type="image/svg+xml",
            format="svg",
            width=config.width,
            height=config.height,
            backend="svg",
        )


# ---------------------------------------------------------------------------
# ImageMagick Slide Renderer (Raster Backend)
# ---------------------------------------------------------------------------

class ImageMagickSlideRenderer:
    """Renders raster slides (PNG/JPEG) via system ImageMagick ('magick' or 'convert')."""

    def __init__(self, binary_path: Optional[str] = None):
        self.binary_path = binary_path or find_imagemagick_binary()
        if not self.binary_path:
            raise ImageMagickNotFoundError(
                "ImageMagick binary ('magick' or 'convert') not found on system. "
                "Ensure ImageMagick is installed or use vector SVG backend."
            )
        self.svg_renderer = SvgSlideRenderer()

    def render(self, content: SlideContent, config: RenderConfig) -> RenderResult:
        """Render SVG vector markup and rasterize to PNG or JPEG via ImageMagick."""
        fmt = config.output_format.lower()
        if fmt == "jpeg":
            fmt = "jpg"
        if fmt not in ("png", "jpg"):
            fmt = "png"

        svg_markup = self.svg_renderer.render_svg_markup(content, config)

        with tempfile.TemporaryDirectory(prefix="bible_slide_") as tmpdir:
            svg_file = Path(tmpdir) / "slide.svg"
            out_file = Path(tmpdir) / f"slide.{fmt}"

            svg_file.write_text(svg_markup, encoding="utf-8")

            cmd = [self.binary_path]

            if config.dpi > 0:
                cmd.extend(["-density", str(config.dpi)])

            cmd.append(str(svg_file))

            if fmt == "jpg":
                cmd.extend(["-quality", str(max(10, min(100, config.jpeg_quality)))])

            cmd.append(str(out_file))

            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=60,
                )
            except subprocess.TimeoutExpired as exc:
                raise RenderError(f"ImageMagick rasterization timed out: {exc}") from exc
            except OSError as exc:
                raise RenderError(f"Failed to execute ImageMagick binary '{self.binary_path}': {exc}") from exc

            if proc.returncode != 0:
                raise RenderError(
                    f"ImageMagick failed (code {proc.returncode}): {proc.stderr.strip()}"
                )

            if not out_file.exists() or out_file.stat().st_size == 0:
                raise RenderError(f"ImageMagick produced empty or missing output file: {out_file}")

            raster_data = out_file.read_bytes()

        mime = "image/png" if fmt == "png" else "image/jpeg"
        return RenderResult(
            data=raster_data,
            mime_type=mime,
            format=fmt,
            width=config.width,
            height=config.height,
            backend="imagemagick",
        )


# ---------------------------------------------------------------------------
# Slide Rendering Engine Facade & Factory
# ---------------------------------------------------------------------------

class SlideRenderEngine:
    """Unified rendering facade providing seamless dual-backend slide generation."""

    def __init__(self):
        self.svg_renderer = SvgSlideRenderer()
        self._im_renderer: Optional[ImageMagickSlideRenderer] = None

    def _get_im_renderer(self) -> ImageMagickSlideRenderer:
        if self._im_renderer is None:
            self._im_renderer = ImageMagickSlideRenderer()
        return self._im_renderer

    def render(self, content: SlideContent, config: Optional[RenderConfig] = None) -> RenderResult:
        """Render a scripture slide according to configuration and available backends."""
        if config is None:
            config = RenderConfig()

        fmt = config.output_format.lower()
        backend = config.backend.lower()

        if fmt == "svg" or backend == "svg":
            return self.svg_renderer.render(content, config)

        if backend == "imagemagick":
            return self._get_im_renderer().render(content, config)

        if is_imagemagick_available():
            try:
                return self._get_im_renderer().render(content, config)
            except ImageMagickNotFoundError:
                pass

        return self.svg_renderer.render(content, config)

    def render_to_file(
        self,
        content: SlideContent,
        destination: Union[str, Path],
        config: Optional[RenderConfig] = None,
    ) -> RenderResult:
        """Render slide and write directly to file destination."""
        dest_path = Path(destination)
        if config is None:
            config = RenderConfig()

        ext = dest_path.suffix.lower().lstrip(".")
        if ext in ("svg", "png", "jpg", "jpeg") and config.output_format == "png":
            config = dataclasses.replace(config, output_format=ext)

        result = self.render(content, config)
        result.save(dest_path)
        return result

    def render_sequence(
        self,
        contents: List[SlideContent],
        config: Optional[RenderConfig] = None,
    ) -> List[RenderResult]:
        """Render a sequence of multi-slide contents into a list of RenderResults."""
        if config is None:
            config = RenderConfig()
        return [self.render(c, config) for c in contents]

    def render_sequence_to_files(
        self,
        contents: List[SlideContent],
        destination: Union[str, Path],
        config: Optional[RenderConfig] = None,
    ) -> List[RenderResult]:
        """Render a multi-slide sequence, writing numbered files if multiple slides.

        If len(contents) <= 1:
            writes to destination directly (e.g. 'slide.png').
        If len(contents) > 1:
            writes numbered files (e.g. 'slide_1.png', 'slide_2.png', 'slide_3.png').
        """
        dest_path = Path(destination)
        if config is None:
            config = RenderConfig()

        ext = dest_path.suffix.lower().lstrip(".")
        if ext in ("svg", "png", "jpg", "jpeg") and config.output_format == "png":
            config = dataclasses.replace(config, output_format=ext)

        if len(contents) <= 1:
            c = contents[0] if contents else SlideContent(text="")
            res = self.render_to_file(c, dest_path, config)
            return [res]

        dest_dir = dest_path.parent
        dest_dir.mkdir(parents=True, exist_ok=True)
        stem = dest_path.stem
        fmt = config.output_format.lower()
        suffix = f".{fmt}" if fmt else dest_path.suffix

        results: List[RenderResult] = []
        total = len(contents)
        for i, c in enumerate(contents, start=1):
            idx_str = f"_{i:02d}" if total >= 10 else f"_{i}"
            page_path = dest_dir / f"{stem}{idx_str}{suffix}"
            res = self.render_to_file(c, page_path, config)
            results.append(res)

        return results

    def render_sequence_to_dir(
        self,
        contents: List[SlideContent],
        destination_dir: Union[str, Path],
        file_prefix: str = "slide",
        config: Optional[RenderConfig] = None,
    ) -> List[RenderResult]:
        """Render a multi-slide sequence into a target directory."""
        dest_dir = Path(destination_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        if config is None:
            config = RenderConfig()

        fmt = config.output_format.lower()
        suffix = f".{fmt}" if fmt else ".png"
        results: List[RenderResult] = []
        total = len(contents)
        for i, c in enumerate(contents, start=1):
            idx_str = f"_{i:02d}" if total >= 10 else f"_{i}"
            page_path = dest_dir / f"{file_prefix}{idx_str}{suffix}"
            res = self.render_to_file(c, page_path, config)
            results.append(res)

        return results


_DEFAULT_ENGINE: Optional[SlideRenderEngine] = None


def get_default_engine() -> SlideRenderEngine:
    global _DEFAULT_ENGINE
    if _DEFAULT_ENGINE is None:
        _DEFAULT_ENGINE = SlideRenderEngine()
    return _DEFAULT_ENGINE


def _format_sub_citation(
    first_v: Any,
    last_v: Any,
    parent_ref: Optional[Any],
    keep_parent: bool = False,
) -> str:
    """Format precise sub-verse citation for a slide chunk (e.g. 'Romans 8:28-30')."""
    parent_str = parent_ref.format() if hasattr(parent_ref, "format") else str(parent_ref or "").strip()
    if keep_parent or not parent_ref:
        return parent_str

    try:
        from core.reference import Reference
        if isinstance(parent_ref, Reference) and hasattr(parent_ref, "book"):
            book = parent_ref.book
            ch1 = getattr(first_v, "chapter", None)
            v1 = getattr(first_v, "verse", getattr(first_v, "verse_number", None))
            ch2 = getattr(last_v, "chapter", None)
            v2 = getattr(last_v, "verse", getattr(last_v, "verse_number", None))
            if ch1 is not None and v1 is not None and ch2 is not None and v2 is not None:
                if ch1 == ch2:
                    if v1 == v2:
                        sub = Reference(book, start_chapter=ch1, start_verse=v1)
                    else:
                        sub = Reference(book, start_chapter=ch1, start_verse=v1, end_chapter=ch1, end_verse=v2)
                else:
                    sub = Reference(book, start_chapter=ch1, start_verse=v1, end_chapter=ch2, end_verse=v2)
                return sub.format()
    except Exception:
        pass

    return parent_str


def _check_verses_fit(
    candidate_verses: List[Any],
    config: RenderConfig,
    pagination: PaginationConfig,
    scale_factor: float,
) -> bool:
    """Check if candidate list of verses fits within readability limits."""
    if pagination.max_verses_per_slide is not None and len(candidate_verses) > pagination.max_verses_per_slide:
        return False

    if pagination.mode == "verses":
        return True

    min_font = pagination.min_readability_font_size if pagination.min_readability_font_size is not None else max(24.0, 48.0 * scale_factor)
    max_lines = pagination.max_lines_per_slide if pagination.max_lines_per_slide is not None else 8
    max_chars = pagination.max_chars_per_slide if pagination.max_chars_per_slide is not None else 420

    txt = " ".join(v.text.strip() for v in candidate_verses if getattr(v, "text", None))
    if len(txt) > max_chars:
        return False

    test_content = SlideContent(text=txt)
    layout = calculate_slide_layout(test_content, config)
    if len(layout.wrapped_lines) > max_lines:
        return False
    if layout.font_size < min_font:
        return False
    return True


def paginate_verses(
    verses: List[Any],
    parent_ref: Optional[Any] = None,
    config: Optional[RenderConfig] = None,
    pagination: Optional[PaginationConfig] = None,
    pericope_title: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> List[SlideContent]:
    """Partition a list of verses into paginated SlideContent objects for optimal readability."""
    if not verses:
        return []

    if pagination is None:
        pagination = PaginationConfig()
    if config is None:
        config = RenderConfig()

    parent_cit = parent_ref.format() if hasattr(parent_ref, "format") else str(parent_ref or "").strip()
    used_id = getattr(verses[0], "translation_id", "WEB") if verses else "WEB"

    if not pagination.enabled or pagination.mode == "disabled":
        full_text = " ".join(v.text.strip() for v in verses if getattr(v, "text", None))
        return [
            SlideContent(
                text=full_text,
                citation=parent_cit,
                translation=used_id,
                pericope_title=pericope_title,
                tags=tags or [],
                page_indicator=None,
            )
        ]

    scale_factor = config.width / 3840.0

    # If all verses fit comfortably on 1 slide and mode is not 'always', keep on single slide
    if pagination.mode != "always" and _check_verses_fit(verses, config, pagination, scale_factor):
        full_text = " ".join(v.text.strip() for v in verses if getattr(v, "text", None))
        return [
            SlideContent(
                text=full_text,
                citation=parent_cit,
                translation=used_id,
                pericope_title=pericope_title,
                tags=tags or [],
                page_indicator=None,
            )
        ]

    # Partition verses into chunks
    chunks: List[List[Any]] = []
    current_chunk: List[Any] = []

    for v in verses:
        if not current_chunk:
            current_chunk.append(v)
            continue
        candidate = current_chunk + [v]
        if _check_verses_fit(candidate, config, pagination, scale_factor):
            current_chunk = candidate
        else:
            chunks.append(current_chunk)
            current_chunk = [v]

    if current_chunk:
        chunks.append(current_chunk)

    total_chunks = len(chunks)
    slide_contents: List[SlideContent] = []

    for i, chunk in enumerate(chunks):
        chunk_text = " ".join(v.text.strip() for v in chunk if getattr(v, "text", None))
        sub_cit = _format_sub_citation(
            chunk[0],
            chunk[-1],
            parent_ref,
            keep_parent=pagination.keep_parent_citation or not pagination.sub_citations,
        )

        indicator = None
        if total_chunks > 1 and pagination.show_indicator:
            indicator = pagination.indicator_format.format(page=i + 1, total=total_chunks)

        chunk_peri = pericope_title if (i == 0 or pagination.repeat_pericope_title) else None

        slide_contents.append(
            SlideContent(
                text=chunk_text,
                citation=sub_cit,
                translation=used_id,
                pericope_title=chunk_peri,
                page_indicator=indicator,
                tags=tags or [],
            )
        )

    return slide_contents


def paginate_text(
    text: str,
    citation: str = "",
    translation: str = "WEB",
    config: Optional[RenderConfig] = None,
    pagination: Optional[PaginationConfig] = None,
    pericope_title: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> List[SlideContent]:
    """Split raw text into paginated SlideContent chunks for optimal display readability."""
    clean_text = text.strip()
    if not clean_text:
        return []

    if pagination is None:
        pagination = PaginationConfig()
    if config is None:
        config = RenderConfig()

    if not pagination.enabled or pagination.mode == "disabled":
        return [
            SlideContent(
                text=clean_text,
                citation=citation,
                translation=translation,
                pericope_title=pericope_title,
                tags=tags or [],
                page_indicator=None,
            )
        ]

    scale_factor = config.width / 3840.0
    min_font = pagination.min_readability_font_size if pagination.min_readability_font_size is not None else max(24.0, 48.0 * scale_factor)
    max_lines = pagination.max_lines_per_slide if pagination.max_lines_per_slide is not None else 8
    max_chars = pagination.max_chars_per_slide if pagination.max_chars_per_slide is not None else 420

    test_content = SlideContent(text=clean_text)
    layout = calculate_slide_layout(test_content, config)

    if (
        pagination.mode != "always"
        and len(clean_text) <= max_chars
        and len(layout.wrapped_lines) <= max_lines
        and layout.font_size >= min_font
    ):
        return [
            SlideContent(
                text=clean_text,
                citation=citation,
                translation=translation,
                pericope_title=pericope_title,
                tags=tags or [],
                page_indicator=None,
            )
        ]

    # Split into sentences or clauses
    raw_sentences = [s.strip() for s in re.split(r"(?<=[.?!;:])\s+", clean_text) if s.strip()]
    if not raw_sentences:
        raw_sentences = [clean_text]

    chunks: List[List[str]] = []
    current: List[str] = []

    for s in raw_sentences:
        if not current:
            current.append(s)
            continue
        candidate = current + [s]
        cand_txt = " ".join(candidate)
        cand_layout = calculate_slide_layout(SlideContent(text=cand_txt), config)
        if (
            len(cand_txt) <= max_chars
            and len(cand_layout.wrapped_lines) <= max_lines
            and cand_layout.font_size >= min_font
        ):
            current = candidate
        else:
            chunks.append(current)
            current = [s]

    if current:
        chunks.append(current)

    total_chunks = len(chunks)
    slide_contents: List[SlideContent] = []

    for i, chunk in enumerate(chunks):
        chunk_txt = " ".join(chunk)
        indicator = None
        if total_chunks > 1 and pagination.show_indicator:
            indicator = pagination.indicator_format.format(page=i + 1, total=total_chunks)

        chunk_peri = pericope_title if (i == 0 or pagination.repeat_pericope_title) else None

        slide_contents.append(
            SlideContent(
                text=chunk_txt,
                citation=citation,
                translation=translation,
                pericope_title=chunk_peri,
                page_indicator=indicator,
                tags=tags or [],
            )
        )

    return slide_contents


def render_verse_slide(
    text: str,
    citation: str = "",
    translation: str = "WEB",
    pericope_title: Optional[str] = None,
    page_indicator: Optional[str] = None,
    theme: Union[str, SlideTheme] = "oled_black",
    resolution: Union[str, Tuple[int, int]] = "4k",
    output_format: str = "png",
    output_path: Optional[Union[str, Path]] = None,
    **kwargs: Any,
) -> RenderResult:
    """Convenience functional interface for generating a single scripture slide."""
    w, h = parse_resolution(resolution)
    config = RenderConfig(
        width=w,
        height=h,
        theme=theme,
        output_format=output_format,
        **kwargs,
    )
    content = SlideContent(
        text=text,
        citation=citation,
        translation=translation,
        pericope_title=pericope_title,
        page_indicator=page_indicator,
    )

    engine = get_default_engine()
    if output_path:
        return engine.render_to_file(content, output_path, config)
    return engine.render(content, config)


def render_verse_slides(
    text_or_verses: Union[str, List[Any]],
    parent_ref: Optional[Any] = None,
    citation: str = "",
    translation: str = "WEB",
    pericope_title: Optional[str] = None,
    tags: Optional[List[str]] = None,
    theme: Union[str, SlideTheme] = "oled_black",
    resolution: Union[str, Tuple[int, int]] = "4k",
    output_format: str = "png",
    output_path: Optional[Union[str, Path]] = None,
    output_dir: Optional[Union[str, Path]] = None,
    pagination: Optional[PaginationConfig] = None,
    **kwargs: Any,
) -> List[RenderResult]:
    """Convenience functional interface for generating paginated scripture slides."""
    w, h = parse_resolution(resolution)
    config = RenderConfig(
        width=w,
        height=h,
        theme=theme,
        output_format=output_format,
        **kwargs,
    )
    if pagination is None:
        pagination = PaginationConfig()

    if isinstance(text_or_verses, list):
        contents = paginate_verses(
            verses=text_or_verses,
            parent_ref=parent_ref,
            config=config,
            pagination=pagination,
            pericope_title=pericope_title,
            tags=tags,
        )
    else:
        cit_str = citation or (parent_ref.format() if hasattr(parent_ref, "format") else str(parent_ref or ""))
        contents = paginate_text(
            text=str(text_or_verses),
            citation=cit_str,
            translation=translation,
            config=config,
            pagination=pagination,
            pericope_title=pericope_title,
            tags=tags,
        )

    engine = get_default_engine()
    if output_dir:
        safe_prefix = re.sub(r"[^a-zA-Z0-9_]+", "_", citation or "slide").strip("_").lower() or "slide"
        return engine.render_sequence_to_dir(contents, output_dir, file_prefix=safe_prefix, config=config)
    elif output_path:
        return engine.render_sequence_to_files(contents, output_path, config=config)
    return engine.render_sequence(contents, config=config)

