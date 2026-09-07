"""Terminal typography, styling, text wrapping, and margin layout engine.

Zero-dependency implementation (Python 3 standard library only per ADR-003).
Provides formatting utilities for reading scripture in terminal environments:
  - ANSI color palette (sacred gold, amber, cyan, dim, bold, italics, reset)
  - NO_COLOR and TERM=dumb compliance (disables styling automatically)
  - Clean text wrapping with margin indentation and hanging verse numbers
  - Paragraph flow mode (flowing verses into biblical prose with superscript numbers)
  - Verse-per-line list mode with aligned verse tags
  - Box headers and decorative dividers for canonical citations
  - Multi-translation aligned and stacked comparison rendering with column margins
"""

import os
import re
import shutil
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from core.db import VerseRecord


# ==============================================================================
# ANSI Styling & Palette
# ==============================================================================

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
ITALIC = "\033[3m"
UNDERLINE = "\033[4m"

# Standard 16-color ANSI codes
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"

BOLD_YELLOW = "\033[1;33m"
BOLD_CYAN = "\033[1;36m"
BOLD_WHITE = "\033[1;37m"
BOLD_GOLD = "\033[1;33m"  # Classic terminal golden highlight

# Theme mapping
THEMES: Dict[str, Dict[str, str]] = {
    "sacred": {
        "header": "\033[1;33m",      # Bold Gold
        "verse_num": "\033[1;36m",    # Bold Cyan
        "text": "\033[0m",            # Standard terminal text
        "citation": "\033[1;37m",    # Bold White
        "version": "\033[2;37m",     # Dim White
        "accent": "\033[33m",        # Amber Gold
        "dim": "\033[2m",            # Dim
    },
    "plain": {
        "header": "",
        "verse_num": "",
        "text": "",
        "citation": "",
        "version": "",
        "accent": "",
        "dim": "",
    },
    "amber": {
        "header": "\033[1;33m",
        "verse_num": "\033[33m",
        "text": "\033[0m",
        "citation": "\033[1;33m",
        "version": "\033[2;33m",
        "accent": "\033[1;33m",
        "dim": "\033[2m",
    },
    "cyan": {
        "header": "\033[1;36m",
        "verse_num": "\033[36m",
        "text": "\033[0m",
        "citation": "\033[1;36m",
        "version": "\033[2;36m",
        "accent": "\033[1;36m",
        "dim": "\033[2m",
    },
}

_ANSI_REGEX = re.compile(r"\033\[[0-9;]*[a-zA-Z]")


def strip_ansi(text: str) -> str:
    """Strip ANSI escape sequences from text to measure visual printed length."""
    return _ANSI_REGEX.sub("", text)


def visual_len(text: str) -> int:
    """Return the display character width of a string disregarding ANSI escape codes."""
    return len(strip_ansi(text))


def should_use_color(force_color: Optional[bool] = None, stream=None) -> bool:
    """Determine whether ANSI styling should be active.

    Complies with:
      - Explicit force_color flag
      - NO_COLOR environment variable (https://no-color.org)
      - TERM=dumb
      - Stream TTY status
    """
    if force_color is not None:
        return force_color

    if os.environ.get("NO_COLOR"):
        return False

    term = os.environ.get("TERM", "")
    if term.lower() == "dumb":
        return False

    target_stream = stream or sys.stdout
    if hasattr(target_stream, "isatty"):
        return target_stream.isatty() and not sys.platform.startswith("win")

    return False


def get_terminal_width(default: int = 80, max_width: int = 88) -> int:
    """Get the usable width of the terminal clamped to a readable typographic measure.

    Reading long passages across wide (160+ column) terminal windows impairs readability.
    Clamping to ~80-88 characters provides optimal typographic line length.
    """
    try:
        cols = shutil.get_terminal_size((default, 24)).columns
        if cols <= 0:
            return default
        return min(cols - 2, max_width) if cols > 40 else cols
    except Exception:
        return default


# ==============================================================================
# Scripture Formatting Engine
# ==============================================================================

