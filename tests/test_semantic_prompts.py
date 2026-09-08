"""Hermetic unit tests for Stratified Exegetical Prompt Architecture & TGC Hermeneutical System.

Verifies:
- All 66 Protestant canonical book horizons cataloged with high-fidelity historical & theological metadata.
- Stratified prompt generation across Layer 0 (Macro-Book), Layer 1 (Pericope), Layer 2 (Discourse),
  Layer 3 (Dual-Horizon Theology), Layer 4 (Typology), and Layer 5 (Semantic Propositions).
- Resilient JSON response parsing, schema validation, and enum normalization.
- Native conversion to database records and verification against SQLite storage.
- 100% Zero external dependencies (ADR-003).
"""

import json
import unittest

from core.db import Database
from core.reference import BOOKS
from core.semantic_prompts import (
    BOOK_HORIZONS,
    PericopeAnalysisInput,
    generate_pericope_prompt,
    get_book_horizon,
    get_semantic_prompt_generator,
    parse_pericope_analysis_json,
    parse_pericope_response,
)


class TestBookHorizons(unittest.TestCase):
    """Tests for canonical BookHorizon catalog across all 66 books."""

    def test_all_66_books_present_in_catalog(self) -> None:
        """Verify that every Protestant canonical book (1-66) has an authoritative horizon."""
        self.assertEqual(len(BOOK_HORIZONS), 66)
        for book_id in range(1, 67):
            self.assertIn(book_id, BOOK_HORIZONS, f"Book {book_id} missing from BOOK_HORIZONS")
            horizon = BOOK_HORIZONS[book_id]
            self.assertEqual(horizon.book_id, book_id)
            self.assertTrue(len(horizon.name) > 0)
            self.assertTrue(len(horizon.osis) > 0)
            self.assertIn(horizon.testament, ("OT", "NT"))
            self.assertTrue(len(horizon.genre) > 0)
            self.assertTrue(len(horizon.author) > 0)
            self.assertTrue(len(horizon.date_range) > 0)
            self.assertTrue(len(horizon.historical_setting) > 0)
            self.assertTrue(len(horizon.theological_theme) > 0)
            self.assertTrue(len(horizon.christological_anticipation) > 0)
            self.assertTrue(len(horizon.storyline_epoch) > 0)
            self.assertTrue(len(horizon.key_motifs) >= 2)

    def test_ot_nt_book_division(self) -> None:
        """Verify OT (1-39) and NT (40-66) division."""
        for book_id in range(1, 40):
            self.assertEqual(BOOK_HORIZONS[book_id].testament, "OT")
        for book_id in range(40, 67):
            self.assertEqual(BOOK_HORIZONS[book_id].testament, "NT")

    def test_get_book_horizon_lookups(self) -> None:
        """Verify get_book_horizon by int, name, abbreviation, and Book object."""
        # By ID
        gen = get_book_horizon(1)
        self.assertEqual(gen.name, "Genesis")
        self.assertEqual(gen.osis, "Gen")

        # By Name
        rom = get_book_horizon("Romans")
        self.assertEqual(rom.name, "Romans")
        self.assertEqual(rom.book_id, 45)
        self.assertEqual(rom.testament, "NT")

        # By OSIS / Abbrev
        rev = get_book_horizon("Rev")
        self.assertEqual(rev.name, "Revelation")
        self.assertEqual(rev.book_id, 66)

        # By Book object
        john_book = BOOKS[43]
        john_horizon = get_book_horizon(john_book)
        self.assertEqual(john_horizon.name, "John")

    def test_get_book_horizon_invalid(self) -> None:
        """Verify error on invalid book identifiers."""
        with self.assertRaises(ValueError):
            get_book_horizon(999)
        with self.assertRaises(ValueError):
            get_book_horizon("NonExistentBook123")

    def test_book_horizon_to_dict(self) -> None:
        """Verify dictionary serialization."""
        h = get_book_horizon(45)
        d = h.to_dict()
        self.assertEqual(d["name"], "Romans")
        self.assertEqual(d["book_id"], 45)
        self.assertIsInstance(d["key_motifs"], list)
        self.assertIn("Justification by Faith", d["key_motifs"])


