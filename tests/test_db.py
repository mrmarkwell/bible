"""Comprehensive Unit Tests for Bible Engine Database Engine (core/db.py).

Zero-dependency tests using Python standard library unittest only (ADR-003).
Hermetic, fast, and thorough verification of SQLite schema, FTS5 search,
canonical indexing, tagging, and cross references.
"""

from pathlib import Path
import tempfile
import unittest

from core.db import (
    CrossReferenceRecord,
    Database,
    SearchResult,
    SpanRecord,
    TagRecord,
    TranslationRecord,
    VerseRecord,
    VerseTagRecord,
    sanitize_fts_query,
)
from core.reference import (
    ALL_BOOKS,
    BOOKS,
    Book,
    Reference,
    get_book,
    parse_reference,
    verse_canonical_id,
    canonical_id_to_triple,
)


class TestFtsSanitizer(unittest.TestCase):
    """Test FTS5 query string sanitization."""

    def test_empty_and_whitespace(self):
        self.assertEqual(sanitize_fts_query(""), "")
        self.assertEqual(sanitize_fts_query("   "), "")

    def test_single_word(self):
        self.assertEqual(sanitize_fts_query("grace"), '"grace"')

    def test_multi_words_default_to_and(self):
        self.assertEqual(sanitize_fts_query("faith hope love"), '"faith" AND "hope" AND "love"')

    def test_explicit_quoted_phrase(self):
        self.assertEqual(
            sanitize_fts_query('"light of the world"'),
            '"light of the world"',
        )

    def test_explicit_boolean_operators(self):
        self.assertEqual(
            sanitize_fts_query("covenant AND promise"),
            '"covenant" AND "promise"',
        )
        self.assertEqual(
            sanitize_fts_query("light OR darkness"),
            '"light" OR "darkness"',
        )
        self.assertEqual(
            sanitize_fts_query("grace NOT law"),
            '"grace" NOT "law"',
        )

    def test_punctuation_stripping(self):
        # Colon, comma, exclamation marks should not cause FTS syntax errors
        res = sanitize_fts_query("John 3:16, 'eternal life'!")
        self.assertIn('"John"', res)
        self.assertIn('"eternal life"', res)


class TestDatabaseCore(unittest.TestCase):
    """Test Database lifecycle, schema initialization, and book catalog seeding."""

    def setUp(self):
        # Fresh in-memory database for each test
        self.db = Database(":memory:")

    def tearDown(self):
        self.db.close()

    def test_books_seeded_automatically(self):
        cur = self.db.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM books")
        count = cur.fetchone()[0]
        self.assertEqual(count, 66)

        # Check Genesis
        cur.execute("SELECT * FROM books WHERE id = 1")
        gen = cur.fetchone()
        self.assertEqual(gen["name"], "Genesis")
        self.assertEqual(gen["osis"], "Gen")
        self.assertEqual(gen["testament"], "OT")
        self.assertEqual(gen["total_chapters"], 50)

        # Check Revelation
        cur.execute("SELECT * FROM books WHERE id = 66")
        rev = cur.fetchone()
        self.assertEqual(rev["name"], "Revelation")
        self.assertEqual(rev["osis"], "Rev")
        self.assertEqual(rev["testament"], "NT")
        self.assertEqual(rev["total_chapters"], 22)

    def test_translations_crud(self):
        # Add WEB
        web = self.db.add_translation(
            translation_id="WEB",
            name="World English Bible",
            language="en",
            is_public_domain=True,
        )
        self.assertEqual(web.id, "WEB")
        self.assertEqual(web.name, "World English Bible")
        self.assertTrue(web.is_public_domain)

        # Add KJV
        kjv = self.db.add_translation(
            translation_id="KJV",
            name="King James Version",
            language="en",
            is_public_domain=True,
        )
        self.assertEqual(kjv.id, "KJV")

        # List translations
        translations = self.db.list_translations()
        self.assertEqual(len(translations), 2)
        ids = [t.id for t in translations]
        self.assertIn("WEB", ids)
        self.assertIn("KJV", ids)

        # Idempotent update
        updated_web = self.db.add_translation(
            translation_id="WEB",
            name="World English Bible (Updated)",
            language="en",
            is_public_domain=True,
        )
        self.assertEqual(updated_web.name, "World English Bible (Updated)")

    def test_context_manager_and_transactions(self):
        with Database(":memory:") as db:
            db.add_translation("WEB", "World English Bible")
            self.assertIsNotNone(db.get_translation("WEB"))

            # Test transaction commit
            with db.transaction():
                db.conn.execute("INSERT INTO tags (name) VALUES ('sovereignty')")

            tag = db.get_tag("sovereignty")
            self.assertIsNotNone(tag)

            # Test transaction rollback on error
            try:
                with db.transaction():
                    db.conn.execute("INSERT INTO tags (name) VALUES ('providence')")
                    raise RuntimeError("Intentional abort")
            except RuntimeError:
                pass

            # 'providence' should have been rolled back
            self.assertIsNone(db.get_tag("providence"))


