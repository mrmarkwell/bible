"""Hermetic Unit Tests for Slide Rendering Engine (Zero External Dependencies).

Tests pure Python SVG vector rendering and system ImageMagick rasterization.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.render import (
    ImageMagickNotFoundError,
    ImageMagickSlideRenderer,
    LayoutBox,
    RenderConfig,
    RenderError,
    RenderResult,
    SlideContent,
    SlideRenderEngine,
    SlideTheme,
    SvgSlideRenderer,
    STANDARD_THEMES,
    calculate_slide_layout,
    detect_imagemagick,
    estimate_char_width,
    find_imagemagick_binary,
    get_available_backends,
    get_default_engine,
    get_theme,
    is_imagemagick_available,
    parse_resolution,
    render_verse_slide,
    wrap_text_to_width,
)


class TestThemesAndResolutions(unittest.TestCase):
    """Test theme resolution and dimension parsing."""

    def test_standard_themes_exist(self):
        for key in ("oled_black", "charcoal", "obsidian", "monastery", "inverted", "parchment"):
            self.assertIn(key, STANDARD_THEMES)
            theme = STANDARD_THEMES[key]
            self.assertTrue(theme.background_color.startswith("#"))
            self.assertTrue(theme.text_color.startswith("#"))
            self.assertTrue(theme.citation_color.startswith("#"))

    def test_theme_aliases_and_lookups(self):
        self.assertEqual(get_theme("black").name, "oled_black")
        self.assertEqual(get_theme("oled").name, "oled_black")
        self.assertEqual(get_theme("dark").name, "charcoal")
        self.assertEqual(get_theme("white").name, "inverted")
        self.assertEqual(get_theme("light").name, "inverted")
        self.assertEqual(get_theme("sepia").name, "parchment")
        self.assertEqual(get_theme("gold").name, "obsidian")
        # Direct theme instance
        custom = SlideTheme("custom", "#111", "#222", "#333", "#444", "#555", "#666")
        self.assertEqual(get_theme(custom), custom)
        # Unknown fallback
        self.assertEqual(get_theme("unknown_theme_123").name, "oled_black")

    def test_resolution_presets(self):
        self.assertEqual(parse_resolution("4k"), (3840, 2160))
        self.assertEqual(parse_resolution("uhd"), (3840, 2160))
        self.assertEqual(parse_resolution("1080p"), (1920, 1080))
        self.assertEqual(parse_resolution("fhd"), (1920, 1080))
        self.assertEqual(parse_resolution("720p"), (1280, 720))
        self.assertEqual(parse_resolution("square"), (1080, 1080))
        self.assertEqual(parse_resolution("instagram"), (1080, 1080))
        self.assertEqual(parse_resolution("portrait_1080p"), (1080, 1920))

    def test_custom_resolution_parsing(self):
        self.assertEqual(parse_resolution("2560x1440"), (2560, 1440))
        self.assertEqual(parse_resolution("1920X1200"), (1920, 1200))
        self.assertEqual(parse_resolution("800,600"), (800, 600))
        self.assertEqual(parse_resolution((1280, 720)), (1280, 720))
        self.assertEqual(parse_resolution([1024, 768]), (1024, 768))
        # Malformed fallback
        self.assertEqual(parse_resolution("invalid"), (3840, 2160))


class TestLayoutAndTypography(unittest.TestCase):
    """Test text wrapping, bounding box calculations, and font scaling."""

    def test_estimate_char_width(self):
        w_narrow = estimate_char_width("i", 100.0)
        w_wide = estimate_char_width("W", 100.0)
        w_normal = estimate_char_width("a", 100.0)
        self.assertLess(w_narrow, w_normal)
        self.assertLess(w_normal, w_wide)

    def test_wrap_text_to_width(self):
        text = "For God so loved the world that he gave his only Son"
        lines = wrap_text_to_width(text, max_width=500.0, font_size=40.0)
        self.assertGreater(len(lines), 1)
        # Ensure all original words are preserved
        reconstructed = " ".join(lines)
        self.assertEqual(reconstructed, text)

    def test_wrap_text_with_newlines(self):
        text = "First paragraph line.\n\nSecond paragraph line."
        lines = wrap_text_to_width(text, max_width=2000.0, font_size=40.0)
        self.assertIn("First paragraph line.", lines)
        self.assertIn("Second paragraph line.", lines)
        self.assertIn("", lines)

    def test_calculate_slide_layout_short_verse(self):
        content = SlideContent(text="Jesus wept.", citation="John 11:35")
        config = RenderConfig(width=3840, height=2160)
        layout = calculate_slide_layout(content, config)

        self.assertIsInstance(layout, LayoutBox)
        # Short verse should receive generous font size
        self.assertGreaterEqual(layout.font_size, 80.0)
        self.assertGreater(layout.start_y, layout.safe_y)
        self.assertLess(layout.start_y + layout.total_content_height, layout.safe_y + layout.safe_h)

    def test_calculate_slide_layout_long_passage(self):
        text = (
            "We know that all things work together for good for those who love God, "
            "to those who are called according to his purpose. For whom he foreknew, "
            "he also predestined to be conformed to the image of his Son, that he might "
            "be the firstborn among many brothers. Whom he predestined, those he also called. "
            "Whom he called, those he also justified. Whom he justified, those he also glorified."
        )
        content = SlideContent(text=text, citation="Romans 8:28-30")
        config = RenderConfig(width=3840, height=2160)
        layout = calculate_slide_layout(content, config)

        self.assertIsInstance(layout, LayoutBox)
        # Font size scales down to fit comfortably
        self.assertLess(layout.font_size, 80.0)
        self.assertGreaterEqual(layout.font_size, 36.0)
        self.assertGreaterEqual(len(layout.wrapped_lines), 4)

    def test_fixed_font_size_override(self):
        content = SlideContent(text="In the beginning", citation="Genesis 1:1")
        config = RenderConfig(width=1920, height=1080, font_size=55.0)
        layout = calculate_slide_layout(content, config)
        self.assertEqual(layout.font_size, 55.0)


class TestSvgSlideRenderer(unittest.TestCase):
    """Test vector SVG slide generation."""

    def setUp(self):
        self.renderer = SvgSlideRenderer()

    def test_render_svg_markup_basic(self):
        content = SlideContent(
            text="The Lord is my shepherd; I shall not want.",
            citation="Psalm 23:1",
            translation="WEB",
        )
        config = RenderConfig(width=1920, height=1080, theme="oled_black")
        markup = self.renderer.render_svg_markup(content, config)

        self.assertTrue(markup.startswith('<svg xmlns="http://www.w3.org/2000/svg"'))
        self.assertTrue(markup.endswith("</svg>"))
        self.assertIn('viewBox="0 0 1920 1080"', markup)
        self.assertIn('fill="#000000"', markup)
        self.assertIn("The Lord is my shepherd", markup)
        self.assertIn("Psalm 23:1", markup)
        self.assertIn("(WEB)", markup)
        self.assertIn('class="accent-rule"', markup)

    def test_render_svg_with_pericope_and_page_indicator(self):
        content = SlideContent(
            text="In the beginning was the Word, and the Word was with God.",
            citation="John 1:1",
            pericope_title="The Word Made Flesh",
            page_indicator="1 / 3",
            tags=["Christology", "Creation"],
        )
        config = RenderConfig(width=3840, height=2160, show_tags=True)
        markup = self.renderer.render_svg_markup(content, config)

        self.assertIn("THE WORD MADE FLESH", markup)
        self.assertIn("1 / 3", markup)
        self.assertIn("Christology · Creation", markup)

    def test_render_svg_xml_escaping(self):
        content = SlideContent(
            text="He said, 'Give <justice> to the weak & fatherless.'",
            citation="Psalm 82:3",
        )
        config = RenderConfig(width=1920, height=1080)
        markup = self.renderer.render_svg_markup(content, config)

        self.assertIn("&lt;justice&gt;", markup)
        self.assertIn("&amp;", markup)
        self.assertNotIn("<justice>", markup)

    def test_render_svg_alignments(self):
        content = SlideContent(text="Peace I leave with you.", citation="John 14:27")
        for align in ("center", "left", "right"):
            config = RenderConfig(text_align=align)
            markup = self.renderer.render_svg_markup(content, config)
            expected_anchor = "middle" if align == "center" else ("start" if align == "left" else "end")
            self.assertIn(f"text-anchor: {expected_anchor}", markup)

    def test_render_svg_result_object(self):
        content = SlideContent(text="Faith hope and love", citation="1 Cor 13:13")
        config = RenderConfig(width=1920, height=1080)
        res = self.renderer.render(content, config)

        self.assertIsInstance(res, RenderResult)
        self.assertEqual(res.mime_type, "image/svg+xml")
        self.assertEqual(res.format, "svg")
        self.assertEqual(res.width, 1920)
        self.assertEqual(res.height, 1080)
        self.assertEqual(res.backend, "svg")
        self.assertIn(b"<svg", res.data)


class TestImageMagickRenderer(unittest.TestCase):
    """Test ImageMagick raster rendering backend."""

    def test_binary_detection(self):
        bin_path = find_imagemagick_binary()
        is_avail = is_imagemagick_available()
        has_bin, detected_bin = detect_imagemagick()

        self.assertEqual(is_avail, bin_path is not None)
        self.assertEqual(has_bin, is_avail)
        self.assertEqual(detected_bin, bin_path)

        backends = get_available_backends()
        self.assertIn("svg", backends)
        if is_avail:
            self.assertIn("imagemagick", backends)

    def test_missing_binary_raises_error(self):
        with patch("core.render.find_imagemagick_binary", return_value=None):
            with self.assertRaises(ImageMagickNotFoundError):
                ImageMagickSlideRenderer(binary_path=None)

    def test_real_rasterization_if_available(self):
        if not is_imagemagick_available():
            self.skipTest("ImageMagick binary not available on host system")

        renderer = ImageMagickSlideRenderer()
        content = SlideContent(
            text="Grace and peace be multiplied to you.",
            citation="2 Peter 1:2",
            translation="WEB",
        )

        # 1. Test PNG rendering
        config_png = RenderConfig(width=1280, height=720, output_format="png", dpi=150)
        res_png = renderer.render(content, config_png)
        self.assertEqual(res_png.mime_type, "image/png")
        self.assertEqual(res_png.format, "png")
        self.assertEqual(res_png.backend, "imagemagick")
        # Check standard PNG magic signature
        self.assertTrue(res_png.data.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertGreater(len(res_png.data), 1000)

        # 2. Test JPG rendering
        config_jpg = RenderConfig(width=1280, height=720, output_format="jpg", jpeg_quality=90, dpi=150)
        res_jpg = renderer.render(content, config_jpg)
        self.assertEqual(res_jpg.mime_type, "image/jpeg")
        self.assertEqual(res_jpg.format, "jpg")
        # Check JPEG SOI marker
        self.assertTrue(res_jpg.data.startswith(b"\xff\xd8\xff"))
        self.assertGreater(len(res_jpg.data), 1000)

    def test_subprocess_failure_handling(self):
        renderer = ImageMagickSlideRenderer(binary_path="/fake/magick")
        content = SlideContent(text="Test")
        config = RenderConfig(output_format="png")

        # Simulate failed process
        mock_proc = MagicMock(returncode=1, stderr="Invalid font family")
        with patch("subprocess.run", return_value=mock_proc):
            with self.assertRaises(RenderError) as ctx:
                renderer.render(content, config)
            self.assertIn("ImageMagick failed (code 1)", str(ctx.exception))


class TestSlideRenderEngine(unittest.TestCase):
    """Test unified SlideRenderEngine facade and file operations."""

    def setUp(self):
        self.engine = SlideRenderEngine()

    def test_singleton_engine(self):
        e1 = get_default_engine()
        e2 = get_default_engine()
        self.assertIs(e1, e2)

    def test_render_svg_explicit(self):
        content = SlideContent(text="Rejoice always", citation="1 Thess 5:16")
        config = RenderConfig(backend="svg", output_format="svg")
        res = self.engine.render(content, config)
        self.assertEqual(res.format, "svg")
        self.assertEqual(res.backend, "svg")

    def test_render_to_file_svg(self):
        content = SlideContent(text="Pray without ceasing", citation="1 Thess 5:17")
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "output.svg"
            res = self.engine.render_to_file(content, out_file)
            self.assertTrue(out_file.exists())
            self.assertGreater(out_file.stat().st_size, 100)
            self.assertEqual(res.file_path, str(out_file))

    def test_render_to_file_raster(self):
        if not is_imagemagick_available():
            self.skipTest("ImageMagick not available")

        content = SlideContent(text="In everything give thanks", citation="1 Thess 5:18")
        with tempfile.TemporaryDirectory() as tmpdir:
            png_file = Path(tmpdir) / "slide.png"
            config = RenderConfig(width=1280, height=720, output_format="png", dpi=150)
            res = self.engine.render_to_file(content, png_file, config)
            self.assertTrue(png_file.exists())
            self.assertTrue(png_file.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))

    def test_convenience_render_verse_slide(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "verse.svg"
            res = render_verse_slide(
                text="The Lord bless you and keep you.",
                citation="Numbers 6:24",
                theme="monastery",
                resolution="1080p",
                output_format="svg",
                output_path=dest,
            )
            self.assertTrue(dest.exists())
            self.assertEqual(res.width, 1920)
            self.assertEqual(res.height, 1080)
            self.assertIn(b"Numbers 6:24", res.data)


class TestShellSlideCommands(unittest.TestCase):
    """Test interactive REPL /slide command integration."""

    def test_shell_slide_svg_generation(self):
        import io
        from cli.shell import BibleShell
        out_buf = io.StringIO()
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "repl_slide.svg"
            shell = BibleShell(stdout=out_buf, color=False)
            with shell:
                shell.do_slide(f"John 3:16 -o {out_file} -f svg -r 1080p -t charcoal")
                self.assertTrue(out_file.exists())
                self.assertIn("Generated 1920x1080 SVG slide", out_buf.getvalue())
                content = out_file.read_text(encoding="utf-8")
                self.assertIn("<svg", content)
                self.assertIn("John 3:16", content)

    def test_shell_slide_completion(self):
        from cli.shell import BibleShell
        shell = BibleShell(color=False)
        matches = shell.complete_slide("ol", "/slide John 3:16 -t ol", 23, 25)
        self.assertIn("oled_black", matches)


if __name__ == "__main__":
    unittest.main()
