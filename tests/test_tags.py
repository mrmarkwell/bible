import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from core.db import Database, VerseRecord
from core.reference import parse_reference
from core.tags import (
    TagCategory,
    TagCoOccurrenceMatrix,
    TagSummary,
    TaggedPassage,
    TaggingService,
    VerseTagRecord,
)
from core.terminal import (
    format_tag_co_occurrence_table,
    format_tag_table,
    format_tagged_passages,
    format_tags_badge,
    format_topic_density_table,
    format_verse_relevance_table,
)
from cli.main import main
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
        self.assertEqual(t.name, "grace")
        self.assertEqual(t.category, "theological")
        self.assertEqual(t.description, "Unmerited favor")

        fetched = self.svc.get_tag("grace")  # case-insensitive
        self.assertIsNotNone(fetched)
        assert fetched is not None
        self.assertEqual(fetched.name, "grace")

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
        self.assertEqual(matches[0].name, "holy_spirit")

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

    def test_normalize_tag_name_and_pruning(self) -> None:
        from core.tags import normalize_tag_name
        self.assertEqual(normalize_tag_name("Holy Spirit"), "holy_spirit")
        self.assertEqual(normalize_tag_name("#starred"), "starred")
        self.assertEqual(normalize_tag_name("sovereign-grace"), "sovereign_grace")
        self.assertEqual(normalize_tag_name("Faith & Works"), "faith_works")
        with self.assertRaises(ValueError):
            normalize_tag_name("   ")

        # Test prune unlinked tags
        self.svc.add_tag("unlinked_one")
        self.svc.add_tag("favorites")  # protected by default
        self.svc.add_tag("starred")    # protected by default
        self.svc.tag_passage("John 3:16", "linked_tag")
        pruned_count = self.svc.prune_unlinked_tags()
        self.assertGreaterEqual(pruned_count, 1)
        self.assertIsNone(self.svc.get_tag("unlinked_one"))
        self.assertIsNotNone(self.svc.get_tag("favorites"))
        self.assertIsNotNone(self.svc.get_tag("starred"))
        self.assertIsNotNone(self.svc.get_tag("linked_tag"))

    def test_starred_tag_unification_and_migration(self) -> None:
        """Test ADR-080 / Task 3.6: Universal Tagging Unification for #starred."""
        # 1. Tag a passage with starred=True creates both the tag and the #starred tag
        recs = self.svc.tag_passage("John 3:16", "salvation", starred=True)
        self.assertEqual(len(recs), 1)
        self.assertTrue(recs[0].starred)

        # Verify 'starred' tag now exists and contains John 3:16
        starred_tag = self.svc.get_tag("starred")
        self.assertIsNotNone(starred_tag)
        starred_passages = self.svc.get_passages_for_tag("starred")
        self.assertEqual(len(starred_passages), 1)
        self.assertEqual(starred_passages[0].human_ref, "John 3:16")

        # 2. Tag multiple with batch
        items = [
            ("Romans 8:1", True, "Key verse"),
            ("Romans 8:2", False, "Normal verse"),
        ]
        self.db.tag_references_batch(items, tag_name="romans_test")
        starred_passages = self.svc.get_passages_for_tag("starred")
        refs = [p.human_ref for p in starred_passages]
        self.assertIn("John 3:16", refs)
        self.assertIn("Romans 8:1", refs)
        self.assertNotIn("Romans 8:2", refs)

        # 3. Idempotent migration
        migrated = self.db.migrate_starred_to_tag()
        self.assertEqual(migrated, 0)  # already synchronized

        # 4. Untagging 'starred' clears starred status
        deleted = self.svc.untag_passage("Romans 8:1", "starred")
        self.assertEqual(deleted, 1)
        tags_r8 = self.svc.get_tags_for_passage("Romans 8:1", exact_only=True)
        for t in tags_r8:
            self.assertFalse(t.starred)



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
        self.assertEqual(r.tag_name, "love")
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

        # Ensure no duplicate rows created for the tag itself, plus the unified #starred tag
        tags = self.svc.get_tags_for_passage("John 3:16", exact_only=True)
        tag_names = {t.tag_name for t in tags}
        self.assertIn("faith", tag_names)
        self.assertIn("starred", tag_names)
        self.assertEqual(len(tags), 2)

    def test_untag_passage(self) -> None:
        self.svc.tag_passage("Romans 8:1-4", ["Holy Spirit", "Sanctification"])
        self.assertEqual(len(self.svc.get_tags_for_passage("Romans 8:1-4", exact_only=True)), 2)

        deleted = self.svc.untag_passage("Romans 8:1-4", "Holy Spirit")
        self.assertEqual(deleted, 1)

        remaining = self.svc.get_tags_for_passage("Romans 8:1-4", exact_only=True)
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].tag_name, "sanctification")

        # Untag non-existent
        self.assertEqual(self.svc.untag_passage("Romans 8:1-4", "NonExistent"), 0)

    def test_multi_tag_comma_separated_string(self) -> None:
        recs = self.svc.tag_passage("John 3:16", "Salvation, Grace, Eternal Life")
        self.assertEqual(len(recs), 3)
        tag_names = [r.tag_name for r in recs]
        self.assertIn("salvation", tag_names)
        self.assertIn("grace", tag_names)
        self.assertIn("eternal_life", tag_names)


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
        # Querying Romans 8:1 should match all 3: freedom (exact), no_condemnation (span), christian_life (chapter)
        tags_v1 = self.svc.get_tags_for_passage("Romans 8:1")
        names_v1 = [t.tag_name for t in tags_v1]
        self.assertIn("freedom", names_v1)
        self.assertIn("no_condemnation", names_v1)
        self.assertIn("christian_life", names_v1)

        # Querying Romans 8:3 should match no_condemnation (span) and christian_life (chapter), but NOT freedom
        tags_v3 = self.svc.get_tags_for_passage("Romans 8:3")
        names_v3 = [t.tag_name for t in tags_v3]
        self.assertNotIn("freedom", names_v3)
        self.assertIn("no_condemnation", names_v3)
        self.assertIn("christian_life", names_v3)

        # Querying Romans 8:5 should match christian_life (chapter), but NOT freedom or no_condemnation
        tags_v5 = self.svc.get_tags_for_passage("Romans 8:5")
        names_v5 = [t.tag_name for t in tags_v5]
        self.assertEqual(names_v5, ["christian_life"])

    def test_exact_queries(self) -> None:
        # Exact on Romans 8:1
        exact_v1 = self.svc.get_tags_for_passage("Romans 8:1", exact_only=True)
        self.assertEqual([t.tag_name for t in exact_v1], ["freedom"])

        # Exact on Romans 8:1-4 (matches 'no_condemnation' and unified 'starred')
        exact_span = self.svc.get_tags_for_passage("Romans 8:1-4", exact_only=True)
        exact_names = {t.tag_name for t in exact_span}
        self.assertEqual(exact_names, {"no_condemnation", "starred"})

    def test_get_passages_for_tag_hydrated(self) -> None:
        passages = self.svc.get_passages_for_tag("no_condemnation", translation_id="WEB")
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
        stats = self.svc.get_tag_stats("no_condemnation")
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

        # Test single-verse vs passage-span distinction
        single_verse_tag = VerseTagRecord(
            id=1,
            tag_id=10,
            tag_name="Grace",
            start_canonical_id=43003016,
            end_canonical_id=43003016,
            human_ref="John 3:16",
        )
        passage_span_tag = VerseTagRecord(
            id=2,
            tag_id=20,
            tag_name="Sovereignty",
            start_canonical_id=45008028,
            end_canonical_id=45008030,
            human_ref="Romans 8:28-30",
        )
        badge_spans_styled = format_tags_badge([single_verse_tag, passage_span_tag], styling=True)
        self.assertIn("●", badge_spans_styled)
        self.assertIn("§", badge_spans_styled)
        self.assertIn("Grace", badge_spans_styled)
        self.assertIn("Sovereignty", badge_spans_styled)

        badge_spans_plain = format_tags_badge([single_verse_tag, passage_span_tag], styling=False)
        self.assertEqual(badge_spans_plain, "Tags: [● Grace] [§ Sovereignty]")

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
        self.assertIn("Tag: atonement", show_output)
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
        self.assertIn("sanctification [Romans 8:1-4]", out)

    def test_cli_tag_remove(self) -> None:
        with patch("sys.stdout", io.StringIO()):
            main(["--db", self.db_path, "tag", "add", "Romans 8:1-4", "Temporary"])
        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = main(["--db", self.db_path, "tag", "remove", "Romans 8:1-4", "Temporary"])
            self.assertEqual(code, 0)
        self.assertIn("Removed tag 'Temporary' from Romans 8:1-4.", stdout.getvalue())

    def test_cli_get_with_tags_flag(self) -> None:
        with patch("sys.stdout", io.StringIO()):
            main(["--db", self.db_path, "tag", "add", "John 3:16", "Gospel"])
        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = main(["--db", self.db_path, "get", "John 3:16", "--tags"])
            self.assertEqual(code, 0)
        self.assertIn("Tags: [● gospel]", stdout.getvalue())


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
        self.assertIn("salvation [John 3:16]", out_for.getvalue())

    def test_shell_tag_completion(self) -> None:
        # Subcommand completion
        matches = self.shell.complete_tag("sh", "tag sh", 4, 6)
        self.assertEqual(matches, ["show"])

        # Tag name completion
        self.shell.onecmd('/tag add "John 3:16" "Resurrection"')
        tag_matches = self.shell.complete_tag("res", "tag show res", 9, 12)
        self.assertEqual(tag_matches, ["resurrection"])


