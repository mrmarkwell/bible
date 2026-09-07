"""Hermetic unit tests for Bible Engine CLI.

Zero external dependencies (Python 3 standard library only per ADR-003).
"""

import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from cli.main import (
    build_parser,
    format_aligned_comparison,
    format_search_results,
    format_search_snippet,
    format_verse_lines,
    highlight_search_tokens,
    main,
    parse_translation_ids,
)
from core.db import Database, SearchResult, VerseRecord
from core.reference import parse_reference


class TestCliFormatting(unittest.TestCase):
    """Test verse line formatting, search formatting, and translation parsing functions."""

    def test_parse_translation_ids(self):
        self.assertEqual(parse_translation_ids(None), ["WEB"])
        self.assertEqual(parse_translation_ids(""), ["WEB"])
        self.assertEqual(parse_translation_ids("WEB,KJV"), ["WEB", "KJV"])
        self.assertEqual(parse_translation_ids("web, kjv, esv"), ["WEB", "KJV", "ESV"])
        self.assertEqual(parse_translation_ids(["WEB, ESV", "kjv", "web"]), ["WEB", "ESV", "KJV"])

    def test_format_single_verse(self):
        v = VerseRecord(
            translation_id="WEB",
            book_id=43,
            book_name="John",
            chapter=3,
            verse=16,
            text="For God so loved the world...",
            canonical_verse_id=43003016,
        )
        out = format_verse_lines([v], show_verse_numbers=True, show_header=True)
        self.assertIn("=== John 3:16 (WEB) ===", out)
        self.assertIn("[16] For God so loved the world...", out)

    def test_format_verse_lines_with_fallback(self):
        v = VerseRecord(
            translation_id="WEB",
            book_id=43,
            book_name="John",
            chapter=3,
            verse=16,
            text="For God so loved the world...",
            canonical_verse_id=43003016,
        )
        out = format_verse_lines([v], show_verse_numbers=True, show_header=True, fallback_for="ESV")
        self.assertIn("=== John 3:16 (WEB [fallback for ESV]) ===", out)

    def test_format_aligned_comparison(self):
        v_web = VerseRecord(
            translation_id="WEB",
            book_id=43,
            book_name="John",
            chapter=1,
            verse=1,
            text="In the beginning was the Word...",
            canonical_verse_id=43001001,
        )
        v_kjv = VerseRecord(
            translation_id="KJV",
            book_id=43,
            book_name="John",
            chapter=1,
            verse=1,
            text="In the beginning was the Word...",
            canonical_verse_id=43001001,
        )
        comp_data = {
            "WEB": ([v_web], "WEB", False),
            "ESV": ([v_kjv], "KJV", True),
        }
        ref = parse_reference("John 1:1")
        out = format_aligned_comparison(ref, comp_data, show_header=True)
        self.assertIn("=== Compare: John 1:1 (WEB, KJV* (fallback for ESV)) ===", out)
        self.assertIn("--- John 1:1 ---", out)
        self.assertIn("[WEB]    In the beginning", out)
        self.assertIn("[KJV*]   In the beginning", out)

    def test_format_multi_verse_same_chapter(self):
        v1 = VerseRecord(
            translation_id="WEB",
            book_id=45,
            book_name="Romans",
            chapter=8,
            verse=28,
            text="And we know...",
            canonical_verse_id=45008028,
        )
        v2 = VerseRecord(
            translation_id="WEB",
            book_id=45,
            book_name="Romans",
            chapter=8,
            verse=29,
            text="For those whom he foreknew...",
            canonical_verse_id=45008029,
        )
        out = format_verse_lines([v1, v2], show_verse_numbers=True, show_header=True)
        self.assertIn("=== Romans 8:28-29 (WEB) ===", out)
        self.assertIn("[28] And we know...", out)
        self.assertIn("[29] For those whom he foreknew...", out)

    def test_format_multi_verse_cross_chapter(self):
        v1 = VerseRecord(
            translation_id="WEB",
            book_id=1,
            book_name="Genesis",
            chapter=1,
            verse=31,
            text="God saw everything...",
            canonical_verse_id=1001031,
        )
        v2 = VerseRecord(
            translation_id="WEB",
            book_id=1,
            book_name="Genesis",
            chapter=2,
            verse=1,
            text="The heavens and earth were finished...",
            canonical_verse_id=1002001,
        )
        out = format_verse_lines([v1, v2], show_verse_numbers=True, show_header=True)
        self.assertIn("=== Genesis 1:31 - 2:1 (WEB) ===", out)

    def test_format_no_header_no_numbers(self):
        v = VerseRecord(
            translation_id="WEB",
            book_id=43,
            book_name="John",
            chapter=11,
            verse=35,
            text="Jesus wept.",
            canonical_verse_id=43011035,
        )
        out = format_verse_lines([v], show_verse_numbers=False, show_header=False)
        self.assertNotIn("===", out)
        self.assertNotIn("[35]", out)
        self.assertEqual(out, "Jesus wept.")

    def test_format_empty_list(self):
        out = format_verse_lines([])
        self.assertEqual(out, "")

    def test_highlight_search_tokens(self):
        text = "You are the light of the world."
        # With color
        colored = highlight_search_tokens(text, "light world", color=True)
        self.assertIn("\033[1;33mlight\033[0m", colored)
        self.assertIn("\033[1;33mworld\033[0m", colored)

        # Without color
        uncolored = highlight_search_tokens(text, "light world", color=False)
        self.assertEqual(uncolored, text)

        # Exact phrase
        exact_colored = highlight_search_tokens(text, "light of the world", color=True, exact=True)
        self.assertIn("\033[1;33mlight of the world\033[0m", exact_colored)

    def test_format_search_snippet(self):
        snippet = "You are the <b>light</b> of the <b>world</b>."
        # With color
        colored = format_search_snippet(snippet, color=True)
        self.assertIn("\033[1;33mlight\033[0m", colored)
        self.assertNotIn("<b>", colored)

        # Without color
        uncolored = format_search_snippet(snippet, color=False)
        self.assertEqual(uncolored, "You are the [light] of the [world].")

    def test_format_search_results(self):
        sr = SearchResult(
            verse_id=1,
            translation_id="WEB",
            book_name="John",
            osis_ref="John.3.16",
            chapter=3,
            verse=16,
            text="For God so loved the world...",
            snippet="For God so loved the <b>world</b>...",
            rank=-5.0,
        )
        # Standard formatted output
        out = format_search_results([sr], "world", total_count=1, translation_label="WEB", color=False)
        self.assertIn('=== Scripture Search: "world" (WEB) ===', out)
        self.assertIn("Found 1 matching verse:", out)
        self.assertIn("1. John 3:16 (WEB)", out)
        self.assertIn("For God so loved the world...", out)

        # Snippet output
        out_snippet = format_search_results(
            [sr], "world", total_count=1, translation_label="WEB", show_snippets=True, color=False
        )
        self.assertIn("[world]", out_snippet)

        # Zero results output
        out_empty = format_search_results([], "nonexistent", total_count=0, translation_label="WEB", color=False)
        self.assertIn("No matching verses found.", out_empty)


