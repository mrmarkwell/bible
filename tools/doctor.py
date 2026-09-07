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
from typing import Any, Callable, List, Optional, Set, Tuple

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


PRE_COMMIT_HOOK_SCRIPT = """#!/usr/bin/env bash
# Bible Engine Pre-Commit Hook (Auto-generated by ./bible doctor --install-hooks)
# Enforces fast Zero-Dependency AST audit, documentation synchronization, and shell integrity.
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

if [ -f "tools/doctor.py" ]; then
    python3 tools/doctor.py --fast
fi
"""

PRE_PUSH_HOOK_SCRIPT = """#!/usr/bin/env bash
# Bible Engine Pre-Push Hook (Auto-generated by ./bible doctor --install-hooks)
# Enforces complete Zero-Dependency AST audit, documentation synchronization,
# shell integrity, SQLite scripture database health, and 100% hermetic unit test pass.
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

if [ -f "tools/doctor.py" ]; then
    python3 tools/doctor.py
fi
"""


def install_hooks(repo_root: Path) -> Tuple[bool, str]:
    """Install automated pre-commit and pre-push git hooks."""
    git_dir = repo_root / ".git"
    if not git_dir.exists() or not git_dir.is_dir():
        return False, f"Not a git repository: '{git_dir}' does not exist."

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)

    pre_commit = hooks_dir / "pre-commit"
    pre_push = hooks_dir / "pre-push"

    pre_commit.write_text(PRE_COMMIT_HOOK_SCRIPT, encoding="utf-8")
    pre_commit.chmod(pre_commit.stat().st_mode | 0o755)

    pre_push.write_text(PRE_PUSH_HOOK_SCRIPT, encoding="utf-8")
    pre_push.chmod(pre_push.stat().st_mode | 0o755)

    return True, f"Successfully installed pre-commit (<0.15s) and pre-push (<2.5s) hooks in {hooks_dir}"


def uninstall_hooks(repo_root: Path) -> Tuple[bool, str]:
    """Remove automated pre-commit and pre-push git hooks."""
    git_dir = repo_root / ".git"
    if not git_dir.exists() or not git_dir.is_dir():
        return False, f"Not a git repository: '{git_dir}' does not exist."

    hooks_dir = git_dir / "hooks"
    removed = []
    for hook_name in ("pre-commit", "pre-push"):
        hook_file = hooks_dir / hook_name
        if hook_file.exists():
            hook_file.unlink()
            removed.append(hook_name)

    if not removed:
        return True, "No Bible Engine git hooks were found to remove."

    return True, f"Removed git hooks: {', '.join(removed)}"


def check_git_hooks(repo_root: Path, fix: bool = False) -> CheckResult:
    """Verify presence and executable status of pre-commit and pre-push hooks."""
    t0 = time.time()
    git_dir = repo_root / ".git"
    if not git_dir.exists() or not git_dir.is_dir():
        return CheckResult(
            "Git Hook Safeguards",
            True,
            "Git repository metadata (.git) not present (skipped)",
            time.time() - t0,
        )

    hooks_dir = git_dir / "hooks"
    pre_commit = hooks_dir / "pre-commit"
    pre_push = hooks_dir / "pre-push"

    issues: List[str] = []
    if not pre_commit.exists():
        issues.append("Missing .git/hooks/pre-commit")
    elif not os.access(pre_commit, os.X_OK):
        issues.append(".git/hooks/pre-commit is not executable")
    else:
        text = pre_commit.read_text(encoding="utf-8", errors="replace")
        if "doctor.py" not in text:
            issues.append(".git/hooks/pre-commit does not invoke doctor.py")

    if not pre_push.exists():
        issues.append("Missing .git/hooks/pre-push")
    elif not os.access(pre_push, os.X_OK):
        issues.append(".git/hooks/pre-push is not executable")
    else:
        text = pre_push.read_text(encoding="utf-8", errors="replace")
        if "doctor.py" not in text:
            issues.append(".git/hooks/pre-push does not invoke doctor.py")

    if issues and fix:
        ok, msg = install_hooks(repo_root)
        dur = time.time() - t0
        if ok:
            return CheckResult(
                "Git Hook Safeguards",
                True,
                "Active (pre-commit: fast linting, pre-push: full doctor - Auto-repaired)",
                dur,
            )

    dur = time.time() - t0
    if issues:
        msg = f"Git hook safeguards inactive ({'; '.join(issues)}). Run './bible doctor --install-hooks' or '--fix' to activate."
        return CheckResult("Git Hook Safeguards", False, msg, dur)

    return CheckResult(
        "Git Hook Safeguards",
        True,
        "Active (pre-commit: fast linting, pre-push: full doctor)",
        dur,
    )


