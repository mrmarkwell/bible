"""Hermetic unit tests for the Sovereign Performance Benchmark Engine.

Zero-dependency implementation (Python 3 standard library only per ADR-003).
Verifies:
  - Statistical analysis (mean, median, percentiles, stddev, ops/sec, throughput).
  - Benchmark result serialization, deserialization, and JSON exports.
  - ANSI terminal styler, latency/throughput formatters, and delta indicators.
  - Custom workload registration and single-task execution.
  - Suite execution with category and pattern filtering.
  - Baseline saving, loading, and regression threshold enforcement.
  - Standalone Sacred-Modern HTML report generation.
  - CLI invocation via `main()`.
  - Omnichannel integration via `./bible bench` and `BibleShell.do_bench()`.
  - Health doctor integration via `check_performance_benchmarks()`.
"""

import io
import json
from pathlib import Path
import tempfile
import unittest

from cli.main import build_parser, preprocess_cli_argv
from cli.shell import BibleShell
from tools.benchmark import (
    BenchmarkResult,
    BenchmarkStyler,
    BenchmarkSuiteResult,
    BenchmarkTask,
    compute_statistics,
    format_benchmark_table,
    generate_html_report,
    load_baseline,
    main,
    run_benchmark_suite,
    run_single_benchmark,
    save_baseline,
)
from tools.doctor import check_performance_benchmarks


class TestBenchmarkStatistics(unittest.TestCase):
    """Unit tests for statistical math and metric calculations."""

    def test_empty_durations(self) -> None:
        mean, med, mn, mx, std, p90, p99, ops, tp = compute_statistics([])
        self.assertEqual(mean, 0.0)
        self.assertEqual(med, 0.0)
        self.assertEqual(mn, 0.0)
        self.assertEqual(mx, 0.0)
        self.assertEqual(std, 0.0)
        self.assertEqual(ops, 0.0)
        self.assertIsNone(tp)

    def test_single_duration(self) -> None:
        # 1,000,000 ns = 1 ms
        mean, med, mn, mx, std, p90, p99, ops, tp = compute_statistics([1_000_000], bytes_per_op=1024)
        self.assertEqual(mean, 1_000_000.0)
        self.assertEqual(med, 1_000_000.0)
        self.assertEqual(mn, 1_000_000.0)
        self.assertEqual(mx, 1_000_000.0)
        self.assertEqual(std, 0.0)
        self.assertEqual(ops, 1_000.0)  # 1,000 ops/sec
        self.assertIsNotNone(tp)
        # 1024 bytes per ms = 1024 * 1000 bytes/sec ~= 0.976 MB/s
        self.assertAlmostEqual(tp, 1024.0 * 1000.0 / (1024.0 * 1024.0), places=2)

    def test_odd_and_even_durations(self) -> None:
        # Odd sample count
        samples_odd = [100, 200, 300, 400, 500]
        mean, med, mn, mx, std, p90, p99, ops, _ = compute_statistics(samples_odd)
        self.assertEqual(mean, 300.0)
        self.assertEqual(med, 300.0)
        self.assertEqual(mn, 100.0)
        self.assertEqual(mx, 500.0)
        self.assertTrue(std > 0.0)

        # Even sample count
        samples_even = [100, 200, 300, 400]
        mean, med, mn, mx, std, p90, p99, ops, _ = compute_statistics(samples_even)
        self.assertEqual(mean, 250.0)
        self.assertEqual(med, 250.0)


class TestBenchmarkDataModels(unittest.TestCase):
    """Unit tests for BenchmarkResult and BenchmarkSuiteResult data structures."""

    def test_result_to_dict_and_from_dict(self) -> None:
        res = BenchmarkResult(
            name="test_workload",
            category="reference",
            description="Mock workload for testing",
            iterations=50,
            warmup_rounds=5,
            durations_ns=[1000, 1100, 900],
            mean_ns=1000.0,
            median_ns=1000.0,
            min_ns=900.0,
            max_ns=1100.0,
            stddev_ns=100.0,
            p90_ns=1100.0,
            p99_ns=1100.0,
            ops_per_sec=1_000_000.0,
            throughput_mb_s=12.5,
            unit="MB/s",
            baseline_mean_ns=1200.0,
            delta_pct=16.67,
            is_regression=False,
        )
        d = res.to_dict(include_raw=True)
        self.assertEqual(d["name"], "test_workload")
        self.assertEqual(d["throughput_mb_s"], 12.5)
        self.assertEqual(d["durations_ns"], [1000, 1100, 900])

        # Roundtrip from_dict
        res_rebuilt = BenchmarkResult.from_dict(d)
        self.assertEqual(res_rebuilt.name, res.name)
        self.assertEqual(res_rebuilt.mean_ns, res.mean_ns)
        self.assertEqual(res_rebuilt.delta_pct, res.delta_pct)
        self.assertFalse(res_rebuilt.is_regression)

    def test_suite_result_json_export(self) -> None:
        res = BenchmarkResult(
            name="workload_a",
            category="db",
            description="DB test",
            iterations=10,
            warmup_rounds=2,
            mean_ns=500.0,
            ops_per_sec=2_000_000.0,
        )
        suite = BenchmarkSuiteResult(
            results=[res],
            total_duration_sec=0.123,
            regressions=[],
        )
        data_json = suite.to_json(indent=2)
        parsed = json.loads(data_json)
        self.assertEqual(parsed["total_benchmarks"], 1)
        self.assertEqual(parsed["results"][0]["name"], "workload_a")


