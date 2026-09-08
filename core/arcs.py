"""Pure Vector SVG Typological Arc Network & Cross-Reference Graph Engine.

Zero-dependency implementation (Python 3 standard library only per ADR-003):
- Pure SVG vector generation for canonical Old Testament shadows to New Testament fulfillments.
- Mathematical layout of all 66 canonical books across Old Testament and New Testament divisions.
- Sub-chapter and verse precise horizontal positioning along the canonical axis.
- Cubic Bézier arched curve geometry (C x1,y1_ctrl x2,y2_ctrl x2,y_base).
- Sacred-Modern aesthetic palettes (Obsidian Dark, Scriptorium, Monastery Light, Transparent).
- Interactive SVG with embedded CSS styles, hover elevation, tooltips, and data attributes.
- Typological and cross-reference relationship filtering (typology, prophecy_fulfillment, quotation, etc.).
- Dual-modal terminal ASCII/Unicode visualizer and summary table for CLI and REPL.
"""

from dataclasses import dataclass
import html
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from core.crossref import (
    CrossReferenceService,
    RelationshipType,
)
from core.db import Database
from core.reference import (
    BOOKS,
    Book,
    Reference,
    get_book,
    parse_reference,
)


class ArcTheme:
    """Color palettes and aesthetic themes for SVG arc rendering."""

    OBSIDIAN = "obsidian"
    SCRIPTORIUM = "scriptorium"
    MONASTERY = "monastery"
    TRANSPARENT = "transparent"

    ALL = (OBSIDIAN, SCRIPTORIUM, MONASTERY, TRANSPARENT)

    PALETTES: Dict[str, Dict[str, str]] = {
        OBSIDIAN: {
            "background": "#0D0E11",
            "surface": "#14151B",
            "border": "#23252E",
            "axis_line": "#2A2B32",
            "text_primary": "#F5F5F7",
            "text_secondary": "#A0A2B0",
            "text_muted": "#6E7182",
            "ot_badge": "#D4AF37",
            "nt_badge": "#5B8DEF",
            "ot_label": "#C5A059",
            "nt_label": "#6898ED",
            "ot_tick": "rgba(212, 175, 55, 0.4)",
            "nt_tick": "rgba(91, 141, 239, 0.4)",
            "glow_color": "#D4AF37",
        },
        SCRIPTORIUM: {
            "background": "#12100E",
            "surface": "#1A1714",
            "border": "#2C2621",
            "axis_line": "#2C2621",
            "text_primary": "#EAE3D2",
            "text_secondary": "#C4BAA9",
            "text_muted": "#8A8174",
            "ot_badge": "#C99700",
            "nt_badge": "#4A7BC7",
            "ot_label": "#BA8B00",
            "nt_label": "#5A84D1",
            "ot_tick": "rgba(201, 151, 0, 0.4)",
            "nt_tick": "rgba(74, 123, 199, 0.4)",
            "glow_color": "#C99700",
        },
        MONASTERY: {
            "background": "#F7F4EB",
            "surface": "#EFE9DC",
            "border": "#DCD5C5",
            "axis_line": "#DCD5C5",
            "text_primary": "#211D19",
            "text_secondary": "#575043",
            "text_muted": "#8C8373",
            "ot_badge": "#997E24",
            "nt_badge": "#2965C7",
            "ot_label": "#8A701E",
            "nt_label": "#2355A8",
            "ot_tick": "rgba(153, 126, 36, 0.4)",
            "nt_tick": "rgba(41, 101, 199, 0.4)",
            "glow_color": "#997E24",
        },
        TRANSPARENT: {
            "background": "none",
            "surface": "rgba(20, 22, 28, 0.6)",
            "border": "rgba(255, 255, 255, 0.1)",
            "axis_line": "rgba(255, 255, 255, 0.15)",
            "text_primary": "#F5F5F7",
            "text_secondary": "#A0A2B0",
            "text_muted": "#6E7182",
            "ot_badge": "#D4AF37",
            "nt_badge": "#5B8DEF",
            "ot_label": "#C5A059",
            "nt_label": "#6898ED",
            "ot_tick": "rgba(212, 175, 55, 0.4)",
            "nt_tick": "rgba(91, 141, 239, 0.4)",
            "glow_color": "#D4AF37",
        },
    }

    @classmethod
    def get_palette(cls, theme_name: str) -> Dict[str, str]:
        """Return color dictionary for specified theme name."""
        return cls.PALETTES.get(theme_name.strip().lower(), cls.PALETTES[cls.OBSIDIAN])


