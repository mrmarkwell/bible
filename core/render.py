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
    line_spacing: float = 1.5
    text_align: str = "center"  # "center", "left", "right"
    citation_style: str = "below"  # "below", "above", "none"
    optical_center_pct: float = 0.45  # 45% baseline for human optical vertical center
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
    """Wrap text to fit within max_width using word boundaries and font heuristics."""
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


def calculate_slide_layout(content: SlideContent, config: RenderConfig) -> LayoutBox:
    """Calculate geometric bounding boxes, optimal font sizes, and vertical centering."""
    w = config.width
    h = config.height
    safe_pct = max(0.05, min(0.35, config.safe_area_pct))

    safe_x = w * safe_pct
    safe_y = h * safe_pct
    safe_w = w * (1.0 - 2.0 * safe_pct)
    safe_h = h * (1.0 - 2.0 * safe_pct)

    scale_factor = w / 3840.0
    min_font_size = 36.0 * scale_factor
    max_font_size = 108.0 * scale_factor

    if config.font_size is not None and config.font_size > 0:
        font_size = config.font_size
    else:
        clean_text = content.text.strip()
        total_chars = len(clean_text)

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

        font_size = max(min_font_size, min(max_font_size, target_pt))

        for _ in range(8):
            lines = wrap_text_to_width(clean_text, safe_w, font_size)
            line_h = font_size * config.line_spacing
            est_body_h = len(lines) * line_h

            aux_h = (font_size * 0.55 * 2.0) + (font_size * 0.42 * 2.0) + (80.0 * scale_factor)
            if est_body_h + aux_h > safe_h and font_size > min_font_size:
                font_size = max(min_font_size, font_size * 0.90)
            else:
                break

    wrapped = wrap_text_to_width(content.text.strip(), safe_w, font_size)
    line_h = font_size * config.line_spacing
    body_h = len(wrapped) * line_h

    citation_pt = max(24.0 * scale_factor, font_size * 0.48)
    pericope_pt = max(20.0 * scale_factor, font_size * 0.40)

    accent_spacing = 40.0 * scale_factor if config.show_accent_rule else 20.0 * scale_factor
    citation_block_h = (citation_pt * 1.5) + accent_spacing if (content.citation or content.translation) else 0.0
    pericope_block_h = (pericope_pt * 1.6) + (24.0 * scale_factor) if content.pericope_title else 0.0

    total_h = body_h + citation_block_h + pericope_block_h

    optical_y = h * config.optical_center_pct
    start_y = optical_y - (total_h / 2.0)

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

        lines: List[str] = [
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
            "  <defs>",
            '    <style type="text/css">',
            f'      .verse-text {{ font-family: {font_family}; font-size: {layout.font_size:.2f}px; '
            f'fill: {theme.text_color}; text-anchor: {anchor}; }}',
            f'      .citation-text {{ font-family: {font_family}; font-size: {layout.citation_font_size:.2f}px; '
            f'fill: {theme.citation_color}; text-anchor: {anchor}; font-weight: 600; letter-spacing: 0.05em; }}',
            f'      .pericope-text {{ font-family: {font_family}; font-size: {layout.pericope_font_size:.2f}px; '
            f'fill: {theme.pericope_color}; text-anchor: {anchor}; text-transform: uppercase; letter-spacing: 0.12em; }}',
            f'      .indicator-text {{ font-family: {font_family}; font-size: {layout.pericope_font_size * 0.85:.2f}px; '
            f'fill: {theme.page_indicator_color}; text-anchor: middle; }}',
            f'      .accent-rule {{ stroke: {theme.accent_color}; stroke-width: {max(1.5, w / 1920.0):.1f}; stroke-linecap: round; }}',
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


_DEFAULT_ENGINE: Optional[SlideRenderEngine] = None


def get_default_engine() -> SlideRenderEngine:
    global _DEFAULT_ENGINE
    if _DEFAULT_ENGINE is None:
        _DEFAULT_ENGINE = SlideRenderEngine()
    return _DEFAULT_ENGINE


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
    """Convenience functional interface for generating a scripture slide."""
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
