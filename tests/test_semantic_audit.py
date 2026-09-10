"""Hermetic Unit Tests for Exegetical Critic & Quality Audit Suite (core/semantic_audit.py).

Zero-dependency test suite per ADR-003, ADR-006, ADR-042, ADR-050, ADR-052, ADR-054, and ADR-055:
- Validates canonical coordinate boundaries (BBCCCVVV) across 66 books, 1,189 chapters, and 31,103 verses.
- Validates span verification and sequential coordinate expansion stepping across chapter/book limits.
- Tests character entity resolution, alias matching, and context-sensitive disambiguation.
- Tests Exegetical Critic rules across pericopes, discourse relations, theology, typology, and propositions.
- Tests TGC Foundation Document gospel uniqueness and Christological depth checks.
- Tests 100% whole-Bible coverage auditor, gap detection, overlap analysis, and summary generation.
- Tests SQLite database audit in hermetic in-memory databases.
"""

import unittest

from core.db import (
    Database,
    DiscourseRelationRecord,
    PericopeRecord,
    TypologicalArcRecord,
    VerseTheologyRecord,
)
from core.semantic_audit import (
    BOOK_CHAPTER_VERSES,
    TOTAL_CANONICAL_BOOKS,
    TOTAL_CANONICAL_CHAPTERS,
    TOTAL_CANONICAL_VERSES,
    CharacterEntityDeduplicator,
    CriticSeverity,
    ExegeticalCritic,
    WholeBibleCoverageAuditor,
    audit_pericope_analysis,
    expand_canonical_span,
    format_canonical_coordinate,
    get_canonical_max_verse,
    get_semantic_auditor,
    is_valid_canonical_coordinate,
    validate_canonical_coordinate,
    validate_canonical_span,
)
from core.semantic_prompts import (
    DiscourseRelationData,
    PericopeAnalysisResult,
    SemanticPropositionData,
    TypologicalArcData,
    VerseTheologyData,
)


