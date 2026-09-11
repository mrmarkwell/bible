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
    enforce_citation_brackets,
    extract_scripture_citations,
    generate_persona_system_prompt,
    get_persona_definition,
    list_canonical_personas,
    load_character_scripture_passages,
    render_citation_reader_links,
    retrieve_author_scoped_rag,
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
        self.assertIn("Biblical Humility & Canonical Realism", prompt)

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


class TestDialogueSessionManager(unittest.TestCase):
    """Test archival dialogue transcripts, session persistence, markdown export, and resumption."""

    def setUp(self):
        import shutil
        import tempfile
        from pathlib import Path
        from core.persona import DialogueSessionManager
        self.temp_dir = Path(tempfile.mkdtemp())
        self.mgr = DialogueSessionManager(sessions_dir=self.temp_dir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_and_load_transcript(self):
        from core.persona import DialogueTurn, DialogueTranscript

        turn1 = DialogueTurn(
            role="user",
            speaker="Inquirer",
            content="Paul, what is the gospel?",
            timestamp="2026-09-10T00:00:00Z",
        )
        turn2 = DialogueTurn(
            role="character",
            speaker="Paul (Apostle)",
            content="That Christ died for our sins according to the Scriptures.",
            timestamp="2026-09-10T00:00:01Z",
        )
        transcript = DialogueTranscript(
            session_id="test_session_paul",
            persona_id="paul",
            character_name="Paul (Apostle)",
            created_at="2026-09-10T00:00:00Z",
            updated_at="2026-09-10T00:00:01Z",
            title="The Gospel Definition",
            translation="ESV",
            turns=[turn1, turn2],
        )

        saved_path = self.mgr.save_transcript(transcript)
        self.assertTrue(saved_path.exists())

        loaded = self.mgr.load_transcript("test_session_paul")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.session_id, "test_session_paul")
        self.assertEqual(loaded.persona_id, "paul")
        self.assertEqual(loaded.character_name, "Paul (Apostle)")
        self.assertEqual(len(loaded.turns), 2)
        self.assertEqual(loaded.turns[0].content, "Paul, what is the gospel?")
        self.assertEqual(loaded.turns[1].speaker, "Paul (Apostle)")

    def test_list_and_delete_sessions(self):
        from core.persona import DialogueTurn, DialogueTranscript

        t1 = DialogueTranscript(
            session_id="session_1",
            persona_id="peter",
            character_name="Peter (Simon Peter)",
            created_at="2026-09-10T00:00:00Z",
            updated_at="2026-09-10T00:05:00Z",
            title="On Confession",
            turns=[DialogueTurn("user", "User", "Who is Jesus?", "2026-09-10T00:00:00Z")],
        )
        t2 = DialogueTranscript(
            session_id="session_2",
            persona_id="moses",
            character_name="Moses",
            created_at="2026-09-10T00:01:00Z",
            updated_at="2026-09-10T00:06:00Z",
            title="On the Law",
            turns=[],
        )
        self.mgr.save_transcript(t1)
        self.mgr.save_transcript(t2)

        sessions = self.mgr.list_transcripts()
        self.assertEqual(len(sessions), 2)
        # Most recently updated first
        self.assertEqual(sessions[0].session_id, "session_2")
        self.assertEqual(sessions[1].session_id, "session_1")

        deleted = self.mgr.delete_transcript("session_1")
        self.assertTrue(deleted)
        self.assertEqual(len(self.mgr.list_transcripts()), 1)
        with self.assertRaises(FileNotFoundError):
            self.mgr.load_transcript("session_1")

    def test_export_markdown_transcript(self):
        from core.persona import DialogueTurn, DialogueTranscript

        transcript = DialogueTranscript(
            session_id="markdown_test",
            persona_id="david",
            character_name="David",
            created_at="2026-09-10T00:00:00Z",
            updated_at="2026-09-10T00:00:02Z",
            title="Songs in the Night",
            translation="ESV",
            turns=[
                DialogueTurn("user", "Inquirer", "How do you praise God in grief?", "2026-09-10T00:00:00Z"),
                DialogueTurn("character", "David", "I pour out my complaint before him; I tell my trouble before him.", "2026-09-10T00:00:02Z"),
            ],
        )
        self.mgr.save_transcript(transcript)
        md_text = transcript.to_markdown()
        self.assertIn("# Songs in the Night", md_text)
        self.assertIn("Canonical Exegetical Dialogue with David", md_text)
        self.assertIn("### Inquirer", md_text)
        self.assertIn("### David", md_text)
        self.assertIn("I pour out my complaint", md_text)

        export_path = self.temp_dir / "exported_david.md"
        result_path = self.mgr.export_markdown(transcript.session_id, export_path)
        self.assertTrue(result_path.exists())
        self.assertEqual(result_path.read_text(encoding="utf-8"), md_text)

    def test_session_resume_and_save_workflow(self):
        from core.persona import BiblicalPersonaSession, DialogueTurn, DialogueTranscript

        mock_client = MagicMock()
        mock_client.is_available.return_value = False

        session = create_persona_session("paul", llm_client=mock_client)
        session.say("Why do you glory in tribulation?")

        transcript = session.to_transcript(title="Glory in Tribulation")
        self.assertEqual(transcript.persona_id, "paul")
        self.assertEqual(len(transcript.turns), 2)

        # Save through session method
        session.save(sessions_dir=self.temp_dir)

        # Resume session
        resumed_session = BiblicalPersonaSession.resume(
            transcript.session_id, sessions_dir=self.temp_dir, llm_client=mock_client
        )
        self.assertEqual(resumed_session.persona.id, "paul")
        self.assertEqual(len(resumed_session.history), 2)
        self.assertEqual(resumed_session.turn_count, 1)

        # Ensure we can continue dialoguing
        resumed_session.say("Can you explain further?")
        self.assertEqual(len(resumed_session.history), 4)
        self.assertEqual(resumed_session.turn_count, 2)


