"""Unit tests for Pure Vector SVG Typological Arc Network & Cross-Reference Graph Engine."""

import io
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
import urllib.request

from cli.main import build_parser, preprocess_cli_argv
from cli.shell import BibleShell
from core.arcs import (
    ArcEndpoint,
    ArcNetwork,
    ArcPath,
    ArcTheme,
    BookAxisMark,
    RELATIONSHIP_COLORS,
    build_arc_network,
    get_reference_x,
)
from core.crossref import RelationshipType
from core.db import DEFAULT_DB_PATH, Database
from core.reference import ALL_BOOKS, Book, BOOKS, parse_reference
from web.server import create_server


class TestArcThemeAndColors(unittest.TestCase):
    """Test theme palettes and relationship color mappings."""

    def test_theme_palettes_exist(self) -> None:
        for theme_name in [ArcTheme.OBSIDIAN, ArcTheme.SCRIPTORIUM, ArcTheme.MONASTERY, ArcTheme.TRANSPARENT]:
            palette = ArcTheme.get_palette(theme_name)
            self.assertIn("background", palette)
            self.assertIn("text_primary", palette)
            self.assertIn("axis_line", palette)
            self.assertIn("ot_label", palette)
            self.assertIn("nt_label", palette)

    def test_fallback_palette(self) -> None:
        palette = ArcTheme.get_palette("nonexistent_theme")
        self.assertEqual(palette, ArcTheme.PALETTES[ArcTheme.OBSIDIAN])

    def test_relationship_colors(self) -> None:
        for rel in RelationshipType.ALL:
            self.assertIn(rel, RELATIONSHIP_COLORS)
            self.assertTrue(RELATIONSHIP_COLORS[rel].startswith("#"))


class TestArcGeometryAndLayout(unittest.TestCase):
    """Test geometric positioning and Bézier calculation."""

    def setUp(self) -> None:
        self.db = Database(DEFAULT_DB_PATH)
        self.network = build_arc_network(self.db, width=1200, height=520)

    def tearDown(self) -> None:
        self.db.close()

    def test_canonical_book_marks_count(self) -> None:
        self.assertEqual(len(self.network.book_marks), 66)
        ot_marks = [bm for bm in self.network.book_marks if bm.testament == "OT"]
        nt_marks = [bm for bm in self.network.book_marks if bm.testament == "NT"]
        self.assertEqual(len(ot_marks), 39)
        self.assertEqual(len(nt_marks), 27)

    def test_intertestamental_gap(self) -> None:
        malachi = self.network.book_marks[38]
        matthew = self.network.book_marks[39]
        self.assertEqual(malachi.book.name, "Malachi")
        self.assertEqual(matthew.book.name, "Matthew")
        gap = matthew.x_start - malachi.x_end
        self.assertGreaterEqual(gap, 25.0)

    def test_reference_x_positioning(self) -> None:
        gen1, _ = get_reference_x("Genesis 1:1", self.network.book_marks)
        gen50, _ = get_reference_x("Genesis 50:26", self.network.book_marks)
        rev22, _ = get_reference_x("Revelation 22:21", self.network.book_marks)

        self.assertLess(gen1, gen50)
        self.assertLess(gen50, rev22)

    def test_arc_bezier_path_syntax(self) -> None:
        self.assertGreater(len(self.network.arcs), 0)
        for arc in self.network.arcs:
            self.assertTrue(arc.path_d.startswith("M "))
            self.assertIn(" C ", arc.path_d)
            self.assertGreater(arc.arc_height, 0)
            self.assertGreaterEqual(arc.distance_books, 0)


class TestArcNetworkFilteringAndRendering(unittest.TestCase):
    """Test ArcNetwork filters, serialization, and rendering formats."""

    def setUp(self) -> None:
        self.db = Database(DEFAULT_DB_PATH)

    def tearDown(self) -> None:
        self.db.close()

    def test_full_network(self) -> None:
        net = build_arc_network(self.db)
        self.assertGreaterEqual(net.total_connections, 40)
        self.assertGreater(net.ot_to_nt_count, 35)

    def test_filter_by_relationship_type(self) -> None:
        net = build_arc_network(self.db, relationship_type="typology")
        self.assertGreater(net.total_connections, 15)
        self.assertTrue(all(a.relationship_type == "typology" for a in net.arcs))

    def test_filter_by_book(self) -> None:
        net = build_arc_network(self.db, book_filter="Genesis")
        self.assertGreater(net.total_connections, 10)
        self.assertTrue(all("Genesis" in (a.source.book.name, a.target.book.name) for a in net.arcs))

    def test_render_svg_standalone_and_inline(self) -> None:
        net = build_arc_network(self.db, theme=ArcTheme.OBSIDIAN)
        svg_standalone = net.render_svg(standalone=True)
        self.assertTrue(svg_standalone.startswith('<?xml version="1.0"'))
        self.assertIn('<svg xmlns="http://www.w3.org/2000/svg"', svg_standalone)
        self.assertIn('</svg>', svg_standalone)
        self.assertIn('class="arc-path', svg_standalone)

        svg_inline = net.render_svg(standalone=False)
        self.assertFalse(svg_inline.startswith('<?xml'))
        self.assertTrue(svg_inline.startswith('<svg'))

    def test_to_dict_serialization(self) -> None:
        net = build_arc_network(self.db)
        data = net.to_dict()
        self.assertEqual(data["total_connections"], net.total_connections)
        self.assertEqual(len(data["arcs"]), net.total_connections)
        self.assertEqual(len(data["books"]), 66)

    def test_render_terminal_summary(self) -> None:
        net = build_arc_network(self.db)
        summary_plain = net.render_terminal_summary(color=False)
        self.assertIn("CANONICAL TYPOLOGICAL ARC NETWORK", summary_plain)
        self.assertIn("Total Connections:", summary_plain)
        self.assertIn("OT ➔ NT Fulfillments:", summary_plain)
        self.assertIn("[ LAW ]", summary_plain)
        self.assertIn("[ REVELATION ]", summary_plain)

        summary_color = net.render_terminal_summary(color=True)
        self.assertIn("\033[", summary_color)


