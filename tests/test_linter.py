"""Hermetic unit tests for tools/linter.py static analysis & code hygiene engine.

Zero external dependencies (Python 3 standard library only per ADR-003).
"""

import io
import json
from pathlib import Path
import tempfile
import unittest

from tools.linter import (
    LinterStyler,
    discover_python_files,
    lint_file,
    lint_repository,
    lint_source_text,
    REPO_ROOT,
)


class TestLinterStyler(unittest.TestCase):
    """Test ANSI styler helper."""

    def test_styler_enabled_and_disabled(self):
        enabled = LinterStyler(enabled=True)
        disabled = LinterStyler(enabled=False)

        self.assertEqual(disabled.bold("hello"), "hello")
        self.assertEqual(disabled.green("ok"), "ok")
        self.assertEqual(disabled.red("err"), "err")
        self.assertEqual(disabled.yellow("warn"), "warn")
        self.assertEqual(disabled.cyan("info"), "info")
        self.assertEqual(disabled.magenta("fix"), "fix")

        self.assertIn("[1m", enabled.bold("hello"))
        self.assertIn("[32m", enabled.green("ok"))
        self.assertIn("[31m", enabled.red("err"))
        self.assertIn("[33m", enabled.yellow("warn"))


class TestFileDiscovery(unittest.TestCase):
    """Test repository file discovery."""

    def test_discover_files_defaults(self):
        files = discover_python_files(REPO_ROOT)
        self.assertGreater(len(files), 30)
        rel_paths = [str(f.relative_to(REPO_ROOT)) for f in files]
        self.assertTrue(any("core/db.py" in p for p in rel_paths))
        self.assertTrue(any("tools/linter.py" in p for p in rel_paths))

    def test_discover_files_with_pattern(self):
        files = discover_python_files(REPO_ROOT, pattern="tools/linter.py")
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].name, "linter.py")


class TestASTAndFormattingAudits(unittest.TestCase):
    """Test AST code smell and formatting inspections."""

    def test_clean_source_passes(self):
        source = """def add(a: int, b: int) -> int:
    return a + b
"""
        issues, fixed, count = lint_source_text(source, Path("dummy.py"), "dummy.py")
        self.assertEqual(len(issues), 0)
        self.assertIsNone(fixed)
        self.assertEqual(count, 0)

    def test_syntax_error_detection(self):
        source = """def broken(
"""
        issues, _, _ = lint_source_text(source, Path("dummy.py"), "dummy.py")
        self.assertGreater(len(issues), 0)
        self.assertEqual(issues[0].code, "E001")
        self.assertEqual(issues[0].severity, "ERROR")

    def test_duplicate_dict_key_detection(self):
        source = """config = {
    'version': 1,
    'theme': 'dark',
    'version': 2,
}
"""
        issues, _, _ = lint_source_text(source, Path("dummy.py"), "dummy.py")
        codes = [i.code for i in issues]
        self.assertIn("E101", codes)
        err = [i for i in issues if i.code == "E101"][0]
        self.assertIn("version", err.message)
        self.assertEqual(err.severity, "ERROR")

    def test_mutable_default_argument_detection(self):
        source = """def process(items=[], mapping={}):
    pass
"""
        issues, _, _ = lint_source_text(source, Path("dummy.py"), "dummy.py")
        codes = [i.code for i in issues]
        self.assertEqual(codes.count("E102"), 2)

    def test_bare_except_clause_detection(self):
        source = """try:
    x = 1
except:
    pass
"""
        issues, _, _ = lint_source_text(source, Path("dummy.py"), "dummy.py")
        codes = [i.code for i in issues]
        self.assertIn("E103", codes)

    def test_unused_imports_detection(self):
        source = """import math
import sys
from typing import List

def run():
    print(math.pi)
"""
        issues, _, _ = lint_source_text(source, Path("dummy.py"), "dummy.py")
        unused = [i.message for i in issues if i.code == "W201"]
        self.assertTrue(any("sys" in m for m in unused))
        self.assertTrue(any("List" in m for m in unused))
        self.assertFalse(any("math" in m for m in unused))

    def test_wildcard_import_detection(self):
        source = """from core.reference import *
"""
        issues, _, _ = lint_source_text(source, Path("dummy.py"), "dummy.py")
        codes = [i.code for i in issues]
        self.assertIn("W202", codes)

    def test_unreachable_code_detection(self):
        source = """def compute():
    return 42
    print('never reached')
"""
        issues, _, _ = lint_source_text(source, Path("dummy.py"), "dummy.py")
        codes = [i.code for i in issues]
        self.assertIn("W203", codes)

    def test_trailing_whitespace_and_autofix(self):
        source = "def hello():   \n    pass\n"
        issues, fixed, count = lint_source_text(source, Path("dummy.py"), "dummy.py", fix=True)
        self.assertEqual(count, 1)
        self.assertEqual(fixed, "def hello():\n    pass\n")

    def test_missing_newline_and_autofix(self):
        source = "x = 1"
        issues, fixed, count = lint_source_text(source, Path("dummy.py"), "dummy.py", fix=True)
        self.assertEqual(count, 1)
        self.assertEqual(fixed, "x = 1\n")

    def test_trailing_blanks_and_autofix(self):
        source = "x = 1\n\n\n\n"
        issues, fixed, count = lint_source_text(source, Path("dummy.py"), "dummy.py", fix=True)
        self.assertEqual(fixed, "x = 1\n")


class TestFileAndRepoLinting(unittest.TestCase):
    """Test file-level and repository-level lint execution."""

    def test_lint_file_with_fix(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            test_py = tmp / "sample.py"
            test_py.write_text("def foo():   \n    return 1\n\n\n", encoding="utf-8")

            # Lint without fix
            res1 = lint_file(test_py, repo_root=tmp, fix=False)
            self.assertFalse(res1.passed)
            self.assertFalse(res1.fixed)

            # Lint with fix
            res2 = lint_file(test_py, repo_root=tmp, fix=True)
            self.assertTrue(res2.passed)
            self.assertTrue(res2.fixed)
            self.assertEqual(test_py.read_text(encoding="utf-8"), "def foo():\n    return 1\n")

    def test_lint_repo_clean(self):
        code, summary = lint_repository(repo_root=REPO_ROOT, quiet=True)
        self.assertEqual(code, 0)
        self.assertTrue(summary.success)
        self.assertEqual(summary.total_errors, 0)

    def test_lint_repo_json_output(self):
        buf = io.StringIO()
        code, summary = lint_repository(repo_root=REPO_ROOT, pattern="linter", output_json=True, stream=buf)
        self.assertEqual(code, 0)
        data = json.loads(buf.getvalue())
        self.assertTrue(data["success"])
        self.assertEqual(data["total_errors"], 0)

    def test_linter_dotted_module_import_recognized(self):
        source = (
            "import http.server\n"
            "import urllib.request\n"
            "class MyHandler(http.server.BaseHTTPRequestHandler):\n"
            "    def handle(self):\n"
            "        req = urllib.request.Request('http://localhost')\n"
        )
        issues, _, _ = lint_source_text(source, Path("dummy.py"), "dummy.py")
        w201_issues = [i for i in issues if i.code == "W201"]
        self.assertEqual(len(w201_issues), 0, f"Expected 0 unused import warnings, got: {w201_issues}")


if __name__ == "__main__":
    unittest.main()
