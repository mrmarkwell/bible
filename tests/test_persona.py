"""Hermetic Unit Tests for Biblical Character Dialogue Engine (core.persona).

Verifies:
- Canonical persona catalog completeness and metadata integrity across OT/NT figures.
- Lookup resolution by ID, canonical name, hyphenated ID, and aliases.
- Normalized name handling and deduplication matching.
- Dynamic scripture citation loading from database.
- System prompt generation enforcing TGC theological guardrails:
  * Canonical horizon constraint
  * Biblical humility & canonical realism
  * Christ-centered teleology (OT longing vs NT testimony)
  * Confession of human frailty, trials, and sin
  * Exclusion of extrabiblical inventions and modern anachronisms
- BiblicalPersonaSession multi-turn dialogue state and turn tracking.
- Informative offline fallback when GEMINI_API_KEY is not configured.
- Unary dialogue generation with mock Gemini response.
- Incremental Server-Sent Events (SSE) streaming with mock chunks.
- Error handling and graceful fallback on network/API failures.
- Zero external dependencies per ADR-003.
"""

import unittest
from unittest.mock import MagicMock

from core.db import Database
from core.llm import LLMResponse, StreamChunk
from core.persona import (
    CANONICAL_PERSONAS,
    GroundedScripturePassage,
    PersonaDialogueResponse,
    create_persona_session,
    generate_persona_system_prompt,
    get_persona_definition,
    list_canonical_personas,
    load_character_scripture_passages,
)


class TestPersonaCatalog(unittest.TestCase):
    """Test the authoritative canonical biblical persona catalog."""

    def test_catalog_non_empty(self):
        personas = list_canonical_personas()
        self.assertGreaterEqual(len(personas), 15)
        self.assertEqual(len(personas), len(CANONICAL_PERSONAS))

    def test_catalog_ids_unique(self):
        ids = [p.id for p in CANONICAL_PERSONAS]
        self.assertEqual(len(ids), len(set(ids)), "Persona IDs must be strictly unique")

    def test_catalog_canonical_names_unique(self):
        names = [p.canonical_name for p in CANONICAL_PERSONAS]
        self.assertEqual(len(names), len(set(names)), "Persona canonical names must be unique")

    def test_persona_required_fields(self):
        for p in CANONICAL_PERSONAS:
            self.assertTrue(p.id.strip(), f"Persona {p} must have non-empty id")
            self.assertTrue(p.canonical_name.strip(), f"Persona {p.id} must have non-empty canonical_name")
            self.assertIn(p.testament, ("OT", "NT", "BOTH"), f"Invalid testament for {p.id}")
            self.assertTrue(p.canonical_era.strip(), f"Persona {p.id} must have canonical_era")
            self.assertTrue(p.lifespan_description.strip(), f"Persona {p.id} must have lifespan_description")
            self.assertTrue(p.theological_role.strip(), f"Persona {p.id} must have theological_role")
            self.assertGreater(len(p.key_passages), 0, f"Persona {p.id} must have key passages")
            self.assertGreater(len(p.core_trials_and_failures), 0, f"Persona {p.id} must have trials/failures")
            self.assertTrue(p.christ_centered_orientation.strip(), f"Persona {p.id} must have Christ-centered orientation")
            self.assertTrue(p.speaking_style.strip(), f"Persona {p.id} must have speaking_style")

    def test_to_dict_serialization(self):
        paul = get_persona_definition("paul")
        self.assertIsNotNone(paul)
        d = paul.to_dict()
        self.assertEqual(d["id"], "paul")
        self.assertEqual(d["canonical_name"], "Paul (Apostle)")
        self.assertEqual(d["testament"], "NT")
        self.assertIsInstance(d["key_passages"], list)
        self.assertIsInstance(d["core_trials_and_failures"], list)


