"""Exegetical Critic & Quality Audit Suite for Bible Engine Semantic Architecture.

Zero-dependency implementation per ADR-003, ADR-006, ADR-042, ADR-050, ADR-052, ADR-054, and ADR-055:
1. Canonical Coordinate Boundary Engine:
   - Authoritative chapter & verse limits across all 66 canonical books (1,189 chapters, 31,103 verses).
   - Strict validation of integer coordinates (BBCCCVVV) and spans (start <= end, book bounds).
   - Canonical coordinate expansion (stepping chapter-by-chapter across verse boundaries).
2. Semantic Schema & Exegetical Critic Engine:
   - Deep structural and qualitative audit of pericopes, discourse relations, verse theology,
     typological arcs, and semantic propositions.
   - Hermeneutical review: gospel uniqueness checks (grace vs. legalism and relativism) against TGC Foundation Documents,
     Christological fulfillment depth, and valid theological loci/epochs.
3. Character Entity Deduplication & Normalization:
   - Authoritative registry of canonical Biblical characters with aliases, testament scope, and roles.
   - Context-aware disambiguation (e.g., Saul of Tarsus vs King Saul, John the Baptist vs John the Apostle).
   - Deduplication and alias resolution across pericope propositions.
4. 100% Whole-Bible Verse Coverage Auditor:
   - Tracks all 31,103 canonical verses across 66 books.
   - Detects pericope gaps, overlaps, missing chapters/books, and per-book coverage percentages.
   - Produces structured coverage reports with summary tables and JSON export.
5. Unified Quality Audit Suite:
   - Comprehensive audit orchestrator for in-memory DTOs, batch outputs, or live SQLite database.
"""

from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path
import re
import sqlite3
import time
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

