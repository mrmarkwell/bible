"""Unit and Integration Tests for World English Bible Ingestion.

Zero external dependencies (Python 3 stdlib unittest only per ADR-003).
"""

import json
from pathlib import Path
import tempfile
import unittest

from core.db import Database
from core.reference import ALL_BOOKS, Book, get_book
from tools.ingest_web import book_to_filename, parse_book_json, ingest_web, RAW_WEB_DIR


class TestWebIngest(unittest.TestCase):
    """Test suite for World English Bible ingestion pipeline."""

    def test_book_to_filename_all_66(self) -> None:
        """Verify all 66 books map to valid non-empty lowercase filenames."""
        filenames = [book_to_filename(b) for b in ALL_BOOKS]
        self.assertEqual(len(filenames), 66)
        self.assertEqual(len(set(filenames)), 66)
        for fn in filenames:
            self.assertTrue(fn.endswith(".json"))
            self.assertTrue(fn.islower())
            self.assertNotIn(" ", fn)

        self.assertEqual(book_to_filename(get_book("Genesis")), "genesis.json")
        self.assertEqual(book_to_filename(get_book("1 Corinthians")), "1corinthians.json")
        self.assertEqual(book_to_filename(get_book("Song of Solomon")), "songofsolomon.json")

    def test_parse_book_json_synthetic(self) -> None:
        """Verify parsing of synthetic TehShrike format JSON."""
        synthetic_data = [
            {"type": "paragraph start"},
            {
                "type": "paragraph text",
                "chapterNumber": 1,
                "verseNumber": 1,
                "sectionNumber": 1,
                "value": "In the beginning, ",
            },
            {
                "type": "paragraph text",
                "chapterNumber": 1,
                "verseNumber": 1,
                "sectionNumber": 2,
                "value": "God created the heavens and the earth. ",
            },
            {"type": "paragraph end"},
            {
                "type": "line text",
                "chapterNumber": 1,
                "verseNumber": 2,
                "sectionNumber": 1,
                "value": "The earth was formless and void. ",
            },
        ]
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(synthetic_data, f)
            temp_path = Path(f.name)

        try:
            verses = parse_book_json(temp_path)
            self.assertEqual(len(verses), 2)
            self.assertEqual(
                verses[(1, 1)],
                "In the beginning, God created the heavens and the earth.",
            )
            self.assertEqual(verses[(1, 2)], "The earth was formless and void.")
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_cached_raw_files_exist_and_complete(self) -> None:
        """Verify all 66 books are present in data/raw/web/."""
        self.assertTrue(RAW_WEB_DIR.exists(), "Raw WEB cache directory must exist")
        raw_files = list(RAW_WEB_DIR.glob("*.json"))
        self.assertEqual(len(raw_files), 66, "Must have exactly 66 cached book JSON files")
        for b in ALL_BOOKS:
            expected_fn = RAW_WEB_DIR / book_to_filename(b)
            self.assertTrue(expected_fn.exists(), f"Missing cache file: {expected_fn}")
            self.assertGreater(expected_fn.stat().st_size, 1000)

    def test_ingest_into_temp_database(self) -> None:
        """Verify hermetic end-to-end ingestion into a temporary SQLite database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_db_path = Path(tmpdir) / "test_bible.db"
            sample_books = [
                get_book("Genesis"),
                get_book("John"),
                get_book("Romans"),
                get_book("Revelation"),
            ]
            count = ingest_web(
                db_path=tmp_db_path,
                raw_dir=RAW_WEB_DIR,
                force_download=False,
                verbose=False,
                books=sample_books,
            )
            self.assertEqual(count, 3250, "Must insert all 3,250 verses across sample books")

            db = Database(db_path=tmp_db_path)
            # Verify translation record
            trans = db.get_translation("WEB")
            self.assertIsNotNone(trans)
            self.assertEqual(trans.id, "WEB")
            self.assertTrue(trans.is_public_domain)

            # Verify key verses
            gen11 = db.get_verse("Genesis", 1, 1, translation_id="WEB")
            self.assertIsNotNone(gen11)
            self.assertEqual(gen11.text, "In the beginning, God created the heavens and the earth.")

            jhn316 = db.get_verse("John", 3, 16, translation_id="WEB")
            self.assertIsNotNone(jhn316)
            self.assertIn("For God so loved the world", jhn316.text)

            rev2221 = db.get_verse("Revelation", 22, 21, translation_id="WEB")
            self.assertIsNotNone(rev2221)
            self.assertIn("Amen", rev2221.text)

            # Verify FTS5 full-text search
            search_results = db.search_text("grace of our Lord Jesus Christ", translation_id="WEB")
            self.assertGreater(len(search_results), 0)

            db.close()


if __name__ == "__main__":
    unittest.main()