RELATIONSHIP_COLORS: Dict[str, str] = {
    RelationshipType.TYPOLOGY: "#F39C12",  # Golden Amber (Shadow to Substance)
    RelationshipType.PROPHECY_FULFILLMENT: "#2ECC71",  # Emerald (Messianic Fulfillment)
    RelationshipType.QUOTATION: "#4A90E2",  # Sapphire (Apostolic Direct Citation)
    RelationshipType.THEMATIC: "#9B51E0",  # Tyrian Purple (Covenant Motif)
    RelationshipType.ALLUSION: "#E056FD",  # Rose Gold (Scriptural Echo)
    RelationshipType.PARALLEL: "#747D8C",  # Slate (Parallel Account)
}

CANONICAL_ABBREVIATIONS: Dict[int, str] = {
    1: "GEN", 2: "EXO", 3: "LEV", 4: "NUM", 5: "DEU",
    6: "JOS", 7: "JDG", 8: "RUT", 9: "1SA", 10: "2SA",
    11: "1KI", 12: "2KI", 13: "1CH", 14: "2CH", 15: "EZR",
    16: "NEH", 17: "EST", 18: "JOB", 19: "PSA", 20: "PRO",
    21: "ECC", 22: "SNG", 23: "ISA", 24: "JER", 25: "LAM",
    26: "EZK", 27: "DAN", 28: "HOS", 29: "JOL", 30: "AMO",
    31: "OBA", 32: "JON", 33: "MIC", 34: "NAM", 35: "HAB",
    36: "ZEP", 37: "HAG", 38: "ZEC", 39: "MAL",
    40: "MAT", 41: "MRK", 42: "LUK", 43: "JHN", 44: "ACT",
    45: "ROM", 46: "1CO", 47: "2CO", 48: "GAL", 49: "EPH",
    50: "PHP", 51: "COL", 52: "1TH", 53: "2TH", 54: "1TI",
    55: "2TI", 56: "TIT", 57: "PHM", 58: "HEB", 59: "JAS",
    60: "1PE", 61: "2PE", 62: "1JN", 63: "2JN", 64: "3JN",
    65: "JUD", 66: "REV",
}


@dataclass(frozen=True)
class ArcEndpoint:
    """An endpoint citation localized along the canonical axis."""

    citation: str
    book: Book
    canonical_id: int
    x: float
    fraction: float
    testament: str  # 'OT' or 'NT'


@dataclass(frozen=True)
class ArcPath:
    """Calculated Bézier arc representing a scripture relationship edge."""

    id: int
    source: ArcEndpoint
    target: ArcEndpoint
    relationship_type: str
    relationship_label: str
    color: str
    weight: float
    notes: Optional[str]
    distance_books: int
    arc_height: float
    path_d: str
    is_ot_to_nt: bool

    def to_dict(self) -> Dict[str, Any]:
        """Serialize arc to dictionary for REST API."""
        return {
            "id": self.id,
            "source_ref": self.source.citation,
            "source_book": self.source.book.name,
            "source_x": round(self.source.x, 2),
            "target_ref": self.target.citation,
            "target_book": self.target.book.name,
            "target_x": round(self.target.x, 2),
            "relationship_type": self.relationship_type,
            "relationship_label": self.relationship_label,
            "color": self.color,
            "weight": self.weight,
            "notes": self.notes,
            "distance_books": self.distance_books,
            "arc_height": round(self.arc_height, 2),
            "path_d": self.path_d,
            "is_ot_to_nt": self.is_ot_to_nt,
        }


@dataclass(frozen=True)
class BookAxisMark:
    """Book mark along the horizontal axis of the SVG."""

    book: Book
    x_start: float
    x_end: float
    x_center: float
    width: float
    testament: str
    abbrev: str


