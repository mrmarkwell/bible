#!/usr/bin/env python3
"""Sovereign Zero-Dependency Code Coverage & Test Gap Detection Engine.

Zero-dependency test coverage utility (Python 3 standard library only per ADR-003):
- Uses Python standard library bytecode inspection (`code.co_lines()`) to discover
  all executable statements across production modules (`core`, `cli`, `tools`, `web`).
- Traces test execution using `trace.Trace` across parallel worker processes.
- Computes statement coverage, missed statements, coverage percentages, and exact
  missed line intervals (e.g. '45-52, 60, 78-83').
- Provides rich ANSI terminal tables with progress bars, strict threshold enforcement
  (`--fail-under`), structured JSON export (`--json`), and standalone Sacred-Modern HTML reports (`--html`).
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Set

# Base repository root directory
REPO_ROOT = Path(__file__).resolve().parent.parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Standard production target packages/directories
DEFAULT_TARGET_DIRS = ("core", "cli", "tools", "web")


@dataclass
class FileCoverage:
    """Coverage metrics for an individual source file."""
    file_path: Path
    relative_path: str
    executable_count: int
    executed_count: int
    missed_count: int
    coverage_pct: float
    executable_lines: Set[int] = field(default_factory=set)
    executed_lines: Set[int] = field(default_factory=set)
    missed_lines: Set[int] = field(default_factory=set)
    missed_ranges: str = ""

    def to_dict(self, include_lines: bool = False) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "file": self.relative_path,
            "executable_statements": self.executable_count,
            "executed_statements": self.executed_count,
            "missed_statements": self.missed_count,
            "coverage_percent": round(self.coverage_pct, 2),
            "missed_lines_formatted": self.missed_ranges,
        }
        if include_lines:
            data["executable_lines"] = sorted(self.executable_lines)
            data["executed_lines"] = sorted(self.executed_lines)
            data["missed_lines"] = sorted(self.missed_lines)
        return data


@dataclass
class CoverageReport:
    """Aggregated coverage report across all evaluated files."""
    files: List[FileCoverage]
    total_executable: int
    total_executed: int
    total_missed: int
    overall_coverage_pct: float
    duration_sec: float
    timestamp: str = ""

    def to_dict(self, include_lines: bool = False) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "duration_sec": round(self.duration_sec, 3),
            "summary": {
                "total_files": len(self.files),
                "total_executable": self.total_executable,
                "total_executed": self.total_executed,
                "total_missed": self.total_missed,
                "overall_coverage_percent": round(self.overall_coverage_pct, 2),
            },
            "files": [f.to_dict(include_lines=include_lines) for f in self.files],
        }

    def to_json(self, indent: int = 2, include_lines: bool = False) -> str:
        return json.dumps(self.to_dict(include_lines=include_lines), indent=indent)


class CoverageStyler:
    """ANSI color formatting helper for coverage terminal output."""

    def __init__(self, enabled: bool = True) -> None:
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

    def yellow(self, text: str) -> str:
        return self._wrap("33", text)

    def red(self, text: str) -> str:
        return self._wrap("31", text)

    def cyan(self, text: str) -> str:
        return self._wrap("36", text)

    def gold(self, text: str) -> str:
        return self._wrap("38;5;214", text)

    def color_by_pct(self, pct: float, text: str) -> str:
        if pct >= 90.0:
            return self.green(text)
        elif pct >= 75.0:
            return self.yellow(text)
        return self.red(text)

    def progress_bar(self, pct: float, width: int = 10) -> str:
        filled = int(round((pct / 100.0) * width))
        filled = max(0, min(width, filled))
        empty = width - filled
        bar = "█" * filled + "░" * empty
        return self.color_by_pct(pct, f"[{bar}]")


def format_line_ranges(line_numbers: Sequence[int]) -> str:
    """Convert a sequence of line numbers into human-readable ranges.

    Examples:
        [1, 2, 3, 5, 7, 8] -> "1-3, 5, 7-8"
        [] -> ""
    """
    if not line_numbers:
        return ""
    sorted_lines = sorted(set(line_numbers))
    ranges: List[str] = []
    start = sorted_lines[0]
    prev = start
    for n in sorted_lines[1:]:
        if n == prev + 1:
            prev = n
        else:
            ranges.append(f"{start}-{prev}" if start != prev else f"{start}")
            start = n
            prev = n
    ranges.append(f"{start}-{prev}" if start != prev else f"{start}")
    return ", ".join(ranges)


def get_executable_lines(file_path: Path) -> Set[int]:
    """Extract all executable line numbers from a Python source file using bytecode inspection.

    Traverses top-level statements and all nested code objects (functions, classes, lambdas,
    generators, and comprehensions) via `code.co_lines()`.
    """
    try:
        source = file_path.read_text(encoding="utf-8")
        code = compile(source, str(file_path), "exec")
    except Exception:
        return set()

    lines: Set[int] = set()

    def _extract_from_code(co: Any) -> None:
        if hasattr(co, "co_lines"):
            for start, end, lineno in co.co_lines():
                if lineno is not None and lineno > 0:
                    lines.add(lineno)
        for const in co.co_consts:
            if hasattr(const, "co_lines"):
                _extract_from_code(const)

    _extract_from_code(code)
    return lines


def discover_target_files(
    repo_root: Path,
    target_dirs: Sequence[str] = DEFAULT_TARGET_DIRS,
    target_module: Optional[str] = None,
) -> List[Path]:
    """Discover production Python source files to audit for test coverage."""
    root = repo_root or REPO_ROOT
    all_files: List[Path] = []

    if target_module:
        cand = root / target_module
        if cand.is_file() and cand.suffix == ".py":
            return [cand]
        if cand.is_dir():
            target_dirs = [target_module]

    for d in target_dirs:
        dir_path = root / d
        if not dir_path.is_dir():
            continue
        for p in sorted(dir_path.glob("**/*.py")):
            rel_parts = p.relative_to(root).parts
            if ".git" in rel_parts or "legacy" in rel_parts or "__pycache__" in rel_parts:
                continue
            all_files.append(p)

    return all_files


def _worker_trace_module(test_module_path: str, repo_root_str: str) -> Dict[str, List[int]]:
    """Execute a single test module under `trace.Trace` in an isolated subprocess.

    Returns:
        Mapping of relative_file_path -> list of executed line numbers.
    """
    repo_root = Path(repo_root_str)
    test_path = Path(test_module_path)
    if not test_path.is_absolute():
        test_path = repo_root / test_path

    worker_script = f"""
