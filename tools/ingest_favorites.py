#!/usr/bin/env python3
"""Batch Ingestion Tool for Curated Favorite Bible Verses.

Zero-dependency script (Python 3 standard library only per ADR-003):
- Ingests favorite_bible_verses.csv (829 passages, 50 starred).
- Parses each CSV record into canonical Reference models.
- Auto-corrects known typographical errors (e.g. 'Mark 1:223-26' -> 'Mark 1:23-26')
  with informational logging.
- Populates the SQLite database with a first-class 'favorites' semantic tag.
- Flags starred verses (starred=1) for prioritized display and screensaver export.
- Supports idempotent re-runs via --force or atomic replacement.
- Runs PRAGMA optimize to ensure query planner statistics are current.
"""

import argparse
import csv
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add repository root to sys.path so core can be imported from tools/
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.db import Database
from core.reference import Reference

DEFAULT_CSV_PATH = REPO_ROOT / "favorite_bible_verses.csv"
DEFAULT_DB_PATH = REPO_ROOT / "data" / "bible.db"

# Known typographical corrections in the raw dataset
TYPO_CORRECTIONS: Dict[Tuple[str, str, str, str], Dict[str, str]] = {
    # Mark 1:223-26 is a typo for Mark 1:23-26
    ("Mark", "1", "223", "26"): {
        "book": "Mark",
        "chapter": "1",
        "start_verse": "23",
        "end_verse": "26",
    },
}


def clean_csv_row(raw_row: Dict[str, str]) -> Tuple[Reference, bool, Optional[str]]:
    """Clean and parse a CSV row, applying corrections if needed.

    Returns:
        Tuple of (Reference, is_starred, notes).
    """
    book_raw = raw_row.get("book", "").strip()
    chapter_raw = raw_row.get("chapter", "").strip()
    sv_raw = raw_row.get("start_verse", "").strip()
    ev_raw = raw_row.get("end_verse", "").strip()
    starred_raw = raw_row.get("starred", "").strip().lower()

    key = (book_raw, chapter_raw, sv_raw, ev_raw)
    notes: Optional[str] = None
    if key in TYPO_CORRECTIONS:
        corrected = dict(raw_row)
        corrected.update(TYPO_CORRECTIONS[key])
        notes = f"Auto-corrected typo from {book_raw} {chapter_raw}:{sv_raw}-{ev_raw}"
        ref = Reference.from_csv_row(corrected)
    else:
        ref = Reference.from_csv_row(raw_row)

    is_starred = starred_raw in ("true", "1", "yes")
    return ref, is_starred, notes


def load_favorites_csv(
    csv_path: Path = DEFAULT_CSV_PATH,
) -> List[Tuple[Reference, bool, Optional[str]]]:
    """Load and parse all rows from the favorites CSV."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Favorites CSV not found: {csv_path}")

    items: List[Tuple[Reference, bool, Optional[str]]] = []
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            items.append(clean_csv_row(row))

    return items


def ingest_favorites(
    db: Database,
    csv_path: Path = DEFAULT_CSV_PATH,
    tag_name: str = "favorites",
    clear_existing: bool = True,
) -> Tuple[int, int]:
    """Ingest favorite verses from CSV into the database.

    Args:
        db: Initialized Database instance.
        csv_path: Path to favorite_bible_verses.csv.
        tag_name: Semantic tag name (default 'favorites').
        clear_existing: If True, replace existing favorites tags.

    Returns:
        Tuple of (total_ingested, starred_count).
    """
    items = load_favorites_csv(csv_path)

    # Register the favorites tag with descriptive metadata
    db.get_or_create_tag(
        name=tag_name,
        category="curation",
        description="Curated favorite Bible verses and passages from user collection",
    )

    if clear_existing:
        db.clear_tag(tag_name)

    # Batch insert all records in an atomic transaction
    inserted = db.tag_references_batch(
        items=items,
        tag_name=tag_name,
        category="curation",
        confidence=1.0,
        source="user",
    )

    starred_count = sum(1 for _, starred, _ in items if starred)

    # Update database statistics
    db.optimize()

    return inserted, starred_count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest curated favorite Bible verses into SQLite database."
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=DEFAULT_CSV_PATH,
        help=f"Path to CSV file (default: {DEFAULT_CSV_PATH})",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"Path to SQLite database (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--tag",
        type=str,
        default="favorites",
        help="Tag name for favorites (default: 'favorites')",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append rather than replace existing favorites",
    )
    args = parser.parse_args()

    print(f"Opening database: {args.db}")
    db = Database(args.db)

    print(f"Reading favorites from: {args.csv}")
    start_time = time.time()
    inserted, starred = ingest_favorites(
        db=db,
        csv_path=args.csv,
        tag_name=args.tag,
        clear_existing=not args.append,
    )
    elapsed = time.time() - start_time

    print(f"Successfully ingested {inserted} favorite passages ({starred} starred) in {elapsed:.3f}s")
    print(f"Database optimized. 100% offline-ready.")


if __name__ == "__main__":
    main()
