#!/usr/bin/env python3
"""Zero-Dependency Scripture Cross-Reference Knowledge Graph Ingestion Tool.

Ingests Whole-Bible Cross-References (~340,000 canonical edges from the
Treasury of Scripture Knowledge - TSK and OpenBible.info) into SQLite (data/bible.db).

Key Capabilities:
- Zero external dependencies (Python 3 standard library only per ADR-003).
- Parses OSIS Scripture references across all 66 canonical books into integer IDs (BBCCCVVV).
- Handles single-verse targets, intra-chapter ranges, cross-chapter spans, and splits
  rare inter-book ranges into valid intra-book edges.
- Normalizes community vote counts into confidence weights in [0.60, 1.0].
- Preserves high-theology canonical seed edges (typology, prophecy_fulfillment, quotation).
- Batch inserts hundreds of thousands of edges in <3 seconds using transactions.
- Provides CLI commands and programmatic APIs for cold-start and scheduled ingestion.
"""

from __future__ import annotations

import argparse
import io
from pathlib import Path
import sqlite3
import sys
import time
from typing import Dict, Generator, List, Optional, Tuple
import urllib.request
import zipfile

# Add repository root to sys.path so core modules can be imported
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.crossref import (
    CrossReferenceService,
    RelationshipType,
)
from core.db import Database
from core.reference import ALL_BOOKS, Book

DEFAULT_RAW_FILE = REPO_ROOT / "data" / "raw" / "cross_references" / "cross_references.txt"
DEFAULT_DB_FILE = REPO_ROOT / "data" / "bible.db"
OPENBIBLE_ZIP_URL = "https://a.openbible.info/data/cross-references.zip"

# Pre-compute OSIS abbreviation lookup table for all 66 books
OSIS_TO_BOOK: Dict[str, Book] = {b.osis: b for b in ALL_BOOKS}


