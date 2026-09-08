"""Hermetic Unit Tests for Parallel Test Runner Engine (tools/test_runner.py).

Verifies zero-dependency parallel process execution, discovery, pattern filtering,
strict ResourceWarning enforcement, and JSON serialization.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from tools.test_runner import (
    REPO_ROOT,
    TestModuleResult,
    TestRunnerStyler,
    TestSuiteSummary,
    discover_test_files,
    load_timing_cache,
    parse_test_count_from_stderr,
    run_single_test_module,
    run_tests,
    run_tests_parallel,
    run_tests_sequential,
    save_timing_cache,
    sort_tests_longest_processing_time,
)


class TestRunnerEngine(unittest.TestCase):
    """Test suite for tools/test_runner.py components."""

    def test_discover_test_files_all(self):
        files = discover_test_files(REPO_ROOT)
        self.assertGreater(len(files), 15)
        names = [f.name for f in files]
        self.assertIn("test_reference.py", names)
        self.assertIn("test_crypto.py", names)
        self.assertIn("test_render.py", names)

    def test_discover_test_files_pattern_substring(self):
        files = discover_test_files(REPO_ROOT, pattern="crypto")
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].name, "test_crypto.py")

    def test_discover_test_files_pattern_wildcard(self):
        files = discover_test_files(REPO_ROOT, pattern="*render*")
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].name, "test_render.py")

    def test_discover_test_files_comma_separated(self):
        files = discover_test_files(REPO_ROOT, pattern="crypto, terminal")
        names = {f.name for f in files}
        self.assertIn("test_crypto.py", names)
        self.assertIn("test_terminal.py", names)
        self.assertEqual(len(files), 2)

    def test_discover_test_files_non_matching(self):
        files = discover_test_files(REPO_ROOT, pattern="nonexistent_xyz_module")
        self.assertEqual(len(files), 0)

    def test_parse_test_count(self):
        self.assertEqual(parse_test_count_from_stderr("Ran 42 tests in 0.2s"), 42)
        self.assertEqual(parse_test_count_from_stderr("Ran 1 test in 0.001s"), 1)
        self.assertEqual(parse_test_count_from_stderr("Ran 100 tests in 5.123s\nOK"), 100)
        self.assertEqual(parse_test_count_from_stderr("Nothing here"), 0)

    def test_styler_formatting(self):
        styler = TestRunnerStyler(enabled=True)
        self.assertIn("\033[32m", styler.green("pass"))
        self.assertIn("\033[31m", styler.red("fail"))
        self.assertIn("\033[1m", styler.bold("bold"))
        self.assertIn("\033[2m", styler.dim("dim"))

        disabled = TestRunnerStyler(enabled=False)
        self.assertEqual(disabled.green("pass"), "pass")
        self.assertEqual(disabled.red("fail"), "fail")

    def test_run_single_test_module_success(self):
        crypto_file = REPO_ROOT / "tests" / "test_crypto.py"
        res = run_single_test_module(crypto_file, REPO_ROOT, warn_error=True)
        self.assertTrue(res.passed)
        self.assertEqual(res.returncode, 0)
        self.assertEqual(res.module_name, "test_crypto")
        self.assertGreaterEqual(res.tests_run, 15)
        self.assertGreater(res.duration_sec, 0.0)

    def test_run_tests_sequential(self):
        crypto_file = REPO_ROOT / "tests" / "test_crypto.py"
        terminal_file = REPO_ROOT / "tests" / "test_terminal.py"
        summary = run_tests_sequential([crypto_file, terminal_file], REPO_ROOT, warn_error=True)
        self.assertTrue(summary.success)
        self.assertEqual(summary.total_modules, 2)
        self.assertEqual(summary.passed_modules, 2)
        self.assertEqual(summary.failed_modules, 0)
        self.assertGreaterEqual(summary.total_tests, 25)

    def test_run_tests_parallel(self):
        crypto_file = REPO_ROOT / "tests" / "test_crypto.py"
        terminal_file = REPO_ROOT / "tests" / "test_terminal.py"
        summary = run_tests_parallel([crypto_file, terminal_file], REPO_ROOT, jobs=2, warn_error=True)
        self.assertTrue(summary.success)
        self.assertEqual(summary.total_modules, 2)
        self.assertEqual(summary.passed_modules, 2)
        self.assertEqual(summary.failed_modules, 0)
        self.assertGreaterEqual(summary.total_tests, 25)

    def test_run_tests_facade_json(self):
        stream = io.StringIO()
        exit_code, summary = run_tests(
            repo_root=REPO_ROOT,
            pattern="crypto",
            parallel=False,
            output_json=True,
            stream=stream,
        )
        self.assertEqual(exit_code, 0)
        self.assertTrue(summary.success)
        raw_json = stream.getvalue()
        data = json.loads(raw_json)
        self.assertTrue(data["success"])
        self.assertEqual(data["total_modules"], 1)
        self.assertGreaterEqual(data["total_tests"], 15)

    def test_summary_to_dict(self):
        res = TestModuleResult(
            module_path="tests/test_mock.py",
            module_name="test_mock",
            tests_run=5,
            passed=True,
            duration_sec=0.123,
            returncode=0,
        )
        summary = TestSuiteSummary(
            total_modules=1,
            passed_modules=1,
            failed_modules=0,
            total_tests=5,
            total_duration_sec=0.125,
            results=[res],
            success=True,
        )
        d = summary.to_dict()
        self.assertTrue(d["success"])
        self.assertEqual(d["total_tests"], 5)
    def test_timing_cache_roundtrip(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            self.assertEqual(load_timing_cache(tmp_root), {})

            res1 = TestModuleResult("tests/test_a.py", "test_a", 5, True, 1.234)
            res2 = TestModuleResult("tests/test_b.py", "test_b", 10, True, 0.456)
            res_fail = TestModuleResult("tests/test_c.py", "test_c", 0, False, 0.100)

            save_timing_cache(tmp_root, [res1, res2, res_fail])
            cache = load_timing_cache(tmp_root)
            self.assertEqual(len(cache), 2)
            self.assertIn("test_a", cache)
            self.assertIn("test_b", cache)
            self.assertNotIn("test_c", cache)
            self.assertEqual(cache["test_a"], 1.234)
            self.assertEqual(cache["test_b"], 0.456)

    def test_sort_tests_longest_processing_time(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            t_dir = tmp_root / "tests"
            t_dir.mkdir()
            f_fast = t_dir / "test_fast.py"
            f_slow = t_dir / "test_slow.py"
            f_med = t_dir / "test_med.py"
            f_fast.write_text("# fast\n", encoding="utf-8")
            f_slow.write_text("# slow\n", encoding="utf-8")
            f_med.write_text("# med\n", encoding="utf-8")

            # Seed cache
            save_timing_cache(
                tmp_root,
                [
                    TestModuleResult("tests/test_fast.py", "test_fast", 1, True, 0.1),
                    TestModuleResult("tests/test_slow.py", "test_slow", 1, True, 3.5),
                    TestModuleResult("tests/test_med.py", "test_med", 1, True, 1.2),
                ],
            )

            sorted_files = sort_tests_longest_processing_time([f_fast, f_med, f_slow], tmp_root)
            self.assertEqual([f.name for f in sorted_files], ["test_slow.py", "test_med.py", "test_fast.py"])


class TestRunnerCliAndShellIntegration(unittest.TestCase):
    """Test CLI subcommand and interactive shell integration for test runner."""

    def test_cli_test_command_dispatch(self):
        from cli.main import build_parser, preprocess_cli_argv
        parser = build_parser()
        args = preprocess_cli_argv(["test", "-p", "crypto", "-s"])
        parsed = parser.parse_args(args)
        self.assertEqual(parsed.func.__name__, "cmd_test")
        self.assertEqual(parsed.pattern, "crypto")
        self.assertTrue(parsed.sequential)

    def test_cli_check_alias_dispatch(self):
        from cli.main import build_parser, preprocess_cli_argv
        parser = build_parser()
        args = preprocess_cli_argv(["check", "--json"])
        parsed = parser.parse_args(args)
        self.assertEqual(parsed.func.__name__, "cmd_test")
        self.assertTrue(parsed.json)

    def test_shell_test_command_execution(self):
        from cli.shell import BibleShell
        out = io.StringIO()
        shell = BibleShell(stdout=out, color=False)
        with shell:
            shell.do_test("-p crypto -s")
        output = out.getvalue()
        self.assertIn("Bible Engine Hermetic Test Runner", output)
        self.assertIn("ALL TESTS PASSED", output)

    def test_shell_test_autocomplete(self):
        from cli.shell import BibleShell
        shell = BibleShell(color=False)
        try:
            matches = shell.complete_test("-p", "/test -p", 6, 8)
            self.assertIn("-p", matches)
            matches_pattern = shell.complete_test("cryp", "/test cryp", 6, 10)
            self.assertIn("crypto", matches_pattern)
        finally:
            shell.close()


if __name__ == "__main__":
    unittest.main()
