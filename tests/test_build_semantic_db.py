"""Hermetic unit tests for tools/build_semantic_db.py.

Zero external dependencies (Python 3 standard library only per ADR-003).
"""

import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from core.db import Database, DEFAULT_DB_PATH
from core.reference import parse_reference
from core.semantic_compiler import (
    CompilationProgress,
    CompilationUnit,
    SemanticCheckpointLedger,
)
from tools.build_semantic_db import main, run_semantic_build


def _create_sample_unit(unit_id: str = "unit-1") -> CompilationUnit:
    ref = parse_reference("Romans 1:1-7")
    return CompilationUnit(
        unit_id=unit_id,
        reference=ref,
        book=ref.book,
        passage_text="Paul, a servant of Christ Jesus...",
        title="Paul's Greeting to Rome",
    )


class TestBuildSemanticDb(unittest.TestCase):
    """Hermetic unit tests for the batch semantic compilation tool."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)
        self.db_path = self.tmp_path / "test_bible.db"
        self.db = Database(self.db_path)
        self.ledger = SemanticCheckpointLedger(self.db)

    def tearDown(self):
        if hasattr(self, "db") and self.db:
            self.db.close()
        self.tmpdir.cleanup()

    def test_missing_database_error(self):
        missing_db = self.tmp_path / "nonexistent.db"
        out = io.StringIO()
        with patch("sys.stdout", out):
            code = run_semantic_build(db_path=missing_db, status_only=True)
        self.assertEqual(code, 1)
        self.assertIn("Database file not found", out.getvalue())

    def test_missing_database_error_json(self):
        missing_db = self.tmp_path / "nonexistent.db"
        out = io.StringIO()
        with patch("sys.stdout", out):
            code = run_semantic_build(db_path=missing_db, json_output=True)
        self.assertEqual(code, 1)
        data = json.loads(out.getvalue())
        self.assertIn("Database file not found", data.get("error", ""))

    def test_invalid_book_error(self):
        out = io.StringIO()
        with patch("sys.stdout", out):
            code = run_semantic_build(db_path=self.db_path, book_filter="NonExistentBookXYZ")
        self.assertEqual(code, 1)
        self.assertIn("Unknown book", out.getvalue())

    def test_invalid_book_error_json(self):
        out = io.StringIO()
        with patch("sys.stdout", out):
            code = run_semantic_build(
                db_path=self.db_path,
                book_filter="NonExistentBookXYZ",
                json_output=True,
            )
        self.assertEqual(code, 1)
        data = json.loads(out.getvalue())
        self.assertIn("Unknown book", data.get("error", ""))

    def test_clear_ledger(self):
        unit = _create_sample_unit("unit-1")
        self.ledger.record_unit(unit)
        self.ledger.mark_completed("unit-1")
        out = io.StringIO()
        with patch("sys.stdout", out):
            code = run_semantic_build(db_path=self.db_path, clear_ledger=True)
        self.assertEqual(code, 0)
        self.assertIn("Cleared 1 checkpoint records", out.getvalue())

    def test_clear_ledger_json(self):
        unit = _create_sample_unit("unit-1")
        self.ledger.record_unit(unit)
        self.ledger.mark_completed("unit-1")
        out = io.StringIO()
        with patch("sys.stdout", out):
            code = run_semantic_build(
                db_path=self.db_path,
                clear_ledger=True,
                book_filter="Romans",
                json_output=True,
            )
        self.assertEqual(code, 0)
        data = json.loads(out.getvalue())
        self.assertEqual(data.get("cleared_units"), 1)
        self.assertEqual(data.get("book"), "Romans")

    def test_reset_failed(self):
        unit = _create_sample_unit("unit-fail")
        self.ledger.record_unit(unit)
        self.ledger.mark_failed("unit-fail", "Timeout error")
        out = io.StringIO()
        with patch("sys.stdout", out):
            code = run_semantic_build(db_path=self.db_path, reset_failed=True)
        self.assertEqual(code, 0)
        self.assertIn("Reset 1 failed units", out.getvalue())

    def test_reset_failed_json(self):
        unit = _create_sample_unit("unit-fail")
        self.ledger.record_unit(unit)
        self.ledger.mark_failed("unit-fail", "Timeout error")
        out = io.StringIO()
        with patch("sys.stdout", out):
            code = run_semantic_build(
                db_path=self.db_path,
                reset_failed=True,
                book_filter="Romans",
                json_output=True,
            )
        self.assertEqual(code, 0)
        data = json.loads(out.getvalue())
        self.assertEqual(data.get("reset_failed_units"), 1)
        self.assertEqual(data.get("book"), "Romans")

    def test_status_only_whole_bible(self):
        out = io.StringIO()
        with patch("sys.stdout", out):
            code = run_semantic_build(db_path=self.db_path, status_only=True)
        self.assertEqual(code, 0)
        self.assertIn("Semantic Compilation Ledger Status", out.getvalue())
        self.assertIn("Total Tracked Units", out.getvalue())

    def test_status_only_json(self):
        out = io.StringIO()
        with patch("sys.stdout", out):
            code = run_semantic_build(db_path=self.db_path, status_only=True, json_output=True)
        self.assertEqual(code, 0)
        data = json.loads(out.getvalue())
        self.assertIn("ledger_status", data)
        self.assertEqual(data.get("book"), "all")

    def test_status_only_single_book(self):
        out = io.StringIO()
        with patch("sys.stdout", out):
            code = run_semantic_build(
                db_path=self.db_path,
                status_only=True,
                book_filter="Romans",
            )
        self.assertEqual(code, 0)
        self.assertIn("Book: Romans", out.getvalue())

    def test_dry_run_all_pericopes(self):
        out = io.StringIO()
        with patch("sys.stdout", out):
            code = run_semantic_build(db_path=DEFAULT_DB_PATH, dry_run=True)
        self.assertEqual(code, 0)
        val = out.getvalue()
        self.assertIn("[Dry Run]", val)
        self.assertIn("units for compilation", val)

    def test_dry_run_json(self):
        out = io.StringIO()
        with patch("sys.stdout", out):
            code = run_semantic_build(
                db_path=DEFAULT_DB_PATH,
                dry_run=True,
                book_filter="Romans",
                json_output=True,
            )
        self.assertEqual(code, 0)
        data = json.loads(out.getvalue())
        self.assertTrue(data.get("dry_run"))
        self.assertEqual(data.get("scope"), "Romans")
        self.assertGreater(data.get("total_units", 0), 0)

    def test_dry_run_compile_all(self):
        out = io.StringIO()
        with patch("sys.stdout", out):
            code = run_semantic_build(
                db_path=DEFAULT_DB_PATH,
                dry_run=True,
                compile_all=True,
                json_output=True,
            )
        self.assertEqual(code, 0)
        data = json.loads(out.getvalue())
        self.assertTrue(data.get("dry_run"))
        self.assertGreater(data.get("total_units", 0), 100)

    @patch("tools.build_semantic_db.get_semantic_compiler")
    def test_real_compilation_success(self, mock_get_compiler):
        mock_compiler = MagicMock()
        mock_compiler.get_canonical_pericope_units.return_value = [_create_sample_unit("unit-1")]
        mock_progress = CompilationProgress(
            total_units=1,
            completed_units=1,
            skipped_units=0,
            failed_units=0,
            total_pericopes=1,
            total_discourse_relations=5,
            total_verse_theologies=10,
            total_typological_arcs=2,
            total_propositions=8,
            total_embeddings=1,
            duration_sec=1.5,
        )
        mock_compiler.compile_units.return_value = mock_progress
        mock_get_compiler.return_value = mock_compiler

        out = io.StringIO()
        with patch("sys.stdout", out):
            code = run_semantic_build(
                db_path=self.db_path,
                book_filter="Romans",
                dry_run=False,
            )
        self.assertEqual(code, 0)
        val = out.getvalue()
        self.assertIn("Batch Semantic Compilation Engine", val)
        self.assertIn("Compilation Summary:", val)
        self.assertIn("Completed:         1", val)

    @patch("tools.build_semantic_db.get_semantic_compiler")
    def test_real_compilation_failures_json(self, mock_get_compiler):
        mock_compiler = MagicMock()
        mock_compiler.get_canonical_pericope_units.return_value = [_create_sample_unit("unit-1")]
        mock_progress = CompilationProgress(
            total_units=1,
            completed_units=0,
            skipped_units=0,
            failed_units=1,
            duration_sec=0.5,
        )
        mock_compiler.compile_units.return_value = mock_progress
        mock_get_compiler.return_value = mock_compiler

        out = io.StringIO()
        with patch("sys.stdout", out):
            code = run_semantic_build(
                db_path=self.db_path,
                book_filter="Romans",
                dry_run=False,
                json_output=True,
            )
        self.assertEqual(code, 1)
        data = json.loads(out.getvalue())
        self.assertEqual(data.get("status"), "COMPLETED_WITH_FAILURES")
        self.assertEqual(data.get("progress", {}).get("failed_units"), 1)

    def test_main_status_json(self):
        out = io.StringIO()
        with patch("sys.stdout", out):
            code = main(["--db", str(self.db_path), "--status", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out.getvalue())
        self.assertIn("ledger_status", data)

    def test_main_dry_run_book(self):
        out = io.StringIO()
        with patch("sys.stdout", out):
            code = main(["--db", str(DEFAULT_DB_PATH), "--dry-run", "--book", "Genesis"])
        self.assertEqual(code, 0)
        self.assertIn("[Dry Run]", out.getvalue())

    def test_main_dry_run_corpus_1(self):
        out = io.StringIO()
        with patch("sys.stdout", out):
            code = main(["--db", str(DEFAULT_DB_PATH), "--dry-run", "--corpus", "1"])
        self.assertEqual(code, 0)
        val = out.getvalue()
        self.assertIn("[Dry Run]", val)
        self.assertIn("Foundational Pauline Epistles & Hebrews", val)

    def test_main_dry_run_corpus_3(self):
        out = io.StringIO()
        with patch("sys.stdout", out):
            code = main(["--db", str(DEFAULT_DB_PATH), "--dry-run", "--corpus", "3"])
        self.assertEqual(code, 0)
        val = out.getvalue()
        self.assertIn("[Dry Run]", val)
        self.assertIn("Pentateuch & Covenant Foundations", val)

    def test_invalid_corpus_filter(self):
        out = io.StringIO()
        with patch("sys.stdout", out):
            code = main(["--db", str(self.db_path), "--corpus", "99"])
        self.assertEqual(code, 1)
        self.assertIn("Unknown canonical corpus", out.getvalue())

    def test_corpus_status_json(self):
        out = io.StringIO()
        with patch("sys.stdout", out):
            code = main(["--db", str(self.db_path), "--corpus", "1", "--status", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out.getvalue())
        self.assertIn("corpus", data)
        self.assertEqual(data["corpus"]["corpus_id"], 1)


if __name__ == "__main__":
    unittest.main()