def format_citation_header(
    ref_header: str,
    translation_id: str,
    fallback_for: Optional[str] = None,
    width: int = 80,
    color: bool = True,
    theme_name: str = "sacred",
    box: bool = False,
) -> str:
    """Format an illuminated or clean citation header.

    Examples:
      Plain: === John 3:16-17 (WEB) ===
      Boxed:
      ┌────────────────────────────────────────────────────────┐
      │ John 3:16-17 (WEB)                                     │
      └────────────────────────────────────────────────────────┘
    """
    theme = THEMES.get(theme_name, THEMES["sacred"]) if color else THEMES["plain"]
    c_header = theme["header"]
    c_vers = theme["version"]
    c_reset = RESET if color else ""

    version_suffix = f" [fallback for {fallback_for}]" if fallback_for and fallback_for != translation_id else ""
    raw_title = f"{ref_header} ({translation_id}{version_suffix})"

    if not box:
        if color:
            return f"{c_header}=== {ref_header} {c_vers}({translation_id}{version_suffix}){c_header} ==={c_reset}"
        return f"=== {raw_title} ==="

    # Boxed header layout
    target_width = max(len(raw_title) + 6, min(width, 76))
    inner_width = target_width - 4
    padded_title = raw_title.ljust(inner_width)

    top = f"┌{'─' * (target_width - 2)}┐"
    bot = f"└{'─' * (target_width - 2)}┘"

    if color:
        mid = f"│ {c_header}{ref_header} {c_vers}({translation_id}{version_suffix}){c_reset}{' ' * (inner_width - len(raw_title))} │"
        return f"{c_header}{top}{c_reset}\n{mid}\n{c_header}{bot}{c_reset}"
    else:
        mid = f"│ {padded_title} │"
        return f"{top}\n{mid}\n{bot}"


def format_scripture_passage(
    verses: Sequence[VerseRecord],
    show_verse_numbers: bool = True,
    show_header: bool = True,
    fallback_for: Optional[str] = None,
    width: Optional[int] = None,
    margin: int = 0,
    flow: bool = False,
    color: bool = True,
    theme_name: str = "sacred",
    box_header: bool = False,
) -> str:
    """Format a sequence of verses with margin, wrapping, and typographic styling.

    Args:
        verses: List of verse records.
        show_verse_numbers: Whether verse numbers should appear.
        show_header: Whether passage title header appears.
        fallback_for: Optional translation ID this replaces.
        width: Maximum typographic line width (None = auto-detect up to 88).
        margin: Left margin indentation spaces.
        flow: If True, flow verses continuously into a paragraph (reader prose mode).
              If False, format each verse on its own line with hanging indentation.
        color: Whether to use ANSI terminal styling.
        theme_name: Styling palette ("sacred", "amber", "cyan", "plain").
        box_header: If True, draw a decorative box around the title header.

    Returns:
        Formatted multi-line text suitable for terminal output.
    """
    if not verses:
        return ""

    theme = THEMES.get(theme_name, THEMES["sacred"]) if color else THEMES["plain"]
    c_vnum = theme["verse_num"]
    c_text = theme["text"]
    c_reset = RESET if color else ""

    # Auto-resolve terminal width
    effective_width = (width or get_terminal_width()) - margin
    if effective_width < 30:
        effective_width = 30

    indent = " " * margin
    first = verses[0]
    last = verses[-1]
    b_name = first.book_name or str(first.book_id)
    t_id = first.translation_id

    # Construct canonical reference header text
    if len(verses) == 1:
        ref_header = f"{b_name} {first.chapter}:{first.verse}{first.subverse or ''}"
    elif first.chapter == last.chapter:
        ref_header = f"{b_name} {first.chapter}:{first.verse}-{last.verse}"
    else:
        ref_header = f"{b_name} {first.chapter}:{first.verse} - {last.chapter}:{last.verse}"

    lines: List[str] = []

    if show_header:
        hdr = format_citation_header(
            ref_header=ref_header,
            translation_id=t_id,
            fallback_for=fallback_for,
            width=effective_width,
            color=color,
            theme_name=theme_name,
            box=box_header,
        )
        for hline in hdr.split("\n"):
            lines.append(f"{indent}{hline}")
        lines.append("")

    if flow:
        # Flow mode: render continuous reader prose with bracketed/colored verse numbers
        flow_tokens: List[str] = []
        for v in verses:
            sub = v.subverse or ""
            if show_verse_numbers:
                if color:
                    tag = f"{c_vnum}[{v.verse}{sub}]{c_reset}"
                else:
                    tag = f"[{v.verse}{sub}]"
                flow_tokens.append(tag)
            flow_tokens.append(v.text)

        full_prose = " ".join(flow_tokens)

        # Word wrap with margin
        wrapped_lines = wrap_prefixed_text(prefix="", text=full_prose, width=effective_width)
        for wline in wrapped_lines:
            lines.append(f"{indent}{wline}")
    else:
        # Line-by-line verse mode: each verse starts on its own line with hanging indent
        for v in verses:
            sub = v.subverse or ""
            v_tag = f"[{v.verse}{sub}]" if show_verse_numbers else ""
            if v_tag:
                tag_len = len(v_tag) + 1
                hang_spaces = " " * tag_len
                prefix = f"{c_vnum}{v_tag}{c_reset} " if color else f"{v_tag} "

                wrapped = wrap_prefixed_text(
                    prefix=prefix,
                    text=v.text,
                    width=effective_width,
                    subsequent_indent=hang_spaces,
                )
            else:
                wrapped = wrap_prefixed_text(prefix="", text=v.text, width=effective_width)

            for wline in wrapped:
                lines.append(f"{indent}{wline}")

    return "\n".join(lines).rstrip()