class TestArcCliAndShell(unittest.TestCase):
    """Test CLI subcommand and REPL shell integration for typological arcs."""

    def setUp(self) -> None:
        self.parser = build_parser()

    def test_preprocess_cli_argv(self) -> None:
        args = preprocess_cli_argv(["arcs", "--type", "typology"])
        self.assertEqual(args, ["arcs", "--type", "typology"])

        args_alias = preprocess_cli_argv(["arc"])
        self.assertEqual(args_alias, ["arc"])

    def test_cli_arcs_command_plain(self) -> None:
        parsed = self.parser.parse_args(["arcs", "--no-color"])
        self.assertEqual(parsed.func.__name__, "cmd_arcs")

        captured = io.StringIO()
        import sys
        old_stdout = sys.stdout
        try:
            sys.stdout = captured
            ret = parsed.func(parsed)
            self.assertEqual(ret, 0)
        finally:
            sys.stdout = old_stdout

        out = captured.getvalue()
        self.assertIn("CANONICAL TYPOLOGICAL ARC NETWORK", out)

    def test_cli_arcs_json_output(self) -> None:
        parsed = self.parser.parse_args(["arcs", "--json"])
        captured = io.StringIO()
        import sys
        old_stdout = sys.stdout
        try:
            sys.stdout = captured
            ret = parsed.func(parsed)
            self.assertEqual(ret, 0)
        finally:
            sys.stdout = old_stdout

        out = captured.getvalue()
        data = json.loads(out)
        self.assertIn("total_connections", data)
        self.assertIn("arcs", data)

    def test_cli_arcs_svg_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_svg = Path(tmpdir) / "output.svg"
            parsed = self.parser.parse_args(["arcs", "--svg", str(out_svg), "--type", "typology"])
            captured = io.StringIO()
            import sys
            old_stdout = sys.stdout
            try:
                sys.stdout = captured
                ret = parsed.func(parsed)
                self.assertEqual(ret, 0)
            finally:
                sys.stdout = old_stdout
            self.assertTrue(out_svg.exists())
            self.assertGreater(out_svg.stat().st_size, 5000)
            content = out_svg.read_text(encoding="utf-8")
            self.assertIn("<svg", content)
            self.assertIn("Exported pure vector SVG", captured.getvalue())

    def test_shell_arcs_and_autocomplete(self) -> None:
        out_buf = io.StringIO()
        shell = BibleShell(stdout=out_buf, color=False)
        with shell:
            shell.do_arcs("-t typology")
            output = out_buf.getvalue()
            self.assertIn("CANONICAL TYPOLOGICAL ARC NETWORK", output)

            # Autocomplete
            completions = shell.complete_arcs("typo", "/arcs typo", 6, 10)
            self.assertIn("typology", completions)


class TestArcHttpEndpoints(unittest.TestCase):
    """Test HTTP REST and SVG endpoints on ephemeral server."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.db = Database(DEFAULT_DB_PATH, check_same_thread=False)
        cls.server = create_server(host="127.0.0.1", port=0, database=cls.db, verbose=False)
        cls.thread = threading.Thread(target=cls.server.start, daemon=True)
        cls.thread.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.thread.join(timeout=2.0)
        cls.db.close()

    def test_api_crossref_arcs_json(self) -> None:
        url = f"{self.server.url}/api/crossref/arcs"
        with urllib.request.urlopen(url) as resp:
            self.assertEqual(resp.status, 200)
            self.assertTrue(resp.headers["Content-Type"].startswith("application/json"))
            data = json.loads(resp.read().decode("utf-8"))
            self.assertIn("total_connections", data)
            self.assertGreater(data["total_connections"], 40)

    def test_api_crossref_arcs_svg(self) -> None:
        url = f"{self.server.url}/api/crossref/arcs.svg?theme=scriptorium"
        with urllib.request.urlopen(url) as resp:
            self.assertEqual(resp.status, 200)
            self.assertTrue(resp.headers["Content-Type"].startswith("image/svg+xml"))
            svg_text = resp.read().decode("utf-8")
            self.assertIn("<svg", svg_text)
            self.assertIn("</svg>", svg_text)
            self.assertIn('data-theme="scriptorium"', svg_text)

    def test_api_arcs_alias(self) -> None:
        url = f"{self.server.url}/api/arcs?type=prophecy_fulfillment"
        with urllib.request.urlopen(url) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(all(a["relationship_type"] == "prophecy_fulfillment" for a in data["arcs"]))


if __name__ == "__main__":
    unittest.main()