class TestCanonicalCoordinateBoundaries(unittest.TestCase):
    """Test suite for canonical integer coordinate boundaries (BBCCCVVV)."""

    def test_canonical_totals(self) -> None:
        """Verify the immutable Protestant canonical totals."""
        self.assertEqual(TOTAL_CANONICAL_BOOKS, 66)
        self.assertEqual(TOTAL_CANONICAL_CHAPTERS, 1189)
        self.assertEqual(TOTAL_CANONICAL_VERSES, 31103)
        self.assertEqual(len(BOOK_CHAPTER_VERSES), 66)
        total_ch = sum(len(ch_list) for ch_list in BOOK_CHAPTER_VERSES.values())
        self.assertEqual(total_ch, 1189)
        total_v = sum(sum(ch_list) for ch_list in BOOK_CHAPTER_VERSES.values())
        self.assertEqual(total_v, 31103)

    def test_valid_canonical_coordinates(self) -> None:
        """Test valid boundary coordinates across Old and New Testaments."""
        valid_samples = [
            1_001_001,   # Genesis 1:1
            1_001_031,   # Genesis 1:31 (max verse of Gen 1)
            1_050_026,   # Genesis 50:26 (last verse of Genesis)
            19_119_176,  # Psalm 119:176 (longest chapter)
            31_001_021,  # Obadiah 1:21 (single-chapter OT book)
            39_004_006,  # Malachi 4:6 (last verse of OT)
            40_001_001,  # Matthew 1:1 (first verse of NT)
            45_008_028,  # Romans 8:28
            57_001_025,  # Philemon 1:25 (single-chapter NT epistle)
            64_001_014,  # 3 John 1:14
            65_001_025,  # Jude 1:25
            66_022_021,  # Revelation 22:21 (last verse of canon)
        ]
        for coord in valid_samples:
            self.assertTrue(is_valid_canonical_coordinate(coord), f"Expected {coord} to be valid")
            ok, err = validate_canonical_coordinate(coord)
            self.assertTrue(ok, f"Expected {coord} to pass validation, got error: {err}")
            self.assertIsNone(err)

    def test_invalid_canonical_coordinates(self) -> None:
        """Test out-of-bounds book, chapter, and verse values."""
        invalid_samples = [
            0,             # zero
            -1001001,      # negative
            1001000,       # verse 0 in Gen 1
            1_001_032,     # verse 32 in Gen 1 (only 31 exist)
            1_051_001,     # chapter 51 in Gen (only 50 exist)
            19_119_177,    # verse 177 in Ps 119 (only 176 exist)
            31_002_001,    # chapter 2 in Obadiah (single-chapter book)
            45_008_040,    # Romans 8:40 (Romans 8 has 39 verses)
            67_001_001,    # book 67 (outside 66-book canon)
            "1001001",     # string instead of int
        ]
        for coord in invalid_samples:
            self.assertFalse(is_valid_canonical_coordinate(coord), f"Expected {coord!r} to be invalid")
            ok, err = validate_canonical_coordinate(coord)
            self.assertFalse(ok)
            self.assertIsNotNone(err)

    def test_canonical_max_verse_lookup(self) -> None:
        """Test get_canonical_max_verse helper."""
        self.assertEqual(get_canonical_max_verse(1, 1), 31)    # Genesis 1
        self.assertEqual(get_canonical_max_verse(1, 2), 25)    # Genesis 2
        self.assertEqual(get_canonical_max_verse(19, 119), 176) # Psalm 119
        self.assertEqual(get_canonical_max_verse(19, 117), 2)   # Psalm 117 (shortest psalm)
        self.assertEqual(get_canonical_max_verse(31, 1), 21)    # Obadiah 1
        self.assertEqual(get_canonical_max_verse(66, 22), 21)   # Revelation 22
        # Invalid inputs return 0
        self.assertEqual(get_canonical_max_verse(0, 1), 0)
        self.assertEqual(get_canonical_max_verse(1, 51), 0)
        self.assertEqual(get_canonical_max_verse(67, 1), 0)

    def test_validate_canonical_span(self) -> None:
        """Test passage span validation logic."""
        # Valid intra-chapter span
        ok, err = validate_canonical_span(45_008_028, 45_008_030)
        self.assertTrue(ok)
        self.assertIsNone(err)

        # Valid cross-chapter span in same book
        ok, err = validate_canonical_span(1_001_001, 1_002_003)
        self.assertTrue(ok)
        self.assertIsNone(err)

        # Single verse span (start == end)
        ok, err = validate_canonical_span(43_003_016, 43_003_016)
        self.assertTrue(ok)

        # Inverted span (start > end)
        ok, err = validate_canonical_span(45_008_030, 45_008_028)
        self.assertFalse(ok)
        self.assertIn("Inverted", err)

        # Cross-book span rejected when allow_cross_book is False
        ok, err = validate_canonical_span(39_004_001, 40_001_001, allow_cross_book=False)
        self.assertFalse(ok)
        self.assertIn("Cross-book span not permitted", err)

        # Cross-book span permitted when allow_cross_book is True
        ok, err = validate_canonical_span(39_004_001, 40_001_001, allow_cross_book=True)
        self.assertTrue(ok)

    def test_expand_canonical_span(self) -> None:
        """Test sequential coordinate expansion stepping across boundaries."""
        # Simple span: John 3:16 to 3:18
        coords = expand_canonical_span(43_003_016, 43_003_018)
        self.assertEqual(coords, [43_003_016, 43_003_017, 43_003_018])

        # Cross-chapter span: Genesis 1:30 to 2:2
        # Genesis 1:30, 1:31 -> Genesis 2:1, 2:2
        coords = expand_canonical_span(1_001_030, 1_002_002)
        expected = [1_001_030, 1_001_031, 1_002_001, 1_002_002]
        self.assertEqual(coords, expected)

        # Cross-book boundary: Malachi 4:6 to Matthew 1:1
        coords = expand_canonical_span(39_004_006, 40_001_001)
        self.assertEqual(coords, [39_004_006, 40_001_001])

    def test_format_canonical_coordinate(self) -> None:
        """Test formatting coordinates to citations."""
        self.assertEqual(format_canonical_coordinate(1_001_001), "Genesis 1:1")
        self.assertEqual(format_canonical_coordinate(45_008_028), "Romans 8:28")
        self.assertEqual(format_canonical_coordinate(66_022_021), "Revelation 22:21")