class CharacterDialogueRAGRetrievalTest(unittest.TestCase):
    """Test suite for author-scoped dynamic per-turn RAG retrieval and CharacterDialogueSession.step()."""

    def test_author_books_catalog_completeness(self):
        """Every canonical persona must specify valid, non-empty author_books."""
        from core.persona import CANONICAL_PERSONAS, get_persona_definition

        for p in CANONICAL_PERSONAS:
            if p.id == "whole-bible":
                self.assertEqual(p.author_books, (), "Whole Bible Counselor spans all 66 books and has empty author_books")
            else:
                self.assertTrue(
                    len(p.author_books) > 0,
                    f"Persona '{p.id}' has empty author_books!",
                )
            # Verify serialization
            d = p.to_dict()
            self.assertIn("author_books", d)
            self.assertEqual(d["author_books"], list(p.author_books))

        # Check key biblical figures have accurate author books
        paul = get_persona_definition("paul")
        self.assertIn("Romans", paul.author_books)
        self.assertIn("Galatians", paul.author_books)

        moses = get_persona_definition("moses")
        self.assertIn("Genesis", moses.author_books)
        self.assertIn("Exodus", moses.author_books)

        david = get_persona_definition("david")
        self.assertIn("Psalms", david.author_books)

        john = get_persona_definition("john-apostle")
        self.assertIn("John", john.author_books)
        self.assertIn("Revelation", john.author_books)

    def test_dynamic_retrieved_passage_dataclass(self):
        """DynamicRetrievedPassage must encapsulate similarity scores and metadata."""
        from core.persona import DynamicRetrievedPassage

        dp = DynamicRetrievedPassage(
            reference="45:3:21-26",
            human_ref="Romans 3:21-26",
            score=0.885,
            similarity_pct=88.5,
            text="But now the righteousness of God has been manifested...",
            translation="ESV",
            pericope_title="The Righteousness of God Through Faith",
            theological_loci=("soteriology", "christology"),
            thematic_ribbons=("covenant_grace",),
            central_proposition="God is both just and the justifier of the one who has faith.",
            retrieval_reasons=("dense_vector_pericope_semantic_similarity",),
        )
        self.assertEqual(dp.reference, "45:3:21-26")
        self.assertEqual(dp.similarity_pct, 88.5)
        d = dp.to_dict()
        self.assertEqual(d["score"], 0.885)
        self.assertEqual(d["similarity_pct"], 88.5)
        self.assertEqual(d["theological_loci"], ["soteriology", "christology"])

    def test_retrieve_author_scoped_rag_author_filtering(self):
        """retrieve_author_scoped_rag must constrain search to the character's author books."""
        from core.persona import get_persona_definition, retrieve_author_scoped_rag

        paul = get_persona_definition("paul")
        passages = retrieve_author_scoped_rag(paul, "justification by faith in Christ", max_passages=3)
        self.assertTrue(len(passages) > 0)
        for p in passages:
            self.assertIn(
                p.human_ref.split()[0],
                paul.author_books,
                f"Passage {p.human_ref} is not within Paul's author books!",
            )
            self.assertGreater(p.score, 0.0)
            self.assertGreater(p.similarity_pct, 0.0)
            self.assertLessEqual(p.similarity_pct, 100.0)

    def test_retrieve_author_scoped_rag_testament_integrity(self):
        """OT characters must strictly retrieve OT passages, preventing anachronistic NT retrieval."""
        from core.persona import get_persona_definition, retrieve_author_scoped_rag
        from core.reference import parse_reference

        moses = get_persona_definition("moses")
        passages = retrieve_author_scoped_rag(moses, "covenant holiness tabernacle sacrifice", max_passages=3)
        self.assertTrue(len(passages) > 0)
        for p in passages:
            ref = parse_reference(p.human_ref)
            self.assertEqual(ref.book.testament, "OT")

    def test_character_dialogue_session_alias_and_step(self):
        """CharacterDialogueSession must alias BiblicalPersonaSession and support step()."""
        from core.persona import (
            BiblicalPersonaSession,
            CharacterDialogueSession,
            create_persona_session,
        )

        self.assertIs(CharacterDialogueSession, BiblicalPersonaSession)

        mock_client = MagicMock()
        mock_client.is_available.return_value = False

        session = create_persona_session("paul", llm_client=mock_client)
        resp = session.step("How are we justified before God?")

        self.assertEqual(resp.character_name, "Paul (Apostle)")
        self.assertTrue(resp.offline_fallback)
        self.assertTrue(len(resp.dynamic_passages) > 0)

        # Check dynamic passages fields
        first_dp = resp.dynamic_passages[0]
        self.assertIn("human_ref", first_dp)
        self.assertIn("score", first_dp)
        self.assertIn("similarity_pct", first_dp)
        self.assertIn("text", first_dp)

        # Grounded badges should contain similarity percentages
        self.assertTrue(any("% match" in b for b in resp.grounded_passages))

        # Check turn recorded dynamic passages
        last_turn = session.turns[-1]
        self.assertEqual(last_turn.role, "character")
        self.assertTrue(len(last_turn.dynamic_passages) > 0)
        turn_dict = last_turn.to_dict()
        self.assertIn("dynamic_passages", turn_dict)

        # Check offline text includes dynamic passages section
        self.assertIn("Dynamically Retrieved Canonical Passages", resp.text)

    def test_step_with_mocked_live_llm(self):
        """step() must inject dynamically retrieved passages into live Gemini system prompt."""
        from core.llm import LLMResponse
        from core.persona import create_persona_session

        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.generate_content.return_value = LLMResponse(
            text="Grace and peace to you! Being justified by faith, we have peace with God.",
            model="gemini-2.5-pro",
            latency_seconds=0.45,
            usage={"prompt_tokens": 100, "completion_tokens": 25, "total_tokens": 125},
        )

        session = create_persona_session("paul", llm_client=mock_client)
        resp = session.step("Explain justification by faith alone.")

        self.assertFalse(resp.offline_fallback)
        self.assertEqual(resp.model, "gemini-2.5-pro")
        self.assertIn("peace with God", resp.text)
        self.assertTrue(len(resp.dynamic_passages) > 0)

        # Verify system_instruction passed to GeminiClient contained dynamic passages block
        call_kwargs = mock_client.generate_content.call_args[1]
        sys_instruction = call_kwargs["system_instruction"]
        self.assertIn("### Dynamically Retrieved Scripture Grounding (Author-Scoped)", sys_instruction)
        self.assertIn("Similarity Match:", sys_instruction)

    def test_dynamic_rag_disabled(self):
        """When enable_dynamic_rag is False, step() must not execute dynamic retrieval."""
        from core.persona import create_persona_session

        mock_client = MagicMock()
        mock_client.is_available.return_value = False

        session = create_persona_session("paul", llm_client=mock_client, enable_dynamic_rag=False)
        resp = session.step("What is faith?")

        self.assertEqual(len(resp.dynamic_passages), 0)
        self.assertFalse(any("% match" in b for b in resp.grounded_passages))


