"""Hermetic unit tests for tools/doctor.py diagnostic utility.

Zero external dependencies (Python 3 standard library only per ADR-003).
"""

import os
from pathlib import Path
import tempfile
import unittest

from tools.doctor import (
    CheckResult,
    DoctorStyler,
    check_zero_dependencies,
    check_doc_synchronization,
    check_bash_scripts,
    check_git_hooks,
    check_database_integrity,
    check_unit_tests,
    install_hooks,
    uninstall_hooks,
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
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            tests_dir = tmp_path / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_sample.py").write_text(
                "import unittest\n\nclass SampleTest(unittest.TestCase):\n    def test_sample(self):\n        self.assertTrue(True)\n",
                encoding="utf-8",
            )
            res = check_unit_tests(tmp_path)
            self.assertTrue(res.passed, f"Unit test execution failed: {res.details}")
            self.assertIn("1 tests passing 100%", res.details)

    def test_check_git_hooks_clean_in_repo(self):
        res = check_git_hooks(REPO_ROOT)
        self.assertTrue(res.passed, f"Git hooks check failed: {res.details}")
        self.assertIn("Active", res.details)

    def test_check_git_hooks_missing_and_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            # Without .git directory: skipped
            res = check_git_hooks(tmp_path)
            self.assertTrue(res.passed)
            self.assertIn("skipped", res.details)

            # With .git directory but no hooks: fails
            git_dir = tmp_path / ".git"
            git_dir.mkdir()
            res_fail = check_git_hooks(tmp_path)
            self.assertFalse(res_fail.passed)
            self.assertIn("Missing", res_fail.details)

            # Install hooks: succeeds
            ok, msg = install_hooks(tmp_path)
            self.assertTrue(ok)
            self.assertIn("Successfully installed", msg)
            self.assertTrue((git_dir / "hooks" / "pre-commit").exists())
            self.assertTrue((git_dir / "hooks" / "pre-push").exists())
            self.assertTrue(os.access(git_dir / "hooks" / "pre-commit", os.X_OK))
            self.assertTrue(os.access(git_dir / "hooks" / "pre-push", os.X_OK))

            # Now check_git_hooks passes
            res_pass = check_git_hooks(tmp_path)
            self.assertTrue(res_pass.passed)
            self.assertIn("Active", res_pass.details)

            # Uninstall hooks: succeeds
            ok_un, msg_un = uninstall_hooks(tmp_path)
            self.assertTrue(ok_un)
            self.assertIn("Removed git hooks", msg_un)
            self.assertFalse((git_dir / "hooks" / "pre-commit").exists())
            self.assertFalse((git_dir / "hooks" / "pre-push").exists())

    def test_run_all_checks_fast_mode(self):
        code, results = run_all_checks(repo_root=REPO_ROOT, color=False, fast=True, quiet=True)
        self.assertEqual(code, 0)
        self.assertEqual(len(results), 4)
        names = [r.name for r in results]
        self.assertIn("Zero External Dependencies (AST Audit)", names)
        self.assertIn("Documentation State Sync", names)
        self.assertIn("Shell Script Integrity", names)
        self.assertIn("Git Hook Safeguards", names)
        self.assertNotIn("Hermetic Test Suite", names)

    def test_run_all_checks_quiet_and_stream(self):
        import io
        buf = io.StringIO()
        code, results = run_all_checks(repo_root=REPO_ROOT, color=False, fast=True, stream=buf)
        self.assertEqual(code, 0)
        output = buf.getvalue()
        self.assertIn("Fast Pre-Commit Mode", output)
        self.assertIn("[PASS] Git Hook Safeguards", output)

    def test_run_all_checks_e2e(self):
        from unittest.mock import patch
        with patch("tools.doctor.check_unit_tests") as mock_test_check:
            mock_test_check.return_value = CheckResult("Hermetic Test Suite", True, "Mock tests passing", 0.01)
            code, results = run_all_checks(repo_root=REPO_ROOT, color=False, quiet=True)
            self.assertEqual(code, 0)
            self.assertEqual(len(results), 6)
            for r in results:
                self.assertTrue(r.passed, f"Check {r.name} failed: {r.details}")


if __name__ == "__main__":
    unittest.main()
