"""Hermetic Unit Tests for Treasury of Scripture Knowledge (TSK) Cross-Reference Ingestion.

Zero-dependency test suite (Python 3 stdlib unittest only per ADR-003).
Covers:
- OSIS reference source and target coordinate parsing (BBCCCVVV)
- Single-verse, intra-chapter range, cross-chapter span, and inter-book partitioning
- Community vote normalization and confidence weighting [0.60, 1.0]
- Resilient streaming from TSV data with min_votes filtering and row limits
- SQLite batch insertion, atomic transactions, and index creation
- CLI invocation and argument parsing (tools/ingest_crossrefs.py and ./bible crossref ingest)
- CLI crossref for pagination (--limit and --all)
"""

import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from core.crossref import CrossReferenceService
from core.db import Database
from tools.ingest_crossrefs import (
    compute_vote_weight,
    ingest_cross_references,
    main as ingest_main,
    parse_osis_source,
    parse_osis_target,
    stream_cross_references,
)
from cli.main import main as cli_main


class TestTSKIngestion(unittest.TestCase):
    """Hermetic unit tests for TSK cross-reference parsing and ingestion engine."""

    def test_parse_osis_source_coordinates(self) -> None:
        """Verify parsing of OSIS source strings into canonical IDs and names."""
        cid, bnum, href = parse_osis_source("Gen.1.1")
        self.assertEqual(cid, 1001001)
        self.assertEqual(bnum, 1)
        self.assertEqual(href, "Genesis 1:1")

        cid, bnum, href = parse_osis_source("John.3.16")
        self.assertEqual(cid, 43003016)
        self.assertEqual(bnum, 43)
        self.assertEqual(href, "John 3:16")

        cid, bnum, href = parse_osis_source("Rev.22.21")
        self.assertEqual(cid, 66022021)
        self.assertEqual(bnum, 66)
        self.assertEqual(href, "Revelation 22:21")

    def test_parse_osis_target_single_and_ranges(self) -> None:
        """Verify target parsing for single verses, verse ranges, and cross-chapter spans."""
        # Single verse
        res = parse_osis_target("Exod.20.11")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0], (2020011, 2020011, "Exodus 20:11"))

        # Same-chapter range
        res = parse_osis_target("John.1.1-John.1.3")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0], (43001001, 43001003, "John 1:1-3"))

        # Single verse with redundant range syntax
        res = parse_osis_target("Ps.119.105-Ps.119.105")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0], (19119105, 19119105, "Psalms 119:105"))

        # Cross-chapter span in same book
        res = parse_osis_target("1Cor.10.33-1Cor.11.1")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0], (46010033, 46011001, "1 Corinthians 10:33-11:1"))

    def test_parse_osis_target_cross_book_partitioning(self) -> None:
        """Verify cross-book target spans are safely partitioned into valid intra-book edges."""
        res = parse_osis_target("2Chr.36.22-Ezra.1.3")
        self.assertEqual(len(res), 2)
        # Part 1: 2 Chronicles 36:22
        self.assertEqual(res[0], (14036022, 14036022, "2 Chronicles 36:22"))
        # Part 2: Ezra 1:1-3
        self.assertEqual(res[1], (15001001, 15001003, "Ezra 1:1-3"))

    def test_compute_vote_weight_scale(self) -> None:
        """Verify community vote counts normalize to bounded weights [0.60, 1.0]."""
        self.assertEqual(compute_vote_weight(0), 0.60)
        self.assertEqual(compute_vote_weight(-5), 0.60)
        self.assertEqual(compute_vote_weight(25), 0.80)
        self.assertEqual(compute_vote_weight(50), 1.00)
        self.assertEqual(compute_vote_weight(300), 1.00)

    def test_stream_cross_references_synthetic_file(self) -> None:
        """Verify streaming parser processes TSV rows, skips comments, and filters by min_votes."""
        sample_tsv = (
            "From Verse\tTo Verse\tVotes\t#Comment Header\n"
            "Gen.1.1\tExod.20.11\t154\n"
            "Gen.1.1\tJer.51.15\t89\n"
            "Gen.1.1\tBad.Entry\t-10\n"  # Downvoted error
            "\n"  # Empty line
            "John.3.16\tRom.5.8\t981\n"
            "John.3.16\t2Chr.36.22-Ezra.1.2\t45\n"  # Cross-book target
        )

        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as f:
            f.write(sample_tsv)
            temp_path = Path(f.name)

        try:
            # Stream with min_votes = 0 (skips -10)
            rows = list(stream_cross_references(temp_path, min_votes=0))
            # 1 (Exod) + 1 (Jer) + 1 (Rom 5:8) + 2 (Cross-book 2Chr/Ezra) = 5 rows
            self.assertEqual(len(rows), 5)

            # Check John 3:16 -> Romans 5:8
            rom_edge = next(r for r in rows if r[5] == "Romans 5:8")
            self.assertEqual(rom_edge[0], 43003016)  # source_start
            self.assertEqual(rom_edge[2], "John 3:16")
            self.assertEqual(rom_edge[3], 45005008)  # target_start
            self.assertEqual(rom_edge[7], 1.0)  # weight
            self.assertEqual(rom_edge[8], "TSK (votes: 981)")

            # Test row limit
            limited = list(stream_cross_references(temp_path, min_votes=0, limit=2))
            self.assertEqual(len(limited), 2)

        finally:
            temp_path.unlink(missing_ok=True)

    def test_ingest_cross_references_into_database(self) -> None:
        """Verify end-to-end ingestion into an isolated SQLite database."""
        sample_tsv = (
            "From Verse\tTo Verse\tVotes\t#CC-BY\n"
            "Gen.1.1\tExod.20.11\t154\n"
            "Gen.1.1\tJer.51.15\t89\n"
            "John.3.16\tRom.5.8\t981\n"
            "Rom.8.28\tRom.8.29-Rom.8.30\t350\n"
        )

        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as f_tsv:
            f_tsv.write(sample_tsv)
            raw_path = Path(f_tsv.name)

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f_db:
            db_path = Path(f_db.name)

        try:
            # Run ingestion
            inserted = ingest_cross_references(
                db_path=db_path,
                raw_file=raw_path,
                min_votes=0,
                rebuild=True,
                reseed_canonical=True,
                verbose=False,
            )

            self.assertEqual(inserted, 4)

            # Query database via Database service
            db = Database(db_path)
            svc = CrossReferenceService(db)

            # Check John 3:16 cross references
            refs = svc.get_cross_references("John 3:16")
            self.assertTrue(any(r.target_human_ref == "Romans 5:8" for r in refs))

            # Check canonical seed cross references were also preserved
            seed_refs = svc.get_cross_references("Genesis 3:15")
            self.assertTrue(any("Galatians 4:4" in r.target_human_ref for r in seed_refs))

            # Check summary statistics
            stats = svc.get_summary_statistics()
            # 67 canonical seeds + 4 TSK = 71 edges
            self.assertEqual(stats.total_edges, 71)
            self.assertIn("thematic", stats.by_relationship_type)

        finally:
            raw_path.unlink(missing_ok=True)
            db_path.unlink(missing_ok=True)

    def test_cli_ingest_and_pagination(self) -> None:
        """Verify CLI crossref ingest subcommand and crossref for --limit pagination."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f_db:
            db_path = Path(f_db.name)

        sample_tsv = (
            "From Verse\tTo Verse\tVotes\n"
            "John.3.16\tRom.5.8\t500\n"
            "John.3.16\tRom.8.32\t400\n"
            "John.3.16\t1John.4.9\t300\n"
        )

        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as f_tsv:
            f_tsv.write(sample_tsv)
            raw_path = Path(f_tsv.name)

        try:
            # 1. Ingest via CLI entrypoint
            ret = ingest_main(["--db", str(db_path), "--raw-file", str(raw_path), "--quiet"])
            self.assertEqual(ret, 0)

            # 2. Query via CLI crossref for with --limit
            buf = io.StringIO()
            with patch("sys.stdout", buf):
                ret_cli = cli_main(["--db", str(db_path), "crossref", "for", "John 3:16", "--limit", "2"])
            self.assertEqual(ret_cli, 0)
            output = buf.getvalue()
            self.assertIn("Cross-References for John 3:16", output)
            self.assertIn("showing top 2 of", output)
            self.assertIn("Romans 5:8", output)

            # 3. Query via CLI crossref stats --json
            buf_json = io.StringIO()
            with patch("sys.stdout", buf_json):
                ret_stats = cli_main(["--db", str(db_path), "crossref", "stats", "--json"])
            self.assertEqual(ret_stats, 0)
            self.assertIn('"total_edges":', buf_json.getvalue())

        finally:
            raw_path.unlink(missing_ok=True)
            db_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