class TestVerseStorageAndRetrieval(unittest.TestCase):
    """Test verse insertion, querying, and canonical range filtering."""

    def setUp(self):
        self.db = Database(":memory:")
        self.db.add_translation("WEB", "World English Bible")

        # Seed sample verses across Genesis 1 and 2
        self.sample_verses = [
            VerseRecord(
                translation_id="WEB",
                book_id=1,
                chapter=1,
                verse=1,
                text="In the beginning, God created the heavens and the earth.",
            ),
            VerseRecord(
                translation_id="WEB",
                book_id=1,
                chapter=1,
                verse=2,
                text="The earth was formless and empty. Darkness was on the surface of the deep.",
            ),
            VerseRecord(
                translation_id="WEB",
                book_id=1,
                chapter=1,
                verse=3,
                text="God said, 'Let there be light,' and there was light.",
            ),
            VerseRecord(
                translation_id="WEB",
                book_id=1,
                chapter=1,
                verse=4,
                text="God saw the light, and saw that it was good. God divided the light from the darkness.",
            ),
            VerseRecord(
                translation_id="WEB",
                book_id=1,
                chapter=2,
                verse=1,
                text="The heavens and the earth were finished, and all their vast array.",
            ),
            VerseRecord(
                translation_id="WEB",
                book_id=1,
                chapter=2,
                verse=2,
                text="On the seventh day God finished his work which he had done.",
            ),
            # John 3:16
            VerseRecord(
                translation_id="WEB",
                book_id=43,
                chapter=3,
                verse=16,
                text="For God so loved the world, that he gave his one and only Son.",
            ),
            # Romans 8:28-30
            VerseRecord(
                translation_id="WEB",
                book_id=45,
                chapter=8,
                verse=28,
                text="We know that all things work together for good for those who love God.",
            ),
            VerseRecord(
                translation_id="WEB",
                book_id=45,
                chapter=8,
                verse=29,
                text="For whom he foreknew, he also predestined to be conformed to the image of his Son.",
            ),
            VerseRecord(
                translation_id="WEB",
                book_id=45,
                chapter=8,
                verse=30,
                text="Whom he predestined, those he also called. Whom he called, those he also justified.",
            ),
        ]
        self.db.insert_verses(self.sample_verses)

    def tearDown(self):
        self.db.close()

    def test_count_verses(self):
        self.assertEqual(self.db.count_verses(), len(self.sample_verses))
        self.assertEqual(self.db.count_verses("WEB"), len(self.sample_verses))
        self.assertEqual(self.db.count_verses("KJV"), 0)

    def test_get_single_verse(self):
        v = self.db.get_verse("Genesis", 1, 1, translation_id="WEB")
        self.assertIsNotNone(v)
        self.assertEqual(v.text, "In the beginning, God created the heavens and the earth.")
        self.assertEqual(v.canonical_verse_id, 1001001)
        self.assertEqual(v.osis_ref, "Gen.1.1")
        self.assertEqual(v.human_ref, "Genesis 1:1")

        # Non-existent verse
        v_none = self.db.get_verse("Genesis", 1, 99)
        self.assertIsNone(v_none)

    def test_get_verses_single_verse_reference(self):
        verses = self.db.get_verses_by_reference("John 3:16")
        self.assertEqual(len(verses), 1)
        self.assertEqual(verses[0].book_name, "John")
        self.assertEqual(verses[0].chapter, 3)
        self.assertEqual(verses[0].verse, 16)
        self.assertIn("loved the world", verses[0].text)

    def test_get_verses_intra_chapter_range(self):
        verses = self.db.get_verses_by_reference("Genesis 1:2-4")
        self.assertEqual(len(verses), 3)
        self.assertEqual([v.verse for v in verses], [2, 3, 4])

    def test_get_verses_cross_chapter_range(self):
        verses = self.db.get_verses_by_reference("Genesis 1:3 - 2:1")
        self.assertEqual(len(verses), 3)  # Gen 1:3, 1:4, 2:1
        self.assertEqual(verses[0].chapter, 1)
        self.assertEqual(verses[0].verse, 3)
        self.assertEqual(verses[1].chapter, 1)
        self.assertEqual(verses[1].verse, 4)
        self.assertEqual(verses[2].chapter, 2)
        self.assertEqual(verses[2].verse, 1)

    def test_get_verses_whole_chapter(self):
        verses = self.db.get_verses_by_reference("Genesis 1")
        self.assertEqual(len(verses), 4)
        for v in verses:
            self.assertEqual(v.chapter, 1)

    def test_get_verses_multi_chapter_range(self):
        verses = self.db.get_verses_by_reference("Genesis 1-2")
        self.assertEqual(len(verses), 6)

    def test_get_available_translation_ids(self):
        self.assertEqual(self.db.get_available_translation_ids(), ["WEB"])
        # Add another translation and verse
        self.db.add_translation("KJV", "King James Version")
        self.db.insert_verse(
            VerseRecord(
                translation_id="KJV",
                book_id=1,
                chapter=1,
                verse=1,
                text="In the beginning God created the heaven and the earth.",
            )
        )
        self.assertEqual(self.db.get_available_translation_ids(), ["KJV", "WEB"])

    def test_get_verses_with_fallback_direct(self):
        verses, eff_id, is_fb = self.db.get_verses_with_fallback("Genesis 1:1", translation_id="WEB", fallback_id="KJV")
        self.assertEqual(len(verses), 1)
        self.assertEqual(eff_id, "WEB")
        self.assertFalse(is_fb)
        self.assertEqual(verses[0].text, "In the beginning, God created the heavens and the earth.")

    def test_get_verses_with_fallback_triggered(self):
        verses, eff_id, is_fb = self.db.get_verses_with_fallback("Genesis 1:1", translation_id="ESV", fallback_id="WEB")
        self.assertEqual(len(verses), 1)
        self.assertEqual(eff_id, "WEB")
        self.assertTrue(is_fb)

    def test_get_verses_with_fallback_disabled(self):
        verses, eff_id, is_fb = self.db.get_verses_with_fallback("Genesis 1:1", translation_id="ESV", fallback_id=None)
        self.assertEqual(verses, [])
        self.assertEqual(eff_id, "ESV")
        self.assertFalse(is_fb)

    def test_compare_verses(self):
        self.db.add_translation("KJV", "King James Version")
        self.db.insert_verse(
            VerseRecord(
                translation_id="KJV",
                book_id=1,
                chapter=1,
                verse=1,
                text="In the beginning God created the heaven and the earth.",
            )
        )
        res = self.db.compare_verses("Genesis 1:1", translation_ids=["WEB", "KJV", "ESV"], fallback_id="WEB")
        self.assertIn("WEB", res)
        self.assertIn("KJV", res)
        self.assertIn("ESV", res)

        web_verses, web_eff, web_fb = res["WEB"]
        self.assertEqual(web_eff, "WEB")
        self.assertFalse(web_fb)

        kjv_verses, kjv_eff, kjv_fb = res["KJV"]
        self.assertEqual(kjv_eff, "KJV")
        self.assertFalse(kjv_fb)

        esv_verses, esv_eff, esv_fb = res["ESV"]
        self.assertEqual(esv_eff, "WEB")
        self.assertTrue(esv_fb)