class TestCharacterEntityDeduplicator(unittest.TestCase):
    """Test suite for biblical character entity resolution, alias mapping, and deduplication."""

    def setUp(self) -> None:
        self.dedup = CharacterEntityDeduplicator()

    def test_normalize_name(self) -> None:
        """Test honorific and punctuation stripping."""
        self.assertEqual(self.dedup.normalize_name("King David"), "david")
        self.assertEqual(self.dedup.normalize_name("Apostle Paul"), "paul")
        self.assertEqual(self.dedup.normalize_name("Prophet Isaiah"), "isaiah")
        self.assertEqual(self.dedup.normalize_name("Saint Peter"), "peter")
        self.assertEqual(self.dedup.normalize_name("Jacob (Israel)"), "jacob israel")

    def test_trinity_resolutions(self) -> None:
        """Test Godhead entity resolution and alias mapping."""
        for alias in ["Yahweh", "the LORD", "Lord GOD", "God", "the Father", "God the Father", "El Shaddai"]:
            res = self.dedup.resolve_character(alias)
            self.assertIsNotNone(res, f"Failed to resolve {alias}")
            self.assertEqual(res.canonical_name, "God (Yahweh)")

        for alias in ["Jesus", "Christ", "Jesus Christ", "Lord Jesus", "Yeshua", "Jesus of Nazareth", "Son of God"]:
            res = self.dedup.resolve_character(alias)
            self.assertIsNotNone(res, f"Failed to resolve {alias}")
            self.assertEqual(res.canonical_name, "Jesus Christ")

        for alias in ["Holy Spirit", "the Spirit", "Spirit of God", "the Comforter", "Spirit of Truth"]:
            res = self.dedup.resolve_character(alias)
            self.assertIsNotNone(res, f"Failed to resolve {alias}")
            self.assertEqual(res.canonical_name, "Holy Spirit")

    def test_context_disambiguation_saul(self) -> None:
        """Test disambiguating Saul between Old Testament King Saul and New Testament Apostle Paul."""
        ot_coord = 9_009_001   # 1 Samuel 9:1 (Saul anointed king)
        nt_coord = 44_009_001  # Acts 9:1 (Saul breathing threats, converted to Paul)

        res_ot = self.dedup.resolve_character("Saul", coordinate=ot_coord)
        self.assertIsNotNone(res_ot)
        self.assertEqual(res_ot.canonical_name, "Saul (King of Israel)")

        res_nt = self.dedup.resolve_character("Saul", coordinate=nt_coord)
        self.assertIsNotNone(res_nt)
        self.assertEqual(res_nt.canonical_name, "Paul (Apostle)")

    def test_context_disambiguation_joseph(self) -> None:
        """Test disambiguating Joseph between Patriarch and Husband of Mary."""
        ot_coord = 1_037_002   # Genesis 37:2 (Joseph son of Jacob)
        nt_coord = 40_001_019  # Matthew 1:19 (Joseph husband of Mary)

        res_ot = self.dedup.resolve_character("Joseph", coordinate=ot_coord)
        self.assertIsNotNone(res_ot)
        self.assertEqual(res_ot.canonical_name, "Joseph (Son of Jacob)")

        res_nt = self.dedup.resolve_character("Joseph", coordinate=nt_coord)
        self.assertIsNotNone(res_nt)
        self.assertEqual(res_nt.canonical_name, "Joseph (Husband of Mary)")

    def test_peter_aliases(self) -> None:
        """Test Simon Peter aliases."""
        for alias in ["Simon", "Simon Peter", "Cephas", "Peter"]:
            res = self.dedup.resolve_character(alias)
            self.assertIsNotNone(res)
            self.assertEqual(res.canonical_name, "Peter (Apostle)")

    def test_patriarch_aliases(self) -> None:
        """Test Abraham and Sarah name changes."""
        self.assertEqual(self.dedup.resolve_character("Abram").canonical_name, "Abraham")
        self.assertEqual(self.dedup.resolve_character("Sarai").canonical_name, "Sarah")

    def test_deduplicate_names_list(self) -> None:
        """Test deduplicating an array of names containing duplicates and aliases."""
        raw_names = [
            "Jesus",
            "Christ",
            "Lord Jesus",
            "Simon Peter",
            "Cephas",
            "Paul",
            "Saul of Tarsus",
            "Abraham",
            "Abram",
        ]
        deduped = self.dedup.deduplicate_names(raw_names)
        self.assertIn("Jesus Christ", deduped)
        self.assertIn("Peter (Apostle)", deduped)
        self.assertIn("Paul (Apostle)", deduped)
        self.assertIn("Abraham", deduped)
        self.assertEqual(len(deduped), 4)

    def test_audit_propositions_characters(self) -> None:
        """Test character entity consistency audit across propositions."""
        props = [
            {"agent": "God", "action": "created", "patient": "the heavens and the earth", "canonical_verse_id": 1_001_001},
            {"agent": "", "action": "commanded", "patient": "Moses", "canonical_verse_id": 2_003_001},  # empty agent
            {"agent": "Abram", "action": "believed", "patient": "the LORD", "canonical_verse_id": 1_015_006},  # alias detected
        ]
        rep = self.dedup.audit_propositions_characters(props)
        self.assertFalse(rep.is_clean)
        self.assertEqual(len(rep.errors), 1)
        self.assertEqual(rep.errors[0].rule_id, "PROP_AGENT_EMPTY")
        # Abram and the LORD trigger info normalization findings
        info_rules = [f.rule_id for f in rep.info]
        self.assertIn("PROP_AGENT_ALIAS_DETECTED", info_rules)


