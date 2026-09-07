import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from core.db import Database, TagRecord, VerseRecord, VerseTagRecord
from core.reference import Reference, parse_reference
from core.tags import (
    CANONICAL_TAXONOMY,
    TagCategory,
    TagSummary,
    TaggedPassage,
    TaggingService,
)
from core.terminal import (
    format_tag_table,
    format_tagged_passages,
    format_tags_badge,
    strip_ansi,
)
from cli.main import main, build_parser
from cli.shell import BibleShell


def create_mock_db(db_path: str = ":memory:") -> Database:
    """Create a database populated with test verses and schema."""
    db = Database(db_path)
    # Insert test translation
    with db.conn:
        db.conn.execute(
            """
            INSERT OR REPLACE INTO translations (id, name, language, is_public_domain)
            VALUES ('WEB', 'World English Bible', 'en', 1)
            """
        )

    # Insert sample verses from Romans 8 and John 3
    verses = [
        # John 3:16-17
        VerseRecord(
            translation_id="WEB",
            book_id=43,  # John
            chapter=3,
            verse=16,
            text="For God so loved the world, that he gave his one and only Son...",
        ),
        VerseRecord(
            translation_id="WEB",
            book_id=43,
            chapter=3,
            verse=17,
            text="For God didn't send his Son into the world to judge the world...",
        ),
        # Romans 8:1-5
        VerseRecord(
            translation_id="WEB",
            book_id=45,  # Romans
            chapter=8,
            verse=1,
            text="There is therefore now no condemnation to those who are in Christ Jesus...",
        ),
        VerseRecord(
            translation_id="WEB",
            book_id=45,
            chapter=8,
            verse=2,
            text="For the law of the Spirit of life in Christ Jesus made me free...",
        ),
        VerseRecord(
            translation_id="WEB",
            book_id=45,
            chapter=8,
            verse=3,
            text="For what the law couldn't do, in that it was weak through the flesh, God did...",
        ),
        VerseRecord(
            translation_id="WEB",
            book_id=45,
            chapter=8,
            verse=4,
            text="that the ordinance of the law might be fulfilled in us...",
        ),
        VerseRecord(
            translation_id="WEB",
            book_id=45,
            chapter=8,
            verse=5,
            text="For those who live according to the flesh set their minds on the things of the flesh...",
        ),
    ]
    db.insert_verses(verses)
    return db


class TestTaggingServiceBasics(unittest.TestCase):
    """Test core tag definition lifecycle and taxonomy management."""

    def setUp(self) -> None:
        self.db = create_mock_db()
        self.svc = TaggingService(self.db)

    def tearDown(self) -> None:
        self.db.close()

    def test_add_and_get_tag(self) -> None:
        t = self.svc.add_tag("Grace", category=TagCategory.THEOLOGICAL, description="Unmerited favor")
        self.assertEqual(t.name, "Grace")
        self.assertEqual(t.category, "theological")
        self.assertEqual(t.description, "Unmerited favor")

        fetched = self.svc.get_tag("grace")  # case-insensitive
        self.assertIsNotNone(fetched)
        assert fetched is not None
        self.assertEqual(fetched.name, "Grace")

    def test_add_tag_validation(self) -> None:
        with self.assertRaises(ValueError):
            self.svc.add_tag("   ")

    def test_get_or_create_tag(self) -> None:
        t1 = self.svc.get_or_create_tag("Justification", category=TagCategory.THEOLOGICAL)
        t2 = self.svc.get_or_create_tag("Justification", category=TagCategory.THEOLOGICAL)
        self.assertEqual(t1.id, t2.id)

    def test_delete_tag_cascades(self) -> None:
        self.svc.add_tag("Temporary", category=TagCategory.THEMATIC)
        self.svc.tag_passage("John 3:16", "Temporary")
        self.assertEqual(len(self.svc.get_tags_for_passage("John 3:16")), 1)

        deleted = self.svc.delete_tag("Temporary")
        self.assertTrue(deleted)
        self.assertIsNone(self.svc.get_tag("Temporary"))
        self.assertEqual(len(self.svc.get_tags_for_passage("John 3:16")), 0)

        # Deleting non-existent returns False
        self.assertFalse(self.svc.delete_tag("NonExistent"))

    def test_list_and_search_tags(self) -> None:
        self.svc.add_tag("Holy Spirit", category=TagCategory.THEOLOGICAL, description="Third person of Trinity")
        self.svc.add_tag("Sanctification", category=TagCategory.THEOLOGICAL, description="Progressive growth")
        self.svc.add_tag("Prayer", category=TagCategory.THEMATIC, description="Communion with God")

        all_tags = self.svc.list_tags()
        self.assertEqual(len(all_tags), 3)

        theological_tags = self.svc.list_tags(category=TagCategory.THEOLOGICAL)
        self.assertEqual(len(theological_tags), 2)

        matches = self.svc.search_tags("Trinity")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].name, "Holy Spirit")

    def test_seed_canonical_taxonomies(self) -> None:
        count = self.svc.seed_canonical_taxonomies()
        self.assertGreater(count, 20)
        t = self.svc.get_tag("Creation")
        self.assertIsNotNone(t)
        self.assertEqual(t.category, TagCategory.HISTORICAL)

    def test_export_and_import_taxonomy(self) -> None:
        self.svc.add_tag("Covenant", category=TagCategory.THEOLOGICAL, description="Binding oath")
        exported = self.svc.export_taxonomy()
        self.assertGreaterEqual(len(exported), 1)

        new_db = Database(":memory:")
        try:
            new_svc = TaggingService(new_db)
            imported = new_svc.import_taxonomy(exported)
            self.assertGreaterEqual(imported, 1)
            t = new_svc.get_tag("Covenant")
            self.assertIsNotNone(t)
            self.assertEqual(t.description, "Binding oath")
        finally:
            new_db.close()


