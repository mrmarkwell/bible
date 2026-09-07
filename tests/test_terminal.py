"""Hermetic unit tests for terminal typography, ANSI styling, text wrapping, and layouts.

Zero external dependencies (Python 3 standard library only per ADR-003).
"""

import os
import unittest
from unittest.mock import patch

from core.db import VerseRecord
from core.terminal import (
    BOLD,
    BOLD_GOLD,
    RESET,
    THEMES,
    format_aligned_comparison_styled,
    format_citation_header,
    format_scripture_passage,
    get_terminal_width,
    should_use_color,
    strip_ansi,
    visual_len,
    wrap_prefixed_text,
)


class TestTerminalTypography(unittest.TestCase):
    """Test ANSI styling, wrapping, margins, and typography formatting."""

    def setUp(self):
        self.v1 = VerseRecord(
            translation_id="WEB",
            book_id=43,
            book_name="John",
            chapter=3,
            verse=16,
            text="For God so loved the world, that he gave his one and only Son, that whoever believes in him should not perish, but have eternal life.",
            canonical_verse_id=43003016,
        )
        self.v2 = VerseRecord(
            translation_id="WEB",
            book_id=43,
            book_name="John",
            chapter=3,
            verse=17,
            text="For God didn't send his Son into the world to judge the world, but that the world should be saved through him.",
            canonical_verse_id=43003017,
        )

    def test_strip_ansi_and_visual_len(self):
        text = f"{BOLD_GOLD}John 3:16{RESET}"
        self.assertEqual(strip_ansi(text), "John 3:16")
        self.assertEqual(visual_len(text), 9)
        self.assertEqual(strip_ansi("Normal text without codes"), "Normal text without codes")
        self.assertEqual(visual_len("Normal text without codes"), 25)

    def test_should_use_color(self):
        # Force flag overrides environment
        self.assertTrue(should_use_color(force_color=True))
        self.assertFalse(should_use_color(force_color=False))

        # NO_COLOR disables color
        with patch.dict(os.environ, {"NO_COLOR": "1"}):
            self.assertFalse(should_use_color())

        # TERM=dumb disables color
        with patch.dict(os.environ, {"TERM": "dumb", "NO_COLOR": ""}):
            self.assertFalse(should_use_color())

    def test_get_terminal_width(self):
        width = get_terminal_width(default=80, max_width=88)
        self.assertGreaterEqual(width, 30)
        self.assertLessEqual(width, 88)

    def test_format_citation_header_plain(self):
        hdr = format_citation_header("John 3:16", "WEB", color=False, box=False)
        self.assertEqual(hdr, "=== John 3:16 (WEB) ===")

    def test_format_citation_header_color(self):
        hdr = format_citation_header("John 3:16", "WEB", color=True, theme_name="sacred", box=False)
        self.assertIn("\033[1;33m=== John 3:16", hdr)
        self.assertIn("(WEB)", hdr)
        self.assertIn(RESET, hdr)

    def test_format_citation_header_boxed(self):
        hdr = format_citation_header("John 3:16-17", "WEB", color=False, box=True)
        lines = hdr.split("\n")
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[0].startswith("┌"))
        self.assertTrue(lines[0].endswith("┐"))
        self.assertIn("John 3:16-17 (WEB)", lines[1])
        self.assertTrue(lines[2].startswith("└"))
        self.assertTrue(lines[2].endswith("┘"))

    def test_format_citation_header_fallback_annotation(self):
        hdr = format_citation_header("John 3:16", "WEB", fallback_for="ESV", color=False, box=False)
        self.assertEqual(hdr, "=== John 3:16 (WEB [fallback for ESV]) ===")

    def test_wrap_prefixed_text(self):
        prefix = "[16] "
        text = "This is a sentence designed to be wrapped neatly across multiple lines."
        lines = wrap_prefixed_text(prefix=prefix, text=text, width=30, subsequent_indent="     ")
        self.assertTrue(lines[0].startswith("[16] "))
        self.assertTrue(lines[1].startswith("     "))
        for line in lines:
            self.assertLessEqual(visual_len(line), 30)

    def test_format_scripture_passage_with_margin_and_wrapping(self):
        out = format_scripture_passage(
            [self.v1, self.v2],
            show_verse_numbers=True,
            show_header=True,
            width=50,
            margin=4,
            flow=False,
            color=False,
        )
        lines = out.split("\n")
        # Header present and indented
        self.assertTrue(lines[0].startswith("    === John 3:16-17 (WEB) ==="))
        # Verses indented
        for line in lines[2:]:
            self.assertTrue(line.startswith("    "))
            self.assertLessEqual(len(line), 54)  # 50 width + 4 margin

    def test_format_scripture_passage_flow_mode(self):
        out = format_scripture_passage(
            [self.v1, self.v2],
            show_verse_numbers=True,
            show_header=False,
            width=60,
            margin=2,
            flow=True,
            color=False,
        )
        # Flow mode joins verses into continuous paragraph
        self.assertIn("[16] For God so loved", out)
        self.assertIn("[17] For God didn't send", out)
        for line in out.split("\n"):
            self.assertTrue(line.startswith("  "))
            self.assertLessEqual(len(line), 62)

    def test_format_scripture_passage_theme_amber_and_cyan(self):
        for theme in ["amber", "cyan", "sacred"]:
            out = format_scripture_passage(
                [self.v1],
                show_verse_numbers=True,
                show_header=True,
                color=True,
                theme_name=theme,
            )
            self.assertIn(RESET, out)
            self.assertIn(strip_ansi(out), strip_ansi(out))

    def test_format_aligned_comparison_styled(self):
        comp_data = {
            "WEB": ([self.v1], "WEB", False),
            "ESV": ([self.v1], "WEB", True),
        }
        out = format_aligned_comparison_styled(
            ref_title="John 3:16",
            comparison_data=comp_data,
            show_header=True,
            width=70,
            margin=2,
            color=True,
            theme_name="sacred",
            box_header=True,
        )
        self.assertIn("Compare: John 3:16", out)
        self.assertIn("[WEB]", out)
        self.assertIn("[WEB*]", out)
        self.assertIn("--- John 3:16 ---", out)
        self.assertIn(RESET, out)


if __name__ == "__main__":
    unittest.main()
