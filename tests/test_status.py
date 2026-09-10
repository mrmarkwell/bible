"""Hermetic unit tests for core/status.py platform status and executive dashboard engine.

Zero external dependencies (Python 3 standard library only per ADR-003).
"""

import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from core.db import DEFAULT_DB_PATH, Database
from core.status import (
    PlatformStatus,
    format_size,
    format_terminal_dashboard,
    get_platform_status,
)


class TestStatusModule(unittest.TestCase):
    """Hermetic unit tests for platform status aggregation and formatting."""

    def test_format_size(self):
        """Verify human-readable byte sizing across byte, KB, MB, and GB boundaries."""
        self.assertEqual(format_size(100), "100 B")
        self.assertEqual(format_size(2048), "2.0 KB")
        self.assertEqual(format_size(10485760), "10.0 MB")
        self.assertEqual(format_size(1073741824 * 2), "2.00 GB")

    def test_platform_status_to_dict_and_json(self):
        """Verify dataclass serialization to dictionary and JSON string."""
        status = PlatformStatus(
            db_path="/mock/path/bible.db",
            db_exists=True,
            db_size_bytes=1024,
            db_size_str="1.0 KB",
            db_healthy=True,
            total_verses=31103,
            total_books=66,
            translations=[{"id": "WEB", "name": "World English Bible", "language": "eng"}],
            total_pericopes=1304,
            total_cross_references=343598,
            total_tags=26,
            total_typological_arcs=26,
            total_vector_embeddings=1317,
            vector_dim=768,
            active_phase="Phase 7",
            roadmap_completed=94,
            roadmap_total=99,
            roadmap_pct=94.9,
            roadmap_remaining=5,
            sequential_runs=100,
            adrs_registered=108,
            pip_dependencies=0,
            npm_dependencies=0,
            health_status="EXCELLENT (100% Passing)",
            health_checked=True,
        )

        d = status.to_dict()
        self.assertEqual(d["database"]["path"], "/mock/path/bible.db")
        self.assertEqual(d["scripture"]["total_verses"], 31103)
        self.assertEqual(d["knowledge_graph"]["pericopes"], 1304)
        self.assertEqual(d["vector_database"]["total_embeddings"], 1317)
        self.assertEqual(d["roadmap"]["tasks_completed"], 94)
        self.assertEqual(d["governance"]["sequential_runs"], 100)
        self.assertEqual(d["governance"]["pip_dependencies"], 0)

        json_str = status.to_json(indent=2)
        parsed = json.loads(json_str)
        self.assertEqual(parsed["roadmap"]["active_phase"], "Phase 7")
        self.assertEqual(parsed["governance"]["adrs_registered"], 108)

    def test_get_platform_status_bundled(self):
        """Verify real platform status aggregation against bundled database."""
        status = get_platform_status(
            db_path=DEFAULT_DB_PATH,
            check_health=False,  # Keep test fast and hermetic
        )

        self.assertTrue(status.db_exists)
        self.assertGreaterEqual(status.total_verses, 31100)
        self.assertEqual(status.total_books, 66)
        self.assertGreaterEqual(len(status.translations), 1)
        self.assertGreaterEqual(status.total_cross_references, 340000)
        self.assertGreaterEqual(status.total_pericopes, 1300)
        self.assertGreaterEqual(status.total_tags, 20)
        self.assertGreaterEqual(status.total_typological_arcs, 20)
        self.assertGreaterEqual(status.total_vector_embeddings, 1300)
        self.assertGreaterEqual(status.roadmap_completed, 90)
        self.assertGreaterEqual(status.sequential_runs, 90)
        self.assertGreaterEqual(status.adrs_registered, 100)
        self.assertEqual(status.pip_dependencies, 0)
        self.assertEqual(status.npm_dependencies, 0)
        self.assertEqual(status.health_status, "SOVEREIGN (Diagnostics Skipped)")

    def test_get_platform_status_isolated_temp_db(self):
        """Verify platform status on a fresh isolated temporary database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_db = Path(tmpdir) / "empty.db"
            with Database(tmp_db) as db:
                db.conn.execute("INSERT OR REPLACE INTO translations (id, name, language) VALUES ('TEST', 'Test Version', 'eng');")
                db.conn.execute(
                    "INSERT INTO verses (canonical_verse_id, translation_id, book_id, chapter, verse, text, osis_ref) "
                    "VALUES (1001001, 'TEST', 1, 1, 1, 'In the beginning', 'Gen.1.1');"
                )
                db.conn.commit()

            status = get_platform_status(
                db_path=tmp_db,
                check_health=False,
            )
            self.assertTrue(status.db_exists)
            self.assertEqual(status.total_verses, 1)
            self.assertEqual(len(status.translations), 1)
            self.assertEqual(status.translations[0]["id"], "TEST")
            self.assertTrue(status.db_healthy)

    def test_format_terminal_dashboard(self):
        """Verify ANSI dashboard rendering with color enabled and disabled."""
        status = PlatformStatus(
            db_path="/mock/data/bible.db",
            db_exists=True,
            db_size_str="223.6 MB",
            db_healthy=True,
            total_verses=62205,
            total_books=66,
            translations=[{"id": "WEB"}, {"id": "KJV"}],
            total_pericopes=1333,
            total_cross_references=343598,
            total_typological_arcs=26,
            total_vector_embeddings=1317,
            vector_dim=768,
            has_esv_key=True,
            esv_source=".env",
            has_gemini_key=False,
            gemini_source="none",
            active_phase="Phase 7",
            roadmap_completed=94,
            roadmap_total=99,
            roadmap_pct=94.9,
            roadmap_remaining=5,
            sequential_runs=100,
            adrs_registered=108,
            health_status="EXCELLENT (100% Passing)",
        )

        colored = format_terminal_dashboard(status, use_color=True)
        uncolored = format_terminal_dashboard(status, use_color=False)

        # Structure checks
        self.assertIn("Bible Engine — Sovereign Scripture & Semantic Knowledge Platform", colored)
        self.assertIn("Run #100", colored)
        self.assertIn("108 ADRs", colored)
        self.assertIn("62,205 verses", colored)
        self.assertIn("343,598 TSK edges", colored)
        self.assertIn("1,317 vectors", colored)
        self.assertIn("Phase 7", colored)
        self.assertIn("94/99 tasks", colored)
        self.assertIn("Quick Commands", colored)

        # Color codes in colored vs absent in uncolored
        self.assertIn("\033[1;33m", colored)
        self.assertNotIn("\033[1;33m", uncolored)

    def test_cli_status_subcommand(self):
        """Verify CLI ./bible status integration and flags."""
        from cli.main import main

        # Standard terminal output with --no-health
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = main(["status", "--no-health"])
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn("Bible Engine — Sovereign Scripture", out)
        self.assertIn("SCRIPTURE & KNOWLEDGE CANON", out)

        # JSON output with --json --no-health
        buf_json = io.StringIO()
        with patch("sys.stdout", buf_json):
            code_json = main(["status", "--json", "--no-health"])
        self.assertEqual(code_json, 0)
        data = json.loads(buf_json.getvalue())
        self.assertIn("scripture", data)
        self.assertIn("vector_database", data)
        self.assertIn("roadmap", data)
        self.assertEqual(data["scripture"]["total_books"], 66)

    def test_shell_status_command(self):
        """Verify interactive REPL /status command and aliases."""
        from cli.shell import BibleShell

        out_buf = io.StringIO()
        shell = BibleShell(stdout=out_buf, color=False)

        # Execute /status --no-health
        shell.do_status("--no-health")
        output = out_buf.getvalue()
        self.assertIn("Bible Engine — Sovereign Scripture", output)
        self.assertIn("SEMANTIC & VECTOR ENGINE", output)

        # Execute /status --json --no-health
        out_json_buf = io.StringIO()
        shell_json = BibleShell(stdout=out_json_buf, color=False)
        shell_json.do_status("--json --no-health")
        json_data = json.loads(out_json_buf.getvalue())
        self.assertEqual(json_data["governance"]["pip_dependencies"], 0)

        # Tab completion
        completions = shell.complete_status("--", "/status --", 8, 10)
        self.assertIn("--json", completions)
        self.assertIn("--no-health", completions)

    def test_server_status_endpoint(self):
        """Verify REST API /api/status endpoint response."""
        from web.server import BibleRequestHandler

        handler = BibleRequestHandler.__new__(BibleRequestHandler)
        handler.headers = {}
        handler.verbose = False
        sent_json = None

        def mock_send_json(data, status=200):
            nonlocal sent_json
            sent_json = (data, status)

        handler.db = Database(DEFAULT_DB_PATH)
        handler.send_json = mock_send_json
        handler.handle_status({"no_health": ["1"]})

        self.assertIsNotNone(sent_json)
        data, code = sent_json
        self.assertEqual(code, 200)
        self.assertIn("scripture", data)
        self.assertIn("knowledge_graph", data)
        self.assertIn("vector_database", data)
        self.assertEqual(data["scripture"]["total_books"], 66)


if __name__ == "__main__":
    unittest.main()
