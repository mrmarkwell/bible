"""Main CLI entry point and argument parsing for Bible Engine.

Zero-dependency implementation (Python 3 standard library only per ADR-003).
Provides commands:
  - get: Fetch and display scripture passages by reference with multi-translation & fallback support.
  - compare: Compare scripture passages across translations in aligned or stacked layouts.
  - translations: List installed scripture translations, copyright status, and verse counts.
  - doctor: Run comprehensive zero-dependency health, dependency, and documentation diagnostics.
  - summary: Generate executive summary and trajectory briefing across recent Ralph iterations.
"""

import argparse
from pathlib import Path
import sys
from typing import Dict, List, Optional, Sequence, Tuple, Union

from core.db import DEFAULT_DB_PATH, Database, VerseRecord
from core.reference import Reference, parse_reference


def parse_translation_ids(
    version_arg: Union[str, Sequence[str], None],
    default: str = "WEB",
) -> List[str]:
    """Parse comma-separated or list-based translation identifiers into a normalized list.

    Args:
        version_arg: Single string ("WEB,KJV"), sequence of strings (["WEB", "KJV"]), or None.
        default: Default translation identifier if none specified.

    Returns:
        List of uppercase, deduplicated translation identifiers preserving requested order.
    """
    if not version_arg:
        return [default.strip().upper()]

    raw_items: List[str] = []
    if isinstance(version_arg, str):
        raw_items = version_arg.split(",")
    else:
        for item in version_arg:
            raw_items.extend(item.split(","))

    result: List[str] = []
    seen = set()
    for item in raw_items:
        clean = item.strip().upper()
        if clean and clean not in seen:
            result.append(clean)
            seen.add(clean)

    return result if result else [default.strip().upper()]


def format_verse_lines(
    verses: Sequence[VerseRecord],
    show_verse_numbers: bool = True,
    show_header: bool = True,
    fallback_for: Optional[str] = None,
) -> str:
    """Format a list of VerseRecord objects for terminal display.

    Args:
        verses: Sequence of VerseRecord objects.
        show_verse_numbers: If True, include [verse] numbers before text.
        show_header: If True, include translation and passage header.
        fallback_for: If specified, notes that this translation is serving as a fallback.

    Returns:
        Formatted string for terminal printing.
    """
    if not verses:
        return ""

    first = verses[0]
    last = verses[-1]
    b_name = first.book_name or str(first.book_id)
    t_id = first.translation_id

    # Build reference header
    if len(verses) == 1:
        ref_header = f"{b_name} {first.chapter}:{first.verse}{first.subverse or ''}"
    elif first.chapter == last.chapter:
        ref_header = f"{b_name} {first.chapter}:{first.verse}-{last.verse}"
    else:
        ref_header = f"{b_name} {first.chapter}:{first.verse} - {last.chapter}:{last.verse}"

    version_suffix = f" [fallback for {fallback_for}]" if fallback_for and fallback_for != t_id else ""

    lines: List[str] = []
    if show_header:
        lines.append(f"=== {ref_header} ({t_id}{version_suffix}) ===")
        lines.append("")

    for v in verses:
        v_num = f"[{v.verse}] " if show_verse_numbers else ""
        lines.append(f"{v_num}{v.text}")

    return "\n".join(lines)