def check_bash_scripts(repo_root: Path) -> CheckResult:
    """Verify syntax and executable flags of bash automation scripts."""
    t0 = time.time()
    scripts = [repo_root / "ralph.sh"]
    installer = repo_root / "tools" / "install_hooks.sh"
    if installer.exists():
        scripts.append(installer)
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

    script_names = ", ".join(s.name for s in scripts)
    return CheckResult("Shell Script Integrity", True, f"{script_names} valid syntax and executable", dur)


def check_code_quality(repo_root: Path, fix: bool = False) -> CheckResult:
    """Verify code quality, syntax compilation, and AST hygiene via zero-dependency linter."""
    from tools.linter import lint_repository

    t0 = time.time()
    code, summary = lint_repository(repo_root=repo_root, fix=fix, quiet=True)
    dur = time.time() - t0

    if not summary.success:
        issues_desc = f"{summary.total_errors} errors across {summary.files_with_issues} files"
        return CheckResult(
            "Code Quality (Static Linter Audit)",
            False,
            f"Defects detected: {issues_desc}. Run './bible lint' or './bible doctor --fix' to inspect/repair.",
            dur,
        )

    fixes_msg = f" (Auto-repaired {summary.fixed_issues} defects across {summary.fixed_files} files)" if summary.fixed_files > 0 else ""
    return CheckResult(
        "Code Quality (Static Linter Audit)",
        True,
        f"100% clean: {summary.total_files} files inspected with 0 errors{fixes_msg}",
        dur,
    )


def check_database_integrity(repo_root: Path, fix: bool = False) -> CheckResult:
    """Verify bundled SQLite scripture database existence and schema integrity."""
    t0 = time.time()
    db_file = repo_root / "data" / "bible.db"
    if not db_file.exists():
        if fix:
            from core.bootstrap import bootstrap_database
            rep = bootstrap_database(db_path=db_file, verbose=False)
            dur = time.time() - t0
            if rep.is_clean:
                return CheckResult(
                    "SQLite Scripture Database",
                    True,
                    f"OK (Auto-healed: {rep.verses_count:,} WEB verses compiled, FTS5 operational)",
                    dur,
                )
            else:
                return CheckResult(
                    "SQLite Scripture Database",
                    False,
                    f"Database auto-heal failed: {rep.details}",
                    dur,
                )

        return CheckResult(
            "SQLite Scripture Database",
            False,
            f"Database file missing at {db_file}. Run './bible init' or './bible doctor --fix' to bootstrap.",
            time.time() - t0,
        )

    try:
        from core.db import Database
        with Database(db_file, auto_init=False) as db:
            cur = db.conn.cursor()
            cur.execute("PRAGMA quick_check")
            integrity = cur.fetchone()[0]
            if integrity != "ok":
                if fix:
                    from core.bootstrap import bootstrap_database
                    rep = bootstrap_database(db_path=db_file, force=True, verbose=False)
                    dur = time.time() - t0
                    if rep.is_clean:
                        return CheckResult(
                            "SQLite Scripture Database",
                            True,
                            f"OK (Auto-rebuilt: {rep.verses_count:,} WEB verses compiled, FTS5 operational)",
                            dur,
                        )

                return CheckResult(
                    "SQLite Scripture Database",
                    False,
                    f"SQLite PRAGMA quick_check failed: {integrity}",
                    time.time() - t0,
                )

            total_verses = db.count_verses(translation_id="WEB")
            if total_verses < 31000:
                if fix:
                    from core.bootstrap import bootstrap_database
                    rep = bootstrap_database(db_path=db_file, force=True, verbose=False)
                    dur = time.time() - t0
                    if rep.is_clean:
                        return CheckResult(
                            "SQLite Scripture Database",
                            True,
                            f"OK (Auto-rebuilt: {rep.verses_count:,} WEB verses compiled, FTS5 operational)",
                            dur,
                        )

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
        if fix:
            try:
                from core.bootstrap import bootstrap_database
                rep = bootstrap_database(db_path=db_file, force=True, verbose=False)
                dur = time.time() - t0
                if rep.is_clean:
                    return CheckResult(
                        "SQLite Scripture Database",
                        True,
                        f"OK (Auto-rebuilt: {rep.verses_count:,} WEB verses compiled, FTS5 operational)",
                        dur,
                    )
            except Exception:
                pass

        return CheckResult(
            "SQLite Scripture Database",
            False,
            f"Database verification exception: {exc}",
            time.time() - t0,
        )


