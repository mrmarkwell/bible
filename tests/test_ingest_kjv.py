"""Unit and Integration Tests for King James Version (KJV) Ingestion.

Zero external dependencies (Python 3 stdlib unittest only per ADR-003).
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from core.db import Database
from core.reference import ALL_BOOKS, get_book
from tools.ingest_kjv import (
    RAW_KJV_DIR,
    book_to_filename,
    fetch_and_cache_book,
    ingest_kjv,
    main,
    parse_book_json,
)


class TestKjvIngest(unittest.TestCase):
    """Test suite for King James Version ingestion pipeline."""

    def test_book_to_filename_all_66(self) -> None:
        """Verify all 66 books map to valid non-empty filenames."""
        filenames = [book_to_filename(b) for b in ALL_BOOKS]
        self.assertEqual(len(filenames), 66)
        self.assertEqual(len(set(filenames)), 66)
        for fn in filenames:
            self.assertTrue(fn.endswith(".json"))
            self.assertNotIn(" ", fn)

        gen = get_book("Genesis")
        self.assertIsNotNone(gen)
        self.assertEqual(book_to_filename(gen), "Genesis.json")

        cor1 = get_book("1 Corinthians")
        self.assertIsNotNone(cor1)
        self.assertEqual(book_to_filename(cor1), "1Corinthians.json")

        sos = get_book("Song of Solomon")
        self.assertIsNotNone(sos)
        self.assertEqual(book_to_filename(sos), "SongofSolomon.json")

        ps = get_book("Psalms")
        self.assertIsNotNone(ps)
        self.assertEqual(book_to_filename(ps), "Psalms.json")

    def test_parse_book_json_synthetic(self) -> None:
        """Verify parsing of synthetic aruljohn format KJV JSON."""
        synthetic_data = {
            "book": "Genesis",
            "chapters": [
                {
                    "chapter": "1",
                    "verses": [
                        {
                            "verse": "1",
                            "text": "In the beginning God created the heaven and the earth.",
                        },
                        {
                            "verse": "2",
                            "text": "And the earth was without form, and void; and darkness was upon the face of the deep.",
                        },
                    ],
                },
                {
                    "chapter": "2",
                    "verses": [
                        {
                            "verse": "1",
                            "text": "Thus the heavens and the earth were finished, and all the host of them.",
                        }
                    ],
                },
            ],
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(synthetic_data, f)
            temp_path = Path(f.name)

        try:
            verses = parse_book_json(temp_path)
            self.assertEqual(len(verses), 3)
            self.assertEqual(
                verses[(1, 1)],
                "In the beginning God created the heaven and the earth.",
            )
            self.assertEqual(
                verses[(1, 2)],
                "And the earth was without form, and void; and darkness was upon the face of the deep.",
            )
            self.assertEqual(
                verses[(2, 1)],
                "Thus the heavens and the earth were finished, and all the host of them.",
            )
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_parse_book_json_malformed_handling(self) -> None:
        """Verify resilient handling of malformed chapter or verse items."""
        synthetic_data = {
            "book": "MalformedBook",
            "chapters": [
                "not a dict",
                {"chapter": "invalid_number", "verses": []},
                {
                    "chapter": "1",
                    "verses": [
                        "not a dict",
                        {"verse": "bad_int", "text": "Some text"},
                        {"verse": "1", "text": ""},
                        {"verse": "2", "text": "  Valid   verse   text!  "},
                    ],
                },
            ],
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(synthetic_data, f)
            temp_path = Path(f.name)

        try:
            verses = parse_book_json(temp_path)
            self.assertEqual(len(verses), 1)
            self.assertEqual(verses[(1, 2)], "Valid verse text!")
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_cached_raw_files_exist_and_complete(self) -> None:
        """Verify all 66 books are present in data/raw/kjv/."""
        self.assertTrue(RAW_KJV_DIR.exists(), "Raw KJV cache directory must exist")
        raw_files = list(RAW_KJV_DIR.glob("*.json"))
        self.assertEqual(len(raw_files), 66, "Must have exactly 66 cached book JSON files")
        for b in ALL_BOOKS:
            expected_fn = RAW_KJV_DIR / book_to_filename(b)
            self.assertTrue(expected_fn.exists(), f"Missing cache file: {expected_fn}")
            self.assertGreater(expected_fn.stat().st_size, 1000)

    def test_ingest_into_temp_database(self) -> None:
        """Verify hermetic end-to-end ingestion into a temporary SQLite database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_db_path = Path(tmpdir) / "test_bible.db"
            gen = get_book("Genesis")
            john = get_book("John")
            self.assertIsNotNone(gen)
            self.assertIsNotNone(john)
            sample_books = [gen, john]

            count = ingest_kjv(
                db_path=tmp_db_path,
                raw_dir=RAW_KJV_DIR,
                force_download=False,
                verbose=False,
                books=sample_books,
            )
            # Genesis has 1,533 verses, John has 879 verses = 2,412 verses
            self.assertEqual(count, 2412)

            with Database(tmp_db_path, auto_init=False) as db:
                trans = db.get_translation("KJV")
                self.assertIsNotNone(trans)
                self.assertEqual(trans.name, "King James Version")
                self.assertTrue(trans.is_public_domain)
                self.assertFalse(trans.is_encrypted)

                # Fetch single verse
                v_gen1 = db.get_verse("Genesis", 1, 1, translation_id="KJV")
                self.assertIsNotNone(v_gen1)
                self.assertEqual(v_gen1.text, "In the beginning God created the heaven and the earth.")

                # Fetch passage
                v_john = db.get_verses_by_reference("John 1:1-3", translation_id="KJV")
                self.assertEqual(len(v_john), 3)
                self.assertEqual(v_john[0].text, "In the beginning was the Word, and the Word was with God, and the Word was God.")

                # Verify FTS5 Search
                search_results = db.search_text("Word was God", translation_id="KJV")
                self.assertGreaterEqual(len(search_results), 1)
                self.assertEqual(search_results[0].human_ref, "John 1:1")

                # Verify available translation IDs
                avail = db.get_available_translation_ids()
                self.assertIn("KJV", avail)

    def test_fetch_and_cache_book_cached(self) -> None:
        """Verify fetch_and_cache_book returns existing cached path without re-downloading."""
        gen = get_book("Genesis")
        self.assertIsNotNone(gen)
        fn = book_to_filename(gen)
        path = fetch_and_cache_book(fn, cache_dir=RAW_KJV_DIR, force=False)
        self.assertTrue(path.exists())
        self.assertEqual(path, RAW_KJV_DIR / fn)

    def test_cli_main_custom_books(self) -> None:
        """Verify main() CLI execution with custom --books and --quiet flags."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_db_path = Path(tmpdir) / "cli_test.db"
            exit_code = main(["--db", str(tmp_db_path), "--books", "Ruth,Jude", "--quiet"])
            self.assertEqual(exit_code, 0)

            with Database(tmp_db_path, auto_init=False) as db:
                # Ruth has 85 verses, Jude has 25 verses = 110 verses
                self.assertEqual(db.count_verses("KJV"), 110)


if __name__ == "__main__":
    unittest.main()
