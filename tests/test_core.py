"""Hermetic unit and integration tests for the Bible Engine core package.

Verifies the unified core package public exports, reference models,
database persistence, full-text search, semantic tagging, cryptographic
pack operations, and cross-cutting integration workflows.

Zero external dependencies: 100% Python standard library unittest.
"""

import os
import tempfile
import unittest
import core
from core import (
    ALL_BOOKS,
    BOOKS,
    CryptoError,
    Database,
    MAGIC_HEADER,
    VerseRecord,
    canonical_id_to_triple,
    decrypt_string,
    decrypt_text_pack,
    encrypt_string,
    encrypt_text_pack,
    get_book,
    parse_reference,
    verse_canonical_id,
)


class TestCoreExports(unittest.TestCase):
    """Verify that core/__init__.py exports all declared public symbols."""

    def test_all_symbols_exported(self):
        """Ensure __all__ is defined and all symbols are present in core namespace."""
        self.assertTrue(hasattr(core, "__all__"), "core module must define __all__")
        self.assertGreater(len(core.__all__), 20)

        for symbol_name in core.__all__:
            self.assertTrue(
                hasattr(core, symbol_name),
                f"Exported symbol '{symbol_name}' not found on core module",
            )

    def test_key_classes_and_functions_present(self):
        """Check expected core public API classes, functions, and datasets."""
        expected_names = [
            # Reference
            "Book",
            "Reference",
            "get_book",
            "parse_reference",
            "parse_references",
            "verse_canonical_id",
            "canonical_id_to_triple",
            "BOOKS",
            "ALL_BOOKS",
            # Database
            "Database",
            "DEFAULT_DB_PATH",
            "VerseRecord",
            "TranslationRecord",
            "SpanRecord",
            "TagRecord",
            "VerseTagRecord",
            "CrossReferenceRecord",
            "PericopeRecord",
            "DiscourseRelationRecord",
            "VerseTheologyRecord",
            "TypologicalArcRecord",
            "SemanticPropositionRecord",
            "VerseEmbeddingRecord",
            "PericopeEmbeddingRecord",
            "SearchResult",
            "sanitize_fts_query",
            # Crypto
            "ChaCha20",
            "CryptoError",
            "MAGIC_HEADER",
            "generate_key",
            "derive_key",
            "keystream_xor",
            "encrypt_bytes",
            "decrypt_bytes",
            "encrypt_string",
            "decrypt_string",
            "encrypt_text_pack",
            "decrypt_text_pack",
            # Semantic Tagging
            "TagCategory",
            "TagSummary",
            "TaggedPassage",
            "TaggingService",
            "CANONICAL_TAXONOMY",
            "BookTopicDensity",
            "TagCoOccurrence",
            "TagCoOccurrenceMatrix",
            "VerseRelevance",
            "GeneratedTag",
            "TaggingResult",
            "get_tgc_hermeneutical_system_prompt",
            "format_taxonomy_for_prompt",
            "generate_tagging_prompt",
            "generate_batch_tagging_prompts",
            "parse_tagging_response",
            "format_prompt_for_gemini_api",
            # Cross References
            "RelationshipType",
            "CrossReferenceService",
            "HydratedCrossReference",
            "CrossReferenceSummary",
            "CANONICAL_CROSS_REFERENCES",
            # Terminal & Typography
            "THEMES",
            "BOLD_GOLD",
            "should_use_color",
            "get_terminal_width",
            "strip_ansi",
            "visual_len",
            "format_citation_header",
            "format_scripture_passage",
            "format_aligned_comparison_styled",
            "format_tags_badge",
            "format_tag_table",
            "format_tagged_passages",
            "format_topic_density_table",
            "format_tag_co_occurrence_table",
            "format_verse_relevance_table",
            "format_cross_references",
            "format_cross_reference_table",
            # Bootstrap & Lifecycle
            "BootstrapReport",
            "bootstrap_database",
            "get_db_stats",
            # Slide Rendering Engine
            "SlideTheme",
            "STANDARD_THEMES",
            "get_theme",
            "parse_resolution",
            "SlideContent",
            "RenderConfig",
            "RenderResult",
            "RenderError",
            "ImageMagickNotFoundError",
            "LayoutBox",
            "calculate_slide_layout",
            "find_imagemagick_binary",
            "is_imagemagick_available",
            "detect_imagemagick",
            "get_available_backends",
            "SvgSlideRenderer",
            "ImageMagickSlideRenderer",
            "SlideRenderEngine",
            "get_default_engine",
            "render_verse_slide",
            # Zero-Dependency Vector Similarity Engine
            "VectorIndex",
            "VectorRecord",
            "SimilarityMatch",
            "DEFAULT_VECTOR_DIM",
            "cosine_similarity",
            "int8_cosine_similarity",
            "quantize_float_to_int8",
            "dequantize_int8_to_float",
            "normalize_vector",
            "get_verse_vector_index",
            "get_pericope_vector_index",
        ]
        for name in expected_names:
            self.assertIn(
                name,
                core.__all__,
                f"{name} should be in core.__all__",
            )
            self.assertTrue(
                hasattr(core, name),
                f"core should have attribute {name}",
            )