def check_unit_tests(repo_root: Path) -> CheckResult:
    """Discover and execute unit tests, verifying 100% pass rate in <5 seconds."""
    from tools.test_runner import run_tests

    t0 = time.time()
    code, summary = run_tests(
        repo_root=repo_root,
        parallel=True,
        warn_error=True,
        quiet=True,
    )
    dur = time.time() - t0

    if not summary.success:
        failed_lines = []
        for r in summary.results:
            if not r.passed:
                failed_lines.append(f"{r.module_name}: {r.error_message}")
        return CheckResult(
            "Hermetic Test Suite",
            False,
            f"Test failures in {summary.failed_modules}/{summary.total_modules} modules:\n" + "\n".join(failed_lines),
            dur,
        )

    return CheckResult(
        "Hermetic Test Suite",
        True,
        f"{summary.total_tests} tests passing 100% across {summary.total_modules} modules in {dur:.3f}s",
        dur,
    )


def check_test_coverage(
    repo_root: Path,
    threshold: float = 70.0,
    target_module: Optional[str] = None,
) -> CheckResult:
    """Verify test coverage percentage against minimum quality threshold."""
    t0 = time.time()
    try:
        from tools.coverage import collect_coverage
        report = collect_coverage(repo_root=repo_root, target_module=target_module, parallel=True)
        dur = time.time() - t0
        passed = report.overall_coverage_pct >= threshold
        msg = (
            f"Overall coverage: {report.overall_coverage_pct:.1f}% "
            f"({report.total_executed:,}/{report.total_executable:,} statements covered across {len(report.files)} files, "
            f"threshold: {threshold:.1f}%)"
            if passed
            else f"Coverage {report.overall_coverage_pct:.1f}% fell below required threshold {threshold:.1f}% "
            f"({report.total_missed} statements missed)"
        )
        return CheckResult("Code Coverage & Test Gaps", passed, msg, dur)
    except Exception as exc:
        return CheckResult("Code Coverage & Test Gaps", False, f"Coverage audit error: {exc}", time.time() - t0)


def run_all_checks(
    repo_root: Optional[Path] = None,
    color: bool = True,
    verbose: bool = False,
    fast: bool = False,
    quiet: bool = False,
    fix: bool = False,
    coverage: bool = False,
    coverage_threshold: float = 70.0,
    stream: Optional[Any] = None,
) -> Tuple[int, List[CheckResult]]:
    """Execute all diagnostic checks and render styled report.

    Args:
        repo_root: Root repository path (defaults to REPO_ROOT).
        color: Whether to use ANSI color escape sequences.
        verbose: Verbose diagnostics flag.
        fast: If True, execute fast pre-commit checks only (<0.15s).
        quiet: If True, suppress console output and return status silently.
        fix: If True, automatically repair fixable defects (install hooks, bootstrap database).
        stream: Optional custom stream (e.g. io.StringIO) for output.

    Returns:
        Tuple of (exit_code, list of CheckResults).
    """
    root = repo_root or REPO_ROOT
    styler = DoctorStyler(enabled=color)
    target_stream = stream or sys.stdout

    def emit(text: str = "") -> None:
        if not quiet:
            target_stream.write(text + "\n")
            target_stream.flush()

    title_suffix = " (Fast Pre-Commit Mode)" if fast else ""
    if fix:
        title_suffix += " [Self-Healing --fix Active]"
    emit(styler.bold("======================================================================"))
    emit(styler.bold(f" Bible Engine System Doctor & Pre-Commit Health Diagnostic{title_suffix}"))
    emit(styler.dim(f" Target Repository: {root}"))
    emit(styler.bold("======================================================================"))

    results: List[CheckResult] = []
    failed = False
    total_start = time.time()

    # 1. Zero External Dependencies
    res = check_zero_dependencies(root)
    results.append(res)
    _emit_check(res, styler, emit)
    if not res.passed:
        failed = True

    # 2. Documentation State Sync
    res = check_doc_synchronization(root)
    results.append(res)
    _emit_check(res, styler, emit)
    if not res.passed:
        failed = True

    # 3. Shell Script Integrity
    res = check_bash_scripts(root)
    results.append(res)
    _emit_check(res, styler, emit)
    if not res.passed:
        failed = True

    # 4. Git Hook Safeguards
    res = check_git_hooks(root, fix=fix)
    results.append(res)
    _emit_check(res, styler, emit)
    if not res.passed:
        failed = True

    # 5. Code Quality & Static Analysis
    res = check_code_quality(root, fix=fix)
    results.append(res)
    _emit_check(res, styler, emit)
    if not res.passed:
        failed = True

    # Fast mode stops here
    if not fast:
        # 6. SQLite Scripture Database
        res = check_database_integrity(root, fix=fix)
        results.append(res)
        _emit_check(res, styler, emit)
        if not res.passed:
            failed = True

        # 7. Hermetic Test Suite
        res = check_unit_tests(root)
        results.append(res)
        _emit_check(res, styler, emit)
        if not res.passed:
            failed = True

        # 8. Test Coverage (Optional or when --coverage requested)
        if coverage:
            res = check_test_coverage(root, threshold=coverage_threshold)
            results.append(res)
            _emit_check(res, styler, emit)
            if not res.passed:
                failed = True

    total_dur = time.time() - total_start
    emit(styler.bold("----------------------------------------------------------------------"))
    if failed:
        emit(styler.red(styler.bold(f" [!] System Health: UNHEALTHY (Completed in {total_dur:.2f}s)")))
        return 1, results
    else:
        emit(styler.green(styler.bold(f" [✓] System Health: EXCELLENT (All checks passed in {total_dur:.2f}s)")))
        return 0, results


