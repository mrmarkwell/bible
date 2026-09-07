#!/usr/bin/env python3
"""Sovereign Zero-Dependency Performance Benchmark Engine & Regression Guard.

Part of Bible Engine (Python 3 standard library only per ADR-003).
Provides high-resolution statistical benchmarking across all critical engine workloads:
- Canonical scripture reference parsing (single, spans, cross-chapter, typos)
- SQLite database verse access, range queries, and FTS5 full-text indexing
- Cryptographic throughput (ChaCha20 keystream, PBKDF2-HMAC authenticated packs)
- Sacred-Modern 4K SVG slide rendering
- Static AST linter analysis and code hygiene
- Crossway-compliant 500-verse LRU cache operations

Features:
- High-precision nanosecond timing via `time.perf_counter_ns()`
- Statistical sampling: Mean, Median, Min, Max, Standard Deviation, p90, p99, Ops/sec
- Baseline persistence and automated regression detection (--fail-regression N%)
- Sacred-Modern ANSI terminal dashboard with delta indicators
- Standalone zero-dependency HTML report export (--html)
- JSON export for CI/CD and automated telemetry (--json)
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
import math
import os
from pathlib import Path
import platform
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

# Base repository root directory
REPO_ROOT = Path(__file__).resolve().parent.parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_BASELINE_PATH = REPO_ROOT / ".benchmark_baseline.json"


@dataclass
class BenchmarkResult:
    """Statistical measurement for a single benchmark workload."""

    name: str
    category: str
    description: str
    iterations: int
    warmup_rounds: int
    durations_ns: List[int] = field(default_factory=list, repr=False)
    mean_ns: float = 0.0
    median_ns: float = 0.0
    min_ns: float = 0.0
    max_ns: float = 0.0
    stddev_ns: float = 0.0
    p90_ns: float = 0.0
    p99_ns: float = 0.0
    ops_per_sec: float = 0.0
    throughput_mb_s: Optional[float] = None
    unit: str = "ops/s"
    baseline_mean_ns: Optional[float] = None
    delta_pct: Optional[float] = None  # Positive = faster, Negative = slower
    is_regression: bool = False

    def to_dict(self, include_raw: bool = False) -> Dict[str, Any]:
        d = {
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "iterations": self.iterations,
            "warmup_rounds": self.warmup_rounds,
            "mean_ns": round(self.mean_ns, 2),
            "median_ns": round(self.median_ns, 2),
            "min_ns": round(self.min_ns, 2),
            "max_ns": round(self.max_ns, 2),
            "stddev_ns": round(self.stddev_ns, 2),
            "p90_ns": round(self.p90_ns, 2),
            "p99_ns": round(self.p99_ns, 2),
            "ops_per_sec": round(self.ops_per_sec, 2),
            "unit": self.unit,
        }
        if self.throughput_mb_s is not None:
            d["throughput_mb_s"] = round(self.throughput_mb_s, 2)
        if self.baseline_mean_ns is not None:
            d["baseline_mean_ns"] = round(self.baseline_mean_ns, 2)
        if self.delta_pct is not None:
            d["delta_pct"] = round(self.delta_pct, 2)
        d["is_regression"] = self.is_regression
        if include_raw:
            d["durations_ns"] = self.durations_ns
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BenchmarkResult:
        return cls(
            name=data["name"],
            category=data["category"],
            description=data.get("description", ""),
            iterations=data.get("iterations", 0),
            warmup_rounds=data.get("warmup_rounds", 0),
            durations_ns=data.get("durations_ns", []),
            mean_ns=float(data.get("mean_ns", 0.0)),
            median_ns=float(data.get("median_ns", 0.0)),
            min_ns=float(data.get("min_ns", 0.0)),
            max_ns=float(data.get("max_ns", 0.0)),
            stddev_ns=float(data.get("stddev_ns", 0.0)),
            p90_ns=float(data.get("p90_ns", 0.0)),
            p99_ns=float(data.get("p99_ns", 0.0)),
            ops_per_sec=float(data.get("ops_per_sec", 0.0)),
            throughput_mb_s=float(data["throughput_mb_s"]) if "throughput_mb_s" in data and data["throughput_mb_s"] is not None else None,
            unit=data.get("unit", "ops/s"),
            baseline_mean_ns=float(data["baseline_mean_ns"]) if "baseline_mean_ns" in data and data["baseline_mean_ns"] is not None else None,
            delta_pct=float(data["delta_pct"]) if "delta_pct" in data and data["delta_pct"] is not None else None,
            is_regression=bool(data.get("is_regression", False)),
        )


@dataclass
class BenchmarkSuiteResult:
    """Container for complete benchmark run results across all workloads."""

    results: List[BenchmarkResult] = field(default_factory=list)
    total_duration_sec: float = 0.0
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()))
    platform_info: str = field(default_factory=lambda: f"{platform.system()} {platform.release()} ({platform.machine()})")
    python_version: str = field(default_factory=lambda: platform.python_version())
    baseline_path: Optional[str] = None
    regression_threshold_pct: Optional[float] = None
    regressions: List[BenchmarkResult] = field(default_factory=list)

    def to_dict(self, include_raw: bool = False) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "platform": self.platform_info,
            "python_version": self.python_version,
            "total_duration_sec": round(self.total_duration_sec, 3),
            "baseline_path": self.baseline_path,
            "regression_threshold_pct": self.regression_threshold_pct,
            "total_benchmarks": len(self.results),
            "regression_count": len(self.regressions),
            "results": [r.to_dict(include_raw=include_raw) for r in self.results],
        }

    def to_json(self, indent: int = 2, include_raw: bool = False) -> str:
        return json.dumps(self.to_dict(include_raw=include_raw), indent=indent)


class BenchmarkStyler:
    """ANSI terminal formatter with high-contrast Sacred-Modern color palette."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled and sys.stdout.isatty() and "NO_COLOR" not in os.environ

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

    def magenta(self, text: str) -> str:
        return self._wrap("35", text)

    def format_latency(self, ns: float) -> str:
        """Format nanoseconds into human-friendly time units."""
        if ns < 1_000:
            return f"{ns:.1f} ns"
        elif ns < 1_000_000:
            return f"{ns / 1_000:.2f} µs"
        elif ns < 1_000_000_000:
            return f"{ns / 1_000_000:.2f} ms"
        else:
            return f"{ns / 1_000_000_000:.3f} s"

    def format_throughput(self, ops_sec: float, unit: str = "ops/s") -> str:
        """Format operations per second with SI prefixes."""
        if ops_sec >= 1_000_000:
            return f"{ops_sec / 1_000_000:.2f} M {unit}"
        elif ops_sec >= 1_000:
            return f"{ops_sec / 1_000:.2f} k {unit}"
        else:
            return f"{ops_sec:.1f} {unit}"

    def format_delta(self, delta_pct: Optional[float], is_regression: bool) -> str:
        """Format performance delta vs baseline."""
        if delta_pct is None:
            return self.dim("—")
        if is_regression:
            return self.red(self.bold(f"▼ {abs(delta_pct):.1f}% SLOWER"))
        elif delta_pct > 5.0:
            return self.green(f"▲ {delta_pct:+.1f}% faster")
        elif delta_pct < -5.0:
            return self.yellow(f"▼ {abs(delta_pct):.1f}% slower")
        else:
            return self.dim(f"~ {delta_pct:+.1f}%")


