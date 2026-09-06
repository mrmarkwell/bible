"""Hermetic unit tests for favorite verses ingestion and database curation.

Verifies:
- Parsing and loading of favorite_bible_verses.csv into Reference objects.
- Accurate handling of single verses, intra-chapter spans, and whole chapters.
- Typo auto-correction (e.g. Mark 1:223-26 -> Mark 1:23-26).
- Batch ingestion into an in-memory SQLite database.
- Idempotent re-ingestion and clear_tag functionality.
- Retrieval of all 829 favorites and 50 starred favorites.
- Passage overlap query matching favorites against scripture citations.

Zero external dependencies: 100% Python standard library unittest.
"""

import tempfile
import unittest
from pathlib import Path

from core.db import Database
from core.reference import Reference, parse_reference
from tools.ingest_favorites import (
    DEFAULT_CSV_PATH,
    clean_csv_row,
    ingest_favorites,
    load_favorites_csv,
)


class TestFavoriteCSVParser(unittest.TestCase):
    """Test reading, cleaning, and validating CSV rows."""

    def test_clean_standard_single_verse(self):
        row = {"book": "Genesis", "chapter": "1", "start_verse": "27", "end_verse": "", "starred": ""}
        ref, starred, notes = clean_csv_row(row)
        self.assertEqual(ref.format(), "Genesis 1:27")
        self.assertFalse(starred)
        self.assertIsNone(notes)

    def test_clean_verse_span(self):
        row = {"book": "Romans", "chapter": "8", "start_verse": "28", "end_verse": "30", "starred": "TRUE"}
        ref, starred, notes = clean_csv_row(row)
        self.assertEqual(ref.format(), "Romans 8:28-30")
        self.assertTrue(starred)
        self.assertIsNone(notes)

    def test_clean_whole_chapter(self):
        row = {"book": "Psalm", "chapter": "23", "start_verse": "", "end_verse": "", "starred": "true"}
        ref, starred, notes = clean_csv_row(row)
        self.assertEqual(ref.format(), "Psalms 23")
        self.assertTrue(starred)
        self.assertIsNone(notes)

    def test_clean_typo_correction(self):
        row = {"book": "Mark", "chapter": "1", "start_verse": "223", "end_verse": "26", "starred": ""}
        ref, starred, notes = clean_csv_row(row)
        self.assertEqual(ref.format(), "Mark 1:23-26")
        self.assertFalse(starred)
        self.assertIsNotNone(notes)
        self.assertIn("Auto-corrected", notes)

    def test_load_all_records_from_csv(self):
        self.assertTrue(DEFAULT_CSV_PATH.exists(), f"CSV path missing: {DEFAULT_CSV_PATH}")
        items = load_favorites_csv(DEFAULT_CSV_PATH)
        self.assertEqual(len(items), 829)
        starred_count = sum(1 for _, starred, _ in items if starred)
        self.assertEqual(starred_count, 50)


class TestFavoritesDatabaseIngestion(unittest.TestCase):
    """Test ingesting favorites into SQLite database."""

    def setUp(self):
        self.db = Database(":memory:")

    def tearDown(self):
        self.db.close()

    def test_batch_ingest_favorites(self):
        total, starred = ingest_favorites(self.db, csv_path=DEFAULT_CSV_PATH)
        self.assertEqual(total, 829)
        self.assertEqual(starred, 50)

        # Check tag metadata
        tag = self.db.get_tag("favorites")
        self.assertIsNotNone(tag)
        self.assertEqual(tag.name, "favorites")
        self.assertEqual(tag.category, "curation")

        # Check all favorites retrieval
        all_favs = self.db.get_favorites(starred_only=False)
        self.assertEqual(len(all_favs), 829)

        # Check starred favorites retrieval
        starred_favs = self.db.get_favorites(starred_only=True)
        self.assertEqual(len(starred_favs), 50)
        for s in starred_favs:
            self.assertTrue(s.starred)

    def test_idempotent_reingest(self):
        total1, _ = ingest_favorites(self.db, csv_path=DEFAULT_CSV_PATH, clear_existing=True)
        self.assertEqual(total1, 829)
        self.assertEqual(len(self.db.get_favorites()), 829)

        # Second ingestion with clear_existing=True replaces records without duplication
        total2, _ = ingest_favorites(self.db, csv_path=DEFAULT_CSV_PATH, clear_existing=True)
        self.assertEqual(total2, 829)
        self.assertEqual(len(self.db.get_favorites()), 829)

    def test_clear_favorites_tag(self):
        ingest_favorites(self.db, csv_path=DEFAULT_CSV_PATH)
        self.assertEqual(len(self.db.get_favorites()), 829)

        deleted = self.db.clear_tag("favorites")
        self.assertEqual(deleted, 829)
        self.assertEqual(len(self.db.get_favorites()), 0)

    def test_favorite_query_by_passage_overlap(self):
        ingest_favorites(self.db, csv_path=DEFAULT_CSV_PATH)

        # John 3:16 is contained in John 3:16-18
        tags = self.db.get_tags_for_reference("John 3:16")
        fav_tag_names = [t.tag_name for t in tags]
        self.assertIn("favorites", fav_tag_names)

        # Philippians 2:6 is contained in Philippians 2:5-11 (which is starred)
        phil_tags = self.db.get_tags_for_reference("Philippians 2:6")
        phil_fav = next(t for t in phil_tags if t.tag_name == "favorites")
        self.assertTrue(phil_fav.starred)


if __name__ == "__main__":
    unittest.main()