class TestFullTextSearch(unittest.TestCase):
    """Test SQLite FTS5 search with automatic trigger synchronization."""

    def setUp(self):
        self.db = Database(":memory:")
        self.db.add_translation("WEB", "World English Bible")
        self.db.add_translation("KJV", "King James Version")

        self.db.insert_verses(
            [
                VerseRecord(
                    translation_id="WEB",
                    book_id=1,
                    chapter=1,
                    verse=1,
                    text="In the beginning, God created the heavens and the earth.",
                ),
                VerseRecord(
                    translation_id="WEB",
                    book_id=1,
                    chapter=1,
                    verse=3,
                    text="God said, 'Let there be light,' and there was light.",
                ),
                VerseRecord(
                    translation_id="WEB",
                    book_id=40,
                    chapter=5,
                    verse=14,
                    text="You are the light of the world. A city located on a hill can't be hidden.",
                ),
                VerseRecord(
                    translation_id="KJV",
                    book_id=40,
                    chapter=5,
                    verse=14,
                    text="Ye are the light of the world. A city that is set on an hill cannot be hid.",
                ),
                VerseRecord(
                    translation_id="WEB",
                    book_id=43,
                    chapter=1,
                    verse=5,
                    text="The light shines in the darkness, and the darkness hasn't overcome it.",
                ),
            ]
        )

    def tearDown(self):
        self.db.close()

    def test_single_word_search(self):
        results = self.db.search_text("heavens")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].human_ref, "Genesis 1:1")
        self.assertIn("<b>heavens</b>", results[0].snippet)

    def test_multi_word_search(self):
        results = self.db.search_text("light world")
        self.assertEqual(len(results), 2)  # Matthew 5:14 in WEB and KJV
        refs = [r.human_ref for r in results]
        self.assertTrue(all(r == "Matthew 5:14" for r in refs))

    def test_phrase_search(self):
        results = self.db.search_text('"light of the world"')
        self.assertEqual(len(results), 2)

    def test_filter_by_translation(self):
        results_web = self.db.search_text('"light of the world"', translation_id="WEB")
        self.assertEqual(len(results_web), 1)
        self.assertEqual(results_web[0].translation_id, "WEB")

        results_kjv = self.db.search_text('"light of the world"', translation_id="KJV")
        self.assertEqual(len(results_kjv), 1)
        self.assertEqual(results_kjv[0].translation_id, "KJV")

    def test_filter_by_book(self):
        results = self.db.search_text("light", book="John")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].human_ref, "John 1:5")

    def test_fts_sync_on_delete_and_update(self):
        # Update verse
        v = self.db.get_verse("John", 1, 5, translation_id="WEB")
        assert v and v.id is not None

        with self.db.conn:
            self.db.conn.execute(
                "UPDATE verses SET text = ? WHERE id = ?",
                ("The radiant glory shines in the darkness.", v.id),
            )

        # "radiant" should now match, "overcome" should no longer match
        self.assertEqual(len(self.db.search_text("radiant")), 1)
        self.assertEqual(len(self.db.search_text("overcome")), 0)

        # Delete verse
        with self.db.conn:
            self.db.conn.execute("DELETE FROM verses WHERE id = ?", (v.id,))

        self.assertEqual(len(self.db.search_text("radiant")), 0)