class TestWholeBibleCounselor(unittest.TestCase):
    """Test the canonical 'Whole Bible Counselor' persona."""

    def test_whole_bible_counselor_registration(self):
        p = get_persona_definition("whole-bible")
        self.assertIsNotNone(p)
        self.assertEqual(p.id, "whole-bible")
        self.assertEqual(p.canonical_name, "Whole Bible Counselor")
        self.assertEqual(p.testament, "BOTH")
        self.assertEqual(p.author_books, ())
        self.assertEqual(len(p.key_passages), 10)

    def test_whole_bible_aliases(self):
        for alias in ("counselor", "pastor", "biblical counselor", "whole bible", "wisdom counselor"):
            p = get_persona_definition(alias)
            self.assertIsNotNone(p, f"Alias '{alias}' must resolve to whole-bible persona")
            self.assertEqual(p.id, "whole-bible")

    def test_whole_bible_to_dict_fields(self):
        p = get_persona_definition("whole-bible")
        d = p.to_dict()
        self.assertEqual(d["id"], "whole-bible")
        self.assertEqual(d["canonical_name"], "Whole Bible Counselor")
        self.assertEqual(d["name"], "Whole Bible Counselor")
        self.assertEqual(d["theological_role"], p.theological_role)
        self.assertEqual(d["epithet"], p.theological_role)
        self.assertEqual(d["historical_context"], p.lifespan_description)
        self.assertEqual(d["theological_significance"], p.theological_role)
        self.assertEqual(d["testament"], "BOTH")
        self.assertEqual(len(d["key_scriptures"]), 10)

    def test_whole_bible_system_prompt_guardrails(self):
        p = get_persona_definition("whole-bible")
        prompt = generate_persona_system_prompt(p)
        self.assertIn("Mandatory Scripture Citation Formatting", prompt)
        self.assertIn("[Book Chapter:Verse]", prompt)
        self.assertIn("Whole Bible Counselor", prompt)
        self.assertIn("Canonical Whole-Bible Horizon", prompt)