import sys, os, trace, unittest, json
from pathlib import Path

repo_root = Path({repo_root_str!r})
sys.path.insert(0, str(repo_root))

stdlib_dir = os.path.dirname(os.__file__)
tracer = trace.Trace(count=1, trace=0, ignoredirs=[stdlib_dir])

test_file = {str(test_path.relative_to(repo_root))!r}
mod_name = test_file.replace("/", ".").replace("\\\\", ".").removesuffix(".py")

def run():
    suite = unittest.defaultTestLoader.loadTestsFromName(mod_name)
    runner = unittest.TextTestRunner(verbosity=0)
    runner.run(suite)

tracer.runfunc(run)
res = tracer.results()
executed = {{}}
for (fname, lineno), cnt in res.counts.items():
    if fname.startswith(str(repo_root)) and "tests" not in fname and ".git" not in fname and "legacy" not in fname:
        try:
            rel = os.path.relpath(fname, str(repo_root))
            executed.setdefault(rel, []).append(lineno)
        except ValueError:
            pass

print("COVERAGE_STREAM:" + json.dumps(executed))
"""

    env = os.environ.copy()
    env["PYTHONPATH"] = repo_root_str
    env["TERM"] = "dumb"

    try:
        proc = subprocess.run(
            [sys.executable, "-c", worker_script],
            cwd=repo_root_str,
            capture_output=True,
            text=True,
            timeout=120.0,
            env=env,
        )
        for line in proc.stdout.splitlines():
            if line.startswith("COVERAGE_STREAM:"):
                return json.loads(line[len("COVERAGE_STREAM:"):])
    except Exception:
        pass

    return {}


def collect_coverage(
    repo_root: Optional[Path] = None,
    test_pattern: Optional[str] = None,
    target_module: Optional[str] = None,
    parallel: bool = True,
    jobs: Optional[int] = None,
) -> CoverageReport:
    """Collect test coverage by executing tests and tracking line execution."""
    root = repo_root or REPO_ROOT
    t0 = time.time()

    # 1. Discover target source files
    target_files = discover_target_files(root, target_module=target_module)

    # Precompute executable lines for all target files
    file_executable_map: Dict[str, Set[int]] = {}
    for f in target_files:
        rel = str(f.relative_to(root))
        file_executable_map[rel] = get_executable_lines(f)

    # 2. Discover test files
    tests_dir = root / "tests"
    test_files: List[Path] = sorted(tests_dir.glob("test_*.py"))
    if test_pattern:
        patterns = [p.strip() for p in test_pattern.split(",") if p.strip()]
        filtered: List[Path] = []
        for tf in test_files:
            for p in patterns:
                if "*" in p or "?" in p:
                    if tf.match(p):
                        filtered.append(tf)
                        break
                elif p.lower() in tf.name.lower() or p.lower() in tf.stem.lower():
                    filtered.append(tf)
                    break
        test_files = filtered

    # 3. Execute tests under trace
    executed_map: Dict[str, Set[int]] = {rel: set() for rel in file_executable_map}

    if parallel and len(test_files) > 1:
        worker_count = jobs or os.cpu_count() or 4
        with ProcessPoolExecutor(max_workers=worker_count) as executor:
            futures = [
                executor.submit(_worker_trace_module, str(tf.relative_to(root)), str(root))
                for tf in test_files
            ]
            for fut in as_completed(futures):
                res = fut.result()
                for rel_path, lnos in res.items():
                    if rel_path in executed_map:
                        executed_map[rel_path].update(lnos)
    else:
        for tf in test_files:
            res = _worker_trace_module(str(tf.relative_to(root)), str(root))
            for rel_path, lnos in res.items():
                if rel_path in executed_map:
                    executed_map[rel_path].update(lnos)

    dur = time.time() - t0

    # 4. Build FileCoverage records
    file_coverages: List[FileCoverage] = []
    total_exec = 0
    total_covered = 0
    total_miss = 0

    for f in target_files:
        rel = str(f.relative_to(root))
        exec_lines = file_executable_map.get(rel, set())
        covered_lines = executed_map.get(rel, set()) & exec_lines
        missed_lines = exec_lines - covered_lines

        exec_count = len(exec_lines)
        cov_count = len(covered_lines)
        miss_count = len(missed_lines)

        pct = (cov_count / exec_count * 100.0) if exec_count > 0 else 100.0

        total_exec += exec_count
        total_covered += cov_count
        total_miss += miss_count

        file_coverages.append(
            FileCoverage(
                file_path=f,
                relative_path=rel,
                executable_count=exec_count,
                executed_count=cov_count,
                missed_count=miss_count,
                coverage_pct=pct,
                executable_lines=exec_lines,
                executed_lines=covered_lines,
                missed_lines=missed_lines,
                missed_ranges=format_line_ranges(sorted(missed_lines)),
            )
        )

    file_coverages.sort(key=lambda item: item.relative_path)
    overall_pct = (total_covered / total_exec * 100.0) if total_exec > 0 else 100.0
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")

    return CoverageReport(
        files=file_coverages,
        total_executable=total_exec,
        total_executed=total_covered,
        total_missed=total_miss,
        overall_coverage_pct=overall_pct,
        duration_sec=dur,
        timestamp=now_str,
    )


def format_terminal_table(
    report: CoverageReport,
    color: bool = True,
    show_missed_only: bool = False,
    max_missed_width: int = 35,
) -> str:
    """Format the coverage report as an elegant, high-contrast ANSI terminal table."""
    styler = CoverageStyler(enabled=color)
    lines: List[str] = []

    lines.append(styler.gold("=" * 80))
    lines.append(
        styler.bold(
            f" Bible Engine Test Coverage Report — {report.timestamp} ({report.duration_sec:.2f}s)"
        )
    )
    lines.append(styler.gold("=" * 80))

    col_file = "File"
    col_stmts = "Stmts"
    col_miss = "Miss"
    col_cover = "Cover"
    col_bar = "Bar"
    col_missing = "Missing Lines"

    hdr = (
        f" {col_file:<28} {col_stmts:>6} {col_miss:>6} {col_cover:>7}  {col_bar:<12} {col_missing}"
    )
    lines.append(styler.bold(hdr))
    lines.append(styler.dim("-" * 80))

    displayed_files = (
        [f for f in report.files if f.missed_count > 0] if show_missed_only else report.files
    )

    for fc in displayed_files:
        pct_str = f"{fc.coverage_pct:>5.1f}%"
        colored_pct = styler.color_by_pct(fc.coverage_pct, pct_str)
        bar = styler.progress_bar(fc.coverage_pct, width=10)

        missed_str = fc.missed_ranges
        if len(missed_str) > max_missed_width:
            missed_str = missed_str[: max_missed_width - 3] + "..."

        row = (
            f" {fc.relative_path:<28} "
            f"{fc.executable_count:>6} "
            f"{fc.missed_count:>6} "
            f"{colored_pct}  "
            f"{bar} "
            f"{styler.dim(missed_str)}"
        )
        lines.append(row)

    lines.append(styler.dim("-" * 80))

    tot_pct_str = f"{report.overall_coverage_pct:>5.1f}%"
    tot_colored = styler.color_by_pct(report.overall_coverage_pct, tot_pct_str)
    tot_bar = styler.progress_bar(report.overall_coverage_pct, width=10)

    total_row = (
        f" {styler.bold('TOTAL'):<28} "
        f"{report.total_executable:>6} "
        f"{report.total_missed:>6} "
        f"{tot_colored}  "
        f"{tot_bar} "
        f"{styler.dim('All statements')}"
    )
    lines.append(total_row)
    lines.append(styler.gold("=" * 80))

    return "\n".join(lines)


def generate_html_report(report: CoverageReport, output_path: Path) -> None:
    """Generate a self-contained Sacred-Modern HTML coverage report with line highlighting."""
    file_rows_html: List[str] = []
    for fc in report.files:
        pct = fc.coverage_pct
        badge_class = "pct-high" if pct >= 90 else ("pct-med" if pct >= 75 else "pct-low")
        file_rows_html.append(f"""
        <tr>
            <td class="file-name">{fc.relative_path}</td>
            <td class="num">{fc.executable_count}</td>
            <td class="num">{fc.executed_count}</td>
            <td class="num">{fc.missed_count}</td>
            <td class="pct {badge_class}">{pct:.1f}%</td>
            <td class="ranges">{fc.missed_ranges or '—'}</td>
        </tr>
        """)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bible Engine — Test Coverage Report</title>
<style>
    :root {{
        --bg: #0D0E11;
        --card: #15181E;
        --border: #232730;
        --gold: #D4AF37;
        --text: #E5E7EB;
        --muted: #9CA3AF;
        --green: #10B981;
        --yellow: #F59E0B;
        --red: #EF4444;
    }}
    body {{
        background: var(--bg);
        color: var(--text);
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        margin: 0;
        padding: 24px;
    }}
    .container {{
        max-width: 1200px;
        margin: 0 auto;
    }}
    header {{
        border-bottom: 2px solid var(--gold);
        padding-bottom: 16px;
        margin-bottom: 24px;
    }}
    h1 {{
        margin: 0 0 8px 0;
        color: var(--gold);
        font-size: 28px;
        letter-spacing: -0.5px;
    }}
    .meta {{
        color: var(--muted);
        font-size: 14px;
    }}
    .kpi-row {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 16px;
        margin-bottom: 24px;
    }}
    .kpi-card {{
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 16px;
    }}
    .kpi-label {{
        font-size: 12px;
        text-transform: uppercase;
        color: var(--muted);
        letter-spacing: 0.5px;
    }}
    .kpi-val {{
        font-size: 32px;
        font-weight: 700;
        margin-top: 4px;
    }}
    .table-card {{
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 8px;
        overflow: hidden;
    }}
    table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 14px;
    }}
    th, td {{
        padding: 12px 16px;
        text-align: left;
        border-bottom: 1px solid var(--border);
    }}
    th {{
        background: rgba(255, 255, 255, 0.02);
        color: var(--muted);
        font-weight: 600;
        text-transform: uppercase;
        font-size: 11px;
    }}
    .num {{
        text-align: right;
        font-family: monospace;
    }}
    .pct {{
        text-align: right;
        font-weight: 700;
        font-family: monospace;
    }}
    .pct-high {{ color: var(--green); }}
    .pct-med {{ color: var(--yellow); }}
    .pct-low {{ color: var(--red); }}
    .ranges {{
        color: var(--muted);
        font-family: monospace;
        font-size: 12px;
    }}
    .file-name {{
        font-family: monospace;
        font-weight: 600;
    }}
</style>
</head>
<body>
<div class="container">
    <header>
        <h1>Bible Engine — Test Coverage Report</h1>
        <div class="meta">Generated: {report.timestamp} | Execution Duration: {report.duration_sec:.2f}s</div>
    </header>

    <div class="kpi-row">
        <div class="kpi-card">
            <div class="kpi-label">Overall Coverage</div>
            <div class="kpi-val pct-high">{report.overall_coverage_pct:.1f}%</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Executable Statements</div>
            <div class="kpi-val">{report.total_executable:,}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Executed Statements</div>
            <div class="kpi-val" style="color: var(--green);">{report.total_executed:,}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Missed Statements</div>
            <div class="kpi-val" style="color: var(--red);">{report.total_missed:,}</div>
        </div>
    </div>

    <div class="table-card">
        <table>
            <thead>
                <tr>
                    <th>File</th>
                    <th class="num">Stmts</th>
                    <th class="num">Exec</th>
                    <th class="num">Miss</th>
                    <th class="num">Coverage</th>
                    <th>Missing Lines</th>
                </tr>
            </thead>
            <tbody>
                {''.join(file_rows_html)}
            </tbody>
        </table>
    </div>
</div>
</body>
</html>
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_content, encoding="utf-8")


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI execution entry point for code coverage analyzer."""
    parser = argparse.ArgumentParser(
        description="Sovereign Zero-Dependency Code Coverage & Test Gap Detection Engine.",
    )
    parser.add_argument(
        "-p",
        "--pattern",
        type=str,
        default=None,
        help="Filter test modules by pattern (e.g. 'test_render' or '*crypto*')",
    )
    parser.add_argument(
        "-m",
        "--module",
        type=str,
        default=None,
        help="Limit audit to specific module or directory (e.g. 'core' or 'core/render.py')",
    )
    parser.add_argument(
        "-s",
        "--sequential",
        action="store_true",
        help="Run test tracing sequentially instead of parallel",
    )
    parser.add_argument(
        "-j",
        "--jobs",
        type=int,
        default=None,
        help="Number of concurrent worker processes",
    )
    parser.add_argument(
        "--fail-under",
        "--threshold",
        dest="threshold",
        type=float,
        default=None,
        help="Fail with exit code 1 if total coverage is under threshold percentage",
    )
    parser.add_argument(
        "-u",
        "--uncovered",
        "--missed",
        dest="missed_only",
        action="store_true",
        help="Only display files with missed statements in table",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output coverage report in structured JSON format",
    )
    parser.add_argument(
        "--html",
        type=str,
        default=None,
        help="Generate standalone Sacred-Modern HTML coverage report at specified path",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress terminal table output",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI terminal colors",
    )

    args = parser.parse_args(argv)

    is_tty = (
        hasattr(sys.stdout, "isatty")
        and sys.stdout.isatty()
        and not args.no_color
        and "NO_COLOR" not in os.environ
    )

    report = collect_coverage(
        repo_root=REPO_ROOT,
        test_pattern=args.pattern,
        target_module=args.module,
        parallel=not args.sequential,
        jobs=args.jobs,
    )

    if args.html:
        generate_html_report(report, Path(args.html).resolve())

    if args.json:
        print(report.to_json(indent=2))
    elif not args.quiet:
        print(
            format_terminal_table(
                report,
                color=is_tty,
                show_missed_only=args.missed_only,
            )
        )
        if args.html:
            print(f"\n[HTML Report] Saved to {Path(args.html).resolve()}")

    if args.threshold is not None:
        if report.overall_coverage_pct < args.threshold:
            sys.stderr.write(
                f"\nERROR: Overall coverage {report.overall_coverage_pct:.1f}% is below required threshold of {args.threshold:.1f}%\n"
            )
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