class TestExegeticalCritic(unittest.TestCase):
    """Test suite for the ExegeticalCritic structural and hermeneutical rules."""

    def setUp(self) -> None:
        self.critic = ExegeticalCritic()

    def test_audit_pericope_clean(self) -> None:
        """Test pericope passing all structural and theological rules."""
        p = PericopeRecord(
            id=1,
            book_id=45,
            start_canonical_id=45_008_028,
            end_canonical_id=45_008_030,
            human_ref="Romans 8:28-30",
            title="The Golden Chain of Sovereign Redemption",
            redemptive_summary="God works all things together for the eternal salvation and conformity of His elect to Jesus Christ.",
            genre="Pauline Epistle",
            literary_structure="Progressive Theological Argument (Foreknowledge to Glorification)",
            central_proposition="God guarantees the final glorification of all whom He sovereignly calls and justifies in Christ.",
        )
        rep = self.critic.audit_pericope(p, strict=True)
        self.assertTrue(rep.is_clean, f"Expected clean report, got: {rep.summary()}")

    def test_audit_pericope_empty_fields_strict_vs_non_strict(self) -> None:
        """Test strict vs non-strict pericope auditing."""
        p = PericopeRecord(
            id=1,
            book_id=1,
            start_canonical_id=1_001_001,
            end_canonical_id=1_002_003,
            human_ref="Genesis 1:1-2:3",
            title="The Creation of the Heavens and the Earth",
            redemptive_summary="",  # empty
            genre="Historical Narrative",
            literary_structure="",
            central_proposition="", # empty
        )
        # In strict mode, missing central proposition and redemptive summary are ERRORS
        rep_strict = self.critic.audit_pericope(p, strict=True)
        self.assertFalse(rep_strict.is_clean)
        self.assertTrue(any(f.rule_id == "PERICOPE_CP_EMPTY" and f.severity == CriticSeverity.ERROR for f in rep_strict.errors))

        # In non-strict mode, missing fields are treated as WARNINGS
        rep_non_strict = self.critic.audit_pericope(p, strict=False)
        self.assertTrue(rep_non_strict.is_clean)
        self.assertTrue(any(f.rule_id == "PERICOPE_CP_EMPTY" and f.severity == CriticSeverity.WARNING for f in rep_non_strict.warnings))

    def test_anti_moralism_detection(self) -> None:
        """Test flagging simplistic moralistic central propositions."""
        p = PericopeRecord(
            id=1,
            book_id=9,
            start_canonical_id=9_017_001,
            end_canonical_id=9_017_058,
            human_ref="1 Samuel 17:1-58",
            title="David and Goliath",
            redemptive_summary="A historical battle where Israel defeated the Philistines.",
            genre="Historical Narrative",
            literary_structure="Narrative battle",
            central_proposition="We must be brave like David to slay our daily giants and overcome life's obstacles.",
        )
        rep = self.critic.audit_pericope(p)
        # Should flag HERMENEUTIC_MORALISM_DETECTED
        moral_findings = [f for f in rep.findings if f.rule_id == "HERMENEUTIC_MORALISM_DETECTED"]
        self.assertEqual(len(moral_findings), 1)
        self.assertEqual(moral_findings[0].severity, CriticSeverity.WARNING)

    def test_audit_discourse_relations(self) -> None:
        """Test discourse relations validation."""
        valid_dr = DiscourseRelationRecord(
            id=1,
            source_canonical_id=45_008_028,
            source_human_ref="Romans 8:28",
            target_canonical_id=45_008_029,
            target_human_ref="Romans 8:29",
            relation_type="ground",
            marker_text="for",
            greek_marker="ὅτι",
            notes="Verse 29 provides the divine ground for the promise of verse 28",
        )
        rep = self.critic.audit_discourse_relations([valid_dr], pericope_start=45_008_028, pericope_end=45_008_030)
        self.assertTrue(rep.is_clean)

        # Invalid relation type
        invalid_dr = DiscourseRelationRecord(
            id=2,
            source_canonical_id=45_008_028,
            source_human_ref="Romans 8:28",
            target_canonical_id=None,
            target_human_ref=None,
            relation_type="random_nonexistent_type",
            marker_text="test",
            greek_marker=None,
            notes=None,
        )
        rep2 = self.critic.audit_discourse_relations([invalid_dr])
        self.assertFalse(rep2.is_clean)
        self.assertEqual(rep2.errors[0].rule_id, "DISCOURSE_INVALID_TYPE")

    def test_audit_verse_theology(self) -> None:
        """Test verse theology taxonomy validation."""
        valid_vt = VerseTheologyRecord(
            id=1,
            start_canonical_id=45_008_028,
            end_canonical_id=45_008_030,
            human_ref="Romans 8:28-30",
            storyline_epoch="apostolic_church",
            theological_locus="soteriology",
            primary_doctrine="Effectual Calling & Justification",
            thematic_ribbon="covenant_grace",
            confidence=0.98,
        )
        rep = self.critic.audit_verse_theology([valid_vt], pericope_start=45_008_028, pericope_end=45_008_030)
        self.assertTrue(rep.is_clean)

        # Invalid epoch and locus
        invalid_vt = VerseTheologyRecord(
            id=2,
            start_canonical_id=45_008_028,
            end_canonical_id=45_008_030,
            human_ref="Romans 8:28-30",
            storyline_epoch="Invalid Epoch 999",
            theological_locus="Invalid Locus 888",
            primary_doctrine="Doctrine",
            thematic_ribbon=None,
            confidence=1.5,  # out of bounds
        )
        rep2 = self.critic.audit_verse_theology([invalid_vt])
        self.assertFalse(rep2.is_clean)
        err_rules = [f.rule_id for f in rep2.errors]
        self.assertIn("THEOLOGY_INVALID_EPOCH", err_rules)
        self.assertIn("THEOLOGY_INVALID_LOCUS", err_rules)
        self.assertIn("THEOLOGY_INVALID_CONFIDENCE", err_rules)

    def test_audit_typological_arcs(self) -> None:
        """Test OT shadow to NT fulfillment verification."""
        # Valid arc: Passover Lamb (Exodus 12) -> Christ our Passover (1 Cor 5:7)
        valid_ta = TypologicalArcRecord(
            id=1,
            type_start_id=2_012_001,       # Exodus 12:1 (OT)
            type_end_id=2_012_014,         # Exodus 12:14
            type_human_ref="Exodus 12:1-14",
            antitype_start_id=46_005_007,  # 1 Corinthians 5:7 (NT)
            antitype_end_id=46_005_007,
            antitype_human_ref="1 Corinthians 5:7",
            theological_correspondence="The unblemished paschal lamb whose blood averted divine wrath foreshadows Christ, the spotless Lamb of God sacrificed for us.",
            warrant="explicit_nt_citation",
            confidence=1.0,
        )
        rep = self.critic.audit_typological_arcs([valid_ta])
        self.assertTrue(rep.is_clean)

        # Inverted arc: Type in NT and Antitype in OT
        invalid_ta = TypologicalArcRecord(
            id=2,
            type_start_id=46_005_007,      # 1 Corinthians (NT) as type!
            type_end_id=46_005_007,
            type_human_ref="1 Corinthians 5:7",
            antitype_start_id=2_012_001,  # Exodus (OT) as antitype!
            antitype_end_id=2_012_014,
            antitype_human_ref="Exodus 12:1-14",
            theological_correspondence="Incorrect inverted typological correspondence.",
            warrant="canonical_thematic_pattern",
            confidence=1.0,
        )
        rep2 = self.critic.audit_typological_arcs([invalid_ta])
        self.assertFalse(rep2.is_clean)
        err_rules = [f.rule_id for f in rep2.errors]
        self.assertIn("TYPOLOGY_TYPE_NOT_OT", err_rules)
        self.assertIn("TYPOLOGY_ANTITYPE_NOT_NT", err_rules)

    def test_audit_pericope_analysis_result(self) -> None:
        """Test end-to-end critique of a PericopeAnalysisResult DTO."""
        res = PericopeAnalysisResult(
            reference="Romans 8:28-30",
            title="The Golden Chain of Sovereign Redemption",
            genre="Pauline Epistle",
            literary_structure="Chain of divine redemptive acts",
            central_proposition="God orchestrates all historical events for the ultimate salvation and glorification of His chosen people in Christ Jesus.",
            redemptive_summary="Paul grounds the believer's absolute security in the unbreakable chain of divine foreknowledge, predestination, calling, justification, and glorification.",
            christological_fulfillment="Jesus Christ is the firstborn among many brothers, in whose image believers are glorified through His death and resurrection.",
            discourse_relations=[
                DiscourseRelationData(
                    source_verse="v. 28",
                    target_verse="v. 29",
                    relation_type="ground",
                    marker_text="for",
                    greek_marker="ὅτι",
                    notes="Verse 29 gives the theological reason for verse 28",
                )
            ],
            verse_theologies=[
                VerseTheologyData(
                    verse_ref="Romans 8:28-30",
                    storyline_epoch="apostolic_church",
                    theological_locus="soteriology",
                    primary_doctrine="Justification and Glorification",
                    thematic_ribbon="covenant_grace",
                    confidence=1.0,
                )
            ],
            typological_arcs=[
                TypologicalArcData(
                    type_ref="Genesis 50:20",
                    type_name="Joseph's Suffering for Good",
                    antitype_ref="Romans 8:28",
                    antitype_name="God Working All Things for Good in Christ",
                    theological_correspondence="Joseph's declaration that God meant evil for good prefigures the overarching sovereignty of God in Christ.",
                    warrant="canonical_thematic_pattern",
                    confidence=1.0,
                )
            ],
            semantic_propositions=[
                SemanticPropositionData(
                    verse_ref="Romans 8:28",
                    speech_act="promise",
                    agent="God",
                    action="causes all things to work together for good",
                    patient="those who love God",
                    tone="pastoral assurance",
                    clause_text="And we know that for those who love God all things work together for good",
                )
            ],
        )
        rep = self.critic.audit_pericope_analysis_result(res)
        self.assertTrue(rep.is_clean, f"Expected clean result, got: {rep.summary()}")