class TestPassageTaggingAndSpans(unittest.TestCase):
    """Test passage tagging across verses, arbitrary spans, and chapters."""

    def setUp(self) -> None:
        self.db = create_mock_db()
        self.svc = TaggingService(self.db)

    def tearDown(self) -> None:
        self.db.close()

    def test_tag_single_verse(self) -> None:
        recs = self.svc.tag_passage("John 3:16", "Love", category="thematic", notes="Golden verse", starred=True)
        self.assertEqual(len(recs), 1)
        r = recs[0]
        self.assertEqual(r.tag_name, "Love")
        self.assertEqual(r.human_ref, "John 3:16")
        self.assertTrue(r.starred)
        self.assertEqual(r.notes, "Golden verse")

    def test_tag_arbitrary_span_and_spans_table_link(self) -> None:
        recs = self.svc.tag_passage(
            "Romans 8:1-4",
            ["Holy Spirit", "Sanctification"],
            category="theological",
            notes="No condemnation",
        )
        self.assertEqual(len(recs), 2)
        for r in recs:
            self.assertEqual(r.human_ref, "Romans 8:1-4")
            # Verify span_id is registered and linked
            self.assertIsNotNone(r.span_id)
            span = self.db.get_span(r.span_id)
            self.assertIsNotNone(span)
            self.assertEqual(span.human_ref, "Romans 8:1-4")

    def test_tag_passage_idempotency(self) -> None:
        # First call
        r1 = self.svc.tag_passage("John 3:16", "Faith", notes="Initial note")
        # Second call with updated notes and star
        r2 = self.svc.tag_passage("John 3:16", "Faith", notes="Updated note", starred=True)
        self.assertEqual(r1[0].id, r2[0].id)
        self.assertTrue(r2[0].starred)
        self.assertEqual(r2[0].notes, "Updated note")

        # Ensure no duplicate rows created
        tags = self.svc.get_tags_for_passage("John 3:16", exact_only=True)
        self.assertEqual(len(tags), 1)

    def test_untag_passage(self) -> None:
        self.svc.tag_passage("Romans 8:1-4", ["Holy Spirit", "Sanctification"])
        self.assertEqual(len(self.svc.get_tags_for_passage("Romans 8:1-4", exact_only=True)), 2)

        deleted = self.svc.untag_passage("Romans 8:1-4", "Holy Spirit")
        self.assertEqual(deleted, 1)

        remaining = self.svc.get_tags_for_passage("Romans 8:1-4", exact_only=True)
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].tag_name, "Sanctification")

        # Untag non-existent
        self.assertEqual(self.svc.untag_passage("Romans 8:1-4", "NonExistent"), 0)

    def test_multi_tag_comma_separated_string(self) -> None:
        recs = self.svc.tag_passage("John 3:16", "Salvation, Grace, Eternal Life")
        self.assertEqual(len(recs), 3)
        tag_names = [r.tag_name for r in recs]
        self.assertIn("Salvation", tag_names)
        self.assertIn("Grace", tag_names)
        self.assertIn("Eternal Life", tag_names)


