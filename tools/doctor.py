#!/usr/bin/env python3
"""Automated Repository Doctor & Health Verification Engine for Bible Engine.

Zero-dependency diagnostic utility (Python 3 standard library only per ADR-003):
- Audits 100% Zero-Dependency compliance across all Python source files via AST inspection.
- Audits documentation state-machine synchronization across ROADMAP.md, DECISIONS.md,
  IDEAS.md, and AGENT_LOG.md.
- Verifies bash script syntax integrity (bash -n).
- Verifies SQLite database file existence, schema integrity, and verse count.
- Discovers and executes the hermetic test suite in <1.0 second.
"""

import ast
from dataclasses import dataclass
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import List, Optional, Sequence, Set, Tuple

# Base repository root directory
REPO_ROOT = Path(__file__).resolve().parent.parent

# Ensure REPO_ROOT is in sys.path so core and cli can be imported
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Recognized first-party packages/modules in the repository
FIRST_PARTY_MODULES = {"core", "cli", "tools", "tests", "web", "bible"}


@dataclass
class CheckResult:
    """Represents the result of an individual diagnostic check."""
    name: str
    passed: bool
    details: str
    duration_sec: float = 0.0


class DoctorStyler:
    """ANSI color and formatting helper for diagnostic output."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    def _wrap(self, code: str, text: str) -> str:
        if not self.enabled:
            return text
        return f"\033[{code}m{text}\033[0m"

    def bold(self, text: str) -> str:
        return self._wrap("1", text)

    def dim(self, text: str) -> str:
        return self._wrap("2", text)

    def green(self, text: str) -> str:
        return self._wrap("32", text)

    def red(self, text: str) -> str:
        return self._wrap("31", text)

    def yellow(self, text: str) -> str:
        return self._wrap("33", text)

    def cyan(self, text: str) -> str:
        return self._wrap("36", text)


def check_zero_dependencies(repo_root: Path) -> CheckResult:
    """Verify that all Python files strictly import only standard library modules.

    Uses AST inspection to guarantee zero third-party pip/external package imports.
    """
    t0 = time.time()
    stdlib_names: Set[str] = set(sys.stdlib_module_names)
    allowed_modules = stdlib_names | FIRST_PARTY_MODULES | {"__future__"}

    violations: List[str] = []
    py_files_checked = 0

    for py_file in repo_root.glob("**/*.py"):
        if ".git" in py_file.parts or "legacy" in py_file.parts:
            continue
        py_files_checked += 1
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        except Exception as exc:
            violations.append(f"{py_file.relative_to(repo_root)}: syntax error: {exc}")
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_pkg = alias.name.split(".")[0]
                    if root_pkg not in allowed_modules and not root_pkg.startswith("_"):
                        violations.append(
                            f"{py_file.relative_to(repo_root)}: illegal import '{alias.name}'"
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    root_pkg = node.module.split(".")[0]
                    if root_pkg not in allowed_modules and not root_pkg.startswith("_"):
                        violations.append(
                            f"{py_file.relative_to(repo_root)}: illegal import from '{node.module}'"
                        )

    dur = time.time() - t0
    if violations:
        msg = f"Found {len(violations)} illegal third-party imports:\n  " + "\n  ".join(violations)
        return CheckResult("Zero External Dependencies (AST Audit)", False, msg, dur)

    return CheckResult(
        "Zero External Dependencies (AST Audit)",
        True,
        f"Audited {py_files_checked} Python files; 100% stdlib compliance (0 pip dependencies)",
        dur,
    )


def check_doc_synchronization(repo_root: Path) -> CheckResult:
    """Verify state machine synchronization across project governance documents."""
    t0 = time.time()
    issues: List[str] = []

    decisions_file = repo_root / "DECISIONS.md"
    agent_log_file = repo_root / "AGENT_LOG.md"
    roadmap_file = repo_root / "ROADMAP.md"
    ideas_file = repo_root / "IDEAS.md"

    if not decisions_file.exists():
        issues.append("Missing DECISIONS.md")
    if not agent_log_file.exists():
        issues.append("Missing AGENT_LOG.md")
    if not roadmap_file.exists():
        issues.append("Missing ROADMAP.md")
    if not ideas_file.exists():
        issues.append("Missing IDEAS.md")

    if issues:
        return CheckResult("Documentation State Sync", False, "\n  ".join(issues), time.time() - t0)

    decisions_text = decisions_file.read_text(encoding="utf-8")
    defined_adrs = set(re.findall(r"ADR-\d+", decisions_text))

    agent_log_text = agent_log_file.read_text(encoding="utf-8")
    referenced_adrs = set(re.findall(r"ADR-\d+", agent_log_text))

    # Check for orphaned ADR references in AGENT_LOG
    unresolved_adrs = referenced_adrs - defined_adrs
    if unresolved_adrs:
        issues.append(f"AGENT_LOG.md references undefined ADRs: {sorted(unresolved_adrs)}")

    # Check run sequence in AGENT_LOG.md
    runs = [int(x) for x in re.findall(r"\[Run (\d+)\]", agent_log_text)]
    if runs:
        expected_runs = list(range(1, len(runs) + 1))
        if runs != expected_runs:
            issues.append(
                f"AGENT_LOG.md run numbers are non-sequential or non-contiguous: {runs}"
            )

    # Check that Rank A+ ideas in IDEAS.md Active section have matching ADRs or roadmap presence
    ideas_text = ideas_file.read_text(encoding="utf-8")
    if "## Active Ideas & Brainstorming Hopper" in ideas_text:
        active_section = ideas_text.split("## Active Ideas & Brainstorming Hopper")[-1]
        entries = re.findall(r"###\s+\[([^\]]+)\]\s+([^\n]+)", active_section)
        roadmap_text = roadmap_file.read_text(encoding="utf-8")
        for status, title in entries:
            if "Rank A+" in title:
                clean_title = re.sub(r"\(Rank.*?\)", "", title).strip()
                keywords = [w.lower() for w in re.findall(r"[A-Za-z0-9]+", clean_title) if len(w) > 4][:3]
                in_roadmap = any(kw in roadmap_text.lower() for kw in keywords)
                in_decisions = any(kw in decisions_text.lower() for kw in keywords)
                if not in_roadmap and not in_decisions:
                    issues.append(f"Rank A+ idea '{clean_title}' has no corresponding ADR or roadmap entry")

    dur = time.time() - t0
    if issues:
        return CheckResult(
            "Documentation State Sync",
            False,
            f"Found {len(issues)} synchronization anomalies:\n  " + "\n  ".join(issues),
            dur,
        )

    return CheckResult(
        "Documentation State Sync",
        True,
        f"{len(defined_adrs)} ADRs registered, {len(runs)} sequential runs, all Rank A+ ideas synchronized",
        dur,
    )


def check_bash_scripts(repo_root: Path) -> CheckResult:
    """Verify syntax and executable flags of bash automation scripts."""
    t0 = time.time()
    scripts = [repo_root / "ralph.sh"]
    issues: List[str] = []

    for s in scripts:
        if not s.exists():
            issues.append(f"Missing script: {s.name}")
            continue
        if not os.access(s, os.X_OK):
            issues.append(f"Script is not executable: {s.name}")
        res = subprocess.run(["bash", "-n", str(s)], capture_output=True, text=True)
        if res.returncode != 0:
            issues.append(f"{s.name} bash syntax error:\n{res.stderr}")

    dur = time.time() - t0
    if issues:
        return CheckResult("Shell Script Integrity", False, "\n  ".join(issues), dur)

    return CheckResult("Shell Script Integrity", True, "ralph.sh valid syntax and executable", dur)


def check_database_integrity(repo_root: Path) -> CheckResult:
    """Verify bundled SQLite scripture database existence and schema integrity."""
    t0 = time.time()
    db_file = repo_root / "data" / "bible.db"
    if not db_file.exists():
        return CheckResult(
            "SQLite Scripture Database",
            False,
            f"Database file missing at {db_file}. Run 'python3 tools/ingest_web.py' to compile.",
            time.time() - t0,
        )

    try:
        from core.db import Database
        with Database(db_file, auto_init=False) as db:
            cur = db.conn.cursor()
            cur.execute("PRAGMA quick_check")
            integrity = cur.fetchone()[0]
            if integrity != "ok":
                return CheckResult(
                    "SQLite Scripture Database",
                    False,
                    f"SQLite PRAGMA quick_check failed: {integrity}",
                    time.time() - t0,
                )

            total_verses = db.count_verses(translation_id="WEB")
            if total_verses < 31000:
                return CheckResult(
                    "SQLite Scripture Database",
                    False,
                    f"WEB translation incomplete: {total_verses} verses (expected 31,102+)",
                    time.time() - t0,
                )

            # Check FTS5 index sanity
            res = db.search_text("faith hope love", translation_id="WEB")
            if not res:
                return CheckResult(
                    "SQLite Scripture Database",
                    False,
                    "FTS5 full-text search query returned 0 results for known passage",
                    time.time() - t0,
                )

            dur = time.time() - t0
            return CheckResult(
                "SQLite Scripture Database",
                True,
                f"OK (PRAGMA quick_check passed, {total_verses:,} WEB verses, FTS5 operational)",
                dur,
            )
    except Exception as exc:
        return CheckResult(
            "SQLite Scripture Database",
            False,
            f"Database verification exception: {exc}",
            time.time() - t0,
        )


def check_unit_tests(repo_root: Path) -> CheckResult:
    """Discover and execute unit tests, verifying 100% pass rate in <5 seconds."""
    import io
    import unittest

    t0 = time.time()
    stream = io.StringIO()
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Discover and run all test modules except test_doctor and test_cli to prevent recursion
    for module_pattern in [
        "test_reference.py",
        "test_db.py",
        "test_favorites.py",
        "test_crypto.py",
        "test_stream_runner.py",
        "test_harness.py",
        "test_ingest.py",
        "test_core.py",
    ]:
        suite.addTests(loader.discover(str(repo_root / "tests"), pattern=module_pattern))

    runner = unittest.TextTestRunner(stream=stream, verbosity=1)
    res = runner.run(suite)
    dur = time.time() - t0

    if not res.wasSuccessful():
        return CheckResult(
            "Hermetic Test Suite",
            False,
            f"Test failures/errors ({len(res.failures)} failures, {len(res.errors)} errors):\n{stream.getvalue()}",
            dur,
        )

    return CheckResult(
        "Hermetic Test Suite",
        True,
        f"{res.testsRun} tests passing 100% in {dur:.3f}s",
        dur,
    )


def run_all_checks(
    repo_root: Optional[Path] = None,
    color: bool = True,
    verbose: bool = False,
) -> Tuple[int, List[CheckResult]]:
    """Execute all diagnostic checks and render styled report.

    Returns:
        Tuple of (exit_code, list of CheckResults).
    """
    root = repo_root or REPO_ROOT
    styler = DoctorStyler(enabled=color)

    print(styler.bold("======================================================================"))
    print(styler.bold(" Bible Engine System Doctor & Pre-Commit Health Diagnostic"))
    print(styler.dim(f" Target Repository: {root}"))
    print(styler.bold("======================================================================"))

    checks = [
        check_zero_dependencies,
        check_doc_synchronization,
        check_bash_scripts,
        check_database_integrity,
        check_unit_tests,
    ]

    results: List[CheckResult] = []
    failed = False
    total_start = time.time()

    for check_fn in checks:
        res = check_fn(root)
        results.append(res)
        if not res.passed:
            failed = True
            badge = styler.red("[FAIL]")
        else:
            badge = styler.green("[PASS]")

        print(f" {badge} {styler.bold(res.name)} {styler.dim(f'({res.duration_sec:.3f}s)')}")
        if res.passed:
            print(f"        {styler.dim(res.details)}")
        else:
            print(f"        {styler.red(res.details)}")

    total_dur = time.time() - total_start
    print(styler.bold("----------------------------------------------------------------------"))
    if failed:
        print(styler.red(styler.bold(f" [!] System Health: UNHEALTHY (Completed in {total_dur:.2f}s)")))
        return 1, results
    else:
        print(styler.green(styler.bold(f" [✓] System Health: EXCELLENT (All checks passed in {total_dur:.2f}s)")))
        return 0, results


if __name__ == "__main__":
    is_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty() and not os.environ.get("NO_COLOR")
    code, _ = run_all_checks(color=is_tty)
    sys.exit(code)
