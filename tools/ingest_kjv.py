#!/usr/bin/env python3
"""Streaming Ingestion & Compiler Tool for King James Version (KJV).

Zero-dependency script (Python 3 standard library only per ADR-003):
- Ingests all 66 canonical books of the King James Version (1611 / 1769 Blayney Oxford edition).
- Caches raw files locally in data/raw/kjv/ for 100% offline reproducibility.
- Parses chapter and verse JSON objects into complete verses.
- Batch inserts all 31,102 verses into SQLite (data/bible.db) with canonical integer IDs.
- Synchronizes SQLite FTS5 full-text search indexes automatically via triggers.
- Runs PRAGMA optimize and VACUUM to produce a compact, production-ready database pack.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Dict, List, Optional, Sequence, Tuple
import urllib.request

# Add repository root to sys.path so core can be imported from tools/
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.db import Database, VerseRecord
from core.reference import ALL_BOOKS, Book, get_book, verse_canonical_id

RAW_KJV_DIR = REPO_ROOT / "data" / "raw" / "kjv"
DEFAULT_DB_FILE = REPO_ROOT / "data" / "bible.db"

# aruljohn/Bible-kjv raw GitHub base URL
GITHUB_RAW_BASE = (
    "https://raw.githubusercontent.com/aruljohn/Bible-kjv/master"
)


def book_to_filename(book: Book) -> str:
    """Map canonical Book instance to aruljohn KJV JSON filename."""
    if book.name == "Song of Solomon":
        return "SongofSolomon.json"
    clean_name = book.name.replace(" ", "")
    return f"{clean_name}.json"


def fetch_and_cache_book(
    filename: str, cache_dir: Path = RAW_KJV_DIR, force: bool = False
) -> Path:
    """Download a single book JSON if not cached, saving to disk."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    local_path = cache_dir / filename
    if local_path.exists() and not force and local_path.stat().st_size > 0:
        return local_path

    url = f"{GITHUB_RAW_BASE}/{filename}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Bible-Engine-KJV-Ingest/1.0 (Python stdlib)"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        content = resp.read()

    with open(local_path, "wb") as f:
        f.write(content)

    return local_path


def parse_book_json(file_path: Path) -> Dict[Tuple[int, int], str]:
    """Parse KJV book JSON file into map of (chapter, verse) -> verse text."""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    verses: Dict[Tuple[int, int], str] = {}
    chapters = data.get("chapters", []) if isinstance(data, dict) else []

    for chap in chapters:
        if not isinstance(chap, dict):
            continue
        c_val = chap.get("chapter")
        if c_val is None:
            continue
        try:
            c_num = int(c_val)
        except (ValueError, TypeError):
            continue

        raw_verses = chap.get("verses", [])
        if not isinstance(raw_verses, list):
            continue

        for v_item in raw_verses:
            if not isinstance(v_item, dict):
                continue
            v_val = v_item.get("verse")
            text_val = v_item.get("text", "")
            if v_val is not None and text_val:
                try:
                    v_num = int(v_val)
                except (ValueError, TypeError):
                    continue
                # Normalize whitespace while preserving essential punctuation
                cleaned_text = " ".join(str(text_val).split())
                if cleaned_text:
                    verses[(c_num, v_num)] = cleaned_text

    return verses


def ingest_kjv(
    db_path: Path = DEFAULT_DB_FILE,
    raw_dir: Path = RAW_KJV_DIR,
    force_download: bool = False,
    verbose: bool = True,
    books: Optional[Sequence[Book]] = None,
) -> int:
    """Ingest King James Version (KJV) into target SQLite database.

    Args:
        db_path: Destination SQLite database file path.
        raw_dir: Cache directory for downloaded raw JSON files.
        force_download: If True, re-downloads even if already cached locally.
        verbose: If True, prints progress reporting to stdout.
        books: Optional sequence of Book instances to ingest (defaults to all 66 books).

    Returns:
        Total number of verses ingested.
    """
    start_time = time.time()
    db = Database(db_path=db_path, auto_init=True)

    if verbose:
        print("=== Bible Engine: King James Version (KJV) Ingestion ===")
        print(f"Database destination: {db_path}")
        print(f"Raw cache directory:  {raw_dir}")

    # 1. Register KJV Translation Record
    db.add_translation(
        translation_id="KJV",
        name="King James Version",
        language="en",
        is_public_domain=True,
        is_encrypted=False,
        license_notes=(
            "King James Version (1611 / 1769 Blayney Oxford edition). "
            "Public Domain worldwide (Crown copyright in the UK applies only to commercial printing)."
        ),
    )

    all_verse_records: List[VerseRecord] = []
    target_books = list(books) if books is not None else list(ALL_BOOKS)
    total_books = len(target_books)

    for idx, book in enumerate(target_books, start=1):
        fn = book_to_filename(book)
        if verbose:
            print(
                f"[{idx:02d}/{total_books:02d}] Processing {book.name} ({fn})...",
                end=" ",
                flush=True,
            )

        local_file = fetch_and_cache_book(fn, cache_dir=raw_dir, force=force_download)
        parsed_verses = parse_book_json(local_file)

        book_records: List[VerseRecord] = []
        for (ch, vs), text in parsed_verses.items():
            cid = verse_canonical_id(book, ch, vs)
            book_records.append(
                VerseRecord(
                    translation_id="KJV",
                    book_id=book.number,
                    chapter=ch,
                    verse=vs,
                    text=text,
                    canonical_verse_id=cid,
                )
            )

        all_verse_records.extend(book_records)
        if verbose:
            print(f"{len(book_records)} verses")

    # 2. Batch Insert All Verses in Atomic Transaction
    if verbose:
        print(f"Inserting {len(all_verse_records):,} total verses into database...")

    inserted_count = db.insert_verses(all_verse_records)

    # 3. Compact and Optimize Database
    if verbose:
        print("Compacting and optimizing SQLite FTS5 index (PRAGMA optimize & VACUUM)...")
    db.optimize()
    db.conn.commit()
    db.vacuum()
    db.close()

    elapsed = time.time() - start_time
    if verbose:
        print(
            f"Ingestion complete: {inserted_count:,} KJV verses compiled in {elapsed:.2f}s."
        )

    return inserted_count


def main(argv: Optional[List[str]] = None) -> int:
    """Command-line interface for KJV ingestion."""
    parser = argparse.ArgumentParser(
        prog="tools/ingest_kjv.py",
        description="Ingest King James Version (KJV) into SQLite with FTS5 search index.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_FILE,
        help=f"Target SQLite database path (default: {DEFAULT_DB_FILE})",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=RAW_KJV_DIR,
        help=f"Directory for cached raw JSON files (default: {RAW_KJV_DIR})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-download of raw JSON files even if cached locally",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Quiet mode: suppress progress output",
    )
    parser.add_argument(
        "--books",
        type=str,
        help="Comma-separated list of book names or numbers to ingest (e.g. 'Genesis,John,Romans')",
    )

    args = parser.parse_args(argv)

    books_to_ingest: Optional[List[Book]] = None
    if args.books:
        books_to_ingest = []
        for raw_b in args.books.split(","):
            token = raw_b.strip()
            if not token:
                continue
            b = get_book(token)
            if b:
                books_to_ingest.append(b)
            else:
                sys.stderr.write(f"Warning: Unknown book '{token}' ignored.\n")

    ingest_kjv(
        db_path=args.db,
        raw_dir=args.raw_dir,
        force_download=args.force,
        verbose=not args.quiet,
        books=books_to_ingest,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