class TestCoreReferenceModels(unittest.TestCase):
    """Test canonical reference handling and parsing via the core API."""

    def test_canonical_book_catalog(self):
        """Verify the 66 canonical books are available and correctly indexed."""
        self.assertEqual(len(ALL_BOOKS), 66)
        self.assertEqual(len(BOOKS), 66)

        # OT / NT boundary
        gen = BOOKS[1]
        self.assertEqual(gen.name, "Genesis")
        self.assertEqual(gen.testament, "OT")
        self.assertEqual(gen.osis, "Gen")

        mal = BOOKS[39]
        self.assertEqual(mal.name, "Malachi")
        self.assertEqual(mal.testament, "OT")

        mat = BOOKS[40]
        self.assertEqual(mat.name, "Matthew")
        self.assertEqual(mat.testament, "NT")

        rev = BOOKS[66]
        self.assertEqual(rev.name, "Revelation")
        self.assertEqual(rev.testament, "NT")

        # Total chapters across canonical Protestant Bible = 1,189
        total_chapters = sum(b.total_chapters for b in ALL_BOOKS)
        self.assertEqual(total_chapters, 1189)

    def test_get_book_resolution(self):
        """Verify robust book resolution by name, abbreviation, and number."""
        self.assertEqual(get_book(1), BOOKS[1])
        self.assertEqual(get_book("Genesis"), BOOKS[1])
        self.assertEqual(get_book("gen"), BOOKS[1])
        self.assertEqual(get_book("1 Cor"), BOOKS[46])
        self.assertEqual(get_book("First Corinthians"), BOOKS[46])
        self.assertEqual(get_book("psalm"), BOOKS[19])
        self.assertEqual(get_book("psalms"), BOOKS[19])
        self.assertEqual(get_book("Song of Songs"), BOOKS[22])
        self.assertIsNone(get_book("NonexistentBook"))

    def test_reference_parsing_and_canonical_ids(self):
        """Verify parsing various reference formats and canonical ID calculation."""
        # Single verse
        ref1 = parse_reference("John 3:16")
        self.assertEqual(ref1.book.name, "John")
        self.assertEqual(ref1.start_chapter, 3)
        self.assertEqual(ref1.start_verse, 16)
        self.assertTrue(ref1.is_single_verse)
        self.assertFalse(ref1.is_verse_range)
        self.assertEqual(ref1.canonical_start_id, 43003016)
        self.assertEqual(ref1.canonical_end_id, 43003016)
        self.assertEqual(ref1.format(), "John 3:16")
        self.assertEqual(ref1.to_osis(), "John.3.16")

        # Intra-chapter range
        ref2 = parse_reference("Romans 8:28-30")
        self.assertEqual(ref2.book.name, "Romans")
        self.assertEqual(ref2.start_chapter, 8)
        self.assertEqual(ref2.start_verse, 28)
        self.assertEqual(ref2.end_verse, 30)
        self.assertTrue(ref2.is_verse_range)
        self.assertFalse(ref2.is_single_verse)
        self.assertEqual(ref2.canonical_start_id, 45008028)
        self.assertEqual(ref2.canonical_end_id, 45008030)
        self.assertEqual(ref2.format(), "Romans 8:28-30")
        self.assertEqual(ref2.to_osis(), "Rom.8.28-Rom.8.30")

        # Cross-chapter range
        ref3 = parse_reference("Genesis 1:1 - 2:3")
        self.assertEqual(ref3.start_chapter, 1)
        self.assertEqual(ref3.start_verse, 1)
        self.assertEqual(ref3.end_chapter, 2)
        self.assertEqual(ref3.end_verse, 3)
        self.assertTrue(ref3.is_verse_range)
        self.assertEqual(ref3.canonical_start_id, 1001001)
        self.assertEqual(ref3.canonical_end_id, 1002003)

        # Whole chapter
        ref4 = parse_reference("Psalm 23")
        self.assertTrue(ref4.is_whole_chapter)
        self.assertEqual(ref4.start_chapter, 23)
        self.assertIsNone(ref4.start_verse)
        self.assertIsNone(ref4.end_verse)
        self.assertEqual(ref4.canonical_start_id, 19023001)
        self.assertEqual(ref4.canonical_end_id, 19023999)

        # Single chapter book without chapter prefix
        ref5 = parse_reference("Jude 24")
        self.assertEqual(ref5.book.name, "Jude")
        self.assertEqual(ref5.start_chapter, 1)
        self.assertEqual(ref5.start_verse, 24)

    def test_reference_canonical_helpers(self):
        """Verify verse_canonical_id and canonical_id_to_triple functions."""
        cid = verse_canonical_id(43, 3, 16)
        self.assertEqual(cid, 43003016)

        b, c, v = canonical_id_to_triple(cid)
        self.assertEqual((b, c, v), (43, 3, 16))

    def test_reference_sorting_and_comparison(self):
        """Verify references sort in canonical scriptural order."""
        refs = [
            parse_reference("Revelation 22:20"),
            parse_reference("Genesis 1:1"),
            parse_reference("Romans 8:28"),
            parse_reference("Genesis 1:2"),
        ]
        sorted_refs = sorted(refs)
        self.assertEqual(sorted_refs[0].format(), "Genesis 1:1")
        self.assertEqual(sorted_refs[1].format(), "Genesis 1:2")
        self.assertEqual(sorted_refs[2].format(), "Romans 8:28")
        self.assertEqual(sorted_refs[3].format(), "Revelation 22:20")


