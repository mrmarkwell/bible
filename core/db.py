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
from pathlib import Path
import re
import sqlite3
from typing import Any, Dict, Generator, Iterable, List, Optional, Sequence, Tuple, Union

from core.reference import (
    ALL_BOOKS,
    BOOKS,
    Book,
    Reference,
    get_book,
    parse_reference,
    verse_canonical_id,
    canonical_id_to_triple,
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

-- Forward-compatible Phase 7 tables for theological knowledge graph
CREATE TABLE IF NOT EXISTS pericopes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL,
    start_canonical_id INTEGER NOT NULL,
    end_canonical_id INTEGER NOT NULL,
    human_ref TEXT NOT NULL,
    title TEXT NOT NULL,
    redemptive_summary TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE RESTRICT
);

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
    ) -> None:
        """Initialize database manager.

        Args:
            db_path: Path to SQLite file or ":memory:".
            auto_init: If True, automatically initialize schema and books catalog.
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
        )
        self.conn.row_factory = sqlite3.Row

        # Optimize SQLite performance for analytical reads and concurrent writes
        self._configure_pragmas()

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
        if self.conn:
            self.conn.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

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
        self.conn.commit()
        cur.close()

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

    # --- Full-Text Search (FTS5) ---

    def search_text(
        self,
        query: str,
        translation_id: Optional[str] = None,
        book: Optional[Union[Book, str, int]] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[SearchResult]:
        """Perform full-text search across scripture text using SQLite FTS5.

        Args:
            query: User search text or exact phrase.
            translation_id: Optional translation filter (e.g. 'WEB').
            book: Optional book filter.
            limit: Maximum result rows.
            offset: Result offset for pagination.

        Returns:
            List of SearchResult matching query ordered by relevance.
        """
        sanitized = sanitize_fts_query(query)
        if not sanitized:
            return []

        conditions = ["verses_fts MATCH ?"]
        params: List[Any] = [sanitized]

        if translation_id:
            conditions.append("f.translation_id = ?")
            params.append(translation_id.strip().upper())

        if book:
            b = get_book(book)
            if b:
                conditions.append("v.book_id = ?")
                params.append(b.number)

        where_clause = " AND ".join(conditions)

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
            ORDER BY f.rank
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
        """Register a new semantic tag definition."""
        clean_name = name.strip()
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
        """Retrieve tag record by name (case-insensitive)."""
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM tags WHERE name = ? COLLATE NOCASE", (name.strip(),))
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
        existing = self.get_tag(name)
        if existing:
            return existing
        return self.add_tag(name, category, description)

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
    ) -> VerseTagRecord:
        """Attach a semantic tag to an individual verse, span, or chapter."""
        ref = parse_reference(reference) if isinstance(reference, str) else reference
        tag = self.get_or_create_tag(tag_name, category=category)
        assert tag.id is not None

        start_id = ref.canonical_start_id
        end_id = ref.canonical_end_id
        human = ref.format()
        now = _utc_now_iso()

        with self.conn:
            cur = self.conn.execute(
                """
                INSERT INTO verse_tags (
                    tag_id, start_canonical_id, end_canonical_id, human_ref,
                    confidence, source, starred, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tag.id,
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
            created_at=now,
        )

    def get_tags_for_reference(
        self,
        reference: Union[Reference, str],
    ) -> List[VerseTagRecord]:
        """Fetch all tags whose range overlaps with the given reference."""
        ref = parse_reference(reference) if isinstance(reference, str) else reference
        start_id = ref.canonical_start_id
        end_id = ref.canonical_end_id

        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT vt.*, t.name as tag_name
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
                SELECT vt.*, t.name as tag_name
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
                SELECT vt.*, t.name as tag_name
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
            )
            for r in rows
        ]

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

    def get_cross_references(
        self,
        reference: Union[Reference, str],
        bidirectional: bool = True,
    ) -> List[CrossReferenceRecord]:
        """Find all cross-references connected to the given reference."""
        ref = parse_reference(reference) if isinstance(reference, str) else reference
        start_id = ref.canonical_start_id
        end_id = ref.canonical_end_id

        cur = self.conn.cursor()
        if bidirectional:
            cur.execute(
                """
                SELECT * FROM cross_references
                WHERE (source_start_id <= ? AND source_end_id >= ?)
                   OR (target_start_id <= ? AND target_end_id >= ?)
                ORDER BY weight DESC, id ASC
                """,
                (end_id, start_id, end_id, start_id),
            )
        else:
            cur.execute(
                """
                SELECT * FROM cross_references
                WHERE (source_start_id <= ? AND source_end_id >= ?)
                ORDER BY weight DESC, id ASC
                """,
                (end_id, start_id),
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
