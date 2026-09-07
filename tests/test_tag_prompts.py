"""Hermetic Unit & Integration Tests for Scripture Tagging Prompts & Batch LLM Generator.

Tests:
- TGC hermeneutical system prompt and taxonomy context formatting.
- Prompt generation for single passages, batch requests, and custom taxonomies.
- Resilient JSON payload extraction and schema validation.
- Response parsing, tag normalization, confidence clamping, and error handling.
- Standalone CLI tool (`tools/tag_generator.py`) subcommands: prompt, batch, apply, generate.
- Integration with `./bible tag` and interactive shell `/tag prompt`.
- Hermetic mock Gemini API calls via standard library `urllib.request`.
"""

import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

from core.db import Database, VerseRecord
from core.reference import Reference, parse_reference
from core.tag_prompts import (
    GeneratedTag,
    TaggingResult,
    extract_json_payload,
    format_prompt_for_gemini_api,
    format_taxonomy_for_prompt,
    generate_batch_tagging_prompts,
    generate_tagging_prompt,
    get_tgc_hermeneutical_system_prompt,
    normalize_category,
    normalize_tag_name,
    parse_tagging_response,
)
from core.tags import CANONICAL_TAXONOMY, TagCategory, TaggingService
from cli.main import main, build_parser
from cli.shell import BibleShell
from tools.tag_generator import (
    build_parser as build_tool_parser,
    call_gemini_api,
    cmd_apply,
    cmd_batch,
    cmd_generate,
    cmd_prompt,
    fetch_passage_text,
)


def create_mock_db(db_path: str = ":memory:") -> Database:
    """Create an in-memory database populated with test verses and schema."""
    db = Database(db_path)
    with db.conn:
        db.conn.execute(
            """
            INSERT OR REPLACE INTO translations (id, name, language, is_public_domain)
            VALUES ('WEB', 'World English Bible', 'en', 1)
            """
        )

    verses = [
        # John 3:16-17
        VerseRecord(
            translation_id="WEB",
            book_id=43,
            chapter=3,
            verse=16,
            text="For God so loved the world, that he gave his one and only Son, that whoever believes in him should not perish, but have eternal life.",
        ),
        VerseRecord(
            translation_id="WEB",
            book_id=43,
            chapter=3,
            verse=17,
            text="For God didn't send his Son into the world to judge the world, but that the world should be saved through him.",
        ),
        # Romans 8:1-3
        VerseRecord(
            translation_id="WEB",
            book_id=45,
            chapter=8,
            verse=1,
            text="There is therefore now no condemnation to those who are in Christ Jesus, who don't walk according to the flesh, but according to the Spirit.",
        ),
        VerseRecord(
            translation_id="WEB",
            book_id=45,
            chapter=8,
            verse=2,
            text="For the law of the Spirit of life in Christ Jesus made me free from the law of sin and of death.",
        ),
        VerseRecord(
            translation_id="WEB",
            book_id=45,
            chapter=8,
            verse=3,
            text="For what the law couldn't do, in that it was weak through the flesh, God did: sending his own Son...",
        ),
    ]
    db.insert_verses(verses)
    return db