class TestCoreDatabaseIntegration(unittest.TestCase):
    """Hermetic tests for Database operations via core package interface."""

    def setUp(self):
        self.db = Database(":memory:")
        self.db.add_translation("WEB", "World English Bible", is_public_domain=True)
        self.db.add_translation("ESV", "English Standard Version", is_public_domain=False, is_encrypted=True)

    def tearDown(self):
        self.db.close()

    def test_translation_crud(self):
        """Verify translations registration and retrieval."""
        translations = self.db.list_translations()
        self.assertEqual(len(translations), 2)
        web = self.db.get_translation("WEB")
        self.assertIsNotNone(web)
        self.assertEqual(web.name, "World English Bible")
        self.assertTrue(web.is_public_domain)

        esv = self.db.get_translation("ESV")
        self.assertIsNotNone(esv)
        self.assertTrue(esv.is_encrypted)

    def test_insert_and_get_single_verse(self):
        """Verify inserting and fetching a single verse."""
        v = VerseRecord(
            id=None,
            translation_id="WEB",
            book_id=43,  # John
            chapter=3,
            verse=16,
            text="For God so loved the world, that he gave his one and only Son, that whoever believes in him should not perish, but have eternal life.",
        )
        rowid = self.db.insert_verse(v)
        self.assertGreater(rowid, 0)

        # Get by exact coordinates
        fetched = self.db.get_verse(43, 3, 16, translation_id="WEB")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.canonical_verse_id, 43003016)
        self.assertIn("eternal life", fetched.text)
        self.assertEqual(fetched.book_name, "John")

        # Get by reference object
        ref = parse_reference("John 3:16")
        verses = self.db.get_verses_by_reference(ref, translation_id="WEB")
        self.assertEqual(len(verses), 1)
        self.assertEqual(verses[0].text, fetched.text)

    def test_batch_insert_and_range_query(self):
        """Verify batch verse insert and span querying."""
        verses_to_insert = [
            VerseRecord(
                id=None,
                translation_id="WEB",
                book_id=45,  # Romans
                chapter=8,
                verse=28,
                text="We know that all things work together for good for those who love God...",
            ),
            VerseRecord(
                id=None,
                translation_id="WEB",
                book_id=45,
                chapter=8,
                verse=29,
                text="For whom he foreknew, he also predestined to be conformed to the image of his Son...",
            ),
            VerseRecord(
                id=None,
                translation_id="WEB",
                book_id=45,
                chapter=8,
                verse=30,
                text="Whom he predestined, those he also called. Whom he called, those he also justified...",
            ),
        ]
        inserted_count = self.db.insert_verses(verses_to_insert)
        self.assertEqual(inserted_count, 3)
        self.assertEqual(self.db.count_verses("WEB"), 3)

        # Query range via Reference
        ref = parse_reference("Romans 8:28-30")
        results = self.db.get_verses_by_reference(ref, translation_id="WEB")
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0].verse, 28)
        self.assertEqual(results[1].verse, 29)
        self.assertEqual(results[2].verse, 30)

    def test_full_text_search(self):
        """Verify SQLite FTS5 index synchronization and query capabilities."""
        verses = [
            VerseRecord(
                id=None,
                translation_id="WEB",
                book_id=43,
                chapter=8,
                verse=12,
                text="Again, therefore, Jesus spoke to them, saying, 'I am the light of the world. He who follows me will not walk in the darkness, but will have the light of life.'",
            ),
            VerseRecord(
                id=None,
                translation_id="WEB",
                book_id=40,
                chapter=5,
                verse=14,
                text="You are the light of the world. A city located on a hill can't be hidden.",
            ),
            VerseRecord(
                id=None,
                translation_id="WEB",
                book_id=1,
                chapter=1,
                verse=3,
                text="God said, 'Let there be light,' and there was light.",
            ),
        ]
        self.db.insert_verses(verses)

        # Search for phrase "light of the world"
        phrase_results = self.db.search_text('"light of the world"', translation_id="WEB")
        self.assertEqual(len(phrase_results), 2)
        human_refs = [r.human_ref for r in phrase_results]
        self.assertIn("John 8:12", human_refs)
        self.assertIn("Matthew 5:14", human_refs)

        # Search for single term
        term_results = self.db.search_text("darkness", translation_id="WEB")
        self.assertEqual(len(term_results), 1)
        self.assertEqual(term_results[0].human_ref, "John 8:12")

    def test_semantic_tagging_and_favorites(self):
        """Verify semantic tagging, spans, and favorites tracking."""
        # Insert a verse
        v = VerseRecord(
            id=None,
            translation_id="WEB",
            book_id=45,
            chapter=8,
            verse=1,
            text="There is therefore now no condemnation to those who are in Christ Jesus...",
        )
        self.db.insert_verse(v)

        # Tag verse as favorite (starred)
        vt = self.db.tag_as_favorite(
            reference="Romans 8:1",
            starred=True,
            notes="Assurance of salvation in Christ",
        )
        self.assertIsNotNone(vt.id)
        self.assertGreater(vt.id, 0)

        # Verify favorites retrieval
        favorites = self.db.get_favorites(starred_only=True)
        self.assertEqual(len(favorites), 1)
        fav = favorites[0]
        self.assertEqual(fav.human_ref, "Romans 8:1")
        self.assertTrue(fav.starred)
        self.assertEqual(fav.tag_name, "favorites")

        # Create additional thematic tag
        tag = self.db.add_tag("Justification", category="theology", description="Righteous standing before God")
        self.db.tag_reference(
            reference="Romans 8:1",
            tag_name=tag.name,
            category="theology",
            confidence=0.95,
            source="curation",
        )

        tags = self.db.get_tags_for_reference("Romans 8:1")
        tag_names = [t.tag_name for t in tags]
        self.assertIn("favorites", tag_names)
        self.assertIn("justification", tag_names)

    def test_cross_references(self):
        """Verify cross-reference graph links between OT prophecy and NT fulfillment."""
        # Micah 5:2 -> Matthew 2:6
        xr = self.db.add_cross_reference(
            source="Micah 5:2",
            target="Matthew 2:6",
            relationship_type="prophecy_fulfillment",
            weight=1.0,
            notes="Ruler of Israel born in Bethlehem Ephrathah",
        )
        self.assertIsNotNone(xr.id)
        self.assertGreater(xr.id, 0)

        # Query links connected to Micah 5:2
        xrefs_micah = self.db.get_cross_references("Micah 5:2", bidirectional=True)
        self.assertEqual(len(xrefs_micah), 1)
        self.assertEqual(xrefs_micah[0].target_human_ref, "Matthew 2:6")
        self.assertEqual(xrefs_micah[0].relationship_type, "prophecy_fulfillment")

        # Query links connected to Matthew 2:6
        xrefs_matthew = self.db.get_cross_references("Matthew 2:6", bidirectional=True)
        self.assertEqual(len(xrefs_matthew), 1)
        self.assertEqual(xrefs_matthew[0].source_human_ref, "Micah 5:2")