class TestBenchmarkStyler(unittest.TestCase):
    """Unit tests for ANSI formatting and units presentation."""

    def test_styler_disabled(self) -> None:
        styler = BenchmarkStyler(enabled=False)
        self.assertEqual(styler.bold("text"), "text")
        self.assertEqual(styler.gold("text"), "text")
        self.assertEqual(styler.green("text"), "text")

    def test_format_latency_units(self) -> None:
        styler = BenchmarkStyler(enabled=False)
        self.assertEqual(styler.format_latency(500.0), "500.0 ns")
        self.assertEqual(styler.format_latency(15_500.0), "15.50 µs")
        self.assertEqual(styler.format_latency(2_500_000.0), "2.50 ms")
        self.assertEqual(styler.format_latency(1_200_000_000.0), "1.200 s")

    def test_format_throughput_units(self) -> None:
        styler = BenchmarkStyler(enabled=False)
        self.assertEqual(styler.format_throughput(50.0), "50.0 ops/s")
        self.assertEqual(styler.format_throughput(2_500.0), "2.50 k ops/s")
        self.assertEqual(styler.format_throughput(5_000_000.0), "5.00 M ops/s")

    def test_format_delta_indicator(self) -> None:
        styler = BenchmarkStyler(enabled=False)
        self.assertIn("—", styler.format_delta(None, False))
        self.assertIn("faster", styler.format_delta(15.2, False))
        self.assertIn("slower", styler.format_delta(-12.4, False))
        self.assertIn("SLOWER", styler.format_delta(-35.0, True))


class TestBenchmarkExecution(unittest.TestCase):
    """Hermetic unit tests executing isolated benchmarks."""

    def test_run_single_benchmark_custom_task(self) -> None:
        counter = [0]

        def work() -> None:
            counter[0] += 1

        task = BenchmarkTask(
            name="mock_task",
            category="custom",
            description="Mock work task",
            func=work,
            default_iterations=10,
            default_warmup=2,
        )
        res = run_single_benchmark(task, iterations=10, warmup_rounds=2)
        self.assertEqual(res.name, "mock_task")
        self.assertEqual(res.iterations, 10)
        self.assertEqual(res.warmup_rounds, 2)
        # Total executions = 2 warmup + 10 measurement = 12
        self.assertEqual(counter[0], 12)
        self.assertTrue(res.mean_ns > 0.0)

    def test_run_suite_filtered_by_category(self) -> None:
        suite = run_benchmark_suite(categories=["reference"], quick=True)
        self.assertTrue(len(suite.results) > 0)
        for r in suite.results:
            self.assertEqual(r.category, "reference")

    def test_run_suite_filtered_by_pattern(self) -> None:
        suite = run_benchmark_suite(pattern="single", quick=True)
        self.assertTrue(len(suite.results) >= 1)
        for r in suite.results:
            self.assertTrue("single" in r.name.lower() or "single" in r.description.lower())

    def test_run_suite_empty_pattern(self) -> None:
        suite = run_benchmark_suite(pattern="non_existent_pattern_xyz_123")
        self.assertEqual(len(suite.results), 0)


class TestBaselinePersistenceAndRegression(unittest.TestCase):
    """Hermetic unit tests for baseline save/load and regression detection."""

    def test_save_and_load_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base_file = Path(tmpdir) / "baseline.json"
            res = BenchmarkResult(
                name="test_op",
                category="test",
                description="Test op",
                iterations=5,
                warmup_rounds=1,
                mean_ns=1000.0,
            )
            suite = BenchmarkSuiteResult(results=[res], total_duration_sec=0.05)
            save_baseline(suite, base_file)
            self.assertTrue(base_file.is_file())

            loaded = load_baseline(base_file)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded["total_benchmarks"], 1)
            self.assertEqual(loaded["results"][0]["name"], "test_op")

    def test_load_non_existent_baseline(self) -> None:
        loaded = load_baseline(Path("/tmp/non_existent_bible_baseline_12345.json"))
        self.assertIsNone(loaded)

    def test_regression_detection(self) -> None:
        # Mock baseline with very fast baseline (mean_ns=100.0)
        mock_baseline = {
            "results": [
                {"name": "ref_parse_single", "mean_ns": 10.0}  # Baseline is 10ns, real run will be ~8000ns
            ]
        }
        suite = run_benchmark_suite(
            pattern="ref_parse_single",
            quick=True,
            baseline=mock_baseline,
            regression_threshold_pct=20.0,
        )
        self.assertEqual(len(suite.results), 1)
        self.assertTrue(suite.results[0].is_regression)
        self.assertEqual(len(suite.regressions), 1)


