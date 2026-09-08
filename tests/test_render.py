"""Hermetic Unit Tests for Slide Rendering Engine (Zero External Dependencies).

Tests pure Python SVG vector rendering and system ImageMagick rasterization.
"""

from __future__ import annotations

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
    wrap_text_balanced,
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

    def test_wrap_text_balanced(self):
        text = "The grace of the Lord Jesus Christ and the love of God and the fellowship of the Holy Spirit be with you all."
        lines = wrap_text_balanced(text, max_width=600.0, font_size=36.0)
        self.assertGreater(len(lines), 1)
        self.assertEqual(" ".join(lines), text)

    def test_balanced_wrapping_eliminates_single_word_orphan(self):
        # A sentence where greedy wrapping might leave one trailing word
        text = "For by grace you have been saved through faith and this is not your own doing"
        greedy_lines = wrap_text_to_width(text, max_width=450.0, font_size=32.0)
        balanced_lines = wrap_text_balanced(text, max_width=450.0, font_size=32.0)

        # Balanced wrapping ensures words are preserved
        self.assertEqual(" ".join(balanced_lines), text)
        # Last line of balanced text should avoid single-word orphan if possible
        if len(balanced_lines) > 1:
            self.assertGreaterEqual(len(balanced_lines[-1].split()), 2)

    def test_font_size_min_max_clamping(self):
        content = SlideContent(text="In the beginning was the Word.", citation="John 1:1")
        # Clamp between 30 and 45 pt
        config = RenderConfig(width=1920, height=1080, min_font_size=30.0, max_font_size=45.0)
        layout = calculate_slide_layout(content, config)
        self.assertLessEqual(layout.font_size, 45.0)
        self.assertGreaterEqual(layout.font_size, 30.0)

    def test_optical_vertical_centering_baseline(self):
        content = SlideContent(text="Peace I leave with you; my peace I give to you.", citation="John 14:27")
        config_45 = RenderConfig(width=1920, height=1080, optical_center_pct=0.45)
        config_50 = RenderConfig(width=1920, height=1080, optical_center_pct=0.50)

        layout_45 = calculate_slide_layout(content, config_45)
        layout_50 = calculate_slide_layout(content, config_50)

        # 45% optical center should position text slightly higher than 50% geometric center
        self.assertLess(layout_45.start_y, layout_50.start_y)

    def test_citation_style_smallcaps_and_none(self):
        content = SlideContent(text="Rejoice always.", citation="1 Thessalonians 5:16", translation="WEB")
        renderer = SvgSlideRenderer()

        # Smallcaps citation
        config_sc = RenderConfig(width=1920, height=1080, citation_style="smallcaps")
        svg_sc = renderer.render_svg_markup(content, config_sc)
        self.assertIn("font-variant: all-small-caps", svg_sc)
        self.assertIn("1 Thessalonians 5:16", svg_sc)

        # None citation
        config_none = RenderConfig(width=1920, height=1080, citation_style="none")
        svg_none = renderer.render_svg_markup(content, config_none)
        self.assertNotIn("class=\"citation-text\"", svg_none)

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


