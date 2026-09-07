"""Hermetic unit tests for Cross-Referencing & Scripture Relationship Engine.

Zero external dependencies (Python stdlib unittest only per ADR-003).
Covers:
- RelationshipType validation and helpers
- CrossReferenceService linking, unlinking, and batch insertions
- Hydrated cross-reference retrieval with verse text and directionality
- Curated canonical seed dataset ingestion and idempotency
- Multi-hop relationship pathfinding (breadth-first search)
- Cross-reference graph summary metrics
- Terminal formatting (cards, tables, and badge annotations)
- CLI subcommands (bible crossref for/link/unlink/list/path/stats/seed) and --refs flag
- Interactive Scripture REPL shell (/crossref, /xref, /refs) and auto-completion
"""

import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from core.crossref import (
    CANONICAL_CROSS_REFERENCES,
    CrossReferenceService,
    CrossReferenceSummary,
    HydratedCrossReference,
    RelationshipType,
)
from core.db import Database, CrossReferenceRecord, VerseRecord
from core.reference import Reference, parse_reference
from core.terminal import (
    format_cross_reference_table,
    format_cross_references,
    strip_ansi,
)
from cli.main import main, build_parser
from cli.shell import BibleShell


def create_test_db(db_path: str = ":memory:") -> Database:
    """Create a test database populated with schema and canonical sample verses."""
    db = Database(db_path)
    with db.conn:
        db.conn.execute(
            """
            INSERT OR REPLACE INTO translations (id, name, language, is_public_domain)
            VALUES ('WEB', 'World English Bible', 'en', 1)
            """
        )

    verses = [
        # Genesis 3:15
        VerseRecord(
            translation_id="WEB",
            book_id=1,  # Genesis
            chapter=3,
            verse=15,
            text="I will put hostility between you and the woman, and between your offspring and her offspring. He will bruise your head, and you will bruise his heel.",
        ),
        # Galatians 4:4-5
        VerseRecord(
            translation_id="WEB",
            book_id=48,  # Galatians
            chapter=4,
            verse=4,
            text="But when the fullness of the time came, God sent out his Son, born to a woman, born under the law,",
        ),
        VerseRecord(
            translation_id="WEB",
            book_id=48,
            chapter=4,
            verse=5,
            text="that he might redeem those who were under the law, that we might receive the adoption of children.",
        ),
        # Romans 16:20
        VerseRecord(
            translation_id="WEB",
            book_id=45,  # Romans
            chapter=16,
            verse=20,
            text="And the God of peace will quickly crush Satan under your feet. The grace of our Lord Jesus Christ be with you.",
        ),
        # Genesis 12:1-3
        VerseRecord(
            translation_id="WEB",
            book_id=1,
            chapter=12,
            verse=1,
            text="Now the LORD said to Abram, 'Get out of your country... to the land that I will show you.'",
        ),
        VerseRecord(
            translation_id="WEB",
            book_id=1,
            chapter=12,
            verse=2,
            text="I will make of you a great nation. I will bless you and make your name great.",
        ),
        VerseRecord(
            translation_id="WEB",
            book_id=1,
            chapter=12,
            verse=3,
            text="I will bless those who bless you, and whoever curses you I will curse. In you all families of the earth will be blessed.",
        ),
        # Galatians 3:8-9
        VerseRecord(
            translation_id="WEB",
            book_id=48,
            chapter=3,
            verse=8,
            text="The Scripture, foreseeing that God would justify the Gentiles by faith, preached the Good News beforehand to Abraham, saying, 'In you all the nations will be blessed.'",
        ),
        VerseRecord(
            translation_id="WEB",
            book_id=48,
            chapter=3,
            verse=9,
            text="So then, those who are of faith are blessed with the faithful Abraham.",
        ),
        # Galatians 3:16
        VerseRecord(
            translation_id="WEB",
            book_id=48,
            chapter=3,
            verse=16,
            text="Now the promises were spoken to Abraham and to his offspring. He doesn't say, 'To descendants', as of many, but as of one, 'And to your offspring', which is Christ.",
        ),
        # John 3:16
        VerseRecord(
            translation_id="WEB",
            book_id=43,
            chapter=3,
            verse=16,
            text="For God so loved the world, that he gave his one and only Son, that whoever believes in him should not perish, but have eternal life.",
        ),
    ]

    db.insert_verses(verses)

    return db


