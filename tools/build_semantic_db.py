#!/usr/bin/env python3
"""Resumable Batch Semantic Compilation Engine & Whole-Bible Database Builder CLI.

Zero-dependency CLI utility (Python 3 standard library only per ADR-003):
- Compiles the 6-layer semantic architecture into SQLite (pericopes, discourse, theology, typology, propositions, vectors).
- Supports book-by-book compilation (e.g. --book Romans) or whole-Bible sweeps.
- Resumes automatically from the SQLite checkpoint ledger, skipping already-completed units.
- Offers interactive progress telemetry, rate limiting, and dry-run execution.
"""

import argparse
import json
from pathlib import Path
import sys
from typing import List, Optional

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.corpora import CanonicalCorpus, get_corpus
from core.db import Database, DEFAULT_DB_PATH
from core.reference import Book, get_book
from core.semantic_compiler import (
    CompilationProgress,
    CompilationUnit,
    CompilationUnitStatus,
    SemanticCheckpointLedger,
    get_semantic_compiler,
)


def run_semantic_build(
    db_path: Path,
    book_filter: Optional[str] = None,
    corpus_filter: Optional[str] = None,
    compile_all: bool = False,
    resume: bool = True,
    reset_failed: bool = False,
    clear_ledger: bool = False,
    status_only: bool = False,
    dry_run: bool = False,
    translation_id: str = "ESV",
    rate_limit_rpm: float = 15.0,
    no_embeddings: bool = False,
    strict_critic: bool = False,
    json_output: bool = False,
    verbose: bool = False,
) -> int:
    """Execute semantic database compilation or ledger inspection."""
    if not db_path.exists():
        if json_output:
            print(json.dumps({"error": f"Database file not found: {db_path}"}))
        else:
            print(f"[31m[!] Error: Database file not found: {db_path}[0m")
        return 1

    db = Database(db_path)
    ledger = SemanticCheckpointLedger(db)

    # Resolve book filter if provided
    book_obj: Optional[Book] = None
    if book_filter:
        book_obj = get_book(book_filter)
        if not book_obj:
            if json_output:
                print(json.dumps({"error": f"Unknown book: {book_filter}"}))
            else:
                print(f" \033[31m[!] Error: Unknown book '{book_filter}'\033[0m")
            return 1

    # Resolve corpus filter if provided
    corpus_obj: Optional[CanonicalCorpus] = None
    if corpus_filter:
        corpus_obj = get_corpus(corpus_filter)
        if not corpus_obj:
            if json_output:
                print(json.dumps({"error": f"Unknown canonical corpus: {corpus_filter}"}))
            else:
                print(f" \033[31m[!] Error: Unknown canonical corpus '{corpus_filter}'\033[0m")
            return 1

    target_book_ids = list(corpus_obj.book_ids) if corpus_obj else ([book_obj.number] if book_obj else None)

    # Handle ledger maintenance operations
    book_label = book_obj.name if book_obj else "all"
    if clear_ledger:
        cleared = ledger.clear_ledger(book_id=target_book_ids)
        scope_name = f"Corpus {corpus_obj.corpus_id}: {corpus_obj.title}" if corpus_obj else (book_obj.name if book_obj else "all")
        if json_output:
            payload: Dict[str, Any] = {"cleared_units": cleared, "book": book_label, "scope": scope_name}
            if corpus_obj:
                payload["corpus"] = corpus_obj.to_dict()
            print(json.dumps(payload))
        else:
            print(f"Cleared {cleared} checkpoint records from ledger for {scope_name}.")
        return 0

    if reset_failed:
        reset_cnt = ledger.reset_status(CompilationUnitStatus.FAILED, book_id=target_book_ids)
        scope_name = f"Corpus {corpus_obj.corpus_id}: {corpus_obj.title}" if corpus_obj else (book_obj.name if book_obj else "all")
        if json_output:
            payload = {"reset_failed_units": reset_cnt, "book": book_label, "scope": scope_name}
            if corpus_obj:
                payload["corpus"] = corpus_obj.to_dict()
            print(json.dumps(payload))
        else:
            print(f"Reset {reset_cnt} failed units back to PENDING for {scope_name}.")
        return 0

    # Status-only telemetry inspection
    if status_only:
        summary = ledger.get_summary(book_id=target_book_ids)
        scope_name = f"Corpus {corpus_obj.corpus_id}: {corpus_obj.title}" if corpus_obj else (f"Book: {book_obj.name}" if book_obj else "Scope: Whole Bible (66 Books)")
        if json_output:
            payload = {"ledger_status": summary, "book": book_label, "scope": scope_name}
            if corpus_obj:
                payload["corpus"] = corpus_obj.to_dict()
            print(json.dumps(payload, indent=2))
        else:
            print("=" * 70)
            print(f" Bible Engine — Semantic Compilation Ledger Status ({scope_name})")
            print("=" * 70)
            total = sum(summary.values())
            print(f" Total Tracked Units:  {total}")
            print(f"  * Completed:         {summary.get('COMPLETED', 0)}")
            print(f"  * Pending:           {summary.get('PENDING', 0)}")
            print(f"  * In Progress:       {summary.get('IN_PROGRESS', 0)}")
            print(f"  * Failed:            {summary.get('FAILED', 0)}")
            print(f"  * Skipped:           {summary.get('SKIPPED', 0)}")
            if total > 0:
                pct = (summary.get('COMPLETED', 0) / total) * 100.0
                print(f" Overall Completion:  {pct:.1f}%")
            print("=" * 70)
        return 0

    # Initialize compiler
    compiler = get_semantic_compiler(
        db=db,
        translation_id=translation_id,
        rate_limit_rpm=rate_limit_rpm,
        generate_embeddings=not no_embeddings,
        strict_critic=strict_critic,
    )

    # Gather units to compile
    units = []
    if compile_all:
        # Complete permanent semantic database pack: 144 pericopes + 1,189 chapters across 66 books
        units.extend(compiler.get_canonical_pericope_units())
        for b_num in range(1, 67):
            units.extend(compiler.get_chapter_units(b_num))
    elif corpus_obj:
        units = compiler.get_corpus_units(corpus_obj)
    elif book_obj:
        units = compiler.get_canonical_pericope_units(book_filter=book_obj)
        if not units:
            units = compiler.get_chapter_units(book_filter=book_obj)
    else:
        # All 144 authoritative canonical pericopes across the canon
        units = compiler.get_canonical_pericope_units()

    if not units:
        if json_output:
            print(json.dumps({"status": "NO_UNITS_FOUND", "units_count": 0}))
        else:
            print("No compilation units found for specified scope.")
        return 0

    scope_str = f"Corpus {corpus_obj.corpus_id}: {corpus_obj.title}" if corpus_obj else (book_obj.name if book_obj else "all_pericopes")
    if dry_run:
        if json_output:
            print(json.dumps({
                "dry_run": True,
                "total_units": len(units),
                "scope": scope_str,
                "sample_units": [u.unit_id for u in units[:5]],
            }, indent=2))
        else:
            print(f"[Dry Run] Prepared {len(units)} units for compilation across {scope_str}.")
            for u in units[:10]:
                print(f"  - {u.reference.format()} ({u.unit_id}): {u.title}")
            if len(units) > 10:
                print(f"  ... and {len(units) - 10} more units.")
        return 0

    # Real compilation run
    if not json_output:
        banner_scope = f"Corpus {corpus_obj.corpus_id}: {corpus_obj.title}" if corpus_obj else (book_obj.name if book_obj else "All Canonical Pericopes")
        print("=" * 78)
        print(f" Bible Engine — Batch Semantic Compilation Engine ({banner_scope})")
        print(f" Target Database: {db_path} | Translation: {translation_id} | Units: {len(units)}")
        print("=" * 78)

    def telemetry_callback(
        unit: CompilationUnit,
        success: bool,
        error_or_msg: Optional[str],
        progress: CompilationProgress,
    ) -> None:
        if json_output:
            return
        status_sym = "[32m[✓][0m" if success else "[31m[✗][0m"
        ref_str = f"{unit.reference.format():<18}"
        pct_str = f"{progress.percent_complete:5.1f}%"
        rpm_str = f"{progress.rate_per_minute:4.1f} u/m"
        print(f" {status_sym} {ref_str} [{pct_str} | {rpm_str}] {unit.title[:35]}")
        if not success and error_or_msg and verbose:
            print(f"     [33mReason: {error_or_msg[:120]}[0m")

    progress = compiler.compile_units(
        units=units,
        resume=resume,
        callback=telemetry_callback,
    )

    if json_output:
        print(json.dumps({
            "status": "COMPLETED" if progress.failed_units == 0 else "COMPLETED_WITH_FAILURES",
            "progress": progress.to_dict(),
        }, indent=2))
    else:
        print("=" * 78)
        print(" Compilation Summary:")
        print(f"  * Units Processed:   {progress.completed_units + progress.skipped_units} / {progress.total_units}")
        print(f"  * Completed:         {progress.completed_units}")
        print(f"  * Skipped (Resume):  {progress.skipped_units}")
        print(f"  * Failed:            {progress.failed_units}")
        print(f"  * New Pericopes:     {progress.total_pericopes}")
        print(f"  * Discourse Rels:    {progress.total_discourse_relations}")
        print(f"  * Verse Theologies:  {progress.total_verse_theologies}")
        print(f"  * Typological Arcs:  {progress.total_typological_arcs}")
        print(f"  * Propositions:      {progress.total_propositions}")
        print(f"  * Vector Embeddings: {progress.total_embeddings}")
        print(f"  * Duration:          {progress.duration_sec:.2f}s")
        print("=" * 78)

    return 0 if progress.failed_units == 0 else 1