def format_aligned_comparison_styled(
    ref_title: str,
    comparison_data: Dict[str, Tuple[Sequence[VerseRecord], str, bool]],
    show_header: bool = True,
    width: Optional[int] = None,
    margin: int = 0,
    color: bool = True,
    theme_name: str = "sacred",
    box_header: bool = False,
) -> str:
    """Format aligned comparison with terminal margins, wrapping, and theme colors."""
    theme = THEMES.get(theme_name, THEMES["sacred"]) if color else THEMES["plain"]
    c_hdr = theme["header"]
    c_vers = theme["version"]
    c_accent = theme["accent"]
    c_reset = RESET if color else ""

    effective_width = (width or get_terminal_width()) - margin
    if effective_width < 30:
        effective_width = 30
    indent = " " * margin

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
        raw_title = f"Compare: {ref_title} ({', '.join(trans_labels)})"

        if box_header:
            target_width = max(len(raw_title) + 6, min(effective_width, 76))
            inner_width = target_width - 4
            top = f"┌{'─' * (target_width - 2)}┐"
            bot = f"└{'─' * (target_width - 2)}┘"
            if color:
                mid = f"│ {c_hdr}{raw_title}{c_reset}{' ' * (inner_width - len(raw_title))} │"
                hdr_str = f"{c_hdr}{top}{c_reset}\n{mid}\n{c_hdr}{bot}{c_reset}"
            else:
                mid = f"│ {raw_title.ljust(inner_width)} │"
                hdr_str = f"{top}\n{mid}\n{bot}"
            for hline in hdr_str.split("\n"):
                lines.append(f"{indent}{hline}")
        else:
            if color:
                lines.append(f"{indent}{c_hdr}=== Compare: {ref_title} {c_vers}({', '.join(trans_labels)}){c_hdr} ==={c_reset}")
            else:
                lines.append(f"{indent}=== {raw_title} ===")
        lines.append("")

    sorted_keys = sorted(verse_map.keys())
    for idx, key in enumerate(sorted_keys):
        label = verse_labels[key]
        if color:
            lines.append(f"{indent}{c_accent}--- {label} ---{c_reset}")
        else:
            lines.append(f"{indent}--- {label} ---")

        for req_id, (_, eff_id, is_fb) in comparison_data.items():
            text = verse_map[key].get(req_id, "(Verse unavailable in this translation)")
            tag = f"[{eff_id}*]" if is_fb else f"[{eff_id}]"
            tag_col = f"{tag:<8} "
            hang_spaces = " " * len(tag_col)

            if color:
                colored_prefix = f"{theme['verse_num']}{tag:<8}{c_reset} "
                wrapped = wrap_prefixed_text(
                    prefix=colored_prefix,
                    text=text,
                    width=effective_width,
                    subsequent_indent=hang_spaces,
                )
            else:
                wrapped = wrap_prefixed_text(
                    prefix=tag_col,
                    text=text,
                    width=effective_width,
                    subsequent_indent=hang_spaces,
                )

            for wline in wrapped:
                lines.append(f"{indent}{wline}")

        if idx < len(sorted_keys) - 1:
            lines.append("")

    return "\n".join(lines)