class TestSlideOptionsAndHelpers(unittest.TestCase):
    """Hermetic unit tests for slide options, color normalization, and table helpers."""

    def test_normalize_color(self):
        from core.render import normalize_color
        self.assertIsNone(normalize_color(None))
        self.assertIsNone(normalize_color(""))
        self.assertEqual(normalize_color("gold"), "#D4AF37")
        self.assertEqual(normalize_color("amber"), "#F39C12")
        self.assertEqual(normalize_color("white"), "#FFFFFF")
        self.assertEqual(normalize_color("black"), "#000000")
        self.assertEqual(normalize_color("D4AF37"), "#D4AF37")
        self.assertEqual(normalize_color("#D4AF37"), "#D4AF37")
        self.assertEqual(normalize_color("abc"), "#ABC")
        self.assertEqual(normalize_color("#abc"), "#abc")
        self.assertEqual(normalize_color("rgb(10, 20, 30)"), "rgb(10, 20, 30)")

    def test_list_themes_and_table(self):
        from core.render import list_themes, format_theme_table
        themes = list_themes()
        self.assertEqual(len(themes), 6)
        names = [t.name for t in themes]
        self.assertIn("oled_black", names)
        self.assertIn("charcoal", names)
        self.assertIn("obsidian", names)
        self.assertIn("monastery", names)
        self.assertIn("inverted", names)
        self.assertIn("parchment", names)
        for t in themes:
            self.assertTrue(len(t.description) > 10)

        table_styled = format_theme_table(styling=True)
        self.assertIn("oled_black", table_styled)
        self.assertIn("\033[", table_styled)

        table_plain = format_theme_table(styling=False)
        self.assertIn("oled_black", table_plain)
        self.assertNotIn("\033[", table_plain)

    def test_list_resolutions_and_table(self):
        from core.render import list_resolutions, format_resolution_table
        res_list = list_resolutions()
        self.assertTrue(len(res_list) >= 6)
        res_dict = {name: (w, h, aspect) for name, w, h, aspect, _ in res_list}
        self.assertEqual(res_dict["4k"], (3840, 2160, "16:9"))
        self.assertEqual(res_dict["1080p"], (1920, 1080, "16:9"))
        self.assertEqual(res_dict["720p"], (1280, 720, "16:9"))
        self.assertEqual(res_dict["square"], (1080, 1080, "1:1"))

        table_styled = format_resolution_table(styling=True)
        self.assertIn("3840x2160", table_styled)
        self.assertIn("\033[", table_styled)

        table_plain = format_resolution_table(styling=False)
        self.assertIn("3840x2160", table_plain)
        self.assertNotIn("\033[", table_plain)

    def test_custom_citation_and_accent_colors(self):
        from core.render import SvgSlideRenderer, RenderConfig, SlideContent
        renderer = SvgSlideRenderer()
        config = RenderConfig(
            width=1920,
            height=1080,
            citation_color="#E74C3C",
            accent_color="#2ECC71",
        )
        content = SlideContent(
            text="In the beginning was the Word.",
            citation="John 1:1",
        )
        markup = renderer.render_svg_markup(content, config)
        self.assertIn("fill: #E74C3C", markup)
        self.assertIn("stroke: #2ECC71", markup)

    def test_tags_rendering_on_slide(self):
        from core.render import SvgSlideRenderer, RenderConfig, SlideContent
        renderer = SvgSlideRenderer()
        config = RenderConfig(
            width=1920,
            height=1080,
            show_tags=True,
        )
        content = SlideContent(
            text="For God so loved the world.",
            citation="John 3:16",
            tags=["Gospel", "Sovereign Grace"],
        )
        markup = renderer.render_svg_markup(content, config)
        self.assertIn("Gospel · Sovereign Grace", markup)
        self.assertIn("<!-- Semantic Tags -->", markup)


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
                shell.do_slide(f"John 3:16 -o {out_file} -f svg -r 1080p -t charcoal -c gold --tags")
                self.assertTrue(out_file.exists())
                self.assertIn("Generated 1920x1080 SVG slide", out_buf.getvalue())
                content = out_file.read_text(encoding="utf-8")
                self.assertIn("<svg", content)
                self.assertIn("John 3:16", content)
                self.assertIn("fill: #D4AF37", content)

    def test_shell_slide_list_themes_and_resolutions(self):
        import io
        from cli.shell import BibleShell
        out_buf = io.StringIO()
        shell = BibleShell(stdout=out_buf, color=False)
        with shell:
            shell.do_slide("--list-themes")
            self.assertIn("oled_black", out_buf.getvalue())
            self.assertIn("charcoal", out_buf.getvalue())

            out_buf.truncate(0)
            out_buf.seek(0)
            shell.do_slide("--list-resolutions")
            self.assertIn("3840x2160", out_buf.getvalue())
            self.assertIn("1920x1080", out_buf.getvalue())

    def test_shell_slide_completion(self):
        from cli.shell import BibleShell
        shell = BibleShell(color=False)
        try:
            matches = shell.complete_slide("ol", "/slide John 3:16 -t ol", 23, 25)
            self.assertIn("oled_black", matches)
            c_matches = shell.complete_slide("--ci", "/slide John 3:16 --ci", 23, 27)
            self.assertIn("--citation-color", c_matches)
            t_matches = shell.complete_slide("--list", "/slide --list", 10, 16)
            self.assertIn("--list-themes", t_matches)
            self.assertIn("--list-resolutions", t_matches)
            p_matches = shell.complete_slide("--pag", "/slide John 3:16 --pag", 23, 28)
            self.assertIn("--paginate", p_matches)
            v_matches = shell.complete_slide("--max-v", "/slide John 3:16 --max-v", 23, 30)
            self.assertIn("--max-verses", v_matches)
        finally:
            shell.close()