@dataclass
class ArcNetwork:
    """Network of canonical typological and cross-reference arcs."""

    width: int
    height: int
    theme_name: str
    book_marks: List[BookAxisMark]
    arcs: List[ArcPath]
    total_connections: int
    connections_by_type: Dict[str, int]
    ot_to_nt_count: int
    y_baseline: float

    def to_dict(self) -> Dict[str, Any]:
        """Return structured summary and arc collection for JSON API."""
        return {
            "width": self.width,
            "height": self.height,
            "theme": self.theme_name,
            "y_baseline": self.y_baseline,
            "total_connections": self.total_connections,
            "ot_to_nt_count": self.ot_to_nt_count,
            "connections_by_type": self.connections_by_type,
            "arcs": [arc.to_dict() for arc in self.arcs],
            "books": [
                {
                    "number": bm.book.number,
                    "name": bm.book.name,
                    "abbrev": bm.abbrev,
                    "testament": bm.testament,
                    "x_start": round(bm.x_start, 2),
                    "x_end": round(bm.x_end, 2),
                    "x_center": round(bm.x_center, 2),
                }
                for bm in self.book_marks
            ],
        }

    def render_svg(self, standalone: bool = True, interactive: bool = True) -> str:
        """Render the complete Typological Arc Network as a pure vector SVG."""
        palette = ArcTheme.get_palette(self.theme_name)
        svg_lines: List[str] = []

        if standalone:
            svg_lines.append('<?xml version="1.0" encoding="UTF-8"?>')

        svg_lines.append(
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.width} {self.height}" '
            f'width="100%" height="100%" class="typological-arc-svg" data-theme="{self.theme_name}">'
        )

        svg_lines.append("  <style>")
        svg_lines.append("    .typological-arc-svg { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }")
        svg_lines.append("    .arc-path { fill: none; stroke-linecap: round; transition: stroke-width 0.25s, stroke-opacity 0.25s, stroke 0.25s; cursor: pointer; }")
        if interactive:
            svg_lines.append("    .arc-path:hover { stroke-width: 3.8px !important; stroke-opacity: 1 !important; filter: drop-shadow(0 0 8px currentColor); }")
            svg_lines.append("    .book-axis-tick { transition: stroke 0.2s, stroke-width 0.2s; cursor: pointer; }")
            svg_lines.append("    .book-axis-label { font-size: 8.5px; font-weight: 500; text-anchor: middle; transition: fill 0.2s, font-weight 0.2s; cursor: pointer; }")
            svg_lines.append("    .book-axis-label:hover { fill: #F5E08F !important; font-weight: 700; }")
        svg_lines.append("  </style>")

        svg_lines.append("  <defs>")
        svg_lines.append('    <filter id="arc-glow" x="-20%" y="-20%" width="140%" height="140%">')
        svg_lines.append('      <feGaussianBlur stdDeviation="3" result="blur" />')
        svg_lines.append('      <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>')
        svg_lines.append("    </filter>")
        svg_lines.append("  </defs>")

        if palette["background"] != "none":
            svg_lines.append(
                f'  <rect width="{self.width}" height="{self.height}" fill="{palette["background"]}" rx="8" />'
            )

        svg_lines.append('  <g class="header-group">')
        svg_lines.append(
            f'    <text x="60" y="32" fill="{palette["text_primary"]}" font-size="14" font-weight="700" letter-spacing="0.5">CANONICAL TYPOLOGICAL ARC NETWORK</text>'
        )
        svg_lines.append(
            f'    <text x="60" y="48" fill="{palette["text_muted"]}" font-size="11">'
            f'Shadow &amp; Substance across Old &amp; New Testaments · {self.total_connections} Edges ({self.ot_to_nt_count} OT ➔ NT Fulfillments)</text>'
        )

        ot_x_center = sum(bm.x_center for bm in self.book_marks if bm.testament == "OT") / 39.0
        nt_x_center = sum(bm.x_center for bm in self.book_marks if bm.testament == "NT") / 27.0
        svg_lines.append(
            f'    <text x="{ot_x_center:.1f}" y="{self.y_baseline - 15:.1f}" fill="{palette["ot_label"]}" font-size="10" font-weight="700" text-anchor="middle" letter-spacing="1">OLD TESTAMENT (39 BOOKS)</text>'
        )
        svg_lines.append(
            f'    <text x="{nt_x_center:.1f}" y="{self.y_baseline - 15:.1f}" fill="{palette["nt_label"]}" font-size="10" font-weight="700" text-anchor="middle" letter-spacing="1">NEW TESTAMENT (27 BOOKS)</text>'
        )
        svg_lines.append("  </g>")

        svg_lines.append('  <g class="arcs-layer">')
        for arc in self.arcs:
            safe_notes = html.escape(arc.notes or "")
            safe_src = html.escape(arc.source.citation)
            safe_tgt = html.escape(arc.target.citation)
            safe_label = html.escape(arc.relationship_label)

            opacity = 0.65 if arc.is_ot_to_nt else 0.45
            stroke_width = 1.6 if arc.is_ot_to_nt else 1.2

            svg_lines.append(
                f'    <path class="arc-path arc-{arc.relationship_type}" id="arc-{arc.id}" '
                f'd="{arc.path_d}" stroke="{arc.color}" stroke-width="{stroke_width}" '
                f'stroke-opacity="{opacity}" data-id="{arc.id}" data-source="{safe_src}" '
                f'data-target="{safe_tgt}" data-type="{arc.relationship_type}" '
                f'data-notes="{safe_notes}" data-distance="{arc.distance_books}">'
                f'<title>{safe_src} ➔ {safe_tgt} ({safe_label})&#10;{safe_notes}</title>'
                f"</path>"
            )
        svg_lines.append("  </g>")

        svg_lines.append('  <g class="axis-layer">')
        svg_lines.append(
            f'    <line x1="50" y1="{self.y_baseline:.1f}" x2="{self.width - 50}" y2="{self.y_baseline:.1f}" '
            f'stroke="{palette["axis_line"]}" stroke-width="1.5" />'
        )

        malachi_end = self.book_marks[38].x_end
        matthew_start = self.book_marks[39].x_start
        div_x = (malachi_end + matthew_start) / 2.0
        svg_lines.append(
            f'    <line x1="{div_x:.1f}" y1="{self.y_baseline - 25:.1f}" x2="{div_x:.1f}" y2="{self.y_baseline + 35:.1f}" '
            f'stroke="{palette["border"]}" stroke-width="1.5" stroke-dasharray="3,3" />'
        )

        for bm in self.book_marks:
            tick_color = palette["ot_tick"] if bm.testament == "OT" else palette["nt_tick"]
            label_color = palette["ot_label"] if bm.testament == "OT" else palette["nt_label"]

            svg_lines.append(
                f'    <line class="book-axis-tick" x1="{bm.x_center:.1f}" y1="{self.y_baseline - 3:.1f}" '
                f'x2="{bm.x_center:.1f}" y2="{self.y_baseline + 5:.1f}" stroke="{tick_color}" stroke-width="1" />'
            )

            label_y = self.y_baseline + 16
            svg_lines.append(
                f'    <text class="book-axis-label" x="{bm.x_center:.1f}" y="{label_y:.1f}" fill="{label_color}" '
                f'transform="rotate(65, {bm.x_center:.1f}, {label_y:.1f})">{bm.abbrev}</text>'
            )

        svg_lines.append("  </g>")
        svg_lines.append("</svg>")
        return "\n".join(svg_lines)

    def render_terminal_summary(self, color: bool = True) -> str:
        """Render an illuminated ANSI terminal summary table and bridge visualizer."""
        def c(text: str, code: str) -> str:
            return f"\033[{code}m{text}\033[0m" if color else text

        gold = lambda t: c(t, "38;5;220")
        cyan = lambda t: c(t, "38;5;51")
        green = lambda t: c(t, "38;5;48")
        purple = lambda t: c(t, "38;5;141")
        bold = lambda t: c(t, "1")
        dim = lambda t: c(t, "2")

        lines: List[str] = []
        lines.append(gold("╔══════════════════════════════════════════════════════════════════════════════╗"))
        lines.append(gold("║        CANONICAL TYPOLOGICAL ARC NETWORK & REDEMPTIVE GRAPH                  ║"))
        lines.append(gold("╚══════════════════════════════════════════════════════════════════════════════╝"))
        lines.append("")

        lines.append(
            f"  {bold('Total Connections:')} {green(str(self.total_connections))} edges  │  "
            f"{bold('OT ➔ NT Fulfillments:')} {gold(str(self.ot_to_nt_count))} arcs"
        )
        type_parts = [
            f"{RelationshipType.get_icon(k)} {RelationshipType.get_label(k)}: {bold(str(v))}"
            for k, v in self.connections_by_type.items()
        ]
        lines.append(f"  {bold('Breakdown:')} {' · '.join(type_parts)}")
        lines.append("")

        lines.append(dim("  ── Canonical Redemptive Trajectory ───────────────────────────────────────────"))
        lines.append(
            f"  {cyan('[ LAW ]')} ──► {cyan('[ HISTORY ]')} ──► {cyan('[ POETRY ]')} ──► {cyan('[ PROPHETS ]')}"
        )
        lines.append(gold("         │               │               │               │"))
        lines.append(gold("         └───────────────┴───────┬───────┴───────────────┘"))
        lines.append(gold("                                 │ (Christological Fulfillment Arcs)"))
        lines.append(gold("                                 ▼"))
        lines.append(
            f"                     {purple('[ GOSPELS ]')} ──► {purple('[ EPISTLES ]')} ──► {purple('[ REVELATION ]')}"
        )
        lines.append(dim("  ──────────────────────────────────────────────────────────────────────────────"))
        lines.append("")

        lines.append(bold("  Curated Typological & Prophetic Connections:"))
        for idx, arc in enumerate(self.arcs[:18], 1):
            src_str = arc.source.citation.ljust(18)
            tgt_str = arc.target.citation.ljust(18)
            dist_str = f"({arc.distance_books} bks)"
            icon = RelationshipType.get_icon(arc.relationship_type)
            notes_str = arc.notes or ""
            if len(notes_str) > 42:
                notes_str = notes_str[:39] + "..."

            lines.append(
                f"  {dim(f'{idx:2d}.')} {cyan(src_str)} {gold('➔')} {purple(tgt_str)} "
                f"{icon} {dim(dist_str.ljust(9))} {notes_str}"
            )

        return "\n".join(lines)