class TestTagPromptsDomain(unittest.TestCase):
    """Test core prompt generation, taxonomy context, and normalization functions."""

    def test_tgc_hermeneutical_system_prompt(self):
        sys_prompt = get_tgc_hermeneutical_system_prompt()
        self.assertIn("DUAL-HORIZON HERMENEUTICS", sys_prompt)
        self.assertIn("CHRIST-CENTERED TELEOLOGY", sys_prompt)
        self.assertIn("ANTI-MORALISTIC READING", sys_prompt)
        self.assertIn("The Gospel Coalition", sys_prompt)

    def test_format_taxonomy_for_prompt(self):
        tax = format_taxonomy_for_prompt()
        self.assertIn("Creation", tax)
        self.assertIn("Justification", tax)
        self.assertIn("Redemptive-Historical Storyline Motifs", tax)

        # Filter categories
        tax_theol = format_taxonomy_for_prompt(categories=["theological"])
        self.assertIn("Justification", tax_theol)
        self.assertNotIn("Creation (`historical`)", tax_theol)

        # Custom tags
        custom = [("Shepherd", "thematic", "God as shepherd of His sheep")]
        tax_custom = format_taxonomy_for_prompt(custom_tags=custom)
        self.assertIn("Shepherd", tax_custom)
        self.assertIn("God as shepherd of His sheep", tax_custom)

    def test_generate_tagging_prompt(self):
        prompt = generate_tagging_prompt(
            reference="Romans 8:1-3",
            passage_text="There is therefore now no condemnation...",
            translation_id="WEB",
            max_tags=4,
        )
        self.assertIn("Romans 8:1-3", prompt)
        self.assertIn("WEB", prompt)
        self.assertIn("There is therefore now no condemnation", prompt)
        self.assertIn("Respond ONLY with valid JSON", prompt)
        self.assertIn('"reference": "Romans 8:1-3"', prompt)

    def test_generate_batch_tagging_prompts(self):
        passages = [
            ("John 3:16", "For God so loved..."),
            ("Romans 8:1", "There is therefore now no condemnation..."),
        ]
        batch = generate_batch_tagging_prompts(passages)
        self.assertEqual(len(batch), 2)
        self.assertEqual(batch[0]["id"], "tag_request_0001")
        self.assertEqual(batch[0]["reference"], "John 3:16")
        self.assertIn("For God so loved", batch[0]["prompt"])
        self.assertEqual(batch[1]["reference"], "Romans 8:1")

    def test_format_prompt_for_gemini_api(self):
        payload = format_prompt_for_gemini_api("Analyze John 3:16")
        self.assertIn("system_instruction", payload)
        self.assertIn("contents", payload)
        self.assertIn("generationConfig", payload)
        self.assertEqual(payload["generationConfig"]["response_mime_type"], "application/json")


class TestTagResponseParser(unittest.TestCase):
    """Test response extraction, JSON parsing, tag normalization, and error recovery."""

    def test_extract_json_payload(self):
        # Code fence with json
        text1 = "Here is the result:\n```json\n{\"reference\": \"John 3:16\", \"tags\": []}\n```\nHope this helps!"
        self.assertEqual(extract_json_payload(text1), '{"reference": "John 3:16", "tags": []}')

        # Code fence without json
        text2 = "```\n[{\"name\": \"Love\"}]\n```"
        self.assertEqual(extract_json_payload(text2), '[{"name": "Love"}]')

        # Raw JSON
        text3 = '{"name": "Love"}'
        self.assertEqual(extract_json_payload(text3), '{"name": "Love"}')

    def test_normalize_tag_name(self):
        # Canonical match
        self.assertEqual(normalize_tag_name("justification"), "Justification")
        self.assertEqual(normalize_tag_name("holy spirit"), "Holy Spirit")
        self.assertEqual(normalize_tag_name("sovereign grace"), "Sovereign Grace")
        # Novel tag Title Case
        self.assertEqual(normalize_tag_name("messianic hope"), "Messianic Hope")

    def test_normalize_category(self):
        self.assertEqual(normalize_category("THEOLOGICAL"), TagCategory.THEOLOGICAL)
        self.assertEqual(normalize_category("doctrinal"), TagCategory.THEOLOGICAL)
        self.assertEqual(normalize_category("history"), TagCategory.HISTORICAL)
        self.assertEqual(normalize_category("eschatology"), TagCategory.PROPHECY)
        self.assertEqual(normalize_category("shadow"), TagCategory.TYPOLOGY)
        self.assertEqual(normalize_category("unknown"), TagCategory.THEMATIC)

    def test_parse_tagging_response_object_format(self):
        raw = json.dumps(
            {
                "reference": "Romans 8:1-3",
                "tags": [
                    {
                        "name": "Justification",
                        "category": "theological",
                        "confidence": 0.98,
                        "starred": True,
                        "notes": "No condemnation in Christ.",
                        "sub_span": "Romans 8:1",
                    },
                    {
                        "name": "Holy Spirit",
                        "category": "theological",
                        "confidence": 0.92,
                        "starred": False,
                        "notes": "Law of Spirit of life.",
                    },
                ],
            }
        )
        res = parse_tagging_response(raw)
        self.assertTrue(res.is_success)
        self.assertEqual(res.reference, "Romans 8:1-3")
        self.assertEqual(len(res.tags), 2)
        self.assertEqual(res.tags[0].name, "Justification")
        self.assertTrue(res.tags[0].starred)
        self.assertEqual(res.tags[0].sub_span, "Romans 8:1")
        self.assertEqual(res.tags[1].name, "Holy Spirit")
        self.assertFalse(res.tags[1].starred)

    def test_parse_tagging_response_array_format(self):
        raw = json.dumps(
            [
                {"name": "Love", "category": "thematic", "confidence": 0.99},
                {"name": "Atonement", "category": "theological", "confidence": 0.95},
            ]
        )
        res = parse_tagging_response(raw, default_reference="John 3:16")
        self.assertTrue(res.is_success)
        self.assertEqual(res.reference, "John 3:16")
        self.assertEqual(len(res.tags), 2)
        # Verify at least one tag is starred automatically
        self.assertTrue(res.tags[0].starred)

    def test_parse_tagging_response_confidence_clamping(self):
        raw = json.dumps(
            {
                "reference": "John 3:16",
                "tags": [
                    {"name": "Love", "confidence": 1.5},
                    {"name": "Faith", "confidence": -0.5},
                ],
            }
        )
        res = parse_tagging_response(raw)
        self.assertTrue(res.is_success)
        self.assertEqual(res.tags[0].confidence, 1.0)
        self.assertEqual(res.tags[1].confidence, 0.0)

    def test_parse_tagging_response_malformed(self):
        res = parse_tagging_response("This is completely not JSON at all.")
        self.assertFalse(res.is_success)
        self.assertIn("Invalid JSON", res.error)

    def test_parse_tagging_response_empty(self):
        res = parse_tagging_response("")
        self.assertFalse(res.is_success)
        self.assertIn("Empty", res.error)