class TestReportGenerators(unittest.TestCase):
    """Unit tests for formatting tables and HTML report output."""

    def test_format_benchmark_table(self) -> None:
        res = BenchmarkResult(
            name="test_workload",
            category="reference",
            description="Formatting test",
            iterations=10,
            warmup_rounds=2,
            mean_ns=25000.0,
            median_ns=24000.0,
            p99_ns=30000.0,
            ops_per_sec=40000.0,
        )
        suite = BenchmarkSuiteResult(results=[res], total_duration_sec=0.1)
        table_text = format_benchmark_table(suite, styler=BenchmarkStyler(enabled=False))
        self.assertIn("Bible Engine Sovereign Performance Benchmark Suite", table_text)
        self.assertIn("test_workload", table_text)
        self.assertIn("25.00 µs", table_text)

    def test_generate_html_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            html_path = Path(tmpdir) / "report.html"
            res = BenchmarkResult(
                name="html_test",
                category="render",
                description="HTML generator test",
                iterations=5,
                warmup_rounds=1,
                mean_ns=12000.0,
                median_ns=11000.0,
                p99_ns=15000.0,
                ops_per_sec=83333.0,
                delta_pct=10.5,
            )
            suite = BenchmarkSuiteResult(results=[res], total_duration_sec=0.05)
            out_file = generate_html_report(suite, html_path)
            self.assertTrue(out_file.is_file())
            content = out_file.read_text(encoding="utf-8")
            self.assertIn("<!DOCTYPE html>", content)
            self.assertIn("Bible Engine Benchmark Report", content)
            self.assertIn("html_test", content)


class TestCLIAndDoctorIntegration(unittest.TestCase):
    """Unit tests for CLI, REPL shell, and Doctor integrations."""

    def test_tools_benchmark_main_cli_json(self) -> None:
        output_buffer = io.StringIO()
        import sys
        old_stdout = sys.stdout
        sys.stdout = output_buffer
        try:
            code = main(["-q", "-p", "ref_parse_single", "--json"])
            self.assertEqual(code, 0)
        finally:
            sys.stdout = old_stdout

        payload = json.loads(output_buffer.getvalue())
        self.assertTrue(payload["total_benchmarks"] >= 1)
        self.assertEqual(payload["results"][0]["name"], "ref_parse_single")

    def test_bible_cli_bench_subcommand_dispatch(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["bench", "-q", "-p", "ref_parse_single", "--json"])
        self.assertTrue(hasattr(args, "func"))

        output_buffer = io.StringIO()
        import sys
        old_stdout = sys.stdout
        sys.stdout = output_buffer
        try:
            exit_code = args.func(args)
            self.assertEqual(exit_code, 0)
        finally:
            sys.stdout = old_stdout

        data = json.loads(output_buffer.getvalue())
        self.assertTrue(len(data["results"]) >= 1)

    def test_cli_preprocess_argv_routing(self) -> None:
        # Verify bench, benchmark, perf are recognized subcommands that are not rewritten to 'get'
        args_bench = preprocess_cli_argv(["bench", "--quick"])
        self.assertEqual(args_bench[0], "bench")

        args_perf = preprocess_cli_argv(["perf", "-q"])
        self.assertEqual(args_perf[0], "perf")

    def test_shell_bench_command(self) -> None:
        out_buf = io.StringIO()
        shell = BibleShell(stdout=out_buf, color=False)
        shell.do_bench("-q -p ref_parse_single --json")
        out_str = out_buf.getvalue()
        self.assertIn('"total_benchmarks": 1', out_str)
        self.assertIn('"name": "ref_parse_single"', out_str)

        # Autocompletion
        completions = shell.complete_bench("-", "- ", 1, 2)
        self.assertIn("-q", completions)
        self.assertIn("-c", completions)

    def test_doctor_check_performance_benchmarks(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        res = check_performance_benchmarks(repo_root=repo_root, quick=True, regression_threshold=None)
        self.assertTrue(res.passed)
        self.assertEqual(res.name, "Performance Benchmarks")
        self.assertIn("verified within performance budgets", res.details)


if __name__ == "__main__":
    unittest.main()