def get_reference_x(
    reference: Union[Reference, str],
    book_marks: Sequence[BookAxisMark],
) -> Tuple[float, Book]:
    """Calculate the precise horizontal X coordinate for a Scripture citation."""
    ref = parse_reference(reference) if isinstance(reference, str) else reference
    book = ref.book

    bm = next((b for b in book_marks if b.book.number == book.number), None)
    if not bm:
        return 60.0, book

    total_chapters = max(1, book.total_chapters)
    chapter_idx = max(0, ref.start_chapter - 1)
    verse_idx = max(0, (ref.start_verse or 1) - 1)

    chapter_fraction = (chapter_idx + min(1.0, verse_idx / 35.0)) / float(total_chapters)
    chapter_fraction = max(0.0, min(1.0, chapter_fraction))

    x = bm.x_start + chapter_fraction * bm.width
    return x, book


def build_arc_network(
    db: Database,
    relationship_type: Optional[str] = None,
    book_filter: Optional[Union[str, Book]] = None,
    testament_filter: Optional[str] = None,
    theme: str = ArcTheme.OBSIDIAN,
    width: int = 1200,
    height: int = 520,
) -> ArcNetwork:
    """Build the complete canonical ArcNetwork with calculated Bézier geometry."""
    margin_left = 60.0
    margin_right = 60.0
    margin_top = 70.0
    margin_bottom = 90.0

    active_width = float(width) - margin_left - margin_right
    y_baseline = float(height) - margin_bottom
    max_arc_height = y_baseline - margin_top

    intertestament_gap = 26.0
    available_book_width = active_width - intertestament_gap
    book_unit_width = available_book_width / 66.0

    book_marks: List[BookAxisMark] = []
    curr_x = margin_left

    for b_num in range(1, 67):
        book = BOOKS[b_num]
        testament = "OT" if b_num <= 39 else "NT"
        abbrev = CANONICAL_ABBREVIATIONS.get(b_num, book.osis.upper()[:3])

        if b_num == 40:
            curr_x += intertestament_gap

        x_start = curr_x
        x_end = curr_x + book_unit_width
        x_center = (x_start + x_end) / 2.0

        book_marks.append(
            BookAxisMark(
                book=book,
                x_start=x_start,
                x_end=x_end,
                x_center=x_center,
                width=book_unit_width,
                testament=testament,
                abbrev=abbrev,
            )
        )
        curr_x += book_unit_width

    crossref_svc = CrossReferenceService(db)
    raw_edges = crossref_svc.list_all_cross_references(limit=2000)

    target_book_obj: Optional[Book] = None
    if book_filter:
        target_book_obj = get_book(book_filter) if isinstance(book_filter, str) else book_filter

    arcs: List[ArcPath] = []
    by_type: Dict[str, int] = {}
    ot_nt_count = 0

    for edge in raw_edges:
        if relationship_type and edge.relationship_type.lower() != relationship_type.strip().lower():
            continue

        try:
            s_ref = parse_reference(edge.source_human_ref)
            t_ref = parse_reference(edge.target_human_ref)
        except Exception:
            continue

        if target_book_obj:
            if s_ref.book.number != target_book_obj.number and t_ref.book.number != target_book_obj.number:
                continue

        is_ot_to_nt = s_ref.book.number <= 39 and t_ref.book.number >= 40
        if testament_filter:
            tf = testament_filter.strip().upper()
            if tf in ("OT-NT", "OT_NT", "OT->NT") and not is_ot_to_nt:
                continue
            elif tf == "OT" and not (s_ref.book.number <= 39 and t_ref.book.number <= 39):
                continue
            elif tf == "NT" and not (s_ref.book.number >= 40 and t_ref.book.number >= 40):
                continue

        sx, s_book = get_reference_x(s_ref, book_marks)
        tx, t_book = get_reference_x(t_ref, book_marks)

        dx = abs(tx - sx)
        distance_books = abs(t_book.number - s_book.number)

        norm_dist = min(1.0, dx / active_width)
        arc_h = min(max_arc_height, 28.0 + (norm_dist ** 0.72) * (max_arc_height - 28.0))

        y_ctrl = max(margin_top, y_baseline - arc_h * 1.08)
        path_d = f"M {sx:.1f},{y_baseline:.1f} C {sx:.1f},{y_ctrl:.1f} {tx:.1f},{y_ctrl:.1f} {tx:.1f},{y_baseline:.1f}"

        rel_type = edge.relationship_type.lower()
        color = RELATIONSHIP_COLORS.get(rel_type, "#D4AF37")
        rel_label = RelationshipType.get_label(rel_type)

        s_endpoint = ArcEndpoint(
            citation=edge.source_human_ref,
            book=s_book,
            canonical_id=edge.source_start_id,
            x=sx,
            fraction=0.0,
            testament="OT" if s_book.number <= 39 else "NT",
        )
        t_endpoint = ArcEndpoint(
            citation=edge.target_human_ref,
            book=t_book,
            canonical_id=edge.target_start_id,
            x=tx,
            fraction=0.0,
            testament="OT" if t_book.number <= 39 else "NT",
        )

        arc = ArcPath(
            id=edge.id or len(arcs) + 1,
            source=s_endpoint,
            target=t_endpoint,
            relationship_type=rel_type,
            relationship_label=rel_label,
            color=color,
            weight=edge.weight,
            notes=edge.notes,
            distance_books=distance_books,
            arc_height=arc_h,
            path_d=path_d,
            is_ot_to_nt=is_ot_to_nt,
        )
        arcs.append(arc)

        by_type[rel_type] = by_type.get(rel_type, 0) + 1
        if is_ot_to_nt:
            ot_nt_count += 1

    return ArcNetwork(
        width=width,
        height=height,
        theme_name=theme,
        book_marks=book_marks,
        arcs=arcs,
        total_connections=len(arcs),
        connections_by_type=by_type,
        ot_to_nt_count=ot_nt_count,
        y_baseline=y_baseline,
    )