class TestSemanticPromptGenerator(unittest.TestCase):
    """Tests for stratified prompt creation."""

    def setUp(self) -> None:
        self.gen = get_semantic_prompt_generator()

    def test_format_book_horizon(self) -> None:
        """Verify rendering of Layer 0 macro-book context."""
        horizon = get_book_horizon("Romans")
        block = self.gen.format_book_horizon(horizon)
        self.assertIn("Layer 0: Macro-Book Context (Romans)", block)
        self.assertIn("Romans (Rom), NT", block)
        self.assertIn("Paul the Apostle", block)
        self.assertIn("Overarching Theological Theme", block)
        self.assertIn("Christological Trajectory", block)
        self.assertIn("Primary Redemptive Epoch", block)

    def test_build_pericope_prompt(self) -> None:
        """Verify complete stratified prompt generation."""
        inp = PericopeAnalysisInput(
            reference="Romans 8:28-30",
            passage_text=(
                "And we know that for those who love God all things work together for good, "
                "for those who are called according to his purpose. For those whom he foreknew "
                "he also predestined to be conformed to the image of his Son, in order that he "
                "might be the firstborn among many brothers. And those whom he predestined he "
                "also called, and those whom he called he also justified, and those whom he "
                "justified he also glorified."
            ),
            preceding_context="Likewise the Spirit helps us in our weakness...",
            following_context="What then shall we say to these things? If God is for us...",
            translation_id="ESV",
        )
        prompt = self.gen.build_pericope_prompt(inp)

        # Check guardrails & TGC Foundation references
        self.assertIn("The Gospel Coalition (TGC) Foundation Documents (THEOLOGY.md)", prompt)
        self.assertIn("Hermeneutical & Theological Guardrails", prompt)
        self.assertIn("Dual-Horizon Hermeneutics", prompt)
        self.assertIn("Christ-Centered Teleology", prompt)

        # Check Layer 0 Macro-Book
        self.assertIn("Layer 0: Macro-Book Context (Romans)", prompt)

        # Check Target Scripture
        self.assertIn("Romans 8:28-30", prompt)
        self.assertIn("ESV", prompt)
        self.assertIn("work together for good", prompt)
        self.assertIn("Preceding Context", prompt)
        self.assertIn("Following Context", prompt)

        # Check Stratified Analytical Directives
        self.assertIn("Layer 1: Pericope Structure & Propositions", prompt)
        self.assertIn("Layer 2: Discourse Rhetoric & Propositional Flow", prompt)
        self.assertIn("Layer 3: Dual-Horizon Theological Classification", prompt)
        self.assertIn("Layer 4: Canonical Typology & Intertextual Arcs", prompt)
        self.assertIn("Layer 5: Semantic Propositions & Agent Triples", prompt)

        # Check JSON Schema
        self.assertIn("```json", prompt)
        self.assertIn('"central_proposition"', prompt)
        self.assertIn('"discourse_relations"', prompt)
        self.assertIn('"verse_theology"', prompt)
        self.assertIn('"typological_arcs"', prompt)
        self.assertIn('"semantic_propositions"', prompt)

    def test_convenience_generate_pericope_prompt(self) -> None:
        """Verify module convenience function."""
        prompt = generate_pericope_prompt(
            reference="Genesis 1:1-5",
            passage_text="In the beginning, God created the heavens and the earth...",
        )
        self.assertIn("Genesis 1:1-5", prompt)
        self.assertIn("Layer 0: Macro-Book Context (Genesis)", prompt)

    def test_build_typology_prompt(self) -> None:
        """Verify specialized typology extraction prompt."""
        prompt = self.gen.build_typology_prompt(
            type_ref="Genesis 22:1-19",
            type_text="Take your son, your only son Isaac, whom you love, and offer him there...",
            antitype_ref="Romans 8:32",
            antitype_text="He who did not spare his own Son but gave him up for us all...",
        )
        self.assertIn("Genesis 22:1-19", prompt)
        self.assertIn("Romans 8:32", prompt)
        self.assertIn("theological_correspondence", prompt)
        self.assertIn("warrant", prompt)

    def test_build_discourse_prompt(self) -> None:
        """Verify specialized discourse prompt."""
        prompt = self.gen.build_discourse_prompt(
            reference="Ephesians 2:8-10",
            passage_text="For by grace you have been saved through faith...",
        )
        self.assertIn("Ephesians 2:8-10", prompt)
        self.assertIn("discourse_relations", prompt)
        self.assertIn("ground", prompt)