def ensure_raw_dataset(
    raw_file: Path = DEFAULT_RAW_FILE,
    force_download: bool = False,
    verbose: bool = True,
) -> Path:
    """Ensure raw cross_references dataset file is available locally."""
    if raw_file.exists() and not force_download and raw_file.stat().st_size > 0:
        return raw_file

    # Check for zip file in same directory
    zip_path = raw_file.parent / "cross_references.zip"
    if zip_path.exists() and not force_download and zip_path.stat().st_size > 0:
        if verbose:
            print(f"Extracting {zip_path.name} to {raw_file}...")
        with zipfile.ZipFile(zip_path, "r") as z:
            txt_data = z.read("cross_references.txt")
            raw_file.parent.mkdir(parents=True, exist_ok=True)
            with open(raw_file, "wb") as f:
                f.write(txt_data)
        return raw_file

    # Download from remote URL
    if verbose:
        print(f"Downloading TSK cross-reference dataset from {OPENBIBLE_ZIP_URL}...")
    raw_file.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(
        OPENBIBLE_ZIP_URL,
        headers={"User-Agent": "Bible-Engine-TSK-Ingest/1.0 (Python stdlib)"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        zip_bytes = resp.read()

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        txt_data = z.read("cross_references.txt")
        with open(raw_file, "wb") as f:
            f.write(txt_data)

    if verbose:
        print(f"Cached {len(txt_data):,} bytes to {raw_file}.")
    return raw_file


def parse_osis_source(src: str) -> Tuple[int, int, str]:
    """Parse single-verse OSIS citation (e.g. 'Gen.1.1').

    Returns:
        (canonical_id, book_number, human_ref)
    """
    b_str, c_str, v_str = src.split(".")
    b = OSIS_TO_BOOK[b_str]
    c = int(c_str)
    v = int(v_str)
    cid = b.number * 1_000_000 + c * 1_000 + v
    href = f"{b.name} {c}:{v}"
    return cid, b.number, href


def parse_osis_target(tgt: str) -> List[Tuple[int, int, str]]:
    """Parse target OSIS citation or range (e.g. 'Exod.20.11' or 'John.1.1-John.1.3').

    Returns list of (start_canonical_id, end_canonical_id, human_ref).
    Inter-book spans (rare) are partitioned into separate intra-book edges.
    """
    if "-" in tgt:
        p1, p2 = tgt.split("-")
        b1_str, c1_str, v1_str = p1.split(".")
        b2_str, c2_str, v2_str = p2.split(".")
        b1, c1, v1 = OSIS_TO_BOOK[b1_str], int(c1_str), int(v1_str)
        b2, c2, v2 = OSIS_TO_BOOK[b2_str], int(c2_str), int(v2_str)

        if b1 != b2:
            # Cross-book span: partition into two valid intra-book edges
            start1 = b1.number * 1_000_000 + c1 * 1_000 + v1
            end1 = start1
            href1 = f"{b1.name} {c1}:{v1}"

            start2 = b2.number * 1_000_000 + c2 * 1_000 + 1
            end2 = b2.number * 1_000_000 + c2 * 1_000 + v2
            href2 = f"{b2.name} {c2}:1-{v2}" if v2 > 1 else f"{b2.name} {c2}:{v2}"

            return [(start1, end1, href1), (start2, end2, href2)]
        else:
            start_id = b1.number * 1_000_000 + c1 * 1_000 + v1
            end_id = b1.number * 1_000_000 + c2 * 1_000 + v2
            if c1 == c2:
                href = f"{b1.name} {c1}:{v1}-{v2}" if v1 != v2 else f"{b1.name} {c1}:{v1}"
            else:
                href = f"{b1.name} {c1}:{v1}-{c2}:{v2}"
            return [(start_id, end_id, href)]
    else:
        b_str, c_str, v_str = tgt.split(".")
        b = OSIS_TO_BOOK[b_str]
        c = int(c_str)
        v = int(v_str)
        cid = b.number * 1_000_000 + c * 1_000 + v
        href = f"{b.name} {c}:{v}"
        return [(cid, cid, href)]


def compute_vote_weight(votes: int) -> float:
    """Normalize community vote count into confidence weight in [0.60, 1.0]."""
    if votes <= 0:
        return 0.60
    return round(min(1.0, 0.60 + min(0.40, (votes / 50.0) * 0.40)), 2)


def stream_cross_references(
    raw_file: Path,
    min_votes: int = 0,
    limit: Optional[int] = None,
) -> Generator[Tuple[int, int, str, int, int, str, str, float, str], None, None]:
    """Yield parsed tuple rows ready for SQLite insertion."""
    count = 0
    with open(raw_file, "r", encoding="utf-8") as f:
        # Skip header
        f.readline()
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue

            src_str = parts[0].strip()
            tgt_str = parts[1].strip()
            votes = int(parts[2].strip()) if len(parts) >= 3 and parts[2].strip().lstrip("-").isdigit() else 0

            if votes < min_votes:
                continue

            try:
                s_id, _, s_href = parse_osis_source(src_str)
                targets = parse_osis_target(tgt_str)
            except Exception:
                continue

            weight = compute_vote_weight(votes)
            notes = f"TSK (votes: {votes})"

            for t_start, t_end, t_href in targets:
                yield (
                    s_id,
                    s_id,
                    s_href,
                    t_start,
                    t_end,
                    t_href,
                    RelationshipType.THEMATIC,
                    weight,
                    notes,
                )
                count += 1
                if limit is not None and count >= limit:
                    return


def ensure_cross_reference_indexes(conn: sqlite3.Connection) -> None:
    """Create optimal indexes for fast cross-reference queries."""
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cross_ref_source ON cross_references(source_start_id, source_end_id);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cross_ref_target ON cross_references(target_start_id, target_end_id);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cross_ref_type ON cross_references(relationship_type);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cross_ref_weight ON cross_references(weight);")


def ingest_cross_references(
    db_path: Path = DEFAULT_DB_FILE,
    raw_file: Optional[Path] = None,
    min_votes: int = 0,
    batch_size: int = 50000,
    rebuild: bool = False,
    limit: Optional[int] = None,
    reseed_canonical: bool = True,
    force_download: bool = False,
    verbose: bool = True,
) -> int:
    """Ingest Treasury of Scripture Knowledge (TSK) cross-references into SQLite.

    Args:
        db_path: Path to target SQLite database.
        raw_file: Path to raw dataset file (defaults to data/raw/cross_references/cross_references.txt).
        min_votes: Minimum community vote threshold (default 0 to exclude downvoted errors).
        batch_size: Insert batch chunk size.
        rebuild: If True, clear existing TSK cross-references before ingesting.
        limit: Optional maximum number of records to ingest (for testing).
        reseed_canonical: If True, ensure canonical high-theology seed edges are preserved.
        force_download: If True, force re-download of raw zip from OpenBible.info.
        verbose: If True, print progress telemetry.

    Returns:
        Number of cross-reference records inserted.
    """
    start_time = time.time()
    raw_path = raw_file or DEFAULT_RAW_FILE
    ensure_raw_dataset(raw_path, force_download=force_download, verbose=verbose)

    db = Database(db_path=db_path, auto_init=True)

    if verbose:
        print("=== Bible Engine: Treasury of Scripture Knowledge (TSK) Ingestion ===")
        print(f"Database destination: {db_path}")
        print(f"Raw dataset source:   {raw_path}")
        print(f"Minimum vote threshold: {min_votes}")

    conn = db.conn
    with conn:
        if rebuild:
            if verbose:
                print("Clearing existing cross-reference edges...")
            conn.execute("DELETE FROM cross_references")

        # Ingest Canonical Seed Cross-References first if requested
        if reseed_canonical:
            xr_service = CrossReferenceService(db)
            seeded = xr_service.seed_canonical_cross_references()
            if verbose and seeded > 0:
                print(f"Seeded {seeded} high-theology canonical cross-reference edges.")

    # Batch insert TSK edges
    insert_sql = """
        INSERT INTO cross_references (
            source_start_id, source_end_id, source_human_ref,
            target_start_id, target_end_id, target_human_ref,
            relationship_type, weight, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    total_inserted = 0
    batch: List[Tuple[int, int, str, int, int, str, str, float, str]] = []

    if verbose:
        print("Streaming and compiling cross-reference edges...")

    for row in stream_cross_references(raw_path, min_votes=min_votes, limit=limit):
        batch.append(row)
        if len(batch) >= batch_size:
            with conn:
                conn.executemany(insert_sql, batch)
            total_inserted += len(batch)
            if verbose:
                print(f"  Compiled {total_inserted:,} cross-reference edges...")
            batch = []

    if batch:
        with conn:
            conn.executemany(insert_sql, batch)
        total_inserted += len(batch)

    # Build and verify indexes
    if verbose:
        print("Optimizing SQLite cross-reference index structures...")
    with conn:
        ensure_cross_reference_indexes(conn)
        conn.execute("PRAGMA optimize;")

    elapsed = time.time() - start_time
    if verbose:
        print(f"Ingestion complete: {total_inserted:,} cross-references compiled in {elapsed:.2f}s.")

    return total_inserted


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point for cross-reference ingestion."""
    parser = argparse.ArgumentParser(
        prog="tools/ingest_crossrefs.py",
        description="Ingest Whole-Bible Treasury of Scripture Knowledge (TSK) Cross-References into SQLite.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_FILE,
        help=f"Target SQLite database path (default: {DEFAULT_DB_FILE})",
    )
    parser.add_argument(
        "--raw-file",
        type=Path,
        default=DEFAULT_RAW_FILE,
        help=f"Path to raw cross_references.txt file (default: {DEFAULT_RAW_FILE})",
    )
    parser.add_argument(
        "--min-votes",
        type=int,
        default=0,
        help="Minimum community vote threshold (default: 0 to exclude downvoted entries)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50000,
        help="Batch insert chunk size (default: 50,000)",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Clear existing cross-reference table before ingesting",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit total records ingested (useful for quick testing)",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Force re-download of cross-reference dataset from OpenBible.info",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Quiet mode: suppress progress output",
    )

    args = parser.parse_args(argv)

    ingest_cross_references(
        db_path=args.db,
        raw_file=args.raw_file,
        min_votes=args.min_votes,
        batch_size=args.batch_size,
        rebuild=args.rebuild,
        limit=args.limit,
        force_download=args.download,
        verbose=not args.quiet,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