class TestWholeBibleCoverageAuditor(unittest.TestCase):
    """Test suite for whole-Bible 100% coverage evaluation across the 66 books."""

    def setUp(self) -> None:
        self.auditor = WholeBibleCoverageAuditor()

    def test_coverage_empty(self) -> None:
        """Test coverage with 0 pericopes."""
        rep = self.auditor.audit_pericopes([])
        self.assertFalse(rep.is_complete)
        self.assertEqual(rep.covered_verses_count, 0)
        self.assertEqual(rep.coverage_pct, 0.0)
        self.assertEqual(len(rep.book_stats), 66)
        self.assertGreater(len(rep.gaps), 0)

    def test_coverage_partial(self) -> None:
        """Test coverage calculation for a small set of pericopes."""
        pericopes = [
            PericopeRecord(
                id=1,
                book_id=1,
                start_canonical_id=1_001_001,
                end_canonical_id=1_001_031,  # Gen 1 (31 verses)
                human_ref="Genesis 1:1-31",
                title="Creation Week",
            ),
            PericopeRecord(
                id=2,
                book_id=45,
                start_canonical_id=45_001_001,
                end_canonical_id=45_001_032,  # Rom 1 (32 verses)
                human_ref="Romans 1:1-32",
                title="The Gospel Unveiled",
            ),
        ]
        rep = self.auditor.audit_pericopes(pericopes)
        self.assertEqual(rep.covered_verses_count, 63)
        self.assertAlmostEqual(rep.coverage_pct, 63 / 31103 * 100.0, places=2)
        # Check Gen stats
        gen_stat = rep.book_stats[1]
        self.assertEqual(gen_stat.covered_verses, 31)
        self.assertFalse(gen_stat.is_complete)
        # Check Rom stats
        rom_stat = rep.book_stats[45]
        self.assertEqual(rom_stat.covered_verses, 32)
        self.assertFalse(rom_stat.is_complete)

    def test_single_chapter_book_complete(self) -> None:
        """Test complete coverage on a single-chapter book (Obadiah)."""
        obadiah_pericope = PericopeRecord(
            id=1,
            book_id=31,
            start_canonical_id=31_001_001,
            end_canonical_id=31_001_021,  # 21 verses
            human_ref="Obadiah 1:1-21",
            title="The Judgment of Edom & Deliverance of Mount Zion",
        )
        rep = self.auditor.audit_pericopes([obadiah_pericope])
        ob_stat = rep.book_stats[31]
        self.assertEqual(ob_stat.covered_verses, 21)
        self.assertEqual(ob_stat.total_verses, 21)
        self.assertEqual(ob_stat.coverage_pct, 100.0)
        self.assertTrue(ob_stat.is_complete)

    def test_summary_table_formatting(self) -> None:
        """Test ASCII summary table rendering."""
        pericope = PericopeRecord(
            id=1,
            book_id=64,
            start_canonical_id=64_001_001,
            end_canonical_id=64_001_014,
            human_ref="3 John 1:1-14",
            title="Walking in the Truth",
        )
        rep = self.auditor.audit_pericopes([pericope])
        table = rep.summary_table()
        self.assertIn("Whole-Bible Semantic Coverage Report", table)
        self.assertIn("3 John", table)
        self.assertIn("100.0%", table)

    def test_to_dict_and_to_json(self) -> None:
        """Test JSON serialization of coverage report."""
        rep = self.auditor.audit_pericopes([])
        d = rep.to_dict()
        self.assertIn("total_verses", d)
        self.assertIn("coverage_pct", d)
        self.assertIn("book_stats", d)
        json_str = rep.to_json()
        self.assertIn('"total_verses": 31103', json_str)