class TestPersonaLookup(unittest.TestCase):
    """Test persona resolution and fuzzy lookup mechanisms."""

    def test_lookup_by_exact_id(self):
        paul = get_persona_definition("paul")
        self.assertIsNotNone(paul)
        self.assertEqual(paul.canonical_name, "Paul (Apostle)")

        moses = get_persona_definition("moses")
        self.assertIsNotNone(moses)
        self.assertEqual(moses.canonical_name, "Moses")

        david = get_persona_definition("david")
        self.assertIsNotNone(david)
        self.assertEqual(david.canonical_name, "David")

    def test_lookup_by_hyphenated_id(self):
        john_baptist = get_persona_definition("john-the-baptist")
        self.assertIsNotNone(john_baptist)
        self.assertEqual(john_baptist.id, "john-the-baptist")

        mary_mag = get_persona_definition("mary-magdalene")
        self.assertIsNotNone(mary_mag)
        self.assertEqual(mary_mag.id, "mary-magdalene")

    def test_lookup_by_alias(self):
        simon = get_persona_definition("Simon Peter")
        self.assertIsNotNone(simon)
        self.assertEqual(simon.id, "peter")

        saul = get_persona_definition("Saul of Tarsus")
        self.assertIsNotNone(saul)
        self.assertEqual(saul.id, "paul")

        abram = get_persona_definition("Abram")
        self.assertIsNotNone(abram)
        self.assertEqual(abram.id, "abraham")

    def test_lookup_by_title_or_honorific(self):
        king_david = get_persona_definition("King David")
        self.assertIsNotNone(king_david)
        self.assertEqual(king_david.id, "david")

        prophet_isaiah = get_persona_definition("Prophet Isaiah")
        self.assertIsNotNone(prophet_isaiah)
        self.assertEqual(prophet_isaiah.id, "isaiah")

        apostle_paul = get_persona_definition("Apostle Paul")
        self.assertIsNotNone(apostle_paul)
        self.assertEqual(apostle_paul.id, "paul")

    def test_lookup_case_insensitive_and_whitespace(self):
        p1 = get_persona_definition("  PAUL  ")
        self.assertIsNotNone(p1)
        self.assertEqual(p1.id, "paul")

        p2 = get_persona_definition("mOsEs")
        self.assertIsNotNone(p2)
        self.assertEqual(p2.id, "moses")

    def test_lookup_unknown_returns_none(self):
        self.assertIsNone(get_persona_definition(""))
        self.assertIsNone(get_persona_definition("NonExistentFigure12345"))


class TestScriptureGrounding(unittest.TestCase):
    """Test loading scripture passages to ground character persona knowledge."""

    @classmethod
    def setUpClass(cls):
        cls.db = Database()

    def test_load_scripture_passages_paul(self):
        paul = get_persona_definition("paul")
        self.assertIsNotNone(paul)
        passages = load_character_scripture_passages(paul, db=self.db, max_passages=4)
        self.assertGreaterEqual(len(passages), 1)
        for p in passages:
            self.assertIsInstance(p, GroundedScripturePassage)
            self.assertTrue(p.reference)
            self.assertTrue(p.translation)
            self.assertTrue(p.text)
            self.assertGreater(p.verse_count, 0)

    def test_load_scripture_passages_david(self):
        david = get_persona_definition("david")
        self.assertIsNotNone(david)
        passages = load_character_scripture_passages(david, db=self.db, max_passages=4)
        self.assertGreaterEqual(len(passages), 1)
        # Should contain Psalm 23 or 2 Samuel 7
        refs = [p.reference for p in passages]
        has_psalm_or_samuel = any("Psalm" in r or "Samuel" in r for r in refs)
        self.assertTrue(has_psalm_or_samuel)


class TestPersonaPromptGeneration(unittest.TestCase):
    """Test the generation of hermeneutically guarded system prompts."""

    def test_system_prompt_structure_ot_figure(self):
        moses = get_persona_definition("moses")
        self.assertIsNotNone(moses)
        prompt = generate_persona_system_prompt(moses)

        # 1. Identity & Era
        self.assertIn("Moses", prompt)
        self.assertIn("Exodus & Wilderness Wandering", prompt)
        # 2. Canonical Horizon
        self.assertIn("Canonical Horizon Constraint", prompt)
        # 3. Humility & Trials
        self.assertIn("Striking the rock in anger at Meribah", prompt)
        # 4. Christ-Centered Teleology
        self.assertIn("Prophet like him", prompt)
        # 5. Prohibition against extrabiblical invention
        self.assertIn("No Extrabiblical Inventions", prompt)
        self.assertIn("Deuteronomy 29:29", prompt)

    def test_system_prompt_structure_nt_figure(self):
        peter = get_persona_definition("peter")
        self.assertIsNotNone(peter)
        prompt = generate_persona_system_prompt(peter)

        self.assertIn("Peter (Apostle)", prompt)
        self.assertIn("Apostolic Era", prompt)
        self.assertIn("Denying with curses that he ever knew Jesus", prompt)
        self.assertIn("You are the Christ, the Son of the living God", prompt)
        self.assertIn("Biblical Humility & Anti-Moralism", prompt)

    def test_system_prompt_with_grounded_passages(self):
        paul = get_persona_definition("paul")
        passages = [
            GroundedScripturePassage(
                reference="Romans 1:16-17",
                translation="WEB",
                text="[16] For I am not ashamed of the Good News of Christ... [17] For in it is revealed God's righteousness",
                verse_count=2,
            )
        ]
        prompt = generate_persona_system_prompt(paul, grounded_passages=passages)
        self.assertIn("Canonical Scripture Foundations (Grounded Context)", prompt)
        self.assertIn("Romans 1:16-17 (WEB)", prompt)
        self.assertIn("For I am not ashamed", prompt)


