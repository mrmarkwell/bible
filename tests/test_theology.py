"""Hermetic Unit Tests for TGC Hermeneutical Framework & System Prompt Generator.

Verifies:
- Redemptive-Historical storyline epochs enum values and human-readable names.
- Systematic theological loci enum values and human-readable names.
- Canonical thematic ribbons enum values and human-readable names.
- TGC Confessional Statement articles and Ministry Vision principles completeness.
- TheologicalGuardrails directive formatting and toggle sensitivity.
- Master system prompt generation grounded in The Gospel Coalition Foundation Documents.
- Pericope analysis prompt generation with 6-layer metadata and JSON contract.
- Scripture RAG system prompt generation.
- Canonical biblical character persona prompt generation (humility, historical horizon, Christ-centered longing).
- Gospel uniqueness and theological compliance verification.
"""

import unittest

from core.reference import parse_reference
from core.theology import (
    RedemptiveEpoch,
    TGC_CONFESSIONAL_ARTICLES,
    TGC_MINISTRY_VISION_PRINCIPLES,
    TGCTheologyEngine,
    ThematicRibbon,
    TheologicalGuardrails,
    TheologicalLocus,
    get_master_system_prompt,
    get_theology_engine,
)


class TestTGCEnumsAndConstants(unittest.TestCase):
    """Test completeness and properties of theological enums and foundation documents."""

    def test_redemptive_epochs(self):
        self.assertEqual(len(RedemptiveEpoch), 11)
        self.assertIn(RedemptiveEpoch.CREATION, RedemptiveEpoch)
        self.assertIn(RedemptiveEpoch.FALL, RedemptiveEpoch)
        self.assertIn(RedemptiveEpoch.INCARNATION_CLIMAX, RedemptiveEpoch)
        self.assertIn(RedemptiveEpoch.CONSUMMATION, RedemptiveEpoch)

        # Verify display names are meaningful
        for epoch in RedemptiveEpoch:
            self.assertTrue(len(epoch.display_name) > 5)
            self.assertIsInstance(epoch.value, str)

    def test_theological_loci(self):
        self.assertEqual(len(TheologicalLocus), 8)
        self.assertIn(TheologicalLocus.THEOLOGY_PROPER, TheologicalLocus)
        self.assertIn(TheologicalLocus.CHRISTOLOGY, TheologicalLocus)
        self.assertIn(TheologicalLocus.SOTERIOLOGY, TheologicalLocus)

        for locus in TheologicalLocus:
            self.assertTrue(len(locus.display_name) > 5)

    def test_thematic_ribbons(self):
        self.assertEqual(len(ThematicRibbon), 12)
        self.assertIn(ThematicRibbon.TEMPLE_PRESENCE, ThematicRibbon)
        self.assertIn(ThematicRibbon.SEED_OFFSPRING, ThematicRibbon)
        self.assertIn(ThematicRibbon.COVENANT_GRACE, ThematicRibbon)
        self.assertIn(ThematicRibbon.SACRIFICE_ATONEMENT, ThematicRibbon)

        for ribbon in ThematicRibbon:
            self.assertTrue(len(ribbon.display_name) > 10)

    def test_tgc_confessional_articles_coverage(self):
        expected_keys = [
            "The Tri-une God",
            "Revelation & The Holy Scripture",
            "Creation & The Fall",
            "The Plan of God",
            "The Gospel & The Work of Christ",
            "Justification by Faith Alone",
            "The Work of the Holy Spirit",
            "The Kingdom of God & The Church",
            "Restoration of All Things",
        ]
        for key in expected_keys:
            self.assertIn(key, TGC_CONFESSIONAL_ARTICLES)
            self.assertTrue(len(TGC_CONFESSIONAL_ARTICLES[key]) > 20)

    def test_tgc_ministry_vision_principles(self):
        expected_principles = [
            "Dual-Horizon Hermeneutics",
            "Christ-Centered Teleology",
            "Gospel Uniqueness (Grace vs. Legalism & Relativism)",
            "Faith, Vocation & Cultural Good",
            "The Doing of Justice and Mercy",
        ]
        for p in expected_principles:
            self.assertIn(p, TGC_MINISTRY_VISION_PRINCIPLES)
            self.assertTrue(len(TGC_MINISTRY_VISION_PRINCIPLES[p]) > 20)


