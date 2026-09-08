"""Hermetic unit tests for tools/doctor.py diagnostic utility.

Zero external dependencies (Python 3 standard library only per ADR-003).
"""

import io
import json
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
    check_ci_workflows,
    check_code_quality,
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
        self.assertEqual(len(results), 6)
        names = [r.name for r in results]
        self.assertIn("Zero External Dependencies (AST Audit)", names)
        self.assertIn("Documentation State Sync", names)
        self.assertIn("Shell Script Integrity", names)
        self.assertIn("Git Hook Safeguards", names)
        self.assertIn("CI/CD Automation & GitHub Actions", names)
        self.assertIn("Code Quality (Static Linter Audit)", names)
        self.assertNotIn("Hermetic Test Suite", names)

    def test_run_all_checks_quiet_and_stream(self):
        from unittest.mock import patch
        buf = io.StringIO()
        with patch("tools.doctor.check_zero_dependencies", return_value=CheckResult("Zero Dependencies", True, "OK", 0.001)), \
             patch("tools.doctor.check_code_quality", return_value=CheckResult("Code Quality", True, "OK", 0.001)):
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
            self.assertEqual(len(results), 8)
            for r in results:
                self.assertTrue(r.passed, f"Check {r.name} failed: {r.details}")

    def test_check_code_quality_clean(self):
        res = check_code_quality(REPO_ROOT)
        self.assertTrue(res.passed)
        self.assertIn("100% clean", res.details)

    def test_check_code_quality_detects_defects(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            bad_file = tmp_path / "broken.py"
            bad_file.write_text("data = {'a': 1, 'a': 2}\n", encoding="utf-8")
            res = check_code_quality(tmp_path)
            self.assertFalse(res.passed)
            self.assertIn("Defects detected", res.details)

    def test_check_git_hooks_auto_repair(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            git_dir = tmp_path / ".git"
            git_dir.mkdir()
            # Without fix, it fails
            res_fail = check_git_hooks(tmp_path, fix=False)
            self.assertFalse(res_fail.passed)

            # With fix, it automatically installs hooks and passes
            res_fix = check_git_hooks(tmp_path, fix=True)
            self.assertTrue(res_fix.passed)
            self.assertIn("Auto-repaired", res_fix.details)
            self.assertTrue((git_dir / "hooks" / "pre-commit").exists())

    def test_check_database_integrity_auto_heal_mock(self):
        from unittest.mock import patch
        from core.bootstrap import BootstrapReport
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            mock_rep = BootstrapReport(
                db_path=tmp_path / "data" / "bible.db",
                duration_sec=0.1,
                verses_count=31103,
                translations_count=1,
                favorites_count=829,
                starred_count=50,
                tags_count=26,
                cross_references_count=43,
                hooks_installed=True,
                pragmas_optimized=True,
                is_clean=True,
                details="Auto-heal complete",
            )
            with patch("core.bootstrap.bootstrap_database", return_value=mock_rep):
                res = check_database_integrity(tmp_path, fix=True)
                self.assertTrue(res.passed)
                self.assertIn("Auto-healed", res.details)

    def test_check_ci_workflows_clean_in_repo(self):
        res = check_ci_workflows(REPO_ROOT)
        self.assertTrue(res.passed, f"CI check failed: {res.details}")
        self.assertIn("workflow(s) active", res.details)
        self.assertIn("ci.yml", res.details)

    def test_check_ci_workflows_anomalies(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            # Missing .github/workflows directory
            res = check_ci_workflows(tmp_path)
            self.assertFalse(res.passed)
            self.assertIn("Missing", res.details)

            wf_dir = tmp_path / ".github" / "workflows"
            wf_dir.mkdir(parents=True)
            # Empty directory
            res = check_ci_workflows(tmp_path)
            self.assertFalse(res.passed)
            self.assertIn("No workflow YAML", res.details)

            # Invalid workflow missing required keys
            bad_wf = wf_dir / "bad.yml"
            bad_wf.write_text("foo: bar\n", encoding="utf-8")
            res = check_ci_workflows(tmp_path)
            self.assertFalse(res.passed)
            self.assertIn("missing required top-level keys", res.details)
            self.assertIn("no 'runs-on:'", res.details)

    def test_check_database_integrity_semantic_schema_and_foreign_keys(self):
        res = check_database_integrity(REPO_ROOT)
        self.assertTrue(res.passed, f"DB integrity check failed: {res.details}")
        self.assertIn("PRAGMA quick_check & FK passed", res.details)
        self.assertIn("tables verified", res.details)
        self.assertIn("semantically audited", res.details)
        self.assertRegex(res.details, r"\d+\.\d+%")

    def test_check_database_integrity_semantic_audit_failure(self):
        from core.db import Database
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            db_dir = tmp_path / "data"
            db_dir.mkdir()
            db_file = db_dir / "bible.db"
            with Database(db_file, auto_init=True) as db:
                db.add_translation("WEB", "World English Bible")
                from core.db import VerseRecord
                db.insert_verses([VerseRecord("WEB", 1, 1, 1, "In the beginning...")])
                # Insert pericope with invalid coordinates to trigger audit error
                db.conn.execute(
                    "INSERT INTO pericopes (book_id, start_canonical_id, end_canonical_id, human_ref, title) "
                    "VALUES (1, 1001050, 1001001, 'Gen 1:50-1', 'Invalid Span')"
                )
                db.conn.commit()

            from unittest.mock import patch
            with patch("core.db.Database.count_verses", return_value=31103), \
                 patch("core.db.Database.search_text", return_value=[{"id": 1}]):
                res = check_database_integrity(tmp_path, fix=False)
                self.assertFalse(res.passed)
                self.assertIn("Semantic quality audit errors detected", res.details)

    def test_check_database_integrity_semantic_auto_migrate(self):
        from core.db import Database
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            db_dir = tmp_path / "data"
            db_dir.mkdir()
            db_file = db_dir / "bible.db"
            with Database(db_file, auto_init=True) as db:
                # Drop one semantic table to simulate an older database
                db.conn.execute("DROP TABLE verse_theology")
                db.conn.commit()

            # Without fix, fails reporting missing table
            res_fail = check_database_integrity(tmp_path, fix=False)
            self.assertFalse(res_fail.passed)
            self.assertIn("verse_theology", res_fail.details)

            # With fix, auto-migrates and passes
            from unittest.mock import patch
            with patch("core.db.Database.count_verses", return_value=31103), \
                 patch("core.db.Database.search_text", return_value=[{"id": 1}]):
                res_fix = check_database_integrity(tmp_path, fix=True)
                self.assertTrue(res_fix.passed)
                self.assertIn("Auto-repaired semantic schema", res_fix.details)

    def test_check_doc_synchronization_roadmap_validation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            # Create minimal governance files
            (tmp_path / "DECISIONS.md").write_text("## ADR-001: Initial\n", encoding="utf-8")
            (tmp_path / "AGENT_LOG.md").write_text("## [Run 001] — ADR-001\n", encoding="utf-8")
            (tmp_path / "IDEAS.md").write_text("# Ideas\n", encoding="utf-8")

            # Incomplete roadmap missing phases
            (tmp_path / "ROADMAP.md").write_text("### Phase 0: Repo\n- [x] **Task 0.1**: Setup\n", encoding="utf-8")
            res = check_doc_synchronization(tmp_path)
            self.assertFalse(res.passed)
            self.assertIn("missing required phases", res.details)

            # Roadmap with duplicate task IDs
            bad_roadmap = "\n".join([f"### Phase {i}: Title" for i in range(9)]) + "\n"
            bad_roadmap += "- [x] **Task 0.1**: Setup\n- [ ] **Task 0.1**: Duplicate\n"
            (tmp_path / "ROADMAP.md").write_text(bad_roadmap, encoding="utf-8")
            res_dup = check_doc_synchronization(tmp_path)
            self.assertFalse(res_dup.passed)
            self.assertIn("duplicate task identifiers", res_dup.details)

    def test_run_all_checks_json_output(self):
        from unittest.mock import patch
        buf = io.StringIO()
        with patch("tools.doctor.check_zero_dependencies", return_value=CheckResult("Zero External Dependencies (AST Audit)", True, "OK", 0.001)), \
             patch("tools.doctor.check_code_quality", return_value=CheckResult("Code Quality (Static Linter Audit)", True, "OK", 0.001)):
            code, results = run_all_checks(
                repo_root=REPO_ROOT,
                color=False,
                fast=True,
                json_output=True,
                stream=buf,
            )
        self.assertEqual(code, 0)
        output_str = buf.getvalue().strip()
        data = json.loads(output_str)
        self.assertEqual(data["system_health"], "EXCELLENT")
        self.assertEqual(data["total_checks"], len(results))
        self.assertEqual(data["failed_checks"], 0)
        self.assertIn("timestamp", data)
        self.assertIn("checks", data)
        self.assertTrue(len(data["checks"]) >= 6)
        names = [c["name"] for c in data["checks"]]
        self.assertIn("Zero External Dependencies (AST Audit)", names)

    def test_cli_doctor_json_flag(self):
        from cli.main import build_parser
        parser = build_parser()
        args = parser.parse_args(["doctor", "--json", "--fast"])
        self.assertTrue(args.json)
        self.assertTrue(args.fast)


if __name__ == "__main__":
    unittest.main()
