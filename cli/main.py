"""Main CLI entry point and argument parsing for Bible Engine.

Zero-dependency implementation (Python 3 standard library only per ADR-003).
Provides commands:
  - get: Fetch and display scripture passages by reference with multi-translation & fallback support.
  - compare: Compare scripture passages across translations in aligned or stacked layouts.
  - search: Full-text search across scripture using SQLite FTS5 with phrase, book, and testament filters.
  - translations: List installed scripture translations, copyright status, and verse counts.
  - doctor: Run comprehensive zero-dependency health, dependency, and documentation diagnostics.
  - summary: Generate executive summary and trajectory briefing across recent Ralph iterations.
  - ask: Query Scripture RAG engine with biblical, thematic, or typological inquiries.
  - chat: Interactive Biblical Character Dialogue Studio (e.g. paul, moses, david, peter).
"""

import argparse
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from core.db import DEFAULT_DB_PATH, Database, SearchResult, VerseRecord
from core.reference import BOOKS, Reference, get_book, parse_reference
from core.terminal import (
    THEMES,
    format_aligned_comparison_styled,
    format_citation_header,
    format_scripture_passage,
    get_terminal_width,
    should_use_color,
)


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
    width: Optional[int] = None,
    margin: int = 0,
    flow: bool = False,
    color: bool = False,
    theme: str = "sacred",
    box: bool = False,
) -> str:
    """Format a list of VerseRecord objects for terminal display.

    Args:
        verses: Sequence of VerseRecord objects.
        show_verse_numbers: If True, include [verse] numbers before text.
        show_header: If True, include translation and passage header.
        fallback_for: If specified, notes that this translation is serving as a fallback.
        width: Optional line wrap width. If None and (margin > 0 or flow or box or color), auto-detects.
        margin: Left margin indentation spaces (default 0).
        flow: If True, format verses continuously as a paragraph reader.
        color: Whether to use ANSI terminal styling.
        theme: Theme name ('sacred', 'amber', 'cyan', 'plain').
        box: Whether to draw a decorative unicode box around header.

    Returns:
        Formatted string for terminal printing.
    """
    if not verses:
        return ""

    # If terminal formatting flags are requested or color/margins active, use typography engine
    if width is not None or margin > 0 or flow or color or box or theme != "plain":
        return format_scripture_passage(
            verses=verses,
            show_verse_numbers=show_verse_numbers,
            show_header=show_header,
            fallback_for=fallback_for,
            width=width,
            margin=margin,
            flow=flow,
            color=color,
            theme_name=theme,
            box_header=box,
        )

    # Legacy clean plain-text behavior
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
    width: Optional[int] = None,
    margin: int = 0,
    color: bool = False,
    theme: str = "sacred",
    box: bool = False,
) -> str:
    """Format multiple translations in an aligned verse-by-verse comparison layout.

    Args:
        ref: The canonical scripture Reference being compared.
        comparison_data: Dict mapping requested translation ID to
            (verses_sequence, effective_translation_id, is_fallback).
        show_header: If True, include comparison title block.
        width: Max width for line wrapping.
        margin: Left margin indent spaces.
        color: Whether to apply ANSI highlights.
        theme: Color palette.
        box: Whether to draw boxed header.

    Returns:
        Formatted string aligning verses across translations.
    """
    if width is not None or margin > 0 or color or box or theme != "plain":
        return format_aligned_comparison_styled(
            ref_title=ref.format(),
            comparison_data=comparison_data,
            show_header=show_header,
            width=width,
            margin=margin,
            color=color,
            theme_name=theme,
            box_header=box,
        )

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



def highlight_search_tokens(
    text: str,
    query: str,
    color: bool = True,
    exact: bool = False,
) -> str:
    """Highlight matched search query tokens or exact phrase in text.

    Args:
        text: Target text to format.
        query: Query string containing tokens or exact phrase.
        color: Whether to inject ANSI yellow/bold color codes.
        exact: Whether query represents an exact contiguous phrase.

    Returns:
        Formatted text with color codes or unaltered text if color is False.
    """
    if not color or not query.strip():
        return text

    if exact:
        clean = re.escape(query.strip().strip('"\''))
        pattern = rf"({clean})"
    else:
        words = re.findall(r"\w+", query)
        operators = {"AND", "OR", "NOT"}
        tokens = [re.escape(w) for w in words if w.upper() not in operators]
        if not tokens:
            return text
        pattern = r"\b(" + "|".join(tokens) + r")\b"

    yellow_bold = "\033[1;33m"
    reset = "\033[0m"
    return re.sub(pattern, rf"{yellow_bold}\1{reset}", text, flags=re.IGNORECASE)


def format_search_snippet(snippet: str, color: bool = True) -> str:
    """Format FTS5 snippet containing <b>...</b> tags for terminal display.

    Args:
        snippet: FTS5 generated snippet with <b> and </b> tags.
        color: If True, replace tags with ANSI highlight; if False, clean tags.

    Returns:
        Formatted snippet text.
    """
    if not snippet:
        return ""

    if color:
        yellow_bold = "\033[1;33m"
        reset = "\033[0m"
        return snippet.replace("<b>", yellow_bold).replace("</b>", reset)
    else:
        return snippet.replace("<b>", "[").replace("</b>", "]")


def format_search_results(
    results: Sequence[SearchResult],
    query: str,
    total_count: int,
    translation_label: str = "WEB",
    book_label: Optional[str] = None,
    testament_label: Optional[str] = None,
    offset: int = 0,
    limit: int = 20,
    show_snippets: bool = False,
    color: bool = True,
    exact: bool = False,
) -> str:
    """Format scripture search results for human terminal display."""
    lines: List[str] = []

    # Build scope descriptor
    scope_parts = [translation_label]
    if book_label:
        scope_parts.append(book_label)
    if testament_label:
        scope_parts.append(testament_label)
    scope_str = ", ".join(scope_parts)

    exact_marker = " (exact phrase)" if exact else ""
    lines.append(f'=== Scripture Search: "{query}"{exact_marker} ({scope_str}) ===')

    if not results:
        lines.append("")
        lines.append("No matching verses found.")
        return "\n".join(lines)

    verse_word = "verse" if total_count == 1 else "verses"
    lines.append(f"Found {total_count} matching {verse_word}:")
    lines.append("")

    for idx, r in enumerate(results, start=offset + 1):
        ref_header = f"{idx}. {r.human_ref} ({r.translation_id})"
        lines.append(f"  {ref_header}")

        if show_snippets and r.snippet:
            formatted_snippet = format_search_snippet(r.snippet, color=color)
            lines.append(f"     {formatted_snippet}")
        else:
            formatted_text = highlight_search_tokens(r.text, query, color=color, exact=exact)
            lines.append(f"     {formatted_text}")
        lines.append("")

    # Pagination footer if more results exist
    displayed_count = offset + len(results)
    if total_count > displayed_count:
        remaining = total_count - displayed_count
        lines.append(
            f"Showing results {offset + 1}–{displayed_count} of {total_count} "
            f"({remaining} more). Use --offset={displayed_count} to view next page."
        )

    return "\n".join(lines).rstrip()


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
            f"Run './bible init' (or 'python3 tools/doctor.py --fix') to bootstrap the offline scripture database.\n"
        )
        return 1

    has_explicit_version = args.version is not None
    requested_translations = parse_translation_ids(args.version, default="ESV")
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

            # Determine color enablement
            if getattr(args, "no_color", False):
                color_enabled = False
            elif getattr(args, "color", None) is True:
                color_enabled = True
            else:
                color_enabled = should_use_color()

            theme_name = getattr(args, "theme", "sacred")
            margin_width = getattr(args, "margin", 0)
            wrap_width = getattr(args, "width", None)
            flow_mode = getattr(args, "flow", False)
            box_header = getattr(args, "box", False)

            for req_id in requested_translations:
                verses, eff_id, is_fb = db.get_verses_with_fallback(
                    ref, translation_id=req_id, fallback_id=fallback
                )

                if is_fb and (has_explicit_version or getattr(args, "verbose", False)):
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

                fb_for = req_id if (is_fb and (has_explicit_version or getattr(args, "verbose", False))) else None
                formatted = format_verse_lines(
                    verses,
                    show_verse_numbers=show_nums,
                    show_header=show_hdr,
                    fallback_for=fb_for,
                    width=wrap_width,
                    margin=margin_width,
                    flow=flow_mode,
                    color=color_enabled,
                    theme=theme_name,
                    box=box_header,
                )
                if getattr(args, "pericopes", False):
                    from core.pericopes import PericopeService
                    from core.terminal import format_pericope_banner
                    p_svc = PericopeService(db)
                    pericopes_found = p_svc.get_pericopes_for_passage(ref)
                    if pericopes_found:
                        p_banners = "\n".join(format_pericope_banner(p, styling=color_enabled, width=wrap_width) for p in pericopes_found)
                        formatted = f"{' ' * margin_width}{p_banners}\n\n{formatted}"

                if getattr(args, "tags", False):
                    from core.tags import TaggingService
                    from core.terminal import format_tags_badge
                    svc = TaggingService(db)
                    tags_found = svc.get_tags_for_passage(ref)
                    if tags_found:
                        badge = format_tags_badge(tags_found, styling=color_enabled)
                        formatted += f"\n\n{' ' * margin_width}{badge}"

                if getattr(args, "refs", False) or getattr(args, "cross_refs", False):
                    from core.crossref import CrossReferenceService
                    from core.terminal import format_cross_references
                    xr_svc = CrossReferenceService(db)
                    hydrated = xr_svc.get_hydrated_cross_references(
                        ref,
                        translation_id=req_id,
                        bidirectional=True,
                    )
                    if hydrated:
                        formatted_xr = format_cross_references(hydrated, styling=color_enabled, max_width=wrap_width)
                        formatted += f"\n\n{' ' * margin_width}── Cross References ──\n{formatted_xr}"

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
            f"Run './bible init' (or 'python3 tools/doctor.py --fix') to bootstrap the offline scripture database.\n"
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

            # Determine color enablement
            if getattr(args, "no_color", False):
                color_enabled = False
            elif getattr(args, "color", None) is True:
                color_enabled = True
            else:
                color_enabled = should_use_color()

            theme_name = getattr(args, "theme", "sacred")
            margin_width = getattr(args, "margin", 0)
            wrap_width = getattr(args, "width", None)
            box_header = getattr(args, "box", False)

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
                            width=wrap_width,
                            margin=margin_width,
                            color=color_enabled,
                            theme=theme_name,
                            box=box_header,
                        )
                    )
                print("\n\n".join(blocks))
            else:
                output = format_aligned_comparison(
                    ref,
                    comparison_data,
                    show_header=show_hdr,
                    width=wrap_width,
                    margin=margin_width,
                    color=color_enabled,
                    theme=theme_name,
                    box=box_header,
                )
                print(output)

            return 0
    except Exception as exc:
        sys.stderr.write(f"Database error: {exc}\n")
        return 1