class TestTagGeneratorTool(unittest.TestCase):
    """Test `tools/tag_generator.py` subcommands and helpers."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_bible.db"
        self.db = create_mock_db(str(self.db_path))

    def tearDown(self):
        self.db.close()
        self.temp_dir.cleanup()

    def test_fetch_passage_text(self):
        ref, text = fetch_passage_text(self.db, "John 3:16")
        self.assertEqual(ref.format(), "John 3:16")
        self.assertIn("For God so loved the world", text)

    def test_fetch_passage_text_invalid(self):
        with self.assertRaises(ValueError):
            fetch_passage_text(self.db, "Revelation 22:21")

    def test_cmd_prompt_stdout(self):
        parser = build_tool_parser()
        args = parser.parse_args(["prompt", "John 3:16", "--db", str(self.db_path)])
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = cmd_prompt(args)
        self.assertEqual(code, 0)
        output = buf.getvalue()
        self.assertIn("Citation**: John 3:16", output)
        self.assertIn("For God so loved", output)

    def test_cmd_prompt_to_file_and_gemini_format(self):
        out_file = Path(self.temp_dir.name) / "prompt.json"
        parser = build_tool_parser()
        args = parser.parse_args(
            ["prompt", "Romans 8:1-2", "--db", str(self.db_path), "--format", "gemini", "-o", str(out_file)]
        )
        with patch("sys.stdout", io.StringIO()):
            code = cmd_prompt(args)
        self.assertEqual(code, 0)
        self.assertTrue(out_file.exists())
        data = json.loads(out_file.read_text(encoding="utf-8"))
        self.assertIn("system_instruction", data)
        self.assertIn("contents", data)

    def test_cmd_batch(self):
        out_file = Path(self.temp_dir.name) / "batch.jsonl"
        parser = build_tool_parser()
        args = parser.parse_args(
            ["batch", "--refs", "John 3:16, Romans 8:1", "--db", str(self.db_path), "-o", str(out_file)]
        )
        with patch("sys.stdout", io.StringIO()):
            code = cmd_batch(args)
        self.assertEqual(code, 0)
        self.assertTrue(out_file.exists())
        lines = out_file.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 2)
        row1 = json.loads(lines[0])
        self.assertEqual(row1["reference"], "John 3:16")
        row2 = json.loads(lines[1])
        self.assertEqual(row2["reference"], "Romans 8:1")

    def test_cmd_apply_dry_run_and_write(self):
        # Create a mock response JSON file
        resp_file = Path(self.temp_dir.name) / "response.json"
        payload = {
            "reference": "Romans 8:1-2",
            "tags": [
                {
                    "name": "Justification",
                    "category": "theological",
                    "confidence": 0.98,
                    "starred": True,
                    "notes": "No condemnation.",
                },
                {
                    "name": "Holy Spirit",
                    "category": "theological",
                    "confidence": 0.95,
                    "starred": False,
                    "notes": "Spirit of life.",
                },
            ],
        }
        resp_file.write_text(json.dumps(payload), encoding="utf-8")

        # 1. Dry run
        parser = build_tool_parser()
        args_dry = parser.parse_args(
            ["apply", str(resp_file), "--db", str(self.db_path), "--dry-run"]
        )
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code_dry = cmd_apply(args_dry)
        self.assertEqual(code_dry, 0)
        self.assertIn("Would apply 2 tag(s)", buf.getvalue())

        # Verify DB is still empty of these tags
        svc = TaggingService(self.db)
        self.assertEqual(len(svc.get_tags_for_passage("Romans 8:1")), 0)

        # 2. Actual write
        args_write = parser.parse_args(
            ["apply", str(resp_file), "--db", str(self.db_path)]
        )
        buf2 = io.StringIO()
        with patch("sys.stdout", buf2):
            code_write = cmd_apply(args_write)
        self.assertEqual(code_write, 0)
        self.assertIn("Successfully applied 2 tag(s)", buf2.getvalue())

        # Verify DB has stored tags
        tags = svc.get_tags_for_passage("Romans 8:1")
        self.assertEqual(len(tags), 2)
        tag_names = {t.tag_name for t in tags}
        self.assertIn("Justification", tag_names)
        self.assertIn("Holy Spirit", tag_names)

    def test_call_gemini_api_mock(self):
        mock_response_data = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": '{"reference": "John 3:16", "tags": [{"name": "Love", "starred": true}]}'
                            }
                        ]
                    }
                }
            ]
        }
        mock_res_bytes = json.dumps(mock_response_data).encode("utf-8")

        mock_context = MagicMock()
        mock_context.read.return_value = mock_res_bytes
        mock_context.__enter__.return_value = mock_context

        with patch("urllib.request.urlopen", return_value=mock_context):
            resp_text = call_gemini_api(prompt="test prompt", api_key="fake-key-12345")
            self.assertIn("John 3:16", resp_text)
            self.assertIn("Love", resp_text)

    def test_cmd_generate_mock(self):
        mock_llm_json = json.dumps(
            {
                "reference": "John 3:16",
                "tags": [
                    {
                        "name": "Love",
                        "category": "thematic",
                        "confidence": 0.99,
                        "starred": True,
                        "notes": "God so loved the world.",
                    }
                ],
            }
        )

        parser = build_tool_parser()
        args = parser.parse_args(
            ["generate", "John 3:16", "--api-key", "test-key", "--db", str(self.db_path)]
        )

        with patch("tools.tag_generator.call_gemini_api", return_value=mock_llm_json):
            buf = io.StringIO()
            with patch("sys.stdout", buf):
                code = cmd_generate(args)
            self.assertEqual(code, 0)
            self.assertIn("Successfully stored tags for John 3:16", buf.getvalue())

        # Verify DB
        svc = TaggingService(self.db)
        tags = svc.get_tags_for_passage("John 3:16")
        self.assertEqual(len(tags), 1)
        self.assertEqual(tags[0].tag_name, "Love")

    def test_cmd_generate_missing_api_key(self):
        parser = build_tool_parser()
        args = parser.parse_args(["generate", "John 3:16", "--db", str(self.db_path)])

        with patch.dict(os.environ, {}, clear=True):
            buf_err = io.StringIO()
            with patch("sys.stderr", buf_err):
                code = cmd_generate(args)
            self.assertEqual(code, 1)
            self.assertIn("GEMINI_API_KEY environment variable or --api-key argument is required", buf_err.getvalue())


class TestCLIAndShellIntegration(unittest.TestCase):
    """Test CLI `./bible tag` commands and interactive REPL shell `/tag`."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_bible.db"
        self.db = create_mock_db(str(self.db_path))

    def tearDown(self):
        self.db.close()
        self.temp_dir.cleanup()

    def test_cli_tag_prompt(self):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = main(["--db", str(self.db_path), "tag", "prompt", "John 3:16"])
        self.assertEqual(code, 0)
        self.assertIn("Citation**: John 3:16", buf.getvalue())

    def test_shell_tag_prompt(self):
        shell_out = io.StringIO()
        with BibleShell(db_path=self.db_path, stdout=shell_out) as shell:
            shell.onecmd("/tag prompt John 3:16")
        output = shell_out.getvalue()
        self.assertIn("Citation**: John 3:16", output)
        self.assertIn("For God so loved the world", output)


if __name__ == "__main__":
    unittest.main()