class TestTagAggregationAnalytics(unittest.TestCase):
    """Hermetic unit tests for Task 3.4 aggregation queries and relevance scoring."""

    def setUp(self) -> None:
        self.db = create_mock_db()
        self.svc = TaggingService(self.db)
        # Tag several passages
        self.svc.tag_passage("Romans 8:1-4", ["Sanctification", "Grace"], category="theological", starred=True, confidence=0.95)
        self.svc.tag_passage("Romans 8:5", ["Flesh", "Sanctification"], category="theological", starred=False, confidence=0.85)
        self.svc.tag_passage("John 3:16", ["Gospel", "Grace", "Love"], category="thematic", starred=True, confidence=1.0)
        self.svc.tag_passage("John 3:17", ["Gospel"], category="thematic", starred=False, confidence=0.90)

    def tearDown(self) -> None:
        self.db.close()

    def test_topic_density_per_book(self) -> None:
        # All books with passages
        densities = self.svc.get_topic_density_per_book(min_passages=1)
        self.assertEqual(len(densities), 2)  # John and Romans

        # John (book_id 43)
        john = next(d for d in densities if d.book_name == "John")
        self.assertEqual(john.passage_count, 2)
        self.assertEqual(john.starred_count, 1)
        self.assertEqual(john.distinct_tags, 4)  # gospel, grace, love, starred
        self.assertEqual(john.tag_counts["gospel"], 2)
        self.assertEqual(john.tag_counts["grace"], 1)

        # Romans (book_id 45)
        romans = next(d for d in densities if d.book_name == "Romans")
        self.assertEqual(romans.passage_count, 2)
        self.assertEqual(romans.starred_count, 1)
        self.assertEqual(romans.distinct_tags, 4)  # sanctification, grace, flesh, starred
        self.assertEqual(romans.tag_counts["sanctification"], 2)

        # Filter by specific tag
        grace_density = self.svc.get_topic_density_per_book(tag_name="Grace", min_passages=1)
        self.assertEqual(len(grace_density), 2)

        # Filter by category
        thematic_density = self.svc.get_topic_density_per_book(category="thematic", min_passages=1)
        self.assertEqual(len(thematic_density), 1)
        self.assertEqual(thematic_density[0].book_name, "John")

        # Filter by testament
        ot_density = self.svc.get_topic_density_per_book(testament="OT", min_passages=1)
        self.assertEqual(len(ot_density), 0)

        # Formatting table
        table_output = format_topic_density_table(densities, styling=False)
        self.assertIn("John", table_output)
        self.assertIn("Romans", table_output)
        self.assertIn("gospel (2)", table_output)

    def test_tag_co_occurrence_matrix(self) -> None:
        res = self.svc.get_tag_co_occurrences(min_co_occurrences=1)
        self.assertIsInstance(res, TagCoOccurrenceMatrix)

        # Sanctification and Grace co-occur on Romans 8:1-4
        pairs = res.pair_metrics
        pair_names = {(p.tag_a, p.tag_b) for p in pairs} | {(p.tag_b, p.tag_a) for p in pairs}
        self.assertIn(("grace", "sanctification"), pair_names)
        self.assertIn(("gospel", "grace"), pair_names)
        self.assertIn(("flesh", "sanctification"), pair_names)

        # Check Jaccard similarity between Grace and Sanctification
        # Grace = 2 passages (Rom 8:1-4, John 3:16)
        # Sanctification = 2 passages (Rom 8:1-4, Rom 8:5)
        # Intersection = 1 passage (Rom 8:1-4)
        # Union = 3 passages -> Jaccard = 1/3 = 0.3333
        p_sg = next(p for p in pairs if (p.tag_a == "grace" and p.tag_b == "sanctification") or (p.tag_a == "sanctification" and p.tag_b == "grace"))
        self.assertEqual(p_sg.shared_passages, 1)
        self.assertAlmostEqual(p_sg.jaccard_similarity, 1.0 / 3.0, places=3)
        self.assertAlmostEqual(p_sg.dice_coefficient, 2.0 * 1.0 / (2 + 2), places=3)

        # Matrix dict access
        self.assertEqual(res.matrix["grace"]["sanctification"], 1)
        self.assertEqual(res.matrix["sanctification"]["grace"], 1)
        self.assertEqual(res.matrix["grace"]["grace"], 2)

        # Formatting table
        output = format_tag_co_occurrence_table(pairs, styling=False)
        self.assertIn("grace", output)
        self.assertIn("sanctification", output)
        self.assertIn("Jaccard Index", output)

    def test_verse_relevance_scoring(self) -> None:
        # Score query for ['Grace', 'Sanctification']
        rankings = self.svc.score_verse_relevance(["Grace", "Sanctification"], translation_id="WEB")
        self.assertTrue(len(rankings) >= 2)

        # Romans 8:1-4 matches BOTH Grace and Sanctification, and is starred -> highest score
        top = rankings[0]
        self.assertEqual(top.human_ref, "Romans 8:1-4")
        self.assertTrue(top.starred)
        self.assertEqual(top.matched_tags, ["grace", "sanctification"])
        self.assertEqual(top.match_ratio, 1.0)
        self.assertTrue(top.score > 0.8)
        self.assertIn("There is therefore now no condemnation", top.text)

        # Passages matching only 1 tag should have lower score
        second = rankings[1]
        self.assertTrue(top.score > second.score)

        # Formatting relevance table
        formatted = format_verse_relevance_table(rankings, styling=False)
        self.assertIn("#1 Romans 8:1-4 ★", formatted)
        self.assertIn("Score:", formatted)
        self.assertIn("100% match", formatted)

    def test_cli_density_command(self) -> None:
        temp_dir = tempfile.TemporaryDirectory()
        db_path = str(Path(temp_dir.name) / "test_density.db")
        db = create_mock_db(db_path)
        svc = TaggingService(db)
        svc.tag_passage("Romans 8:1", ["Atonement"])
        db.close()

        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = main(["--db", db_path, "tag", "density", "--json"])
            self.assertEqual(code, 0)
        data = json.loads(stdout.getvalue())
        self.assertIsInstance(data, list)
        self.assertTrue(any(d["book_name"] == "Romans" for d in data))

        # Test text output
        stdout_txt = io.StringIO()
        with patch("sys.stdout", stdout_txt):
            code = main(["--db", db_path, "tag", "density"])
            self.assertEqual(code, 0)
        self.assertIn("Topic Density Distribution Across Books", stdout_txt.getvalue())
        self.assertIn("Romans", stdout_txt.getvalue())
        temp_dir.cleanup()

    def test_cli_cooccurrence_and_relevance_commands(self) -> None:
        temp_dir = tempfile.TemporaryDirectory()
        db_path = str(Path(temp_dir.name) / "test_co.db")
        db = create_mock_db(db_path)
        svc = TaggingService(db)
        svc.tag_passage("John 3:16", ["Gospel", "Love"])
        db.close()

        # Co-occurrence CLI
        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = main(["--db", db_path, "tag", "co-occurrence", "--json"])
            self.assertEqual(code, 0)
        data = json.loads(stdout.getvalue())
        self.assertIn("pairs", data)
        self.assertTrue(any(p["tag_a"] in ("gospel", "love") for p in data["pairs"]))

        # Relevance CLI
        stdout_rel = io.StringIO()
        with patch("sys.stdout", stdout_rel):
            code = main(["--db", db_path, "tag", "relevance", "Gospel", "Love", "--json"])
            self.assertEqual(code, 0)
        rel_data = json.loads(stdout_rel.getvalue())
        self.assertEqual(len(rel_data), 1)
        self.assertEqual(rel_data[0]["reference"], "John 3:16")

        temp_dir.cleanup()

    def test_shell_aggregation_commands(self) -> None:
        out = io.StringIO()
        with BibleShell(db_path=str(self.db.db_path), stdout=out, database=self.db) as shell:
            # /tag density
            shell.onecmd("/tag density")
            self.assertIn("Topic Density Distribution", out.getvalue())

            # /tag co-occurrence
            out_co = io.StringIO()
            shell.stdout = out_co
            shell.onecmd("/tag co-occurrence")
            self.assertIn("Tag Co-Occurrence Analysis", out_co.getvalue())

            # /tag relevance
            out_rel = io.StringIO()
            shell.stdout = out_rel
            shell.onecmd("/tag relevance Grace Sanctification")
            self.assertIn("Scripture Passage Relevance Rankings", out_rel.getvalue())

            # Autocompletion
            matches = shell.complete_tag("den", "tag den", 4, 7)
            self.assertEqual(matches, ["density"])
            rel_matches = shell.complete_tag("rel", "tag rel", 4, 7)
            self.assertEqual(rel_matches, ["relevance"])
            rib_matches = shell.complete_tag("rib", "tag rib", 4, 7)
            self.assertEqual(rib_matches, ["ribbon"])


