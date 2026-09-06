"""Bible Engine Core Library (Zero External Dependencies)."""

from core.reference import (
    Book,
    Reference,
    get_book,
    parse_reference,
    parse_references,
    BOOKS,
    ALL_BOOKS,
)

__all__ = [
    "Book",
    "Reference",
    "get_book",
    "parse_reference",
    "parse_references",
    "BOOKS",
    "ALL_BOOKS",
]