from core.db import (
    Database,
    DiscourseRelationRecord,
    PericopeRecord,
    SemanticPropositionRecord,
    TypologicalArcRecord,
    VerseTheologyRecord,
)
from core.reference import (
    BOOKS,
    canonical_id_to_triple,
    parse_reference,
)
from core.semantic_prompts import (
    DISCOURSE_RELATION_TYPES,
    DiscourseRelationData,
    LITERARY_GENRES,
    PericopeAnalysisResult,
    SPEECH_ACT_TYPES,
    SemanticPropositionData,
    TypologicalArcData,
    VerseTheologyData,
)
from core.theology import (
    RedemptiveEpoch,
    ThematicRibbon,
    TheologicalLocus,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


# ==============================================================================
# 1. Canonical Coordinate Boundary Catalog & Limits (66 Books, 1,189 Chapters)
# ==============================================================================

TOTAL_CANONICAL_BOOKS: int = 66
TOTAL_CANONICAL_CHAPTERS: int = 1189
TOTAL_CANONICAL_VERSES: int = 31103

# Authoritative maximum verse count for every chapter in each book (1-indexed books).
# Key: book_id (1..66), Value: tuple of max verse numbers for chapters 1..total_chapters.
BOOK_CHAPTER_VERSES: Dict[int, Tuple[int, ...]] = {
    1: (31, 25, 24, 26, 32, 22, 24, 22, 29, 32, 32, 20, 18, 24, 21, 16, 27, 33, 38, 18, 34, 24, 20, 67, 34, 35, 46, 22, 35, 43, 55, 32, 20, 31, 29, 43, 36, 30, 23, 23, 57, 38, 34, 34, 28, 34, 31, 22, 33, 26),
    2: (22, 25, 22, 31, 23, 30, 25, 32, 35, 29, 10, 51, 22, 31, 27, 36, 16, 27, 25, 26, 36, 31, 33, 18, 40, 37, 21, 43, 46, 38, 18, 35, 23, 35, 35, 38, 29, 31, 43, 38),
    3: (17, 16, 17, 35, 19, 30, 38, 36, 24, 20, 47, 8, 59, 57, 33, 34, 16, 30, 37, 27, 24, 33, 44, 23, 55, 46, 34),
    4: (54, 34, 51, 49, 31, 27, 89, 26, 23, 36, 35, 16, 33, 45, 41, 50, 13, 32, 22, 29, 35, 41, 30, 25, 18, 65, 23, 31, 40, 16, 54, 42, 56, 29, 34, 13),
    5: (46, 37, 29, 49, 33, 25, 26, 20, 29, 22, 32, 32, 18, 29, 23, 22, 20, 22, 21, 20, 23, 30, 25, 22, 19, 19, 26, 68, 29, 20, 30, 52, 29, 12),
    6: (18, 24, 17, 24, 15, 27, 26, 35, 27, 43, 23, 24, 33, 15, 63, 10, 18, 28, 51, 9, 45, 34, 16, 33),
    7: (36, 23, 31, 24, 31, 40, 25, 35, 57, 18, 40, 15, 25, 20, 20, 31, 13, 31, 30, 48, 25),
    8: (22, 23, 18, 22),
    9: (28, 36, 21, 22, 12, 21, 17, 22, 27, 27, 15, 25, 23, 52, 35, 23, 58, 30, 24, 42, 15, 23, 29, 22, 44, 25, 12, 25, 11, 31, 13),
    10: (27, 32, 39, 12, 25, 23, 29, 18, 13, 19, 27, 31, 39, 33, 37, 23, 29, 33, 43, 26, 22, 51, 39, 25),
    11: (53, 46, 28, 34, 18, 38, 51, 66, 28, 29, 43, 33, 34, 31, 34, 34, 24, 46, 21, 43, 29, 53),
    12: (18, 25, 27, 44, 27, 33, 20, 29, 37, 36, 21, 21, 25, 29, 38, 20, 41, 37, 37, 21, 26, 20, 37, 20, 30),
    13: (54, 55, 24, 43, 26, 81, 40, 40, 44, 14, 47, 40, 14, 17, 29, 43, 27, 17, 19, 8, 30, 19, 32, 31, 31, 32, 34, 21, 30),
    14: (17, 18, 17, 22, 14, 42, 22, 18, 31, 19, 23, 16, 22, 15, 19, 14, 19, 34, 11, 37, 20, 12, 21, 27, 28, 23, 9, 27, 36, 27, 21, 33, 25, 33, 27, 23),
    15: (11, 70, 13, 24, 17, 22, 28, 36, 15, 44),
    16: (11, 20, 32, 23, 19, 19, 73, 18, 38, 39, 36, 47, 31),
    17: (22, 23, 15, 17, 14, 14, 10, 17, 32, 3),
    18: (22, 13, 26, 21, 27, 30, 21, 22, 35, 22, 20, 25, 28, 22, 35, 22, 16, 21, 29, 29, 34, 30, 17, 25, 6, 14, 23, 28, 25, 31, 40, 22, 33, 37, 16, 33, 24, 41, 30, 24, 34, 17),
    19: (6, 12, 8, 8, 12, 10, 17, 9, 20, 18, 7, 8, 6, 7, 5, 11, 15, 50, 14, 9, 13, 31, 6, 10, 22, 12, 14, 9, 11, 12, 24, 11, 22, 22, 28, 12, 40, 22, 13, 17, 13, 11, 5, 26, 17, 11, 9, 14, 20, 23, 19, 9, 6, 7, 23, 13, 11, 11, 17, 12, 8, 12, 11, 10, 13, 20, 7, 35, 36, 5, 24, 20, 28, 23, 10, 12, 20, 72, 13, 19, 16, 8, 18, 12, 13, 17, 7, 18, 52, 17, 16, 15, 5, 23, 11, 13, 12, 9, 9, 5, 8, 28, 22, 35, 45, 48, 43, 13, 31, 7, 10, 10, 9, 8, 18, 19, 2, 29, 176, 7, 8, 9, 4, 8, 5, 6, 5, 6, 8, 8, 3, 18, 3, 3, 21, 26, 9, 8, 24, 13, 10, 7, 12, 15, 21, 10, 20, 14, 9, 6),
    20: (33, 22, 35, 27, 23, 35, 27, 36, 18, 32, 31, 28, 25, 35, 33, 33, 28, 24, 29, 30, 31, 29, 35, 34, 28, 28, 27, 28, 27, 33, 31),
    21: (18, 26, 22, 16, 20, 12, 29, 17, 18, 20, 10, 14),
    22: (17, 17, 11, 16, 16, 13, 13, 14),
    23: (31, 22, 26, 6, 30, 13, 25, 22, 21, 34, 16, 6, 22, 32, 9, 14, 14, 7, 25, 6, 17, 25, 18, 23, 12, 21, 13, 29, 24, 33, 9, 20, 24, 17, 10, 22, 38, 22, 8, 31, 29, 25, 28, 28, 25, 13, 15, 22, 26, 11, 23, 15, 12, 17, 13, 12, 21, 14, 21, 22, 11, 12, 19, 12, 25, 24),
    24: (19, 37, 25, 31, 31, 30, 34, 22, 26, 25, 23, 17, 27, 22, 21, 21, 27, 23, 15, 18, 14, 30, 40, 10, 38, 24, 22, 17, 32, 24, 40, 44, 26, 22, 19, 32, 21, 28, 18, 16, 18, 22, 13, 30, 5, 28, 7, 47, 39, 46, 64, 34),
    25: (22, 22, 66, 22, 22),
    26: (28, 10, 27, 17, 17, 14, 27, 18, 11, 22, 25, 28, 23, 23, 8, 63, 24, 32, 14, 49, 32, 31, 49, 27, 17, 21, 36, 26, 21, 26, 18, 32, 33, 31, 15, 38, 28, 23, 29, 49, 26, 20, 27, 31, 25, 24, 23, 35),
    27: (21, 49, 30, 37, 31, 28, 28, 27, 27, 21, 45, 13),
    28: (11, 23, 5, 19, 15, 11, 16, 14, 17, 15, 12, 14, 16, 9),
    29: (20, 32, 21),
    30: (15, 16, 15, 13, 27, 14, 17, 14, 15),
    31: (21,),
    32: (17, 10, 10, 11),
    33: (16, 13, 12, 13, 15, 16, 20),
    34: (15, 13, 19),
    35: (17, 20, 19),
    36: (18, 15, 20),
    37: (15, 23),
    38: (21, 13, 10, 14, 11, 15, 14, 23, 17, 12, 17, 14, 9, 21),
    39: (14, 17, 18, 6),
    40: (25, 23, 17, 25, 48, 34, 29, 34, 38, 42, 30, 50, 58, 36, 39, 28, 27, 35, 30, 34, 46, 46, 39, 51, 46, 75, 66, 20),
    41: (45, 28, 35, 41, 43, 56, 37, 38, 50, 52, 33, 44, 37, 72, 47, 20),
    42: (80, 52, 38, 44, 39, 49, 50, 56, 62, 42, 54, 59, 35, 35, 32, 31, 37, 43, 48, 47, 38, 71, 56, 53),
    43: (51, 25, 36, 54, 47, 71, 53, 59, 41, 42, 57, 50, 38, 31, 27, 33, 26, 40, 42, 31, 25),
    44: (26, 47, 26, 37, 42, 15, 60, 40, 43, 48, 30, 25, 52, 28, 41, 40, 34, 28, 41, 38, 40, 30, 35, 27, 27, 32, 44, 31),
    45: (32, 29, 31, 25, 21, 23, 25, 39, 33, 21, 36, 21, 14, 26, 33, 25),
    46: (31, 16, 23, 21, 13, 20, 40, 13, 27, 33, 34, 31, 13, 40, 58, 24),
    47: (24, 17, 18, 18, 21, 18, 16, 24, 15, 18, 33, 21, 14),
    48: (24, 21, 29, 31, 26, 18),
    49: (23, 22, 21, 32, 33, 24),
    50: (30, 30, 21, 23),
    51: (29, 23, 25, 18),
    52: (10, 20, 13, 18, 28),
    53: (12, 17, 18),
    54: (20, 15, 16, 16, 25, 21),
    55: (18, 26, 17, 22),
    56: (16, 15, 15),
    57: (25,),
    58: (14, 18, 19, 16, 14, 20, 28, 13, 28, 39, 40, 29, 25),
    59: (27, 26, 18, 17, 20),
    60: (25, 25, 22, 19, 14),
    61: (21, 22, 18),
    62: (10, 29, 24, 21, 21),
    63: (13,),
    64: (14,),
    65: (25,),
    66: (20, 29, 22, 11, 14, 17, 17, 13, 21, 11, 19, 17, 18, 20, 8, 21, 18, 24, 21, 15, 27, 21),
}


def get_canonical_max_verse(book_id: int, chapter: int) -> int:
    """Return the canonical maximum verse number for a given book and chapter.

    Returns 0 if book or chapter is out of canonical bounds.
    """
    if book_id not in BOOK_CHAPTER_VERSES:
        return 0
    chapters = BOOK_CHAPTER_VERSES[book_id]
    if chapter < 1 or chapter > len(chapters):
        return 0
    return chapters[chapter - 1]


def is_valid_canonical_coordinate(coord: int) -> bool:
    """Check if an integer coordinate BBCCCVVV represents a valid biblical verse."""
    if not isinstance(coord, int) or coord < 1_001_001 or coord > 66_999_999:
        return False
    b, ch, v = canonical_id_to_triple(coord)
    if b < 1 or b > TOTAL_CANONICAL_BOOKS:
        return False
    max_v = get_canonical_max_verse(b, ch)
    return 1 <= v <= max_v


def validate_canonical_coordinate(coord: int) -> Tuple[bool, Optional[str]]:
    """Validate a single canonical integer coordinate BBCCCVVV.

    Returns:
        (is_valid, error_message_or_none)
    """
    if not isinstance(coord, int):
        return False, f"Coordinate must be an integer, got {type(coord).__name__}: {coord!r}"
    if coord < 1_001_001 or coord > 66_999_999:
        return False, f"Coordinate {coord} is out of canon range [1001001, 66022021]"

    b, ch, v = canonical_id_to_triple(coord)
    if b < 1 or b > TOTAL_CANONICAL_BOOKS:
        return False, f"Book number {b} out of Protestant canon range [1, 66]"

    book_obj = BOOKS.get(b)
    book_name = book_obj.name if book_obj else f"Book_{b}"
    chapters = BOOK_CHAPTER_VERSES.get(b, ())
    if ch < 1 or ch > len(chapters):
        return False, f"Chapter {ch} is invalid for {book_name} (valid range: 1..{len(chapters)})"

    max_v = chapters[ch - 1]
    if v < 1 or v > max_v:
        return False, f"Verse {v} is invalid for {book_name} {ch} (valid range: 1..{max_v})"

    return True, None


def validate_canonical_span(
    start_id: int,
    end_id: int,
    allow_cross_book: bool = False,
) -> Tuple[bool, Optional[str]]:
    """Validate a canonical passage span [start_id, end_id].

    Asserts that both coordinates are valid and start_id <= end_id.
    If allow_cross_book is False, asserts start and end belong to the same book.
    """
    ok_start, err_start = validate_canonical_coordinate(start_id)
    if not ok_start:
        return False, f"Invalid span start coordinate: {err_start}"

    ok_end, err_end = validate_canonical_coordinate(end_id)
    if not ok_end:
        return False, f"Invalid span end coordinate: {err_end}"

    if start_id > end_id:
        return False, f"Inverted span coordinates: start {start_id} > end {end_id}"

    start_book, _, _ = canonical_id_to_triple(start_id)
    end_book, _, _ = canonical_id_to_triple(end_id)
    if not allow_cross_book and start_book != end_book:
        return False, f"Cross-book span not permitted: book {start_book} to book {end_book}"

    return True, None


def expand_canonical_span(start_id: int, end_id: int) -> List[int]:
    """Expand a canonical span [start_id, end_id] into all sequential verse coordinates.

    Correctly steps across chapter boundaries and book boundaries adhering to the
    authoritative canon versification.
    """
    ok, err = validate_canonical_span(start_id, end_id, allow_cross_book=True)
    if not ok:
        raise ValueError(f"Cannot expand invalid span [{start_id}, {end_id}]: {err}")

    coords: List[int] = []
    b_start, ch_start, v_start = canonical_id_to_triple(start_id)
    b_end, ch_end, v_end = canonical_id_to_triple(end_id)

    curr_b = b_start
    curr_ch = ch_start
    curr_v = v_start

    while True:
        curr_id = curr_b * 1_000_000 + curr_ch * 1_000 + curr_v
        coords.append(curr_id)

        if curr_b == b_end and curr_ch == ch_end and curr_v == v_end:
            break

        max_v = get_canonical_max_verse(curr_b, curr_ch)
        if curr_v < max_v:
            curr_v += 1
        else:
            # Advance to next chapter
            total_ch = len(BOOK_CHAPTER_VERSES.get(curr_b, ()))
            if curr_ch < total_ch:
                curr_ch += 1
                curr_v = 1
            else:
                # Advance to next book
                curr_b += 1
                curr_ch = 1
                curr_v = 1

    return coords


def format_canonical_coordinate(coord: int) -> str:
    """Format a canonical coordinate into a human-readable citation (e.g. 'Romans 8:28')."""
    b, ch, v = canonical_id_to_triple(coord)
    book_obj = BOOKS.get(b)
    b_name = book_obj.name if book_obj else f"Book_{b}"
    return f"{b_name} {ch}:{v}"


# ==============================================================================
# 2. Audit Severity, Findings & Report Data Transfer Objects
# ==============================================================================


class CriticSeverity(str, Enum):
    """Severity levels for exegetical and structural audit findings."""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class AuditFinding:
    """Represents an atomic diagnostic finding from an audit rule."""

    rule_id: str
    message: str
    severity: CriticSeverity
    coordinate: Optional[int] = None
    human_ref: Optional[str] = None
    context: Optional[str] = None
    suggested_fix: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert finding to dictionary representation."""
        return {
            "rule_id": self.rule_id,
            "message": self.message,
            "severity": self.severity.value,
            "coordinate": self.coordinate,
            "human_ref": self.human_ref,
            "context": self.context,
            "suggested_fix": self.suggested_fix,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AuditFinding":
        """Reconstruct AuditFinding from dictionary representation."""
        return cls(
            rule_id=d["rule_id"],
            message=d["message"],
            severity=CriticSeverity(d["severity"]),
            coordinate=d.get("coordinate"),
            human_ref=d.get("human_ref"),
            context=d.get("context"),
            suggested_fix=d.get("suggested_fix"),
        )


@dataclass
class AuditReport:
    """Consolidated report aggregating findings across an audited entity or database."""

    findings: List[AuditFinding] = field(default_factory=list)
    total_inspected: int = 0
    duration_sec: float = 0.0

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AuditReport":
        """Reconstruct AuditReport from dictionary representation."""
        findings = [AuditFinding.from_dict(f) for f in d.get("findings", [])]
        return cls(
            findings=findings,
            total_inspected=d.get("total_inspected", 0),
            duration_sec=d.get("duration_sec", 0.0),
        )

    @property
    def errors(self) -> List[AuditFinding]:
        """Return all findings of ERROR or CRITICAL severity."""
        return [f for f in self.findings if f.severity in (CriticSeverity.ERROR, CriticSeverity.CRITICAL)]

    @property
    def warnings(self) -> List[AuditFinding]:
        """Return all findings of WARNING severity."""
        return [f for f in self.findings if f.severity == CriticSeverity.WARNING]

    @property
    def info(self) -> List[AuditFinding]:
        """Return all findings of INFO severity."""
        return [f for f in self.findings if f.severity == CriticSeverity.INFO]

    @property
    def is_clean(self) -> bool:
        """True if zero ERROR or CRITICAL findings exist."""
        return len(self.errors) == 0

    def add_finding(
        self,
        rule_id: str,
        message: str,
        severity: CriticSeverity,
        coordinate: Optional[int] = None,
        human_ref: Optional[str] = None,
        context: Optional[str] = None,
        suggested_fix: Optional[str] = None,
    ) -> None:
        """Append a new finding to the report."""
        self.findings.append(
            AuditFinding(
                rule_id=rule_id,
                message=message,
                severity=severity,
                coordinate=coordinate,
                human_ref=human_ref,
                context=context,
                suggested_fix=suggested_fix,
            )
        )

    def merge(self, other: "AuditReport") -> None:
        """Merge another AuditReport into this one."""
        self.findings.extend(other.findings)
        self.total_inspected += other.total_inspected
        self.duration_sec += other.duration_sec

    def summary(self) -> str:
        """Produce a concise human-readable text summary of the audit results."""
        status = "PASSED" if self.is_clean else "FAILED"
        lines = [
            f"Audit Status: {status} (Inspected: {self.total_inspected}, "
            f"Errors: {len(self.errors)}, Warnings: {len(self.warnings)}, "
            f"Duration: {self.duration_sec:.3f}s)"
        ]
        for f in self.findings:
            loc = f" [{f.human_ref}]" if f.human_ref else (f" [{f.coordinate}]" if f.coordinate else "")
            lines.append(f"  - [{f.severity.value}]{loc} {f.rule_id}: {f.message}")
            if f.suggested_fix:
                lines.append(f"    * Suggestion: {f.suggested_fix}")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary."""
        return {
            "is_clean": self.is_clean,
            "total_inspected": self.total_inspected,
            "errors_count": len(self.errors),
            "warnings_count": len(self.warnings),
            "duration_sec": round(self.duration_sec, 4),
            "findings": [f.to_dict() for f in self.findings],
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize report to JSON formatted string."""
        return json.dumps(self.to_dict(), indent=indent)


# ==============================================================================
# 3. Canonical Character Entity Catalog & Deduplication Engine
# ==============================================================================


@dataclass(frozen=True)
class CanonicalCharacter:
    """Authoritative representation of a biblical character entity."""

    canonical_name: str
    testament: str  # "OT", "NT", or "BOTH"
    aliases: Tuple[str, ...]
    theological_role: str
    primary_books: Tuple[str, ...]


# Canonical Biblical Characters Catalog
_CHARACTER_DATA: List[CanonicalCharacter] = [
    # Godhead
    CanonicalCharacter(
        canonical_name="God (Yahweh)",
        testament="BOTH",
        aliases=("Yahweh", "the LORD", "Lord GOD", "God", "El Shaddai", "the Almighty", "the Father", "God the Father", "Most High", "Creator", "Lord of Hosts"),
        theological_role="Sovereign Creator, Covenant Lord, and Triune God of redemptive history.",
        primary_books=("Genesis", "Exodus", "Psalms", "Isaiah", "John", "Romans"),
    ),
    CanonicalCharacter(
        canonical_name="Jesus Christ",
        testament="BOTH",
        aliases=("Jesus", "Christ", "Lord Jesus", "Jesus of Nazareth", "Son of God", "Messiah", "The Word", "Son of Man", "Yeshua", "Lamb of God", "Risen Lord"),
        theological_role="Incarnate Son of God, Prophet, Priest, King, and sole Mediator of the New Covenant.",
        primary_books=("Matthew", "Mark", "Luke", "John", "Romans", "Hebrews", "Revelation"),
    ),
    CanonicalCharacter(
        canonical_name="Holy Spirit",
        testament="BOTH",
        aliases=("the Spirit", "Spirit of God", "the Comforter", "the Paraclete", "Spirit of the LORD", "Holy Ghost", "Spirit of Truth"),
        theological_role="Third Person of the Trinity who inspires Scripture, regenerates believers, and indwells the Church.",
        primary_books=("Genesis", "Ezekiel", "John", "Acts", "Romans", "Galatians"),
    ),
    # Patriarchs & Early Redemptive History
    CanonicalCharacter(
        canonical_name="Adam",
        testament="BOTH",
        aliases=("the first man", "First Adam"),
        theological_role="Federal head of original creation and fallen humanity, type of Christ (Rom 5).",
        primary_books=("Genesis", "Romans", "1 Corinthians"),
    ),
    CanonicalCharacter(
        canonical_name="Eve",
        testament="BOTH",
        aliases=("mother of all living",),
        theological_role="First woman, mother of the human race, recipient of the Protoevangelium (Gen 3:15).",
        primary_books=("Genesis", "2 Corinthians", "1 Timothy"),
    ),
    CanonicalCharacter(
        canonical_name="Noah",
        testament="BOTH",
        aliases=(),
        theological_role="Righteous covenant mediator through judgment waters, foreshadowing salvation in Christ.",
        primary_books=("Genesis", "Hebrews", "1 Peter", "2 Peter"),
    ),
    CanonicalCharacter(
        canonical_name="Abraham",
        testament="BOTH",
        aliases=("Abram", "Father Abraham"),
        theological_role="Father of the faithful, recipient of the unconditional covenant promise of seed, land, and blessing.",
        primary_books=("Genesis", "Romans", "Galatians", "Hebrews"),
    ),
    CanonicalCharacter(
        canonical_name="Sarah",
        testament="BOTH",
        aliases=("Sarai",),
        theological_role="Matriarch of the promise, mother of Isaac.",
        primary_books=("Genesis", "Romans", "Galatians", "Hebrews", "1 Peter"),
    ),
    CanonicalCharacter(
        canonical_name="Isaac",
        testament="BOTH",
        aliases=(),
        theological_role="Miraculous son of the promise, offered on Mount Moriah as a type of the beloved Son.",
        primary_books=("Genesis", "Galatians", "Hebrews"),
    ),
    CanonicalCharacter(
        canonical_name="Jacob (Israel)",
        testament="BOTH",
        aliases=("Jacob", "Israel"),
        theological_role="Patriarch father of the twelve tribes of Israel, recipient of sovereign electing grace.",
        primary_books=("Genesis", "Exodus", "Psalms", "Romans"),
    ),
    CanonicalCharacter(
        canonical_name="Joseph (Son of Jacob)",
        testament="OT",
        aliases=("Joseph", "Zaphenath-paneah"),
        theological_role="Patriarch preserved through suffering and exalted to save God's people, prominent Christological type.",
        primary_books=("Genesis", "Psalms", "Acts"),
    ),
    # Exodus & The Law
    CanonicalCharacter(
        canonical_name="Moses",
        testament="BOTH",
        aliases=("prophet Moses", "servant of the LORD"),
        theological_role="Mediator of the Old Covenant, lawgiver, and prophetic type of the greater Prophet to come.",
        primary_books=("Exodus", "Leviticus", "Numbers", "Deuteronomy", "John", "Hebrews"),
    ),
    CanonicalCharacter(
        canonical_name="Aaron",
        testament="BOTH",
        aliases=("Aaron the priest", "high priest Aaron"),
        theological_role="First Levitical High Priest, whose priesthood is fulfilled and surpassed by Christ.",
        primary_books=("Exodus", "Leviticus", "Numbers", "Hebrews"),
    ),
    CanonicalCharacter(
        canonical_name="Joshua",
        testament="BOTH",
        aliases=("Hoshea", "Joshua son of Nun"),
        theological_role="Leader of the Conquest who brought Israel into the Promised Land, foreshadowing true rest.",
        primary_books=("Exodus", "Numbers", "Joshua", "Hebrews"),
    ),
    # United Monarchy & Kings
    CanonicalCharacter(
        canonical_name="Samuel",
        testament="BOTH",
        aliases=("prophet Samuel",),
        theological_role="Last judge and premier transitional prophet who anointed the Davidic monarchy.",
        primary_books=("1 Samuel", "Psalms", "Acts", "Hebrews"),
    ),
    CanonicalCharacter(
        canonical_name="Saul (King of Israel)",
        testament="OT",
        aliases=("King Saul", "Saul son of Kish"),
        theological_role="First king of Israel whose disobedience and tragic fall highlight the necessity of a faithful king.",
        primary_books=("1 Samuel", "1 Chronicles"),
    ),
    CanonicalCharacter(
        canonical_name="David",
        testament="BOTH",
        aliases=("King David", "sweet psalmist of Israel", "son of Jesse"),
        theological_role="Man after God's own heart, recipient of the Davidic Covenant, primary prophetic type of King Jesus.",
        primary_books=("1 Samuel", "2 Samuel", "1 Chronicles", "Psalms", "Matthew", "Acts", "Romans"),
    ),
    CanonicalCharacter(
        canonical_name="Solomon",
        testament="BOTH",
        aliases=("King Solomon", "Jedidiah"),
        theological_role="Son of David, temple builder, renowned for wisdom and the tragic idolatry of divided heart.",
        primary_books=("1 Kings", "2 Chronicles", "Proverbs", "Ecclesiastes", "Song of Solomon"),
    ),
    CanonicalCharacter(
        canonical_name="Elijah",
        testament="BOTH",
        aliases=("Elijah the Tishbite", "prophet Elijah"),
        theological_role="Prophet of fire defending Yahweh's covenant against Baal, type of John the Baptist.",
        primary_books=("1 Kings", "2 Kings", "Malachi", "Matthew", "Luke"),
    ),
    CanonicalCharacter(
        canonical_name="Elisha",
        testament="OT",
        aliases=("prophet Elisha", "son of Shaphat"),
        theological_role="Successor to Elijah, minister of double-portion miracles and grace in Israel.",
        primary_books=("1 Kings", "2 Kings"),
    ),
    CanonicalCharacter(
        canonical_name="Isaiah",
        testament="BOTH",
        aliases=("prophet Isaiah", "son of Amoz"),
        theological_role="Evangelical prophet proclaiming the Holy One of Israel, the Virgin Birth, and the Suffering Servant.",
        primary_books=("2 Kings", "Isaiah", "Matthew", "Romans"),
    ),
    CanonicalCharacter(
        canonical_name="Jeremiah",
        testament="BOTH",
        aliases=("weeping prophet",),
        theological_role="Prophet to the nations announcing the Babylonian exile and the promise of the New Covenant.",
        primary_books=("Jeremiah", "Lamentations", "Hebrews"),
    ),
    CanonicalCharacter(
        canonical_name="Daniel",
        testament="BOTH",
        aliases=("Belteshazzar",),
        theological_role="Statesman and prophet in Babylon revealing the universal, everlasting Kingdom of the Son of Man.",
        primary_books=("Daniel", "Ezekiel", "Matthew"),
    ),
    # Gospels & New Testament
    CanonicalCharacter(
        canonical_name="John the Baptist",
        testament="NT",
        aliases=("John the Baptizer", "the Baptist"),
        theological_role="Forerunner of the Messiah, the voice crying in the wilderness, last and greatest of OT prophets.",
        primary_books=("Matthew", "Mark", "Luke", "John"),
    ),
    CanonicalCharacter(
        canonical_name="Mary (Mother of Jesus)",
        testament="NT",
        aliases=("Mary", "virgin Mary", "mother of Jesus"),
        theological_role="Humble handmaiden chosen to bear the incarnate Son of God according to prophecy.",
        primary_books=("Matthew", "Luke", "John", "Acts"),
    ),
    CanonicalCharacter(
        canonical_name="Joseph (Husband of Mary)",
        testament="NT",
        aliases=("Joseph", "husband of Mary"),
        theological_role="Righteous Davidic descendant who adopted and protected Jesus during childhood.",
        primary_books=("Matthew", "Luke"),
    ),
    CanonicalCharacter(
        canonical_name="Peter (Apostle)",
        testament="NT",
        aliases=("Simon", "Simon Peter", "Cephas", "Simeon"),
        theological_role="Lead apostle of the Twelve, preacher of Pentecost, pillar of the early church.",
        primary_books=("Matthew", "Mark", "Luke", "John", "Acts", "Galatians", "1 Peter", "2 Peter"),
    ),
    CanonicalCharacter(
        canonical_name="Paul (Apostle)",
        testament="NT",
        aliases=("Saul", "Saul of Tarsus", "Apostle Paul", "Paul"),
        theological_role="Apostle to the Gentiles, converted persecutor, inspired author of 13 canonical epistles.",
        primary_books=("Acts", "Romans", "1 Corinthians", "2 Corinthians", "Galatians", "Ephesians", "Philippians", "Colossians", "1 Thessalonians", "2 Thessalonians", "1 Timothy", "2 Timothy", "Titus", "Philemon", "2 Peter"),
    ),
    CanonicalCharacter(
        canonical_name="John (Apostle)",
        testament="NT",
        aliases=("John", "Beloved Disciple", "John the Apostle", "son of Zebedee"),
        theological_role="Apostle of love, author of the Fourth Gospel, three Johannine epistles, and Revelation.",
        primary_books=("Matthew", "Mark", "Luke", "John", "Acts", "1 John", "2 John", "3 John", "Revelation"),
    ),
    CanonicalCharacter(
        canonical_name="James (Brother of Jesus)",
        testament="NT",
        aliases=("James the Just", "brother of the Lord", "James"),
        theological_role="Leader of the Jerusalem church, presiding over the Jerusalem Council, author of the Epistle of James.",
        primary_books=("Matthew", "Acts", "1 Corinthians", "Galatians", "James"),
    ),
    CanonicalCharacter(
        canonical_name="Mary Magdalene",
        testament="NT",
        aliases=("Magdalene",),
        theological_role="Devoted disciple delivered from seven demons, first witness to the Risen Lord.",
        primary_books=("Matthew", "Mark", "Luke", "John"),
    ),
]


class CharacterEntityDeduplicator:
    """Resolves entity references, disambiguates shared biblical names, and deduplicates character profiles."""

    def __init__(self, catalog: Optional[Sequence[CanonicalCharacter]] = None) -> None:
        self.catalog: List[CanonicalCharacter] = list(catalog or _CHARACTER_DATA)
        self._alias_map: Dict[str, CanonicalCharacter] = {}
        self._name_map: Dict[str, CanonicalCharacter] = {}

        # Build fast lookup indexes
        for char in self.catalog:
            norm_canonical = self.normalize_name(char.canonical_name)
            self._name_map[norm_canonical] = char
            for alias in char.aliases:
                norm_alias = self.normalize_name(alias)
                self._alias_map[norm_alias] = char

    @staticmethod
    def normalize_name(raw_name: str) -> str:
        """Strip honorifics, titles, punctuation, and normalize whitespace/case."""
        if not raw_name:
            return ""
        # Remove common biblical honorific prefixes
        cleaned = re.sub(
            r"^(?:king|prophet|apostle|saint|st\.|patriarch|brother|priest|father)\s+",
            "",
            raw_name.strip(),
            flags=re.IGNORECASE,
        )
        # Remove parentheses and punctuation
        cleaned = re.sub(r"[^\w\s]", "", cleaned)
        return re.sub(r"\s+", " ", cleaned).strip().lower()

    def resolve_character(
        self,
        raw_name: str,
        coordinate: Optional[int] = None,
    ) -> Optional[CanonicalCharacter]:
        """Resolve a raw name string into a CanonicalCharacter entity with context-aware disambiguation."""
        if not raw_name or not raw_name.strip():
            return None

        clean = raw_name.strip()
        norm = self.normalize_name(clean)

        # Context-based disambiguation for famous overloaded names
        if coordinate is not None:
            book_id, _, _ = canonical_id_to_triple(coordinate)
            is_ot = book_id <= 39
            is_nt = book_id >= 40

            # Disambiguate "Saul"
            if norm in ("saul", "king saul", "saul of tarsus"):
                if is_ot:
                    return self._name_map.get("saul king of israel")
                if is_nt:
                    return self._name_map.get("paul apostle")

            # Disambiguate "Joseph"
            if norm == "joseph":
                if is_ot:
                    return self._name_map.get("joseph son of jacob")
                if is_nt:
                    return self._name_map.get("joseph husband of mary")

            # Disambiguate "John"
            if norm == "john":
                if is_nt:
                    # In Gospels early chapters (e.g. Matt 3, John 1), could be John the Baptist
                    if "baptist" in clean.lower():
                        return self._name_map.get("john the baptist")
                    # Default in NT epistles or general: John the Apostle
                    return self._name_map.get("john apostle")

            # Disambiguate "Mary"
            if norm == "mary":
                if "magdalene" in clean.lower():
                    return self._name_map.get("mary magdalene")
                return self._name_map.get("mary mother of jesus")

            # Disambiguate "James"
            if norm == "james":
                if book_id == 59 or book_id == 44:  # James or Acts
                    return self._name_map.get("james brother of jesus")

        # Direct canonical name match
        if norm in self._name_map:
            return self._name_map[norm]

        # Alias lookup
        if norm in self._alias_map:
            return self._alias_map[norm]

        # Substring / partial match on canonical names
        for k, v in self._name_map.items():
            if norm == k or norm in k or k in norm:
                return v

        # Substring match on aliases
        for k, v in self._alias_map.items():
            if norm == k or norm in k:
                return v

        return None

    def deduplicate_names(
        self,
        names: Sequence[str],
        coordinates: Optional[Sequence[Optional[int]]] = None,
    ) -> List[str]:
        """Deduplicate a sequence of entity names into their canonical names."""
        seen: Set[str] = set()
        deduped: List[str] = []

        coords_list = list(coordinates) if coordinates else [None] * len(names)
        for i, name in enumerate(names):
            coord = coords_list[i] if i < len(coords_list) else None
            resolved = self.resolve_character(name, coordinate=coord)
            canonical = resolved.canonical_name if resolved else name.strip()
            if canonical and canonical not in seen:
                seen.add(canonical)
                deduped.append(canonical)

        return deduped

    def audit_propositions_characters(
        self,
        propositions: Sequence[Union[SemanticPropositionRecord, SemanticPropositionData, Dict[str, Any]]],
    ) -> AuditReport:
        """Audit agent and patient fields across semantic propositions for entity consistency."""
        report = AuditReport(total_inspected=len(propositions))
        for prop in propositions:
            # Extract fields flexibly from dataclass or dict
            if isinstance(prop, dict):
                agent = str(prop.get("agent") or "").strip()
                patient = prop.get("patient")
                coord = prop.get("canonical_verse_id")
                human_ref = prop.get("human_ref")
            elif hasattr(prop, "canonical_verse_id"):
                agent = getattr(prop, "agent", "").strip()
                patient = getattr(prop, "patient", None)
                coord = getattr(prop, "canonical_verse_id", None)
                human_ref = getattr(prop, "human_ref", None)
            else:
                agent = getattr(prop, "agent", "").strip()
                patient = getattr(prop, "patient", None)
                coord = None
                human_ref = getattr(prop, "verse_ref", None)

            if not agent:
                report.add_finding(
                    rule_id="PROP_AGENT_EMPTY",
                    message="Semantic proposition agent is empty",
                    severity=CriticSeverity.ERROR,
                    coordinate=coord,
                    human_ref=human_ref,
                    suggested_fix="Assign specific agent (e.g. 'God', 'Jesus', 'Paul', 'Israel')",
                )

            # Check if agent is an unresolved alias
            if agent:
                resolved = self.resolve_character(agent, coordinate=coord)
                if resolved and resolved.canonical_name != agent and agent.lower() in ("saul", "simon", "abram", "sarai"):
                    report.add_finding(
                        rule_id="PROP_AGENT_ALIAS_DETECTED",
                        message=f"Proposition agent '{agent}' can be normalized to canonical entity '{resolved.canonical_name}'",
                        severity=CriticSeverity.INFO,
                        coordinate=coord,
                        human_ref=human_ref,
                        suggested_fix=f"Normalize agent to '{resolved.canonical_name}'",
                    )

            if patient:
                p_str = str(patient).strip()
                resolved_p = self.resolve_character(p_str, coordinate=coord)
                if resolved_p and resolved_p.canonical_name != p_str and p_str.lower() in ("saul", "simon", "abram", "sarai"):
                    report.add_finding(
                        rule_id="PROP_PATIENT_ALIAS_DETECTED",
                        message=f"Proposition patient '{p_str}' can be normalized to canonical entity '{resolved_p.canonical_name}'",
                        severity=CriticSeverity.INFO,
                        coordinate=coord,
                        human_ref=human_ref,
                        suggested_fix=f"Normalize patient to '{resolved_p.canonical_name}'",
                    )

        return report


# ==============================================================================
# 4. Schema & Exegetical Critic Engine
# ==============================================================================

# Common simplistic moralistic triggers flagged by TGC anti-moralism audit
_MORALISTIC_PATTERNS = (
    re.compile(r"\bbe\s+(?:brave|courageous|strong)\s+like\s+\w+\b", re.IGNORECASE),
    re.compile(r"\bfollow\s+(?:the\s+example\s+of|david|moses|abraham|gideon)\b", re.IGNORECASE),
    re.compile(r"\btry\s+harder\s+to\b", re.IGNORECASE),
    re.compile(r"\bwe\s+must\s+(?:earn|achieve|attain)\s+god's?\s+favor\b", re.IGNORECASE),
    re.compile(r"\bdo\s+good\s+things\s+and\s+god\s+will\b", re.IGNORECASE),
)

_GOSPEL_GRACE_KEYWORDS = {
    "christ", "jesus", "grace", "faith", "cross", "atonement", "salvation",
    "redeem", "redemption", "mercy", "righteousness", "covenant", "sovereign",
    "justification", "gospel", "resurrection", "sacrifice",
}


class ExegeticalCritic:
    """Audits and critiques pericope exegesis, coordinate boundaries, schemas, and hermeneutics."""

    def __init__(self, character_deduplicator: Optional[CharacterEntityDeduplicator] = None) -> None:
        self.deduplicator = character_deduplicator or CharacterEntityDeduplicator()

    def audit_coordinate(self, coord: int, label: str = "coordinate") -> List[AuditFinding]:
        """Audit a single integer coordinate."""
        ok, err = validate_canonical_coordinate(coord)
        if not ok:
            return [
                AuditFinding(
                    rule_id="COORD_OUT_OF_BOUNDS",
                    message=f"Invalid {label}: {err}",
                    severity=CriticSeverity.ERROR,
                    coordinate=coord,
                    suggested_fix="Ensure coordinate format is BBCCCVVV within valid Protestant canonical boundaries",
                )
            ]
        return []

    def audit_span(
        self,
        start_id: int,
        end_id: int,
        label: str = "span",
        allow_cross_book: bool = False,
    ) -> List[AuditFinding]:
        """Audit start and end coordinates of a passage span."""
        ok, err = validate_canonical_span(start_id, end_id, allow_cross_book=allow_cross_book)
        if not ok:
            return [
                AuditFinding(
                    rule_id="SPAN_INVALID",
                    message=f"Invalid {label} [{start_id}..{end_id}]: {err}",
                    severity=CriticSeverity.ERROR,
                    coordinate=start_id,
                    suggested_fix="Verify start <= end and valid chapter/verse boundaries",
                )
            ]
        return []

    def audit_pericope(
        self,
        pericope: Union[PericopeRecord, Dict[str, Any]],
        strict: bool = True,
    ) -> AuditReport:
        """Audit pericope record structure, coordinate boundaries, and exegesis."""
        report = AuditReport(total_inspected=1)

        # Extract fields
        if isinstance(pericope, dict):
            start_id = int(pericope.get("start_canonical_id", 0))
            end_id = int(pericope.get("end_canonical_id", 0))
            title = str(pericope.get("title") or "").strip()
            genre = str(pericope.get("genre") or "").strip()
            cp = str(pericope.get("central_proposition") or "").strip()
            rs = str(pericope.get("redemptive_summary") or "").strip()
            cf = str(pericope.get("christological_fulfillment") or "").strip()
            human_ref = pericope.get("human_ref")
        else:
            start_id = pericope.start_canonical_id
            end_id = pericope.end_canonical_id
            title = pericope.title.strip() if pericope.title else ""
            genre = pericope.genre.strip() if pericope.genre else ""
            cp = pericope.central_proposition.strip() if pericope.central_proposition else ""
            rs = pericope.redemptive_summary.strip() if pericope.redemptive_summary else ""
            cf = ""
            human_ref = pericope.human_ref

        # 1. Coordinate Validation
        span_findings = self.audit_span(start_id, end_id, label="pericope")
        report.findings.extend(span_findings)

        # 2. Title Validation
        if not title:
            report.add_finding(
                rule_id="PERICOPE_TITLE_EMPTY",
                message="Pericope title is empty",
                severity=CriticSeverity.ERROR,
                coordinate=start_id,
                human_ref=human_ref,
                suggested_fix="Provide a dignified, descriptive pericope title",
            )
        elif title.lower() in ("untitled", "passage", "section", "text"):
            report.add_finding(
                rule_id="PERICOPE_TITLE_PLACEHOLDER",
                message=f"Pericope title '{title}' appears to be a generic placeholder",
                severity=CriticSeverity.WARNING,
                coordinate=start_id,
                human_ref=human_ref,
                suggested_fix="Provide an informative title reflecting the authorial subject",
            )

        # 3. Genre Validation
        if genre and genre not in LITERARY_GENRES:
            report.add_finding(
                rule_id="PERICOPE_GENRE_NONSTANDARD",
                message=f"Genre '{genre}' is not in standard LITERARY_GENRES",
                severity=CriticSeverity.WARNING,
                coordinate=start_id,
                human_ref=human_ref,
                suggested_fix=f"Choose from standard genres: {', '.join(LITERARY_GENRES)}",
            )

        # 4. Central Proposition & Redemptive Summary Validation
        if not cp:
            sev = CriticSeverity.ERROR if strict else CriticSeverity.WARNING
            report.add_finding(
                rule_id="PERICOPE_CP_EMPTY",
                message="Pericope central proposition is empty",
                severity=sev,
                coordinate=start_id,
                human_ref=human_ref,
                suggested_fix="Formulate a concise, author-intended theological thesis (compile via ./bible build-semantic)",
            )
        elif len(cp) < 10:
            report.add_finding(
                rule_id="PERICOPE_CP_TRIVIAL",
                message="Pericope central proposition is too brief (< 10 chars)",
                severity=CriticSeverity.WARNING,
                coordinate=start_id,
                human_ref=human_ref,
                suggested_fix="Expand central proposition with complete exegetical thought",
            )

        if not rs:
            sev = CriticSeverity.ERROR if strict else CriticSeverity.WARNING
            report.add_finding(
                rule_id="PERICOPE_RS_EMPTY",
                message="Pericope redemptive summary is empty",
                severity=sev,
                coordinate=start_id,
                human_ref=human_ref,
                suggested_fix="Articulate how this passage situates within God's redemptive storyline",
            )

        # 5. Hermeneutical Anti-Moralism Audit
        combined_text = f"{title} {cp} {rs} {cf}".lower()
        has_grace_context = any(kw in combined_text for kw in _GOSPEL_GRACE_KEYWORDS)

        for pat in _MORALISTIC_PATTERNS:
            m = pat.search(cp) or pat.search(rs)
            if m and not has_grace_context:
                report.add_finding(
                    rule_id="HERMENEUTIC_MORALISM_DETECTED",
                    message=f"Moralistic moralizing detected ('{m.group(0)}') without gospel/grace grounding",
                    severity=CriticSeverity.WARNING,
                    coordinate=start_id,
                    human_ref=human_ref,
                    context=m.group(0),
                    suggested_fix="Anchor moral imperatives in God's prior indicative grace and Christological redemption (TGC Foundation Documents)",
                )

        return report

    def audit_discourse_relations(
        self,
        relations: Sequence[Union[DiscourseRelationRecord, DiscourseRelationData, Dict[str, Any]]],
        pericope_start: Optional[int] = None,
        pericope_end: Optional[int] = None,
    ) -> AuditReport:
        """Audit discourse relations for valid connectives and canonical boundaries."""
        report = AuditReport(total_inspected=len(relations))
        for rel in relations:
            # Extract attributes
            if isinstance(rel, dict):
                src_id = rel.get("source_canonical_id")
                tgt_id = rel.get("target_canonical_id")
                rtype = str(rel.get("relation_type") or "").strip().lower()
                marker = rel.get("marker_text")
                h_ref = rel.get("source_human_ref")
            elif isinstance(rel, DiscourseRelationRecord):
                src_id = rel.source_canonical_id
                tgt_id = rel.target_canonical_id
                rtype = rel.relation_type.strip().lower()
                marker = rel.marker_text
                h_ref = rel.source_human_ref
            else:
                # DiscourseRelationData
                rtype = rel.relation_type.strip().lower()
                marker = rel.marker_text
                h_ref = rel.source_verse
                src_id = None
                tgt_id = None

            # Check relation type
            if rtype not in DISCOURSE_RELATION_TYPES:
                report.add_finding(
                    rule_id="DISCOURSE_INVALID_TYPE",
                    message=f"Invalid discourse relation type '{rtype}'",
                    severity=CriticSeverity.ERROR,
                    coordinate=src_id,
                    human_ref=h_ref,
                    suggested_fix=f"Must be one of: {', '.join(DISCOURSE_RELATION_TYPES)}",
                )

            # Check coordinates if present
            if src_id is not None:
                report.findings.extend(self.audit_coordinate(src_id, label="discourse source"))
                if pericope_start and pericope_end and (src_id < pericope_start or src_id > pericope_end):
                    report.add_finding(
                        rule_id="DISCOURSE_SOURCE_OUTSIDE_PERICOPE",
                        message=f"Discourse source {src_id} falls outside pericope bounds [{pericope_start}..{pericope_end}]",
                        severity=CriticSeverity.WARNING,
                        coordinate=src_id,
                        human_ref=h_ref,
                    )

            if tgt_id is not None:
                report.findings.extend(self.audit_coordinate(tgt_id, label="discourse target"))

            if not marker:
                report.add_finding(
                    rule_id="DISCOURSE_MARKER_MISSING",
                    message="Discourse relation lacks an identified connective marker text",
                    severity=CriticSeverity.INFO,
                    coordinate=src_id,
                    human_ref=h_ref,
                )

        return report

    def audit_verse_theology(
        self,
        records: Sequence[Union[VerseTheologyRecord, VerseTheologyData, Dict[str, Any]]],
        pericope_start: Optional[int] = None,
        pericope_end: Optional[int] = None,
    ) -> AuditReport:
        """Audit verse theology classifications for canonical taxonomy compliance."""
        report = AuditReport(total_inspected=len(records))
        valid_epochs = {e.value for e in RedemptiveEpoch}
        valid_loci = {l.value for l in TheologicalLocus}
        valid_ribbons = {r.value for r in ThematicRibbon}

        def _is_valid_enum(val: str, valid_set: Set[str]) -> bool:
            if not val:
                return False
            clean = re.sub(r"[^\w\s]", " ", val.strip().lower())
            clean = re.sub(r"[\s\-]+", "_", clean).strip("_")
            if clean in valid_set:
                return True
            for v in valid_set:
                if clean == v.replace("_", "") or clean == v:
                    return True
            return False

        for vt in records:
            if isinstance(vt, dict):
                start_id = vt.get("start_canonical_id")
                end_id = vt.get("end_canonical_id")
                epoch = str(vt.get("storyline_epoch") or "").strip()
                locus = str(vt.get("theological_locus") or "").strip()
                ribbon = vt.get("thematic_ribbon")
                conf = float(vt.get("confidence") or 1.0)
                h_ref = vt.get("human_ref")
            elif isinstance(vt, VerseTheologyRecord):
                start_id = vt.start_canonical_id
                end_id = vt.end_canonical_id
                epoch = vt.storyline_epoch.strip()
                locus = vt.theological_locus.strip()
                ribbon = vt.thematic_ribbon
                conf = vt.confidence
                h_ref = vt.human_ref
            else:
                # VerseTheologyData
                start_id = None
                end_id = None
                epoch = vt.storyline_epoch.strip()
                locus = vt.theological_locus.strip()
                ribbon = vt.thematic_ribbon
                conf = vt.confidence
                h_ref = vt.verse_ref

            if start_id is not None and end_id is not None:
                report.findings.extend(self.audit_span(start_id, end_id, label="verse_theology"))
                if pericope_start and pericope_end and (start_id < pericope_start or end_id > pericope_end):
                    report.add_finding(
                        rule_id="THEOLOGY_OUTSIDE_PERICOPE",
                        message=f"Theology span [{start_id}..{end_id}] exceeds pericope bounds [{pericope_start}..{pericope_end}]",
                        severity=CriticSeverity.WARNING,
                        coordinate=start_id,
                        human_ref=h_ref,
                    )

            if not _is_valid_enum(epoch, valid_epochs):
                report.add_finding(
                    rule_id="THEOLOGY_INVALID_EPOCH",
                    message=f"Invalid redemptive storyline epoch: '{epoch}'",
                    severity=CriticSeverity.ERROR,
                    coordinate=start_id,
                    human_ref=h_ref,
                    suggested_fix=f"Choose from RedemptiveEpoch: {', '.join(sorted(valid_epochs))}",
                )

            if not _is_valid_enum(locus, valid_loci):
                report.add_finding(
                    rule_id="THEOLOGY_INVALID_LOCUS",
                    message=f"Invalid systematic theological locus: '{locus}'",
                    severity=CriticSeverity.ERROR,
                    coordinate=start_id,
                    human_ref=h_ref,
                    suggested_fix=f"Choose from TheologicalLocus: {', '.join(sorted(valid_loci))}",
                )

            if ribbon and not _is_valid_enum(str(ribbon), valid_ribbons):
                report.add_finding(
                    rule_id="THEOLOGY_INVALID_RIBBON",
                    message=f"Invalid thematic ribbon: '{ribbon}'",
                    severity=CriticSeverity.WARNING,
                    coordinate=start_id,
                    human_ref=h_ref,
                    suggested_fix=f"Choose from ThematicRibbon: {', '.join(sorted(valid_ribbons))}",
                )

            if conf < 0.0 or conf > 1.0:
                report.add_finding(
                    rule_id="THEOLOGY_INVALID_CONFIDENCE",
                    message=f"Confidence score {conf} is out of bounds [0.0, 1.0]",
                    severity=CriticSeverity.ERROR,
                    coordinate=start_id,
                    human_ref=h_ref,
                )

        return report

    def audit_typological_arcs(
        self,
        records: Sequence[Union[TypologicalArcRecord, TypologicalArcData, Dict[str, Any]]],
    ) -> AuditReport:
        """Audit typological arcs asserting OT shadows connect to NT fulfillments."""
        report = AuditReport(total_inspected=len(records))

        for ta in records:
            if isinstance(ta, dict):
                t_start = ta.get("type_start_id")
                t_end = ta.get("type_end_id")
                at_start = ta.get("antitype_start_id")
                at_end = ta.get("antitype_end_id")
                corr = str(ta.get("theological_correspondence") or "").strip()
                warrant = str(ta.get("warrant") or "").strip()
                t_ref = ta.get("type_human_ref")
            elif isinstance(ta, TypologicalArcRecord):
                t_start = ta.type_start_id
                t_end = ta.type_end_id
                at_start = ta.antitype_start_id
                at_end = ta.antitype_end_id
                corr = ta.theological_correspondence.strip()
                warrant = (ta.warrant or "").strip()
                t_ref = ta.type_human_ref
            else:
                # TypologicalArcData
                corr = ta.theological_correspondence.strip()
                warrant = (ta.warrant or "").strip()
                t_ref = ta.type_ref
                t_start = None
                t_end = None
                at_start = None
                at_end = None

            # Verify Type in OT (book 1..39) and Antitype in NT (book 40..66)
            if t_start is not None and t_end is not None:
                report.findings.extend(self.audit_span(t_start, t_end, label="typology OT type"))
                b_type, _, _ = canonical_id_to_triple(t_start)
                if b_type > 39:
                    report.add_finding(
                        rule_id="TYPOLOGY_TYPE_NOT_OT",
                        message=f"Typological type reference {t_ref} is in the New Testament (book {b_type}); types must originate in the Old Testament",
                        severity=CriticSeverity.ERROR,
                        coordinate=t_start,
                        human_ref=t_ref,
                        suggested_fix="Ensure type reference points to an Old Testament shadow, institution, person, or event",
                    )

            if at_start is not None and at_end is not None:
                report.findings.extend(self.audit_span(at_start, at_end, label="typology NT antitype"))
                b_antitype, _, _ = canonical_id_to_triple(at_start)
                if b_antitype < 40:
                    report.add_finding(
                        rule_id="TYPOLOGY_ANTITYPE_NOT_NT",
                        message=f"Typological antitype is in the Old Testament (book {b_antitype}); antitypes must culminate in the New Testament fulfillment in Christ",
                        severity=CriticSeverity.ERROR,
                        coordinate=at_start,
                        suggested_fix="Ensure antitype reference points to Christological fulfillment in the New Testament",
                    )

            # Check theological correspondence
            if not corr or len(corr) < 15:
                report.add_finding(
                    rule_id="TYPOLOGY_CORRESPONDENCE_TRIVIAL",
                    message="Theological correspondence explanation is absent or superficial (< 15 chars)",
                    severity=CriticSeverity.WARNING,
                    coordinate=t_start,
                    human_ref=t_ref,
                    suggested_fix="Articulate the covenantal, organic correspondence between shadow and fulfillment",
                )

        return report

    def audit_semantic_propositions(
        self,
        records: Sequence[Union[SemanticPropositionRecord, SemanticPropositionData, Dict[str, Any]]],
        pericope_start: Optional[int] = None,
        pericope_end: Optional[int] = None,
    ) -> AuditReport:
        """Audit semantic propositions (speech acts, agents, actions, and tone)."""
        report = AuditReport(total_inspected=len(records))
        # 1. Check character entities
        char_report = self.deduplicator.audit_propositions_characters(records)
        report.merge(char_report)

        # 2. Check proposition structure & speech acts
        for prop in records:
            if isinstance(prop, dict):
                cid = prop.get("canonical_verse_id")
                sa = str(prop.get("speech_act") or "").strip().lower()
                action = str(prop.get("action") or "").strip()
                h_ref = prop.get("human_ref")
            elif isinstance(prop, SemanticPropositionRecord):
                cid = prop.canonical_verse_id
                sa = prop.speech_act.strip().lower()
                action = prop.action.strip()
                h_ref = prop.human_ref
            else:
                cid = None
                sa = prop.speech_act.strip().lower()
                action = prop.action.strip()
                h_ref = prop.verse_ref

            if cid is not None:
                report.findings.extend(self.audit_coordinate(cid, label="proposition verse"))
                if pericope_start and pericope_end and (cid < pericope_start or cid > pericope_end):
                    report.add_finding(
                        rule_id="PROP_COORDINATE_OUTSIDE_PERICOPE",
                        message=f"Proposition verse {cid} is outside pericope range [{pericope_start}..{pericope_end}]",
                        severity=CriticSeverity.WARNING,
                        coordinate=cid,
                        human_ref=h_ref,
                    )

            if sa not in SPEECH_ACT_TYPES:
                report.add_finding(
                    rule_id="PROP_INVALID_SPEECH_ACT",
                    message=f"Invalid speech act '{sa}'",
                    severity=CriticSeverity.ERROR,
                    coordinate=cid,
                    human_ref=h_ref,
                    suggested_fix=f"Choose from: {', '.join(SPEECH_ACT_TYPES)}",
                )

            if not action:
                report.add_finding(
                    rule_id="PROP_ACTION_EMPTY",
                    message="Proposition action verb is empty",
                    severity=CriticSeverity.ERROR,
                    coordinate=cid,
                    human_ref=h_ref,
                )

        return report

    def audit_pericope_analysis_result(self, result: PericopeAnalysisResult) -> AuditReport:
        """Execute a complete exegetical critique across all 6 layers of a PericopeAnalysisResult."""
        t0 = time.time()
        report = AuditReport()

        # Parse reference to obtain start and end coordinates
        try:
            ref_obj = parse_reference(result.reference)
            p_start = ref_obj.canonical_start_id
            p_end = ref_obj.canonical_end_id
        except Exception:
            p_start = None
            p_end = None

        # Convert to DB records to validate resolution
        try:
            p_rec, disc_recs, theol_recs, typo_recs, prop_recs = result.to_db_records()
        except Exception as exc:
            report.add_finding(
                rule_id="CONVERSION_TO_DB_FAILED",
                message=f"Failed to convert PericopeAnalysisResult to DB records: {exc}",
                severity=CriticSeverity.CRITICAL,
                context=str(exc),
            )
            report.duration_sec = time.time() - t0
            return report

        # 1. Audit Pericope
        report.merge(self.audit_pericope(p_rec))

        # 2. Audit Discourse Relations
        report.merge(self.audit_discourse_relations(disc_recs, pericope_start=p_start, pericope_end=p_end))

        # 3. Audit Verse Theologies
        report.merge(self.audit_verse_theology(theol_recs, pericope_start=p_start, pericope_end=p_end))

        # 4. Audit Typological Arcs
        report.merge(self.audit_typological_arcs(typo_recs))

        # 5. Audit Semantic Propositions
        report.merge(self.audit_semantic_propositions(prop_recs, pericope_start=p_start, pericope_end=p_end))

        # 6. Christological Fulfillment Depth Check
        if not result.christological_fulfillment or len(result.christological_fulfillment.strip()) < 20:
            report.add_finding(
                rule_id="HERMENEUTIC_SUPERFICIAL_CHRISTOLOGY",
                message="Christological fulfillment is absent or too brief (< 20 chars)",
                severity=CriticSeverity.WARNING,
                coordinate=p_start,
                human_ref=result.reference,
                suggested_fix="Detail how this passage anticipates, prefigures, or flows from the person and work of Christ",
            )

        report.duration_sec = time.time() - t0
        return report


# ==============================================================================
# 5. 100% Whole-Bible Verse Coverage Auditor
# ==============================================================================


@dataclass(frozen=True)
class CoverageGap:
    """Represents an unmapped range of canonical verses."""

    start_canonical_id: int
    end_canonical_id: int
    start_human_ref: str
    end_human_ref: str
    verse_count: int
    book_name: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_canonical_id": self.start_canonical_id,
            "end_canonical_id": self.end_canonical_id,
            "start_human_ref": self.start_human_ref,
            "end_human_ref": self.end_human_ref,
            "verse_count": self.verse_count,
            "book_name": self.book_name,
        }


@dataclass(frozen=True)
class BookCoverageStats:
    """Coverage statistics for one canonical book."""

    book_id: int
    book_name: str
    testament: str
    total_chapters: int
    total_verses: int
    covered_verses: int
    coverage_pct: float
    pericope_count: int

    @property
    def is_complete(self) -> bool:
        """True if 100% of the book's verses are mapped."""
        return self.covered_verses >= self.total_verses

    def to_dict(self) -> Dict[str, Any]:
        return {
            "book_id": self.book_id,
            "book_name": self.book_name,
            "testament": self.testament,
            "total_chapters": self.total_chapters,
            "total_verses": self.total_verses,
            "covered_verses": self.covered_verses,
            "coverage_pct": round(self.coverage_pct, 2),
            "pericope_count": self.pericope_count,
            "is_complete": self.is_complete,
        }


@dataclass
class WholeBibleCoverageReport:
    """Comprehensive audit report measuring whole-Bible coverage."""

    total_verses: int = TOTAL_CANONICAL_VERSES
    covered_verses_count: int = 0
    coverage_pct: float = 0.0
    book_stats: Dict[int, BookCoverageStats] = field(default_factory=dict)
    gaps: List[CoverageGap] = field(default_factory=list)
    overlap_count: int = 0
    ot_coverage_pct: float = 0.0
    nt_coverage_pct: float = 0.0
    duration_sec: float = 0.0

    @property
    def is_complete(self) -> bool:
        """True if 100% whole-Bible coverage is attained across all 31,103 verses."""
        return self.covered_verses_count >= self.total_verses

    def summary_table(self) -> str:
        """Format an ASCII table summarizing canonical coverage."""
        lines = [
            "=" * 78,
            f" Whole-Bible Semantic Coverage Report — {self.coverage_pct:.2f}% Complete",
            f" Covered Verses: {self.covered_verses_count:,} / {self.total_verses:,} | Gaps: {len(self.gaps)} | Overlaps: {self.overlap_count}",
            f" Old Testament: {self.ot_coverage_pct:.2f}% | New Testament: {self.nt_coverage_pct:.2f}%",
            "=" * 78,
            f"{'Book':<20} {'Test':<5} {'Chapters':<9} {'Verses':<8} {'Covered':<8} {'Coverage %':<12} {'Pericopes':<10}",
            "-" * 78,
        ]
        for b_id in sorted(self.book_stats.keys()):
            st = self.book_stats[b_id]
            flag = "✓" if st.is_complete else " "
            lines.append(
                f"{flag} {st.book_name:<18} {st.testament:<5} {st.total_chapters:<9} "
                f"{st.total_verses:<8} {st.covered_verses:<8} {st.coverage_pct:>8.1f}%   {st.pericope_count:<10}"
            )
        lines.append("=" * 78)
        if self.gaps and len(self.gaps) <= 10:
            lines.append(" Identified Coverage Gaps:")
            for g in self.gaps:
                lines.append(f"   * {g.book_name}: {g.start_human_ref} to {g.end_human_ref} ({g.verse_count} verses)")
        elif self.gaps:
            lines.append(f" Total Gaps: {len(self.gaps)} (run with --json or inspect gaps for details)")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_complete": self.is_complete,
            "total_verses": self.total_verses,
            "covered_verses_count": self.covered_verses_count,
            "coverage_pct": round(self.coverage_pct, 2),
            "ot_coverage_pct": round(self.ot_coverage_pct, 2),
            "nt_coverage_pct": round(self.nt_coverage_pct, 2),
            "overlap_count": self.overlap_count,
            "gaps_count": len(self.gaps),
            "duration_sec": round(self.duration_sec, 4),
            "book_stats": {b: st.to_dict() for b, st in self.book_stats.items()},
            "gaps": [g.to_dict() for g in self.gaps[:100]],
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "WholeBibleCoverageReport":
        """Reconstruct WholeBibleCoverageReport from dictionary."""
        book_stats = {}
        for b_str, st_dict in d.get("book_stats", {}).items():
            b_id = int(b_str)
            book_stats[b_id] = BookCoverageStats(
                book_id=st_dict["book_id"],
                book_name=st_dict["book_name"],
                testament=st_dict["testament"],
                total_chapters=st_dict["total_chapters"],
                total_verses=st_dict["total_verses"],
                covered_verses=st_dict["covered_verses"],
                coverage_pct=st_dict["coverage_pct"],
                pericope_count=st_dict["pericope_count"],
            )
        gaps = [
            CoverageGap(
                book_id=g["book_id"],
                book_name=g["book_name"],
                start_canonical_id=g["start_canonical_id"],
                end_canonical_id=g["end_canonical_id"],
                start_human_ref=g["start_human_ref"],
                end_human_ref=g["end_human_ref"],
                verse_count=g["verse_count"],
            )
            for g in d.get("gaps", [])
        ]
        return cls(
            total_verses=d.get("total_verses", TOTAL_CANONICAL_VERSES),
            covered_verses_count=d.get("covered_verses_count", 0),
            coverage_pct=d.get("coverage_pct", 0.0),
            book_stats=book_stats,
            gaps=gaps,
            overlap_count=d.get("overlap_count", 0),
            ot_coverage_pct=d.get("ot_coverage_pct", 0.0),
            nt_coverage_pct=d.get("nt_coverage_pct", 0.0),
            duration_sec=d.get("duration_sec", 0.0),
        )

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class WholeBibleCoverageAuditor:
    """Audits Scripture collections, database tables, or pericopes for 100% whole-Bible coverage."""

    def __init__(self) -> None:
        # Precompute canonical verse sets per book and globally
        self._all_canonical_verses: Set[int] = set()
        self._book_verses: Dict[int, Set[int]] = {}
        for b_id, chapters in BOOK_CHAPTER_VERSES.items():
            b_set: Set[int] = set()
            for ch_idx, max_v in enumerate(chapters, start=1):
                for v in range(1, max_v + 1):
                    cid = b_id * 1_000_000 + ch_idx * 1_000 + v
                    b_set.add(cid)
            self._book_verses[b_id] = b_set
            self._all_canonical_verses.update(b_set)

    def audit_pericopes(self, pericopes: Sequence[PericopeRecord]) -> WholeBibleCoverageReport:
        """Audit whole-Bible coverage across a collection of pericope records."""
        t0 = time.time()
        covered_counts: Dict[int, int] = {}
        pericope_counts: Dict[int, int] = {b: 0 for b in range(1, 67)}

        for p in pericopes:
            if p.start_canonical_id and p.end_canonical_id:
                try:
                    coords = expand_canonical_span(p.start_canonical_id, p.end_canonical_id)
                    for c in coords:
                        covered_counts[c] = covered_counts.get(c, 0) + 1
                    b_id = p.book_id or (p.start_canonical_id // 1_000_000)
                    pericope_counts[b_id] = pericope_counts.get(b_id, 0) + 1
                except Exception:
                    pass

        covered_set = set(covered_counts.keys())
        total_covered = len(covered_set)
        coverage_pct = (total_covered / TOTAL_CANONICAL_VERSES) * 100.0 if TOTAL_CANONICAL_VERSES > 0 else 0.0

        # Calculate overlap count
        overlap_count = sum(1 for c, cnt in covered_counts.items() if cnt > 1)

        # Compute book statistics
        book_stats: Dict[int, BookCoverageStats] = {}
        ot_covered = 0
        ot_total = 0
        nt_covered = 0
        nt_total = 0

        for b_id in range(1, 67):
            b_obj = BOOKS.get(b_id)
            b_name = b_obj.name if b_obj else f"Book_{b_id}"
            testament = b_obj.testament if b_obj else ("OT" if b_id <= 39 else "NT")
            expected_set = self._book_verses[b_id]
            b_cov = len(expected_set.intersection(covered_set))
            b_total = len(expected_set)
            b_pct = (b_cov / b_total) * 100.0 if b_total > 0 else 0.0

            if testament == "OT":
                ot_covered += b_cov
                ot_total += b_total
            else:
                nt_covered += b_cov
                nt_total += b_total

            book_stats[b_id] = BookCoverageStats(
                book_id=b_id,
                book_name=b_name,
                testament=testament,
                total_chapters=len(BOOK_CHAPTER_VERSES.get(b_id, ())),
                total_verses=b_total,
                covered_verses=b_cov,
                coverage_pct=b_pct,
                pericope_count=pericope_counts.get(b_id, 0),
            )

        ot_pct = (ot_covered / ot_total) * 100.0 if ot_total > 0 else 0.0
        nt_pct = (nt_covered / nt_total) * 100.0 if nt_total > 0 else 0.0

        # Compute gaps
        uncovered = sorted(self._all_canonical_verses - covered_set)
        gaps: List[CoverageGap] = []
        if uncovered:
            gap_start = uncovered[0]
            gap_prev = uncovered[0]
            for curr in uncovered[1:]:
                # Check if contiguous within same chapter
                b_curr, ch_curr, v_curr = canonical_id_to_triple(curr)
                b_prev, ch_prev, v_prev = canonical_id_to_triple(gap_prev)
                is_contiguous = False
                if b_curr == b_prev and ch_curr == ch_prev and v_curr == v_prev + 1:
                    is_contiguous = True
                elif b_curr == b_prev and ch_curr == ch_prev + 1 and v_curr == 1 and v_prev == get_canonical_max_verse(b_prev, ch_prev):
                    is_contiguous = True
                elif b_curr == b_prev + 1 and ch_curr == 1 and v_curr == 1 and ch_prev == len(BOOK_CHAPTER_VERSES.get(b_prev, ())) and v_prev == get_canonical_max_verse(b_prev, ch_prev):
                    is_contiguous = True

                if is_contiguous:
                    gap_prev = curr
                else:
                    b_g, _, _ = canonical_id_to_triple(gap_start)
                    b_name = BOOKS.get(b_g).name if BOOKS.get(b_g) else f"Book_{b_g}"
                    g_span = expand_canonical_span(gap_start, gap_prev)
                    gaps.append(
                        CoverageGap(
                            start_canonical_id=gap_start,
                            end_canonical_id=gap_prev,
                            start_human_ref=format_canonical_coordinate(gap_start),
                            end_human_ref=format_canonical_coordinate(gap_prev),
                            verse_count=len(g_span),
                            book_name=b_name,
                        )
                    )
                    gap_start = curr
                    gap_prev = curr

            # Append final gap
            b_g, _, _ = canonical_id_to_triple(gap_start)
            b_name = BOOKS.get(b_g).name if BOOKS.get(b_g) else f"Book_{b_g}"
            g_span = expand_canonical_span(gap_start, gap_prev)
            gaps.append(
                CoverageGap(
                    start_canonical_id=gap_start,
                    end_canonical_id=gap_prev,
                    start_human_ref=format_canonical_coordinate(gap_start),
                    end_human_ref=format_canonical_coordinate(gap_prev),
                    verse_count=len(g_span),
                    book_name=b_name,
                )
            )

        return WholeBibleCoverageReport(
            total_verses=TOTAL_CANONICAL_VERSES,
            covered_verses_count=total_covered,
            coverage_pct=coverage_pct,
            book_stats=book_stats,
            gaps=gaps,
            overlap_count=overlap_count,
            ot_coverage_pct=ot_pct,
            nt_coverage_pct=nt_pct,
            duration_sec=time.time() - t0,
        )

    def audit_theology_coverage(
        self,
        theology_records: Sequence[VerseTheologyRecord],
    ) -> WholeBibleCoverageReport:
        """Audit whole-Bible coverage for verse theology records."""
        t0 = time.time()
        covered_set: Set[int] = set()
        for vt in theology_records:
            if vt.start_canonical_id and vt.end_canonical_id:
                try:
                    coords = expand_canonical_span(vt.start_canonical_id, vt.end_canonical_id)
                    covered_set.update(coords)
                except Exception:
                    pass

        total_covered = len(covered_set)
        coverage_pct = (total_covered / TOTAL_CANONICAL_VERSES) * 100.0 if TOTAL_CANONICAL_VERSES > 0 else 0.0

        ot_covered = 0
        ot_total = 0
        nt_covered = 0
        nt_total = 0

        book_stats: Dict[int, BookCoverageStats] = {}
        for b_id in range(1, 67):
            b_obj = BOOKS.get(b_id)
            b_name = b_obj.name if b_obj else f"Book_{b_id}"
            testament = b_obj.testament if b_obj else ("OT" if b_id <= 39 else "NT")
            expected_set = self._book_verses[b_id]
            b_cov = len(expected_set.intersection(covered_set))
            b_total = len(expected_set)
            b_pct = (b_cov / b_total) * 100.0 if b_total > 0 else 0.0

            if testament == "OT":
                ot_covered += b_cov
                ot_total += b_total
            else:
                nt_covered += b_cov
                nt_total += b_total

            book_stats[b_id] = BookCoverageStats(
                book_id=b_id,
                book_name=b_name,
                testament=testament,
                total_chapters=len(BOOK_CHAPTER_VERSES.get(b_id, ())),
                total_verses=b_total,
                covered_verses=b_cov,
                coverage_pct=b_pct,
                pericope_count=0,
            )

        ot_pct = (ot_covered / ot_total) * 100.0 if ot_total > 0 else 0.0
        nt_pct = (nt_covered / nt_total) * 100.0 if nt_total > 0 else 0.0

        return WholeBibleCoverageReport(
            total_verses=TOTAL_CANONICAL_VERSES,
            covered_verses_count=total_covered,
            coverage_pct=coverage_pct,
            book_stats=book_stats,
            gaps=[],
            overlap_count=0,
            ot_coverage_pct=ot_pct,
            nt_coverage_pct=nt_pct,
            duration_sec=time.time() - t0,
        )

    def audit_database(self, db: Database) -> WholeBibleCoverageReport:
        """Query live SQLite database to evaluate whole-Bible pericope coverage."""
        cur = db.conn.cursor()
        cur.execute(
            """
            SELECT id, book_id, start_canonical_id, end_canonical_id, human_ref, title,
                   redemptive_summary, genre, literary_structure, central_proposition, created_at
            FROM pericopes
            ORDER BY start_canonical_id ASC
            """
        )
        rows = cur.fetchall()
        cur.close()
        pericopes = [
            PericopeRecord(
                id=r["id"],
                book_id=r["book_id"],
                start_canonical_id=r["start_canonical_id"],
                end_canonical_id=r["end_canonical_id"],
                human_ref=r["human_ref"],
                title=r["title"],
                redemptive_summary=r["redemptive_summary"],
                genre=r["genre"],
                literary_structure=r["literary_structure"],
                central_proposition=r["central_proposition"],
                created_at=r["created_at"],
            )
            for r in rows
        ]
        return self.audit_pericopes(pericopes)


# ==============================================================================
# 6. Unified Semantic Quality Auditor (Facade)
# ==============================================================================


class SemanticQualityAuditor:
    """Unified quality auditor combining coordinate checks, schema validation, critic, and coverage."""

    def __init__(self) -> None:
        self.critic = ExegeticalCritic()
        self.deduplicator = self.critic.deduplicator
        self.coverage_auditor = WholeBibleCoverageAuditor()

    def audit_pericope_analysis(self, result: PericopeAnalysisResult) -> AuditReport:
        """Critique and audit a single LLM pericope analysis result."""
        return self.critic.audit_pericope_analysis_result(result)

    def audit_database(
        self,
        db: Database,
        include_coverage: bool = True,
        strict: bool = False,
    ) -> Tuple[AuditReport, Optional[WholeBibleCoverageReport]]:
        """Run deep audit across all semantic records in a SQLite database."""
        t0 = time.time()
        report = AuditReport()

        cur = db.conn.cursor()

        # 1. Audit all pericopes
        cur.execute(
            """
            SELECT id, book_id, start_canonical_id, end_canonical_id, human_ref, title,
                   redemptive_summary, genre, literary_structure, central_proposition, created_at
            FROM pericopes
            ORDER BY start_canonical_id ASC
            """
        )
        p_rows = cur.fetchall()
        pericopes: List[PericopeRecord] = []
        for r in p_rows:
            p_rec = PericopeRecord(
                id=r["id"],
                book_id=r["book_id"],
                start_canonical_id=r["start_canonical_id"],
                end_canonical_id=r["end_canonical_id"],
                human_ref=r["human_ref"],
                title=r["title"],
                redemptive_summary=r["redemptive_summary"],
                genre=r["genre"],
                literary_structure=r["literary_structure"],
                central_proposition=r["central_proposition"],
                created_at=r["created_at"],
            )
            pericopes.append(p_rec)
            report.merge(self.critic.audit_pericope(p_rec, strict=strict))

        # 2. Audit all discourse relations
        cur.execute(
            """
            SELECT id, source_canonical_id, source_human_ref, target_canonical_id, target_human_ref,
                   relation_type, marker_text, greek_marker, notes, created_at
            FROM discourse_relations
            """
        )
        d_rows = cur.fetchall()
        disc_recs = [
            DiscourseRelationRecord(
                id=r["id"],
                source_canonical_id=r["source_canonical_id"],
                source_human_ref=r["source_human_ref"],
                target_canonical_id=r["target_canonical_id"],
                target_human_ref=r["target_human_ref"],
                relation_type=r["relation_type"],
                marker_text=r["marker_text"],
                greek_marker=r["greek_marker"],
                notes=r["notes"],
                created_at=r["created_at"],
            )
            for r in d_rows
        ]
        report.merge(self.critic.audit_discourse_relations(disc_recs))

        # 3. Audit all verse theology records
        cur.execute(
            """
            SELECT id, start_canonical_id, end_canonical_id, human_ref, storyline_epoch,
                   theological_locus, primary_doctrine, thematic_ribbon, confidence, created_at
            FROM verse_theology
            """
        )
        vt_rows = cur.fetchall()
        theol_recs = [
            VerseTheologyRecord(
                id=r["id"],
                start_canonical_id=r["start_canonical_id"],
                end_canonical_id=r["end_canonical_id"],
                human_ref=r["human_ref"],
                storyline_epoch=r["storyline_epoch"],
                theological_locus=r["theological_locus"],
                primary_doctrine=r["primary_doctrine"],
                thematic_ribbon=r["thematic_ribbon"],
                confidence=r["confidence"],
                created_at=r["created_at"],
            )
            for r in vt_rows
        ]
        report.merge(self.critic.audit_verse_theology(theol_recs))

        # 4. Audit all typological arcs
        cur.execute(
            """
            SELECT id, type_start_id, type_end_id, type_human_ref, antitype_start_id,
                   antitype_end_id, antitype_human_ref, theological_correspondence, warrant, confidence, created_at
            FROM typological_arcs
            """
        )
        ta_rows = cur.fetchall()
        typo_recs = [
            TypologicalArcRecord(
                id=r["id"],
                type_start_id=r["type_start_id"],
                type_end_id=r["type_end_id"],
                type_human_ref=r["type_human_ref"],
                antitype_start_id=r["antitype_start_id"],
                antitype_end_id=r["antitype_end_id"],
                antitype_human_ref=r["antitype_human_ref"],
                theological_correspondence=r["theological_correspondence"],
                warrant=r["warrant"],
                confidence=r["confidence"],
                created_at=r["created_at"],
            )
            for r in ta_rows
        ]
        report.merge(self.critic.audit_typological_arcs(typo_recs))

        # 5. Audit all semantic propositions
        cur.execute(
            """
            SELECT id, canonical_verse_id, human_ref, speech_act, agent, action,
                   patient, tone, clause_text, created_at
            FROM semantic_propositions
            """
        )
        sp_rows = cur.fetchall()
        prop_recs = [
            SemanticPropositionRecord(
                id=r["id"],
                canonical_verse_id=r["canonical_verse_id"],
                human_ref=r["human_ref"],
                speech_act=r["speech_act"],
                agent=r["agent"],
                action=r["action"],
                patient=r["patient"],
                tone=r["tone"],
                clause_text=r["clause_text"],
                created_at=r["created_at"],
            )
            for r in sp_rows
        ]
        report.merge(self.critic.audit_semantic_propositions(prop_recs))

        cur.close()

        cov_report: Optional[WholeBibleCoverageReport] = None
        if include_coverage:
            cov_report = self.coverage_auditor.audit_pericopes(pericopes)

        report.duration_sec = time.time() - t0
        return report, cov_report


# ==============================================================================
# Module Singletons & Convenience Helpers
# ==============================================================================

_DEFAULT_AUDITOR = SemanticQualityAuditor()


def get_semantic_auditor() -> SemanticQualityAuditor:
    """Return default singleton SemanticQualityAuditor instance."""
    return _DEFAULT_AUDITOR


def audit_pericope_analysis(result: PericopeAnalysisResult) -> AuditReport:
    """Convenience function to critique an LLM pericope result."""
    return _DEFAULT_AUDITOR.audit_pericope_analysis(result)


def audit_whole_bible_coverage(pericopes: Sequence[PericopeRecord]) -> WholeBibleCoverageReport:
    """Convenience function to audit whole-Bible pericope coverage."""
    return _DEFAULT_AUDITOR.coverage_auditor.audit_pericopes(pericopes)


# ==============================================================================
# 6. Sovereign Semantic Quality Audit Cache Ledger
# ==============================================================================

DEFAULT_SEMANTIC_AUDIT_CACHE_PATH: Path = REPO_ROOT / ".semantic_audit_cache.json"


def compute_db_audit_fingerprint(db_path: Path, db: Optional[Database] = None) -> Dict[str, Any]:
    """Compute mathematical fingerprint of a SQLite database file for audit caching.

    Combines filesystem metadata (size, mtime) with SQLite internal version counters
    (PRAGMA data_version, PRAGMA schema_version) to guarantee zero false-cache hits.
    """
    target = db_path.resolve()
    if not target.exists():
        return {}
    st = target.stat()
    data_version = 0
    schema_version = 0
    try:
        if db is not None and db.conn:
            cur = db.conn.cursor()
            cur.execute("PRAGMA data_version")
            row = cur.fetchone()
            if row:
                data_version = int(row[0])
            cur.execute("PRAGMA schema_version")
            row = cur.fetchone()
            if row:
                schema_version = int(row[0])
            cur.close()
        else:
            with sqlite3.connect(f"file:{target}?mode=ro", uri=True) as conn:
                cur = conn.cursor()
                cur.execute("PRAGMA data_version")
                row = cur.fetchone()
                if row:
                    data_version = int(row[0])
                cur.execute("PRAGMA schema_version")
                row = cur.fetchone()
                if row:
                    schema_version = int(row[0])
                cur.close()
    except Exception:
        pass

    return {
        "path": str(target),
        "size_bytes": st.st_size,
        "mtime": st.st_mtime,
        "data_version": data_version,
        "schema_version": schema_version,
    }


def load_audit_cache(cache_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load cached audit ledger dictionary from disk."""
    p = cache_path or DEFAULT_SEMANTIC_AUDIT_CACHE_PATH
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_audit_cache(
    db_path: Path,
    audit_report: AuditReport,
    cov_report: Optional[WholeBibleCoverageReport],
    cache_path: Optional[Path] = None,
    db: Optional[Database] = None,
    integrity: str = "ok",
) -> bool:
    """Atomically save audit report and coverage metrics to JSON cache ledger keyed by DB path."""
    p = cache_path or DEFAULT_SEMANTIC_AUDIT_CACHE_PATH
    try:
        target_str = str(db_path.resolve())
        fp = compute_db_audit_fingerprint(db_path, db=db)
        if not fp:
            return False
        cache = load_audit_cache(p)
        cache[target_str] = {
            "fingerprint": fp,
            "cached_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "integrity": integrity,
            "audit_report": audit_report.to_dict(),
            "coverage_report": cov_report.to_dict() if cov_report else None,
        }
        tmp_p = p.with_suffix(".tmp")
        tmp_p.write_text(json.dumps(cache, indent=2), encoding="utf-8")
        tmp_p.replace(p)
        return True
    except Exception:
        return False


def is_audit_cache_valid(
    db_path: Path,
    cache_path: Optional[Path] = None,
    db: Optional[Database] = None,
) -> bool:
    """Check if the cache ledger matches current database state for the target database."""
    target_str = str(db_path.resolve())
    cache = load_audit_cache(cache_path)
    entry = cache.get(target_str)
    if not entry or "fingerprint" not in entry:
        return False
    cached_fp = entry["fingerprint"]
    current_fp = compute_db_audit_fingerprint(db_path, db=db)
    if not current_fp:
        return False
    return (
        cached_fp.get("size_bytes") == current_fp.get("size_bytes")
        and cached_fp.get("mtime") == current_fp.get("mtime")
        and cached_fp.get("data_version") == current_fp.get("data_version")
        and cached_fp.get("schema_version") == current_fp.get("schema_version")
    )


def get_cached_or_run_audit(
    db: Database,
    cache_path: Optional[Path] = None,
    force_re_audit: bool = False,
    include_coverage: bool = True,
    strict: bool = False,
) -> Tuple[AuditReport, Optional[WholeBibleCoverageReport], bool]:
    """Retrieve cached audit report if valid, or execute full audit and update cache ledger.

    Returns:
        Tuple of (AuditReport, Optional[WholeBibleCoverageReport], was_cached: bool).
    """
    db_path = Path(db.db_path) if hasattr(db, "db_path") else Path(DEFAULT_DB_PATH)
    target_str = str(db_path.resolve())
    if not force_re_audit and is_audit_cache_valid(db_path, cache_path=cache_path, db=db):
        cache = load_audit_cache(cache_path)
        entry = cache.get(target_str)
        if entry and "audit_report" in entry:
            try:
                audit_rep = AuditReport.from_dict(entry["audit_report"])
                cov_rep = None
                if include_coverage and entry.get("coverage_report"):
                    cov_rep = WholeBibleCoverageReport.from_dict(entry["coverage_report"])
                return audit_rep, cov_rep, True
            except Exception:
                pass

    # Run full audit
    auditor = get_semantic_auditor()
    audit_rep, cov_rep = auditor.audit_database(db, include_coverage=include_coverage, strict=strict)
    save_audit_cache(db_path, audit_rep, cov_rep, cache_path=cache_path, db=db, integrity="ok")
    return audit_rep, cov_rep, False