def cmd_search(args: argparse.Namespace) -> int:
    """Handle 'search' subcommand: full-text search across scripture using SQLite FTS5."""
    raw_query = " ".join(args.query).strip()
    if not raw_query:
        sys.stderr.write("Error: Search query required (e.g. 'light of the world', 'faith AND works').\n")
        return 1

    db_path = Path(args.db).resolve() if args.db else DEFAULT_DB_PATH
    if not db_path.exists():
        sys.stderr.write(
            f"Error: Database file not found at '{db_path}'.\n"
            f"Run './bible init' (or 'python3 tools/doctor.py --fix') to bootstrap the offline scripture database.\n"
        )
        return 1

    # Book filter validation
    book_filter = None
    book_label = None
    if getattr(args, "book", None):
        b = get_book(args.book)
        if not b:
            sys.stderr.write(f"Error: Unknown book '{args.book}'.\n")
            return 1
        book_filter = b
        book_label = b.name

    # Testament filter validation
    testament_filter = None
    testament_label = None
    if getattr(args, "testament", None):
        t_raw = args.testament.strip().upper()
        if t_raw in ("OT", "OLD", "OLD TESTAMENT"):
            testament_filter = "OT"
            testament_label = "Old Testament"
        elif t_raw in ("NT", "NEW", "NEW TESTAMENT"):
            testament_filter = "NT"
            testament_label = "New Testament"
        else:
            sys.stderr.write(f"Error: Unknown testament '{args.testament}'. Expected 'OT' or 'NT'.\n")
            return 1

    exact = bool(getattr(args, "exact", False))
    sort_by = getattr(args, "sort", "relevance")
    limit = max(1, getattr(args, "limit", 20))
    offset = max(0, getattr(args, "offset", 0))
    show_snippets = bool(getattr(args, "snippets", False))
    only_count = bool(getattr(args, "count", False))
    output_json = bool(getattr(args, "json", False))

    fallback = (
        None
        if (getattr(args, "strict", False) or getattr(args, "no_fallback", False))
        else (args.fallback or "WEB").strip().upper()
    )

    is_tty = (
        hasattr(sys.stdout, "isatty")
        and sys.stdout.isatty()
        and "NO_COLOR" not in os.environ
        and not getattr(args, "no_highlight", False)
    )

    try:
        with Database(db_path, auto_init=False) as db:
            available_ids = db.get_available_translation_ids()
            raw_version = getattr(args, "version", None)
            requested_translations = parse_translation_ids(raw_version, default="WEB")

            # Check translation availability and fallback
            effective_translations: List[str] = []
            for t_id in requested_translations:
                if t_id == "ALL":
                    effective_translations = ["ALL"]
                    break
                if t_id in available_ids:
                    effective_translations.append(t_id)
                elif fallback and fallback in available_ids:
                    sys.stderr.write(
                        f"Notice: Translation '{t_id}' not available; searching in fallback '{fallback}'.\n"
                    )
                    if fallback not in effective_translations:
                        effective_translations.append(fallback)
                else:
                    sys.stderr.write(f"Error: Translation '{t_id}' is not installed in database.\n")
                    return 1

            trans_arg = None if "ALL" in effective_translations else effective_translations

            # If --count requested:
            if only_count:
                count = db.count_search_matches(
                    raw_query,
                    translation_id=trans_arg,
                    book=book_filter,
                    testament=testament_filter,
                    exact=exact,
                )
                print(count)
                return 0

            # Perform search query
            results = db.search_text(
                raw_query,
                translation_id=trans_arg,
                book=book_filter,
                testament=testament_filter,
                exact=exact,
                sort_by=sort_by,
                limit=limit,
                offset=offset,
            )

            # If JSON output requested:
            if output_json:
                print(json.dumps([r.to_dict() for r in results], indent=2))
                return 0

            # Count total matches for summary & pagination
            total_count = db.count_search_matches(
                raw_query,
                translation_id=trans_arg,
                book=book_filter,
                testament=testament_filter,
                exact=exact,
            )

            trans_display = "ALL" if not trans_arg else ", ".join(trans_arg)
            output = format_search_results(
                results=results,
                query=raw_query,
                total_count=total_count,
                translation_label=trans_display,
                book_label=book_label,
                testament_label=testament_label,
                offset=offset,
                limit=limit,
                show_snippets=show_snippets,
                color=is_tty,
                exact=exact,
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
        sys.stderr.write(
            f"Error: Database file not found at '{db_path}'.\n"
            f"Run './bible init' (or 'python3 tools/doctor.py --fix') to bootstrap the offline scripture database.\n"
        )
        return 1

    try:
        with Database(db_path, auto_init=False) as db:
            records = db.list_translations()
            if not records:
                print("No translations registered in database.")
                return 0

            print("Installed Scripture Translations:")
            print("  [ESV] English Standard Version (Crossway API & 500-verse LRU cache, default with WEB fallback)")
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


def cmd_tag(args: argparse.Namespace) -> int:
    """Handle 'tag' subcommand: semantic tagging, passage annotation, and taxonomy."""
    tag_action = getattr(args, "tag_action", None)
    if not tag_action:
        tag_action = "list"

    db_path = Path(args.db).resolve() if args.db else DEFAULT_DB_PATH
    if not db_path.exists():
        sys.stderr.write(
            f"Error: Database file not found at '{db_path}'.\n"
            f"Run './bible init' (or 'python3 tools/doctor.py --fix') to bootstrap the offline scripture database.\n"
        )
        return 1

    color_enabled = (
        False
        if getattr(args, "no_color", False)
        else (True if getattr(args, "color", None) else should_use_color())
    )

    try:
        with Database(db_path, auto_init=False) as db:
            from core.tags import TaggingService
            from core.terminal import (
                format_tag_table,
                format_tagged_passages,
                format_topic_density_table,
                format_tag_co_occurrence_table,
                format_verse_relevance_table,
            )
            svc = TaggingService(db)

            if tag_action == "add":
                raw_ref = args.reference
                try:
                    ref = parse_reference(raw_ref)
                except Exception as exc:
                    sys.stderr.write(f"Error parsing reference '{raw_ref}': {exc}\n")
                    return 1

                cat = getattr(args, "category", "thematic")
                starred = getattr(args, "starred", False)
                notes = getattr(args, "notes", None)
                conf = getattr(args, "confidence", 1.0)
                tag_names = args.tags

                recs = svc.tag_passage(
                    reference=ref,
                    tags=tag_names,
                    category=cat,
                    confidence=conf,
                    source="user",
                    starred=starred,
                    notes=notes,
                )
                print(f"Successfully tagged {ref.format()} with {len(recs)} tag(s):")
                for r in recs:
                    star_str = " ★" if r.starred else ""
                    print(f"  • {r.tag_name} [{r.human_ref}]{star_str}")
                return 0

            elif tag_action == "list":
                cat = getattr(args, "category", None)
                sort_by = getattr(args, "sort", "passages")
                as_json = getattr(args, "json", False)

                summaries = svc.list_tags(category=cat, sort_by=sort_by)
                if as_json:
                    print(json.dumps([s.to_dict() for s in summaries], indent=2))
                else:
                    print(format_tag_table(summaries, styling=color_enabled))
                return 0

            elif tag_action == "show":
                tag_name = args.tag
                version = getattr(args, "version", "ESV") or "ESV"
                starred_only = getattr(args, "starred_only", False)
                limit = getattr(args, "limit", 20)
                as_json = getattr(args, "json", False)

                passages = svc.get_passages_for_tag(
                    tag_name=tag_name,
                    translation_id=version,
                    starred_only=starred_only,
                    limit=limit,
                )
                if as_json:
                    print(json.dumps([p.to_dict() for p in passages], indent=2))
                else:
                    tag_rec = svc.get_tag(tag_name)
                    if not tag_rec:
                        sys.stderr.write(f"Error: Tag '{tag_name}' not found.\n")
                        return 1
                    header = f"Tag: {tag_rec.name} ({tag_rec.category}) — {len(passages)} passage(s)"
                    if tag_rec.description:
                        header += f"\nDescription: {tag_rec.description}"
                    print(header + "\n")
                    print(format_tagged_passages(passages, styling=color_enabled))
                return 0

            elif tag_action == "for":
                raw_ref = args.reference
                try:
                    ref = parse_reference(raw_ref)
                except Exception as exc:
                    sys.stderr.write(f"Error parsing reference '{raw_ref}': {exc}\n")
                    return 1

                exact = getattr(args, "exact", False)
                as_json = getattr(args, "json", False)

                records = svc.get_tags_for_passage(ref, exact_only=exact)
                if as_json:
                    print(
                        json.dumps(
                            [
                                {
                                    "tag": r.tag_name,
                                    "reference": r.human_ref,
                                    "starred": r.starred,
                                    "confidence": r.confidence,
                                    "notes": r.notes,
                                }
                                for r in records
                            ],
                            indent=2,
                        )
                    )
                else:
                    if not records:
                        print(f"No tags found for {ref.format()}.")
                    else:
                        match_type = "exact match" if exact else "overlapping or exact"
                        print(f"Tags for {ref.format()} ({match_type}):")
                        for r in records:
                            star = " ★" if r.starred else ""
                            note_str = f" — {r.notes}" if r.notes else ""
                            print(f"  🏷  {r.tag_name} [{r.human_ref}]{star}{note_str}")
                return 0

            elif tag_action == "remove":
                raw_ref = args.reference
                try:
                    ref = parse_reference(raw_ref)
                except Exception as exc:
                    sys.stderr.write(f"Error parsing reference '{raw_ref}': {exc}\n")
                    return 1
                tag_name = args.tag
                deleted = svc.untag_passage(ref, tag_name)
                if deleted > 0:
                    print(f"Removed tag '{tag_name}' from {ref.format()}.")
                else:
                    print(f"No tag association found for '{tag_name}' on {ref.format()}.")
                return 0

            elif tag_action == "delete":
                tag_name = args.tag
                ok = svc.delete_tag(tag_name)
                if ok:
                    print(f"Deleted tag '{tag_name}' and all its passage associations.")
                else:
                    sys.stderr.write(f"Error: Tag '{tag_name}' not found.\n")
                    return 1
                return 0

            elif tag_action == "stats":
                tag_name = getattr(args, "tag", None)
                as_json = getattr(args, "json", False)
                stats = db.get_tag_stats(tag_name=tag_name)
                if as_json:
                    print(json.dumps(stats, indent=2))
                else:
                    if not stats:
                        print("No tags found.")
                    else:
                        for s in stats:
                            print(f"Tag: {s['name']} ({s['category']})")
                            print(f"  Passages: {s['passage_count']}")
                            print(f"  Starred:  {s['starred_count']}")
                            print(f"  Books:    {s['distinct_books']}")
                            if s['description']:
                                print(f"  Description: {s['description']}")
                            print()
                return 0

            elif tag_action == "density":
                tag_name = getattr(args, "tag", None)
                cat = getattr(args, "category", None)
                testament = getattr(args, "testament", None)
                min_passages = getattr(args, "min_passages", 0)
                as_json = getattr(args, "json", False)

                densities = svc.get_topic_density_per_book(
                    tag_name=tag_name,
                    category=cat,
                    testament=testament,
                    min_passages=min_passages,
                )
                if as_json:
                    print(json.dumps([d.to_dict() for d in densities], indent=2))
                elif getattr(args, "ribbon", False):
                    from core.terminal import format_redemptive_ribbon_ascii
                    print(format_redemptive_ribbon_ascii(
                        densities=densities,
                        styling=color_enabled,
                        tag_name=tag_name,
                    ))
                else:
                    filter_info = []
                    if tag_name:
                        filter_info.append(f"Tag: '{tag_name}'")
                    if cat:
                        filter_info.append(f"Category: '{cat}'")
                    if testament:
                        filter_info.append(f"Testament: {testament.upper()}")
                    filter_str = f" ({', '.join(filter_info)})" if filter_info else ""
                    print(f"Topic Density Distribution Across Books{filter_str}:\n")
                    print(format_topic_density_table(densities, styling=color_enabled))
                return 0

            elif tag_action in ("co-occurrence", "co-occur", "matrix"):
                tags_filter = getattr(args, "tags", None)
                cat = getattr(args, "category", None)
                min_co = getattr(args, "min_shared", 1)
                as_json = getattr(args, "json", False)

                matrix_res = svc.get_tag_co_occurrences(
                    tags=tags_filter,
                    category=cat,
                    min_co_occurrences=min_co,
                )
                if as_json:
                    print(json.dumps(matrix_res.to_dict(), indent=2))
                else:
                    print(f"Tag Co-Occurrence Analysis (min shared passages: {min_co}):\n")
                    print(format_tag_co_occurrence_table(matrix_res.pair_metrics, styling=color_enabled))
                return 0

            elif tag_action in ("relevance", "rank"):
                tags_list = args.tags
                version = getattr(args, "version", "ESV") or "ESV"
                starred_only = getattr(args, "starred_only", False)
                min_score = getattr(args, "min_score", 0.0)
                limit = getattr(args, "limit", 20)
                as_json = getattr(args, "json", False)
                no_text = getattr(args, "no_text", False)

                rankings = svc.score_verse_relevance(
                    tags=tags_list,
                    translation_id=version,
                    starred_only=starred_only,
                    min_score=min_score,
                    limit=limit,
                    hydrate_verses=not no_text,
                )
                if as_json:
                    print(json.dumps([r.to_dict() for r in rankings], indent=2))
                else:
                    tags_str = ", ".join(tags_list)
                    print(f"Scripture Passage Relevance Rankings for [{tags_str}] ({len(rankings)} results):\n")
                    print(format_verse_relevance_table(rankings, styling=color_enabled, show_text=not no_text))
                return 0

            elif tag_action in ("prune", "clean"):
                preserve = ("favorites",)
                deleted = svc.prune_unlinked_tags(preserve_tags=preserve)
                print(f"Successfully pruned {deleted} unlinked tag(s) with 0 passage associations.")
                return 0

            elif tag_action == "seed":
                count = svc.seed_canonical_taxonomies()
                print(f"Successfully seeded {count} canonical theological and redemptive-historical tags.")
                return 0

            elif tag_action == "prompt":
                from tools.tag_generator import cmd_prompt
                return cmd_prompt(args)

            elif tag_action == "generate":
                from tools.tag_generator import cmd_generate
                return cmd_generate(args)

            elif tag_action in ("apply-llm", "apply"):
                from tools.tag_generator import cmd_apply
                return cmd_apply(args)

            elif tag_action == "batch":
                from tools.tag_generator import cmd_batch
                return cmd_batch(args)

            else:
                sys.stderr.write(f"Unknown tag action: {tag_action}\n")
                return 1

    except Exception as exc:
        sys.stderr.write(f"Tagging error: {exc}\n")
        return 1


def cmd_crossref(args: argparse.Namespace) -> int:
    """Handle 'crossref' (and 'xref', 'refs') subcommand."""
    action = getattr(args, "ref_action", None)
    if not action:
        sys.stderr.write("Error: Cross-reference action required (for, link, unlink, list, path, stats, seed).\n")
        return 1

    db_path = Path(args.db).resolve() if args.db else DEFAULT_DB_PATH
    if not db_path.exists():
        sys.stderr.write(
            f"Error: Database file not found at '{db_path}'.\n"
            f"Run './bible init' (or 'python3 tools/doctor.py --fix') to bootstrap the offline scripture database.\n"
        )
        return 1

    try:
        with Database(db_path, auto_init=False) as db:
            from core.crossref import (
                CrossReferenceService,
                RelationshipType,
            )
            from core.terminal import (
                format_cross_reference_table,
                format_cross_references,
                should_use_color,
            )

            color_enabled = should_use_color()
            svc = CrossReferenceService(db)

            if action == "for":
                raw_ref = args.reference
                try:
                    ref = parse_reference(raw_ref)
                except Exception as exc:
                    sys.stderr.write(f"Error parsing reference '{raw_ref}': {exc}\n")
                    return 1

                rel_type = getattr(args, "type", None)
                trans_id = getattr(args, "version", "ESV") or "ESV"
                as_json = getattr(args, "json", False)
                min_wt = getattr(args, "min_weight", 0.0)

                hydrated = svc.get_hydrated_cross_references(
                    reference=ref,
                    translation_id=trans_id,
                    relationship_type=rel_type,
                    bidirectional=True,
                    min_weight=min_wt,
                )

                if as_json:
                    print(json.dumps([h.to_dict() for h in hydrated], indent=2))
                else:
                    if not hydrated:
                        type_str = f" of type '{rel_type}'" if rel_type else ""
                        print(f"No cross-references found for {ref.format()}{type_str}.")
                    else:
                        print(f"Cross-References for {ref.format()} ({len(hydrated)} connected passage{'s' if len(hydrated) != 1 else ''}):\n")
                        print(format_cross_references(hydrated, styling=color_enabled))
                return 0

            elif action == "link":
                raw_src = args.source
                raw_tgt = args.target
                try:
                    src_ref = parse_reference(raw_src)
                    tgt_ref = parse_reference(raw_tgt)
                except Exception as exc:
                    sys.stderr.write(f"Error parsing scripture references: {exc}\n")
                    return 1

                rel_type = getattr(args, "type", RelationshipType.THEMATIC)
                weight = getattr(args, "weight", 1.0)
                notes = getattr(args, "notes", None)

                record = svc.link_passages(
                    source=src_ref,
                    target=tgt_ref,
                    relationship_type=rel_type,
                    weight=weight,
                    notes=notes,
                )
                print(
                    f"Linked {record.source_human_ref} ➜ {record.target_human_ref} "
                    f"[{record.relationship_type}] (id: {record.id}, weight: {record.weight:.2f})"
                )
                return 0

            elif action == "unlink":
                raw_src = args.source
                raw_tgt = args.target
                try:
                    src_ref = parse_reference(raw_src)
                    tgt_ref = parse_reference(raw_tgt)
                except Exception as exc:
                    sys.stderr.write(f"Error parsing scripture references: {exc}\n")
                    return 1

                rel_type = getattr(args, "type", None)
                deleted = svc.unlink_passages(src_ref, tgt_ref, relationship_type=rel_type)
                if deleted > 0:
                    print(f"Removed {deleted} cross-reference edge(s) between {src_ref.format()} and {tgt_ref.format()}.")
                else:
                    print(f"No cross-reference edges found between {src_ref.format()} and {tgt_ref.format()}.")
                return 0

            elif action == "list":
                rel_type = getattr(args, "type", None)
                limit = getattr(args, "limit", 100)
                as_json = getattr(args, "json", False)
                edges = svc.list_all_cross_references(relationship_type=rel_type, limit=limit)

                if as_json:
                    print(
                        json.dumps(
                            [
                                {
                                    "id": e.id,
                                    "source": e.source_human_ref,
                                    "target": e.target_human_ref,
                                    "relationship_type": e.relationship_type,
                                    "weight": e.weight,
                                    "notes": e.notes,
                                }
                                for e in edges
                            ],
                            indent=2,
                        )
                    )
                else:
                    print(format_cross_reference_table(edges, styling=color_enabled))
                return 0

            elif action == "path":
                raw_src = args.source
                raw_tgt = args.target
                try:
                    src_ref = parse_reference(raw_src)
                    tgt_ref = parse_reference(raw_tgt)
                except Exception as exc:
                    sys.stderr.write(f"Error parsing scripture references: {exc}\n")
                    return 1

                depth = getattr(args, "max_depth", 3)
                as_json = getattr(args, "json", False)
                path = svc.find_path(src_ref, tgt_ref, max_depth=depth)

                if as_json:
                    print(
                        json.dumps(
                            [
                                {
                                    "id": p.id,
                                    "source": p.source_human_ref,
                                    "target": p.target_human_ref,
                                    "relationship_type": p.relationship_type,
                                    "weight": p.weight,
                                    "notes": p.notes,
                                }
                                for p in (path or [])
                            ],
                            indent=2,
                        )
                    )
                else:
                    if not path:
                        print(f"No cross-reference path found connecting {src_ref.format()} and {tgt_ref.format()} within depth {depth}.")
                    else:
                        print(f"Cross-Reference Path connecting {src_ref.format()} and {tgt_ref.format()} ({len(path)} hop{'s' if len(path) != 1 else ''}):\n")
                        for idx, step in enumerate(path, 1):
                            icon = RelationshipType.get_icon(step.relationship_type)
                            label = RelationshipType.get_label(step.relationship_type)
                            print(f"  {idx}. {step.source_human_ref} ➜ {step.target_human_ref}  {icon} [{label}]")
                            if step.notes:
                                print(f"     Note: {step.notes}")
                return 0

            elif action == "stats":
                as_json = getattr(args, "json", False)
                summary = svc.get_summary_statistics()

                if as_json:
                    print(
                        json.dumps(
                            {
                                "total_edges": summary.total_edges,
                                "by_relationship_type": summary.by_relationship_type,
                                "testament_connections": summary.testament_connections,
                                "distinct_sources": summary.distinct_sources,
                                "distinct_targets": summary.distinct_targets,
                            },
                            indent=2,
                        )
                    )
                else:
                    print("Cross-Reference Knowledge Graph Statistics:")
                    print("============================================")
                    print(f"  Total Relational Edges:  {summary.total_edges}")
                    print(f"  Distinct Passages:       {summary.distinct_sources + summary.distinct_targets} ({summary.distinct_sources} sources, {summary.distinct_targets} targets)")
                    print("\nBy Relationship Type:")
                    for rel, cnt in summary.by_relationship_type.items():
                        icon = RelationshipType.get_icon(rel)
                        label = RelationshipType.get_label(rel)
                        print(f"  {icon}  {label:<30} {cnt:>5}")
                    print("\nTestament Trajectories:")
                    for t_conn, cnt in summary.testament_connections.items():
                        print(f"  {t_conn:<12} {cnt:>5}")
                return 0

            elif action == "seed":
                count = svc.seed_canonical_cross_references()
                print(f"Successfully seeded {count} canonical cross-reference edge(s).")
                return 0

            else:
                sys.stderr.write(f"Unknown cross-reference action: {action}\n")
                return 1

    except Exception as exc:
        sys.stderr.write(f"Cross-reference error: {exc}\n")
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
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Launch interactive scripture study REPL shell",
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
        help="Translation identifier(s) (e.g. 'ESV', 'WEB', or comma-separated 'ESV,WEB', default: ESV with offline WEB fallback)",
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
        "--verbose",
        "-v",
        action="store_true",
        help="Display verbose diagnostics and translation fallback notifications",
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
    parser_get.add_argument(
        "--width",
        "-w",
        type=int,
        default=None,
        help="Target line wrap width for reading (defaults to terminal width up to 88)",
    )
    parser_get.add_argument(
        "--margin",
        "-m",
        type=int,
        default=0,
        help="Left margin indentation width in spaces (default: 0)",
    )
    parser_get.add_argument(
        "--flow",
        action="store_true",
        help="Flow verses into continuous reader paragraph prose instead of line-by-line",
    )
    parser_get.add_argument(
        "--color",
        action="store_true",
        default=None,
        help="Force enable ANSI color styling (illuminated sacred theme)",
    )
    parser_get.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI color styling (plain monochrome text)",
    )
    parser_get.add_argument(
        "--theme",
        choices=["sacred", "amber", "cyan", "plain"],
        default="sacred",
        help="Color theme palette: sacred (gold), amber, cyan, or plain (default: sacred)",
    )
    parser_get.add_argument(
        "--box",
        action="store_true",
        help="Draw illuminated unicode box border around citation headers",
    )
    parser_get.add_argument(
        "--tags",
        action="store_true",
        help="Display semantic tags associated with this passage",
    )
    parser_get.add_argument(
        "--refs",
        "--cross-refs",
        dest="refs",
        action="store_true",
        help="Display related cross-references with hydrated verse texts",
    )
    parser_get.add_argument(
        "--pericopes",
        "-p",
        action="store_true",
        help="Display canonical pericope section headings and redemptive summaries",
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
        help="Translations to compare (comma-separated or repeated, e.g. 'ESV,WEB', default: installed versions or ESV,WEB)",
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
    parser_compare.add_argument(
        "--width",
        "-w",
        type=int,
        default=None,
        help="Target line wrap width for reading (defaults to terminal width up to 88)",
    )
    parser_compare.add_argument(
        "--margin",
        "-m",
        type=int,
        default=0,
        help="Left margin indentation width in spaces (default: 0)",
    )
    parser_compare.add_argument(
        "--color",
        action="store_true",
        default=None,
        help="Force enable ANSI color styling",
    )
    parser_compare.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI color styling",
    )
    parser_compare.add_argument(
        "--theme",
        choices=["sacred", "amber", "cyan", "plain"],
        default="sacred",
        help="Color theme palette: sacred (gold), amber, cyan, or plain (default: sacred)",
    )
    parser_compare.add_argument(
        "--box",
        action="store_true",
        help="Draw illuminated unicode box border around citation headers",
    )
    parser_compare.set_defaults(func=cmd_compare)


    # Subcommand: search (alias: find)
    parser_search = subparsers.add_parser(
        "search",
        aliases=["find"],
        help="Full-text search across scripture (e.g. 'light of the world', 'faith AND works')",
        description="High-performance SQLite FTS5 full-text search across scripture text.",
    )
    parser_search.add_argument(
        "query",
        nargs="+",
        help="Search query text, exact phrase, or Boolean operators (AND, OR, NOT)",
    )
    parser_search.add_argument(
        "--version",
        "-t",
        dest="version",
        default="WEB",
        help="Translation to search in local database (e.g. 'WEB', 'all', default: WEB [offline public domain])",
    )
    parser_search.add_argument(
        "--fallback",
        default="WEB",
        help="Fallback translation if requested version is missing (default: WEB)",
    )
    parser_search.add_argument(
        "--no-fallback",
        action="store_true",
        help="Disable automatic fallback cascade and fail if requested version is missing",
    )
    parser_search.add_argument(
        "--strict",
        action="store_true",
        help="Strictly require requested translation without fallback",
    )
    parser_search.add_argument(
        "--book",
        "-b",
        type=str,
        default=None,
        help="Filter search to specific book (e.g. 'John', 'Romans', 'Genesis')",
    )
    parser_search.add_argument(
        "--testament",
        choices=["ot", "nt", "OT", "NT"],
        default=None,
        help="Filter search to Old Testament (OT) or New Testament (NT)",
    )
    parser_search.add_argument(
        "--exact",
        "-e",
        action="store_true",
        help="Match search query as an exact contiguous phrase",
    )
    parser_search.add_argument(
        "--sort",
        choices=["relevance", "canonical"],
        default="relevance",
        help="Sort order: 'relevance' (BM25 rank) or 'canonical' (Genesis-Revelation)",
    )
    parser_search.add_argument(
        "--limit",
        "-n",
        type=int,
        default=20,
        help="Maximum results to return (default: 20)",
    )
    parser_search.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Pagination offset for results (default: 0)",
    )
    parser_search.add_argument(
        "--snippets",
        action="store_true",
        help="Display contextual snippets instead of full verse text",
    )
    parser_search.add_argument(
        "--count",
        action="store_true",
        help="Output total count of matching verses and exit",
    )
    parser_search.add_argument(
        "--no-highlight",
        action="store_true",
        help="Disable ANSI terminal color highlighting",
    )
    parser_search.add_argument(
        "--json",
        action="store_true",
        help="Output search results as JSON",
    )
    parser_search.set_defaults(func=cmd_search)

    # Subcommand: translations (alias: versions)
    parser_translations = subparsers.add_parser(
        "translations",
        aliases=["versions"],
        help="List installed scripture translations and verse counts",
        description="Inspect registered Bible translations, language, copyright status, and verse statistics.",
    )
    parser_translations.set_defaults(func=cmd_translations)

    # Subcommand: tag (aliases: tags)
    parser_tag = subparsers.add_parser(
        "tag",
        aliases=["tags"],
        help="Semantic tagging, passage annotations, and knowledge taxonomy",
        description="Attach, query, and manage semantic tags across verses and arbitrary spans.",
    )
    tag_subparsers = parser_tag.add_subparsers(dest="tag_action", help="Tag action to perform")

    # tag add
    p_tag_add = tag_subparsers.add_parser("add", help="Attach one or more tags to a verse or passage span")
    p_tag_add.add_argument("reference", help="Scripture citation or span (e.g. 'Romans 8:1-11', 'John 3:16')")
    p_tag_add.add_argument("tags", nargs="+", help="Tag name(s) to attach (e.g. 'Holy Spirit' 'Sanctification')")
    p_tag_add.add_argument("--category", "-c", default="thematic", help="Tag category (thematic, theological, etc.)")
    p_tag_add.add_argument("--notes", help="Optional notes or context for the tag association")
    p_tag_add.add_argument("--starred", action="store_true", help="Mark tag association as starred/priority")
    p_tag_add.add_argument("--confidence", type=float, default=1.0, help="Confidence score (0.0 to 1.0, default: 1.0)")

    # tag list
    p_tag_list = tag_subparsers.add_parser("list", help="List all defined semantic tags with usage metrics")
    p_tag_list.add_argument("--category", "-c", help="Filter tags by category")
    p_tag_list.add_argument(
        "--sort",
        choices=["passages", "name", "starred", "category"],
        default="passages",
        help="Sort order (default: passages)",
    )
    p_tag_list.add_argument("--json", action="store_true", help="Output results in JSON format")

    # tag show
    p_tag_show = tag_subparsers.add_parser("show", help="Display passages associated with a specific tag")
    p_tag_show.add_argument("tag", help="Tag name to inspect")
    p_tag_show.add_argument("--version", "-t", default="ESV", help="Scripture translation for verse text (default: ESV with offline WEB fallback)")
    p_tag_show.add_argument("--starred-only", action="store_true", help="Only show starred passages")
    p_tag_show.add_argument("--limit", "-n", type=int, default=20, help="Maximum passages to show (default: 20)")
    p_tag_show.add_argument("--json", action="store_true", help="Output results in JSON format")

    # tag for
    p_tag_for = tag_subparsers.add_parser("for", help="Display all tags applying to a specific verse or span")
    p_tag_for.add_argument("reference", help="Scripture citation or span (e.g. 'Romans 8:1', 'John 3:16')")
    p_tag_for.add_argument("--exact", action="store_true", help="Only match tags assigned to this exact reference boundary")
    p_tag_for.add_argument("--json", action="store_true", help="Output results in JSON format")

    # tag remove
    p_tag_rem = tag_subparsers.add_parser("remove", help="Remove a tag association from a specific passage citation")
    p_tag_rem.add_argument("reference", help="Scripture citation or span")
    p_tag_rem.add_argument("tag", help="Tag name to remove")

    # tag delete
    p_tag_del = tag_subparsers.add_parser("delete", help="Delete a tag definition and all its passage associations")
    p_tag_del.add_argument("tag", help="Tag name to delete")

    # tag stats
    p_tag_stats = tag_subparsers.add_parser("stats", help="Show aggregated metrics for a tag or all tags")
    p_tag_stats.add_argument("tag", nargs="?", default=None, help="Optional tag name to inspect")
    p_tag_stats.add_argument("--json", action="store_true", help="Output results in JSON format")

    # tag seed
    p_tag_seed = tag_subparsers.add_parser("seed", help="Seed canonical TGC theological and redemptive taxonomies")

    # tag prune
    p_tag_prune = tag_subparsers.add_parser(
        "prune",
        aliases=["clean"],
        help="Prune unlinked tags that have zero verse associations (preserves favorites)",
    )

    # tag prompt
    p_tag_prompt = tag_subparsers.add_parser("prompt", help="Generate and display LLM tagging prompt for a passage")
    p_tag_prompt.add_argument("reference", help="Scripture citation or span (e.g. 'Romans 8:1-11')")
    p_tag_prompt.add_argument("--version", "-t", default="ESV", help="Scripture translation ID (default: ESV with offline WEB fallback)")
    p_tag_prompt.add_argument("--category", help="Comma-separated category filter (e.g. 'theological,historical')")
    p_tag_prompt.add_argument("--custom-tags", help="Comma-separated custom candidate tags")
    p_tag_prompt.add_argument("--no-new-tags", action="store_true", help="Disallow novel tags outside taxonomy")
    p_tag_prompt.add_argument("--max-tags", type=int, default=6, help="Maximum tags to request (default: 6)")
    p_tag_prompt.add_argument("--format", choices=["text", "gemini", "json"], default="text", help="Output format")
    p_tag_prompt.add_argument("--output", "-o", help="Write prompt to output file")

    # tag generate
    p_tag_gen = tag_subparsers.add_parser("generate", help="Direct online LLM tagging via Google Gemini API")
    p_tag_gen.add_argument("reference", help="Scripture citation or span (e.g. 'Romans 8:1-11')")
    p_tag_gen.add_argument("--api-key", help="Google Gemini API key (defaults to $GEMINI_API_KEY)")
    p_tag_gen.add_argument("--model", default="gemini-2.5-pro", help="Gemini model ID (default: gemini-2.5-pro)")
    p_tag_gen.add_argument("--version", "-t", default="ESV", help="Scripture translation ID (default: ESV with offline WEB fallback)")
    p_tag_gen.add_argument("--category", help="Comma-separated category filter")
    p_tag_gen.add_argument("--custom-tags", help="Comma-separated custom candidate tags")
    p_tag_gen.add_argument("--no-new-tags", action="store_true", help="Disallow novel tags")
    p_tag_gen.add_argument("--max-tags", type=int, default=6, help="Maximum tags to produce")
    p_tag_gen.add_argument("--dry-run", action="store_true", help="Print tags without writing to database")
    p_tag_gen.add_argument("--source", default="llm-gemini", help="Provenance source identifier (default: llm-gemini)")

    # tag apply-llm (alias: apply)
    p_tag_apply = tag_subparsers.add_parser("apply-llm", aliases=["apply"], help="Parse and apply LLM tagging response payload to SQLite")
    p_tag_apply.add_argument("file", help="Path to response JSON or JSONL file (or '-' for stdin)")
    p_tag_apply.add_argument("--dry-run", action="store_true", help="Preview tags without writing to database")
    p_tag_apply.add_argument("--min-confidence", type=float, default=0.5, help="Minimum confidence threshold (0.0-1.0)")
    p_tag_apply.add_argument("--source", default="llm-gemini", help="Provenance source identifier (default: llm-gemini)")

    # tag batch
    p_tag_batch = tag_subparsers.add_parser("batch", help="Generate batch prompt requests (JSONL/JSON) for multiple passages")
    p_tag_batch.add_argument("--refs", help="Comma-separated citations (e.g. 'John 3:16, Romans 8:1')")
    p_tag_batch.add_argument("--favorites", action="store_true", help="Extract passages from favorite_bible_verses.csv")
    p_tag_batch.add_argument("--starred-only", action="store_true", help="With --favorites, filter to starred passages")
    p_tag_batch.add_argument("--book", help="Generate prompts for all chapters of a book")
    p_tag_batch.add_argument("--input-file", help="Path to text file containing references (one per line)")
    p_tag_batch.add_argument("--limit", type=int, help="Maximum passages to process")
    p_tag_batch.add_argument("--version", "-t", default="ESV", help="Scripture translation ID (default: ESV with offline WEB fallback)")
    p_tag_batch.add_argument("--category", help="Comma-separated category filter")
    p_tag_batch.add_argument("--no-new-tags", action="store_true", help="Disallow novel tags")
    p_tag_batch.add_argument("--max-tags", type=int, default=6, help="Maximum tags per passage")
    p_tag_batch.add_argument("--format", choices=["jsonl", "json"], default="jsonl", help="Batch output format")
    p_tag_batch.add_argument("--output", "-o", help="Write batch output to file")

    # tag density
    p_tag_density = tag_subparsers.add_parser("density", help="Compute topic density across canonical books")
    p_tag_density.add_argument("tag", nargs="?", default=None, help="Optional tag name to filter distribution")
    p_tag_density.add_argument("--category", "-c", help="Filter tags by category (thematic, theological, etc.)")
    p_tag_density.add_argument("--testament", "-T", choices=["OT", "NT", "ot", "nt"], help="Filter by Old or New Testament")
    p_tag_density.add_argument("--min-passages", type=int, default=0, help="Minimum passage count threshold (default: 0)")
    p_tag_density.add_argument("--ribbon", "-r", action="store_true", help="Render as visual ASCII Redemptive Ribbon heatmap")
    p_tag_density.add_argument("--json", action="store_true", help="Output results in JSON format")

    # tag co-occurrence (aliases: co-occur, matrix)
    p_tag_cooccur = tag_subparsers.add_parser("co-occurrence", aliases=["co-occur", "matrix"], help="Compute tag co-occurrence matrix and similarity indices")
    p_tag_cooccur.add_argument("tags", nargs="*", default=None, help="Optional specific tags to restrict matrix")
    p_tag_cooccur.add_argument("--category", "-c", help="Filter tags by category")
    p_tag_cooccur.add_argument("--min-shared", type=int, default=1, help="Minimum shared passages threshold (default: 1)")
    p_tag_cooccur.add_argument("--json", action="store_true", help="Output matrix in JSON format")

    # tag relevance (aliases: rank)
    p_tag_rel = tag_subparsers.add_parser("relevance", aliases=["rank"], help="Rank scripture passages matching query tags by relevance")
    p_tag_rel.add_argument("tags", nargs="+", help="One or more topic tag names to score (e.g. 'Atonement' 'Redemption')")
    p_tag_rel.add_argument("--version", "-t", default="ESV", help="Scripture translation for text hydration (default: ESV with offline WEB fallback)")
    p_tag_rel.add_argument("--starred-only", action="store_true", help="Only rank starred passages")
    p_tag_rel.add_argument("--min-score", type=float, default=0.0, help="Minimum relevance score threshold (0.0 to 1.0, default: 0.0)")
    p_tag_rel.add_argument("--limit", "-n", type=int, default=20, help="Maximum ranked results to display (default: 20)")
    p_tag_rel.add_argument("--no-text", action="store_true", help="Omit scripture text snippet from output")
    p_tag_rel.add_argument("--json", action="store_true", help="Output rankings in JSON format")

    parser_tag.set_defaults(func=cmd_tag)

    # Subcommand: crossref (aliases: xref, refs)
    parser_crossref = subparsers.add_parser(
        "crossref",
        aliases=["xref", "refs"],
        help="Scripture cross-referencing, typological arcs, and relationship edges",
        description="Query, explore, link, and analyze relational connections across scripture.",
    )
    xref_subparsers = parser_crossref.add_subparsers(dest="ref_action", help="Cross-reference action to perform")

    # crossref for
    p_xr_for = xref_subparsers.add_parser("for", help="Display all cross-references connected to a passage citation")
    p_xr_for.add_argument("reference", help="Scripture citation or span (e.g. 'Genesis 3:15', 'John 3:16')")
    p_xr_for.add_argument("--type", "-T", help="Filter by relationship type (thematic, prophecy_fulfillment, typology, quotation, allusion, parallel)")
    p_xr_for.add_argument("--version", "-t", default="ESV", help="Scripture translation for related verse texts (default: ESV with offline WEB fallback)")
    p_xr_for.add_argument("--min-weight", type=float, default=0.0, help="Minimum relationship weight threshold (default: 0.0)")
    p_xr_for.add_argument("--json", action="store_true", help="Output results in JSON format")

    # crossref link
    p_xr_link = xref_subparsers.add_parser("link", help="Create a relationship edge between two scripture passages")
    p_xr_link.add_argument("source", help="Source scripture citation or span (e.g. 'Genesis 3:15')")
    p_xr_link.add_argument("target", help="Target scripture citation or span (e.g. 'Galatians 4:4-5')")
    p_xr_link.add_argument("--type", "-T", default="thematic", help="Relationship type (thematic, prophecy_fulfillment, typology, quotation, allusion, parallel)")
    p_xr_link.add_argument("--weight", "-w", type=float, default=1.0, help="Relationship confidence/prominence weight (0.0 to 1.0, default: 1.0)")
    p_xr_link.add_argument("--notes", help="Theological rationale or scholarly note explaining the connection")

    # crossref unlink
    p_xr_unlink = xref_subparsers.add_parser("unlink", help="Remove relationship edge(s) between two scripture passages")
    p_xr_unlink.add_argument("source", help="Source scripture citation or span")
    p_xr_unlink.add_argument("target", help="Target scripture citation or span")
    p_xr_unlink.add_argument("--type", "-T", help="Filter by specific relationship type to delete")

    # crossref list
    p_xr_list = xref_subparsers.add_parser("list", help="List all stored cross-reference relationship edges")
    p_xr_list.add_argument("--type", "-T", help="Filter by relationship type")
    p_xr_list.add_argument("--limit", "-n", type=int, default=100, help="Maximum edges to display (default: 100)")
    p_xr_list.add_argument("--json", action="store_true", help="Output results in JSON format")

    # crossref path
    p_xr_path = xref_subparsers.add_parser("path", help="Find multi-hop cross-reference chain connecting two scripture passages")
    p_xr_path.add_argument("source", help="Starting scripture citation (e.g. 'Genesis 12:1-3')")
    p_xr_path.add_argument("target", help="Destination scripture citation (e.g. 'Galatians 3:16')")
    p_xr_path.add_argument("--max-depth", "-d", type=int, default=3, help="Maximum search depth (default: 3 hops)")
    p_xr_path.add_argument("--json", action="store_true", help="Output path in JSON format")

    # crossref stats
    p_xr_stats = xref_subparsers.add_parser("stats", help="Display summary statistics of cross-reference knowledge graph")
    p_xr_stats.add_argument("--json", action="store_true", help="Output statistics in JSON format")

    # crossref seed
    p_xr_seed = xref_subparsers.add_parser("seed", help="Seed curated canonical OT/NT cross-reference edges")

    parser_crossref.set_defaults(func=cmd_crossref)

    # Subcommand: doctor
    parser_doctor = subparsers.add_parser(
        "doctor",
        help="Run comprehensive health, dependency, and documentation diagnostics",
        description="Verify zero external dependencies, documentation sync, bash scripts, git hooks, and tests.",
    )
    parser_doctor.add_argument(
        "--fast",
        action="store_true",
        help="Run fast pre-commit checks only (<0.15s: dependencies, doc sync, shell scripts, hook status)",
    )
    parser_doctor.add_argument(
        "--fix",
        "-f",
        action="store_true",
        help="Self-healing mode: automatically repair fixable defects (install git hooks, bootstrap database)",
    )
    parser_doctor.add_argument(
        "--install-hooks",
        "--install-hook",
        dest="install_hooks",
        action="store_true",
        help="Install automated git pre-commit (fast) and pre-push (full) hooks in .git/hooks",
    )
    parser_doctor.add_argument(
        "--uninstall-hooks",
        action="store_true",
        help="Remove automated git hooks from .git/hooks",
    )
    parser_doctor.add_argument(
        "--check-hooks",
        action="store_true",
        help="Check git hook safeguards status only",
    )
    parser_doctor.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Quiet mode: suppress output and exit with status code only",
    )
    parser_doctor.add_argument(
        "--bench",
        "--benchmark",
        dest="bench",
        action="store_true",
        help="Include sovereign performance benchmark suite in diagnostics",
    )
    parser_doctor.add_argument(
        "--credentials",
        action="store_true",
        help="Audit external API credential configuration (ESV and Gemini)",
    )
    parser_doctor.add_argument(
        "--probe",
        action="store_true",
        help="Perform live network connectivity probe on configured API credentials",
    )
    parser_doctor.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON health report",
    )
    def cmd_doctor(args: argparse.Namespace) -> int:
        from tools.doctor import install_hooks, uninstall_hooks, check_git_hooks, run_all_checks, DoctorStyler
        repo_root = Path(__file__).resolve().parent.parent

        if getattr(args, "install_hooks", False):
            ok, msg = install_hooks(repo_root)
            print(msg)
            return 0 if ok else 1

        if getattr(args, "uninstall_hooks", False):
            ok, msg = uninstall_hooks(repo_root)
            print(msg)
            return 0 if ok else 1

        if getattr(args, "check_hooks", False):
            res = check_git_hooks(repo_root)
            styler = DoctorStyler(enabled=not getattr(args, "no_color", False))
            badge = styler.green("[PASS]") if res.passed else styler.red("[FAIL]")
            print(f"{badge} {res.name}: {res.details}")
            return 0 if res.passed else 1

        is_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty() and not sys.platform.startswith("win")
        fast_mode = getattr(args, "fast", False)
        quiet_mode = getattr(args, "quiet", False)
        fix_mode = getattr(args, "fix", False)
        bench_mode = getattr(args, "bench", False)
        credentials_mode = getattr(args, "credentials", False)
        probe_mode = getattr(args, "probe", False)
        json_mode = getattr(args, "json", False)
        code, _ = run_all_checks(
            repo_root=repo_root,
            color=is_tty and not json_mode,
            fast=fast_mode,
            quiet=quiet_mode,
            fix=fix_mode,
            bench=bench_mode,
            credentials=credentials_mode,
            probe=probe_mode,
            json_output=json_mode,
        )
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

    # Subcommand: shell (aliases: interactive, repl, console)
    parser_shell = subparsers.add_parser(
        "shell",
        aliases=["interactive", "repl", "console"],
        help="Launch interactive scripture study REPL shell",
        description="Interactive zero-dependency terminal shell with instant lookup, search, comparison, and theme customization.",
    )
    parser_shell.add_argument(
        "--version",
        "-t",
        default="ESV",
        help="Initial active translation ID (default: ESV with offline WEB fallback)",
    )
    parser_shell.add_argument(
        "--theme",
        choices=["sacred", "amber", "cyan", "plain"],
        default="sacred",
        help="Initial ANSI color theme (default: sacred)",
    )
    parser_shell.add_argument(
        "--margin",
        "-m",
        type=int,
        default=2,
        help="Initial left indentation margin (default: 2)",
    )
    parser_shell.add_argument(
        "--flow",
        action="store_true",
        help="Start in continuous paragraph reader mode",
    )
    parser_shell.add_argument(
        "--no-box",
        action="store_true",
        help="Disable decorative unicode box header",
    )

    def cmd_shell(args: argparse.Namespace) -> int:
        from cli.shell import launch_shell
        db_path = Path(args.db).resolve() if args.db else None
        return launch_shell(
            db_path=db_path,
            translation_id=args.version,
            theme=args.theme,
            margin=args.margin,
            flow=args.flow,
            box=not args.no_box,
        )

    parser_shell.set_defaults(func=cmd_shell)

    # -------------------------------------------------------------------------
    # serve / server / http subcommand
    # -------------------------------------------------------------------------
    parser_serve = subparsers.add_parser(
        "serve",
        aliases=["server", "http", "web"],
        help="Start built-in local HTTP web server and REST API",
        description="Launch zero-dependency local HTTP web server serving Sacred-Modern Web UI and REST API.",
    )
    parser_serve.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host IP address to bind (default: 127.0.0.1)",
    )
    parser_serve.add_argument(
        "--port",
        "-p",
        type=int,
        default=8080,
        help="Port to listen on (default: 8080)",
    )
    parser_serve.add_argument(
        "--open",
        action="store_true",
        help="Automatically open web browser at server URL",
    )
    parser_serve.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Log incoming HTTP requests to stderr",
    )

    def cmd_serve(args: argparse.Namespace) -> int:
        from web.server import create_server
        db_path = Path(args.db).resolve() if args.db else None
        server = create_server(
            host=args.host,
            port=args.port,
            db_path=db_path,
            verbose=args.verbose,
        )
        print("=" * 68)
        print("  Bible Engine — Sacred-Modern Web Server & REST API")
        print("=" * 68)
        print(f"  • Web UI:     {server.url}")
        print(f"  • REST API:   {server.url}/api/health")
        print(f"  • Database:   {server.database.db_path}")
        print(f"  • Bound Host: {server.bound_host}:{server.port}")
        print("-" * 68)
        print("  Press Ctrl+C to gracefully stop the server.\n")

        try:
            server.start(open_browser=args.open)
        except KeyboardInterrupt:
            print("\nShutting down Bible Engine web server...")
        finally:
            server.shutdown()
        return 0

    parser_serve.set_defaults(func=cmd_serve)

    # Subcommand: init / setup / bootstrap
    parser_init = subparsers.add_parser(
        "init",
        aliases=["setup", "bootstrap"],
        help="Bootstrap and compile sovereign scripture database from raw sources",
        description="Compile World English Bible (31,103 verses), favorites, canonical taxonomies, cross-references, and git hooks.",
    )
    parser_init.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Recompile and re-index database from scratch even if already initialized",
    )
    parser_init.add_argument(
        "--quick",
        action="store_true",
        help="Fast sample bootstrap (Genesis, John, Romans, Revelation) for rapid testing",
    )
    parser_init.add_argument(
        "--no-hooks",
        action="store_true",
        help="Skip automatic installation of git pre-commit and pre-push hooks",
    )
    parser_init.add_argument(
        "--wizard",
        "-w",
        action="store_true",
        help="Launch interactive API key onboarding wizard (ESV and Gemini exegesis)",
    )
    parser_init.add_argument(
        "--esv-key",
        type=str,
        default=None,
        help="Configure Crossway ESV API key during initialization",
    )
    parser_init.add_argument(
        "--gemini-key",
        type=str,
        default=None,
        help="Configure Google Gemini API key during initialization",
    )
    parser_init.add_argument(
        "--no-probe",
        action="store_true",
        help="Skip live network connectivity probes on configured API keys",
    )
    parser_init.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Quiet mode: suppress progress output",
    )

    def cmd_init(args: argparse.Namespace) -> int:
        from core.bootstrap import bootstrap_database
        db_path = Path(args.db).resolve() if args.db else DEFAULT_DB_PATH
        force = getattr(args, "force", False)
        quick = getattr(args, "quick", False)
        no_hooks = getattr(args, "no_hooks", False)
        quiet = getattr(args, "quiet", False)
        wizard = getattr(args, "wizard", False)
        esv_key = getattr(args, "esv_key", None)
        gemini_key = getattr(args, "gemini_key", None)
        probe_keys = not getattr(args, "no_probe", False)

        if not quiet:
            mode_str = " (Quick/Sample Mode)" if quick else ""
            if force:
                mode_str += " [Rebuild --force]"
            print(f"Bible Engine: Bootstrapping Sovereign Database{mode_str}...")

        rep = bootstrap_database(
            db_path=db_path,
            force=force,
            quick=quick,
            install_git_hooks=not no_hooks,
            verbose=not quiet,
            onboarding_wizard=wizard,
            esv_key=esv_key,
            gemini_key=gemini_key,
            probe_keys=probe_keys,
        )

        if not quiet:
            print("\n" + "=" * 65)
            print(" Sovereign Database Bootstrap Complete")
            print("=" * 65)
            for line in rep.summary_lines():
                print(f" {line}")
            print("=" * 65 + "\n")

        return 0 if rep.is_clean else 1

    parser_init.set_defaults(func=cmd_init)

    # Subcommand: db / database
    parser_db = subparsers.add_parser(
        "db",
        aliases=["database"],
        help="Inspect database health, table metrics, pragmas, and perform maintenance",
        description="Database storage metrics, statistics, vacuum, and optimization.",
    )
    db_subparsers = parser_db.add_subparsers(dest="db_action", help="Database maintenance action")

    p_db_stats = db_subparsers.add_parser("stats", aliases=["status"], help="Show database storage metrics, table row counts, and pragmas")
    p_db_init = db_subparsers.add_parser("init", aliases=["setup", "bootstrap"], help="Bootstrap offline database from raw sources")
    p_db_init.add_argument("--force", "-f", action="store_true", help="Recompile from scratch")
    p_db_init.add_argument("--quick", action="store_true", help="Fast sample bootstrap")
    p_db_init.add_argument("--no-hooks", action="store_true", help="Skip git hooks installation")
    p_db_init.add_argument("--quiet", "-q", action="store_true", help="Suppress progress output")

    p_db_opt = db_subparsers.add_parser("optimize", help="Run SQLite PRAGMA optimize and update query planner statistics")
    p_db_vac = db_subparsers.add_parser("vacuum", help="Reclaim unused disk space and defragment SQLite database")

    def cmd_db(args: argparse.Namespace) -> int:
        action = getattr(args, "db_action", None) or "stats"
        db_path = Path(args.db).resolve() if args.db else DEFAULT_DB_PATH

        if action in ("init", "setup", "bootstrap"):
            return cmd_init(args)

        if action in ("stats", "status"):
            from core.bootstrap import get_db_stats
            stats = get_db_stats(db_path)
            if not stats["exists"]:
                sys.stderr.write(
                    f"Error: Database file not found at '{db_path}'.\n"
                    f"Run './bible init' (or 'python3 tools/doctor.py --fix') to bootstrap.\n"
                )
                return 1

            print("=" * 65)
            print(" Bible Engine Database Diagnostics & Storage Status")
            print("=" * 65)
            print(f" File Location:        {stats['path']}")
            print(f" File Size:            {stats['size_human']} ({stats['size_bytes']:,} bytes)")
            print(f" SQLite Version:       {stats['sqlite_version']}")
            print(f" Integrity Check:      {stats['integrity_check']}")
            print(f" Journal Mode:         {stats['journal_mode'].upper()}")
            print(f" Page Size / Count:    {stats['page_size']} bytes / {stats['page_count']:,} pages")
            print(f" FTS5 Search Index:    {stats['fts5_status'].upper()}")
            print("-" * 65)
            print(f" Total Verses:         {stats['total_verses']:,}")
            for tr in stats["translations"]:
                print(f"   - {tr['id']}: {tr['name']} ({tr['verse_count']:,} verses)")
            print(f" Total Tags:           {stats['total_tags']} taxonomies")
            print(f" Tagged Passages:      {stats['total_tagged_passages']} annotations")
            print(f" Curated Favorites:    {stats['total_favorites']} passages ({stats['total_starred']} starred)")
            print(f" Cross-References:     {stats['total_cross_references']} canonical links")
            print("=" * 65)
            return 0

        if action == "optimize":
            if not db_path.exists():
                sys.stderr.write(f"Error: Database file not found at '{db_path}'.\n")
                return 1
            with Database(db_path) as db:
                db.optimize()
            print(f"Successfully optimized SQLite database query planner and statistics at '{db_path}'.")
            return 0

        if action == "vacuum":
            if not db_path.exists():
                sys.stderr.write(f"Error: Database file not found at '{db_path}'.\n")
                return 1
            with Database(db_path) as db:
                db.vacuum()
            print(f"Successfully vacuumed database and reclaimed unused storage at '{db_path}'.")
            return 0

        sys.stderr.write(f"Unknown db action '{action}'. Available: stats, status, init, optimize, vacuum\n")
        return 1

    parser_db.set_defaults(func=cmd_db)

    # Subcommand: ribbon (alias for ./bible tag density --ribbon)
    parser_ribbon = subparsers.add_parser(
        "ribbon",
        help="Display visual ASCII Canonical Redemptive Ribbon heatmap across all 66 books",
        description="Render illuminated canonical thematic heatmap visualizing topic density across 66 books.",
    )
    parser_ribbon.add_argument("tag", nargs="?", default=None, help="Optional topic tag name (e.g. 'Covenant', 'Justification')")
    parser_ribbon.add_argument("--category", "-c", help="Filter tags by category")
    parser_ribbon.add_argument("--testament", "-T", choices=["OT", "NT", "ot", "nt"], help="Filter by Old or New Testament")
    parser_ribbon.add_argument("--json", action="store_true", help="Output density data as JSON")

    def cmd_ribbon(args: argparse.Namespace) -> int:
        setattr(args, "ribbon", True)
        setattr(args, "min_passages", 0)
        setattr(args, "tag_action", "density")
        return cmd_tag(args)

    parser_ribbon.set_defaults(func=cmd_ribbon)

    # Subcommand: pericopes (alias: pericope)
    parser_pericopes = subparsers.add_parser(
        "pericopes",
        aliases=["pericope"],
        help="Inspect or search canonical pericope headings and redemptive-historical summaries",
        description="List and explore canonical pericopes, passage outlines, and redemptive summaries.",
    )
    parser_pericopes.add_argument("query", nargs="?", default=None, help="Scripture passage or search keyword (e.g. 'Gen 1', 'Romans', 'covenant')")
    parser_pericopes.add_argument("--book", "-b", help="Filter pericopes by specific book (e.g. 'Genesis', 'Rom')")
    parser_pericopes.add_argument("--json", action="store_true", help="Output pericopes in JSON format")

    def cmd_pericopes(args: argparse.Namespace) -> int:
        db_path = Path(args.db).resolve() if args.db else DEFAULT_DB_PATH
        if not db_path.exists():
            sys.stderr.write(f"Database not found at '{db_path}'. Run './bible init' first.\n")
            return 1
        with Database(db_path) as db:
            from core.pericopes import PericopeService
            from core.terminal import format_pericope_table
            svc = PericopeService(db)

            query = getattr(args, "query", None)
            book_filter = getattr(args, "book", None)
            color_enabled = False if getattr(args, "no_color", False) else (True if getattr(args, "color", None) else should_use_color())

            pericopes = []
            if query:
                # Try parsing as reference
                ref = parse_reference(query)
                if ref:
                    pericopes = svc.get_pericopes_for_passage(ref)
                else:
                    # Treat query as book or search term
                    book_match = get_book(query.strip())
                    if book_match:
                        pericopes = svc.get_pericopes_for_book(book_match.name)
                    else:
                        # Fallback search title / summary
                        all_p = db.get_pericopes_for_book(None)
                        q_lower = query.lower()
                        pericopes = [p for p in all_p if q_lower in p.title.lower() or (p.redemptive_summary and q_lower in p.redemptive_summary.lower())]
            elif book_filter:
                book_match = get_book(book_filter.strip())
                book_name = book_match.name if book_match else book_filter
                pericopes = svc.get_pericopes_for_book(book_name)
            else:
                pericopes = db.get_pericopes_for_book(None)

            if getattr(args, "json", False):
                print(json.dumps([p.to_dict() for p in pericopes], indent=2))
            else:
                title_desc = f" for '{query or book_filter}'" if (query or book_filter) else ""
                print(f"Canonical Pericopes & Redemptive Summaries{title_desc} ({len(pericopes)} entries):\n")
                print(format_pericope_table(pericopes, styling=color_enabled))
            return 0

    parser_pericopes.set_defaults(func=cmd_pericopes)

    # Subcommand: chapters (alias: chapter)
    parser_chapters = subparsers.add_parser(
        "chapters",
        aliases=["chapter"],
        help="Display chapter-by-chapter topic density drill-down for a book",
        description="Drill down into a book's individual chapters to visualize topical and thematic density.",
    )
    parser_chapters.add_argument("book", help="Book of the Bible to inspect (e.g. 'Genesis', 'Romans', 'John')")
    parser_chapters.add_argument("tag", nargs="?", default=None, help="Optional topic tag name (e.g. 'Covenant', 'Grace')")
    parser_chapters.add_argument("--category", "-c", help="Filter tags by category")
    parser_chapters.add_argument("--json", action="store_true", help="Output chapter density as JSON")

    def cmd_chapters(args: argparse.Namespace) -> int:
        db_path = Path(args.db).resolve() if args.db else DEFAULT_DB_PATH
        if not db_path.exists():
            sys.stderr.write(f"Database not found at '{db_path}'. Run './bible init' first.\n")
            return 1
        with Database(db_path) as db:
            from core.tags import TaggingService
            from core.terminal import format_chapter_density_grid
            svc = TaggingService(db)

            book_input = args.book.strip()
            book_match = get_book(book_input)
            if not book_match:
                sys.stderr.write(f"Error: Unknown book '{book_input}'.\n")
                return 1

            tag_name = getattr(args, "tag", None)
            cat = getattr(args, "category", None)
            color_enabled = False if getattr(args, "no_color", False) else (True if getattr(args, "color", None) else should_use_color())

            chapters = svc.get_topic_density_per_chapter(
                book=book_match.name,
                tag_name=tag_name,
                category=cat,
            )

            if getattr(args, "json", False):
                print(json.dumps([c.to_dict() for c in chapters], indent=2))
            else:
                print(format_chapter_density_grid(
                    book_name=book_match.name,
                    chapters=chapters,
                    styling=color_enabled,
                    tag_name=tag_name,
                ))
            return 0

    parser_chapters.set_defaults(func=cmd_chapters)

    # Subcommand: arcs (aliases: arc, typology, typologies)
    parser_arcs = subparsers.add_parser(
        "arcs",
        aliases=["arc", "typology", "typologies"],
        help="Render pure vector SVG Typological Arc Network & explore Old/New Testament fulfillments",
        description="Visualize Old Testament shadows connected to New Testament fulfillments via pure vector Bézier SVG curves and terminal bridge diagrams.",
    )
    parser_arcs.add_argument("book_or_type", nargs="?", default=None, help="Optional topic, relationship type (e.g. 'typology', 'prophecy'), or book name")
    parser_arcs.add_argument("--type", "-t", help="Filter by relationship type (e.g. 'typology', 'prophecy_fulfillment', 'quotation', 'thematic')")
    parser_arcs.add_argument("--book", "-b", help="Filter arcs connected to a specific canonical book (e.g. 'Genesis', 'Hebrews')")
    parser_arcs.add_argument("--testament", "-T", choices=["OT-NT", "all", "ot-nt", "ALL"], default="OT-NT", help="Filter scope (default: 'OT-NT' for inter-testament fulfillments)")
    parser_arcs.add_argument("--svg", "-o", help="Export high-resolution standalone vector SVG to specified file path (e.g. 'arcs.svg')")
    parser_arcs.add_argument("--theme", choices=["obsidian", "scriptorium", "monastery", "transparent"], default="obsidian", help="Aesthetic visual theme for SVG (default: obsidian)")
    parser_arcs.add_argument("--width", type=int, default=1200, help="Width in pixels for generated SVG (default: 1200)")
    parser_arcs.add_argument("--height", type=int, default=520, help="Height in pixels for generated SVG (default: 520)")
    parser_arcs.add_argument("--json", action="store_true", help="Output raw arc network data in JSON format")
    parser_arcs.add_argument("--color", action="store_true", default=None, help="Force enable ANSI color styling")
    parser_arcs.add_argument("--no-color", action="store_true", help="Disable ANSI color styling")

    def cmd_arcs(args: argparse.Namespace) -> int:
        db_path = Path(args.db).resolve() if args.db else DEFAULT_DB_PATH
        if not db_path.exists():
            sys.stderr.write(f"Database not found at '{db_path}'. Run './bible init' first.\n")
            return 1

        with Database(db_path) as db:
            from core.arcs import build_arc_network
            from core.crossref import RelationshipType
            from core.reference import get_book

            pos_val = getattr(args, "book_or_type", None)
            rel_type = getattr(args, "type", None)
            book = getattr(args, "book", None)

            if pos_val and not rel_type and not book:
                if RelationshipType.is_valid(pos_val):
                    rel_type = pos_val
                elif get_book(pos_val):
                    book = pos_val
                elif pos_val.lower() in ("prophecy", "prophecies"):
                    rel_type = "prophecy_fulfillment"
                else:
                    rel_type = pos_val

            testament = getattr(args, "testament", "OT-NT")
            theme = getattr(args, "theme", "obsidian")
            width = getattr(args, "width", 1200)
            height = getattr(args, "height", 520)
            svg_out = getattr(args, "svg", None)
            color_enabled = False if getattr(args, "no_color", False) else (True if getattr(args, "color", None) else should_use_color())

            net = build_arc_network(
                db,
                relationship_type=rel_type,
                book_filter=book,
                testament_filter=testament,
                theme=theme,
                width=width,
                height=height,
            )

            if getattr(args, "json", False):
                print(json.dumps(net.to_dict(), indent=2))
                return 0

            if svg_out:
                svg_content = net.render_svg(standalone=True, interactive=True)
                out_path = Path(svg_out).resolve()
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(svg_content, encoding="utf-8")
                size_str = f"{len(svg_content.encode('utf-8')):,} bytes"
                print(f"Exported pure vector SVG Typological Arc Network to '{out_path}' ({size_str})")

            print(net.render_terminal_summary(color=color_enabled))
            return 0

    parser_arcs.set_defaults(func=cmd_arcs)

    def parse_font_size_arg(val: Optional[str]) -> Optional[float]:
        """Parse font size CLI argument (e.g. '48', '64pt', 'auto', 'fit')."""
        if val is None:
            return None
        val_str = str(val).strip().lower()
        if val_str in ("auto", "none", "fit", "default"):
            return None
        if val_str.endswith("pt") or val_str.endswith("px"):
            val_str = val_str[:-2].strip()
        try:
            num = float(val_str)
            if num <= 0:
                raise argparse.ArgumentTypeError("Font size must be greater than 0.")
            return num
        except ValueError:
            raise argparse.ArgumentTypeError(f"Invalid font size '{val}'. Expected a number (e.g. 48, 64pt) or 'auto'.")

    def parse_safe_area_arg(val: Optional[str]) -> float:
        """Parse TV safe area margin percentage (e.g. '15%', '15', '0.15')."""
        if val is None:
            return 0.15
        val_str = str(val).strip()
        if val_str.endswith("%"):
            val_str = val_str[:-1].strip()
        try:
            num = float(val_str)
            if num > 1.0:
                num = num / 100.0
            if num < 0.0 or num >= 0.5:
                raise argparse.ArgumentTypeError("Safe area margin must be between 0% and 50% (0.0 to 0.5).")
            return num
        except ValueError:
            raise argparse.ArgumentTypeError(f"Invalid safe area margin '{val}'. Expected a percentage (e.g. 15% or 0.15).")

    # Subcommand: slide (aliases: render)
    parser_slide = subparsers.add_parser(
        "slide",
        aliases=["render"],
        help="Generate visual verse slides for TV screensavers and digital displays",
        description="Generate high-resolution 16:9 4K UHD or 1080p landscape scripture slides with OLED pure black, dynamic typography, and TV safe margins.",
    )
    parser_slide.add_argument(
        "reference",
        nargs="?",
        default=None,
        help="Scripture citation or passage (e.g. 'John 3:16', 'Romans 8:28-30', 'Psalm 23:1-3')",
    )
    parser_slide.add_argument(
        "--output",
        "-o",
        dest="output",
        default=None,
        help="Destination file path for generated slide (e.g. 'verse.png', 'slide.svg', '-' for stdout)",
    )
    parser_slide.add_argument(
        "--resolution",
        "-r",
        default="4k",
        help="Display resolution preset ('4k', '1080p', '720p', 'square', or 'WIDTHxHEIGHT', default: 4k)",
    )
    parser_slide.add_argument(
        "--theme",
        "-t",
        default="oled_black",
        help="Color theme ('oled_black', 'charcoal', 'obsidian', 'monastery', 'inverted', 'parchment', default: oled_black)",
    )
    parser_slide.add_argument(
        "--format",
        "-f",
        dest="output_format",
        choices=["png", "jpg", "jpeg", "svg"],
        default=None,
        help="Output file format ('png', 'jpg', 'svg', default: determined from output extension or png)",
    )
    parser_slide.add_argument(
        "--backend",
        "-b",
        choices=["auto", "imagemagick", "svg"],
        default="auto",
        help="Rendering backend: 'auto', 'imagemagick' (raster), or 'svg' (pure vector, default: auto)",
    )
    parser_slide.add_argument(
        "--version",
        dest="version",
        default="ESV",
        help="Scripture translation identifier (default: ESV with offline WEB fallback)",
    )
    parser_slide.add_argument(
        "--font",
        dest="font_family",
        default=None,
        help="Custom font family name or CSS stack (e.g. 'Georgia, serif')",
    )
    parser_slide.add_argument(
        "--font-size",
        type=parse_font_size_arg,
        default=None,
        help="Typography font size in points (e.g. 48, 64pt, or 'auto' for dynamic fitting, default: auto)",
    )
    parser_slide.add_argument(
        "--line-spacing",
        type=float,
        default=1.5,
        help="Line height multiplier for verse typography (default: 1.5)",
    )
    parser_slide.add_argument(
        "--citation-style",
        choices=["below", "smallcaps", "none"],
        default="below",
        help="Citation typography style ('below', 'smallcaps', 'none', default: below)",
    )
    parser_slide.add_argument(
        "--citation-color",
        "-c",
        type=str,
        default=None,
        help="Custom citation text color (hex e.g. '#D4AF37' or named color like 'gold')",
    )
    parser_slide.add_argument(
        "--accent-color",
        type=str,
        default=None,
        help="Custom decorative accent divider rule color (hex or named color)",
    )
    parser_slide.add_argument(
        "--tags",
        action="store_true",
        help="Display active semantic tags on the slide footer",
    )
    parser_slide.add_argument(
        "--no-balance",
        action="store_true",
        help="Disable balanced word wrapping (revert to greedy first-fit line breaking)",
    )
    parser_slide.add_argument(
        "--optical-center",
        type=float,
        default=0.45,
        help="Optical vertical centering ratio baseline between 0.0 and 1.0 (default: 0.45 for human golden eye line)",
    )
    parser_slide.add_argument(
        "--safe-area",
        type=parse_safe_area_arg,
        default=0.15,
        help="TV safe area margin percentage (e.g. '15%%', '15', '0.15', default: 15%%)",
    )
    parser_slide.add_argument(
        "--align",
        choices=["center", "left", "right"],
        default="center",
        help="Text alignment within canvas (default: center)",
    )
    parser_slide.add_argument(
        "--no-rule",
        action="store_true",
        help="Disable decorative illuminated accent divider rule between body and citation",
    )
    parser_slide.add_argument(
        "--quality",
        type=int,
        default=95,
        help="JPEG quality level from 10 to 100 (default: 95)",
    )
    parser_slide.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="DPI rendering density for rasterization (default: 300)",
    )
    parser_slide.add_argument(
        "--open",
        action="store_true",
        help="Open generated slide in system default image viewer",
    )
    parser_slide.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress console status summary",
    )
    parser_slide.add_argument(
        "--list-themes",
        action="store_true",
        help="List all available slide color themes and styling descriptions",
    )
    parser_slide.add_argument(
        "--list-resolutions",
        action="store_true",
        help="List all standard resolution presets and dimensions",
    )
    parser_slide.add_argument(
        "--paginate",
        action="store_true",
        help="Enable multi-slide pagination (or force passage splitting across multiple slides)",
    )
    parser_slide.add_argument(
        "--no-paginate",
        action="store_true",
        help="Disable pagination; force entire passage onto a single slide",
    )
    parser_slide.add_argument(
        "--max-verses",
        type=int,
        default=None,
        help="Maximum verses per slide before paginating (e.g. 2, 3)",
    )
    parser_slide.add_argument(
        "--max-lines",
        type=int,
        default=None,
        help="Maximum wrapped lines per slide before paginating (default: 8)",
    )
    parser_slide.add_argument(
        "--max-chars",
        type=int,
        default=None,
        help="Maximum characters per slide before paginating (default: 420)",
    )
    parser_slide.add_argument(
        "--page-format",
        type=str,
        default="{page} / {total}",
        help="Multi-slide page indicator format string (default: '{page} / {total}')",
    )
    parser_slide.add_argument(
        "--no-page-indicator",
        action="store_true",
        help="Suppress multi-slide page indicator in footer",
    )
    parser_slide.add_argument(
        "--keep-citation",
        action="store_true",
        help="Preserve parent passage citation across all slides instead of sub-verse citations",
    )
    parser_slide.add_argument(
        "--output-dir",
        "-d",
        type=str,
        default=None,
        help="Directory to save generated slide files",
    )

    def cmd_slide(args: argparse.Namespace) -> int:
        from core.render import (
            ImageMagickNotFoundError,
            PaginationConfig,
            RenderConfig,
            RenderError,
            SlideContent,
            format_resolution_table,
            format_theme_table,
            get_default_engine,
            get_theme,
            normalize_color,
            paginate_verses,
            parse_resolution,
        )

        color_enabled = (
            hasattr(sys.stdout, "isatty")
            and sys.stdout.isatty()
            and "NO_COLOR" not in os.environ
        )

        if getattr(args, "list_themes", False):
            print(format_theme_table(styling=color_enabled))
            return 0

        if getattr(args, "list_resolutions", False):
            print(format_resolution_table(styling=color_enabled))
            return 0

        ref_str = args.reference
        if not ref_str:
            sys.stderr.write(
                "Error: Scripture reference required (e.g. 'John 3:16', 'Romans 8:28-30').\n"
                "Use '--list-themes' or '--list-resolutions' to view available styling options.\n"
            )
            return 1

        db_path = Path(args.db).resolve() if args.db else DEFAULT_DB_PATH
        if not db_path.exists():
            sys.stderr.write(f"Database not found at '{db_path}'. Run './bible init' first.\n")
            return 1

        ref = parse_reference(ref_str)
        if ref is None:
            sys.stderr.write(f"Error: Could not parse '{ref_str}' as a canonical scripture reference.\n")
            return 1

        with Database(db_path) as db:
            from core.pericopes import PericopeService

            verses, used_id, is_fallback = db.get_verses_with_fallback(
                ref, translation_id=args.version
            )
            if not verses:
                sys.stderr.write(f"Error: No verses found for '{ref_str}' in translation '{args.version}'.\n")
                return 1

            verse_text = " ".join(v.text.strip() for v in verses)
            citation_str = ref.format()

            # Attempt to fetch pericope title for context
            pericope_svc = PericopeService(db)
            pericopes = pericope_svc.get_pericopes_for_passage(ref)
            pericope_title = pericopes[0].title if pericopes else None

            # Retrieve semantic tags if requested
            slide_tags: List[str] = []
            if getattr(args, "tags", False):
                from core.tags import TaggingService
                tagging_svc = TaggingService(db)
                passages = tagging_svc.get_tags_for_passage(ref)
                slide_tags = [p.tag_name for p in passages if p.tag_name]

            # Determine output destination and format
            out_dest = args.output
            output_dir = getattr(args, "output_dir", None)
            target_format = args.output_format
            is_stdout = out_dest in ("-", "stdout")

            if out_dest and not is_stdout:
                dest_path = Path(out_dest).resolve()
                ext = dest_path.suffix.lower().lstrip(".")
                if not target_format and ext in ("png", "jpg", "jpeg", "svg"):
                    target_format = ext
            elif not is_stdout:
                target_format = target_format or "png"
                safe_stem = re.sub(r"[^a-zA-Z0-9_]+", "_", citation_str).strip("_").lower()
                dest_path = Path.cwd() / f"slide_{safe_stem}.{target_format}"
            else:
                dest_path = None

            target_format = target_format or "png"
            safe_stem = re.sub(r"[^a-zA-Z0-9_]+", "_", citation_str).strip("_").lower()

            # Parse dimensions and theme
            w, h = parse_resolution(args.resolution)
            theme = get_theme(args.theme)

            config = RenderConfig(
                width=w,
                height=h,
                theme=theme,
                safe_area_pct=args.safe_area,
                font_family=getattr(args, "font_family", None),
                font_size=args.font_size,
                line_spacing=getattr(args, "line_spacing", 1.5),
                text_align=args.align,
                citation_style=getattr(args, "citation_style", "below"),
                citation_color=normalize_color(getattr(args, "citation_color", None)),
                accent_color=normalize_color(getattr(args, "accent_color", None)),
                optical_center_pct=getattr(args, "optical_center", 0.45),
                balance_lines=not getattr(args, "no_balance", False),
                show_accent_rule=not args.no_rule,
                show_tags=bool(args.tags),
                backend=args.backend,
                output_format=target_format,
                jpeg_quality=args.quality,
                dpi=args.dpi,
            )

            # Configure multi-slide pagination
            paginate_flag = getattr(args, "paginate", False)
            no_paginate_flag = getattr(args, "no_paginate", False)
            max_verses = getattr(args, "max_verses", None)
            max_lines = getattr(args, "max_lines", None)
            max_chars = getattr(args, "max_chars", None)
            page_format = getattr(args, "page_format", "{page} / {total}")
            show_indicator = not getattr(args, "no_page_indicator", False)
            keep_citation = getattr(args, "keep_citation", False)

            if no_paginate_flag:
                pagination = PaginationConfig(enabled=False)
            else:
                pagination = PaginationConfig(
                    enabled=True,
                    mode="always" if paginate_flag else "auto",
                    max_verses_per_slide=max_verses,
                    max_lines_per_slide=max_lines,
                    max_chars_per_slide=max_chars,
                    indicator_format=page_format,
                    show_indicator=show_indicator,
                    sub_citations=not keep_citation,
                    keep_parent_citation=keep_citation,
                )

            slide_contents = paginate_verses(
                verses=verses,
                parent_ref=ref,
                config=config,
                pagination=pagination,
                pericope_title=pericope_title,
                tags=slide_tags,
            )

            if not slide_contents:
                slide_contents = [
                    SlideContent(
                        text=verse_text,
                        citation=citation_str,
                        translation=used_id,
                        pericope_title=pericope_title,
                        tags=slide_tags,
                    )
                ]

            engine = get_default_engine()
            try:
                if is_stdout:
                    if target_format == "svg":
                        for c in slide_contents:
                            res = engine.render(c, config)
                            sys.stdout.buffer.write(res.data)
                            if len(slide_contents) > 1:
                                sys.stdout.buffer.write(b"\n")
                        sys.stdout.buffer.flush()
                        return 0
                    else:
                        if len(slide_contents) > 1:
                            sys.stderr.write("Notice: Stdout output for binary image formats only streams slide 1 of sequence.\n")
                        res = engine.render(slide_contents[0], config)
                        sys.stdout.buffer.write(res.data)
                        sys.stdout.buffer.flush()
                        return 0
                elif output_dir:
                    out_dir_path = Path(output_dir).resolve()
                    results = engine.render_sequence_to_dir(
                        slide_contents,
                        destination_dir=out_dir_path,
                        file_prefix=f"slide_{safe_stem}",
                        config=config,
                    )
                else:
                    assert dest_path is not None
                    results = engine.render_sequence_to_files(
                        slide_contents,
                        destination=dest_path,
                        config=config,
                    )
            except ImageMagickNotFoundError as exc:
                sys.stderr.write(f"ImageMagick Error: {exc}\nTip: Run with '--backend=svg' or install ImageMagick on your system.\n")
                return 1
            except RenderError as exc:
                sys.stderr.write(f"Render Error: {exc}\n")
                return 1

            if not getattr(args, "quiet", False):
                if len(results) == 1:
                    result = results[0]
                    size_str = f"{len(result.data):,} bytes"
                    print(f"Generated {result.width}x{result.height} {result.format.upper()} slide ({size_str}) via {result.backend}:")
                    print(f"  • File:       {result.file_path or dest_path}")
                    print(f"  • Passage:    {citation_str} ({used_id})")
                    print(f"  • Theme:      {theme.name}")
                    if config.citation_color:
                        print(f"  • Citation:   {config.citation_color} ({config.citation_style})")
                    if slide_tags:
                        print(f"  • Tags:       {', '.join(slide_tags)}")
                else:
                    res0 = results[0]
                    print(f"Generated {len(results)}-slide sequence ({res0.width}x{res0.height} {res0.format.upper()}) via {res0.backend}:")
                    print(f"  • Passage:    {citation_str} ({used_id})")
                    print(f"  • Theme:      {theme.name}")
                    print(f"  • Sequence:   {len(results)} slides auto-paginated for optimal display readability")
                    for i, res in enumerate(results):
                        c = slide_contents[i]
                        size_str = f"{len(res.data):,} bytes"
                        ind = f"[{c.page_indicator}]" if c.page_indicator else f"[{i+1}/{len(results)}]"
                        print(f"    {ind:<9} {res.file_path} ({size_str}) — {c.citation}")

            if getattr(args, "open", False) and results:
                target_open = results[0].file_path or dest_path
                if target_open:
                    try:
                        import subprocess
                        opener = "open" if sys.platform == "darwin" else "xdg-open"
                        subprocess.Popen([opener, str(target_open)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    except Exception:
                        pass

            return 0

    parser_slide.set_defaults(func=cmd_slide)

    # Subcommand: slide-batch (aliases: batch-slide, slides-batch, batch-render, slidebatch)
    parser_slide_batch = subparsers.add_parser(
        "slide-batch",
        aliases=["batch-slide", "slides-batch", "batch-render", "slidebatch"],
        help="Batch export visual verse slides for Google Photos, Chromecast, and TV screensavers",
        description=(
            "Generate high-resolution 16:9 4K UHD or 1080p scripture slide albums from user favorites, "
            "curated reading plans, thematic tags, canonical books, or custom reference lists, complete with "
            "an offline Sacred-Modern HTML gallery (index.html) and manifest.json."
        ),
    )
    # Source options
    parser_slide_batch.add_argument(
        "references",
        nargs="*",
        default=None,
        help="Optional explicit scripture citations to render (e.g. 'John 3:16' 'Romans 8:28')",
    )
    parser_slide_batch.add_argument(
        "--favorites",
        action="store_true",
        help="Export user curated favorite passages (from favorite_bible_verses.csv / database)",
    )
    parser_slide_batch.add_argument(
        "--starred-only",
        action="store_true",
        help="Filter favorites or tags to only starred/prioritized passages",
    )
    parser_slide_batch.add_argument(
        "--tag",
        type=str,
        default=None,
        help="Export all scripture passages associated with a semantic tag (e.g. 'Covenant', 'Grace')",
    )
    parser_slide_batch.add_argument(
        "--book",
        type=str,
        default=None,
        help="Export all pericopes or chapters of a canonical book (e.g. 'Romans', 'James', 'Psalms')",
    )
    parser_slide_batch.add_argument(
        "--plan",
        "--reading-plan",
        type=str,
        default=None,
        help="Export passages from a curated reading plan (e.g. 'psalms_of_ascent', 'sermon', 'romans_road')",
    )
    parser_slide_batch.add_argument(
        "--list-plans",
        action="store_true",
        help="List all available curated reading plans with passage counts and descriptions",
    )
    parser_slide_batch.add_argument(
        "--file",
        type=str,
        default=None,
        help="File path containing scripture citations (one per line)",
    )
    # Album & Destination options
    parser_slide_batch.add_argument(
        "--output-dir",
        "-d",
        type=str,
        default=None,
        help="Destination directory for generated slide album (default: exports/slides/<album_name>)",
    )
    parser_slide_batch.add_argument(
        "--title",
        type=str,
        default=None,
        help="Custom title for the exported album and HTML visual gallery",
    )
    parser_slide_batch.add_argument(
        "--resolution",
        "-r",
        type=str,
        default="4k",
        help="Resolution preset ('4k', '1080p', 'square', 'portrait_1080p') or WxH (default: '4k')",
    )
    parser_slide_batch.add_argument(
        "--theme",
        "-t",
        type=str,
        default="oled_black",
        help="Color theme ('oled_black', 'charcoal', 'obsidian', 'monastery', 'inverted', 'parchment')",
    )
    parser_slide_batch.add_argument(
        "--output-format",
        "-f",
        type=str,
        default="png",
        choices=["png", "jpg", "jpeg", "svg"],
        help="Output image format: 'png' (lossless, default), 'jpg' (JPEG), 'svg' (vector)",
    )
    parser_slide_batch.add_argument(
        "--version",
        dest="version",
        default="ESV",
        help="Scripture translation identifier (default: ESV with offline WEB fallback)",
    )
    parser_slide_batch.add_argument(
        "--backend",
        "-b",
        type=str,
        default="auto",
        choices=["auto", "raster", "svg"],
        help="Rendering backend: 'auto' (default), 'raster' (ImageMagick), 'svg' (pure Python)",
    )
    parser_slide_batch.add_argument(
        "--quality",
        type=int,
        default=95,
        help="JPEG quality compression factor (1-100, default: 95)",
    )
    parser_slide_batch.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="Rasterization DPI when converting SVG to raster (default: 300)",
    )
    parser_slide_batch.add_argument(
        "--safe-area",
        type=float,
        default=0.15,
        help="TV safe area margin percentage (0.05 to 0.30, default: 0.15 for 15%%)",
    )
    parser_slide_batch.add_argument(
        "--align",
        type=str,
        default="center",
        choices=["center", "left", "right"],
        help="Horizontal text alignment (default: 'center')",
    )
    parser_slide_batch.add_argument(
        "--font-family",
        "--font",
        type=str,
        default=None,
        help="Custom font family for slide typography",
    )
    parser_slide_batch.add_argument(
        "--font-size",
        type=parse_font_size_arg,
        default=None,
        help="Font size in points, or 'auto' (default) for layout engine calculation",
    )
    parser_slide_batch.add_argument(
        "--line-spacing",
        type=float,
        default=1.5,
        help="Line spacing multiplier (default: 1.5)",
    )
    parser_slide_batch.add_argument(
        "--citation-style",
        type=str,
        default="below",
        choices=["below", "smallcaps", "none"],
        help="Citation placement style (default: 'below')",
    )
    parser_slide_batch.add_argument(
        "--citation-color",
        "-c",
        type=str,
        default=None,
        help="Custom hex color for citation text (e.g. '#D4AF37')",
    )
    parser_slide_batch.add_argument(
        "--accent-color",
        type=str,
        default=None,
        help="Custom hex color for accent divider rule",
    )
    parser_slide_batch.add_argument(
        "--optical-center",
        type=float,
        default=0.45,
        help="Optical vertical centering factor (0.0 - 1.0, default: 0.45)",
    )
    parser_slide_batch.add_argument(
        "--no-balance",
        action="store_true",
        help="Disable typographic line balancing",
    )
    parser_slide_batch.add_argument(
        "--no-rule",
        action="store_true",
        help="Suppress decorative accent rule between verse and citation",
    )
    parser_slide_batch.add_argument(
        "--tags",
        action="store_true",
        help="Display semantic tags in the slide footer",
    )
    # Slicing & Ordering
    parser_slide_batch.add_argument(
        "--limit",
        "-n",
        type=int,
        default=None,
        help="Maximum number of passages to export",
    )
    parser_slide_batch.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Number of passages to skip before exporting",
    )
    parser_slide_batch.add_argument(
        "--shuffle",
        action="store_true",
        help="Randomize passage order before generating slides",
    )
    parser_slide_batch.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Deterministic random seed for shuffling",
    )
    # Pagination
    parser_slide_batch.add_argument(
        "--no-paginate",
        action="store_true",
        help="Disable multi-slide pagination; force passage onto a single slide",
    )
    parser_slide_batch.add_argument(
        "--max-verses",
        type=int,
        default=None,
        help="Maximum verses per slide before paginating",
    )
    parser_slide_batch.add_argument(
        "--max-lines",
        type=int,
        default=None,
        help="Maximum wrapped lines per slide before paginating (default: 8)",
    )
    parser_slide_batch.add_argument(
        "--max-chars",
        type=int,
        default=None,
        help="Maximum characters per slide before paginating (default: 420)",
    )
    # Execution & Automation
    parser_slide_batch.add_argument(
        "--jobs",
        "-j",
        type=int,
        default=None,
        help="Number of concurrent worker processes for rendering (default: CPU count)",
    )
    parser_slide_batch.add_argument(
        "--sequential",
        "-s",
        action="store_true",
        help="Force sequential rendering in a single process",
    )
    parser_slide_batch.add_argument(
        "--no-gallery",
        action="store_true",
        help="Skip generating HTML visual gallery (index.html)",
    )
    parser_slide_batch.add_argument(
        "--no-manifest",
        action="store_true",
        help="Skip generating JSON manifest (manifest.json)",
    )
    parser_slide_batch.add_argument(
        "--open",
        action="store_true",
        help="Open generated visual gallery (index.html) in default web browser",
    )
    parser_slide_batch.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress terminal progress bar and status output",
    )
    parser_slide_batch.add_argument(
        "--json",
        action="store_true",
        help="Output structured JSON summary of exported album",
    )

    def cmd_slide_batch(args: argparse.Namespace) -> int:
        from core.plans import format_plans_table, get_plan
        from core.render import (
            ImageMagickNotFoundError,
            PaginationConfig,
            RenderConfig,
            RenderError,
            get_theme,
            normalize_color,
            parse_resolution,
        )
        from core.slide_batch import BatchExportConfig, SlideBatchExporter

        color_enabled = (
            hasattr(sys.stdout, "isatty")
            and sys.stdout.isatty()
            and "NO_COLOR" not in os.environ
        )

        if getattr(args, "list_plans", False):
            print(format_plans_table(styling=color_enabled))
            return 0

        # Validate source selection
        has_favs = bool(getattr(args, "favorites", False))
        has_tag = bool(getattr(args, "tag", None))
        has_book = bool(getattr(args, "book", None))
        has_plan = bool(getattr(args, "plan", None))
        has_file = bool(getattr(args, "file", None))
        has_refs = bool(getattr(args, "references", None))

        if not (has_favs or has_tag or has_book or has_plan or has_file or has_refs):
            sys.stderr.write(
                "Error: No passage source specified for batch export.\n"
                "Specify a source, for example:\n"
                "  ./bible slide-batch --favorites [--starred-only]\n"
                "  ./bible slide-batch --plan psalms_of_ascent\n"
                "  ./bible slide-batch --tag Covenant\n"
                "  ./bible slide-batch --book James\n"
                "  ./bible slide-batch 'John 3:16' 'Romans 8:28' 'Psalm 23'\n"
                "Run with '--list-plans' to view all available reading plans.\n"
            )
            return 1

        db_path = Path(args.db).resolve() if args.db else DEFAULT_DB_PATH
        if not db_path.exists():
            sys.stderr.write(f"Database not found at '{db_path}'. Run './bible init' first.\n")
            return 1

        # Derive default album title and folder slug
        custom_title = getattr(args, "title", None)
        starred_only = bool(getattr(args, "starred_only", False))
        folder_slug = "scripture_slides"
        album_title = custom_title or "Scripture Screensaver Album"
        source_type = "custom"
        source_query = ""

        if has_favs:
            source_type = "favorites"
            if starred_only:
                album_title = custom_title or "Curated Starred Bible Verses"
                folder_slug = "favorites_starred"
            else:
                album_title = custom_title or "Curated Favorite Bible Verses"
                folder_slug = "favorites"
        elif has_plan:
            source_type = "plan"
            source_query = args.plan
            plan_obj = get_plan(args.plan)
            if plan_obj:
                album_title = custom_title or plan_obj.title
                folder_slug = f"plan_{plan_obj.name}"
            else:
                album_title = custom_title or f"Reading Plan: {args.plan}"
                folder_slug = f"plan_{re.sub(r'[^a-zA-Z0-9_]+', '_', args.plan).strip('_').lower()}"
        elif has_tag:
            source_type = "tag"
            source_query = args.tag
            album_title = custom_title or f"Thematic Scriptures: {args.tag}"
            folder_slug = f"tag_{re.sub(r'[^a-zA-Z0-9_]+', '_', args.tag).strip('_').lower()}"
        elif has_book:
            source_type = "book"
            source_query = args.book
            album_title = custom_title or f"Canonical Book: {args.book}"
            folder_slug = f"book_{re.sub(r'[^a-zA-Z0-9_]+', '_', args.book).strip('_').lower()}"
        elif has_file:
            source_type = "file"
            source_query = str(args.file)
            f_stem = Path(args.file).stem
            album_title = custom_title or f"Scripture Collection ({f_stem})"
            folder_slug = f"file_{re.sub(r'[^a-zA-Z0-9_]+', '_', f_stem).strip('_').lower()}"
        elif has_refs:
            source_type = "references"
            album_title = custom_title or "Curated Scripture Passages"
            folder_slug = "custom_passages"

        out_dir_arg = getattr(args, "output_dir", None)
        if out_dir_arg:
            dest_dir = Path(out_dir_arg).resolve()
        else:
            dest_dir = Path.cwd() / "exports" / "slides" / folder_slug

        # Parse dimensions and theme
        w, h = parse_resolution(args.resolution)
        theme = get_theme(args.theme)
        target_format = getattr(args, "output_format", "png")

        render_config = RenderConfig(
            width=w,
            height=h,
            theme=theme,
            safe_area_pct=args.safe_area,
            font_family=getattr(args, "font_family", None),
            font_size=args.font_size,
            line_spacing=getattr(args, "line_spacing", 1.5),
            text_align=args.align,
            citation_style=getattr(args, "citation_style", "below"),
            citation_color=normalize_color(getattr(args, "citation_color", None)),
            accent_color=normalize_color(getattr(args, "accent_color", None)),
            optical_center_pct=getattr(args, "optical_center", 0.45),
            balance_lines=not getattr(args, "no_balance", False),
            show_accent_rule=not args.no_rule,
            show_tags=bool(args.tags),
            backend=args.backend,
            output_format=target_format,
            jpeg_quality=args.quality,
            dpi=args.dpi,
        )

        no_paginate_flag = getattr(args, "no_paginate", False)
        if no_paginate_flag:
            pagination = PaginationConfig(enabled=False)
        else:
            pagination = PaginationConfig(
                enabled=True,
                mode="auto",
                max_verses_per_slide=getattr(args, "max_verses", None),
                max_lines_per_slide=getattr(args, "max_lines", None),
                max_chars_per_slide=getattr(args, "max_chars", None),
            )

        export_config = BatchExportConfig(
            destination_dir=dest_dir,
            render_config=render_config,
            pagination_config=pagination,
            album_title=album_title,
            album_description=f"Generated with Bible Engine ({render_config.width}x{render_config.height} {render_config.output_format.upper()})",
            source_type=source_type,
            source_query=source_query,
            max_workers=getattr(args, "jobs", None) or (os.cpu_count() or 4),
            sequential=getattr(args, "sequential", False),
            shuffle=getattr(args, "shuffle", False),
            seed=getattr(args, "seed", None),
            limit=getattr(args, "limit", None),
            offset=getattr(args, "offset", 0),
            generate_gallery=not getattr(args, "no_gallery", False),
            generate_manifest=not getattr(args, "no_manifest", False),
            quiet=getattr(args, "quiet", False) or getattr(args, "json", False),
        )

        with Database(db_path) as db:
            exporter = SlideBatchExporter(db)
            passages = exporter.resolve_passages(
                favorites=has_favs,
                starred_only=starred_only,
                tag=args.tag,
                book=args.book,
                plan=args.plan,
                file_path=args.file,
                references=args.references,
                translation_id=args.version,
                limit=args.limit,
                offset=args.offset,
                shuffle=args.shuffle,
                seed=args.seed,
            )

            if not passages:
                sys.stderr.write("Error: No matching scripture passages found to export.\n")
                return 1

            if not export_config.quiet:
                gold = "\033[38;2;212;175;55m" if color_enabled else ""
                cyan = "\033[36m" if color_enabled else ""
                reset = "\033[0m" if color_enabled else ""
                bold = "\033[1m" if color_enabled else ""
                workers_label = "1 worker (sequential)" if export_config.sequential else f"{export_config.max_workers} worker processes"
                print(f"{bold}{gold}=== Exporting Batch Scripture Slide Album ==={reset}")
                print(f"  • Title:       {album_title}")
                print(f"  • Passages:    {len(passages)} resolved")
                print(f"  • Resolution:  {render_config.width}x{render_config.height} ({render_config.output_format.upper()})")
                print(f"  • Theme:       {render_config.theme.name if hasattr(render_config.theme, 'name') else render_config.theme}")
                print(f"  • Workers:     {workers_label}")
                print(f"  • Destination: {cyan}{dest_dir}{reset}")
                print()

            try:
                result = exporter.export_batch(export_config, passages=passages)
            except ImageMagickNotFoundError as exc:
                sys.stderr.write(f"ImageMagick Error: {exc}\nTip: Run with '--backend=svg' or install ImageMagick.\n")
                return 1
            except RenderError as exc:
                sys.stderr.write(f"Render Error: {exc}\n")
                return 1

        if getattr(args, "json", False):
            print(json.dumps(result.to_dict(), indent=2))
            return 0

        if not getattr(args, "quiet", False):
            gold = "\033[38;2;212;175;55m" if color_enabled else ""
            green = "\033[32m" if color_enabled else ""
            cyan = "\033[36m" if color_enabled else ""
            reset = "\033[0m" if color_enabled else ""
            bold = "\033[1m" if color_enabled else ""

            mb_size = result.total_bytes / (1024 * 1024)
            size_str = f"{mb_size:.2f} MB" if mb_size >= 1.0 else f"{result.total_bytes / 1024:.1f} KB"

            print()
            print(f"{bold}{green}✓ Batch Slide Export Complete!{reset}")
            print(f"  • Album:       {result.album_title}")
            print(f"  • Slides:      {result.total_slides} generated across {result.total_passages} passages in {result.duration_seconds:.2f}s")
            print(f"  • Total Size:  {size_str}")
            print(f"  • Directory:   {cyan}{result.destination_dir}{reset}")
            if result.gallery_path:
                print(f"  • Gallery:     {cyan}file://{result.gallery_path}{reset}")
            if result.manifest_path:
                print(f"  • Manifest:    {result.manifest_path.name}")
            print()
            print(f"  {gold}📺 TV Screensaver Tip:{reset} Open the gallery above in your browser, or upload this directory")
            print("     to Google Photos to sync with Google TV / Chromecast ambient screensavers.")

        if getattr(args, "open", False) and result.gallery_path:
            try:
                import subprocess
                opener = "open" if sys.platform == "darwin" else "xdg-open"
                subprocess.Popen([opener, str(result.gallery_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

        return 0

    parser_slide_batch.set_defaults(func=cmd_slide_batch)

    # Subcommand: test (aliases: tests, check)
    parser_test = subparsers.add_parser(
        "test",
        aliases=["tests", "check"],
        help="Run hermetic unit test suite in parallel with strict resource auditing",
        description="Execute test modules in parallel with zero output leakage, sub-2-second velocity, and strict ResourceWarning checking.",
    )
    parser_test.add_argument(
        "-p",
        "--pattern",
        type=str,
        default=None,
        help="Filter test modules by substring or wildcard (e.g. 'render', '*arc*', 'crypto,db')",
    )
    parser_test.add_argument(
        "-j",
        "--jobs",
        type=int,
        default=None,
        help="Number of concurrent worker processes (default: CPU core count)",
    )
    parser_test.add_argument(
        "-s",
        "--sequential",
        action="store_true",
        help="Run test modules sequentially instead of in parallel",
    )
    parser_test.add_argument(
        "-w",
        "--warn-error",
        action="store_true",
        default=True,
        help="Treat ResourceWarning as test errors (default: True)",
    )
    parser_test.add_argument(
        "--no-warn-error",
        dest="warn_error",
        action="store_false",
        help="Do not treat ResourceWarning as fatal errors",
    )
    parser_test.add_argument(
        "-x",
        "--failfast",
        action="store_true",
        help="Stop execution on first module failure",
    )
    parser_test.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show per-module execution details and timings",
    )
    parser_test.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress output and exit with status code only",
    )
    parser_test.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI colors",
    )
    parser_test.add_argument(
        "--json",
        action="store_true",
        help="Output structured JSON summary",
    )
    parser_test.add_argument(
        "--coverage",
        action="store_true",
        help="Run tests with sovereign zero-dependency code coverage report",
    )
    parser_test.add_argument(
        "--fail-under",
        dest="coverage_threshold",
        type=float,
        default=None,
        help="Fail if coverage percentage is below threshold (requires --coverage)",
    )
    parser_test.add_argument(
        "--slowest",
        type=int,
        nargs="?",
        const=5,
        default=None,
        help="Show leaderboard of N slowest test modules (default: 5 if flag provided)",
    )
    parser_test.add_argument(
        "--warn-latency",
        type=float,
        default=None,
        help="Highlight and warn on test modules exceeding latency threshold in seconds",
    )

    def cmd_test(args: argparse.Namespace) -> int:
        from tools.test_runner import REPO_ROOT, run_tests
        is_tty = (
            hasattr(sys.stdout, "isatty")
            and sys.stdout.isatty()
            and not args.no_color
            and "NO_COLOR" not in os.environ
        )
        exit_code, _ = run_tests(
            repo_root=REPO_ROOT,
            pattern=args.pattern,
            parallel=not args.sequential,
            jobs=args.jobs,
            warn_error=args.warn_error,
            failfast=args.failfast,
            verbose=args.verbose,
            quiet=args.quiet,
            color=is_tty,
            output_json=args.json,
            slowest=getattr(args, "slowest", None),
            warn_latency=getattr(args, "warn_latency", None),
        )
        if exit_code == 0 and getattr(args, "coverage", False):
            from tools.coverage import collect_coverage, format_terminal_table
            cov_report = collect_coverage(
                repo_root=REPO_ROOT,
                test_pattern=args.pattern,
                parallel=not args.sequential,
                jobs=args.jobs,
            )
            if not args.quiet:
                print()
                print(format_terminal_table(cov_report, color=is_tty))
            if (
                args.coverage_threshold is not None
                and cov_report.overall_coverage_pct < args.coverage_threshold
            ):
                sys.stderr.write(
                    f"\nERROR: Overall coverage {cov_report.overall_coverage_pct:.1f}% is below required threshold of {args.coverage_threshold:.1f}%\n"
                )
                return 1

        return exit_code

    parser_test.set_defaults(func=cmd_test)

    # Subcommand: lint (aliases: linter, check-style)
    parser_lint = subparsers.add_parser(
        "lint",
        aliases=["linter", "check-style"],
        help="Run sovereign static analysis and code hygiene audit across repository",
        description="Audit Python source files for syntax errors, AST code smells (duplicate dict keys, mutable defaults, bare excepts), and formatting defects.",
    )
    parser_lint.add_argument(
        "-f",
        "--fix",
        action="store_true",
        help="Automatically repair formatting defects (strip trailing whitespace, fix final newlines)",
    )
    parser_lint.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show per-file execution details and passing files",
    )
    parser_lint.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress output and exit with status code only",
    )
    parser_lint.add_argument(
        "--strict",
        action="store_true",
        help="Strict mode: treat warnings and style notices as fatal errors",
    )
    parser_lint.add_argument(
        "-p",
        "--pattern",
        type=str,
        default=None,
        help="Filter scanned files by glob or substring (e.g. 'core', '*render*')",
    )
    parser_lint.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI colors",
    )
    parser_lint.add_argument(
        "--json",
        action="store_true",
        help="Output structured JSON report",
    )

    def cmd_lint(args: argparse.Namespace) -> int:
        from tools.linter import REPO_ROOT, lint_repository
        is_tty = (
            hasattr(sys.stdout, "isatty")
            and sys.stdout.isatty()
            and not args.no_color
            and "NO_COLOR" not in os.environ
        )
        exit_code, _ = lint_repository(
            repo_root=REPO_ROOT,
            pattern=args.pattern,
            fix=args.fix,
            strict=args.strict,
            verbose=args.verbose,
            quiet=args.quiet,
            color=is_tty,
            output_json=args.json,
        )
        return exit_code

    parser_lint.set_defaults(func=cmd_lint)

    # Subcommand: coverage (aliases: cov, test-coverage)
    parser_cov = subparsers.add_parser(
        "coverage",
        aliases=["cov", "test-coverage"],
        help="Audit test coverage and test gaps across repository modules (zero-dependency)",
        description="Sovereign zero-dependency code coverage & test gap detection engine using Python stdlib bytecode inspection.",
    )
    parser_cov.add_argument(
        "-p",
        "--pattern",
        type=str,
        default=None,
        help="Filter test modules by pattern (e.g. 'test_render' or '*crypto*')",
    )
    parser_cov.add_argument(
        "-m",
        "--module",
        type=str,
        default=None,
        help="Limit audit to specific module or directory (e.g. 'core' or 'core/render.py')",
    )
    parser_cov.add_argument(
        "-s",
        "--sequential",
        action="store_true",
        help="Run test tracing sequentially instead of parallel",
    )
    parser_cov.add_argument(
        "-j",
        "--jobs",
        type=int,
        default=None,
        help="Number of concurrent worker processes",
    )
    parser_cov.add_argument(
        "--fail-under",
        "--threshold",
        dest="threshold",
        type=float,
        default=None,
        help="Fail with exit code 1 if total coverage is under threshold percentage",
    )
    parser_cov.add_argument(
        "-u",
        "--uncovered",
        "--missed",
        dest="missed_only",
        action="store_true",
        help="Only display files with missed statements in table",
    )
    parser_cov.add_argument(
        "--json",
        action="store_true",
        help="Output coverage report in structured JSON format",
    )
    parser_cov.add_argument(
        "--html",
        type=str,
        default=None,
        help="Generate standalone Sacred-Modern HTML coverage report at specified path",
    )
    parser_cov.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress terminal table output",
    )
    parser_cov.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI terminal colors",
    )

    def cmd_coverage(args: argparse.Namespace) -> int:
        from tools.coverage import (
            REPO_ROOT,
            collect_coverage,
            format_terminal_table,
            generate_html_report,
        )
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

        if args.threshold is not None and report.overall_coverage_pct < args.threshold:
            sys.stderr.write(
                f"\nERROR: Overall coverage {report.overall_coverage_pct:.1f}% is below required threshold of {args.threshold:.1f}%\n"
            )
            return 1
        return 0

    parser_cov.set_defaults(func=cmd_coverage)

    # Subcommand: esv
    parser_esv = subparsers.add_parser(
        "esv",
        aliases=["esv-api", "esv-cache"],
        help="Inspect ESV API configuration, 500-verse LRU cache, and Crossway legal compliance",
        description="Inspect and manage the zero-dependency Crossway ESV API integration and 500-verse LRU cache (ADR-041).",
    )
    parser_esv.add_argument(
        "action",
        nargs="?",
        default="status",
        choices=["status", "cache", "clear", "fetch"],
        help="Action: 'status' (configuration & cache status), 'cache' (list cached verses), 'clear' (evict all cached verses), 'fetch' (fetch and cache a passage)",
    )
    parser_esv.add_argument(
        "reference",
        nargs="*",
        help="Scripture citation when action is 'fetch' (e.g. 'John 3:16', 'Romans 8:28-30')",
    )
    parser_esv.add_argument(
        "--json",
        action="store_true",
        help="Output structured JSON metrics",
    )

    def cmd_esv(args: argparse.Namespace) -> int:
        from core.esv import (
            ESV_ATTRIBUTION_URL,
            ESV_FULL_COPYRIGHT,
            ESV_MAX_CACHE_VERSES,
            ESV_SHORT_ATTRIBUTION,
            ESVError,
            get_esv_api_key,
        )

        action = getattr(args, "action", "status") or "status"
        db_path = Path(args.db).resolve() if args.db else DEFAULT_DB_PATH
        output_json = getattr(args, "json", False)

        color_enabled = (
            hasattr(sys.stdout, "isatty")
            and sys.stdout.isatty()
            and "NO_COLOR" not in os.environ
        )

        api_key = get_esv_api_key()
        has_key = bool(api_key and api_key.strip())
        masked_key = f"...{api_key[-4:]}" if has_key and len(api_key) >= 8 else ("Configured" if has_key else "Unset")

        if not db_path.exists():
            if action == "status" and output_json:
                print(json.dumps({
                    "api_key_configured": has_key,
                    "database_exists": False,
                    "cached_verses": 0,
                    "max_capacity": ESV_MAX_CACHE_VERSES,
                    "compliant": True,
                }, indent=2))
                return 0
            sys.stderr.write(f"Error: Database file not found at '{db_path}'. Run './bible init' first.\n")
            return 1

        try:
            with Database(db_path, auto_init=False) as db:
                if action == "clear":
                    cleared_count = db.clear_esv_cache()
                    if output_json:
                        print(json.dumps({"cleared_verses": cleared_count, "remaining": 0}, indent=2))
                    else:
                        print(f"Successfully cleared ephemeral ESV cache ({cleared_count} verses evicted).")
                    return 0

                elif action == "fetch":
                    raw_ref = " ".join(getattr(args, "reference", [])).strip()
                    if not raw_ref:
                        sys.stderr.write("Error: Reference citation required for 'fetch' action (e.g. './bible esv fetch John 3:16').\n")
                        return 1

                    try:
                        ref = parse_reference(raw_ref)
                    except Exception as exc:
                        sys.stderr.write(f"Error parsing reference '{raw_ref}': {exc}\n")
                        return 1

                    if not has_key:
                        sys.stderr.write(
                            "Error: ESV API key is not configured. Set ESV_API_KEY environment variable "
                            "or create a .env file with ESV_API_KEY=your_key.\n"
                        )
                        return 1

                    client = db.get_esv_client()
                    try:
                        verses = client.fetch_verses(ref)
                    except ESVError as exc:
                        sys.stderr.write(f"ESV API error: {exc}\n")
                        return 1

                    saved = db.save_esv_cached_verses(verses)

                    if output_json:
                        print(json.dumps({
                            "reference": ref.format(),
                            "fetched_verses": len(verses),
                            "cached_count": saved,
                            "verses": [{"verse": v.verse, "text": v.text} for v in verses],
                            "attribution": ESV_SHORT_ATTRIBUTION,
                        }, indent=2))
                    else:
                        header = f"=== {ref.format()} (ESV) ==="
                        print(header)
                        print()
                        for v in verses:
                            print(f"[{v.verse}] {v.text}")
                        print()
                        print(f"Attribution: {ESV_SHORT_ATTRIBUTION}")
                        print(f"(Cached {len(verses)} verses into ephemeral ESV cache; total: {db.count_esv_cached_verses()}/{ESV_MAX_CACHE_VERSES})")
                    return 0

                elif action == "cache":
                    cur = db.conn.cursor()
                    cur.execute(
                        """
                        SELECT c.canonical_verse_id, b.name as book_name, c.chapter, c.verse, c.text, c.last_accessed_at
                        FROM esv_cache c
                        JOIN books b ON b.id = c.book_id
                        ORDER BY c.canonical_verse_id ASC
                        """
                    )
                    rows = cur.fetchall()
                    cur.close()

                    if output_json:
                        items = [
                            {
                                "canonical_id": r["canonical_verse_id"],
                                "citation": f"{r['book_name']} {r['chapter']}:{r['verse']}",
                                "text": r["text"],
                                "last_accessed_at": r["last_accessed_at"],
                            }
                            for r in rows
                        ]
                        print(json.dumps({"total_cached": len(items), "verses": items}, indent=2))
                        return 0

                    if not rows:
                        print("Ephemeral ESV cache is currently empty (0 / 500 verses).")
                        return 0

                    print(f"=== Ephemeral ESV Cache ({len(rows)} / {ESV_MAX_CACHE_VERSES} verses) ===")
                    print(f"{'Citation':<20} {'Last Accessed':<24} {'Text Snippet'}")
                    print(f"{'-' * 18} {'-' * 22} {'-' * 35}")
                    for r in rows[:50]:
                        cite = f"{r['book_name']} {r['chapter']}:{r['verse']}"
                        snippet = (r["text"][:32] + "...") if len(r["text"]) > 35 else r["text"]
                        print(f"{cite:<20} {r['last_accessed_at']:<24} {snippet}")
                    if len(rows) > 50:
                        print(f"... and {len(rows) - 50} more cached verses.")
                    return 0

                else:  # status
                    stats = db.get_esv_cache_stats()
                    cached_count = stats["cached_verses"]
                    pct = (cached_count / ESV_MAX_CACHE_VERSES) * 100
                    bar_len = 20
                    filled = int(bar_len * (cached_count / ESV_MAX_CACHE_VERSES))
                    bar = "█" * filled + "░" * (bar_len - filled)

                    if output_json:
                        print(json.dumps({
                            "api_key_configured": has_key,
                            "masked_key": masked_key,
                            "base_url": "https://api.esv.org/v3/passage/text/",
                            "rate_limits": "60 req/min, 5,000 req/day",
                            "cache_stats": stats,
                            "legal_attribution": ESV_SHORT_ATTRIBUTION,
                            "copyright_url": ESV_ATTRIBUTION_URL,
                        }, indent=2))
                        return 0

                    gold = "\033[1;33m" if color_enabled else ""
                    cyan = "\033[36m" if color_enabled else ""
                    dim = "\033[2m" if color_enabled else ""
                    green = "\033[32m" if color_enabled else ""
                    yellow = "\033[33m" if color_enabled else ""
                    reset = "\033[0m" if color_enabled else ""

                    print(f"{gold}======================================================================{reset}")
                    print(f"{gold} Crossway ESV API & Ephemeral 500-Verse LRU Cache Status (ADR-041){reset}")
                    print(f"{gold}======================================================================{reset}")
                    key_status = f"{green}Configured ({masked_key}){reset}" if has_key else f"{yellow}Not Configured (Set ESV_API_KEY){reset}"
                    print(f" ESV API Key:           {key_status}")
                    print(f" API Base Endpoint:     https://api.esv.org/v3/passage/text/")
                    print(f" Standard Rate Limits:  60 req/min, 5,000 req/day")
                    print(f"----------------------------------------------------------------------")
                    comp_str = f"{green}COMPLIANT (<= 500 verses){reset}" if stats["compliant"] else f"\033[31mNON-COMPLIANT{reset}"
                    print(f" Ephemeral Cache Usage: {cached_count} / {ESV_MAX_CACHE_VERSES} verses ({pct:.1f}%)")
                    print(f" Progress:              [{bar}]")
                    print(f" Compliance Status:     {comp_str}")
                    print(f" Oldest Accessed:       {stats['oldest_accessed_at'] or 'N/A'}")
                    print(f" Newest Accessed:       {stats['newest_accessed_at'] or 'N/A'}")
                    print(f"----------------------------------------------------------------------")
                    print(f"{dim} Crossway Legal Attribution Notice:{reset}")
                    print(f" {ESV_FULL_COPYRIGHT}")
                    print(f" Web: {cyan}https://www.esv.org{reset}")
                    print(f"{gold}======================================================================{reset}")
                    return 0
        except Exception as exc:
            sys.stderr.write(f"Database error: {exc}\n")
            return 1

    parser_esv.set_defaults(func=cmd_esv)

    # Subcommand: gemini (aliases: llm, gemini-api)
    parser_gemini = subparsers.add_parser(
        "gemini",
        aliases=["llm", "gemini-api"],
        help="Google Gemini LLM client, model fallback, and passage context engine",
        description="Interact with the zero-dependency Google Gemini API client (ADR-006) and passage context builder (ADR-041).",
    )
    parser_gemini.add_argument(
        "action",
        nargs="?",
        default="status",
        choices=["status", "prompt", "context", "embed"],
        help="Action: 'status' (API key & model configuration), 'prompt' (generate text), 'context' (build passage context block), 'embed' (generate vector embedding)",
    )
    parser_gemini.add_argument(
        "argument",
        nargs="*",
        help="Prompt text, scripture reference citation, or text to embed",
    )
    parser_gemini.add_argument(
        "--model",
        default=None,
        help="Gemini model identifier (default: gemini-2.5-pro with gemini-2.0-flash fallback)",
    )
    parser_gemini.add_argument(
        "--system",
        default=None,
        help="System instruction / prompt guardrail",
    )
    parser_gemini.add_argument(
        "--translation",
        default="ESV",
        help="Scripture translation for context builder (default: ESV)",
    )
    parser_gemini.add_argument(
        "--stream",
        action="store_true",
        help="Stream response chunks using Server-Sent Events",
    )
    parser_gemini.add_argument(
        "--json",
        action="store_true",
        help="Output structured JSON metrics and data",
    )

    def cmd_gemini(args: argparse.Namespace) -> int:
        from core.llm import (
            DEFAULT_EMBEDDING_MODEL,
            DEFAULT_GEMINI_MODEL,
            FALLBACK_GEMINI_MODEL,
            GEMINI_API_BASE_URL,
            SUPPORTED_MODELS,
            GeminiClient,
            GenerationConfig,
            LLMAuthError,
            LLMError,
            build_passage_context,
            get_gemini_api_key,
        )

        action = getattr(args, "action", "status") or "status"
        raw_args = getattr(args, "argument", []) or []
        user_input = " ".join(raw_args).strip()
        output_json = getattr(args, "json", False)

        color_enabled = (
            hasattr(sys.stdout, "isatty")
            and sys.stdout.isatty()
            and "NO_COLOR" not in os.environ
        )
        gold = "\033[1;33m" if color_enabled else ""
        cyan = "\033[36m" if color_enabled else ""
        dim = "\033[2m" if color_enabled else ""
        green = "\033[32m" if color_enabled else ""
        yellow = "\033[33m" if color_enabled else ""
        reset = "\033[0m" if color_enabled else ""

        api_key = get_gemini_api_key()
        has_key = bool(api_key and api_key.strip())
        masked_key = (
            f"...{api_key[-4:]}"
            if has_key and len(api_key) >= 8
            else ("Configured" if has_key else "Unset")
        )

        if action == "context":
            if not user_input:
                sys.stderr.write("Error: Reference citation required for 'context' action (e.g. './bible gemini context \"John 3:16\"').\n")
                return 1

            db_path = Path(args.db).resolve() if args.db else DEFAULT_DB_PATH
            target_trans = getattr(args, "translation", "ESV") or "ESV"

            try:
                with Database(db_path, auto_init=False) as db:
                    ctx = build_passage_context(user_input, db=db, translation=target_trans)
            except Exception as exc:
                sys.stderr.write(f"Error building passage context: {exc}\n")
                return 1

            if output_json:
                print(json.dumps(ctx.to_dict(), indent=2))
                return 0

            print(f"{gold}=== Passage Context: {ctx.reference} ({ctx.translation}) ==={reset}")
            print(ctx.format_prompt_block(include_attribution=True))
            return 0

        elif action == "prompt":
            if not user_input:
                sys.stderr.write("Error: Prompt text required for 'prompt' action (e.g. './bible gemini prompt \"Explain Romans 8:28\"').\n")
                return 1

            if not has_key:
                sys.stderr.write(
                    "Error: Gemini API key is not configured. Set GEMINI_API_KEY environment variable "
                    "or create a .env file with GEMINI_API_KEY=your_key.\n"
                )
                return 1

            model_id = getattr(args, "model", None) or DEFAULT_GEMINI_MODEL
            system_inst = getattr(args, "system", None)
            is_stream = getattr(args, "stream", False)

            client = GeminiClient(api_key=api_key, model=model_id, fallback_model=FALLBACK_GEMINI_MODEL)

            try:
                if is_stream:
                    chunks = client.generate_stream(user_input, system_instruction=system_inst)
                    for chunk in chunks:
                        sys.stdout.write(chunk.text)
                        sys.stdout.flush()
                    sys.stdout.write("\n")
                    return 0
                else:
                    resp = client.generate(user_input, system_instruction=system_inst)
                    if output_json:
                        print(json.dumps(resp.to_dict(), indent=2))
                        return 0

                    print(resp.text)
                    if resp.fallback_used:
                        print(f"{dim}(Note: Fallback model '{resp.model}' was utilized){reset}")
                    return 0
            except LLMError as exc:
                sys.stderr.write(f"Gemini API error: {exc}\n")
                return 1

        elif action == "embed":
            if not user_input:
                sys.stderr.write("Error: Text required for 'embed' action (e.g. './bible gemini embed \"In the beginning\"').\n")
                return 1

            if not has_key:
                sys.stderr.write(
                    "Error: Gemini API key is not configured. Set GEMINI_API_KEY environment variable "
                    "or create a .env file with GEMINI_API_KEY=your_key.\n"
                )
                return 1

            client = GeminiClient(api_key=api_key)
            try:
                vec = client.embed_content(user_input)
                if output_json:
                    print(json.dumps({"text": user_input, "dimension": len(vec), "values": vec}, indent=2))
                    return 0

                print(f"Computed vector embedding: dimension={len(vec)}, preview={vec[:5]}...")
                return 0
            except LLMError as exc:
                sys.stderr.write(f"Embedding error: {exc}\n")
                return 1

        else:  # status
            if output_json:
                print(json.dumps({
                    "api_key_configured": has_key,
                    "masked_key": masked_key,
                    "default_model": DEFAULT_GEMINI_MODEL,
                    "fallback_model": FALLBACK_GEMINI_MODEL,
                    "default_embedding_model": DEFAULT_EMBEDDING_MODEL,
                    "supported_models": list(SUPPORTED_MODELS),
                    "api_base_url": GEMINI_API_BASE_URL,
                    "zero_dependencies": True,
                }, indent=2))
                return 0

            print(f"{gold}======================================================================{reset}")
            print(f"{gold} Google Gemini LLM Client & Context Engine (ADR-006 / ADR-041){reset}")
            print(f"{gold}======================================================================{reset}")
            key_status = f"{green}Configured ({masked_key}){reset}" if has_key else f"{yellow}Not Configured (Set GEMINI_API_KEY){reset}"
            print(f" Gemini API Key:        {key_status}")
            print(f" Primary Model:         {cyan}{DEFAULT_GEMINI_MODEL}{reset}")
            print(f" Fallback Model:        {cyan}{FALLBACK_GEMINI_MODEL}{reset} (Automatic on 404/429/failures)")
            print(f" Embedding Model:       {cyan}{DEFAULT_EMBEDDING_MODEL}{reset}")
            print(f" Endpoint Base URL:     {GEMINI_API_BASE_URL}")
            print(f" Architecture:          100% Zero-Dependency Python stdlib (urllib.request)")
            print(f" Passage Context:       Defaults to ESV with Crossway legal compliance")
            print(f"----------------------------------------------------------------------")
            print(f" Actions:")
            print(f"   ./bible gemini status                 Check API key & model status")
            print(f"   ./bible gemini context \"John 3:16\"     Build structured passage prompt context")
            print(f"   ./bible gemini prompt \"<query>\"        Generate completion from prompt")
            print(f"   ./bible gemini embed \"<text>\"          Generate semantic vector embedding")
            print(f"{gold}======================================================================{reset}")
            return 0

    parser_gemini.set_defaults(func=cmd_gemini)

    # Subcommand: bench (aliases: benchmark, perf)
    parser_bench = subparsers.add_parser(
        "bench",
        aliases=["benchmark", "perf"],
        help="Sovereign high-velocity performance benchmark engine & regression guard",
        description="High-precision statistical benchmarking and latency regression detection across all core workloads.",
    )
    parser_bench.add_argument(
        "-c",
        "--category",
        default=None,
        help="Filter benchmarks by category (comma-separated: reference,database,fts,crypto,render,linter,cache)",
    )
    parser_bench.add_argument(
        "-p",
        "--pattern",
        default=None,
        help="Filter benchmarks by name or description pattern substring",
    )
    parser_bench.add_argument(
        "-n",
        "--iterations",
        type=int,
        default=None,
        help="Override iteration count for workloads",
    )
    parser_bench.add_argument(
        "-w",
        "--warmup",
        type=int,
        default=None,
        help="Override warmup round count",
    )
    parser_bench.add_argument(
        "-q",
        "--quick",
        "--fast",
        action="store_true",
        help="Run benchmarks in high-velocity quick mode (<2s)",
    )
    parser_bench.add_argument(
        "--save-baseline",
        nargs="?",
        const=".benchmark_baseline.json",
        default=None,
        help="Save benchmark results to persistent baseline file (default: .benchmark_baseline.json)",
    )
    parser_bench.add_argument(
        "--compare-baseline",
        nargs="?",
        const=".benchmark_baseline.json",
        default=None,
        help="Compare execution against persistent baseline file (default: .benchmark_baseline.json)",
    )
    parser_bench.add_argument(
        "--fail-regression",
        type=float,
        metavar="THRESHOLD_PCT",
        default=None,
        help="Exit with code 1 if any benchmark regresses by more than THRESHOLD_PCT (e.g. 20.0)",
    )
    parser_bench.add_argument(
        "--json",
        action="store_true",
        help="Emit results as structured JSON",
    )
    parser_bench.add_argument(
        "--html",
        metavar="PATH",
        default=None,
        help="Export Sacred-Modern HTML performance dashboard to target file",
    )
    parser_bench.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI colors in terminal output",
    )

    def cmd_bench(args: argparse.Namespace) -> int:
        from tools.benchmark import (
            BenchmarkStyler,
            format_benchmark_table,
            generate_html_report,
            load_baseline,
            run_benchmark_suite,
            save_baseline,
        )

        categories = [c.strip() for c in args.category.split(",") if c.strip()] if getattr(args, "category", None) else None
        baseline_data = None
        baseline_path_str = None
        if getattr(args, "compare_baseline", None):
            base_p = Path(args.compare_baseline)
            baseline_path_str = str(base_p)
            baseline_data = load_baseline(base_p)
            if not baseline_data and not getattr(args, "json", False):
                sys.stderr.write(f"[Notice] Baseline file '{base_p}' not found. Running benchmarks without baseline comparison.\n")

        suite = run_benchmark_suite(
            categories=categories,
            pattern=getattr(args, "pattern", None),
            iterations=getattr(args, "iterations", None),
            warmup=getattr(args, "warmup", None),
            quick=getattr(args, "quick", False),
            baseline=baseline_data,
            regression_threshold_pct=getattr(args, "fail_regression", None),
            baseline_path_str=baseline_path_str,
        )

        if getattr(args, "save_baseline", None):
            target_p = Path(args.save_baseline)
            save_baseline(suite, target_p)
            if not getattr(args, "json", False):
                sys.stderr.write(f"[Saved] Baseline successfully saved to {target_p}\n")

        if getattr(args, "html", None):
            html_f = generate_html_report(suite, Path(args.html))
            if not getattr(args, "json", False):
                sys.stderr.write(f"[Exported] HTML benchmark report saved to {html_f}\n")

        if getattr(args, "json", False):
            print(suite.to_json(indent=2, include_raw=False))
        else:
            styler = BenchmarkStyler(enabled=not getattr(args, "no_color", False))
            print(format_benchmark_table(suite, styler=styler))

        if getattr(args, "fail_regression", None) is not None and suite.regressions:
            return 1
        return 0

    parser_bench.set_defaults(func=cmd_bench)

    # Subcommand: vector (aliases: vec, embedding, embeddings)
    parser_vector = subparsers.add_parser(
        "vector",
        aliases=["vec", "embedding", "embeddings"],
        help="Zero-dependency vector similarity engine and semantic search",
        description="Search and inspect vector embeddings, int8 quantization, and semantic similarity.",
    )
    vector_subparsers = parser_vector.add_subparsers(dest="vector_action", help="Vector action to perform")

    # vector status
    p_vec_status = vector_subparsers.add_parser("status", help="Show vector storage and index statistics")
    p_vec_status.add_argument("--json", action="store_true", help="Output metrics as structured JSON")

    # vector search
    p_vec_search = vector_subparsers.add_parser("search", help="Semantic vector search using Gemini Embeddings API")
    p_vec_search.add_argument("query", nargs="+", help="Natural language query string to search semantically")
    p_vec_search.add_argument("--target", choices=["verses", "pericopes"], default="verses", help="Search target (verses or pericopes)")
    p_vec_search.add_argument("--top-k", "-k", type=int, default=10, help="Number of top results to return (default: 10)")
    p_vec_search.add_argument("--mode", choices=["hierarchical", "exhaustive"], default="hierarchical", help="Search mode (default: hierarchical)")
    p_vec_search.add_argument("--book", "-b", help="Filter results by canonical book name or abbreviation")
    p_vec_search.add_argument("--testament", choices=["OT", "NT", "ot", "nt"], help="Filter results by testament")
    p_vec_search.add_argument("--min-score", type=float, default=0.0, help="Minimum cosine similarity threshold (default: 0.0)")
    p_vec_search.add_argument("--json", action="store_true", help="Output results as JSON")

    # vector similar
    p_vec_similar = vector_subparsers.add_parser("similar", help="Find scripture verses semantically similar to a reference")
    p_vec_similar.add_argument("reference", help="Source scripture citation (e.g. 'John 3:16', 'Romans 8:28')")
    p_vec_similar.add_argument("--target", choices=["verses", "pericopes"], default="verses", help="Search target (verses or pericopes)")
    p_vec_similar.add_argument("--top-k", "-k", type=int, default=10, help="Number of top results to return (default: 10)")
    p_vec_similar.add_argument("--mode", choices=["hierarchical", "exhaustive"], default="hierarchical", help="Search mode (default: hierarchical)")
    p_vec_similar.add_argument("--min-score", type=float, default=0.0, help="Minimum cosine similarity threshold (default: 0.0)")
    p_vec_similar.add_argument("--json", action="store_true", help="Output results as JSON")

    def cmd_vector(args: argparse.Namespace) -> int:
        from core.vector import (
            DEFAULT_VECTOR_DIM,
            VectorIndex,
            get_pericope_vector_index,
            get_verse_vector_index,
        )
        from core.llm import GeminiClient, get_gemini_api_key

        action = getattr(args, "vector_action", None) or "status"
        output_json = getattr(args, "json", False)
        db_path = Path(args.db).resolve() if args.db else DEFAULT_DB_PATH

        if not db_path.exists():
            sys.stderr.write(f"Error: Database not found at '{db_path}'. Run './bible init'.\n")
            return 1

        color_enabled = (
            hasattr(sys.stdout, "isatty")
            and sys.stdout.isatty()
            and "NO_COLOR" not in os.environ
        )
        gold = "\033[1;33m" if color_enabled else ""
        cyan = "\033[36m" if color_enabled else ""
        green = "\033[32m" if color_enabled else ""
        dim = "\033[2m" if color_enabled else ""
        reset = "\033[0m" if color_enabled else ""

        with Database(db_path, auto_init=False) as db:
            if action == "status":
                verse_count = db.count_verse_embeddings()
                pericope_count = db.count_pericope_embeddings()

                if output_json:
                    print(json.dumps({
                        "verse_embeddings_count": verse_count,
                        "pericope_embeddings_count": pericope_count,
                        "dimensions": DEFAULT_VECTOR_DIM,
                        "quantization": "int8 signed [-127, 127] with 768-bit sign hash",
                        "database_path": str(db_path),
                        "zero_dependencies": True,
                    }, indent=2))
                    return 0

                print(f"{gold}======================================================================{reset}")
                print(f"{gold} Zero-Dependency Vector Similarity Engine (ADR-003 / ADR-051){reset}")
                print(f"{gold}======================================================================{reset}")
                print(f" Verse Embeddings:      {cyan}{verse_count:,}{reset} stored")
                print(f" Pericope Embeddings:   {cyan}{pericope_count:,}{reset} stored")
                print(f" Standard Dimensions:   {cyan}{DEFAULT_VECTOR_DIM}{reset} (text-embedding-004)")
                print(f" Quantization Scheme:   Int8 signed [-127, 127] (4x compression)")
                print(f" Index Architecture:    Two-Tier (768-bit Sign Hash Filter + Exact Int8 Rerank)")
                print(f" Whole-Bible Target:    31,102 verses searchable in <15ms without external DBs")
                print(f"----------------------------------------------------------------------")
                print(f" Subcommands:")
                print(f"   ./bible vector status                 Check stored vector statistics")
                print(f"   ./bible vector search \"<query>\"       Semantic search via Gemini embedding")
                print(f"   ./bible vector similar \"John 3:16\"    Find semantically related passages")
                print(f"{gold}======================================================================{reset}")
                return 0

            elif action in ("search", "similar"):
                target = getattr(args, "target", "verses") or "verses"
                table_name = "verse_embeddings" if target == "verses" else "pericope_embeddings"
                top_k = getattr(args, "top_k", 10) or 10
                search_mode = getattr(args, "mode", "hierarchical") or "hierarchical"
                min_score = getattr(args, "min_score", 0.0) or 0.0

                # Check if embeddings exist in database
                stored_count = db.count_verse_embeddings() if target == "verses" else db.count_pericope_embeddings()
                if stored_count == 0:
                    sys.stderr.write(
                        f"Notice: No {target} embeddings stored in '{db_path.name}'.\n"
                        f"Run './bible build-semantic' or Phase 7 compilation to populate vector embeddings.\n"
                    )
                    return 1

                # Load or get cached index
                index = VectorIndex(dimensions=DEFAULT_VECTOR_DIM)
                index.build_from_database(db, table=table_name)

                # Obtain query vector
                if action == "similar":
                    ref_input = getattr(args, "reference", "")
                    try:
                        ref_obj = parse_reference(ref_input)
                    except Exception as e:
                        sys.stderr.write(f"Error: Invalid reference '{ref_input}': {e}\n")
                        return 1

                    if target == "pericopes":
                        matching_pericopes = db.get_pericopes_for_reference(ref_obj)
                        source_emb = None
                        if matching_pericopes:
                            source_emb = db.get_pericope_embedding(matching_pericopes[0].id)
                        if not source_emb:
                            sys.stderr.write(f"Error: No pericope embedding stored for reference '{ref_obj.format()}'.\n")
                            return 1
                        query_bytes = source_emb.embedding
                    else:
                        source_emb = db.get_verse_embedding(ref_obj)
                        if not source_emb:
                            sys.stderr.write(f"Error: No verse embedding stored for reference '{ref_obj.format()}'.\n")
                            return 1
                        query_bytes = source_emb.embedding
                else:
                    raw_q = " ".join(getattr(args, "query", [])).strip()
                    if not raw_q:
                        sys.stderr.write("Error: Query text required for vector search.\n")
                        return 1

                    api_key = get_gemini_api_key()
                    if api_key:
                        client = GeminiClient(api_key=api_key)
                        try:
                            q_floats = client.embed_content(raw_q)
                            query_bytes = bytes(q_floats)
                        except Exception as exc:
                            sys.stderr.write(f"Error generating query embedding: {exc}\n")
                            return 1
                    else:
                        # Deterministic offline vector query embedding (ADR-003, ADR-042)
                        from core.semantic_compiler import SemanticDatabaseCompiler
                        from core.vector import normalize_vector, quantize_float_to_int8
                        pseudo_vec = normalize_vector(SemanticDatabaseCompiler._pseudo_embed(raw_q, dim=DEFAULT_VECTOR_DIM))
                        packed_bytes, _ = quantize_float_to_int8(pseudo_vec)
                        query_bytes = packed_bytes

                # Build filter function if book or testament specified
                book_filter = getattr(args, "book", None)
                testament_filter = getattr(args, "testament", None)
                filter_fn = None
                if book_filter or testament_filter:
                    def custom_filter(rec):
                        # Filter by book or testament from metadata
                        meta = rec.metadata or {}
                        if book_filter and meta.get("book") != book_filter:
                            return False
                        if testament_filter and meta.get("testament", "").upper() != testament_filter.upper():
                            return False
                        return True
                    filter_fn = custom_filter

                matches = index.search(
                    query_bytes,
                    top_k=top_k,
                    mode=search_mode,
                    min_score=min_score,
                    filter_fn=filter_fn,
                )

                if output_json:
                    print(json.dumps([m.to_dict() for m in matches], indent=2))
                    return 0

                print(f"{gold}=== Semantic Vector Search Results ({len(matches)} matches) ==={reset}")
                if not matches:
                    print(f"{dim}No matching passages exceeded similarity threshold {min_score}.{reset}")
                    return 0

                for m in matches:
                    pct = int(round(m.score * 100))
                    bar = "█" * (pct // 10) + "░" * (10 - (pct // 10))
                    print(f" {m.rank:2d}. {cyan}{m.human_ref:<18}{reset} [{bar}] {green}{m.score:+.4f}{reset}")
                return 0

            else:
                sys.stderr.write(f"Unknown vector action: '{action}'. See './bible vector --help'.\n")
                return 1

    parser_vector.set_defaults(func=cmd_vector)

    # Subcommand: audit-semantic (aliases: audit, audit-critic)
    parser_audit_semantic = subparsers.add_parser(
        "audit-semantic",
        aliases=["audit", "audit-critic"],
        help="Audit semantic database coordinates, schemas, and whole-Bible coverage",
        description="Audit coordinate boundaries (BBCCCVVV), schema validation, character entity deduplication, and whole-Bible coverage.",
    )
    parser_audit_semantic.add_argument(
        "--no-coverage",
        dest="coverage",
        action="store_false",
        default=True,
        help="Skip whole-Bible verse coverage calculation",
    )
    parser_audit_semantic.add_argument(
        "--book",
        type=str,
        default=None,
        help="Filter audit to a specific canonical book (e.g. 'Romans', 'Genesis')",
    )
    parser_audit_semantic.add_argument(
        "--json",
        action="store_true",
        help="Output results as machine-readable JSON",
    )
    parser_audit_semantic.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed findings and suggested remediation fixes",
    )
    parser_audit_semantic.add_argument(
        "--strict",
        action="store_true",
        help="Enforce strict error severity on missing pericope central propositions/summaries",
    )

    def cmd_audit_semantic(args: argparse.Namespace) -> int:
        from tools.audit_semantic import run_semantic_audit
        db_path = Path(args.db).resolve() if args.db else DEFAULT_DB_PATH
        return run_semantic_audit(
            db_path=db_path,
            include_coverage=getattr(args, "coverage", True),
            book_filter=getattr(args, "book", None),
            json_output=getattr(args, "json", False),
            verbose=getattr(args, "verbose", False),
            strict=getattr(args, "strict", False),
        )

    parser_audit_semantic.set_defaults(func=cmd_audit_semantic)

    # Subcommand: build-semantic (aliases: compile-semantic, build-db)
    parser_build_semantic = subparsers.add_parser(
        "build-semantic",
        aliases=["compile-semantic", "build-db"],
        help="Resumable batch semantic compiler & whole-Bible database builder",
        description="Compile 6-layer semantic exegesis (pericopes, discourse, theology, typology, propositions, vectors) into SQLite with crash-resilient ledger resumption.",
    )
    parser_build_semantic.add_argument(
        "--all",
        action="store_true",
        dest="compile_all",
        help="Compile complete permanent semantic pack (144 pericopes + 1,189 chapters across all 66 books)",
    )
    parser_build_semantic.add_argument(
        "--book",
        type=str,
        default=None,
        help="Filter compilation to a specific canonical book (e.g. 'Romans', 'Genesis')",
    )
    parser_build_semantic.add_argument(
        "--no-resume",
        action="store_false",
        dest="resume",
        default=True,
        help="Do not skip previously completed units; reprocess all",
    )
    parser_build_semantic.add_argument(
        "--reset-failed",
        action="store_true",
        help="Reset all failed units in the ledger back to PENDING",
    )
    parser_build_semantic.add_argument(
        "--clear-ledger",
        action="store_true",
        help="Clear checkpoint records from the ledger",
    )
    parser_build_semantic.add_argument(
        "--status",
        action="store_true",
        help="Inspect current checkpoint ledger counts without executing compilation",
    )
    parser_build_semantic.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan and list compilation units without executing LLM analysis",
    )
    parser_build_semantic.add_argument(
        "--version",
        "-v_id",
        dest="version",
        type=str,
        default="ESV",
        help="Target scripture translation for passage context (default: ESV)",
    )
    parser_build_semantic.add_argument(
        "--rpm",
        type=float,
        default=15.0,
        help="Rate limit in requests per minute (default: 15.0)",
    )
    parser_build_semantic.add_argument(
        "--no-embeddings",
        action="store_true",
        help="Skip generating dense vector embeddings",
    )
    parser_build_semantic.add_argument(
        "--strict",
        action="store_true",
        help="Enforce strict ExegeticalCritic error thresholds",
    )
    parser_build_semantic.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON telemetry",
    )
    parser_build_semantic.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print detailed progress and failure reasons",
    )

    def cmd_build_semantic(args: argparse.Namespace) -> int:
        from tools.build_semantic_db import run_semantic_build
        db_path = Path(args.db).resolve() if args.db else DEFAULT_DB_PATH
        return run_semantic_build(
            db_path=db_path,
            book_filter=getattr(args, "book", None),
            compile_all=getattr(args, "compile_all", False),
            resume=getattr(args, "resume", True),
            reset_failed=getattr(args, "reset_failed", False),
            clear_ledger=getattr(args, "clear_ledger", False),
            status_only=getattr(args, "status", False),
            dry_run=getattr(args, "dry_run", False),
            translation_id=getattr(args, "version", "ESV"),
            rate_limit_rpm=getattr(args, "rpm", 15.0),
            no_embeddings=getattr(args, "no_embeddings", False),
            strict_critic=getattr(args, "strict", False),
            json_output=getattr(args, "json", False),
            verbose=getattr(args, "verbose", False),
        )

    parser_build_semantic.set_defaults(func=cmd_build_semantic)

    # -------------------------------------------------------------------------
    # Subcommand: issues (aliases: bug, bugs)
    # -------------------------------------------------------------------------
    parser_issues = subparsers.add_parser(
        "issues",
        aliases=["bug", "bugs"],
        help="GitHub issue triage, bug report inspection, and resolution engine",
    )
    parser_issues.add_argument(
        "--repo",
        help="Target GitHub repository in 'owner/repo' format (auto-detected by default)",
    )
    parser_issues.add_argument(
        "--token",
        help="GitHub Personal Access Token (defaults to GITHUB_TOKEN or GH_TOKEN env var)",
    )
    issues_subparsers = parser_issues.add_subparsers(dest="issue_command", help="Issue operation to perform")

    p_iss_list = issues_subparsers.add_parser("list", help="List GitHub issues")
    p_iss_list.add_argument("--state", choices=["open", "closed", "all"], default="open", help="Issue state (default: open)")
    p_iss_list.add_argument("--limit", type=int, default=30, help="Maximum number of issues to fetch (default: 30)")
    p_iss_list.add_argument("--json", action="store_true", help="Output raw JSON")

    p_iss_view = issues_subparsers.add_parser("view", help="View issue details and discussion comments")
    p_iss_view.add_argument("issue_number", type=int, help="Issue number to view")
    p_iss_view.add_argument("--json", action="store_true", help="Output raw JSON")

    p_iss_comment = issues_subparsers.add_parser("comment", help="Add a comment to an issue")
    p_iss_comment.add_argument("issue_number", type=int, help="Issue number to comment on")
    p_iss_comment.add_argument("comment", help="Comment body text")

    p_iss_close = issues_subparsers.add_parser("close", help="Close a GitHub issue")
    p_iss_close.add_argument("issue_number", type=int, help="Issue number to close")
    p_iss_close.add_argument("--reason", choices=["completed", "not_planned"], default="completed", help="Close reason (default: completed)")
    p_iss_close.add_argument("--comment", help="Optional closing explanation comment to post before closing")

    p_iss_check = issues_subparsers.add_parser("check", help="Check for open issues (designed for ralph.sh loop)")
    p_iss_check.add_argument("--prompt", action="store_true", help="Output full Ralph prompt if open issues exist (exit 0)")
    p_iss_check.add_argument("--summary", action="store_true", help="Output single-line summary of primary issue (exit 0)")
    p_iss_check.add_argument("--quiet", "-q", action="store_true", help="Do not output anything, only exit code")
    p_iss_check.add_argument("--json", action="store_true", help="Output JSON status")
    p_iss_check.add_argument("--verbose", "-v", action="store_true", help="Print verbose status even if no issues found")

    def cmd_issues(args: argparse.Namespace) -> int:
        from tools import github_issues
        cmd = getattr(args, "issue_command", None)
        if not cmd or cmd == "list":
            if not hasattr(args, "state") or args.state is None:
                args.state = "open"
            if not hasattr(args, "limit") or args.limit is None:
                args.limit = 30
            if not hasattr(args, "json"):
                args.json = False
            return github_issues.cmd_list(args)
        elif cmd == "view":
            return github_issues.cmd_view(args)
        elif cmd == "comment":
            return github_issues.cmd_comment(args)
        elif cmd == "close":
            return github_issues.cmd_close(args)
        elif cmd == "check":
            return github_issues.cmd_check(args)
        return 0

    parser_issues.set_defaults(func=cmd_issues)

    # -------------------------------------------------------------------------
    # Subcommand: ask (aliases: rag, inquiry)
    # -------------------------------------------------------------------------
    parser_ask = subparsers.add_parser(
        "ask",
        aliases=["rag", "inquiry"],
        help="Query Scripture RAG engine with biblical, thematic, or typological inquiries",
        description=(
            "Execute Scripture RAG (Retrieval-Augmented Generation) inquiries. "
            "Retrieves grounded Scripture passages via multi-signal hybrid search "
            "(FTS5 keywords, semantic tags, typological arcs, and cross-references) "
            "and optionally synthesizes answers via Google Gemini under TGC theological guardrails."
        ),
    )
    parser_ask.add_argument(
        "query",
        nargs="+",
        help="Natural language inquiry, question, or thematic prompt (e.g. 'How does Jesus fulfill the Day of Atonement?')",
    )
    parser_ask.add_argument(
        "--context-only",
        action="store_true",
        help="Retrieve and display grounded Scripture context window without querying LLM",
    )
    parser_ask.add_argument(
        "--stream",
        action="store_true",
        help="Stream LLM answer tokens in real time via Server-Sent Events",
    )
    parser_ask.add_argument(
        "--show-context",
        action="store_true",
        help="Print retrieved Scripture context window details alongside LLM answer",
    )
    parser_ask.add_argument(
        "--max-passages",
        type=int,
        default=5,
        help="Maximum distinct Scripture passages to retrieve (default: 5)",
    )
    parser_ask.add_argument(
        "--max-tokens",
        type=int,
        default=4000,
        help="Maximum estimated token budget for context window (default: 4000)",
    )
    parser_ask.add_argument(
        "--model",
        default=None,
        help="Gemini model identifier (defaults to gemini-2.5-pro with gemini-2.0-flash fallback)",
    )
    parser_ask.add_argument(
        "--translation",
        default="ESV",
        help="Scripture translation for context retrieval (default: ESV with WEB fallback)",
    )
    parser_ask.add_argument(
        "--json",
        action="store_true",
        help="Output structured JSON payload (response and retrieved context)",
    )

    def cmd_ask(args: argparse.Namespace) -> int:
        from core.db import Database, DEFAULT_DB_PATH
        from core.rag import ScriptureRAGEngine
        from core.llm import GeminiClient, LLMAuthError, LLMError, get_gemini_api_key

        query_text = " ".join(getattr(args, "query", []) or []).strip()
        if not query_text:
            sys.stderr.write("Error: Inquiry query text cannot be empty.\n")
            return 1

        db_path = Path(args.db).resolve() if args.db else DEFAULT_DB_PATH
        if not db_path.exists():
            sys.stderr.write(f"Error: Database not found at '{db_path}'. Run './bible init'.\n")
            return 1

        output_json = getattr(args, "json", False)
        context_only = getattr(args, "context_only", False)
        show_context = getattr(args, "show_context", False)
        do_stream = getattr(args, "stream", False)
        max_passages = getattr(args, "max_passages", 5)
        max_tokens = getattr(args, "max_tokens", 4000)
        target_model = getattr(args, "model", None)
        target_trans = getattr(args, "translation", "ESV") or "ESV"

        color_enabled = (
            hasattr(sys.stdout, "isatty")
            and sys.stdout.isatty()
            and "NO_COLOR" not in os.environ
        )
        gold = "\033[1;33m" if color_enabled else ""
        cyan = "\033[36m" if color_enabled else ""
        dim = "\033[2m" if color_enabled else ""
        green = "\033[32m" if color_enabled else ""
        bold = "\033[1m" if color_enabled else ""
        reset = "\033[0m" if color_enabled else ""

        with Database(db_path, auto_init=False) as db:
            engine = ScriptureRAGEngine(db=db, translation=target_trans)
            context = engine.retrieve(
                query_text,
                max_passages=max_passages,
                max_tokens=max_tokens,
                preferred_translation=target_trans,
            )

            # Context-only mode
            if context_only:
                if output_json:
                    print(json.dumps(context.to_dict(), indent=2))
                    return 0

                print(f"\n{gold}{bold}=== Scripture RAG Retrieved Context ==={reset}")
                print(f"{bold}Inquiry:{reset} {query_text}")
                print(f"{dim}Passages: {len(context.passages)} | Total Verses: {context.total_verses} | Est. Tokens: {context.estimated_tokens}{reset}\n")

                if not context.passages:
                    print(f"{dim}(No matching scripture passages found for this inquiry.){reset}\n")
                    return 0

                for idx, p in enumerate(context.passages, 1):
                    reasons_str = f" [{', '.join(p.retrieval_reasons)}]" if p.retrieval_reasons else ""
                    print(f"{gold}[{idx}] {p.human_ref} ({p.translation}){reset} {dim}(Score: {p.score:.2f}{reasons_str}){reset}")
                    if p.pericope_title:
                        print(f"    {dim}Pericope: {p.pericope_title}{reset}")
                    if p.theological_loci:
                        print(f"    {dim}Loci: {', '.join(p.theological_loci)}{reset}")
                    if p.thematic_ribbons:
                        print(f"    {dim}Thematic Ribbons: {', '.join(p.thematic_ribbons)}{reset}")
                    if p.typological_arcs:
                        arc_summaries = [f"{a.get('type_human_ref', a.get('type_ref'))} ➔ {a.get('antitype_human_ref', a.get('antitype_ref'))}" for a in p.typological_arcs[:2]]
                        print(f"    {dim}Typological Arcs: {'; '.join(arc_summaries)}{reset}")
                    print(f"    {p.text}\n")
                return 0

            # Answer synthesis mode
            api_key = get_gemini_api_key()
            if not api_key:
                if output_json:
                    print(json.dumps({
                        "error": "GEMINI_API_KEY is not configured",
                        "context": context.to_dict(),
                    }, indent=2))
                    return 1
                sys.stderr.write(
                    f"\n{gold}Notice:{reset} GEMINI_API_KEY is not configured. Displaying retrieved Scripture context.\n"
                    f"{dim}To enable AI answer synthesis, set the GEMINI_API_KEY environment variable.{reset}\n\n"
                )
                print(f"{gold}{bold}=== Retrieved Scripture Context ==={reset}")
                for idx, p in enumerate(context.passages, 1):
                    print(f"{gold}[{idx}] {p.human_ref} ({p.translation}){reset} {dim}(Score: {p.score:.2f}){reset}")
                    print(f"    {p.text}\n")
                return 1

            client = GeminiClient(api_key=api_key)
            prompt_payload = context.format_prompt_payload()
            system_text = prompt_payload["system_instruction"]["parts"][0]["text"]
            user_prompt = prompt_payload["contents"][0]["parts"][0]["text"]

            if not output_json and not do_stream:
                print(f"{dim}Synthesizing grounded answer via Google Gemini ({client.model})...{reset}\n")

            if do_stream:
                if not output_json:
                    print(f"{bold}Inquiry:{reset} {query_text}\n")
                streamed_text = []
                try:
                    for chunk in client.generate_stream(user_prompt, system_instruction=system_text, model=target_model):
                        if chunk.text:
                            streamed_text.append(chunk.text)
                            sys.stdout.write(chunk.text)
                            sys.stdout.flush()
                    print()
                except LLMError as exc:
                    sys.stderr.write(f"\nError during streaming generation: {exc}\n")
                    return 1

                full_text = "".join(streamed_text)
                if show_context:
                    print(f"\n{gold}{bold}--- Retrieved Scripture Context ---{reset}")
                    for idx, p in enumerate(context.passages, 1):
                        print(f"{gold}[{idx}] {p.human_ref} ({p.translation}){reset} {dim}(Score: {p.score:.2f}){reset}")
                        print(f"    {p.text}\n")
                return 0

            # Non-streaming generation
            try:
                llm_resp = client.generate(user_prompt, system_instruction=system_text, model=target_model)
            except LLMError as exc:
                sys.stderr.write(f"Error during LLM answer synthesis: {exc}\n")
                return 1

            if output_json:
                res_dict = {
                    "query": query_text,
                    "answer": llm_resp.text,
                    "model": llm_resp.model,
                    "usage": llm_resp.usage,
                    "latency_seconds": llm_resp.latency_seconds,
                    "context": context.to_dict(),
                }
                print(json.dumps(res_dict, indent=2))
                return 0

            print(f"{bold}Inquiry:{reset} {query_text}\n")
            print(f"{llm_resp.text}\n")
            print(f"{dim}[Model: {llm_resp.model} | Latency: {llm_resp.latency_seconds:.2f}s | Passages: {len(context.passages)}]{reset}\n")

            if show_context:
                print(f"{gold}{bold}--- Grounded Context Passages ---{reset}")
                for idx, p in enumerate(context.passages, 1):
                    reasons = f" [{', '.join(p.retrieval_reasons)}]" if p.retrieval_reasons else ""
                    print(f"{gold}[{idx}] {p.human_ref} ({p.translation}){reset} {dim}(Score: {p.score:.2f}{reasons}){reset}")
                    print(f"    {p.text}\n")

            return 0

    parser_ask.set_defaults(func=cmd_ask)

    # -------------------------------------------------------------------------
    # Subcommand: chat (aliases: persona, character, dialogue)
    # -------------------------------------------------------------------------
    parser_chat = subparsers.add_parser(
        "chat",
        aliases=["persona", "character", "dialogue"],
        help="Interactive Biblical Character Dialogue Studio (e.g. paul, moses, david, peter)",
        description=(
            "Engage in reverent, TGC-theologically grounded dialogue with canonical biblical "
            "figures (Moses, David, Isaiah, Paul, Peter, John, etc.). Dynamically grounds character "
            "knowledge in their canonical scripture citations and preserves canonical realism."
        ),
    )
    parser_chat.add_argument(
        "character",
        nargs="?",
        default=None,
        help="Biblical character identifier or name (e.g. 'paul', 'moses', 'david', 'peter')",
    )
    parser_chat.add_argument(
        "message",
        nargs="*",
        default=[],
        help="Optional initial question or message to ask the biblical character (omitting starts interactive REPL)",
    )
    parser_chat.add_argument(
        "--list",
        action="store_true",
        help="List all canonical biblical character personas available in the studio",
    )
    parser_chat.add_argument(
        "--profile",
        action="store_true",
        help="Display full canonical profile, historical context, and key passages for character",
    )
    parser_chat.add_argument(
        "--stream",
        action="store_true",
        help="Stream response tokens in real time via Server-Sent Events",
    )
    parser_chat.add_argument(
        "--show-scripture",
        action="store_true",
        help="Display grounded Scripture passages loaded into the character's context window",
    )
    parser_chat.add_argument(
        "--translation",
        default="ESV",
        help="Preferred scripture translation for grounding passages (default: ESV with WEB fallback)",
    )
    parser_chat.add_argument(
        "--model",
        default=None,
        help="Gemini model identifier (defaults to gemini-2.5-pro with gemini-2.0-flash fallback)",
    )
    parser_chat.add_argument(
        "--temperature",
        type=float,
        default=0.4,
        help="Generation temperature (default: 0.4 for reverent consistency)",
    )
    parser_chat.add_argument(
        "--json",
        action="store_true",
        help="Output structured JSON payload (response, profile, and grounded passages)",
    )

    def cmd_chat(args: argparse.Namespace) -> int:
        from core.db import Database, DEFAULT_DB_PATH
        from core.persona import (
            CANONICAL_PERSONAS,
            BiblicalPersonaSession,
            create_persona_session,
            get_persona_definition,
            list_canonical_personas,
        )
        from core.llm import LLMError, get_gemini_api_key

        output_json = getattr(args, "json", False)
        do_list = getattr(args, "list", False)
        do_profile = getattr(args, "profile", False)
        do_stream = getattr(args, "stream", False)
        show_scripture = getattr(args, "show_scripture", False)
        target_trans = getattr(args, "translation", "ESV") or "ESV"
        target_model = getattr(args, "model", None)
        temperature = getattr(args, "temperature", 0.4)

        color_enabled = (
            hasattr(sys.stdout, "isatty")
            and sys.stdout.isatty()
            and "NO_COLOR" not in os.environ
        )
        gold = "\033[1;33m" if color_enabled else ""
        cyan = "\033[36m" if color_enabled else ""
        dim = "\033[2m" if color_enabled else ""
        green = "\033[32m" if color_enabled else ""
        bold = "\033[1m" if color_enabled else ""
        reset = "\033[0m" if color_enabled else ""

        # Listing mode: --list or no character argument provided
        char_arg = getattr(args, "character", None)
        if do_list or not char_arg:
            personas = list_canonical_personas()
            if output_json:
                print(json.dumps([p.to_dict() for p in personas], indent=2))
                return 0

            print(f"\n{gold}{bold}=== Canonical Biblical Character Studio ==={reset}")
            print(f"{dim}Total Personas: {len(personas)} | Grounded in Canonical Scripture & TGC Guardrails{reset}\n")
            print(f"{bold}{'ID':<14} {'Canonical Name':<22} {'Testament':<10} {'Era':<32}{reset}")
            print(f"{dim}{'─'*14} {'─'*22} {'─'*10} {'─'*32}{reset}")
            for p in personas:
                print(f"{gold}{p.id:<14}{reset} {bold}{p.canonical_name:<22}{reset} {cyan}{p.testament:<10}{reset} {dim}{p.canonical_era:<32}{reset}")
            print(f"\n{dim}To chat: ./bible chat <id> [\"your message\"] (e.g. './bible chat paul \"Why do you boast in weakness?\"'){reset}")
            print(f"{dim}To view profile: ./bible chat <id> --profile{reset}\n")
            return 0

        # Resolve character persona definition
        persona_def = get_persona_definition(char_arg)
        if not persona_def:
            sys.stderr.write(
                f"Error: Unknown biblical character persona '{char_arg}'.\n"
                f"Run './bible chat --list' to view all {len(CANONICAL_PERSONAS)} available characters.\n"
            )
            return 1

        db_path = Path(args.db).resolve() if args.db else DEFAULT_DB_PATH
        db = Database(db_path, auto_init=False) if db_path.exists() else None

        # Instantiate dialogue session
        kwargs = {
            "character_identifier": persona_def.id,
            "db": db,
            "translation": target_trans,
        }
        if target_model:
            kwargs["model"] = target_model
        session = create_persona_session(**kwargs)
        session.temperature = temperature

        # Profile-only inspection mode
        if do_profile:
            if output_json:
                prof_data = persona_def.to_dict()
                prof_data["grounded_passages"] = [
                    {
                        "reference": p.reference,
                        "translation": p.translation,
                        "verse_count": p.verse_count,
                        "text": p.text,
                    }
                    for p in session.grounded_passages
                ]
                print(json.dumps(prof_data, indent=2))
                return 0

            print(f"\n{gold}{bold}=== Biblical Character Profile: {persona_def.canonical_name} ==={reset}")
            print(f"{bold}Canonical Era:{reset} {persona_def.canonical_era} ({persona_def.testament})")
            print(f"{bold}Theological Role:{reset} {persona_def.theological_role}")
            print(f"{bold}Lifespan Context:{reset} {persona_def.lifespan_description}")
            print(f"{bold}Christ-Centered Orientation:{reset} {persona_def.christ_centered_orientation}")
            print(f"{bold}Speaking Style:{reset} {persona_def.speaking_style}\n")
            print(f"{bold}Core Trials & Canonical Realism:{reset}")
            for t in persona_def.core_trials_and_failures:
                print(f"  {dim}•{reset} {t}")
            print(f"\n{bold}Canonical Key Passages:{reset} {', '.join(persona_def.key_passages)}")
            print(f"{dim}Loaded {len(session.grounded_passages)} scripture passage texts into grounding context.{reset}\n")

            if show_scripture:
                print(f"{gold}{bold}--- Grounded Scripture Texts ---{reset}")
                for p in session.grounded_passages:
                    print(f"{gold}[{p.reference}] ({p.translation}){reset}\n{p.text}\n")
            return 0

        # Determine user message
        raw_msg_tokens = getattr(args, "message", []) or []
        user_msg = " ".join(raw_msg_tokens).strip()

        # Unary single-turn invocation if message provided
        if user_msg:
            # Check API key status
            api_key = get_gemini_api_key()
            if not api_key:
                resp = session.say(user_msg)
                if output_json:
                    print(json.dumps({
                        "character": persona_def.canonical_name,
                        "character_id": persona_def.id,
                        "query": user_msg,
                        "response": resp.text,
                        "offline_fallback": True,
                        "notice": "GEMINI_API_KEY not configured",
                    }, indent=2))
                    return 1

                sys.stderr.write(
                    f"\n{gold}Notice:{reset} GEMINI_API_KEY is not configured. Displaying canonical offline character card.\n"
                    f"{dim}To enable AI character dialogue synthesis, set GEMINI_API_KEY in your environment.{reset}\n\n"
                )
                print(f"{bold}Inquirer:{reset} {user_msg}\n")
                print(f"{gold}{bold}{persona_def.canonical_name}:{reset}\n{resp.text}\n")
                return 1

            if do_stream:
                if not output_json:
                    print(f"\n{bold}Inquirer:{reset} {user_msg}\n")
                    print(f"{gold}{bold}{persona_def.canonical_name}:{reset} ", end="", flush=True)
                streamed = []
                try:
                    for chunk in session.say_stream(user_msg):
                        streamed.append(chunk)
                        if not output_json:
                            sys.stdout.write(chunk)
                            sys.stdout.flush()
                    if not output_json:
                        print("\n")
                except LLMError as exc:
                    sys.stderr.write(f"\nError during streaming dialogue: {exc}\n")
                    return 1

                if show_scripture and not output_json:
                    print(f"{gold}{bold}--- Grounded Scripture Citations ---{reset}")
                    for p in session.grounded_passages:
                        print(f"{gold}[{p.reference}] ({p.translation}){reset}\n{p.text}\n")
                return 0

            # Unary non-streaming response
            try:
                resp = session.say(user_msg)
            except LLMError as exc:
                sys.stderr.write(f"Error during character dialogue: {exc}\n")
                return 1

            if output_json:
                res_dict = {
                    "character": resp.character_name,
                    "character_id": resp.character_id,
                    "query": user_msg,
                    "response": resp.text,
                    "model": resp.model,
                    "turn_count": resp.turn_count,
                    "offline_fallback": resp.offline_fallback,
                    "grounded_passages": resp.grounded_passages,
                }
                print(json.dumps(res_dict, indent=2))
                return 0

            print(f"\n{bold}Inquirer:{reset} {user_msg}\n")
            print(f"{gold}{bold}{persona_def.canonical_name}:{reset}\n{resp.text}\n")
            print(f"{dim}[Model: {resp.model} | Latency: {resp.latency_seconds:.2f}s | Grounded Citations: {len(resp.grounded_passages)}]{reset}\n")

            if show_scripture:
                print(f"{gold}{bold}--- Grounded Scripture Citations ---{reset}")
                for p in session.grounded_passages:
                    print(f"{gold}[{p.reference}] ({p.translation}){reset}\n{p.text}\n")
            return 0

        # Interactive multi-turn REPL loop
        has_key = session.llm_client.is_available()
        print(f"\n{gold}{bold}╔════════════════════════════════════════════════════════════════════════════════╗{reset}")
        print(f"{gold}{bold}║     Biblical Character Dialogue Studio — {persona_def.canonical_name:<37} ║{reset}")
        print(f"{gold}{bold}╚════════════════════════════════════════════════════════════════════════════════╝{reset}")
        print(f"{dim}Era: {persona_def.canonical_era} | Scripture Citations: {len(session.grounded_passages)} passages loaded{reset}")
        if has_key:
            print(f"{green}Engine: Online AI Active ({session.model}){reset}")
        else:
            print(f"{gold}Engine: Offline Mode (Set GEMINI_API_KEY for dynamic dialogue){reset}")
        print(f"{dim}Commands: '/profile' (view bio), '/passages' (view scripture), '/reset' (clear history), 'exit' / Ctrl+D (quit){reset}\n")

        prompt_str = f"{gold}{persona_def.id}> {reset}"
        while True:
            try:
                line = input(prompt_str).strip()
            except (EOFError, KeyboardInterrupt):
                print(f"\n{dim}Exiting dialogue with {persona_def.canonical_name}. Grace and peace.{reset}\n")
                break

            if not line:
                continue

            cmd_lower = line.lower()
            if cmd_lower in ("exit", "quit", ":q"):
                print(f"\n{dim}Exiting dialogue with {persona_def.canonical_name}. Grace and peace.{reset}\n")
                break
            if cmd_lower == "/reset":
                session.reset()
                print(f"{dim}Dialogue history reset for {persona_def.canonical_name}.{reset}\n")
                continue
            if cmd_lower in ("/profile", "/bio"):
                print(f"\n{bold}Theological Role:{reset} {persona_def.theological_role}")
                print(f"{bold}Lifespan Context:{reset} {persona_def.lifespan_description}")
                print(f"{bold}Christ-Centered Orientation:{reset} {persona_def.christ_centered_orientation}\n")
                continue
            if cmd_lower in ("/passages", "/scripture"):
                print(f"\n{gold}{bold}--- Grounded Scripture Citations ({len(session.grounded_passages)}) ---{reset}")
                for p in session.grounded_passages:
                    print(f"{gold}[{p.reference}] ({p.translation}){reset}\n{p.text}\n")
                continue
            if cmd_lower.startswith("/"):
                print(f"{dim}Available commands: /profile, /passages, /reset, exit{reset}\n")
                continue

            # Process dialogue turn
            if do_stream and has_key:
                print(f"\n{gold}{bold}{persona_def.canonical_name}:{reset} ", end="", flush=True)
                for chunk in session.say_stream(line):
                    sys.stdout.write(chunk)
                    sys.stdout.flush()
                print("\n")
            else:
                resp = session.say(line)
                print(f"\n{gold}{bold}{persona_def.canonical_name}:{reset}\n{resp.text}\n")

        return 0

    parser_chat.set_defaults(func=cmd_chat)

    # -------------------------------------------------------------------------
    # Subcommand: ci (aliases: workflow, workflows, actions)
    # -------------------------------------------------------------------------
    parser_ci = subparsers.add_parser(
        "ci",
        aliases=["workflow", "workflows", "actions"],
        help="Query GitHub Actions CI status, view job matrix steps, and watch workflow runs",
        description=(
            "Interrogate GitHub Actions continuous integration status and workflow runs. "
            "Inspect build and test matrix health across Python versions (3.10, 3.11, 3.12, 3.13), "
            "drill down into individual step failures, or watch in-progress runs after pushing."
        ),
    )
    parser_ci.add_argument(
        "--repo",
        "-r",
        help="Target GitHub repository in 'owner/repo' format (auto-detected by default)",
    )
    parser_ci.add_argument(
        "--token",
        "-t",
        help="GitHub Personal Access Token (defaults to GITHUB_TOKEN or GH_TOKEN env var)",
    )
    parser_ci.add_argument(
        "--branch",
        "-b",
        help="Filter workflow runs by branch (e.g. 'main')",
    )
    parser_ci.add_argument(
        "--limit",
        "-n",
        type=int,
        default=5,
        help="Number of workflow runs to fetch (default: 5)",
    )
    parser_ci.add_argument(
        "--details",
        "-d",
        action="store_true",
        help="Show detailed job matrix steps for latest run or specified run",
    )
    parser_ci.add_argument(
        "--run-id",
        type=int,
        help="Specific workflow run ID to inspect or watch",
    )
    parser_ci.add_argument(
        "--watch",
        "-w",
        action="store_true",
        help="Continuously monitor latest or specified run until completion",
    )
    parser_ci.add_argument(
        "--interval",
        type=float,
        default=6.0,
        help="Polling interval in seconds for --watch (default: 6.0)",
    )
    parser_ci.add_argument(
        "action",
        nargs="?",
        default="status",
        choices=["status", "check", "watch"],
        help="CI action: 'status' (view runs), 'check' (pre-flight health check), 'watch' (poll until completion)",
    )
    parser_ci.add_argument(
        "--check",
        "-c",
        action="store_true",
        help="Pre-flight health check: exit with code 1 if latest CI run failed",
    )
    parser_ci.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON telemetry",
    )

    def cmd_ci(args: argparse.Namespace) -> int:
        from tools import ci
        ci_args = []
        action = getattr(args, "action", "status") or "status"
        if action and action != "status":
            ci_args.append(action)
        if getattr(args, "check", False):
            ci_args.append("--check")
        if getattr(args, "repo", None):
            ci_args.extend(["--repo", args.repo])
        if getattr(args, "token", None):
            ci_args.extend(["--token", args.token])
        if getattr(args, "branch", None):
            ci_args.extend(["--branch", args.branch])
        if getattr(args, "limit", None) is not None:
            ci_args.extend(["--limit", str(args.limit)])
        if getattr(args, "details", False):
            ci_args.append("--details")
        if getattr(args, "run_id", None) is not None:
            ci_args.extend(["--run-id", str(args.run_id)])
        if getattr(args, "watch", False):
            ci_args.append("--watch")
        if getattr(args, "interval", None) is not None:
            ci_args.extend(["--interval", str(args.interval)])
        if getattr(args, "json", False):
            ci_args.append("--json")
        return ci.main(ci_args)

    parser_ci.set_defaults(func=cmd_ci)

    # Subcommand: keys / key / onboarding / credentials
    parser_keys = subparsers.add_parser(
        "keys",
        aliases=["key", "onboarding", "credentials"],
        help="Manage external API credentials (ESV and Gemini) and run onboarding wizard",
        description="Configure, probe, and manage external API credentials with secure POSIX permissions.",
    )
    parser_keys.add_argument(
        "action",
        nargs="?",
        default="status",
        choices=["status", "wizard", "probe", "set", "clear"],
        help="Action: 'status' (view config), 'wizard' (interactive setup), 'probe' (test connectivity), 'set' (save keys), 'clear' (remove keys)",
    )
    parser_keys.add_argument(
        "--wizard",
        "-w",
        action="store_true",
        help="Launch interactive setup wizard",
    )
    parser_keys.add_argument(
        "--probe",
        "-p",
        action="store_true",
        help="Perform live network connectivity probe on configured API keys",
    )
    parser_keys.add_argument(
        "--esv",
        type=str,
        default=None,
        help="Set Crossway ESV API key",
    )
    parser_keys.add_argument(
        "--gemini",
        type=str,
        default=None,
        help="Set Google Gemini API key",
    )
    parser_keys.add_argument(
        "--user-config",
        action="store_true",
        help="Save credentials to ~/.config/bible/ instead of repository config/",
    )
    parser_keys.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON telemetry",
    )

    def cmd_keys(args: argparse.Namespace) -> int:
        from tools import onboarding
        action = getattr(args, "action", "status") or "status"
        if getattr(args, "wizard", False) or action == "wizard":
            return onboarding.main(["wizard"])
        elif action == "set" or getattr(args, "esv", None) or getattr(args, "gemini", None):
            set_args = ["set"]
            if getattr(args, "esv", None):
                set_args.extend(["--esv", args.esv])
            if getattr(args, "gemini", None):
                set_args.extend(["--gemini", args.gemini])
            if getattr(args, "user_config", False):
                set_args.append("--user-config")
            if getattr(args, "probe", False):
                set_args.append("--probe")
            return onboarding.main(set_args)
        elif action == "clear":
            return onboarding.main(["clear", "all"])
        elif action == "probe":
            probe_args = ["probe"]
            if getattr(args, "json", False):
                probe_args.append("--json")
            return onboarding.main(probe_args)
        else:
            status_args = ["status"]
            if getattr(args, "probe", False):
                status_args.append("--probe")
            if getattr(args, "json", False):
                status_args.append("--json")
            return onboarding.main(status_args)

    parser_keys.set_defaults(func=cmd_keys)

    return parser