class TestSpansTagsAndCrossReferences(unittest.TestCase):
    """Test passage spans, semantic tagging, and cross-reference links."""

    def setUp(self):
        self.db = Database(":memory:")

    def tearDown(self):
        self.db.close()

    def test_spans_registration_and_overlap(self):
        span1 = self.db.add_span("Romans 8:1-11", label="Life in the Spirit")
        self.assertEqual(span1.human_ref, "Romans 8:1-11")
        self.assertEqual(span1.osis_ref, "Rom.8.1-Rom.8.11")

        # Overlapping query on Romans 8:5
        overlaps = self.db.find_overlapping_spans("Romans 8:5")
        self.assertEqual(len(overlaps), 1)
        self.assertEqual(overlaps[0].label, "Life in the Spirit")

        # Non-overlapping query on Romans 9:1
        no_overlaps = self.db.find_overlapping_spans("Romans 9:1")
        self.assertEqual(len(no_overlaps), 0)

    def test_tag_crud_and_categories(self):
        t1 = self.db.add_tag("sovereignty", category="doctrine", description="God's supreme authority")
        self.assertEqual(t1.name, "sovereignty")
        self.assertEqual(t1.category, "doctrine")

        # Case-insensitive retrieval
        t_found = self.db.get_tag("SOVEREIGNTY")
        self.assertIsNotNone(t_found)
        self.assertEqual(t_found.name, "sovereignty")

        # List by category
        self.db.add_tag("atonement", category="doctrine")
        self.db.add_tag("grief", category="emotion")

        doctrine_tags = self.db.list_tags(category="doctrine")
        self.assertEqual(len(doctrine_tags), 2)
        names = [t.name for t in doctrine_tags]
        self.assertIn("sovereignty", names)
        self.assertIn("atonement", names)

    def test_tagging_passage_and_retrieval(self):
        # Tag Romans 8:28-30 with 'providence'
        vt = self.db.tag_reference(
            reference="Romans 8:28-30",
            tag_name="providence",
            category="doctrine",
            confidence=0.95,
            starred=True,
            notes="Golden chain of redemption",
        )
        self.assertEqual(vt.tag_name, "providence")
        self.assertTrue(vt.starred)

        # Querying Romans 8:29 should match because 8:29 is inside 8:28-30
        tags_on_v29 = self.db.get_tags_for_reference("Romans 8:29")
        self.assertEqual(len(tags_on_v29), 1)
        self.assertEqual(tags_on_v29[0].tag_name, "providence")
        self.assertTrue(tags_on_v29[0].starred)

        # Querying all passages for tag 'providence'
        passages = self.db.get_references_for_tag("providence")
        self.assertEqual(len(passages), 1)
        self.assertEqual(passages[0].human_ref, "Romans 8:28-30")

    def test_favorites_convenience_api(self):
        # Tag user favorite passage
        fav1 = self.db.tag_as_favorite("Genesis 1:1", starred=False)
        fav2 = self.db.tag_as_favorite("John 3:16", starred=True, notes="Memorized")

        all_favs = self.db.get_favorites()
        self.assertEqual(len(all_favs), 2)

        starred_favs = self.db.get_favorites(starred_only=True)
        self.assertEqual(len(starred_favs), 1)
        self.assertEqual(starred_favs[0].human_ref, "John 3:16")
        self.assertEqual(starred_favs[0].notes, "Memorized")

    def test_cross_references(self):
        # Link Genesis 3:15 (Protoevangelium) -> Galatians 4:4 (Seed born of woman)
        xr = self.db.add_cross_reference(
            source="Genesis 3:15",
            target="Galatians 4:4",
            relationship_type="prophecy_fulfillment",
            notes="Fulfillment of the Seed of the woman",
        )
        self.assertEqual(xr.relationship_type, "prophecy_fulfillment")

        # Bidirectional query from Genesis 3:15
        xrs_gen = self.db.get_cross_references("Genesis 3:15")
        self.assertEqual(len(xrs_gen), 1)
        self.assertEqual(xrs_gen[0].target_human_ref, "Galatians 4:4")

        # Bidirectional query from Galatians 4:4
        xrs_gal = self.db.get_cross_references("Galatians 4:4")
        self.assertEqual(len(xrs_gal), 1)
        self.assertEqual(xrs_gal[0].source_human_ref, "Genesis 3:15")


