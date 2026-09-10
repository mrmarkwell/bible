"""Semantic Passport Generator & Structured Context Formulator for Pericopes.

Implementation per ADR-083 (Semantic Passport Architecture) and ADR-003 (Zero External Dependencies):
- Synthesizes structured "Semantic Passport" documents for canonical pericopes.
- Formulates multi-tiered metadata:
    * [DOCUMENT TITLE]: Book Chapter:Verse range + Pericope heading.
    * [CANONICAL HORIZON]: Author, genre, historical epoch, and redemptive-historical trajectory (from BookHorizon).
    * [THEOLOGICAL LOCI & RIBBONS]: Systematic theological categories and redemptive themes.
    * [CENTRAL PROPOSITION]: The exegetical main idea and Christological purpose.
    * [PRECEDING DISCOURSE]: Narrative or argumentative context/transition.
    * [SCRIPTURE TEXT]: Full passage text with bracketed verse numbers.
- Acts as a high-density semantic beacon for dense vector embedding via Google Gemini text-embedding-004
  or local hash pseudo-embeddings.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Union

from core.db import Database, PericopeRecord
from core.reference import Reference, get_book, parse_reference
from core.semantic_prompts import BookHorizon, get_book_horizon


@dataclass(frozen=True)
class SemanticPassport:
    """Represents a structured Semantic Passport document for a canonical pericope."""

    pericope_id: Optional[int]
    reference: Reference
    title: str
    book_horizon: Optional[BookHorizon]
    genre: str
    central_proposition: str
    redemptive_summary: str
    theological_loci: Sequence[str]
    thematic_ribbons: Sequence[str]
    preceding_context: str
    scripture_text: str

    def format_document(self) -> str:
        """Format the pericope into a structured Semantic Passport text document."""
        lines: List[str] = []

        # 1. Document Title
        clean_title = self.title.strip() if self.title else "Canonical Scripture Passage"
        lines.append(f"[DOCUMENT TITLE]: {self.reference.format()} — {clean_title}")

        # 2. Canonical Horizon
        if self.book_horizon:
            h = self.book_horizon
            horizon_desc = (
                f"Author: {h.author} | Era: {h.date_range} | Epoch: {h.storyline_epoch} | "
                f"Testament: {h.testament} | Setting: {h.historical_setting}"
            )
            lines.append(f"[CANONICAL HORIZON]: {horizon_desc}")
            if h.theological_theme:
                lines.append(f"[BOOK THEME]: {h.theological_theme}")
            if h.christological_anticipation:
                lines.append(f"[CHRISTOLOGICAL ANTICIPATION]: {h.christological_anticipation}")
        else:
            lines.append(f"[CANONICAL HORIZON]: {self.reference.book.name} ({self.genre})")

        # 3. Theological Loci & Ribbons
        loci_str = ", ".join(self.theological_loci) if self.theological_loci else "Systematic Exegesis"
        ribbons_str = ", ".join(self.thematic_ribbons) if self.thematic_ribbons else "Covenant Grace"
        lines.append(f"[THEOLOGICAL LOCI]: {loci_str}")
        lines.append(f"[THEMATIC RIBBONS]: {ribbons_str}")

        # 4. Central Proposition & Redemptive Summary
        if self.central_proposition:
            lines.append(f"[CENTRAL PROPOSITION]: {self.central_proposition.strip()}")
        if self.redemptive_summary:
            lines.append(f"[REDEMPTIVE SUMMARY]: {self.redemptive_summary.strip()}")

        # 5. Preceding Discourse / Narrative Context
        if self.preceding_context:
            lines.append(f"[PRECEDING CONTEXT]: {self.preceding_context.strip()}")

        # 6. Scripture Text
        if self.scripture_text:
            lines.append(f"[SCRIPTURE TEXT]:\n{self.scripture_text.strip()}")

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Convert Semantic Passport to JSON-serializable dictionary."""
        return {
            "pericope_id": self.pericope_id,
            "reference": self.reference.format(),
            "title": self.title,
            "genre": self.genre,
            "central_proposition": self.central_proposition,
            "redemptive_summary": self.redemptive_summary,
            "theological_loci": list(self.theological_loci),
            "thematic_ribbons": list(self.thematic_ribbons),
            "preceding_context": self.preceding_context,
            "scripture_text": self.scripture_text,
            "document_text": self.format_document(),
        }