class TestRedemptiveRibbon(unittest.TestCase):
    """Hermetic unit tests for the Canonical Redemptive Ribbon ASCII visualizer."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test_ribbon.db")
        self.db = create_mock_db(self.db_path)
        self.svc = TaggingService(self.db)
        self.svc.seed_canonical_taxonomies()

    def tearDown(self) -> None:
        self.db.close()
        self.temp_dir.cleanup()

    def test_format_redemptive_ribbon_ascii(self) -> None:
        from core.terminal import format_redemptive_ribbon_ascii
        densities = self.svc.get_topic_density_per_book()
        self.assertEqual(len(densities), 66)

        # Plain mode
        plain_out = format_redemptive_ribbon_ascii(densities, styling=False)
        self.assertIn("CANONICAL REDEMPTIVE RIBBON", plain_out)
        self.assertIn("Law (Torah / Pentateuch)", plain_out)
        self.assertIn("Pauline Epistles", plain_out)
        self.assertIn("Gen:", plain_out)
        self.assertIn("Rom:", plain_out)
        self.assertIn("Rev:", plain_out)

        # Styled mode
        styled_out = format_redemptive_ribbon_ascii(densities, styling=True, tag_name="sovereign_grace")
        self.assertIn("#sovereign_grace", styled_out)
        self.assertIn("\033[", styled_out)

    def test_cli_ribbon_subcommand(self) -> None:
        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = main(["--db", self.db_path, "ribbon"])
            self.assertEqual(code, 0)
        out = stdout.getvalue()
        self.assertIn("CANONICAL REDEMPTIVE RIBBON", out)
        self.assertIn("Active Books:", out)

    def test_cli_tag_density_ribbon_flag(self) -> None:
        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = main(["--db", self.db_path, "tag", "density", "--ribbon"])
            self.assertEqual(code, 0)
        out = stdout.getvalue()
        self.assertIn("CANONICAL REDEMPTIVE RIBBON", out)

    def test_shell_ribbon_commands(self) -> None:
        out = io.StringIO()
        with BibleShell(db_path=self.db_path, stdout=out, database=self.db) as shell:
            # /ribbon command
            shell.onecmd("/ribbon")
            self.assertIn("CANONICAL REDEMPTIVE RIBBON", out.getvalue())

            # /tag ribbon command
            out_tag = io.StringIO()
            shell.stdout = out_tag
            shell.onecmd("/tag ribbon")
            self.assertIn("CANONICAL REDEMPTIVE RIBBON", out_tag.getvalue())

            # /ribbon auto-completion
            rib_matches = shell.complete_ribbon("sov", "ribbon sov", 7, 10)
            self.assertTrue(any("sovereign_grace" in m for m in rib_matches))

    def test_get_topic_density_per_chapter(self) -> None:
        chapters = self.svc.get_topic_density_per_chapter(book="Genesis")
        self.assertEqual(len(chapters), 50)
        self.assertEqual(chapters[0].chapter, 1)
        self.assertEqual(chapters[0].book_name, "Genesis")
        d = chapters[0].to_dict()
        self.assertEqual(d["chapter"], 1)
        self.assertEqual(d["book_name"], "Genesis")

        # Test CLI chapters subcommand
        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = main(["--db", self.db_path, "chapters", "Genesis", "--json"])
            self.assertEqual(code, 0)
        data = json.loads(stdout.getvalue())
        self.assertEqual(len(data), 50)
        self.assertEqual(data[0]["chapter"], 1)

        # Test Shell /chapters command
        out_shell = io.StringIO()
        with BibleShell(db_path=self.db_path, stdout=out_shell, database=self.db) as shell:
            shell.onecmd("/chapters Genesis")
            self.assertIn("CHAPTER DRILL-DOWN HEATMAP: GENESIS", out_shell.getvalue())


if __name__ == "__main__":
    unittest.main()