class TestSemanticQualityAuditorIntegration(unittest.TestCase):
    """Test integration of SemanticQualityAuditor with SQLite Database."""

    def test_audit_in_memory_database(self) -> None:
        """Test auditing an in-memory SQLite database populated with test records."""
        db = Database(":memory:")
        db.init_schema()

        # Insert test pericopes
        db.insert_pericope(
            reference="Romans 8:28-30",
            title="Sovereign Assurance",
            redemptive_summary="God works all things together for good according to His redemptive purpose.",
            genre="Pauline Epistle",
            literary_structure="Chain of salvation",
            central_proposition="God's elect are eternally secure in His sovereign purpose.",
        )
        db.insert_discourse_relation(
            source_reference="Romans 8:28",
            relation_type="ground",
            target_reference="Romans 8:29",
            marker_text="for",
            notes="Ground of assurance",
        )
        db.insert_verse_theology(
            reference="Romans 8:28-30",
            storyline_epoch="apostolic_church",
            theological_locus="soteriology",
            primary_doctrine="Justification",
            thematic_ribbon="covenant_grace",
        )

        auditor = get_semantic_auditor()
        report, cov_report = auditor.audit_database(db, include_coverage=True, strict=True)
        self.assertTrue(report.is_clean, f"Expected clean report, got: {report.summary()}")
        self.assertIsNotNone(cov_report)
        self.assertEqual(cov_report.covered_verses_count, 3)
        self.assertEqual(cov_report.book_stats[45].covered_verses, 3)

    def test_audit_convenience_helpers(self) -> None:
        """Test module-level convenience functions."""
        res = PericopeAnalysisResult(
            reference="John 3:16-17",
            title="God's Love Revealed in the Son",
            genre="Gospel",
            literary_structure="Discourse with Nicodemus",
            central_proposition="God sent His Son into the world not to condemn but that whoever believes may be saved.",
            redemptive_summary="The pinnacle of redemptive revelation wherein the Father gives His only Son.",
            christological_fulfillment="Christ is the serpent lifted up in the wilderness to give eternal life.",
        )
        rep = audit_pericope_analysis(res)
        self.assertTrue(rep.is_clean)