class TestTagQueriesAndHydration(unittest.TestCase):
    """Test resolution semantics (exact vs overlapping) and hydrated passage rendering."""

    def setUp(self) -> None:
        self.db = create_mock_db()
        self.svc = TaggingService(self.db)
        # Setup tags on different scopes
        # 1. Whole chapter: Romans 8
        self.svc.tag_passage("Romans 8", "Christian Life")
        # 2. Multi-verse span: Romans 8:1-4
        self.svc.tag_passage("Romans 8:1-4", "No Condemnation", starred=True)
        # 3. Single verse: Romans 8:1
        self.svc.tag_passage("Romans 8:1", "Freedom")

    def tearDown(self) -> None:
        self.db.close()

    def test_overlapping_queries(self) -> None:
        # Querying Romans 8:1 should match all 3: Freedom (exact), No Condemnation (span), Christian Life (chapter)
        tags_v1 = self.svc.get_tags_for_passage("Romans 8:1")
        names_v1 = [t.tag_name for t in tags_v1]
        self.assertIn("Freedom", names_v1)
        self.assertIn("No Condemnation", names_v1)
        self.assertIn("Christian Life", names_v1)

        # Querying Romans 8:3 should match No Condemnation (span) and Christian Life (chapter), but NOT Freedom
        tags_v3 = self.svc.get_tags_for_passage("Romans 8:3")
        names_v3 = [t.tag_name for t in tags_v3]
        self.assertNotIn("Freedom", names_v3)
        self.assertIn("No Condemnation", names_v3)
        self.assertIn("Christian Life", names_v3)

        # Querying Romans 8:5 should match Christian Life (chapter), but NOT Freedom or No Condemnation
        tags_v5 = self.svc.get_tags_for_passage("Romans 8:5")
        names_v5 = [t.tag_name for t in tags_v5]
        self.assertEqual(names_v5, ["Christian Life"])

    def test_exact_queries(self) -> None:
        # Exact on Romans 8:1
        exact_v1 = self.svc.get_tags_for_passage("Romans 8:1", exact_only=True)
        self.assertEqual([t.tag_name for t in exact_v1], ["Freedom"])

        # Exact on Romans 8:1-4
        exact_span = self.svc.get_tags_for_passage("Romans 8:1-4", exact_only=True)
        self.assertEqual([t.tag_name for t in exact_span], ["No Condemnation"])

    def test_get_passages_for_tag_hydrated(self) -> None:
        passages = self.svc.get_passages_for_tag("No Condemnation", translation_id="WEB")
        self.assertEqual(len(passages), 1)
        p = passages[0]
        self.assertEqual(p.human_ref, "Romans 8:1-4")
        self.assertTrue(p.starred)
        self.assertEqual(p.verse_count, 4)
        self.assertIn("There is therefore now no condemnation", p.text)
        self.assertIn("that the ordinance of the law might be fulfilled", p.text)

        p_dict = p.to_dict()
        self.assertEqual(p_dict["verse_count"], 4)
        self.assertEqual(len(p_dict["verses"]), 4)

    def test_tag_stats(self) -> None:
        stats = self.svc.get_tag_stats("No Condemnation")
        self.assertIsNotNone(stats)
        assert stats is not None
        self.assertEqual(stats["passage_count"], 1)
        self.assertEqual(stats["starred_count"], 1)
        self.assertEqual(stats["distinct_books"], 1)


class TestTerminalTagFormatting(unittest.TestCase):
    """Test terminal formatting badges, tables, and passage output."""

    def test_format_tags_badge(self) -> None:
        badge_styled = format_tags_badge(["Grace", "Faith"], styling=True)
        self.assertIn("Grace", badge_styled)
        self.assertIn("Faith", badge_styled)

        badge_plain = format_tags_badge(["Grace", "Faith"], styling=False)
        self.assertEqual(badge_plain, "Tags: [Grace] [Faith]")

        self.assertEqual(format_tags_badge([]), "")

    def test_format_tag_table(self) -> None:
        summaries = [
            TagSummary(
                id=1,
                name="Holy Spirit",
                category="theological",
                description="Third person of Trinity",
                passage_count=12,
                starred_count=3,
                distinct_books=4,
            )
        ]
        table_str = format_tag_table(summaries, styling=False)
        self.assertIn("Tag Name", table_str)
        self.assertIn("Holy Spirit", table_str)
        self.assertIn("theological", table_str)
        self.assertIn("12", table_str)

    def test_format_tagged_passages(self) -> None:
        verses = [
            VerseRecord(
                translation_id="WEB",
                book_id=43,
                chapter=3,
                verse=16,
                text="For God so loved the world...",
            )
        ]
        tp = TaggedPassage(
            id=1,
            tag_id=1,
            tag_name="Love",
            reference=parse_reference("John 3:16"),
            human_ref="John 3:16",
            confidence=1.0,
            source="user",
            starred=True,
            notes="Evangelistic",
            span_id=None,
            created_at=None,
            verses=verses,
        )
        out = format_tagged_passages([tp], styling=False)
        self.assertIn("John 3:16 ★", out)
        self.assertIn("For God so loved the world...", out)
        self.assertIn("Note: Evangelistic", out)