class TestCoreCryptoIntegration(unittest.TestCase):
    """Hermetic tests for cryptographic operations and sovereign pack files."""

    def test_encrypt_decrypt_string_roundtrip(self):
        """Verify string encryption and decryption with passphrase."""
        passphrase = "SovereignScriptureKey2026!"
        original_text = "The grass withers, the flower fades, but the word of our God stands forever. (Isaiah 40:8)"
        ciphertext = encrypt_string(original_text, passphrase, iterations=1000)
        self.assertNotEqual(ciphertext, original_text.encode("utf-8"))

        decrypted = decrypt_string(ciphertext, passphrase)
        self.assertEqual(decrypted, original_text)

    def test_tamper_detection(self):
        """Verify that any modification to encrypted ciphertext is caught by HMAC."""
        passphrase = "SecretTamperKey42"
        plaintext = "In the beginning was the Word, and the Word was with God."
        ciphertext = encrypt_string(plaintext, passphrase, iterations=1000)

        # Tamper with the last byte
        corrupted = bytearray(ciphertext)
        corrupted[-1] ^= 0xFF

        with self.assertRaises(CryptoError):
            decrypt_string(bytes(corrupted), passphrase)

    def test_wrong_passphrase_rejection(self):
        """Verify that decrypting with wrong password raises CryptoError."""
        passphrase1 = "CorrectPassword123"
        passphrase2 = "WrongPassword456"
        ciphertext = encrypt_string("Peace I leave with you; my peace I give you.", passphrase1, iterations=1000)

        with self.assertRaises(CryptoError):
            decrypt_string(ciphertext, passphrase2)

    def test_text_pack_file_lifecycle(self):
        """Verify sovereign .bpack file export and import lifecycle."""
        passphrase = "HermeticTestPassword!42"
        scripture_corpus = (
            "Genesis 1:1 In the beginning God created the heavens and the earth.\n"
            "Genesis 1:2 The earth was formless and empty.\n"
            "Genesis 1:3 God said, 'Let there be light,' and there was light.\n"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            src_file = os.path.join(temp_dir, "corpus.txt")
            pack_file = os.path.join(temp_dir, "corpus.bpack")
            dec_file = os.path.join(temp_dir, "restored.txt")

            with open(src_file, "w", encoding="utf-8") as f:
                f.write(scripture_corpus)

            # Encrypt into .bpack
            encrypt_text_pack(src_file, pack_file, passphrase, iterations=1000)
            self.assertTrue(os.path.isfile(pack_file))

            # Inspect pack magic header
            with open(pack_file, "rb") as f:
                header = f.read(len(MAGIC_HEADER))
                self.assertEqual(header, MAGIC_HEADER)

            # Decrypt back
            decrypt_text_pack(pack_file, dec_file, passphrase)
            self.assertTrue(os.path.isfile(dec_file))

            with open(dec_file, "r", encoding="utf-8") as f:
                restored_text = f.read()

            self.assertEqual(restored_text, scripture_corpus)


class TestCoreEndToEndWorkflow(unittest.TestCase):
    """End-to-end integration scenario across reference, database, and crypto."""

    def test_redemptive_pipeline(self):
        """A complete multi-stage workflow integrating all core capabilities."""
        # 1. Parse references
        ot_ref = parse_reference("Isaiah 53:5")
        nt_ref = parse_reference("1 Peter 2:24")

        self.assertEqual(ot_ref.book.name, "Isaiah")
        self.assertEqual(nt_ref.book.name, "1 Peter")

        # 2. Setup database
        db = Database(":memory:")
        db.add_translation("WEB", "World English Bible", is_public_domain=True)

        ot_verse = VerseRecord(
            id=None,
            translation_id="WEB",
            book_id=ot_ref.book.number,
            chapter=ot_ref.start_chapter,
            verse=ot_ref.start_verse,
            text="But he was pierced for our transgressions. He was crushed for our iniquities. The punishment that brought our peace was on him; and by his wounds we are healed.",
        )
        nt_verse = VerseRecord(
            id=None,
            translation_id="WEB",
            book_id=nt_ref.book.number,
            chapter=nt_ref.start_chapter,
            verse=nt_ref.start_verse,
            text="He himself bore our sins in his body on the tree, that we, having died to sins, might live to righteousness; by whose stripes you were healed.",
        )
        db.insert_verses([ot_verse, nt_verse])

        # 3. Create cross-reference link
        db.add_cross_reference(
            source=ot_ref.format(),
            target=nt_ref.format(),
            relationship_type="typology",
            notes="Substitutionary atonement and healing through the Suffering Servant",
        )

        # 4. Tag passages
        db.tag_as_favorite(ot_ref.format(), starred=True, notes="Atonement prophecy")
        db.tag_as_favorite(nt_ref.format(), starred=False, notes="Atonement fulfillment")

        # 5. Search FTS5
        search_results = db.search_text("wounds OR stripes", translation_id="WEB")
        self.assertEqual(len(search_results), 2)

        # 6. Retrieve passages by Reference
        fetched_ot = db.get_verses_by_reference(ot_ref, translation_id="WEB")
        self.assertEqual(len(fetched_ot), 1)
        self.assertEqual(fetched_ot[0].canonical_verse_id, ot_ref.canonical_start_id)

        # 7. Encrypt the retrieved text using core crypto
        passphrase = "MessianicProphecyPassphrase42"
        encrypted_blob = encrypt_string(fetched_ot[0].text, passphrase, iterations=1000)
        self.assertIsInstance(encrypted_blob, bytes)

        # 8. Decrypt and verify exact match
        decrypted_text = decrypt_string(encrypted_blob, passphrase)
        self.assertEqual(decrypted_text, ot_verse.text)

        # 9. Render a TV screensaver slide from retrieved passage
        slide_res = core.render_verse_slide(
            text=fetched_ot[0].text,
            citation=ot_ref.format(),
            translation="WEB",
            theme="monastery",
            resolution="1080p",
            output_format="svg",
        )
        self.assertIsInstance(slide_res, core.RenderResult)
        self.assertEqual(slide_res.format, "svg")
        self.assertIn(b"Isaiah 53:5", slide_res.data)

        # 10. Clean up
        db.close()


if __name__ == "__main__":
    unittest.main()
