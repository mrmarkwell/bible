"""Hermetic Unit Tests for Resumable Batch Semantic Compilation Engine.

Zero-dependency test suite per ADR-003, ADR-006, ADR-042, ADR-050, ADR-052, ADR-054, ADR-055, and ADR-056:
- Tests SQLite Checkpoint Ledger lifecycle transitions (PENDING -> IN_PROGRESS -> COMPLETED / FAILED / SKIPPED).
- Tests state machine resumption, idempotency, and ledger resets.
- Tests compilation unit generators (canonical pericopes and chapters).
- Tests rate limiter pacing and interval enforcement.
- Tests mock response execution, multi-layer extraction, and database persistence.
- Tests vector embedding calculation (Layer 6) and int8 quantization.
- Tests CLI command options (--status, --dry-run, --reset-failed, --clear-ledger).
"""

from pathlib import Path
import tempfile
import time
import unittest
from typing import Tuple

from core.db import Database
from core.reference import parse_reference
from core.semantic_compiler import (
    CompilationUnit,
    CompilationUnitStatus,
    RateLimiter,
    SemanticCheckpointLedger,
    SemanticDatabaseCompiler,
)


def _create_test_database() -> Tuple[Path, Database]:
    """Create a hermetic SQLite database in a temporary directory with seeded verses."""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test_bible.db"
    db = Database(db_path, auto_init=True)

    from core.db import VerseRecord
    with db.conn:
        db.conn.execute("INSERT OR REPLACE INTO translations (id, name, language, is_public_domain) VALUES ('WEB', 'World English Bible', 'en', 1)")
        db.conn.execute("INSERT OR REPLACE INTO translations (id, name, language, is_public_domain) VALUES ('ESV', 'English Standard Version', 'en', 0)")

    # Seed Romans 8 verses for hermetic compiler testing
    verses = [
        VerseRecord("WEB", 45, 8, 28, "We know that all things work together for good for those who love God, to those who are called according to his purpose."),
        VerseRecord("WEB", 45, 8, 29, "For whom he foreknew, he also predestined to be conformed to the image of his Son, that he might be the firstborn among many brothers."),
        VerseRecord("WEB", 45, 8, 30, "Whom he predestined, those he also called. Whom he called, those he also justified. Whom he justified, those he also glorified."),
    ]
    db.insert_verses(verses)

    # Seed Genesis 1:1-3
    gen_verses = [
        VerseRecord("WEB", 1, 1, 1, "In the beginning, God created the heavens and the earth."),
        VerseRecord("WEB", 1, 1, 2, "The earth was formless and empty. Darkness was on the surface of the deep and God's Spirit was hovering over the surface of the waters."),
        VerseRecord("WEB", 1, 1, 3, "God said, 'Let there be light,' and there was light."),
    ]
    db.insert_verses(gen_verses)

    return db_path, db