def compute_statistics(
    durations_ns: List[int],
    bytes_per_op: Optional[int] = None,
) -> Tuple[float, float, float, float, float, float, float, float, Optional[float]]:
    """Compute comprehensive statistical metrics from a list of duration samples."""
    if not durations_ns:
        return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, None)

    n = len(durations_ns)
    sorted_d = sorted(durations_ns)
    mean_val = sum(durations_ns) / n

    # Median
    if n % 2 == 1:
        median_val = float(sorted_d[n // 2])
    else:
        median_val = (sorted_d[n // 2 - 1] + sorted_d[n // 2]) / 2.0

    min_val = float(sorted_d[0])
    max_val = float(sorted_d[-1])

    # Standard deviation
    if n > 1:
        variance = sum((x - mean_val) ** 2 for x in durations_ns) / (n - 1)
        stddev_val = math.sqrt(variance)
    else:
        stddev_val = 0.0

    # Percentiles (nearest rank method)
    p90_idx = max(0, min(n - 1, int(math.ceil(0.90 * n)) - 1))
    p99_idx = max(0, min(n - 1, int(math.ceil(0.99 * n)) - 1))
    p90_val = float(sorted_d[p90_idx])
    p99_val = float(sorted_d[p99_idx])

    # Operations per second based on mean duration
    ops_sec = (1_000_000_000.0 / mean_val) if mean_val > 0 else 0.0

    # Throughput in MB/s if byte count provided
    throughput_mb_s = None
    if bytes_per_op and bytes_per_op > 0 and mean_val > 0:
        bytes_sec = (bytes_per_op * 1_000_000_000.0) / mean_val
        throughput_mb_s = bytes_sec / (1024.0 * 1024.0)

    return (
        mean_val,
        median_val,
        min_val,
        max_val,
        stddev_val,
        p90_val,
        p99_val,
        ops_sec,
        throughput_mb_s,
    )


# ---------------------------------------------------------------------------
# Benchmark Workload Definitions & Registry
# ---------------------------------------------------------------------------

@dataclass
class BenchmarkTask:
    """Specification for an executable benchmark workload."""

    name: str
    category: str
    description: str
    func: Callable[[], Any]
    default_iterations: int = 100
    default_warmup: int = 10
    bytes_per_op: Optional[int] = None
    unit: str = "ops/s"


BENCHMARK_REGISTRY: List[BenchmarkTask] = []


def register_benchmark(
    name: str,
    category: str,
    description: str,
    default_iterations: int = 100,
    default_warmup: int = 10,
    bytes_per_op: Optional[int] = None,
    unit: str = "ops/s",
) -> Callable[[Callable[[], Any]], Callable[[], Any]]:
    """Decorator to register a benchmark task into the registry."""

    def decorator(fn: Callable[[], Any]) -> Callable[[], Any]:
        BENCHMARK_REGISTRY.append(
            BenchmarkTask(
                name=name,
                category=category,
                description=description,
                func=fn,
                default_iterations=default_iterations,
                default_warmup=default_warmup,
                bytes_per_op=bytes_per_op,
                unit=unit,
            )
        )
        return fn

    return decorator


def _init_benchmarks() -> None:
    """Initialize and register all canonical Bible Engine benchmark workloads."""
    if BENCHMARK_REGISTRY:
        return

    # Import dependencies lazily
    from core.db import DEFAULT_DB_PATH, Database
    from core.reference import parse_reference, parse_references
    from core.crypto import encrypt_string, decrypt_string
    from core.render import render_verse_slide
    from tools.linter import lint_source_text

    # Shared test resources
    db = Database(DEFAULT_DB_PATH)
    ref_john = parse_reference("John 3:16")
    ref_romans = parse_reference("Romans 8:28-30")
    ref_gen_ch = parse_reference("Genesis 1")
    raw_sample_text = (
        "For God so loved the world, that he gave his one and only Son, "
        "that whoever believes in him should not perish, but have eternal life. "
        * 100
    )  # ~14 KB

    # 1. Reference Parsing
    register_benchmark(
        name="ref_parse_single",
        category="reference",
        description="Parse standard single verse reference ('John 3:16')",
        default_iterations=2000,
        default_warmup=100,
    )(lambda: parse_reference("John 3:16"))

    register_benchmark(
        name="ref_parse_span",
        category="reference",
        description="Parse multi-verse span ('Romans 8:28-30')",
        default_iterations=2000,
        default_warmup=100,
    )(lambda: parse_reference("Romans 8:28-30"))

    register_benchmark(
        name="ref_parse_cross_chapter",
        category="reference",
        description="Parse cross-chapter span ('Genesis 1:1 - 2:3')",
        default_iterations=1500,
        default_warmup=100,
    )(lambda: parse_reference("Genesis 1:1 - 2:3"))

    register_benchmark(
        name="ref_parse_typos",
        category="reference",
        description="Resolve common book name typos ('Galations 5:22-23')",
        default_iterations=1500,
        default_warmup=100,
    )(lambda: parse_reference("Galations 5:22-23"))

    register_benchmark(
        name="ref_parse_batch",
        category="reference",
        description="Parse multi-citation string ('John 3:16; Rom 8:28; Rev 22:21')",
        default_iterations=1000,
        default_warmup=50,
    )(lambda: parse_references("John 3:16; Rom 8:28-30; Gen 1:1; Rev 22:21"))

    # 2. SQLite Database Queries
    register_benchmark(
        name="db_get_single",
        category="database",
        description="SQLite retrieve single verse by canonical ID ('John 3:16')",
        default_iterations=1000,
        default_warmup=50,
    )(lambda: db.get_verse("John", 3, 16, translation_id="WEB"))

    register_benchmark(
        name="db_get_span",
        category="database",
        description="SQLite retrieve 3-verse passage span ('Romans 8:28-30')",
        default_iterations=800,
        default_warmup=50,
    )(lambda: db.get_verses_by_reference(ref_romans, translation_id="WEB"))

    register_benchmark(
        name="db_get_chapter",
        category="database",
        description="SQLite retrieve entire chapter (Genesis 1, 31 verses)",
        default_iterations=400,
        default_warmup=25,
    )(lambda: db.get_verses_by_reference(ref_gen_ch, translation_id="WEB"))

    # 3. Full-Text Search (FTS5)
    register_benchmark(
        name="db_fts_phrase",
        category="fts",
        description="FTS5 exact phrase query across 31,103 verses ('\"light of the world\"')",
        default_iterations=400,
        default_warmup=25,
    )(lambda: db.search_text('"light of the world"', translation_id="WEB", limit=10))

    register_benchmark(
        name="db_fts_boolean",
        category="fts",
        description="FTS5 boolean query across 31,103 verses ('faith AND works')",
        default_iterations=400,
        default_warmup=25,
    )(lambda: db.search_text("faith AND works", translation_id="WEB", limit=10))

    # 4. Cryptography
    text_len_bytes = len(raw_sample_text.encode("utf-8"))

    register_benchmark(
        name="crypto_chacha20_string",
        category="crypto",
        description=f"ChaCha20-HMAC authenticated string encrypt+decrypt ({text_len_bytes // 1024} KB)",
        default_iterations=150,
        default_warmup=15,
        bytes_per_op=text_len_bytes,
        unit="MB/s",
    )(lambda: decrypt_string(encrypt_string(raw_sample_text, "benchmark-secret-key"), "benchmark-secret-key"))

    # 5. Slide Rendering
    register_benchmark(
        name="render_svg_slide",
        category="render",
        description="Render Sacred-Modern 4K SVG slide for 'John 3:16'",
        default_iterations=200,
        default_warmup=20,
    )(lambda: render_verse_slide("For God so loved the world, that he gave his one and only Son...", citation="John 3:16", translation="WEB", theme="oled_black", output_format="svg"))

    # 6. Static Analysis / Linter
    sample_code_snippet = """
import os, sys
def calculate_metrics(data):
    total = sum(data)
    return {"sum": total, "avg": total / len(data) if data else 0}
"""
    register_benchmark(
        name="lint_ast_analysis",
        category="linter",
        description="Parse & analyze AST code smells and style checks on Python snippet",
        default_iterations=1500,
        default_warmup=100,
    )(lambda: lint_source_text(sample_code_snippet, Path("benchmark_snippet.py"), "benchmark_snippet.py"))

    # 7. ESV LRU Cache Simulation
    register_benchmark(
        name="cache_esv_lru_touch",
        category="cache",
        description="LRU Cache lookup and touch timestamp in SQLite",
        default_iterations=600,
        default_warmup=50,
    )(lambda: db.get_esv_cached_verses(ref_john))


# ---------------------------------------------------------------------------
# Benchmark Execution Engine
# ---------------------------------------------------------------------------

def run_single_benchmark(
    task: BenchmarkTask,
    iterations: Optional[int] = None,
    warmup_rounds: Optional[int] = None,
    quick: bool = False,
) -> BenchmarkResult:
    """Execute a single benchmark task and return statistical results."""
    iters = iterations if iterations is not None else task.default_iterations
    warmup = warmup_rounds if warmup_rounds is not None else task.default_warmup

    if quick:
        iters = max(5, iters // 5)
        warmup = max(2, warmup // 5)

    fn = task.func

    # 1. Warmup rounds
    for _ in range(warmup):
        fn()

    # 2. Measurement rounds
    durations: List[int] = []
    t_start = time.perf_counter_ns
    for _ in range(iters):
        t0 = t_start()
        fn()
        t1 = t_start()
        durations.append(t1 - t0)

    # 3. Calculate statistics
    (
        mean_val,
        median_val,
        min_val,
        max_val,
        stddev_val,
        p90_val,
        p99_val,
        ops_sec,
        throughput_mb_s,
    ) = compute_statistics(durations, bytes_per_op=task.bytes_per_op)

    return BenchmarkResult(
        name=task.name,
        category=task.category,
        description=task.description,
        iterations=iters,
        warmup_rounds=warmup,
        durations_ns=durations,
        mean_ns=mean_val,
        median_ns=median_val,
        min_ns=min_val,
        max_ns=max_val,
        stddev_ns=stddev_val,
        p90_ns=p90_val,
        p99_ns=p99_val,
        ops_per_sec=ops_sec,
        throughput_mb_s=throughput_mb_s,
        unit=task.unit,
    )


def run_benchmark_suite(
    categories: Optional[Sequence[str]] = None,
    pattern: Optional[str] = None,
    iterations: Optional[int] = None,
    warmup: Optional[int] = None,
    quick: bool = False,
    baseline: Optional[Dict[str, Any]] = None,
    regression_threshold_pct: Optional[float] = None,
    baseline_path_str: Optional[str] = None,
) -> BenchmarkSuiteResult:
    """Execute a suite of benchmarks, calculate statistics, and evaluate regressions."""
    _init_benchmarks()

    tasks = BENCHMARK_REGISTRY

    # Filter by category
    if categories:
        cats = {c.strip().lower() for c in categories}
        tasks = [t for t in tasks if t.category.lower() in cats]

    # Filter by pattern
    if pattern:
        pat = pattern.strip().lower()
        tasks = [t for t in tasks if pat in t.name.lower() or pat in t.description.lower()]

    if not tasks:
        return BenchmarkSuiteResult()

    t_suite_start = time.time()
    results: List[BenchmarkResult] = []
    regressions: List[BenchmarkResult] = []

    for task in tasks:
        res = run_single_benchmark(task, iterations=iterations, warmup_rounds=warmup, quick=quick)

        # Compare against baseline if provided
        if baseline and "results" in baseline:
            base_map = {b["name"]: b for b in baseline["results"] if "name" in b}
            if task.name in base_map:
                base_item = base_map[task.name]
                base_mean = float(base_item.get("mean_ns", 0.0))
                if base_mean > 0.0:
                    res.baseline_mean_ns = base_mean
                    # Delta: positive means faster, negative means slower
                    delta = ((base_mean - res.mean_ns) / base_mean) * 100.0
                    res.delta_pct = delta

                    # Check for regression (e.g. slower by more than threshold)
                    if regression_threshold_pct is not None:
                        if delta < -regression_threshold_pct:
                            res.is_regression = True
                            regressions.append(res)

        results.append(res)

    t_suite_dur = time.time() - t_suite_start

    return BenchmarkSuiteResult(
        results=results,
        total_duration_sec=t_suite_dur,
        baseline_path=baseline_path_str,
        regression_threshold_pct=regression_threshold_pct,
        regressions=regressions,
    )


# ---------------------------------------------------------------------------
# Baseline Management & File I/O
# ---------------------------------------------------------------------------

def save_baseline(suite_result: BenchmarkSuiteResult, target_path: Path = DEFAULT_BASELINE_PATH) -> None:
    """Save benchmark results as the persistent repository baseline."""
    target_path = Path(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
        f.write(suite_result.to_json(indent=2, include_raw=False) + "\n")


def load_baseline(source_path: Path = DEFAULT_BASELINE_PATH) -> Optional[Dict[str, Any]]:
    """Load baseline benchmark data from a JSON file."""
    source_path = Path(source_path)
    if not source_path.is_file():
        return None
    try:
        with open(source_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Presentation & Report Generators (ANSI Terminal & HTML)
# ---------------------------------------------------------------------------

def format_benchmark_table(suite: BenchmarkSuiteResult, styler: Optional[BenchmarkStyler] = None) -> str:
    """Format benchmark results into a clean, high-contrast ANSI terminal dashboard."""
    if styler is None:
        styler = BenchmarkStyler(enabled=True)

    lines: List[str] = []
    lines.append(styler.bold("=" * 90))
    lines.append(
        styler.bold(f" Bible Engine Sovereign Performance Benchmark Suite — {suite.timestamp}")
    )
    lines.append(
        styler.dim(f" Platform: {suite.platform_info} │ Python: {suite.python_version} │ Duration: {suite.total_duration_sec:.2f}s")
    )
    if suite.baseline_path:
        lines.append(styler.cyan(f" Baseline Reference: {suite.baseline_path}"))
    if suite.regression_threshold_pct:
        lines.append(styler.yellow(f" Regression Guard Threshold: {suite.regression_threshold_pct:.1f}%"))
    lines.append(styler.bold("=" * 90))

    # Header
    hdr = f" {'Benchmark Workload':<28} {'Mean':>10} {'Median':>10} {'p99':>10} {'Throughput':>15}"
    if suite.baseline_path:
        hdr += f" {'Delta vs Base':>14}"
    lines.append(styler.bold(hdr))
    lines.append(styler.dim("-" * 90))

    current_cat = ""
    for r in suite.results:
        if r.category != current_cat:
            current_cat = r.category
            lines.append(styler.gold(styler.bold(f" [Category: {current_cat.upper()}]")))

        name_display = f"  {r.name:<26}"
        mean_str = styler.format_latency(r.mean_ns)
        med_str = styler.format_latency(r.median_ns)
        p99_str = styler.format_latency(r.p99_ns)

        if r.throughput_mb_s is not None:
            tp_str = f"{r.throughput_mb_s:.2f} MB/s"
        else:
            tp_str = styler.format_throughput(r.ops_per_sec, r.unit)

        row = f"{name_display} {mean_str:>10} {med_str:>10} {p99_str:>10} {tp_str:>15}"

        if suite.baseline_path:
            delta_str = styler.format_delta(r.delta_pct, r.is_regression)
            row += f" {delta_str:>14}"

        lines.append(row)

    lines.append(styler.dim("-" * 90))

    # Summary Card
    total_benchmarks = len(suite.results)
    reg_count = len(suite.regressions)
    if reg_count > 0:
        status_line = styler.red(styler.bold(f" [FAILED] {reg_count} REGRESSION(S) DETECTED across {total_benchmarks} benchmarks!"))
        for reg in suite.regressions:
            status_line += f"\n  - {reg.name}: regressed by {abs(reg.delta_pct or 0.0):.1f}% (mean: {styler.format_latency(reg.mean_ns)} vs base: {styler.format_latency(reg.baseline_mean_ns or 0.0)})"
    else:
        status_line = styler.green(styler.bold(f" [PASSED] All {total_benchmarks} benchmarks verified within performance budgets."))

    lines.append(status_line)
    lines.append(styler.bold("=" * 90))
    return "\n".join(lines)


def generate_html_report(suite: BenchmarkSuiteResult, output_path: Path) -> Path:
    """Generate a standalone, zero-dependency Sacred-Modern HTML performance dashboard."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows_html: List[str] = []
    for r in suite.results:
        delta_badge = ""
        if r.delta_pct is not None:
            if r.is_regression:
                delta_badge = f'<span class="badge regression">▼ {abs(r.delta_pct):.1f}% SLOWER</span>'
            elif r.delta_pct > 5.0:
                delta_badge = f'<span class="badge faster">▲ {r.delta_pct:+.1f}% faster</span>'
            else:
                delta_badge = f'<span class="badge neutral">~ {r.delta_pct:+.1f}%</span>'
        else:
            delta_badge = '<span class="badge dim">—</span>'

        latency_str = f"{r.mean_ns / 1_000:.2f} µs" if r.mean_ns < 1_000_000 else f"{r.mean_ns / 1_000_000:.2f} ms"
        tp_str = f"{r.throughput_mb_s:.2f} MB/s" if r.throughput_mb_s is not None else f"{r.ops_per_sec:,.0f} ops/s"

        rows_html.append(f"""
        <tr>
          <td><strong>{r.name}</strong><br><small class="text-muted">{r.description}</small></td>
          <td><span class="cat-pill">{r.category}</span></td>
          <td class="num">{latency_str}</td>
          <td class="num">{r.median_ns / 1_000:.2f} µs</td>
          <td class="num">{r.p99_ns / 1_000:.2f} µs</td>
          <td class="num bold gold">{tp_str}</td>
          <td class="num">{delta_badge}</td>
        </tr>
        """)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Bible Engine Benchmark Report</title>
  <style>
    :root {{
      --bg-dark: #0D0E11;
      --card-bg: #14171F;
      --border-color: #242938;
      --gold-primary: #D4AF37;
      --gold-accent: #F3E5AB;
      --text-main: #E6EDF3;
      --text-muted: #8B949E;
      --green: #3FB950;
      --red: #F85149;
      --yellow: #D29922;
    }}
    body {{
      background-color: var(--bg-dark);
      color: var(--text-main);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      margin: 0;
      padding: 32px 20px;
    }}
    .container {{
      max-width: 1100px;
      margin: 0 auto;
    }}
    header {{
      border-bottom: 1px solid var(--border-color);
      padding-bottom: 24px;
      margin-bottom: 24px;
    }}
    h1 {{
      color: var(--gold-primary);
      margin: 0 0 8px 0;
      font-size: 28px;
    }}
    .meta {{
      color: var(--text-muted);
      font-size: 14px;
    }}
    .card {{
      background-color: var(--card-bg);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 24px;
      margin-bottom: 24px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    th {{
      text-align: left;
      padding: 12px 14px;
      color: var(--gold-accent);
      border-bottom: 2px solid var(--border-color);
    }}
    td {{
      padding: 12px 14px;
      border-bottom: 1px solid var(--border-color);
    }}
    .num {{ text-align: right; }}
    .bold {{ font-weight: bold; }}
    .gold {{ color: var(--gold-primary); }}
    .text-muted {{ color: var(--text-muted); }}
    .cat-pill {{
      background-color: #1F2430;
      color: #79C0FF;
      padding: 3px 8px;
      border-radius: 4px;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
    .badge {{
      display: inline-block;
      padding: 3px 8px;
      border-radius: 4px;
      font-size: 12px;
      font-weight: 600;
    }}
    .badge.faster {{ background-color: rgba(63, 185, 80, 0.15); color: var(--green); }}
    .badge.regression {{ background-color: rgba(248, 81, 73, 0.2); color: var(--red); border: 1px solid var(--red); }}
    .badge.neutral {{ background-color: #21262D; color: var(--text-muted); }}
    .badge.dim {{ color: var(--text-muted); }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>⚡ Bible Engine Performance Benchmark</h1>
      <div class="meta">
        Generated on {suite.timestamp} │ Platform: {suite.platform_info} │ Python {suite.python_version}
      </div>
    </header>
    <div class="card">
      <table>
        <thead>
          <tr>
            <th>Workload</th>
            <th>Category</th>
            <th class="num">Mean Latency</th>
            <th class="num">Median</th>
            <th class="num">p99 Latency</th>
            <th class="num">Throughput</th>
            <th class="num">Delta vs Base</th>
          </tr>
        </thead>
        <tbody>
          {"".join(rows_html)}
        </tbody>
      </table>
    </div>
  </div>
</body>
</html>
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    return output_path


# ---------------------------------------------------------------------------
# CLI Parser & Entry Point
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Construct CLI argument parser for benchmark suite."""
    parser = argparse.ArgumentParser(
        prog="bible bench",
        description="Sovereign High-Velocity Performance Benchmark Engine & Regression Guard.",
    )
    parser.add_argument(
        "-c",
        "--category",
        help="Filter benchmarks by category (comma-separated: reference,database,fts,crypto,render,linter,cache)",
    )
    parser.add_argument(
        "-p",
        "--pattern",
        help="Filter benchmarks by name or description pattern substring",
    )
    parser.add_argument(
        "-n",
        "--iterations",
        type=int,
        help="Override iteration count for workloads",
    )
    parser.add_argument(
        "-w",
        "--warmup",
        type=int,
        help="Override warmup round count",
    )
    parser.add_argument(
        "-q",
        "--quick",
        "--fast",
        action="store_true",
        help="Run benchmarks in high-velocity quick mode (<2s)",
    )
    parser.add_argument(
        "--save-baseline",
        nargs="?",
        const=str(DEFAULT_BASELINE_PATH),
        help="Save benchmark results to persistent baseline file (default: .benchmark_baseline.json)",
    )
    parser.add_argument(
        "--compare-baseline",
        nargs="?",
        const=str(DEFAULT_BASELINE_PATH),
        help="Compare execution against persistent baseline file (default: .benchmark_baseline.json)",
    )
    parser.add_argument(
        "--fail-regression",
        type=float,
        metavar="THRESHOLD_PCT",
        help="Exit with code 1 if any benchmark regresses by more than THRESHOLD_PCT (e.g. 20.0)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit results as structured JSON",
    )
    parser.add_argument(
        "--html",
        metavar="PATH",
        help="Export Sacred-Modern HTML performance dashboard to target file",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI colors in terminal output",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Main CLI entrypoint for `tools/benchmark.py`."""
    parser = build_parser()
    args = parser.parse_args(argv)

    categories = [c.strip() for c in args.category.split(",") if c.strip()] if args.category else None

    # Handle baseline loading
    baseline_data = None
    baseline_path_str = None
    if args.compare_baseline:
        baseline_path = Path(args.compare_baseline)
        baseline_path_str = str(baseline_path)
        baseline_data = load_baseline(baseline_path)
        if not baseline_data and not args.json:
            print(f"[Notice] Baseline file '{baseline_path}' not found. Running benchmarks without baseline comparison.", file=sys.stderr)

    suite = run_benchmark_suite(
        categories=categories,
        pattern=args.pattern,
        iterations=args.iterations,
        warmup=args.warmup,
        quick=args.quick,
        baseline=baseline_data,
        regression_threshold_pct=args.fail_regression,
        baseline_path_str=baseline_path_str,
    )

    # Handle baseline saving
    if args.save_baseline:
        target_path = Path(args.save_baseline)
        save_baseline(suite, target_path)
        if not args.json:
            print(f"[Saved] Baseline successfully saved to {target_path}", file=sys.stderr)

    # Handle HTML export
    if args.html:
        html_file = generate_html_report(suite, Path(args.html))
        if not args.json:
            print(f"[Exported] HTML benchmark report saved to {html_file}", file=sys.stderr)

    # Output results
    if args.json:
        print(suite.to_json(indent=2, include_raw=False))
    else:
        styler = BenchmarkStyler(enabled=not args.no_color)
        print(format_benchmark_table(suite, styler=styler))

    # Regression gate: exit code 1 if regression detected
    if args.fail_regression is not None and suite.regressions:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