def format_aligned_comparison(
    ref: Reference,
    comparison_data: Dict[str, Tuple[Sequence[VerseRecord], str, bool]],
    show_header: bool = True,
) -> str:
    """Format multiple translations in an aligned verse-by-verse comparison layout.

    Args:
        ref: The canonical scripture Reference being compared.
        comparison_data: Dict mapping requested translation ID to
            (verses_sequence, effective_translation_id, is_fallback).
        show_header: If True, include comparison title block.

    Returns:
        Formatted string aligning verses across translations.
    """
    verse_map: Dict[Tuple[int, str], Dict[str, str]] = {}
    verse_labels: Dict[Tuple[int, str], str] = {}

    for req_id, (verses, eff_id, is_fb) in comparison_data.items():
        for v in verses:
            cid = v.canonical_verse_id or 0
            sub = v.subverse or ""
            key = (cid, sub)
            if key not in verse_map:
                verse_map[key] = {}
                b_name = v.book_name or str(v.book_id)
                verse_labels[key] = f"{b_name} {v.chapter}:{v.verse}{sub}"
            verse_map[key][req_id] = v.text

    lines: List[str] = []
    if show_header:
        trans_labels = []
        for req_id, (_, eff_id, is_fb) in comparison_data.items():
            if is_fb:
                trans_labels.append(f"{eff_id}* (fallback for {req_id})")
            else:
                trans_labels.append(eff_id)
        lines.append(f"=== Compare: {ref.format()} ({', '.join(trans_labels)}) ===")
        lines.append("")

    sorted_keys = sorted(verse_map.keys())
    for idx, key in enumerate(sorted_keys):
        label = verse_labels[key]
        lines.append(f"--- {label} ---")
        for req_id, (_, eff_id, is_fb) in comparison_data.items():
            text = verse_map[key].get(req_id, "(Verse unavailable in this translation)")
            tag = f"[{eff_id}*]" if is_fb else f"[{eff_id}]"
            lines.append(f"{tag:<8} {text}")
        if idx < len(sorted_keys) - 1:
            lines.append("")

    return "\n".join(lines)


def cmd_get(args: argparse.Namespace) -> int:
    """Handle 'get' subcommand: fetch verses by reference with multi-translation and fallback."""
    raw_ref = " ".join(args.reference).strip()
    if not raw_ref:
        sys.stderr.write("Error: Reference citation required (e.g. 'John 3:16', 'Romans 8:28-30').\n")
        return 1

    try:
        ref = parse_reference(raw_ref)
    except Exception as exc:
        sys.stderr.write(f"Error parsing reference '{raw_ref}': {exc}\n")
        return 1

    db_path = Path(args.db).resolve() if args.db else DEFAULT_DB_PATH
    if not db_path.exists():
        sys.stderr.write(
            f"Error: Database file not found at '{db_path}'.\n"
            f"Run 'python3 tools/ingest_web.py' to compile offline scripture database.\n"
        )
        return 1

    requested_translations = parse_translation_ids(args.version, default="WEB")
    fallback = (
        None
        if (getattr(args, "strict", False) or getattr(args, "no_fallback", False))
        else (args.fallback or "WEB").strip().upper()
    )

    try:
        with Database(db_path, auto_init=False) as db:
            outputs: List[str] = []
            show_nums = not args.no_numbers
            show_hdr = not args.no_header

            for req_id in requested_translations:
                verses, eff_id, is_fb = db.get_verses_with_fallback(
                    ref, translation_id=req_id, fallback_id=fallback
                )

                if is_fb:
                    sys.stderr.write(
                        f"Notice: Translation '{req_id}' not available; falling back to '{eff_id}'.\n"
                    )

                if not verses:
                    if fallback and fallback != req_id:
                        sys.stderr.write(
                            f"No verses found for reference '{ref.format()}' in requested translation '{req_id}' or fallback '{fallback}'.\n"
                        )
                    else:
                        sys.stderr.write(
                            f"No verses found for reference '{ref.format()}' in translation '{req_id}'.\n"
                        )
                    return 1

                fb_for = req_id if is_fb else None
                formatted = format_verse_lines(
                    verses,
                    show_verse_numbers=show_nums,
                    show_header=show_hdr,
                    fallback_for=fb_for,
                )
                outputs.append(formatted)

            print("\n\n".join(outputs))
            return 0
    except Exception as exc:
        sys.stderr.write(f"Database error: {exc}\n")
        return 1