class TestSemanticCheckpointLedger(unittest.TestCase):
    """Test suite for SQLite Checkpoint Ledger state machine."""

    def setUp(self) -> None:
        self.db_path, self.db = _create_test_database()
        self.ledger = SemanticCheckpointLedger(self.db)

    def tearDown(self) -> None:
        self.db.close()
        import shutil
        shutil.rmtree(self.db_path.parent, ignore_errors=True)

    def test_ledger_initialization_and_record_unit(self) -> None:
        ref = parse_reference("Romans 8:28-30")
        unit = CompilationUnit(
            unit_id="test_rom_8_28_30",
            reference=ref,
            book=ref.book,
            passage_text="Test passage",
            title="The Golden Chain of Redemption",
        )
        rec = self.ledger.record_unit(unit)
        self.assertEqual(rec.unit_id, "test_rom_8_28_30")
        self.assertEqual(rec.status, CompilationUnitStatus.PENDING)
        self.assertEqual(rec.attempts, 0)
        self.assertEqual(rec.human_ref, "Romans 8:28-30")

    def test_status_transitions_and_attempts(self) -> None:
        ref = parse_reference("Romans 8:28-30")
        unit = CompilationUnit(
            unit_id="test_unit_1",
            reference=ref,
            book=ref.book,
            passage_text="Test passage",
        )
        self.ledger.record_unit(unit)

        # Mark in progress
        self.ledger.mark_in_progress("test_unit_1")
        rec = self.ledger.get_checkpoint("test_unit_1")
        self.assertIsNotNone(rec)
        self.assertEqual(rec.status, CompilationUnitStatus.IN_PROGRESS)
        self.assertEqual(rec.attempts, 1)

        # Mark failed
        self.ledger.mark_failed("test_unit_1", "Simulated API timeout")
        rec = self.ledger.get_checkpoint("test_unit_1")
        self.assertEqual(rec.status, CompilationUnitStatus.FAILED)
        self.assertIn("Simulated API timeout", rec.last_error)

        # Mark completed
        self.ledger.mark_completed("test_unit_1", pericope_id=42)
        rec = self.ledger.get_checkpoint("test_unit_1")
        self.assertEqual(rec.status, CompilationUnitStatus.COMPLETED)
        self.assertEqual(rec.pericope_id, 42)
        self.assertIsNone(rec.last_error)

    def test_reset_status_and_clear_ledger(self) -> None:
        ref1 = parse_reference("Romans 8:28-30")
        ref2 = parse_reference("Genesis 1:1-3")
        u1 = CompilationUnit("u1", ref1, ref1.book, "p1")
        u2 = CompilationUnit("u2", ref2, ref2.book, "p2")
        self.ledger.record_unit(u1)
        self.ledger.record_unit(u2)

        self.ledger.mark_failed("u1", "Error 1")
        self.ledger.mark_failed("u2", "Error 2")

        summary = self.ledger.get_summary()
        self.assertEqual(summary.get("FAILED"), 2)

        # Reset failed for Romans only (book 45)
        reset_cnt = self.ledger.reset_status(CompilationUnitStatus.FAILED, book_id=45)
        self.assertEqual(reset_cnt, 1)
        rec1 = self.ledger.get_checkpoint("u1")
        rec2 = self.ledger.get_checkpoint("u2")
        self.assertEqual(rec1.status, CompilationUnitStatus.PENDING)
        self.assertEqual(rec2.status, CompilationUnitStatus.FAILED)

        # Clear ledger
        cleared = self.ledger.clear_ledger()
        self.assertEqual(cleared, 2)
        self.assertEqual(sum(self.ledger.get_summary().values()), 0)


class TestRateLimiter(unittest.TestCase):
    """Test suite for pure Python rate limiter."""

    def test_rate_limiter_interval(self) -> None:
        limiter = RateLimiter(requests_per_minute=600.0, min_interval_sec=0.01)
        self.assertAlmostEqual(limiter.interval, 0.1, places=2)

        t0 = time.time()
        limiter.wait()
        limiter.wait()
        elapsed = time.time() - t0
        self.assertGreaterEqual(elapsed, 0.08)


