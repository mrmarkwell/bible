"""SQLite Database Schema & Connection Manager for Bible Engine.

Zero-dependency implementation (Python 3 standard library only per ADR-003):
- SQLite connection management with WAL journal mode, foreign keys, and transaction support.
- Fully normalized schema: books, translations, verses, spans, tags, verse_tags, cross_references.
- High-performance SQLite FTS5 full-text search with automatic synchronization triggers.
- Canonical integer ID encoding for ultra-fast, index-backed passage range queries.
- Multi-resolution semantic tagging supporting individual verses, pericopes, chapters, and spans.
- Forward-compatible tables for theological enrichment (pericopes, typology, character profiles).
"""

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import sqlite3
import sys

from typing import Any, Dict, Generator, List, Optional, Sequence, Tuple, Union


from core.reference import (
    ALL_BOOKS,
    BOOKS,
    Book,
    Reference,
    get_book,
    parse_reference,
    verse_canonical_id,
)

# Default location for SQLite database: <repo_root>/data/bible.db
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "bible.db"


def _utc_now_iso() -> str:
    """Return current UTC timestamp formatted as ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def sanitize_fts_query(query: str) -> str:
    """Sanitize and format query string for safe SQLite FTS5 matching.

    Extracts word tokens and quoted phrases, escaping quotes and safely structuring
    Boolean operators (AND, OR, NOT) while avoiding syntax errors on punctuation.
    """
    q = query.strip()
    if not q:
        return ""

    # Match either single/double quoted strings or sequences of word characters
    parts = re.findall(r"\"[^\"]+\"|'[^']+'|\w+", q)
    if not parts:
        return ""

    valid_tokens: List[str] = []
    prev_is_op = True

    for p in parts:
        upper_p = p.upper()
        if upper_p in ("AND", "OR"):
            if not prev_is_op:
                valid_tokens.append(upper_p)
                prev_is_op = True
        elif upper_p == "NOT":
            if not prev_is_op:
                valid_tokens.append("NOT")
                prev_is_op = True
        else:
            if not prev_is_op:
                valid_tokens.append("AND")
            if (p.startswith('"') and p.endswith('"')) or (p.startswith("'") and p.endswith("'")):
                inner = p[1:-1].replace('"', '""').strip()
                if inner:
                    valid_tokens.append(f'"{inner}"')
                    prev_is_op = False
            else:
                valid_tokens.append(f'"{p}"')
                prev_is_op = False

    # Strip any trailing dangling operators
    while valid_tokens and valid_tokens[-1] in ("AND", "OR", "NOT"):
        valid_tokens.pop()

    return " ".join(valid_tokens)


def normalize_tag_name(name: str) -> str:
    """Normalize a semantic tag name to canonical lowercase snake_case.

    Rules:
    - Strips leading '#' symbol (e.g. '#starred' -> 'starred').
    - Strips leading and trailing whitespace.
    - Replaces spaces, hyphens, and non-alphanumeric characters with underscores.
    - Strips leading and trailing underscores.
    - Collapses consecutive underscores into a single underscore.
    - Converts to lowercase.

    Raises:
        ValueError: If tag name is empty or contains no alphanumeric characters.
    """
    if not isinstance(name, str):
        raise ValueError("Tag name must be a string.")
    clean = name.strip()
    if clean.startswith("#"):
        clean = clean.lstrip("#").strip()
    if not clean:
        raise ValueError("Tag name cannot be empty.")
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", clean).strip("_").lower()
    if not normalized:
        raise ValueError(f"Tag name '{name}' contains no valid alphanumeric characters.")
    return normalized


# --- Data Transfer Objects & Records ---


@dataclass(frozen=True)
class TranslationRecord:
    """Metadata record for a Bible translation."""

    id: str  # e.g., "WEB", "KJV", "ESV"
    name: str  # e.g., "World English Bible"
    language: str = "en"
    is_public_domain: bool = True
    is_encrypted: bool = False
    license_notes: Optional[str] = None
    created_at: Optional[str] = None


@dataclass(frozen=True)
class VerseRecord:
    """Represents a single verse row stored in the database."""

    translation_id: str
    book_id: int  # 1 to 66
    chapter: int
    verse: int
    text: str
    subverse: str = ""
    osis_ref: Optional[str] = None
    canonical_verse_id: Optional[int] = None
    id: Optional[int] = None
    book_name: Optional[str] = None

    def __post_init__(self) -> None:
        # Auto-compute canonical ID and OSIS ref if not provided
        b = BOOKS.get(self.book_id)
        if b:
            if not self.book_name:
                object.__setattr__(self, "book_name", b.name)
            if not self.osis_ref:
                sub = self.subverse or ""
                object.__setattr__(self, "osis_ref", f"{b.osis}.{self.chapter}.{self.verse}{sub}")
            if self.canonical_verse_id is None:
                cid = verse_canonical_id(b, self.chapter, self.verse)
                object.__setattr__(self, "canonical_verse_id", cid)

    @property
    def book(self) -> Optional[Book]:
        """Canonical Book instance."""
        return BOOKS.get(self.book_id)

    @property
    def human_ref(self) -> str:
        """Human-readable citation (e.g. 'John 3:16')."""
        bname = self.book_name or (self.book.name if self.book else f"Book_{self.book_id}")
        sub = self.subverse or ""
        return f"{bname} {self.chapter}:{self.verse}{sub}"


@dataclass(frozen=True)
class SpanRecord:
    """Represents a passage span (verse range, pericope, or chapter)."""

    id: Optional[int]
    human_ref: str
    osis_ref: str
    book_id: int
    start_canonical_id: int
    end_canonical_id: int
    label: Optional[str] = None
    created_at: Optional[str] = None


@dataclass(frozen=True)
class TagRecord:
    """Represents a category or semantic classification tag."""

    id: Optional[int]
    name: str
    category: str = "thematic"
    description: Optional[str] = None
    created_at: Optional[str] = None


@dataclass(frozen=True)
class VerseTagRecord:
    """Associates a semantic tag with a verse, span, or chapter."""

    id: Optional[int]
    tag_id: int
    tag_name: str
    start_canonical_id: int
    end_canonical_id: int
    human_ref: str
    confidence: float = 1.0
    source: str = "human"  # 'human', 'curation', 'llm-gemini'
    starred: bool = False
    notes: Optional[str] = None
    span_id: Optional[int] = None
    created_at: Optional[str] = None
    category: Optional[str] = None


@dataclass(frozen=True)
class CrossReferenceRecord:
    """Represents a relational link between two scripture passages."""

    id: Optional[int]
    source_start_id: int
    source_end_id: int
    source_human_ref: str
    target_start_id: int
    target_end_id: int
    target_human_ref: str
    relationship_type: str = "thematic"  # 'thematic', 'prophecy_fulfillment', 'quotation', 'typology'
    weight: float = 1.0
    notes: Optional[str] = None
    created_at: Optional[str] = None


@dataclass(frozen=True)
class PericopeRecord:
    """Represents a discrete scripture pericope section with heading and redemptive summary."""

    id: Optional[int]
    book_id: int
    start_canonical_id: int
    end_canonical_id: int
    human_ref: str
    title: str
    redemptive_summary: Optional[str] = None
    genre: Optional[str] = None
    literary_structure: Optional[str] = None
    central_proposition: Optional[str] = None
    created_at: Optional[str] = None

    @property
    def book(self) -> Optional[Book]:
        """Associated canonical Book object."""
        return BOOKS.get(self.book_id)

    @property
    def book_name(self) -> str:
        """Name of the canonical book."""
        return self.book.name if self.book else f"Book_{self.book_id}"

    @property
    def osis(self) -> str:
        """OSIS code of the book."""
        return self.book.osis if self.book else ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert pericope record to dictionary representation."""
        return {
            "id": self.id,
            "book_id": self.book_id,
            "book_name": self.book_name,
            "osis": self.osis,
            "start_canonical_id": self.start_canonical_id,
            "end_canonical_id": self.end_canonical_id,
            "human_ref": self.human_ref,
            "title": self.title,
            "redemptive_summary": self.redemptive_summary,
            "genre": self.genre,
            "literary_structure": self.literary_structure,
            "central_proposition": self.central_proposition,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class DiscourseRelationRecord:
    """Represents a clause or verse-level discourse relation."""

    id: Optional[int]
    source_canonical_id: int
    source_human_ref: str
    relation_type: str  # ground, inference, purpose, contrast, condition, concession, result, temporal
    target_canonical_id: Optional[int] = None
    target_human_ref: Optional[str] = None
    marker_text: Optional[str] = None
    greek_marker: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert discourse relation record to dictionary representation."""
        return {
            "id": self.id,
            "source_canonical_id": self.source_canonical_id,
            "source_human_ref": self.source_human_ref,
            "target_canonical_id": self.target_canonical_id,
            "target_human_ref": self.target_human_ref,
            "relation_type": self.relation_type,
            "marker_text": self.marker_text,
            "greek_marker": self.greek_marker,
            "notes": self.notes,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class VerseTheologyRecord:
    """Represents theological locus, storyline epoch, and thematic ribbon for a verse/passage."""

    id: Optional[int]
    start_canonical_id: int
    end_canonical_id: int
    human_ref: str
    storyline_epoch: str
    theological_locus: str
    primary_doctrine: str
    thematic_ribbon: Optional[str] = None
    confidence: float = 1.0
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert verse theology record to dictionary representation."""
        return {
            "id": self.id,
            "start_canonical_id": self.start_canonical_id,
            "end_canonical_id": self.end_canonical_id,
            "human_ref": self.human_ref,
            "storyline_epoch": self.storyline_epoch,
            "theological_locus": self.theological_locus,
            "primary_doctrine": self.primary_doctrine,
            "thematic_ribbon": self.thematic_ribbon,
            "confidence": self.confidence,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class TypologicalArcRecord:
    """Represents a canonical typological arc linking Old Testament type to New Testament antitype."""

    id: Optional[int]
    type_start_id: int
    type_end_id: int
    type_human_ref: str
    antitype_start_id: int
    antitype_end_id: int
    antitype_human_ref: str
    theological_correspondence: str
    warrant: Optional[str] = None
    confidence: float = 1.0
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert typological arc record to dictionary representation."""
        return {
            "id": self.id,
            "type_start_id": self.type_start_id,
            "type_end_id": self.type_end_id,
            "type_human_ref": self.type_human_ref,
            "antitype_start_id": self.antitype_start_id,
            "antitype_end_id": self.antitype_end_id,
            "antitype_human_ref": self.antitype_human_ref,
            "theological_correspondence": self.theological_correspondence,
            "warrant": self.warrant,
            "confidence": self.confidence,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class SemanticPropositionRecord:
    """Represents an agent-action-patient semantic triple, speech act, and devotional tone."""

    id: Optional[int]
    canonical_verse_id: int
    human_ref: str
    speech_act: str
    agent: str
    action: str
    patient: Optional[str] = None
    tone: Optional[str] = None
    clause_text: Optional[str] = None
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert semantic proposition record to dictionary representation."""
        return {
            "id": self.id,
            "canonical_verse_id": self.canonical_verse_id,
            "human_ref": self.human_ref,
            "speech_act": self.speech_act,
            "agent": self.agent,
            "action": self.action,
            "patient": self.patient,
            "tone": self.tone,
            "clause_text": self.clause_text,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class CharacterProfileRecord:
    """Represents a canonical biblical character profile entity."""

    id: Optional[int]
    name: str
    canonical_spans: Optional[str] = None
    historical_context: Optional[str] = None
    theological_role: Optional[str] = None
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert character profile record to dictionary representation."""
        return {
            "id": self.id,
            "name": self.name,
            "canonical_spans": self.canonical_spans,
            "historical_context": self.historical_context,
            "theological_role": self.theological_role,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class VerseEmbeddingRecord:
    """Represents a dense vector embedding stored as a binary BLOB for a canonical verse."""

    canonical_verse_id: int
    human_ref: str
    model_id: str
    dimensions: int
    embedding: bytes
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert verse embedding record to dictionary representation."""
        return {
            "canonical_verse_id": self.canonical_verse_id,
            "human_ref": self.human_ref,
            "model_id": self.model_id,
            "dimensions": self.dimensions,
            "embedding_bytes": len(self.embedding),
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class PericopeEmbeddingRecord:
    """Represents a dense vector embedding stored as a binary BLOB for a pericope unit."""

    pericope_id: int
    start_canonical_id: int
    end_canonical_id: int
    human_ref: str
    model_id: str
    dimensions: int
    embedding: bytes
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert pericope embedding record to dictionary representation."""
        return {
            "pericope_id": self.pericope_id,
            "start_canonical_id": self.start_canonical_id,
            "end_canonical_id": self.end_canonical_id,
            "human_ref": self.human_ref,
            "model_id": self.model_id,
            "dimensions": self.dimensions,
            "embedding_bytes": len(self.embedding),
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class SearchResult:
    """Result item returned by FTS5 full-text search."""

    verse_id: int
    translation_id: str
    book_name: str
    osis_ref: str
    chapter: int
    verse: int
    text: str
    snippet: str
    rank: float

    @property
    def human_ref(self) -> str:
        """Formatted human reference string."""
        return f"{self.book_name} {self.chapter}:{self.verse}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert search result item to dictionary representation."""
        return {
            "verse_id": self.verse_id,
            "reference": self.human_ref,
            "book": self.book_name,
            "chapter": self.chapter,
            "verse": self.verse,
            "translation": self.translation_id,
            "text": self.text,
            "snippet": self.snippet,
            "rank": round(self.rank, 4),
        }


# --- Database Schema SQL ---

SCHEMA_SQL = """
-- Books catalog: Protestant 66 canonical books
CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    osis TEXT NOT NULL UNIQUE,
    testament TEXT NOT NULL CHECK(testament IN ('OT', 'NT')),
    canonical_order INTEGER NOT NULL UNIQUE,
    total_chapters INTEGER NOT NULL
);

-- Bible Translations metadata table
CREATE TABLE IF NOT EXISTS translations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'en',
    is_public_domain INTEGER NOT NULL DEFAULT 1,
    is_encrypted INTEGER NOT NULL DEFAULT 0,
    license_notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Verses storage table
CREATE TABLE IF NOT EXISTS verses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    translation_id TEXT NOT NULL,
    book_id INTEGER NOT NULL,
    chapter INTEGER NOT NULL,
    verse INTEGER NOT NULL,
    subverse TEXT DEFAULT '',
    text TEXT NOT NULL,
    osis_ref TEXT NOT NULL,
    canonical_verse_id INTEGER NOT NULL,
    FOREIGN KEY (translation_id) REFERENCES translations(id) ON DELETE CASCADE,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE RESTRICT,
    UNIQUE (translation_id, book_id, chapter, verse, subverse)
);

CREATE INDEX IF NOT EXISTS idx_verses_lookup
ON verses(translation_id, book_id, chapter, verse);

CREATE INDEX IF NOT EXISTS idx_verses_canonical_id
ON verses(translation_id, canonical_verse_id);

CREATE INDEX IF NOT EXISTS idx_verses_osis
ON verses(translation_id, osis_ref);

-- Full-Text Search (FTS5) virtual table
CREATE VIRTUAL TABLE IF NOT EXISTS verses_fts USING fts5(
    verse_id UNINDEXED,
    translation_id,
    book_name,
    osis_ref,
    text,
    tokenize='porter unicode61'
);

-- Triggers to synchronize FTS5 index automatically with verses table
CREATE TRIGGER IF NOT EXISTS trg_verses_fts_insert AFTER INSERT ON verses
BEGIN
    INSERT INTO verses_fts(verse_id, translation_id, book_name, osis_ref, text)
    VALUES (
        new.id,
        new.translation_id,
        (SELECT name FROM books WHERE id = new.book_id),
        new.osis_ref,
        new.text
    );
END;

CREATE TRIGGER IF NOT EXISTS trg_verses_fts_delete AFTER DELETE ON verses
BEGIN
    DELETE FROM verses_fts WHERE verse_id = old.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_verses_fts_update AFTER UPDATE ON verses
BEGIN
    DELETE FROM verses_fts WHERE verse_id = old.id;
    INSERT INTO verses_fts(verse_id, translation_id, book_name, osis_ref, text)
    VALUES (
        new.id,
        new.translation_id,
        (SELECT name FROM books WHERE id = new.book_id),
        new.osis_ref,
        new.text
    );
END;

-- Arbitrary passage spans (multi-verse passages, pericopes, chapters)
CREATE TABLE IF NOT EXISTS spans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    human_ref TEXT NOT NULL,
    osis_ref TEXT NOT NULL,
    book_id INTEGER NOT NULL,
    start_canonical_id INTEGER NOT NULL,
    end_canonical_id INTEGER NOT NULL,
    label TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_spans_canonical_range
ON spans(start_canonical_id, end_canonical_id);

-- Semantic tags dictionary
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    category TEXT NOT NULL DEFAULT 'thematic',
    description TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_tags_category
ON tags(category);

-- Multi-resolution tag associations for individual verses and spans
CREATE TABLE IF NOT EXISTS verse_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tag_id INTEGER NOT NULL,
    span_id INTEGER,
    start_canonical_id INTEGER NOT NULL,
    end_canonical_id INTEGER NOT NULL,
    human_ref TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 1.0,
    source TEXT NOT NULL DEFAULT 'human',
    starred INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE,
    FOREIGN KEY (span_id) REFERENCES spans(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_verse_tags_tag
ON verse_tags(tag_id);

CREATE INDEX IF NOT EXISTS idx_verse_tags_range
ON verse_tags(start_canonical_id, end_canonical_id);

CREATE INDEX IF NOT EXISTS idx_verse_tags_starred
ON verse_tags(starred);

-- Cross-references and scripture edge relationships
CREATE TABLE IF NOT EXISTS cross_references (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_start_id INTEGER NOT NULL,
    source_end_id INTEGER NOT NULL,
    source_human_ref TEXT NOT NULL,
    target_start_id INTEGER NOT NULL,
    target_end_id INTEGER NOT NULL,
    target_human_ref TEXT NOT NULL,
    relationship_type TEXT NOT NULL DEFAULT 'thematic',
    weight REAL NOT NULL DEFAULT 1.0,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_cross_ref_source
ON cross_references(source_start_id, source_end_id);

CREATE INDEX IF NOT EXISTS idx_cross_ref_target
ON cross_references(target_start_id, target_end_id);

CREATE INDEX IF NOT EXISTS idx_cross_ref_type
ON cross_references(relationship_type);

-- Phase 7 6-Layer Semantic Architecture Tables (ADR-042)

-- Layer 1: Pericopes with genre, literary structure, central proposition, and redemptive summary
CREATE TABLE IF NOT EXISTS pericopes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL,
    start_canonical_id INTEGER NOT NULL,
    end_canonical_id INTEGER NOT NULL,
    human_ref TEXT NOT NULL,
    title TEXT NOT NULL,
    redemptive_summary TEXT,
    genre TEXT,
    literary_structure TEXT,
    central_proposition TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_pericopes_book
ON pericopes(book_id, start_canonical_id);

CREATE INDEX IF NOT EXISTS idx_pericopes_range
ON pericopes(start_canonical_id, end_canonical_id);

-- Layer 1: Discourse Relations (ground, inference, purpose, contrast, condition, etc.)
CREATE TABLE IF NOT EXISTS discourse_relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_canonical_id INTEGER NOT NULL,
    source_human_ref TEXT NOT NULL,
    target_canonical_id INTEGER,
    target_human_ref TEXT,
    relation_type TEXT NOT NULL,
    marker_text TEXT,
    greek_marker TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_discourse_source
ON discourse_relations(source_canonical_id);

CREATE INDEX IF NOT EXISTS idx_discourse_target
ON discourse_relations(target_canonical_id);

CREATE INDEX IF NOT EXISTS idx_discourse_type
ON discourse_relations(relation_type);

-- Layer 2: Dual-Horizon Verse Theology (storyline epoch, thematic ribbon, theological locus, doctrine)
CREATE TABLE IF NOT EXISTS verse_theology (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_canonical_id INTEGER NOT NULL,
    end_canonical_id INTEGER NOT NULL,
    human_ref TEXT NOT NULL,
    storyline_epoch TEXT NOT NULL,
    thematic_ribbon TEXT,
    theological_locus TEXT NOT NULL,
    primary_doctrine TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 1.0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_verse_theology_range
ON verse_theology(start_canonical_id, end_canonical_id);

CREATE INDEX IF NOT EXISTS idx_verse_theology_epoch
ON verse_theology(storyline_epoch);

CREATE INDEX IF NOT EXISTS idx_verse_theology_ribbon
ON verse_theology(thematic_ribbon);

CREATE INDEX IF NOT EXISTS idx_verse_theology_locus
ON verse_theology(theological_locus);

-- Layer 3: Typological Arcs (type, antitype, theological correspondence, warrant)
CREATE TABLE IF NOT EXISTS typological_arcs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type_start_id INTEGER NOT NULL,
    type_end_id INTEGER NOT NULL,
    type_human_ref TEXT NOT NULL,
    antitype_start_id INTEGER NOT NULL,
    antitype_end_id INTEGER NOT NULL,
    antitype_human_ref TEXT NOT NULL,
    theological_correspondence TEXT NOT NULL,
    warrant TEXT,
    confidence REAL NOT NULL DEFAULT 1.0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_typological_arcs_type
ON typological_arcs(type_start_id, type_end_id);

CREATE INDEX IF NOT EXISTS idx_typological_arcs_antitype
ON typological_arcs(antitype_start_id, antitype_end_id);

CREATE TABLE IF NOT EXISTS typology_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type_start_id INTEGER NOT NULL,
    type_end_id INTEGER NOT NULL,
    type_human_ref TEXT NOT NULL,
    antitype_start_id INTEGER NOT NULL,
    antitype_end_id INTEGER NOT NULL,
    antitype_human_ref TEXT NOT NULL,
    theological_connection TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Layer 4 & 5: Entity Character Profiles, Theological Themes & Semantic Propositions
CREATE TABLE IF NOT EXISTS character_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    canonical_spans TEXT,
    historical_context TEXT,
    theological_role TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS theological_themes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    axis TEXT NOT NULL CHECK(axis IN ('along_canon', 'across_doctrine')),
    description TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS semantic_propositions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_verse_id INTEGER NOT NULL,
    human_ref TEXT NOT NULL,
    speech_act TEXT NOT NULL,
    agent TEXT NOT NULL,
    action TEXT NOT NULL,
    patient TEXT,
    tone TEXT,
    clause_text TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_propositions_verse
ON semantic_propositions(canonical_verse_id);

CREATE INDEX IF NOT EXISTS idx_propositions_agent
ON semantic_propositions(agent);

CREATE INDEX IF NOT EXISTS idx_propositions_action
ON semantic_propositions(action);

CREATE INDEX IF NOT EXISTS idx_propositions_speech_act
ON semantic_propositions(speech_act);

-- Layer 6: Dense Vector Embeddings for Verses and Pericopes (BLOB storage)
CREATE TABLE IF NOT EXISTS verse_embeddings (
    canonical_verse_id INTEGER PRIMARY KEY,
    human_ref TEXT NOT NULL,
    model_id TEXT NOT NULL,
    dimensions INTEGER NOT NULL,
    embedding BLOB NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS pericope_embeddings (
    pericope_id INTEGER PRIMARY KEY,
    start_canonical_id INTEGER NOT NULL,
    end_canonical_id INTEGER NOT NULL,
    human_ref TEXT NOT NULL,
    model_id TEXT NOT NULL,
    dimensions INTEGER NOT NULL,
    embedding BLOB NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (pericope_id) REFERENCES pericopes(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pericope_embeddings_range
ON pericope_embeddings(start_canonical_id, end_canonical_id);

-- Ephemeral Crossway-compliant 500-verse LRU cache for ESV text (ADR-041)
CREATE TABLE IF NOT EXISTS esv_cache (
    canonical_verse_id INTEGER PRIMARY KEY,
    book_id INTEGER NOT NULL,
    chapter INTEGER NOT NULL,
    verse INTEGER NOT NULL,
    subverse TEXT DEFAULT '',
    text TEXT NOT NULL,
    osis_ref TEXT NOT NULL,
    last_accessed_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_esv_cache_accessed
ON esv_cache(last_accessed_at);
"""


class Database:
    """SQLite Database Manager for Bible Engine.

    Encapsulates connection lifecycle, schema initialization, and high-performance
    data access methods for translations, verses, full-text search, spans, tags,
    and cross references.
    """

    def __init__(
        self,
        db_path: Union[str, Path] = DEFAULT_DB_PATH,
        auto_init: bool = True,
        check_same_thread: bool = True,
    ) -> None:
        """Initialize database manager.

        Args:
            db_path: Path to SQLite file or ":memory:".
            auto_init: If True, automatically initialize schema and books catalog.
            check_same_thread: If False, allow connection sharing across threads (useful for web servers).
        """
        self.db_path = db_path
        self._is_memory = str(db_path) == ":memory:"

        if not self._is_memory:
            path_obj = Path(db_path)
            path_obj.parent.mkdir(parents=True, exist_ok=True)
            self._target = str(path_obj)
        else:
            self._target = ":memory:"

        self.conn = sqlite3.connect(
            self._target,
            detect_types=sqlite3.PARSE_DECLTYPES,
            check_same_thread=check_same_thread,
        )
        self.conn.row_factory = sqlite3.Row

        # Optimize SQLite performance for analytical reads and concurrent writes
        self._configure_pragmas()
        self._esv_client: Optional[Any] = None
        self._max_cross_ref_spans: Optional[Tuple[int, int]] = None

        if auto_init:
            self.init_schema()

    def _configure_pragmas(self) -> None:
        """Set performance and safety pragmas."""
        cur = self.conn.cursor()
        cur.execute("PRAGMA foreign_keys = ON;")
        if not self._is_memory:
            # WAL mode enables concurrent readers while writers work
            cur.execute("PRAGMA journal_mode = WAL;")
            cur.execute("PRAGMA synchronous = NORMAL;")
        cur.close()

    def close(self) -> None:
        """Close SQLite database connection."""
        if hasattr(self, "conn") and self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def execute_sql(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
        """Execute arbitrary SQL statement and return cursor."""
        return self.conn.execute(sql, params)

    def vacuum(self) -> None:
        """Run SQLite VACUUM to reclaim disk space and defragment database."""
        self.conn.execute("VACUUM")

    def optimize(self) -> None:
        """Run SQLite PRAGMA optimize to update query planner statistics."""
        self.conn.execute("PRAGMA optimize")

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager providing an atomic SQLite transaction block."""
        with self.conn:
            yield self.conn

    def init_schema(self) -> None:
        """Create all tables, indexes, and triggers; seed books catalog."""
        cur = self.conn.cursor()
        cur.executescript(SCHEMA_SQL)

        # Seed Protestant 66 books catalog if not already populated
        cur.execute("SELECT COUNT(*) FROM books")
        count = cur.fetchone()[0]
        if count < 66:
            for book in ALL_BOOKS:
                cur.execute(
                    """
                    INSERT OR IGNORE INTO books (id, name, osis, testament, canonical_order, total_chapters)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        book.number,
                        book.name,
                        book.osis,
                        book.testament,
                        book.number,
                        book.total_chapters,
                    ),
                )
        # Ensure pericopes schema evolution for existing databases
        cur.execute("PRAGMA table_info(pericopes)")
        p_cols = {row[1] for row in cur.fetchall()}
        if "genre" not in p_cols:
            cur.execute("ALTER TABLE pericopes ADD COLUMN genre TEXT")
        if "literary_structure" not in p_cols:
            cur.execute("ALTER TABLE pericopes ADD COLUMN literary_structure TEXT")
        if "central_proposition" not in p_cols:
            cur.execute("ALTER TABLE pericopes ADD COLUMN central_proposition TEXT")

        self.conn.commit()
        cur.close()

        # Clean-slate dynamic taxonomy migration (Task 3.5 / ADR-079)
        self.migrate_clean_slate_tags()

        # Universal tagging unification migration (Task 3.6 / ADR-080)
        self.migrate_starred_to_tag()

    # --- Translations ---

    def add_translation(
        self,
        translation_id: str,
        name: str,
        language: str = "en",
        is_public_domain: bool = True,
        is_encrypted: bool = False,
        license_notes: Optional[str] = None,
    ) -> TranslationRecord:
        """Register a new translation in the database."""
        t_id = translation_id.strip().upper()
        now = _utc_now_iso()
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO translations (id, name, language, is_public_domain, is_encrypted, license_notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    language=excluded.language,
                    is_public_domain=excluded.is_public_domain,
                    is_encrypted=excluded.is_encrypted,
                    license_notes=excluded.license_notes
                """,
                (
                    t_id,
                    name.strip(),
                    language.strip(),
                    1 if is_public_domain else 0,
                    1 if is_encrypted else 0,
                    license_notes,
                    now,
                ),
            )
        return self.get_translation(t_id)  # type: ignore[return-value]

    def get_translation(self, translation_id: str) -> Optional[TranslationRecord]:
        """Retrieve translation metadata by identifier (e.g. 'WEB')."""
        t_id = translation_id.strip().upper()
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM translations WHERE id = ?", (t_id,))
        row = cur.fetchone()
        cur.close()
        if not row:
            return None
        return TranslationRecord(
            id=row["id"],
            name=row["name"],
            language=row["language"],
            is_public_domain=bool(row["is_public_domain"]),
            is_encrypted=bool(row["is_encrypted"]),
            license_notes=row["license_notes"],
            created_at=row["created_at"],
        )

    def list_translations(self) -> List[TranslationRecord]:
        """List all registered translations in the database."""
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM translations ORDER BY id ASC")
        rows = cur.fetchall()
        cur.close()
        return [
            TranslationRecord(
                id=row["id"],
                name=row["name"],
                language=row["language"],
                is_public_domain=bool(row["is_public_domain"]),
                is_encrypted=bool(row["is_encrypted"]),
                license_notes=row["license_notes"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def get_available_translation_ids(self) -> List[str]:
        """Return list of translation IDs that currently have verses stored in the database."""
        cur = self.conn.cursor()
        cur.execute("SELECT DISTINCT translation_id FROM verses ORDER BY translation_id ASC")
        rows = cur.fetchall()
        cur.close()
        return [r[0] for r in rows]

    # --- Verses ---

    def insert_verse(self, verse: VerseRecord) -> int:
        """Insert a single verse row into the database."""
        t_id = verse.translation_id.strip().upper()
        cid = (
            verse.canonical_verse_id
            if verse.canonical_verse_id is not None
            else verse_canonical_id(verse.book_id, verse.chapter, verse.verse)
        )
        b = BOOKS.get(verse.book_id)
        sub = verse.subverse or ""
        osis = verse.osis_ref or (f"{b.osis}.{verse.chapter}.{verse.verse}{sub}" if b else "")

        with self.conn:
            cur = self.conn.execute(
                """
                INSERT OR REPLACE INTO verses (
                    translation_id, book_id, chapter, verse, subverse, text, osis_ref, canonical_verse_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    t_id,
                    verse.book_id,
                    verse.chapter,
                    verse.verse,
                    sub,
                    verse.text.strip(),
                    osis,
                    cid,
                ),
            )
            return cur.lastrowid

    def insert_verses(self, verses: Sequence[VerseRecord]) -> int:
        """Batch insert multiple verses inside an atomic transaction.

        Returns:
            Count of inserted verses.
        """
        if not verses:
            return 0

        rows = []
        for v in verses:
            t_id = v.translation_id.strip().upper()
            cid = (
                v.canonical_verse_id
                if v.canonical_verse_id is not None
                else verse_canonical_id(v.book_id, v.chapter, v.verse)
            )
            b = BOOKS.get(v.book_id)
            sub = v.subverse or ""
            osis = v.osis_ref or (f"{b.osis}.{v.chapter}.{v.verse}{sub}" if b else "")
            rows.append(
                (
                    t_id,
                    v.book_id,
                    v.chapter,
                    v.verse,
                    sub,
                    v.text.strip(),
                    osis,
                    cid,
                )
            )

        with self.conn:
            self.conn.executemany(
                """
                INSERT OR REPLACE INTO verses (
                    translation_id, book_id, chapter, verse, subverse, text, osis_ref, canonical_verse_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        return len(rows)

    def get_verse(
        self,
        book: Union[Book, str, int],
        chapter: int,
        verse: int,
        subverse: str = "",
        translation_id: str = "WEB",
    ) -> Optional[VerseRecord]:
        """Fetch a single verse by book, chapter, and verse number."""
        b = get_book(book)
        if not b:
            return None
        t_id = translation_id.strip().upper()

        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT v.*, b.name as book_name
            FROM verses v
            JOIN books b ON b.id = v.book_id
            WHERE v.translation_id = ?
              AND v.book_id = ?
              AND v.chapter = ?
              AND v.verse = ?
              AND v.subverse = ?
            """,
            (t_id, b.number, chapter, verse, subverse),
        )
        row = cur.fetchone()
        cur.close()
        if not row:
            return None
        return self._row_to_verse(row)

    def get_verses_by_reference(
        self,
        reference: Union[Reference, str],
        translation_id: str = "WEB",
    ) -> List[VerseRecord]:
        """Retrieve all verses matching a Reference or citation string in canonical order."""
        if isinstance(reference, str):
            ref = parse_reference(reference)
        else:
            ref = reference

        t_id = translation_id.strip().upper()
        if t_id == "ESV":
            cached = self.get_esv_cached_verses(ref)
            if cached:
                return cached

        start_id = ref.canonical_start_id
        end_id = ref.canonical_end_id

        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT v.*, b.name as book_name
            FROM verses v
            JOIN books b ON b.id = v.book_id
            WHERE v.translation_id = ?
              AND v.canonical_verse_id >= ?
              AND v.canonical_verse_id <= ?
            ORDER BY v.canonical_verse_id ASC, v.subverse ASC
            """,
            (t_id, start_id, end_id),
        )
        rows = cur.fetchall()
        cur.close()
        return [self._row_to_verse(r) for r in rows]

    def get_verses_with_fallback(
        self,
        reference: Union[Reference, str],
        translation_id: str = "ESV",
        fallback_id: Optional[str] = "WEB",
        allow_network: bool = True,
    ) -> Tuple[List[VerseRecord], str, bool]:
        """Retrieve verses for a reference with automatic fallback resolution.

        Supports ESV 500-verse ephemeral LRU cache, live ESV API fetching, and graceful fallback to WEB.

        Args:
            reference: Reference object or canonical scripture citation string.
            translation_id: Desired translation identifier (default: 'ESV').
            fallback_id: Optional fallback translation ID (default: 'WEB') to use if the requested
                translation has no matching verses in the database or cache.
            allow_network: Whether to attempt live ESV API fetching if ESV verses are not cached.

        Returns:
            Tuple of (verses_list, effective_translation_id, is_fallback_used).
        """
        if isinstance(reference, str):
            ref = parse_reference(reference)
        else:
            ref = reference

        req_id = translation_id.strip().upper()

        if req_id == "ESV":
            # 1. Check ephemeral 500-verse LRU cache
            cached = self.get_esv_cached_verses(ref)
            if cached:
                # If specific verse range, ensure complete coverage
                if (
                    ref.start_verse is not None
                    and ref.end_verse is not None
                    and ref.start_chapter == ref.end_chapter
                ):
                    expected_count = ref.end_verse - ref.start_verse + 1
                    if len(cached) >= expected_count:
                        return cached, "ESV", False
                else:
                    return cached, "ESV", False

            # 2. Attempt live ESV API fetch if allowed
            if allow_network:
                has_custom_client = getattr(self, "_esv_client", None) is not None
                if has_custom_client:
                    is_offline = False
                else:
                    is_offline = (
                        os.environ.get("BIBLE_OFFLINE") == "1"
                        or os.environ.get("BIBLE_TEST_MODE") == "1"
                        or "unittest" in sys.modules
                    )
                if not is_offline:
                    client = self.get_esv_client()
                    if client.is_available():

                        try:
                            fetched = client.fetch_verses(ref)
                            if fetched:
                                self.save_esv_cached_verses(fetched)
                                return fetched, "ESV", False
                        except Exception:
                            pass


            # 3. If ESV unavailable, cascade to fallback
            if fallback_id:
                fb_id = fallback_id.strip().upper()
                if fb_id != "ESV":
                    fb_verses = self.get_verses_by_reference(ref, translation_id=fb_id)
                    if fb_verses:
                        return fb_verses, fb_id, True

            return [], "ESV", False

        # Non-ESV translations: standard database lookup
        verses = self.get_verses_by_reference(ref, translation_id=req_id)
        if verses:
            return verses, req_id, False

        # Attempt fallback if configured and different from requested translation
        if fallback_id:
            fb_id = fallback_id.strip().upper()
            if fb_id != req_id:
                fb_verses = self.get_verses_by_reference(reference, translation_id=fb_id)
                if fb_verses:
                    return fb_verses, fb_id, True

        return [], req_id, False

    def compare_verses(
        self,
        reference: Union[Reference, str],
        translation_ids: Sequence[str],
        fallback_id: Optional[str] = "WEB",
    ) -> Dict[str, Tuple[List[VerseRecord], str, bool]]:
        """Retrieve verses across multiple translations for parallel comparison.

        Args:
            reference: Reference object or citation string.
            translation_ids: Sequence of translation IDs to query.
            fallback_id: Optional fallback translation ID if a requested version is absent.

        Returns:
            Dictionary mapping requested translation ID to (verses_list, effective_id, is_fallback).
        """
        results: Dict[str, Tuple[List[VerseRecord], str, bool]] = {}
        for t_id in translation_ids:
            clean_id = t_id.strip().upper()
            verses, eff_id, is_fallback = self.get_verses_with_fallback(
                reference, translation_id=clean_id, fallback_id=fallback_id
            )
            results[clean_id] = (verses, eff_id, is_fallback)
        return results

    def count_verses(self, translation_id: Optional[str] = None) -> int:
        """Return total count of verses stored, optionally filtered by translation."""
        cur = self.conn.cursor()
        if translation_id:
            cur.execute(
                "SELECT COUNT(*) FROM verses WHERE translation_id = ?",
                (translation_id.strip().upper(),),
            )
        else:
            cur.execute("SELECT COUNT(*) FROM verses")
        count = cur.fetchone()[0]
        cur.close()
        return count

    def _row_to_verse(self, row: sqlite3.Row) -> VerseRecord:
        """Convert a SQLite row to a VerseRecord."""
        return VerseRecord(
            id=row["id"],
            translation_id=row["translation_id"],
            book_id=row["book_id"],
            book_name=row["book_name"],
            chapter=row["chapter"],
            verse=row["verse"],
            subverse=row["subverse"],
            text=row["text"],
            osis_ref=row["osis_ref"],
            canonical_verse_id=row["canonical_verse_id"],
        )

    # --- ESV API & Ephemeral 500-Verse LRU Cache (ADR-041) ---

    def get_esv_client(self) -> Any:
        """Return or lazily initialize the zero-dependency ESV API Client."""
        if getattr(self, "_esv_client", None) is None:
            from core.esv import ESVClient
            self._esv_client = ESVClient()
        return self._esv_client

    def set_esv_client(self, client: Any) -> None:
        """Set custom ESVClient instance (useful for hermetic test mocking)."""
        self._esv_client = client

    def get_esv_cached_verses(
        self,
        reference: Union[Reference, str],
    ) -> List[VerseRecord]:
        """Retrieve cached ESV verses within reference bounds and touch last_accessed_at."""
        if isinstance(reference, str):
            ref = parse_reference(reference)
        else:
            ref = reference

        start_id = ref.canonical_start_id
        end_id = ref.canonical_end_id
        now = _utc_now_iso()

        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT c.*, b.name as book_name
            FROM esv_cache c
            JOIN books b ON b.id = c.book_id
            WHERE c.canonical_verse_id >= ?
              AND c.canonical_verse_id <= ?
            ORDER BY c.canonical_verse_id ASC, c.subverse ASC
            """,
            (start_id, end_id),
        )
        rows = cur.fetchall()
        if not rows:
            cur.close()
            return []

        # Touch last_accessed_at for LRU freshness
        with self.conn:
            self.conn.execute(
                """
                UPDATE esv_cache
                SET last_accessed_at = ?
                WHERE canonical_verse_id >= ? AND canonical_verse_id <= ?
                """,
                (now, start_id, end_id),
            )
        cur.close()

        return [
            VerseRecord(
                id=None,
                translation_id="ESV",
                book_id=row["book_id"],
                book_name=row["book_name"],
                chapter=row["chapter"],
                verse=row["verse"],
                subverse=row["subverse"],
                text=row["text"],
                osis_ref=row["osis_ref"],
                canonical_verse_id=row["canonical_verse_id"],
            )
            for row in rows
        ]

    def save_esv_cached_verses(
        self,
        verses: Sequence[VerseRecord],
        max_verses: int = 500,
    ) -> int:
        """Store ESV verses into ephemeral cache and enforce the strict 500-verse LRU limit."""
        if not verses:
            return 0

        now = _utc_now_iso()
        rows = []
        for v in verses:
            cid = (
                v.canonical_verse_id
                if v.canonical_verse_id is not None
                else verse_canonical_id(v.book_id, v.chapter, v.verse)
            )
            b = BOOKS.get(v.book_id)
            sub = v.subverse or ""
            osis = v.osis_ref or (f"{b.osis}.{v.chapter}.{v.verse}{sub}" if b else "")
            rows.append((
                cid,
                v.book_id,
                v.chapter,
                v.verse,
                sub,
                v.text.strip(),
                osis,
                now,
            ))

        with self.conn:
            self.conn.executemany(
                """
                INSERT INTO esv_cache (
                    canonical_verse_id, book_id, chapter, verse, subverse, text, osis_ref, last_accessed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(canonical_verse_id) DO UPDATE SET
                    text=excluded.text,
                    last_accessed_at=excluded.last_accessed_at
                """,
                rows,
            )

            # Enforce 500-verse LRU eviction per Crossway compliance
            cur = self.conn.execute("SELECT COUNT(*) FROM esv_cache")
            total_count = cur.fetchone()[0]
            if total_count > max_verses:
                overflow = total_count - max_verses
                self.conn.execute(
                    """
                    DELETE FROM esv_cache
                    WHERE canonical_verse_id IN (
                        SELECT canonical_verse_id FROM esv_cache
                        ORDER BY last_accessed_at ASC, canonical_verse_id ASC
                        LIMIT ?
                    )
                    """,
                    (overflow,),
                )

        return len(rows)

    def count_esv_cached_verses(self) -> int:
        """Return count of verses currently in the ephemeral ESV cache."""
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM esv_cache")
        count = cur.fetchone()[0]
        cur.close()
        return count

    def clear_esv_cache(self) -> int:
        """Clear all entries in the ephemeral ESV cache."""
        with self.conn:
            cur = self.conn.execute("DELETE FROM esv_cache")
            return cur.rowcount

    def get_esv_cache_stats(self) -> Dict[str, Any]:
        """Return diagnostic statistics about the ephemeral ESV cache."""
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT
                COUNT(*) as total_verses,
                MIN(last_accessed_at) as oldest_accessed,
                MAX(last_accessed_at) as newest_accessed
            FROM esv_cache
            """
        )
        row = cur.fetchone()
        cur.close()
        total = row["total_verses"] if row else 0
        return {
            "cached_verses": total,
            "max_capacity": 500,
            "oldest_accessed_at": row["oldest_accessed"] if row else None,
            "newest_accessed_at": row["newest_accessed"] if row else None,
            "compliant": total <= 500,
        }

    # --- Full-Text Search (FTS5) ---

    def search_text(
        self,
        query: str,
        translation_id: Optional[Union[str, Sequence[str]]] = None,
        book: Optional[Union[Book, str, int]] = None,
        testament: Optional[str] = None,
        exact: bool = False,
        sort_by: str = "relevance",
        limit: int = 50,
        offset: int = 0,
    ) -> List[SearchResult]:
        """Perform full-text search across scripture text using SQLite FTS5.

        Args:
            query: User search text, phrase, or Boolean query.
            translation_id: Optional translation filter (e.g. 'WEB' or ['WEB', 'KJV']).
            book: Optional book filter (Book object, name, abbreviation, or number).
            testament: Optional testament filter ('OT' or 'NT').
            exact: If True, treat query as an exact contiguous phrase.
            sort_by: Sort order: 'relevance' (BM25 rank) or 'canonical' (Genesis-Revelation).
            limit: Maximum result rows.
            offset: Result offset for pagination.

        Returns:
            List of SearchResult matching query ordered by relevance or canonical order.
        """
        raw_query = query.strip()
        if exact and not (raw_query.startswith('"') and raw_query.endswith('"')):
            raw_query = f'"{raw_query}"'

        sanitized = sanitize_fts_query(raw_query)
        if not sanitized:
            return []

        conditions = ["verses_fts MATCH ?"]
        params: List[Any] = [sanitized]

        if translation_id:
            if isinstance(translation_id, str):
                t_ids = [t.strip().upper() for t in translation_id.split(",") if t.strip()]
            else:
                t_ids = [t.strip().upper() for t in translation_id if t.strip()]
            if t_ids and "ALL" not in t_ids:
                if len(t_ids) == 1:
                    conditions.append("f.translation_id = ?")
                    params.append(t_ids[0])
                else:
                    placeholders = ", ".join(["?"] * len(t_ids))
                    conditions.append(f"f.translation_id IN ({placeholders})")
                    params.extend(t_ids)

        if testament:
            t = testament.strip().upper()
            if t in ("OT", "OLD", "OLD TESTAMENT", "OLD_TESTAMENT"):
                conditions.append("v.book_id <= 39")
            elif t in ("NT", "NEW", "NEW TESTAMENT", "NEW_TESTAMENT"):
                conditions.append("v.book_id >= 40")
            else:
                raise ValueError(f"Unknown testament filter '{testament}'. Expected 'OT' or 'NT'.")

        if book:
            b = get_book(book)
            if b:
                conditions.append("v.book_id = ?")
                params.append(b.number)
            else:
                raise ValueError(f"Unknown book '{book}'")

        where_clause = " AND ".join(conditions)
        if sort_by in ("canonical", "order", "book"):
            order_clause = "v.canonical_verse_id ASC"
        else:
            order_clause = "f.rank ASC"

        sql = f"""
            SELECT
                f.verse_id,
                f.translation_id,
                f.book_name,
                f.osis_ref,
                v.chapter,
                v.verse,
                v.text,
                snippet(verses_fts, 4, '<b>', '</b>', '...', 10) AS snippet,
                f.rank
            FROM verses_fts f
            JOIN verses v ON v.id = f.verse_id
            WHERE {where_clause}
            ORDER BY {order_clause}
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        cur = self.conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()

        return [
            SearchResult(
                verse_id=r["verse_id"],
                translation_id=r["translation_id"],
                book_name=r["book_name"],
                osis_ref=r["osis_ref"],
                chapter=r["chapter"],
                verse=r["verse"],
                text=r["text"],
                snippet=r["snippet"],
                rank=r["rank"],
            )
            for r in rows
        ]

    def count_search_matches(
        self,
        query: str,
        translation_id: Optional[Union[str, Sequence[str]]] = None,
        book: Optional[Union[Book, str, int]] = None,
        testament: Optional[str] = None,
        exact: bool = False,
    ) -> int:
        """Count total verses matching FTS5 query with optional filters.

        Args:
            query: User search text, phrase, or Boolean query.
            translation_id: Optional translation filter (e.g. 'WEB' or ['WEB', 'KJV']).
            book: Optional book filter.
            testament: Optional testament filter ('OT' or 'NT').
            exact: If True, treat query as an exact contiguous phrase.

        Returns:
            Total count of matching verses.
        """
        raw_query = query.strip()
        if exact and not (raw_query.startswith('"') and raw_query.endswith('"')):
            raw_query = f'"{raw_query}"'

        sanitized = sanitize_fts_query(raw_query)
        if not sanitized:
            return 0

        conditions = ["verses_fts MATCH ?"]
        params: List[Any] = [sanitized]

        if translation_id:
            if isinstance(translation_id, str):
                t_ids = [t.strip().upper() for t in translation_id.split(",") if t.strip()]
            else:
                t_ids = [t.strip().upper() for t in translation_id if t.strip()]
            if t_ids and "ALL" not in t_ids:
                if len(t_ids) == 1:
                    conditions.append("f.translation_id = ?")
                    params.append(t_ids[0])
                else:
                    placeholders = ", ".join(["?"] * len(t_ids))
                    conditions.append(f"f.translation_id IN ({placeholders})")
                    params.extend(t_ids)

        if testament:
            t = testament.strip().upper()
            if t in ("OT", "OLD", "OLD TESTAMENT", "OLD_TESTAMENT"):
                conditions.append("v.book_id <= 39")
            elif t in ("NT", "NEW", "NEW TESTAMENT", "NEW_TESTAMENT"):
                conditions.append("v.book_id >= 40")
            else:
                raise ValueError(f"Unknown testament filter '{testament}'. Expected 'OT' or 'NT'.")

        if book:
            b = get_book(book)
            if b:
                conditions.append("v.book_id = ?")
                params.append(b.number)
            else:
                raise ValueError(f"Unknown book '{book}'")

        where_clause = " AND ".join(conditions)
        sql = f"""
            SELECT COUNT(*) AS total
            FROM verses_fts f
            JOIN verses v ON v.id = f.verse_id
            WHERE {where_clause}
        """
        cur = self.conn.cursor()
        cur.execute(sql, params)
        row = cur.fetchone()
        cur.close()
        return int(row["total"]) if row else 0


    # --- Spans ---

    def add_span(
        self,
        reference: Union[Reference, str],
        label: Optional[str] = None,
    ) -> SpanRecord:
        """Register or retrieve an arbitrary passage span in the spans table."""
        ref = parse_reference(reference) if isinstance(reference, str) else reference
        now = _utc_now_iso()
        start_id = ref.canonical_start_id
        end_id = ref.canonical_end_id
        human = ref.format()
        osis = ref.to_osis()

        with self.conn:
            cur = self.conn.execute(
                """
                INSERT INTO spans (human_ref, osis_ref, book_id, start_canonical_id, end_canonical_id, label, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (human, osis, ref.book.number, start_id, end_id, label, now),
            )
            span_id = cur.lastrowid

        return SpanRecord(
            id=span_id,
            human_ref=human,
            osis_ref=osis,
            book_id=ref.book.number,
            start_canonical_id=start_id,
            end_canonical_id=end_id,
            label=label,
            created_at=now,
        )

    def get_span(self, span_id: int) -> Optional[SpanRecord]:
        """Fetch a passage span record by ID."""
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM spans WHERE id = ?", (span_id,))
        row = cur.fetchone()
        cur.close()
        if not row:
            return None
        return SpanRecord(
            id=row["id"],
            human_ref=row["human_ref"],
            osis_ref=row["osis_ref"],
            book_id=row["book_id"],
            start_canonical_id=row["start_canonical_id"],
            end_canonical_id=row["end_canonical_id"],
            label=row["label"],
            created_at=row["created_at"],
        )

    def find_overlapping_spans(self, reference: Union[Reference, str]) -> List[SpanRecord]:
        """Find all registered spans that overlap with the specified reference."""
        ref = parse_reference(reference) if isinstance(reference, str) else reference
        start_id = ref.canonical_start_id
        end_id = ref.canonical_end_id

        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT * FROM spans
            WHERE start_canonical_id <= ? AND end_canonical_id >= ?
            ORDER BY start_canonical_id ASC
            """,
            (end_id, start_id),
        )
        rows = cur.fetchall()
        cur.close()
        return [
            SpanRecord(
                id=r["id"],
                human_ref=r["human_ref"],
                osis_ref=r["osis_ref"],
                book_id=r["book_id"],
                start_canonical_id=r["start_canonical_id"],
                end_canonical_id=r["end_canonical_id"],
                label=r["label"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    # --- Tags & Semantic Knowledge ---

    def add_tag(
        self,
        name: str,
        category: str = "thematic",
        description: Optional[str] = None,
    ) -> TagRecord:
        """Register a new semantic tag definition in canonical snake_case."""
        clean_name = normalize_tag_name(name)
        now = _utc_now_iso()
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO tags (name, category, description, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    category=excluded.category,
                    description=COALESCE(excluded.description, tags.description)
                """,
                (clean_name, category.strip().lower(), description, now),
            )
        return self.get_tag(clean_name)  # type: ignore[return-value]

    def get_tag(self, name: str) -> Optional[TagRecord]:
        """Retrieve tag record by name (case-insensitive, snake_case normalized)."""
        clean_name = normalize_tag_name(name)
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM tags WHERE name = ? COLLATE NOCASE", (clean_name,))
        row = cur.fetchone()
        cur.close()
        if not row:
            return None
        return TagRecord(
            id=row["id"],
            name=row["name"],
            category=row["category"],
            description=row["description"],
            created_at=row["created_at"],
        )

    def get_or_create_tag(
        self,
        name: str,
        category: str = "thematic",
        description: Optional[str] = None,
    ) -> TagRecord:
        """Retrieve tag by name or create it if absent."""
        clean_name = normalize_tag_name(name)
        existing = self.get_tag(clean_name)
        if existing:
            return existing
        return self.add_tag(clean_name, category, description)

    def list_tags(self, category: Optional[str] = None) -> List[TagRecord]:
        """List all defined tags, optionally filtered by category."""
        cur = self.conn.cursor()
        if category:
            cur.execute(
                "SELECT * FROM tags WHERE category = ? ORDER BY name ASC",
                (category.strip().lower(),),
            )
        else:
            cur.execute("SELECT * FROM tags ORDER BY category ASC, name ASC")
        rows = cur.fetchall()
        cur.close()
        return [
            TagRecord(
                id=r["id"],
                name=r["name"],
                category=r["category"],
                description=r["description"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def tag_reference(
        self,
        reference: Union[Reference, str],
        tag_name: str,
        category: str = "thematic",
        confidence: float = 1.0,
        source: str = "human",
        starred: bool = False,
        notes: Optional[str] = None,
        span_id: Optional[int] = None,
    ) -> VerseTagRecord:
        """Attach a semantic tag to an individual verse, span, or chapter."""
        ref = parse_reference(reference) if isinstance(reference, str) else reference
        tag = self.get_or_create_tag(tag_name, category=category)
        assert tag.id is not None

        start_id = ref.canonical_start_id
        end_id = ref.canonical_end_id
        human = ref.format()
        now = _utc_now_iso()

        # Link to spans table if this reference represents a multi-verse span and span_id was not provided
        resolved_span_id = span_id
        if resolved_span_id is None and (ref.is_verse_range or ref.is_chapter_range or not ref.is_single_verse):
            cur = self.conn.cursor()
            cur.execute(
                "SELECT id FROM spans WHERE start_canonical_id = ? AND end_canonical_id = ? LIMIT 1",
                (start_id, end_id),
            )
            span_row = cur.fetchone()
            cur.close()
            if span_row:
                resolved_span_id = span_row["id"]
            else:
                span = self.add_span(ref)
                resolved_span_id = span.id

        with self.conn:
            # Check for existing association to ensure idempotency
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT id FROM verse_tags
                WHERE tag_id = ? AND start_canonical_id = ? AND end_canonical_id = ?
                LIMIT 1
                """,
                (tag.id, start_id, end_id),
            )
            existing = cur.fetchone()
            if existing:
                vt_id = existing["id"]
                self.conn.execute(
                    """
                    UPDATE verse_tags
                    SET human_ref = ?, confidence = ?, source = ?, starred = ?, notes = ?, span_id = ?
                    WHERE id = ?
                    """,
                    (human, confidence, source, 1 if starred else 0, notes, resolved_span_id, vt_id),
                )
            else:
                cur = self.conn.execute(
                    """
                    INSERT INTO verse_tags (
                        tag_id, span_id, start_canonical_id, end_canonical_id, human_ref,
                        confidence, source, starred, notes, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        tag.id,
                        resolved_span_id,
                        start_id,
                        end_id,
                        human,
                        confidence,
                        source,
                        1 if starred else 0,
                        notes,
                        now,
                    ),
                )
                vt_id = cur.lastrowid

            # If marked starred and this is not already the 'starred' tag itself,
            # ensure a first-class 'starred' tag association exists (Task 3.6 / ADR-080).
            if starred and tag.name != "starred":
                cur_star = self.conn.cursor()
                cur_star.execute(
                    "SELECT id FROM tags WHERE name = 'starred' LIMIT 1"
                )
                starred_tag_row = cur_star.fetchone()
                if not starred_tag_row:
                    cur_star.execute(
                        """
                        INSERT INTO tags (name, category, description, created_at)
                        VALUES ('starred', 'curation', 'Priority starred scripture citations and key verses', ?)
                        """,
                        (now,),
                    )
                    starred_tag_id = cur_star.lastrowid
                else:
                    starred_tag_id = starred_tag_row["id"]

                cur_star.execute(
                    """
                    SELECT id FROM verse_tags
                    WHERE tag_id = ? AND start_canonical_id = ? AND end_canonical_id = ?
                    LIMIT 1
                    """,
                    (starred_tag_id, start_id, end_id),
                )
                if not cur_star.fetchone():
                    cur_star.execute(
                        """
                        INSERT INTO verse_tags (
                            tag_id, span_id, start_canonical_id, end_canonical_id, human_ref,
                            confidence, source, starred, notes, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                        """,
                        (starred_tag_id, resolved_span_id, start_id, end_id, human, confidence, source, notes, now),
                    )
                cur_star.close()

        return VerseTagRecord(
            id=vt_id,
            tag_id=tag.id,
            tag_name=tag.name,
            start_canonical_id=start_id,
            end_canonical_id=end_id,
            human_ref=human,
            confidence=confidence,
            source=source,
            starred=starred,
            notes=notes,
            span_id=resolved_span_id,
            created_at=now,
            category=tag.category,
        )

    def get_tags_for_reference(
        self,
        reference: Union[Reference, str],
        exact_only: bool = False,
    ) -> List[VerseTagRecord]:
        """Fetch all tags whose range overlaps (or matches exactly) with the given reference."""
        ref = parse_reference(reference) if isinstance(reference, str) else reference
        start_id = ref.canonical_start_id
        end_id = ref.canonical_end_id

        cur = self.conn.cursor()
        if exact_only:
            cur.execute(
                """
                SELECT vt.*, t.name as tag_name, t.category as category
                FROM verse_tags vt
                JOIN tags t ON t.id = vt.tag_id
                WHERE vt.start_canonical_id = ? AND vt.end_canonical_id = ?
                ORDER BY vt.starred DESC, vt.confidence DESC, vt.id ASC
                """,
                (start_id, end_id),
            )
        else:
            cur.execute(
                """
                SELECT vt.*, t.name as tag_name, t.category as category
                FROM verse_tags vt
                JOIN tags t ON t.id = vt.tag_id
                WHERE vt.start_canonical_id <= ? AND vt.end_canonical_id >= ?
                ORDER BY vt.starred DESC, vt.confidence DESC, vt.id ASC
                """,
                (end_id, start_id),
            )
        rows = cur.fetchall()
        cur.close()
        return [
            VerseTagRecord(
                id=r["id"],
                tag_id=r["tag_id"],
                tag_name=r["tag_name"],
                start_canonical_id=r["start_canonical_id"],
                end_canonical_id=r["end_canonical_id"],
                human_ref=r["human_ref"],
                confidence=r["confidence"],
                source=r["source"],
                starred=bool(r["starred"]),
                notes=r["notes"],
                span_id=r["span_id"],
                created_at=r["created_at"],
                category=r["category"] if "category" in r.keys() else None,
            )
            for r in rows
        ]

    def get_references_for_tag(
        self,
        tag_name: str,
        starred_only: bool = False,
    ) -> List[VerseTagRecord]:
        """Retrieve all passage citations tagged with the given tag name."""
        tag = self.get_tag(tag_name)
        if not tag:
            return []

        cur = self.conn.cursor()
        if starred_only:
            cur.execute(
                """
                SELECT vt.*, t.name as tag_name, t.category as category
                FROM verse_tags vt
                JOIN tags t ON t.id = vt.tag_id
                WHERE vt.tag_id = ? AND vt.starred = 1
                ORDER BY vt.start_canonical_id ASC
                """,
                (tag.id,),
            )
        else:
            cur.execute(
                """
                SELECT vt.*, t.name as tag_name, t.category as category
                FROM verse_tags vt
                JOIN tags t ON t.id = vt.tag_id
                WHERE vt.tag_id = ?
                ORDER BY vt.start_canonical_id ASC
                """,
                (tag.id,),
            )
        rows = cur.fetchall()
        cur.close()
        return [
            VerseTagRecord(
                id=r["id"],
                tag_id=r["tag_id"],
                tag_name=r["tag_name"],
                start_canonical_id=r["start_canonical_id"],
                end_canonical_id=r["end_canonical_id"],
                human_ref=r["human_ref"],
                confidence=r["confidence"],
                source=r["source"],
                starred=bool(r["starred"]),
                notes=r["notes"],
                span_id=r["span_id"],
                created_at=r["created_at"],
                category=r["category"] if "category" in r.keys() else tag.category,
            )
            for r in rows
        ]

    def untag_reference(
        self,
        reference: Union[Reference, str],
        tag_name: str,
    ) -> int:
        """Remove tag association(s) for a specific reference and tag name.

        Returns the number of deleted rows.
        """
        tag = self.get_tag(tag_name)
        if not tag or tag.id is None:
            return 0
        ref = parse_reference(reference) if isinstance(reference, str) else reference
        start_id = ref.canonical_start_id
        end_id = ref.canonical_end_id
        with self.conn:
            cur = self.conn.execute(
                """
                DELETE FROM verse_tags
                WHERE tag_id = ? AND start_canonical_id = ? AND end_canonical_id = ?
                """,
                (tag.id, start_id, end_id),
            )
            deleted = cur.rowcount
            # If removing the 'starred' tag, also reset legacy starred = 0 on any overlapping rows
            if tag.name == "starred":
                self.conn.execute(
                    """
                    UPDATE verse_tags
                    SET starred = 0
                    WHERE start_canonical_id = ? AND end_canonical_id = ?
                    """,
                    (start_id, end_id),
                )
            return deleted

    def delete_tag(self, name: str) -> bool:
        """Delete a tag definition and all its associations from the database.

        Returns True if the tag was found and deleted, False otherwise.
        """
        tag = self.get_tag(name)
        if not tag or tag.id is None:
            return False
        with self.conn:
            self.conn.execute("DELETE FROM tags WHERE id = ?", (tag.id,))
            return True

    def get_tag_stats(self, tag_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Compute aggregated statistics for tags.

        Returns list of dicts with id, name, category, description, passage_count,
        starred_count, distinct_books, min_canonical_id, max_canonical_id.
        """
        cur = self.conn.cursor()
        query = """
            SELECT
                t.id,
                t.name,
                t.category,
                t.description,
                t.created_at,
                COUNT(vt.id) AS passage_count,
                SUM(CASE WHEN vt.starred = 1 THEN 1 ELSE 0 END) AS starred_count,
                COUNT(DISTINCT (vt.start_canonical_id / 1000000)) AS distinct_books,
                MIN(vt.start_canonical_id) AS min_canonical_id,
                MAX(vt.end_canonical_id) AS max_canonical_id
            FROM tags t
            LEFT JOIN verse_tags vt ON vt.tag_id = t.id
        """
        params: List[Any] = []
        if tag_name:
            query += " WHERE t.name = ? COLLATE NOCASE"
            params.append(normalize_tag_name(tag_name))
        query += " GROUP BY t.id ORDER BY passage_count DESC, t.name ASC"
        cur.execute(query, params)
        rows = cur.fetchall()
        cur.close()
        return [
            {
                "id": r["id"],
                "name": r["name"],
                "category": r["category"],
                "description": r["description"],
                "created_at": r["created_at"],
                "passage_count": r["passage_count"],
                "starred_count": r["starred_count"] or 0,
                "distinct_books": r["distinct_books"] or 0,
                "min_canonical_id": r["min_canonical_id"],
                "max_canonical_id": r["max_canonical_id"],
            }
            for r in rows
        ]

    def prune_unlinked_tags(self, preserve_tags: Sequence[str] = ("favorites", "starred")) -> int:
        """Prune unused tags that have zero verse associations in verse_tags.

        Preserves 'favorites' and 'starred' (and any other specified tags) even if empty.
        Returns the count of deleted tags.
        """
        preserve_normalized = {normalize_tag_name(t) for t in preserve_tags}
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT id, name FROM tags
            WHERE id NOT IN (SELECT DISTINCT tag_id FROM verse_tags)
            """
        )
        rows = cur.fetchall()
        to_delete_ids = [r["id"] for r in rows if normalize_tag_name(r["name"]) not in preserve_normalized]
        cur.close()

        if not to_delete_ids:
            return 0

        with self.conn:
            placeholders = ",".join("?" * len(to_delete_ids))
            self.conn.execute(f"DELETE FROM tags WHERE id IN ({placeholders})", to_delete_ids)
        return len(to_delete_ids)

    def migrate_clean_slate_tags(self) -> int:
        """Migrate existing tags to clean-slate dynamic snake_case architecture (Task 3.5 / ADR-079).

        - Prunes legacy unlinked pre-assumed tags.
        - Normalizes all remaining tag names to canonical snake_case.
        - Merges any duplicate tags resulting from case/space normalization.
        """
        legacy_unlinked_names = {
            "creation", "fall", "covenant", "exodus", "temple", "kingship", "exile",
            "restoration", "redemption", "new creation", "new_creation", "trinity",
            "christology", "pneumatology", "holy spirit", "holy_spirit", "justification",
            "sanctification", "sovereign grace", "sovereign_grace", "resurrection",
            "atonement", "prayer", "wisdom", "suffering", "joy", "faith", "love",
        }
        with self.conn:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT id, name FROM tags
                WHERE id NOT IN (SELECT DISTINCT tag_id FROM verse_tags)
                """
            )
            unlinked = cur.fetchall()
            pruned_count = 0
            for row in unlinked:
                clean_n = row["name"].strip().lower()
                if clean_n in legacy_unlinked_names and clean_n != "favorites":
                    cur.execute("DELETE FROM tags WHERE id = ?", (row["id"],))
                    pruned_count += 1

            # Normalize remaining tag names
            cur.execute("SELECT id, name FROM tags")
            all_tags = cur.fetchall()
            for row in all_tags:
                t_id = row["id"]
                orig_name = row["name"]
                try:
                    norm_name = normalize_tag_name(orig_name)
                except Exception:
                    continue
                if norm_name != orig_name:
                    cur.execute("SELECT id FROM tags WHERE name = ? AND id != ?", (norm_name, t_id))
                    dup = cur.fetchone()
                    if dup:
                        dup_id = dup["id"]
                        cur.execute("UPDATE OR IGNORE verse_tags SET tag_id = ? WHERE tag_id = ?", (dup_id, t_id))
                        cur.execute("DELETE FROM verse_tags WHERE tag_id = ?", (t_id,))
                        cur.execute("DELETE FROM tags WHERE id = ?", (t_id,))
                    else:
                        cur.execute("UPDATE tags SET name = ? WHERE id = ?", (norm_name, t_id))
            cur.close()
            return pruned_count

    def migrate_starred_to_tag(self) -> int:
        """Migrate legacy starred=1 column flags to first-class #starred tag (Task 3.6 / ADR-080).

        - Finds all verse_tags rows where starred = 1.
        - If any exist, ensures the 'starred' tag exists in category 'curation'.
        - Creates a verse_tags association with tag 'starred' for each, idempotently.
        - Returns the count of migrated starred associations.
        """
        now = _utc_now_iso()
        with self.conn:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT span_id, start_canonical_id, end_canonical_id, human_ref, confidence, source, notes
                FROM verse_tags
                WHERE starred = 1
                """
            )
            rows = cur.fetchall()
            if not rows:
                cur.close()
                return 0

            tag = self.get_or_create_tag(
                name="starred",
                category="curation",
                description="Priority starred scripture citations and key verses",
            )
            assert tag.id is not None
            starred_tag_id = tag.id

            migrated_count = 0
            for r in rows:
                span_id = r["span_id"]
                s_cid = r["start_canonical_id"]
                e_cid = r["end_canonical_id"]
                human_ref = r["human_ref"]
                conf = r["confidence"]
                src = r["source"]
                notes = r["notes"]

                cur.execute(
                    """
                    SELECT id FROM verse_tags
                    WHERE tag_id = ? AND start_canonical_id = ? AND end_canonical_id = ?
                    LIMIT 1
                    """,
                    (starred_tag_id, s_cid, e_cid),
                )
                if not cur.fetchone():
                    cur.execute(
                        """
                        INSERT INTO verse_tags (
                            tag_id, span_id, start_canonical_id, end_canonical_id, human_ref,
                            confidence, source, starred, notes, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                        """,
                        (starred_tag_id, span_id, s_cid, e_cid, human_ref, conf, src, notes, now),
                    )
                    migrated_count += 1
            cur.close()
            return migrated_count

    # --- Cross References ---

    def add_cross_reference(
        self,
        source: Union[Reference, str],
        target: Union[Reference, str],
        relationship_type: str = "thematic",
        weight: float = 1.0,
        notes: Optional[str] = None,
    ) -> CrossReferenceRecord:
        """Record a cross-reference relationship edge between two passages."""
        s_ref = parse_reference(source) if isinstance(source, str) else source
        t_ref = parse_reference(target) if isinstance(target, str) else target
        now = _utc_now_iso()

        s_start = s_ref.canonical_start_id
        s_end = s_ref.canonical_end_id
        s_human = s_ref.format()

        t_start = t_ref.canonical_start_id
        t_end = t_ref.canonical_end_id
        t_human = t_ref.format()

        with self.conn:
            cur = self.conn.execute(
                """
                INSERT INTO cross_references (
                    source_start_id, source_end_id, source_human_ref,
                    target_start_id, target_end_id, target_human_ref,
                    relationship_type, weight, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    s_start,
                    s_end,
                    s_human,
                    t_start,
                    t_end,
                    t_human,
                    relationship_type.strip().lower(),
                    weight,
                    notes,
                    now,
                ),
            )
            xr_id = cur.lastrowid

        # Maintain cached max spans if initialized
        if self._max_cross_ref_spans is not None:
            s_span = s_end - s_start
            t_span = t_end - t_start
            m_s, m_t = self._max_cross_ref_spans
            if s_span > m_s or t_span > m_t:
                self._max_cross_ref_spans = (max(m_s, s_span), max(m_t, t_span))

        return CrossReferenceRecord(
            id=xr_id,
            source_start_id=s_start,
            source_end_id=s_end,
            source_human_ref=s_human,
            target_start_id=t_start,
            target_end_id=t_end,
            target_human_ref=t_human,
            relationship_type=relationship_type.strip().lower(),
            weight=weight,
            notes=notes,
            created_at=now,
        )

    def _get_cross_ref_max_spans(self) -> Tuple[int, int]:
        """Return maximum coordinate span for source and target cross-references.

        Returns (max_source_span, max_target_span) in canonical coordinate ID space.
        Cached in-memory to provide instantaneous mathematical lower-bounding for
        spatial index seeks in get_cross_references(), eliminating full table scans.
        """
        if self._max_cross_ref_spans is None:
            cur = self.conn.cursor()
            try:
                cur.execute(
                    """
                    SELECT
                        COALESCE(MAX(source_end_id - source_start_id), 0),
                        COALESCE(MAX(target_end_id - target_start_id), 0)
                    FROM cross_references
                    """
                )
                row = cur.fetchone()
                if row and (row[0] > 0 or row[1] > 0):
                    self._max_cross_ref_spans = (int(row[0]), int(row[1]))
                else:
                    self._max_cross_ref_spans = (100, 10000)
            except Exception:
                self._max_cross_ref_spans = (100, 10000)
            finally:
                cur.close()
        return self._max_cross_ref_spans

    def get_cross_references(
        self,
        reference: Union[Reference, str],
        bidirectional: bool = True,
    ) -> List[CrossReferenceRecord]:
        """Find all cross-references connected to the given reference using bounded spatial index seeks.

        Optimized with mathematical lower bounds derived from cached max span bounds,
        converting un-indexed O(N) full table scans over 343,000+ edges into O(log N)
        dual binary search index seeks on idx_cross_ref_source and idx_cross_ref_target.
        """
        ref = parse_reference(reference) if isinstance(reference, str) else reference
        start_id = ref.canonical_start_id
        end_id = ref.canonical_end_id

        max_src_span, max_tgt_span = self._get_cross_ref_max_spans()
        src_min = max(0, start_id - max_src_span)

        cur = self.conn.cursor()
        if bidirectional:
            tgt_min = max(0, start_id - max_tgt_span)
            cur.execute(
                """
                SELECT * FROM (
                    SELECT * FROM cross_references
                    WHERE source_start_id >= ? AND source_start_id <= ? AND source_end_id >= ?
                    UNION ALL
                    SELECT * FROM cross_references
                    WHERE target_start_id >= ? AND target_start_id <= ? AND target_end_id >= ?
                      AND NOT (source_start_id >= ? AND source_start_id <= ? AND source_end_id >= ?)
                )
                ORDER BY weight DESC, id ASC
                """,
                (src_min, end_id, start_id, tgt_min, end_id, start_id, src_min, end_id, start_id),
            )
        else:
            cur.execute(
                """
                SELECT * FROM cross_references
                WHERE source_start_id >= ? AND source_start_id <= ? AND source_end_id >= ?
                ORDER BY weight DESC, id ASC
                """,
                (src_min, end_id, start_id),
            )
        rows = cur.fetchall()
        cur.close()
        return [
            CrossReferenceRecord(
                id=r["id"],
                source_start_id=r["source_start_id"],
                source_end_id=r["source_end_id"],
                source_human_ref=r["source_human_ref"],
                target_start_id=r["target_start_id"],
                target_end_id=r["target_end_id"],
                target_human_ref=r["target_human_ref"],
                relationship_type=r["relationship_type"],
                weight=r["weight"],
                notes=r["notes"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def tag_references_batch(
        self,
        items: Sequence[Tuple[Union[Reference, str], bool, Optional[str]]],
        tag_name: str = "favorites",
        category: str = "curation",
        confidence: float = 1.0,
        source: str = "user",
    ) -> int:
        """Batch insert tag associations inside an atomic transaction.

        Args:
            items: Sequence of (reference, starred, notes) tuples.
            tag_name: Semantic tag name (e.g. 'favorites').
            category: Tag category.
            confidence: Confidence score.
            source: Provenance source.

        Returns:
            Count of inserted tag associations.
        """
        if not items:
            return 0

        tag = self.get_or_create_tag(tag_name, category=category)
        assert tag.id is not None

        now = _utc_now_iso()
        rows = []
        for ref_input, starred, notes in items:
            ref = parse_reference(ref_input) if isinstance(ref_input, str) else ref_input
            rows.append(
                (
                    tag.id,
                    ref.canonical_start_id,
                    ref.canonical_end_id,
                    ref.format(),
                    confidence,
                    source,
                    1 if starred else 0,
                    notes,
                    now,
                )
            )

        with self.conn:
            self.conn.executemany(
                """
                INSERT INTO verse_tags (
                    tag_id, start_canonical_id, end_canonical_id, human_ref,
                    confidence, source, starred, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

            # If any items are starred and tag is not already 'starred',
            # also batch-link them to the first-class 'starred' tag (Task 3.6 / ADR-080).
            if tag.name != "starred":
                starred_items = [(ref_input, s, notes) for (ref_input, s, notes) in items if s]
                if starred_items:
                    cur_star = self.conn.cursor()
                    cur_star.execute("SELECT id FROM tags WHERE name = 'starred' LIMIT 1")
                    starred_row = cur_star.fetchone()
                    if not starred_row:
                        cur_star.execute(
                            """
                            INSERT INTO tags (name, category, description, created_at)
                            VALUES ('starred', 'curation', 'Priority starred scripture citations and key verses', ?)
                            """,
                            (now,),
                        )
                        starred_tag_id = cur_star.lastrowid
                    else:
                        starred_tag_id = starred_row["id"]

                    starred_rows = []
                    for ref_input, _, notes in starred_items:
                        ref = parse_reference(ref_input) if isinstance(ref_input, str) else ref_input
                        s_id = ref.canonical_start_id
                        e_id = ref.canonical_end_id
                        cur_star.execute(
                            """
                            SELECT id FROM verse_tags
                            WHERE tag_id = ? AND start_canonical_id = ? AND end_canonical_id = ?
                            LIMIT 1
                            """,
                            (starred_tag_id, s_id, e_id),
                        )
                        if not cur_star.fetchone():
                            starred_rows.append(
                                (
                                    starred_tag_id,
                                    s_id,
                                    e_id,
                                    ref.format(),
                                    confidence,
                                    source,
                                    1,
                                    notes,
                                    now,
                                )
                            )
                    if starred_rows:
                        self.conn.executemany(
                            """
                            INSERT INTO verse_tags (
                                tag_id, start_canonical_id, end_canonical_id, human_ref,
                                confidence, source, starred, notes, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            starred_rows,
                        )
                    cur_star.close()

        return len(rows)

    def clear_tag(self, tag_name: str) -> int:
        """Remove all verse associations for a tag. Returns deleted row count."""
        tag = self.get_tag(tag_name)
        if not tag or tag.id is None:
            return 0
        with self.conn:
            cur = self.conn.execute("DELETE FROM verse_tags WHERE tag_id = ?", (tag.id,))
            return cur.rowcount

    # --- Favorites Convenience API (Task 1.6 First-Class Support) ---

    def tag_as_favorite(
        self,
        reference: Union[Reference, str],
        starred: bool = False,
        notes: Optional[str] = None,
    ) -> VerseTagRecord:
        """Mark a passage as a user favorite (with optional starred priority)."""
        return self.tag_reference(
            reference=reference,
            tag_name="favorites",
            category="curation",
            confidence=1.0,
            source="user",
            starred=starred,
            notes=notes,
        )

    def get_favorites(self, starred_only: bool = False) -> List[VerseTagRecord]:
        """Retrieve all passages tagged as favorites."""
        return self.get_references_for_tag("favorites", starred_only=starred_only)

    # --- Pericopes & Redemptive Headings API (Task 4.4 & Phase 7) ---

    def insert_pericope(
        self,
        reference: Union[Reference, str],
        title: str,
        redemptive_summary: Optional[str] = None,
        genre: Optional[str] = None,
        literary_structure: Optional[str] = None,
        central_proposition: Optional[str] = None,
    ) -> PericopeRecord:
        """Insert a canonical scripture pericope section with heading and summary.

        Args:
            reference: Passage reference (e.g. 'Romans 8:1-11').
            title: Section title / pericope heading.
            redemptive_summary: Optional redemptive-historical theological summary.
            genre: Optional literary genre (e.g. 'epistle', 'narrative', 'prophecy').
            literary_structure: Optional structural outline or chiasm notes.
            central_proposition: Optional central theological proposition.

        Returns:
            Created PericopeRecord instance.
        """
        ref = parse_reference(reference) if isinstance(reference, str) else reference
        book_id = ref.book.number
        start_id = ref.canonical_start_id
        end_id = ref.canonical_end_id
        human = ref.format()
        now = _utc_now_iso()

        with self.conn:
            cur = self.conn.execute(
                """
                INSERT INTO pericopes (
                    book_id, start_canonical_id, end_canonical_id, human_ref,
                    title, redemptive_summary, genre, literary_structure, central_proposition, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    book_id,
                    start_id,
                    end_id,
                    human,
                    title.strip(),
                    redemptive_summary.strip() if redemptive_summary else None,
                    genre.strip() if genre else None,
                    literary_structure.strip() if literary_structure else None,
                    central_proposition.strip() if central_proposition else None,
                    now,
                ),
            )
            p_id = cur.lastrowid

        return PericopeRecord(
            id=p_id,
            book_id=book_id,
            start_canonical_id=start_id,
            end_canonical_id=end_id,
            human_ref=human,
            title=title.strip(),
            redemptive_summary=redemptive_summary.strip() if redemptive_summary else None,
            genre=genre.strip() if genre else None,
            literary_structure=literary_structure.strip() if literary_structure else None,
            central_proposition=central_proposition.strip() if central_proposition else None,
            created_at=now,
        )

    def insert_pericopes_batch(
        self,
        items: Sequence[Tuple[Any, ...]],
    ) -> int:
        """Batch insert multiple pericope headings inside a single transaction.

        Supports tuples of:
        - (reference, title, redemptive_summary)
        - (reference, title, redemptive_summary, genre)
        - (reference, title, redemptive_summary, genre, literary_structure)
        - (reference, title, redemptive_summary, genre, literary_structure, central_proposition)
        """
        now = _utc_now_iso()
        rows: List[Tuple[Any, ...]] = []
        for item in items:
            if isinstance(item, PericopeRecord):
                rows.append((
                    item.book_id,
                    item.start_canonical_id,
                    item.end_canonical_id,
                    item.human_ref,
                    item.title.strip(),
                    item.redemptive_summary.strip() if item.redemptive_summary else None,
                    item.genre.strip() if item.genre else None,
                    item.literary_structure.strip() if item.literary_structure else None,
                    item.central_proposition.strip() if item.central_proposition else None,
                    item.created_at or now,
                ))
                continue

            ref_input = item[0]
            title = item[1]
            summary = item[2] if len(item) > 2 else None
            genre = item[3] if len(item) > 3 else None
            structure = item[4] if len(item) > 4 else None
            prop = item[5] if len(item) > 5 else None

            ref = parse_reference(ref_input) if isinstance(ref_input, str) else ref_input
            rows.append((
                ref.book.number,
                ref.canonical_start_id,
                ref.canonical_end_id,
                ref.format(),
                title.strip(),
                summary.strip() if summary else None,
                genre.strip() if genre else None,
                structure.strip() if structure else None,
                prop.strip() if prop else None,
                now,
            ))

        with self.conn:
            self.conn.executemany(
                """
                INSERT INTO pericopes (
                    book_id, start_canonical_id, end_canonical_id, human_ref,
                    title, redemptive_summary, genre, literary_structure, central_proposition, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        return len(rows)

    def get_pericopes_for_reference(
        self,
        reference: Union[Reference, str],
    ) -> List[PericopeRecord]:
        """Fetch all pericope headings overlapping with the given reference range."""
        ref = parse_reference(reference) if isinstance(reference, str) else reference
        start_id = ref.canonical_start_id
        end_id = ref.canonical_end_id

        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT id, book_id, start_canonical_id, end_canonical_id, human_ref, title,
                   redemptive_summary, genre, literary_structure, central_proposition, created_at
            FROM pericopes
            WHERE start_canonical_id <= ? AND end_canonical_id >= ?
            ORDER BY start_canonical_id ASC, id ASC
            """,
            (end_id, start_id),
        )
        rows = cur.fetchall()
        cur.close()
        return [
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

    def get_pericopes_for_book(
        self,
        book: Union[Book, str, int],
        chapter: Optional[int] = None,
    ) -> List[PericopeRecord]:
        """Retrieve pericope headings for an entire book or specific chapter."""
        b = get_book(book)
        cur = self.conn.cursor()
        if chapter is not None:
            c_start = verse_canonical_id(b.number, chapter, 1)
            c_end = verse_canonical_id(b.number, chapter, 999)
            cur.execute(
                """
                SELECT id, book_id, start_canonical_id, end_canonical_id, human_ref, title,
                       redemptive_summary, genre, literary_structure, central_proposition, created_at
                FROM pericopes
                WHERE book_id = ? AND start_canonical_id <= ? AND end_canonical_id >= ?
                ORDER BY start_canonical_id ASC, id ASC
                """,
                (b.number, c_end, c_start),
            )
        else:
            cur.execute(
                """
                SELECT id, book_id, start_canonical_id, end_canonical_id, human_ref, title,
                       redemptive_summary, genre, literary_structure, central_proposition, created_at
                FROM pericopes
                WHERE book_id = ?
                ORDER BY start_canonical_id ASC, id ASC
                """,
                (b.number,),
            )
        rows = cur.fetchall()
        cur.close()
        return [
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

    def count_pericopes(self, book_id: Optional[int] = None) -> int:
        """Count total pericopes stored in the database."""
        cur = self.conn.cursor()
        if book_id is not None:
            cur.execute("SELECT count(*) FROM pericopes WHERE book_id = ?", (book_id,))
        else:
            cur.execute("SELECT count(*) FROM pericopes")
        row = cur.fetchone()
        cur.close()
        return row[0] if row else 0

    def get_all_pericopes(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[PericopeRecord]:
        """Retrieve all pericope records ordered canonically by start coordinate."""
        cur = self.conn.cursor()
        query = """
            SELECT id, book_id, start_canonical_id, end_canonical_id, human_ref, title,
                   redemptive_summary, genre, literary_structure, central_proposition, created_at
            FROM pericopes
            ORDER BY start_canonical_id ASC, id ASC
        """
        params: List[Any] = []
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        cur.execute(query, params)
        rows = cur.fetchall()
        cur.close()
        return [
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

    def update_pericope(
        self,
        pericope_id: int,
        title: Optional[str] = None,
        redemptive_summary: Optional[str] = None,
        genre: Optional[str] = None,
        literary_structure: Optional[str] = None,
        central_proposition: Optional[str] = None,
    ) -> bool:
        """Update semantic attributes for an existing pericope record."""
        fields: List[str] = []
        params: List[Any] = []
        if title is not None:
            fields.append("title = ?")
            params.append(title.strip())
        if redemptive_summary is not None:
            fields.append("redemptive_summary = ?")
            params.append(redemptive_summary.strip() if redemptive_summary else None)
        if genre is not None:
            fields.append("genre = ?")
            params.append(genre.strip() if genre else None)
        if literary_structure is not None:
            fields.append("literary_structure = ?")
            params.append(literary_structure.strip() if literary_structure else None)
        if central_proposition is not None:
            fields.append("central_proposition = ?")
            params.append(central_proposition.strip() if central_proposition else None)

        if not fields:
            return False

        query = f"UPDATE pericopes SET {', '.join(fields)} WHERE id = ?"
        params.append(pericope_id)

        with self.conn:
            cur = self.conn.execute(query, params)
            return cur.rowcount > 0

    def clear_pericopes(self, book_id: Optional[int] = None) -> int:
        """Remove pericope headings (optionally filtered by book_id)."""
        with self.conn:
            if book_id is not None:
                cur = self.conn.execute("DELETE FROM pericopes WHERE book_id = ?", (book_id,))
            else:
                cur = self.conn.execute("DELETE FROM pericopes")
            return cur.rowcount

    # --- Discourse Relations API (Phase 7 / ADR-042) ---

    def insert_discourse_relation(
        self,
        source_reference: Union[Reference, str],
        relation_type: str,
        target_reference: Optional[Union[Reference, str]] = None,
        marker_text: Optional[str] = None,
        greek_marker: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> DiscourseRelationRecord:
        """Insert a discourse relation connecting verses or clauses."""
        s_ref = parse_reference(source_reference) if isinstance(source_reference, str) else source_reference
        s_id = s_ref.canonical_start_id
        s_human = s_ref.format()

        t_id = None
        t_human = None
        if target_reference:
            t_ref = parse_reference(target_reference) if isinstance(target_reference, str) else target_reference
            t_id = t_ref.canonical_start_id
            t_human = t_ref.format()

        now = _utc_now_iso()
        with self.conn:
            cur = self.conn.execute(
                """
                INSERT INTO discourse_relations (
                    source_canonical_id, source_human_ref, target_canonical_id, target_human_ref,
                    relation_type, marker_text, greek_marker, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    s_id,
                    s_human,
                    t_id,
                    t_human,
                    relation_type.strip().lower(),
                    marker_text.strip() if marker_text else None,
                    greek_marker.strip() if greek_marker else None,
                    notes.strip() if notes else None,
                    now,
                ),
            )
            d_id = cur.lastrowid

        return DiscourseRelationRecord(
            id=d_id,
            source_canonical_id=s_id,
            source_human_ref=s_human,
            target_canonical_id=t_id,
            target_human_ref=t_human,
            relation_type=relation_type.strip().lower(),
            marker_text=marker_text.strip() if marker_text else None,
            greek_marker=greek_marker.strip() if greek_marker else None,
            notes=notes.strip() if notes else None,
            created_at=now,
        )

    def insert_discourse_relations_batch(
        self,
        items: Sequence[Tuple[Any, ...]],
    ) -> int:
        """Batch insert multiple discourse relations inside a single transaction."""
        now = _utc_now_iso()
        rows = []
        for item in items:
            if isinstance(item, DiscourseRelationRecord):
                rows.append((
                    item.source_canonical_id,
                    item.source_human_ref,
                    item.target_canonical_id,
                    item.target_human_ref,
                    item.relation_type.strip().lower(),
                    item.marker_text.strip() if item.marker_text else None,
                    item.greek_marker.strip() if item.greek_marker else None,
                    item.notes.strip() if item.notes else None,
                    item.created_at or now,
                ))
                continue

            s_ref_input = item[0]
            rel_type = item[1]
            t_ref_input = item[2] if len(item) > 2 else None
            marker_text = item[3] if len(item) > 3 else None
            greek_marker = item[4] if len(item) > 4 else None
            notes = item[5] if len(item) > 5 else None

            s_ref = parse_reference(s_ref_input) if isinstance(s_ref_input, str) else s_ref_input
            s_id = s_ref.canonical_start_id
            s_human = s_ref.format()

            t_id = None
            t_human = None
            if t_ref_input:
                t_ref = parse_reference(t_ref_input) if isinstance(t_ref_input, str) else t_ref_input
                t_id = t_ref.canonical_start_id
                t_human = t_ref.format()

            rows.append((
                s_id,
                s_human,
                t_id,
                t_human,
                rel_type.strip().lower(),
                marker_text.strip() if marker_text else None,
                greek_marker.strip() if greek_marker else None,
                notes.strip() if notes else None,
                now,
            ))

        with self.conn:
            self.conn.executemany(
                """
                INSERT INTO discourse_relations (
                    source_canonical_id, source_human_ref, target_canonical_id, target_human_ref,
                    relation_type, marker_text, greek_marker, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        return len(rows)

    def get_discourse_relations_for_verse(
        self,
        reference: Union[Reference, str],
    ) -> List[DiscourseRelationRecord]:
        """Fetch discourse relations where the given verse/range is either source or target."""
        ref = parse_reference(reference) if isinstance(reference, str) else reference
        start_id = ref.canonical_start_id
        end_id = ref.canonical_end_id

        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT id, source_canonical_id, source_human_ref, target_canonical_id, target_human_ref,
                   relation_type, marker_text, greek_marker, notes, created_at
            FROM discourse_relations
            WHERE (source_canonical_id >= ? AND source_canonical_id <= ?)
               OR (target_canonical_id >= ? AND target_canonical_id <= ?)
            ORDER BY source_canonical_id ASC, id ASC
            """,
            (start_id, end_id, start_id, end_id),
        )
        rows = cur.fetchall()
        cur.close()
        return [
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
            for r in rows
        ]

    def get_discourse_relations_by_type(
        self,
        relation_type: str,
        limit: int = 100,
    ) -> List[DiscourseRelationRecord]:
        """Retrieve discourse relations filtered by relation type."""
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT id, source_canonical_id, source_human_ref, target_canonical_id, target_human_ref,
                   relation_type, marker_text, greek_marker, notes, created_at
            FROM discourse_relations
            WHERE relation_type = ?
            ORDER BY source_canonical_id ASC, id ASC
            LIMIT ?
            """,
            (relation_type.strip().lower(), limit),
        )
        rows = cur.fetchall()
        cur.close()
        return [
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
            for r in rows
        ]

    def count_discourse_relations(self, relation_type: Optional[str] = None) -> int:
        """Count discourse relations, optionally filtered by type."""
        cur = self.conn.cursor()
        if relation_type:
            cur.execute(
                "SELECT count(*) FROM discourse_relations WHERE relation_type = ?",
                (relation_type.strip().lower(),),
            )
        else:
            cur.execute("SELECT count(*) FROM discourse_relations")
        row = cur.fetchone()
        cur.close()
        return row[0] if row else 0

    def get_all_discourse_relations(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[DiscourseRelationRecord]:
        """Retrieve all discourse relations ordered canonically by source coordinate."""
        cur = self.conn.cursor()
        query = """
            SELECT id, source_canonical_id, source_human_ref, target_canonical_id, target_human_ref,
                   relation_type, marker_text, greek_marker, notes, created_at
            FROM discourse_relations
            ORDER BY source_canonical_id ASC, id ASC
        """
        params: List[Any] = []
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        cur.execute(query, params)
        rows = cur.fetchall()
        cur.close()
        return [
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
            for r in rows
        ]

    def clear_discourse_relations(self) -> int:
        """Remove all discourse relations from database."""
        with self.conn:
            cur = self.conn.execute("DELETE FROM discourse_relations")
            return cur.rowcount

    # --- Verse Theology API (Phase 7 / ADR-042) ---

    def insert_verse_theology(
        self,
        reference: Union[Reference, str],
        storyline_epoch: str,
        theological_locus: str,
        primary_doctrine: str,
        thematic_ribbon: Optional[str] = None,
        confidence: float = 1.0,
    ) -> VerseTheologyRecord:
        """Insert theological locus, epoch, and ribbon annotation for a passage."""
        ref = parse_reference(reference) if isinstance(reference, str) else reference
        s_id = ref.canonical_start_id
        e_id = ref.canonical_end_id
        human = ref.format()
        now = _utc_now_iso()

        with self.conn:
            cur = self.conn.execute(
                """
                INSERT INTO verse_theology (
                    start_canonical_id, end_canonical_id, human_ref, storyline_epoch,
                    thematic_ribbon, theological_locus, primary_doctrine, confidence,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    s_id,
                    e_id,
                    human,
                    storyline_epoch.strip(),
                    thematic_ribbon.strip() if thematic_ribbon else None,
                    theological_locus.strip(),
                    primary_doctrine.strip(),
                    confidence,
                    now,
                ),
            )
            vt_id = cur.lastrowid

        return VerseTheologyRecord(
            id=vt_id,
            start_canonical_id=s_id,
            end_canonical_id=e_id,
            human_ref=human,
            storyline_epoch=storyline_epoch.strip(),
            theological_locus=theological_locus.strip(),
            primary_doctrine=primary_doctrine.strip(),
            thematic_ribbon=thematic_ribbon.strip() if thematic_ribbon else None,
            confidence=confidence,
            created_at=now,
        )

    def insert_verse_theology_batch(
        self,
        items: Sequence[Tuple[Any, ...]],
    ) -> int:
        """Batch insert multiple verse theology annotations in a transaction."""
        now = _utc_now_iso()
        rows = []
        for item in items:
            if isinstance(item, VerseTheologyRecord):
                rows.append((
                    item.start_canonical_id,
                    item.end_canonical_id,
                    item.human_ref,
                    item.storyline_epoch.strip(),
                    item.thematic_ribbon.strip() if item.thematic_ribbon else None,
                    item.theological_locus.strip(),
                    item.primary_doctrine.strip(),
                    item.confidence,
                    item.created_at or now,
                ))
                continue

            ref_input = item[0]
            epoch = item[1]
            locus = item[2]
            doctrine = item[3]
            ribbon = item[4] if len(item) > 4 else None
            conf = item[5] if len(item) > 5 else 1.0

            ref = parse_reference(ref_input) if isinstance(ref_input, str) else ref_input
            rows.append((
                ref.canonical_start_id,
                ref.canonical_end_id,
                ref.format(),
                epoch.strip(),
                ribbon.strip() if ribbon else None,
                locus.strip(),
                doctrine.strip(),
                conf,
                now,
            ))

        with self.conn:
            self.conn.executemany(
                """
                INSERT INTO verse_theology (
                    start_canonical_id, end_canonical_id, human_ref, storyline_epoch,
                    thematic_ribbon, theological_locus, primary_doctrine, confidence,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        return len(rows)

    def get_verse_theology_for_reference(
        self,
        reference: Union[Reference, str],
    ) -> List[VerseTheologyRecord]:
        """Retrieve theological annotations overlapping with the specified reference."""
        ref = parse_reference(reference) if isinstance(reference, str) else reference
        start_id = ref.canonical_start_id
        end_id = ref.canonical_end_id

        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT id, start_canonical_id, end_canonical_id, human_ref, storyline_epoch,
                   thematic_ribbon, theological_locus, primary_doctrine, confidence,
                   created_at
            FROM verse_theology
            WHERE start_canonical_id <= ? AND end_canonical_id >= ?
            ORDER BY start_canonical_id ASC, id ASC
            """,
            (end_id, start_id),
        )
        rows = cur.fetchall()
        cur.close()
        return [
            VerseTheologyRecord(
                id=r["id"],
                start_canonical_id=r["start_canonical_id"],
                end_canonical_id=r["end_canonical_id"],
                human_ref=r["human_ref"],
                storyline_epoch=r["storyline_epoch"],
                thematic_ribbon=r["thematic_ribbon"],
                theological_locus=r["theological_locus"],
                primary_doctrine=r["primary_doctrine"],
                confidence=r["confidence"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def get_verse_theology_by_epoch(
        self,
        storyline_epoch: str,
        limit: int = 100,
    ) -> List[VerseTheologyRecord]:
        """Fetch theology annotations by redemptive storyline epoch."""
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT id, start_canonical_id, end_canonical_id, human_ref, storyline_epoch,
                   thematic_ribbon, theological_locus, primary_doctrine, confidence,
                   created_at
            FROM verse_theology
            WHERE storyline_epoch = ?
            ORDER BY start_canonical_id ASC, id ASC
            LIMIT ?
            """,
            (storyline_epoch.strip(), limit),
        )
        rows = cur.fetchall()
        cur.close()
        return [
            VerseTheologyRecord(
                id=r["id"],
                start_canonical_id=r["start_canonical_id"],
                end_canonical_id=r["end_canonical_id"],
                human_ref=r["human_ref"],
                storyline_epoch=r["storyline_epoch"],
                thematic_ribbon=r["thematic_ribbon"],
                theological_locus=r["theological_locus"],
                primary_doctrine=r["primary_doctrine"],
                confidence=r["confidence"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def get_verse_theology_by_locus(
        self,
        theological_locus: str,
        limit: int = 100,
    ) -> List[VerseTheologyRecord]:
        """Fetch theology annotations by systematic theological locus."""
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT id, start_canonical_id, end_canonical_id, human_ref, storyline_epoch,
                   thematic_ribbon, theological_locus, primary_doctrine, confidence,
                   created_at
            FROM verse_theology
            WHERE theological_locus = ?
            ORDER BY start_canonical_id ASC, id ASC
            LIMIT ?
            """,
            (theological_locus.strip(), limit),
        )
        rows = cur.fetchall()
        cur.close()
        return [
            VerseTheologyRecord(
                id=r["id"],
                start_canonical_id=r["start_canonical_id"],
                end_canonical_id=r["end_canonical_id"],
                human_ref=r["human_ref"],
                storyline_epoch=r["storyline_epoch"],
                thematic_ribbon=r["thematic_ribbon"],
                theological_locus=r["theological_locus"],
                primary_doctrine=r["primary_doctrine"],
                confidence=r["confidence"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def get_verse_theology_by_ribbon(
        self,
        thematic_ribbon: str,
        limit: int = 100,
    ) -> List[VerseTheologyRecord]:
        """Fetch theology annotations by canonical thematic ribbon."""
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT id, start_canonical_id, end_canonical_id, human_ref, storyline_epoch,
                   thematic_ribbon, theological_locus, primary_doctrine, confidence,
                   created_at
            FROM verse_theology
            WHERE thematic_ribbon = ?
            ORDER BY start_canonical_id ASC, id ASC
            LIMIT ?
            """,
            (thematic_ribbon.strip(), limit),
        )
        rows = cur.fetchall()
        cur.close()
        return [
            VerseTheologyRecord(
                id=r["id"],
                start_canonical_id=r["start_canonical_id"],
                end_canonical_id=r["end_canonical_id"],
                human_ref=r["human_ref"],
                storyline_epoch=r["storyline_epoch"],
                thematic_ribbon=r["thematic_ribbon"],
                theological_locus=r["theological_locus"],
                primary_doctrine=r["primary_doctrine"],
                confidence=r["confidence"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def count_verse_theology(
        self,
        storyline_epoch: Optional[str] = None,
        theological_locus: Optional[str] = None,
    ) -> int:
        """Count total theology annotations with optional filtering."""
        cur = self.conn.cursor()
        if storyline_epoch and theological_locus:
            cur.execute(
                "SELECT count(*) FROM verse_theology WHERE storyline_epoch = ? AND theological_locus = ?",
                (storyline_epoch.strip(), theological_locus.strip()),
            )
        elif storyline_epoch:
            cur.execute("SELECT count(*) FROM verse_theology WHERE storyline_epoch = ?", (storyline_epoch.strip(),))
        elif theological_locus:
            cur.execute("SELECT count(*) FROM verse_theology WHERE theological_locus = ?", (theological_locus.strip(),))
        else:
            cur.execute("SELECT count(*) FROM verse_theology")
        row = cur.fetchone()
        cur.close()
        return row[0] if row else 0

    def get_all_verse_theology(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[VerseTheologyRecord]:
        """Retrieve all verse theology annotations ordered canonically by start coordinate."""
        cur = self.conn.cursor()
        query = """
            SELECT id, start_canonical_id, end_canonical_id, human_ref, storyline_epoch,
                   thematic_ribbon, theological_locus, primary_doctrine, confidence, created_at
            FROM verse_theology
            ORDER BY start_canonical_id ASC, id ASC
        """
        params: List[Any] = []
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        cur.execute(query, params)
        rows = cur.fetchall()
        cur.close()
        return [
            VerseTheologyRecord(
                id=r["id"],
                start_canonical_id=r["start_canonical_id"],
                end_canonical_id=r["end_canonical_id"],
                human_ref=r["human_ref"],
                storyline_epoch=r["storyline_epoch"],
                thematic_ribbon=r["thematic_ribbon"],
                theological_locus=r["theological_locus"],
                primary_doctrine=r["primary_doctrine"],
                confidence=r["confidence"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def clear_verse_theology(self) -> int:
        """Remove all verse theology rows."""
        with self.conn:
            cur = self.conn.execute("DELETE FROM verse_theology")
            return cur.rowcount

    # --- Typological Arcs API (Phase 7 / ADR-042) ---

    def insert_typological_arc(
        self,
        type_reference: Union[Reference, str],
        antitype_reference: Union[Reference, str],
        theological_correspondence: str,
        warrant: Optional[str] = None,
        confidence: float = 1.0,
    ) -> TypologicalArcRecord:
        """Insert a canonical typological arc linking OT type to NT antitype."""
        type_ref = parse_reference(type_reference) if isinstance(type_reference, str) else type_reference
        antitype_ref = parse_reference(antitype_reference) if isinstance(antitype_reference, str) else antitype_reference
        now = _utc_now_iso()

        with self.conn:
            cur = self.conn.execute(
                """
                INSERT INTO typological_arcs (
                    type_start_id, type_end_id, type_human_ref,
                    antitype_start_id, antitype_end_id, antitype_human_ref,
                    theological_correspondence, warrant, confidence, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    type_ref.canonical_start_id,
                    type_ref.canonical_end_id,
                    type_ref.format(),
                    antitype_ref.canonical_start_id,
                    antitype_ref.canonical_end_id,
                    antitype_ref.format(),
                    theological_correspondence.strip(),
                    warrant.strip() if warrant else None,
                    confidence,
                    now,
                ),
            )
            arc_id = cur.lastrowid

        return TypologicalArcRecord(
            id=arc_id,
            type_start_id=type_ref.canonical_start_id,
            type_end_id=type_ref.canonical_end_id,
            type_human_ref=type_ref.format(),
            antitype_start_id=antitype_ref.canonical_start_id,
            antitype_end_id=antitype_ref.canonical_end_id,
            antitype_human_ref=antitype_ref.format(),
            theological_correspondence=theological_correspondence.strip(),
            warrant=warrant.strip() if warrant else None,
            confidence=confidence,
            created_at=now,
        )

    def insert_typological_arcs_batch(
        self,
        items: Sequence[Tuple[Any, ...]],
    ) -> int:
        """Batch insert typological arcs in a transaction."""
        now = _utc_now_iso()
        rows = []
        for item in items:
            if isinstance(item, TypologicalArcRecord):
                rows.append((
                    item.type_start_id,
                    item.type_end_id,
                    item.type_human_ref,
                    item.antitype_start_id,
                    item.antitype_end_id,
                    item.antitype_human_ref,
                    item.theological_correspondence.strip(),
                    item.warrant.strip() if item.warrant else None,
                    item.confidence,
                    item.created_at or now,
                ))
                continue

            t_input = item[0]
            at_input = item[1]
            corr = item[2]
            warrant = item[3] if len(item) > 3 else None
            conf = item[4] if len(item) > 4 else 1.0

            t_ref = parse_reference(t_input) if isinstance(t_input, str) else t_input
            at_ref = parse_reference(at_input) if isinstance(at_input, str) else at_input

            rows.append((
                t_ref.canonical_start_id,
                t_ref.canonical_end_id,
                t_ref.format(),
                at_ref.canonical_start_id,
                at_ref.canonical_end_id,
                at_ref.format(),
                corr.strip(),
                warrant.strip() if warrant else None,
                conf,
                now,
            ))

        with self.conn:
            self.conn.executemany(
                """
                INSERT INTO typological_arcs (
                    type_start_id, type_end_id, type_human_ref,
                    antitype_start_id, antitype_end_id, antitype_human_ref,
                    theological_correspondence, warrant, confidence, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        return len(rows)

    def get_typological_arcs_for_reference(
        self,
        reference: Union[Reference, str],
        as_type: bool = True,
        as_antitype: bool = True,
    ) -> List[TypologicalArcRecord]:
        """Fetch typological arcs overlapping with reference as either type or antitype."""
        ref = parse_reference(reference) if isinstance(reference, str) else reference
        start_id = ref.canonical_start_id
        end_id = ref.canonical_end_id

        clauses = []
        params: List[Any] = []
        if as_type:
            clauses.append("(type_start_id <= ? AND type_end_id >= ?)")
            params.extend([end_id, start_id])
        if as_antitype:
            clauses.append("(antitype_start_id <= ? AND antitype_end_id >= ?)")
            params.extend([end_id, start_id])

        if not clauses:
            return []

        where_sql = " OR ".join(clauses)
        cur = self.conn.cursor()
        cur.execute(
            f"""
            SELECT id, type_start_id, type_end_id, type_human_ref,
                   antitype_start_id, antitype_end_id, antitype_human_ref,
                   theological_correspondence, warrant, confidence, created_at
            FROM typological_arcs
            WHERE {where_sql}
            ORDER BY confidence DESC, id ASC
            """,
            params,
        )
        rows = cur.fetchall()
        cur.close()
        return [
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
            for r in rows
        ]

    def count_typological_arcs(self) -> int:
        """Count total typological arcs."""
        cur = self.conn.cursor()
        cur.execute("SELECT count(*) FROM typological_arcs")
        row = cur.fetchone()
        cur.close()
        return row[0] if row else 0

    def get_all_typological_arcs(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[TypologicalArcRecord]:
        """Retrieve all typological arcs ordered canonically by type start coordinate."""
        cur = self.conn.cursor()
        query = """
            SELECT id, type_start_id, type_end_id, type_human_ref, antitype_start_id,
                   antitype_end_id, antitype_human_ref, theological_correspondence, warrant, confidence, created_at
            FROM typological_arcs
            ORDER BY type_start_id ASC, id ASC
        """
        params: List[Any] = []
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        cur.execute(query, params)
        rows = cur.fetchall()
        cur.close()
        return [
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
            for r in rows
        ]

    def clear_typological_arcs(self) -> int:
        """Remove all typological arcs."""
        with self.conn:
            cur = self.conn.execute("DELETE FROM typological_arcs")
            return cur.rowcount

    # --- Semantic Propositions API (Phase 7 / ADR-042) ---

    def insert_semantic_proposition(
        self,
        reference: Union[Reference, str],
        speech_act: str,
        agent: str,
        action: str,
        patient: Optional[str] = None,
        tone: Optional[str] = None,
        clause_text: Optional[str] = None,
    ) -> SemanticPropositionRecord:
        """Insert a semantic proposition agent-action-patient triple and speech act."""
        ref = parse_reference(reference) if isinstance(reference, str) else reference
        vid = ref.canonical_start_id
        human = ref.format()
        now = _utc_now_iso()

        with self.conn:
            cur = self.conn.execute(
                """
                INSERT INTO semantic_propositions (
                    canonical_verse_id, human_ref, speech_act, agent, action, patient, tone, clause_text, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    vid,
                    human,
                    speech_act.strip().lower(),
                    agent.strip(),
                    action.strip(),
                    patient.strip() if patient else None,
                    tone.strip().lower() if tone else None,
                    clause_text.strip() if clause_text else None,
                    now,
                ),
            )
            sp_id = cur.lastrowid

        return SemanticPropositionRecord(
            id=sp_id,
            canonical_verse_id=vid,
            human_ref=human,
            speech_act=speech_act.strip().lower(),
            agent=agent.strip(),
            action=action.strip(),
            patient=patient.strip() if patient else None,
            tone=tone.strip().lower() if tone else None,
            clause_text=clause_text.strip() if clause_text else None,
            created_at=now,
        )

    def insert_semantic_propositions_batch(
        self,
        items: Sequence[Tuple[Any, ...]],
    ) -> int:
        """Batch insert semantic propositions in a transaction."""
        now = _utc_now_iso()
        rows = []
        for item in items:
            if isinstance(item, SemanticPropositionRecord):
                rows.append((
                    item.canonical_verse_id,
                    item.human_ref,
                    item.speech_act.strip().lower(),
                    item.agent.strip(),
                    item.action.strip(),
                    item.patient.strip() if item.patient else None,
                    item.tone.strip().lower() if item.tone else None,
                    item.clause_text.strip() if item.clause_text else None,
                    item.created_at or now,
                ))
                continue

            ref_input = item[0]
            speech_act = item[1]
            agent = item[2]
            action = item[3]
            patient = item[4] if len(item) > 4 else None
            tone = item[5] if len(item) > 5 else None
            clause = item[6] if len(item) > 6 else None

            ref = parse_reference(ref_input) if isinstance(ref_input, str) else ref_input
            rows.append((
                ref.canonical_start_id,
                ref.format(),
                speech_act.strip().lower(),
                agent.strip(),
                action.strip(),
                patient.strip() if patient else None,
                tone.strip().lower() if tone else None,
                clause.strip() if clause else None,
                now,
            ))

        with self.conn:
            self.conn.executemany(
                """
                INSERT INTO semantic_propositions (
                    canonical_verse_id, human_ref, speech_act, agent, action, patient, tone, clause_text, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        return len(rows)

    def get_semantic_propositions_for_verse(
        self,
        reference: Union[Reference, str],
    ) -> List[SemanticPropositionRecord]:
        """Fetch semantic propositions for a specific verse or range."""
        ref = parse_reference(reference) if isinstance(reference, str) else reference
        start_id = ref.canonical_start_id
        end_id = ref.canonical_end_id

        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT id, canonical_verse_id, human_ref, speech_act, agent, action, patient, tone, clause_text, created_at
            FROM semantic_propositions
            WHERE canonical_verse_id >= ? AND canonical_verse_id <= ?
            ORDER BY canonical_verse_id ASC, id ASC
            """,
            (start_id, end_id),
        )
        rows = cur.fetchall()
        cur.close()
        return [
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
            for r in rows
        ]

    def get_semantic_propositions_by_agent(
        self,
        agent: str,
        limit: int = 100,
    ) -> List[SemanticPropositionRecord]:
        """Fetch propositions by agent (e.g. 'God', 'Jesus', 'Paul')."""
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT id, canonical_verse_id, human_ref, speech_act, agent, action, patient, tone, clause_text, created_at
            FROM semantic_propositions
            WHERE agent = ? COLLATE NOCASE
            ORDER BY canonical_verse_id ASC, id ASC
            LIMIT ?
            """,
            (agent.strip(), limit),
        )
        rows = cur.fetchall()
        cur.close()
        return [
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
            for r in rows
        ]

    def get_semantic_propositions_by_speech_act(
        self,
        speech_act: str,
        limit: int = 100,
    ) -> List[SemanticPropositionRecord]:
        """Fetch propositions by speech act (e.g. 'promise', 'command', 'imperative')."""
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT id, canonical_verse_id, human_ref, speech_act, agent, action, patient, tone, clause_text, created_at
            FROM semantic_propositions
            WHERE speech_act = ? COLLATE NOCASE
            ORDER BY canonical_verse_id ASC, id ASC
            LIMIT ?
            """,
            (speech_act.strip().lower(), limit),
        )
        rows = cur.fetchall()
        cur.close()
        return [
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
            for r in rows
        ]

    def count_semantic_propositions(
        self,
        agent: Optional[str] = None,
        speech_act: Optional[str] = None,
    ) -> int:
        """Count semantic propositions with optional filtering."""
        cur = self.conn.cursor()
        if agent and speech_act:
            cur.execute(
                "SELECT count(*) FROM semantic_propositions WHERE agent = ? COLLATE NOCASE AND speech_act = ? COLLATE NOCASE",
                (agent.strip(), speech_act.strip().lower()),
            )
        elif agent:
            cur.execute("SELECT count(*) FROM semantic_propositions WHERE agent = ? COLLATE NOCASE", (agent.strip(),))
        elif speech_act:
            cur.execute("SELECT count(*) FROM semantic_propositions WHERE speech_act = ? COLLATE NOCASE", (speech_act.strip().lower(),))
        else:
            cur.execute("SELECT count(*) FROM semantic_propositions")
        row = cur.fetchone()
        cur.close()
        return row[0] if row else 0

    def get_all_semantic_propositions(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[SemanticPropositionRecord]:
        """Retrieve all semantic propositions ordered canonically by verse coordinate."""
        cur = self.conn.cursor()
        query = """
            SELECT id, canonical_verse_id, human_ref, speech_act, agent, action, patient, tone, clause_text, created_at
            FROM semantic_propositions
            ORDER BY canonical_verse_id ASC, id ASC
        """
        params: List[Any] = []
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        cur.execute(query, params)
        rows = cur.fetchall()
        cur.close()
        return [
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
            for r in rows
        ]

    def clear_semantic_propositions(self) -> int:
        """Remove all semantic propositions."""
        with self.conn:
            cur = self.conn.execute("DELETE FROM semantic_propositions")
            return cur.rowcount

    # --- Vector Embeddings API (Phase 7 / ADR-042) ---

    def save_verse_embedding(
        self,
        reference: Union[Reference, str],
        model_id: str,
        dimensions: int,
        embedding: bytes,
    ) -> VerseEmbeddingRecord:
        """Save a dense vector embedding as binary bytes for a canonical verse."""
        ref = parse_reference(reference) if isinstance(reference, str) else reference
        vid = ref.canonical_start_id
        human = ref.format()
        now = _utc_now_iso()

        with self.conn:
            self.conn.execute(
                """
                INSERT INTO verse_embeddings (
                    canonical_verse_id, human_ref, model_id, dimensions, embedding, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(canonical_verse_id) DO UPDATE SET
                    model_id=excluded.model_id,
                    dimensions=excluded.dimensions,
                    embedding=excluded.embedding,
                    created_at=excluded.created_at
                """,
                (vid, human, model_id.strip(), dimensions, embedding, now),
            )

        return VerseEmbeddingRecord(
            canonical_verse_id=vid,
            human_ref=human,
            model_id=model_id.strip(),
            dimensions=dimensions,
            embedding=embedding,
            created_at=now,
        )

    def save_verse_embeddings_batch(
        self,
        items: Sequence[Tuple[Union[Reference, str], str, int, bytes]],
    ) -> int:
        """Batch save verse embeddings in a transaction."""
        now = _utc_now_iso()
        rows = []
        for ref_input, model_id, dims, emb in items:
            ref = parse_reference(ref_input) if isinstance(ref_input, str) else ref_input
            rows.append((
                ref.canonical_start_id,
                ref.format(),
                model_id.strip(),
                dims,
                emb,
                now,
            ))

        with self.conn:
            self.conn.executemany(
                """
                INSERT INTO verse_embeddings (
                    canonical_verse_id, human_ref, model_id, dimensions, embedding, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(canonical_verse_id) DO UPDATE SET
                    model_id=excluded.model_id,
                    dimensions=excluded.dimensions,
                    embedding=excluded.embedding,
                    created_at=excluded.created_at
                """,
                rows,
            )
        return len(rows)

    def get_verse_embedding(
        self,
        reference: Union[Reference, str],
    ) -> Optional[VerseEmbeddingRecord]:
        """Fetch vector embedding for a canonical verse."""
        ref = parse_reference(reference) if isinstance(reference, str) else reference
        vid = ref.canonical_start_id

        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT canonical_verse_id, human_ref, model_id, dimensions, embedding, created_at
            FROM verse_embeddings
            WHERE canonical_verse_id = ?
            """,
            (vid,),
        )
        row = cur.fetchone()
        cur.close()
        if not row:
            return None
        return VerseEmbeddingRecord(
            canonical_verse_id=row["canonical_verse_id"],
            human_ref=row["human_ref"],
            model_id=row["model_id"],
            dimensions=row["dimensions"],
            embedding=row["embedding"],
            created_at=row["created_at"],
        )

    def get_all_verse_embeddings(
        self,
        model_id: Optional[str] = None,
    ) -> List[VerseEmbeddingRecord]:
        """Retrieve all stored verse embeddings, optionally filtered by model."""
        cur = self.conn.cursor()
        if model_id:
            cur.execute(
                """
                SELECT canonical_verse_id, human_ref, model_id, dimensions, embedding, created_at
                FROM verse_embeddings
                WHERE model_id = ?
                ORDER BY canonical_verse_id ASC
                """,
                (model_id.strip(),),
            )
        else:
            cur.execute(
                """
                SELECT canonical_verse_id, human_ref, model_id, dimensions, embedding, created_at
                FROM verse_embeddings
                ORDER BY canonical_verse_id ASC
                """
            )
        rows = cur.fetchall()
        cur.close()
        return [
            VerseEmbeddingRecord(
                canonical_verse_id=r["canonical_verse_id"],
                human_ref=r["human_ref"],
                model_id=r["model_id"],
                dimensions=r["dimensions"],
                embedding=r["embedding"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def count_verse_embeddings(self) -> int:
        """Count total stored verse embeddings."""
        cur = self.conn.cursor()
        cur.execute("SELECT count(*) FROM verse_embeddings")
        row = cur.fetchone()
        cur.close()
        return row[0] if row else 0

    def clear_verse_embeddings(self) -> int:
        """Remove all verse embeddings."""
        with self.conn:
            cur = self.conn.execute("DELETE FROM verse_embeddings")
            return cur.rowcount

    def save_pericope_embedding(
        self,
        pericope_id: int,
        reference: Union[Reference, str],
        model_id: str,
        dimensions: int,
        embedding: bytes,
    ) -> PericopeEmbeddingRecord:
        """Save a dense vector embedding as binary bytes for a pericope unit."""
        ref = parse_reference(reference) if isinstance(reference, str) else reference
        s_id = ref.canonical_start_id
        e_id = ref.canonical_end_id
        human = ref.format()
        now = _utc_now_iso()

        with self.conn:
            self.conn.execute(
                """
                INSERT INTO pericope_embeddings (
                    pericope_id, start_canonical_id, end_canonical_id, human_ref, model_id, dimensions, embedding, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(pericope_id) DO UPDATE SET
                    start_canonical_id=excluded.start_canonical_id,
                    end_canonical_id=excluded.end_canonical_id,
                    human_ref=excluded.human_ref,
                    model_id=excluded.model_id,
                    dimensions=excluded.dimensions,
                    embedding=excluded.embedding,
                    created_at=excluded.created_at
                """,
                (pericope_id, s_id, e_id, human, model_id.strip(), dimensions, embedding, now),
            )

        return PericopeEmbeddingRecord(
            pericope_id=pericope_id,
            start_canonical_id=s_id,
            end_canonical_id=e_id,
            human_ref=human,
            model_id=model_id.strip(),
            dimensions=dimensions,
            embedding=embedding,
            created_at=now,
        )

    def save_pericope_embeddings_batch(
        self,
        items: Sequence[Tuple[int, Union[Reference, str], str, int, bytes]],
    ) -> int:
        """Batch save pericope embeddings in a transaction."""
        now = _utc_now_iso()
        rows = []
        for pid, ref_input, model_id, dims, emb in items:
            ref = parse_reference(ref_input) if isinstance(ref_input, str) else ref_input
            rows.append((
                pid,
                ref.canonical_start_id,
                ref.canonical_end_id,
                ref.format(),
                model_id.strip(),
                dims,
                emb,
                now,
            ))

        with self.conn:
            self.conn.executemany(
                """
                INSERT INTO pericope_embeddings (
                    pericope_id, start_canonical_id, end_canonical_id, human_ref, model_id, dimensions, embedding, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(pericope_id) DO UPDATE SET
                    start_canonical_id=excluded.start_canonical_id,
                    end_canonical_id=excluded.end_canonical_id,
                    human_ref=excluded.human_ref,
                    model_id=excluded.model_id,
                    dimensions=excluded.dimensions,
                    embedding=excluded.embedding,
                    created_at=excluded.created_at
                """,
                rows,
            )
        return len(rows)

    def get_pericope_embedding(
        self,
        pericope_id: int,
    ) -> Optional[PericopeEmbeddingRecord]:
        """Fetch vector embedding for a pericope by ID."""
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT pericope_id, start_canonical_id, end_canonical_id, human_ref, model_id, dimensions, embedding, created_at
            FROM pericope_embeddings
            WHERE pericope_id = ?
            """,
            (pericope_id,),
        )
        row = cur.fetchone()
        cur.close()
        if not row:
            return None
        return PericopeEmbeddingRecord(
            pericope_id=row["pericope_id"],
            start_canonical_id=row["start_canonical_id"],
            end_canonical_id=row["end_canonical_id"],
            human_ref=row["human_ref"],
            model_id=row["model_id"],
            dimensions=row["dimensions"],
            embedding=row["embedding"],
            created_at=row["created_at"],
        )

    def get_all_pericope_embeddings(
        self,
        model_id: Optional[str] = None,
    ) -> List[PericopeEmbeddingRecord]:
        """Retrieve all stored pericope embeddings, optionally filtered by model."""
        cur = self.conn.cursor()
        if model_id:
            cur.execute(
                """
                SELECT pericope_id, start_canonical_id, end_canonical_id, human_ref, model_id, dimensions, embedding, created_at
                FROM pericope_embeddings
                WHERE model_id = ?
                ORDER BY pericope_id ASC
                """,
                (model_id.strip(),),
            )
        else:
            cur.execute(
                """
                SELECT pericope_id, start_canonical_id, end_canonical_id, human_ref, model_id, dimensions, embedding, created_at
                FROM pericope_embeddings
                ORDER BY pericope_id ASC
                """
            )
        rows = cur.fetchall()
        cur.close()
        return [
            PericopeEmbeddingRecord(
                pericope_id=r["pericope_id"],
                start_canonical_id=r["start_canonical_id"],
                end_canonical_id=r["end_canonical_id"],
                human_ref=r["human_ref"],
                model_id=r["model_id"],
                dimensions=r["dimensions"],
                embedding=r["embedding"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def count_pericope_embeddings(self) -> int:
        """Count total stored pericope embeddings."""
        cur = self.conn.cursor()
        cur.execute("SELECT count(*) FROM pericope_embeddings")
        row = cur.fetchone()
        cur.close()
        return row[0] if row else 0

    def clear_pericope_embeddings(self) -> int:
        """Remove all pericope embeddings."""
        with self.conn:
            cur = self.conn.execute("DELETE FROM pericope_embeddings")
            return cur.rowcount

    def insert_character_profile(
        self,
        name: str,
        canonical_spans: Optional[str] = None,
        historical_context: Optional[str] = None,
        theological_role: Optional[str] = None,
    ) -> int:
        """Insert or replace a character profile in the database."""
        now = _utc_now_iso()
        with self.conn:
            cur = self.conn.execute(
                """
                INSERT INTO character_profiles (
                    name, canonical_spans, historical_context, theological_role, created_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    canonical_spans = excluded.canonical_spans,
                    historical_context = excluded.historical_context,
                    theological_role = excluded.theological_role
                """,
                (name.strip(), canonical_spans, historical_context, theological_role, now),
            )
            return cur.lastrowid or 0

    def get_character_profile(self, name: str) -> Optional[CharacterProfileRecord]:
        """Fetch character profile by exact name."""
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT id, name, canonical_spans, historical_context, theological_role, created_at
            FROM character_profiles
            WHERE name = ?
            """,
            (name.strip(),),
        )
        row = cur.fetchone()
        cur.close()
        if not row:
            return None
        return CharacterProfileRecord(
            id=row["id"],
            name=row["name"],
            canonical_spans=row["canonical_spans"],
            historical_context=row["historical_context"],
            theological_role=row["theological_role"],
            created_at=row["created_at"],
        )

    def get_all_character_profiles(self) -> List[CharacterProfileRecord]:
        """Fetch all stored character profiles ordered by name."""
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT id, name, canonical_spans, historical_context, theological_role, created_at
            FROM character_profiles
            ORDER BY name ASC
            """
        )
        rows = cur.fetchall()
        cur.close()
        return [
            CharacterProfileRecord(
                id=r["id"],
                name=r["name"],
                canonical_spans=r["canonical_spans"],
                historical_context=r["historical_context"],
                theological_role=r["theological_role"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

