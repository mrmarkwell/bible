"""Main CLI entry point and argument parsing for Bible Engine.

Zero-dependency implementation (Python 3 standard library only per ADR-003).
Provides commands:
  - get: Fetch and display scripture passages by reference.
"""

import argparse
from pathlib import Path
import sys
from typing import List, Optional, Sequence

from core.db import DEFAULT_DB_PATH, Database
from core.reference import Reference, parse_reference


def format_verse_lines(
    verses: Sequence,
    show_verse_numbers: bool = True,
    show_header: bool = True,
) -> str:
    """Format a list of VerseRecord objects for terminal display.

    Args:
        verses: Sequence of VerseRecord objects.
        show_verse_numbers: If True, include [verse] numbers before text.
        show_header: If True, include translation and passage header.

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

    lines: List[str] = []
    if show_header:
        lines.append(f"=== {ref_header} ({t_id}) ===")
        lines.append("")

    for v in verses:
        v_num = f"[{v.verse}] " if show_verse_numbers else ""
        lines.append(f"{v_num}{v.text}")

    return "\n".join(lines)


def cmd_get(args: argparse.Namespace) -> int:
    """Handle 'get' subcommand: fetch verses by reference."""
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

    try:
        with Database(db_path, auto_init=False) as db:
            t_id = (args.version or "WEB").strip().upper()
            verses = db.get_verses_by_reference(ref, translation_id=t_id)

            if not verses:
                sys.stderr.write(
                    f"No verses found for reference '{ref.format()}' in translation '{t_id}'.\n"
                )
                return 1

            show_nums = not args.no_numbers
            show_hdr = not args.no_header
            output = format_verse_lines(verses, show_verse_numbers=show_nums, show_header=show_hdr)
            print(output)
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
        version="%(prog)s 0.1.0 (Phase 2)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Subcommand to execute")

    # Subcommand: get
    parser_get = subparsers.add_parser(
        "get",
        help="Lookup scripture passage by canonical reference (e.g. 'John 3:16', 'Rom 8:28-30')",
        description="Fetch and display scripture passage by reference.",
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
        default="WEB",
        help="Translation identifier (default: WEB)",
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
