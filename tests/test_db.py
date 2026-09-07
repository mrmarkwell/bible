"""Comprehensive Unit Tests for Bible Engine Database Engine (core/db.py).

Zero-dependency tests using Python standard library unittest only (ADR-003).
Hermetic, fast, and thorough verification of SQLite schema, FTS5 search,
canonical indexing, tagging, and cross references.
"""

from pathlib import Path
import sqlite3
import tempfile
import unittest

from core.db import (
    CrossReferenceRecord,
    Database,
    DiscourseRelationRecord,
    PericopeEmbeddingRecord,
    PericopeRecord,
    SearchResult,
    SemanticPropositionRecord,
    SpanRecord,
    TagRecord,
    TranslationRecord,
    TypologicalArcRecord,
    VerseEmbeddingRecord,
    VerseRecord,
    VerseTagRecord,
    VerseTheologyRecord,
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

    def test_exact_phrase_search_flag(self):
        # Unquoted "light world" without exact flag matches any verse with both tokens
        results_fuzzy = self.db.search_text("light world", exact=False)
        self.assertEqual(len(results_fuzzy), 2)

        # With exact=True, matches only contiguous phrase "light world", which does not occur
        results_exact = self.db.search_text("light world", exact=True)
        self.assertEqual(len(results_exact), 0)

        # Exact phrase "light of the world" matches 2 verses (WEB & KJV)
        results_phrase = self.db.search_text("light of the world", exact=True)
        self.assertEqual(len(results_phrase), 2)

    def test_filter_by_testament(self):
        # "light" in OT (Genesis 1:3) vs NT (Matthew 5:14, John 1:5)
        ot_results = self.db.search_text("light", testament="OT")
        self.assertEqual(len(ot_results), 1)
        self.assertEqual(ot_results[0].human_ref, "Genesis 1:3")

        nt_results = self.db.search_text("light", testament="NT", translation_id="WEB")
        self.assertEqual(len(nt_results), 2)
        nt_refs = {r.human_ref for r in nt_results}
        self.assertEqual(nt_refs, {"Matthew 5:14", "John 1:5"})

        with self.assertRaises(ValueError):
            self.db.search_text("light", testament="INVALID")

    def test_sort_by_canonical(self):
        results = self.db.search_text("light", translation_id="WEB", sort_by="canonical")
        refs = [r.human_ref for r in results]
        self.assertEqual(refs, ["Genesis 1:3", "Matthew 5:14", "John 1:5"])

    def test_count_search_matches(self):
        count_all = self.db.count_search_matches("light")
        self.assertEqual(count_all, 4)  # Gen 1:3 (WEB), Matt 5:14 (WEB, KJV), John 1:5 (WEB)

        count_ot = self.db.count_search_matches("light", testament="OT")
        self.assertEqual(count_ot, 1)

        count_exact = self.db.count_search_matches("light of the world", exact=True)
        self.assertEqual(count_exact, 2)

        count_none = self.db.count_search_matches("nonexistentword")
        self.assertEqual(count_none, 0)

    def test_search_result_to_dict(self):
        results = self.db.search_text("heavens")
        self.assertEqual(len(results), 1)
        d = results[0].to_dict()
        self.assertEqual(d["reference"], "Genesis 1:1")
        self.assertEqual(d["book"], "Genesis")
        self.assertEqual(d["chapter"], 1)
        self.assertEqual(d["verse"], 1)
        self.assertEqual(d["translation"], "WEB")
        self.assertIn("heavens", d["text"])

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


class TestPhase7SemanticArchitecture(unittest.TestCase):
    """Hermetic unit tests for Phase 7 6-Layer Semantic Database Architecture (ADR-042)."""

    def setUp(self):
        self.db = Database(":memory:")
        self.db.add_translation("WEB", "World English Bible")

    def tearDown(self):
        self.db.close()

    def test_pericopes_extended_attributes(self):
        # Insert pericope with 6-layer metadata
        p = self.db.insert_pericope(
            reference="Romans 5:1-11",
            title="Peace with God Through Faith",
            redemptive_summary="Justification produces objective peace, joy in suffering, and assurance in Christ.",
            genre="epistle",
            literary_structure="Thesis (1-2) -> Progression through suffering (3-5) -> Ground in Christ's death (6-11)",
            central_proposition="Since we have been justified by faith, we have peace with God through our Lord Jesus Christ.",
        )
        self.assertIsNotNone(p.id)
        self.assertEqual(p.genre, "epistle")
        self.assertEqual(p.literary_structure, "Thesis (1-2) -> Progression through suffering (3-5) -> Ground in Christ's death (6-11)")
        self.assertEqual(p.central_proposition, "Since we have been justified by faith, we have peace with God through our Lord Jesus Christ.")

        d = p.to_dict()
        self.assertEqual(d["genre"], "epistle")
        self.assertEqual(d["title"], "Peace with God Through Faith")

        # Query overlapping reference
        results = self.db.get_pericopes_for_reference("Romans 5:1")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].genre, "epistle")
        self.assertEqual(results[0].central_proposition, p.central_proposition)

        # Batch insert with mixed lengths
        count = self.db.insert_pericopes_batch([
            ("Romans 8:1-11", "Life in the Spirit", "No condemnation in Christ", "epistle", "Chiasm", "The Spirit of life sets us free"),
            ("Romans 8:28-39", "God's Everlasting Love", "More than conquerors"),
        ])
        self.assertEqual(count, 2)
        all_romans = self.db.get_pericopes_for_book("Romans")
        self.assertEqual(len(all_romans), 3)
        self.assertIsNone(all_romans[2].genre)

    def test_discourse_relations(self):
        # Insert single discourse relation: Romans 8:1 -> Romans 8:2
        dr1 = self.db.insert_discourse_relation(
            source_reference="Romans 8:2",
            relation_type="ground",
            target_reference="Romans 8:1",
            marker_text="for",
            greek_marker="γάρ",
            notes="The law of the Spirit is the causal ground for no condemnation",
        )
        self.assertIsNotNone(dr1.id)
        self.assertEqual(dr1.relation_type, "ground")
        self.assertEqual(dr1.greek_marker, "γάρ")
        d = dr1.to_dict()
        self.assertEqual(d["relation_type"], "ground")

        # Batch insert
        count = self.db.insert_discourse_relations_batch([
            ("Romans 12:1", "inference", None, "therefore", "οὖν", "Appeal based on mercies of God"),
            ("Galatians 2:16", "contrast", None, "but", "ἐὰν μή", "Not by works of law but faith in Christ"),
        ])
        self.assertEqual(count, 2)
        self.assertEqual(self.db.count_discourse_relations(), 3)
        self.assertEqual(self.db.count_discourse_relations("ground"), 1)
        self.assertEqual(self.db.count_discourse_relations("inference"), 1)

        # Query for verse
        rels_v1 = self.db.get_discourse_relations_for_verse("Romans 8:1")
        self.assertEqual(len(rels_v1), 1)
        self.assertEqual(rels_v1[0].marker_text, "for")

        rels_type = self.db.get_discourse_relations_by_type("ground")
        self.assertEqual(len(rels_type), 1)

        # Clear
        deleted = self.db.clear_discourse_relations()
        self.assertEqual(deleted, 3)
        self.assertEqual(self.db.count_discourse_relations(), 0)

    def test_verse_theology(self):
        # Single insert
        vt1 = self.db.insert_verse_theology(
            reference="Romans 3:21-26",
            storyline_epoch="incarnation_resurrection",
            theological_locus="soteriology",
            primary_doctrine="Justification by grace through faith in Christ's propitiation",
            thematic_ribbon="covenant_of_grace",
            confidence=0.99,
        )
        self.assertIsNotNone(vt1.id)
        self.assertEqual(vt1.theological_locus, "soteriology")
        self.assertEqual(vt1.storyline_epoch, "incarnation_resurrection")
        d = vt1.to_dict()
        self.assertEqual(d["primary_doctrine"], "Justification by grace through faith in Christ's propitiation")

        # Batch insert
        count = self.db.insert_verse_theology_batch([
            ("Genesis 1:1", "creation", "theology_proper", "Ex nihilo creation by God", "temple_presence", 1.0),
            ("Genesis 3:15", "fall", "christology", "Protoevangelium seed of woman", "seed_of_woman", 0.95),
            ("Hebrews 9:11-14", "incarnation_resurrection", "christology", "Eternal redemption by Christ's blood", "priesthood_mediation", 0.98),
        ])
        self.assertEqual(count, 3)
        self.assertEqual(self.db.count_verse_theology(), 4)
        self.assertEqual(self.db.count_verse_theology(theological_locus="christology"), 2)
        self.assertEqual(self.db.count_verse_theology(storyline_epoch="creation"), 1)

        # Query by reference
        matches = self.db.get_verse_theology_for_reference("Romans 3:23")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].theological_locus, "soteriology")

        # Query by epoch, locus, ribbon
        creation_records = self.db.get_verse_theology_by_epoch("creation")
        self.assertEqual(len(creation_records), 1)

        soteriology_records = self.db.get_verse_theology_by_locus("soteriology")
        self.assertEqual(len(soteriology_records), 1)

        priesthood_records = self.db.get_verse_theology_by_ribbon("priesthood_mediation")
        self.assertEqual(len(priesthood_records), 1)

        # Clear
        deleted = self.db.clear_verse_theology()
        self.assertEqual(deleted, 4)
        self.assertEqual(self.db.count_verse_theology(), 0)

    def test_typological_arcs(self):
        # Single insert: Abraham offering Isaac prefiguring God offering His Son
        arc1 = self.db.insert_typological_arc(
            type_reference="Genesis 22:1-14",
            antitype_reference="John 19:16-18",
            theological_correspondence="The beloved only son carrying the wood up the mountain; God provides the substitute sacrifice",
            warrant="apostolic_citation",
            confidence=0.98,
        )
        self.assertIsNotNone(arc1.id)
        self.assertEqual(arc1.type_human_ref, "Genesis 22:1-14")
        self.assertEqual(arc1.warrant, "apostolic_citation")
        d = arc1.to_dict()
        self.assertEqual(d["antitype_human_ref"], "John 19:16-18")

        # Batch insert
        count = self.db.insert_typological_arcs_batch([
            ("Exodus 12:1-13", "1 Corinthians 5:7", "Passover Lamb without blemish whose blood protects from wrath", "apostolic_citation", 1.0),
            ("Numbers 21:8-9", "John 3:14-15", "Bronze serpent lifted up on pole for healing of deadly poison", "direct_claim", 1.0),
        ])
        self.assertEqual(count, 2)
        self.assertEqual(self.db.count_typological_arcs(), 3)

        # Query as type
        type_matches = self.db.get_typological_arcs_for_reference("Genesis 22:2", as_type=True, as_antitype=False)
        self.assertEqual(len(type_matches), 1)

        # Query as antitype
        antitype_matches = self.db.get_typological_arcs_for_reference("John 3:14", as_type=False, as_antitype=True)
        self.assertEqual(len(antitype_matches), 1)
        self.assertEqual(antitype_matches[0].type_human_ref, "Numbers 21:8-9")

        # Clear
        deleted = self.db.clear_typological_arcs()
        self.assertEqual(deleted, 3)
        self.assertEqual(self.db.count_typological_arcs(), 0)

    def test_semantic_propositions(self):
        # Single insert
        sp1 = self.db.insert_semantic_proposition(
            reference="John 3:16",
            speech_act="doxology",
            agent="God",
            action="loved",
            patient="the world",
            tone="majestic",
            clause_text="For God so loved the world",
        )
        self.assertIsNotNone(sp1.id)
        self.assertEqual(sp1.agent, "God")
        self.assertEqual(sp1.action, "loved")
        self.assertEqual(sp1.patient, "the world")
        d = sp1.to_dict()
        self.assertEqual(d["speech_act"], "doxology")

        # Batch insert
        count = self.db.insert_semantic_propositions_batch([
            ("Romans 8:33", "indicative", "God", "justifies", "the elect", "triumphant", "It is God who justifies"),
            ("Micah 6:8", "imperative", "Lord", "requires", "man", "solemn", "What does the Lord require of you"),
        ])
        self.assertEqual(count, 2)
        self.assertEqual(self.db.count_semantic_propositions(), 3)
        self.assertEqual(self.db.count_semantic_propositions(agent="God"), 2)
        self.assertEqual(self.db.count_semantic_propositions(speech_act="imperative"), 1)

        # Query by verse
        v_props = self.db.get_semantic_propositions_for_verse("John 3:16")
        self.assertEqual(len(v_props), 1)
        self.assertEqual(v_props[0].action, "loved")

        # Query by agent
        god_props = self.db.get_semantic_propositions_by_agent("God")
        self.assertEqual(len(god_props), 2)

        # Query by speech act
        imp_props = self.db.get_semantic_propositions_by_speech_act("imperative")
        self.assertEqual(len(imp_props), 1)

        # Clear
        deleted = self.db.clear_semantic_propositions()
        self.assertEqual(deleted, 3)
        self.assertEqual(self.db.count_semantic_propositions(), 0)

    def test_vector_embeddings(self):
        # Verse embeddings
        dummy_bytes = b"\x00\x01\x02\x03" * 192  # 768 bytes
        ve1 = self.db.save_verse_embedding(
            reference="John 3:16",
            model_id="text-embedding-004",
            dimensions=768,
            embedding=dummy_bytes,
        )
        self.assertEqual(ve1.dimensions, 768)
        self.assertEqual(ve1.model_id, "text-embedding-004")
        self.assertEqual(len(ve1.embedding), 768)
        d = ve1.to_dict()
        self.assertEqual(d["dimensions"], 768)

        # Query single
        fetched = self.db.get_verse_embedding("John 3:16")
        self.assertIsNotNone(fetched)
        assert fetched is not None
        self.assertEqual(fetched.embedding, dummy_bytes)

        # Batch save
        dummy_bytes_2 = b"\x04\x05\x06\x07" * 192
        batch_count = self.db.save_verse_embeddings_batch([
            ("Romans 8:28", "text-embedding-004", 768, dummy_bytes_2),
            ("Psalm 23:1", "text-embedding-004", 768, dummy_bytes),
        ])
        self.assertEqual(batch_count, 2)
        self.assertEqual(self.db.count_verse_embeddings(), 3)

        all_embs = self.db.get_all_verse_embeddings("text-embedding-004")
        self.assertEqual(len(all_embs), 3)

        # Clear verse embeddings
        del_count = self.db.clear_verse_embeddings()
        self.assertEqual(del_count, 3)
        self.assertEqual(self.db.count_verse_embeddings(), 0)

        # Pericope embeddings
        p = self.db.insert_pericope("Romans 8:1-11", "Life in the Spirit")
        pe1 = self.db.save_pericope_embedding(
            pericope_id=p.id,
            reference="Romans 8:1-11",
            model_id="text-embedding-004",
            dimensions=768,
            embedding=dummy_bytes,
        )
        self.assertEqual(pe1.pericope_id, p.id)
        d_pe = pe1.to_dict()
        self.assertEqual(d_pe["pericope_id"], p.id)

        fetched_pe = self.db.get_pericope_embedding(p.id)
        self.assertIsNotNone(fetched_pe)
        assert fetched_pe is not None
        self.assertEqual(fetched_pe.embedding, dummy_bytes)

        # Batch pericope embeddings
        p2 = self.db.insert_pericope("Romans 8:28-39", "More Than Conquerors")
        p_batch_count = self.db.save_pericope_embeddings_batch([
            (p2.id, "Romans 8:28-39", "text-embedding-004", 768, dummy_bytes_2),
        ])
        self.assertEqual(p_batch_count, 1)
        self.assertEqual(self.db.count_pericope_embeddings(), 2)

        # Clear pericope embeddings
        del_pe = self.db.clear_pericope_embeddings()
        self.assertEqual(del_pe, 2)
        self.assertEqual(self.db.count_pericope_embeddings(), 0)

    def test_pericopes_schema_evolution(self):
        # Create an in-memory database with an older pericopes table lacking genre
        db_raw = sqlite3.connect(":memory:")
        db_raw.row_factory = sqlite3.Row
        db_raw.execute("""
            CREATE TABLE pericopes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL,
                start_canonical_id INTEGER NOT NULL,
                end_canonical_id INTEGER NOT NULL,
                human_ref TEXT NOT NULL,
                title TEXT NOT NULL,
                redemptive_summary TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)
        db_raw.execute("""
            INSERT INTO pericopes (book_id, start_canonical_id, end_canonical_id, human_ref, title, redemptive_summary)
            VALUES (45, 45001001, 45001007, 'Romans 1:1-7', 'Greeting', 'Paul servant of Christ');
        """)
        db_raw.commit()

        # Wrap in Database class and invoke init_schema
        db = Database(db_path=":memory:", auto_init=False)
        db.conn.close()
        db.conn = db_raw
        db.init_schema()

        # Assert columns now exist
        cur = db.conn.cursor()
        cur.execute("PRAGMA table_info(pericopes)")
        cols = {row["name"] for row in cur.fetchall()}
        self.assertIn("genre", cols)
        self.assertIn("literary_structure", cols)
        self.assertIn("central_proposition", cols)

        # Check existing row preserved and can update
        p = db.get_pericopes_for_reference("Romans 1:1")[0]
        self.assertEqual(p.title, "Greeting")
        self.assertIsNone(p.genre)

        db.close()


if __name__ == "__main__":
    unittest.main()