def wrap_prefixed_text(
    prefix: str,
    text: str,
    width: int = 80,
    subsequent_indent: str = "",
) -> List[str]:
    """Wrap words of `text` after an initial `prefix` without splitting fixed whitespace in prefix."""
    words = text.split()
    if not words:
        return [prefix.rstrip()]

    lines: List[str] = []
    curr_line: List[str] = [prefix + words[0]]
    curr_len = visual_len(prefix) + visual_len(words[0])

    for word in words[1:]:
        w_len = visual_len(word)
        if curr_len + 1 + w_len <= width:
            curr_line.append(word)
            curr_len += 1 + w_len
        else:
            lines.append(" ".join(curr_line))
            curr_line = [subsequent_indent + word if subsequent_indent else word]
            curr_len = visual_len(subsequent_indent) + w_len

    if curr_line:
        lines.append(" ".join(curr_line))

    return lines


# ==============================================================================
# Semantic Tagging Formatting Utilities
# ==============================================================================


def format_tags_badge(
    tags: Sequence[Union[str, Any]],
    styling: bool = True,
) -> str:
    """Format a sequence of tags as subtle inline badges/pills."""
    if not tags:
        return ""
    tag_names: List[str] = []
    for t in tags:
        if isinstance(t, str):
            tag_names.append(t)
        elif hasattr(t, "tag_name"):
            tag_names.append(t.tag_name)
        elif hasattr(t, "name"):
            tag_names.append(t.name)
        else:
            tag_names.append(str(t))

    if not tag_names:
        return ""

    if styling:
        pills = [f"{DIM}[{RESET}{BOLD_CYAN}{name}{RESET}{DIM}]{RESET}" for name in tag_names]
        return f"{DIM}🏷  {RESET}" + " ".join(pills)
    else:
        pills = [f"[{name}]" for name in tag_names]
        return "Tags: " + " ".join(pills)


def format_tag_table(
    tags: Sequence[Any],
    styling: bool = True,
    max_width: Optional[int] = None,
) -> str:
    """Format a list of TagSummary items as an aligned table."""
    if not tags:
        return "No tags found."

    headers = ("Tag Name", "Category", "Passages", "Starred", "Books", "Description")
    rows: List[Tuple[str, str, str, str, str, str]] = []
    for t in tags:
        name = getattr(t, "name", "")
        cat = getattr(t, "category", "")
        passages = str(getattr(t, "passage_count", 0))
        starred = str(getattr(t, "starred_count", 0))
        books = str(getattr(t, "distinct_books", 0))
        desc = getattr(t, "description", "") or ""
        rows.append((name, cat, passages, starred, books, desc))

    col_widths = [len(h) for h in headers]
    for r in rows:
        for i in range(5):  # Name, Cat, Passages, Starred, Books
            col_widths[i] = max(col_widths[i], len(r[i]))

    # Cap description column to remaining terminal width
    term_width = max_width or get_terminal_width()
    prefix_width = sum(col_widths[:5]) + 10  # 2 spaces between columns
    desc_width = max(20, term_width - prefix_width)
    col_widths[5] = desc_width

    lines: List[str] = []
    header_str = (
        f"{headers[0]:<{col_widths[0]}}  "
        f"{headers[1]:<{col_widths[1]}}  "
        f"{headers[2]:>{col_widths[2]}}  "
        f"{headers[3]:>{col_widths[3]}}  "
        f"{headers[4]:>{col_widths[4]}}  "
        f"{headers[5]}"
    )
    divider = "-" * min(term_width, prefix_width + desc_width)

    if styling:
        lines.append(f"{BOLD_GOLD}{header_str}{RESET}")
        lines.append(f"{DIM}{divider}{RESET}")
        for r in rows:
            desc = r[5]
            if len(desc) > desc_width:
                desc = desc[:desc_width - 3] + "..."
            line = (
                f"{BOLD_WHITE}{r[0]:<{col_widths[0]}}{RESET}  "
                f"{CYAN}{r[1]:<{col_widths[1]}}{RESET}  "
                f"{YELLOW}{r[2]:>{col_widths[2]}}{RESET}  "
                f"{DIM}{r[3]:>{col_widths[3]}}{RESET}  "
                f"{DIM}{r[4]:>{col_widths[4]}}{RESET}  "
                f"{desc}"
            )
            lines.append(line)
    else:
        lines.append(header_str)
        lines.append(divider)
        for r in rows:
            desc = r[5]
            if len(desc) > desc_width:
                desc = desc[:desc_width - 3] + "..."
            line = (
                f"{r[0]:<{col_widths[0]}}  "
                f"{r[1]:<{col_widths[1]}}  "
                f"{r[2]:>{col_widths[2]}}  "
                f"{r[3]:>{col_widths[3]}}  "
                f"{r[4]:>{col_widths[4]}}  "
                f"{desc}"
            )
            lines.append(line)

    return "\n".join(lines)


