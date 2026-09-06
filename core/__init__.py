"""Bible Engine Core Library (Zero External Dependencies)."""

from core.db import (
    DEFAULT_DB_PATH,
    CrossReferenceRecord,
    Database,
    SearchResult,
    SpanRecord,
    TagRecord,
    TranslationRecord,
    VerseRecord,
    VerseTagRecord,
    sanitize_fts_query,
)
from core.reference import (
    ALL_BOOKS,
    BOOKS,
    Book,
    Reference,
    canonical_id_to_triple,
    get_book,
    parse_reference,
    parse_references,
    verse_canonical_id,
)

__all__ = [
    # Reference
    "Book",
    "Reference",
    "get_book",
    "parse_reference",
    "parse_references",
    "verse_canonical_id",
    "canonical_id_to_triple",
    "BOOKS",
    "ALL_BOOKS",
    # Database
    "Database",
    "DEFAULT_DB_PATH",
    "VerseRecord",
    "TranslationRecord",
    "SpanRecord",
    "TagRecord",
    "VerseTagRecord",
    "CrossReferenceRecord",
    "SearchResult",
    "sanitize_fts_query",
]
