"""Hermetic unit tests for core/passport.py (Semantic Passport Generator).

Tests SemanticPassport formulation, BookHorizon injection, theological loci and ribbons,
preceding context formatting, and SQLite pericope record synthesis per ADR-083.

Zero external dependencies (Python 3 standard library only per ADR-003).
"""

from pathlib import Path
import tempfile
import unittest

from core.db import Database, VerseRecord
from core.passport import (
    SemanticPassport,
    SemanticPassportGenerator,
    generate_semantic_passport,
)
from core.reference import parse_reference


class TestSemanticPassportGenerator(unittest.TestCase):
    """Test suite for Semantic Passport creation and formatting."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "test.db"
        self.db = Database(self.db_path)
        self.db.add_translation("WEB", "World English Bible")

        # Seed sample pericope, verse, and theology
        ref = parse_reference("Romans 1:16-17")
        self.pericope = self.db.insert_pericope(
            reference=ref,
            title="The Power of God for Salvation",
            redemptive_summary="The gospel reveals the righteousness of God by faith from first to last.",
            genre="Pauline Epistle",
            central_proposition="The righteous shall live by faith through the gospel of Christ.",
        )

        # Insert WEB verses for this pericope
        self.db.insert_verse(
            VerseRecord(
                translation_id="WEB",
                book_id=ref.book.number,
                chapter=1,
                verse=16,
                text="For I am not ashamed of the Good News of Christ, for it is the power of God for salvation for everyone who believes.",
            )
        )
        self.db.insert_verse(
            VerseRecord(
                translation_id="WEB",
                book_id=ref.book.number,
                chapter=1,
                verse=17,
                text="For in it is revealed God's righteousness from faith to faith. As it is written, 'But the righteous shall live by faith.'",
            )
        )

        # Insert verse theology
        self.db.conn.execute(
            """
            INSERT INTO verse_theology (
                start_canonical_id, end_canonical_id, human_ref, storyline_epoch,
                thematic_ribbon, theological_locus, primary_doctrine, confidence, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1.0, datetime('now'))
            """,
            (
                ref.canonical_start_id,
                ref.canonical_end_id,
                ref.format(),
                "apostolic_church",
                "covenant_grace",
                "soteriology",
                "Justification by Faith",
            ),
        )

        # Insert a tag
        t = self.db.add_tag("justification", category="theological")
        self.db.conn.execute(
            """
            INSERT INTO verse_tags (
                tag_id, start_canonical_id, end_canonical_id, human_ref, confidence, source, starred, created_at
            ) VALUES (?, ?, ?, ?, 1.0, 'test', 1, datetime('now'))
            """,
            (t.id, ref.canonical_start_id, ref.canonical_end_id, ref.format()),
        )

    def tearDown(self):
        self.db.close()
        self.tmpdir.cleanup()

    def test_generate_passport_from_record(self):
        generator = SemanticPassportGenerator(self.db)
        passport = generator.generate_for_pericope_record(self.pericope)

        self.assertIsInstance(passport, SemanticPassport)
        self.assertEqual(passport.reference.format(), "Romans 1:16-17")
        self.assertEqual(passport.title, "The Power of God for Salvation")
        self.assertEqual(passport.genre, "Pauline Epistle")
        self.assertIn("soteriology", passport.theological_loci)
        self.assertIn("covenant_grace", passport.thematic_ribbons)
        self.assertIn("justification", passport.theological_loci)
        self.assertIn("[16] For I am not ashamed", passport.scripture_text)

        # Verify Book Horizon metadata
        self.assertIsNotNone(passport.book_horizon)
        self.assertEqual(passport.book_horizon.name, "Romans")
        self.assertEqual(passport.book_horizon.author, "Paul the Apostle")

        # Verify document text formatting
        doc_text = passport.format_document()
        self.assertIn("[DOCUMENT TITLE]: Romans 1:16-17 — The Power of God for Salvation", doc_text)
        self.assertIn("[CANONICAL HORIZON]:", doc_text)
        self.assertIn("[BOOK THEME]:", doc_text)
        self.assertIn("[THEOLOGICAL LOCI]:", doc_text)
        self.assertIn("[THEMATIC RIBBONS]:", doc_text)
        self.assertIn("[CENTRAL PROPOSITION]:", doc_text)
        self.assertIn("[SCRIPTURE TEXT]:", doc_text)
        self.assertIn("[16] For I am not ashamed", doc_text)

    def test_generate_passport_by_pericope_id(self):
        generator = SemanticPassportGenerator(self.db)
        passport = generator.generate_for_pericope_id(self.pericope.id)

        self.assertIsNotNone(passport)
        self.assertEqual(passport.pericope_id, self.pericope.id)
        self.assertEqual(passport.title, "The Power of God for Salvation")

    def test_generate_passport_nonexistent_id(self):
        generator = SemanticPassportGenerator(self.db)
        passport = generator.generate_for_pericope_id(999999)
        self.assertIsNone(passport)

    def test_passport_to_dict(self):
        passport = generate_semantic_passport(self.db, self.pericope.id)
        self.assertIsNotNone(passport)
        p_dict = passport.to_dict()

        self.assertEqual(p_dict["reference"], "Romans 1:16-17")
        self.assertEqual(p_dict["title"], "The Power of God for Salvation")
        self.assertIn("document_text", p_dict)
        self.assertIsInstance(p_dict["theological_loci"], list)
        self.assertIsInstance(p_dict["thematic_ribbons"], list)

    def test_convenience_helper_with_dict(self):
        row_dict = {
            "id": 42,
            "book_id": 45,
            "human_ref": "Romans 8:28-30",
            "title": "The Golden Chain of Redemption",
            "redemptive_summary": "God works all things together for good for those who are called according to His purpose.",
            "genre": "Pauline Epistle",
            "central_proposition": "Those whom God foreknew He also predestined, called, justified, and glorified.",
            "start_canonical_id": 45008028,
            "end_canonical_id": 45008030,
        }
        passport = generate_semantic_passport(self.db, row_dict)
        self.assertIsNotNone(passport)
        self.assertEqual(passport.reference.format(), "Romans 8:28-30")
        self.assertEqual(passport.title, "The Golden Chain of Redemption")
        doc = passport.format_document()
        self.assertIn("[DOCUMENT TITLE]: Romans 8:28-30 — The Golden Chain of Redemption", doc)


if __name__ == "__main__":
    unittest.main()