class TestMultiSlidePagination(unittest.TestCase):
    """Hermetic unit tests for multi-slide passage pagination and sequence rendering."""

    def setUp(self):
        from core.db import Database, DEFAULT_DB_PATH
        from core.reference import parse_reference
        self.db = Database(DEFAULT_DB_PATH)
        self.ref_short = parse_reference("John 3:16")
        self.verses_short, _, _ = self.db.get_verses_with_fallback(self.ref_short)
        self.ref_long = parse_reference("Romans 8:28-39")
        self.verses_long, _, _ = self.db.get_verses_with_fallback(self.ref_long)

    def tearDown(self):
        self.db.close()

    def test_pagination_config_defaults(self):
        from core.render import PaginationConfig
        config = PaginationConfig()
        self.assertTrue(config.enabled)
        self.assertEqual(config.mode, "auto")
        self.assertIsNone(config.max_lines_per_slide)
        self.assertIsNone(config.max_chars_per_slide)
        self.assertIsNone(config.max_verses_per_slide)
        self.assertIsNone(config.min_readability_font_size)
        self.assertEqual(config.indicator_format, "{page} / {total}")
        self.assertTrue(config.show_indicator)
        self.assertTrue(config.sub_citations)
        self.assertFalse(config.keep_parent_citation)

    def test_single_verse_fits_without_pagination(self):
        from core.render import paginate_verses, RenderConfig, PaginationConfig
        config = RenderConfig(width=3840, height=2160)
        pagination = PaginationConfig()
        slides = paginate_verses(self.verses_short, parent_ref=self.ref_short, config=config, pagination=pagination)
        self.assertEqual(len(slides), 1)
        self.assertIsNone(slides[0].page_indicator)
        self.assertEqual(slides[0].citation, "John 3:16")

    def test_long_passage_auto_paginates(self):
        from core.render import paginate_verses, RenderConfig, PaginationConfig
        config = RenderConfig(width=3840, height=2160)
        pagination = PaginationConfig(mode="auto")
        slides = paginate_verses(self.verses_long, parent_ref=self.ref_long, config=config, pagination=pagination)
        self.assertGreater(len(slides), 1)
        # Verify page indicators
        total = len(slides)
        for i, slide in enumerate(slides, start=1):
            self.assertEqual(slide.page_indicator, f"{i} / {total}")
            self.assertTrue(slide.citation.startswith("Romans 8:"))

    def test_sub_citation_accuracy(self):
        from core.render import paginate_verses, RenderConfig, PaginationConfig
        config = RenderConfig(width=3840, height=2160)
        pagination = PaginationConfig(mode="auto", sub_citations=True)
        slides = paginate_verses(self.verses_long, parent_ref=self.ref_long, config=config, pagination=pagination)
        self.assertGreaterEqual(len(slides), 3)
        # First slide starts at verse 28
        self.assertIn("Romans 8:28", slides[0].citation)
        # Last slide ends at verse 39
        self.assertTrue(slides[-1].citation.endswith("39"))

    def test_keep_parent_citation_flag(self):
        from core.render import paginate_verses, RenderConfig, PaginationConfig
        config = RenderConfig(width=3840, height=2160)
        pagination = PaginationConfig(mode="auto", keep_parent_citation=True)
        slides = paginate_verses(self.verses_long, parent_ref=self.ref_long, config=config, pagination=pagination)
        for slide in slides:
            self.assertEqual(slide.citation, "Romans 8:28-39")

    def test_max_verses_per_slide_constraint(self):
        from core.render import paginate_verses, RenderConfig, PaginationConfig
        config = RenderConfig(width=3840, height=2160)
        # 12 verses with max 2 per slide = 6 slides
        pagination = PaginationConfig(max_verses_per_slide=2)
        slides = paginate_verses(self.verses_long, parent_ref=self.ref_long, config=config, pagination=pagination)
        self.assertEqual(len(slides), 6)
        self.assertEqual(slides[0].citation, "Romans 8:28-29")
        self.assertEqual(slides[0].page_indicator, "1 / 6")
        self.assertEqual(slides[-1].citation, "Romans 8:38-39")
        self.assertEqual(slides[-1].page_indicator, "6 / 6")

    def test_custom_page_format_and_suppress_indicator(self):
        from core.render import paginate_verses, RenderConfig, PaginationConfig
        config = RenderConfig(width=3840, height=2160)
        pagination = PaginationConfig(max_verses_per_slide=3, indicator_format="{page} of {total}")
        slides = paginate_verses(self.verses_long, parent_ref=self.ref_long, config=config, pagination=pagination)
        self.assertEqual(slides[0].page_indicator, f"1 of {len(slides)}")

        pagination_no_ind = PaginationConfig(max_verses_per_slide=3, show_indicator=False)
        slides_no_ind = paginate_verses(self.verses_long, parent_ref=self.ref_long, config=config, pagination=pagination_no_ind)
        self.assertIsNone(slides_no_ind[0].page_indicator)

    def test_disabled_pagination_forces_single_slide(self):
        from core.render import paginate_verses, RenderConfig, PaginationConfig
        config = RenderConfig(width=3840, height=2160)
        pagination = PaginationConfig(enabled=False)
        slides = paginate_verses(self.verses_long, parent_ref=self.ref_long, config=config, pagination=pagination)
        self.assertEqual(len(slides), 1)
        self.assertEqual(slides[0].citation, "Romans 8:28-39")
        self.assertIsNone(slides[0].page_indicator)

    def test_paginate_text(self):
        from core.render import paginate_text, RenderConfig, PaginationConfig
        config = RenderConfig(width=3840, height=2160)
        short_text = "Jesus wept."
        slides_short = paginate_text(short_text, citation="John 11:35", config=config)
        self.assertEqual(len(slides_short), 1)
        self.assertIsNone(slides_short[0].page_indicator)

        long_text = " ".join([
            "For I am persuaded, that neither death, nor life, nor angels, nor principalities, nor things present, nor things to come, nor powers, nor height, nor depth, nor any other created thing, will be able to separate us from the love of God, which is in Christ Jesus our Lord.",
            "We know that all things work together for good for those who love God, to those who are called according to his purpose.",
            "For whom he foreknew, he also predestined to be conformed to the image of his Son, that he might be the firstborn among many brothers.",
            "Whom he predestined, those he also called. Whom he called, those he also justified. Whom he justified, those he also glorified.",
            "What then shall we say about these things? If God is for us, who can be against us?",
        ])
        slides_long = paginate_text(long_text, citation="Romans 8", config=config, pagination=PaginationConfig(mode="auto"))
        self.assertGreater(len(slides_long), 1)
        self.assertEqual(slides_long[0].page_indicator, f"1 / {len(slides_long)}")

    def test_render_sequence_to_files(self):
        from core.render import (
            get_default_engine,
            paginate_verses,
            RenderConfig,
            PaginationConfig,
        )
        engine = get_default_engine()
        config = RenderConfig(width=1920, height=1080, output_format="svg")
        pagination = PaginationConfig(max_verses_per_slide=3)
        slides = paginate_verses(self.verses_long, parent_ref=self.ref_long, config=config, pagination=pagination)

        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "presentation_slide.svg"
            results = engine.render_sequence_to_files(slides, destination=out_file, config=config)
            self.assertEqual(len(results), 4)
            for i, res in enumerate(results, start=1):
                expected_path = Path(tmpdir) / f"presentation_slide_{i}.svg"
                self.assertTrue(expected_path.exists())
                self.assertEqual(res.file_path, str(expected_path))
                svg_content = expected_path.read_text(encoding="utf-8")
                self.assertIn(f"{i} / 4", svg_content)
                self.assertIn("<svg", svg_content)

    def test_render_sequence_to_dir(self):
        from core.render import (
            get_default_engine,
            paginate_verses,
            RenderConfig,
            PaginationConfig,
        )
        engine = get_default_engine()
        config = RenderConfig(width=1920, height=1080, output_format="svg")
        pagination = PaginationConfig(mode="verses", max_verses_per_slide=4)
        slides = paginate_verses(self.verses_long, parent_ref=self.ref_long, config=config, pagination=pagination)

        with tempfile.TemporaryDirectory() as tmpdir:
            results = engine.render_sequence_to_dir(slides, destination_dir=tmpdir, file_prefix="romans", config=config)
            self.assertEqual(len(results), 3)
            for i, res in enumerate(results, start=1):
                expected_path = Path(tmpdir) / f"romans_{i}.svg"
                self.assertTrue(expected_path.exists())
                self.assertEqual(res.file_path, str(expected_path))

    def test_render_verse_slides_functional_interface(self):
        from core.render import render_verse_slides, PaginationConfig
        with tempfile.TemporaryDirectory() as tmpdir:
            results = render_verse_slides(
                text_or_verses=self.verses_long,
                parent_ref=self.ref_long,
                output_format="svg",
                resolution="1080p",
                output_dir=tmpdir,
                pagination=PaginationConfig(mode="verses", max_verses_per_slide=4),
            )
            self.assertEqual(len(results), 3)
            for i in range(1, 4):
                p = Path(tmpdir) / f"slide_{i}.svg"
                self.assertTrue(p.exists())


if __name__ == "__main__":
    unittest.main()