def main(argv: Optional[List[str]] = None) -> int:
    """CLI execution entry point."""
    parser = argparse.ArgumentParser(
        prog="build_semantic_db",
        description="Resumable Batch Semantic Compilation Engine & Whole-Bible Database Builder.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"Path to target SQLite database (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="compile_all",
        help="Compile complete permanent semantic pack (144 pericopes + 1,189 chapters across all 66 books)",
    )
    parser.add_argument(
        "--book",
        type=str,
        default=None,
        help="Filter compilation to a specific canonical book (e.g. 'Romans', 'Genesis')",
    )
    parser.add_argument(
        "--corpus",
        type=str,
        default=None,
        help="Filter compilation to a specific canonical corpus (1-7 or name, e.g. '1', 'pauline_foundations_hebrews')",
    )
    parser.add_argument(
        "--no-resume",
        action="store_false",
        dest="resume",
        default=True,
        help="Do not skip previously completed units; reprocess all",
    )
    parser.add_argument(
        "--reset-failed",
        action="store_true",
        help="Reset all failed units in the ledger back to PENDING",
    )
    parser.add_argument(
        "--clear-ledger",
        action="store_true",
        help="Clear checkpoint records from the ledger",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Inspect current checkpoint ledger counts without executing compilation",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan and list compilation units without executing LLM analysis",
    )
    parser.add_argument(
        "--version",
        "-v_id",
        dest="version",
        type=str,
        default="WEB",
        help="Target scripture translation for passage context (default: WEB)",
    )
    parser.add_argument(
        "--rpm",
        type=float,
        default=15.0,
        help="Rate limit in requests per minute (default: 15.0)",
    )
    parser.add_argument(
        "--no-embeddings",
        action="store_true",
        help="Skip generating dense vector embeddings",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enforce strict ExegeticalCritic error thresholds",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON telemetry",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print detailed progress and failure reasons",
    )

    args = parser.parse_args(argv)

    try:
        return run_semantic_build(
            db_path=args.db,
            book_filter=args.book,
            corpus_filter=args.corpus,
            compile_all=getattr(args, "compile_all", False),
            resume=args.resume,
            reset_failed=args.reset_failed,
            clear_ledger=args.clear_ledger,
            status_only=args.status,
            dry_run=args.dry_run,
            translation_id=args.version,
            rate_limit_rpm=args.rpm,
            no_embeddings=args.no_embeddings,
            strict_critic=args.strict,
            json_output=args.json,
            verbose=args.verbose,
        )
    except BrokenPipeError:
        try:
            sys.stderr.close()
        except Exception:
            pass
        return 0


if __name__ == "__main__":
    sys.exit(main())
