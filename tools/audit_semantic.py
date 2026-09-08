#!/usr/bin/env python3
"""Semantic Architecture Quality & Exegetical Critic Audit CLI Tool.

Zero-dependency CLI utility (Python 3 standard library only per ADR-003):
- Audits canonical coordinate boundaries across all stored pericopes, theology, typology, and propositions.
- Measures whole-Bible pericope coverage across all 66 books (31,103 verses, 1,189 chapters).
- Critiques exegesis against TGC Foundation Documents (anti-moralism, Christological depth).
- Deduplicates and normalizes biblical character entities.
- Emits human-readable terminal dashboards or machine-readable JSON telemetry.
"""

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any, Dict, Optional

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.db import Database, DEFAULT_DB_PATH
from core.reference import get_book
from core.semantic_audit import (
    CriticSeverity,
    get_semantic_auditor,
)


def run_semantic_audit(
    db_path: Path,
    include_coverage: bool = True,
    book_filter: Optional[str] = None,
    json_output: bool = False,
    verbose: bool = False,
    strict: bool = False,
    stream: Optional[Any] = None,
) -> int:
    """Run semantic quality audit and emit results."""
    t0 = time.time()
    target_stream = stream or sys.stdout

    def emit(text: str = "") -> None:
        target_stream.write(text + "\n")
        target_stream.flush()

    if not db_path.exists():
        if json_output:
            emit(json.dumps({"error": f"Database file not found: {db_path}"}))
        else:
            emit(f"\033[31m[!] Error: Database file not found: {db_path}\033[0m")
        return 1

    db = Database(db_path)
    auditor = get_semantic_auditor()

    # Filter by book if specified
    book_id: Optional[int] = None
    if book_filter:
        b = get_book(book_filter)
        if not b:
            if json_output:
                emit(json.dumps({"error": f"Unknown book: {book_filter}"}))
            else:
                emit(f"\033[31m[!] Error: Unknown book '{book_filter}'\033[0m")
            return 1
        book_id = b.number

    report, cov_report = auditor.audit_database(db, include_coverage=include_coverage, strict=strict)
    duration = time.time() - t0

    if json_output:
        payload: Dict[str, Any] = {
            "status": "PASSED" if report.is_clean else "FAILED",
            "database": str(db_path),
            "duration_sec": round(duration, 4),
            "audit_report": report.to_dict(),
        }
        if cov_report:
            payload["coverage_report"] = cov_report.to_dict()
        emit(json.dumps(payload, indent=2))
        return 0 if report.is_clean else 1

    # Human-readable terminal output
    emit("=" * 78)
    emit(" Bible Engine — Exegetical Critic & Semantic Quality Audit")
    emit(f" Database: {db_path} | Duration: {duration:.3f}s")
    emit("=" * 78)

    # Print coverage summary table
    if cov_report:
        if book_id is not None and book_id in cov_report.book_stats:
            bst = cov_report.book_stats[book_id]
            emit(f"\n Book Coverage: {bst.book_name}")
            emit(f"  * Verses Covered: {bst.covered_verses} / {bst.total_verses} ({bst.coverage_pct:.1f}%)")
            emit(f"  * Pericopes: {bst.pericope_count}")
            emit(f"  * Status: {'COMPLETE (100%)' if bst.is_complete else 'INCOMPLETE'}")
        else:
            emit(cov_report.summary_table())

    # Print Audit Findings
    emit("\n Exegetical Critic Findings:")
    emit(f"  * Total Inspected: {report.total_inspected}")
    emit(f"  * Errors: {len(report.errors)}")
    emit(f"  * Warnings: {len(report.warnings)}")
    emit(f"  * Info: {len(report.info)}")

    if report.findings:
        emit("\n Diagnostics Details:")
        displayed = report.findings if verbose else report.findings[:25]
        for f in displayed:
            color = "\033[31m" if f.severity in (CriticSeverity.ERROR, CriticSeverity.CRITICAL) else "\033[33m"
            loc = f" [{f.human_ref}]" if f.human_ref else ""
            emit(f"  {color}[{f.severity.value}]{loc} {f.rule_id}\033[0m: {f.message}")
            if f.suggested_fix and verbose:
                emit(f"    \033[36m-> Fix: {f.suggested_fix}\033[0m")
        if not verbose and len(report.findings) > 25:
            emit(f"  ... and {len(report.findings) - 25} more findings (use --verbose to view all)")
    else:
        emit("  \033[32m[✓] All semantic schemas and coordinate boundaries are 100% valid!\033[0m")

    emit("-" * 78)
    if report.is_clean:
        emit(f"\033[32m[✓] Semantic Quality Audit: PASSED (Completed in {duration:.3f}s)\033[0m")
        return 0
    else:
        emit(f"\033[31m[!] Semantic Quality Audit: FAILED with {len(report.errors)} errors\033[0m")
        return 1


def main() -> int:
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Audit semantic database coordinates, schemas, and whole-Bible coverage."
    )
    parser.add_argument(
        "--db",
        type=str,
        default=str(DEFAULT_DB_PATH),
        help=f"Path to SQLite database (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--no-coverage",
        dest="coverage",
        action="store_false",
        default=True,
        help="Skip whole-Bible verse coverage calculation",
    )
    parser.add_argument(
        "--book",
        type=str,
        default=None,
        help="Filter audit to a specific canonical book (e.g. 'Romans', 'Genesis')",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as machine-readable JSON",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed findings and suggested remediation fixes",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enforce strict error severity on missing pericope central propositions/summaries",
    )

    args = parser.parse_args()
    return run_semantic_audit(
        db_path=Path(args.db),
        include_coverage=args.coverage,
        book_filter=args.book,
        json_output=args.json,
        verbose=args.verbose,
        strict=args.strict,
    )


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        sys.stderr.close()
        sys.exit(0)
