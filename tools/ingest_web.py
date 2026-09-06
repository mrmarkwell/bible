#!/usr/bin/env python3
"""Streaming Ingestion & Compiler Tool for World English Bible (WEB).

Zero-dependency script (Python 3 standard library only per ADR-003):
- Downloads all 66 canonical books of the World English Bible in structured JSON format.
- Caches raw files locally in data/raw/web/ for 100% offline reproducibility.
- Parses paragraph and poetic line text into complete verses.
- Batch inserts all ~31,102 verses into SQLite (data/bible.db) with canonical integer IDs.
- Synchronizes SQLite FTS5 full-text search indexes automatically via triggers.
- Runs PRAGMA optimize and VACUUM to produce a compact, production-ready database pack.
"""

from collections import defaultdict
import json
import sys
from pathlib import Path

# Add repository root to sys.path so core can be imported from tools/
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import time
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from core.db import Database, TranslationRecord, VerseRecord
from core.reference import ALL_BOOKS, Book, BOOKS, get_book, verse_canonical_id

RAW_WEB_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "web"
DEFAULT_DB_FILE = Path(__file__).resolve().parent.parent / "data" / "bible.db"

# TehShrike/world-english-bible raw GitHub base URL
GITHUB_RAW_BASE = (
    "https://raw.githubusercontent.com/TehShrike/world-english-bible/master/json"
)


def book_to_filename(book: Book) -> str:
    """Map canonical Book instance to TehShrike JSON filename."""
    name_clean = book.name.lower().replace(" ", "")
    return f"{name_clean}.json"


def fetch_and_cache_book(
    filename: str, cache_dir: Path = RAW_WEB_DIR, force: bool = False
) -> Path:
    """Download a single book JSON if not cached, saving to disk."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    local_path = cache_dir / filename
    if local_path.exists() and not force and local_path.stat().st_size > 0:
        return local_path

    url = f"{GITHUB_RAW_BASE}/{filename}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Bible-Engine-Ingest/1.0 (Python stdlib)"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        content = resp.read()

    with open(local_path, "wb") as f:
        f.write(content)

    return local_path


def parse_book_json(file_path: Path) -> Dict[Tuple[int, int], str]:
    """Parse TehShrike book JSON file into map of (chapter, verse) -> verse text."""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    verse_parts: Dict[Tuple[int, int], List[str]] = defaultdict(list)

    for item in data:
        if not isinstance(item, dict):
            continue
        c = item.get("chapterNumber")
        v = item.get("verseNumber")
        val = item.get("value")
        if c is not None and v is not None and val:
            verse_parts[(int(c), int(v))].append(str(val))

    verses: Dict[Tuple[int, int], str] = {}
    for (ch, vs), parts in sorted(verse_parts.items()):
        # Normalize whitespace while preserving essential punctuation
        raw_text = "".join(parts)
        cleaned_text = " ".join(raw_text.split())
        verses[(ch, vs)] = cleaned_text

    return verses


def ingest_web(
    db_path: Path = DEFAULT_DB_FILE,
    raw_dir: Path = RAW_WEB_DIR,
    force_download: bool = False,
    verbose: bool = True,
) -> int:
    """Ingest full World English Bible (WEB) into target SQLite database.

    Args:
        db_path: Destination SQLite database file path.
        raw_dir: Cache directory for downloaded raw JSON files.
        force_download: If True, re-downloads even if already cached locally.
        verbose: If True, prints progress reporting to stdout.

    Returns:
        Total number of verses ingested.
    """
    start_time = time.time()
    db = Database(db_path=db_path, auto_init=True)

    if verbose:
        print(f"=== Bible Engine: World English Bible (WEB) Ingestion ===")
        print(f"Database destination: {db_path}")
        print(f"Raw cache directory:  {raw_dir}")

    # 1. Register WEB Translation Record
    db.add_translation(
        translation_id="WEB",
        name="World English Bible",
        language="en",
        is_public_domain=True,
        is_encrypted=False,
        license_notes=(
            "World English Bible (WEB) is 100% Dedicated to the Public Domain "
            "by Rainbow Missions, Inc."
        ),
    )

    all_verse_records: List[VerseRecord] = []
    total_books = len(ALL_BOOKS)

    for idx, book in enumerate(ALL_BOOKS, start=1):
        fn = book_to_filename(book)
        if verbose:
            print(f"[{idx:02d}/{total_books:02d}] Processing {book.name} ({fn})...", end=" ", flush=True)

        local_file = fetch_and_cache_book(fn, cache_dir=raw_dir, force=force_download)
        parsed_verses = parse_book_json(local_file)

        book_records: List[VerseRecord] = []
        for (ch, vs), text in parsed_verses.items():
            cid = verse_canonical_id(book, ch, vs)
            book_records.append(
                VerseRecord(
                    translation_id="WEB",
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
        print(f"Ingestion complete: {inserted_count:,} verses compiled in {elapsed:.2f}s.")

    return inserted_count


if __name__ == "__main__":
    db_arg = DEFAULT_DB_FILE
    if len(sys.argv) > 1:
        db_arg = Path(sys.argv[1])
    ingest_web(db_path=db_arg)
