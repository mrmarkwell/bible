"""Hermetic unit tests for tools/doctor.py diagnostic utility.

Zero external dependencies (Python 3 standard library only per ADR-003).
"""

from pathlib import Path
import tempfile
import unittest

from tools.doctor import (
    CheckResult,
    DoctorStyler,
    check_zero_dependencies,
    check_doc_synchronization,
    check_bash_scripts,
    check_database_integrity,
    check_unit_tests,
    run_all_checks,
    REPO_ROOT,
)


class TestDoctorStyler(unittest.TestCase):
    """Test ANSI styler helper."""

    def test_styler_enabled_and_disabled(self):
        enabled = DoctorStyler(enabled=True)
        disabled = DoctorStyler(enabled=False)

        self.assertEqual(disabled.bold("hello"), "hello")
        self.assertEqual(disabled.green("ok"), "ok")
        self.assertEqual(disabled.red("err"), "err")

        self.assertIn("\033[1m", enabled.bold("hello"))
        self.assertIn("\033[32m", enabled.green("ok"))
        self.assertIn("\033[31m", enabled.red("err"))


class TestDoctorChecks(unittest.TestCase):
    """Hermetic unit tests for individual doctor diagnostic checks."""

    def test_check_zero_dependencies_repo_clean(self):
        res = check_zero_dependencies(REPO_ROOT)
        self.assertTrue(res.passed, f"Zero-dependency check failed: {res.details}")
        self.assertIn("100% stdlib compliance", res.details)

    def test_check_zero_dependencies_detects_violation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            dirty_py = tmp_path / "bad_script.py"
            dirty_py.write_text("import requests\nfrom fastapi import FastAPI\n", encoding="utf-8")

            res = check_zero_dependencies(tmp_path)
            self.assertFalse(res.passed)
            self.assertIn("requests", res.details)
            self.assertIn("fastapi", res.details)

    def test_check_doc_synchronization_clean(self):
        res = check_doc_synchronization(REPO_ROOT)
        self.assertTrue(res.passed, f"Doc sync failed: {res.details}")
        self.assertIn("sequential runs", res.details)

    def test_check_bash_scripts_clean(self):
        res = check_bash_scripts(REPO_ROOT)
        self.assertTrue(res.passed, f"Bash check failed: {res.details}")

    def test_check_database_integrity_clean(self):
        res = check_database_integrity(REPO_ROOT)
        self.assertTrue(res.passed, f"Database check failed: {res.details}")
        self.assertIn("WEB verses", res.details)

    def test_check_unit_tests_clean(self):
        res = check_unit_tests(REPO_ROOT)
        self.assertTrue(res.passed, f"Unit test execution failed: {res.details}")
        self.assertIn("passing 100%", res.details)

    def test_run_all_checks_e2e(self):
        code, results = run_all_checks(repo_root=REPO_ROOT, color=False)
        self.assertEqual(code, 0)
        self.assertEqual(len(results), 5)
        for r in results:
            self.assertTrue(r.passed, f"Check {r.name} failed: {r.details}")


if __name__ == "__main__":
    unittest.main()
