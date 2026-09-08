"""Hermetic Unit Tests for Scripture RAG Retrieval Engine (core.rag).

Verifies:
- Natural language query feature extraction and stop word filtering.
- Canonical scripture reference detection in conversational queries.
- Theological loci, redemptive epochs, and thematic ribbon motif detection.
- FTS5 keyword search and BM25 rank integration.
- Semantic tag intersection and relevance scoring.
- Canonical cross-reference and typological arc shadow-to-fulfillment expansion.
- Pericope coherence grouping and token budget clamping.
- Grounded context window markdown generation and Gemini API payload formatting.
- Deterministic reference context building.
- LLM answer synthesis error handling and mock generation.
- Zero external dependencies per ADR-003.
"""

import unittest
from unittest.mock import MagicMock, patch

from core.db import Database
from core.llm import LLMAuthError, LLMResponse
from core.rag import (
    RAGContextWindow,
    RAGResponse,
    RAGScoringWeights,
    ScriptureRAGEngine,
    estimate_tokens,
    extract_query_features,
    get_rag_engine,
    retrieve_rag_context,
)
from core.theology import ThematicRibbon, TheologicalLocus


class TestEstimateTokens(unittest.TestCase):
    """Test token estimation utility."""

    def test_empty_string(self):
        self.assertEqual(estimate_tokens(""), 0)
        self.assertEqual(estimate_tokens(None), 0)

    def test_sample_text(self):
        text = "In the beginning God created the heavens and the earth."
        tokens = estimate_tokens(text)
        self.assertGreaterEqual(tokens, 10)
        self.assertLessEqual(tokens, 20)


class TestQueryFeatureExtraction(unittest.TestCase):
    """Test natural language query parsing and theological concept detection."""

    @classmethod
    def setUpClass(cls):
        cls.db = Database()

    def test_explicit_reference_extraction(self):
        query = "What does Romans 8:28 teach about divine sovereignty?"
        features = extract_query_features(query, self.db)
        self.assertEqual(len(features.explicit_references), 1)
        self.assertEqual(features.explicit_references[0].format(), "Romans 8:28")
        self.assertFalse(features.is_empty)

    def test_multiple_references_extraction(self):
        query = "Compare John 3:16 with Genesis 3:15 and Romans 5:8."
        features = extract_query_features(query, self.db)
        refs = [r.format() for r in features.explicit_references]
        self.assertIn("John 3:16", refs)
        self.assertIn("Genesis 3:15", refs)
        self.assertIn("Romans 5:8", refs)

    def test_keyword_stop_word_filtering(self):
        query = "How does the Bible explain the role of grace in salvation?"
        features = extract_query_features(query, self.db)
        self.assertNotIn("how", features.keywords)
        self.assertNotIn("does", features.keywords)
        self.assertNotIn("the", features.keywords)
        self.assertNotIn("explain", features.keywords)
        self.assertNotIn("role", features.keywords)
        self.assertIn("grace", features.keywords)
        self.assertIn("salvation", features.keywords)

    def test_theological_locus_detection(self):
        query = "Examine justification by faith alone and soteriology."
        features = extract_query_features(query, self.db)
        self.assertIn(TheologicalLocus.SOTERIOLOGY, features.detected_loci)

    def test_thematic_ribbon_and_typological_keywords(self):
        query = "Trace the theme of the temple from Eden to the New Jerusalem."
        features = extract_query_features(query, self.db)
        self.assertIn(ThematicRibbon.TEMPLE_PRESENCE, features.detected_ribbons)
        self.assertIn(ThematicRibbon.CITY_OF_GOD, features.detected_ribbons)
        self.assertIn("temple", features.typological_keywords)
        self.assertIn("tabernacle", features.typological_keywords)
        self.assertIn("sanctuary", features.typological_keywords)

    def test_empty_query(self):
        features = extract_query_features("", self.db)
        self.assertTrue(features.is_empty)

    def test_to_dict_serialization(self):
        query = "Tell me about John 3:16 and atonement."
        features = extract_query_features(query, self.db)
        d = features.to_dict()
        self.assertEqual(d["raw_query"], query)
        self.assertIn("John 3:16", d["explicit_references"])
        self.assertIsInstance(d["keywords"], list)
        self.assertIsInstance(d["detected_loci"], list)