class TestCitationEnforcementAndReaderLinks(unittest.TestCase):
    """Test scripture citation bracket enforcement and hyperlink rendering."""

    def test_enforce_citation_brackets_bare_references(self):
        text = "As Paul writes in Romans 8:28, God works all things together for good."
        bracketed = enforce_citation_brackets(text)
        self.assertIn("[Romans 8:28]", bracketed)
        self.assertNotIn("in Romans 8:28,", bracketed)

    def test_enforce_citation_brackets_parenthetical(self):
        text = "Remember the promise of eternal life (John 3:16) and peace."
        bracketed = enforce_citation_brackets(text)
        self.assertIn("[John 3:16]", bracketed)

    def test_enforce_citation_brackets_preserves_already_bracketed(self):
        text = "Already formatted: [Genesis 1:1] and [Revelation 22:20]."
        bracketed = enforce_citation_brackets(text)
        self.assertEqual(text, bracketed)

    def test_enforce_citation_brackets_numbered_and_multiword_books(self):
        text = "Consider 1 Corinthians 13:4-8, 2 Timothy 3:16, and Song of Solomon 2:4."
        bracketed = enforce_citation_brackets(text)
        self.assertIn("[1 Corinthians 13:4-8]", bracketed)
        self.assertIn("[2 Timothy 3:16]", bracketed)
        self.assertIn("[Song of Solomon 2:4]", bracketed)

    def test_enforce_citation_brackets_ignores_non_scripture(self):
        text = "The meeting is at 10:30 tomorrow or at 14:00."
        bracketed = enforce_citation_brackets(text)
        self.assertEqual(text, bracketed)

    def test_extract_scripture_citations(self):
        text = "Reflect on [Romans 8:28], then [Psalm 23:1], and remember [Romans 8:28] again."
        citations = extract_scripture_citations(text)
        self.assertEqual(citations, ["Romans 8:28", "Psalms 23:1"])

    def test_extract_scripture_citations_empty(self):
        self.assertEqual(extract_scripture_citations("No scripture here."), [])
        self.assertEqual(extract_scripture_citations(""), [])

    def test_render_citation_reader_links_markdown(self):
        text = "Consider [Romans 8:28] and [Genesis 1:1]."
        md = render_citation_reader_links(text, base_url="#passage=", as_html=False)
        self.assertIn("[Romans 8:28](#passage=Romans%208%3A28)", md)
        self.assertIn("[Genesis 1:1](#passage=Genesis%201%3A1)", md)

    def test_render_citation_reader_links_html(self):
        text = "Consider [Romans 8:28]."
        html = render_citation_reader_links(text, base_url="#passage=", as_html=True)
        self.assertIn('class="citation-reader-link"', html)
        self.assertIn('data-ref="Romans 8:28"', html)
        self.assertIn('href="#passage=Romans%208%3A28"', html)
        self.assertIn('>[Romans 8:28]</a>', html)