class TestCliTagCommands(unittest.TestCase):
    """Test CLI subcommand integration for `./bible tag` and `./bible get --tags`."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test_bible.db")
        self.db = create_mock_db(self.db_path)

    def tearDown(self) -> None:
        self.db.close()
        self.temp_dir.cleanup()

    def test_cli_tag_add_and_show(self) -> None:
        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = main(["--db", self.db_path, "tag", "add", "Romans 8:1-3", "Atonement", "Grace", "--starred", "--notes", "Key passage"])
            self.assertEqual(code, 0)
        output = stdout.getvalue()
        self.assertIn("Successfully tagged Romans 8:1-3 with 2 tag(s)", output)

        stdout_show = io.StringIO()
        with patch("sys.stdout", stdout_show):
            code = main(["--db", self.db_path, "tag", "show", "Atonement"])
            self.assertEqual(code, 0)
        show_output = stdout_show.getvalue()
        self.assertIn("Tag: Atonement", show_output)
        self.assertIn("Romans 8:1-3", show_output)
        self.assertIn("There is therefore now no condemnation", show_output)

    def test_cli_tag_list_json(self) -> None:
        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = main(["--db", self.db_path, "tag", "list", "--json"])
            self.assertEqual(code, 0)
        data = json.loads(stdout.getvalue())
        self.assertIsInstance(data, list)

    def test_cli_tag_for(self) -> None:
        with patch("sys.stdout", io.StringIO()):
            main(["--db", self.db_path, "tag", "add", "Romans 8:1-4", "Sanctification"])
        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = main(["--db", self.db_path, "tag", "for", "Romans 8:2"])
            self.assertEqual(code, 0)
        out = stdout.getvalue()
        self.assertIn("Sanctification [Romans 8:1-4]", out)

    def test_cli_tag_remove(self) -> None:
        with patch("sys.stdout", io.StringIO()):
            main(["--db", self.db_path, "tag", "add", "Romans 8:1-4", "Temporary"])
        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = main(["--db", self.db_path, "tag", "remove", "Romans 8:1-4", "Temporary"])
            self.assertEqual(code, 0)
        self.assertIn("Removed tag 'Temporary' from Romans 8:1-4", stdout.getvalue())

    def test_cli_get_with_tags_flag(self) -> None:
        with patch("sys.stdout", io.StringIO()):
            main(["--db", self.db_path, "tag", "add", "John 3:16", "Gospel"])
        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = main(["--db", self.db_path, "get", "John 3:16", "--tags"])
            self.assertEqual(code, 0)
        self.assertIn("Tags: [Gospel]", stdout.getvalue())


class TestShellTagCommands(unittest.TestCase):
    """Test interactive shell /tag command execution and autocompletion."""

    def setUp(self) -> None:
        self.db = create_mock_db()
        self.out = io.StringIO()
        self.shell = BibleShell(db_path=str(self.db.db_path), stdout=self.out, database=self.db)

    def tearDown(self) -> None:
        self.db.close()

    def test_shell_tag_add_and_for(self) -> None:
        self.shell.onecmd('/tag add "John 3:16" "Salvation"')
        self.assertIn("Successfully tagged John 3:16 with 1 tag(s)", self.out.getvalue())

        out_for = io.StringIO()
        self.shell.stdout = out_for
        self.shell.onecmd('/tag for "John 3:16"')
        self.assertIn("Salvation [John 3:16]", out_for.getvalue())

    def test_shell_tag_completion(self) -> None:
        # Subcommand completion
        matches = self.shell.complete_tag("sh", "tag sh", 4, 6)
        self.assertEqual(matches, ["show"])

        # Tag name completion
        self.shell.onecmd('/tag add "John 3:16" "Resurrection"')
        tag_matches = self.shell.complete_tag("Res", "tag show Res", 9, 12)
        self.assertEqual(tag_matches, ["Resurrection"])


if __name__ == "__main__":
    unittest.main()