class TestRAGScoringWeights(unittest.TestCase):
    """Test scoring weights configuration."""

    def test_default_weights(self):
        w = RAGScoringWeights()
        self.assertEqual(w.explicit_ref_score, 1.00)
        self.assertEqual(w.fts_weight, 0.25)
        self.assertEqual(w.typology_weight, 0.35)
        self.assertEqual(w.theology_weight, 0.15)
        self.assertEqual(w.crossref_weight, 0.15)
        self.assertEqual(w.tag_weight, 0.20)
        self.assertEqual(w.starred_boost, 0.05)

    def test_custom_weights(self):
        w = RAGScoringWeights(fts_weight=0.5, typology_weight=0.2)
        self.assertEqual(w.fts_weight, 0.5)
        self.assertEqual(w.typology_weight, 0.2)


class TestScriptureRAGEngineRetrieval(unittest.TestCase):
    """Test multi-signal hybrid retrieval across database."""

    @classmethod
    def setUpClass(cls):
        cls.db = Database()
        cls.engine = ScriptureRAGEngine(db=cls.db)

    def test_explicit_reference_inquiry(self):
        ctx = self.engine.retrieve("What does Romans 8:28-30 teach?", max_passages=3)
        self.assertIsInstance(ctx, RAGContextWindow)
        self.assertGreaterEqual(len(ctx.passages), 1)
        top_passage = ctx.passages[0]
        self.assertEqual(top_passage.human_ref, "Romans 8:28-30")
        self.assertEqual(top_passage.score, 1.0)
        self.assertTrue(any("Explicit reference" in r for r in top_passage.retrieval_reasons))

    def test_temple_typological_retrieval(self):
        ctx = self.engine.retrieve(
            "Trace the theme of the temple from the Garden of Eden to the New Jerusalem",
            max_passages=5,
        )
        self.assertGreater(len(ctx.passages), 0)
        passage_refs = [p.human_ref for p in ctx.passages]

        # Verify key canonical temple/tabernacle milestones are captured
        has_tabernacle_or_temple = any(
            "Exodus 25" in r or "Exodus 40" in r or "John 1:14" in r or "Hebrews 9" in r
            for r in passage_refs
        )
        self.assertTrue(has_tabernacle_or_temple, f"Expected tabernacle/temple passages, got {passage_refs}")

        # Verify typological arcs are present
        all_arcs = [a for p in ctx.passages for a in p.typological_arcs]
        self.assertGreater(len(all_arcs), 0)

    def test_day_of_atonement_retrieval(self):
        ctx = self.engine.retrieve("How does Jesus fulfill the Day of Atonement?", max_passages=5)
        self.assertGreater(len(ctx.passages), 0)
        passage_refs = [p.human_ref for p in ctx.passages]

        # Expect Leviticus (Day of Atonement shadow) or Hebrews (Christ's fulfillment)
        has_atonement_focus = any(
            "Leviticus 16" in r or "Hebrews 9" in r or "Exodus 12" in r or "Leviticus 23" in r
            for r in passage_refs
        )
        self.assertTrue(has_atonement_focus, f"Expected Day of Atonement passages, got {passage_refs}")

    def test_fts5_keyword_search(self):
        ctx = self.engine.retrieve("light of the world", max_passages=3)
        self.assertGreater(len(ctx.passages), 0)
        texts = " ".join(p.text.lower() for p in ctx.passages)
        self.assertIn("light", texts)

    def test_expansion_toggle(self):
        # When expansion is disabled, typological arc expansion and crossrefs are skipped
        ctx_no_exp = self.engine.retrieve("light of the world", max_passages=3, allow_expansion=False)
        self.assertGreater(len(ctx_no_exp.passages), 0)
        for p in ctx_no_exp.passages:
            self.assertFalse(any("Typological" in r for r in p.retrieval_reasons))

    def test_token_budget_enforcement(self):
        # Set tiny token budget: permits exactly 1 passage and halts further additions
        ctx_small = self.engine.retrieve("God so loved the world", max_passages=10, max_tokens=150)
        self.assertEqual(len(ctx_small.passages), 1)
        self.assertLessEqual(ctx_small.estimated_tokens, 450)

    def test_passage_clamping_for_long_chapters(self):
        # Ensure long 50+ verse chapters don't produce massive passages
        ctx = self.engine.retrieve("Luke 2", max_passages=1)
        self.assertGreater(len(ctx.passages), 0)
        p = ctx.passages[0]
        # Should be clamped to 12 verses
        self.assertLessEqual(len(p.verses), 12)

    def test_build_context_for_references(self):
        refs = ["John 3:16", "Romans 8:1"]
        ctx = self.engine.build_context_for_references(refs, query="Gospel assurance")
        self.assertEqual(len(ctx.passages), 2)
        self.assertEqual(ctx.passages[0].human_ref, "John 3:16")
        self.assertEqual(ctx.passages[1].human_ref, "Romans 8:1")
        self.assertEqual(ctx.passages[0].score, 1.0)
        self.assertEqual(ctx.query, "Gospel assurance")