def preprocess_cli_argv(argv: Optional[Sequence[str]]) -> Optional[List[str]]:
    """Preprocess CLI arguments to route direct passage citations to the 'get' subcommand.

    If the first positional argument is not a registered subcommand or flag,
    and parses successfully as a canonical scripture reference (e.g. 'John 3:16', 'Rom 8:28-30'),
    'get' is automatically prepended to provide seamless citation ergonomics.
    """
    if argv is None:
        raw_args = list(sys.argv[1:])
    else:
        raw_args = list(argv)

    if not raw_args:
        return raw_args

    registered_commands = {
        "get", "compare", "search", "find", "translations", "versions",
        "tag", "tags", "crossref", "xref", "refs",
        "doctor", "summary", "shell", "interactive", "repl", "console",
        "serve", "server", "http", "web",
        "init", "setup", "bootstrap", "db", "database",
        "ribbon", "pericopes", "pericope", "chapters", "chapter",
        "arcs", "arc", "typology", "typologies",
        "slide", "render",
        "slide-batch", "batch-slide", "slides-batch", "batch-render", "slidebatch",
        "test", "tests", "check",
        "lint", "linter", "check-style",
        "coverage", "cov", "test-coverage",
        "esv", "esv-api", "esv-cache",
        "gemini", "llm", "gemini-api",
        "bench", "benchmark", "perf",
        "vector", "vec", "embedding", "embeddings",
        "audit-semantic", "audit", "audit-critic",
        "build-semantic", "compile-semantic", "build-db",
        "issues", "bug", "bugs",
        "ask", "rag", "inquiry",
        "chat", "persona", "character", "dialogue",
        "ci", "workflow", "workflows", "actions",
        "keys", "key", "onboarding", "credentials",
    }

    pos_idx = -1
    skip_next = False
    for i, token in enumerate(raw_args):
        if skip_next:
            skip_next = False
            continue
        if token == "--":
            if i + 1 < len(raw_args):
                pos_idx = i + 1
            break
        if token in (
            "--db", "-w", "--width", "-m", "--margin", "--theme", "-t", "--version",
            "--window", "-r", "--resolution", "-o", "--output", "-f", "--format",
            "--backend", "-b", "--dpi", "--quality", "--safe-area", "--align",
            "--font-size", "-c", "--citation-color", "--accent-color", "--font",
            "--line-spacing", "--citation-style", "--optical-center",
        ):
            skip_next = True
            continue
        if token.startswith("-"):
            continue
        pos_idx = i
        break

    if pos_idx != -1:
        first_pos = raw_args[pos_idx]
        if first_pos.lower() not in registered_commands:
            try:
                ref = parse_reference(first_pos)
            except (ValueError, TypeError):
                ref = None
            if ref is not None:
                raw_args.insert(pos_idx, "get")

    return raw_args


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI execution entry point."""
    processed_argv = preprocess_cli_argv(argv)
    parser = build_parser()
    args, unknown = parser.parse_known_args(processed_argv)

    # In Python 3.10 and 3.11, options placed between positional arguments (e.g.
    # 'chat paul --stream Greetings') cause subsequent positional tokens to be left in unknown.
    # If residual unknown arguments do not start with '-', fold them into the subparser's positional container.
    if unknown:
        non_options = [u for u in unknown if not u.startswith("-")]
        options = [u for u in unknown if u.startswith("-")]
        if options:
            parser.error(f"unrecognized arguments: {' '.join(unknown)}")
        if hasattr(args, "message") and isinstance(args.message, list):
            args.message.extend(non_options)
        elif hasattr(args, "query") and isinstance(args.query, list):
            args.query.extend(non_options)
        else:
            parser.error(f"unrecognized arguments: {' '.join(unknown)}")

    if getattr(args, "interactive", False):
        from cli.shell import launch_shell
        db_path = Path(args.db).resolve() if args.db else None
        return launch_shell(db_path=db_path)

    if not hasattr(args, "func") or args.func is None:
        parser.print_help()
        print("\nTip: Run './bible shell' for interactive scripture exploration.")
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