class TestFileDatabase(unittest.TestCase):
    """Test disk-backed file database initialization and WAL pragmas."""

    def test_file_database_creation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_file = Path(tmpdir) / "test_bible.db"
            self.assertFalse(db_file.exists())

            with Database(db_file) as db:
                self.assertTrue(db_file.exists())
                # Verify tables and books exist
                cur = db.conn.cursor()
                cur.execute("SELECT COUNT(*) FROM books")
                self.assertEqual(cur.fetchone()[0], 66)

                # Verify WAL journal mode
                cur.execute("PRAGMA journal_mode")
                mode = cur.fetchone()[0].lower()
                self.assertEqual(mode, "wal")


class TestCanonicalIdOperations(unittest.TestCase):
    """Test canonical ID conversions and boundary handling."""

    def test_canonical_id_boundaries(self):
        # Genesis 1:1 -> 1_001_001
        self.assertEqual(verse_canonical_id(1, 1, 1), 1001001)
        self.assertEqual(canonical_id_to_triple(1001001), (1, 1, 1))

        # Psalm 119:176 -> 19_119_176
        ps = get_book("Psalms")
        assert ps is not None
        self.assertEqual(verse_canonical_id(ps, 119, 176), 19119176)
        self.assertEqual(canonical_id_to_triple(19119176), (19, 119, 176))

        # Revelation 22:21 -> 66_022_021
        self.assertEqual(verse_canonical_id("Revelation", 22, 21), 66022021)
        self.assertEqual(canonical_id_to_triple(66022021), (66, 22, 21))

    def test_reference_canonical_properties(self):
        ref_single = parse_reference("John 3:16")
        self.assertEqual(ref_single.canonical_start_id, 43003016)
        self.assertEqual(ref_single.canonical_end_id, 43003016)
        self.assertEqual(ref_single.canonical_range, (43003016, 43003016))

        ref_range = parse_reference("Romans 8:28-30")
        self.assertEqual(ref_range.canonical_start_id, 45008028)
        self.assertEqual(ref_range.canonical_end_id, 45008030)

        ref_chapter = parse_reference("Genesis 1")
        self.assertEqual(ref_chapter.canonical_start_id, 1001001)
        self.assertEqual(ref_chapter.canonical_end_id, 1001999)

        ref_ch_range = parse_reference("1 Corinthians 12-14")
        self.assertEqual(ref_ch_range.canonical_start_id, 46012001)
        self.assertEqual(ref_ch_range.canonical_end_id, 46014999)