class TestWholeBibleCounselorSession(unittest.TestCase):
    """Test whole-bible counselor session, dynamic RAG, and citation tracking."""

    def test_whole_bible_dynamic_rag(self):
        persona = get_persona_definition("whole-bible")
        passages = retrieve_author_scoped_rag(persona, "suffering and comfort in affliction", max_passages=3)
        self.assertGreater(len(passages), 0)
        for p in passages:
            self.assertTrue(p.human_ref)
            self.assertGreater(p.similarity_pct, 0.0)

    def test_offline_counselor_response_citations(self):
        session = create_persona_session("whole-bible")
        resp = session.step("How should I bear heavy grief and sorrow?")
        self.assertTrue(resp.offline_fallback)
        self.assertEqual(resp.character_id, "whole-bible")
        self.assertTrue(len(resp.citations) > 0)
        for citation in resp.citations:
            self.assertIn(f"[{citation}]", resp.text)
        md_text = resp.text_with_reader_links(as_html=False)
        self.assertIn("](#passage=", md_text)
        html_text = resp.text_with_reader_links(as_html=True)
        self.assertIn('class="citation-reader-link"', html_text)

    def test_live_mocked_llm_citation_enforcement(self):
        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.generate_content.return_value = LLMResponse(
            text="As written in Romans 8:28 and Psalm 23:1-3, the Lord shepherds his people through valley deeps.",
            model="gemini-2.5-pro",
            latency_seconds=0.35,
            usage={"prompt_tokens": 100, "completion_tokens": 30, "total_tokens": 130},
        )
        session = create_persona_session("whole-bible", llm_client=mock_client)
        resp = session.step("Where do I find peace in grief?")
        self.assertFalse(resp.offline_fallback)
        self.assertIn("[Romans 8:28]", resp.text)
        self.assertIn("[Psalm 23:1-3]", resp.text)
        self.assertIn("Romans 8:28", resp.citations)
        self.assertIn("Psalms 23:1-3", resp.citations)

    def test_dialogue_transcript_markdown_with_citations(self):
        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.generate_content.return_value = LLMResponse(
            text="Peace be with you. Take heart from [John 16:33] and [Romans 8:31].",
            model="gemini-2.5-pro",
            latency_seconds=0.25,
            usage={"prompt_tokens": 80, "completion_tokens": 20, "total_tokens": 100},
        )
        session = create_persona_session("whole-bible", llm_client=mock_client)
        session.step("I feel overwhelmed by the world.")
        transcript = session.to_transcript()
        md = transcript.to_markdown()
        self.assertIn("[John 16:33](#passage=John%2016%3A33)", md)
        self.assertIn("[Romans 8:31](#passage=Romans%208%3A31)", md)
        self.assertIn("## Exegetical Reference Matrix", md)


if __name__ == "__main__":
    unittest.main()