class TestPericopeAnalysisParser(unittest.TestCase):
    """Tests for parsing and normalizing LLM JSON responses."""

    def test_parse_valid_pericope_json(self) -> None:
        """Verify parsing of clean JSON payload with all 5 layers."""
        sample_json = {
            "reference": "Romans 8:28-30",
            "title": "The Golden Chain of Redemption",
            "genre": "Pauline Exposition",
            "literary_structure": "Threefold progression: assurance (v. 28), decree (v. 29), unbroken chain (v. 30)",
            "central_proposition": "God sovereignly works all things for the good of the elect, ensuring their glorification.",
            "redemptive_summary": "Paul anchors believer security in God's eternal sovereign decree in Christ.",
            "christological_fulfillment": "Christ is the firstborn among many brothers, the pattern to whom all elect are conformed.",
            "discourse_relations": [
                {
                    "source_verse": "Romans 8:28",
                    "target_verse": "Romans 8:29",
                    "relation_type": "ground",
                    "marker_text": "for",
                    "greek_marker": "ὅτι",
                    "notes": "Verse 29 provides the divine ground for v. 28.",
                }
            ],
            "verse_theology": [
                {
                    "verse_ref": "Romans 8:28-30",
                    "storyline_epoch": "apostolic_church",
                    "theological_locus": "soteriology",
                    "primary_doctrine": "Effectual Calling & Unconditional Preservation",
                    "thematic_ribbon": "covenant_grace",
                    "confidence": 1.0,
                }
            ],
            "typological_arcs": [
                {
                    "type_ref": "Genesis 50:20",
                    "type_name": "Joseph Reassuring Brothers",
                    "antitype_ref": "Romans 8:28",
                    "antitype_name": "All Things Working for Good",
                    "theological_correspondence": "Sovereign providence transforming human evil into redemptive blessing.",
                    "warrant": "canonical_thematic_pattern",
                    "confidence": 0.95,
                }
            ],
            "semantic_propositions": [
                {
                    "verse_ref": "Romans 8:28",
                    "speech_act": "promise",
                    "agent": "God",
                    "action": "works all things together for good",
                    "patient": "those who love Him",
                    "tone": "triumphant confidence",
                    "clause_text": "all things work together for good",
                }
            ],
        }

        raw_text = f"```json\n{json.dumps(sample_json, indent=2)}\n```"
        result = parse_pericope_analysis_json(raw_text)

        self.assertEqual(result.reference, "Romans 8:28-30")
        self.assertEqual(result.title, "The Golden Chain of Redemption")
        self.assertEqual(result.genre, "Pauline Exposition")
        self.assertEqual(len(result.discourse_relations), 1)
        self.assertEqual(result.discourse_relations[0].relation_type, "ground")
        self.assertEqual(result.discourse_relations[0].greek_marker, "ὅτι")

        self.assertEqual(len(result.verse_theologies), 1)
        self.assertEqual(result.verse_theologies[0].theological_locus, "soteriology")
        self.assertEqual(result.verse_theologies[0].thematic_ribbon, "covenant_grace")

        self.assertEqual(len(result.typological_arcs), 1)
        self.assertEqual(result.typological_arcs[0].type_ref, "Genesis 50:20")

        self.assertEqual(len(result.semantic_propositions), 1)
        self.assertEqual(result.semantic_propositions[0].speech_act, "promise")
        self.assertEqual(result.semantic_propositions[0].agent, "God")

    def test_parse_with_preamble_and_dirty_formatting(self) -> None:
        """Verify parser succeeds even with conversational text around JSON."""
        dirty = """Here is the exegetical analysis:
```json
{
  "reference": "John 3:16",
  "title": "For God So Loved the World",
  "genre": "Gospel Exposition",
  "central_proposition": "God gave His only Son so that whoever believes in Him should not perish.",
  "redemptive_summary": "The gospel in miniature: eternal life granted through faith in Christ.",
  "christological_fulfillment": "Christ is the unique Son given as the sacrificial Savior of the world."
}
```
Hope this meets your needs!"""
        res = parse_pericope_response(dirty)
        self.assertEqual(res.reference, "John 3:16")
        self.assertEqual(res.title, "For God So Loved the World")

    def test_parse_enum_normalization(self) -> None:
        """Verify case and format normalization for theological enums."""
        payload = {
            "reference": "Romans 3:21-26",
            "title": "The Righteousness of God Manifested",
            "genre": "Epistle",
            "verse_theology": [
                {
                    "verse_ref": "Romans 3:24",
                    "storyline_epoch": "Apostolic Church",
                    "theological_locus": "SOTERIOLOGY",
                    "primary_doctrine": "Justification by Grace Alone",
                    "thematic_ribbon": "Sacrifice & Atonement",
                }
            ],
            "semantic_propositions": [
                {
                    "verse_ref": "Romans 3:24",
                    "speech_act": "ASSERTION",
                    "agent": "God",
                    "action": "justifies sinners as a gift",
                }
            ],
        }
        res = parse_pericope_analysis_json(json.dumps(payload))
        self.assertEqual(res.verse_theologies[0].storyline_epoch, "apostolic_church")
        self.assertEqual(res.verse_theologies[0].theological_locus, "soteriology")
        self.assertEqual(res.verse_theologies[0].thematic_ribbon, "sacrifice_atonement")
        self.assertEqual(res.semantic_propositions[0].speech_act, "assertion")

    def test_parse_invalid_json(self) -> None:
        """Verify ValueError raised on malformed JSON."""
        with self.assertRaises(ValueError):
            parse_pericope_analysis_json("Not a json string at all")
        with self.assertRaises(ValueError):
            parse_pericope_analysis_json("[1, 2, 3]")  # array instead of dict