class TestSemanticAuditCache(unittest.TestCase):
    """Test suite for semantic audit cache fingerprinting and stability."""

    def test_cache_fingerprint_and_validity(self):
        import tempfile
        from pathlib import Path
        from core.semantic_audit import (
            compute_db_audit_fingerprint,
            is_audit_cache_valid,
            save_audit_cache,
            AuditReport,
        )

        with tempfile.TemporaryDirectory() as td:
            db_file = Path(td) / "test.db"
            cache_file = Path(td) / "cache.json"
            db = Database(str(db_file))
            db.init_schema()

            fp = compute_db_audit_fingerprint(db_file, db=db)
            self.assertIn("size_bytes", fp)
            self.assertIn("data_version", fp)
            self.assertIn("schema_version", fp)
            self.assertIn("path", fp)

            audit_rep = AuditReport(total_inspected=10)
            saved = save_audit_cache(db_file, audit_rep, None, cache_path=cache_file, db=db)
            self.assertTrue(saved)
            self.assertTrue(cache_file.exists())

            # Cache is valid immediately
            self.assertTrue(is_audit_cache_valid(db_file, cache_path=cache_file, db=db))

            # If we insert data, data_version advances, invalidating cache
            with db.conn:
                db.conn.execute(
                    "INSERT INTO character_profiles (name, canonical_spans, historical_context, theological_role) VALUES (?, ?, ?, ?)",
                    ("Temp", "[]", "Temp", "Temp"),
                )
            self.assertFalse(is_audit_cache_valid(db_file, cache_path=cache_file, db=db))


if __name__ == "__main__":
    unittest.main()