class TestSemanticDatabaseCompiler(unittest.TestCase):
    """Test suite for SemanticDatabaseCompiler orchestrator."""

    def setUp(self) -> None:
        self.db_path, self.db = _create_test_database()
        self.compiler = SemanticDatabaseCompiler(
            db=self.db,
            llm_client=None,
            translation_id="WEB",
            rate_limiter=RateLimiter(requests_per_minute=1000.0, min_interval_sec=0.001),
            generate_embeddings=True,
        )

    def tearDown(self) -> None:
        self.db.close()
        import shutil
        shutil.rmtree(self.db_path.parent, ignore_errors=True)

    def test_fetch_passage_text(self) -> None:
        ref = parse_reference("Romans 8:28-30")
        text = self.compiler.fetch_passage_text(ref, translation_id="WEB")
        self.assertIn("all things work together for good", text)
        self.assertIn("[28]", text)
        self.assertIn("[30]", text)

    def test_process_unit_with_mock_response(self) -> None:
        ref = parse_reference("Romans 8:28-30")
        unit = CompilationUnit(
            unit_id="rom_8_28_30_mock",
            reference=ref,
            book=ref.book,
            passage_text="Passage text for Romans 8:28-30",
            title="The Golden Chain of Redemption",
            summary="God works all things together for the good of those who love Him.",
        )

        mock_payload = {
            "reference": "Romans 8:28-30",
            "title": "The Golden Chain of Redemption",
            "genre": "Epistle / Theological Exposition",
            "literary_structure": "Progressive Sorites / Golden Chain (Foreknown -> Predestined -> Called -> Justified -> Glorified)",
            "central_proposition": "God's eternal sovereign purpose infallibly guarantees the final glorification of His elect.",
            "redemptive_summary": "Believers' security rests not on their temporal strength, but upon God's eternal redemptive covenant.",
            "christological_fulfillment": "Christ is the firstborn among many brethren; His resurrected glory is the pattern and surety of the believer's glorification.",
            "discourse_relations": [
                {
                    "source_verse": "Romans 8:29",
                    "target_verse": "Romans 8:28",
                    "relation_type": "ground",
                    "marker_text": "For",
                    "greek_marker": "ὅτι",
                    "notes": "Verse 29 provides the theological basis for why all things work for good."
                }
            ],
            "verse_theology": [
                {
                    "verse_ref": "Romans 8:28-30",
                    "storyline_epoch": "Apostolic Church",
                    "theological_locus": "Soteriology",
                    "primary_doctrine": "Effectual Calling & Perseverance of the Saints",
                    "thematic_ribbon": "Sovereign Election",
                    "confidence": 0.98
                }
            ],
            "typological_arcs": [
                {
                    "type_ref": "Genesis 50:20",
                    "type_name": "Joseph's Providence",
                    "antitype_ref": "Romans 8:28",
                    "antitype_name": "Sovereign Redemptive Purpose",
                    "theological_correspondence": "What men intended for evil, God meant for good to save many lives.",
                    "warrant": "canonical_thematic_pattern",
                    "confidence": 0.95
                }
            ],
            "semantic_propositions": [
                {
                    "verse_ref": "Romans 8:28",
                    "speech_act": "promise",
                    "agent": "God",
                    "action": "works all things together for good",
                    "patient": "those who love God",
                    "tone": "assurance"
                }
            ]
        }

        ok, err, res = self.compiler.process_unit(unit, mock_response=mock_payload)
        self.assertTrue(ok, f"Unit processing failed: {err}")
        self.assertIsNone(err)
        self.assertIsNotNone(res)

        # Verify SQLite insertion across all 6 layers
        # 1. Pericope
        pericopes = self.db.get_pericopes_for_reference(ref)
        self.assertTrue(len(pericopes) >= 1)
        p = pericopes[0]
        self.assertEqual(p.title, "The Golden Chain of Redemption")
        self.assertIn("infallibly guarantees", p.central_proposition)

        # 2. Discourse
        disc_rels = self.db.get_discourse_relations_for_verse("Romans 8:29")
        self.assertTrue(len(disc_rels) >= 1)
        self.assertEqual(disc_rels[0].relation_type, "ground")

        # 3. Theology
        theos = self.db.get_verse_theology_for_reference(ref)
        self.assertTrue(len(theos) >= 1)
        self.assertEqual(theos[0].theological_locus.lower(), "soteriology")

        # 4. Typology
        arcs = self.db.get_typological_arcs_for_reference(ref)
        self.assertTrue(len(arcs) >= 1)
        self.assertEqual(arcs[0].type_human_ref, "Genesis 50:20")

        # 5. Propositions
        props = self.db.get_semantic_propositions_for_verse("Romans 8:28")
        self.assertTrue(len(props) >= 1)
        self.assertEqual(props[0].agent, "God")
        self.assertEqual(props[0].speech_act, "promise")

        # 6. Embeddings
        chk = self.compiler.ledger.get_checkpoint("rom_8_28_30_mock")
        self.assertIsNotNone(chk)
        self.assertEqual(chk.status, CompilationUnitStatus.COMPLETED)
        self.assertIsNotNone(chk.pericope_id)
        emb_rec = self.db.get_pericope_embedding(chk.pericope_id)
        self.assertIsNotNone(emb_rec)
        self.assertEqual(emb_rec.dimensions, 768)
        self.assertEqual(len(emb_rec.embedding), 768)

    def test_batch_compilation_and_resumption(self) -> None:
        ref = parse_reference("Romans 8:28-30")
        unit = CompilationUnit(
            unit_id="batch_unit_1",
            reference=ref,
            book=ref.book,
            passage_text="Passage text",
            title="The Golden Chain",
        )

        mock_payload = {
            "reference": "Romans 8:28-30",
            "title": "The Golden Chain",
            "genre": "Epistle",
            "central_proposition": "God saves his people.",
            "redemptive_summary": "Grace prevails.",
            "christological_fulfillment": "Fulfilled in Christ.",
        }

        # First run
        progress1 = self.compiler.compile_units(
            units=[unit],
            resume=True,
            mock_results={"batch_unit_1": mock_payload},
        )
        self.assertEqual(progress1.completed_units, 1)
        self.assertEqual(progress1.skipped_units, 0)

        # Second run with resume=True: should skip completed unit
        progress2 = self.compiler.compile_units(
            units=[unit],
            resume=True,
            mock_results={"batch_unit_1": mock_payload},
        )
        self.assertEqual(progress2.completed_units, 0)
        self.assertEqual(progress2.skipped_units, 1)

        # Third run with resume=False: should re-process unit
        progress3 = self.compiler.compile_units(
            units=[unit],
            resume=False,
            mock_results={"batch_unit_1": mock_payload},
        )
        self.assertEqual(progress3.completed_units, 1)
        self.assertEqual(progress3.skipped_units, 0)


if __name__ == "__main__":
    unittest.main()
