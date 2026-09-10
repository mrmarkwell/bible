"""Hermetic unit tests for tools/build_vector_db.py.

Tests the batch vector ingestion engine, CLI arguments, checkpoint ledger,
and dry-run/status/compile execution flows (ADR-083).

Zero external dependencies (Python 3 standard library only per ADR-003).
"""

import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from core.db import Database, VerseRecord
from core.reference import parse_reference
from tools.build_vector_db import (
    VectorCheckpointLedger,
    main,
    run_vector_build,
)


class TestBuildVectorDb(unittest.TestCase):
    """Hermetic unit tests for the batch vector compiler tool."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)
        self.db_path = self.tmp_path / "test_bible.db"
        self.db = Database(self.db_path)
        self.db.add_translation("WEB", "World English Bible")

        # Seed sample pericope in Romans (Corpus 1)
        ref = parse_reference("Romans 1:16-17")
        self.pericope = self.db.insert_pericope(
            reference=ref,
            title="The Power of God for Salvation",
            redemptive_summary="The gospel reveals the righteousness of God by faith.",
            genre="Pauline Epistle",
            central_proposition="The righteous shall live by faith.",
        )
        self.db.insert_verse(
            VerseRecord(
                translation_id="WEB",
                book_id=ref.book.number,
                chapter=1,
                verse=16,
                text="For I am not ashamed of the Good News of Christ.",
            )
        )

        # Seed sample pericope in John (Corpus 2)
        ref_john = parse_reference("John 1:1-5")
        self.pericope_john = self.db.insert_pericope(
            reference=ref_john,
            title="The Word Became Flesh",
            redemptive_summary="The eternal Word was in the beginning with God.",
            genre="Gospel",
            central_proposition="In the beginning was the Word, and the Word was God.",
        )
        self.db.insert_verse(
            VerseRecord(
                translation_id="WEB",
                book_id=ref_john.book.number,
                chapter=1,
                verse=1,
                text="In the beginning was the Word, and the Word was with God, and the Word was God.",
            )
        )
        self.ledger = VectorCheckpointLedger(self.db)

    def tearDown(self):
        self.db.close()
        self.tmpdir.cleanup()

    def test_missing_database_error(self):
        missing_db = self.tmp_path / "nonexistent.db"
        out = io.StringIO()
        with patch("sys.stdout", out):
            code = run_vector_build(db_path=missing_db, status_only=True)
        self.assertEqual(code, 1)
        self.assertIn("Database file not found", out.getvalue())

    def test_missing_database_error_json(self):
        missing_db = self.tmp_path / "nonexistent.db"
        out = io.StringIO()
        with patch("sys.stdout", out):
            code = run_vector_build(db_path=missing_db, json_output=True)
        self.assertEqual(code, 1)
        data = json.loads(out.getvalue())
        self.assertIn("Database file not found", data.get("error", ""))

    def test_invalid_book_error(self):
        out = io.StringIO()
        with patch("sys.stdout", out):
            code = run_vector_build(db_path=self.db_path, book_filter="NonExistentBookXYZ")
        self.assertEqual(code, 1)
        self.assertIn("Unknown book", out.getvalue())

    def test_invalid_book_error_json(self):
        out = io.StringIO()
        with patch("sys.stdout", out):
            code = run_vector_build(
                db_path=self.db_path,
                book_filter="NonExistentBookXYZ",
                json_output=True,
            )
        self.assertEqual(code, 1)
        data = json.loads(out.getvalue())
        self.assertIn("Unknown book", data.get("error", ""))

    def test_invalid_corpus_error(self):
        out = io.StringIO()
        with patch("sys.stdout", out):
            code = run_vector_build(db_path=self.db_path, corpus_filter="999")
        self.assertEqual(code, 1)
        self.assertIn("Unknown canonical corpus", out.getvalue())

    def test_clear_ledger(self):
        self.ledger.record_pericope(self.pericope.id, 45, "Romans 1:16-17", 45001016, 45001017)
        out = io.StringIO()
        with patch("sys.stdout", out):
            code = run_vector_build(db_path=self.db_path, clear_ledger=True)
        self.assertEqual(code, 0)
        self.assertIn("Cleared 1 vector checkpoint records", out.getvalue())

    def test_clear_ledger_json(self):
        self.ledger.record_pericope(self.pericope.id, 45, "Romans 1:16-17", 45001016, 45001017)
        out = io.StringIO()
        with patch("sys.stdout", out):
            code = run_vector_build(db_path=self.db_path, clear_ledger=True, json_output=True)
        self.assertEqual(code, 0)
        data = json.loads(out.getvalue())
        self.assertEqual(data.get("cleared_units"), 1)

    def test_reset_failed(self):
        u_id = self.ledger.record_pericope(self.pericope.id, 45, "Romans 1:16-17", 45001016, 45001017)
        self.ledger.mark_failed(u_id, "Rate limit exceeded")
        out = io.StringIO()
        with patch("sys.stdout", out):
            code = run_vector_build(db_path=self.db_path, reset_failed=True)
        self.assertEqual(code, 0)
        self.assertIn("Reset 1 failed vector checkpoint records", out.getvalue())

    def test_status_inspection(self):
        self.ledger.record_pericope(self.pericope.id, 45, "Romans 1:16-17", 45001016, 45001017)
        out = io.StringIO()
        with patch("sys.stdout", out):
            code = run_vector_build(db_path=self.db_path, status_only=True)
        self.assertEqual(code, 0)
        val = out.getvalue()
        self.assertIn("Vector Compilation Ledger Status", val)
        self.assertIn("Total Tracked Units:", val)

    def test_status_inspection_json(self):
        self.ledger.record_pericope(self.pericope.id, 45, "Romans 1:16-17", 45001016, 45001017)
        out = io.StringIO()
        with patch("sys.stdout", out):
            code = run_vector_build(db_path=self.db_path, status_only=True, json_output=True)
        self.assertEqual(code, 0)
        data = json.loads(out.getvalue())
        self.assertIn("ledger_status", data)
        self.assertEqual(data["ledger_status"].get("PENDING"), 1)

    def test_dry_run(self):
        out = io.StringIO()
        with patch("sys.stdout", out):
            code = run_vector_build(db_path=self.db_path, dry_run=True, book_filter="Romans")
        self.assertEqual(code, 0)
        val = out.getvalue()
        self.assertIn("[Dry Run] Prepared 1 pericope units", val)
        self.assertIn("Romans 1:16-17", val)

    def test_dry_run_json(self):
        out = io.StringIO()
        with patch("sys.stdout", out):
            code = run_vector_build(
                db_path=self.db_path,
                dry_run=True,
                book_filter="Romans",
                json_output=True,
            )
        self.assertEqual(code, 0)
        data = json.loads(out.getvalue())
        self.assertTrue(data.get("dry_run"))
        self.assertEqual(data.get("total_units"), 1)

    def test_compilation_execution_and_resumption(self):
        # Run compilation
        out = io.StringIO()
        with patch("sys.stdout", out):
            code = run_vector_build(
                db_path=self.db_path,
                book_filter="Romans",
                resume=True,
            )
        self.assertEqual(code, 0)
        val = out.getvalue()
        self.assertIn("Vector Compilation Summary:", val)
        self.assertIn("Completed:         1", val)

        # Verify record exists in pericope_embeddings table
        cur = self.db.conn.cursor()
        emb_row = cur.execute(
            "SELECT dimensions, LENGTH(embedding) FROM pericope_embeddings WHERE pericope_id = ?",
            (self.pericope.id,),
        ).fetchone()
        self.assertIsNotNone(emb_row)
        self.assertEqual(emb_row[0], 768)
        self.assertEqual(emb_row[1], 768)

        # Run again with resume=True to test skip
        out_resume = io.StringIO()
        with patch("sys.stdout", out_resume):
            code_resume = run_vector_build(
                db_path=self.db_path,
                book_filter="Romans",
                resume=True,
            )
        self.assertEqual(code_resume, 0)
        val_resume = out_resume.getvalue()
        self.assertIn("Skipped (Resume):  1", val_resume)
        self.assertIn("Completed:         0", val_resume)

    def test_cli_main_entry_point(self):
        out = io.StringIO()
        with patch("sys.stdout", out):
            code = main(["--db", str(self.db_path), "--status", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out.getvalue())
        self.assertIn("ledger_status", data)

    def test_compilation_execution_corpus_filter(self):
        # Test compiling with corpus_filter="1"
        out = io.StringIO()
        with patch("sys.stdout", out):
            code = run_vector_build(
                db_path=self.db_path,
                corpus_filter="1",
                resume=False,
            )
        self.assertEqual(code, 0)
        val = out.getvalue()
        self.assertIn("Vector Compilation Summary:", val)
        self.assertIn("Completed:         1", val)

    def test_compilation_execution_corpus_2_filter(self):
        # Test compiling with corpus_filter="2" (Gospels & Acts)
        out = io.StringIO()
        with patch("sys.stdout", out):
            code = run_vector_build(
                db_path=self.db_path,
                corpus_filter="2",
                resume=False,
            )
        self.assertEqual(code, 0)
        val = out.getvalue()
        self.assertIn("Vector Compilation Summary:", val)
        self.assertIn("Completed:         1", val)

        # Verify the John pericope was embedded
        cur = self.db.conn.cursor()
        emb_row = cur.execute(
            "SELECT dimensions, LENGTH(embedding) FROM pericope_embeddings WHERE pericope_id = ?",
            (self.pericope_john.id,),
        ).fetchone()
        self.assertIsNotNone(emb_row)
        self.assertEqual(emb_row[0], 768)
        self.assertEqual(emb_row[1], 768)


if __name__ == "__main__":
    unittest.main()