def cmd_compare(args: argparse.Namespace) -> int:
    """Handle 'compare' subcommand: parallel multi-translation comparison in aligned or stacked view."""
    raw_ref = " ".join(args.reference).strip()
    if not raw_ref:
        sys.stderr.write("Error: Reference citation required (e.g. 'John 1:1', 'Romans 8:28').\n")
        return 1

    try:
        ref = parse_reference(raw_ref)
    except Exception as exc:
        sys.stderr.write(f"Error parsing reference '{raw_ref}': {exc}\n")
        return 1

    db_path = Path(args.db).resolve() if args.db else DEFAULT_DB_PATH
    if not db_path.exists():
        sys.stderr.write(
            f"Error: Database file not found at '{db_path}'.\n"
            f"Run 'python3 tools/ingest_web.py' to compile offline scripture database.\n"
        )
        return 1

    fallback = (
        None
        if (getattr(args, "strict", False) or getattr(args, "no_fallback", False))
        else (args.fallback or "WEB").strip().upper()
    )

    try:
        with Database(db_path, auto_init=False) as db:
            available_ids = db.get_available_translation_ids()
            if not available_ids:
                sys.stderr.write("Error: No scripture translations installed in database.\n")
                return 1

            if args.versions:
                requested_ids = parse_translation_ids(args.versions)
            else:
                # Default to all installed translations if multiple exist, else WEB
                requested_ids = available_ids if len(available_ids) > 1 else available_ids[:1]

            comparison_data: Dict[str, Tuple[List[VerseRecord], str, bool]] = {}
            for req_id in requested_ids:
                verses, eff_id, is_fb = db.get_verses_with_fallback(
                    ref, translation_id=req_id, fallback_id=fallback
                )
                if is_fb:
                    sys.stderr.write(
                        f"Notice: Translation '{req_id}' not available; falling back to '{eff_id}'.\n"
                    )
                if not verses:
                    if fallback and fallback != req_id:
                        sys.stderr.write(
                            f"Error: No verses found for reference '{ref.format()}' in requested translation '{req_id}' or fallback '{fallback}'.\n"
                        )
                    else:
                        sys.stderr.write(
                            f"Error: No verses found for reference '{ref.format()}' in translation '{req_id}'.\n"
                        )
                    return 1
                comparison_data[req_id] = (verses, eff_id, is_fb)

            show_nums = not args.no_numbers
            show_hdr = not args.no_header
            mode = getattr(args, "mode", "aligned")

            if mode == "stacked":
                blocks = []
                for req_id, (verses, eff_id, is_fb) in comparison_data.items():
                    fb_for = req_id if is_fb else None
                    blocks.append(
                        format_verse_lines(
                            verses,
                            show_verse_numbers=show_nums,
                            show_header=show_hdr,
                            fallback_for=fb_for,
                        )
                    )
                print("\n\n".join(blocks))
            else:
                output = format_aligned_comparison(
                    ref,
                    comparison_data,
                    show_header=show_hdr,
                )
                print(output)

            return 0
    except Exception as exc:
        sys.stderr.write(f"Database error: {exc}\n")
        return 1


def cmd_translations(args: argparse.Namespace) -> int:
    """Handle 'translations' subcommand: list registered translations and verse totals."""
    db_path = Path(args.db).resolve() if args.db else DEFAULT_DB_PATH
    if not db_path.exists():
        sys.stderr.write(f"Error: Database file not found at '{db_path}'.\n")
        return 1

    try:
        with Database(db_path, auto_init=False) as db:
            records = db.list_translations()
            if not records:
                print("No translations registered in database.")
                return 0

            print("Installed Scripture Translations:")
            for rec in records:
                count = db.count_verses(rec.id)
                pd_status = (
                    "Public Domain"
                    if rec.is_public_domain
                    else ("Encrypted" if rec.is_encrypted else "Proprietary")
                )
                print(f"  [{rec.id}] {rec.name} ({rec.language}, {pd_status}) — {count:,} verses")
            return 0
    except Exception as exc:
        sys.stderr.write(f"Database error: {exc}\n")
        return 1