def format_tagged_passages(
    tagged_passages: Sequence[Any],
    styling: bool = True,
    max_width: Optional[int] = None,
) -> str:
    """Format a sequence of TaggedPassage records with verse text and citations."""
    if not tagged_passages:
        return "No passages found for this tag."

    term_width = max_width or get_terminal_width()
    blocks: List[str] = []

    for idx, tp in enumerate(tagged_passages, 1):
        star = " ★" if getattr(tp, "starred", False) else ""
        header_title = f"{tp.human_ref}{star}"
        notes = getattr(tp, "notes", None)

        lines: List[str] = []
        rule_len = max(10, min(term_width, len(header_title) + 20))
        rule = "─" * rule_len
        if styling:
            lines.append(f"{BOLD_GOLD}── {header_title} {rule}{RESET}"[:term_width])
        else:
            lines.append(f"── {header_title} {rule}"[:term_width])

        if tp.verses:
            passage_lines = format_scripture_passage(
                verses=tp.verses,
                show_verse_numbers=True,
                show_header=False,
                width=term_width,
                flow=True,
                margin=2,
                color=styling,
            )
            lines.append(passage_lines)
        elif getattr(tp, "text", ""):
            lines.append(f"  {tp.text}")

        if notes:
            if styling:
                lines.append(f"  {DIM}Note: {notes}{RESET}")
            else:
                lines.append(f"  Note: {notes}")

        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)


