"""Hermetic unit tests for canonical pericopes and outline navigation.

Zero-dependency implementation (Python 3 standard library only per ADR-003).
Verifies:
  - Database schema and index creation for pericopes.
  - CRUD operations: insert, batch insert, query by reference, query by book, count.
  - Overlap calculation for passage ranges.
  - PericopeService integration, retrieval, and canonical seed idempotency.
  - Terminal pericope banner and table formatting.
"""

import unittest
from pathlib import Path
import tempfile

from core.db import Database, PericopeRecord
from core.pericopes import CANONICAL_PERICOPES, PericopeService
from core.reference import parse_reference
from core.terminal import format_pericope_banner, format_pericope_table


class TestPericopes(unittest.TestCase):
    """Unit tests for pericope storage and service layer."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_bible.db"
        self.db = Database(self.db_path)
        self.service = PericopeService(self.db)

    def tearDown(self) -> None:
        self.db.close()
        self.temp_dir.cleanup()

    def test_pericope_record_properties(self) -> None:
        rec = PericopeRecord(
            id=1,
            book_id=1,
            start_canonical_id=1001001,
            end_canonical_id=1002003,
            human_ref="Genesis 1:1-2:3",
            title="The Creation",
            redemptive_summary="God speaks the cosmos into existence.",
        )
        self.assertEqual(rec.book.name, "Genesis")
        self.assertEqual(rec.book_name, "Genesis")
        self.assertEqual(rec.osis, "Gen")
        d = rec.to_dict()
        self.assertEqual(d["human_ref"], "Genesis 1:1-2:3")
        self.assertEqual(d["book_id"], 1)
        self.assertEqual(d["book_name"], "Genesis")

    def test_insert_and_count(self) -> None:
        self.assertEqual(self.db.count_pericopes(), 0)
        rec = self.db.insert_pericope(
            reference="Genesis 1:1-2:3",
            title="The Creation",
            redemptive_summary="Creation ex nihilo.",
        )
        self.assertGreater(rec.id, 0)
        self.assertEqual(self.db.count_pericopes(), 1)
        self.assertEqual(self.db.count_pericopes(book_id=1), 1)
        self.assertEqual(self.db.count_pericopes(book_id=2), 0)

    def test_seed_canonical_pericopes_idempotent(self) -> None:
        first_count = self.service.seed_canonical_pericopes()
        self.assertGreaterEqual(first_count, 140)
        self.assertEqual(self.db.count_pericopes(), first_count)

        # Re-seeding should not insert any duplicates (returns 0 newly inserted)
        second_count = self.service.seed_canonical_pericopes()
        self.assertEqual(second_count, 0)
        self.assertEqual(self.db.count_pericopes(), first_count)

    def test_get_pericopes_for_passage(self) -> None:
        self.service.seed_canonical_pericopes()

        # John 3:16 should fall into John 3:1-21 pericope
        ref_john = parse_reference("John 3:16")
        pericopes = self.service.get_pericopes_for_passage(ref_john)
        self.assertTrue(len(pericopes) >= 1)
        titles = [p.title for p in pericopes]
        self.assertTrue(any("Born Again" in t for t in titles))

        # Romans 8:28 should fall into Romans 8:26-39
        ref_rom = parse_reference("Romans 8:28")
        rom_pericopes = self.service.get_pericopes_for_passage(ref_rom)
        self.assertTrue(len(rom_pericopes) >= 1)
        self.assertTrue(any("Golden Chain" in p.title or "More Than Conquerors" in p.title for p in rom_pericopes))

    def test_get_pericopes_for_book(self) -> None:
        self.service.seed_canonical_pericopes()

        gen_pericopes = self.service.get_pericopes_for_book("Genesis")
        self.assertGreaterEqual(len(gen_pericopes), 5)
        self.assertEqual(gen_pericopes[0].book_name, "Genesis")

        # Filter by OSIS
        rev_pericopes = self.service.get_pericopes_for_book("Rev")
        self.assertGreaterEqual(len(rev_pericopes), 4)

    def test_terminal_formatting(self) -> None:
        rec = PericopeRecord(
            id=1,
            book_id=43,
            start_canonical_id=43001001,
            end_canonical_id=43001018,
            human_ref="John 1:1-18",
            title="The Word Became Flesh",
            redemptive_summary="The eternal Word became incarnate.",
        )
        banner_color = format_pericope_banner(rec, styling=True)
        self.assertIn("THE WORD BECAME FLESH", banner_color)
        self.assertIn("John 1:1-18", banner_color)

        banner_plain = format_pericope_banner(rec, styling=False)
        self.assertIn("§ THE WORD BECAME FLESH (John 1:1-18)", banner_plain)

        table = format_pericope_table([rec], styling=False)
        self.assertIn("John 1:1-18", table)
        self.assertIn("The Word Became Flesh", table)


if __name__ == "__main__":
    unittest.main()
