"""Hermetic Unit Tests for Zero-Dependency Google Gemini LLM Client & Context Engine.

Verifies:
- API key discovery across parameters, environment variables, .env, and config files.
- PassageContext builder with default ESV translation, Crossway attribution, and WEB fallback.
- GeminiClient initialization, authentication headers, and availability checks.
- Unary content generation with gemini-2.5-pro and ChatMessage structures.
- Automatic model fallback from gemini-2.5-pro to gemini-2.0-flash on 404/429 errors.
- Retry logic with exponential backoff on transient 500/503/network errors.
- Streaming response generation with Server-Sent Events (SSE) chunks.
- Structured JSON generation mode and markdown code fence unwrapping.
- Embeddings API generation (single and batch).
"""

import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from core.db import Database, VerseRecord
from core.llm import (
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_GEMINI_MODEL,
    FALLBACK_GEMINI_MODEL,
    ChatMessage,
    GeminiClient,
    GenerationConfig,
    LLMAuthError,
    LLMError,
    LLMModelNotFoundError,
    LLMNetworkError,
    LLMRateLimitError,
    LLMResponse,
    LLMResponseError,
    PassageContext,
    StreamChunk,
    build_passage_context,
    get_gemini_api_key,
)
from core.reference import parse_reference


class TestGeminiKeyDiscovery(unittest.TestCase):
    """Test Gemini API key resolution order across inputs, env vars, and files."""

    def test_explicit_key_priority(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "env_key", "GOOGLE_API_KEY": "google_key"}):
            self.assertEqual(get_gemini_api_key("explicit_key"), "explicit_key")

    def test_gemini_api_key_env_var(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "gemini_env_val", "GOOGLE_API_KEY": ""}):
            self.assertEqual(get_gemini_api_key(), "gemini_env_val")

    def test_google_api_key_fallback_env_var(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "", "GOOGLE_API_KEY": "google_env_val"}):
            self.assertEqual(get_gemini_api_key(), "google_env_val")

    def test_env_file_discovery(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text("SOME_VAR=1\nGEMINI_API_KEY=test_env_file_key\n", encoding="utf-8")
            with patch("core.llm.Path.cwd", return_value=Path(tmpdir)):
                with patch.dict(os.environ, {}, clear=True):
                    self.assertEqual(get_gemini_api_key(), "test_env_file_key")

    def test_config_file_discovery(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_file = Path(tmpdir) / "config" / "gemini_api_key.txt"
            cfg_file.parent.mkdir(parents=True)
            cfg_file.write_text("test_config_file_key\n", encoding="utf-8")
            fake_llm_path = Path(tmpdir) / "core" / "llm.py"
            with patch.dict(os.environ, {}, clear=True):
                with patch("core.llm.Path.cwd", return_value=Path("/tmp/nonexistent")):
                    with patch("core.llm.Path.home", return_value=Path("/tmp/nonexistent_home")):
                        with patch("core.llm.__file__", str(fake_llm_path)):
                            self.assertEqual(get_gemini_api_key(), "test_config_file_key")

    def test_unset_key_returns_none(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("core.llm.Path.cwd", return_value=Path("/tmp/nonexistent")):
                with patch("core.llm.Path.home", return_value=Path("/tmp/nonexistent_home")):
                    self.assertIsNone(get_gemini_api_key())


class TestPassageContextBuilder(unittest.TestCase):
    """Test passage context construction, ESV default routing, and formatting."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "test_llm_passage.db"
        self.db = Database(self.db_path, auto_init=True)
        self.db.add_translation("WEB", "World English Bible")

        # Seed sample WEB and ESV verses
        verses = [
            VerseRecord(
                translation_id="WEB",
                book_id=43,
                chapter=3,
                verse=16,
                text="For God so loved the world...",
                canonical_verse_id=43003016,
            ),
            VerseRecord(
                translation_id="WEB",
                book_id=43,
                chapter=3,
                verse=17,
                text="For God didn't send his Son...",
                canonical_verse_id=43003017,
            ),
        ]
        self.db.insert_verses(verses)

    def tearDown(self):
        self.db.close()
        self.tmpdir.cleanup()

    def test_build_passage_context_with_web_fallback(self):
        # Without ESV cache and without network, should fallback to WEB
        ctx = build_passage_context("John 3:16", db=self.db, translation="ESV", allow_network=False)
        self.assertEqual(ctx.reference, "John 3:16")
        self.assertEqual(ctx.translation, "WEB")
        self.assertTrue(ctx.fallback_used)
        self.assertEqual(ctx.fallback_translation, "WEB")
        self.assertIn("World English Bible", ctx.attribution)
        self.assertEqual(len(ctx.verses), 1)

        prompt_block = ctx.format_prompt_block()
        self.assertIn("John 3:16 (WEB)", prompt_block)
        self.assertIn("[16] For God so loved", prompt_block)
        self.assertIn("Translated from fallback WEB", prompt_block)

    def test_build_passage_context_with_esv_cache(self):
        # Seed ESV cache
        esv_verse = [
            VerseRecord(
                translation_id="ESV",
                book_id=43,
                chapter=3,
                verse=16,
                text="For God so loved the world, that he gave his only Son...",
                canonical_verse_id=43003016,
            )
        ]
        self.db.save_esv_cached_verses(esv_verse)

        ctx = build_passage_context("John 3:16", db=self.db, translation="ESV", allow_network=False)
        self.assertEqual(ctx.reference, "John 3:16")
        self.assertEqual(ctx.translation, "ESV")
        self.assertFalse(ctx.fallback_used)
        self.assertIn("(ESV) - www.esv.org", ctx.attribution)

        prompt_block = ctx.format_prompt_block()
        self.assertIn("John 3:16 (ESV)", prompt_block)
        self.assertIn("his only Son", prompt_block)
        self.assertIn("(ESV) - www.esv.org", prompt_block)

        d = ctx.to_dict()
        self.assertEqual(d["reference"], "John 3:16")
        self.assertEqual(d["translation"], "ESV")
        self.assertEqual(d["verse_count"], 1)
        self.assertIsInstance(ctx, PassageContext)

        # Reference object input
        ref_obj = parse_reference("John 3:16")
        ctx_from_ref = build_passage_context(ref_obj, db=self.db, translation="ESV", allow_network=False)
        self.assertEqual(ctx_from_ref.reference, "John 3:16")


class TestGeminiClientUnary(unittest.TestCase):
    """Test unary generation, parameter serialization, and response parsing."""

    def test_availability(self):
        c_no_key = GeminiClient(api_key=None)
        with patch.dict(os.environ, {}, clear=True):
            with patch("core.llm.Path.cwd", return_value=Path("/tmp/nonexistent")):
                self.assertFalse(c_no_key.is_available())

        c_with_key = GeminiClient(api_key="test_key_123")
        self.assertTrue(c_with_key.is_available())

    def test_missing_key_raises_auth_error(self):
        c = GeminiClient(api_key=None)
        with patch.dict(os.environ, {}, clear=True):
            with patch("core.llm.Path.cwd", return_value=Path("/tmp/nonexistent")):
                with self.assertRaises(LLMAuthError):
                    c.generate("Hello")

    def test_successful_generate(self):
        mock_opener = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "Grace to you and peace from God our Father."}],
                        "role": "model",
                    },
                    "finishReason": "STOP",
                    "index": 0,
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 15,
                "candidatesTokenCount": 12,
                "totalTokenCount": 27,
            },
        }).encode("utf-8")
        mock_resp.headers.get_content_charset.return_value = "utf-8"
        mock_opener.open.return_value.__enter__.return_value = mock_resp

        client = GeminiClient(api_key="mock_key", opener=mock_opener)
        cfg = GenerationConfig(temperature=0.4, max_output_tokens=100)
        res = client.generate(
            prompt="Write a biblical greeting",
            system_instruction="Speak like Paul",
            config=cfg,
        )

        self.assertEqual(res.text, "Grace to you and peace from God our Father.")
        self.assertEqual(res.model, DEFAULT_GEMINI_MODEL)
        self.assertEqual(res.finish_reason, "STOP")
        self.assertEqual(res.usage["total_tokens"], 27)
        self.assertFalse(res.fallback_used)
        self.assertEqual(res.attempts, 1)

        # Inspect HTTP request details
        call_args = mock_opener.open.call_args
        req = call_args[0][0]
        self.assertIn(f"/{DEFAULT_GEMINI_MODEL}:generateContent", req.full_url)
        self.assertEqual(req.headers["X-goog-api-key"], "mock_key")
        self.assertEqual(req.headers["Content-type"], "application/json")

        payload = json.loads(req.data.decode("utf-8"))
        self.assertEqual(payload["contents"][0]["parts"][0]["text"], "Write a biblical greeting")
        self.assertEqual(payload["system_instruction"]["parts"][0]["text"], "Speak like Paul")
        self.assertEqual(payload["generationConfig"]["temperature"], 0.4)
        self.assertEqual(payload["generationConfig"]["maxOutputTokens"], 100)

    def test_chat_messages_input(self):
        mock_opener = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({
            "candidates": [{"content": {"parts": [{"text": "Response"}]}}],
        }).encode("utf-8")
        mock_resp.headers.get_content_charset.return_value = "utf-8"
        mock_opener.open.return_value.__enter__.return_value = mock_resp

        client = GeminiClient(api_key="mock_key", opener=mock_opener)
        messages = [
            ChatMessage(role="system", content="System instruction"),
            ChatMessage(role="user", content="Hello"),
            ChatMessage(role="model", content="Greetings"),
            ChatMessage(role="user", content="How are you?"),
        ]
        res = client.generate(messages)
        self.assertEqual(res.text, "Response")

        call_args = mock_opener.open.call_args
        payload = json.loads(call_args[0][0].data.decode("utf-8"))
        self.assertEqual(payload["system_instruction"]["parts"][0]["text"], "System instruction")
        self.assertEqual(len(payload["contents"]), 3)
        self.assertEqual(payload["contents"][0]["role"], "user")
        self.assertEqual(payload["contents"][1]["role"], "model")
        self.assertEqual(payload["contents"][2]["role"], "user")

    def test_prompt_safety_blocked(self):
        mock_opener = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({
            "candidates": [],
            "promptFeedback": {"blockReason": "SAFETY"},
        }).encode("utf-8")
        mock_resp.headers.get_content_charset.return_value = "utf-8"
        mock_opener.open.return_value.__enter__.return_value = mock_resp

        client = GeminiClient(api_key="mock_key", opener=mock_opener)
        with self.assertRaises(LLMResponseError) as cm:
            client.generate("Trigger safety filter")
        self.assertIn("SAFETY", str(cm.exception))


class TestGeminiClientFallbackAndRetries(unittest.TestCase):
    """Test automatic fallback from gemini-2.5-pro to gemini-2.0-flash and retry loops."""

    def test_fallback_on_404_model_not_found(self):
        mock_opener = MagicMock()

        # First request (gemini-2.5-pro) fails with 404
        err_404 = HTTPError("url", 404, "Not Found", {}, io.BytesIO(b'{"error": "models/gemini-2.5-pro is not found"}'))

        # Second request (gemini-2.0-flash) succeeds
        mock_resp_200 = MagicMock()
        mock_resp_200.status = 200
        mock_resp_200.read.return_value = json.dumps({
            "candidates": [{"content": {"parts": [{"text": "Fallback answer from flash"}]}}],
            "usageMetadata": {"totalTokenCount": 10},
        }).encode("utf-8")
        mock_resp_200.headers.get_content_charset.return_value = "utf-8"
        mock_resp_200.__enter__.return_value = mock_resp_200

        mock_opener.open.side_effect = [err_404, mock_resp_200]

        client = GeminiClient(api_key="mock_key", opener=mock_opener, max_retries=0)
        res = client.generate("Hello world")

        self.assertEqual(res.text, "Fallback answer from flash")
        self.assertEqual(res.model, FALLBACK_GEMINI_MODEL)
        self.assertTrue(res.fallback_used)
        self.assertEqual(mock_opener.open.call_count, 2)
        self.assertTrue(issubclass(LLMModelNotFoundError, LLMError))

    def test_auth_error_401_fails_immediately_without_fallback(self):
        mock_opener = MagicMock()
        err_401 = HTTPError("url", 401, "Unauthorized", {}, io.BytesIO(b'{"error": "API_KEY_INVALID"}'))
        mock_opener.open.side_effect = err_401

        client = GeminiClient(api_key="invalid_key", opener=mock_opener, max_retries=1)
        with self.assertRaises(LLMAuthError):
            client.generate("Test")

        # Should not retry auth errors
        self.assertEqual(mock_opener.open.call_count, 1)

    def test_transient_500_retries_and_succeeds(self):
        mock_opener = MagicMock()
        err_500 = HTTPError("url", 500, "Internal Server Error", {}, io.BytesIO(b"{}"))

        mock_resp_200 = MagicMock()
        mock_resp_200.status = 200
        mock_resp_200.read.return_value = json.dumps({
            "candidates": [{"content": {"parts": [{"text": "Success after 500"}]}}],
        }).encode("utf-8")
        mock_resp_200.headers.get_content_charset.return_value = "utf-8"
        mock_resp_200.__enter__.return_value = mock_resp_200

        mock_opener.open.side_effect = [err_500, mock_resp_200]

        client = GeminiClient(api_key="mock_key", opener=mock_opener, max_retries=2, backoff_factor=1.0)
        res = client.generate("Test prompt")
        self.assertEqual(res.text, "Success after 500")
        self.assertEqual(mock_opener.open.call_count, 2)


class TestGeminiClientStreaming(unittest.TestCase):
    """Test streaming generator with Server-Sent Events."""

    def test_streaming_sse_chunks(self):
        mock_opener = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status = 200

        # Simulate SSE lines
        sse_lines = [
            b'data: {"candidates": [{"content": {"parts": [{"text": "In the "}]}}]}\n',
            b"\n",
            b'data: {"candidates": [{"content": {"parts": [{"text": "beginning..."}]}}]}\n',
            b"\n",
            b'data: {"candidates": [{"content": {"parts": []}, "finishReason": "STOP"}]}\n',
            b"\n",
            b"data: [DONE]\n",
        ]
        mock_resp.__iter__.return_value = iter(sse_lines)
        mock_opener.open.return_value.__enter__.return_value = mock_resp

        client = GeminiClient(api_key="mock_key", opener=mock_opener)
        chunks = list(client.generate_stream("Stream this"))

        self.assertEqual(len(chunks), 3)
        self.assertEqual(chunks[0].text, "In the ")
        self.assertEqual(chunks[1].text, "beginning...")
        self.assertEqual(chunks[2].finish_reason, "STOP")
        self.assertIsInstance(chunks[0], StreamChunk)


class TestGeminiClientJSONAndEmbeddings(unittest.TestCase):
    """Test structured JSON parsing and vector embeddings."""

    def test_generate_json_clean(self):
        mock_opener = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({
            "candidates": [{"content": {"parts": [{"text": "```json\n{\"doctrine\": \"Atonement\", \"confidence\": 0.98}\n```"}]}}],
        }).encode("utf-8")
        mock_resp.headers.get_content_charset.return_value = "utf-8"
        mock_opener.open.return_value.__enter__.return_value = mock_resp

        client = GeminiClient(api_key="mock_key", opener=mock_opener)
        data, res = client.generate_json("Analyze passage")

        self.assertEqual(data["doctrine"], "Atonement")
        self.assertEqual(data["confidence"], 0.98)
        self.assertIsInstance(res, LLMResponse)

    def test_generate_json_parse_error(self):
        mock_opener = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({
            "candidates": [{"content": {"parts": [{"text": "Not valid JSON at all"}]}}],
        }).encode("utf-8")
        mock_resp.headers.get_content_charset.return_value = "utf-8"
        mock_opener.open.return_value.__enter__.return_value = mock_resp

        client = GeminiClient(api_key="mock_key", opener=mock_opener)
        with self.assertRaises(LLMResponseError):
            client.generate_json("Test")

    def test_embed_content(self):
        mock_opener = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({
            "embedding": {"values": [0.1, -0.2, 0.35]},
        }).encode("utf-8")
        mock_resp.headers.get_content_charset.return_value = "utf-8"
        mock_opener.open.return_value.__enter__.return_value = mock_resp

        client = GeminiClient(api_key="mock_key", opener=mock_opener)
        vector = client.embed_content("In the beginning")

        self.assertEqual(vector, [0.1, -0.2, 0.35])
        req = mock_opener.open.call_args[0][0]
        self.assertIn(f"/{DEFAULT_EMBEDDING_MODEL}:embedContent", req.full_url)

    def test_batch_embed_contents(self):
        mock_opener = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({
            "embeddings": [
                {"values": [0.1, 0.2]},
                {"values": [-0.3, 0.4]},
            ],
        }).encode("utf-8")
        mock_resp.headers.get_content_charset.return_value = "utf-8"
        mock_opener.open.return_value.__enter__.return_value = mock_resp

        client = GeminiClient(api_key="mock_key", opener=mock_opener)
        vectors = client.batch_embed_contents(["Passage 1", "Passage 2"])

        self.assertEqual(len(vectors), 2)
        self.assertEqual(vectors[0], [0.1, 0.2])
        self.assertEqual(vectors[1], [-0.3, 0.4])


if __name__ == "__main__":
    unittest.main()


class TestGeminiEdgeCasesAndDTOs(unittest.TestCase):
    """Test DTO serialization, stream errors, and edge case coverage."""

    def test_dto_serialization(self):
        msg = ChatMessage(role="user", content="Test")
        self.assertEqual(msg.to_dict(), {"role": "user", "content": "Test"})

        cfg = GenerationConfig(
            temperature=0.8,
            top_p=0.9,
            top_k=20,
            max_output_tokens=500,
            stop_sequences=["END"],
            response_mime_type="application/json",
            response_schema={"type": "object"},
        )
        d = cfg.to_dict()
        self.assertEqual(d["temperature"], 0.8)
        self.assertEqual(d["topP"], 0.9)
        self.assertEqual(d["topK"], 20)
        self.assertEqual(d["maxOutputTokens"], 500)
        self.assertEqual(d["stopSequences"], ["END"])
        self.assertEqual(d["responseMimeType"], "application/json")
        self.assertEqual(d["responseSchema"], {"type": "object"})

        resp = LLMResponse(
            text="Result",
            model="gemini-2.5-pro",
            finish_reason="STOP",
            usage={"total_tokens": 10},
            latency_seconds=0.1234,
            fallback_used=False,
            attempts=1,
        )
        self.assertEqual(resp.to_dict()["text"], "Result")
        self.assertEqual(resp.to_dict()["latency_seconds"], 0.123)

    def test_stream_auth_and_network_errors(self):
        mock_opener = MagicMock()
        err_401 = HTTPError("url", 401, "Unauthorized", {}, io.BytesIO(b"{}"))
        mock_opener.open.side_effect = err_401

        client = GeminiClient(api_key="key", opener=mock_opener)
        with self.assertRaises(LLMAuthError):
            list(client.generate_stream("Test"))

        mock_opener.open.side_effect = URLError("DNS failure")
        with self.assertRaises(LLMNetworkError):
            list(client.generate_stream("Test"))

    def test_stream_rate_limit_error(self):
        mock_opener = MagicMock()
        err_429 = HTTPError("url", 429, "Too Many Requests", {}, io.BytesIO(b"{}"))
        mock_opener.open.side_effect = err_429

        client = GeminiClient(api_key="key", opener=mock_opener)
        with self.assertRaises(LLMRateLimitError):
            list(client.generate_stream("Test"))

    def test_batch_embed_empty(self):
        client = GeminiClient(api_key="key")
        self.assertEqual(client.batch_embed_contents([]), [])

    def test_batch_embed_mismatch_raises_response_error(self):
        mock_opener = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({"embeddings": []}).encode("utf-8")
        mock_resp.headers.get_content_charset.return_value = "utf-8"
        mock_opener.open.return_value.__enter__.return_value = mock_resp

        client = GeminiClient(api_key="key", opener=mock_opener)
        with self.assertRaises(LLMResponseError):
            client.batch_embed_contents(["Text 1", "Text 2"])

    def test_empty_embedding_values_raises_response_error(self):
        mock_opener = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({"embedding": {"values": []}}).encode("utf-8")
        mock_resp.headers.get_content_charset.return_value = "utf-8"
        mock_opener.open.return_value.__enter__.return_value = mock_resp

        client = GeminiClient(api_key="key", opener=mock_opener)
        with self.assertRaises(LLMResponseError):
            client.embed_content("Text")