def format_topic_density_table(
    densities: Sequence[Any],
    styling: bool = True,
    max_width: Optional[int] = None,
) -> str:
    """Format BookTopicDensity records as an aligned terminal table."""
    if not densities:
        return "No topic density records found matching criteria."

    headers = ["#", "Book", "Testament", "Chapters", "Passages", "Starred", "Tags", "Top Tags"]

    rows: List[List[str]] = []
    for d in densities:
        # Get top 2-3 tags by count
        top_tags_sorted = sorted(
            getattr(d, "tag_counts", {}).items(),
            key=lambda item: item[1],
            reverse=True,
        )[:3]
        top_tags_str = ", ".join(f"{name} ({cnt})" for name, cnt in top_tags_sorted) if top_tags_sorted else "-"

        rows.append([
            str(getattr(d, "book_id", "")),
            str(getattr(d, "book_name", "")),
            str(getattr(d, "testament", "")),
            str(getattr(d, "total_chapters", "")),
            str(getattr(d, "passage_count", "")),
            str(getattr(d, "starred_count", "")),
            str(getattr(d, "distinct_tags", "")),
            top_tags_str,
        ])

    col_widths = [len(h) for h in headers]
    for r in rows:
        for i in range(len(headers) - 1):  # exclude top tags from hard fixed width
            col_widths[i] = max(col_widths[i], len(r[i]))

    lines: List[str] = []
    if styling:
        header_line = (
            f"{BOLD_GOLD}{headers[0]:>{col_widths[0]}}{RESET}  "
            f"{BOLD_GOLD}{headers[1]:<{col_widths[1]}}{RESET}  "
            f"{BOLD_GOLD}{headers[2]:^{col_widths[2]}}{RESET}  "
            f"{BOLD_GOLD}{headers[3]:>{col_widths[3]}}{RESET}  "
            f"{BOLD_GOLD}{headers[4]:>{col_widths[4]}}{RESET}  "
            f"{BOLD_GOLD}{headers[5]:>{col_widths[5]}}{RESET}  "
            f"{BOLD_GOLD}{headers[6]:>{col_widths[6]}}{RESET}  "
            f"{BOLD_GOLD}{headers[7]}{RESET}"
        )
        sep = "  ".join("─" * w for w in col_widths[:7]) + "  ──────────────"
        lines.append(header_line)
        lines.append(f"{DIM}{sep}{RESET}")
        for r in rows:
            line = (
                f"{DIM}{r[0]:>{col_widths[0]}}{RESET}  "
                f"{BOLD_GOLD}{r[1]:<{col_widths[1]}}{RESET}  "
                f"{r[2]:^{col_widths[2]}}  "
                f"{r[3]:>{col_widths[3]}}  "
                f"{r[4]:>{col_widths[4]}}  "
                f"{r[5]:>{col_widths[5]}}  "
                f"{r[6]:>{col_widths[6]}}  "
                f"{DIM}{r[7]}{RESET}"
            )
            lines.append(line)
    else:
        header_line = (
            f"{headers[0]:>{col_widths[0]}}  "
            f"{headers[1]:<{col_widths[1]}}  "
            f"{headers[2]:^{col_widths[2]}}  "
            f"{headers[3]:>{col_widths[3]}}  "
            f"{headers[4]:>{col_widths[4]}}  "
            f"{headers[5]:>{col_widths[5]}}  "
            f"{headers[6]:>{col_widths[6]}}  "
            f"{headers[7]}"
        )
        sep = "  ".join("─" * w for w in col_widths[:7]) + "  ──────────────"
        lines.append(header_line)
        lines.append(sep)
        for r in rows:
            line = (
                f"{r[0]:>{col_widths[0]}}  "
                f"{r[1]:<{col_widths[1]}}  "
                f"{r[2]:^{col_widths[2]}}  "
                f"{r[3]:>{col_widths[3]}}  "
                f"{r[4]:>{col_widths[4]}}  "
                f"{r[5]:>{col_widths[5]}}  "
                f"{r[6]:>{col_widths[6]}}  "
                f"{r[7]}"
            )
            lines.append(line)

    return "\n".join(lines)


def format_tag_co_occurrence_table(
    co_occurrences: Sequence[Any],
    styling: bool = True,
    max_width: Optional[int] = None,
) -> str:
    """Format TagCoOccurrence pair metrics as an aligned terminal table."""
    if not co_occurrences:
        return "No tag co-occurrences found meeting threshold."

    headers = ["Tag A", "Tag B", "Shared Passages", "Jaccard Index", "Dice Coeff"]
    rows: List[List[str]] = []
    for co in co_occurrences:
        rows.append([
            str(getattr(co, "tag_a", "")),
            str(getattr(co, "tag_b", "")),
            str(getattr(co, "shared_passages", "")),
            f"{getattr(co, 'jaccard_similarity', 0.0):.3f}",
            f"{getattr(co, 'dice_coefficient', 0.0):.3f}",
        ])

    col_widths = [len(h) for h in headers]
    for i in range(len(headers)):
        for r in rows:
            col_widths[i] = max(col_widths[i], len(r[i]))

    lines: List[str] = []
    if styling:
        header_line = (
            f"{BOLD_GOLD}{headers[0]:<{col_widths[0]}}{RESET}  "
            f"{BOLD_GOLD}{headers[1]:<{col_widths[1]}}{RESET}  "
            f"{BOLD_GOLD}{headers[2]:>{col_widths[2]}}{RESET}  "
            f"{BOLD_GOLD}{headers[3]:>{col_widths[3]}}{RESET}  "
            f"{BOLD_GOLD}{headers[4]:>{col_widths[4]}}{RESET}"
        )
        sep = "  ".join("─" * w for w in col_widths)
        lines.append(header_line)
        lines.append(f"{DIM}{sep}{RESET}")
        for r in rows:
            line = (
                f"{BOLD_GOLD}{r[0]:<{col_widths[0]}}{RESET}  "
                f"{BOLD_GOLD}{r[1]:<{col_widths[1]}}{RESET}  "
                f"{r[2]:>{col_widths[2]}}  "
                f"{r[3]:>{col_widths[3]}}  "
                f"{r[4]:>{col_widths[4]}}"
            )
            lines.append(line)
    else:
        header_line = (
            f"{headers[0]:<{col_widths[0]}}  "
            f"{headers[1]:<{col_widths[1]}}  "
            f"{headers[2]:>{col_widths[2]}}  "
            f"{headers[3]:>{col_widths[3]}}  "
            f"{headers[4]:>{col_widths[4]}}"
        )
        sep = "  ".join("─" * w for w in col_widths)
        lines.append(header_line)
        lines.append(sep)
        for r in rows:
            line = (
                f"{r[0]:<{col_widths[0]}}  "
                f"{r[1]:<{col_widths[1]}}  "
                f"{r[2]:>{col_widths[2]}}  "
                f"{r[3]:>{col_widths[3]}}  "
                f"{r[4]:>{col_widths[4]}}"
            )
            lines.append(line)

    return "\n".join(lines)