class TestCliExecution(unittest.TestCase):
    """Test CLI execution and command-line parsing hermetically."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.db_path = Path(cls.temp_dir.name) / "test_bible.db"
        cls.db = Database(cls.db_path, auto_init=True)
        cls.db.add_translation("WEB", "World English Bible")
        cls.db.add_translation("KJV", "King James Version")
        cls.db.insert_verses(
            [
                VerseRecord(
                    translation_id="WEB",
                    book_id=1,
                    chapter=1,
                    verse=1,
                    text="In the beginning, God created the heavens and the earth.",
                ),
                VerseRecord(
                    translation_id="WEB",
                    book_id=1,
                    chapter=1,
                    verse=3,
                    text="God said, 'Let there be light,' and there was light.",
                ),
                VerseRecord(
                    translation_id="WEB",
                    book_id=43,
                    chapter=3,
                    verse=16,
                    text="For God so loved the world, that he gave his one and only Son.",
                ),
                VerseRecord(
                    translation_id="WEB",
                    book_id=43,
                    chapter=3,
                    verse=17,
                    text="For God didn't send his Son into the world to judge the world.",
                ),
                VerseRecord(
                    translation_id="KJV",
                    book_id=43,
                    chapter=3,
                    verse=16,
                    text="For God so loved the world, that he gave his only begotten Son.",
                ),
            ]
            + [
                VerseRecord(
                    translation_id="WEB",
                    book_id=58,
                    chapter=11,
                    verse=v_num,
                    text=f"Hebrews chapter 11 verse {v_num} text describing faith, redemption, and perseverance.",
                )
                for v_num in range(1, 13)
            ]
        )

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        cls.temp_dir.cleanup()

    def test_cli_get_single_verse(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main(["--db", str(self.db_path), "get", "John 3:16"])
        self.assertEqual(code, 0)
        self.assertIn("=== John 3:16 (WEB) ===", stdout.getvalue())
        self.assertIn("[16] For God so loved the world", stdout.getvalue())

    def test_cli_get_verse_span(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main(["--db", str(self.db_path), "get", "John 3:16-17"])
        self.assertEqual(code, 0)
        self.assertIn("=== John 3:16-17 (WEB) ===", stdout.getvalue())
        self.assertIn("[16] For God so loved the world", stdout.getvalue())
        self.assertIn("[17] For God didn't send his Son", stdout.getvalue())

    def test_cli_get_no_numbers_and_no_header(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main(
                [
                    "--db",
                    str(self.db_path),
                    "get",
                    "John 3:16",
                    "--no-numbers",
                    "--no-header",
                ]
            )
        self.assertEqual(code, 0)
        self.assertNotIn("===", stdout.getvalue())
        self.assertNotIn("[16]", stdout.getvalue())
        self.assertIn("For God so loved the world", stdout.getvalue().strip())

    def test_cli_missing_db(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        fake_path = Path(self.temp_dir.name) / "nonexistent.db"
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main(["--db", str(fake_path), "get", "John 3:16"])
        self.assertEqual(code, 1)
        self.assertIn("Error: Database file not found", stderr.getvalue())

    def test_cli_invalid_reference(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main(["--db", str(self.db_path), "get", "NonexistentBook 99:99"])
        self.assertEqual(code, 1)
        self.assertIn("Error parsing reference", stderr.getvalue())

    def test_cli_not_found_verse(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main(["--db", str(self.db_path), "get", "Romans 8:28"])
        self.assertEqual(code, 1)
        self.assertIn("No verses found for reference", stderr.getvalue())

    def test_cli_no_subcommand(self):
        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = main([])
        self.assertEqual(code, 0)
        self.assertIn("usage: bible", stdout.getvalue())

    @patch("tools.doctor.run_all_checks", return_value=(0, []))
    def test_cli_doctor(self, mock_doctor):
        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = main(["doctor"])
        self.assertEqual(code, 0)
        self.assertTrue(mock_doctor.called)
        self.assertFalse(mock_doctor.call_args.kwargs.get("fast", False))

    @patch("tools.doctor.run_all_checks", return_value=(0, []))
    def test_cli_doctor_fast(self, mock_doctor):
        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = main(["doctor", "--fast"])
        self.assertEqual(code, 0)
        self.assertTrue(mock_doctor.called)
        self.assertTrue(mock_doctor.call_args.kwargs.get("fast", False))

    @patch("tools.doctor.install_hooks", return_value=(True, "Hooks installed successfully"))
    def test_cli_doctor_install_hooks(self, mock_install):
        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = main(["doctor", "--install-hooks"])
        self.assertEqual(code, 0)
        self.assertTrue(mock_install.called)
        self.assertIn("Hooks installed", stdout.getvalue())

    @patch("tools.doctor.uninstall_hooks", return_value=(True, "Hooks uninstalled successfully"))
    def test_cli_doctor_uninstall_hooks(self, mock_uninstall):
        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = main(["doctor", "--uninstall-hooks"])
        self.assertEqual(code, 0)
        self.assertTrue(mock_uninstall.called)
        self.assertIn("Hooks uninstalled", stdout.getvalue())

    @patch("tools.doctor.check_git_hooks")
    def test_cli_doctor_check_hooks(self, mock_check):
        from tools.doctor import CheckResult
        mock_check.return_value = CheckResult("Git Hook Safeguards", True, "Hooks active", 0.001)
        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = main(["doctor", "--check-hooks"])
        self.assertEqual(code, 0)
        self.assertTrue(mock_check.called)
        self.assertIn("Git Hook Safeguards", stdout.getvalue())

    @patch("tools.executive_summary.generate_summary")
    def test_cli_summary(self, mock_summary):
        from tools.executive_summary import ExecutiveReport, RoadmapStats
        mock_summary.return_value = ExecutiveReport(
            start_run=1,
            end_run=5,
            run_count=5,
            runs=[],
            roadmap_stats=RoadmapStats(total_tasks=10, completed_tasks=5),
            avg_velocity_tasks_per_run=1.0,
            estimated_runs_remaining=5,
            system_health_status="EXCELLENT",
            system_health_details=["Zero dependencies OK"],
        )
        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = main(["summary", "--window", "5"])
        self.assertEqual(code, 0)
        self.assertIn("Executive Summary & Trajectory Briefing", stdout.getvalue())
        self.assertTrue(mock_summary.called)

    def test_cli_get_multi_translation(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main(["--db", str(self.db_path), "get", "John 3:16", "--version", "WEB,KJV"])
        self.assertEqual(code, 0)
        out = stdout.getvalue()
        self.assertIn("=== John 3:16 (WEB) ===", out)
        self.assertIn("one and only Son", out)
        self.assertIn("=== John 3:16 (KJV) ===", out)
        self.assertIn("only begotten Son", out)

    def test_cli_get_fallback_notice_and_output(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main(["--db", str(self.db_path), "get", "John 3:16", "--version", "ESV"])
        self.assertEqual(code, 0)
        self.assertIn("Notice: Translation 'ESV' not available; falling back to 'WEB'.", stderr.getvalue())
        self.assertIn("=== John 3:16 (WEB [fallback for ESV]) ===", stdout.getvalue())
        self.assertIn("one and only Son", stdout.getvalue())

    def test_cli_get_strict_mode_prevents_fallback(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main(["--db", str(self.db_path), "get", "John 3:16", "--version", "ESV", "--strict"])
        self.assertEqual(code, 1)
        self.assertIn("No verses found for reference 'John 3:16' in translation 'ESV'.", stderr.getvalue())

    def test_cli_compare_default_aligned(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main(["--db", str(self.db_path), "compare", "John 3:16"])
        self.assertEqual(code, 0)
        out = stdout.getvalue()
        self.assertIn("=== Compare: John 3:16", out)
        self.assertIn("--- John 3:16 ---", out)
        self.assertIn("[KJV]", out)
        self.assertIn("only begotten Son", out)
        self.assertIn("[WEB]", out)
        self.assertIn("one and only Son", out)

    def test_cli_compare_stacked_mode(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main(["--db", str(self.db_path), "compare", "John 3:16", "--mode", "stacked"])
        self.assertEqual(code, 0)
        out = stdout.getvalue()
        self.assertIn("=== John 3:16 (KJV) ===", out)
        self.assertIn("=== John 3:16 (WEB) ===", out)

    def test_cli_compare_with_fallback(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main(["--db", str(self.db_path), "compare", "John 3:16", "--versions", "ESV,WEB"])
        self.assertEqual(code, 0)
        self.assertIn("Notice: Translation 'ESV' not available; falling back to 'WEB'.", stderr.getvalue())
        out = stdout.getvalue()
        self.assertIn("=== Compare: John 3:16 (WEB* (fallback for ESV), WEB) ===", out)
        self.assertIn("[WEB*]", out)
        self.assertIn("[WEB]", out)

    def test_cli_compare_strict_failure(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main(["--db", str(self.db_path), "compare", "John 3:16", "--versions", "ESV,WEB", "--strict"])
        self.assertEqual(code, 1)
        self.assertIn("Error: No verses found for reference 'John 3:16' in translation 'ESV'.", stderr.getvalue())

    def test_cli_translations(self):
        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = main(["--db", str(self.db_path), "translations"])
        self.assertEqual(code, 0)
        out = stdout.getvalue()
        self.assertIn("Installed Scripture Translations:", out)
        self.assertIn("[WEB] World English Bible", out)
        self.assertIn("[KJV] King James Version", out)

    def test_cli_versions_alias(self):
        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = main(["--db", str(self.db_path), "versions"])
        self.assertEqual(code, 0)
        out = stdout.getvalue()
        self.assertIn("Installed Scripture Translations:", out)
        self.assertIn("[WEB] World English Bible", out)

    def test_cli_search_basic(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main(["--db", str(self.db_path), "search", "light"])
        self.assertEqual(code, 0)
        out = stdout.getvalue()
        self.assertIn('=== Scripture Search: "light" (WEB) ===', out)
        self.assertIn("Genesis 1:3", out)
        self.assertIn("Let there be light", out)

    def test_cli_search_exact_phrase(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main(["--db", str(self.db_path), "search", "one and only Son", "--exact"])
        self.assertEqual(code, 0)
        out = stdout.getvalue()
        self.assertIn('=== Scripture Search: "one and only Son" (exact phrase) (WEB) ===', out)
        self.assertIn("John 3:16", out)
        self.assertIn("one and only Son", out)

    def test_cli_search_alias_find(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main(["--db", str(self.db_path), "find", "heavens"])
        self.assertEqual(code, 0)
        out = stdout.getvalue()
        self.assertIn('=== Scripture Search: "heavens" (WEB) ===', out)
        self.assertIn("Genesis 1:1", out)

    def test_cli_search_book_filter(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main(["--db", str(self.db_path), "search", "world", "--book", "Genesis"])
        self.assertEqual(code, 0)
        out = stdout.getvalue()
        self.assertIn("(WEB, Genesis)", out)
        # "world" does not appear in Genesis 1:1 or 1:3 in our test data
        self.assertIn("No matching verses found.", out)

        stdout = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main(["--db", str(self.db_path), "search", "world", "--book", "John"])
        self.assertEqual(code, 0)
        out = stdout.getvalue()
        self.assertIn("(WEB, John)", out)
        self.assertIn("John 3:16", out)

    def test_cli_search_invalid_book(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main(["--db", str(self.db_path), "search", "light", "--book", "FakeBook"])
        self.assertEqual(code, 1)
        self.assertIn("Error: Unknown book 'FakeBook'.", stderr.getvalue())

    def test_cli_search_testament_filter(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main(["--db", str(self.db_path), "search", "world", "--testament", "NT"])
        self.assertEqual(code, 0)
        out = stdout.getvalue()
        self.assertIn("New Testament", out)
        self.assertIn("John 3:16", out)

        stdout = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main(["--db", str(self.db_path), "search", "world", "--testament", "OT"])
        self.assertEqual(code, 0)
        out = stdout.getvalue()
        self.assertIn("Old Testament", out)
        self.assertIn("No matching verses found.", out)

    def test_cli_search_invalid_testament(self):
        stderr = io.StringIO()
        with patch("sys.stderr", stderr), self.assertRaises(SystemExit) as ctx:
            main(["--db", str(self.db_path), "search", "world", "--testament", "INVALID"])
        self.assertEqual(ctx.exception.code, 2)

    def test_cli_search_canonical_sort(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main(["--db", str(self.db_path), "search", "the", "--sort", "canonical"])
        self.assertEqual(code, 0)
        out = stdout.getvalue()
        gen_idx = out.find("Genesis 1:1")
        john_idx = out.find("John 3:16")
        self.assertTrue(gen_idx != -1 and john_idx != -1)
        self.assertLess(gen_idx, john_idx)

    def test_cli_search_snippets(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main(["--db", str(self.db_path), "search", "heavens", "--snippets", "--no-highlight"])
        self.assertEqual(code, 0)
        out = stdout.getvalue()
        self.assertIn("[heavens]", out)

    def test_cli_search_count(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main(["--db", str(self.db_path), "search", "world", "--count"])
        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue().strip(), "2")  # John 3:16 and John 3:17 in WEB

    def test_cli_search_json(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main(["--db", str(self.db_path), "search", "heavens", "--json"])
        self.assertEqual(code, 0)
        import json
        data = json.loads(stdout.getvalue())
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["reference"], "Genesis 1:1")
        self.assertEqual(data[0]["book"], "Genesis")

    def test_cli_search_fallback_translation(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main(["--db", str(self.db_path), "search", "heavens", "--version", "ESV"])
        self.assertEqual(code, 0)
        self.assertIn("Notice: Translation 'ESV' not available; searching in fallback 'WEB'.", stderr.getvalue())
        self.assertIn("Genesis 1:1", stdout.getvalue())

    def test_cli_search_strict_missing_translation(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main(["--db", str(self.db_path), "search", "heavens", "--version", "ESV", "--strict"])
        self.assertEqual(code, 1)
        self.assertIn("Error: Translation 'ESV' is not installed in database.", stderr.getvalue())

    def test_cli_search_empty_query(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main(["--db", str(self.db_path), "search", "   "])
        self.assertEqual(code, 1)
        self.assertIn("Error: Search query required", stderr.getvalue())

    def test_cli_get_with_typography_options(self):
        # Test get with margin, width, flow, and boxed header
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main([
                "--db", str(self.db_path),
                "get", "John 3:16-17",
                "--margin", "4",
                "--width", "60",
                "--flow",
                "--box",
                "--no-color",
            ])
        self.assertEqual(code, 0)
        out = stdout.getvalue()
        self.assertIn("┌", out)
        self.assertIn("John 3:16-17 (WEB)", out)
        self.assertIn("    [16] For God so loved", out)

    def test_cli_get_with_color_theme(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main([
                "--db", str(self.db_path),
                "get", "John 3:16",
                "--color",
                "--theme", "amber",
            ])
        self.assertEqual(code, 0)
        out = stdout.getvalue()
        self.assertIn("\033[1;33m=== John 3:16", out)

    def test_cli_compare_with_typography_options(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main([
                "--db", str(self.db_path),
                "compare", "John 3:16",
                "--versions", "WEB,KJV",
                "--margin", "2",
                "--width", "70",
                "--box",
                "--no-color",
            ])
        self.assertEqual(code, 0)
        out = stdout.getvalue()
        self.assertIn("┌", out)
        self.assertIn("Compare: John 3:16", out)
        self.assertIn("[WEB]", out)
        self.assertIn("[KJV]", out)

    def test_cli_direct_citation_routing(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main([
                "--db", str(self.db_path),
                "John 3:16",
            ])
        self.assertEqual(code, 0)
        self.assertIn("=== John 3:16 (WEB) ===", stdout.getvalue())
        self.assertIn("one and only Son", stdout.getvalue())

    def test_cli_direct_citation_with_flags(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main([
                "--db", str(self.db_path),
                "John 3:16-17",
                "--margin", "4",
                "--flow",
                "--box",
                "--no-color",
            ])
        self.assertEqual(code, 0)
        self.assertIn("┌", stdout.getvalue())
        self.assertIn("John 3:16-17 (WEB)", stdout.getvalue())

    @patch("cli.shell.launch_shell", return_value=0)
    def test_cli_shell_command(self, mock_launch):
        code = main(["shell"])
        self.assertEqual(code, 0)
        self.assertTrue(mock_launch.called)

    @patch("cli.shell.launch_shell", return_value=0)
    def test_cli_interactive_flag(self, mock_launch):
        code = main(["-i"])
        self.assertEqual(code, 0)
        self.assertTrue(mock_launch.called)

    def test_cli_db_stats(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main(["--db", str(self.db_path), "db", "stats"])
        self.assertEqual(code, 0)
        out = stdout.getvalue()
        self.assertIn("Database Diagnostics & Storage Status", out)
        self.assertIn("Total Verses:", out)
        self.assertIn("WEB", out)

    def test_cli_db_optimize_and_vacuum(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code_opt = main(["--db", str(self.db_path), "db", "optimize"])
            code_vac = main(["--db", str(self.db_path), "db", "vacuum"])
        self.assertEqual(code_opt, 0)
        self.assertEqual(code_vac, 0)
        self.assertIn("Successfully optimized", stdout.getvalue())
        self.assertIn("Successfully vacuumed", stdout.getvalue())

    def test_cli_init_idempotent(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_db = Path(tmpdir) / "test_init.db"
            with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                code = main(["--db", str(tmp_db), "init", "--quick", "--no-hooks"])
            self.assertEqual(code, 0)
            self.assertIn("Sovereign Database Bootstrap Complete", stdout.getvalue())
            self.assertTrue(tmp_db.exists())

    def test_cli_doctor_fix_flag(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main(["doctor", "--fast", "--fix"])
        self.assertEqual(code, 0)
        self.assertIn("[Self-Healing --fix Active]", stdout.getvalue())
        self.assertIn("EXCELLENT", stdout.getvalue())

    def test_cli_slide_svg_generation(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as tmpdir:
            out_svg = Path(tmpdir) / "test_slide.svg"
            with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                code = main([
                    "--db", str(self.db_path),
                    "slide", "John 3:16",
                    "--output", str(out_svg),
                    "--format", "svg",
                    "--theme", "oled_black",
                    "--resolution", "1080p",
                ])
            self.assertEqual(code, 0)
            self.assertTrue(out_svg.exists())
            self.assertGreater(out_svg.stat().st_size, 1000)
            svg_content = out_svg.read_text(encoding="utf-8")
            self.assertIn("<svg", svg_content)
            self.assertIn("John 3:16", svg_content)
            self.assertIn("Generated 1920x1080 SVG slide", stdout.getvalue())

    def test_cli_slide_alias_render(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as tmpdir:
            out_svg = Path(tmpdir) / "render_alias.svg"
            with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                code = main([
                    "--db", str(self.db_path),
                    "render", "Genesis 1:1",
                    "-o", str(out_svg),
                    "-f", "svg",
                ])
            self.assertEqual(code, 0)
            self.assertTrue(out_svg.exists())
            self.assertIn("Generated 3840x2160 SVG slide", stdout.getvalue())

    def test_cli_slide_list_themes(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main(["--db", str(self.db_path), "slide", "--list-themes"])
        self.assertEqual(code, 0)
        out = stdout.getvalue()
        self.assertIn("oled_black", out)
        self.assertIn("charcoal", out)
        self.assertIn("obsidian", out)

    def test_cli_slide_list_resolutions(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main(["--db", str(self.db_path), "slide", "--list-resolutions"])
        self.assertEqual(code, 0)
        out = stdout.getvalue()
        self.assertIn("3840x2160", out)
        self.assertIn("1920x1080", out)

    def test_cli_slide_missing_reference_error(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main(["--db", str(self.db_path), "slide"])
        self.assertEqual(code, 1)
        self.assertIn("Scripture reference required", stderr.getvalue())

    def test_cli_slide_rich_options(self):
        self.db.tag_reference(parse_reference("John 3:16"), "Gospel", category="theological")
        stdout = io.StringIO()
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as tmpdir:
            out_svg = Path(tmpdir) / "rich_slide.svg"
            with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                code = main([
                    "--db", str(self.db_path),
                    "slide", "John 3:16",
                    "-o", str(out_svg),
                    "-f", "svg",
                    "--safe-area", "15%",
                    "--font-size", "auto",
                    "--citation-color", "gold",
                    "--accent-color", "#2ECC71",
                    "--tags",
                ])
            self.assertEqual(code, 0)
            self.assertTrue(out_svg.exists())
            content = out_svg.read_text(encoding="utf-8")
            self.assertIn("fill: #D4AF37", content)
            self.assertIn("stroke: #2ECC71", content)
            self.assertIn("John 3:16", content)
            self.assertIn("Gospel", content)
            self.assertIn("Generated 3840x2160 SVG slide", stdout.getvalue())
            self.assertIn("Citation:   #D4AF37", stdout.getvalue())

    def test_cli_slide_stdout_piping(self):
        import io
        stdout_buf = io.BytesIO()
        stderr = io.StringIO()
        fake_stdout = io.TextIOWrapper(stdout_buf, encoding="utf-8")
        with patch("sys.stdout", fake_stdout), patch("sys.stderr", stderr):
            code = main([
                "--db", str(self.db_path),
                "slide", "John 3:16",
                "-f", "svg",
                "-o", "-",
            ])
        self.assertEqual(code, 0)
        output_bytes = stdout_buf.getvalue()
        self.assertIn(b"<svg", output_bytes)
        self.assertIn(b"John 3:16", output_bytes)

    def test_cli_slide_quiet_flag(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as tmpdir:
            out_svg = Path(tmpdir) / "quiet_slide.svg"
            with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                code = main([
                    "--db", str(self.db_path),
                    "slide", "John 3:16",
                    "-o", str(out_svg),
                    "-f", "svg",
                    "-q",
                ])
            self.assertEqual(code, 0)
            self.assertTrue(out_svg.exists())
            self.assertEqual(stdout.getvalue(), "")

    def test_cli_slide_multi_pagination(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as tmpdir:
            base_file = Path(tmpdir) / "hebrews.svg"
            with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                code = main([
                    "--db", str(self.db_path),
                    "slide", "Hebrews 11:1-12",
                    "-o", str(base_file),
                    "-f", "svg",
                    "--paginate",
                ])
            self.assertEqual(code, 0)
            out = stdout.getvalue()
            self.assertIn("slide sequence", out)
            self.assertIn("[1 /", out)
            created_files = list(Path(tmpdir).glob("hebrews_*.svg"))
            self.assertGreater(len(created_files), 1)

    def test_cli_slide_output_dir_and_max_verses(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                code = main([
                    "--db", str(self.db_path),
                    "slide", "Hebrews 11:1-12",
                    "-d", str(tmpdir),
                    "--max-verses", "3",
                    "-f", "svg",
                ])
            self.assertEqual(code, 0)
            out = stdout.getvalue()
            self.assertIn("Generated 4-slide sequence", out)
            files = list(Path(tmpdir).glob("*.svg"))
            self.assertEqual(len(files), 4)

    def test_cli_slide_no_paginate_override(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "single_hebrews.svg"
            with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                code = main([
                    "--db", str(self.db_path),
                    "slide", "Hebrews 11:1-12",
                    "-o", str(out_file),
                    "-f", "svg",
                    "--no-paginate",
                ])
            self.assertEqual(code, 0)
            out = stdout.getvalue()
            self.assertIn("Generated 3840x2160 SVG slide", out)
            self.assertTrue(out_file.exists())


if __name__ == "__main__":
    unittest.main()