class TestDatabaseRecordConversion(unittest.TestCase):
    """Tests for converting analysis DTOs to DB records and persisting in SQLite."""

    def test_conversion_and_sqlite_persistence(self) -> None:
        """Verify full lifecycle: parse -> to_db_records -> SQLite database insertion."""
        sample_json = {
            "reference": "Romans 8:28-30",
            "title": "The Golden Chain of Redemption",
            "genre": "Pauline Exposition",
            "literary_structure": "Threefold progression: assurance, decree, unbroken chain",
            "central_proposition": "God sovereignly orchestrates all things for the eternal good of His elect.",
            "redemptive_summary": "Paul anchors believer assurance in God's unshakable covenant decree.",
            "christological_fulfillment": "Christ is the firstborn among many brothers.",
            "discourse_relations": [
                {
                    "source_verse": "Romans 8:28",
                    "target_verse": "Romans 8:29",
                    "relation_type": "ground",
                    "marker_text": "for",
                    "greek_marker": "ὅτι",
                    "notes": "Verse 29 gives foundational reason",
                }
            ],
            "verse_theology": [
                {
                    "verse_ref": "Romans 8:28-30",
                    "storyline_epoch": "apostolic_church",
                    "theological_locus": "soteriology",
                    "primary_doctrine": "Effectual Calling & Unconditional Preservation",
                    "thematic_ribbon": "covenant_grace",
                    "confidence": 1.0,
                }
            ],
            "typological_arcs": [
                {
                    "type_ref": "Genesis 50:20",
                    "type_name": "Joseph in Egypt",
                    "antitype_ref": "Romans 8:28",
                    "antitype_name": "Providence for Good",
                    "theological_correspondence": "Human evil turned to sovereign redemptive blessing.",
                    "warrant": "canonical_thematic_pattern",
                    "confidence": 0.95,
                }
            ],
            "semantic_propositions": [
                {
                    "verse_ref": "v. 28",  # relative verse reference
                    "speech_act": "promise",
                    "agent": "God",
                    "action": "works all things together for good",
                    "patient": "those who love God",
                    "tone": "triumphant confidence",
                    "clause_text": "all things work together for good",
                }
            ],
        }

        result = parse_pericope_analysis_json(json.dumps(sample_json))
        pericope_rec, disc_recs, theo_recs, typo_recs, prop_recs = result.to_db_records()

        # Check PericopeRecord
        self.assertEqual(pericope_rec.book_id, 45)  # Romans
        self.assertEqual(pericope_rec.start_canonical_id, 45008028)
        self.assertEqual(pericope_rec.end_canonical_id, 45008030)
        self.assertEqual(pericope_rec.title, "The Golden Chain of Redemption")

        # Check DiscourseRelationRecord
        self.assertEqual(len(disc_recs), 1)
        self.assertEqual(disc_recs[0].source_canonical_id, 45008028)
        self.assertEqual(disc_recs[0].target_canonical_id, 45008029)
        self.assertEqual(disc_recs[0].relation_type, "ground")

        # Check VerseTheologyRecord
        self.assertEqual(len(theo_recs), 1)
        self.assertEqual(theo_recs[0].start_canonical_id, 45008028)
        self.assertEqual(theo_recs[0].end_canonical_id, 45008030)
        self.assertEqual(theo_recs[0].theological_locus, "soteriology")

        # Check TypologicalArcRecord
        self.assertEqual(len(typo_recs), 1)
        self.assertEqual(typo_recs[0].type_start_id, 1050020)  # Gen 50:20
        self.assertEqual(typo_recs[0].antitype_start_id, 45008028)  # Rom 8:28

        # Check SemanticPropositionRecord (resolved from relative "v. 28")
        self.assertEqual(len(prop_recs), 1)
        self.assertEqual(prop_recs[0].canonical_verse_id, 45008028)
        self.assertEqual(prop_recs[0].agent, "God")

        # Now test inserting into in-memory SQLite database!
        db = Database(":memory:")
        try:
            # Seed Pericope
            db.insert_pericopes_batch([pericope_rec])
            fetched_p = db.get_pericopes_for_book(45)
            self.assertEqual(len(fetched_p), 1)
            self.assertEqual(fetched_p[0].title, "The Golden Chain of Redemption")

            # Seed Discourse Relations
            db.insert_discourse_relations_batch(disc_recs)
            fetched_d = db.get_discourse_relations_for_verse("Romans 8:28")
            self.assertEqual(len(fetched_d), 1)
            self.assertEqual(fetched_d[0].relation_type, "ground")

            # Seed Verse Theology
            db.insert_verse_theology_batch(theo_recs)
            fetched_t = db.get_verse_theology_for_reference("Romans 8:28")
            self.assertEqual(len(fetched_t), 1)
            self.assertEqual(fetched_t[0].theological_locus, "soteriology")

            # Seed Typological Arcs
            db.insert_typological_arcs_batch(typo_recs)
            fetched_arcs = db.get_typological_arcs_for_reference("Genesis 50:20")
            self.assertEqual(len(fetched_arcs), 1)
            self.assertEqual(fetched_arcs[0].antitype_human_ref, "Romans 8:28")

            # Seed Semantic Propositions
            db.insert_semantic_propositions_batch(prop_recs)
            fetched_props = db.get_semantic_propositions_for_verse("Romans 8:28")
            self.assertEqual(len(fetched_props), 1)
            self.assertEqual(fetched_props[0].speech_act, "promise")
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