def format_verse_relevance_table(
    rankings: Sequence[Any],
    styling: bool = True,
    max_width: Optional[int] = None,
    show_text: bool = True,
) -> str:
    """Format VerseRelevance ranked passages for terminal presentation."""
    if not rankings:
        return "No passages matched the requested topic tags."

    term_width = max_width or get_terminal_width()
    blocks: List[str] = []

    for idx, vr in enumerate(rankings, 1):
        star = " ★" if getattr(vr, "starred", False) else ""
        ref_title = f"{vr.human_ref}{star}"
        score = getattr(vr, "score", 0.0)
        matched = ", ".join(getattr(vr, "matched_tags", []))
        ratio = getattr(vr, "match_ratio", 0.0)

        lines: List[str] = []
        rule_len = max(10, min(term_width, len(ref_title) + 25))
        rule = "─" * rule_len

        if styling:
            header = (
                f"{BOLD_GOLD}#{idx} {ref_title}{RESET}  "
                f"{DIM}Score: {score:.3f} | Tags: [{matched}] ({ratio*100:.0f}% match){RESET}"
            )
            lines.append(header)
            lines.append(f"{DIM}{rule}{RESET}")
        else:
            header = f"#{idx} {ref_title}  Score: {score:.3f} | Tags: [{matched}] ({ratio*100:.0f}% match)"
            lines.append(header)
            lines.append(rule)

        if show_text:
            verses = getattr(vr, "verses", [])
            if verses:
                passage_lines = format_scripture_passage(
                    verses=verses,
                    show_verse_numbers=True,
                    show_header=False,
                    width=term_width,
                    flow=True,
                    margin=2,
                    color=styling,
                )
                lines.append(passage_lines)
            elif getattr(vr, "text", ""):
                lines.append(f"  {vr.text}")

        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)



# ==============================================================================
# Cross-Reference Formatting Utilities
# ==============================================================================