class TestTheologicalGuardrails(unittest.TestCase):
    """Test guardrail configuration and directive text rendering."""

    def test_default_guardrails_active(self):
        guardrails = TheologicalGuardrails()
        text = guardrails.build_directive_text()

        self.assertIn("The Gospel Coalition", text)
        self.assertIn("Biblical Inerrancy & Sufficiency", text)
        self.assertIn("Dual-Horizon Hermeneutics", text)
        self.assertIn("Christ-Centered Teleology", text)
        self.assertIn("Gospel Uniqueness & Grace-Driven Obedience", text)
        self.assertIn("Justification by Grace Alone through Faith Alone", text)

    def test_custom_guardrail_toggles(self):
        guardrails = TheologicalGuardrails(
            dual_horizon=False,
            christocentric=True,
            grace_driven_obedience=False,
            justification_by_faith=True,
            inerrancy_sufficiency=False,
        )
        text = guardrails.build_directive_text()

        self.assertNotIn("Dual-Horizon Hermeneutics", text)
        self.assertNotIn("Gospel Uniqueness & Grace-Driven Obedience", text)
        self.assertNotIn("Biblical Inerrancy", text)
        self.assertIn("Christ-Centered Teleology", text)
        self.assertIn("Justification by Grace Alone", text)


class TestTGCTheologyEnginePrompts(unittest.TestCase):
    """Test prompt synthesis across master prompt, pericopes, RAG, and character personas."""

    def setUp(self):
        self.engine = TGCTheologyEngine()

    def test_master_system_prompt(self):
        prompt = self.engine.get_master_system_prompt()
        self.assertIn("The Gospel Coalition (TGC) Foundation Documents", prompt)
        self.assertIn("Confessional Statement and Theological Vision for Ministry", prompt)
        self.assertIn("Dual-Horizon Hermeneutics", prompt)
        self.assertIn("Justification by Faith Alone", prompt)
        self.assertIn("Tri-une God", prompt)

    def test_pericope_analysis_prompt_with_str_reference(self):
        prompt = self.engine.generate_pericope_analysis_prompt(
            reference="Genesis 3:1-15",
            passage_text="Now the serpent was more crafty than any other beast of the field...",
            translation_id="ESV",
        )
        self.assertIn("Genesis 3:1-15", prompt)
        self.assertIn("Translation**: ESV", prompt)
        self.assertIn("Redemptive-Historical Epoch", prompt)
        self.assertIn("Systematic Theological Loci", prompt)
        self.assertIn("Canonical Thematic Ribbons", prompt)
        self.assertIn("Discourse Logic", prompt)
        self.assertIn('"storyline_epoch": "<epoch_key>"', prompt)
        self.assertIn('"typological_arcs"', prompt)

    def test_pericope_analysis_prompt_with_reference_object(self):
        ref = parse_reference("Romans 8:28-39")
        prompt = self.engine.generate_pericope_analysis_prompt(
            reference=ref,
            passage_text="And we know that for those who love God all things work together for good...",
            translation_id="ESV",
        )
        self.assertIn("Romans 8:28-39", prompt)
        self.assertIn("discourse_rhetoric", prompt)

    def test_rag_system_prompt(self):
        prompt = self.engine.generate_rag_system_prompt()
        self.assertIn("Bible Engine Scripture RAG Assistant", prompt)
        self.assertIn("The Gospel Coalition", prompt)
        self.assertIn("Overarching Storyline", prompt)
        self.assertIn("justification by faith alone", prompt)

    def test_character_persona_prompt(self):
        prompt = self.engine.generate_character_persona_prompt(
            character_name="David",
            canonical_era="United Monarchy, c. 1010-970 BC",
            key_passages=["1 Samuel 16-17", "2 Samuel 7", "Psalm 51", "Psalm 110"],
            core_trials_and_failures=[
                "Adultery with Bathsheba",
                "Murder of Uriah the Hittite",
                "Prideful census of Israel",
            ],
        )
        self.assertIn("**David**", prompt)
        self.assertIn("United Monarchy", prompt)
        self.assertIn("Canonical Horizon Constraint", prompt)
        self.assertIn("Biblical Humility & Canonical Realism", prompt)
        self.assertIn("Adultery with Bathsheba", prompt)
        self.assertIn("Murder of Uriah the Hittite", prompt)
        self.assertIn("chesed", prompt)
        self.assertIn("Psalm 51", prompt)

    def test_module_level_convenience_functions(self):
        engine = get_theology_engine()
        self.assertIsInstance(engine, TGCTheologyEngine)

        master = get_master_system_prompt()
        self.assertEqual(master, engine.get_master_system_prompt())


if __name__ == "__main__":
    unittest.main()