class TestRAGContextFormatting(unittest.TestCase):
    """Test context window markdown formatting and prompt generation."""

    @classmethod
    def setUpClass(cls):
        cls.db = Database()
        cls.engine = ScriptureRAGEngine(db=cls.db)

    def test_format_context_markdown(self):
        ctx = self.engine.retrieve("John 3:16", max_passages=1)
        md = ctx.format_context_markdown()
        self.assertIn("# Scripture RAG Grounded Context: John 3:16", md)
        self.assertIn("The Gospel Coalition Standard", md)
        self.assertIn("John 3:16", md)
        self.assertIn("Grounded Scripture Passages", md)

    def test_format_prompt_payload(self):
        ctx = self.engine.retrieve("John 3:16", max_passages=1)
        payload = ctx.format_prompt_payload(custom_instructions="Be brief.")
        self.assertIn("system_instruction", payload)
        self.assertIn("contents", payload)
        parts = payload["contents"][0]["parts"][0]["text"]
        self.assertIn("## User Inquiry", parts)
        self.assertIn("Be brief.", parts)

    def test_to_dict_serialization(self):
        ctx = self.engine.retrieve("John 3:16", max_passages=1)
        d = ctx.to_dict()
        self.assertEqual(d["query"], "John 3:16")
        self.assertEqual(d["passage_count"], 1)
        self.assertGreater(d["total_verses"], 0)
        self.assertIsInstance(d["passages"], list)
        p0 = d["passages"][0]
        self.assertEqual(p0["human_ref"], "John 3:16")
        self.assertIn("score", p0)
        self.assertIn("verses", p0)


class TestRAGAnswerSynthesis(unittest.TestCase):
    """Test LLM answer synthesis and error handling."""

    @classmethod
    def setUpClass(cls):
        cls.db = Database()
        cls.engine = ScriptureRAGEngine(db=cls.db)

    def test_answer_without_api_key_raises_auth_error(self):
        with patch("core.rag.get_gemini_api_key", return_value=None):
            with self.assertRaises(LLMAuthError) as cm:
                self.engine.answer("Explain John 3:16")
            self.assertIn("GEMINI_API_KEY is not configured", str(cm.exception))

    def test_answer_with_mocked_client(self):
        mock_client = MagicMock()
        mock_client.generate.return_value = LLMResponse(
            text="In John 3:16, God demonstrates His sacrificial love by giving His Son for salvation.",
            model="gemini-2.5-pro",
            usage={"prompt_tokens": 420, "candidate_tokens": 55, "total_tokens": 475},
        )

        resp = self.engine.answer("Explain John 3:16", client=mock_client)
        self.assertIsInstance(resp, RAGResponse)
        self.assertEqual(resp.query, "Explain John 3:16")
        self.assertIn("sacrificial love", resp.answer)
        self.assertEqual(resp.model, "gemini-2.5-pro")
        self.assertEqual(resp.token_usage["total_tokens"], 475)
        self.assertIsInstance(resp.context, RAGContextWindow)

        # Verify to_dict
        d = resp.to_dict()
        self.assertEqual(d["query"], "Explain John 3:16")
        self.assertIn("sacrificial love", d["answer"])
        self.assertEqual(d["model"], "gemini-2.5-pro")


class TestRAGModuleSingletons(unittest.TestCase):
    """Test convenience factory functions."""

    def test_get_rag_engine(self):
        engine1 = get_rag_engine()
        engine2 = get_rag_engine()
        self.assertIs(engine1, engine2)
        self.assertIsInstance(engine1, ScriptureRAGEngine)

    def test_retrieve_rag_context(self):
        ctx = retrieve_rag_context("John 3:16", max_passages=1)
        self.assertIsInstance(ctx, RAGContextWindow)
        self.assertEqual(len(ctx.passages), 1)


if __name__ == "__main__":
    unittest.main()
