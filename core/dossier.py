"""Sovereign Omnichannel Exegetical Study Dossier & Multi-Modal Passage Research Packet Engine.

Zero-dependency implementation (Python 3 standard library only per ADR-003).
Aggregates and synthesizes multi-dimensional theological datasets into a unified
research dossier for any canonical passage:
  1. Multi-translation Scripture text (comparative and aligned)
  2. Pericope structural passport (literary genre, structure, proposition, redemptive summary)
  3. Theological facets (storyline epoch, locus, primary doctrine, thematic ribbon)
  4. Thematic & theological semantic tags (TGC foundation categories and confidence)
  5. Typological redemptive arcs (Old Testament types -> New Testament Christological fulfillments)
  6. Curated canonical cross-references (prioritized TSK edges with relationship typology)
  7. Dense semantic vector proximity (topologically closest pericopes across 66 books with match scores)
  8. Biblical character persona commentary & pastoral exegesis (author persona & whole-bible counselor)
  9. Omnichannel multi-format export (Terminal ANSI, Markdown, standalone HTML, JSON, Plain Text)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import html
import json
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from core.db import Database, VerseRecord
from core.reference import Reference, parse_reference
from core.vector import get_pericope_recommender, PericopeRecommender
from core.persona import CANONICAL_PERSONAS, CharacterPersonaDefinition
from core.terminal import THEMES, RESET, BOLD, GREEN


@dataclass
class DossierPericope:
    """Hydrated pericope passport within a study dossier."""
    id: int
    title: str
    human_ref: str
    genre: str = ""
    literary_structure: str = ""
    central_proposition: str = ""
    redemptive_summary: str = ""
    map_x: Optional[float] = None
    map_y: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "human_ref": self.human_ref,
            "genre": self.genre,
            "literary_structure": self.literary_structure,
            "central_proposition": self.central_proposition,
            "redemptive_summary": self.redemptive_summary,
            "map_x": self.map_x,
            "map_y": self.map_y,
        }


@dataclass
class DossierTheology:
    """Theological classification facets."""
    storyline_epoch: str = ""
    theological_locus: str = ""
    primary_doctrine: str = ""
    thematic_ribbon: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "storyline_epoch": self.storyline_epoch,
            "theological_locus": self.theological_locus,
            "primary_doctrine": self.primary_doctrine,
            "thematic_ribbon": self.thematic_ribbon,
        }


@dataclass
class DossierTag:
    """Thematic semantic tag annotation."""
    name: str
    category: str = ""
    confidence: float = 1.0
    starred: bool = False
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "confidence": round(self.confidence, 2),
            "starred": self.starred,
            "notes": self.notes,
        }


@dataclass
class DossierCrossRef:
    """Curated canonical cross-reference edge."""
    target_ref: str
    direction: str = "outgoing"
    relationship_type: str = "thematic"
    icon: str = "🔗"
    confidence: float = 1.0
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_ref": self.target_ref,
            "direction": self.direction,
            "relationship_type": self.relationship_type,
            "icon": self.icon,
            "confidence": round(self.confidence, 2),
            "notes": self.notes,
        }


@dataclass
class DossierTypologicalArc:
    """Typological arc connecting Old Testament shadow to New Testament fulfillment."""
    id: int
    title: str
    type_ref: str
    antitype_ref: str
    theological_correspondence: str = ""
    warrant: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "type_ref": self.type_ref,
            "antitype_ref": self.antitype_ref,
            "theological_correspondence": self.theological_correspondence,
            "warrant": self.warrant,
        }


@dataclass
class DossierVectorNeighbor:
    """Topologically nearest pericope in 768d vector space."""
    rank: int
    score: float
    match_pct: str
    title: str
    human_ref: str
    book_name: str
    genre: str = ""
    redemptive_summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rank": self.rank,
            "score": round(self.score, 4),
            "match_pct": self.match_pct,
            "title": self.title,
            "human_ref": self.human_ref,
            "book_name": self.book_name,
            "genre": self.genre,
            "redemptive_summary": self.redemptive_summary,
        }


@dataclass
class DossierPersonaPerspective:
    """Pastoral or theological reflection from a biblical character persona."""
    persona_id: str
    name: str
    title: str
    canonical_era: str
    is_author: bool = False
    pastoral_reflection: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "persona_id": self.persona_id,
            "name": self.name,
            "title": self.title,
            "canonical_era": self.canonical_era,
            "is_author": self.is_author,
            "pastoral_reflection": self.pastoral_reflection,
        }


@dataclass
class ExegeticalDossier:
    """Comprehensive Exegetical Study Dossier aggregating all theological dimensions."""
    reference: Reference
    human_ref: str
    book_name: str
    testament: str
    canon_order: int
    verses_by_translation: Dict[str, List[VerseRecord]] = field(default_factory=dict)
    pericopes: List[DossierPericope] = field(default_factory=list)
    theology: Optional[DossierTheology] = None
    tags: List[DossierTag] = field(default_factory=list)
    typological_arcs: List[DossierTypologicalArc] = field(default_factory=list)
    cross_references: List[DossierCrossRef] = field(default_factory=list)
    vector_neighbors: List[DossierVectorNeighbor] = field(default_factory=list)
    persona_perspectives: List[DossierPersonaPerspective] = field(default_factory=list)
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    )

    @property
    def total_verses(self) -> int:
        """Total verses represented across the passage."""
        if not self.verses_by_translation:
            return 0
        return max(len(v_list) for v_list in self.verses_by_translation.values())

    def to_dict(self) -> Dict[str, Any]:
        """Serialize complete study dossier to Python dictionary."""
        tr_data: Dict[str, List[Dict[str, Any]]] = {}
        for tr_id, verses in self.verses_by_translation.items():
            tr_data[tr_id] = [
                {
                    "verse": v.verse,
                    "subverse": v.subverse,
                    "text": v.text,
                }
                for v in verses
            ]

        return {
            "metadata": {
                "reference": str(self.reference),
                "human_ref": self.human_ref,
                "book_name": self.book_name,
                "testament": self.testament,
                "canon_order": self.canon_order,
                "total_verses": self.total_verses,
                "generated_at": self.generated_at,
            },
            "scripture": tr_data,
            "pericopes": [p.to_dict() for p in self.pericopes],
            "theology": self.theology.to_dict() if self.theology else None,
            "tags": [t.to_dict() for t in self.tags],
            "typological_arcs": [a.to_dict() for a in self.typological_arcs],
            "cross_references": [x.to_dict() for x in self.cross_references],
            "vector_neighbors": [v.to_dict() for v in self.vector_neighbors],
            "persona_perspectives": [p.to_dict() for p in self.persona_perspectives],
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize dossier to structured JSON."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def to_markdown(self) -> str:
        """Render Obsidian-ready Markdown dossier with frontmatter and structured callouts."""
        lines: List[str] = []

        # YAML Frontmatter
        lines.append("---")
        lines.append(f'title: "Exegetical Study Dossier: {self.human_ref}"')
        lines.append(f'reference: "{self.human_ref}"')
        lines.append(f'book: "{self.book_name}"')
        lines.append(f'testament: "{self.testament}"')
        if self.theology:
            if self.theology.theological_locus:
                lines.append(f'theological_locus: "{self.theology.theological_locus}"')
            if self.theology.storyline_epoch:
                lines.append(f'storyline_epoch: "{self.theology.storyline_epoch}"')
            if self.theology.primary_doctrine:
                lines.append(f'primary_doctrine: "{self.theology.primary_doctrine}"')
        lines.append(f'generated: "{self.generated_at}"')
        lines.append("tags:")
        lines.append("  - bible-study")
        lines.append("  - exegetical-dossier")
        for tag in self.tags[:8]:
            slug = tag.name.lower().replace(" ", "-").replace("/", "-")
            lines.append(f"  - {slug}")
        lines.append("---")
        lines.append("")

        # Header Title
        lines.append(f"# 📜 Exegetical Study Dossier: {self.human_ref}")
        lines.append("")
        lines.append(f"*Canon: {self.book_name} ({self.testament} • Book #{self.canon_order}) — Generated {self.generated_at}*")
        lines.append("")

        # Pericope Proposition Block
        if self.pericopes:
            p_primary = self.pericopes[0]
            lines.append(f"> [!NOTE] **Parent Pericope: {p_primary.title} ({p_primary.human_ref})**")
            if p_primary.genre:
                lines.append(f"> **Genre**: {p_primary.genre} • **Structure**: {p_primary.literary_structure}")
            if p_primary.central_proposition:
                lines.append(f"> **Central Proposition**: {p_primary.central_proposition}")
            if p_primary.redemptive_summary:
                lines.append(f"> **Redemptive-Historical Summary**: {p_primary.redemptive_summary}")
            lines.append("")

        # Section 1: Scripture Text
        lines.append("## 1. Scripture Text (Comparative Translations)")
        lines.append("")
        for tr_id, verses in self.verses_by_translation.items():
            lines.append(f"### Translation: {tr_id}")
            lines.append("")
            for v in verses:
                lines.append(f"> **[{v.verse}]** {v.text}")
            lines.append("")

        # Section 2: Theological Classification & Facets
        if self.theology:
            lines.append("## 2. Theological Classification & Canonical Horizons")
            lines.append("")
            lines.append("| Dimension | Classification | Description |")
            lines.append("|---|---|---|")
            lines.append(f"| **Storyline Epoch** | `{self.theology.storyline_epoch or 'canonical'}` | Redemptive-historical epoch |")
            lines.append(f"| **Theological Locus** | `{self.theology.theological_locus or 'theology'}` | Systematic doctrinal category |")
            lines.append(f"| **Primary Doctrine** | `{self.theology.primary_doctrine or 'general'}` | Core theological affirmation |")
            if self.theology.thematic_ribbon:
                lines.append(f"| **Thematic Ribbon** | `{self.theology.thematic_ribbon}` | Tracing canonical motif |")
            lines.append("")

        # Section 3: Thematic Semantic Tags
        if self.tags:
            lines.append("## 3. Thematic Semantic Tags & Taxonomies")
            lines.append("")
            lines.append("| Tag Name | Category | Confidence | Notes |")
            lines.append("|---|---|---|---|")
            for t in self.tags:
                star = "⭐ " if t.starred else ""
                lines.append(f"| {star}**{t.name}** | `{t.category or 'thematic'}` | {t.confidence * 100:.0f}% | {t.notes or '—'} |")
            lines.append("")

        # Section 4: Typological Arcs
        if self.typological_arcs:
            lines.append("## 4. Redemptive Typological Arcs (OT Shadows ➔ NT Fulfillments)")
            lines.append("")
            for arc in self.typological_arcs:
                lines.append(f"### 🏛 {arc.title}")
                lines.append(f"- **Shadow / Type**: `[{arc.type_ref}]`")
                lines.append(f"- **Antitype / Fulfillment**: `[{arc.antitype_ref}]`")
                if arc.theological_correspondence:
                    lines.append(f"- **Theological Correspondence**: {arc.theological_correspondence}")
                if arc.warrant:
                    lines.append(f"- **Biblical Warrant**: {arc.warrant}")
                lines.append("")

        # Section 5: Cross-References
        if self.cross_references:
            lines.append("## 5. Curated Canonical Cross-References (TSK)")
            lines.append("")
            lines.append("| Target Passage | Edge Type | Direction | Confidence | Notes |")
            lines.append("|---|---|---|---|---|")
            for xr in self.cross_references[:20]:
                lines.append(f"| **[{xr.target_ref}]** | {xr.icon} `{xr.relationship_type}` | {xr.direction} | {xr.confidence * 100:.0f}% | {xr.notes or '—'} |")
            lines.append("")

        # Section 6: Semantic Vector Proximity
        if self.vector_neighbors:
            lines.append("## 6. Dense Semantic Vector Proximity (Canonical Nearest Neighbors)")
            lines.append("")
            lines.append("| Rank | Similarity | Passage | Title | Genre | Redemptive Horizon |")
            lines.append("|---|---|---|---|---|---|")
            for vn in self.vector_neighbors:
                lines.append(f"| #{vn.rank} | **{vn.match_pct}** | `[{vn.human_ref}]` | {vn.title} | `{vn.genre}` | {vn.redemptive_summary} |")
            lines.append("")

        # Section 7: Biblical Persona Commentary
        if self.persona_perspectives:
            lines.append("## 7. Biblical Character Persona Exegesis & Pastoral Synthesis")
            lines.append("")
            for pp in self.persona_perspectives:
                author_badge = " *(Canonical Author)*" if pp.is_author else ""
                lines.append(f"### 👤 {pp.name} — {pp.title}{author_badge}")
                lines.append(f"*Era: {pp.canonical_era}*")
                lines.append("")
                lines.append(f"> {pp.pastoral_reflection}")
                lines.append("")

        lines.append("---")
        lines.append("*Sovereign Bible Engine • Zero External Dependencies • Sacred-Modern Architecture*")
        return "\n".join(lines)

    def to_html(self) -> str:
        """Render a self-contained, beautifully styled Sacred-Modern HTML document."""
        ref_esc = html.escape(self.human_ref)
        book_esc = html.escape(self.book_name)
        testament_esc = html.escape(self.testament)

        html_buf: List[str] = []
        html_buf.append("<!DOCTYPE html>")
        html_buf.append("<html lang=\"en\">")
        html_buf.append("<head>")
        html_buf.append("  <meta charset=\"UTF-8\">")
        html_buf.append("  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">")
        html_buf.append(f"  <title>Exegetical Study Dossier: {ref_esc}</title>")
        html_buf.append("  <style>")
        html_buf.append("    :root {")
        html_buf.append("      --bg-base: #0D0E11;")
        html_buf.append("      --bg-surface: #14161C;")
        html_buf.append("      --bg-card: #1A1D24;")
        html_buf.append("      --border-color: #2D3139;")
        html_buf.append("      --text-main: #E6E8EC;")
        html_buf.append("      --text-muted: #8E95A5;")
        html_buf.append("      --gold: #D4AF37;")
        html_buf.append("      --gold-dim: rgba(212, 175, 55, 0.15);")
        html_buf.append("      --cyan: #38BDF8;")
        html_buf.append('      --font-serif: "Georgia", "Palatino Linotype", "Liberation Serif", serif;')
        html_buf.append('      --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;')
        html_buf.append("    }")
        html_buf.append("    body {")
        html_buf.append("      background-color: var(--bg-base);")
        html_buf.append("      color: var(--text-main);")
        html_buf.append("      font-family: var(--font-sans);")
        html_buf.append("      margin: 0;")
        html_buf.append("      padding: 2rem 1rem;")
        html_buf.append("      line-height: 1.6;")
        html_buf.append("    }")
        html_buf.append("    .container {")
        html_buf.append("      max-width: 960px;")
        html_buf.append("      margin: 0 auto;")
        html_buf.append("    }")
        html_buf.append("    header.dossier-header {")
        html_buf.append("      border-bottom: 2px solid var(--gold);")
        html_buf.append("      padding-bottom: 1.5rem;")
        html_buf.append("      margin-bottom: 2rem;")
        html_buf.append("    }")
        html_buf.append("    h1 {")
        html_buf.append("      font-family: var(--font-serif);")
        html_buf.append("      color: var(--gold);")
        html_buf.append("      font-size: 2.25rem;")
        html_buf.append("      margin: 0 0 0.5rem 0;")
        html_buf.append("    }")
        html_buf.append("    .subtitle {")
        html_buf.append("      color: var(--text-muted);")
        html_buf.append("      font-size: 0.95rem;")
        html_buf.append("    }")
        html_buf.append("    .badge {")
        html_buf.append("      display: inline-block;")
        html_buf.append("      padding: 0.2rem 0.6rem;")
        html_buf.append("      border-radius: 4px;")
        html_buf.append("      font-size: 0.8rem;")
        html_buf.append("      font-weight: 600;")
        html_buf.append("      background: var(--gold-dim);")
        html_buf.append("      color: var(--gold);")
        html_buf.append("      border: 1px solid var(--gold);")
        html_buf.append("      margin-right: 0.5rem;")
        html_buf.append("      margin-bottom: 0.4rem;")
        html_buf.append("    }")
        html_buf.append("    .card {")
        html_buf.append("      background: var(--bg-surface);")
        html_buf.append("      border: 1px solid var(--border-color);")
        html_buf.append("      border-radius: 8px;")
        html_buf.append("      padding: 1.5rem;")
        html_buf.append("      margin-bottom: 1.75rem;")
        html_buf.append("    }")
        html_buf.append("    .card h2 {")
        html_buf.append("      font-family: var(--font-serif);")
        html_buf.append("      color: var(--gold);")
        html_buf.append("      font-size: 1.35rem;")
        html_buf.append("      margin-top: 0;")
        html_buf.append("      border-bottom: 1px solid var(--border-color);")
        html_buf.append("      padding-bottom: 0.5rem;")
        html_buf.append("    }")
        html_buf.append("    .scripture-verse {")
        html_buf.append("      font-family: var(--font-serif);")
        html_buf.append("      font-size: 1.05rem;")
        html_buf.append("      margin-bottom: 0.75rem;")
        html_buf.append("    }")
        html_buf.append("    .verse-num {")
        html_buf.append("      color: var(--cyan);")
        html_buf.append("      font-weight: bold;")
        html_buf.append("      margin-right: 0.4rem;")
        html_buf.append("    }")
        html_buf.append("    table {")
        html_buf.append("      width: 100%;")
        html_buf.append("      border-collapse: collapse;")
        html_buf.append("      margin-top: 0.75rem;")
        html_buf.append("    }")
        html_buf.append("    th, td {")
        html_buf.append("      text-align: left;")
        html_buf.append("      padding: 0.6rem 0.75rem;")
        html_buf.append("      border-bottom: 1px solid var(--border-color);")
        html_buf.append("      font-size: 0.9rem;")
        html_buf.append("    }")
        html_buf.append("    th {")
        html_buf.append("      color: var(--gold);")
        html_buf.append("      font-weight: 600;")
        html_buf.append("    }")
        html_buf.append("    blockquote {")
        html_buf.append("      border-left: 3px solid var(--gold);")
        html_buf.append("      margin: 1rem 0;")
        html_buf.append("      padding: 0.5rem 1rem;")
        html_buf.append("      background: var(--bg-card);")
        html_buf.append("      font-style: italic;")
        html_buf.append("    }")
        html_buf.append("    footer {")
        html_buf.append("      text-align: center;")
        html_buf.append("      color: var(--text-muted);")
        html_buf.append("      font-size: 0.85rem;")
        html_buf.append("      margin-top: 3rem;")
        html_buf.append("      border-top: 1px solid var(--border-color);")
        html_buf.append("      padding-top: 1rem;")
        html_buf.append("    }")
        html_buf.append("  </style>")
        html_buf.append("</head>")
        html_buf.append("<body>")
        html_buf.append("  <div class=\"container\">")
        html_buf.append("    <header class=\"dossier-header\">")
        html_buf.append(f"      <h1>📜 Exegetical Study Dossier: {ref_esc}</h1>")
        html_buf.append(f"      <div class=\"subtitle\">Canon: {book_esc} ({testament_esc} • Book #{self.canon_order}) • Generated {self.generated_at}</div>")
        html_buf.append("    </header>")

        # Pericope Passport
        if self.pericopes:
            p = self.pericopes[0]
            html_buf.append("    <div class=\"card\">")
            html_buf.append(f"      <h2>Parent Pericope: {html.escape(p.title)} ({html.escape(p.human_ref)})</h2>")
            if p.genre or p.literary_structure:
                html_buf.append(f"      <p><strong>Genre:</strong> {html.escape(p.genre)} &bull; <strong>Structure:</strong> {html.escape(p.literary_structure)}</p>")
            if p.central_proposition:
                html_buf.append(f"      <blockquote><strong>Central Proposition:</strong> {html.escape(p.central_proposition)}</blockquote>")
            if p.redemptive_summary:
                html_buf.append(f"      <p><strong>Redemptive-Historical Summary:</strong> {html.escape(p.redemptive_summary)}</p>")
            html_buf.append("    </div>")

        # Scripture Verses
        html_buf.append("    <div class=\"card\">")
        html_buf.append("      <h2>1. Scripture Text (Comparative Translations)</h2>")
        for tr_id, verses in self.verses_by_translation.items():
            html_buf.append(f"      <h3 style=\"color: var(--cyan); margin-top: 1.25rem;\">Translation: {html.escape(tr_id)}</h3>")
            for v in verses:
                html_buf.append(f"      <div class=\"scripture-verse\"><span class=\"verse-num\">[{v.verse}]</span>{html.escape(v.text)}</div>")
        html_buf.append("    </div>")

        # Theological Facets
        if self.theology:
            html_buf.append("    <div class=\"card\">")
            html_buf.append("      <h2>2. Theological Classification &amp; Horizons</h2>")
            html_buf.append("      <table>")
            html_buf.append("        <tr><th>Dimension</th><th>Classification</th></tr>")
            html_buf.append(f"        <tr><td>Storyline Epoch</td><td><span class=\"badge\">{html.escape(self.theology.storyline_epoch or 'canonical')}</span></td></tr>")
            html_buf.append(f"        <tr><td>Theological Locus</td><td><span class=\"badge\">{html.escape(self.theology.theological_locus or 'theology')}</span></td></tr>")
            html_buf.append(f"        <tr><td>Primary Doctrine</td><td><strong>{html.escape(self.theology.primary_doctrine or 'general')}</strong></td></tr>")
            if self.theology.thematic_ribbon:
                html_buf.append(f"        <tr><td>Thematic Ribbon</td><td>{html.escape(self.theology.thematic_ribbon)}</td></tr>")
            html_buf.append("      </table>")
            html_buf.append("    </div>")

        # Semantic Tags
        if self.tags:
            html_buf.append("    <div class=\"card\">")
            html_buf.append("      <h2>3. Thematic Semantic Tags</h2>")
            html_buf.append("      <div>")
            for t in self.tags:
                star = "⭐ " if t.starred else ""
                html_buf.append(f"        <span class=\"badge\">{star}{html.escape(t.name)} ({int(t.confidence * 100)}%)</span>")
            html_buf.append("      </div>")
            html_buf.append("    </div>")

        # Typological Arcs
        if self.typological_arcs:
            html_buf.append("    <div class=\"card\">")
            html_buf.append("      <h2>4. Redemptive Typological Arcs</h2>")
            for arc in self.typological_arcs:
                html_buf.append("      <div style=\"margin-bottom: 1rem;\">")
                html_buf.append(f"        <strong>🏛 {html.escape(arc.title)}</strong><br>")
                html_buf.append(f"        <small>Shadow: [{html.escape(arc.type_ref)}] ➔ Antitype: [{html.escape(arc.antitype_ref)}]</small>")
                if arc.theological_correspondence:
                    html_buf.append(f"        <p>{html.escape(arc.theological_correspondence)}</p>")
                html_buf.append("      </div>")
            html_buf.append("    </div>")

        # Cross References
        if self.cross_references:
            html_buf.append("    <div class=\"card\">")
            html_buf.append("      <h2>5. Curated Canonical Cross-References (TSK)</h2>")
            html_buf.append("      <table>")
            html_buf.append("        <tr><th>Passage</th><th>Type</th><th>Direction</th><th>Confidence</th></tr>")
            for xr in self.cross_references[:15]:
                html_buf.append(f"        <tr><td><strong>[{html.escape(xr.target_ref)}]</strong></td><td>{xr.icon} {html.escape(xr.relationship_type)}</td><td>{html.escape(xr.direction)}</td><td>{int(xr.confidence * 100)}%</td></tr>")
            html_buf.append("      </table>")
            html_buf.append("    </div>")

        # Vector Proximity
        if self.vector_neighbors:
            html_buf.append("    <div class=\"card\">")
            html_buf.append("      <h2>6. Dense Semantic Vector Proximity (Nearest Neighbors)</h2>")
            html_buf.append("      <table>")
            html_buf.append("        <tr><th>Rank</th><th>Match</th><th>Passage</th><th>Title</th></tr>")
            for vn in self.vector_neighbors:
                html_buf.append(f"        <tr><td>#{vn.rank}</td><td><span class=\"badge\">{vn.match_pct}%</span></td><td>[{html.escape(vn.human_ref)}]</td><td>{html.escape(vn.title)}</td></tr>")
            html_buf.append("      </table>")
            html_buf.append("    </div>")

        # Persona Reflections
        if self.persona_perspectives:
            html_buf.append("    <div class=\"card\">")
            html_buf.append("      <h2>7. Biblical Character Persona Exegesis</h2>")
            for pp in self.persona_perspectives:
                author_flag = " (Canonical Author)" if pp.is_author else ""
                html_buf.append(f"      <h3>👤 {html.escape(pp.name)} &mdash; {html.escape(pp.title)}{author_flag}</h3>")
                html_buf.append(f"      <blockquote>{html.escape(pp.pastoral_reflection)}</blockquote>")
            html_buf.append("    </div>")

        html_buf.append("    <footer>")
        html_buf.append("      Sovereign Bible Engine &bull; Zero External Dependencies &bull; Sacred-Modern Architecture")
        html_buf.append("    </footer>")
        html_buf.append("  </div>")
        html_buf.append("</body>")
        html_buf.append("</html>")
        return "\n".join(html_buf)

    def to_ansi(self, color: bool = True, theme: str = "sacred") -> str:
        """Render an illuminated ANSI layout for the terminal."""
        t_style = THEMES.get(theme, THEMES["sacred"])
        c_gold = t_style["header"] if color else ""
        c_cyan = t_style["verse_num"] if color else ""
        c_dim = t_style["dim"] if color else ""
        c_bold = BOLD if color else ""
        c_reset = RESET if color else ""
        c_green = GREEN if color else ""

        lines: List[str] = []
        bar_w = 78
        lines.append(f"{c_gold}╔═{'═' * bar_w}╗{c_reset}")
        title_str = f" Exegetical Study Dossier: {self.human_ref} "
        pad_l = (bar_w - len(title_str)) // 2
        pad_r = bar_w - len(title_str) - pad_l
        lines.append(f"{c_gold}║{c_reset}{' ' * pad_l}{c_bold}{c_gold}{title_str}{c_reset}{' ' * pad_r}{c_gold}║{c_reset}")
        meta_str = f" Canon: {self.book_name} ({self.testament} • Book #{self.canon_order}) • {self.generated_at} "
        pad_ml = (bar_w - len(meta_str)) // 2
        pad_mr = bar_w - len(meta_str) - pad_ml
        lines.append(f"{c_gold}║{c_reset}{' ' * pad_ml}{c_dim}{meta_str}{c_reset}{' ' * pad_mr}{c_gold}║{c_reset}")
        lines.append(f"{c_gold}╚═{'═' * bar_w}╝{c_reset}")
        lines.append("")

        # Pericope Passport
        if self.pericopes:
            p = self.pericopes[0]
            lines.append(f"{c_gold}📖 PARENT PERICOPE PASSPORT{c_reset}")
            lines.append(f"   • Title:      {c_bold}{p.title}{c_reset} ({p.human_ref})")
            if p.genre or p.literary_structure:
                lines.append(f"   • Structure:  {p.genre} — {p.literary_structure}")
            if p.central_proposition:
                lines.append(f"   • Exegesis:   {c_cyan}\"{p.central_proposition}\"{c_reset}")
            if p.redemptive_summary:
                lines.append(f"   • Redemptive: {c_dim}{p.redemptive_summary}{c_reset}")
            lines.append("")

        # Section 1: Scripture Text
        lines.append(f"{c_gold}📜 SCRIPTURE TEXT{c_reset}")
        for tr_id, verses in self.verses_by_translation.items():
            lines.append(f"   {c_bold}[{tr_id}]{c_reset}")
            for v in verses:
                lines.append(f"   {c_cyan}[{v.verse}]{c_reset} {v.text}")
            lines.append("")

        # Section 2: Theology & Tags
        if self.theology or self.tags:
            lines.append(f"{c_gold}🧠 THEOLOGY & SEMANTIC MOTIFS{c_reset}")
            if self.theology:
                lines.append(f"   • Epoch:      {c_cyan}{self.theology.storyline_epoch or 'canonical'}{c_reset}")
                lines.append(f"   • Locus:      {c_cyan}{self.theology.theological_locus or 'theology'}{c_reset}")
                lines.append(f"   • Doctrine:   {c_bold}{self.theology.primary_doctrine or 'general'}{c_reset}")
            if self.tags:
                tag_badges = " ".join([f"{c_green}[{t.name}]{c_reset}" for t in self.tags[:10]])
                lines.append(f"   • Tags:       {tag_badges}")
            lines.append("")

        # Section 3: Typological Arcs
        if self.typological_arcs:
            lines.append(f"{c_gold}🏛 REDEMPTIVE TYPOLOGICAL ARCS{c_reset}")
            for arc in self.typological_arcs:
                lines.append(f"   • {c_bold}{arc.title}{c_reset}: [{arc.type_ref}] ➔ [{arc.antitype_ref}]")
                if arc.theological_correspondence:
                    lines.append(f"     {c_dim}{arc.theological_correspondence}{c_reset}")
            lines.append("")

        # Section 4: Cross-References
        if self.cross_references:
            lines.append(f"{c_gold}🔗 CANONICAL CROSS-REFERENCES (TSK){c_reset}")
            for xr in self.cross_references[:10]:
                lines.append(f"   • {xr.icon} {c_bold}[{xr.target_ref:<18}]{c_reset} {xr.relationship_type:<14} ({int(xr.confidence*100)}%) {c_dim}{xr.direction}{c_reset}")
            lines.append("")

        # Section 5: Vector Proximity
        if self.vector_neighbors:
            lines.append(f"{c_gold}🧭 DENSE VECTOR PROXIMITY (TOPOLOGICAL NEIGHBORS){c_reset}")
            for vn in self.vector_neighbors:
                lines.append(f"   • #{vn.rank} {c_green}[{vn.match_pct}]{c_reset} {c_bold}[{vn.human_ref:<16}]{c_reset} {vn.title}")
            lines.append("")

        # Section 6: Persona Perspectives
        if self.persona_perspectives:
            lines.append(f"{c_gold}👤 BIBLICAL PERSONA EXEGESIS{c_reset}")
            for pp in self.persona_perspectives:
                author_badge = f" {c_green}(Canonical Author){c_reset}" if pp.is_author else ""
                lines.append(f"   • {c_bold}{pp.name}{c_reset} — {pp.title}{author_badge}")
                lines.append(f"     {c_dim}\"{pp.pastoral_reflection}\"{c_reset}")
            lines.append("")

        lines.append(f"{c_dim}──────────────────────────────────────────────────────────────────────────────{c_reset}")
        return "\n".join(lines)

    def to_text(self) -> str:
        """Render clean plain ASCII text without ANSI escape sequences."""
        return self.to_ansi(color=False)


class ExegeticalDossierService:
    """High-velocity service to construct comprehensive study dossiers from SQLite data."""

    def __init__(self, db: Database, recommender: Optional[PericopeRecommender] = None) -> None:
        self.db = db
        self.recommender = recommender

    def generate_dossier(
        self,
        reference: Union[Reference, str],
        translations: Sequence[str] = ("WEB", "KJV"),
        top_crossrefs: int = 15,
        top_vectors: int = 5,
        include_personas: bool = True,
        persona_id: Optional[str] = None,
    ) -> ExegeticalDossier:
        """Generate a complete Exegetical Study Dossier for the given Scripture reference.

        Args:
            reference: Reference or citation string (e.g. "Romans 8:28-30").
            translations: List of Bible translations to hydrate.
            top_crossrefs: Maximum number of prioritized cross-references.
            top_vectors: Maximum number of dense vector neighbors.
            include_personas: Whether to include biblical persona reflections.
            persona_id: Specific persona to highlight, or None for automatic author matching.

        Returns:
            Fully populated ExegeticalDossier instance.
        """
        ref = parse_reference(reference) if isinstance(reference, str) else reference
        b_name = ref.book.name
        testament = ref.book.testament
        canon_order = ref.book.number
        human_ref = ref.format()

        if not translations:
            avail = self.db.get_available_translation_ids()
            translations = tuple(avail) if avail else ("WEB", "KJV")

        # 1. Hydrate Scripture verses for each translation
        verses_by_tr: Dict[str, List[VerseRecord]] = {}
        for tr in translations:
            try:
                v_list = self.db.get_verses_by_reference(ref, translation_id=tr)
                if v_list:
                    verses_by_tr[tr] = list(v_list)
            except Exception:
                pass

        # If none found, attempt default WEB fallback
        if not verses_by_tr:
            try:
                v_fallback = self.db.get_verses_by_reference(ref, translation_id="WEB")
                if v_fallback:
                    verses_by_tr["WEB"] = list(v_fallback)
            except Exception:
                pass

        # 2. Pericopes
        pericopes: List[DossierPericope] = []
        try:
            p_records = self.db.get_pericopes_for_reference(ref)
            for p in p_records:
                pericopes.append(
                    DossierPericope(
                        id=p.id,
                        title=p.title,
                        human_ref=p.human_ref,
                        genre=p.genre or "",
                        literary_structure=p.literary_structure or "",
                        central_proposition=p.central_proposition or "",
                        redemptive_summary=p.redemptive_summary or "",
                    )
                )
        except Exception:
            pass

        # 3. Theological Facets
        theology: Optional[DossierTheology] = None
        try:
            t_records = self.db.get_verse_theology_for_reference(ref)
            if t_records:
                first_t = t_records[0]
                theology = DossierTheology(
                    storyline_epoch=getattr(first_t, "storyline_epoch", "") or "",
                    theological_locus=getattr(first_t, "theological_locus", "") or "",
                    primary_doctrine=getattr(first_t, "primary_doctrine", "") or "",
                    thematic_ribbon=getattr(first_t, "thematic_ribbon", "") or "",
                )
        except Exception:
            pass

        # 4. Semantic Tags
        tags: List[DossierTag] = []
        seen_tags = set()
        try:
            t_list = self.db.get_tags_for_reference(ref)
            for t in t_list:
                name = getattr(t, "tag_name", "") or (t.get("name") if isinstance(t, dict) else "")
                if not name or name in seen_tags:
                    continue
                seen_tags.add(name)
                cat = getattr(t, "category", "") or (t.get("category") if isinstance(t, dict) else "thematic")
                conf = float(getattr(t, "confidence", 1.0) or 1.0)
                starred = bool(getattr(t, "starred", False))
                notes = getattr(t, "notes", "") or ""
                tags.append(
                    DossierTag(
                        name=name,
                        category=cat or "thematic",
                        confidence=conf,
                        starred=starred,
                        notes=notes,
                    )
                )
        except Exception:
            pass

        # 5. Typological Arcs
        typological_arcs: List[DossierTypologicalArc] = []
        try:
            arc_records = self.db.get_typological_arcs_for_reference(ref)
            for a in arc_records:
                t_ref = getattr(a, "type_human_ref", "") or getattr(a, "type_ref", "")
                at_ref = getattr(a, "antitype_human_ref", "") or getattr(a, "antitype_ref", "")
                title = getattr(a, "title", "") or f"{t_ref} ➔ {at_ref}"
                corr = getattr(a, "theological_correspondence", "") or ""
                warrant = getattr(a, "warrant", "") or ""
                typological_arcs.append(
                    DossierTypologicalArc(
                        id=getattr(a, "id", 0),
                        title=title,
                        type_ref=t_ref,
                        antitype_ref=at_ref,
                        theological_correspondence=corr,
                        warrant=warrant,
                    )
                )
        except Exception:
            pass

        # 6. Cross-References
        cross_references: List[DossierCrossRef] = []
        try:
            x_records = self.db.get_cross_references(ref, bidirectional=True)
            icon_map = {
                "quotation": "📜",
                "prophecy_fulfillment": "⚡",
                "typology": "🏛",
                "thematic": "🔗",
                "allusion": "✨",
                "parallel": "⚖",
            }
            seen_targets = set()
            for xr in x_records:
                s_start = getattr(xr, "source_start_id", 0)
                s_end = getattr(xr, "source_end_id", 0)
                is_source = s_start <= ref.canonical_end_id and s_end >= ref.canonical_start_id
                target_str = getattr(xr, "target_human_ref", "") if is_source else getattr(xr, "source_human_ref", "")
                direction = "outgoing" if is_source else "incoming"
                if not target_str or target_str in seen_targets:
                    continue
                seen_targets.add(target_str)
                rel_type = getattr(xr, "relationship_type", "thematic")
                weight = float(getattr(xr, "weight", 1.0) or 1.0)
                notes = getattr(xr, "notes", "") or ""
                cross_references.append(
                    DossierCrossRef(
                        target_ref=target_str,
                        direction=direction,
                        relationship_type=rel_type,
                        icon=icon_map.get(rel_type, "🔗"),
                        confidence=weight,
                        notes=notes,
                    )
                )
                if len(cross_references) >= top_crossrefs:
                    break
        except Exception:
            pass

        # 7. Dense Semantic Vector Proximity
        vector_neighbors: List[DossierVectorNeighbor] = []
        rec = self.recommender or get_pericope_recommender(db=self.db)
        if rec and top_vectors > 0:
            try:
                res = rec.recommend_for_reference(ref, top_k=top_vectors + 2)
                matches = res.get("matches", [])
                for m in matches:
                    if pericopes and m.get("pericope_id") == pericopes[0].id:
                        continue
                    vector_neighbors.append(
                        DossierVectorNeighbor(
                            rank=len(vector_neighbors) + 1,
                            score=float(m.get("score") or 0.0),
                            match_pct=m.get("match_pct") or f"{float(m.get('score') or 0.0)*100:.1f}%",
                            title=m.get("title") or "",
                            human_ref=m.get("human_ref") or "",
                            book_name=m.get("book_name") or "",
                            genre=m.get("genre") or "",
                            redemptive_summary=m.get("redemptive_summary") or "",
                        )
                    )
                    if len(vector_neighbors) >= top_vectors:
                        break
            except Exception:
                pass

        # 8. Biblical Character Persona Perspectives
        persona_perspectives: List[DossierPersonaPerspective] = []
        if include_personas:
            try:
                matched_personas: List[Tuple[CharacterPersonaDefinition, bool]] = []
                for p_def in CANONICAL_PERSONAS:
                    if persona_id and p_def.id == persona_id:
                        matched_personas.append((p_def, b_name in p_def.author_books))
                    elif not persona_id and b_name in p_def.author_books:
                        matched_personas.append((p_def, True))

                if not persona_id:
                    wb_list = [p for p in CANONICAL_PERSONAS if p.id == "whole-bible"]
                    if wb_list and (wb_list[0], False) not in matched_personas:
                        matched_personas.append((wb_list[0], False))

                for p_def, is_author in matched_personas[:2]:
                    role_desc = p_def.theological_role or p_def.canonical_era
                    refl = (
                        f"Reflecting on {human_ref}: {role_desc}. "
                        f"Christ-centered focus: {p_def.christ_centered_orientation}"
                    )
                    persona_perspectives.append(
                        DossierPersonaPerspective(
                            persona_id=p_def.id,
                            name=p_def.canonical_name,
                            title=p_def.canonical_era,
                            canonical_era=p_def.canonical_era,
                            is_author=is_author,
                            pastoral_reflection=refl,
                        )
                    )
            except Exception:
                pass

        return ExegeticalDossier(
            reference=ref,
            human_ref=human_ref,
            book_name=b_name,
            testament=testament,
            canon_order=canon_order,
            verses_by_translation=verses_by_tr,
            pericopes=pericopes,
            theology=theology,
            tags=tags,
            typological_arcs=typological_arcs,
            cross_references=cross_references,
            vector_neighbors=vector_neighbors,
            persona_perspectives=persona_perspectives,
        )
