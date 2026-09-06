"""Hermetic unit tests for Bible Engine CLI.

Zero external dependencies (Python 3 standard library only per ADR-003).
"""

import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from cli.main import build_parser, format_verse_lines, main
from core.db import Database, VerseRecord


class TestCliFormatting(unittest.TestCase):
    """Test verse line formatting functions."""

    def test_format_single_verse(self):
        v = VerseRecord(
            translation_id="WEB",
            book_id=43,
            book_name="John",
            chapter=3,
            verse=16,
            text="For God so loved the world...",
            canonical_verse_id=43003016,
        )
        out = format_verse_lines([v], show_verse_numbers=True, show_header=True)
        self.assertIn("=== John 3:16 (WEB) ===", out)
        self.assertIn("[16] For God so loved the world...", out)

    def test_format_multi_verse_same_chapter(self):
        v1 = VerseRecord(
            translation_id="WEB",
            book_id=45,
            book_name="Romans",
            chapter=8,
            verse=28,
            text="And we know...",
            canonical_verse_id=45008028,
        )
        v2 = VerseRecord(
            translation_id="WEB",
            book_id=45,
            book_name="Romans",
            chapter=8,
            verse=29,
            text="For those whom he foreknew...",
            canonical_verse_id=45008029,
        )
        out = format_verse_lines([v1, v2], show_verse_numbers=True, show_header=True)
        self.assertIn("=== Romans 8:28-29 (WEB) ===", out)
        self.assertIn("[28] And we know...", out)
        self.assertIn("[29] For those whom he foreknew...", out)

    def test_format_multi_verse_cross_chapter(self):
        v1 = VerseRecord(
            translation_id="WEB",
            book_id=1,
            book_name="Genesis",
            chapter=1,
            verse=31,
            text="God saw everything...",
            canonical_verse_id=1001031,
        )
        v2 = VerseRecord(
            translation_id="WEB",
            book_id=1,
            book_name="Genesis",
            chapter=2,
            verse=1,
            text="The heavens and earth were finished...",
            canonical_verse_id=1002001,
        )
        out = format_verse_lines([v1, v2], show_verse_numbers=True, show_header=True)
        self.assertIn("=== Genesis 1:31 - 2:1 (WEB) ===", out)

    def test_format_no_header_no_numbers(self):
        v = VerseRecord(
            translation_id="WEB",
            book_id=43,
            book_name="John",
            chapter=11,
            verse=35,
            text="Jesus wept.",
            canonical_verse_id=43011035,
        )
        out = format_verse_lines([v], show_verse_numbers=False, show_header=False)
        self.assertNotIn("===", out)
        self.assertNotIn("[35]", out)
        self.assertEqual(out, "Jesus wept.")

    def test_format_empty_list(self):
        out = format_verse_lines([])
        self.assertEqual(out, "")


class TestCliExecution(unittest.TestCase):
    """Test CLI execution and command-line parsing hermetically."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_bible.db"
        self.db = Database(self.db_path, auto_init=True)
        self.db.add_translation("WEB", "World English Bible")
        self.db.insert_verses(
            [
                VerseRecord(
                    translation_id="WEB",
                    book_id=43,
                    chapter=3,
                    verse=16,
                    text="For God so loved the world, that he gave his one and only Son.",
                ),
                VerseRecord(
                    translation_id="WEB",
                    book_id=43,
                    chapter=3,
                    verse=17,
                    text="For God didn't send his Son into the world to judge the world.",
                ),
            ]
        )

    def tearDown(self):
        self.db.close()
        self.temp_dir.cleanup()

    def test_cli_get_single_verse(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main(["--db", str(self.db_path), "get", "John 3:16"])
        self.assertEqual(code, 0)
        self.assertIn("=== John 3:16 (WEB) ===", stdout.getvalue())
        self.assertIn("[16] For God so loved the world", stdout.getvalue())

    def test_cli_get_verse_span(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main(["--db", str(self.db_path), "get", "John 3:16-17"])
        self.assertEqual(code, 0)
        self.assertIn("=== John 3:16-17 (WEB) ===", stdout.getvalue())
        self.assertIn("[16] For God so loved the world", stdout.getvalue())
        self.assertIn("[17] For God didn't send his Son", stdout.getvalue())

    def test_cli_get_no_numbers_and_no_header(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main(
                [
                    "--db",
                    str(self.db_path),
                    "get",
                    "John 3:16",
                    "--no-numbers",
                    "--no-header",
                ]
            )
        self.assertEqual(code, 0)
        self.assertNotIn("===", stdout.getvalue())
        self.assertNotIn("[16]", stdout.getvalue())
        self.assertIn("For God so loved the world", stdout.getvalue().strip())

    def test_cli_missing_db(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        fake_path = Path(self.temp_dir.name) / "nonexistent.db"
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main(["--db", str(fake_path), "get", "John 3:16"])
        self.assertEqual(code, 1)
        self.assertIn("Error: Database file not found", stderr.getvalue())

    def test_cli_invalid_reference(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main(["--db", str(self.db_path), "get", "NonexistentBook 99:99"])
        self.assertEqual(code, 1)
        self.assertIn("Error parsing reference", stderr.getvalue())

    def test_cli_not_found_verse(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main(["--db", str(self.db_path), "get", "Romans 8:28"])
        self.assertEqual(code, 1)
        self.assertIn("No verses found for reference", stderr.getvalue())

    def test_cli_no_subcommand(self):
        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = main([])
        self.assertEqual(code, 0)
        self.assertIn("usage: bible", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