class SemanticPassportGenerator:
    """Generates structured Semantic Passport documents from SQLite database records."""

    def __init__(self, db: Database, translation_id: str = "WEB") -> None:
        self.db = db
        self.translation_id = translation_id.strip().upper()

    def generate_for_pericope_record(
        self,
        record: Union[PericopeRecord, Dict[str, Any], Any],
        preceding_context: str = "",
    ) -> SemanticPassport:
        """Generate a Semantic Passport from a PericopeRecord or row dictionary."""
        if isinstance(record, dict) or hasattr(record, "keys"):
            pid = record["id"] if "id" in record.keys() else record.get("id")
            human_ref = record["human_ref"] if "human_ref" in record.keys() else record.get("human_ref", "")
            title = record["title"] if "title" in record.keys() else record.get("title", "")
            redemptive_summary = record["redemptive_summary"] if "redemptive_summary" in record.keys() else record.get("redemptive_summary", "")
            genre = record["genre"] if "genre" in record.keys() else record.get("genre", "Other")
            central_prop = record["central_proposition"] if "central_proposition" in record.keys() else record.get("central_proposition", "")
            s_id = record["start_canonical_id"] if "start_canonical_id" in record.keys() else record.get("start_canonical_id", 0)
            e_id = record["end_canonical_id"] if "end_canonical_id" in record.keys() else record.get("end_canonical_id", 0)
            b_id = record["book_id"] if "book_id" in record.keys() else record.get("book_id", 1)
        else:
            pid = getattr(record, "id", None)
            human_ref = getattr(record, "human_ref", "")
            title = getattr(record, "title", "")
            redemptive_summary = getattr(record, "redemptive_summary", "")
            genre = getattr(record, "genre", "Other")
            central_prop = getattr(record, "central_proposition", "")
            s_id = getattr(record, "start_canonical_id", 0)
            e_id = getattr(record, "end_canonical_id", 0)
            b_id = getattr(record, "book_id", 1)

        ref: Reference
        try:
            ref = parse_reference(human_ref)
        except Exception:
            b = get_book(b_id) or get_book(1)
            ref = parse_reference(f"{b.name} 1:1")

        # Fetch Book Horizon
        horizon: Optional[BookHorizon] = None
        try:
            horizon = get_book_horizon(ref.book.number)
        except Exception:
            pass

        # Query associated theology records for loci and thematic ribbons
        theological_loci: List[str] = []
        thematic_ribbons: List[str] = []

        try:
            cur = self.db.conn.cursor()
            rows = cur.execute(
                """
                SELECT theological_locus, thematic_ribbon
                FROM verse_theology
                WHERE (start_canonical_id <= ? AND end_canonical_id >= ?)
                   OR (start_canonical_id >= ? AND start_canonical_id <= ?)
                """,
                (e_id, s_id, s_id, e_id),
            ).fetchall()
            for r in rows:
                loc = r[0] if isinstance(r, (tuple, list)) else r["theological_locus"]
                rib = r[1] if isinstance(r, (tuple, list)) else r["thematic_ribbon"]
                if loc and loc not in theological_loci:
                    theological_loci.append(loc)
                if rib and rib not in thematic_ribbons:
                    thematic_ribbons.append(rib)
        except Exception:
            pass

        # Also pull associated tags for ribbons/loci enrichment if available
        try:
            cur = self.db.conn.cursor()
            tag_rows = cur.execute(
                """
                SELECT t.name, t.category
                FROM tags t
                JOIN verse_tags vt ON t.id = vt.tag_id
                WHERE vt.start_canonical_id <= ? AND vt.end_canonical_id >= ?
                """,
                (e_id, s_id),
            ).fetchall()
            for tr in tag_rows:
                tname = tr[0] if isinstance(tr, (tuple, list)) else tr["name"]
                tcat = tr[1] if isinstance(tr, (tuple, list)) else tr["category"]
                if tcat == "theological" and tname not in theological_loci:
                    theological_loci.append(tname)
                elif tcat == "thematic" and tname not in thematic_ribbons:
                    thematic_ribbons.append(tname)
        except Exception:
            pass

        # Fetch Scripture Passage Text
        scripture_text = self._fetch_scripture_text(ref)

        return SemanticPassport(
            pericope_id=pid,
            reference=ref,
            title=title or ref.format(),
            book_horizon=horizon,
            genre=genre or (horizon.genre if horizon else "Biblical Text"),
            central_proposition=central_prop or "",
            redemptive_summary=redemptive_summary or "",
            theological_loci=theological_loci,
            thematic_ribbons=thematic_ribbons,
            preceding_context=preceding_context,
            scripture_text=scripture_text,
        )

    def generate_for_pericope_id(self, pericope_id: int) -> Optional[SemanticPassport]:
        """Generate a Semantic Passport for a specific pericope ID in SQLite."""
        cur = self.db.conn.cursor()
        row = cur.execute(
            """
            SELECT id, book_id, start_canonical_id, end_canonical_id, human_ref,
                   title, redemptive_summary, genre, literary_structure, central_proposition
            FROM pericopes
            WHERE id = ?
            """,
            (pericope_id,),
        ).fetchone()
        if not row:
            return None

        # Fetch preceding pericope title/reference for preceding context
        preceding_text = ""
        b_id = row["book_id"] if isinstance(row, dict) else row[1]
        s_id = row["start_canonical_id"] if isinstance(row, dict) else row[2]
        prev_row = cur.execute(
            """
            SELECT human_ref, title, central_proposition
            FROM pericopes
            WHERE book_id = ? AND end_canonical_id < ?
            ORDER BY end_canonical_id DESC
            LIMIT 1
            """,
            (b_id, s_id),
        ).fetchone()
        if prev_row:
            p_ref = prev_row["human_ref"] if isinstance(prev_row, dict) else prev_row[0]
            p_title = prev_row["title"] if isinstance(prev_row, dict) else prev_row[1]
            p_prop = prev_row["central_proposition"] if isinstance(prev_row, dict) else prev_row[2]
            preceding_text = f"Following {p_ref} ({p_title}): {p_prop}".strip()

        return self.generate_for_pericope_record(row, preceding_context=preceding_text)

    def _fetch_scripture_text(self, ref: Reference) -> str:
        """Fetch passage text with verse numbers from SQLite database."""
        verses = self.db.get_verses_by_reference(ref, translation_id=self.translation_id)
        if not verses and self.translation_id != "WEB":
            verses = self.db.get_verses_by_reference(ref, translation_id="WEB")
        if not verses:
            return ""
        return " ".join(f"[{v.verse}] {v.text.strip()}" for v in verses)


def generate_semantic_passport(
    db: Database,
    pericope: Union[int, PericopeRecord, Dict[str, Any]],
    translation_id: str = "WEB",
) -> Optional[SemanticPassport]:
    """Convenience helper to generate a Semantic Passport."""
    generator = SemanticPassportGenerator(db, translation_id=translation_id)
    if isinstance(pericope, int):
        return generator.generate_for_pericope_id(pericope)
    return generator.generate_for_pericope_record(pericope)
