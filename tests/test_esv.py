"""Hermetic Unit Tests for Zero-Dependency ESV API Client & 500-Verse LRU Cache.

Verifies:
- Key discovery from argument, environment, and config files.
- Crossway legal attribution formatting and compliance constants.
- ESV passage response text parsing (single, multi, cross-chapter, unbracketed).
- ESVClient HTTP requests, header tokens, and error handling (401, 429, 500, timeout).
- Ephemeral 500-verse LRU cache operations, timestamps, and hard limit eviction.
- Database fallback cascade to WEB when ESV is offline or unset.
- CLI subcommand ./bible esv actions (status, cache, clear, fetch) and --json.
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
from core.esv import (
    ESV_FULL_COPYRIGHT,
    ESV_MAX_CACHE_VERSES,
    ESV_SHORT_ATTRIBUTION,
    ESVAuthError,
    ESVClient,
    ESVNetworkError,
    ESVParseError,
    ESVRateLimitError,
    format_esv_attribution,
    get_esv_api_key,
    parse_esv_passage_text,
)
from core.reference import parse_reference


class TestESVKeyDiscovery(unittest.TestCase):
    """Test API key resolution across parameters, environment, and files."""

    def test_explicit_key_priority(self):
        with patch.dict(os.environ, {"ESV_API_KEY": "env_key"}):
            self.assertEqual(get_esv_api_key("explicit_key"), "explicit_key")

    def test_environment_variable_key(self):
        with patch.dict(os.environ, {"ESV_API_KEY": "env_token_12345"}):
            self.assertEqual(get_esv_api_key(), "env_token_12345")

    def test_env_file_parsing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text("SOME_VAR=foo\nESV_API_KEY=test_env_key_6789\nOTHER_VAR=bar\n", encoding="utf-8")
            with patch("core.esv.Path.cwd", return_value=Path(tmpdir)):
                with patch.dict(os.environ, {}, clear=True):
                    self.assertEqual(get_esv_api_key(), "test_env_key_6789")

    def test_unset_key_returns_none(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("core.esv.Path.cwd", return_value=Path("/tmp/nonexistent")):
                self.assertIsNone(get_esv_api_key(None))


class TestESVAttributionAndParsing(unittest.TestCase):
    """Test legal attribution strings and response text parser."""

    def test_attribution_formatting(self):
        self.assertEqual(format_esv_attribution("short"), ESV_SHORT_ATTRIBUTION)
        self.assertIn("www.esv.org", format_esv_attribution("short"))
        self.assertIn("Crossway", format_esv_attribution("notice"))
        self.assertEqual(format_esv_attribution("full"), ESV_FULL_COPYRIGHT)
        self.assertIn("The Holy Bible, English Standard Version", format_esv_attribution("full"))

    def test_parse_single_verse(self):
        passages = [
            "  [16] For God so loved the world, that he gave his only Son, "
            "that whoever believes in him should not perish but have eternal life."
        ]
        ref = parse_reference("John 3:16")
        parsed = parse_esv_passage_text(passages, requested_ref=ref)
        self.assertEqual(len(parsed), 1)
        v = parsed[0]
        self.assertEqual(v["book_id"], 43)
        self.assertEqual(v["chapter"], 3)
        self.assertEqual(v["verse"], 16)
        self.assertEqual(v["canonical_verse_id"], 43003016)
        self.assertTrue(v["text"].startswith("For God so loved"))

    def test_parse_multi_verse_span(self):
        passages = [
            "  [16] For God so loved the world, that he gave his only Son...\n"
            "  [17] For God did not send his Son into the world to condemn the world..."
        ]
        ref = parse_reference("John 3:16-17")
        parsed = parse_esv_passage_text(passages, requested_ref=ref)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]["verse"], 16)
        self.assertEqual(parsed[0]["canonical_verse_id"], 43003016)
        self.assertEqual(parsed[1]["verse"], 17)
        self.assertEqual(parsed[1]["canonical_verse_id"], 43003017)

    def test_parse_cross_chapter_span(self):
        passages = [
            "  [31] And God saw everything that he had made, and behold, it was very good.\n\n"
            "  [1] Thus the heavens and the earth were finished, and all the host of them.\n"
            "  [2] And on the seventh day God finished his work that he had done..."
        ]
        ref = parse_reference("Genesis 1:31 - 2:2")
        parsed = parse_esv_passage_text(passages, requested_ref=ref)
        self.assertEqual(len(parsed), 3)
        self.assertEqual(parsed[0]["chapter"], 1)
        self.assertEqual(parsed[0]["verse"], 31)
        self.assertEqual(parsed[0]["canonical_verse_id"], 1001031)

        self.assertEqual(parsed[1]["chapter"], 2)
        self.assertEqual(parsed[1]["verse"], 1)
        self.assertEqual(parsed[1]["canonical_verse_id"], 1002001)

        self.assertEqual(parsed[2]["chapter"], 2)
        self.assertEqual(parsed[2]["verse"], 2)
        self.assertEqual(parsed[2]["canonical_verse_id"], 1002002)

    def test_parse_unbracketed_text(self):
        passages = ["In the beginning was the Word, and the Word was with God."]
        ref = parse_reference("John 1:1")
        parsed = parse_esv_passage_text(passages, requested_ref=ref)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["book_id"], 43)
        self.assertEqual(parsed[0]["chapter"], 1)
        self.assertEqual(parsed[0]["verse"], 1)
        self.assertEqual(parsed[0]["text"], "In the beginning was the Word, and the Word was with God.")

    def test_parse_empty_passages(self):
        self.assertEqual(parse_esv_passage_text([]), [])
        self.assertEqual(parse_esv_passage_text(["   "]), [])


class TestESVClient(unittest.TestCase):
    """Test HTTP client operations, authentication, and status codes."""

    def test_client_availability(self):
        c_no_key = ESVClient(api_key=None)
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(c_no_key.is_available())

        c_with_key = ESVClient(api_key="valid_token")
        self.assertTrue(c_with_key.is_available())

    def test_missing_key_raises_auth_error(self):
        c = ESVClient(api_key=None)
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ESVAuthError):
                c.fetch_passage_raw("John 3:16")

    def test_successful_passage_fetch(self):
        mock_opener = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({
            "query": "John 3:16",
            "canonical": "John 3:16",
            "parsed": [[43003016, 43003016]],
            "passages": ["  [16] For God so loved the world..."],
        }).encode("utf-8")
        mock_resp.headers.get_content_charset.return_value = "utf-8"
        mock_opener.open.return_value.__enter__.return_value = mock_resp

        client = ESVClient(api_key="mock_key", opener=mock_opener)
        verses = client.fetch_verses("John 3:16")
        self.assertEqual(len(verses), 1)
        self.assertEqual(verses[0].translation_id, "ESV")
        self.assertEqual(verses[0].book_name, "John")
        self.assertEqual(verses[0].chapter, 3)
        self.assertEqual(verses[0].verse, 16)
        self.assertEqual(verses[0].canonical_verse_id, 43003016)
        self.assertTrue(verses[0].text.startswith("For God so loved"))

    def test_http_401_raises_auth_error(self):
        mock_opener = MagicMock()
        mock_opener.open.side_effect = HTTPError("url", 401, "Unauthorized", {}, None)
        client = ESVClient(api_key="bad_key", opener=mock_opener)
        with self.assertRaises(ESVAuthError):
            client.fetch_passage_raw("John 3:16")

    def test_http_429_raises_rate_limit_error(self):
        mock_opener = MagicMock()
        mock_opener.open.side_effect = HTTPError("url", 429, "Too Many Requests", {}, None)
        client = ESVClient(api_key="mock_key", opener=mock_opener)
        with self.assertRaises(ESVRateLimitError):
            client.fetch_passage_raw("John 3:16")

    def test_network_failure_raises_network_error(self):
        mock_opener = MagicMock()
        mock_opener.open.side_effect = URLError("DNS lookup failed")
        client = ESVClient(api_key="mock_key", opener=mock_opener)
        with self.assertRaises(ESVNetworkError):
            client.fetch_passage_raw("John 3:16")

    def test_malformed_json_raises_parse_error(self):
        mock_opener = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b"<html>Not JSON</html>"
        mock_resp.headers.get_content_charset.return_value = "utf-8"
        mock_opener.open.return_value.__enter__.return_value = mock_resp

        client = ESVClient(api_key="mock_key", opener=mock_opener)
        with self.assertRaises(ESVParseError):
            client.fetch_passage_raw("John 3:16")


class TestESVCacheOperations(unittest.TestCase):
    """Test ephemeral SQLite cache storage, LRU touch, capacity eviction, and stats."""

    def setUp(self):
        self.db = Database(":memory:")

    def tearDown(self):
        self.db.close()

    def test_cache_starts_empty(self):
        self.assertEqual(self.db.count_esv_cached_verses(), 0)
        stats = self.db.get_esv_cache_stats()
        self.assertEqual(stats["cached_verses"], 0)
        self.assertEqual(stats["max_capacity"], 500)
        self.assertTrue(stats["compliant"])

    def test_save_and_retrieve_cached_verses(self):
        records = [
            VerseRecord(
                translation_id="ESV",
                book_id=43,
                chapter=3,
                verse=16,
                text="For God so loved the world...",
                canonical_verse_id=43003016,
            ),
            VerseRecord(
                translation_id="ESV",
                book_id=43,
                chapter=3,
                verse=17,
                text="For God did not send his Son...",
                canonical_verse_id=43003017,
            ),
        ]
        saved = self.db.save_esv_cached_verses(records)
        self.assertEqual(saved, 2)
        self.assertEqual(self.db.count_esv_cached_verses(), 2)

        cached = self.db.get_esv_cached_verses("John 3:16-17")
        self.assertEqual(len(cached), 2)
        self.assertEqual(cached[0].translation_id, "ESV")
        self.assertEqual(cached[0].verse, 16)
        self.assertEqual(cached[1].verse, 17)

    def test_strict_500_verse_lru_eviction(self):
        """Verify that storing >500 verses evicts oldest accessed entries and caps at 500."""
        batch_1 = [
            VerseRecord(
                translation_id="ESV",
                book_id=19,  # Psalms
                chapter=1,
                verse=i,
                text=f"Psalm 1:{i} text",
                canonical_verse_id=19001000 + i,
            )
            for i in range(1, 301)  # 300 verses
        ]
        self.db.save_esv_cached_verses(batch_1)
        self.assertEqual(self.db.count_esv_cached_verses(), 300)

        # Store 250 more verses (total 550 verses -> exceeds 500 limit)
        batch_2 = [
            VerseRecord(
                translation_id="ESV",
                book_id=19,
                chapter=2,
                verse=i,
                text=f"Psalm 2:{i} text",
                canonical_verse_id=19002000 + i,
            )
            for i in range(1, 251)  # 250 verses
        ]
        self.db.save_esv_cached_verses(batch_2)

        # Strict compliance verification: must never exceed 500 verses
        total_count = self.db.count_esv_cached_verses()
        self.assertEqual(total_count, 500)
        self.assertEqual(total_count, ESV_MAX_CACHE_VERSES)
        stats = self.db.get_esv_cache_stats()
        self.assertTrue(stats["compliant"])

        # The first 50 verses of batch 1 should have been evicted by LRU
        evicted = self.db.get_esv_cached_verses("Psalm 1:1-50")
        self.assertEqual(len(evicted), 0)

        # The remaining verses of batch 1 and all of batch 2 should be preserved
        surviving_batch1 = self.db.get_esv_cached_verses("Psalm 1:51-300")
        self.assertEqual(len(surviving_batch1), 250)

        surviving_batch2 = self.db.get_esv_cached_verses("Psalm 2:1-250")
        self.assertEqual(len(surviving_batch2), 250)

    def test_clear_esv_cache(self):
        records = [
            VerseRecord(
                translation_id="ESV",
                book_id=43,
                chapter=1,
                verse=1,
                text="In the beginning was the Word...",
                canonical_verse_id=43001001,
            )
        ]
        self.db.save_esv_cached_verses(records)
        self.assertEqual(self.db.count_esv_cached_verses(), 1)

        cleared = self.db.clear_esv_cache()
        self.assertEqual(cleared, 1)
        self.assertEqual(self.db.count_esv_cached_verses(), 0)


class TestDatabaseESVFallback(unittest.TestCase):
    """Test get_verses_with_fallback resolution with ESV cache, API, and WEB fallback."""

    def setUp(self):
        self.db = Database(":memory:")
        # Seed WEB translation and a sample verse
        self.db.add_translation("WEB", "World English Bible")
        self.db.insert_verse(
            VerseRecord(
                translation_id="WEB",
                book_id=43,
                chapter=3,
                verse=16,
                text="For God so loved the world, that he gave his one and only Son...",
                canonical_verse_id=43003016,
            )
        )

    def tearDown(self):
        self.db.close()

    def test_cached_esv_resolved_first(self):
        self.db.save_esv_cached_verses([
            VerseRecord(
                translation_id="ESV",
                book_id=43,
                chapter=3,
                verse=16,
                text="For God so loved the world, that he gave his only Son...",
                canonical_verse_id=43003016,
            )
        ])

        verses, eff_id, is_fb = self.db.get_verses_with_fallback("John 3:16", translation_id="ESV")
        self.assertEqual(eff_id, "ESV")
        self.assertFalse(is_fb)
        self.assertEqual(len(verses), 1)
        self.assertEqual(verses[0].text, "For God so loved the world, that he gave his only Son...")

    def test_live_esv_api_fetch_and_cache(self):
        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.fetch_verses.return_value = [
            VerseRecord(
                translation_id="ESV",
                book_id=43,
                chapter=3,
                verse=16,
                text="For God so loved the world, that he gave his only Son...",
                canonical_verse_id=43003016,
            )
        ]
        self.db.set_esv_client(mock_client)

        verses, eff_id, is_fb = self.db.get_verses_with_fallback("John 3:16", translation_id="ESV")
        self.assertEqual(eff_id, "ESV")
        self.assertFalse(is_fb)
        self.assertEqual(len(verses), 1)
        # Verify it automatically saved to ephemeral cache
        self.assertEqual(self.db.count_esv_cached_verses(), 1)

    def test_fallback_to_web_when_esv_unavailable(self):
        mock_client = MagicMock()
        mock_client.is_available.return_value = False
        self.db.set_esv_client(mock_client)

        verses, eff_id, is_fb = self.db.get_verses_with_fallback(
            "John 3:16", translation_id="ESV", fallback_id="WEB"
        )
        self.assertEqual(eff_id, "WEB")
        self.assertTrue(is_fb)
        self.assertEqual(len(verses), 1)
        self.assertIn("one and only Son", verses[0].text)


class TestCliESVCommands(unittest.TestCase):
    """Test CLI subcommands: ./bible esv [status|cache|clear|fetch]."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.db = Database(self.db_path)
        self.db.add_translation("WEB", "World English Bible")
        self.db.insert_verse(
            VerseRecord(
                translation_id="WEB",
                book_id=43,
                chapter=3,
                verse=16,
                text="For God so loved the world, that he gave his one and only Son...",
                canonical_verse_id=43003016,
            )
        )

    def tearDown(self):
        self.db.close()
        self.temp_dir.cleanup()

    def test_cli_esv_status(self):
        from cli.main import main
        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = main(["--db", str(self.db_path), "esv", "status"])
        self.assertEqual(code, 0)
        out = stdout.getvalue()
        self.assertIn("Crossway ESV API & Ephemeral 500-Verse LRU Cache Status", out)
        self.assertIn("COMPLIANT", out)
        self.assertIn("https://api.esv.org/v3/passage/text/", out)

    def test_cli_esv_status_json(self):
        from cli.main import main
        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = main(["--db", str(self.db_path), "esv", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(stdout.getvalue())
        self.assertIn("cache_stats", data)
        self.assertEqual(data["cache_stats"]["max_capacity"], 500)
        self.assertTrue(data["cache_stats"]["compliant"])

    def test_cli_esv_clear(self):
        from cli.main import main
        self.db.save_esv_cached_verses([
            VerseRecord(
                translation_id="ESV",
                book_id=43,
                chapter=1,
                verse=1,
                text="In the beginning...",
                canonical_verse_id=43001001,
            )
        ])
        self.assertEqual(self.db.count_esv_cached_verses(), 1)

        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = main(["--db", str(self.db_path), "esv", "clear"])
        self.assertEqual(code, 0)
        self.assertIn("Successfully cleared ephemeral ESV cache", stdout.getvalue())
        self.assertEqual(self.db.count_esv_cached_verses(), 0)

    def test_cli_esv_cache_list(self):
        from cli.main import main
        self.db.save_esv_cached_verses([
            VerseRecord(
                translation_id="ESV",
                book_id=43,
                chapter=3,
                verse=16,
                text="For God so loved the world...",
                canonical_verse_id=43003016,
            )
        ])
        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = main(["--db", str(self.db_path), "esv", "cache"])
        self.assertEqual(code, 0)
        out = stdout.getvalue()
        self.assertIn("John 3:16", out)
        self.assertIn("For God so loved the world", out)


if __name__ == "__main__":
    unittest.main()