class TestCascadeAndEdgeCases(unittest.TestCase):
    """Test foreign key cascade and partial verse edge cases."""

    def test_translation_cascade_delete(self):
        db = Database(":memory:")
        db.add_translation("TEMP", "Temporary Translation")
        db.insert_verse(
            VerseRecord(
                translation_id="TEMP",
                book_id=1,
                chapter=1,
                verse=1,
                text="A temporary verse.",
            )
        )
        self.assertEqual(db.count_verses("TEMP"), 1)
        self.assertEqual(len(db.search_text("temporary")), 1)

        # Delete translation -> should cascade delete verse and FTS entry
        with db.conn:
            db.conn.execute("DELETE FROM translations WHERE id = 'TEMP'")

        self.assertEqual(db.count_verses("TEMP"), 0)
        self.assertEqual(len(db.search_text("temporary")), 0)
        db.close()

    def test_subverse_parts(self):
        db = Database(":memory:")
        db.add_translation("WEB", "World English Bible")
        # Mark 4:41a and 4:41b
        v_a = VerseRecord(
            translation_id="WEB",
            book_id=41,
            chapter=4,
            verse=41,
            subverse="a",
            text="They were filled with great fear and said to one another,",
        )
        v_b = VerseRecord(
            translation_id="WEB",
            book_id=41,
            chapter=4,
            verse=41,
            subverse="b",
            text="'Who then is this, that even the wind and the sea obey him?'",
        )
        db.insert_verse(v_a)
        db.insert_verse(v_b)

        fetched_a = db.get_verse("Mark", 4, 41, subverse="a")
        fetched_b = db.get_verse("Mark", 4, 41, subverse="b")
        self.assertIsNotNone(fetched_a)
        self.assertIsNotNone(fetched_b)
        assert fetched_a is not None and fetched_b is not None
        self.assertIn("great fear", fetched_a.text)
        self.assertIn("wind and the sea", fetched_b.text)
        db.close()


if __name__ == "__main__":
    unittest.main()
