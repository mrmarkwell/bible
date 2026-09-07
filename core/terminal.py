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
from typing import Dict, List, Optional, Sequence, Tuple, Union

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