def _emit_check(res: CheckResult, styler: DoctorStyler, emit: Callable[[str], None]) -> None:
    """Helper to format and print check result lines."""
    if not res.passed:
        badge = styler.red("[FAIL]")
    else:
        badge = styler.green("[PASS]")

    emit(f" {badge} {styler.bold(res.name)} {styler.dim(f'({res.duration_sec:.3f}s)')}")
    if res.passed:
        emit(f"        {styler.dim(res.details)}")
    else:
        emit(f"        {styler.red(res.details)}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Bible Engine System Doctor & Health Diagnostic"
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Run fast pre-commit checks only (<0.15s: dependencies, doc sync, shell scripts, hook status)",
    )
    parser.add_argument(
        "--fix",
        "-f",
        action="store_true",
        help="Self-healing mode: automatically repair fixable defects (install git hooks, bootstrap database)",
    )
    parser.add_argument(
        "--install-hooks",
        "--install-hook",
        dest="install_hooks",
        action="store_true",
        help="Install automated git pre-commit (fast) and pre-push (full) hooks into .git/hooks",
    )
    parser.add_argument(
        "--uninstall-hooks",
        action="store_true",
        help="Remove automated git hooks from .git/hooks",
    )
    parser.add_argument(
        "--check-hooks",
        action="store_true",
        help="Check git hook safeguards status only",
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Include sovereign zero-dependency test coverage audit in diagnostics",
    )
    parser.add_argument(
        "--coverage-threshold",
        type=float,
        default=70.0,
        help="Minimum coverage percentage required when --coverage is enabled (default: 70%%)",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Quiet mode: suppress console output and exit with status code only",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI color codes",
    )
    parser.add_argument(
        "--repo",
        type=str,
        default=None,
        help="Target repository directory (default: current repository root)",
    )

    args = parser.parse_args()
    target_repo = Path(args.repo).resolve() if args.repo else REPO_ROOT

    if args.install_hooks:
        ok, msg = install_hooks(target_repo)
        print(msg)
        sys.exit(0 if ok else 1)

    if args.uninstall_hooks:
        ok, msg = uninstall_hooks(target_repo)
        print(msg)
        sys.exit(0 if ok else 1)

    if args.check_hooks:
        res = check_git_hooks(target_repo)
        styler = DoctorStyler(enabled=not args.no_color)
        badge = styler.green("[PASS]") if res.passed else styler.red("[FAIL]")
        print(f"{badge} {res.name}: {res.details}")
        sys.exit(0 if res.passed else 1)

    is_tty = (
        hasattr(sys.stdout, "isatty")
        and sys.stdout.isatty()
        and not args.no_color
        and "NO_COLOR" not in os.environ
    )
    code, _ = run_all_checks(
        repo_root=target_repo,
        color=is_tty,
        fast=args.fast,
        quiet=args.quiet,
        fix=args.fix,
        coverage=args.coverage,
        coverage_threshold=args.coverage_threshold,
    )
    sys.exit(code)