class TestRelationshipTypes(unittest.TestCase):
    """Verify relationship edge type enumeration and formatting."""

    def test_valid_types(self):
        self.assertTrue(RelationshipType.is_valid("thematic"))
        self.assertTrue(RelationshipType.is_valid("prophecy_fulfillment"))
        self.assertTrue(RelationshipType.is_valid("typology"))
        self.assertTrue(RelationshipType.is_valid("quotation"))
        self.assertTrue(RelationshipType.is_valid("allusion"))
        self.assertTrue(RelationshipType.is_valid("parallel"))
        self.assertFalse(RelationshipType.is_valid("invalid_type"))

    def test_labels_and_icons(self):
        self.assertEqual(RelationshipType.get_label("quotation"), "Direct Citation / Quotation")
        self.assertEqual(RelationshipType.get_icon("prophecy_fulfillment"), "⚡")
        self.assertEqual(RelationshipType.get_icon("typology"), "🏛")


class TestCrossReferenceService(unittest.TestCase):
    """Verify core service edge manipulation, querying, and hydration."""

    def setUp(self):
        self.db = create_test_db()
        self.svc = CrossReferenceService(self.db)

    def tearDown(self):
        self.db.close()

    def test_link_and_get_cross_reference(self):
        edge = self.svc.link_passages(
            source="Genesis 3:15",
            target="Galatians 4:4-5",
            relationship_type="prophecy_fulfillment",
            weight=1.0,
            notes="Protoevangelium fulfillment",
        )
        self.assertIsNotNone(edge.id)
        self.assertEqual(edge.source_human_ref, "Genesis 3:15")
        self.assertEqual(edge.target_human_ref, "Galatians 4:4-5")
        self.assertEqual(edge.relationship_type, "prophecy_fulfillment")

        # Query from source
        src_edges = self.svc.get_cross_references("Genesis 3:15")
        self.assertEqual(len(src_edges), 1)
        self.assertEqual(src_edges[0].target_human_ref, "Galatians 4:4-5")

        # Query from target (bidirectional)
        tgt_edges = self.svc.get_cross_references("Galatians 4:4-5", bidirectional=True)
        self.assertEqual(len(tgt_edges), 1)
        self.assertEqual(tgt_edges[0].source_human_ref, "Genesis 3:15")

        # Query directed only (target should have 0 outgoing)
        directed_edges = self.svc.get_cross_references("Galatians 4:4-5", bidirectional=False)
        self.assertEqual(len(directed_edges), 0)

    def test_invalid_relationship_type_raises(self):
        with self.assertRaises(ValueError):
            self.svc.link_passages("Genesis 1:1", "John 1:1", relationship_type="bad_type")

    def test_hydrated_cross_references(self):
        self.svc.link_passages(
            source="Genesis 3:15",
            target="Galatians 4:4-5",
            relationship_type="prophecy_fulfillment",
            weight=1.0,
            notes="Protoevangelium fulfillment",
        )

        # Query source
        hydrated = self.svc.get_hydrated_cross_references("Genesis 3:15", translation_id="WEB")
        self.assertEqual(len(hydrated), 1)
        h = hydrated[0]
        self.assertEqual(h.direction, "outgoing")
        self.assertEqual(h.related_ref, "Galatians 4:4-5")
        self.assertEqual(len(h.related_verses), 2)  # Galatians 4:4 and 4:5
        self.assertTrue("fullness of the time" in h.to_dict()["related_text"])

        # Query target
        h_tgt = self.svc.get_hydrated_cross_references("Galatians 4:4", translation_id="WEB")
        self.assertEqual(len(h_tgt), 1)
        self.assertEqual(h_tgt[0].direction, "incoming")
        self.assertEqual(h_tgt[0].related_ref, "Genesis 3:15")
        self.assertTrue("bruise your head" in h_tgt[0].to_dict()["related_text"])

    def test_unlink_passages(self):
        self.svc.link_passages("Genesis 3:15", "Galatians 4:4-5", relationship_type="prophecy_fulfillment")
        self.svc.link_passages("Genesis 3:15", "Romans 16:20", relationship_type="thematic")

        deleted = self.svc.unlink_passages("Genesis 3:15", "Galatians 4:4-5")
        self.assertEqual(deleted, 1)

        remaining = self.svc.get_cross_references("Genesis 3:15")
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].target_human_ref, "Romans 16:20")

    def test_seed_canonical_cross_references_and_idempotency(self):
        count1 = self.svc.seed_canonical_cross_references()
        self.assertGreaterEqual(count1, 30)

        # Second seeding should insert 0 duplicates
        count2 = self.svc.seed_canonical_cross_references()
        self.assertEqual(count2, 0)

        # Check Gen 3:15 has multiple connections
        gen3 = self.svc.get_cross_references("Genesis 3:15")
        self.assertGreaterEqual(len(gen3), 2)

    def test_find_path_multihop(self):
        # A -> B -> C
        self.svc.link_passages("Genesis 12:1-3", "Galatians 3:8-9", relationship_type="quotation")
        self.svc.link_passages("Galatians 3:8-9", "Galatians 3:16", relationship_type="thematic")

        path = self.svc.find_path("Genesis 12:1-3", "Galatians 3:16", max_depth=3)
        self.assertIsNotNone(path)
        self.assertEqual(len(path), 2)

        # Direct connection should be 1 hop
        self.svc.link_passages("Genesis 12:1-3", "Galatians 3:16", relationship_type="thematic")
        direct_path = self.svc.find_path("Genesis 12:1-3", "Galatians 3:16", max_depth=2)
        self.assertIsNotNone(direct_path)
        self.assertEqual(len(direct_path), 1)

    def test_summary_statistics(self):
        self.svc.link_passages("Genesis 3:15", "Galatians 4:4-5", relationship_type="prophecy_fulfillment")
        self.svc.link_passages("Genesis 12:1-3", "Galatians 3:8-9", relationship_type="quotation")

        summary = self.svc.get_summary_statistics()
        self.assertEqual(summary.total_edges, 2)
        self.assertEqual(summary.by_relationship_type["prophecy_fulfillment"], 1)
        self.assertEqual(summary.by_relationship_type["quotation"], 1)
        self.assertEqual(summary.testament_connections.get("OT->NT"), 2)