class TestBiblicalPersonaSession(unittest.TestCase):
    """Test interactive multi-turn dialogue session management."""

    @classmethod
    def setUpClass(cls):
        cls.db = Database()

    def test_create_session_factory(self):
        session = create_persona_session("paul", db=self.db)
        self.assertEqual(session.persona.id, "paul")
        self.assertEqual(session.turn_count, 0)
        self.assertGreater(len(session.grounded_passages), 0)

    def test_create_session_invalid_persona_raises(self):
        with self.assertRaises(ValueError):
            create_persona_session("unrecognized_figure_999")

    def test_offline_fallback_when_no_api_key(self):
        # Force LLM client to report unavailable
        mock_client = MagicMock()
        mock_client.is_available.return_value = False

        session = create_persona_session("david", db=self.db, llm_client=mock_client)
        resp = session.say("King David, what comfort do you have in sorrow?")

        self.assertIsInstance(resp, PersonaDialogueResponse)
        self.assertEqual(resp.character_id, "david")
        self.assertTrue(resp.offline_fallback)
        self.assertEqual(resp.model, "offline-profile")
        self.assertEqual(resp.turn_count, 1)
        self.assertIn("OFFLINE PERSONA PROFILE: DAVID", resp.text)
        self.assertIn("Identity", resp.text)
        self.assertIn("Canonical Scripture Foundations", resp.text)

        # History updated
        self.assertEqual(len(session.history), 2)
        self.assertEqual(session.history[0].role, "user")
        self.assertEqual(session.history[1].role, "model")

    def test_offline_streaming_fallback(self):
        mock_client = MagicMock()
        mock_client.is_available.return_value = False

        session = create_persona_session("moses", db=self.db, llm_client=mock_client)
        tokens = list(session.say_stream("Tell me of Mount Sinai."))

        self.assertEqual(len(tokens), 1)
        self.assertIn("OFFLINE PERSONA PROFILE: MOSES", tokens[0])
        self.assertEqual(session.turn_count, 1)

    def test_say_with_mocked_gemini_generation(self):
        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.generate_content.return_value = LLMResponse(
            text="Grace and peace to you in Christ Jesus our Lord. I consider that our present sufferings are not worth comparing with the glory that will be revealed in us.",
            model="gemini-2.5-pro",
            latency_seconds=0.45,
        )

        session = create_persona_session("paul", db=self.db, llm_client=mock_client)
        resp = session.say("Brother Paul, what is your encouragement for those in trial?")

        self.assertFalse(resp.offline_fallback)
        self.assertEqual(resp.model, "gemini-2.5-pro")
        self.assertIn("Grace and peace to you", resp.text)
        self.assertEqual(resp.turn_count, 1)

        # Second turn
        resp2 = session.say("How then shall we live?")
        self.assertEqual(resp2.turn_count, 2)
        self.assertEqual(len(session.history), 4)

    def test_say_stream_with_mocked_gemini_chunks(self):
        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.generate_stream.return_value = iter([
            StreamChunk(text="The LORD "),
            StreamChunk(text="is my shepherd; "),
            StreamChunk(text="I shall not want."),
        ])

        session = create_persona_session("david", db=self.db, llm_client=mock_client)
        chunks = list(session.say_stream("Sing for us, sweet psalmist."))

        self.assertEqual(chunks, ["The LORD ", "is my shepherd; ", "I shall not want."])
        self.assertEqual(session.turn_count, 1)
        self.assertEqual(session.history[-1].content, "The LORD is my shepherd; I shall not want.")

    def test_empty_message_raises_value_error(self):
        session = create_persona_session("peter", db=self.db)
        with self.assertRaises(ValueError):
            session.say("")
        with self.assertRaises(ValueError):
            session.say("   ")
        with self.assertRaises(ValueError):
            list(session.say_stream(""))

    def test_reset_clears_history(self):
        mock_client = MagicMock()
        mock_client.is_available.return_value = False

        session = create_persona_session("paul", db=self.db, llm_client=mock_client)
        session.say("Hello")
        self.assertEqual(session.turn_count, 1)
        self.assertEqual(len(session.history), 2)

        session.reset()
        self.assertEqual(session.turn_count, 0)
        self.assertEqual(len(session.history), 0)


class TestDatabaseCharacterProfiles(unittest.TestCase):
    """Test database character_profiles table integration and CRUD."""

    @classmethod
    def setUpClass(cls):
        cls.db = Database()

    def test_seeded_character_profiles_in_db(self):
        profiles = self.db.get_all_character_profiles()
        self.assertGreaterEqual(len(profiles), 15)

        paul_prof = self.db.get_character_profile("Paul (Apostle)")
        self.assertIsNotNone(paul_prof)
        self.assertEqual(paul_prof.name, "Paul (Apostle)")
        self.assertTrue(paul_prof.theological_role)

    def test_insert_and_retrieve_custom_profile(self):
        test_name = "Test Figure"
        self.db.insert_character_profile(
            name=test_name,
            canonical_spans='["Genesis 1:1"]',
            historical_context="Test Era",
            theological_role="Test Role",
        )

        retrieved = self.db.get_character_profile(test_name)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, test_name)
        self.assertEqual(retrieved.historical_context, "Test Era")

        # Clean up
        with self.db.conn:
            self.db.conn.execute("DELETE FROM character_profiles WHERE name = ?", (test_name,))


if __name__ == "__main__":
    unittest.main()