def format_cross_references(
    hydrated_refs: Sequence[Any],
    styling: bool = True,
    max_width: Optional[int] = None,
) -> str:
    """Format a sequence of HydratedCrossReference objects for terminal presentation."""
    if not hydrated_refs:
        return "No cross-references found."

    term_width = max_width or get_terminal_width()
    blocks: List[str] = []

    for idx, xr in enumerate(hydrated_refs, 1):
        lines: List[str] = []
        icon = getattr(xr, "icon", "🔗")
        label = getattr(xr, "relationship_label", "Cross-Reference")
        rel_type = getattr(xr, "relationship_type", "thematic")
        related_ref = getattr(xr, "related_ref", "")
        direction = getattr(xr, "direction", "outgoing")
        arrow = "➜" if direction == "outgoing" else ("⬅" if direction == "incoming" else "↔")
        weight = getattr(xr, "weight", 1.0)
        notes = getattr(xr, "notes", None)

        if styling:
            header = (
                f"{BOLD_GOLD}{icon}  {related_ref}{RESET}  "
                f"{DIM}{arrow} [{label}]{RESET}  "
                f"{DIM}(weight: {weight:.2f}){RESET}"
            )
            rule = f"{DIM}─" * min(60, term_width) + f"{RESET}"
        else:
            header = f"{icon}  {related_ref}  {arrow} [{label}] (weight: {weight:.2f})"
            rule = "─" * min(60, term_width)

        lines.append(header)
        lines.append(rule)

        verses = getattr(xr, "related_verses", [])
        if verses:
            passage_lines = format_scripture_passage(
                verses=verses,
                show_verse_numbers=True,
                show_header=False,
                width=term_width,
                flow=True,
                margin=2,
                color=styling,
            )
            lines.append(passage_lines)
        else:
            rel_text = getattr(xr, "related_text", "")
            if rel_text:
                lines.append(f"  {rel_text}")

        if notes:
            if styling:
                lines.append(f"  {DIM}Note: {notes}{RESET}")
            else:
                lines.append(f"  Note: {notes}")

        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)


def format_cross_reference_table(
    edges: Sequence[Any],
    styling: bool = True,
) -> str:
    """Format a collection of CrossReferenceRecord objects into a clean tabular layout."""
    if not edges:
        return "No cross-references recorded."

    headers = ["ID", "Source", "Target", "Type", "Weight", "Notes"]
    rows: List[List[str]] = []
    for e in edges:
        notes_str = e.notes or ""
        rows.append([
            str(e.id or ""),
            e.source_human_ref,
            e.target_human_ref,
            e.relationship_type,
            f"{e.weight:.2f}",
            notes_str,
        ])

    col_widths = [len(h) for h in headers]
    for r in rows:
        for i in range(5):
            col_widths[i] = max(col_widths[i], len(r[i]))
        col_widths[5] = max(col_widths[5], min(40, len(r[5])))

    term_width = get_terminal_width()
    desc_width = max(15, term_width - sum(col_widths[:5]) - 14)
    col_widths[5] = min(col_widths[5], desc_width)

    lines: List[str] = []
    header_line = (
        f"{headers[0]:<{col_widths[0]}}  "
        f"{headers[1]:<{col_widths[1]}}  "
        f"{headers[2]:<{col_widths[2]}}  "
        f"{headers[3]:<{col_widths[3]}}  "
        f"{headers[4]:>{col_widths[4]}}  "
        f"{headers[5]}"
    )

    if styling:
        lines.append(f"{BOLD_CYAN}{header_line}{RESET}")
        sep = "  ".join("─" * w for w in col_widths[:5]) + f"  {'─' * col_widths[5]}"
        lines.append(f"{DIM}{sep}{RESET}")
        for r in rows:
            notes = r[5]
            if len(notes) > col_widths[5]:
                notes = notes[: col_widths[5] - 3] + "..."
            line = (
                f"{DIM}{r[0]:<{col_widths[0]}}{RESET}  "
                f"{BOLD_GOLD}{r[1]:<{col_widths[1]}}{RESET}  "
                f"{BOLD_GOLD}{r[2]:<{col_widths[2]}}{RESET}  "
                f"{r[3]:<{col_widths[3]}}  "
                f"{r[4]:>{col_widths[4]}}  "
                f"{DIM}{notes}{RESET}"
            )
            lines.append(line)
    else:
        lines.append(header_line)
        sep = "  ".join("─" * w for w in col_widths[:5]) + f"  {'─' * col_widths[5]}"
        lines.append(sep)
        for r in rows:
            notes = r[5]
            if len(notes) > col_widths[5]:
                notes = notes[: col_widths[5] - 3] + "..."
            line = (
                f"{r[0]:<{col_widths[0]}}  "
                f"{r[1]:<{col_widths[1]}}  "
                f"{r[2]:<{col_widths[2]}}  "
                f"{r[3]:<{col_widths[3]}}  "
                f"{r[4]:>{col_widths[4]}}  "
                f"{notes}"
            )
            lines.append(line)

    return "\n".join(lines)


