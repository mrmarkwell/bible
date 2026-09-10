"""Hermetic unit tests for tools/executive_summary.py and summary CLI integration."""

import json
from pathlib import Path
import tempfile
import unittest

from tools.executive_summary import (
    generate_summary,
    format_markdown_report,
    parse_agent_log,
    parse_roadmap,
    ExecutiveReport,
)


class TestExecutiveSummary(unittest.TestCase):
    """Verify parsing, calculations, and reporting of executive summary generator."""

    def test_parse_agent_log(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "AGENT_LOG.md"
            log_path.write_text(
                "# Autonomous Agent Worklog\n\n"
                "## [Run 001] — 2026-09-06\n"
                "- **Phase**: Phase 0 — Foundation\n"
                "- **Goal**: Setup repo\n"
                "- **Actions Taken**:\n"
                "  - Created files\n"
                "  - Wrote tests\n\n"
                "## [Run 002] — 2026-09-07\n"
                "- **Phase**: Phase 1 — Data Models\n"
                "- **Task**: Implement models\n"
                "- **Actions Taken**:\n"
                "  - Added models\n",
                encoding="utf-8",
            )
            entries = parse_agent_log(log_path)
            self.assertEqual(len(entries), 2)
            self.assertEqual(entries[0].run_number, 1)
            self.assertEqual(entries[1].run_number, 2)
            self.assertIn("Added models", entries[1].actions)

    def test_parse_roadmap(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rm_path = Path(tmpdir) / "ROADMAP.md"
            rm_path.write_text(
                "# Roadmap\n\n"
                "- **Active Phase**: Phase 2 — CLI\n\n"
                "### Phase 1: Core Models\n"
                "- [x] Task 1.1\n"
                "- [x] Task 1.2\n\n"
                "### Phase 2: CLI\n"
                "- [x] Task 2.1\n"
                "- [ ] Task 2.2\n"
                "- [ ] Task 2.3\n",
                encoding="utf-8",
            )
            stats = parse_roadmap(rm_path)
            self.assertEqual(stats.active_phase, "Phase 2 — CLI")
            self.assertEqual(stats.completed_tasks, 3)
            self.assertEqual(stats.todo_tasks, 2)
            self.assertEqual(stats.total_tasks, 5)

    def test_generate_summary_live(self):
        report = generate_summary(window=5, run_doctor=False)
        self.assertIsInstance(report, ExecutiveReport)
        self.assertGreater(report.run_count, 0)
        self.assertGreater(report.roadmap_stats.completed_tasks, 0)
        self.assertGreaterEqual(report.estimated_runs_remaining, 0)
        md = format_markdown_report(report)
        self.assertIn("Executive Summary & Trajectory Briefing", md)
        self.assertIn("Executive Overview & Trajectory", md)
        self.assertIn("Review of Work Done", md)
        self.assertIn("Overall Project Health", md)

    def test_generate_summary_with_mocked_doctor(self):
        from unittest.mock import patch
        from tools.doctor import CheckResult
        mock_res = CheckResult("SQLite Scripture Database", True, "Mock DB OK", 0.001)
        with patch("tools.doctor.check_database_integrity", return_value=mock_res):
            report = generate_summary(window=3, run_doctor=True)
            self.assertIn("EXCELLENT", report.system_health_status)
            md = format_markdown_report(report)
            self.assertIn("Overall Project Health", md)
            self.assertIn("Mock DB OK", md)

    def test_parse_agent_log_resilient(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "AGENT_LOG.md"
            log_path.write_text(
                "# Autonomous Agent Worklog\n\n"
                "## [Run 039] 2026-09-07 — Senior Product Manager Meta-Improvement & System Health Sprint (Task 0.13 / ADR-040)\n"
                "- **Role**: Senior Product Manager & Meta-Architect.\n"
                "- **Sprint Mode**: Mandatory Cadence Protocol (Meta-Improvement & System Health Sprint).\n"
                "- **Accomplishments & Rank A+ Execution**:\n"
                "  - **Sovereign Linter Engine (`tools/linter.py`)**:\n"
                "    - Built fast static analysis engine.\n"
                "  - **Latent Bug Discovery**:\n"
                "    - Fixed dictionary collision.\n\n"
                "## [Run 040] (Senior PM Double Milestone)\n"
                "- **Phase**: Phase 0 — Foundation\n"
                "- **Task**: Double Milestone Briefing\n"
                "- **Actions Taken**:\n"
                "  - **Coverage Engine**:\n"
                "    - Added coverage tool.\n",
                encoding="utf-8",
            )
            entries = parse_agent_log(log_path)
            self.assertEqual(len(entries), 2)
            self.assertEqual(entries[0].run_number, 39)
            self.assertEqual(entries[0].archetype, "meta_sprint")
            self.assertIn("Task 0.13", entries[0].task)
            self.assertTrue(len(entries[0].actions) >= 1)

            self.assertEqual(entries[1].run_number, 40)
            self.assertEqual(entries[1].archetype, "milestone")

    def test_parse_agent_log_nested_actions_and_bugfix(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "AGENT_LOG.md"
            log_path.write_text(
                "# Autonomous Agent Worklog\n\n"
                "## [Run 056] — 2026-09-08\n"
                "- **Agent**: Ralph Loop Agent (Mandatory Priority: GitHub Issue Triage & Resolution)\n"
                "- **Context / Trigger**: Mandatory Priority GitHub Bug Report #1: *\"SVG never renders on the web UI\"* submitted by @mrmarkwell.\n"
                "- **Actions Taken**:\n"
                "  - **Global Visibility Utility in `web/static/style.css`**:\n"
                "    - Added universal `.hidden { display: none !important; }` rule.\n"
                "  - **Vector SVG DOM Sanitization in `web/static/app.js`**:\n"
                "    - Added regex XML prolog stripping.\n\n"
                "## [Run 057] — 2026-09-08\n"
                "- **Agent**: Ralph Loop Agent (Autonomous Roadmap Lifecycle)\n"
                "- **Task Addressed**: Phase 8, **Task 8.1**: *Implement Scripture RAG retrieval engine in `core/rag.py`.*\n"
                "- **Actions Taken**:\n"
                "  - **Query Analysis & Feature Extraction (`extract_query_features`)**:\n"
                "    - Scans queries for canonical citations.\n",
                encoding="utf-8",
            )
            entries = parse_agent_log(log_path)
            self.assertEqual(len(entries), 2)
            self.assertEqual(entries[0].run_number, 56)
            self.assertEqual(entries[0].archetype, "bugfix")
            self.assertEqual(entries[0].phase, "Bug Triage & Resolution")
            self.assertTrue(any("Global Visibility Utility" in a and "Added universal" in a for a in entries[0].actions))

            self.assertEqual(entries[1].run_number, 57)
            self.assertEqual(entries[1].phase, "Phase 8")
            self.assertIn("Task 8.1", entries[1].task)
            self.assertTrue(any("Query Analysis" in a and "Scans queries" in a for a in entries[1].actions))

    def test_json_export(self):
        report = generate_summary(window=3, run_doctor=False)
        json_data = report.to_json()
        parsed = json.loads(json_data)
        self.assertIn("window", parsed)
        self.assertIn("roadmap", parsed)
        self.assertIn("velocity", parsed)
        self.assertIn("recent_runs", parsed)

    def test_parse_agent_log_meta_sprint_rank_a_plus(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "AGENT_LOG.md"
            log_path.write_text(
                "# Autonomous Agent Worklog\n\n"
                "## [Run 085] — 2026-09-10\n"
                "- **Agent**: Senior Product Manager & Meta-Architect\n"
                "- **Phase**: Phase 0 — Senior Product Manager Meta-Improvement & System Health Sprint\n"
                "- **Task**: System Health Audit\n"
                "- **Rank A+ Meta-Improvements Formulated & Executed**:\n"
                "  - **Sovereign Interval Sweep-Line Tag Co-Occurrence Engine (`core/tags.py`)**:\n"
                "    - Replaced quadratic SQL self-join.\n"
                "  - **Authoritative WAL Checkpoint Cache Stabilization**:\n"
                "    - Added PRAGMA wal_checkpoint.\n",
                encoding="utf-8",
            )
            entries = parse_agent_log(log_path)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].run_number, 85)
            self.assertEqual(entries[0].archetype, "meta_sprint")
            self.assertTrue(len(entries[0].actions) >= 2)
            self.assertTrue(any("Interval Sweep-Line" in a for a in entries[0].actions))


    def test_generate_summary_all_nine_doctor_checks(self):
        from unittest.mock import patch
        from tools.doctor import CheckResult

        def make_mock_check(name):
            return CheckResult(name, True, f"Mock {name} OK", 0.001)

        with patch("tools.doctor.check_zero_dependencies", return_value=make_mock_check("Zero External Dependencies (AST Audit)")), \
             patch("tools.doctor.check_doc_synchronization", return_value=make_mock_check("Documentation State Sync")), \
             patch("tools.doctor.check_bash_scripts", return_value=make_mock_check("Shell Script Integrity")), \
             patch("tools.doctor.check_git_hooks", return_value=make_mock_check("Git Hook Safeguards")), \
             patch("tools.doctor.check_ci_workflows", return_value=make_mock_check("CI/CD Automation & GitHub Actions")), \
             patch("tools.doctor.check_secret_leak_prevention", return_value=make_mock_check("Secret Leak Safeguards")), \
             patch("tools.doctor.check_code_quality", return_value=make_mock_check("Code Quality (Static Linter Audit)")), \
             patch("tools.doctor.check_module_test_symmetry", return_value=make_mock_check("Module-Test Suite Symmetry")), \
             patch("tools.doctor.check_database_integrity", return_value=make_mock_check("SQLite Scripture Database")):
            report = generate_summary(window=3, run_doctor=True)
            self.assertEqual(len(report.system_health_details), 9)
            details_str = " ".join(report.system_health_details)
            self.assertIn("Zero External Dependencies", details_str)
            self.assertIn("CI/CD Automation", details_str)
            self.assertIn("Secret Leak Safeguards", details_str)
            self.assertIn("Module-Test Suite Symmetry", details_str)
            self.assertIn("SQLite Scripture Database", details_str)

    def test_active_phase_dynamic_fallback(self):
        report = generate_summary(window=1, run_doctor=False)
        md = format_markdown_report(report)
        # Verify it doesn't contain the old hardcoded Phase 5
        self.assertNotIn("Phase 5: Visual Slide Generator", md)
        self.assertIn("Phase 4, 7 & 8", md)


if __name__ == "__main__":
    unittest.main()
