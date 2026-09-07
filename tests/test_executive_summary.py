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
        report = generate_summary(window=5, run_doctor=True)
        self.assertIsInstance(report, ExecutiveReport)
        self.assertGreater(report.run_count, 0)
        self.assertGreater(report.roadmap_stats.completed_tasks, 0)
        self.assertGreater(report.estimated_runs_remaining, 0)
        md = format_markdown_report(report)
        self.assertIn("Executive Summary & Trajectory Briefing", md)
        self.assertIn("Executive Overview & Trajectory", md)
        self.assertIn("Review of Work Done", md)
        self.assertIn("Overall Project Health", md)

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

    def test_json_export(self):
        report = generate_summary(window=3, run_doctor=False)
        json_data = report.to_json()
        parsed = json.loads(json_data)
        self.assertIn("window", parsed)
        self.assertIn("roadmap", parsed)
        self.assertIn("velocity", parsed)
        self.assertIn("recent_runs", parsed)


if __name__ == "__main__":
    unittest.main()
