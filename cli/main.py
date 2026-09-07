"""Main CLI entry point and argument parsing for Bible Engine.

Zero-dependency implementation (Python 3 standard library only per ADR-003).
Provides commands:
  - get: Fetch and display scripture passages by reference with multi-translation & fallback support.
  - compare: Compare scripture passages across translations in aligned or stacked layouts.
  - search: Full-text search across scripture using SQLite FTS5 with phrase, book, and testament filters.
  - translations: List installed scripture translations, copyright status, and verse counts.
  - doctor: Run comprehensive zero-dependency health, dependency, and documentation diagnostics.
  - summary: Generate executive summary and trajectory briefing across recent Ralph iterations.
"""

import argparse
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from core.db import DEFAULT_DB_PATH, Database, SearchResult, VerseRecord
from core.reference import Reference, get_book, parse_reference
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
                    width=wrap_width,
                    margin=margin_width,
                    flow=flow_mode,
                    color=color_enabled,
                    theme=theme_name,
                    box=box_header,
                )
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
            f"Run 'python3 tools/ingest_web.py' to compile offline scripture database.\n"
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


def cmd_tag(args: argparse.Namespace) -> int:
    """Handle 'tag' subcommand: semantic tagging, passage annotation, and taxonomy."""
    tag_action = getattr(args, "tag_action", None)
    if not tag_action:
        tag_action = "list"

    db_path = Path(args.db).resolve() if args.db else DEFAULT_DB_PATH
    if not db_path.exists():
        sys.stderr.write(
            f"Error: Database file not found at '{db_path}'.\n"
            f"Run 'python3 tools/ingest_web.py' to compile offline scripture database.\n"
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
            from core.terminal import format_tag_table, format_tagged_passages
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
                version = getattr(args, "version", "WEB") or "WEB"
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
            f"Run 'python3 tools/ingest_web.py' to compile offline scripture database.\n"
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
                trans_id = getattr(args, "version", "WEB")
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
        help="Translation to search (e.g. 'WEB', 'ESV', or 'all', default: WEB)",
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
    p_tag_show.add_argument("--version", "-t", default="WEB", help="Scripture translation for verse text (default: WEB)")
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

    # tag prompt
    p_tag_prompt = tag_subparsers.add_parser("prompt", help="Generate and display LLM tagging prompt for a passage")
    p_tag_prompt.add_argument("reference", help="Scripture citation or span (e.g. 'Romans 8:1-11')")
    p_tag_prompt.add_argument("--version", "-t", default="WEB", help="Scripture translation ID (default: WEB)")
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
    p_tag_gen.add_argument("--version", "-t", default="WEB", help="Scripture translation ID (default: WEB)")
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
    p_tag_batch.add_argument("--version", "-t", default="WEB", help="Scripture translation ID (default: WEB)")
    p_tag_batch.add_argument("--category", help="Comma-separated category filter")
    p_tag_batch.add_argument("--no-new-tags", action="store_true", help="Disallow novel tags")
    p_tag_batch.add_argument("--max-tags", type=int, default=6, help="Maximum tags per passage")
    p_tag_batch.add_argument("--format", choices=["jsonl", "json"], default="jsonl", help="Batch output format")
    p_tag_batch.add_argument("--output", "-o", help="Write batch output to file")

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
    p_xr_for.add_argument("--version", "-t", default="WEB", help="Scripture translation for related verse texts (default: WEB)")
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
        code, _ = run_all_checks(repo_root=repo_root, color=is_tty, fast=fast_mode, quiet=quiet_mode)
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
        default="WEB",
        help="Initial active translation ID (default: WEB)",
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
        if token in ("--db", "-w", "--width", "-m", "--margin", "--theme", "-t", "--version", "--window"):
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
    args = parser.parse_args(processed_argv)

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
