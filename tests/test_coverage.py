"""Hermetic unit tests for sovereign zero-dependency code coverage engine."""

import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.coverage import (
    CoverageReport,
    CoverageStyler,
    FileCoverage,
    collect_coverage,
    discover_target_files,
    format_line_ranges,
    format_terminal_table,
    generate_html_report,
    get_executable_lines,
    main,
)


class TestCoverageEngine(unittest.TestCase):
    """Test suite for tools/coverage.py line discovery, formatting, and report generation."""

    def test_format_line_ranges(self):
        self.assertEqual(format_line_ranges([]), "")
        self.assertEqual(format_line_ranges([42]), "42")
        self.assertEqual(format_line_ranges([1, 2, 3]), "1-3")
        self.assertEqual(format_line_ranges([1, 3, 5]), "1, 3, 5")
        self.assertEqual(format_line_ranges([10, 11, 12, 15, 20, 21]), "10-12, 15, 20-21")
        # Duplicates and unsorted
        self.assertEqual(format_line_ranges([5, 2, 3, 1, 2, 3]), "1-3, 5")

    def test_get_executable_lines_simple(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sample_py = Path(tmpdir) / "sample.py"
            sample_py.write_text(
                '"""Docstring."""\n'
                'x = 1\n'
                'def foo(y):\n'
                '    if y > 0:\n'
                '        return y * 2\n'
                '    return 0\n'
                'z = foo(x)\n',
                encoding="utf-8",
            )
            lines = get_executable_lines(sample_py)
            self.assertIsInstance(lines, set)
            self.assertIn(2, lines)  # x = 1
            self.assertIn(3, lines)  # def foo(y):
            self.assertIn(7, lines)  # z = foo(x)
            self.assertTrue(all(l > 0 for l in lines))

    def test_get_executable_lines_invalid_file(self):
        lines = get_executable_lines(Path("/nonexistent/file.py"))
        self.assertEqual(lines, set())

    def test_discover_target_files(self):
        repo_root = Path(__file__).resolve().parent.parent
        files = discover_target_files(repo_root, target_dirs=("core",))
        self.assertTrue(len(files) >= 10)
        self.assertTrue(any(f.name == "reference.py" for f in files))
        self.assertTrue(all(not f.name.endswith(".pyc") for f in files))

        # Single file targeting
        single = discover_target_files(repo_root, target_module="core/crypto.py")
        self.assertEqual(len(single), 1)
        self.assertEqual(single[0].name, "crypto.py")

    def test_coverage_styler(self):
        styler_color = CoverageStyler(enabled=True)
        self.assertIn("\033[", styler_color.bold("text"))
        self.assertIn("\033[32m", styler_color.green("text"))
        self.assertIn("\033[31m", styler_color.red("text"))

        styler_plain = CoverageStyler(enabled=False)
        self.assertEqual(styler_plain.bold("text"), "text")
        self.assertEqual(styler_plain.green("text"), "text")

        bar_100 = styler_plain.progress_bar(100.0, width=10)
        self.assertEqual(bar_100, "[██████████]")
        bar_0 = styler_plain.progress_bar(0.0, width=10)
        self.assertEqual(bar_0, "[░░░░░░░░░░]")

    def test_file_coverage_and_report_serialization(self):
        fc = FileCoverage(
            file_path=Path("/tmp/sample.py"),
            relative_path="core/sample.py",
            executable_count=100,
            executed_count=90,
            missed_count=10,
            coverage_pct=90.0,
            executable_lines=set(range(1, 101)),
            executed_lines=set(range(1, 91)),
            missed_lines=set(range(91, 101)),
            missed_ranges="91-100",
        )
        data = fc.to_dict(include_lines=True)
        self.assertEqual(data["file"], "core/sample.py")
        self.assertEqual(data["coverage_percent"], 90.0)
        self.assertEqual(len(data["missed_lines"]), 10)

        report = CoverageReport(
            files=[fc],
            total_executable=100,
            total_executed=90,
            total_missed=10,
            overall_coverage_pct=90.0,
            duration_sec=0.45,
            timestamp="2026-09-07 12:00:00",
        )
        rep_dict = report.to_dict()
        self.assertEqual(rep_dict["summary"]["overall_coverage_percent"], 90.0)
        json_str = report.to_json()
        self.assertIn('"overall_coverage_percent": 90.0', json_str)

        # Terminal table formatting
        table_output = format_terminal_table(report, color=False)
        self.assertIn("Bible Engine Test Coverage Report", table_output)
        self.assertIn("core/sample.py", table_output)
        self.assertIn("90.0%", table_output)

    def test_html_report_generation(self):
        fc = FileCoverage(
            file_path=Path("/tmp/sample.py"),
            relative_path="core/sample.py",
            executable_count=50,
            executed_count=45,
            missed_count=5,
            coverage_pct=90.0,
            missed_ranges="46-50",
        )
        report = CoverageReport(
            files=[fc],
            total_executable=50,
            total_executed=45,
            total_missed=5,
            overall_coverage_pct=90.0,
            duration_sec=0.12,
            timestamp="2026-09-07 12:00:00",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            html_out = Path(tmpdir) / "report.html"
            generate_html_report(report, html_out)
            self.assertTrue(html_out.is_file())
            content = html_out.read_text(encoding="utf-8")
            self.assertIn("<!DOCTYPE html>", content)
            self.assertIn("Bible Engine — Test Coverage Report", content)
            self.assertIn("core/sample.py", content)
            self.assertIn("90.0%", content)

    def test_collect_coverage_targeted(self):
        repo_root = Path(__file__).resolve().parent.parent
        report = collect_coverage(
            repo_root=repo_root,
            test_pattern="test_crypto",
            target_module="core/crypto.py",
            parallel=False,
        )
        self.assertEqual(len(report.files), 1)
        fc = report.files[0]
        self.assertEqual(fc.relative_path, "core/crypto.py")
        self.assertGreater(fc.executable_count, 100)
        self.assertGreater(fc.executed_count, 100)
        self.assertGreaterEqual(fc.coverage_pct, 90.0)

    def test_main_cli_execution(self):
        exit_code = main(["-p", "test_crypto", "-m", "core/crypto.py", "-q", "--threshold", "90.0"])
        self.assertEqual(exit_code, 0)

        # Threshold failure test (suppress expected stderr message during test execution)
        with io.StringIO() as err_buf, patch("sys.stderr", err_buf):
            exit_code_fail = main(["-p", "test_crypto", "-m", "core/crypto.py", "-q", "--threshold", "99.9"])
            self.assertEqual(exit_code_fail, 1)
            self.assertIn("ERROR: Overall coverage", err_buf.getvalue())


if __name__ == "__main__":
    unittest.main()