def build_parser() -> argparse.ArgumentParser:
    """Construct argument parser for Bible Engine CLI."""
    parser = argparse.ArgumentParser(
        prog="bible",
        description="Bible Engine: Offline-First Sovereign Scripture & Semantic Knowledge Platform.",
    )
    parser.add_argument(
        "--db",
        type=str,
        default=None,
        help=f"Path to SQLite database (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "-v",
        "--version",
        dest="cli_version",
        action="version",
        version="%(prog)s 0.2.0 (Phase 2)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Subcommand to execute")

    # Subcommand: get
    parser_get = subparsers.add_parser(
        "get",
        help="Lookup scripture passage by canonical reference (e.g. 'John 3:16', 'Rom 8:28-30')",
        description="Fetch and display scripture passage by reference with multi-translation and fallback support.",
    )
    parser_get.add_argument(
        "reference",
        nargs="+",
        help="Scripture citation or span (e.g., 'John 3:16', 'Genesis 1:1-3', 'Psalm 23')",
    )
    parser_get.add_argument(
        "--version",
        "-t",
        dest="version",
        action="append",
        default=None,
        help="Translation identifier(s) (e.g. 'WEB', 'ESV', or comma-separated 'WEB,KJV', default: WEB)",
    )
    parser_get.add_argument(
        "--fallback",
        default="WEB",
        help="Fallback translation if requested version is not installed (default: WEB)",
    )
    parser_get.add_argument(
        "--no-fallback",
        action="store_true",
        help="Disable automatic fallback cascade and fail if requested version is missing",
    )
    parser_get.add_argument(
        "--strict",
        action="store_true",
        help="Alias for --no-fallback: strictly require requested translation",
    )
    parser_get.add_argument(
        "--no-numbers",
        action="store_true",
        help="Hide verse numbers in output",
    )
    parser_get.add_argument(
        "--no-header",
        action="store_true",
        help="Suppress passage reference and translation header",
    )
    parser_get.set_defaults(func=cmd_get)

    # Subcommand: compare
    parser_compare = subparsers.add_parser(
        "compare",
        help="Compare scripture passage across multiple translations in parallel",
        description="Parallel multi-translation comparison for study and analysis.",
    )
    parser_compare.add_argument(
        "reference",
        nargs="+",
        help="Scripture citation or span (e.g., 'John 1:1', 'Romans 8:28-30')",
    )
    parser_compare.add_argument(
        "--versions",
        "-t",
        dest="versions",
        action="append",
        default=None,
        help="Translations to compare (comma-separated or repeated, default: installed versions)",
    )
    parser_compare.add_argument(
        "--fallback",
        default="WEB",
        help="Fallback translation if a requested version is absent (default: WEB)",
    )
    parser_compare.add_argument(
        "--no-fallback",
        action="store_true",
        help="Disable automatic fallback cascade and fail if any requested version is missing",
    )
    parser_compare.add_argument(
        "--strict",
        action="store_true",
        help="Alias for --no-fallback: strictly require all requested translations",
    )
    parser_compare.add_argument(
        "--mode",
        choices=["aligned", "stacked"],
        default="aligned",
        help="Comparison presentation layout: 'aligned' (verse-by-verse) or 'stacked' (full blocks)",
    )
    parser_compare.add_argument(
        "--no-numbers",
        action="store_true",
        help="Hide verse numbers in output",
    )
    parser_compare.add_argument(
        "--no-header",
        action="store_true",
        help="Suppress comparison headers",
    )
    parser_compare.set_defaults(func=cmd_compare)

    # Subcommand: translations (alias: versions)
    parser_translations = subparsers.add_parser(
        "translations",
        aliases=["versions"],
        help="List installed scripture translations and verse counts",
        description="Inspect registered Bible translations, language, copyright status, and verse statistics.",
    )
    parser_translations.set_defaults(func=cmd_translations)

    # Subcommand: doctor
    parser_doctor = subparsers.add_parser(
        "doctor",
        help="Run comprehensive health, dependency, and documentation diagnostics",
        description="Verify zero external dependencies, documentation sync, bash scripts, and tests.",
    )
    def cmd_doctor(args: argparse.Namespace) -> int:
        from tools.doctor import run_all_checks
        repo_root = Path(__file__).resolve().parent.parent
        is_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty() and not sys.platform.startswith("win")
        code, _ = run_all_checks(repo_root=repo_root, color=is_tty)
        return code

    parser_doctor.set_defaults(func=cmd_doctor)

    # Subcommand: summary
    parser_summary = subparsers.add_parser(
        "summary",
        help="Generate executive summary and trajectory briefing across recent Ralph iterations",
        description="Review work done across recent iterations, project completion trajectory, and health.",
    )
    parser_summary.add_argument(
        "--window",
        "-w",
        type=int,
        default=10,
        help="Number of past iterations to review (default: 10)",
    )
    parser_summary.add_argument(
        "--no-doctor",
        action="store_true",
        help="Skip running live doctor diagnostics",
    )
    def cmd_summary(args: argparse.Namespace) -> int:
        from tools.executive_summary import generate_summary, format_markdown_report
        repo_root = Path(__file__).resolve().parent.parent
        report = generate_summary(window=args.window, repo_root=repo_root, run_doctor=not args.no_doctor)
        print(format_markdown_report(report))
        return 0

    parser_summary.set_defaults(func=cmd_summary)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI execution entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "func") or args.func is None:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