class TestCrossReferenceFormatting(unittest.TestCase):
    """Verify terminal rendering utilities for cross-references."""

    def setUp(self):
        self.db = create_test_db()
        self.svc = CrossReferenceService(self.db)
        self.svc.link_passages(
            "Genesis 3:15",
            "Galatians 4:4-5",
            relationship_type="prophecy_fulfillment",
            weight=1.0,
            notes="The virgin-born Messiah crushing Satan",
        )

    def tearDown(self):
        self.db.close()

    def test_format_cross_references(self):
        hydrated = self.svc.get_hydrated_cross_references("Genesis 3:15", translation_id="WEB")
        output = format_cross_references(hydrated, styling=False)
        self.assertIn("Galatians 4:4-5", output)
        self.assertIn("Prophecy & Fulfillment", output)
        self.assertIn("fullness of the time", output)
        self.assertIn("The virgin-born Messiah", output)

    def test_format_cross_reference_table(self):
        edges = self.svc.list_all_cross_references()
        table = format_cross_reference_table(edges, styling=False)
        self.assertIn("Genesis 3:15", table)
        self.assertIn("Galatians 4:4-5", table)
        self.assertIn("prophecy_fulfillment", table)


class TestCrossReferenceCLI(unittest.TestCase):
    """Verify CLI subcommands and flags for cross-references."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "bible.db"
        db = create_test_db(str(self.db_path))
        svc = CrossReferenceService(db)
        svc.link_passages(
            "Genesis 3:15",
            "Galatians 4:4-5",
            relationship_type="prophecy_fulfillment",
            weight=1.0,
            notes="Seed of woman",
        )
        db.close()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_cli_crossref_for(self):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = main(["--db", str(self.db_path), "crossref", "for", "Genesis 3:15"])
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn("Galatians 4:4-5", out)
        self.assertIn("Prophecy & Fulfillment", out)

    def test_cli_crossref_for_json(self):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = main(["--db", str(self.db_path), "crossref", "for", "Genesis 3:15", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(buf.getvalue())
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["related_ref"], "Galatians 4:4-5")

    def test_cli_crossref_link_and_list(self):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = main([
                "--db", str(self.db_path),
                "crossref", "link",
                "Genesis 12:1-3", "Galatians 3:8-9",
                "--type", "quotation",
                "--notes", "Gospel to Abraham",
            ])
        self.assertEqual(code, 0)
        self.assertIn("Linked Genesis 12:1-3 ➜ Galatians 3:8-9", buf.getvalue())

        buf_list = io.StringIO()
        with patch("sys.stdout", buf_list):
            code = main(["--db", str(self.db_path), "crossref", "list"])
        self.assertEqual(code, 0)
        self.assertIn("Genesis 12:1-3", buf_list.getvalue())

    def test_cli_crossref_unlink(self):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = main(["--db", str(self.db_path), "crossref", "unlink", "Genesis 3:15", "Galatians 4:4-5"])
        self.assertEqual(code, 0)
        self.assertIn("Removed 1 cross-reference edge", buf.getvalue())

    def test_cli_crossref_seed_and_stats(self):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = main(["--db", str(self.db_path), "crossref", "seed"])
        self.assertEqual(code, 0)
        self.assertIn("Successfully seeded", buf.getvalue())

        buf_stats = io.StringIO()
        with patch("sys.stdout", buf_stats):
            code = main(["--db", str(self.db_path), "crossref", "stats"])
        self.assertEqual(code, 0)
        self.assertIn("Cross-Reference Knowledge Graph Statistics", buf_stats.getvalue())

    def test_cli_get_with_refs_flag(self):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = main(["--db", str(self.db_path), "get", "Genesis 3:15", "--refs"])
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn("Cross References", out)
        self.assertIn("Galatians 4:4-5", out)


class TestCrossReferenceShell(unittest.TestCase):
    """Verify interactive scripture shell /crossref and /xref commands."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "bible.db"
        db = create_test_db(str(self.db_path))
        svc = CrossReferenceService(db)
        svc.link_passages("Genesis 3:15", "Galatians 4:4-5", relationship_type="prophecy_fulfillment")
        db.close()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_shell_crossref_for(self):
        out = io.StringIO()
        shell = BibleShell(db_path=self.db_path)
        shell.stdout = out
        shell.do_crossref("for Genesis 3:15")
        self.assertIn("Galatians 4:4-5", out.getvalue())

    def test_shell_xref_alias_and_seed(self):
        out = io.StringIO()
        shell = BibleShell(db_path=self.db_path)
        shell.stdout = out
        shell.do_xref("seed")
        self.assertIn("Successfully seeded", out.getvalue())

    def test_shell_autocompletions(self):
        shell = BibleShell(db_path=self.db_path)
        comps = shell.complete_crossref("", "crossref ", 9, 9)
        self.assertIn("for", comps)
        self.assertIn("link", comps)
        self.assertIn("seed", comps)

        rel_comps = shell.complete_crossref("", "crossref for Gen 3:15 ", 23, 23)
        self.assertIn("prophecy_fulfillment", rel_comps)
        self.assertIn("typology", rel_comps)


if __name__ == '__main__':
    unittest.main()
